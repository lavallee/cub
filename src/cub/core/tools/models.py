"""
Tool execution models and adapter configuration.

This module defines Pydantic models for tool execution results, adapter-specific
configurations (HTTP, CLI, MCP), tool registry, and tool configurations. These
models ensure consistent data structures across all tool adapters and provide
the foundation for the unified tool ecosystem.

Key Models:
    - ToolResult: Structured result from tool execution
    - ToolConfig: Configuration for an approved tool
    - Registry: Tool registry with approved tools and version tracking
    - ToolMetrics: Execution statistics for tool performance tracking
    - HTTPConfig, CLIConfig, MCPConfig: Adapter-specific configurations
    - AuthConfig: Authentication requirements

Example:
    >>> from cub.core.tools.models import ToolResult, ToolConfig, Registry
    >>> from cub.core.tools.models import HTTPConfig, AdapterType, AuthConfig
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
    >>> # Creating a tool configuration
    >>> tool_config = ToolConfig(
    ...     id="brave-search",
    ...     name="Brave Search",
    ...     adapter_type=AdapterType.HTTP,
    ...     capabilities=["web_search", "current_events"],
    ...     http_config=HTTPConfig(
    ...         base_url="https://api.brave.com",
    ...         endpoints={"search": "/v1/web/search"},
    ...         headers={"Accept": "application/json"},
    ...         auth_header="X-API-Key",
    ...         auth_env_var="BRAVE_API_KEY"
    ...     ),
    ...     auth=AuthConfig(
    ...         required=True,
    ...         env_var="BRAVE_API_KEY",
    ...         signup_url="https://brave.com/search/api/"
    ...     ),
    ...     adopted_at=datetime.now(timezone.utc),
    ...     adopted_from="mcp-official"
    ... )
    >>>
    >>> # Creating a registry
    >>> registry = Registry(version="1.0.0")
    >>> registry.add(tool_config)
    >>> found = registry.find_by_capability("web_search")
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


class ToolConfig(BaseModel):
    """
    Configuration for an approved tool.

    ToolConfig represents a tool that has been approved for execution with all
    configuration needed to invoke it. Tools are adopted from the catalog into
    the registry, transitioning from "known" to "runnable".

    Attributes:
        id: Unique tool identifier (e.g., "brave-search")
        name: Human-readable tool name
        adapter_type: Type of adapter to use (http | cli | mcp_stdio)
        capabilities: List of capabilities this tool provides (e.g., ["web_search"])
        http_config: HTTP adapter configuration (if adapter_type is HTTP)
        cli_config: CLI adapter configuration (if adapter_type is CLI)
        mcp_config: MCP adapter configuration (if adapter_type is MCP_STDIO)
        auth: Authentication requirements and configuration
        adopted_at: Timestamp when tool was adopted into registry
        adopted_from: Source where tool was adopted from (e.g., "mcp-official")
        version_hash: Optional hash for detecting version changes requiring re-approval
    """

    id: str = Field(
        ...,
        min_length=1,
        description="Unique tool identifier",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Human-readable tool name",
    )
    adapter_type: AdapterType = Field(
        ...,
        description="Type of adapter to use for execution",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of capabilities this tool provides",
    )

    # Adapter-specific configurations (mutually exclusive by adapter_type)
    http_config: HTTPConfig | None = Field(
        default=None,
        description="HTTP adapter configuration",
    )
    cli_config: CLIConfig | None = Field(
        default=None,
        description="CLI adapter configuration",
    )
    mcp_config: MCPConfig | None = Field(
        default=None,
        description="MCP adapter configuration",
    )

    # Authentication
    auth: AuthConfig | None = Field(
        default=None,
        description="Authentication requirements and configuration",
    )

    # Adoption metadata
    adopted_at: datetime = Field(
        ...,
        description="Timestamp when tool was adopted into registry",
    )
    adopted_from: str = Field(
        ...,
        min_length=1,
        description="Source where tool was adopted from",
    )
    version_hash: str | None = Field(
        default=None,
        description="Optional hash for detecting version changes",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("adopted_at", mode="before")
    @classmethod
    def normalize_adopted_at(cls, v: datetime | str) -> datetime:
        """
        Normalize adopted_at to timezone-aware datetime.

        Args:
            v: The adopted_at value (datetime or ISO string)

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
                normalized = v.replace("Z", "+00:00") if v.endswith("Z") else v
                dt = datetime.fromisoformat(normalized)
                # Ensure timezone-aware (treat naive as UTC)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError as e:
                raise ValueError(f"Invalid 'adopted_at' timestamp format: {v}") from e
        raise ValueError(f"Invalid 'adopted_at' type: {type(v)}")

    @field_validator("adapter_type")
    @classmethod
    def validate_adapter_config(cls, v: AdapterType, info: Any) -> AdapterType:
        """
        Validate that appropriate config is provided for adapter_type.

        Note: This validator only checks after all fields are set. The actual
        validation happens in model_validator with mode='after'.

        Args:
            v: The adapter_type value

        Returns:
            The validated adapter_type
        """
        # Validation happens in model_validator below
        return v

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str]) -> list[str]:
        """
        Validate capabilities list.

        Args:
            v: The capabilities list

        Returns:
            The validated capabilities list

        Raises:
            ValueError: If capabilities contains empty strings
        """
        if any(not cap.strip() for cap in v):
            raise ValueError("Capabilities cannot contain empty strings")
        return v

    def get_adapter_config(self) -> HTTPConfig | CLIConfig | MCPConfig:
        """
        Get the adapter configuration for this tool.

        Returns:
            The adapter-specific configuration

        Raises:
            ValueError: If no adapter configuration is set
        """
        match self.adapter_type:
            case AdapterType.HTTP:
                if self.http_config is None:
                    raise ValueError("HTTP adapter requires http_config")
                return self.http_config
            case AdapterType.CLI:
                if self.cli_config is None:
                    raise ValueError("CLI adapter requires cli_config")
                return self.cli_config
            case AdapterType.MCP_STDIO:
                if self.mcp_config is None:
                    raise ValueError("MCP stdio adapter requires mcp_config")
                return self.mcp_config


