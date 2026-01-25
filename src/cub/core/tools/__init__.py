"""
Tool execution runtime for cub.

This package provides a pluggable tool execution system with support for
multiple adapter types (HTTP, CLI, MCP stdio, skill bridge).

Components:
- ToolAdapter: Protocol for tool execution backends
- ToolResult: Structured result from tool execution
- ExecutionService: Main entry point for tool execution
- Adapter registry: Decorator-based registration system

Example:
    from cub.core.tools import ExecutionService

    # Initialize service
    service = ExecutionService()

    # Check readiness
    readiness = await service.check_readiness(
        tool_id='brave-search',
        adapter_type='http',
        config={'auth_env_var': 'BRAVE_API_KEY'}
    )

    if readiness.ready:
        # Execute a tool
        result = await service.execute(
            tool_id='brave-search',
            action='search',
            adapter_type='http',
            params={'query': 'Python async patterns'},
            timeout=10.0
        )

        if result.success:
            print(f"Found results: {result.output}")
            print(f"Artifact saved to: {result.artifact_path}")
        else:
            print(f"Error: {result.error}")
    else:
        print(f"Missing: {', '.join(readiness.missing)}")
"""

# Import adapters to trigger registration
from . import adapters as _adapters  # noqa: F401

# Export protocol and models
from .adapter import (
    ToolAdapter,
    get_adapter,
    is_adapter_available,
    list_adapters,
    register_adapter,
)
from .exceptions import (
    AdapterError,
    ExecutionError,
    ToolError,
    ToolNotAdoptedError,
)
from .execution import ExecutionService, ReadinessCheck
from .models import (
    AdapterType,
    AuthConfig,
    CLIConfig,
    HTTPConfig,
    MCPConfig,
    ToolResult,
)

__all__ = [
    # Adapter protocol and registry
    "ToolAdapter",
    "get_adapter",
    "is_adapter_available",
    "list_adapters",
    "register_adapter",
    # Execution service
    "ExecutionService",
    "ReadinessCheck",
    # Exceptions
    "ToolError",
    "ToolNotAdoptedError",
    "AdapterError",
    "ExecutionError",
    # Models
    "AdapterType",
    "AuthConfig",
    "CLIConfig",
    "HTTPConfig",
    "MCPConfig",
    "ToolResult",
]
