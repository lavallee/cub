"""
Unit tests for JSONL file task backend (tasks.jsonl).

Tests the JsonlBackend implementation including file I/O, atomic writes,
caching, task CRUD operations, error handling, and prd.json migration.
"""

import json
from pathlib import Path

import pytest

from cub.core.tasks.jsonl import JsonlBackend, TasksFileCorruptedError
from cub.core.tasks.models import TaskPriority, TaskStatus, TaskType

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


# ==============================================================================
# Initialization Tests
# ==============================================================================


class TestJsonlBackendInit:
    """Test JsonlBackend initialization and file discovery."""

    def test_init_default_project_dir(self):
        """Test initialization defaults to current directory."""
        backend = JsonlBackend()
        assert backend.project_dir == Path.cwd()
        assert backend.cub_dir == Path.cwd() / ".cub"
        assert backend.tasks_file == Path.cwd() / ".cub" / "tasks.jsonl"

    def test_init_with_project_dir(self, temp_dir):
        """Test initialization with explicit project directory."""
        backend = JsonlBackend(project_dir=temp_dir)
        assert backend.project_dir == temp_dir
        assert backend.cub_dir == temp_dir / ".cub"
        assert backend.tasks_file == temp_dir / ".cub" / "tasks.jsonl"

    def test_init_cache_is_empty(self, temp_dir):
        """Test that cache is initially None."""
        backend = JsonlBackend(project_dir=temp_dir)
        assert backend._cache is None
        assert backend._cache_mtime is None


# ==============================================================================
# File Loading Tests
# ==============================================================================


class TestLoadTasks:
    """Test loading and parsing tasks.jsonl file."""

    def test_load_existing_file(self, temp_dir):
        """Test loading a valid tasks.jsonl file."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        # Write JSONL format (one task per line)
        tasks_file.write_text(
            '{"id": "test-001", "title": "Task 1", "status": "open"}\n'
            '{"id": "test-002", "title": "Task 2", "status": "closed"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend._load_tasks()

        assert len(tasks) == 2
        assert tasks[0]["id"] == "test-001"
        assert tasks[1]["id"] == "test-002"

    def test_load_creates_empty_file_if_missing(self, temp_dir):
        """Test that missing tasks.jsonl is created automatically."""
        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend._load_tasks()

        # Check file was created
        assert backend.tasks_file.exists()
        assert backend.cub_dir.exists()

        # Check returns empty list
        assert tasks == []

    def test_load_invalid_json_raises_error(self, temp_dir):
        """Test that corrupted JSONL raises TasksFileCorruptedError."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text("{ invalid json }\n")

        backend = JsonlBackend(project_dir=temp_dir)
        with pytest.raises(TasksFileCorruptedError) as exc_info:
            backend._load_tasks()
        assert "Line 1" in str(exc_info.value)
        assert "invalid JSON" in str(exc_info.value)

    def test_load_non_dict_json_raises_error(self, temp_dir):
        """Test that non-object JSON raises error."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('["not", "an", "object"]\n')

        backend = JsonlBackend(project_dir=temp_dir)
        with pytest.raises(TasksFileCorruptedError) as exc_info:
            backend._load_tasks()
        assert "Line 1" in str(exc_info.value)
        assert "expected JSON object" in str(exc_info.value)

    def test_load_skips_empty_lines(self, temp_dir):
        """Test that empty lines are skipped."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Task 1"}\n'
            '\n'  # Empty line
            '{"id": "test-002", "title": "Task 2"}\n'
            '   \n'  # Whitespace only
            '{"id": "test-003", "title": "Task 3"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend._load_tasks()

        assert len(tasks) == 3

    def test_load_caching(self, temp_dir):
        """Test that tasks.jsonl is cached and not re-parsed."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "test-001", "title": "Task 1"}\n')

        backend = JsonlBackend(project_dir=temp_dir)

        # First load
        tasks1 = backend._load_tasks()
        assert backend._cache is not None
        assert backend._cache_mtime is not None

        # Second load should use cache (same object reference)
        tasks2 = backend._load_tasks()
        assert tasks1 is tasks2

    def test_load_cache_invalidation_on_file_change(self, temp_dir):
        """Test that cache is invalidated when file changes."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "test-001", "title": "v1"}\n')

        backend = JsonlBackend(project_dir=temp_dir)
        tasks1 = backend._load_tasks()
        assert tasks1[0]["title"] == "v1"

        # Modify file
        import time
        time.sleep(0.01)  # Ensure mtime changes
        tasks_file.write_text('{"id": "test-001", "title": "v2"}\n')

        # Load again - should detect change
        tasks2 = backend._load_tasks()
        assert tasks2[0]["title"] == "v2"
        assert tasks1 is not tasks2


