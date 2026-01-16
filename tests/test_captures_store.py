"""
Unit tests for capture storage layer.

Tests CaptureStore for reading/writing captures to filesystem,
ID generation, and store location handling.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.captures.models import Capture, CaptureSource, CaptureStatus
from cub.core.captures.store import CaptureStore


class TestCaptureStoreInit:
    """Test CaptureStore initialization."""

    def test_init_with_path(self, tmp_path: Path) -> None:
        """Test creating store with explicit path."""
        captures_dir = tmp_path / "captures"
        store = CaptureStore(captures_dir)

        assert store.get_captures_dir() == captures_dir

    def test_init_creates_directory_on_demand(self, tmp_path: Path) -> None:
        """Test that directory is created when needed."""
        captures_dir = tmp_path / "captures"
        store = CaptureStore(captures_dir)

        # Directory doesn't exist yet
        assert not captures_dir.exists()

        # Save a capture - should create directory
        capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Test",
        )
        store.save_capture(capture, "Test content")

        # Now directory should exist
        assert captures_dir.exists()


class TestCaptureStoreNextId:
    """Test ID generation."""

    def test_next_id_empty_directory(self, tmp_path: Path) -> None:
        """Test next_id generates a valid random ID when no captures exist."""
        import re

        store = CaptureStore(tmp_path / "captures")

        next_id = store.next_id()

        # Should be a random 6-char alphanumeric ID
        assert re.match(r"^cap-[a-z0-9]{6}$", next_id)

    def test_next_id_generates_unique_ids(self, tmp_path: Path) -> None:
        """Test next_id generates unique random IDs."""
        import re

        captures_dir = tmp_path / "captures"
        captures_dir.mkdir()
        store = CaptureStore(captures_dir)

        # Generate multiple IDs and verify uniqueness
        generated_ids = set()
        for _ in range(10):
            new_id = store.next_id()
            # Verify format
            assert re.match(r"^cap-[a-z0-9]{6}$", new_id)
            # Verify uniqueness (before we save with this ID)
            assert new_id not in generated_ids
            generated_ids.add(new_id)

            # Save with this ID so collision detection sees it
            capture = Capture(
                id=new_id,
                created=datetime.now(),
                title=f"Capture",
            )
            store.save_capture(capture, "Content")

    def test_next_id_avoids_collision(self, tmp_path: Path) -> None:
        """Test next_id avoids collision with existing IDs."""
        import re

        captures_dir = tmp_path / "captures"
        captures_dir.mkdir()
        store = CaptureStore(captures_dir)

        # Create a capture with a specific ID
        existing_id = "cap-abc123"
        capture = Capture(
            id=existing_id,
            created=datetime.now(),
            title="Existing",
        )
        store.save_capture(capture, "Content")

        # Generate multiple new IDs - none should collide with existing
        for _ in range(5):
            new_id = store.next_id()
            assert re.match(r"^cap-[a-z0-9]{6}$", new_id)
            assert new_id != existing_id

    def test_next_id_ignores_malformed_files(self, tmp_path: Path) -> None:
        """Test next_id ignores non-capture files."""
        import re

        captures_dir = tmp_path / "captures"
        captures_dir.mkdir()
        store = CaptureStore(captures_dir)

        # Create valid capture
        capture = Capture(
            id="cap-abc123",
            created=datetime.now(),
            title="Valid",
        )
        store.save_capture(capture, "Content")

        # Create files that should be ignored
        (captures_dir / "README.md").write_text("Not a capture")
        (captures_dir / "cap-invalid.md").write_text("Invalid ID format")
        (captures_dir / "note-001.md").write_text("Wrong prefix")

        # Should still generate a new unique ID
        next_id = store.next_id()
        assert re.match(r"^cap-[a-z0-9]{6}$", next_id)
        assert next_id != "cap-abc123"  # Not the existing ID

    def test_next_id_creates_directory(self, tmp_path: Path) -> None:
        """Test next_id creates directory if it doesn't exist."""
        import re

        captures_dir = tmp_path / "captures"
        store = CaptureStore(captures_dir)

        # Directory doesn't exist yet
        assert not captures_dir.exists()

        # next_id should create it
        next_id = store.next_id()

        assert captures_dir.exists()
        assert re.match(r"^cap-[a-z0-9]{6}$", next_id)


