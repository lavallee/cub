"""Tests for Toolsmith adoption (tool selection/approval) module.

This module tests the AdoptedTool model and AdoptionStore class which handle
recording which tools have been adopted for use in a project.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from cub.core.toolsmith.adoption import AdoptedTool, AdoptionStore


class TestAdoptedTool:
    """Tests for AdoptedTool model validation and behavior."""

    def test_valid_tool_creation_minimal(self) -> None:
        """Test creating an AdoptedTool with only required fields."""
        tool = AdoptedTool(tool_id="mcp-official:brave-search")

        assert tool.tool_id == "mcp-official:brave-search"
        assert tool.note is None
        assert isinstance(tool.adopted_at, datetime)
        assert tool.adopted_at.tzinfo is not None  # Should be timezone-aware

    def test_valid_tool_creation_with_note(self) -> None:
        """Test creating an AdoptedTool with a note."""
        tool = AdoptedTool(
            tool_id="smithery:filesystem",
            note="Needed for local file access",
        )

        assert tool.tool_id == "smithery:filesystem"
        assert tool.note == "Needed for local file access"

    def test_valid_tool_creation_with_explicit_timestamp(self) -> None:
        """Test creating an AdoptedTool with explicit adopted_at timestamp."""
        ts = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        tool = AdoptedTool(
            tool_id="glama:web-scraper",
            adopted_at=ts,
            note="For web research",
        )

        assert tool.adopted_at == ts
        assert tool.adopted_at.year == 2024
        assert tool.adopted_at.month == 6

    def test_adopted_at_defaults_to_utc(self) -> None:
        """Test that adopted_at default is timezone-aware (UTC)."""
        before = datetime.now(timezone.utc)
        tool = AdoptedTool(tool_id="test:tool")
        after = datetime.now(timezone.utc)

        assert tool.adopted_at.tzinfo == timezone.utc
        assert before <= tool.adopted_at <= after

    def test_tool_id_required(self) -> None:
        """Test that tool_id is a required field."""
        with pytest.raises(ValidationError, match="tool_id"):
            AdoptedTool()

    def test_tool_serialization_round_trip(self) -> None:
        """Test that AdoptedTool can be serialized and deserialized."""
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        original = AdoptedTool(
            tool_id="mcp-official:github",
            adopted_at=ts,
            note="For PR management",
        )

        # Serialize to dict (JSON mode for datetime serialization)
        data = original.model_dump(mode="json")

        # Deserialize back
        restored = AdoptedTool.model_validate(data)

        assert restored.tool_id == original.tool_id
        assert restored.note == original.note
        # Compare timestamps (may have microsecond differences)
        assert restored.adopted_at.replace(microsecond=0) == original.adopted_at.replace(
            microsecond=0
        )

    def test_empty_tool_id_is_valid(self) -> None:
        """Test that empty string tool_id is technically valid (no custom validation)."""
        # The model doesn't have custom validation preventing empty strings
        tool = AdoptedTool(tool_id="")
        assert tool.tool_id == ""


class TestAdoptionStoreInit:
    """Tests for AdoptionStore initialization."""

    def test_init_sets_paths(self, tmp_path: Path) -> None:
        """Test that __init__ properly sets directory and file paths."""
        toolsmith_dir = tmp_path / ".cub" / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        assert store.toolsmith_dir == toolsmith_dir
        assert store.adopted_file == toolsmith_dir / "adopted.json"

    def test_init_converts_string_path(self, tmp_path: Path) -> None:
        """Test that __init__ converts string paths to Path objects."""
        toolsmith_dir_str = str(tmp_path / "toolsmith")
        store = AdoptionStore(Path(toolsmith_dir_str))

        assert isinstance(store.toolsmith_dir, Path)

    def test_init_does_not_create_directory(self, tmp_path: Path) -> None:
        """Test that __init__ does not create the directory."""
        toolsmith_dir = tmp_path / "nonexistent" / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        assert not toolsmith_dir.exists()
        assert store.toolsmith_dir == toolsmith_dir


class TestAdoptionStoreList:
    """Tests for AdoptionStore.list_all() method."""

    def test_list_empty_when_no_file_exists(self, tmp_path: Path) -> None:
        """Test that list() returns empty list when adopted.json doesn't exist."""
        store = AdoptionStore(tmp_path / "toolsmith")

        result = store.list_all()

        assert result == []
        assert isinstance(result, list)

    def test_list_returns_adopted_tools(self, tmp_path: Path) -> None:
        """Test that list() returns all adopted tools from file."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)

        tools_data = [
            {
                "tool_id": "mcp-official:filesystem",
                "adopted_at": "2024-01-15T10:00:00+00:00",
                "note": "For file access",
            },
            {
                "tool_id": "smithery:github",
                "adopted_at": "2024-01-16T12:00:00+00:00",
                "note": None,
            },
        ]
        (toolsmith_dir / "adopted.json").write_text(json.dumps(tools_data))

        store = AdoptionStore(toolsmith_dir)
        result = store.list_all()

        assert len(result) == 2
        assert all(isinstance(t, AdoptedTool) for t in result)
        assert result[0].tool_id == "mcp-official:filesystem"
        assert result[0].note == "For file access"
        assert result[1].tool_id == "smithery:github"
        assert result[1].note is None

    def test_list_empty_json_array(self, tmp_path: Path) -> None:
        """Test that list() returns empty list for empty JSON array."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)
        (toolsmith_dir / "adopted.json").write_text("[]")

        store = AdoptionStore(toolsmith_dir)
        result = store.list_all()

        assert result == []

    def test_list_preserves_timestamps(self, tmp_path: Path) -> None:
        """Test that list() preserves datetime timestamps."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)

        tools_data = [
            {
                "tool_id": "test:tool",
                "adopted_at": "2024-06-15T14:30:00+00:00",
                "note": None,
            },
        ]
        (toolsmith_dir / "adopted.json").write_text(json.dumps(tools_data))

        store = AdoptionStore(toolsmith_dir)
        result = store.list_all()

        assert len(result) == 1
        assert result[0].adopted_at.year == 2024
        assert result[0].adopted_at.month == 6
        assert result[0].adopted_at.day == 15


class TestAdoptionStoreSave:
    """Tests for AdoptionStore.save() method."""

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """Test that save() creates the toolsmith directory if needed."""
        toolsmith_dir = tmp_path / "new" / "nested" / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        tools = [AdoptedTool(tool_id="test:tool")]
        store.save(tools)

        assert toolsmith_dir.exists()
        assert toolsmith_dir.is_dir()

    def test_save_writes_valid_json(self, tmp_path: Path) -> None:
        """Test that save() writes valid, parseable JSON."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        ts = datetime(2024, 3, 20, 8, 0, 0, tzinfo=timezone.utc)
        tools = [
            AdoptedTool(tool_id="mcp:tool1", adopted_at=ts, note="Note 1"),
            AdoptedTool(tool_id="mcp:tool2", adopted_at=ts),
        ]
        store.save(tools)

        # Read and parse the file
        content = (toolsmith_dir / "adopted.json").read_text()
        data = json.loads(content)

        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["tool_id"] == "mcp:tool1"
        assert data[0]["note"] == "Note 1"
        assert data[1]["tool_id"] == "mcp:tool2"
        assert data[1]["note"] is None

    def test_save_empty_list(self, tmp_path: Path) -> None:
        """Test that save() can write an empty list."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        store.save([])

        content = (toolsmith_dir / "adopted.json").read_text()
        data = json.loads(content)

        assert data == []

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Test that save() overwrites existing file."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)
        (toolsmith_dir / "adopted.json").write_text('[{"tool_id": "old:tool"}]')

        store = AdoptionStore(toolsmith_dir)
        store.save([AdoptedTool(tool_id="new:tool")])

        data = json.loads((toolsmith_dir / "adopted.json").read_text())

        assert len(data) == 1
        assert data[0]["tool_id"] == "new:tool"

    def test_save_formats_json_with_indent(self, tmp_path: Path) -> None:
        """Test that save() writes JSON with indentation for readability."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        store.save([AdoptedTool(tool_id="test:tool")])

        content = (toolsmith_dir / "adopted.json").read_text()
        # Indented JSON should have newlines and spaces
        assert "\n" in content
        assert "  " in content  # 2-space indent


