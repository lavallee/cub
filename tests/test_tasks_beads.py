"""
Unit tests for beads task backend.

Tests the BeadsBackend implementation including bd CLI subprocess calls,
JSON parsing, task transformation, and error handling.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cub.core.tasks.beads import BeadsBackend, BeadsCommandError, BeadsNotAvailableError
from cub.core.tasks.models import TaskPriority, TaskStatus, TaskType

# ==============================================================================
# Initialization Tests
# ==============================================================================


class TestBeadsBackendInit:
    """Test BeadsBackend initialization and availability checking."""

    def test_init_with_bd_available(self, project_dir):
        """Test successful initialization when bd CLI is available."""
        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            backend = BeadsBackend(project_dir=project_dir)
            assert backend.project_dir == project_dir

    def test_init_without_bd_available(self, project_dir):
        """Test initialization fails when bd CLI is not available."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(BeadsNotAvailableError) as exc_info:
                BeadsBackend(project_dir=project_dir)
            assert "not installed" in str(exc_info.value)

    def test_init_defaults_to_cwd(self):
        """Test that project_dir defaults to current working directory."""
        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            backend = BeadsBackend()
            assert backend.project_dir == Path.cwd()


# ==============================================================================
# BD Command Execution Tests
# ==============================================================================


class TestRunBd:
    """Test the _run_bd helper method for subprocess execution."""

    def test_run_bd_successful_json_list(self, project_dir):
        """Test running bd command that returns JSON list."""
        mock_result = Mock()
        mock_result.stdout = json.dumps([{"id": "cub-001", "title": "Task 1"}])
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result):
                backend = BeadsBackend(project_dir=project_dir)
                result = backend._run_bd(["list", "--json"])

                assert isinstance(result, list)
                assert len(result) == 1
                assert result[0]["id"] == "cub-001"

    def test_run_bd_successful_json_dict(self, project_dir):
        """Test running bd command that returns JSON dict."""
        mock_result = Mock()
        mock_result.stdout = json.dumps({"id": "cub-001", "title": "Task 1"})
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result):
                backend = BeadsBackend(project_dir=project_dir)
                result = backend._run_bd(["show", "cub-001", "--json"])

                assert isinstance(result, dict)
                assert result["id"] == "cub-001"

    def test_run_bd_empty_output(self, project_dir):
        """Test running bd command with empty output returns empty list."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result):
                backend = BeadsBackend(project_dir=project_dir)
                result = backend._run_bd(["list", "--json"])

                assert result == []

    def test_run_bd_invalid_json(self, project_dir):
        """Test that invalid JSON raises BeadsCommandError."""
        mock_result = Mock()
        mock_result.stdout = "{ invalid json }"
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result):
                backend = BeadsBackend(project_dir=project_dir)
                with pytest.raises(BeadsCommandError) as exc_info:
                    backend._run_bd(["list", "--json"])
                assert "Failed to parse" in str(exc_info.value)

    def test_run_bd_command_fails(self, project_dir):
        """Test that subprocess error raises BeadsCommandError."""
        error = subprocess.CalledProcessError(1, ["bd", "list"], stderr="Error message")

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=error):
                backend = BeadsBackend(project_dir=project_dir)
                with pytest.raises(BeadsCommandError) as exc_info:
                    backend._run_bd(["list", "--json"])
                assert "bd command failed" in str(exc_info.value)

    def test_run_bd_uses_correct_cwd(self, project_dir):
        """Test that bd commands run in the correct working directory."""
        mock_result = Mock()
        mock_result.stdout = "[]"
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                backend._run_bd(["list", "--json"])

                # Verify subprocess.run was called with correct cwd
                mock_run.assert_called_once()
                assert mock_run.call_args[1]["cwd"] == project_dir


# ==============================================================================
# Task Transformation Tests
# ==============================================================================


class TestTransformBeadsTask:
    """Test transformation of beads JSON to Task model."""

    def test_transform_minimal_task(self, project_dir):
        """Test transforming minimal beads task data."""
        raw_task = {"id": "cub-001", "title": "Minimal task"}

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            backend = BeadsBackend(project_dir=project_dir)
            task = backend._transform_beads_task(raw_task)

            assert task.id == "cub-001"
            assert task.title == "Minimal task"
            assert task.status == TaskStatus.OPEN  # default
            assert task.type == TaskType.TASK  # default
            assert task.priority == TaskPriority.P2  # default

    def test_transform_full_task(self, project_dir):
        """Test transforming full beads task with all fields."""
        raw_task = {
            "id": "cub-042",
            "title": "Full task",
            "description": "Detailed description",
            "status": "in_progress",
            "priority": 0,
            "issue_type": "feature",
            "assignee": "alice",
            "labels": ["backend", "model:sonnet"],
            "parent": "epic-001",
            "blocks": ["cub-041"],  # beads uses "blocks" for depends_on
            "acceptance_criteria": ["criterion 1", "criterion 2"],
            "notes": "Some notes",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        }

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            backend = BeadsBackend(project_dir=project_dir)
            task = backend._transform_beads_task(raw_task)

            assert task.id == "cub-042"
            assert task.title == "Full task"
            assert task.description == "Detailed description"
            assert task.status == TaskStatus.IN_PROGRESS
            assert task.priority == TaskPriority.P0
            assert task.type == TaskType.FEATURE
            assert task.assignee == "alice"
            assert "backend" in task.labels
            assert "model:sonnet" in task.labels
            assert task.parent == "epic-001"
            assert task.depends_on == ["cub-041"]
            assert len(task.acceptance_criteria) == 2
            assert task.notes == "Some notes"

    def test_transform_priority_mapping(self, project_dir):
        """Test that priority integers are correctly mapped to P0-P4."""
        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            backend = BeadsBackend(project_dir=project_dir)

            for priority_int in range(5):
                raw_task = {"id": f"cub-{priority_int}", "title": "Task", "priority": priority_int}
                task = backend._transform_beads_task(raw_task)
                assert task.priority == TaskPriority(f"P{priority_int}")


# ==============================================================================
# List Tasks Tests
# ==============================================================================


class TestListTasks:
    """Test listing tasks with various filters."""

    def test_list_all_tasks(self, project_dir):
        """Test listing all tasks without filters."""
        tasks_json = json.dumps(
            [
                {"id": "cub-001", "title": "Task 1", "status": "open"},
                {"id": "cub-002", "title": "Task 2", "status": "closed"},
            ]
        )

        mock_result = Mock()
        mock_result.stdout = tasks_json
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                tasks = backend.list_tasks()

                assert len(tasks) == 2
                assert tasks[0].id == "cub-001"
                assert tasks[1].id == "cub-002"

                # Verify correct bd command
                args = mock_run.call_args[0][0]
                assert args == ["bd", "list", "--json", "--limit", "1000"]

    def test_list_tasks_by_status(self, project_dir):
        """Test filtering tasks by status."""
        mock_result = Mock()
        mock_result.stdout = json.dumps([{"id": "cub-001", "title": "Open task", "status": "open"}])
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                tasks = backend.list_tasks(status=TaskStatus.OPEN)

                assert len(tasks) == 1
                assert tasks[0].status == TaskStatus.OPEN

                # Verify status filter in command
                args = mock_run.call_args[0][0]
                assert "--status" in args
                assert "open" in args

    def test_list_tasks_by_parent(self, project_dir):
        """Test filtering tasks by parent epic."""
        mock_result = Mock()
        mock_result.stdout = json.dumps(
            [{"id": "cub-001", "title": "Child task", "parent": "epic-001"}]
        )
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                backend.list_tasks(parent="epic-001")

                # Verify parent filter in command
                args = mock_run.call_args[0][0]
                assert "--parent" in args
                assert "epic-001" in args

    def test_list_tasks_by_label(self, project_dir):
        """Test filtering tasks by label."""
        mock_result = Mock()
        mock_result.stdout = json.dumps(
            [{"id": "cub-001", "title": "Task", "labels": ["backend", "urgent"]}]
        )
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                backend.list_tasks(label="backend")

                # Verify label filter in command
                args = mock_run.call_args[0][0]
                assert "--label" in args
                assert "backend" in args

    def test_list_tasks_empty_result(self, project_dir):
        """Test listing tasks when no tasks exist."""
        mock_result = Mock()
        mock_result.stdout = "[]"
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result):
                backend = BeadsBackend(project_dir=project_dir)
                tasks = backend.list_tasks()

                assert tasks == []


# ==============================================================================
# Get Task Tests
# ==============================================================================


class TestGetTask:
    """Test getting a single task by ID."""

    def test_get_task_success(self, project_dir):
        """Test successfully getting a task by ID."""
        task_json = json.dumps({"id": "cub-042", "title": "Test task", "status": "open"})

        mock_result = Mock()
        mock_result.stdout = task_json
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.get_task("cub-042")

                assert task is not None
                assert task.id == "cub-042"
                assert task.title == "Test task"

                # Verify correct command
                args = mock_run.call_args[0][0]
                assert args == ["bd", "show", "cub-042", "--json"]

    def test_get_task_not_found(self, project_dir):
        """Test getting a non-existent task returns None."""
        error = subprocess.CalledProcessError(1, ["bd", "show"], stderr="Task not found")

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=error):
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.get_task("nonexistent")

                assert task is None

    def test_get_task_list_response(self, project_dir):
        """Test get_task when bd returns a list with one item."""
        task_json = json.dumps([{"id": "cub-001", "title": "Task", "status": "open"}])

        mock_result = Mock()
        mock_result.stdout = task_json
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result):
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.get_task("cub-001")

                assert task is not None
                assert task.id == "cub-001"


# ==============================================================================
# Get Ready Tasks Tests
# ==============================================================================


class TestGetReadyTasks:
    """Test getting tasks that are ready to work on."""

    def test_get_ready_tasks(self, project_dir):
        """Test getting ready tasks sorted by priority."""
        tasks_json = json.dumps(
            [
                {"id": "cub-002", "title": "Task 2", "status": "open", "priority": 2},
                {"id": "cub-001", "title": "Task 1", "status": "open", "priority": 0},
                {"id": "cub-003", "title": "Task 3", "status": "open", "priority": 1},
            ]
        )

        mock_result = Mock()
        mock_result.stdout = tasks_json
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                tasks = backend.get_ready_tasks()

                # Should be sorted by priority (P0 first)
                assert len(tasks) == 3
                assert tasks[0].id == "cub-001"  # P0
                assert tasks[1].id == "cub-003"  # P1
                assert tasks[2].id == "cub-002"  # P2

                # Verify correct command
                args = mock_run.call_args[0][0]
                assert args == ["bd", "ready", "--json", "--limit", "1000"]

    def test_get_ready_tasks_with_filters(self, project_dir):
        """Test getting ready tasks with parent and label filters.

        Epic association strategy (see .cub/EPIC_TASK_ASSOCIATION.md):
        - The parent field is the canonical source for epic-task relationships
        - The epic:{parent} label is a compatibility layer
        - We filter by parent in Python (not via beads CLI) to support both
        """
        # Return tasks with both parent and epic: label scenarios
        mock_result = Mock()
        mock_result.stdout = json.dumps([
            # Task with parent field matching
            {"id": "task-1", "title": "Task 1", "parent": "epic-001", "labels": ["backend"]},
            # Task with epic: label matching (fallback)
            {"id": "task-2", "title": "Task 2", "parent": None, "labels": ["backend", "epic:epic-001"]},
            # Task with neither (should be filtered out)
            {"id": "task-3", "title": "Task 3", "parent": "epic-002", "labels": ["backend"]},
        ])
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                tasks = backend.get_ready_tasks(parent="epic-001", label="backend")

                args = mock_run.call_args[0][0]
                # Label filter is passed to beads CLI
                assert "--label" in args
                assert "backend" in args
                # Parent filter is done in Python, NOT passed to beads
                assert "epic:epic-001" not in args

                # Verify Python-side filtering works
                assert len(tasks) == 2
                task_ids = {t.id for t in tasks}
                assert "task-1" in task_ids  # parent field match
                assert "task-2" in task_ids  # epic: label match
                assert "task-3" not in task_ids  # different parent

    def test_get_ready_tasks_command_error(self, project_dir):
        """Test that command error returns empty list."""
        error = subprocess.CalledProcessError(1, ["bd", "ready"], stderr="Error")

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=error):
                backend = BeadsBackend(project_dir=project_dir)
                tasks = backend.get_ready_tasks()

                assert tasks == []


# ==============================================================================
# Update Task Tests
# ==============================================================================


class TestUpdateTask:
    """Test updating task fields."""

    def test_update_task_status(self, project_dir):
        """Test updating task status."""
        # Mock both update and get_task calls
        update_result = Mock()
        update_result.stdout = ""
        update_result.returncode = 0

        get_result = Mock()
        get_result.stdout = json.dumps({"id": "cub-001", "title": "Task", "status": "in_progress"})
        get_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=[update_result, get_result]) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.update_task("cub-001", status=TaskStatus.IN_PROGRESS)

                assert task.status == TaskStatus.IN_PROGRESS

                # Verify update command
                update_args = mock_run.call_args_list[0][0][0]
                assert "update" in update_args
                assert "cub-001" in update_args
                assert "--status" in update_args
                assert "in_progress" in update_args

    def test_update_task_multiple_fields(self, project_dir):
        """Test updating multiple fields at once."""
        update_result = Mock()
        update_result.stdout = ""
        update_result.returncode = 0

        get_result = Mock()
        get_result.stdout = json.dumps(
            {
                "id": "cub-001",
                "title": "Task",
                "status": "in_progress",
                "assignee": "alice",
                "labels": ["backend", "urgent"],
            }
        )
        get_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=[update_result, get_result]) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.update_task(
                    "cub-001",
                    status=TaskStatus.IN_PROGRESS,
                    assignee="alice",
                    labels=["backend", "urgent"],
                )

                assert task.assignee == "alice"

                # Verify all fields in command
                update_args = mock_run.call_args_list[0][0][0]
                assert "--status" in update_args
                assert "--assignee" in update_args
                assert "--labels" in update_args

    def test_update_task_not_found(self, project_dir):
        """Test updating non-existent task raises ValueError."""
        error = subprocess.CalledProcessError(1, ["bd", "update"], stderr="Not found")

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=error):
                backend = BeadsBackend(project_dir=project_dir)
                with pytest.raises(ValueError) as exc_info:
                    backend.update_task("cub-999", status=TaskStatus.CLOSED)
                assert "Failed to update" in str(exc_info.value)


# ==============================================================================
# Task Counts Tests
# ==============================================================================


class TestGetTaskCounts:
    """Test getting task statistics."""

    def test_get_task_counts(self, project_dir):
        """Test getting correct task counts."""
        tasks_json = json.dumps(
            [
                {"id": "cub-001", "status": "open"},
                {"id": "cub-002", "status": "open"},
                {"id": "cub-003", "status": "in_progress"},
                {"id": "cub-004", "status": "closed"},
                {"id": "cub-005", "status": "closed"},
            ]
        )

        mock_result = Mock()
        mock_result.stdout = tasks_json
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=mock_result):
                backend = BeadsBackend(project_dir=project_dir)
                counts = backend.get_task_counts()

                assert counts.total == 5
                assert counts.open == 2
                assert counts.in_progress == 1
                assert counts.closed == 2
                assert counts.remaining == 3  # open + in_progress
                assert counts.completion_percentage == 40.0  # 2/5 closed

    def test_get_task_counts_error(self, project_dir):
        """Test that command error returns zero counts."""
        error = subprocess.CalledProcessError(1, ["bd", "list"], stderr="Error")

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=error):
                backend = BeadsBackend(project_dir=project_dir)
                counts = backend.get_task_counts()

                assert counts.total == 0
                assert counts.open == 0


# ==============================================================================
# Try Close Epic Tests
# ==============================================================================


class TestTryCloseEpic:
    """Test auto-closing epics when all tasks complete."""

    def test_close_epic_all_tasks_closed(self, project_dir):
        """Test that epic is closed when all its tasks are closed."""
        # Epic data for get_task
        epic_data = {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"}
        epic_json = json.dumps(epic_data)

        # Tasks for list_tasks by parent
        parent_tasks_json = json.dumps(
            [
                {"id": "task-001", "title": "Task 1", "parent": "epic-001", "status": "closed"},
                {"id": "task-002", "title": "Task 2", "parent": "epic-001", "status": "closed"},
            ]
        )

        # Tasks for list_tasks by label (empty in this case)
        label_tasks_json = json.dumps([])

        # Closed epic for verification
        closed_epic_json = json.dumps(
            {"id": "epic-001", "title": "Epic", "type": "epic", "status": "closed"}
        )

        mock_results = [
            Mock(stdout=epic_json, returncode=0),  # get_task for epic
            Mock(stdout=parent_tasks_json, returncode=0),  # list_tasks by parent
            Mock(stdout=label_tasks_json, returncode=0),  # list_tasks by label
            Mock(stdout="", returncode=0),  # close_task
            Mock(stdout=closed_epic_json, returncode=0),  # get_task after close
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results):
                backend = BeadsBackend(project_dir=project_dir)
                closed, message = backend.try_close_epic("epic-001")

                assert closed is True
                assert "auto-closed" in message
                assert "2 tasks completed" in message

    def test_epic_stays_open_with_open_tasks(self, project_dir):
        """Test that epic stays open when some tasks are still open."""
        epic_data = {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"}
        epic_json = json.dumps(epic_data)
        tasks_json = json.dumps(
            [
                {"id": "task-001", "title": "Task 1", "parent": "epic-001", "status": "closed"},
                {"id": "task-002", "title": "Task 2", "parent": "epic-001", "status": "open"},
            ]
        )
        empty_tasks_json = json.dumps([])

        mock_results = [
            Mock(stdout=epic_json, returncode=0),  # get_task for epic
            Mock(stdout=tasks_json, returncode=0),  # list_tasks by parent
            Mock(stdout=empty_tasks_json, returncode=0),  # list_tasks by label
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results):
                backend = BeadsBackend(project_dir=project_dir)
                closed, message = backend.try_close_epic("epic-001")

                assert closed is False
                assert "1 open" in message

    def test_epic_stays_open_with_in_progress_tasks(self, project_dir):
        """Test that epic stays open when some tasks are in progress."""
        epic_data = {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"}
        epic_json = json.dumps(epic_data)
        tasks_json = json.dumps(
            [
                {"id": "task-001", "title": "Task 1", "parent": "epic-001", "status": "closed"},
                {
                    "id": "task-002",
                    "title": "Task 2",
                    "parent": "epic-001",
                    "status": "in_progress",
                },
            ]
        )
        empty_tasks_json = json.dumps([])

        mock_results = [
            Mock(stdout=epic_json, returncode=0),  # get_task for epic
            Mock(stdout=tasks_json, returncode=0),  # list_tasks by parent
            Mock(stdout=empty_tasks_json, returncode=0),  # list_tasks by label
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results):
                backend = BeadsBackend(project_dir=project_dir)
                closed, message = backend.try_close_epic("epic-001")

                assert closed is False
                assert "1 in-progress" in message

    def test_epic_not_found(self, project_dir):
        """Test handling of non-existent epic."""
        error = subprocess.CalledProcessError(1, ["bd", "show"], stderr="Not found")

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=error):
                backend = BeadsBackend(project_dir=project_dir)
                closed, message = backend.try_close_epic("nonexistent")

                assert closed is False
                assert "not found" in message

    def test_epic_already_closed(self, project_dir):
        """Test handling of already closed epic."""
        epic_json = json.dumps(
            {"id": "epic-001", "title": "Epic", "type": "epic", "status": "closed"}
        )

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=Mock(stdout=epic_json, returncode=0)):
                backend = BeadsBackend(project_dir=project_dir)
                closed, message = backend.try_close_epic("epic-001")

                assert closed is False
                assert "already closed" in message

    def test_epic_no_tasks(self, project_dir):
        """Test handling of epic with no tasks."""
        epic_data = {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"}
        epic_json = json.dumps(epic_data)
        empty_tasks_json = json.dumps([])

        mock_results = [
            Mock(stdout=epic_json, returncode=0),  # get_task for epic
            Mock(stdout=empty_tasks_json, returncode=0),  # list_tasks by parent
            Mock(stdout=empty_tasks_json, returncode=0),  # list_tasks by label
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results):
                backend = BeadsBackend(project_dir=project_dir)
                closed, message = backend.try_close_epic("epic-001")

                assert closed is False
                assert "No tasks found" in message

    def test_close_epic_with_tasks_by_label(self, project_dir):
        """Test that tasks with epic ID as label are included."""
        epic_data = {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"}
        epic_json = json.dumps(epic_data)
        empty_parent_tasks = json.dumps([])
        label_tasks_json = json.dumps(
            [
                {"id": "task-001", "title": "Task 1", "labels": ["epic-001"], "status": "closed"},
                {
                    "id": "task-002",
                    "title": "Task 2",
                    "labels": ["epic-001", "urgent"],
                    "status": "closed",
                },
            ]
        )
        closed_epic_json = json.dumps(
            {"id": "epic-001", "title": "Epic", "type": "epic", "status": "closed"}
        )

        mock_results = [
            Mock(stdout=epic_json, returncode=0),  # get_task for epic
            Mock(stdout=empty_parent_tasks, returncode=0),  # list_tasks by parent
            Mock(stdout=label_tasks_json, returncode=0),  # list_tasks by label
            Mock(stdout="", returncode=0),  # close_task
            Mock(stdout=closed_epic_json, returncode=0),  # get_task after close
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results):
                backend = BeadsBackend(project_dir=project_dir)
                closed, message = backend.try_close_epic("epic-001")

                assert closed is True
                assert "auto-closed" in message
