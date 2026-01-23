"""
Unit tests for JSON file task backend (prd.json).

Tests the JsonBackend implementation including file I/O, atomic writes,
caching, task CRUD operations, and error handling.
"""

import json
from pathlib import Path

import pytest

from cub.core.tasks.json import JsonBackend, PrdFileCorruptedError
from cub.core.tasks.models import TaskPriority, TaskStatus, TaskType

# ==============================================================================
# Initialization Tests
# ==============================================================================


class TestJsonBackendInit:
    """Test JsonBackend initialization and file discovery."""

    def test_init_default_project_dir(self):
        """Test initialization defaults to current directory."""
        backend = JsonBackend()
        assert backend.project_dir == Path.cwd()
        assert backend.prd_file == Path.cwd() / "prd.json"

    def test_init_with_project_dir(self, temp_dir):
        """Test initialization with explicit project directory."""
        backend = JsonBackend(project_dir=temp_dir)
        assert backend.project_dir == temp_dir
        assert backend.prd_file == temp_dir / "prd.json"

    def test_init_with_explicit_prd_file(self, temp_dir):
        """Test initialization with explicit prd.json path."""
        prd_path = temp_dir / "custom.json"
        backend = JsonBackend(prd_file=prd_path)
        assert backend.prd_file == prd_path

    def test_init_cache_is_empty(self, temp_dir):
        """Test that cache is initially None."""
        backend = JsonBackend(project_dir=temp_dir)
        assert backend._cache is None
        assert backend._cache_mtime is None


# ==============================================================================
# File Loading Tests
# ==============================================================================


class TestLoadPrd:
    """Test loading and parsing prd.json file."""

    def test_load_existing_file(self, temp_dir):
        """Test loading a valid prd.json file."""
        prd_file = temp_dir / "prd.json"
        prd_data = {
            "prefix": "test",
            "tasks": [{"id": "test-001", "title": "Task 1", "status": "open"}],
        }
        prd_file.write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        data = backend._load_prd()

        assert data["prefix"] == "test"
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["id"] == "test-001"

    def test_load_creates_empty_file_if_missing(self, temp_dir):
        """Test that missing prd.json is created automatically."""
        backend = JsonBackend(project_dir=temp_dir)
        data = backend._load_prd()

        # Check file was created
        assert backend.prd_file.exists()

        # Check default structure
        assert "prefix" in data
        assert "tasks" in data
        assert data["tasks"] == []

    def test_load_uses_directory_name_for_prefix(self, temp_dir):
        """Test that prefix defaults to first 3 chars of directory name."""
        project_dir = temp_dir / "myproject"
        project_dir.mkdir()

        backend = JsonBackend(project_dir=project_dir)
        data = backend._load_prd()

        assert data["prefix"] == "myp"  # First 3 chars of "myproject"

    def test_load_invalid_json_raises_error(self, temp_dir):
        """Test that corrupted JSON raises PrdFileCorruptedError."""
        prd_file = temp_dir / "prd.json"
        prd_file.write_text("{ invalid json }")

        backend = JsonBackend(project_dir=temp_dir)
        with pytest.raises(PrdFileCorruptedError) as exc_info:
            backend._load_prd()
        assert "Failed to parse" in str(exc_info.value)

    def test_load_non_dict_json_raises_error(self, temp_dir):
        """Test that non-object JSON raises error."""
        prd_file = temp_dir / "prd.json"
        prd_file.write_text(json.dumps(["not", "an", "object"]))

        backend = JsonBackend(project_dir=temp_dir)
        with pytest.raises(PrdFileCorruptedError) as exc_info:
            backend._load_prd()
        assert "must be a JSON object" in str(exc_info.value)

    def test_load_adds_missing_tasks_key(self, temp_dir):
        """Test that missing 'tasks' key is added automatically."""
        prd_file = temp_dir / "prd.json"
        prd_file.write_text(json.dumps({"prefix": "test"}))

        backend = JsonBackend(project_dir=temp_dir)
        data = backend._load_prd()

        assert "tasks" in data
        assert data["tasks"] == []

    def test_load_caching(self, temp_dir):
        """Test that prd.json is cached and not re-parsed."""
        prd_file = temp_dir / "prd.json"
        prd_data = {"prefix": "test", "tasks": []}
        prd_file.write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)

        # First load
        data1 = backend._load_prd()
        assert backend._cache is not None
        assert backend._cache_mtime is not None

        # Second load should use cache (same object reference)
        data2 = backend._load_prd()
        assert data1 is data2

    def test_load_cache_invalidation_on_file_change(self, temp_dir):
        """Test that cache is invalidated when file changes."""
        prd_file = temp_dir / "prd.json"
        prd_file.write_text(json.dumps({"prefix": "v1", "tasks": []}))

        backend = JsonBackend(project_dir=temp_dir)
        data1 = backend._load_prd()
        assert data1["prefix"] == "v1"

        # Modify file
        import time

        time.sleep(0.01)  # Ensure mtime changes
        prd_file.write_text(json.dumps({"prefix": "v2", "tasks": []}))

        # Load again - should detect change
        data2 = backend._load_prd()
        assert data2["prefix"] == "v2"
        assert data1 is not data2


