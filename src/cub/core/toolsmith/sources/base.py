"""
Tool source protocol and registry.

This module defines the ToolSource protocol that all tool sources
must implement, enabling pluggable tool adapters (npm, PyPI, GitHub, etc.).

The pattern mirrors cub.core.tasks.backend for consistency:
- ToolSource is a runtime_checkable Protocol
- Sources are registered with a decorator
- Registry provides discovery and instantiation
- Sources are instantiated on demand, not at import time
"""

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from cub.core.toolsmith.models import Tool


@runtime_checkable
class ToolSource(Protocol):
    """
    Protocol for tool source implementations.

    All tool sources (npm, PyPI, GitHub, custom, etc.) must implement this interface
    to be compatible with the cub toolsmith system.

    Sources are responsible for:
    - Fetching available tools from their catalog
    - Searching for tools matching a query
    - Providing source metadata and identification
    """

    @property
    def name(self) -> str:
        """
        Get the name of this source.

        Returns:
            Source name (e.g., 'npm', 'pypi', 'github', 'custom')
        """
        ...

    def fetch_tools(self) -> list[Tool]:
        """
        Fetch all available tools from this source.

        This method should retrieve the complete catalog of tools
        from the source. Implementation details vary by source:
        - npm: query npm registry API
        - PyPI: query PyPI registry API
        - GitHub: search GitHub repositories
        - custom: read local catalog files

        Returns:
            List of Tool objects representing all available tools

        Raises:
            Exception: If tool fetching fails (connection error, API error, etc.)
        """
        ...

    def search_live(self, query: str) -> list[Tool]:
        """
        Search for tools matching a query in this source.

        This method performs a live search against the source catalog,
        typically used for real-time discovery and filtering.

        Args:
            query: Search query (e.g., "linter", "eslint", "test")

        Returns:
            List of Tool objects matching the search query

        Raises:
            Exception: If search fails (connection error, API error, etc.)
        """
        ...


# Source registry
_sources: dict[str, type[ToolSource]] = {}


def register_source(name: str) -> Callable[[type[ToolSource]], type[ToolSource]]:
    """
    Decorator to register a tool source implementation.

    Usage:
        @register_source('npm')
        class NpmSource:
            @property
            def name(self) -> str:
                return 'npm'

            def fetch_tools(self) -> list[Tool]:
                ...

            def search_live(self, query: str) -> list[Tool]:
                ...

    Args:
        name: Source name (e.g., 'npm', 'pypi', 'github', 'custom')

    Returns:
        Decorator function

    Raises:
        ValueError: If source name is already registered
    """

    def decorator(source_class: type[ToolSource]) -> type[ToolSource]:
        if name in _sources:
            raise ValueError(
                f"Source '{name}' is already registered. "
                f"Available sources: {', '.join(_sources.keys())}"
            )
        _sources[name] = source_class
        return source_class

    return decorator


def get_source(name: str) -> ToolSource:
    """
    Get a tool source by name.

    Instantiates the source class on demand. Each call returns
    a fresh instance, allowing sources to maintain independent state
    if needed.

    Args:
        name: Source name (e.g., 'npm', 'pypi', 'github', 'custom')

    Returns:
        ToolSource instance

    Raises:
        ValueError: If source name is not registered
    """
    source_class = _sources.get(name)
    if source_class is None:
        available = ", ".join(_sources.keys()) if _sources else "none registered"
        raise ValueError(
            f"Source '{name}' not registered. Available sources: {available}"
        )

    # Instantiate and return
    return source_class()


def list_sources() -> list[str]:
    """
    List all registered source names.

    Returns:
        List of source names in alphabetical order
    """
    return sorted(_sources.keys())


def get_all_sources() -> list[ToolSource]:
    """
    Get all registered sources as instantiated objects.

    Returns a list of all registered tool sources, with each
    source instantiated once. Useful for aggregate operations
    like fetching tools from all sources or syncing all catalogs.

    Returns:
        List of ToolSource instances, one for each registered source

    Raises:
        Exception: If any source instantiation fails
    """
    return [source_class() for source_class in _sources.values()]
