"""
Unit tests for punchlist processor.

Tests the punchlist processing workflow including hydration,
plan generation, and round-trip with parse_itemized_plan.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.hydrate.engine import _fallback, _parse_response
from cub.core.hydrate.models import HydrationResult, HydrationStatus
from cub.core.hydrate.formatter import generate_itemized_plan
from cub.core.punchlist.models import PunchlistItem, PunchlistResult
from cub.core.punchlist.processor import _derive_epic_title, process_punchlist


class TestFallbackHydrate:
    """Test the fallback hydration without AI."""

    def test_short_title(self) -> None:
        """Test hydration with short first line."""
        result = _fallback("Fix the bug")

        assert result.title == "Fix the bug"
        assert result.context == "Fix the bug"
        assert result.status == HydrationStatus.FALLBACK

    def test_long_title_truncated(self) -> None:
        """Test that long titles are truncated at word boundary."""
        text = "This is a very long title that should be truncated at a word boundary to fit within 50 characters"
        result = _fallback(text)

        assert len(result.title) <= 50
        assert result.title.endswith("...")
        assert "word boundary" in result.context

    def test_multiline_uses_first_line(self) -> None:
        """Test that first line is used for title."""
        result = _fallback("First line for title\nSecond line\nThird line")

        assert result.title == "First line for title"
        assert "Second line" in result.context


class TestParseHydrationResponse:
    """Test parsing Claude's hydration response."""

    def test_valid_response_new_format(self) -> None:
        """Test parsing a well-formed response with new CONTEXT/STEPS/CRITERIA format."""
        response = """TITLE: Fix login authentication bug
CONTEXT: The login form fails to validate user credentials correctly when special characters are used in the password.
STEPS:
1. Update the password validation regex
2. Add proper escaping for special characters
CRITERIA:
- [ ] Login works with special characters in password
- [ ] Existing tests still pass"""
        result = _parse_response(response, "test")

        assert result.title == "Fix login authentication bug"
        assert "login form fails" in result.context
        assert len(result.implementation_steps) == 2
        assert len(result.acceptance_criteria) == 2
        assert result.status == HydrationStatus.SUCCESS

    def test_valid_response_legacy_format(self) -> None:
        """Test parsing legacy TITLE/DESCRIPTION format."""
        response = """TITLE: Fix login authentication bug
DESCRIPTION: The login form fails to validate user credentials correctly."""
        result = _parse_response(response, "test")

        assert result.title == "Fix login authentication bug"
        assert "login form fails" in result.context
        assert result.implementation_steps == []

    def test_response_case_insensitive(self) -> None:
        """Test that labels are case-insensitive."""
        response = """title: Some Title
context: Some context here."""
        result = _parse_response(response, "test")

        assert result.title == "Some Title"
        assert "Some context" in result.context

    def test_missing_title_fallback(self) -> None:
        """Test fallback when title is missing."""
        response = """CONTEXT: Some context without title."""
        result = _parse_response(response, "fallback text")

        assert result.status == HydrationStatus.FALLBACK
        assert result.title == "fallback text"

    def test_missing_context_and_description_fallback(self) -> None:
        """Test fallback when both context and description are missing."""
        response = """TITLE: Some Title"""
        result = _parse_response(response, "fallback text")

        assert result.status == HydrationStatus.FALLBACK

    def test_title_truncated_if_too_long(self) -> None:
        """Test that very long titles are truncated."""
        long_title = "A" * 150
        response = f"""TITLE: {long_title}
CONTEXT: Some context."""
        result = _parse_response(response, "test")

        assert len(result.title) <= 100


class TestDeriveEpicTitle:
    """Test the epic title derivation from filename."""

    def test_version_bugs_pattern(self) -> None:
        path = Path("v0.27.0-bugs.md")
        title = _derive_epic_title(path)
        assert title == "v0.27.0 Bug Fixes"

    def test_bugs_only_pattern(self) -> None:
        path = Path("bugs.md")
        title = _derive_epic_title(path)
        assert title == "Bugs"

    def test_features_pattern(self) -> None:
        path = Path("v1.0-feature-requests.md")
        title = _derive_epic_title(path)
        assert title == "v1.0 Feature Requests"

    def test_generic_pattern(self) -> None:
        path = Path("my-cool-punchlist.md")
        title = _derive_epic_title(path)
        assert title == "My Cool Punchlist"

    def test_underscore_separator(self) -> None:
        path = Path("sprint_12_tasks.md")
        title = _derive_epic_title(path)
        assert title == "Sprint 12 Tasks"


