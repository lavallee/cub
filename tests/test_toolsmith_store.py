"""
Tests for ToolsmithStore (load/save/search).

Tests cover:
- load_catalog() with missing and existing files
- save_catalog() with directory creation and atomic writes
- search() with various query patterns
- ToolsmithStore.default() factory method
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.toolsmith.models import Catalog, Tool, ToolType
from cub.core.toolsmith.store import ToolsmithStore


class TestLoadCatalog:
    """Tests for load_catalog() method."""

    def test_load_catalog_when_file_missing(self, tmp_path: Path) -> None:
        """load_catalog() returns empty catalog when file doesn't exist."""
        store = ToolsmithStore(tmp_path)
        catalog = store.load_catalog()

        assert isinstance(catalog, Catalog)
        assert catalog.version == "1.0.0"
        assert catalog.tools == []
        assert catalog.last_sync is None
        assert catalog.sources_synced == []

    def test_load_catalog_when_directory_missing(self, tmp_path: Path) -> None:
        """load_catalog() returns empty catalog when directory doesn't exist."""
        non_existent = tmp_path / "nonexistent"
        store = ToolsmithStore(non_existent)
        catalog = store.load_catalog()

        assert isinstance(catalog, Catalog)
        assert catalog.tools == []

    def test_load_catalog_with_empty_catalog(self, tmp_path: Path) -> None:
        """load_catalog() works with empty catalog file."""
        catalog_file = tmp_path / "catalog.json"
        empty_catalog = Catalog(version="1.0.0")
        catalog_file.write_text(json.dumps(empty_catalog.model_dump(), indent=2))

        store = ToolsmithStore(tmp_path)
        loaded = store.load_catalog()

        assert loaded.version == "1.0.0"
        assert loaded.tools == []

    def test_load_catalog_with_tools(self, tmp_path: Path) -> None:
        """load_catalog() returns populated catalog when file exists."""
        tool1 = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="JavaScript linter",
            tags=["linter", "javascript"],
        )
        tool2 = Tool(
            id="npm:prettier",
            name="Prettier",
            source="npm",
            source_url="https://www.npmjs.com/package/prettier",
            tool_type=ToolType.MCP_SERVER,
            description="Code formatter",
            tags=["formatter"],
        )
        catalog = Catalog(
            version="1.2.3",
            tools=[tool1, tool2],
            sources_synced=["npm"],
        )

        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text(json.dumps(catalog.model_dump(), indent=2))

        store = ToolsmithStore(tmp_path)
        loaded = store.load_catalog()

        assert loaded.version == "1.2.3"
        assert len(loaded.tools) == 2
        assert loaded.tools[0].id == "npm:eslint"
        assert loaded.tools[1].id == "npm:prettier"
        assert loaded.sources_synced == ["npm"]

    def test_load_catalog_with_timestamps(self, tmp_path: Path) -> None:
        """load_catalog() preserves timestamps."""
        now = datetime.now(timezone.utc)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
            last_seen=now,
        )
        catalog = Catalog(version="1.0.0", tools=[tool], last_sync=now)

        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text(json.dumps(catalog.model_dump(mode='json'), indent=2))

        store = ToolsmithStore(tmp_path)
        loaded = store.load_catalog()

        assert loaded.last_sync is not None
        assert loaded.tools[0].last_seen is not None
        # Compare timestamps (allowing small precision differences)
        assert abs((loaded.last_sync - now).total_seconds()) < 1

    def test_load_catalog_malformed_json_raises(self, tmp_path: Path) -> None:
        """load_catalog() raises on malformed JSON."""
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("{invalid json")

        store = ToolsmithStore(tmp_path)
        with pytest.raises(json.JSONDecodeError):
            store.load_catalog()

    def test_load_catalog_invalid_schema_raises(self, tmp_path: Path) -> None:
        """load_catalog() raises on invalid catalog schema."""
        catalog_file = tmp_path / "catalog.json"
        # Missing required 'version' field
        catalog_file.write_text('{"tools": []}')

        store = ToolsmithStore(tmp_path)
        with pytest.raises(Exception):  # Pydantic ValidationError
            store.load_catalog()


