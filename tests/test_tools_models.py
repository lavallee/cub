"""
Tests for tool models.

Tests the Pydantic models for ToolResult and adapter configs (HTTP, CLI, MCP, Auth).
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cub.core.tools.models import (
    AdapterType,
    AuthConfig,
    CLIConfig,
    HTTPConfig,
    MCPConfig,
    ToolResult,
)


class TestAdapterType:
    """Test AdapterType enum."""

    def test_adapter_types(self):
        """Test all adapter type values."""
        assert AdapterType.HTTP == "http"
        assert AdapterType.CLI == "cli"
        assert AdapterType.MCP_STDIO == "mcp_stdio"

    def test_adapter_type_from_string(self):
        """Test creating AdapterType from string."""
        assert AdapterType("http") == AdapterType.HTTP
        assert AdapterType("cli") == AdapterType.CLI
        assert AdapterType("mcp_stdio") == AdapterType.MCP_STDIO


class TestToolResult:
    """Test ToolResult model."""

    def test_tool_result_success(self):
        """Test creating a successful ToolResult."""
        started_at = datetime.now(timezone.utc)
        result = ToolResult(
            tool_id="test-tool",
            action="test-action",
            success=True,
            output={"data": "test"},
            started_at=started_at,
            adapter_type=AdapterType.HTTP,
            duration_ms=150,
            tokens_used=100,
            output_markdown="# Test Result",
            metadata={"status": 200},
        )

        assert result.tool_id == "test-tool"
        assert result.action == "test-action"
        assert result.success is True
        assert result.output == {"data": "test"}
        assert result.started_at == started_at
        assert result.adapter_type == AdapterType.HTTP
        assert result.duration_ms == 150
        assert result.tokens_used == 100
        assert result.output_markdown == "# Test Result"
        assert result.metadata == {"status": 200}
        assert result.error is None
        assert result.error_type is None

    def test_tool_result_failure(self):
        """Test creating a failed ToolResult."""
        started_at = datetime.now(timezone.utc)
        result = ToolResult(
            tool_id="test-tool",
            action="test-action",
            success=False,
            output=None,
            started_at=started_at,
            adapter_type=AdapterType.CLI,
            error="Connection timeout",
            error_type="timeout",
            duration_ms=30000,
        )

        assert result.success is False
        assert result.output is None
        assert result.error == "Connection timeout"
        assert result.error_type == "timeout"
        assert result.duration_ms == 30000

    def test_tool_result_datetime_normalization(self):
        """Test datetime normalization with timezone-aware datetimes."""
        # Test with timezone-aware datetime
        started_at_aware = datetime.now(timezone.utc)
        result = ToolResult(
            tool_id="test",
            action="test",
            success=True,
            output={},
            started_at=started_at_aware,
            adapter_type=AdapterType.HTTP,
        )
        assert result.started_at.tzinfo is not None
        assert result.started_at == started_at_aware

        # Test with naive datetime (should be treated as UTC)
        started_at_naive = datetime.now()
        result = ToolResult(
            tool_id="test",
            action="test",
            success=True,
            output={},
            started_at=started_at_naive,
            adapter_type=AdapterType.HTTP,
        )
        assert result.started_at.tzinfo is not None
        assert result.started_at == started_at_naive.replace(tzinfo=timezone.utc)

    def test_tool_result_datetime_from_iso_string(self):
        """Test datetime parsing from ISO 8601 strings."""
        # Test with Z suffix (UTC)
        result = ToolResult(
            tool_id="test",
            action="test",
            success=True,
            output={},
            started_at="2024-01-15T10:30:00Z",
            adapter_type=AdapterType.HTTP,
        )
        assert result.started_at.tzinfo is not None
        assert result.started_at.year == 2024
        assert result.started_at.month == 1
        assert result.started_at.day == 15

        # Test with timezone offset
        result = ToolResult(
            tool_id="test",
            action="test",
            success=True,
            output={},
            started_at="2024-01-15T10:30:00+05:00",
            adapter_type=AdapterType.HTTP,
        )
        assert result.started_at.tzinfo is not None

        # Test with no timezone (should be treated as UTC)
        result = ToolResult(
            tool_id="test",
            action="test",
            success=True,
            output={},
            started_at="2024-01-15T10:30:00",
            adapter_type=AdapterType.HTTP,
        )
        assert result.started_at.tzinfo is not None

    def test_tool_result_datetime_invalid_format(self):
        """Test datetime validation with invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            ToolResult(
                tool_id="test",
                action="test",
                success=True,
                output={},
                started_at="not-a-datetime",
                adapter_type=AdapterType.HTTP,
            )
        assert "started_at" in str(exc_info.value)

    def test_tool_result_model_dump_json(self):
        """Test ToolResult serialization to JSON."""
        started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = ToolResult(
            tool_id="test-tool",
            action="search",
            success=True,
            output={"data": "test"},
            started_at=started_at,
            adapter_type=AdapterType.HTTP,
            duration_ms=150,
        )

        json_str = result.model_dump_json()
        assert isinstance(json_str, str)
        assert "test-tool" in json_str
        assert "search" in json_str
        assert "http" in json_str

        # Test round-trip
        loaded = ToolResult.model_validate_json(json_str)
        assert loaded.tool_id == result.tool_id
        assert loaded.action == result.action
        assert loaded.success == result.success
        assert loaded.adapter_type == result.adapter_type

    def test_tool_result_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            ToolResult()

        with pytest.raises(ValidationError):
            ToolResult(tool_id="test")

        with pytest.raises(ValidationError):
            ToolResult(tool_id="test", action="test", success=True)


