"""
Tests for ExecutionService.

Tests the tool execution service, including adapter selection, readiness checks,
artifact writing, and error handling.
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cub.core.tools.execution import ExecutionService, ReadinessCheck
from cub.core.tools.models import AdapterType, ToolResult


class TestReadinessCheck:
    """Test ReadinessCheck model."""

    def test_ready_no_missing(self):
        """Test readiness check with no missing dependencies."""
        check = ReadinessCheck(ready=True, missing=[])
        assert check.ready is True
        assert check.missing == []

    def test_not_ready_with_missing(self):
        """Test readiness check with missing dependencies."""
        check = ReadinessCheck(
            ready=False, missing=["BRAVE_API_KEY not set", "Tool not found"]
        )
        assert check.ready is False
        assert len(check.missing) == 2
        assert "BRAVE_API_KEY not set" in check.missing


class TestExecutionServiceInit:
    """Test ExecutionService initialization."""

    def test_init_default_artifact_dir(self, tmp_path):
        """Test initialization with default artifact directory."""
        service = ExecutionService()
        assert service.artifact_dir == Path(".cub/toolsmith/runs")

    def test_init_custom_artifact_dir(self, tmp_path):
        """Test initialization with custom artifact directory."""
        artifact_dir = tmp_path / "custom_artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)
        assert service.artifact_dir == artifact_dir
        assert artifact_dir.exists()

    def test_init_creates_artifact_dir(self, tmp_path):
        """Test that initialization creates artifact directory."""
        artifact_dir = tmp_path / "artifacts"
        ExecutionService(artifact_dir=artifact_dir)
        assert artifact_dir.exists()


class TestExecutionServiceExecute:
    """Test ExecutionService execute method."""

    @pytest.mark.asyncio
    async def test_execute_success_with_artifact(self, tmp_path):
        """Test successful execution with artifact saving."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create mock adapter
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="test-tool",
            action="search",
            success=True,
            output={"results": [{"id": 1}]},
            started_at="2024-01-24T12:00:00Z",
            duration_ms=250,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            result = await service.execute(
                tool_id="test-tool",
                action="search",
                adapter_type="http",
                params={"query": "test"},
                timeout=30.0,
                save_artifact=True,
            )

        assert result.success is True
        assert result.tool_id == "test-tool"
        assert result.action == "search"
        assert result.artifact_path is not None
        assert Path(result.artifact_path).exists()

        # Verify adapter was called correctly
        mock_adapter.execute.assert_called_once_with(
            tool_id="test-tool",
            action="search",
            params={"query": "test"},
            timeout=30.0,
        )

    @pytest.mark.asyncio
    async def test_execute_success_without_artifact(self, tmp_path):
        """Test successful execution without artifact saving."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create mock adapter
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="test-tool",
            action="search",
            success=True,
            output={"results": []},
            started_at="2024-01-24T12:00:00Z",
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            result = await service.execute(
                tool_id="test-tool",
                action="search",
                adapter_type="http",
                params={"query": "test"},
                timeout=30.0,
                save_artifact=False,
            )

        assert result.success is True
        assert result.artifact_path is None

        # Verify no artifacts were created
        artifacts = list(artifact_dir.glob("*.json"))
        assert len(artifacts) == 0

    @pytest.mark.asyncio
    async def test_execute_failure(self, tmp_path):
        """Test execution failure handling."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create mock adapter that returns failure
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="test-tool",
            action="search",
            success=False,
            output=None,
            started_at="2024-01-24T12:00:00Z",
            duration_ms=50,
            adapter_type=AdapterType.HTTP,
            error="API key not found",
            error_type="auth",
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            result = await service.execute(
                tool_id="test-tool",
                action="search",
                adapter_type="http",
                params={"query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error == "API key not found"
        assert result.error_type == "auth"
        # Artifact should still be saved
        assert result.artifact_path is not None

    @pytest.mark.asyncio
    async def test_execute_invalid_adapter(self, tmp_path):
        """Test execution with invalid adapter type."""
        service = ExecutionService(artifact_dir=tmp_path / "artifacts")

        with patch(
            "cub.core.tools.execution.get_adapter",
            side_effect=ValueError("Adapter 'invalid' not registered"),
        ):
            with pytest.raises(ValueError, match="Adapter 'invalid' not registered"):
                await service.execute(
                    tool_id="test-tool",
                    action="search",
                    adapter_type="invalid",
                    params={"query": "test"},
                    timeout=30.0,
                )

    @pytest.mark.asyncio
    async def test_execute_timeout(self, tmp_path):
        """Test execution timeout handling."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create mock adapter that returns timeout error
        mock_adapter = Mock()
        mock_result = ToolResult(
            tool_id="test-tool",
            action="search",
            success=False,
            output=None,
            started_at="2024-01-24T12:00:00Z",
            duration_ms=30000,
            adapter_type=AdapterType.HTTP,
            error="Request timed out after 30.0s",
            error_type="timeout",
        )
        mock_adapter.execute = AsyncMock(return_value=mock_result)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            result = await service.execute(
                tool_id="test-tool",
                action="search",
                adapter_type="http",
                params={"query": "test"},
                timeout=30.0,
            )

        assert result.success is False
        assert result.error_type == "timeout"


class TestExecutionServiceReadiness:
    """Test ExecutionService check_readiness method."""

    @pytest.mark.asyncio
    async def test_check_readiness_all_ready(self):
        """Test readiness check when all requirements are met."""
        service = ExecutionService()

        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_adapter.is_available = AsyncMock(return_value=True)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            readiness = await service.check_readiness(
                tool_id="test-tool",
                adapter_type="http",
                config=None,
            )

        assert readiness.ready is True
        assert readiness.missing == []

    @pytest.mark.asyncio
    async def test_check_readiness_adapter_not_registered(self):
        """Test readiness check when adapter is not registered."""
        service = ExecutionService()

        with patch(
            "cub.core.tools.execution.get_adapter",
            side_effect=ValueError("Adapter 'invalid' not registered"),
        ):
            readiness = await service.check_readiness(
                tool_id="test-tool",
                adapter_type="invalid",
            )

        assert readiness.ready is False
        assert len(readiness.missing) == 1
        assert "Adapter 'invalid' not registered" in readiness.missing[0]

    @pytest.mark.asyncio
    async def test_check_readiness_health_check_fails(self):
        """Test readiness check when adapter health check fails."""
        service = ExecutionService()

        # Mock adapter with failed health check
        mock_adapter = Mock()
        mock_adapter.health_check = AsyncMock(return_value=False)
        mock_adapter.is_available = AsyncMock(return_value=True)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            readiness = await service.check_readiness(
                tool_id="test-tool",
                adapter_type="http",
            )

        assert readiness.ready is False
        assert len(readiness.missing) == 1
        assert "health check failed" in readiness.missing[0]

    @pytest.mark.asyncio
    async def test_check_readiness_tool_not_available(self):
        """Test readiness check when tool is not available."""
        service = ExecutionService()

        # Mock adapter where tool is not available
        mock_adapter = Mock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_adapter.is_available = AsyncMock(return_value=False)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            readiness = await service.check_readiness(
                tool_id="missing-tool",
                adapter_type="http",
            )

        assert readiness.ready is False
        assert len(readiness.missing) == 1
        assert "not available" in readiness.missing[0]

    @pytest.mark.asyncio
    async def test_check_readiness_missing_auth_env_var(self):
        """Test readiness check when auth env var is missing."""
        service = ExecutionService()

        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_adapter.is_available = AsyncMock(return_value=True)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            with patch.dict(os.environ, {}, clear=True):
                readiness = await service.check_readiness(
                    tool_id="test-tool",
                    adapter_type="http",
                    config={"auth_env_var": "MISSING_API_KEY"},
                )

        assert readiness.ready is False
        assert len(readiness.missing) == 1
        assert "MISSING_API_KEY" in readiness.missing[0]

    @pytest.mark.asyncio
    async def test_check_readiness_with_auth_env_var_present(self):
        """Test readiness check when auth env var is present."""
        service = ExecutionService()

        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.health_check = AsyncMock(return_value=True)
        mock_adapter.is_available = AsyncMock(return_value=True)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            with patch.dict(os.environ, {"API_KEY": "secret123"}):
                readiness = await service.check_readiness(
                    tool_id="test-tool",
                    adapter_type="http",
                    config={"auth_env_var": "API_KEY"},
                )

        assert readiness.ready is True
        assert readiness.missing == []

    @pytest.mark.asyncio
    async def test_check_readiness_multiple_issues(self):
        """Test readiness check with multiple missing requirements."""
        service = ExecutionService()

        # Mock adapter with failed checks
        mock_adapter = Mock()
        mock_adapter.health_check = AsyncMock(return_value=False)
        mock_adapter.is_available = AsyncMock(return_value=False)

        with patch("cub.core.tools.execution.get_adapter", return_value=mock_adapter):
            with patch.dict(os.environ, {}, clear=True):
                readiness = await service.check_readiness(
                    tool_id="test-tool",
                    adapter_type="http",
                    config={"auth_env_var": "MISSING_KEY"},
                )

        assert readiness.ready is False
        assert len(readiness.missing) == 3
        assert any("health check" in msg for msg in readiness.missing)
        assert any("not available" in msg for msg in readiness.missing)
        assert any("MISSING_KEY" in msg for msg in readiness.missing)


class TestExecutionServiceArtifacts:
    """Test ExecutionService artifact management."""

    def test_write_artifact(self, tmp_path):
        """Test artifact writing with atomic file pattern."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        result = ToolResult(
            tool_id="brave-search",
            action="search",
            success=True,
            output={"results": [{"title": "Test"}]},
            started_at="2024-01-24T12:30:45Z",
            duration_ms=250,
            adapter_type=AdapterType.HTTP,
        )

        artifact_path = service._write_artifact(result)

        # Verify file exists
        assert artifact_path.exists()
        # Verify filename format
        assert artifact_path.name.endswith("-brave-search-search.json")
        # Verify no temp files left behind
        temp_files = list(artifact_dir.glob("*.tmp"))
        assert len(temp_files) == 0

        # Verify content is valid JSON
        with artifact_path.open() as f:
            data = json.load(f)
        assert data["tool_id"] == "brave-search"
        assert data["action"] == "search"
        assert data["success"] is True

    def test_read_artifact(self, tmp_path):
        """Test artifact reading."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Write an artifact
        result = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"data": "test"},
            started_at="2024-01-24T12:00:00Z",
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        artifact_path = service._write_artifact(result)

        # Read it back
        read_result = service.read_artifact(artifact_path)

        assert read_result is not None
        assert read_result.tool_id == "test-tool"
        assert read_result.action == "test"
        assert read_result.success is True
        assert read_result.output == {"data": "test"}

    def test_read_artifact_not_found(self, tmp_path):
        """Test reading non-existent artifact."""
        service = ExecutionService(artifact_dir=tmp_path / "artifacts")
        result = service.read_artifact(tmp_path / "nonexistent.json")
        assert result is None

    def test_read_artifact_invalid_json(self, tmp_path):
        """Test reading artifact with invalid JSON."""
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        service = ExecutionService(artifact_dir=artifact_dir)

        # Write invalid JSON
        invalid_path = artifact_dir / "invalid.json"
        invalid_path.write_text("{ invalid json }")

        result = service.read_artifact(invalid_path)
        assert result is None

    def test_list_artifacts_empty(self, tmp_path):
        """Test listing artifacts when directory is empty."""
        service = ExecutionService(artifact_dir=tmp_path / "artifacts")
        artifacts = service.list_artifacts()
        assert artifacts == []

    def test_list_artifacts_all(self, tmp_path):
        """Test listing all artifacts."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create multiple artifacts
        result1 = ToolResult(
            tool_id="tool1",
            action="action1",
            success=True,
            output={},
            started_at="2024-01-24T12:00:00Z",
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        result2 = ToolResult(
            tool_id="tool2",
            action="action2",
            success=True,
            output={},
            started_at="2024-01-24T12:01:00Z",
            duration_ms=150,
            adapter_type=AdapterType.CLI,
        )

        service._write_artifact(result1)
        service._write_artifact(result2)

        artifacts = service.list_artifacts()
        assert len(artifacts) == 2

    def test_list_artifacts_filter_by_tool_id(self, tmp_path):
        """Test listing artifacts filtered by tool ID."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create artifacts for different tools
        result1 = ToolResult(
            tool_id="brave-search",
            action="search",
            success=True,
            output={},
            started_at="2024-01-24T12:00:00Z",
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        result2 = ToolResult(
            tool_id="gh",
            action="pr",
            success=True,
            output={},
            started_at="2024-01-24T12:01:00Z",
            duration_ms=150,
            adapter_type=AdapterType.CLI,
        )

        service._write_artifact(result1)
        service._write_artifact(result2)

        # Filter by tool_id
        brave_artifacts = service.list_artifacts(tool_id="brave-search")
        assert len(brave_artifacts) == 1
        assert "brave-search" in brave_artifacts[0].name

    def test_list_artifacts_filter_by_action(self, tmp_path):
        """Test listing artifacts filtered by action."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create artifacts with different actions
        result1 = ToolResult(
            tool_id="tool1",
            action="search",
            success=True,
            output={},
            started_at="2024-01-24T12:00:00Z",
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        result2 = ToolResult(
            tool_id="tool2",
            action="create",
            success=True,
            output={},
            started_at="2024-01-24T12:01:00Z",
            duration_ms=150,
            adapter_type=AdapterType.HTTP,
        )

        service._write_artifact(result1)
        service._write_artifact(result2)

        # Filter by action
        search_artifacts = service.list_artifacts(action="search")
        assert len(search_artifacts) == 1
        assert "-search.json" in search_artifacts[0].name

    def test_list_artifacts_sorted_by_time(self, tmp_path):
        """Test artifacts are sorted by modification time (newest first)."""
        artifact_dir = tmp_path / "artifacts"
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create artifacts with different timestamps
        result1 = ToolResult(
            tool_id="tool1",
            action="action1",
            success=True,
            output={},
            started_at="2024-01-24T12:00:00Z",
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        result2 = ToolResult(
            tool_id="tool2",
            action="action2",
            success=True,
            output={},
            started_at="2024-01-24T12:01:00Z",
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )

        # Write in order
        path1 = service._write_artifact(result1)
        path2 = service._write_artifact(result2)

        artifacts = service.list_artifacts()

        # Most recent should be first
        assert artifacts[0] == path2
        assert artifacts[1] == path1

    def test_list_artifacts_excludes_temp_files(self, tmp_path):
        """Test that temp files are excluded from artifact listing."""
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        service = ExecutionService(artifact_dir=artifact_dir)

        # Create a normal artifact
        result = ToolResult(
            tool_id="tool1",
            action="action1",
            success=True,
            output={},
            started_at="2024-01-24T12:00:00Z",
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        service._write_artifact(result)

        # Create a temp file
        temp_file = artifact_dir / "artifact.json.tmp"
        temp_file.write_text("{}")

        artifacts = service.list_artifacts()

        # Should only see the real artifact, not the temp file
        assert len(artifacts) == 1
        assert artifacts[0].suffix == ".json"
