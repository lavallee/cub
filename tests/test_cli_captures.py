"""
Tests for the captures CLI subcommand.

Tests `cub captures` commands: list, show, edit, import, archive.

Two-tier storage model:
- Default: Global captures at ~/.local/share/cub/captures/{project}/
- With --project: Project captures at ./captures/
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
def isolated_capture_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up an isolated environment for capture tests."""
    # Set up project directory
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # Set up global captures directory
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

    # Mock get_project_id to return a consistent value
    with patch("cub.core.captures.store.get_project_id", return_value="test-project"):
        with patch("cub.core.captures.project_id.get_project_id", return_value="test-project"):
            with patch("cub.cli.captures.get_project_id", return_value="test-project"):
                yield {
                    "project_dir": project_dir,
                    "global_dir": global_dir,
                    "global_captures_dir": global_dir / "cub" / "captures" / "test-project",
                    "project_captures_dir": project_dir / "captures",
                }


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

    def test_list_no_captures_directory(self, isolated_capture_env: dict) -> None:
        """Test list when captures directory doesn't exist."""
        result = runner.invoke(app, ["captures"])

        assert result.exit_code == 0
        assert "No captures found" in result.output

    def test_list_empty_directory(self, isolated_capture_env: dict) -> None:
        """Test list when captures directory is empty."""
        # Create empty project captures dir
        isolated_capture_env["project_captures_dir"].mkdir(parents=True)

        result = runner.invoke(app, ["captures"])

        assert result.exit_code == 0
        assert "No captures found" in result.output

    def test_list_shows_captures(self, isolated_capture_env: dict) -> None:
        """Test list displays captures in table format."""
        # Create some captures in global store (default)
        store = CaptureStore.global_store()
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

    def test_list_limits_to_20_by_default(self, isolated_capture_env: dict) -> None:
        """Test list limits output to 20 captures by default."""
        # Create 25 captures in global store
        store = CaptureStore.global_store()
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
        assert "20 of 25" in result.output

    def test_list_with_all_flag(self, isolated_capture_env: dict) -> None:
        """Test list --all shows all captures."""
        # Create 25 captures in global store
        store = CaptureStore.global_store()
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
        assert "20 of" not in result.output

    def test_list_with_tag_filter(self, isolated_capture_env: dict) -> None:
        """Test list --tag filters by tag."""
        # Create captures with different tags in global store
        store = CaptureStore.global_store()
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

    def test_list_with_search(self, isolated_capture_env: dict) -> None:
        """Test list --search filters by content."""
        # Create captures with searchable content in global store
        store = CaptureStore.global_store()
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

    def test_list_json_output(self, isolated_capture_env: dict) -> None:
        """Test list --json outputs JSON format with global/project sections."""
        # Create captures in both stores
        global_store = CaptureStore.global_store()
        global_capture = Capture(
            id="cap-001",
            created=datetime(2026, 1, 16, 14, 32, 0, tzinfo=timezone.utc),
            title="Global Test",
            tags=["test"],
        )
        global_store.save_capture(global_capture, "Global content")

        project_store = CaptureStore.project()
        project_capture = Capture(
            id="cap-002",
            created=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            title="Project Test",
            tags=["project"],
        )
        project_store.save_capture(project_capture, "Project content")

        result = runner.invoke(app, ["captures", "--json"])

        assert result.exit_code == 0
        # Should be valid JSON with global/project sections
        import json

        output = json.loads(result.output)
        assert "global" in output
        assert "project" in output
        assert len(output["global"]) == 1
        assert len(output["project"]) == 1
        assert output["global"][0]["id"] == "cap-001"
        assert output["project"][0]["id"] == "cap-002"

    def test_list_global_flag(self, isolated_capture_env: dict) -> None:
        """Test list --global shows only global store."""
        # Create global capture
        global_store = CaptureStore.global_store()
        global_capture = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Global note",
        )
        global_store.save_capture(global_capture, "Global content")

        # Create project capture
        project_store = CaptureStore.project()
        project_capture = Capture(
            id="cap-002",
            created=datetime.now(timezone.utc),
            title="Project note",
        )
        project_store.save_capture(project_capture, "Project content")

        result = runner.invoke(app, ["captures", "--global"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "cap-002" not in result.output
        assert "global" in result.output.lower()

    def test_list_project_flag(self, isolated_capture_env: dict) -> None:
        """Test list --project shows only project store."""
        # Create global capture
        global_store = CaptureStore.global_store()
        global_capture = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Global note",
        )
        global_store.save_capture(global_capture, "Global content")

        # Create project capture
        project_store = CaptureStore.project()
        project_capture = Capture(
            id="cap-002",
            created=datetime.now(timezone.utc),
            title="Project note",
        )
        project_store.save_capture(project_capture, "Project content")

        result = runner.invoke(app, ["captures", "--project"])

        assert result.exit_code == 0
        assert "cap-002" in result.output
        assert "cap-001" not in result.output
        assert "project" in result.output.lower()

    def test_list_no_active_captures_filtered(self, isolated_capture_env: dict) -> None:
        """Test that archived captures are filtered out by default."""
        # Create active and archived captures in global store
        store = CaptureStore.global_store()
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

    def test_show_existing_capture_in_global(
        self, isolated_capture_env: dict, sample_capture: Capture
    ) -> None:
        """Test showing an existing capture in global store."""
        # Create capture in global store
        store = CaptureStore.global_store()
        store.save_capture(sample_capture, "This is the content")

        result = runner.invoke(app, ["captures", "show", "cap-001"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "Test idea" in result.output
        assert "This is the content" in result.output
        assert "global" in result.output.lower()

    def test_show_existing_capture_in_project(
        self, isolated_capture_env: dict, sample_capture: Capture
    ) -> None:
        """Test showing an existing capture in project store."""
        # Create capture in project store
        store = CaptureStore.project()
        store.save_capture(sample_capture, "This is the content")

        result = runner.invoke(app, ["captures", "show", "cap-001"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "Test idea" in result.output
        assert "This is the content" in result.output
        assert "project" in result.output.lower()

    def test_show_nonexistent_capture(self, isolated_capture_env: dict) -> None:
        """Test showing a capture that doesn't exist."""
        result = runner.invoke(app, ["captures", "show", "cap-999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_show_searches_both_stores(self, isolated_capture_env: dict) -> None:
        """Test that show command searches both global and project stores."""
        # Create capture in global store
        global_store = CaptureStore.global_store()
        global_capture = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Global note",
        )
        global_store.save_capture(global_capture, "Global content")

        # Create capture in project store
        project_store = CaptureStore.project()
        project_capture = Capture(
            id="cap-002",
            created=datetime.now(timezone.utc),
            title="Project note",
        )
        project_store.save_capture(project_capture, "Project content")

        # Should find global capture
        result1 = runner.invoke(app, ["captures", "show", "cap-001"])
        assert result1.exit_code == 0
        assert "Global note" in result1.output

        # Should find project capture
        result2 = runner.invoke(app, ["captures", "show", "cap-002"])
        assert result2.exit_code == 0
        assert "Project note" in result2.output


class TestCapturesEditCommand:
    """Test the captures edit command."""

    def test_edit_existing_capture_in_global(
        self, isolated_capture_env: dict, sample_capture: Capture
    ) -> None:
        """Test editing an existing capture in global store."""
        # Create capture in global store
        store = CaptureStore.global_store()
        store.save_capture(sample_capture, "Content")

        # Mock subprocess.run to simulate editor
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = runner.invoke(app, ["captures", "edit", "cap-001"])

            assert result.exit_code == 0
            assert "Edited cap-001" in result.output
            assert "global" in result.output.lower()

            # Verify editor was called with correct file
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "cap-001.md" in str(call_args)

    def test_edit_existing_capture_in_project(
        self, isolated_capture_env: dict, sample_capture: Capture
    ) -> None:
        """Test editing an existing capture in project store."""
        # Create capture in project store
        store = CaptureStore.project()
        store.save_capture(sample_capture, "Content")

        # Mock subprocess.run to simulate editor
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            result = runner.invoke(app, ["captures", "edit", "cap-001"])

            assert result.exit_code == 0
            assert "Edited cap-001" in result.output
            assert "project" in result.output.lower()

    def test_edit_nonexistent_capture(self, isolated_capture_env: dict) -> None:
        """Test editing a capture that doesn't exist."""
        result = runner.invoke(app, ["captures", "edit", "cap-999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_edit_uses_editor_env_var(
        self, isolated_capture_env: dict, sample_capture: Capture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test edit uses EDITOR environment variable."""
        # Create capture in global store
        store = CaptureStore.global_store()
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
        self, isolated_capture_env: dict, sample_capture: Capture
    ) -> None:
        """Test edit handles editor not found error."""
        # Create capture in global store
        store = CaptureStore.global_store()
        store.save_capture(sample_capture, "Content")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = runner.invoke(app, ["captures", "edit", "cap-001"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()


class TestCapturesImportCommand:
    """Test the captures import command."""

    def test_import_from_global(self, isolated_capture_env: dict) -> None:
        """Test importing a capture from global store (moves by default)."""
        # Create global capture
        global_store = CaptureStore.global_store()
        capture = Capture(
            id="cap-042",
            created=datetime.now(timezone.utc),
            title="Global idea",
            tags=["import"],
        )
        global_store.save_capture(capture, "Global content")

        result = runner.invoke(app, ["captures", "import", "cap-042"])

        assert result.exit_code == 0
        assert "Imported cap-042" in result.output

        # Verify file was copied to project
        project_file = isolated_capture_env["project_captures_dir"] / "cap-042.md"
        assert project_file.exists()

        # Verify file was removed from global (default behavior)
        global_file = isolated_capture_env["global_captures_dir"] / "cap-042.md"
        assert not global_file.exists()

    def test_import_with_keep(self, isolated_capture_env: dict) -> None:
        """Test importing with --keep flag preserves global copy."""
        # Create global capture
        global_store = CaptureStore.global_store()
        capture = Capture(
            id="cap-042",
            created=datetime.now(timezone.utc),
            title="Global idea",
        )
        global_store.save_capture(capture, "Content")

        result = runner.invoke(app, ["captures", "import", "cap-042", "--keep"])

        assert result.exit_code == 0
        assert "Imported cap-042" in result.output

        # Verify file exists in both locations
        project_file = isolated_capture_env["project_captures_dir"] / "cap-042.md"
        global_file = isolated_capture_env["global_captures_dir"] / "cap-042.md"
        assert project_file.exists()
        assert global_file.exists()

    def test_import_nonexistent_capture(self, isolated_capture_env: dict) -> None:
        """Test importing a capture that doesn't exist."""
        result = runner.invoke(app, ["captures", "import", "cap-999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestCapturesArchiveCommand:
    """Test the captures archive command."""

    def test_archive_active_capture_in_global(self, isolated_capture_env: dict) -> None:
        """Test archiving an active capture in global store."""
        # Create active capture in global store
        store = CaptureStore.global_store()
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
        assert "global" in result.output.lower()

        # Verify status changed
        archived = store.get_capture("cap-001")
        assert archived.status == CaptureStatus.ARCHIVED

    def test_archive_active_capture_in_project(self, isolated_capture_env: dict) -> None:
        """Test archiving an active capture in project store."""
        # Create active capture in project store
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
        assert "project" in result.output.lower()

        # Verify status changed
        archived = store.get_capture("cap-001")
        assert archived.status == CaptureStatus.ARCHIVED

    def test_archive_already_archived(self, isolated_capture_env: dict) -> None:
        """Test archiving an already archived capture."""
        # Create archived capture in global store
        store = CaptureStore.global_store()
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

    def test_archive_nonexistent_capture(self, isolated_capture_env: dict) -> None:
        """Test archiving a capture that doesn't exist."""
        result = runner.invoke(app, ["captures", "archive", "cap-999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_archive_searches_both_stores(self, isolated_capture_env: dict) -> None:
        """Test that archive command searches both global and project stores."""
        # Create capture in global store
        global_store = CaptureStore.global_store()
        global_capture = Capture(
            id="cap-001",
            created=datetime.now(timezone.utc),
            title="Global note",
            status=CaptureStatus.ACTIVE,
        )
        global_store.save_capture(global_capture, "Global content")

        # Create capture in project store
        project_store = CaptureStore.project()
        project_capture = Capture(
            id="cap-002",
            created=datetime.now(timezone.utc),
            title="Project note",
            status=CaptureStatus.ACTIVE,
        )
        project_store.save_capture(project_capture, "Project content")

        # Should archive global capture
        result1 = runner.invoke(app, ["captures", "archive", "cap-001"])
        assert result1.exit_code == 0
        assert global_store.get_capture("cap-001").status == CaptureStatus.ARCHIVED

        # Should archive project capture
        result2 = runner.invoke(app, ["captures", "archive", "cap-002"])
        assert result2.exit_code == 0
        assert project_store.get_capture("cap-002").status == CaptureStatus.ARCHIVED