class TestCaptureStoreSave:
    """Test saving captures to disk."""

    def test_save_minimal_capture(self, tmp_path: Path) -> None:
        """Test saving a minimal capture."""
        store = CaptureStore(tmp_path / "captures")
        capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Test idea",
        )
        content = "This is the content of the capture."

        store.save_capture(capture, content)

        # Verify file was created
        capture_file = tmp_path / "captures" / "cap-001.md"
        assert capture_file.exists()

        # Verify content
        file_content = capture_file.read_text()
        assert "id: cap-001" in file_content
        assert "title: Test idea" in file_content
        assert "This is the content of the capture." in file_content

    def test_save_full_capture(self, tmp_path: Path) -> None:
        """Test saving a capture with all fields."""
        store = CaptureStore(tmp_path / "captures")
        capture = Capture(
            id="cap-002",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Important idea",
            tags=["feature", "urgent"],
            source=CaptureSource.INTERACTIVE,
            status=CaptureStatus.ACTIVE,
            priority=1,
        )
        content = "Detailed content here."

        store.save_capture(capture, content)

        # Verify file content
        capture_file = tmp_path / "captures" / "cap-002.md"
        file_content = capture_file.read_text()

        assert "id: cap-002" in file_content
        assert "title: Important idea" in file_content
        assert "- feature" in file_content
        assert "- urgent" in file_content
        assert "source: interactive" in file_content
        assert "priority: 1" in file_content
        assert "Detailed content here." in file_content

    def test_save_multiline_content(self, tmp_path: Path) -> None:
        """Test saving capture with multiline content."""
        store = CaptureStore(tmp_path / "captures")
        capture = Capture(
            id="cap-001",
            created=datetime.now(),
            title="Multiline note",
        )
        content = """Line 1
Line 2
Line 3

Paragraph 2"""

        store.save_capture(capture, content)

        # Verify multiline content preserved
        capture_file = tmp_path / "captures" / "cap-001.md"
        file_content = capture_file.read_text()

        assert "Line 1" in file_content
        assert "Line 2" in file_content
        assert "Line 3" in file_content
        assert "Paragraph 2" in file_content

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Test that saving overwrites existing capture."""
        store = CaptureStore(tmp_path / "captures")
        capture = Capture(
            id="cap-001",
            created=datetime.now(),
            title="Original",
        )

        # Save first version
        store.save_capture(capture, "Original content")

        # Update and save again
        capture.title = "Updated"
        store.save_capture(capture, "Updated content")

        # Verify updated version
        capture_file = tmp_path / "captures" / "cap-001.md"
        file_content = capture_file.read_text()

        assert "title: Updated" in file_content
        assert "Updated content" in file_content
        assert "Original content" not in file_content


class TestCaptureStoreList:
    """Test listing captures from directory."""

    def test_list_empty_directory_fails(self, tmp_path: Path) -> None:
        """Test list_captures raises error when directory doesn't exist."""
        store = CaptureStore(tmp_path / "captures")

        with pytest.raises(FileNotFoundError):
            store.list_captures()

    def test_list_no_captures(self, tmp_path: Path) -> None:
        """Test list_captures returns empty list when no captures exist."""
        captures_dir = tmp_path / "captures"
        captures_dir.mkdir()
        store = CaptureStore(captures_dir)

        captures = store.list_captures()

        assert captures == []

    def test_list_single_capture(self, tmp_path: Path) -> None:
        """Test listing a single capture."""
        store = CaptureStore(tmp_path / "captures")
        capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Test",
        )
        store.save_capture(capture, "Content")

        captures = store.list_captures()

        assert len(captures) == 1
        assert captures[0].id == "cap-001"
        assert captures[0].title == "Test"

    def test_list_multiple_captures(self, tmp_path: Path) -> None:
        """Test listing multiple captures."""
        store = CaptureStore(tmp_path / "captures")

        # Create captures with different timestamps
        for i in range(1, 4):
            capture = Capture(
                id=f"cap-{i:03d}",
                created=datetime(2026, 1, i, 12, 0, 0),
                title=f"Capture {i}",
            )
            store.save_capture(capture, f"Content {i}")

        captures = store.list_captures()

        assert len(captures) == 3
        # Should be sorted by creation date, newest first
        assert captures[0].id == "cap-003"
        assert captures[1].id == "cap-002"
        assert captures[2].id == "cap-001"

    def test_list_sorted_by_date_newest_first(self, tmp_path: Path) -> None:
        """Test captures are sorted by creation date, newest first."""
        store = CaptureStore(tmp_path / "captures")

        # Create captures in non-chronological order
        capture_old = Capture(
            id="cap-001",
            created=datetime(2026, 1, 1, 10, 0, 0),
            title="Oldest",
        )
        capture_newest = Capture(
            id="cap-002",
            created=datetime(2026, 1, 16, 10, 0, 0),
            title="Newest",
        )
        capture_middle = Capture(
            id="cap-003",
            created=datetime(2026, 1, 10, 10, 0, 0),
            title="Middle",
        )

        # Save in random order
        store.save_capture(capture_middle, "Content")
        store.save_capture(capture_old, "Content")
        store.save_capture(capture_newest, "Content")

        captures = store.list_captures()

        # Should be sorted newest to oldest
        assert captures[0].id == "cap-002"  # Newest
        assert captures[1].id == "cap-003"  # Middle
        assert captures[2].id == "cap-001"  # Oldest

    def test_list_ignores_non_capture_files(self, tmp_path: Path) -> None:
        """Test list_captures ignores non-capture files."""
        captures_dir = tmp_path / "captures"
        captures_dir.mkdir()
        store = CaptureStore(captures_dir)

        # Create valid capture
        capture = Capture(
            id="cap-001",
            created=datetime.now(),
            title="Valid",
        )
        store.save_capture(capture, "Content")

        # Create files that should be ignored
        (captures_dir / "README.md").write_text("Not a capture")
        (captures_dir / "notes.txt").write_text("Text file")

        captures = store.list_captures()

        # Should only find the valid capture
        assert len(captures) == 1
        assert captures[0].id == "cap-001"

    def test_list_skips_malformed_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test list_captures skips malformed capture files."""
        captures_dir = tmp_path / "captures"
        captures_dir.mkdir()
        store = CaptureStore(captures_dir)

        # Create valid capture
        capture = Capture(
            id="cap-001",
            created=datetime.now(),
            title="Valid",
        )
        store.save_capture(capture, "Content")

        # Create malformed capture file
        (captures_dir / "cap-002.md").write_text("Invalid YAML frontmatter")

        captures = store.list_captures()

        # Should only return valid capture, skip malformed
        assert len(captures) == 1
        assert captures[0].id == "cap-001"

        # Should print warning about malformed file
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "cap-002.md" in captured.out


class TestCaptureStoreGet:
    """Test retrieving individual captures."""

    def test_get_existing_capture(self, tmp_path: Path) -> None:
        """Test getting an existing capture."""
        store = CaptureStore(tmp_path / "captures")
        capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0),
            title="Test",
            tags=["test"],
        )
        store.save_capture(capture, "Content")

        retrieved = store.get_capture("cap-001")

        assert retrieved.id == "cap-001"
        assert retrieved.title == "Test"
        assert retrieved.tags == ["test"]

    def test_get_nonexistent_capture_fails(self, tmp_path: Path) -> None:
        """Test getting a capture that doesn't exist raises error."""
        captures_dir = tmp_path / "captures"
        captures_dir.mkdir()
        store = CaptureStore(captures_dir)

        with pytest.raises(FileNotFoundError, match="Capture not found: cap-999"):
            store.get_capture("cap-999")

    def test_get_malformed_capture_fails(self, tmp_path: Path) -> None:
        """Test getting a malformed capture raises error."""
        captures_dir = tmp_path / "captures"
        captures_dir.mkdir()
        store = CaptureStore(captures_dir)

        # Create malformed file
        (captures_dir / "cap-001.md").write_text("Invalid YAML")

        with pytest.raises(ValueError):
            store.get_capture("cap-001")