# ==============================================================================
# Migration Tests
# ==============================================================================


class TestMigrationFromPrdJson:
    """Test migration from prd.json to tasks.jsonl."""

    def test_migrate_basic_tasks(self, temp_dir):
        """Test migrating basic tasks from prd.json."""
        prd_file = temp_dir / "prd.json"
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Task 1", "status": "open"},
                {"id": "test-002", "title": "Task 2", "status": "closed"},
            ],
        }
        prd_file.write_text(json.dumps(prd_data))

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()  # This triggers migration

        assert len(tasks) == 2
        assert tasks[0].id == "test-001"
        assert tasks[1].id == "test-002"

        # Check that tasks.jsonl was created
        assert backend.tasks_file.exists()

    def test_migrate_with_dependencies(self, temp_dir):
        """Test migrating tasks with dependencies (dependsOn -> depends_on)."""
        prd_file = temp_dir / "prd.json"
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Task 1", "status": "closed"},
                {
                    "id": "test-002",
                    "title": "Task 2",
                    "status": "open",
                    "dependsOn": ["test-001"],  # Old camelCase format
                },
            ],
        }
        prd_file.write_text(json.dumps(prd_data))

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        assert len(tasks) == 2
        # Check that dependencies were migrated
        task2 = backend.get_task("test-002")
        assert task2.depends_on == ["test-001"]

    def test_migrate_with_type_field(self, temp_dir):
        """Test migrating tasks with type field (type -> issue_type)."""
        prd_file = temp_dir / "prd.json"
        prd_data = {
            "prefix": "test",
            "tasks": [
                {"id": "test-001", "title": "Bug Fix", "type": "bug"},  # Old field name
                {"id": "test-002", "title": "New Feature", "type": "feature"},
            ],
        }
        prd_file.write_text(json.dumps(prd_data))

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        assert len(tasks) == 2
        assert tasks[0].type == TaskType.BUG
        assert tasks[1].type == TaskType.FEATURE

    def test_migrate_creates_backup(self, temp_dir):
        """Test that migration creates a backup of prd.json."""
        prd_file = temp_dir / "prd.json"
        prd_data = {"prefix": "test", "tasks": [{"id": "test-001", "title": "Task"}]}
        prd_file.write_text(json.dumps(prd_data))

        backend = JsonlBackend(project_dir=temp_dir)
        backend.list_tasks()  # Trigger migration

        # Check backup was created
        backup_file = temp_dir / "prd.json.bak"
        assert backup_file.exists()

        # Verify backup content matches original
        backup_data = json.loads(backup_file.read_text())
        assert backup_data == prd_data

    def test_migrate_preserves_all_fields(self, temp_dir):
        """Test that migration preserves all task fields."""
        prd_file = temp_dir / "prd.json"
        prd_data = {
            "prefix": "test",
            "tasks": [
                {
                    "id": "test-001",
                    "title": "Full Task",
                    "description": "Detailed description",
                    "type": "feature",
                    "status": "in_progress",
                    "priority": "P0",
                    "labels": ["backend", "urgent"],
                    "dependsOn": ["test-000"],
                    "parent": "epic-001",
                    "assignee": "alice",
                    "notes": "Some notes",
                }
            ],
        }
        prd_file.write_text(json.dumps(prd_data))

        backend = JsonlBackend(project_dir=temp_dir)
        task = backend.get_task("test-001")

        assert task is not None
        assert task.title == "Full Task"
        assert task.description == "Detailed description"
        assert task.type == TaskType.FEATURE
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.priority == TaskPriority.P0
        assert "backend" in task.labels
        assert task.depends_on == ["test-000"]
        assert task.parent == "epic-001"
        assert task.assignee == "alice"
        assert task.notes == "Some notes"

    def test_migrate_invalid_prd_json(self, temp_dir):
        """Test that invalid prd.json raises error."""
        prd_file = temp_dir / "prd.json"
        prd_file.write_text("{ invalid json }")

        backend = JsonlBackend(project_dir=temp_dir)
        with pytest.raises(TasksFileCorruptedError) as exc_info:
            backend.list_tasks()
        assert "Failed to parse" in str(exc_info.value)

    def test_migrate_non_dict_prd_json(self, temp_dir):
        """Test that non-object prd.json raises error."""
        prd_file = temp_dir / "prd.json"
        prd_file.write_text('["not", "an", "object"]')

        backend = JsonlBackend(project_dir=temp_dir)
        with pytest.raises(TasksFileCorruptedError) as exc_info:
            backend.list_tasks()
        assert "must be a JSON object" in str(exc_info.value)

    def test_migrate_empty_tasks_array(self, temp_dir):
        """Test migrating prd.json with empty tasks array."""
        prd_file = temp_dir / "prd.json"
        prd_data = {"prefix": "test", "tasks": []}
        prd_file.write_text(json.dumps(prd_data))

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        assert tasks == []
        assert backend.tasks_file.exists()

    def test_no_migration_if_tasks_jsonl_exists(self, temp_dir):
        """Test that migration doesn't happen if tasks.jsonl already exists."""
        # Create both files
        prd_file = temp_dir / "prd.json"
        prd_data = {"prefix": "test", "tasks": [{"id": "prd-001", "title": "From PRD"}]}
        prd_file.write_text(json.dumps(prd_data))

        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "jsonl-001", "title": "From JSONL"}\n')

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        # Should load from tasks.jsonl, not prd.json
        assert len(tasks) == 1
        assert tasks[0].id == "jsonl-001"