class TestHTTPConfig:
    """Test HTTPConfig model."""

    def test_http_config_full(self):
        """Test creating HTTPConfig with all fields."""
        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search", "fetch": "/v1/fetch"},
            headers={"Accept": "application/json", "User-Agent": "cub/1.0"},
            auth_header="X-API-Key",
            auth_env_var="EXAMPLE_API_KEY",
        )

        assert config.base_url == "https://api.example.com"
        assert config.endpoints == {"search": "/v1/search", "fetch": "/v1/fetch"}
        assert config.headers == {"Accept": "application/json", "User-Agent": "cub/1.0"}
        assert config.auth_header == "X-API-Key"
        assert config.auth_env_var == "EXAMPLE_API_KEY"

    def test_http_config_minimal(self):
        """Test creating HTTPConfig with minimal required fields."""
        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"default": "/"},
        )

        assert config.base_url == "https://api.example.com"
        assert config.endpoints == {"default": "/"}
        assert config.headers == {}
        assert config.auth_header is None
        assert config.auth_env_var is None

    def test_http_config_validation(self):
        """Test HTTPConfig validation."""
        # Empty base_url should fail
        with pytest.raises(ValidationError):
            HTTPConfig(base_url="", endpoints={"default": "/"})

    def test_http_config_serialization(self):
        """Test HTTPConfig serialization."""
        config = HTTPConfig(
            base_url="https://api.example.com",
            endpoints={"search": "/v1/search"},
            auth_header="Authorization",
            auth_env_var="API_KEY",
        )

        json_str = config.model_dump_json()
        loaded = HTTPConfig.model_validate_json(json_str)
        assert loaded.base_url == config.base_url
        assert loaded.endpoints == config.endpoints
        assert loaded.auth_header == config.auth_header
        assert loaded.auth_env_var == config.auth_env_var


