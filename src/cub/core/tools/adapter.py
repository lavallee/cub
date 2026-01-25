"""
Tool adapter protocol and registry.

This module defines the ToolAdapter protocol that all tool adapters
must implement, enabling pluggable tool execution backends (HTTP, CLI, MCP stdio, etc.).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolResult:
    """
    Structured result from tool execution.

    Attributes:
        success: Whether the tool executed successfully
        output: Structured data returned by the tool (dict, list, str, etc.)
        output_markdown: Optional human-readable summary of the result
        duration_ms: Execution time in milliseconds
        tokens_used: Optional token count for LLM-based tools
        error: Optional error message if success=False
        metadata: Additional execution metadata (headers, status codes, etc.)
    """

    success: bool
    output: Any
    output_markdown: str | None = None
    duration_ms: int = 0
    tokens_used: int | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


@runtime_checkable
class ToolAdapter(Protocol):
    """
    Protocol for tool adapter implementations.

    All tool adapters (HTTP, CLI, MCP stdio, skill bridge) must implement
    this interface to be compatible with the cub tool execution runtime.

    Adapters are responsible for:
    - Executing tool actions with parameters
    - Checking tool availability/readiness
    - Handling timeouts and errors consistently
    - Returning structured results with timing info
    """

    @property
    def adapter_type(self) -> str:
        """
        Adapter type identifier (e.g., 'http', 'cli', 'mcp-stdio').

        Returns:
            Lowercase adapter type string
        """
        ...

    async def execute(
        self,
        tool_id: str,
        action: str,
        params: dict[str, Any],
        timeout: float = 30.0,
    ) -> ToolResult:
        """
        Execute a tool action with parameters.

        Runs the tool action and returns a structured result with timing,
        output data, and any errors encountered.

        Args:
            tool_id: Tool identifier from registry
            action: Action/method to invoke (e.g., 'search', 'send_email')
            params: Parameters for the action (validated by caller)
            timeout: Execution timeout in seconds (default: 30.0)

        Returns:
            ToolResult with output data, timing, and error info

        Raises:
            TimeoutError: If execution exceeds timeout
            RuntimeError: If tool execution fails critically
        """
        ...

    async def is_available(self, tool_id: str) -> bool:
        """
        Check if a tool is available and ready to execute.

        Verifies that the tool can be invoked. For CLI tools, checks if
        the command exists in PATH. For HTTP tools, checks credentials.
        For MCP tools, checks if server can be launched.

        Args:
            tool_id: Tool identifier from registry

        Returns:
            True if tool is ready to execute
        """
        ...

    async def health_check(self) -> bool:
        """
        Check if the adapter itself is healthy.

        Verifies the adapter's runtime environment (e.g., network connectivity
        for HTTP, subprocess support for CLI, MCP server launcher availability).

        Returns:
            True if adapter is operational
        """
        ...


# Adapter registry
_adapters: dict[str, type[ToolAdapter]] = {}


def register_adapter(
    adapter_type: str,
) -> Callable[[type[ToolAdapter]], type[ToolAdapter]]:
    """
    Decorator to register a tool adapter implementation.

    Usage:
        @register_adapter('http')
        class HttpAdapter:
            @property
            def adapter_type(self) -> str:
                return 'http'

            async def execute(self, ...):
                ...

    Args:
        adapter_type: Adapter type identifier (e.g., 'http', 'cli', 'mcp-stdio')

    Returns:
        Decorator function
    """

    def decorator(adapter_class: type[ToolAdapter]) -> type[ToolAdapter]:
        _adapters[adapter_type] = adapter_class
        return adapter_class

    return decorator


def get_adapter(adapter_type: str) -> ToolAdapter:
    """
    Get a tool adapter by type.

    Args:
        adapter_type: Adapter type ('http', 'cli', 'mcp-stdio', etc.)

    Returns:
        ToolAdapter instance

    Raises:
        ValueError: If adapter type is not registered
    """
    adapter_class = _adapters.get(adapter_type)
    if adapter_class is None:
        raise ValueError(
            f"Adapter '{adapter_type}' not registered. "
            f"Available adapters: {', '.join(_adapters.keys())}"
        )

    # Instantiate and return
    return adapter_class()


def list_adapters() -> list[str]:
    """
    List all registered adapter types.

    Returns:
        List of adapter type identifiers
    """
    return list(_adapters.keys())


def is_adapter_available(adapter_type: str) -> bool:
    """
    Check if an adapter type is registered.

    Args:
        adapter_type: Adapter type to check

    Returns:
        True if adapter is registered
    """
    return adapter_type in _adapters
