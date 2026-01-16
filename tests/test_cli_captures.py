"""
Tests for the captures CLI subcommand.

Tests `cub captures` commands: list, show, edit, import, archive.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from cub.cli import app
from cub.core.captures.models import Capture, CaptureSource, CaptureStatus
from cub.core.captures.store import CaptureStore

runner = CliRunner()


@pytest.fixture
def sample_capture() -> Capture:
    """Create a sample capture for testing."""
    return Capture(
        id="cap-001",
        created=datetime(2026, 1, 16, 14, 32, 0, tzinfo=timezone.utc),
        title="Test idea",
        tags=["test"],
        source=CaptureSource.CLI,
        status=CaptureStatus.ACTIVE,
        priority=1,
    )


@pytest.fixture
def populated_captures_dir(tmp_path: Path) -> Path:
    """Create a captures directory with sample captures."""
    captures_dir = tmp_path / "captures"
    captures_dir.mkdir()
    store = CaptureStore(captures_dir)

    # Create multiple captures
    for i in range(1, 6):
        capture = Capture(
            id=f"cap-{i:03d}",
            created=datetime(2026, 1, i, 12, 0, 0, tzinfo=timezone.utc),
            title=f"Capture {i}",
            tags=["tag1", "tag2"] if i % 2 == 0 else ["tag1"],
        )
        store.save_capture(capture, f"Content for capture {i}")

    return captures_dir


class TestCapturesListCommand:
    """Test the captures list command (default callback)."""

    def test_list_no_captures_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test list when captures directory doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["captures"])

        assert result.exit_code == 0
        assert "No captures found" in result.output

    def test_list_empty_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test list when captures directory is empty."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        captures_dir = project_dir / "captures"
        captures_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["captures"])

        assert result.exit_code == 0
        assert "No captures found" in result.output

    def test_list_shows_captures(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test list displays captures in table format."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create some captures
        store = CaptureStore.project()
        capture1 = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0, tzinfo=timezone.utc),
            title="First idea",
            tags=["feature"],
        )
        capture2 = Capture(
            id="cap-002",
            created=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            title="Second idea",
            tags=["bug"],
        )
        store.save_capture(capture1, "Content 1")
        store.save_capture(capture2, "Content 2")

        result = runner.invoke(app, ["captures"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "cap-002" in result.output
        assert "First idea" in result.output
        assert "Second idea" in result.output

    def test_list_limits_to_20_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test list limits output to 20 captures by default."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create 25 captures
        store = CaptureStore.project()
        for i in range(1, 26):
            capture = Capture(
                id=f"cap-{i:03d}",
                created=datetime(2026, 1, i % 28 + 1, 12, 0, 0, tzinfo=timezone.utc),
                title=f"Capture {i}",
            )
            store.save_capture(capture, f"Content {i}")

        result = runner.invoke(app, ["captures"])

        assert result.exit_code == 0
        # Should show summary about limiting
        assert "Showing last 20 of 25" in result.output

    def test_list_with_all_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test list --all shows all captures."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create 25 captures
        store = CaptureStore.project()
        for i in range(1, 26):
            capture = Capture(
                id=f"cap-{i:03d}",
                created=datetime(2026, 1, i % 28 + 1, 12, 0, 0, tzinfo=timezone.utc),
                title=f"Capture {i}",
            )
            store.save_capture(capture, f"Content {i}")

        result = runner.invoke(app, ["captures", "--all"])

        assert result.exit_code == 0
        # Should not show limiting message
        assert "Showing last 20" not in result.output

    def test_list_with_tag_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test list --tag filters by tag."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create captures with different tags
        store = CaptureStore.project()
        capture1 = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Feature idea",
            tags=["feature"],
        )
        capture2 = Capture(
            id="cap-002",
            created=datetime.now(timezone.utc),
            title="Bug fix",
            tags=["bug"],
        )
        store.save_capture(capture1, "Content 1")
        store.save_capture(capture2, "Content 2")

        result = runner.invoke(app, ["captures", "--tag", "feature"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "cap-002" not in result.output

    def test_list_with_search(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test list --search filters by content."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create captures with searchable content
        store = CaptureStore.project()
        capture1 = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Authentication feature",
        )
        capture2 = Capture(
            id="cap-002",
            created=datetime.now(timezone.utc),
            title="UI improvements",
        )
        store.save_capture(capture1, "Add OAuth authentication")
        store.save_capture(capture2, "Update button styles")

        result = runner.invoke(app, ["captures", "--search", "auth"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "cap-002" not in result.output

    def test_list_json_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test list --json outputs JSON format."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create a capture
        store = CaptureStore.project()
        capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0, tzinfo=timezone.utc),
            title="Test",
            tags=["test"],
        )
        store.save_capture(capture, "Content")

        result = runner.invoke(app, ["captures", "--json"])

        assert result.exit_code == 0
        # Should be valid JSON
        import json

        output = json.loads(result.output)
        assert len(output) == 1
        assert output[0]["id"] == "cap-001"
        assert output[0]["title"] == "Test"

    def test_list_global_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test list --global uses global store."""
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

        # Create global capture
        store = CaptureStore.global_store()
        capture = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Global note",
        )
        store.save_capture(capture, "Global content")

        result = runner.invoke(app, ["captures", "--global"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "global" in result.output.lower()

    def test_list_no_active_captures_filtered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that archived captures are filtered out by default."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create active and archived captures
        store = CaptureStore.project()
        active = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Active",
            status=CaptureStatus.ACTIVE,
        )
        archived = Capture(
            id="cap-002",
            created=datetime.now(timezone.utc),
            title="Archived",
            status=CaptureStatus.ARCHIVED,
        )
        store.save_capture(active, "Content")
        store.save_capture(archived, "Content")

        result = runner.invoke(app, ["captures"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "cap-002" not in result.output


class TestCapturesShowCommand:
    """Test the captures show command."""

    def test_show_existing_capture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_capture: Capture
    ) -> None:
        """Test showing an existing capture."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create capture
        store = CaptureStore.project()
        store.save_capture(sample_capture, "This is the content")

        result = runner.invoke(app, ["captures", "show", "cap-001"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "Test idea" in result.output
        assert "This is the content" in result.output

    def test_show_nonexistent_capture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test showing a capture that doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        captures_dir = project_dir / "captures"
        captures_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["captures", "show", "cap-999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_show_global_capture(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test showing a global capture."""
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

        # Create global capture
        store = CaptureStore.global_store()
        capture = Capture(
            id="cap-042",
            created=datetime.now(timezone.utc),
            title="Global note",
        )
        store.save_capture(capture, "Global content")

        result = runner.invoke(app, ["captures", "show", "cap-042", "--global"])

        assert result.exit_code == 0
        assert "cap-042" in result.output
        assert "Global note" in result.output


class TestCapturesEditCommand:
    """Test the captures edit command."""

    def test_edit_existing_capture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_capture: Capture
    ) -> None:
        """Test editing an existing capture."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create capture
        store = CaptureStore.project()
        store.save_capture(sample_capture, "Content")

        # Mock subprocess.run to simulate editor
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = runner.invoke(app, ["captures", "edit", "cap-001"])

            assert result.exit_code == 0
            assert "Edited cap-001" in result.output

            # Verify editor was called with correct file
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "cap-001.md" in str(call_args)

    def test_edit_nonexistent_capture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test editing a capture that doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        captures_dir = project_dir / "captures"
        captures_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["captures", "edit", "cap-999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_edit_uses_editor_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_capture: Capture
    ) -> None:
        """Test edit uses EDITOR environment variable."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create capture
        store = CaptureStore.project()
        store.save_capture(sample_capture, "Content")

        # Set custom editor
        monkeypatch.setenv("EDITOR", "nano")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = runner.invoke(app, ["captures", "edit", "cap-001"])

            assert result.exit_code == 0

            # Verify nano was called
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "nano"

    def test_edit_editor_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_capture: Capture
    ) -> None:
        """Test edit handles editor not found error."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create capture
        store = CaptureStore.project()
        store.save_capture(sample_capture, "Content")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = runner.invoke(app, ["captures", "edit", "cap-001"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()


class TestCapturesImportCommand:
    """Test the captures import command."""

    def test_import_from_global(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test importing a capture from global store."""
        # Set up global store
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

        global_store = CaptureStore.global_store()
        capture = Capture(
            id="cap-042",
            created=datetime.now(timezone.utc),
            title="Global idea",
            tags=["import"],
        )
        global_store.save_capture(capture, "Global content")

        # Set up project
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["captures", "import-capture", "cap-042"])

        assert result.exit_code == 0
        assert "Imported cap-042" in result.output

        # Verify file was copied to project
        project_file = project_dir / "captures" / "cap-042.md"
        assert project_file.exists()

    def test_import_with_reassign(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test importing with --reassign flag."""
        # Set up global store
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

        global_store = CaptureStore.global_store()
        capture = Capture(
            id="cap-042",
            created=datetime.now(timezone.utc),
            title="Global idea",
        )
        global_store.save_capture(capture, "Content")

        # Set up project with existing capture
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        project_store = CaptureStore.project()
        existing = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Existing",
        )
        project_store.save_capture(existing, "Content")

        result = runner.invoke(app, ["captures", "import-capture", "cap-042", "--reassign"])

        assert result.exit_code == 0
        # Should get new ID (cap-002)
        assert "cap-002" in result.output

        # Verify new ID was used
        new_file = project_dir / "captures" / "cap-002.md"
        assert new_file.exists()

    def test_import_nonexistent_capture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test importing a capture that doesn't exist."""
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

        # Create empty global store
        CaptureStore.global_store().get_captures_dir().mkdir(parents=True)

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["captures", "import-capture", "cap-999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestCapturesArchiveCommand:
    """Test the captures archive command."""

    def test_archive_active_capture(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test archiving an active capture."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create active capture
        store = CaptureStore.project()
        capture = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Active",
            status=CaptureStatus.ACTIVE,
        )
        store.save_capture(capture, "Content")

        result = runner.invoke(app, ["captures", "archive", "cap-001"])

        assert result.exit_code == 0
        assert "Archived cap-001" in result.output

        # Verify status changed
        archived = store.get_capture("cap-001")
        assert archived.status == CaptureStatus.ARCHIVED

    def test_archive_already_archived(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test archiving an already archived capture."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create archived capture
        store = CaptureStore.project()
        capture = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Already archived",
            status=CaptureStatus.ARCHIVED,
        )
        store.save_capture(capture, "Content")

        result = runner.invoke(app, ["captures", "archive", "cap-001"])

        assert result.exit_code == 0
        assert "already archived" in result.output.lower()

    def test_archive_nonexistent_capture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test archiving a capture that doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        captures_dir = project_dir / "captures"
        captures_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["captures", "archive", "cap-999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_archive_global_capture(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test archiving a global capture."""
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

        # Create global capture
        store = CaptureStore.global_store()
        capture = Capture(
            id="cap-042",
            created=datetime.now(timezone.utc),
            title="Global note",
            status=CaptureStatus.ACTIVE,
        )
        store.save_capture(capture, "Content")

        result = runner.invoke(app, ["captures", "archive", "cap-042", "--global"])

        assert result.exit_code == 0
        assert "Archived cap-042" in result.output

        # Verify archived
        archived = store.get_capture("cap-042")
        assert archived.status == CaptureStatus.ARCHIVED
