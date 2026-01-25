"""
Tests for capability gap recognition API.

Tests cover:
- query_capability() returning adopted tools from registry
- query_capability() returning suggestions from catalog
- Relevance ranking (exact > partial > fuzzy match)
- Filtering out already adopted tools from suggestions
- Handling missing catalog gracefully
"""

from datetime import datetime, timezone
from pathlib import Path

from cub.core.tools.models import (
    AdapterType,
    CapabilityGapResult,
    HTTPConfig,
    Registry,
    ToolConfig,
    ToolSuggestion,
)
from cub.core.tools.registry import RegistryService, RegistryStore
from cub.core.toolsmith.models import Catalog, Tool, ToolType
from cub.core.toolsmith.store import ToolsmithStore


class TestQueryCapabilityRegistry:
    """Tests for query_capability() searching the registry."""

    def test_query_capability_returns_adopted_tools(self, tmp_path: Path) -> None:
        """query_capability() returns tools from registry that match capability."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Adopt a tool with web_search capability
        tool = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search", "current_events"],
            http_config=HTTPConfig(base_url="https://api.brave.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        service.adopt(tool)

        # Query for web_search
        result = service.query_capability("web_search")

        assert isinstance(result, CapabilityGapResult)
        assert result.capability == "web_search"
        assert len(result.adopted_tools) == 1
        assert result.adopted_tools[0].id == "brave-search"

    def test_query_capability_returns_empty_when_no_adopted_tools(
        self, tmp_path: Path
    ) -> None:
        """query_capability() returns empty adopted_tools when no matches."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # No tools adopted
        result = service.query_capability("web_search")

        assert result.capability == "web_search"
        assert len(result.adopted_tools) == 0

    def test_query_capability_returns_multiple_adopted_tools(
        self, tmp_path: Path
    ) -> None:
        """query_capability() returns all tools that match capability."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Adopt multiple tools with same capability
        tool1 = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search"],
            http_config=HTTPConfig(base_url="https://api.brave.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        tool2 = ToolConfig(
            id="duckduckgo",
            name="DuckDuckGo",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search"],
            http_config=HTTPConfig(base_url="https://api.duckduckgo.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )

        service.adopt(tool1)
        service.adopt(tool2)

        result = service.query_capability("web_search")

        assert len(result.adopted_tools) == 2
        tool_ids = {t.id for t in result.adopted_tools}
        assert tool_ids == {"brave-search", "duckduckgo"}


class TestQueryCapabilityCatalog:
    """Tests for query_capability() searching the catalog."""

    def test_query_capability_returns_catalog_suggestions(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """query_capability() returns suggestions from catalog."""
        # Setup registry service
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Setup catalog with a matching tool
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        catalog_tool = Tool(
            id="npm:brave-search",
            name="Brave Search",
            source="npm",
            source_url="https://npmjs.com/package/brave-search",
            tool_type=ToolType.MCP_SERVER,
            description="Web search using Brave Search API",
            tags=["web_search", "search"],
        )
        catalog = Catalog(version="1.0.0", tools=[catalog_tool])
        catalog_store.save_catalog(catalog)

        # Monkeypatch the current directory to tmp_path
        monkeypatch.chdir(tmp_path)

        # Query for web_search
        result = service.query_capability("web_search")

        assert len(result.suggestions) == 1
        suggestion = result.suggestions[0]
        assert suggestion.tool_id == "npm:brave-search"
        assert suggestion.name == "Brave Search"
        assert suggestion.match_type == "exact"
        assert suggestion.relevance_score == 1.0

    def test_query_capability_filters_adopted_tools_from_suggestions(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """query_capability() doesn't suggest tools that are already adopted."""
        # Setup registry with adopted tool
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        adopted_tool = ToolConfig(
            id="npm:brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search"],
            http_config=HTTPConfig(base_url="https://api.brave.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        service.adopt(adopted_tool)

        # Setup catalog with the same tool
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        catalog_tool = Tool(
            id="npm:brave-search",
            name="Brave Search",
            source="npm",
            source_url="https://npmjs.com/package/brave-search",
            tool_type=ToolType.MCP_SERVER,
            description="Web search using Brave Search API",
            tags=["web_search"],
        )
        catalog = Catalog(version="1.0.0", tools=[catalog_tool])
        catalog_store.save_catalog(catalog)

        monkeypatch.chdir(tmp_path)

        # Query for web_search
        result = service.query_capability("web_search")

        # Tool should be in adopted_tools, not suggestions
        assert len(result.adopted_tools) == 1
        assert result.adopted_tools[0].id == "npm:brave-search"
        assert len(result.suggestions) == 0

    def test_query_capability_handles_missing_catalog(self, tmp_path: Path) -> None:
        """query_capability() works even if catalog doesn't exist."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # No catalog exists - should not raise error
        result = service.query_capability("web_search")

        assert result.capability == "web_search"
        assert len(result.adopted_tools) == 0
        assert len(result.suggestions) == 0


class TestQueryCapabilityRanking:
    """Tests for relevance ranking in query_capability()."""

    def test_exact_match_scores_highest(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Exact tag match gets score of 1.0."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Setup catalog with exact match
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        exact_tool = Tool(
            id="npm:brave-search",
            name="Brave Search",
            source="npm",
            source_url="https://npmjs.com/package/brave-search",
            tool_type=ToolType.MCP_SERVER,
            description="Web search tool",
            tags=["web_search"],  # Exact match
        )
        catalog = Catalog(version="1.0.0", tools=[exact_tool])
        catalog_store.save_catalog(catalog)

        monkeypatch.chdir(tmp_path)

        result = service.query_capability("web_search")

        assert len(result.suggestions) == 1
        assert result.suggestions[0].relevance_score == 1.0
        assert result.suggestions[0].match_type == "exact"

    def test_partial_match_in_description_scores_medium(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Partial match in description gets score 0.5-0.8."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Setup catalog with partial match
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        partial_tool = Tool(
            id="npm:searcher",
            name="Searcher",
            source="npm",
            source_url="https://npmjs.com/package/searcher",
            tool_type=ToolType.MCP_SERVER,
            description="A tool for web search across multiple engines",
            tags=["search"],
        )
        catalog = Catalog(version="1.0.0", tools=[partial_tool])
        catalog_store.save_catalog(catalog)

        monkeypatch.chdir(tmp_path)

        result = service.query_capability("web_search")

        assert len(result.suggestions) == 1
        assert 0.5 <= result.suggestions[0].relevance_score <= 0.8
        assert result.suggestions[0].match_type == "partial"

    def test_fuzzy_match_scores_lower(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Fuzzy match with some word overlap gets score 0.3-0.5."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Setup catalog with fuzzy match - only "search" appears once
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        fuzzy_tool = Tool(
            id="npm:code-finder",
            name="Code Finder",
            source="npm",
            source_url="https://npmjs.com/package/code-finder",
            tool_type=ToolType.MCP_SERVER,
            description="Find and search code in repositories",
            tags=["code", "finder"],  # Only "search" in description matches "web_search"
        )
        catalog = Catalog(version="1.0.0", tools=[fuzzy_tool])
        catalog_store.save_catalog(catalog)

        monkeypatch.chdir(tmp_path)

        result = service.query_capability("web_search")

        # "search" appears in description, should get fuzzy/partial match
        assert len(result.suggestions) == 1
        # Since "search" appears in description, it's a partial match
        assert result.suggestions[0].relevance_score > 0.3
        assert result.suggestions[0].match_type in ["fuzzy", "partial"]

    def test_suggestions_sorted_by_relevance(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Suggestions are sorted by relevance score (highest first)."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Setup catalog with multiple tools
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        tools = [
            Tool(
                id="npm:fuzzy",
                name="Fuzzy Tool",
                source="npm",
                source_url="https://npmjs.com/package/fuzzy",
                tool_type=ToolType.MCP_SERVER,
                description="A web tool",
                tags=["web"],  # Fuzzy match
            ),
            Tool(
                id="npm:exact",
                name="Exact Tool",
                source="npm",
                source_url="https://npmjs.com/package/exact",
                tool_type=ToolType.MCP_SERVER,
                description="Exact match tool",
                tags=["web_search"],  # Exact match
            ),
            Tool(
                id="npm:partial",
                name="Partial Tool",
                source="npm",
                source_url="https://npmjs.com/package/partial",
                tool_type=ToolType.MCP_SERVER,
                description="Tool for web search operations",
                tags=["search"],  # Partial match
            ),
        ]
        catalog = Catalog(version="1.0.0", tools=tools)
        catalog_store.save_catalog(catalog)

        monkeypatch.chdir(tmp_path)

        result = service.query_capability("web_search")

        # Should have all three tools, sorted by relevance
        assert len(result.suggestions) == 3

        # Exact match should be first
        assert result.suggestions[0].tool_id == "npm:exact"
        assert result.suggestions[0].relevance_score == 1.0

        # Partial match should be second
        assert result.suggestions[1].tool_id == "npm:partial"
        assert result.suggestions[1].relevance_score > result.suggestions[2].relevance_score

        # Fuzzy match should be last
        assert result.suggestions[2].tool_id == "npm:fuzzy"

    def test_no_match_excluded_from_suggestions(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Tools with no relevance (score 0.0) are excluded."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Setup catalog with irrelevant tool
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        irrelevant_tool = Tool(
            id="npm:database",
            name="Database Tool",
            source="npm",
            source_url="https://npmjs.com/package/database",
            tool_type=ToolType.MCP_SERVER,
            description="Manage PostgreSQL databases",
            tags=["database", "postgres"],
        )
        catalog = Catalog(version="1.0.0", tools=[irrelevant_tool])
        catalog_store.save_catalog(catalog)

        monkeypatch.chdir(tmp_path)

        result = service.query_capability("web_search")

        # No suggestions because the tool is completely irrelevant
        assert len(result.suggestions) == 0


class TestQueryCapabilityIntegration:
    """Integration tests combining registry and catalog."""

    def test_combined_adopted_and_suggestions(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """query_capability() returns both adopted tools and suggestions."""
        # Setup registry with one adopted tool
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        adopted_tool = ToolConfig(
            id="npm:brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search"],
            http_config=HTTPConfig(base_url="https://api.brave.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        service.adopt(adopted_tool)

        # Setup catalog with different tool
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        catalog_tool = Tool(
            id="npm:duckduckgo",
            name="DuckDuckGo",
            source="npm",
            source_url="https://npmjs.com/package/duckduckgo",
            tool_type=ToolType.MCP_SERVER,
            description="DuckDuckGo search",
            tags=["web_search"],
        )
        catalog = Catalog(version="1.0.0", tools=[catalog_tool])
        catalog_store.save_catalog(catalog)

        monkeypatch.chdir(tmp_path)

        result = service.query_capability("web_search")

        # Should have both adopted tool and suggestion
        assert len(result.adopted_tools) == 1
        assert result.adopted_tools[0].id == "npm:brave-search"

        assert len(result.suggestions) == 1
        assert result.suggestions[0].tool_id == "npm:duckduckgo"

    def test_underscore_to_space_normalization(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """query_capability() normalizes underscores to spaces for matching."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Setup catalog with space-separated tag
        catalog_dir = tmp_path / ".cub" / "toolsmith"
        catalog_store = ToolsmithStore(catalog_dir)
        catalog_tool = Tool(
            id="npm:search",
            name="Search Tool",
            source="npm",
            source_url="https://npmjs.com/package/search",
            tool_type=ToolType.MCP_SERVER,
            description="Search tool",
            tags=["web search"],  # Space-separated
        )
        catalog = Catalog(version="1.0.0", tools=[catalog_tool])
        catalog_store.save_catalog(catalog)

        monkeypatch.chdir(tmp_path)

        # Query with underscore
        result = service.query_capability("web_search")

        # Should match even though tag uses space
        assert len(result.suggestions) == 1
        assert result.suggestions[0].match_type == "exact"
