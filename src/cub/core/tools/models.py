"""
Tool execution models and adapter configuration.

This module defines Pydantic models for tool execution results and
adapter-specific configurations (HTTP, CLI, MCP). These models ensure
consistent data structures across all tool adapters.

Example:
    >>> from cub.core.tools.models import ToolResult, HTTPConfig, AdapterType
    >>> from datetime import datetime, timezone
    >>>
    >>> # Creating a tool result
    >>> result = ToolResult(
    ...     tool_id="brave-search",
    ...     action="search",
    ...     success=True,
    ...     output={"results": [{"title": "Example", "url": "https://example.com"}]},
    ...     started_at=datetime.now(timezone.utc),
    ...     duration_ms=250,
    ...     adapter_type=AdapterType.HTTP
    ... )
    >>>
    >>> # Creating HTTP adapter config
    >>> http_config = HTTPConfig(
    ...     base_url="https://api.brave.com",
    ...     endpoints={"search": "/v1/web/search"},
    ...     headers={"Accept": "application/json"},
    ...     auth_header="X-API-Key",
    ...     auth_env_var="BRAVE_API_KEY"
    ... )
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdapterType(str, Enum):
    """Tool adapter type enumeration."""

    HTTP = "http"
    CLI = "cli"
    MCP_STDIO = "mcp_stdio"


class ToolResult(BaseModel):
    """
    Structured result from tool execution.

    Provides a unified structure for all tool adapters to return execution results,
    including success/failure status, output data, timing information, and metadata.

    Attributes:
        tool_id: Unique identifier of the tool that was executed
        action: Action or method that was invoked (e.g., 'search', 'send_email')
        success: Whether the tool executed successfully
        output: Structured data returned by the tool (dict, list, str, etc.)
        output_markdown: Optional human-readable markdown summary of the result
        started_at: Timestamp when execution started (ISO 8601, timezone-aware)
        duration_ms: Execution time in milliseconds
        tokens_used: Optional token count for LLM-based tools
        error: Optional error message if success=False
        error_type: Optional error classification (timeout, auth, network, etc.)
        adapter_type: Type of adapter that executed the tool
        artifact_path: Optional path to saved execution artifacts
        metadata: Additional execution metadata (headers, status codes, etc.)
    """

    tool_id: str = Field(..., description="Unique identifier of the executed tool")
    action: str = Field(..., description="Action or method invoked")
    success: bool = Field(..., description="Whether execution succeeded")
    output: Any = Field(..., description="Structured data returned by the tool")

    output_markdown: str | None = Field(
        default=None,
        description="Optional human-readable markdown summary",
    )
    started_at: datetime = Field(
        ...,
        description="Timestamp when execution started (ISO 8601, timezone-aware)",
    )
    duration_ms: int = Field(
        default=0,
        ge=0,
        description="Execution time in milliseconds",
    )
    tokens_used: int | None = Field(
        default=None,
        description="Optional token count for LLM-based tools",
    )
    error: str | None = Field(
        default=None,
        description="Optional error message if success=False",
    )
    error_type: str | None = Field(
        default=None,
        description="Optional error classification (timeout, auth, network, etc.)",
    )
    adapter_type: AdapterType = Field(
        ...,
        description="Type of adapter that executed the tool",
    )
    artifact_path: str | None = Field(
        default=None,
        description="Optional path to saved execution artifacts",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional execution metadata (headers, status codes, etc.)",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("started_at", mode="before")
    @classmethod
    def normalize_started_at(cls, v: datetime | str) -> datetime:
        """
        Normalize started_at to timezone-aware datetime.

        Args:
            v: The started_at value (datetime or ISO string)

        Returns:
            Timezone-aware datetime

        Raises:
            ValueError: If datetime string cannot be parsed
        """
        if isinstance(v, datetime):
            # Ensure timezone-aware (treat naive as UTC)
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        if isinstance(v, str):
            try:
                # Handle 'Z' suffix for UTC (Python 3.10 compatibility)
                # datetime.fromisoformat() didn't support 'Z' until Python 3.11
                normalized = v.replace("Z", "+00:00") if v.endswith("Z") else v
                dt = datetime.fromisoformat(normalized)
                # Ensure timezone-aware (treat naive as UTC)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError as e:
                raise ValueError(f"Invalid 'started_at' timestamp format: {v}") from e
        raise ValueError(f"Invalid 'started_at' type: {type(v)}")


class HTTPConfig(BaseModel):
    """
    Configuration for HTTP-based tool adapters.

    Defines how to make HTTP requests to external APIs, including URL construction,
    headers, and authentication configuration.

    Attributes:
        base_url: Base URL for API requests (e.g., "https://api.example.com")
        endpoints: Mapping of action names to URL paths (e.g., {"search": "/v1/search"})
        headers: Static headers to include in all requests (e.g., {"Accept": "application/json"})
        auth_header: Optional header name for authentication (e.g., "X-API-Key", "Authorization")
        auth_env_var: Optional environment variable name containing auth credentials
    """

    base_url: str = Field(
        ...,
        min_length=1,
        description="Base URL for API requests",
    )
    endpoints: dict[str, str] = Field(
        ...,
        description="Mapping of action names to URL paths",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Static headers to include in all requests",
    )
    auth_header: str | None = Field(
        default=None,
        description="Optional header name for authentication",
    )
    auth_env_var: str | None = Field(
        default=None,
        description="Optional environment variable name containing auth credentials",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )


class CLIConfig(BaseModel):
    """
    Configuration for CLI-based tool adapters.

    Defines how to execute command-line tools, including command construction,
    output parsing, and environment variable handling.

    Attributes:
        command: Base command to execute (e.g., "gh", "jq", "curl")
        args_template: Optional template string for command arguments
            (e.g., "{action} --query {query}")
        output_format: Expected output format for parsing (json | text | lines)
        env_vars: Environment variables to set when running the command
    """

    command: str = Field(
        ...,
        min_length=1,
        description="Base command to execute",
    )
    args_template: str | None = Field(
        default=None,
        description="Optional template string for command arguments",
    )
    output_format: str = Field(
        default="text",
        description="Expected output format for parsing (json | text | lines)",
    )
    env_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set when running the command",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """
        Validate output_format is a supported format.

        Args:
            v: The output_format value

        Returns:
            The validated output_format

        Raises:
            ValueError: If output_format is not supported
        """
        valid_formats = {"json", "text", "lines"}
        if v not in valid_formats:
            raise ValueError(
                f"Invalid output_format: '{v}' (must be one of: {', '.join(valid_formats)})"
            )
        return v


class MCPConfig(BaseModel):
    """
    Configuration for MCP (Model Context Protocol) stdio-based tool adapters.

    Defines how to launch and communicate with MCP servers via stdio transport,
    including command, arguments, and environment configuration.

    Attributes:
        command: Command to spawn the MCP server (e.g., "uvx mcp-server-filesystem")
        args: Command-line arguments to pass to the MCP server
        env_vars: Environment variables to set when launching the server
    """

    command: str = Field(
        ...,
        min_length=1,
        description="Command to spawn the MCP server",
    )
    args: list[str] = Field(
        default_factory=list,
        description="Command-line arguments to pass to the MCP server",
    )
    env_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set when launching the server",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )


class AuthConfig(BaseModel):
    """
    Configuration for tool authentication requirements.

    Defines authentication requirements for tools, including whether auth is required,
    where to find credentials, and how to obtain them if missing.

    Attributes:
        required: Whether authentication is required to use this tool
        env_var: Environment variable name containing credentials (e.g., "BRAVE_API_KEY")
        signup_url: Optional URL where users can sign up or obtain credentials
        description: Optional description of what this authentication is for
    """

    required: bool = Field(
        ...,
        description="Whether authentication is required to use this tool",
    )
    env_var: str = Field(
        ...,
        min_length=1,
        description="Environment variable name containing credentials",
    )
    signup_url: str | None = Field(
        default=None,
        description="Optional URL where users can sign up or obtain credentials",
    )
    description: str | None = Field(
        default=None,
        description="Optional description of what this authentication is for",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )
