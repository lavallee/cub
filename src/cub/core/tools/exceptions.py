"""
Custom exceptions for the unified tool ecosystem.

This module defines exceptions for tool execution, registry operations,
and adapter-related errors.

Exception Hierarchy:
    ToolError (base)
    ├── ToolNotAdoptedError (tool not in registry)
    ├── AdapterError (adapter-related errors)
    └── ExecutionError (execution failures)

Example:
    >>> from cub.core.tools.exceptions import ToolNotAdoptedError
    >>> try:
    ...     # Attempt to execute unapproved tool
    ...     raise ToolNotAdoptedError("my-tool", "Tool not found in registry")
    ... except ToolNotAdoptedError as e:
    ...     print(f"Tool '{e.tool_id}' cannot be executed: {e}")
"""


class ToolError(Exception):
    """
    Base exception for all tool-related errors.

    All custom exceptions in the tool execution system inherit from this base.
    Provides consistent error handling and context preservation across the
    unified tool ecosystem.

    Attributes:
        message: Human-readable error message
        context: Optional dictionary of additional context
    """

    def __init__(self, message: str, **context: object) -> None:
        """
        Initialize a tool error with message and context.

        Args:
            message: Human-readable error message
            **context: Additional context as keyword arguments
        """
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        """Return string representation of the error."""
        return self.message


class ToolNotAdoptedError(ToolError):
    """
    Exception raised when attempting to execute a tool not in the registry.

    Raised when a tool execution is attempted but the tool has not been
    adopted into the registry. This is the gate check that enforces the
    adopt-before-execute flow.

    Attributes:
        tool_id: The ID of the tool that was not found
        message: Human-readable error message
        context: Additional context about the failure

    Example:
        >>> raise ToolNotAdoptedError(
        ...     "brave-search",
        ...     "Tool 'brave-search' must be adopted before execution"
        ... )
    """

    def __init__(self, tool_id: str, message: str, **context: object) -> None:
        """
        Initialize a tool not adopted error.

        Args:
            tool_id: The tool identifier that was not found
            message: Human-readable error message
            **context: Additional context as keyword arguments
        """
        super().__init__(message, tool_id=tool_id, **context)
        self.tool_id = tool_id

    def __str__(self) -> str:
        """Return string representation with tool ID."""
        return f"Tool '{self.tool_id}' not adopted: {self.message}"


class AdapterError(ToolError):
    """
    Exception for adapter-related errors.

    Raised when an adapter encounters an error during execution, health check,
    or availability check. Includes the adapter type for better error reporting.

    Attributes:
        adapter_type: The type of adapter that failed (e.g., "http", "cli")
        message: Human-readable error message
        context: Additional context about the failure

    Example:
        >>> raise AdapterError(
        ...     "http",
        ...     "HTTP adapter failed to connect",
        ...     url="https://api.example.com"
        ... )
    """

    def __init__(self, adapter_type: str, message: str, **context: object) -> None:
        """
        Initialize an adapter error.

        Args:
            adapter_type: The adapter type that failed
            message: Human-readable error message
            **context: Additional context as keyword arguments
        """
        super().__init__(message, adapter_type=adapter_type, **context)
        self.adapter_type = adapter_type

    def __str__(self) -> str:
        """Return string representation with adapter type."""
        return f"[{self.adapter_type}] {self.message}"


class ExecutionError(ToolError):
    """
    Exception for tool execution failures.

    Raised when a tool execution fails critically (not just returns success=False).
    Used for catastrophic failures like timeouts, network errors, or invalid
    configurations that prevent execution from completing.

    Attributes:
        tool_id: The tool that failed to execute
        message: Human-readable error message
        context: Additional context about the failure

    Example:
        >>> raise ExecutionError(
        ...     "brave-search",
        ...     "Execution timed out",
        ...     timeout=30.0
        ... )
    """

    def __init__(self, tool_id: str, message: str, **context: object) -> None:
        """
        Initialize an execution error.

        Args:
            tool_id: The tool identifier that failed
            message: Human-readable error message
            **context: Additional context as keyword arguments
        """
        super().__init__(message, tool_id=tool_id, **context)
        self.tool_id = tool_id

    def __str__(self) -> str:
        """Return string representation with tool ID."""
        return f"Execution failed for '{self.tool_id}': {self.message}"


__all__ = [
    "ToolError",
    "ToolNotAdoptedError",
    "AdapterError",
    "ExecutionError",
]
