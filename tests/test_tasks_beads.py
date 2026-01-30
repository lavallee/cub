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
            {
                "id": "task-2",
                "title": "Task 2",
                "parent": None,
                "labels": ["backend", "epic:epic-001"],
            },
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
# Dependency Management Tests
# ==============================================================================


class TestDependencyManagement:
    """Test adding and removing task dependencies."""

    def test_add_dependency_success(self, project_dir):
        """Test adding a dependency between two tasks."""
        # Mock get_task calls for both tasks
        task1_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "open"})
        task2_json = json.dumps({"id": "task-2", "title": "Task 2", "status": "open"})
        updated_task1_json = json.dumps(
            {"id": "task-1", "title": "Task 1", "status": "open", "blocks": ["task-2"]}
        )

        mock_results = [
            Mock(stdout=task1_json, returncode=0),  # get_task for task-1
            Mock(stdout=task2_json, returncode=0),  # get_task for task-2
            Mock(stdout="", returncode=0),  # dep add command
            Mock(stdout=updated_task1_json, returncode=0),  # get_task after update
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.add_dependency("task-1", "task-2")

                assert task.id == "task-1"
                assert "task-2" in task.depends_on

                # Verify dep add command was called
                dep_add_args = mock_run.call_args_list[2][0][0]
                assert dep_add_args == ["bd", "dep", "add", "task-1", "task-2", "--type", "blocks"]

    def test_add_dependency_task_not_found(self, project_dir):
        """Test adding dependency when task doesn't exist."""
        error = subprocess.CalledProcessError(1, ["bd", "show"], stderr="Not found")

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=error):
                backend = BeadsBackend(project_dir=project_dir)
                with pytest.raises(ValueError) as exc_info:
                    backend.add_dependency("task-1", "task-2")
                assert "not found" in str(exc_info.value).lower()

    def test_remove_dependency_success(self, project_dir):
        """Test removing a dependency from a task."""
        task_json = json.dumps(
            {"id": "task-1", "title": "Task 1", "status": "open", "blocks": ["task-2"]}
        )
        updated_task_json = json.dumps(
            {"id": "task-1", "title": "Task 1", "status": "open", "blocks": []}
        )

        mock_results = [
            Mock(stdout=task_json, returncode=0),  # get_task
            Mock(stdout="", returncode=0),  # dep remove command
            Mock(stdout=updated_task_json, returncode=0),  # get_task after update
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.remove_dependency("task-1", "task-2")

                assert task.id == "task-1"
                assert "task-2" not in task.depends_on

                # Verify dep remove command was called
                dep_remove_args = mock_run.call_args_list[1][0][0]
                assert dep_remove_args == ["bd", "dep", "remove", "task-1", "task-2"]

    def test_remove_dependency_not_exists(self, project_dir):
        """Test removing dependency that doesn't exist."""
        task_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "open", "blocks": []})

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=Mock(stdout=task_json, returncode=0)):
                backend = BeadsBackend(project_dir=project_dir)
                with pytest.raises(ValueError) as exc_info:
                    backend.remove_dependency("task-1", "task-2")
                assert "does not depend on" in str(exc_info.value)


# ==============================================================================
# Blocked Tasks Tests
# ==============================================================================


class TestListBlockedTasks:
    """Test listing blocked tasks."""

    def test_list_blocked_tasks_using_bd_command(self, project_dir):
        """Test listing blocked tasks using bd blocked command."""
        blocked_tasks_json = json.dumps(
            [
                {"id": "task-1", "title": "Task 1", "status": "open", "blocks": ["task-0"]},
                {"id": "task-2", "title": "Task 2", "status": "open", "blocks": ["task-0"]},
            ]
        )

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch(
                "subprocess.run", return_value=Mock(stdout=blocked_tasks_json, returncode=0)
            ) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                tasks = backend.list_blocked_tasks()

                assert len(tasks) == 2
                assert tasks[0].id == "task-1"
                assert tasks[1].id == "task-2"

                # Verify blocked command was called
                args = mock_run.call_args[0][0]
                assert args == ["bd", "blocked", "--json"]

    def test_list_blocked_tasks_fallback(self, project_dir):
        """Test falling back to manual filtering when bd blocked fails."""
        # First call fails (bd blocked doesn't exist)
        # Second call returns open tasks
        # Third, fourth calls get dependency tasks
        error = subprocess.CalledProcessError(1, ["bd", "blocked"], stderr="Command not found")
        open_tasks_json = json.dumps(
            [
                {"id": "task-1", "title": "Task 1", "status": "open", "blocks": ["task-0"]},
                {"id": "task-2", "title": "Task 2", "status": "open", "blocks": []},
            ]
        )
        dep_task_json = json.dumps({"id": "task-0", "title": "Dependency", "status": "open"})

        mock_results = [
            error,  # bd blocked fails
            Mock(stdout=open_tasks_json, returncode=0),  # list_tasks
            Mock(stdout=dep_task_json, returncode=0),  # get_task for dependency
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results):
                backend = BeadsBackend(project_dir=project_dir)
                tasks = backend.list_blocked_tasks()

                # Only task-1 should be blocked (has open dependency)
                assert len(tasks) == 1
                assert tasks[0].id == "task-1"