class TestGenerateItemizedPlan:
    """Test markdown plan generation from hydration results."""

    def test_generates_valid_markdown(self) -> None:
        """Test that generated markdown has correct structure."""
        results = [
            HydrationResult(
                title="Fix login bug",
                description="Login fails with special chars",
                context="The login form fails when passwords contain special characters.",
                implementation_steps=["Update regex", "Add escaping"],
                acceptance_criteria=["Login works with special chars"],
                status=HydrationStatus.SUCCESS,
                source_text="Fix login bug with special chars",
            ),
            HydrationResult(
                title="Add verbose flag",
                description="Add --verbose to cub run",
                context="Users need more output during cub run sessions.",
                implementation_steps=["Add CLI flag", "Wire to logger"],
                acceptance_criteria=["--verbose shows extra output"],
                status=HydrationStatus.SUCCESS,
                source_text="Add verbose flag to cub run",
            ),
        ]

        md = generate_itemized_plan(
            results=results,
            epic_title="Test Bugs",
            source_path=Path("test-bugs.md"),
            labels=["sprint-1"],
            project_id="cub",
        )

        # Check structure
        assert "# Itemized Plan: Test Bugs" in md
        assert "## Context Summary" in md
        assert "## Epic: cub-" in md
        assert "### Task: cub-" in md
        assert "Fix login bug" in md
        assert "Add verbose flag" in md
        assert "**Context**:" in md
        assert "**Implementation Steps**:" in md
        assert "**Acceptance Criteria**:" in md
        assert "punchlist" in md
        assert "sprint-1" in md

    def test_fallback_items_included(self) -> None:
        """Test that fallback items are included in output."""
        results = [
            HydrationResult(
                title="Simple fix",
                description="Simple fix description",
                context="Simple fix context",
                status=HydrationStatus.FALLBACK,
                source_text="simple fix",
            ),
        ]

        md = generate_itemized_plan(
            results=results,
            epic_title="Fallback Test",
            project_id="cub",
        )

        assert "Simple fix" in md
        assert "### Task: cub-" in md


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

    def test_dry_run(self, punchlist_file: Path) -> None:
        """Test dry run doesn't write files."""
        with (
            patch("subprocess.run") as mock_run,
            patch("cub.core.punchlist.processor.get_project_id", return_value="cub"),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Fixed title\nCONTEXT: Fixed context.\nSTEPS:\n1. Do something\nCRITERIA:\n- [ ] It works",
            )

            result = process_punchlist(
                punchlist_file,
                dry_run=True,
            )

        assert result.task_count == 2
        assert result.epic_title == "test Bug Fixes"
        assert result.output_file is not None
        # Dry run should NOT write the file
        assert not result.output_file.exists()

    def test_process_writes_plan_file(self, punchlist_file: Path) -> None:
        """Test that processing writes an itemized-plan.md file."""
        with (
            patch("subprocess.run") as mock_run,
            patch("cub.core.punchlist.processor.get_project_id", return_value="cub"),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Fixed title\nCONTEXT: Fixed context paragraph.\nSTEPS:\n1. Do the thing\nCRITERIA:\n- [ ] It works",
            )

            result = process_punchlist(
                punchlist_file,
                dry_run=False,
            )

        assert result.output_file is not None
        assert result.output_file.exists()
        content = result.output_file.read_text(encoding="utf-8")
        assert "# Itemized Plan:" in content
        assert "## Epic: cub-" in content
        assert "### Task: cub-" in content

    def test_custom_output_path(self, punchlist_file: Path, tmp_path: Path) -> None:
        """Test custom output path."""
        custom_output = tmp_path / "custom-plan.md"

        with (
            patch("subprocess.run") as mock_run,
            patch("cub.core.punchlist.processor.get_project_id", return_value="cub"),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Title\nCONTEXT: Context.\nSTEPS:\n1. Step\nCRITERIA:\n- [ ] Done",
            )

            result = process_punchlist(
                punchlist_file,
                output=custom_output,
            )

        assert result.output_file == custom_output
        assert custom_output.exists()

    def test_custom_epic_title(self, punchlist_file: Path) -> None:
        """Test custom epic title is used."""
        with (
            patch("subprocess.run") as mock_run,
            patch("cub.core.punchlist.processor.get_project_id", return_value="cub"),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Title\nCONTEXT: Context.\nSTEPS:\n1. Step\nCRITERIA:\n- [ ] Done",
            )

            result = process_punchlist(
                punchlist_file,
                epic_title="Custom Title",
            )

        assert result.epic_title == "Custom Title"
        content = result.output_file.read_text(encoding="utf-8")
        assert "Custom Title" in content

    def test_additional_labels(self, punchlist_file: Path) -> None:
        """Test additional labels appear in output."""
        with (
            patch("subprocess.run") as mock_run,
            patch("cub.core.punchlist.processor.get_project_id", return_value="cub"),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Title\nCONTEXT: Context.\nSTEPS:\n1. Step\nCRITERIA:\n- [ ] Done",
            )

            result = process_punchlist(
                punchlist_file,
                labels=["sprint-12", "high-priority"],
            )

        content = result.output_file.read_text(encoding="utf-8")
        assert "sprint-12" in content
        assert "high-priority" in content

    def test_empty_file_raises_error(self, tmp_path: Path) -> None:
        """Test that empty file raises ValueError."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="No items found"):
            process_punchlist(empty_file, dry_run=True)

    def test_progress_callbacks(self, punchlist_file: Path) -> None:
        """Test progress callbacks are called for each item."""
        start_calls: list[tuple[int, int, str]] = []
        complete_calls: list[tuple[int, int, HydrationResult]] = []

        def on_start(index: int, total: int, text: str) -> None:
            start_calls.append((index, total, text))

        def on_complete(index: int, total: int, result: HydrationResult) -> None:
            complete_calls.append((index, total, result))

        with (
            patch("subprocess.run") as mock_run,
            patch("cub.core.punchlist.processor.get_project_id", return_value="cub"),
        ):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="TITLE: Title\nCONTEXT: Context.\nSTEPS:\n1. Step\nCRITERIA:\n- [ ] Done",
            )

            process_punchlist(
                punchlist_file,
                dry_run=True,
                on_start=on_start,
                on_complete=on_complete,
            )

        assert len(start_calls) == 2
        assert len(complete_calls) == 2
        assert start_calls[0][0] == 0  # First item index
        assert start_calls[0][1] == 2  # Total count
        assert complete_calls[1][0] == 1  # Second item index


class TestRoundTrip:
    """Test that generated plans can be parsed back."""

    def test_round_trip_with_plan_parser(self) -> None:
        """Test that generated markdown round-trips through parse_itemized_plan."""
        from cub.core.plan.parser import parse_itemized_plan_content

        results = [
            HydrationResult(
                title="Fix login bug",
                description="Login fails",
                context="The login form fails when passwords contain special characters.",
                implementation_steps=["Update regex", "Add escaping"],
                acceptance_criteria=["Login works with special chars", "Tests pass"],
                status=HydrationStatus.SUCCESS,
                source_text="fix login",
            ),
            HydrationResult(
                title="Add verbose flag",
                description="Add --verbose",
                context="Users need more output during cub run.",
                implementation_steps=["Add CLI flag"],
                acceptance_criteria=["--verbose shows extra output"],
                status=HydrationStatus.SUCCESS,
                source_text="add verbose",
            ),
        ]

        md = generate_itemized_plan(
            results=results,
            epic_title="Test Round Trip",
            source_path=Path("test.md"),
            project_id="cub",
        )

        # Parse it back
        parsed = parse_itemized_plan_content(md)

        assert len(parsed.epics) == 1
        assert parsed.epics[0].title == "Test Round Trip"
        assert len(parsed.tasks) == 2
        assert parsed.tasks[0].title == "Fix login bug"
        assert parsed.tasks[1].title == "Add verbose flag"

        # Check task details survived round-trip
        task1 = parsed.tasks[0]
        assert "login form fails" in task1.context
        assert len(task1.implementation_steps) == 2
        assert len(task1.acceptance_criteria) == 2


class TestPunchlistResultModel:
    """Test PunchlistResult dataclass."""

    def test_task_count_property(self) -> None:
        """Test task_count computed property."""
        items = [
            HydrationResult(title="T1", description="D1", context="C1", source_text="t1"),
            HydrationResult(title="T2", description="D2", context="C2", source_text="t2"),
            HydrationResult(title="T3", description="D3", context="C3", source_text="t3"),
        ]
        result = PunchlistResult(epic_title="Epic", items=items)

        assert result.task_count == 3

    def test_empty_items(self) -> None:
        """Test result with no items."""
        result = PunchlistResult(epic_title="Epic")

        assert result.task_count == 0
        assert result.items == []

    def test_source_file(self) -> None:
        """Test source_file attribute."""
        path = Path("/path/to/punchlist.md")
        result = PunchlistResult(epic_title="Epic", source_file=path)

        assert result.source_file == path

    def test_output_file(self) -> None:
        """Test output_file attribute."""
        path = Path("/path/to/plan.md")
        result = PunchlistResult(epic_title="Epic", output_file=path)

        assert result.output_file == path