class ToolMetrics(BaseModel):
    """
    Execution statistics for a tool.

    Tracks usage metrics for a tool, including invocation count, success/failure
    rates, timing statistics, and error tracking. These metrics enable the learning
    loop to evaluate tool reliability and performance over time.

    Attributes:
        tool_id: Unique identifier of the tool being tracked
        invocations: Total number of times the tool has been invoked
        successes: Number of successful invocations
        failures: Number of failed invocations
        total_duration_ms: Cumulative execution time across all invocations (milliseconds)
        min_duration_ms: Fastest execution time (milliseconds)
        max_duration_ms: Slowest execution time (milliseconds)
        avg_duration_ms: Average execution time (milliseconds)
        error_types: Mapping of error types to their occurrence counts
        last_used_at: Timestamp of most recent invocation
        first_used_at: Timestamp of first invocation
    """

    tool_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier of the tool being tracked",
    )
    invocations: int = Field(
        default=0,
        ge=0,
        description="Total number of invocations",
    )
    successes: int = Field(
        default=0,
        ge=0,
        description="Number of successful invocations",
    )
    failures: int = Field(
        default=0,
        ge=0,
        description="Number of failed invocations",
    )
    total_duration_ms: int = Field(
        default=0,
        ge=0,
        description="Cumulative execution time (milliseconds)",
    )
    min_duration_ms: int | None = Field(
        default=None,
        description="Fastest execution time (milliseconds)",
    )
    max_duration_ms: int | None = Field(
        default=None,
        description="Slowest execution time (milliseconds)",
    )
    avg_duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Average execution time (milliseconds)",
    )
    error_types: dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of error types to occurrence counts",
    )
    last_used_at: datetime | None = Field(
        default=None,
        description="Timestamp of most recent invocation",
    )
    first_used_at: datetime | None = Field(
        default=None,
        description="Timestamp of first invocation",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("last_used_at", "first_used_at", mode="before")
    @classmethod
    def normalize_timestamps(cls, v: datetime | str | None) -> datetime | None:
        """
        Normalize timestamp fields to timezone-aware datetime.

        Args:
            v: The timestamp value (datetime, ISO string, or None)

        Returns:
            Timezone-aware datetime or None

        Raises:
            ValueError: If datetime string cannot be parsed
        """
        if v is None:
            return None
        if isinstance(v, datetime):
            # Ensure timezone-aware (treat naive as UTC)
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        if isinstance(v, str):
            try:
                # Handle 'Z' suffix for UTC (Python 3.10 compatibility)
                normalized = v.replace("Z", "+00:00") if v.endswith("Z") else v
                dt = datetime.fromisoformat(normalized)
                # Ensure timezone-aware (treat naive as UTC)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError as e:
                raise ValueError(f"Invalid timestamp format: {v}") from e
        raise ValueError(f"Invalid timestamp type: {type(v)}")

    def success_rate(self) -> float:
        """
        Calculate success rate as a percentage.

        Returns:
            Success rate (0.0-100.0), or 0.0 if no invocations
        """
        if self.invocations == 0:
            return 0.0
        return (self.successes / self.invocations) * 100

    def failure_rate(self) -> float:
        """
        Calculate failure rate as a percentage.

        Returns:
            Failure rate (0.0-100.0), or 0.0 if no invocations
        """
        if self.invocations == 0:
            return 0.0
        return (self.failures / self.invocations) * 100

    def record_execution(self, result: ToolResult) -> None:
        """
        Update metrics based on a tool execution result.

        Args:
            result: The ToolResult from tool execution
        """
        # Increment invocation count
        self.invocations += 1

        # Update success/failure counts
        if result.success:
            self.successes += 1
        else:
            self.failures += 1
            # Track error type if present
            if result.error_type:
                self.error_types[result.error_type] = (
                    self.error_types.get(result.error_type, 0) + 1
                )

        # Update timing statistics
        self.total_duration_ms += result.duration_ms

        if self.min_duration_ms is None or result.duration_ms < self.min_duration_ms:
            self.min_duration_ms = result.duration_ms

        if self.max_duration_ms is None or result.duration_ms > self.max_duration_ms:
            self.max_duration_ms = result.duration_ms

        self.avg_duration_ms = self.total_duration_ms / self.invocations

        # Update timestamps
        if self.first_used_at is None:
            self.first_used_at = result.started_at

        self.last_used_at = result.started_at


class Registry(BaseModel):
    """
    Tool registry with approved tools.

    Registry holds all approved tools with version tracking. It serves as the
    source of truth for which tools can be executed. Registries exist at both
    user and project levels, with project-level overriding user-level.

    Storage locations:
    - User: ~/.config/cub/tools/registry.json
    - Project: .cub/tools/registry.json

    Attributes:
        version: Registry schema version (semantic versioning)
        tools: Mapping of tool IDs to their configurations
    """

    version: str = Field(
        default="1.0.0",
        description="Registry schema version",
    )
    tools: dict[str, ToolConfig] = Field(
        default_factory=dict,
        description="Mapping of tool IDs to configurations",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("version", mode="before")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """
        Validate version format (semantic versioning).

        Args:
            v: The version string to validate

        Returns:
            The validated version

        Raises:
            ValueError: If version format is invalid
        """
        if not isinstance(v, str):
            raise ValueError("Version must be a string")
        if not v:
            raise ValueError("Version cannot be empty")
        # Allow semantic versioning formats: X.Y.Z, X.Y.Z-prerelease
        import re

        if not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$", v):
            raise ValueError(
                f"Invalid version format: '{v}' (expected semantic version like 1.0.0)"
            )
        return v

    def get(self, tool_id: str) -> ToolConfig | None:
        """
        Get a tool configuration by ID.

        Args:
            tool_id: The tool identifier

        Returns:
            The tool configuration, or None if not found
        """
        return self.tools.get(tool_id)

    def add(self, tool: ToolConfig) -> None:
        """
        Add a tool to the registry.

        Args:
            tool: The tool configuration to add
        """
        self.tools[tool.id] = tool

    def remove(self, tool_id: str) -> bool:
        """
        Remove a tool from the registry.

        Args:
            tool_id: The tool identifier

        Returns:
            True if tool was removed, False if not found
        """
        if tool_id in self.tools:
            del self.tools[tool_id]
            return True
        return False

    def find_by_capability(self, capability: str) -> list[ToolConfig]:
        """
        Find all tools that provide a specific capability.

        Args:
            capability: The capability to search for

        Returns:
            List of tool configurations that provide the capability
        """
        return [tool for tool in self.tools.values() if capability in tool.capabilities]

    def list_all(self) -> list[ToolConfig]:
        """
        Get all tools in the registry.

        Returns:
            List of all tool configurations
        """
        return list(self.tools.values())
