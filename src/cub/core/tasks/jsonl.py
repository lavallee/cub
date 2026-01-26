"""
JSONL file backend implementation (tasks.jsonl).

This backend reads and writes tasks from a tasks.jsonl file using the
beads-compatible JSONL format (one JSON object per line). Provides full
CRUD operations with atomic file writes.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .backend import register_backend
from .models import Task, TaskCounts, TaskStatus


class TasksFileNotFoundError(Exception):
    """Raised when tasks.jsonl file is not found."""

    pass


class TasksFileCorruptedError(Exception):
    """Raised when tasks.jsonl file is malformed."""

    pass


@register_backend("jsonl")
class JsonlBackend:
    """
    Task backend that uses a tasks.jsonl file for storage.

    This backend provides task management using the beads-compatible JSONL
    format where each line is a complete JSON object representing a task.
    All tasks are stored in a single JSONL file with atomic writes to
    prevent corruption.

    File format:
        Each line is a JSON object representing one task:
        {"id": "task-id", "title": "Task title", "status": "open", ...}
        {"id": "task-id-2", "title": "Another task", "status": "closed", ...}

    Example:
        >>> backend = JsonlBackend()
        >>> tasks = backend.list_tasks(status=TaskStatus.OPEN)
        >>> task = backend.get_task("cub-001")
    """

    def __init__(self, project_dir: Path | None = None):
        """
        Initialize the JSONL backend.

        Args:
            project_dir: Project directory (defaults to current directory)
        """
        self.project_dir = project_dir or Path.cwd()
        self.cub_dir = self.project_dir / ".cub"
        self.tasks_file = self.cub_dir / "tasks.jsonl"

        # Cache for loaded data to avoid re-parsing on every call
        self._cache: list[dict[str, Any]] | None = None
        self._cache_mtime: float | None = None

    def _load_tasks(self) -> list[dict[str, Any]]:
        """
        Load and parse tasks.jsonl file with caching.

        Returns:
            List of task dictionaries (one per line)

        Raises:
            TasksFileNotFoundError: If tasks.jsonl doesn't exist
            TasksFileCorruptedError: If JSONL is invalid
        """
        # Check if file exists
        if not self.tasks_file.exists():
            # Create empty tasks.jsonl if it doesn't exist
            self._create_empty_tasks_file()
            return []

        # Check cache validity
        current_mtime = os.path.getmtime(self.tasks_file)
        if self._cache is not None and self._cache_mtime == current_mtime:
            return self._cache

        # Load and parse file
        tasks: list[dict[str, Any]] = []
        try:
            with open(self.tasks_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        # Skip empty lines
                        continue
                    try:
                        task_data = json.loads(line)
                        if not isinstance(task_data, dict):
                            type_name = type(task_data).__name__
                            raise TasksFileCorruptedError(
                                f"Line {line_num}: expected JSON object, got {type_name}"
                            )
                        tasks.append(task_data)
                    except json.JSONDecodeError as e:
                        raise TasksFileCorruptedError(f"Line {line_num}: invalid JSON - {e}") from e
        except OSError as e:
            raise TasksFileNotFoundError(f"Failed to read {self.tasks_file}: {e}") from e

        # Update cache
        self._cache = tasks
        self._cache_mtime = current_mtime

        return tasks

    def _create_empty_tasks_file(self) -> None:
        """Create an empty tasks.jsonl file with .cub directory."""
        # Ensure .cub directory exists
        self.cub_dir.mkdir(parents=True, exist_ok=True)

        # Create empty file
        self.tasks_file.touch(exist_ok=True)

        # Initialize cache
        self._cache = []
        self._cache_mtime = os.path.getmtime(self.tasks_file)

    def _save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        """
        Save tasks.jsonl file atomically.

        Uses a temporary file and atomic rename to prevent corruption
        on write failures.

        Args:
            tasks: List of task dictionaries to save
        """
        # Ensure .cub directory exists
        self.cub_dir.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first
        fd, temp_path = tempfile.mkstemp(dir=self.cub_dir, prefix=".tasks_", suffix=".jsonl.tmp")

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for task in tasks:
                    json.dump(task, f, ensure_ascii=False)
                    f.write("\n")

            # Atomic rename (replaces existing file)
            os.replace(temp_path, self.tasks_file)

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
            raw_task: Raw task dictionary from JSONL

        Returns:
            Validated Task object
        """
        return Task(**raw_task)

    def _task_to_dict(self, task: Task, preserve_unknown: bool = True) -> dict[str, Any]:
        """
        Convert Task model to dict for JSONL serialization.

        Args:
            task: Task object to serialize
            preserve_unknown: If True, preserve fields not in Task model

        Returns:
            Dictionary suitable for JSONL serialization
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
        raw_tasks = self._load_tasks()
        tasks = []

        for raw_task in raw_tasks:
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
        raw_tasks = self._load_tasks()

        for raw_task in raw_tasks:
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
        raw_tasks = self._load_tasks()

        # Build set of closed task IDs for dependency checking
        closed_ids = set()
        all_tasks = []

        for raw_task in raw_tasks:
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
        tasks = self._load_tasks()

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
        self._save_tasks(tasks)

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
        tasks = self._load_tasks()

        for i, raw_task in enumerate(tasks):
            if raw_task.get("id") == task_id:
                tasks[i] = self._task_to_dict(task)
                break

        self._save_tasks(tasks)

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
        tasks = self._load_tasks()

        # Generate task ID
        prefix = self._get_prefix()
        existing_ids = {t.get("id", "") for t in tasks}

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
        tasks.append(self._task_to_dict(task))

        # Save atomically
        self._save_tasks(tasks)

        return task

    def _get_prefix(self) -> str:
        """
        Get the task ID prefix for this project.

        Uses the first 3 letters of the project directory name,
        defaulting to "cub" if the name is too short.

        Returns:
            Task ID prefix (e.g., "cub", "myp")
        """
        prefix = self.project_dir.name[:3].lower()
        return prefix if prefix else "cub"

    def get_task_counts(self) -> TaskCounts:
        """
        Get count statistics for tasks.

        Returns:
            TaskCounts object with total, open, in_progress, closed counts
        """
        tasks = self._load_tasks()

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
        tasks = self._load_tasks()

        for i, raw_task in enumerate(tasks):
            if raw_task.get("id") == task_id:
                tasks[i] = self._task_to_dict(task)
                break

        self._save_tasks(tasks)

        return task

    def import_tasks(self, tasks: list[Task]) -> list[Task]:
        """
        Bulk import tasks, preserving explicit IDs.

        This method enables efficient bulk import of multiple tasks at once
        with a single file write for better performance. If a task has an
        explicit ID, it is preserved; otherwise a new ID is generated.

        Args:
            tasks: List of Task objects to import

        Returns:
            List of imported Task objects

        Raises:
            ValueError: If import fails or duplicate IDs detected
        """
        existing_tasks = self._load_tasks()
        prefix = self._get_prefix()
        existing_ids = {t.get("id", "") for t in existing_tasks}

        # Find starting task number for any tasks without explicit IDs
        task_num = 1
        while f"{prefix}-{task_num:03d}" in existing_ids:
            task_num += 1

        imported_tasks: list[Task] = []

        for task in tasks:
            # Use explicit ID if provided, otherwise generate one
            if task.id:
                task_id = task.id
                if task_id in existing_ids:
                    raise ValueError(
                        f"Task ID '{task_id}' already exists. Cannot import duplicate IDs."
                    )
            else:
                task_id = f"{prefix}-{task_num:03d}"
                task_num += 1

            existing_ids.add(task_id)

            # Create new task preserving all fields from source
            new_task = Task(
                id=task_id,
                title=task.title,
                description=task.description,
                type=task.type,
                priority=task.priority,
                labels=task.labels if task.labels else [],
                depends_on=task.depends_on if task.depends_on else [],
                parent=task.parent,
                blocks=task.blocks if task.blocks else [],
                status=task.status,
                assignee=task.assignee,
                acceptance_criteria=(task.acceptance_criteria if task.acceptance_criteria else []),
                notes=task.notes if task.notes else "",
                created_at=task.created_at or datetime.now(),
                updated_at=datetime.now(),
            )

            existing_tasks.append(self._task_to_dict(new_task))
            imported_tasks.append(new_task)

        # Save atomically (single file write for efficiency)
        self._save_tasks(existing_tasks)

        return imported_tasks

    @property
    def backend_name(self) -> str:
        """Get the name of this backend."""
        return "jsonl"

    def get_agent_instructions(self, task_id: str) -> str:
        """
        Get instructions for an AI agent on how to interact with JSONL backend.

        Args:
            task_id: The current task ID for context

        Returns:
            Multiline string with agent instructions
        """
        return f"""This project uses the JSONL task backend (.cub/tasks.jsonl).