# ==============================================================================
# File Saving Tests
# ==============================================================================


class TestSaveTasks:
    """Test saving tasks.jsonl with atomic writes."""

    def test_save_creates_file(self, temp_dir):
        """Test that save creates a new file."""
        backend = JsonlBackend(project_dir=temp_dir)
        tasks = [{"id": "test-001", "title": "Task 1"}]
        backend._save_tasks(tasks)

        assert backend.tasks_file.exists()
        assert backend.cub_dir.exists()

        # Verify content
        lines = backend.tasks_file.read_text().strip().split("\n")
        assert len(lines) == 1
        saved_task = json.loads(lines[0])
        assert saved_task["id"] == "test-001"

    def test_save_overwrites_existing_file(self, temp_dir):
        """Test that save overwrites existing file."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "old", "title": "Old"}\n')

        backend = JsonlBackend(project_dir=temp_dir)
        backend._save_tasks([{"id": "new", "title": "New"}])

        lines = tasks_file.read_text().strip().split("\n")
        assert len(lines) == 1
        saved_task = json.loads(lines[0])
        assert saved_task["id"] == "new"

    def test_save_invalidates_cache(self, temp_dir):
        """Test that save invalidates the cache."""
        backend = JsonlBackend(project_dir=temp_dir)
        backend._load_tasks()  # Populate cache

        assert backend._cache is not None

        backend._save_tasks([{"id": "test-001", "title": "Task"}])

        # Cache should be invalidated
        assert backend._cache is None
        assert backend._cache_mtime is None

    def test_save_multiple_tasks(self, temp_dir):
        """Test saving multiple tasks (one per line)."""
        backend = JsonlBackend(project_dir=temp_dir)
        tasks = [
            {"id": "test-001", "title": "Task 1"},
            {"id": "test-002", "title": "Task 2"},
            {"id": "test-003", "title": "Task 3"},
        ]
        backend._save_tasks(tasks)

        lines = backend.tasks_file.read_text().strip().split("\n")
        assert len(lines) == 3

        for i, line in enumerate(lines):
            task = json.loads(line)
            assert task["id"] == f"test-{i+1:03d}"


# ==============================================================================
# List Tasks Tests
# ==============================================================================


class TestListTasks:
    """Test listing tasks with filters."""

    def test_list_all_tasks(self, temp_dir):
        """Test listing all tasks."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Task 1", "status": "open", '
            '"priority": "P0", "issue_type": "task"}\n'
            '{"id": "test-002", "title": "Task 2", "status": "closed", '
            '"priority": "P1", "issue_type": "feature"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        assert len(tasks) == 2
        assert tasks[0].id == "test-001"
        assert tasks[1].id == "test-002"

    def test_list_tasks_by_status(self, temp_dir):
        """Test filtering tasks by status."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Open", "status": "open"}\n'
            '{"id": "test-002", "title": "Closed", "status": "closed"}\n'
            '{"id": "test-003", "title": "In Progress", "status": "in_progress"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        open_tasks = backend.list_tasks(status=TaskStatus.OPEN)

        assert len(open_tasks) == 1
        assert open_tasks[0].id == "test-001"

    def test_list_tasks_by_parent(self, temp_dir):
        """Test filtering tasks by parent epic."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "epic-001", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "test-001", "title": "Child 1", "parent": "epic-001"}\n'
            '{"id": "test-002", "title": "Child 2", "parent": "epic-001"}\n'
            '{"id": "test-003", "title": "Orphan"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        child_tasks = backend.list_tasks(parent="epic-001")

        assert len(child_tasks) == 2
        assert all(t.parent == "epic-001" for t in child_tasks)

    def test_list_tasks_by_label(self, temp_dir):
        """Test filtering tasks by label."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Task 1", "labels": ["backend", "urgent"]}\n'
            '{"id": "test-002", "title": "Task 2", "labels": ["frontend"]}\n'
            '{"id": "test-003", "title": "Task 3", "labels": ["backend", "low"]}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        backend_tasks = backend.list_tasks(label="backend")

        assert len(backend_tasks) == 2
        assert all(any("backend" in label for label in t.labels) for t in backend_tasks)

    def test_list_tasks_skips_invalid(self, temp_dir):
        """Test that invalid tasks are skipped without crashing."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Valid Task"}\n'
            '{"id": "test-002"}\n'  # Missing required 'title'
            '{"id": "test-003", "title": "Another Valid Task"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        # Should skip invalid task
        assert len(tasks) == 2
        assert tasks[0].id == "test-001"
        assert tasks[1].id == "test-003"

    def test_list_tasks_empty_file(self, temp_dir):
        """Test listing tasks from empty file."""
        backend = JsonlBackend(project_dir=temp_dir)
        tasks = backend.list_tasks()

        assert tasks == []


