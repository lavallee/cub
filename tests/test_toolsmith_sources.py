"""
Tests for tool source protocol and registry.

Tests the ToolSource protocol, source registration, registry management,
and all registry functions.
"""

import pytest

from cub.core.toolsmith import sources as sources_module
from cub.core.toolsmith.models import Tool, ToolType
from cub.core.toolsmith.sources import (
    ToolSource,
    get_all_sources,
    get_source,
    list_sources,
    register_source,
)


class TestSourceRegistry:
    """Test source registration and retrieval."""

    def test_register_source(self) -> None:
        """Test registering a source."""

        @register_source("test-source")
        class TestSource:
            @property
            def name(self) -> str:
                return "test-source"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        # Verify source is registered
        assert "test-source" in list_sources()

        # Clean up
        sources_module._sources.pop("test-source", None)

    def test_register_source_duplicate_raises(self) -> None:
        """Test registering a duplicate source name raises ValueError."""

        @register_source("duplicate-source")
        class TestSource1:
            @property
            def name(self) -> str:
                return "duplicate-source"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        # Try to register with same name
        with pytest.raises(ValueError, match="already registered"):

            @register_source("duplicate-source")
            class TestSource2:
                @property
                def name(self) -> str:
                    return "duplicate-source"

                def fetch_tools(self) -> list[Tool]:
                    return []

                def search_live(self, query: str) -> list[Tool]:
                    return []

        # Clean up
        sources_module._sources.pop("duplicate-source", None)

    def test_get_source_by_name(self) -> None:
        """Test getting a source by name returns instantiated object."""

        @register_source("test-get")
        class TestSource:
            @property
            def name(self) -> str:
                return "test-get"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        source = get_source("test-get")
        assert source.name == "test-get"
        assert isinstance(source, TestSource)

        # Clean up
        sources_module._sources.pop("test-get", None)

    def test_get_source_invalid_name_raises(self) -> None:
        """Test getting an invalid source raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            get_source("nonexistent-source")

    def test_get_source_returns_fresh_instance(self) -> None:
        """Test get_source returns fresh instances on each call."""

        @register_source("instance-test")
        class TestSource:
            @property
            def name(self) -> str:
                return "instance-test"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        source1 = get_source("instance-test")
        source2 = get_source("instance-test")
        # Both are instances of the class, but different objects
        assert isinstance(source1, TestSource)
        assert isinstance(source2, TestSource)
        assert source1 is not source2

        # Clean up
        sources_module._sources.pop("instance-test", None)

    def test_list_sources_returns_sorted(self) -> None:
        """Test list_sources returns alphabetically sorted source names."""

        @register_source("zeta")
        class ZetaSource:
            @property
            def name(self) -> str:
                return "zeta"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        @register_source("alpha")
        class AlphaSource:
            @property
            def name(self) -> str:
                return "alpha"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        @register_source("beta")
        class BetaSource:
            @property
            def name(self) -> str:
                return "beta"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        sources = list_sources()
        # Find our registered sources in the list
        our_sources = [s for s in sources if s in ("alpha", "beta", "zeta")]
        assert our_sources == ["alpha", "beta", "zeta"]

        # Clean up
        sources_module._sources.pop("zeta", None)
        sources_module._sources.pop("alpha", None)
        sources_module._sources.pop("beta", None)

    def test_get_all_sources_returns_list(self) -> None:
        """Test get_all_sources returns list of instantiated sources."""

        @register_source("source-a")
        class SourceA:
            @property
            def name(self) -> str:
                return "source-a"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        @register_source("source-b")
        class SourceB:
            @property
            def name(self) -> str:
                return "source-b"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        all_sources = get_all_sources()
        # Should have at least our two sources
        assert len(all_sources) >= 2
        names = [s.name for s in all_sources]
        assert "source-a" in names
        assert "source-b" in names

        # Clean up
        sources_module._sources.pop("source-a", None)
        sources_module._sources.pop("source-b", None)


class TestToolSourceProtocol:
    """Test ToolSource protocol implementation and contract."""

    def test_protocol_name_property(self) -> None:
        """Test ToolSource requires name property."""

        @register_source("proto-test-name")
        class GoodSource:
            @property
            def name(self) -> str:
                return "proto-test-name"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        source = get_source("proto-test-name")
        assert source.name == "proto-test-name"

        # Clean up
        sources_module._sources.pop("proto-test-name", None)

    def test_protocol_fetch_tools_method(self) -> None:
        """Test ToolSource requires fetch_tools method."""

        @register_source("proto-test-fetch")
        class GoodSource:
            @property
            def name(self) -> str:
                return "proto-test-fetch"

            def fetch_tools(self) -> list[Tool]:
                tool = Tool(
                    id="test:tool1",
                    name="Tool 1",
                    source="test",
                    source_url="http://example.com",
                    tool_type=ToolType.MCP_SERVER,
                    description="Test tool",
                )
                return [tool]

            def search_live(self, query: str) -> list[Tool]:
                return []

        source = get_source("proto-test-fetch")
        tools = source.fetch_tools()
        assert len(tools) == 1
        assert tools[0].id == "test:tool1"

        # Clean up
        sources_module._sources.pop("proto-test-fetch", None)

    def test_protocol_search_live_method(self) -> None:
        """Test ToolSource requires search_live method."""

        @register_source("proto-test-search")
        class GoodSource:
            @property
            def name(self) -> str:
                return "proto-test-search"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                if query == "linter":
                    tool = Tool(
                        id="test:eslint",
                        name="ESLint",
                        source="test",
                        source_url="http://example.com",
                        tool_type=ToolType.MCP_SERVER,
                        description="Linter",
                    )
                    return [tool]
                return []

        source = get_source("proto-test-search")
        results = source.search_live("linter")
        assert len(results) == 1
        assert results[0].id == "test:eslint"

        no_results = source.search_live("formatter")
        assert len(no_results) == 0

        # Clean up
        sources_module._sources.pop("proto-test-search", None)

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test ToolSource protocol is runtime_checkable."""

        @register_source("proto-runtime-test")
        class ValidSource:
            @property
            def name(self) -> str:
                return "proto-runtime-test"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        source = get_source("proto-runtime-test")
        # Should recognize the source as implementing ToolSource protocol
        assert isinstance(source, ToolSource)

        # Clean up
        sources_module._sources.pop("proto-runtime-test", None)


