"""Tests for ToolConfig and Registry models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cub.core.tools.models import (
    AdapterType,
    AuthConfig,
    CLIConfig,
    HTTPConfig,
    MCPConfig,
    Registry,
    ToolConfig,
    ToolMetrics,
    ToolResult,
)


class TestToolConfig:
    """Tests for ToolConfig model."""

    def test_create_minimal_http_tool(self):
        """Test creating a minimal HTTP tool configuration."""
        config = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(
                base_url="https://api.example.com",
                endpoints={"test": "/test"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test-source",
        )
        assert config.id == "test-tool"
        assert config.name == "Test Tool"
        assert config.adapter_type == AdapterType.HTTP
        assert config.capabilities == []
        assert config.http_config is not None
        assert config.cli_config is None
        assert config.mcp_config is None

    def test_create_complete_http_tool(self):
        """Test creating a complete HTTP tool configuration with all fields."""
        now = datetime.now(timezone.utc)
        config = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search", "current_events"],
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
                description="API key for Brave Search",
            ),
            adopted_at=now,
            adopted_from="mcp-official",
            version_hash="abc123",
        )
        assert config.id == "brave-search"
        assert len(config.capabilities) == 2
        assert "web_search" in config.capabilities
        assert config.auth is not None
        assert config.auth.required is True
        assert config.version_hash == "abc123"

    def test_create_cli_tool(self):
        """Test creating a CLI tool configuration."""
        config = ToolConfig(
            id="gh-cli",
            name="GitHub CLI",
            adapter_type=AdapterType.CLI,
            capabilities=["github", "pr_management"],
            cli_config=CLIConfig(
                command="gh",
                args_template="{action} {params}",
                output_format="json",
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="custom",
        )
        assert config.adapter_type == AdapterType.CLI
        assert config.cli_config is not None
        assert config.cli_config.command == "gh"
        assert config.http_config is None

    def test_create_mcp_tool(self):
        """Test creating an MCP tool configuration."""
        config = ToolConfig(
            id="filesystem",
            name="Filesystem MCP",
            adapter_type=AdapterType.MCP_STDIO,
            capabilities=["read_file", "write_file"],
            mcp_config=MCPConfig(
                command="uvx",
                args=["mcp-server-filesystem"],
                env_vars={"PATH": "/usr/local/bin"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="mcp-official",
        )
        assert config.adapter_type == AdapterType.MCP_STDIO
        assert config.mcp_config is not None
        assert config.mcp_config.command == "uvx"
        assert len(config.mcp_config.args) == 1

    def test_adopted_at_datetime_normalization(self):
        """Test that adopted_at is normalized to timezone-aware datetime."""
        # Test with naive datetime
        naive_dt = datetime(2024, 1, 15, 10, 30, 0)
        config = ToolConfig(
            id="test",
            name="Test",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=naive_dt,
            adopted_from="test",
        )
        assert config.adopted_at.tzinfo is not None
        assert config.adopted_at.tzinfo == timezone.utc

        # Test with ISO string
        config2 = ToolConfig(
            id="test2",
            name="Test2",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at="2024-01-15T10:30:00Z",
            adopted_from="test",
        )
        assert config2.adopted_at.tzinfo is not None

    def test_capabilities_validation(self):
        """Test that empty capability strings are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ToolConfig(
                id="test",
                name="Test",
                adapter_type=AdapterType.HTTP,
                capabilities=["valid", "", "another"],
                http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="test",
            )
        assert "Capabilities cannot contain empty strings" in str(exc_info.value)

    def test_get_adapter_config_http(self):
        """Test get_adapter_config returns HTTP config."""
        config = ToolConfig(
            id="test",
            name="Test",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        adapter_config = config.get_adapter_config()
        assert isinstance(adapter_config, HTTPConfig)
        assert adapter_config.base_url == "https://api.test.com"

    def test_get_adapter_config_cli(self):
        """Test get_adapter_config returns CLI config."""
        config = ToolConfig(
            id="test",
            name="Test",
            adapter_type=AdapterType.CLI,
            cli_config=CLIConfig(command="test"),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        adapter_config = config.get_adapter_config()
        assert isinstance(adapter_config, CLIConfig)
        assert adapter_config.command == "test"

    def test_get_adapter_config_mcp(self):
        """Test get_adapter_config returns MCP config."""
        config = ToolConfig(
            id="test",
            name="Test",
            adapter_type=AdapterType.MCP_STDIO,
            mcp_config=MCPConfig(command="test"),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        adapter_config = config.get_adapter_config()
        assert isinstance(adapter_config, MCPConfig)
        assert adapter_config.command == "test"

    def test_get_adapter_config_missing_raises(self):
        """Test get_adapter_config raises when config is missing."""
        # Create with HTTP type but no config (bypassing validation for test)
        config = ToolConfig.model_construct(
            id="test",
            name="Test",
            adapter_type=AdapterType.HTTP,
            http_config=None,
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        with pytest.raises(ValueError, match="HTTP adapter requires http_config"):
            config.get_adapter_config()


class TestRegistry:
    """Tests for Registry model."""

    def test_create_empty_registry(self):
        """Test creating an empty registry."""
        registry = Registry()
        assert registry.version == "1.0.0"
        assert len(registry.tools) == 0

    def test_create_registry_with_version(self):
        """Test creating registry with custom version."""
        registry = Registry(version="2.0.0")
        assert registry.version == "2.0.0"

    def test_version_validation(self):
        """Test semantic version validation."""
        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "1.0.0-beta", "1.0.0-alpha.1"]
        for version in valid_versions:
            registry = Registry(version=version)
            assert registry.version == version

        # Invalid versions
        invalid_versions = ["1.0", "v1.0.0", "1.0.0.0", "invalid"]
        for version in invalid_versions:
            with pytest.raises(ValidationError):
                Registry(version=version)

    def test_add_tool(self):
        """Test adding a tool to the registry."""
        registry = Registry()
        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        registry.add(tool)
        assert len(registry.tools) == 1
        assert "test-tool" in registry.tools

    def test_get_tool(self):
        """Test getting a tool by ID."""
        registry = Registry()
        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        registry.add(tool)

        retrieved = registry.get("test-tool")
        assert retrieved is not None
        assert retrieved.id == "test-tool"

        not_found = registry.get("nonexistent")
        assert not_found is None

    def test_remove_tool(self):
        """Test removing a tool from the registry."""
        registry = Registry()
        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        registry.add(tool)
        assert len(registry.tools) == 1

        removed = registry.remove("test-tool")
        assert removed is True
        assert len(registry.tools) == 0

        removed_again = registry.remove("test-tool")
        assert removed_again is False

    def test_find_by_capability(self):
        """Test finding tools by capability."""
        registry = Registry()

        tool_a = ToolConfig(
            id="tool-a",
            name="Tool A",
            adapter_type=AdapterType.HTTP,
            capabilities=["search", "web"],
            http_config=HTTPConfig(base_url="https://api.a.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )

        tool_b = ToolConfig(
            id="tool-b",
            name="Tool B",
            adapter_type=AdapterType.CLI,
            capabilities=["database", "query"],
            cli_config=CLIConfig(command="test"),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )

        tool_c = ToolConfig(
            id="tool-c",
            name="Tool C",
            adapter_type=AdapterType.HTTP,
            capabilities=["search", "database"],
            http_config=HTTPConfig(base_url="https://api.c.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )

        registry.add(tool_a)
        registry.add(tool_b)
        registry.add(tool_c)

        # Search for "search" capability
        found_search = registry.find_by_capability("search")
        assert len(found_search) == 2
        assert set(t.id for t in found_search) == {"tool-a", "tool-c"}

        # Search for "database" capability
        found_db = registry.find_by_capability("database")
        assert len(found_db) == 2
        assert set(t.id for t in found_db) == {"tool-b", "tool-c"}

        # Search for nonexistent capability
        found_none = registry.find_by_capability("nonexistent")
        assert len(found_none) == 0

    def test_list_all(self):
        """Test listing all tools."""
        registry = Registry()
        assert len(registry.list_all()) == 0

        for i in range(3):
            tool = ToolConfig(
                id=f"tool-{i}",
                name=f"Tool {i}",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="test",
            )
            registry.add(tool)

        all_tools = registry.list_all()
        assert len(all_tools) == 3
        assert set(t.id for t in all_tools) == {"tool-0", "tool-1", "tool-2"}

    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        registry = Registry(version="1.0.0")
        tool = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search", "current_events"],
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
            adopted_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            adopted_from="mcp-official",
            version_hash="abc123",
        )
        registry.add(tool)

        # Serialize
        json_str = registry.model_dump_json()
        assert "brave-search" in json_str
        assert "web_search" in json_str

        # Deserialize
        loaded = Registry.model_validate_json(json_str)
        assert loaded.version == "1.0.0"
        assert len(loaded.tools) == 1
        assert "brave-search" in loaded.tools

        loaded_tool = loaded.tools["brave-search"]
        assert loaded_tool.name == "Brave Search"
        assert loaded_tool.adapter_type == AdapterType.HTTP
        assert len(loaded_tool.capabilities) == 2
        assert loaded_tool.auth is not None
        assert loaded_tool.auth.required is True


class TestToolMetrics:
    """Tests for ToolMetrics model."""

    def test_create_empty_metrics(self):
        """Test creating empty metrics for a tool."""
        metrics = ToolMetrics(tool_id="test-tool")
        assert metrics.tool_id == "test-tool"
        assert metrics.invocations == 0
        assert metrics.successes == 0
        assert metrics.failures == 0
        assert metrics.total_duration_ms == 0
        assert metrics.min_duration_ms is None
        assert metrics.max_duration_ms is None
        assert metrics.avg_duration_ms == 0.0
        assert metrics.error_types == {}
        assert metrics.last_used_at is None
        assert metrics.first_used_at is None

    def test_create_with_initial_data(self):
        """Test creating metrics with initial data."""
        now = datetime.now(timezone.utc)
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=8,
            failures=2,
            total_duration_ms=5000,
            min_duration_ms=100,
            max_duration_ms=1000,
            avg_duration_ms=500.0,
            error_types={"timeout": 1, "auth": 1},
            last_used_at=now,
            first_used_at=now,
        )
        assert metrics.invocations == 10
        assert metrics.successes == 8
        assert metrics.failures == 2
        assert metrics.total_duration_ms == 5000
        assert metrics.min_duration_ms == 100
        assert metrics.max_duration_ms == 1000
        assert metrics.avg_duration_ms == 500.0
        assert metrics.error_types == {"timeout": 1, "auth": 1}
        assert metrics.last_used_at == now
        assert metrics.first_used_at == now

    def test_success_rate_empty(self):
        """Test success rate calculation with no invocations."""
        metrics = ToolMetrics(tool_id="test-tool")
        assert metrics.success_rate() == 0.0

    def test_success_rate_all_successful(self):
        """Test success rate with all successful invocations."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=10,
            failures=0,
        )
        assert metrics.success_rate() == 100.0

    def test_success_rate_partial(self):
        """Test success rate with partial success."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=7,
            failures=3,
        )
        assert metrics.success_rate() == 70.0

    def test_failure_rate_empty(self):
        """Test failure rate calculation with no invocations."""
        metrics = ToolMetrics(tool_id="test-tool")
        assert metrics.failure_rate() == 0.0

    def test_failure_rate_all_failed(self):
        """Test failure rate with all failed invocations."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=0,
            failures=10,
        )
        assert metrics.failure_rate() == 100.0

    def test_failure_rate_partial(self):
        """Test failure rate with partial failure."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=7,
            failures=3,
        )
        assert metrics.failure_rate() == 30.0

    def test_record_successful_execution(self):
        """Test recording a successful tool execution."""
        metrics = ToolMetrics(tool_id="test-tool")
        started_at = datetime.now(timezone.utc)

        result = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=started_at,
            duration_ms=250,
            adapter_type=AdapterType.HTTP,
        )

        metrics.record_execution(result)

        assert metrics.invocations == 1
        assert metrics.successes == 1
        assert metrics.failures == 0
        assert metrics.total_duration_ms == 250
        assert metrics.min_duration_ms == 250
        assert metrics.max_duration_ms == 250
        assert metrics.avg_duration_ms == 250.0
        assert metrics.first_used_at == started_at
        assert metrics.last_used_at == started_at

    def test_record_failed_execution(self):
        """Test recording a failed tool execution."""
        metrics = ToolMetrics(tool_id="test-tool")
        started_at = datetime.now(timezone.utc)

        result = ToolResult(
            tool_id="test-tool",
            action="test",
            success=False,
            output=None,
            error="Connection timeout",
            error_type="timeout",
            started_at=started_at,
            duration_ms=5000,
            adapter_type=AdapterType.HTTP,
        )

        metrics.record_execution(result)

        assert metrics.invocations == 1
        assert metrics.successes == 0
        assert metrics.failures == 1
        assert metrics.error_types == {"timeout": 1}
        assert metrics.total_duration_ms == 5000

    def test_record_multiple_executions(self):
        """Test recording multiple executions and metric updates."""
        metrics = ToolMetrics(tool_id="test-tool")
        base_time = datetime.now(timezone.utc)

        # First execution - success, 100ms
        result1 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=base_time,
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result1)

        # Second execution - success, 300ms
        result2 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={"result": "success"},
            started_at=base_time,
            duration_ms=300,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result2)

        # Third execution - failure, 200ms
        result3 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=False,
            output=None,
            error="Auth error",
            error_type="auth",
            started_at=base_time,
            duration_ms=200,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result3)

        assert metrics.invocations == 3
        assert metrics.successes == 2
        assert metrics.failures == 1
        assert metrics.total_duration_ms == 600
        assert metrics.min_duration_ms == 100
        assert metrics.max_duration_ms == 300
        assert metrics.avg_duration_ms == 200.0
        assert metrics.error_types == {"auth": 1}
        assert metrics.success_rate() == pytest.approx(66.666, rel=0.01)
        assert metrics.failure_rate() == pytest.approx(33.333, rel=0.01)

    def test_record_multiple_error_types(self):
        """Test tracking multiple error types."""
        metrics = ToolMetrics(tool_id="test-tool")
        base_time = datetime.now(timezone.utc)

        # Timeout error
        result1 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=False,
            output=None,
            error="Timeout",
            error_type="timeout",
            started_at=base_time,
            duration_ms=5000,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result1)

        # Auth error
        result2 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=False,
            output=None,
            error="Auth failed",
            error_type="auth",
            started_at=base_time,
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result2)

        # Another timeout
        result3 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=False,
            output=None,
            error="Timeout again",
            error_type="timeout",
            started_at=base_time,
            duration_ms=5000,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result3)

        assert metrics.error_types == {"timeout": 2, "auth": 1}
        assert metrics.failures == 3

    def test_timestamp_normalization_naive_datetime(self):
        """Test that naive datetimes are normalized to UTC."""
        naive_dt = datetime(2024, 1, 15, 10, 30, 0)
        metrics = ToolMetrics(
            tool_id="test-tool",
            first_used_at=naive_dt,
            last_used_at=naive_dt,
        )
        assert metrics.first_used_at is not None
        assert metrics.first_used_at.tzinfo == timezone.utc
        assert metrics.last_used_at is not None
        assert metrics.last_used_at.tzinfo == timezone.utc

    def test_timestamp_normalization_iso_string(self):
        """Test that ISO strings are normalized to timezone-aware datetime."""
        metrics = ToolMetrics(
            tool_id="test-tool",
            first_used_at="2024-01-15T10:30:00Z",
            last_used_at="2024-01-15T11:00:00+00:00",
        )
        assert metrics.first_used_at is not None
        assert metrics.first_used_at.tzinfo is not None
        assert metrics.last_used_at is not None
        assert metrics.last_used_at.tzinfo is not None

    def test_validation_negative_counts(self):
        """Test that negative counts are rejected."""
        with pytest.raises(ValidationError):
            ToolMetrics(
                tool_id="test-tool",
                invocations=-1,
            )

        with pytest.raises(ValidationError):
            ToolMetrics(
                tool_id="test-tool",
                successes=-1,
            )

        with pytest.raises(ValidationError):
            ToolMetrics(
                tool_id="test-tool",
                failures=-1,
            )

    def test_validation_empty_tool_id(self):
        """Test that empty tool_id is rejected."""
        with pytest.raises(ValidationError):
            ToolMetrics(tool_id="")

    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        now = datetime.now(timezone.utc)
        metrics = ToolMetrics(
            tool_id="test-tool",
            invocations=10,
            successes=8,
            failures=2,
            total_duration_ms=5000,
            min_duration_ms=100,
            max_duration_ms=1000,
            avg_duration_ms=500.0,
            error_types={"timeout": 1, "auth": 1},
            last_used_at=now,
            first_used_at=now,
        )

        # Serialize
        json_str = metrics.model_dump_json()
        assert "test-tool" in json_str
        assert "timeout" in json_str

        # Deserialize
        loaded = ToolMetrics.model_validate_json(json_str)
        assert loaded.tool_id == "test-tool"
        assert loaded.invocations == 10
        assert loaded.successes == 8
        assert loaded.failures == 2
        assert loaded.error_types == {"timeout": 1, "auth": 1}
        assert loaded.first_used_at is not None
        assert loaded.last_used_at is not None

    def test_first_used_timestamp_only_set_once(self):
        """Test that first_used_at is only set on first execution."""
        metrics = ToolMetrics(tool_id="test-tool")

        time1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        result1 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={},
            started_at=time1,
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result1)

        time2 = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
        result2 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={},
            started_at=time2,
            duration_ms=100,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result2)

        # first_used_at should still be time1
        assert metrics.first_used_at == time1
        # last_used_at should be time2
        assert metrics.last_used_at == time2

    def test_min_max_duration_updates(self):
        """Test that min and max duration are properly tracked."""
        metrics = ToolMetrics(tool_id="test-tool")
        base_time = datetime.now(timezone.utc)

        # First execution - 500ms
        result1 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={},
            started_at=base_time,
            duration_ms=500,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result1)
        assert metrics.min_duration_ms == 500
        assert metrics.max_duration_ms == 500

        # Second execution - 200ms (new min)
        result2 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={},
            started_at=base_time,
            duration_ms=200,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result2)
        assert metrics.min_duration_ms == 200
        assert metrics.max_duration_ms == 500

        # Third execution - 1000ms (new max)
        result3 = ToolResult(
            tool_id="test-tool",
            action="test",
            success=True,
            output={},
            started_at=base_time,
            duration_ms=1000,
            adapter_type=AdapterType.HTTP,
        )
        metrics.record_execution(result3)
        assert metrics.min_duration_ms == 200
        assert metrics.max_duration_ms == 1000