**Task lifecycle:**
1. Read `.cub/tasks.jsonl` to view task details (one JSON object per line)
2. Update the line for task `{task_id}` with `"status": "in_progress"` when starting
3. Update the line for task `{task_id}` with `"status": "closed"` when complete

**File structure:**
Each line is a complete JSON object:
```jsonl
{{"id": "{task_id}", "status": "open|in_progress|closed", ...}}
{{"id": "another-task", "status": "closed", ...}}
```

**Important:** Always run feedback loops (tests, typecheck, lint) BEFORE marking the task closed."""

    def bind_branch(
        self,
        epic_id: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> bool:
        """
        Bind a git branch to an epic.

        The JSONL backend doesn't have native branch binding support.
        This is a no-op that returns False.

        Args:
            epic_id: Epic ID to bind
            branch_name: Git branch name
            base_branch: Base branch for merging

        Returns:
            False (branch binding not supported in JSONL backend)
        """
        # JSONL backend doesn't support branch bindings
        # Could optionally store in task metadata in the future
        return False

    def try_close_epic(self, epic_id: str) -> tuple[bool, str]:
        """
        Attempt to close an epic if all its tasks are complete.

        Checks all tasks belonging to the epic and closes the epic if
        all tasks have status CLOSED.

        Args:
            epic_id: The epic ID to potentially close

        Returns:
            Tuple of (closed: bool, message: str)
        """
        # First, check if the epic exists and get its current status
        epic = self.get_task(epic_id)
        if epic is None:
            return False, f"Epic '{epic_id}' not found"

        if epic.status == TaskStatus.CLOSED:
            return False, f"Epic '{epic_id}' is already closed"

        # Get all tasks that belong to this epic (using parent filter)
        tasks_by_parent = self.list_tasks(parent=epic_id)

        # Also check for tasks that have the epic ID as a label
        all_tasks = self.list_tasks()
        tasks_by_label = [t for t in all_tasks if t.has_label(epic_id) and t.id != epic_id]

        # Combine and deduplicate
        seen_ids: set[str] = set()
        all_epic_tasks: list[Task] = []
        for task in tasks_by_parent + tasks_by_label:
            if task.id not in seen_ids and task.id != epic_id:
                seen_ids.add(task.id)
                all_epic_tasks.append(task)

        if not all_epic_tasks:
            return False, f"No tasks found for epic '{epic_id}'"

        # Check status of all tasks
        open_count = 0
        in_progress_count = 0
        closed_count = 0

        for task in all_epic_tasks:
            if task.status == TaskStatus.CLOSED:
                closed_count += 1
            elif task.status == TaskStatus.IN_PROGRESS:
                in_progress_count += 1
            else:
                open_count += 1

        # If any tasks are not closed, don't close the epic
        if open_count > 0 or in_progress_count > 0:
            return False, (
                f"Epic '{epic_id}' has {open_count} open and "
                f"{in_progress_count} in-progress tasks remaining "
                f"({closed_count} closed)"
            )

        # All tasks are closed - close the epic
        try:
            self.close_task(epic_id, reason="All tasks completed")
            return True, f"Epic '{epic_id}' auto-closed ({closed_count} tasks completed)"
        except ValueError as e:
            return False, f"Failed to close epic '{epic_id}': {e}"