class TestCaptureStoreFactoryMethods:
    """Test factory methods for creating stores."""

    def test_project_store_default_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test project store uses current directory by default."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        store = CaptureStore.project()

        assert store.get_captures_dir() == project_dir / "captures"

    def test_project_store_explicit_path(self, tmp_path: Path) -> None:
        """Test project store with explicit path."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        store = CaptureStore.project(project_dir)

        assert store.get_captures_dir() == project_dir / "captures"

    def test_global_store_default_location(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test global store uses XDG_DATA_HOME with project ID."""
        from unittest.mock import patch

        data_home = tmp_path / "data"
        data_home.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

        # Mock get_project_id to return a consistent value
        with patch("cub.core.captures.store.get_project_id", return_value="test-project"):
            store = CaptureStore.global_store()

        assert store.get_captures_dir() == data_home / "cub" / "captures" / "test-project"

    def test_global_store_with_explicit_project_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test global store with explicit project ID."""
        data_home = tmp_path / "data"
        data_home.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

        store = CaptureStore.global_store(project_id="my-project")

        assert store.get_captures_dir() == data_home / "cub" / "captures" / "my-project"

    def test_global_store_no_xdg_uses_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test global store uses ~/.local/share when XDG_DATA_HOME not set."""
        from unittest.mock import patch

        # Remove XDG_DATA_HOME if set
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)

        # Mock expanduser to use tmp_path
        import os

        original_expanduser = os.path.expanduser

        def mock_expanduser(path: str) -> str:
            if path == "~/.local/share":
                return str(tmp_path / ".local" / "share")
            return original_expanduser(path)

        monkeypatch.setattr(os.path, "expanduser", mock_expanduser)

        # Mock get_project_id
        with patch("cub.core.captures.store.get_project_id", return_value="test-project"):
            store = CaptureStore.global_store()

        expected = tmp_path / ".local" / "share" / "cub" / "captures" / "test-project"
        assert store.get_captures_dir() == expected

    def test_global_unscoped_store(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test global_unscoped store for captures outside any project."""
        data_home = tmp_path / "data"
        data_home.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

        store = CaptureStore.global_unscoped()

        assert store.get_captures_dir() == data_home / "cub" / "captures" / "_global"


class TestCaptureStoreRoundTrip:
    """Test full save/load round-trips."""

    def test_roundtrip_minimal_capture(self, tmp_path: Path) -> None:
        """Test saving and loading a minimal capture."""
        store = CaptureStore(tmp_path / "captures")
        original = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0, tzinfo=timezone.utc),
            title="Test",
        )
        content = "Test content"

        # Save
        store.save_capture(original, content)

        # Load
        loaded = store.get_capture("cap-001")

        # Verify all fields match
        assert loaded.id == original.id
        assert loaded.created == original.created
        assert loaded.title == original.title
        assert loaded.tags == original.tags
        assert loaded.source == original.source
        assert loaded.status == original.status
        assert loaded.priority == original.priority

    def test_roundtrip_full_capture(self, tmp_path: Path) -> None:
        """Test saving and loading a capture with all fields."""
        store = CaptureStore(tmp_path / "captures")
        original = Capture(
            id="cap-002",
            created=datetime(2026, 1, 16, 14, 32, 0, tzinfo=timezone.utc),
            title="Important",
            tags=["feature", "urgent"],
            source=CaptureSource.INTERACTIVE,
            status=CaptureStatus.ARCHIVED,
            priority=1,
        )
        content = "Detailed content"

        # Save
        store.save_capture(original, content)

        # Load
        loaded = store.get_capture("cap-002")

        # Verify all fields match
        assert loaded.id == original.id
        assert loaded.created == original.created
        assert loaded.title == original.title
        assert loaded.tags == original.tags
        assert loaded.source == original.source
        assert loaded.status == original.status
        assert loaded.priority == original.priority
