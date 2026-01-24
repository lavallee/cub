"""
Custom exceptions for Toolsmith.

This module defines a hierarchy of exceptions for the Toolsmith system,
providing structured error handling with context preservation.

Exception Hierarchy:
    ToolsmithError (base)
    ├── SourceError (source-related errors)
    │   ├── NetworkError (network/API failures)
    │   └── ParseError (data parsing failures)
    └── StoreError (catalog storage errors)

Example:
    >>> from cub.core.toolsmith.exceptions import NetworkError
    >>> try:
    ...     # Network operation
    ...     raise NetworkError("smithery", "Connection timeout", timeout_value=30.0)
    ... except NetworkError as e:
    ...     print(f"Error from {e.source}: {e}")
    ...     print(f"Context: {e.context}")
"""


class ToolsmithError(Exception):
    """
    Base exception for all Toolsmith errors.

    All custom exceptions in the Toolsmith system inherit from this base.
    Provides consistent error handling and context preservation across
    the tool discovery and catalog management system.

    Attributes:
        message: Human-readable error message
        context: Optional dictionary of additional context
    """

    def __init__(self, message: str, **context: object) -> None:
        """
        Initialize a Toolsmith error with message and context.

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


class SourceError(ToolsmithError):
    """
    Base exception for tool source errors.

    Raised when a tool source encounters an error during fetching,
    searching, or processing tools. Includes the source name for
    better error reporting and debugging.

    Attributes:
        source: Name of the source that failed (e.g., "smithery", "glama")
        message: Human-readable error message
        context: Additional context about the failure
    """

    def __init__(self, source: str, message: str, **context: object) -> None:
        """
        Initialize a source error.

        Args:
            source: Name of the source that failed
            message: Human-readable error message
            **context: Additional context as keyword arguments
        """
        super().__init__(message, source=source, **context)
        self.source = source

    def __str__(self) -> str:
        """Return string representation with source name."""
        return f"[{self.source}] {self.message}"


class NetworkError(SourceError):
    """
    Exception for network-related errors.

    Raised when HTTP requests fail, connections timeout, or other
    network issues occur while communicating with tool sources.

    The original exception is preserved via the __cause__ attribute
    for full context when debugging.

    Example:
        >>> import httpx
        >>> try:
        ...     # HTTP request fails
        ...     raise httpx.ConnectError("Connection refused")
        ... except httpx.ConnectError as e:
        ...     raise NetworkError(
        ...         "smithery",
        ...         "Failed to connect to Smithery API",
        ...         url="https://registry.smithery.ai/servers"
        ...     ) from e
    """

    def __init__(self, source: str, message: str, **context: object) -> None:
        """
        Initialize a network error.

        Args:
            source: Name of the source that failed
            message: Human-readable error message
            **context: Additional context (url, status_code, etc.)
        """
        super().__init__(source, message, **context)


class ParseError(SourceError):
    """
    Exception for data parsing errors.

    Raised when API responses cannot be parsed, validation fails,
    or data is in an unexpected format. Includes details about what
    failed to parse and why.

    Example:
        >>> try:
        ...     # JSON parsing fails
        ...     data = json.loads(bad_json)
        ... except json.JSONDecodeError as e:
        ...     raise ParseError(
        ...         "glama",
        ...         "Invalid JSON in API response",
        ...         field="servers",
        ...         position=e.pos
        ...     ) from e
    """

    def __init__(self, source: str, message: str, **context: object) -> None:
        """
        Initialize a parse error.

        Args:
            source: Name of the source that failed
            message: Human-readable error message
            **context: Additional context (field, expected_type, etc.)
        """
        super().__init__(source, message, **context)


class StoreError(ToolsmithError):
    """
    Exception for catalog storage errors.

    Raised when reading or writing the tool catalog fails due to
    file I/O errors, permission issues, or data corruption.

    Example:
        >>> try:
        ...     # File operation fails
        ...     with open(path, 'r') as f:
        ...         data = f.read()
        ... except IOError as e:
        ...     raise StoreError(
        ...         "Failed to read catalog",
        ...         path=path,
        ...         error=str(e)
        ...     ) from e
    """

    def __init__(self, message: str, **context: object) -> None:
        """
        Initialize a store error.

        Args:
            message: Human-readable error message
            **context: Additional context (path, operation, etc.)
        """
        super().__init__(message, **context)


__all__ = [
    "ToolsmithError",
    "SourceError",
    "NetworkError",
    "ParseError",
    "StoreError",
]
