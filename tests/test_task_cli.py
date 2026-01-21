"""
Unit tests for the task CLI command.

Tests the unified task interface CLI commands.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli.task import app
from cub.core.tasks.models import Task, TaskCounts, TaskPriority, TaskStatus, TaskType

runner = CliRunner()


@pytest.fixture
def mock_backend() -> MagicMock:
    """Create a mock task backend."""
    backend = MagicMock()
    backend.backend_name = "test"
    return backend


class TestTaskCreate:
    """Test cub task create command."""

    def test_create_minimal(self, mock_backend: MagicMock) -> None:
        """Test creating a task with minimal arguments."""
        mock_backend.create_task.return_value = Task(
            id="cub-001",
            title="Test task",
            status=TaskStatus.OPEN,
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["create", "Test task"])

        assert result.exit_code == 0
        assert "cub-001" in result.stdout
        mock_backend.create_task.assert_called_once()

    def test_create_with_options(self, mock_backend: MagicMock) -> None:
        """Test creating a task with all options."""
        mock_backend.create_task.return_value = Task(
            id="cub-001",
            title="Bug fix",
            status=TaskStatus.OPEN,
            type=TaskType.BUG,
            priority=TaskPriority.P1,
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(
                app,
                [
                    "create",
                    "Bug fix",
                    "--type",
                    "bug",
                    "--priority",
                    "1",
                    "--parent",
                    "epic-001",
                    "--label",
                    "urgent",
                    "--description",
                    "Fix this bug",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_backend.create_task.call_args.kwargs
        assert call_kwargs["title"] == "Bug fix"
        assert call_kwargs["task_type"] == "bug"
        assert call_kwargs["priority"] == 1
        assert call_kwargs["parent"] == "epic-001"
        assert "urgent" in call_kwargs["labels"]

    def test_create_json_output(self, mock_backend: MagicMock) -> None:
        """Test JSON output format."""
        mock_backend.create_task.return_value = Task(
            id="cub-001",
            title="Test",
            status=TaskStatus.OPEN,
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["create", "Test", "--json"])

        assert result.exit_code == 0
        assert '"id": "cub-001"' in result.stdout


class TestTaskShow:
    """Test cub task show command."""

    def test_show_task(self, mock_backend: MagicMock) -> None:
        """Test showing task details."""
        mock_backend.get_task.return_value = Task(
            id="cub-001",
            title="Test task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P1,
            description="Task description",
            labels=["feature", "urgent"],
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["show", "cub-001"])

        assert result.exit_code == 0
        assert "cub-001" in result.stdout
        assert "Test task" in result.stdout
        assert "in_progress" in result.stdout
        assert "P1" in result.stdout

    def test_show_not_found(self, mock_backend: MagicMock) -> None:
        """Test showing non-existent task."""
        mock_backend.get_task.return_value = None

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["show", "cub-999"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestTaskList:
    """Test cub task list command."""

    def test_list_all(self, mock_backend: MagicMock) -> None:
        """Test listing all tasks."""
        mock_backend.list_tasks.return_value = [
            Task(id="cub-001", title="Task 1", status=TaskStatus.OPEN),
            Task(id="cub-002", title="Task 2", status=TaskStatus.CLOSED),
        ]

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "cub-001" in result.stdout
        assert "cub-002" in result.stdout
        mock_backend.list_tasks.assert_called_once_with(
            status=None, parent=None, label=None
        )

    def test_list_filtered_by_status(self, mock_backend: MagicMock) -> None:
        """Test filtering by status."""
        mock_backend.list_tasks.return_value = [
            Task(id="cub-001", title="Task 1", status=TaskStatus.OPEN),
        ]

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["list", "--status", "open"])

        assert result.exit_code == 0
        mock_backend.list_tasks.assert_called_once_with(
            status=TaskStatus.OPEN, parent=None, label=None
        )

    def test_list_filtered_by_parent(self, mock_backend: MagicMock) -> None:
        """Test filtering by parent."""
        mock_backend.list_tasks.return_value = []

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["list", "--parent", "epic-001"])

        assert result.exit_code == 0
        mock_backend.list_tasks.assert_called_once_with(
            status=None, parent="epic-001", label=None
        )

    def test_list_empty(self, mock_backend: MagicMock) -> None:
        """Test listing when no tasks match."""
        mock_backend.list_tasks.return_value = []

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No tasks found" in result.stdout

    def test_list_invalid_status(self, mock_backend: MagicMock) -> None:
        """Test invalid status value."""
        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["list", "--status", "invalid"])

        assert result.exit_code == 1
        assert "Invalid status" in result.stdout


class TestTaskUpdate:
    """Test cub task update command."""

    def test_update_status(self, mock_backend: MagicMock) -> None:
        """Test updating task status."""
        mock_backend.get_task.return_value = Task(
            id="cub-001",
            title="Test",
            status=TaskStatus.OPEN,
        )
        mock_backend.update_task.return_value = Task(
            id="cub-001",
            title="Test",
            status=TaskStatus.IN_PROGRESS,
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["update", "cub-001", "--status", "in_progress"])

        assert result.exit_code == 0
        assert "Updated" in result.stdout
        mock_backend.update_task.assert_called_once()

    def test_update_not_found(self, mock_backend: MagicMock) -> None:
        """Test updating non-existent task."""
        mock_backend.get_task.return_value = None

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["update", "cub-999", "--status", "closed"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestTaskClose:
    """Test cub task close command."""

    def test_close_task(self, mock_backend: MagicMock) -> None:
        """Test closing a task."""
        mock_backend.close_task.return_value = Task(
            id="cub-001",
            title="Test",
            status=TaskStatus.CLOSED,
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["close", "cub-001"])

        assert result.exit_code == 0
        assert "Closed" in result.stdout
        mock_backend.close_task.assert_called_once_with("cub-001", reason=None)

    def test_close_with_reason(self, mock_backend: MagicMock) -> None:
        """Test closing a task with reason."""
        mock_backend.close_task.return_value = Task(
            id="cub-001",
            title="Test",
            status=TaskStatus.CLOSED,
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(
                app, ["close", "cub-001", "--reason", "Completed in PR #123"]
            )

        assert result.exit_code == 0
        mock_backend.close_task.assert_called_once_with(
            "cub-001", reason="Completed in PR #123"
        )


class TestTaskReady:
    """Test cub task ready command."""

    def test_ready_tasks(self, mock_backend: MagicMock) -> None:
        """Test listing ready tasks."""
        mock_backend.get_ready_tasks.return_value = [
            Task(id="cub-001", title="Ready task 1", status=TaskStatus.OPEN),
            Task(id="cub-002", title="Ready task 2", status=TaskStatus.OPEN),
        ]

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["ready"])

        assert result.exit_code == 0
        assert "cub-001" in result.stdout
        assert "cub-002" in result.stdout
        assert "Ready Tasks" in result.stdout

    def test_no_ready_tasks(self, mock_backend: MagicMock) -> None:
        """Test when no tasks are ready."""
        mock_backend.get_ready_tasks.return_value = []

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["ready"])

        assert result.exit_code == 0
        assert "No tasks ready" in result.stdout


class TestTaskCounts:
    """Test cub task counts command."""

    def test_counts(self, mock_backend: MagicMock) -> None:
        """Test showing task statistics."""
        mock_backend.get_task_counts.return_value = TaskCounts(
            total=10,
            open=5,
            in_progress=2,
            closed=3,
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["counts"])

        assert result.exit_code == 0
        assert "Total:" in result.stdout
        assert "10" in result.stdout
        assert "Open:" in result.stdout
        assert "5" in result.stdout
        assert "30.0%" in result.stdout  # Completion percentage

    def test_counts_json(self, mock_backend: MagicMock) -> None:
        """Test JSON output for counts."""
        mock_backend.get_task_counts.return_value = TaskCounts(
            total=10,
            open=5,
            in_progress=2,
            closed=3,
        )

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["counts", "--json"])

        assert result.exit_code == 0
        assert '"total": 10' in result.stdout


class TestTaskDep:
    """Test cub task dep subcommands."""

    def test_dep_list(self, mock_backend: MagicMock) -> None:
        """Test listing task dependencies."""
        mock_backend.get_task.side_effect = [
            Task(
                id="cub-001",
                title="Main task",
                status=TaskStatus.OPEN,
                depends_on=["cub-002"],
                blocks=["cub-003"],
            ),
            Task(id="cub-002", title="Blocker", status=TaskStatus.CLOSED),
            Task(id="cub-003", title="Blocked", status=TaskStatus.OPEN),
        ]

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["dep", "list", "cub-001"])

        assert result.exit_code == 0
        assert "cub-002" in result.stdout
        assert "cub-003" in result.stdout

    def test_dep_list_not_found(self, mock_backend: MagicMock) -> None:
        """Test dep list for non-existent task."""
        mock_backend.get_task.return_value = None

        with patch("cub.cli.task.get_backend", return_value=mock_backend):
            result = runner.invoke(app, ["dep", "list", "cub-999"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()