class TestSaveCatalog:
    """Tests for save_catalog() method."""

    def test_save_catalog_creates_directory(self, tmp_path: Path) -> None:
        """save_catalog() creates directory if it doesn't exist."""
        toolsmith_dir = tmp_path / "new_dir"
        assert not toolsmith_dir.exists()

        store = ToolsmithStore(toolsmith_dir)
        catalog = Catalog(version="1.0.0")
        result_path = store.save_catalog(catalog)

        assert toolsmith_dir.exists()
        assert result_path.exists()
        assert result_path == toolsmith_dir / "catalog.json"

    def test_save_catalog_writes_valid_json(self, tmp_path: Path) -> None:
        """save_catalog() writes valid JSON to catalog.json."""
        store = ToolsmithStore(tmp_path)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        catalog = Catalog(version="1.0.0", tools=[tool])

        result_path = store.save_catalog(catalog)

        # Verify file exists
        assert result_path.exists()
        assert result_path == tmp_path / "catalog.json"

        # Verify it's valid JSON
        with open(result_path) as f:
            data = json.load(f)
        assert data["version"] == "1.0.0"
        assert len(data["tools"]) == 1
        assert data["tools"][0]["id"] == "npm:eslint"

    def test_save_catalog_human_readable_formatting(self, tmp_path: Path) -> None:
        """save_catalog() uses indented JSON for readability."""
        store = ToolsmithStore(tmp_path)
        catalog = Catalog(version="1.0.0", tools=[])

        store.save_catalog(catalog)
        catalog_file = tmp_path / "catalog.json"
        content = catalog_file.read_text()

        # Check for indentation (human-readable format)
        assert "  " in content  # Has indentation
        assert "\n" in content  # Has newlines

    def test_save_catalog_overwrites_existing(self, tmp_path: Path) -> None:
        """save_catalog() overwrites existing catalog file."""
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text('{"version": "0.0.1", "tools": []}')

        store = ToolsmithStore(tmp_path)
        new_catalog = Catalog(version="2.0.0", tools=[])
        store.save_catalog(new_catalog)

        # Verify new content replaced old
        with open(catalog_file) as f:
            data = json.load(f)
        assert data["version"] == "2.0.0"

    def test_save_catalog_preserves_all_fields(self, tmp_path: Path) -> None:
        """save_catalog() preserves all catalog fields."""
        now = datetime.now(timezone.utc)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
            install_hint="npm install eslint",
            tags=["linter", "js"],
            last_seen=now,
        )
        catalog = Catalog(
            version="1.2.3",
            tools=[tool],
            last_sync=now,
            sources_synced=["npm", "github"],
        )

        store = ToolsmithStore(tmp_path)
        store.save_catalog(catalog)

        # Reload and verify all fields
        loaded = store.load_catalog()
        assert loaded.version == "1.2.3"
        assert len(loaded.tools) == 1
        assert loaded.tools[0].install_hint == "npm install eslint"
        assert loaded.tools[0].tags == ["linter", "js"]
        assert loaded.sources_synced == ["npm", "github"]

    def test_save_catalog_atomic_write(self, tmp_path: Path) -> None:
        """save_catalog() uses atomic write (no partial corruption)."""
        store = ToolsmithStore(tmp_path)
        catalog = Catalog(version="1.0.0")

        # Save once
        store.save_catalog(catalog)
        catalog_file = tmp_path / "catalog.json"
        assert catalog_file.exists()

        # Save again - should not leave temp files
        catalog2 = Catalog(version="2.0.0")
        store.save_catalog(catalog2)

        # Check no temp files left behind
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_save_catalog_returns_path(self, tmp_path: Path) -> None:
        """save_catalog() returns path to saved file."""
        store = ToolsmithStore(tmp_path)
        catalog = Catalog(version="1.0.0")

        result_path = store.save_catalog(catalog)

        assert isinstance(result_path, Path)
        assert result_path == tmp_path / "catalog.json"
        assert result_path.exists()


