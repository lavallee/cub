"""Tests for tool source base protocol and registry."""

import pytest

from cub.core.toolsmith.models import Tool, ToolType
from cub.core.toolsmith.sources.base import (
    ToolSource,
    get_all_sources,
    get_source,
    list_sources,
    register_source,
)


class TestSourceRegistry:
    """Tests for source registration and retrieval."""

    def test_get_source_success(self) -> None:
        """Test getting a registered source."""
        # ClawdHub should be registered by default
        source = get_source("clawdhub")
        assert source.name == "clawdhub"

    def test_get_source_not_found(self) -> None:
        """Test getting a non-existent source raises ValueError."""
        with pytest.raises(ValueError, match="Source 'nonexistent' not registered"):
            get_source("nonexistent")

    def test_get_source_error_lists_available_sources(self) -> None:
        """Test that error message lists available sources."""
        with pytest.raises(ValueError, match="Available sources:"):
            get_source("nonexistent")

    def test_list_sources(self) -> None:
        """Test listing all registered sources."""
        sources = list_sources()
        assert isinstance(sources, list)
        assert len(sources) > 0  # Should have at least one source registered
        # Should be sorted
        assert sources == sorted(sources)

    def test_get_all_sources(self) -> None:
        """Test getting all source instances."""
        sources = get_all_sources()
        assert isinstance(sources, list)
        assert len(sources) > 0
        # All should be ToolSource instances
        for source in sources:
            assert isinstance(source, ToolSource)

    def test_register_source_duplicate_raises_error(self) -> None:
        """Test that registering duplicate source name raises ValueError."""

        # First registration should succeed
        @register_source("test_duplicate")
        class TestSource1:
            @property
            def name(self) -> str:
                return "test_duplicate"

            def fetch_tools(self) -> list[Tool]:
                return []

            def search_live(self, query: str) -> list[Tool]:
                return []

        # Second registration with same name should fail
        with pytest.raises(ValueError, match="Source 'test_duplicate' is already registered"):

            @register_source("test_duplicate")
            class TestSource2:
                @property
                def name(self) -> str:
                    return "test_duplicate"

                def fetch_tools(self) -> list[Tool]:
                    return []

                def search_live(self, query: str) -> list[Tool]:
                    return []

    def test_register_and_get_custom_source(self) -> None:
        """Test registering and retrieving a custom source."""

        @register_source("test_custom")
        class CustomSource:
            @property
            def name(self) -> str:
                return "test_custom"

            def fetch_tools(self) -> list[Tool]:
                return [
                    Tool(
                        id="test_custom:tool1",
                        name="Tool 1",
                        source="test_custom",
                        source_url="https://example.com/tool1",
                        tool_type=ToolType.SKILL,
                        description="Test tool 1",
                    )
                ]

            def search_live(self, query: str) -> list[Tool]:
                return []

        # Get the source
        source = get_source("test_custom")
        assert source.name == "test_custom"

        # Fetch tools
        tools = source.fetch_tools()
        assert len(tools) == 1
        assert tools[0].id == "test_custom:tool1"
