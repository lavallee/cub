"""
Integration tests for the unified tool execution runtime.

Tests the complete flow: discover → adopt → execute → learn
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cub.core.tools.approvals import ApprovalService
from cub.core.tools.execution import ExecutionService
from cub.core.tools.metrics import MetricsStore
from cub.core.tools.models import (
    AdapterType,
    AuthConfig,
    FreedomLevel,
    HTTPConfig,
    ToolConfig,
    ToolResult,
)
from cub.core.tools.registry import RegistryService, RegistryStore


class TestFullFlowWithApprovals:
    """Test complete flow with approval system integration."""

    @pytest.mark.asyncio
    async def test_low_freedom_requires_approval(self, tmp_path: Path) -> None:
        """
        Test LOW freedom level requires approval for all tools.

        Flow:
        1. Set freedom level to LOW
        2. Try to execute a tool
        3. Should raise ToolApprovalRequiredError
        """
        # Setup approval service with LOW freedom
        approvals_file = tmp_path / "approvals.json"
        approval_service = ApprovalService(approvals_file)
        approval_service.set_freedom_level(FreedomLevel.LOW)
        approval_service.save()

        # Setup execution service
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir,
            approval_service=approval_service,
        )

        # Mock adapter
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="test-tool",
            action="search",
            success=True,
            output={"results": []},
            started_at=datetime.now(timezone.utc),
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Should raise approval required error
            from cub.core.tools.exceptions import ToolApprovalRequiredError

            with pytest.raises(ToolApprovalRequiredError) as exc_info:
                await service.execute(
                    tool_id="test-tool",
                    action="search",
                    adapter_type="http",
                    params={},
                    timeout=30.0,
                )

            assert "test-tool" in str(exc_info.value)
            assert "low" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_high_freedom_executes_without_approval(self, tmp_path: Path) -> None:
        """
        Test HIGH freedom level executes tools without approval.

        Flow:
        1. Set freedom level to HIGH
        2. Execute a tool
        3. Should succeed without requiring approval
        """
        # Setup approval service with HIGH freedom
        approvals_file = tmp_path / "approvals.json"
        approval_service = ApprovalService(approvals_file)
        approval_service.set_freedom_level(FreedomLevel.HIGH)
        approval_service.save()

        # Setup execution service
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir,
            approval_service=approval_service,
        )

        # Mock adapter
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="test-tool",
            action="search",
            success=True,
            output={"results": ["item1", "item2"]},
            started_at=datetime.now(timezone.utc),
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Should execute successfully
            result = await service.execute(
                tool_id="test-tool",
                action="search",
                adapter_type="http",
                params={},
                timeout=30.0,
            )

            assert result.success is True
            assert result.output == {"results": ["item1", "item2"]}
            mock_adapter.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_medium_freedom_allows_safe_tools(self, tmp_path: Path) -> None:
        """
        Test MEDIUM freedom level allows safe tools without approval.

        Flow:
        1. Set freedom level to MEDIUM
        2. Mark a tool as safe
        3. Execute the safe tool
        4. Should succeed without requiring approval
        """
        # Setup approval service with MEDIUM freedom
        approvals_file = tmp_path / "approvals.json"
        approval_service = ApprovalService(approvals_file)
        approval_service.set_freedom_level(FreedomLevel.MEDIUM)
        approval_service.mark_safe("safe-tool")
        approval_service.save()

        # Setup execution service
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir,
            approval_service=approval_service,
        )

        # Mock adapter
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="safe-tool",
            action="read",
            success=True,
            output={"data": "content"},
            started_at=datetime.now(timezone.utc),
            duration_ms=50,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Should execute successfully
            result = await service.execute(
                tool_id="safe-tool",
                action="read",
                adapter_type="http",
                params={},
                timeout=30.0,
            )

            assert result.success is True
            assert result.output == {"data": "content"}

    @pytest.mark.asyncio
    async def test_medium_freedom_blocks_risky_tools(self, tmp_path: Path) -> None:
        """
        Test MEDIUM freedom level requires approval for risky tools.

        Flow:
        1. Set freedom level to MEDIUM
        2. Mark a tool as risky
        3. Try to execute the risky tool
        4. Should raise ToolApprovalRequiredError
        """
        # Setup approval service with MEDIUM freedom
        approvals_file = tmp_path / "approvals.json"
        approval_service = ApprovalService(approvals_file)
        approval_service.set_freedom_level(FreedomLevel.MEDIUM)
        approval_service.mark_risky("risky-tool")
        approval_service.save()

        # Setup execution service
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir,
            approval_service=approval_service,
        )

        # Should raise approval required error
        from cub.core.tools.exceptions import ToolApprovalRequiredError

        with pytest.raises(ToolApprovalRequiredError) as exc_info:
            await service.execute(
                tool_id="risky-tool",
                action="delete",
                adapter_type="http",
                params={},
                timeout=30.0,
            )

        assert "risky-tool" in str(exc_info.value)
        assert "medium" in str(exc_info.value).lower()


class TestFullFlowWithRegistry:
    """Test complete flow with registry integration."""

    @pytest.mark.asyncio
    async def test_discover_adopt_execute_flow(self, tmp_path: Path) -> None:
        """
        Test full flow: discover → adopt → execute.

        Flow:
        1. Create a tool definition in registry
        2. Adopt the tool
        3. Execute the tool
        4. Verify execution succeeds
        """
        # Setup registry
        registry_file = tmp_path / "registry.json"
        registry_store = RegistryStore(registry_file)
        registry_service = RegistryService(
            user_store=registry_store,
            project_store=registry_store,
        )

        # Discover: Add a tool to registry
        tool_config = ToolConfig(
            id="discovered-tool",
            name="Discovered Tool",
            adapter_type=AdapterType.HTTP,
            capabilities=["search"],
            http_config=HTTPConfig(
                base_url="https://api.example.com",
                endpoints={"search": "/v1/search"},
                headers={"Accept": "application/json"},
            ),
            auth=AuthConfig(
                required=False,
                env_var="TEST_API_KEY",
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        registry_service.adopt(tool_config)

        # Verify tool was added
        registry = registry_service.load()
        assert len(registry.tools) == 1
        assert "discovered-tool" in registry.tools
        assert registry.tools["discovered-tool"].name == "Discovered Tool"

        # Setup execution service with registry
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir,
            registry_service=registry_service,
        )

        # Mock adapter for execution
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="discovered-tool",
            action="search",
            success=True,
            output={"results": [{"id": 1, "title": "Result"}]},
            started_at=datetime.now(timezone.utc),
            duration_ms=200,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Execute: Run the adopted tool
            result = await service.execute(
                tool_id="discovered-tool",
                action="search",
                adapter_type="http",
                params={"query": "test"},
                timeout=30.0,
            )

            assert result.success is True
            assert result.tool_id == "discovered-tool"
            assert result.output["results"][0]["title"] == "Result"


class TestFullFlowWithMetrics:
    """Test complete flow with metrics/learning integration."""

    @pytest.mark.asyncio
    async def test_execute_and_learn_success(self, tmp_path: Path) -> None:
        """
        Test execute → learn flow for successful execution.

        Flow:
        1. Execute a tool successfully
        2. Verify metrics are recorded
        3. Check success rate is 100%
        """
        # Setup metrics store
        metrics_file = tmp_path / "metrics.json"
        metrics_store = MetricsStore(metrics_file)

        # Setup execution service
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir,
            metrics_store=metrics_store,
        )

        # Mock successful execution
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="learning-tool",
            action="search",
            success=True,
            output={"data": "result"},
            started_at=datetime.now(timezone.utc),
            duration_ms=150,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            result = await service.execute(
                tool_id="learning-tool",
                action="search",
                adapter_type="http",
                params={},
                timeout=30.0,
            )

            assert result.success is True

        # Learn: Verify metrics were recorded
        metrics = metrics_store.get("learning-tool")
        assert metrics is not None
        assert metrics.tool_id == "learning-tool"
        assert metrics.invocations == 1
        assert metrics.successes == 1
        assert metrics.success_rate() == 100.0
        assert metrics.avg_duration_ms == 150.0

    @pytest.mark.asyncio
    async def test_execute_and_learn_failure(self, tmp_path: Path) -> None:
        """
        Test execute → learn flow for failed execution.

        Flow:
        1. Execute a tool that fails
        2. Verify failure metrics are recorded
        3. Check error tracking works
        """
        # Setup metrics store
        metrics_file = tmp_path / "metrics.json"
        metrics_store = MetricsStore(metrics_file)

        # Setup execution service
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir,
            metrics_store=metrics_store,
        )

        # Mock failed execution
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="failing-tool",
            action="search",
            success=False,
            output={},
            error="API key invalid",
            error_type="auth",
            started_at=datetime.now(timezone.utc),
            duration_ms=50,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            result = await service.execute(
                tool_id="failing-tool",
                action="search",
                adapter_type="http",
                params={},
                timeout=30.0,
            )

            assert result.success is False

        # Learn: Verify failure metrics were recorded
        metrics = metrics_store.get("failing-tool")
        assert metrics is not None
        assert metrics.invocations == 1
        assert metrics.successes == 0
        assert metrics.success_rate() == 0.0
        assert "auth" in metrics.error_types
        assert metrics.error_types["auth"] == 1

    @pytest.mark.asyncio
    async def test_execute_and_learn_mixed_results(self, tmp_path: Path) -> None:
        """
        Test execute → learn with mixed success/failure results.

        Flow:
        1. Execute tool multiple times with varying results
        2. Verify metrics aggregate correctly
        3. Check success rate calculation
        """
        # Setup metrics store
        metrics_file = tmp_path / "metrics.json"
        metrics_store = MetricsStore(metrics_file)

        # Setup execution service
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir,
            metrics_store=metrics_store,
        )

        # Mock adapter with varying results
        mock_adapter = Mock()

        # First execution: success
        mock_result_1 = ToolResult(
            tool_id="mixed-tool",
            action="search",
            success=True,
            output={"data": "result1"},
            started_at=datetime.now(timezone.utc),
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )

        # Second execution: failure
        mock_result_2 = ToolResult(
            tool_id="mixed-tool",
            action="search",
            success=False,
            output={},
            error="Timeout",
            error_type="timeout",
            started_at=datetime.now(timezone.utc),
            duration_ms=5000,
            adapter_type=AdapterType.HTTP,
        )

        # Third execution: success
        mock_result_3 = ToolResult(
            tool_id="mixed-tool",
            action="search",
            success=True,
            output={"data": "result3"},
            started_at=datetime.now(timezone.utc),
            duration_ms=150,
            adapter_type=AdapterType.HTTP,
        )

        mock_adapter.execute = AsyncMock(
            side_effect=[mock_result_1, mock_result_2, mock_result_3]
        )

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Execute three times
            await service.execute(
                tool_id="mixed-tool",
                action="search",
                adapter_type="http",
                params={},
                timeout=30.0,
            )
            await service.execute(
                tool_id="mixed-tool",
                action="search",
                adapter_type="http",
                params={},
                timeout=30.0,
            )
            await service.execute(
                tool_id="mixed-tool",
                action="search",
                adapter_type="http",
                params={},
                timeout=30.0,
            )

        # Learn: Verify aggregated metrics
        metrics = metrics_store.get("mixed-tool")
        assert metrics is not None
        assert metrics.invocations == 3
        assert metrics.successes == 2
        assert metrics.success_rate() == pytest.approx(66.67, rel=0.01)
        assert "timeout" in metrics.error_types
        assert metrics.error_types["timeout"] == 1


class TestEndToEndFlow:
    """Test complete end-to-end flow with all components."""

    @pytest.mark.asyncio
    async def test_complete_flow_discover_adopt_approve_execute_learn(
        self, tmp_path: Path
    ) -> None:
        """
        Test complete end-to-end flow with all components integrated.

        Flow:
        1. Discover: Add tool to registry
        2. Adopt: Register tool definition
        3. Approve: Mark tool as safe
        4. Execute: Run the tool
        5. Learn: Verify metrics are recorded
        """
        # Setup all services
        registry_file = tmp_path / "registry.json"
        approvals_file = tmp_path / "approvals.json"
        metrics_file = tmp_path / "metrics.json"
        artifact_dir = tmp_path / "artifacts"

        # 1. Discover: Create registry with tool
        registry_store = RegistryStore(registry_file)
        registry_service = RegistryService(
            user_store=registry_store,
            project_store=registry_store,
        )

        tool_config = ToolConfig(
            id="complete-tool",
            name="Complete Tool",
            adapter_type=AdapterType.HTTP,
            capabilities=["execute"],
            http_config=HTTPConfig(
                base_url="https://api.example.com",
                endpoints={"execute": "/v1/execute"},
                headers={"Accept": "application/json"},
            ),
            auth=AuthConfig(
                required=False,
                env_var="TEST_API_KEY",
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )

        # 2. Adopt: Add tool to registry
        registry_service.adopt(tool_config)
        registry = registry_service.load()
        assert len(registry.tools) == 1

        # 3. Approve: Setup approvals and mark tool as safe
        approval_service = ApprovalService(approvals_file)
        approval_service.set_freedom_level(FreedomLevel.MEDIUM)
        approval_service.mark_safe("complete-tool")
        approval_service.save()

        # Verify approval configuration
        assert approval_service.get_freedom_level() == FreedomLevel.MEDIUM
        assert "complete-tool" in approval_service.get_safe_tools()
        assert not approval_service.requires_approval("complete-tool", "execute")

        # Setup metrics store
        metrics_store = MetricsStore(metrics_file)

        # Setup execution service with all components
        service = ExecutionService(
            artifact_dir=artifact_dir,
            registry_service=registry_service,
            approval_service=approval_service,
            metrics_store=metrics_store,
        )

        # Mock successful execution
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="complete-tool",
            action="execute",
            success=True,
            output={"status": "completed", "data": [1, 2, 3]},
            started_at=datetime.now(timezone.utc),
            duration_ms=250,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # 4. Execute: Run the tool
            result = await service.execute(
                tool_id="complete-tool",
                action="execute",
                adapter_type="http",
                params={"input": "test"},
                timeout=30.0,
                save_artifact=True,
            )

            # Verify execution succeeded
            assert result.success is True
            assert result.tool_id == "complete-tool"
            assert result.action == "execute"
            assert result.output["status"] == "completed"
            assert result.artifact_path is not None

            # Verify artifact was saved
            artifact_path = Path(result.artifact_path)
            assert artifact_path.exists()
            assert artifact_path.parent == artifact_dir

        # 5. Learn: Verify metrics were recorded
        metrics = metrics_store.get("complete-tool")
        assert metrics is not None
        assert metrics.tool_id == "complete-tool"
        assert metrics.invocations == 1
        assert metrics.successes == 1
        assert metrics.success_rate() == 100.0
        assert metrics.avg_duration_ms == 250.0
        assert metrics.last_used_at is not None

        # Verify registry still has the tool
        registry = registry_service.load()
        assert len(registry.tools) == 1
        assert "complete-tool" in registry.tools
        assert registry.tools["complete-tool"].name == "Complete Tool"

        # Verify approvals still configured correctly
        assert not approval_service.requires_approval("complete-tool", "execute")
