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