# ==============================================================================
# File Saving Tests
# ==============================================================================


class TestSavePrd:
    """Test saving prd.json with atomic writes."""

    def test_save_creates_file(self, temp_dir):
        """Test that save creates a new file."""
        backend = JsonBackend(project_dir=temp_dir)
        data = {"prefix": "test", "tasks": []}
        backend._save_prd(data)

        assert backend.prd_file.exists()

        # Verify content
        saved_data = json.loads(backend.prd_file.read_text())
        assert saved_data["prefix"] == "test"

    def test_save_overwrites_existing_file(self, temp_dir):
        """Test that save overwrites existing file."""
        prd_file = temp_dir / "prd.json"
        prd_file.write_text(json.dumps({"prefix": "old", "tasks": []}))

        backend = JsonBackend(project_dir=temp_dir)
        backend._save_prd({"prefix": "new", "tasks": []})

        saved_data = json.loads(prd_file.read_text())
        assert saved_data["prefix"] == "new"

    def test_save_invalidates_cache(self, temp_dir):
        """Test that save invalidates the cache."""
        backend = JsonBackend(project_dir=temp_dir)
        backend._load_prd()  # Populate cache

        assert backend._cache is not None

        backend._save_prd({"prefix": "test", "tasks": []})

        # Cache should be invalidated
        assert backend._cache is None
        assert backend._cache_mtime is None

    def test_save_is_atomic(self, temp_dir):
        """Test that save uses atomic write (temp file + rename)."""
        backend = JsonBackend(project_dir=temp_dir)

        # Create initial file
        backend._save_prd({"prefix": "test", "tasks": []})

        # The file should exist and be valid JSON (atomic write succeeded)
        assert backend.prd_file.exists()
        data = json.loads(backend.prd_file.read_text())
        assert data["prefix"] == "test"

    def test_save_adds_trailing_newline(self, temp_dir):
        """Test that saved file has trailing newline."""
        backend = JsonBackend(project_dir=temp_dir)
        backend._save_prd({"prefix": "test", "tasks": []})

        content = backend.prd_file.read_text()
        assert content.endswith("\n")


# ==============================================================================
# List Tasks Tests
# ==============================================================================