class TestSourceBehavior:
    """Test real source behavior and contracts."""

    def test_fetch_tools_returns_list(self) -> None:
        """Test fetch_tools returns list of Tool objects."""

        @register_source("fetch-test")
        class FetchSource:
            @property
            def name(self) -> str:
                return "fetch-test"

            def fetch_tools(self) -> list[Tool]:
                return [
                    Tool(
                        id="test:tool1",
                        name="Tool 1",
                        source="test",
                        source_url="http://example.com",
                        tool_type=ToolType.MCP_SERVER,
                        description="Test",
                    ),
                    Tool(
                        id="test:tool2",
                        name="Tool 2",
                        source="test",
                        source_url="http://example.com",
                        tool_type=ToolType.SKILL,
                        description="Test",
                    ),
                ]

            def search_live(self, query: str) -> list[Tool]:
                return []

        source = get_source("fetch-test")
        tools = source.fetch_tools()
        assert isinstance(tools, list)
        assert len(tools) == 2
        assert all(isinstance(t, Tool) for t in tools)

        # Clean up
        sources_module._sources.pop("fetch-test", None)

    def test_search_live_returns_list(self) -> None:
        """Test search_live returns list of Tool objects."""

        @register_source("search-test")
        class SearchSource:
            @property
            def name(self) -> str:
                return "search-test"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                if "linter" in query.lower():
                    return [
                        Tool(
                            id="test:eslint",
                            name="ESLint",
                            source="test",
                            source_url="http://example.com",
                            tool_type=ToolType.MCP_SERVER,
                            description="Linter",
                        )
                    ]
                return []

        source = get_source("search-test")
        results = source.search_live("linter")
        assert isinstance(results, list)
        assert len(results) == 1

        # Clean up
        sources_module._sources.pop("search-test", None)

    def test_source_with_empty_results(self) -> None:
        """Test source can return empty list from fetch_tools and search_live."""

        @register_source("empty-test")
        class EmptySource:
            @property
            def name(self) -> str:
                return "empty-test"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        source = get_source("empty-test")
        assert source.fetch_tools() == []
        assert source.search_live("anything") == []

        # Clean up
        sources_module._sources.pop("empty-test", None)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_get_source_empty_registry_message(self) -> None:
        """Test error message when no sources are registered."""
        # Temporarily clear registry
        original = sources_module._sources.copy()
        sources_module._sources.clear()

        try:
            with pytest.raises(ValueError, match="none registered"):
                get_source("any-source")
        finally:
            # Restore registry
            sources_module._sources.update(original)

    def test_list_sources_empty_list(self) -> None:
        """Test list_sources returns empty list when no sources registered."""
        # Temporarily clear registry
        original = sources_module._sources.copy()
        sources_module._sources.clear()

        try:
            sources = list_sources()
            assert sources == []
        finally:
            # Restore registry
            sources_module._sources.update(original)

    def test_get_all_sources_empty_list(self) -> None:
        """Test get_all_sources returns empty list when no sources registered."""
        # Temporarily clear registry
        original = sources_module._sources.copy()
        sources_module._sources.clear()

        try:
            sources = get_all_sources()
            assert sources == []
        finally:
            # Restore registry
            sources_module._sources.update(original)

    def test_source_name_property_consistent(self) -> None:
        """Test source name property returns consistent value."""

        @register_source("consistent")
        class ConsistentSource:
            @property
            def name(self) -> str:
                return "consistent"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        source = get_source("consistent")
        # Call multiple times, should get same value
        assert source.name == "consistent"
        assert source.name == "consistent"
        assert source.name == "consistent"

        # Clean up
        sources_module._sources.pop("consistent", None)