# ==============================================================================
# Get Task Tests
# ==============================================================================


class TestGetTask:
    """Test getting a single task by ID."""

    def test_get_task_success(self, temp_dir):
        """Test successfully getting a task by ID."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Task 1"}\n'
            '{"id": "test-002", "title": "Task 2"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        task = backend.get_task("test-002")

        assert task is not None
        assert task.id == "test-002"
        assert task.title == "Task 2"

    def test_get_task_not_found(self, temp_dir):
        """Test getting non-existent task returns None."""
        backend = JsonlBackend(project_dir=temp_dir)
        task = backend.get_task("nonexistent")

        assert task is None

    def test_get_task_invalid_returns_none(self, temp_dir):
        """Test that invalid task data returns None."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "test-001"}\n')  # Missing required 'title'

        backend = JsonlBackend(project_dir=temp_dir)
        task = backend.get_task("test-001")

        assert task is None


# ==============================================================================
# Get Ready Tasks Tests
# ==============================================================================


class TestGetReadyTasks:
    """Test getting tasks ready to work on."""

    def test_get_ready_tasks_no_dependencies(self, temp_dir):
        """Test getting ready tasks when no dependencies exist."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Task 1", "status": "open", "priority": "P2"}\n'
            '{"id": "test-002", "title": "Task 2", "status": "open", "priority": "P0"}\n'
            '{"id": "test-003", "title": "Task 3", "status": "in_progress"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        ready = backend.get_ready_tasks()

        # Only open tasks, sorted by priority (P0 first)
        assert len(ready) == 2
        assert ready[0].id == "test-002"  # P0
        assert ready[1].id == "test-001"  # P2

    def test_get_ready_tasks_with_dependencies(self, temp_dir):
        """Test that tasks with unclosed dependencies are not ready."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Task 1", "status": "open"}\n'
            '{"id": "test-002", "title": "Task 2", "status": "open", "depends_on": ["test-001"]}\n'
            '{"id": "test-003", "title": "Task 3", "status": "closed"}\n'
            '{"id": "test-004", "title": "Task 4", "status": "open", "depends_on": ["test-003"]}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
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
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Low", "status": "open", "priority": "P4"}\n'
            '{"id": "test-002", "title": "High", "status": "open", "priority": "P0"}\n'
            '{"id": "test-003", "title": "Med", "status": "open", "priority": "P2"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
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
        backend = JsonlBackend(project_dir=temp_dir)
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
        backend = JsonlBackend(project_dir=temp_dir)
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
        backend = JsonlBackend(project_dir=temp_dir)

        task1 = backend.create_task(title="Task 1")
        task2 = backend.create_task(title="Task 2")
        task3 = backend.create_task(title="Task 3")

        # IDs should be sequential
        assert task1.id.endswith("-001")
        assert task2.id.endswith("-002")
        assert task3.id.endswith("-003")

    def test_create_task_uses_prefix(self, temp_dir):
        """Test that created tasks use directory-based prefix."""
        project_dir = temp_dir / "myapp"
        project_dir.mkdir()

        backend = JsonlBackend(project_dir=project_dir)
        task = backend.create_task(title="Test")

        assert task.id.startswith("mya-")  # First 3 chars of "myapp"


