"""
Tool adapters for various execution backends.

This package provides concrete implementations of the ToolAdapter protocol
for different execution backends (HTTP, CLI, MCP stdio, etc.).
"""

from cub.core.tools.adapters.cli import CLIAdapter
from cub.core.tools.adapters.http import HTTPAdapter
from cub.core.tools.adapters.mcp_stdio import MCPStdioAdapter

__all__ = ["CLIAdapter", "HTTPAdapter", "MCPStdioAdapter"]