class TestAdoptionStoreAdopt:
    """Tests for AdoptionStore.adopt() method."""

    def test_adopt_new_tool(self, tmp_path: Path) -> None:
        """Test adopting a tool that doesn't exist yet."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        result = store.adopt("mcp-official:brave-search", note="Web search capability")

        assert isinstance(result, AdoptedTool)
        assert result.tool_id == "mcp-official:brave-search"
        assert result.note == "Web search capability"
        assert isinstance(result.adopted_at, datetime)

    def test_adopt_persists_to_file(self, tmp_path: Path) -> None:
        """Test that adopt() persists the tool to the JSON file."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        store.adopt("test:tool", note="Test note")

        # Verify by reading directly
        data = json.loads((toolsmith_dir / "adopted.json").read_text())
        assert len(data) == 1
        assert data[0]["tool_id"] == "test:tool"
        assert data[0]["note"] == "Test note"

    def test_adopt_without_note(self, tmp_path: Path) -> None:
        """Test adopting a tool without a note."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        result = store.adopt("mcp:tool-without-note")

        assert result.tool_id == "mcp:tool-without-note"
        assert result.note is None

    def test_adopt_existing_tool_updates_note(self, tmp_path: Path) -> None:
        """Test that adopting existing tool updates the note if provided."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)

        original_ts = "2024-01-01T00:00:00+00:00"
        (toolsmith_dir / "adopted.json").write_text(
            json.dumps(
                [
                    {
                        "tool_id": "mcp:existing-tool",
                        "adopted_at": original_ts,
                        "note": "Original note",
                    }
                ]
            )
        )

        store = AdoptionStore(toolsmith_dir)
        result = store.adopt("mcp:existing-tool", note="Updated note")

        assert result.tool_id == "mcp:existing-tool"
        assert result.note == "Updated note"
        # Timestamp should be preserved
        assert result.adopted_at.year == 2024
        assert result.adopted_at.month == 1
        assert result.adopted_at.day == 1

    def test_adopt_existing_tool_keeps_timestamp(self, tmp_path: Path) -> None:
        """Test that adopting existing tool preserves original timestamp."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)

        original_ts = "2023-06-15T12:30:00+00:00"
        (toolsmith_dir / "adopted.json").write_text(
            json.dumps(
                [
                    {
                        "tool_id": "mcp:keep-timestamp",
                        "adopted_at": original_ts,
                        "note": "Old note",
                    }
                ]
            )
        )

        store = AdoptionStore(toolsmith_dir)
        result = store.adopt("mcp:keep-timestamp", note="New note")

        # Timestamp should be preserved from original adoption
        assert result.adopted_at.year == 2023
        assert result.adopted_at.month == 6
        assert result.adopted_at.day == 15

    def test_adopt_existing_without_note_no_change(self, tmp_path: Path) -> None:
        """Test adopting existing tool without note doesn't change the note."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)

        (toolsmith_dir / "adopted.json").write_text(
            json.dumps(
                [
                    {
                        "tool_id": "mcp:has-note",
                        "adopted_at": "2024-01-01T00:00:00+00:00",
                        "note": "Existing note",
                    }
                ]
            )
        )

        store = AdoptionStore(toolsmith_dir)
        result = store.adopt("mcp:has-note")  # No note provided

        # Note should remain unchanged
        assert result.note == "Existing note"

    def test_adopt_multiple_tools(self, tmp_path: Path) -> None:
        """Test adopting multiple tools sequentially."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        store.adopt("tool:first", note="First tool")
        store.adopt("tool:second", note="Second tool")
        store.adopt("tool:third")

        tools = store.list_all()

        assert len(tools) == 3
        tool_ids = {t.tool_id for t in tools}
        assert tool_ids == {"tool:first", "tool:second", "tool:third"}


class TestAdoptionStoreRoundTrip:
    """Tests for round-trip operations (adopt then list)."""

    def test_adopt_then_list_returns_same_data(self, tmp_path: Path) -> None:
        """Test that adopted tools can be retrieved via list()."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        adopted = store.adopt("mcp:roundtrip-test", note="Testing round-trip")

        tools = store.list_all()

        assert len(tools) == 1
        assert tools[0].tool_id == adopted.tool_id
        assert tools[0].note == adopted.note
        # Compare timestamps (may have slight differences due to serialization)
        assert tools[0].adopted_at.replace(microsecond=0) == adopted.adopted_at.replace(
            microsecond=0
        )

    def test_multiple_adopts_persist_across_instances(self, tmp_path: Path) -> None:
        """Test that adopted tools persist across store instances."""
        toolsmith_dir = tmp_path / "toolsmith"

        # First store instance
        store1 = AdoptionStore(toolsmith_dir)
        store1.adopt("tool:persistent1", note="From instance 1")
        store1.adopt("tool:persistent2")

        # New store instance (simulating app restart)
        store2 = AdoptionStore(toolsmith_dir)
        store2.adopt("tool:persistent3", note="From instance 2")

        # Verify all tools are present
        tools = store2.list_all()
        tool_ids = {t.tool_id for t in tools}

        assert len(tools) == 3
        assert tool_ids == {"tool:persistent1", "tool:persistent2", "tool:persistent3"}