# ==============================================================================
# Reopen Task Tests
# ==============================================================================


class TestReopenTask:
    """Test reopening closed tasks."""

    def test_reopen_task_success(self, project_dir):
        """Test successfully reopening a closed task."""
        closed_task_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "closed"})
        reopened_task_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "open"})

        mock_results = [
            Mock(stdout=closed_task_json, returncode=0),  # get_task
            Mock(stdout="", returncode=0),  # update command
            Mock(stdout=reopened_task_json, returncode=0),  # get_task after update
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.reopen_task("task-1")

                assert task.status == TaskStatus.OPEN

                # Verify update command was called
                update_args = mock_run.call_args_list[1][0][0]
                assert update_args == ["bd", "update", "task-1", "--status", "open"]

    def test_reopen_task_with_reason(self, project_dir):
        """Test reopening a task with a reason."""
        closed_task_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "closed"})
        reopened_task_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "open"})

        mock_results = [
            Mock(stdout=closed_task_json, returncode=0),  # get_task (initial check)
            Mock(stdout="", returncode=0),  # update command
            Mock(stdout="", returncode=0),  # comment command
            # get_task (after comment in add_task_note)
            Mock(stdout=reopened_task_json, returncode=0),
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.reopen_task("task-1", reason="Found a bug")

                assert task.status == TaskStatus.OPEN

                # Verify comment command was called
                comment_args = mock_run.call_args_list[2][0][0]
                assert comment_args == ["bd", "comment", "task-1", "Reopened: Found a bug"]

    def test_reopen_task_not_closed(self, project_dir):
        """Test error when trying to reopen a task that's not closed."""
        open_task_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "open"})

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=Mock(stdout=open_task_json, returncode=0)):
                backend = BeadsBackend(project_dir=project_dir)
                with pytest.raises(ValueError) as exc_info:
                    backend.reopen_task("task-1")
                assert "not closed" in str(exc_info.value)


# ==============================================================================
# Delete Task Tests
# ==============================================================================


class TestDeleteTask:
    """Test deleting tasks."""

    def test_delete_task_success(self, project_dir):
        """Test successfully deleting a task."""
        task_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "open"})
        all_tasks_json = json.dumps(
            [
                {"id": "task-1", "title": "Task 1", "status": "open", "blocks": []},
                {"id": "task-2", "title": "Task 2", "status": "open", "blocks": []},
            ]
        )

        mock_results = [
            Mock(stdout=task_json, returncode=0),  # get_task
            Mock(stdout=all_tasks_json, returncode=0),  # list_tasks to check dependents
            Mock(stdout="", returncode=0),  # delete command
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                result = backend.delete_task("task-1")

                assert result is True

                # Verify delete command was called
                delete_args = mock_run.call_args_list[2][0][0]
                assert delete_args == ["bd", "delete", "task-1"]

    def test_delete_task_not_found(self, project_dir):
        """Test deleting a non-existent task."""
        error = subprocess.CalledProcessError(1, ["bd", "show"], stderr="Not found")

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=error):
                backend = BeadsBackend(project_dir=project_dir)
                result = backend.delete_task("nonexistent")

                assert result is False

    def test_delete_task_with_dependents(self, project_dir):
        """Test error when deleting a task that has dependents."""
        task_json = json.dumps({"id": "task-1", "title": "Task 1", "status": "open"})
        all_tasks_json = json.dumps(
            [
                {"id": "task-1", "title": "Task 1", "status": "open", "blocks": []},
                {"id": "task-2", "title": "Task 2", "status": "open", "blocks": ["task-1"]},
            ]
        )

        mock_results = [
            Mock(stdout=task_json, returncode=0),  # get_task
            Mock(stdout=all_tasks_json, returncode=0),  # list_tasks to check dependents
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results):
                backend = BeadsBackend(project_dir=project_dir)
                with pytest.raises(ValueError) as exc_info:
                    backend.delete_task("task-1")
                assert "has dependents" in str(exc_info.value)
                assert "task-2" in str(exc_info.value)


# ==============================================================================
# Label Management Tests
# ==============================================================================