# ==============================================================================
# Update Task Tests
# ==============================================================================


class TestUpdateTask:
    """Test updating task fields."""

    def test_update_task_status(self, temp_dir):
        """Test updating task status."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "test-001", "title": "Task", "status": "open"}\n')

        backend = JsonlBackend(project_dir=temp_dir)
        updated = backend.update_task("test-001", status=TaskStatus.IN_PROGRESS)

        assert updated.status == TaskStatus.IN_PROGRESS

        # Verify persisted
        saved = backend.get_task("test-001")
        assert saved.status == TaskStatus.IN_PROGRESS

    def test_update_task_multiple_fields(self, temp_dir):
        """Test updating multiple fields at once."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "test-001", "title": "Task", "status": "open"}\n')

        backend = JsonlBackend(project_dir=temp_dir)
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
        backend = JsonlBackend(project_dir=temp_dir)

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
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "test-001", "title": "Task", "status": "open"}\n')

        backend = JsonlBackend(project_dir=temp_dir)
        closed = backend.close_task("test-001")

        assert closed.status == TaskStatus.CLOSED
        assert closed.closed_at is not None

    def test_close_task_with_reason(self, temp_dir):
        """Test closing task with reason."""
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text('{"id": "test-001", "title": "Task", "status": "open"}\n')

        backend = JsonlBackend(project_dir=temp_dir)
        closed = backend.close_task("test-001", reason="Completed successfully")

        assert "Completed successfully" in closed.notes

    def test_close_task_not_found(self, temp_dir):
        """Test closing non-existent task raises ValueError."""
        backend = JsonlBackend(project_dir=temp_dir)

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
        cub_dir = temp_dir / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.write_text(
            '{"id": "test-001", "title": "Open 1", "status": "open"}\n'
            '{"id": "test-002", "title": "Open 2", "status": "open"}\n'
            '{"id": "test-003", "title": "In Progress", "status": "in_progress"}\n'
            '{"id": "test-004", "title": "Closed 1", "status": "closed"}\n'
            '{"id": "test-005", "title": "Closed 2", "status": "closed"}\n'
        )

        backend = JsonlBackend(project_dir=temp_dir)
        counts = backend.get_task_counts()

        assert counts.total == 5
        assert counts.open == 2
        assert counts.in_progress == 1
        assert counts.closed == 2
        assert counts.remaining == 3  # open + in_progress
        assert counts.completion_percentage == 40.0  # 2/5 closed

    def test_get_task_counts_empty(self, temp_dir):
        """Test counts for empty task list."""
        backend = JsonlBackend(project_dir=temp_dir)
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

        backend = JsonlBackend(project_dir=temp_dir)

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

        # Verify saved to file
        saved_task = backend.get_task(imported[0].id)
        assert saved_task is not None
        assert saved_task.title == "Imported Task"

    def test_import_multiple_tasks(self, temp_dir):
        """Test importing multiple tasks at once."""
        from cub.core.tasks.models import Task

        backend = JsonlBackend(project_dir=temp_dir)

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

        # All should be saved
        all_tasks = backend.list_tasks()
        assert len(all_tasks) == 3

    def test_import_tasks_preserves_explicit_id(self, temp_dir):
        """Test that imported tasks preserve their explicit IDs."""
        from cub.core.tasks.models import Task

        backend = JsonlBackend(project_dir=temp_dir)

        # Task with explicit ID should keep it
        task_to_import = Task(id="custom-001", title="Test Task")
        imported = backend.import_tasks([task_to_import])

        assert imported[0].id == "custom-001"

    def test_import_tasks_rejects_duplicate_ids(self, temp_dir):
        """Test that importing tasks with duplicate IDs raises error."""
        from cub.core.tasks.models import Task

        backend = JsonlBackend(project_dir=temp_dir)

        # Create initial task
        backend.create_task(title="Existing")
        existing = backend.list_tasks()[0]

        # Try to import a task with the same ID
        tasks_to_import = [Task(id=existing.id, title="Duplicate Task")]

        with pytest.raises(ValueError, match="already exists"):
            backend.import_tasks(tasks_to_import)


# ==============================================================================
# Backend Protocol Tests
# ==============================================================================


class TestBackendProtocol:
    """Test backend protocol compliance."""

    def test_backend_name(self, temp_dir):
        """Test backend_name property."""
        backend = JsonlBackend(project_dir=temp_dir)
        assert backend.backend_name == "jsonl"

    def test_get_agent_instructions(self, temp_dir):
        """Test agent instructions generation."""
        backend = JsonlBackend(project_dir=temp_dir)
        instructions = backend.get_agent_instructions("test-001")

        assert "test-001" in instructions
        assert "tasks.jsonl" in instructions
        assert "status" in instructions

    def test_bind_branch_not_supported(self, temp_dir):
        """Test that branch binding is not supported."""
        backend = JsonlBackend(project_dir=temp_dir)
        result = backend.bind_branch("epic-001", "feature-branch")

        assert result is False
