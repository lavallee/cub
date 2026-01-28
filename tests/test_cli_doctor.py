"""
Tests for the doctor CLI command.

Tests the `cub doctor` command for diagnostics and auto-fixing issues.
"""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli import app
from cub.core.tasks.models import Task, TaskStatus, TaskType

runner = CliRunner()


@pytest.fixture
def mock_project_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    """Set up a mock project directory."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # Mock get_project_root to return our temp directory
    with patch("cub.cli.doctor.get_project_root", return_value=project_dir):
        yield project_dir


class TestDoctorCommand:
    """Test the doctor command functionality."""

    def test_doctor_basic_run(self, mock_project_dir: Path) -> None:
        """Test basic doctor run without issues."""
        # Mock backend with no tasks
        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = []

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 0
            assert "Cub Doctor" in result.output
            assert "No issues found" in result.output

    def test_doctor_detects_stale_epic(self, mock_project_dir: Path) -> None:
        """Test that doctor detects stale epics (all subtasks complete)."""
        # Create an epic with all subtasks closed
        epic = Task(
            id="epic-001",
            title="Test Epic",
            type=TaskType.EPIC,
            status=TaskStatus.OPEN,
        )
        subtask1 = Task(
            id="epic-001.1",
            title="Subtask 1",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
            parent="epic-001",
        )
        subtask2 = Task(
            id="epic-001.2",
            title="Subtask 2",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
            parent="epic-001",
        )

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = [epic, subtask1, subtask2]

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor"])

            # Should detect the stale epic but not fix it without --fix flag
            assert result.exit_code == 1  # Exit with error when issues found
            assert "1 stale epic" in result.output
            assert "epic-001" in result.output
            assert "--fix" in result.output

    def test_doctor_ignores_epic_with_open_subtasks(self, mock_project_dir: Path) -> None:
        """Test that doctor ignores epics with open subtasks."""
        # Create an epic with mixed subtask statuses
        epic = Task(
            id="epic-002",
            title="Active Epic",
            type=TaskType.EPIC,
            status=TaskStatus.OPEN,
        )
        subtask1 = Task(
            id="epic-002.1",
            title="Closed Subtask",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
            parent="epic-002",
        )
        subtask2 = Task(
            id="epic-002.2",
            title="Open Subtask",
            type=TaskType.TASK,
            status=TaskStatus.OPEN,
            parent="epic-002",
        )

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = [epic, subtask1, subtask2]

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 0
            assert "No stale epics found" in result.output

    def test_doctor_fix_closes_stale_epic(self, mock_project_dir: Path) -> None:
        """Test that doctor --fix closes stale epics."""
        # Create a stale epic
        epic = Task(
            id="epic-003",
            title="Stale Epic",
            type=TaskType.EPIC,
            status=TaskStatus.OPEN,
        )
        subtask1 = Task(
            id="epic-003.1",
            title="Subtask 1",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
            parent="epic-003",
        )

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = [epic, subtask1]
        mock_backend.close_task.return_value = Task(
            id="epic-003", title="Stale Epic", type=TaskType.EPIC, status=TaskStatus.CLOSED
        )

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor", "--fix"])

            assert result.exit_code == 0
            assert "Auto-closing stale epics" in result.output
            assert "Closed: epic-003" in result.output

            # Verify close_task was called with correct arguments
            mock_backend.close_task.assert_called_once_with(
                "epic-003", reason="Auto-closed: all subtasks complete"
            )

    def test_doctor_handles_multiple_stale_epics(self, mock_project_dir: Path) -> None:
        """Test that doctor can handle multiple stale epics."""
        # Create multiple stale epics
        epic1 = Task(id="epic-101", title="Epic 1", type=TaskType.EPIC, status=TaskStatus.OPEN)
        epic2 = Task(id="epic-102", title="Epic 2", type=TaskType.EPIC, status=TaskStatus.OPEN)
        subtask1 = Task(
            id="epic-101.1",
            title="Subtask 1",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
            parent="epic-101",
        )
        subtask2 = Task(
            id="epic-102.1",
            title="Subtask 2",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
            parent="epic-102",
        )

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = [epic1, epic2, subtask1, subtask2]

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 1
            assert "2 stale epic" in result.output
            assert "epic-101" in result.output
            assert "epic-102" in result.output

    def test_doctor_fix_handles_close_failure(self, mock_project_dir: Path) -> None:
        """Test that doctor --fix handles failures gracefully."""
        epic = Task(id="epic-999", title="Broken Epic", type=TaskType.EPIC, status=TaskStatus.OPEN)
        subtask = Task(
            id="epic-999.1",
            title="Subtask",
            type=TaskType.TASK,
            status=TaskStatus.CLOSED,
            parent="epic-999",
        )

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = [epic, subtask]
        mock_backend.close_task.side_effect = Exception("Permission denied")

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor", "--fix"])

            assert "Failed to close epic-999" in result.output
            assert "Permission denied" in result.output

    def test_doctor_ignores_epics_without_subtasks(self, mock_project_dir: Path) -> None:
        """Test that doctor ignores epics with no subtasks (parent containers)."""
        epic = Task(
            id="epic-empty", title="Empty Epic", type=TaskType.EPIC, status=TaskStatus.OPEN
        )

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = [epic]

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 0
            assert "No stale epics found" in result.output

    def test_doctor_finds_subtasks_by_prefix(self, mock_project_dir: Path) -> None:
        """Test that doctor finds subtasks using ID prefix matching."""
        # Epic with subtasks using prefix convention (epic-id.1, epic-id.2)
        epic = Task(id="cub-abc", title="Epic", type=TaskType.EPIC, status=TaskStatus.OPEN)
        # Subtask without explicit parent field, but with prefix
        subtask1 = Task(
            id="cub-abc.1", title="Subtask 1", type=TaskType.TASK, status=TaskStatus.CLOSED
        )
        subtask2 = Task(
            id="cub-abc.2", title="Subtask 2", type=TaskType.TASK, status=TaskStatus.CLOSED
        )

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = [epic, subtask1, subtask2]

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor"])

            # Should detect stale epic based on prefix matching
            assert result.exit_code == 1
            assert "1 stale epic" in result.output
            assert "cub-abc" in result.output

    def test_doctor_backend_not_available(self, mock_project_dir: Path) -> None:
        """Test that doctor handles backend loading errors gracefully."""
        with (
            patch("cub.cli.doctor.get_backend", side_effect=Exception("Backend not found")),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor"])

            # Should complete but warn about backend issue
            assert "Warning: Could not load task backend" in result.output
            # Should still check other things and exit successfully if no other issues
            assert result.exit_code == 0

    def test_doctor_verbose_flag(self, mock_project_dir: Path) -> None:
        """Test that --verbose flag is accepted (even if not fully implemented)."""
        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = []

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor", "--verbose"])

            assert result.exit_code == 0
            assert "Cub Doctor" in result.output


class TestDoctorHooksCheck:
    """Test the hooks checking functionality in doctor command."""

    def test_doctor_checks_hooks_not_installed(self, mock_project_dir: Path) -> None:
        """Test that doctor detects when hooks are not installed."""
        # No .claude directory exists
        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = []

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 0
            assert "Claude Code Hooks" in result.output
            assert ".claude/ directory not found" in result.output
            assert "cub init --hooks" in result.output

    def test_doctor_checks_hooks_installed_correctly(self, mock_project_dir: Path) -> None:
        """Test that doctor confirms when hooks are properly configured."""
        # Create .claude directory
        (mock_project_dir / ".claude").mkdir()

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = []

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
            patch("cub.cli.doctor.validate_hooks", return_value=[]),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 0
            assert "Hooks are properly configured" in result.output

    def test_doctor_reports_hook_errors(self, mock_project_dir: Path) -> None:
        """Test that doctor reports hook configuration errors."""
        from cub.core.hooks.installer import HookIssue

        # Create .claude directory
        (mock_project_dir / ".claude").mkdir()

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = []

        issues = [
            HookIssue(
                severity="error",
                message="Hook script not found",
                file_path=str(mock_project_dir / ".cub" / "scripts" / "hooks" / "cub-hook.sh"),
            ),
            HookIssue(
                severity="warning",
                message="Hook PostToolUse not configured",
                hook_name="PostToolUse",
            ),
        ]

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
            patch("cub.cli.doctor.validate_hooks", return_value=issues),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 1  # Exit with error code
            assert "Hook script not found" in result.output
            assert "Hook PostToolUse not configured" in result.output
            assert "cub init --hooks --force" in result.output

    def test_doctor_reports_hook_warnings(self, mock_project_dir: Path) -> None:
        """Test that doctor reports hook configuration warnings."""
        from cub.core.hooks.installer import HookIssue

        # Create .claude directory
        (mock_project_dir / ".claude").mkdir()

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = []

        issues = [
            HookIssue(
                severity="warning",
                message="Hook script not executable",
                file_path=str(mock_project_dir / ".cub" / "scripts" / "hooks" / "cub-hook.sh"),
            )
        ]

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
            patch("cub.cli.doctor.validate_hooks", return_value=issues),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 1  # Exit with error code due to warning
            assert "Hook script not executable" in result.output

    def test_doctor_ignores_info_messages(self, mock_project_dir: Path) -> None:
        """Test that doctor shows info messages only in summary."""
        from cub.core.hooks.installer import HookIssue

        # Create .claude directory
        (mock_project_dir / ".claude").mkdir()

        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = []

        issues = [
            HookIssue(
                severity="info",
                message="Hook SessionEnd not configured",
                hook_name="SessionEnd",
            )
        ]

        with (
            patch("cub.cli.doctor.get_backend", return_value=mock_backend),
            patch("cub.cli.doctor.check_environment", return_value=0),
            patch("cub.cli.doctor.validate_hooks", return_value=issues),
        ):
            result = runner.invoke(app, ["doctor"])

            assert result.exit_code == 0  # Info messages don't cause failure
            assert "1 info message" in result.output