class TestAdoptionStoreDefault:
    """Tests for AdoptionStore.default() classmethod."""

    def test_default_returns_correct_path(self) -> None:
        """Test that default() returns store in cwd/.cub/toolsmith."""
        with patch("cub.core.toolsmith.adoption.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/fake/project")

            store = AdoptionStore.default()

            assert store.toolsmith_dir == Path("/fake/project/.cub/toolsmith")
            assert store.adopted_file == Path("/fake/project/.cub/toolsmith/adopted.json")

    def test_default_returns_adoption_store_instance(self) -> None:
        """Test that default() returns an AdoptionStore instance."""
        with patch("cub.core.toolsmith.adoption.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/tmp/test")

            store = AdoptionStore.default()

            assert isinstance(store, AdoptionStore)

    def test_default_uses_current_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that default() uses the actual current working directory."""
        monkeypatch.chdir(tmp_path)

        store = AdoptionStore.default()

        assert store.toolsmith_dir == tmp_path / ".cub" / "toolsmith"


class TestAdoptionStoreEdgeCases:
    """Tests for edge cases and error handling."""

    def test_list_handles_malformed_json_gracefully(self, tmp_path: Path) -> None:
        """Test that list() raises appropriate error for malformed JSON."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)
        (toolsmith_dir / "adopted.json").write_text("not valid json")

        store = AdoptionStore(toolsmith_dir)

        with pytest.raises(json.JSONDecodeError):
            store.list_all()

    def test_list_handles_invalid_tool_data(self, tmp_path: Path) -> None:
        """Test that list() raises error for invalid tool data."""
        toolsmith_dir = tmp_path / "toolsmith"
        toolsmith_dir.mkdir(parents=True)
        # Missing required field 'tool_id'
        (toolsmith_dir / "adopted.json").write_text('[{"note": "missing tool_id"}]')

        store = AdoptionStore(toolsmith_dir)

        with pytest.raises(ValidationError):
            store.list_all()

    def test_adopt_empty_string_tool_id(self, tmp_path: Path) -> None:
        """Test adopting a tool with empty string ID (technically valid)."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        # The model doesn't prevent empty strings
        result = store.adopt("")

        assert result.tool_id == ""

    def test_adopt_with_empty_note_string(self, tmp_path: Path) -> None:
        """Test adopting with empty string note vs None."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        # Empty string is falsy, so won't update existing note
        store.adopt("tool:test", note="Initial note")
        result = store.adopt("tool:test", note="")  # Empty string

        # Empty string is falsy, so note remains unchanged
        assert result.note == "Initial note"

    def test_concurrent_directory_exists(self, tmp_path: Path) -> None:
        """Test save() when directory is created between check and mkdir."""
        toolsmith_dir = tmp_path / "toolsmith"
        store = AdoptionStore(toolsmith_dir)

        # Pre-create the directory
        toolsmith_dir.mkdir(parents=True)

        # Should not fail even though directory exists
        store.save([AdoptedTool(tool_id="test:tool")])

        assert (toolsmith_dir / "adopted.json").exists()