class TestListTasks:
    """Test listing tasks with filters."""

    def test_list_all_tasks(self, temp_dir):
        """Test listing all tasks."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {
                    "id": "test-001",
                    "title": "Task 1",
                    "status": "open",
                    "priority": "P0",
                    "type": "task",
                },
                {
                    "id": "test-002",
                    "title": "Task 2",
                    "status": "closed",
                    "priority": "P1",
                    "type": "feature",
                },
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        assert len(tasks) == 2
        assert tasks[0].id == "test-001"
        assert tasks[1].id == "test-002"

    def test_list_tasks_by_status(self, temp_dir):
        """Test filtering tasks by status."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Open", "status": "open"},
                {"id": "test-002", "title": "Closed", "status": "closed"},
                {"id": "test-003", "title": "In Progress", "status": "in_progress"},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        open_tasks = backend.list_tasks(status=TaskStatus.OPEN)

        assert len(open_tasks) == 1
        assert open_tasks[0].id == "test-001"

    def test_list_tasks_by_parent(self, temp_dir):
        """Test filtering tasks by parent epic."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "epic-001", "title": "Epic", "type": "epic"},
                {"id": "test-001", "title": "Child 1", "parent": "epic-001"},
                {"id": "test-002", "title": "Child 2", "parent": "epic-001"},
                {"id": "test-003", "title": "Orphan"},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        child_tasks = backend.list_tasks(parent="epic-001")

        assert len(child_tasks) == 2
        assert all(t.parent == "epic-001" for t in child_tasks)

    def test_list_tasks_by_label(self, temp_dir):
        """Test filtering tasks by label."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Task 1", "labels": ["backend", "urgent"]},
                {"id": "test-002", "title": "Task 2", "labels": ["frontend"]},
                {"id": "test-003", "title": "Task 3", "labels": ["backend", "low"]},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        backend_tasks = backend.list_tasks(label="backend")

        assert len(backend_tasks) == 2
        assert all(any("backend" in label for label in t.labels) for t in backend_tasks)

    def test_list_tasks_skips_invalid(self, temp_dir):
        """Test that invalid tasks are skipped without crashing."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Valid Task"},
                {"id": "test-002"},  # Missing required 'title'
                {"id": "test-003", "title": "Another Valid Task"},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        # Should skip invalid task
        assert len(tasks) == 2
        assert tasks[0].id == "test-001"
        assert tasks[1].id == "test-003"

    def test_list_tasks_empty_file(self, temp_dir):
        """Test listing tasks from empty file."""
        backend = JsonBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        assert tasks == []


# ==============================================================================
# Get Task Tests
# ==============================================================================


class TestGetTask:
    """Test getting a single task by ID."""

    def test_get_task_success(self, temp_dir):
        """Test successfully getting a task by ID."""
        prd_data = {
            "prefix": "test",
            "tasks": [{"id": "test-001", "title": "Task 1"}, {"id": "test-002", "title": "Task 2"}],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        task = backend.get_task("test-002")

        assert task is not None
        assert task.id == "test-002"
        assert task.title == "Task 2"

    def test_get_task_not_found(self, temp_dir):
        """Test getting non-existent task returns None."""
        prd_data = {"prefix": "test", "tasks": []}
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        task = backend.get_task("nonexistent")

        assert task is None

    def test_get_task_invalid_returns_none(self, temp_dir):
        """Test that invalid task data returns None."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001"}  # Missing required 'title'
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        task = backend.get_task("test-001")

        assert task is None


# ==============================================================================
# Get Ready Tasks Tests
# ==============================================================================


