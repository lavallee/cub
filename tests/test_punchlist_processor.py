"""
Unit tests for punchlist processor.

Tests the punchlist processing workflow including hydration and task creation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.punchlist.hydrator import (
    _fallback_hydrate,
    _parse_hydration_response,
    hydrate_item,
)
from cub.core.punchlist.models import HydratedItem, PunchlistItem, PunchlistResult
from cub.core.punchlist.processor import _derive_epic_title, process_punchlist
from cub.core.tasks.models import Task, TaskStatus


class TestFallbackHydrate:
    """Test the fallback hydration without AI."""

    def test_short_title(self) -> None:
        """Test hydration with short first line."""
        item = PunchlistItem(raw_text="Fix the bug", index=0)
        result = _fallback_hydrate(item)

        assert result.title == "Fix the bug"
        assert result.description == "Fix the bug"
        assert result.raw_item == item

    def test_long_title_truncated(self) -> None:
        """Test that long titles are truncated at word boundary."""
        item = PunchlistItem(
            raw_text="This is a very long title that should be truncated at a word boundary to fit within 50 characters",
            index=0,
        )
        result = _fallback_hydrate(item)

        assert len(result.title) <= 50
        assert result.title.endswith("...")
        # Full text in description
        assert "word boundary" in result.description

    def test_multiline_uses_first_line(self) -> None:
        """Test that first line is used for title."""
        item = PunchlistItem(
            raw_text="First line for title\nSecond line\nThird line",
            index=0,
        )
        result = _fallback_hydrate(item)

        assert result.title == "First line for title"
        assert "Second line" in result.description


class TestParseHydrationResponse:
    """Test parsing Claude's hydration response."""

    def test_valid_response(self) -> None:
        """Test parsing a well-formed response."""
        response = """TITLE: Fix login authentication bug
DESCRIPTION: The login form fails to validate user credentials correctly when special characters are used in the password. This should be fixed by properly escaping user input."""
        item = PunchlistItem(raw_text="test", index=0)

        result = _parse_hydration_response(response, item)

        assert result.title == "Fix login authentication bug"
        assert "login form fails" in result.description

    def test_response_case_insensitive(self) -> None:
        """Test that TITLE/DESCRIPTION labels are case-insensitive."""
        response = """title: Some Title
description: Some description here."""
        item = PunchlistItem(raw_text="test", index=0)

        result = _parse_hydration_response(response, item)

        assert result.title == "Some Title"
        assert "Some description" in result.description

    def test_missing_title_fallback(self) -> None:
        """Test fallback when title is missing."""
        response = """DESCRIPTION: Some description without title."""
        item = PunchlistItem(raw_text="fallback text", index=0)

        result = _parse_hydration_response(response, item)

        # Should fall back to simple extraction
        assert result.title == "fallback text"

    def test_missing_description_fallback(self) -> None:
        """Test fallback when description is missing."""
        response = """TITLE: Some Title"""
        item = PunchlistItem(raw_text="fallback text", index=0)

        result = _parse_hydration_response(response, item)

        # Should fall back to simple extraction
        assert result.title == "fallback text"

    def test_title_truncated_if_too_long(self) -> None:
        """Test that very long titles are truncated."""
        long_title = "A" * 150
        response = f"""TITLE: {long_title}
DESCRIPTION: Some description."""
        item = PunchlistItem(raw_text="test", index=0)

        result = _parse_hydration_response(response, item)

        assert len(result.title) <= 100


