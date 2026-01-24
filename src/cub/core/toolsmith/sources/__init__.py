"""
Tool source protocol and registry.

This module provides:
- ToolSource: Protocol that all tool sources must implement
- @register_source: Decorator for registering source implementations
- get_source(): Get a source instance by name
- list_sources(): Get all registered source names
- get_all_sources(): Get all registered source instances

Example:
    >>> from cub.core.toolsmith.sources import ToolSource, register_source, get_source
    >>> from cub.core.toolsmith.models import Tool
    >>>
    >>> @register_source('example')
    ... class ExampleSource:
    ...     @property
    ...     def name(self) -> str:
    ...         return 'example'
    ...
    ...     def fetch_tools(self) -> list[Tool]:
    ...         return []
    ...
    ...     def search_live(self, query: str) -> list[Tool]:
    ...         return []
    >>>
    >>> source = get_source('example')
    >>> source.name
    'example'
"""

from cub.core.toolsmith.sources import base as _base
from cub.core.toolsmith.sources.base import (
    ToolSource,
    get_all_sources,
    get_source,
    list_sources,
    register_source,
)

# Import source implementations to register them
from cub.core.toolsmith.sources import glama as _glama  # noqa: F401
from cub.core.toolsmith.sources import mcp_official as _mcp_official  # noqa: F401
from cub.core.toolsmith.sources import skillsmp as _skillsmp  # noqa: F401
from cub.core.toolsmith.sources import smithery as _smithery  # noqa: F401

# Expose the registry for testing purposes
_sources = _base._sources

__all__ = [
    "ToolSource",
    "register_source",
    "get_source",
    "list_sources",
    "get_all_sources",
]