class TestGetReadyTasks:
    """Test getting tasks ready to work on."""

    def test_get_ready_tasks_no_dependencies(self, temp_dir):
        """Test getting ready tasks when no dependencies exist."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Task 1", "status": "open", "priority": "P2"},
                {"id": "test-002", "title": "Task 2", "status": "open", "priority": "P0"},
                {"id": "test-003", "title": "Task 3", "status": "in_progress"},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        ready = backend.get_ready_tasks()

        # Only open tasks, sorted by priority (P0 first)
        assert len(ready) == 2
        assert ready[0].id == "test-002"  # P0
        assert ready[1].id == "test-001"  # P2

    def test_get_ready_tasks_with_dependencies(self, temp_dir):
        """Test that tasks with unclosed dependencies are not ready."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Task 1", "status": "open"},
                {"id": "test-002", "title": "Task 2", "status": "open", "depends_on": ["test-001"]},
                {"id": "test-003", "title": "Task 3", "status": "closed"},
                {"id": "test-004", "title": "Task 4", "status": "open", "depends_on": ["test-003"]},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        ready = backend.get_ready_tasks()

        # test-001 is ready (no deps)
        # test-002 is NOT ready (depends on open test-001)
        # test-004 IS ready (depends on closed test-003)
        assert len(ready) == 2
        task_ids = {t.id for t in ready}
        assert "test-001" in task_ids
        assert "test-004" in task_ids
        assert "test-002" not in task_ids

    def test_get_ready_tasks_sorted_by_priority(self, temp_dir):
        """Test that ready tasks are sorted by priority."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Low", "status": "open", "priority": "P4"},
                {"id": "test-002", "title": "High", "status": "open", "priority": "P0"},
                {"id": "test-003", "title": "Med", "status": "open", "priority": "P2"},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        ready = backend.get_ready_tasks()

        # Should be sorted P0, P2, P4
        assert ready[0].priority == TaskPriority.P0
        assert ready[1].priority == TaskPriority.P2
        assert ready[2].priority == TaskPriority.P4


# ==============================================================================
# Create Task Tests
# ==============================================================================


class TestCreateTask:
    """Test creating new tasks."""

    def test_create_minimal_task(self, temp_dir):
        """Test creating task with minimal fields."""
        backend = JsonBackend(project_dir=temp_dir)
        task = backend.create_task(title="New Task")

        assert task.id is not None
        assert task.title == "New Task"
        assert task.status == TaskStatus.OPEN
        assert task.priority == TaskPriority.P2

        # Verify saved to file
        saved_task = backend.get_task(task.id)
        assert saved_task is not None
        assert saved_task.title == "New Task"

    def test_create_full_task(self, temp_dir):
        """Test creating task with all fields."""
        backend = JsonBackend(project_dir=temp_dir)
        task = backend.create_task(
            title="Full Task",
            description="Detailed description",
            task_type="feature",
            priority=0,
            labels=["backend", "urgent"],
            depends_on=["test-000"],
            parent="epic-001",
        )

        assert task.type == TaskType.FEATURE
        assert task.priority == TaskPriority.P0
        assert task.description == "Detailed description"
        assert "backend" in task.labels
        assert task.depends_on == ["test-000"]
        assert task.parent == "epic-001"

    def test_create_task_generates_sequential_ids(self, temp_dir):
        """Test that task IDs are generated sequentially."""
        backend = JsonBackend(project_dir=temp_dir)

        task1 = backend.create_task(title="Task 1")
        task2 = backend.create_task(title="Task 2")
        task3 = backend.create_task(title="Task 3")

        # IDs should be sequential
        assert task1.id.endswith("-001")
        assert task2.id.endswith("-002")
        assert task3.id.endswith("-003")

    def test_create_task_uses_prefix(self, temp_dir):
        """Test that created tasks use the file's prefix."""
        prd_data = {"prefix": "myapp", "tasks": []}
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        task = backend.create_task(title="Test")

        assert task.id.startswith("myapp-")


# ==============================================================================
# Update Task Tests
# ==============================================================================