class TestHydrateItem:
    """Test the hydrate_item function."""

    @patch("subprocess.run")
    def test_successful_hydration(self, mock_run: MagicMock) -> None:
        """Test successful Claude CLI call."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="TITLE: Fix the bug\nDESCRIPTION: Detailed description here.",
        )

        item = PunchlistItem(raw_text="Fix something", index=0)
        result = hydrate_item(item)

        assert result.title == "Fix the bug"
        assert "Detailed description" in result.description
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_fallback_on_cli_failure(self, mock_run: MagicMock) -> None:
        """Test fallback when CLI returns error."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")

        item = PunchlistItem(raw_text="Fix something", index=0)
        result = hydrate_item(item)

        # Should use fallback
        assert result.title == "Fix something"

    @patch("subprocess.run")
    def test_fallback_on_timeout(self, mock_run: MagicMock) -> None:
        """Test fallback when CLI times out."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("claude", 60)

        item = PunchlistItem(raw_text="Fix timeout issue", index=0)
        result = hydrate_item(item)

        # Should use fallback
        assert result.title == "Fix timeout issue"

    @patch("subprocess.run")
    def test_fallback_on_file_not_found(self, mock_run: MagicMock) -> None:
        """Test fallback when claude CLI not installed."""
        mock_run.side_effect = FileNotFoundError()

        item = PunchlistItem(raw_text="Fix missing CLI", index=0)
        result = hydrate_item(item)

        # Should use fallback
        assert result.title == "Fix missing CLI"


class TestDeriveEpicTitle:
    """Test the epic title derivation from filename."""

    def test_version_bugs_pattern(self) -> None:
        """Test v0.27.0-bugs.md pattern."""
        path = Path("v0.27.0-bugs.md")
        title = _derive_epic_title(path)
        assert title == "v0.27.0 Bug Fixes"

    def test_bugs_only_pattern(self) -> None:
        """Test bugs.md pattern - just 'bugs' becomes 'Bugs'."""
        path = Path("bugs.md")
        title = _derive_epic_title(path)
        assert title == "Bugs"

    def test_features_pattern(self) -> None:
        """Test feature-requests.md pattern."""
        path = Path("v1.0-feature-requests.md")
        title = _derive_epic_title(path)
        assert title == "v1.0 Feature Requests"

    def test_generic_pattern(self) -> None:
        """Test generic filename pattern."""
        path = Path("my-cool-punchlist.md")
        title = _derive_epic_title(path)
        assert title == "My Cool Punchlist"

    def test_underscore_separator(self) -> None:
        """Test filename with underscores."""
        path = Path("sprint_12_tasks.md")
        title = _derive_epic_title(path)
        assert title == "Sprint 12 Tasks"


class TestProcessPunchlist:
    """Test the full punchlist processing workflow."""

    @pytest.fixture
    def punchlist_file(self, tmp_path: Path) -> Path:
        """Create a test punchlist file."""
        file_path = tmp_path / "test-bugs.md"
        file_path.write_text(
            """Fix the typo in README

——