class TestCLIConfig:
    """Test CLIConfig model."""

    def test_cli_config_full(self):
        """Test creating CLIConfig with all fields."""
        config = CLIConfig(
            command="gh",
            args_template="{action} --query {query}",
            output_format="json",
            env_vars={"GH_TOKEN": "github_token", "GH_ENTERPRISE_TOKEN": "token"},
        )

        assert config.command == "gh"
        assert config.args_template == "{action} --query {query}"
        assert config.output_format == "json"
        assert config.env_vars == {"GH_TOKEN": "github_token", "GH_ENTERPRISE_TOKEN": "token"}

    def test_cli_config_minimal(self):
        """Test creating CLIConfig with minimal required fields."""
        config = CLIConfig(command="jq")

        assert config.command == "jq"
        assert config.args_template is None
        assert config.output_format == "text"
        assert config.env_vars == {}

    def test_cli_config_output_format_validation(self):
        """Test output_format validation."""
        # Valid formats
        for fmt in ["json", "text", "lines"]:
            config = CLIConfig(command="test", output_format=fmt)
            assert config.output_format == fmt

        # Invalid format
        with pytest.raises(ValidationError) as exc_info:
            CLIConfig(command="test", output_format="invalid")
        assert "output_format" in str(exc_info.value)

    def test_cli_config_serialization(self):
        """Test CLIConfig serialization."""
        config = CLIConfig(
            command="gh",
            args_template="{action}",
            output_format="json",
            env_vars={"GH_TOKEN": "token"},
        )

        json_str = config.model_dump_json()
        loaded = CLIConfig.model_validate_json(json_str)
        assert loaded.command == config.command
        assert loaded.args_template == config.args_template
        assert loaded.output_format == config.output_format
        assert loaded.env_vars == config.env_vars


class TestMCPConfig:
    """Test MCPConfig model."""

    def test_mcp_config_full(self):
        """Test creating MCPConfig with all fields."""
        config = MCPConfig(
            command="uvx",
            args=["mcp-server-filesystem", "--root", "/tmp"],
            env_vars={"MCP_LOG_LEVEL": "debug"},
        )

        assert config.command == "uvx"
        assert config.args == ["mcp-server-filesystem", "--root", "/tmp"]
        assert config.env_vars == {"MCP_LOG_LEVEL": "debug"}

    def test_mcp_config_minimal(self):
        """Test creating MCPConfig with minimal required fields."""
        config = MCPConfig(command="uvx mcp-server-filesystem")

        assert config.command == "uvx mcp-server-filesystem"
        assert config.args == []
        assert config.env_vars == {}

    def test_mcp_config_serialization(self):
        """Test MCPConfig serialization."""
        config = MCPConfig(
            command="uvx",
            args=["mcp-server-filesystem"],
            env_vars={"LOG_LEVEL": "info"},
        )

        json_str = config.model_dump_json()
        loaded = MCPConfig.model_validate_json(json_str)
        assert loaded.command == config.command
        assert loaded.args == config.args
        assert loaded.env_vars == config.env_vars


class TestAuthConfig:
    """Test AuthConfig model."""

    def test_auth_config_full(self):
        """Test creating AuthConfig with all fields."""
        config = AuthConfig(
            required=True,
            env_var="BRAVE_API_KEY",
            signup_url="https://brave.com/signup",
            description="API key for Brave Search",
        )

        assert config.required is True
        assert config.env_var == "BRAVE_API_KEY"
        assert config.signup_url == "https://brave.com/signup"
        assert config.description == "API key for Brave Search"

    def test_auth_config_minimal(self):
        """Test creating AuthConfig with minimal required fields."""
        config = AuthConfig(required=False, env_var="API_KEY")

        assert config.required is False
        assert config.env_var == "API_KEY"
        assert config.signup_url is None
        assert config.description is None

    def test_auth_config_validation(self):
        """Test AuthConfig validation."""
        # Empty env_var should fail
        with pytest.raises(ValidationError):
            AuthConfig(required=True, env_var="")

    def test_auth_config_serialization(self):
        """Test AuthConfig serialization."""
        config = AuthConfig(
            required=True,
            env_var="API_KEY",
            signup_url="https://example.com",
            description="Test API key",
        )

        json_str = config.model_dump_json()
        loaded = AuthConfig.model_validate_json(json_str)
        assert loaded.required == config.required
        assert loaded.env_var == config.env_var
        assert loaded.signup_url == config.signup_url
        assert loaded.description == config.description