class TestLabelManagement:
    """Test adding and removing labels."""

    def test_add_label_success(self, project_dir):
        """Test adding a label to a task."""
        task_json = json.dumps({"id": "task-1", "title": "Task 1", "labels": []})
        updated_task_json = json.dumps({"id": "task-1", "title": "Task 1", "labels": ["bug"]})

        mock_results = [
            Mock(stdout=task_json, returncode=0),  # get_task
            Mock(stdout="", returncode=0),  # label add command
            Mock(stdout=updated_task_json, returncode=0),  # get_task after update
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.add_label("task-1", "bug")

                assert "bug" in task.labels

                # Verify label add command was called
                label_add_args = mock_run.call_args_list[1][0][0]
                assert label_add_args == ["bd", "label", "add", "task-1", "bug"]

    def test_add_label_already_exists(self, project_dir):
        """Test adding a label that already exists."""
        task_json = json.dumps({"id": "task-1", "title": "Task 1", "labels": ["bug"]})

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=Mock(stdout=task_json, returncode=0)):
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.add_label("task-1", "bug")

                # Should return task without calling bd label add
                assert "bug" in task.labels

    def test_remove_label_success(self, project_dir):
        """Test removing a label from a task."""
        task_json = json.dumps({"id": "task-1", "title": "Task 1", "labels": ["bug", "urgent"]})
        updated_task_json = json.dumps({"id": "task-1", "title": "Task 1", "labels": ["urgent"]})

        mock_results = [
            Mock(stdout=task_json, returncode=0),  # get_task
            Mock(stdout="", returncode=0),  # label remove command
            Mock(stdout=updated_task_json, returncode=0),  # get_task after update
        ]

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=mock_results) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.remove_label("task-1", "bug")

                assert "bug" not in task.labels
                assert "urgent" in task.labels

                # Verify label remove command was called
                label_remove_args = mock_run.call_args_list[1][0][0]
                assert label_remove_args == ["bd", "label", "remove", "task-1", "bug"]

    def test_remove_label_not_exists(self, project_dir):
        """Test error when removing label that doesn't exist."""
        task_json = json.dumps({"id": "task-1", "title": "Task 1", "labels": []})

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=Mock(stdout=task_json, returncode=0)):
                backend = BeadsBackend(project_dir=project_dir)
                with pytest.raises(ValueError) as exc_info:
                    backend.remove_label("task-1", "bug")
                assert "not found" in str(exc_info.value)


# ==============================================================================
# Update Task Extended Tests
# ==============================================================================


class TestUpdateTaskExtended:
    """Test extended update_task functionality."""

    def test_update_task_with_title(self, project_dir):
        """Test updating task title."""
        update_result = Mock(stdout="", returncode=0)
        get_result = Mock(
            stdout=json.dumps({"id": "task-1", "title": "New Title", "status": "open"}),
            returncode=0,
        )

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=[update_result, get_result]) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.update_task("task-1", title="New Title")

                assert task.title == "New Title"

                # Verify update command
                update_args = mock_run.call_args_list[0][0][0]
                assert "--title" in update_args
                assert "New Title" in update_args

    def test_update_task_with_priority(self, project_dir):
        """Test updating task priority."""
        update_result = Mock(stdout="", returncode=0)
        get_result = Mock(
            stdout=json.dumps({"id": "task-1", "title": "Task", "status": "open", "priority": 0}),
            returncode=0,
        )

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=[update_result, get_result]) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.update_task("task-1", priority=0)

                assert task.priority == TaskPriority.P0

                # Verify update command
                update_args = mock_run.call_args_list[0][0][0]
                assert "--priority" in update_args
                assert "0" in update_args

    def test_update_task_with_notes(self, project_dir):
        """Test updating task notes."""
        update_result = Mock(stdout="", returncode=0)
        get_result = Mock(
            stdout=json.dumps(
                {"id": "task-1", "title": "Task", "status": "open", "notes": "Important note"}
            ),
            returncode=0,
        )

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", side_effect=[update_result, get_result]) as mock_run:
                backend = BeadsBackend(project_dir=project_dir)
                task = backend.update_task("task-1", notes="Important note")

                assert task.notes == "Important note"

                # Verify update command
                update_args = mock_run.call_args_list[0][0][0]
                assert "--notes" in update_args
                assert "Important note" in update_args


# ==============================================================================
# Task Counts Extended Tests
# ==============================================================================


class TestGetTaskCountsExtended:
    """Test extended task counts functionality."""

    def test_get_task_counts_with_blocked(self, project_dir):
        """Test getting task counts including blocked tasks."""
        tasks_json = json.dumps(
            [
                {"id": "task-0", "status": "open"},
                {"id": "task-1", "status": "open", "blocks": ["task-0"]},  # blocked
                {"id": "task-2", "status": "open", "blocks": []},  # not blocked
                {"id": "task-3", "status": "in_progress"},
                {"id": "task-4", "status": "closed"},
            ]
        )

        with patch("shutil.which", return_value="/usr/local/bin/bd"):
            with patch("subprocess.run", return_value=Mock(stdout=tasks_json, returncode=0)):
                backend = BeadsBackend(project_dir=project_dir)
                counts = backend.get_task_counts()

                assert counts.total == 5
                assert counts.open == 3
                assert counts.in_progress == 1
                assert counts.closed == 1
                assert counts.blocked == 1  # task-1 is blocked


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
