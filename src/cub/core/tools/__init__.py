"""
Tool execution runtime for cub.

This package provides a pluggable tool execution system with support for
multiple adapter types (HTTP, CLI, MCP stdio, skill bridge).

Components:
- ToolAdapter: Protocol for tool execution backends
- ToolResult: Structured result from tool execution
- Adapter registry: Decorator-based registration system

Example:
    from cub.core.tools import get_adapter, ToolResult

    # Get HTTP adapter
    adapter = get_adapter('http')

    # Execute a tool
    result = await adapter.execute(
        tool_id='brave-search',
        action='search',
        params={'query': 'Python async patterns'},
        timeout=10.0
    )

    if result.success:
        print(f"Found {len(result.output)} results")
    else:
        print(f"Error: {result.error}")
"""

# Export protocol and models
from .adapter import (
    ToolAdapter,
    ToolResult,
    get_adapter,
    is_adapter_available,
    list_adapters,
    register_adapter,
)

__all__ = [
    "ToolAdapter",
    "ToolResult",
    "get_adapter",
    "is_adapter_available",
    "list_adapters",
    "register_adapter",
]
