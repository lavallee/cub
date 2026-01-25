"""
Tests for ExecutionService integration with RegistryService.

Tests the adopt-before-execute flow, ensuring tools must be in the registry
before they can be executed.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cub.core.tools.exceptions import ToolNotAdoptedError
from cub.core.tools.execution import ExecutionService
from cub.core.tools.models import (
    AdapterType,
    AuthConfig,
    HTTPConfig,
    ToolConfig,
    ToolResult,
)
from cub.core.tools.registry import RegistryService, RegistryStore


class TestExecutionServiceWithRegistry:
    """Test ExecutionService with RegistryService integration."""

    @pytest.mark.asyncio
    async def test_execute_tool_not_adopted_raises_error(self, tmp_path):
        """Test that executing a non-adopted tool raises ToolNotAdoptedError."""
        # Create registry service with empty registry
        registry_store = RegistryStore(tmp_path / "registry.json")
        registry_service = RegistryService(
            user_store=registry_store, project_store=registry_store
        )

        # Create execution service with registry
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir, registry_service=registry_service
        )

        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.execute = AsyncMock()

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Attempt to execute non-adopted tool
            with pytest.raises(ToolNotAdoptedError) as exc_info:
                await service.execute(
                    tool_id="unapproved-tool",
                    action="search",
                    adapter_type="http",
                    params={"query": "test"},
                    timeout=30.0,
                )

        # Verify exception details
        assert exc_info.value.tool_id == "unapproved-tool"
        assert "not adopted" in str(exc_info.value).lower()
        assert "cub tools adopt" in str(exc_info.value)

        # Verify adapter was never called
        mock_adapter.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_adopted_tool_succeeds(self, tmp_path):
        """Test that executing an adopted tool succeeds."""
        # Create registry and adopt a tool
        registry_store = RegistryStore(tmp_path / "registry.json")
        registry_service = RegistryService(
            user_store=registry_store, project_store=registry_store
        )

        tool_config = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search"],
            http_config=HTTPConfig(
                base_url="https://api.brave.com",
                endpoints={"search": "/v1/web/search"},
                headers={"Accept": "application/json"},
                auth_header="X-API-Key",
                auth_env_var="BRAVE_API_KEY",
            ),
            auth=AuthConfig(
                required=True,
                env_var="BRAVE_API_KEY",
                signup_url="https://brave.com/search/api/",
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        registry_service.adopt(tool_config)

        # Create execution service with registry
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(
            artifact_dir=artifact_dir, registry_service=registry_service
        )

        # Mock adapter
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="brave-search",
            action="search",
            success=True,
            output={"results": [{"title": "Test"}]},
            started_at=datetime.now(timezone.utc),
            duration_ms=250,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Execute adopted tool - should succeed
            result = await service.execute(
                tool_id="brave-search",
                action="search",
                adapter_type="http",
                params={"query": "test"},
                timeout=30.0,
            )

        assert result.success is True
        assert result.tool_id == "brave-search"
        mock_adapter.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_without_registry_service_allows_any_tool(self, tmp_path):
        """Test that without registry_service, any tool can execute."""
        # Create execution service WITHOUT registry
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir, registry_service=None)

        # Mock adapter
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="any-tool",
            action="test",
            success=True,
            output={"data": "test"},
            started_at=datetime.now(timezone.utc),
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Execute without registry check - should succeed
            result = await service.execute(
                tool_id="any-tool",
                action="test",
                adapter_type="http",
                params={"test": "data"},
                timeout=30.0,
            )

        assert result.success is True
        assert result.tool_id == "any-tool"
        mock_adapter.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_readiness_tool_not_adopted(self, tmp_path):
        """Test readiness check fails when tool not adopted."""
        # Create registry service with empty registry
        registry_store = RegistryStore(tmp_path / "registry.json")
        registry_service = RegistryService(
            user_store=registry_store, project_store=registry_store
        )

        # Create execution service with registry
        service = ExecutionService(registry_service=registry_service)

        # Check readiness for non-adopted tool
        readiness = await service.check_readiness(
            tool_id="unapproved-tool",
            adapter_type="http",
            config=None,
        )

        assert readiness.ready is False
        assert len(readiness.missing) == 1
        assert "not adopted" in readiness.missing[0].lower()
        assert "unapproved-tool" in readiness.missing[0]

    @pytest.mark.asyncio
    async def test_check_readiness_adopted_tool_succeeds(self, tmp_path):
        """Test readiness check succeeds for adopted tool."""
        # Create registry and adopt a tool
        registry_store = RegistryStore(tmp_path / "registry.json")
        registry_service = RegistryService(
            user_store=registry_store, project_store=registry_store
        )

        tool_config = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            capabilities=["testing"],
            http_config=HTTPConfig(
                base_url="https://api.test.com",
                endpoints={"test": "/test"},
                headers={},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        registry_service.adopt(tool_config)

        # Create execution service with registry
        service = ExecutionService(registry_service=registry_service)

        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_adapter.is_available = AsyncMock(return_value=True)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Check readiness for adopted tool
            readiness = await service.check_readiness(
                tool_id="test-tool",
                adapter_type="http",
                config=None,
            )

        assert readiness.ready is True
        assert readiness.missing == []

    @pytest.mark.asyncio
    async def test_check_readiness_without_registry_service(self):
        """Test readiness check without registry service skips adoption check."""
        # Create execution service WITHOUT registry
        service = ExecutionService(registry_service=None)

        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_adapter.is_available = AsyncMock(return_value=True)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            # Check readiness for any tool
            readiness = await service.check_readiness(
                tool_id="any-tool",
                adapter_type="http",
                config=None,
            )

        # Should be ready (no registry check)
        assert readiness.ready is True
        assert readiness.missing == []


class TestToolNotAdoptedError:
    """Test ToolNotAdoptedError exception."""

    def test_exception_creation(self):
        """Test creating ToolNotAdoptedError."""
        error = ToolNotAdoptedError("my-tool", "Tool not found in registry")
        assert error.tool_id == "my-tool"
        assert error.message == "Tool not found in registry"
        assert "my-tool" in str(error)
        assert "not adopted" in str(error)

    def test_exception_with_context(self):
        """Test ToolNotAdoptedError with context."""
        error = ToolNotAdoptedError(
            "my-tool", "Tool not found", registry_path="/path/to/registry.json"
        )
        assert error.tool_id == "my-tool"
        assert error.context["registry_path"] == "/path/to/registry.json"

    def test_exception_inheritance(self):
        """Test that ToolNotAdoptedError inherits from ToolError."""
        from cub.core.tools.exceptions import ToolError

        error = ToolNotAdoptedError("my-tool", "Test error")
        assert isinstance(error, ToolError)
        assert isinstance(error, Exception)