class TestSearch:
    """Tests for search() method."""

    def test_search_empty_query_returns_empty(self, tmp_path: Path) -> None:
        """search() returns empty list for empty query."""
        store = ToolsmithStore(tmp_path)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        catalog = Catalog(version="1.0.0", tools=[tool])
        store.save_catalog(catalog)

        results = store.search("")
        assert results == []

    def test_search_whitespace_query_returns_empty(self, tmp_path: Path) -> None:
        """search() returns empty list for whitespace-only query."""
        store = ToolsmithStore(tmp_path)
        results = store.search("   ")
        assert results == []

    def test_search_no_matches_returns_empty(self, tmp_path: Path) -> None:
        """search() returns empty list when no matches."""
        store = ToolsmithStore(tmp_path)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        catalog = Catalog(version="1.0.0", tools=[tool])
        store.save_catalog(catalog)

        results = store.search("formatter")
        assert results == []

    def test_search_matches_name_case_insensitive(self, tmp_path: Path) -> None:
        """search() matches tool name (case-insensitive)."""
        store = ToolsmithStore(tmp_path)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        catalog = Catalog(version="1.0.0", tools=[tool])
        store.save_catalog(catalog)

        # Test various cases
        for query in ["eslint", "ESLint", "ESLINT", "EsLiNt"]:
            results = store.search(query)
            assert len(results) == 1
            assert results[0].id == "npm:eslint"

    def test_search_matches_description_case_insensitive(self, tmp_path: Path) -> None:
        """search() matches tool description (case-insensitive)."""
        store = ToolsmithStore(tmp_path)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="JavaScript linter for code quality",
        )
        catalog = Catalog(version="1.0.0", tools=[tool])
        store.save_catalog(catalog)

        # Match terms from description
        results = store.search("linter")
        assert len(results) == 1

        results = store.search("JAVASCRIPT")
        assert len(results) == 1

        results = store.search("quality")
        assert len(results) == 1

    def test_search_multiple_terms_all_must_match(self, tmp_path: Path) -> None:
        """search() with multiple terms requires ALL to match."""
        store = ToolsmithStore(tmp_path)
        tool1 = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="JavaScript linter",
        )
        tool2 = Tool(
            id="npm:prettier",
            name="Prettier",
            source="npm",
            source_url="https://www.npmjs.com/package/prettier",
            tool_type=ToolType.MCP_SERVER,
            description="JavaScript formatter",
        )
        catalog = Catalog(version="1.0.0", tools=[tool1, tool2])
        store.save_catalog(catalog)

        # "javascript linter" should match only eslint
        results = store.search("javascript linter")
        assert len(results) == 1
        assert results[0].id == "npm:eslint"

        # "javascript formatter" should match only prettier
        results = store.search("javascript formatter")
        assert len(results) == 1
        assert results[0].id == "npm:prettier"

        # "javascript" alone should match both
        results = store.search("javascript")
        assert len(results) == 2

    def test_search_partial_word_match(self, tmp_path: Path) -> None:
        """search() matches partial words."""
        store = ToolsmithStore(tmp_path)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter for JavaScript",
        )
        catalog = Catalog(version="1.0.0", tools=[tool])
        store.save_catalog(catalog)

        # "lint" should match "ESLint" and "Linter"
        results = store.search("lint")
        assert len(results) == 1

        # "script" should match "JavaScript"
        results = store.search("script")
        assert len(results) == 1

    def test_search_multiple_results(self, tmp_path: Path) -> None:
        """search() returns all matching tools."""
        store = ToolsmithStore(tmp_path)
        tools = [
            Tool(
                id="npm:eslint",
                name="ESLint",
                source="npm",
                source_url="https://www.npmjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="JavaScript linter",
            ),
            Tool(
                id="npm:tslint",
                name="TSLint",
                source="npm",
                source_url="https://www.npmjs.com/package/tslint",
                tool_type=ToolType.MCP_SERVER,
                description="TypeScript linter",
            ),
            Tool(
                id="npm:prettier",
                name="Prettier",
                source="npm",
                source_url="https://www.npmjs.com/package/prettier",
                tool_type=ToolType.MCP_SERVER,
                description="Code formatter",
            ),
        ]
        catalog = Catalog(version="1.0.0", tools=tools)
        store.save_catalog(catalog)

        # Search for "linter" should match eslint and tslint
        results = store.search("linter")
        assert len(results) == 2
        ids = {r.id for r in results}
        assert ids == {"npm:eslint", "npm:tslint"}

    def test_search_with_no_catalog_file(self, tmp_path: Path) -> None:
        """search() returns empty list when catalog file doesn't exist."""
        store = ToolsmithStore(tmp_path)
        results = store.search("anything")
        assert results == []

    def test_search_returns_tool_objects(self, tmp_path: Path) -> None:
        """search() returns Tool objects, not dicts."""
        store = ToolsmithStore(tmp_path)
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="Linter",
        )
        catalog = Catalog(version="1.0.0", tools=[tool])
        store.save_catalog(catalog)

        results = store.search("eslint")
        assert len(results) == 1
        assert isinstance(results[0], Tool)
        assert results[0].name == "ESLint"