class TestUpdateTask:
    """Test updating task fields."""

    def test_update_task_status(self, temp_dir):
        """Test updating task status."""
        prd_data = {
            "prefix": "test",
            "tasks": [{"id": "test-001", "title": "Task", "status": "open"}],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        updated = backend.update_task("test-001", status=TaskStatus.IN_PROGRESS)

        assert updated.status == TaskStatus.IN_PROGRESS

        # Verify persisted
        saved = backend.get_task("test-001")
        assert saved.status == TaskStatus.IN_PROGRESS

    def test_update_task_multiple_fields(self, temp_dir):
        """Test updating multiple fields at once."""
        prd_data = {
            "prefix": "test",
            "tasks": [{"id": "test-001", "title": "Task", "status": "open"}],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        updated = backend.update_task(
            "test-001",
            status=TaskStatus.IN_PROGRESS,
            assignee="alice",
            labels=["backend", "urgent"],
        )

        assert updated.assignee == "alice"
        assert "backend" in updated.labels

    def test_update_task_not_found(self, temp_dir):
        """Test updating non-existent task raises ValueError."""
        backend = JsonBackend(project_dir=temp_dir)

        with pytest.raises(ValueError) as exc_info:
            backend.update_task("nonexistent", status=TaskStatus.CLOSED)
        assert "not found" in str(exc_info.value)


# ==============================================================================
# Close Task Tests
# ==============================================================================


class TestCloseTask:
    """Test closing tasks."""

    def test_close_task(self, temp_dir):
        """Test closing a task."""
        prd_data = {
            "prefix": "test",
            "tasks": [{"id": "test-001", "title": "Task", "status": "open"}],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed = backend.close_task("test-001")

        assert closed.status == TaskStatus.CLOSED
        assert closed.closed_at is not None

    def test_close_task_with_reason(self, temp_dir):
        """Test closing task with reason."""
        prd_data = {
            "prefix": "test",
            "tasks": [{"id": "test-001", "title": "Task", "status": "open"}],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed = backend.close_task("test-001", reason="Completed successfully")

        assert "Completed successfully" in closed.notes

    def test_close_task_not_found(self, temp_dir):
        """Test closing non-existent task raises ValueError."""
        backend = JsonBackend(project_dir=temp_dir)

        with pytest.raises(ValueError) as exc_info:
            backend.close_task("nonexistent")
        assert "not found" in str(exc_info.value)


# ==============================================================================
# Task Counts Tests
# ==============================================================================


class TestGetTaskCounts:
    """Test getting task statistics."""

    def test_get_task_counts(self, temp_dir):
        """Test getting correct task counts."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Open 1", "status": "open"},
                {"id": "test-002", "title": "Open 2", "status": "open"},
                {"id": "test-003", "title": "In Progress", "status": "in_progress"},
                {"id": "test-004", "title": "Closed 1", "status": "closed"},
                {"id": "test-005", "title": "Closed 2", "status": "closed"},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        counts = backend.get_task_counts()

        assert counts.total == 5
        assert counts.open == 2
        assert counts.in_progress == 1
        assert counts.closed == 2
        assert counts.remaining == 3  # open + in_progress
        assert counts.completion_percentage == 40.0  # 2/5 closed

    def test_get_task_counts_empty(self, temp_dir):
        """Test counts for empty task list."""
        backend = JsonBackend(project_dir=temp_dir)
        counts = backend.get_task_counts()

        assert counts.total == 0
        assert counts.completion_percentage == 0.0


# ==============================================================================
# Import Tasks Tests
# ==============================================================================


class TestImportTasks:
    """Test bulk importing tasks."""

    def test_import_single_task(self, temp_dir):
        """Test importing a single task."""
        from cub.core.tasks.models import Task

        backend = JsonBackend(project_dir=temp_dir)

        # Create a task to import
        task_to_import = Task(
            id="temp-001",  # This ID will be replaced
            title="Imported Task",
            description="A task imported via bulk import",
        )

        imported = backend.import_tasks([task_to_import])

        assert len(imported) == 1
        assert imported[0].title == "Imported Task"
        assert imported[0].description == "A task imported via bulk import"
        # ID should be assigned by the backend
        assert imported[0].id.endswith("-001")

        # Verify saved to file
        saved_task = backend.get_task(imported[0].id)
        assert saved_task is not None
        assert saved_task.title == "Imported Task"

    def test_import_multiple_tasks(self, temp_dir):
        """Test importing multiple tasks at once."""
        from cub.core.tasks.models import Task

        backend = JsonBackend(project_dir=temp_dir)

        tasks_to_import = [
            Task(id="temp-001", title="Task 1", description="First task"),
            Task(id="temp-002", title="Task 2", description="Second task"),
            Task(id="temp-003", title="Task 3", description="Third task"),
        ]

        imported = backend.import_tasks(tasks_to_import)

        assert len(imported) == 3
        assert imported[0].title == "Task 1"
        assert imported[1].title == "Task 2"
        assert imported[2].title == "Task 3"

        # IDs should be sequential
        assert imported[0].id.endswith("-001")
        assert imported[1].id.endswith("-002")
        assert imported[2].id.endswith("-003")

        # All should be saved
        all_tasks = backend.list_tasks()
        assert len(all_tasks) == 3

    def test_import_tasks_with_existing_tasks(self, temp_dir):
        """Test importing tasks preserves explicit IDs even with existing tasks."""
        prd_data = {
            "prefix": "test",
            "tasks": [{"id": "test-001", "title": "Existing Task", "status": "open"}],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        from cub.core.tasks.models import Task

        backend = JsonBackend(project_dir=temp_dir)

        tasks_to_import = [
            Task(id="new-001", title="New Task 1"),
            Task(id="new-002", title="New Task 2"),
        ]

        imported = backend.import_tasks(tasks_to_import)

        assert len(imported) == 2
        # Explicit IDs should be preserved
        assert imported[0].id == "new-001"
        assert imported[1].id == "new-002"

        # Total tasks should be 3
        all_tasks = backend.list_tasks()
        assert len(all_tasks) == 3

    def test_import_tasks_rejects_duplicate_ids(self, temp_dir):
        """Test that importing tasks with duplicate IDs raises error."""
        prd_data = {
            "prefix": "test",
            "tasks": [{"id": "test-001", "title": "Existing Task", "status": "open"}],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        from cub.core.tasks.models import Task

        backend = JsonBackend(project_dir=temp_dir)

        # Try to import a task with an ID that already exists
        tasks_to_import = [Task(id="test-001", title="Duplicate Task")]

        import pytest
        with pytest.raises(ValueError, match="already exists"):
            backend.import_tasks(tasks_to_import)

    def test_import_tasks_preserves_fields(self, temp_dir):
        """Test that import preserves task fields."""
        from cub.core.tasks.models import Task, TaskPriority, TaskType

        backend = JsonBackend(project_dir=temp_dir)

        task_to_import = Task(
            id="temp-001",
            title="Full Task",
            description="Detailed description",
            type=TaskType.FEATURE,
            priority=TaskPriority.P0,
            labels=["backend", "urgent"],
            depends_on=["other-001"],
            parent="epic-001",
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            notes="Some notes",
        )

        imported = backend.import_tasks([task_to_import])

        assert len(imported) == 1
        task = imported[0]
        assert task.title == "Full Task"
        assert task.description == "Detailed description"
        assert task.type == TaskType.FEATURE
        assert task.priority == TaskPriority.P0
        assert "backend" in task.labels
        assert "urgent" in task.labels
        assert task.depends_on == ["other-001"]
        assert task.parent == "epic-001"
        assert task.acceptance_criteria == ["Criterion 1", "Criterion 2"]
        assert task.notes == "Some notes"

    def test_import_empty_list(self, temp_dir):
        """Test importing empty list returns empty list."""
        backend = JsonBackend(project_dir=temp_dir)

        imported = backend.import_tasks([])

        assert imported == []
        assert backend.list_tasks() == []

    def test_import_tasks_preserves_explicit_id(self, temp_dir):
        """Test that imported tasks preserve their explicit IDs."""
        prd_data = {"prefix": "myapp", "tasks": []}
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        from cub.core.tasks.models import Task

        backend = JsonBackend(project_dir=temp_dir)

        # Task with explicit ID should keep it
        task_to_import = Task(id="custom-001", title="Test Task")
        imported = backend.import_tasks([task_to_import])

        assert imported[0].id == "custom-001"

    def test_import_tasks_generates_id_when_missing(self, temp_dir):
        """Test that tasks without IDs get generated IDs using prefix."""
        prd_data = {"prefix": "myapp", "tasks": []}
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        from cub.core.tasks.models import Task

        backend = JsonBackend(project_dir=temp_dir)

        # Task without ID should get one generated
        task_to_import = Task(id="", title="Test Task")
        imported = backend.import_tasks([task_to_import])

        assert imported[0].id.startswith("myapp-")


# ==============================================================================
# Try Close Epic Tests
# ==============================================================================


class TestTryCloseEpic:
    """Test auto-closing epics when all tasks complete."""

    def test_close_epic_all_tasks_closed(self, temp_dir):
        """Test that epic is closed when all its tasks are closed."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"},
                {
                    "id": "test-001",
                    "title": "Task 1",
                    "parent": "epic-001",
                    "status": "closed",
                },
                {
                    "id": "test-002",
                    "title": "Task 2",
                    "parent": "epic-001",
                    "status": "closed",
                },
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed, message = backend.try_close_epic("epic-001")

        assert closed is True
        assert "auto-closed" in message
        assert "2 tasks completed" in message

        # Verify epic is now closed
        epic = backend.get_task("epic-001")
        assert epic.status == TaskStatus.CLOSED

    def test_epic_stays_open_with_open_tasks(self, temp_dir):
        """Test that epic stays open when some tasks are still open."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"},
                {
                    "id": "test-001",
                    "title": "Task 1",
                    "parent": "epic-001",
                    "status": "closed",
                },
                {
                    "id": "test-002",
                    "title": "Task 2",
                    "parent": "epic-001",
                    "status": "open",
                },
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed, message = backend.try_close_epic("epic-001")

        assert closed is False
        assert "1 open" in message

        # Verify epic is still open
        epic = backend.get_task("epic-001")
        assert epic.status == TaskStatus.OPEN

    def test_epic_stays_open_with_in_progress_tasks(self, temp_dir):
        """Test that epic stays open when some tasks are in progress."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"},
                {
                    "id": "test-001",
                    "title": "Task 1",
                    "parent": "epic-001",
                    "status": "closed",
                },
                {
                    "id": "test-002",
                    "title": "Task 2",
                    "parent": "epic-001",
                    "status": "in_progress",
                },
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed, message = backend.try_close_epic("epic-001")

        assert closed is False
        assert "1 in-progress" in message

        # Verify epic is still open
        epic = backend.get_task("epic-001")
        assert epic.status == TaskStatus.OPEN

    def test_epic_not_found(self, temp_dir):
        """Test handling of non-existent epic."""
        backend = JsonBackend(project_dir=temp_dir)
        closed, message = backend.try_close_epic("nonexistent")

        assert closed is False
        assert "not found" in message

    def test_epic_already_closed(self, temp_dir):
        """Test handling of already closed epic."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "epic-001", "title": "Epic", "type": "epic", "status": "closed"},
                {
                    "id": "test-001",
                    "title": "Task 1",
                    "parent": "epic-001",
                    "status": "closed",
                },
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed, message = backend.try_close_epic("epic-001")

        assert closed is False
        assert "already closed" in message

    def test_epic_no_tasks(self, temp_dir):
        """Test handling of epic with no tasks."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"},
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed, message = backend.try_close_epic("epic-001")

        assert closed is False
        assert "No tasks found" in message

    def test_close_epic_with_tasks_by_label(self, temp_dir):
        """Test that tasks with epic ID as label are included."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"},
                {
                    "id": "test-001",
                    "title": "Task 1",
                    "labels": ["epic-001"],
                    "status": "closed",
                },
                {
                    "id": "test-002",
                    "title": "Task 2",
                    "labels": ["epic-001", "urgent"],
                    "status": "closed",
                },
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed, message = backend.try_close_epic("epic-001")

        assert closed is True
        assert "auto-closed" in message

    def test_close_epic_mixed_parent_and_label(self, temp_dir):
        """Test that tasks with either parent or label are included."""
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "epic-001", "title": "Epic", "type": "epic", "status": "open"},
                {
                    "id": "test-001",
                    "title": "Task 1",
                    "parent": "epic-001",
                    "status": "closed",
                },
                {
                    "id": "test-002",
                    "title": "Task 2",
                    "labels": ["epic-001"],
                    "status": "closed",
                },
                {
                    "id": "test-003",
                    "title": "Task 3",
                    "parent": "epic-001",
                    "labels": ["epic-001"],  # Both parent and label
                    "status": "closed",
                },
            ],
        }
        (temp_dir / "prd.json").write_text(json.dumps(prd_data))

        backend = JsonBackend(project_dir=temp_dir)
        closed, message = backend.try_close_epic("epic-001")

        assert closed is True
        assert "3 tasks completed" in message