Add --verbose flag to cub run""",
            encoding="utf-8",
        )
        return file_path

    @pytest.fixture
    def mock_backend(self) -> MagicMock:
        """Create a mock task backend."""
        backend = MagicMock()

        # Create mock epic
        mock_epic = Task(
            id="cub-001",
            title="Test Epic",
            status=TaskStatus.OPEN,
        )
        backend.create_task.side_effect = [
            mock_epic,  # First call creates epic
            Task(id="cub-002", title="Task 1", status=TaskStatus.OPEN),
            Task(id="cub-003", title="Task 2", status=TaskStatus.OPEN),
        ]

        return backend

    def test_dry_run(self, punchlist_file: Path) -> None:
        """Test dry run doesn't create tasks."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Fixed title\nDESCRIPTION: Fixed description.",
            )

            result = process_punchlist(
                punchlist_file,
                dry_run=True,
                write_back=False,
            )

        assert result.epic.id == "<dry-run>"
        assert result.task_count == 2
        assert all(t.id.startswith("<dry-run") for t in result.tasks)

    def test_process_creates_epic_and_tasks(
        self, punchlist_file: Path, mock_backend: MagicMock
    ) -> None:
        """Test that processing creates epic and tasks."""
        with (
            patch("subprocess.run") as mock_run,
            patch(
                "cub.core.punchlist.processor.get_backend", return_value=mock_backend
            ),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Fixed title\nDESCRIPTION: Fixed description.",
            )

            result = process_punchlist(
                punchlist_file,
                dry_run=False,
                write_back=False,
            )

        assert result.epic.id == "cub-001"
        assert result.task_count == 2

        # Check epic was created with correct parameters
        epic_call = mock_backend.create_task.call_args_list[0]
        assert epic_call.kwargs["task_type"] == "epic"
        assert "punchlist" in epic_call.kwargs["labels"]

        # Check tasks were created with epic ID in labels (not using parent)
        # We use labels instead of --parent to avoid beads creating
        # blocking parent-child dependencies. Label format is "epic:{id}".
        task_call = mock_backend.create_task.call_args_list[1]
        assert "epic:cub-001" in task_call.kwargs["labels"]
        assert "parent" not in task_call.kwargs  # Should NOT use parent

    def test_custom_epic_title(
        self, punchlist_file: Path, mock_backend: MagicMock
    ) -> None:
        """Test custom epic title is used."""
        with (
            patch("subprocess.run") as mock_run,
            patch(
                "cub.core.punchlist.processor.get_backend", return_value=mock_backend
            ),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Title\nDESCRIPTION: Description.",
            )

            process_punchlist(
                punchlist_file,
                epic_title="Custom Title",
                dry_run=False,
                write_back=False,
            )

        epic_call = mock_backend.create_task.call_args_list[0]
        assert epic_call.kwargs["title"] == "Custom Title"

    def test_additional_labels(
        self, punchlist_file: Path, mock_backend: MagicMock
    ) -> None:
        """Test additional labels are added."""
        with (
            patch("subprocess.run") as mock_run,
            patch(
                "cub.core.punchlist.processor.get_backend", return_value=mock_backend
            ),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Title\nDESCRIPTION: Description.",
            )

            process_punchlist(
                punchlist_file,
                labels=["sprint-12", "high-priority"],
                dry_run=False,
                write_back=False,
            )

        epic_call = mock_backend.create_task.call_args_list[0]
        labels = epic_call.kwargs["labels"]
        assert "sprint-12" in labels
        assert "high-priority" in labels

    def test_empty_file_raises_error(self, tmp_path: Path) -> None:
        """Test that empty file raises ValueError."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="No items found"):
            process_punchlist(empty_file, dry_run=True)

    def test_progress_callback(self, punchlist_file: Path) -> None:
        """Test progress callback is called for each item."""
        progress_calls: list[tuple[int, int, HydratedItem]] = []

        def on_progress(current: int, total: int, item: HydratedItem) -> None:
            progress_calls.append((current, total, item))

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Title\nDESCRIPTION: Description.",
            )

            process_punchlist(
                punchlist_file,
                dry_run=True,
                write_back=False,
                on_item_hydrated=on_progress,
            )

        assert len(progress_calls) == 2
        assert progress_calls[0][0] == 0  # First item index
        assert progress_calls[0][1] == 2  # Total count
        assert progress_calls[1][0] == 1  # Second item index


class TestPunchlistResultModel:
    """Test PunchlistResult dataclass."""

    def test_task_count_property(self) -> None:
        """Test task_count computed property."""
        epic = Task(id="epic-001", title="Epic", status=TaskStatus.OPEN)
        tasks = [
            Task(id="task-001", title="Task 1", status=TaskStatus.OPEN),
            Task(id="task-002", title="Task 2", status=TaskStatus.OPEN),
            Task(id="task-003", title="Task 3", status=TaskStatus.OPEN),
        ]
        result = PunchlistResult(epic=epic, tasks=tasks)

        assert result.task_count == 3

    def test_empty_tasks(self) -> None:
        """Test result with no tasks."""
        epic = Task(id="epic-001", title="Epic", status=TaskStatus.OPEN)
        result = PunchlistResult(epic=epic)

        assert result.task_count == 0
        assert result.tasks == []

    def test_source_file(self) -> None:
        """Test source_file attribute."""
        epic = Task(id="epic-001", title="Epic", status=TaskStatus.OPEN)
        path = Path("/path/to/punchlist.md")
        result = PunchlistResult(epic=epic, source_file=path)

        assert result.source_file == path