class TestDefaultFactory:
    """Tests for ToolsmithStore.default() class method."""

    def test_default_returns_store(self) -> None:
        """ToolsmithStore.default() returns ToolsmithStore instance."""
        store = ToolsmithStore.default()
        assert isinstance(store, ToolsmithStore)

    def test_default_uses_cub_toolsmith_path(self) -> None:
        """ToolsmithStore.default() uses .cub/toolsmith/ directory."""
        store = ToolsmithStore.default()
        expected_path = Path.cwd() / ".cub" / "toolsmith"
        assert store.toolsmith_dir == expected_path

    def test_default_catalog_file_path(self) -> None:
        """ToolsmithStore.default() has correct catalog_file path."""
        store = ToolsmithStore.default()
        expected_file = Path.cwd() / ".cub" / "toolsmith" / "catalog.json"
        assert store.catalog_file == expected_file


class TestIntegration:
    """Integration tests for common workflows."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Save and load roundtrip preserves data."""
        store = ToolsmithStore(tmp_path)

        # Create catalog with tools
        tools = [
            Tool(
                id="npm:eslint",
                name="ESLint",
                source="npm",
                source_url="https://www.npmjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="JavaScript linter",
                tags=["linter", "js"],
            ),
            Tool(
                id="npm:prettier",
                name="Prettier",
                source="npm",
                source_url="https://www.npmjs.com/package/prettier",
                tool_type=ToolType.MCP_SERVER,
                description="Code formatter",
                tags=["formatter"],
            ),
        ]
        original = Catalog(version="1.0.0", tools=tools, sources_synced=["npm"])

        # Save
        store.save_catalog(original)

        # Load
        loaded = store.load_catalog()

        # Verify
        assert loaded.version == original.version
        assert len(loaded.tools) == len(original.tools)
        assert loaded.tools[0].id == original.tools[0].id
        assert loaded.tools[1].id == original.tools[1].id
        assert loaded.sources_synced == original.sources_synced

    def test_add_tool_and_search(self, tmp_path: Path) -> None:
        """Workflow: load, add tool, save, search."""
        store = ToolsmithStore(tmp_path)

        # Start with empty catalog
        catalog = store.load_catalog()
        assert len(catalog.tools) == 0

        # Add a tool
        tool = Tool(
            id="npm:eslint",
            name="ESLint",
            source="npm",
            source_url="https://www.npmjs.com/package/eslint",
            tool_type=ToolType.MCP_SERVER,
            description="JavaScript linter",
        )
        catalog.tools.append(tool)
        store.save_catalog(catalog)

        # Search for it
        results = store.search("linter")
        assert len(results) == 1
        assert results[0].id == "npm:eslint"

    def test_update_catalog_incrementally(self, tmp_path: Path) -> None:
        """Workflow: incrementally update catalog."""
        store = ToolsmithStore(tmp_path)

        # Save initial catalog
        catalog = Catalog(version="1.0.0", tools=[])
        store.save_catalog(catalog)

        # Load and add first tool
        catalog = store.load_catalog()
        catalog.tools.append(
            Tool(
                id="npm:eslint",
                name="ESLint",
                source="npm",
                source_url="https://www.npmjs.com/package/eslint",
                tool_type=ToolType.MCP_SERVER,
                description="Linter",
            )
        )
        store.save_catalog(catalog)

        # Load and add second tool
        catalog = store.load_catalog()
        assert len(catalog.tools) == 1
        catalog.tools.append(
            Tool(
                id="npm:prettier",
                name="Prettier",
                source="npm",
                source_url="https://www.npmjs.com/package/prettier",
                tool_type=ToolType.MCP_SERVER,
                description="Formatter",
            )
        )
        store.save_catalog(catalog)

        # Verify final state
        catalog = store.load_catalog()
        assert len(catalog.tools) == 2
