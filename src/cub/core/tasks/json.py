"""
JSON file backend implementation (prd.json).

This backend reads and writes tasks from a prd.json file for projects
not using beads. Provides full CRUD operations with atomic file writes.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .backend import register_backend
from .models import Task, TaskCounts, TaskStatus


class PrdFileNotFoundError(Exception):
    """Raised when prd.json file is not found."""

    pass


class PrdFileCorruptedError(Exception):
    """Raised when prd.json file is malformed."""

    pass


@register_backend("json")
class JsonBackend:
    """
    Task backend that uses a prd.json file for storage.

    This backend provides task management for projects not using beads.
    All tasks are stored in a single JSON file with atomic writes to
    prevent corruption.

    File format:
        {
            "prefix": "project-id",
            "tasks": [
                {
                    "id": "task-id",
                    "title": "Task title",
                    "status": "open",
                    ...
                }
            ]
        }

    Example:
        >>> backend = JsonBackend()
        >>> tasks = backend.list_tasks(status=TaskStatus.OPEN)
        >>> task = backend.get_task("prd-001")
    """

    def __init__(self, project_dir: Path | None = None, prd_file: Path | None = None):
        """
        Initialize the JSON backend.

        Args:
            project_dir: Project directory (defaults to current directory)
            prd_file: Explicit path to prd.json (overrides project_dir)
        """
        self.project_dir = project_dir or Path.cwd()

        if prd_file:
            self.prd_file = Path(prd_file)
        else:
            self.prd_file = self.project_dir / "prd.json"

        # Cache for loaded data to avoid re-parsing on every call
        self._cache: dict[str, Any] | None = None
        self._cache_mtime: float | None = None

    def _load_prd(self) -> dict[str, Any]:
        """
        Load and parse prd.json file with caching.

        Returns:
            Parsed JSON data with 'prefix' and 'tasks' keys

        Raises:
            PrdFileNotFoundError: If prd.json doesn't exist
            PrdFileCorruptedError: If JSON is invalid
        """
        # Check if file exists
        if not self.prd_file.exists():
            # Create empty prd.json if it doesn't exist
            self._create_empty_prd()

        # Check cache validity
        current_mtime = os.path.getmtime(self.prd_file)
        if self._cache is not None and self._cache_mtime == current_mtime:
            return self._cache

        # Load and parse file
        try:
            with open(self.prd_file, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise PrdFileCorruptedError(f"Failed to parse {self.prd_file}: {e}") from e
        except OSError as e:
            raise PrdFileNotFoundError(f"Failed to read {self.prd_file}: {e}") from e

        # Validate structure
        if not isinstance(data, dict):
            raise PrdFileCorruptedError("prd.json must be a JSON object")
        if "tasks" not in data:
            data["tasks"] = []

        # Update cache
        self._cache = data
        self._cache_mtime = current_mtime

        return data

    def _create_empty_prd(self) -> None:
        """Create an empty prd.json file with default structure."""
        # Generate prefix from directory name
        prefix = self.project_dir.name[:3].lower() or "prd"

        empty_prd = {"prefix": prefix, "tasks": []}

        self._save_prd(empty_prd)

    def _save_prd(self, data: dict[str, Any]) -> None:
        """
        Save prd.json file atomically.

        Uses a temporary file and atomic rename to prevent corruption
        on write failures.

        Args:
            data: Complete prd.json data structure to save
        """
        # Write to temporary file first
        fd, temp_path = tempfile.mkstemp(
            dir=self.prd_file.parent, prefix=".prd_", suffix=".json.tmp"
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")  # Add trailing newline

            # Atomic rename (replaces existing file)
            os.replace(temp_path, self.prd_file)

            # Invalidate cache
            self._cache = None
            self._cache_mtime = None

        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _parse_task(self, raw_task: dict[str, Any]) -> Task:
        """
        Parse a raw task dict into a Task model.

        Args:
            raw_task: Raw task dictionary from JSON

        Returns:
            Validated Task object
        """
        return Task(**raw_task)

    def _task_to_dict(self, task: Task, preserve_unknown: bool = True) -> dict[str, Any]:
        """
        Convert Task model to dict for JSON serialization.

        Args:
            task: Task object to serialize
            preserve_unknown: If True, preserve fields not in Task model

        Returns:
            Dictionary suitable for JSON serialization
        """
        # Use Pydantic's serialization with aliases and JSON mode
        return task.model_dump(by_alias=True, exclude_none=False, mode="json")

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """
        List all tasks, optionally filtered.

        Args:
            status: Filter by task status (open, in_progress, closed)
            parent: Filter by parent epic/task ID
            label: Filter by label (tasks with this label)

        Returns:
            List of tasks matching the filter criteria
        """
        data = self._load_prd()
        tasks = []

        for raw_task in data.get("tasks", []):
            # Parse task
            try:
                task = self._parse_task(raw_task)
            except Exception:
                # Skip invalid tasks
                continue

            # Apply filters
            if status is not None and task.status != status:
                continue
            if parent is not None and task.parent != parent:
                continue
            if label is not None and not task.has_label(label):
                continue

            tasks.append(task)

        return tasks

    def get_task(self, task_id: str) -> Task | None:
        """
        Get a specific task by ID.

        Args:
            task_id: Unique task identifier

        Returns:
            Task object if found, None otherwise
        """
        data = self._load_prd()

        for raw_task in data.get("tasks", []):
            if raw_task.get("id") == task_id:
                try:
                    return self._parse_task(raw_task)
                except Exception:
                    return None

        return None

    def get_ready_tasks(
        self,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """
        Get all tasks that are ready to work on.

        A task is ready if:
        - Status is OPEN
        - All dependencies are CLOSED

        Tasks are returned sorted by priority (P0 first).

        Args:
            parent: Filter by parent epic/task ID
            label: Filter by label

        Returns:
            List of ready tasks sorted by priority
        """
        data = self._load_prd()

        # Build set of closed task IDs for dependency checking
        closed_ids = set()
        all_tasks = []

        for raw_task in data.get("tasks", []):
            try:
                task = self._parse_task(raw_task)
                all_tasks.append(task)
                if task.status == TaskStatus.CLOSED:
                    closed_ids.add(task.id)
            except Exception:
                continue

        # Filter for ready tasks
        ready_tasks = []
        for task in all_tasks:
            # Must be open
            if task.status != TaskStatus.OPEN:
                continue

            # All dependencies must be closed
            if task.depends_on:
                if not all(dep_id in closed_ids for dep_id in task.depends_on):
                    continue

            # Apply filters
            if parent is not None and task.parent != parent:
                continue
            if label is not None and not task.has_label(label):
                continue

            ready_tasks.append(task)

        # Sort by priority (P0 = 0 is highest priority)
        ready_tasks.sort(key=lambda t: t.priority_numeric)

        return ready_tasks

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        assignee: str | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
    ) -> Task:
        """
        Update a task's fields.

        Args:
            task_id: Task to update
            status: New status
            assignee: New assignee
            description: New description
            labels: New labels list

        Returns:
            Updated task object

        Raises:
            ValueError: If task not found or update fails
        """
        data = self._load_prd()
        tasks = data.get("tasks", [])

        # Find task index
        task_index = None
        for i, raw_task in enumerate(tasks):
            if raw_task.get("id") == task_id:
                task_index = i
                break

        if task_index is None:
            raise ValueError(f"Task {task_id} not found")

        # Parse task
        task = self._parse_task(tasks[task_index])

        # Update fields
        if status is not None:
            task.status = status
        if assignee is not None:
            task.assignee = assignee
        if description is not None:
            task.description = description
        if labels is not None:
            task.labels = labels

        # Update timestamp
        task.updated_at = datetime.now()

        # Convert back to dict and update in tasks array
        tasks[task_index] = self._task_to_dict(task)

        # Save atomically
        self._save_prd(data)

        return task

    def close_task(self, task_id: str, reason: str | None = None) -> Task:
        """
        Close a task.

        Marks the task as closed and optionally adds a closing note.

        Args:
            task_id: Task to close
            reason: Optional reason for closing

        Returns:
            Closed task object

        Raises:
            ValueError: If task not found or already closed
        """
        # Get current task
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Update task
        task.close()

        # Add reason as note if provided
        if reason:
            if task.notes:
                task.notes += f"\n\n[Closed: {datetime.now().isoformat()}] {reason}"
            else:
                task.notes = f"[Closed: {datetime.now().isoformat()}] {reason}"

        # Update in file
        data = self._load_prd()
        tasks = data.get("tasks", [])

        for i, raw_task in enumerate(tasks):
            if raw_task.get("id") == task_id:
                tasks[i] = self._task_to_dict(task)
                break

        self._save_prd(data)

        return task

    def create_task(
        self,
        title: str,
        description: str = "",
        task_type: str = "task",
        priority: int = 2,
        labels: list[str] | None = None,
        depends_on: list[str] | None = None,
        parent: str | None = None,
    ) -> Task:
        """
        Create a new task.

        Args:
            title: Task title
            description: Task description
            task_type: Task type (task, feature, bug, epic, gate)
            priority: Priority level (0-4, where 0 is highest)
            labels: Task labels
            depends_on: List of task IDs this task depends on
            parent: Parent epic/task ID

        Returns:
            Created task object

        Raises:
            ValueError: If task creation fails
        """
        data = self._load_prd()

        # Generate task ID
        prefix = data.get("prefix", "prd")
        existing_ids = {t.get("id", "") for t in data.get("tasks", [])}

        # Find next available numeric ID
        task_num = 1
        while True:
            task_id = f"{prefix}-{task_num:03d}"
            if task_id not in existing_ids:
                break
            task_num += 1

        # Create task object
        from .models import TaskPriority, TaskType

        task = Task(
            id=task_id,
            title=title,
            description=description,
            type=TaskType(task_type),
            priority=TaskPriority(f"P{priority}"),
            labels=labels or [],
            depends_on=depends_on or [],
            parent=parent,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Add to tasks array
        tasks = data.get("tasks", [])
        tasks.append(self._task_to_dict(task))
        data["tasks"] = tasks

        # Save atomically
        self._save_prd(data)

        return task

    def get_task_counts(self) -> TaskCounts:
        """
        Get count statistics for tasks.

        Returns:
            TaskCounts object with total, open, in_progress, closed counts
        """
        data = self._load_prd()
        tasks = data.get("tasks", [])

        total = len(tasks)
        open_count = 0
        in_progress = 0
        closed = 0

        for raw_task in tasks:
            status = raw_task.get("status", "open")
            if status == "open":
                open_count += 1
            elif status == "in_progress":
                in_progress += 1
            elif status == "closed":
                closed += 1

        return TaskCounts(
            total=total,
            open=open_count,
            in_progress=in_progress,
            closed=closed,
        )

    def add_task_note(self, task_id: str, note: str) -> Task:
        """
        Add a note/comment to a task.

        Args:
            task_id: Task to add note to
            note: Note text to add

        Returns:
            Updated task object

        Raises:
            ValueError: If task not found
        """
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Append note with timestamp
        timestamp = datetime.now().isoformat()
        new_note = f"[{timestamp}] {note}"

        if task.notes:
            task.notes += f"\n{new_note}"
        else:
            task.notes = new_note

        # Update timestamp
        task.updated_at = datetime.now()

        # Update in file
        data = self._load_prd()
        tasks = data.get("tasks", [])

        for i, raw_task in enumerate(tasks):
            if raw_task.get("id") == task_id:
                tasks[i] = self._task_to_dict(task)
                break

        self._save_prd(data)

        return task
