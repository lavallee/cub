"""
Tests for ToolsmithService.

Validates sync logic, error handling, and statistics generation.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.toolsmith.models import Tool, ToolType
from cub.core.toolsmith.service import ToolsmithService
from cub.core.toolsmith.store import ToolsmithStore


class MockSource:
    """Mock tool source for testing."""

    def __init__(
        self,
        name: str,
        tools: list[Tool] | None = None,
        error: Exception | None = None,
        search_results: list[Tool] | None = None,
        search_error: Exception | None = None,
    ):
        self._name = name
        self._tools = tools or []
        self._error = error
        self._search_results = search_results or []
        self._search_error = search_error

    @property
    def name(self) -> str:
        return self._name

    def fetch_tools(self) -> list[Tool]:
        if self._error:
            raise self._error
        return self._tools

    def search_live(self, query: str) -> list[Tool]:
        if self._search_error:
            raise self._search_error
        # Simple filtering: return tools that contain query in name or description
        return [
            tool
            for tool in self._search_results
            if query.lower() in tool.name.lower() or query.lower() in tool.description.lower()
        ]


@pytest.fixture
def temp_store(tmp_path: Path) -> ToolsmithStore:
    """Create a temporary toolsmith store."""
    return ToolsmithStore(tmp_path / "toolsmith")


@pytest.fixture
def sample_tool_1() -> Tool:
    """Create a sample tool for testing."""
    return Tool(
        id="source1:tool1",
        name="Tool 1",
        source="source1",
        source_url="https://example.com/tool1",
        tool_type=ToolType.MCP_SERVER,
        description="First test tool",
        tags=["test"],
    )


@pytest.fixture
def sample_tool_2() -> Tool:
    """Create another sample tool for testing."""
    return Tool(
        id="source2:tool2",
        name="Tool 2",
        source="source2",
        source_url="https://example.com/tool2",
        tool_type=ToolType.SKILL,
        description="Second test tool",
        tags=["test", "skill"],
    )


def test_service_init(temp_store: ToolsmithStore) -> None:
    """Test service initialization."""
    source = MockSource("test", [])
    service = ToolsmithService(temp_store, [source])

    assert service.store == temp_store
    assert len(service.sources) == 1
    assert service.sources[0].name == "test"


def test_sync_all_sources(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
    sample_tool_2: Tool,
) -> None:
    """Test syncing all sources."""
    source1 = MockSource("source1", [sample_tool_1])
    source2 = MockSource("source2", [sample_tool_2])
    service = ToolsmithService(temp_store, [source1, source2])

    result = service.sync()

    assert result.tools_added == 2
    assert result.tools_updated == 0
    assert result.errors == []

    # Verify catalog was saved
    catalog = temp_store.load_catalog()
    assert len(catalog.tools) == 2
    assert catalog.last_sync is not None
    assert set(catalog.sources_synced) == {"source1", "source2"}


def test_sync_specific_sources(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
    sample_tool_2: Tool,
) -> None:
    """Test syncing only specified sources."""
    source1 = MockSource("source1", [sample_tool_1])
    source2 = MockSource("source2", [sample_tool_2])
    service = ToolsmithService(temp_store, [source1, source2])

    result = service.sync(source_names=["source1"])

    assert result.tools_added == 1
    assert result.tools_updated == 0
    assert result.errors == []

    # Verify only source1 tool was added
    catalog = temp_store.load_catalog()
    assert len(catalog.tools) == 1
    assert catalog.tools[0].id == "source1:tool1"
    assert catalog.sources_synced == ["source1"]


def test_sync_updates_existing_tools(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
) -> None:
    """Test that sync updates existing tools."""
    # First sync
    source = MockSource("source1", [sample_tool_1])
    service = ToolsmithService(temp_store, [source])
    result1 = service.sync()

    assert result1.tools_added == 1
    assert result1.tools_updated == 0

    # Second sync with updated tool
    updated_tool = sample_tool_1.model_copy(update={"description": "Updated description"})
    source = MockSource("source1", [updated_tool])
    service = ToolsmithService(temp_store, [source])
    result2 = service.sync()

    assert result2.tools_added == 0
    assert result2.tools_updated == 1

    # Verify tool was updated
    catalog = temp_store.load_catalog()
    assert len(catalog.tools) == 1
    assert catalog.tools[0].description == "Updated description"


def test_sync_updates_last_seen_timestamp(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
) -> None:
    """Test that sync updates last_seen timestamps."""
    source = MockSource("source1", [sample_tool_1])
    service = ToolsmithService(temp_store, [source])

    before_sync = datetime.now(timezone.utc)
    result = service.sync()
    after_sync = datetime.now(timezone.utc)

    assert result.tools_added == 1

    # Verify last_seen was set
    catalog = temp_store.load_catalog()
    tool = catalog.tools[0]
    assert tool.last_seen is not None
    assert before_sync <= tool.last_seen <= after_sync


def test_sync_handles_source_errors_gracefully(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
    sample_tool_2: Tool,
) -> None:
    """Test that sync continues with other sources when one fails."""
    source1 = MockSource("source1", error=RuntimeError("API error"))
    source2 = MockSource("source2", [sample_tool_2])
    service = ToolsmithService(temp_store, [source1, source2])

    result = service.sync()

    # Should have one error but still sync source2
    assert result.tools_added == 1
    assert result.tools_updated == 0
    assert len(result.errors) == 1
    assert "source1" in result.errors[0]
    assert "API error" in result.errors[0]

    # Verify source2 tool was added
    catalog = temp_store.load_catalog()
    assert len(catalog.tools) == 1
    assert catalog.tools[0].id == "source2:tool2"
    assert catalog.sources_synced == ["source2"]


def test_sync_invalid_source_name(temp_store: ToolsmithStore) -> None:
    """Test syncing with invalid source name."""
    source = MockSource("source1", [])
    service = ToolsmithService(temp_store, [source])

    result = service.sync(source_names=["invalid_source"])

    assert result.tools_added == 0
    assert result.tools_updated == 0
    assert len(result.errors) == 1
    assert "invalid_source" in result.errors[0]


def test_sync_merges_sources_synced(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
    sample_tool_2: Tool,
) -> None:
    """Test that sources_synced preserves history across syncs."""
    # First sync with source1
    source1 = MockSource("source1", [sample_tool_1])
    service = ToolsmithService(temp_store, [source1])
    service.sync()

    # Second sync with source2
    source2 = MockSource("source2", [sample_tool_2])
    service = ToolsmithService(temp_store, [source2])
    service.sync()

    # Verify both sources are in sources_synced
    catalog = temp_store.load_catalog()
    assert set(catalog.sources_synced) == {"source1", "source2"}


def test_stats_empty_catalog(temp_store: ToolsmithStore) -> None:
    """Test statistics for empty catalog."""
    service = ToolsmithService(temp_store, [])
    stats = service.stats()

    assert stats.total_tools == 0
    assert stats.by_source == {}
    assert stats.by_type == {}
    assert stats.last_sync is None
    assert stats.sources_synced == []


def test_stats_with_tools(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
    sample_tool_2: Tool,
) -> None:
    """Test statistics with tools in catalog."""
    source1 = MockSource("source1", [sample_tool_1])
    source2 = MockSource("source2", [sample_tool_2])
    service = ToolsmithService(temp_store, [source1, source2])

    # Sync to populate catalog
    service.sync()

    # Get stats
    stats = service.stats()

    assert stats.total_tools == 2
    assert stats.by_source == {"source1": 1, "source2": 1}
    assert stats.by_type == {"mcp_server": 1, "skill": 1}
    assert stats.last_sync is not None
    assert set(stats.sources_synced) == {"source1", "source2"}


def test_stats_multiple_tools_same_source(temp_store: ToolsmithStore) -> None:
    """Test statistics with multiple tools from same source."""
    tool1 = Tool(
        id="source1:tool1",
        name="Tool 1",
        source="source1",
        source_url="https://example.com/tool1",
        tool_type=ToolType.MCP_SERVER,
        description="Tool 1",
    )
    tool2 = Tool(
        id="source1:tool2",
        name="Tool 2",
        source="source1",
        source_url="https://example.com/tool2",
        tool_type=ToolType.MCP_SERVER,
        description="Tool 2",
    )

    source = MockSource("source1", [tool1, tool2])
    service = ToolsmithService(temp_store, [source])

    service.sync()
    stats = service.stats()

    assert stats.total_tools == 2
    assert stats.by_source == {"source1": 2}
    assert stats.by_type == {"mcp_server": 2}


def test_search_local_catalog_returns_results(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
) -> None:
    """Test search returns local results when available."""
    source = MockSource("source1", [sample_tool_1])
    service = ToolsmithService(temp_store, [source])

    # Sync to populate catalog
    service.sync()

    # Search for tool (should find it locally)
    results = service.search("test")

    assert len(results) == 1
    assert results[0].id == "source1:tool1"


def test_search_local_catalog_no_fallback_when_found(
    temp_store: ToolsmithStore,
    sample_tool_1: Tool,
) -> None:
    """Test search does not fall back to live when local results found."""
    # Create a tool that exists locally
    local_tool = sample_tool_1

    # Create a different tool that would be returned by live search
    live_tool = Tool(
        id="source1:live-tool",
        name="Live Tool",
        source="source1",
        source_url="https://example.com/live",
        tool_type=ToolType.MCP_SERVER,
        description="Only available via live search",
    )

    # Set up source with both tools
    source = MockSource("source1", [local_tool], search_results=[live_tool])
    service = ToolsmithService(temp_store, [source])

    # Sync to add local_tool to catalog
    service.sync()

    # Search for "test" - should find local_tool and NOT call live search
    results = service.search("test")

    # Should only return local result, not live result
    assert len(results) == 1
    assert results[0].id == "source1:tool1"


def test_search_fallback_when_no_local_results(temp_store: ToolsmithStore) -> None:
    """Test search falls back to live sources when no local results."""
    live_tool = Tool(
        id="source1:live-tool",
        name="Live Linter Tool",
        source="source1",
        source_url="https://example.com/live",
        tool_type=ToolType.MCP_SERVER,
        description="Only available via live search",
    )

    source = MockSource("source1", [], search_results=[live_tool])
    service = ToolsmithService(temp_store, [source])

    # Search for "linter" - no local results, should fall back to live
    results = service.search("linter")

    assert len(results) == 1
    assert results[0].id == "source1:live-tool"


def test_search_no_fallback_when_disabled(temp_store: ToolsmithStore) -> None:
    """Test search with live_fallback=False only searches local catalog."""
    live_tool = Tool(
        id="source1:live-tool",
        name="Live Tool",
        source="source1",
        source_url="https://example.com/live",
        tool_type=ToolType.MCP_SERVER,
        description="Only available via live search",
    )

    source = MockSource("source1", [], search_results=[live_tool])
    service = ToolsmithService(temp_store, [source])

    # Search with live_fallback=False - should return empty
    results = service.search("live", live_fallback=False)

    assert len(results) == 0


def test_search_deduplicates_by_tool_id(temp_store: ToolsmithStore) -> None:
    """Test search deduplicates results from multiple sources by tool ID."""
    # Same tool ID, different sources
    tool1 = Tool(
        id="common:tool",
        name="Tool from Source 1",
        source="source1",
        source_url="https://example.com/1",
        tool_type=ToolType.MCP_SERVER,
        description="Test tool",
    )
    tool2 = Tool(
        id="common:tool",  # Same ID!
        name="Tool from Source 2",
        source="source2",
        source_url="https://example.com/2",
        tool_type=ToolType.MCP_SERVER,
        description="Test tool",
    )

    source1 = MockSource("source1", [], search_results=[tool1])
    source2 = MockSource("source2", [], search_results=[tool2])
    service = ToolsmithService(temp_store, [source1, source2])

    # Search - should deduplicate
    results = service.search("test")

    # Should only have one result (first one encountered)
    assert len(results) == 1
    assert results[0].id == "common:tool"


def test_search_merges_results_from_multiple_sources(temp_store: ToolsmithStore) -> None:
    """Test search merges results from multiple sources."""
    tool1 = Tool(
        id="source1:tool1",
        name="Tool 1",
        source="source1",
        source_url="https://example.com/1",
        tool_type=ToolType.MCP_SERVER,
        description="Test tool 1",
    )
    tool2 = Tool(
        id="source2:tool2",
        name="Tool 2",
        source="source2",
        source_url="https://example.com/2",
        tool_type=ToolType.MCP_SERVER,
        description="Test tool 2",
    )

    source1 = MockSource("source1", [], search_results=[tool1])
    source2 = MockSource("source2", [], search_results=[tool2])
    service = ToolsmithService(temp_store, [source1, source2])

    # Search - should merge from both sources
    results = service.search("test")

    assert len(results) == 2
    result_ids = {r.id for r in results}
    assert result_ids == {"source1:tool1", "source2:tool2"}


def test_search_handles_source_errors_gracefully(temp_store: ToolsmithStore) -> None:
    """Test search continues with other sources when one fails."""
    tool2 = Tool(
        id="source2:tool2",
        name="Tool 2",
        source="source2",
        source_url="https://example.com/2",
        tool_type=ToolType.MCP_SERVER,
        description="Test tool 2",
    )

    # source1 will raise an error
    source1 = MockSource("source1", [], search_error=RuntimeError("API error"))
    # source2 will return results
    source2 = MockSource("source2", [], search_results=[tool2])

    service = ToolsmithService(temp_store, [source1, source2])

    # Search - should get results from source2 despite source1 error
    results = service.search("test")

    assert len(results) == 1
    assert results[0].id == "source2:tool2"


def test_search_empty_query_returns_empty(temp_store: ToolsmithStore) -> None:
    """Test search with empty query returns empty list."""
    service = ToolsmithService(temp_store, [])

    results = service.search("")

    assert len(results) == 0


def test_search_no_sources_returns_empty(temp_store: ToolsmithStore) -> None:
    """Test search with no sources returns empty list."""
    service = ToolsmithService(temp_store, [])

    results = service.search("test")

    assert len(results) == 0
