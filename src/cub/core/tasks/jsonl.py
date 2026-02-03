"""
JSONL file backend implementation (tasks.jsonl).

This backend reads and writes tasks from a tasks.jsonl file using the
beads-compatible JSONL format (one JSON object per line). Provides full
CRUD operations with atomic file writes.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None

from .backend import TaskBackendDefaults, register_backend
from .models import Task, TaskCounts, TaskPriority, TaskStatus


class TasksFileNotFoundError(Exception):
    """Raised when tasks.jsonl file is not found."""

    pass


class TasksFileCorruptedError(Exception):
    """Raised when tasks.jsonl file is malformed."""

    def __init__(self, message: str, line_num: int | None = None):
        self.line_num = line_num
        # Add helpful hint about cub doctor
        hint = "\n\nRun 'cub doctor --fix' to attempt automatic repair."
        super().__init__(message + hint)


@register_backend("jsonl")
class JsonlBackend(TaskBackendDefaults):
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
            # Check for prd.json to migrate
            prd_file = self.project_dir / "prd.json"
            if prd_file.exists():
                self._migrate_from_prd_json(prd_file)
                # After migration, file should exist, so continue loading
            else:
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
                                f"Line {line_num}: expected JSON object, got {type_name}",
                                line_num=line_num,
                            )
                        tasks.append(task_data)
                    except json.JSONDecodeError as e:
                        raise TasksFileCorruptedError(
                            f"Line {line_num}: invalid JSON - {e}",
                            line_num=line_num,
                        ) from e
        except OSError as e:
            raise TasksFileNotFoundError(f"Failed to read {self.tasks_file}: {e}") from e

        # Update cache
        self._cache = tasks
        self._cache_mtime = current_mtime

        return tasks

    def repair_corrupted_file(self) -> tuple[bool, str, int]:
        """
        Attempt to repair a corrupted tasks.jsonl file.

        This method handles the most common corruption case: JSON objects that
        have been split across multiple lines (e.g., when \\n escape sequences
        were converted to actual newlines by an editor or copy-paste).

        The repair process:
        1. Creates a backup of the corrupted file (.jsonl.bak)
        2. Reads the file and attempts to rejoin split lines
        3. Validates each repaired JSON object
        4. Writes the repaired file

        Returns:
            Tuple of (success: bool, message: str, tasks_recovered: int)
        """
        if not self.tasks_file.exists():
            return False, "Tasks file does not exist", 0

        # Create backup
        backup_path = self.tasks_file.with_suffix(".jsonl.bak")
        try:
            shutil.copy2(self.tasks_file, backup_path)
        except OSError as e:
            return False, f"Failed to create backup: {e}", 0

        # Read all lines
        try:
            with open(self.tasks_file, encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            return False, f"Failed to read tasks file: {e}", 0

        # Attempt to repair by joining fragmented lines
        repaired_tasks: list[dict[str, Any]] = []
        current_fragment = ""
        line_num = 0
        errors: list[str] = []

        for line in lines:
            line_num += 1
            stripped = line.rstrip("\n\r")

            # Add to current fragment (empty lines become escaped newlines too)
            if current_fragment:
                # Join with escaped newline (this is the key repair)
                # Empty lines become double newlines in the content
                current_fragment += "\\n" + stripped
            else:
                if not stripped:
                    # Skip leading empty lines
                    continue
                current_fragment = stripped

            # Try to parse the current fragment
            try:
                task_data = json.loads(current_fragment)
                if isinstance(task_data, dict):
                    repaired_tasks.append(task_data)
                    current_fragment = ""
                else:
                    # Valid JSON but not an object - error
                    type_name = type(task_data).__name__
                    errors.append(f"Line {line_num}: parsed as {type_name}, not object")
                    current_fragment = ""
            except json.JSONDecodeError:
                # Not valid yet - might need more lines
                # Check if it looks like we're accumulating too much
                if current_fragment.count("\\n") > 100:
                    errors.append(f"Line {line_num}: fragment too long, likely unrecoverable")
                    current_fragment = ""

        # Handle any remaining fragment
        if current_fragment:
            errors.append("File ended with incomplete JSON fragment")

        if not repaired_tasks:
            return False, f"No tasks could be recovered. Errors: {'; '.join(errors)}", 0

        # Save repaired file
        try:
            self._save_tasks(repaired_tasks)
        except Exception as e:
            return False, f"Failed to save repaired file: {e}", 0

        # Invalidate cache
        self._cache = None
        self._cache_mtime = None

        msg = f"Recovered {len(repaired_tasks)} task(s). Backup saved to {backup_path.name}"
        if errors:
            msg += f". Warnings: {'; '.join(errors[:3])}"
            if len(errors) > 3:
                msg += f" (+{len(errors) - 3} more)"

        return True, msg, len(repaired_tasks)

    def validate_file(self) -> tuple[bool, str | None]:
        """
        Validate the tasks.jsonl file without loading into cache.

        Returns:
            Tuple of (is_valid: bool, error_message: str | None)
        """
        if not self.tasks_file.exists():
            return True, None  # Non-existent file is valid (will be created)

        try:
            with open(self.tasks_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        task_data = json.loads(line)
                        if not isinstance(task_data, dict):
                            type_name = type(task_data).__name__
                            return False, f"Line {line_num}: expected JSON object, got {type_name}"
                    except json.JSONDecodeError as e:
                        return False, f"Line {line_num}: invalid JSON - {e}"
            return True, None
        except OSError as e:
            return False, f"Failed to read file: {e}"

    def _migrate_from_prd_json(self, prd_file: Path) -> None:
        """
        Migrate tasks from old prd.json format to tasks.jsonl.

        Reads the JSON array format from prd.json, converts field names
        to match the beads-compatible schema, and writes to tasks.jsonl.
        Creates a backup of the original prd.json as prd.json.bak.

        Args:
            prd_file: Path to prd.json file to migrate

        Raises:
            TasksFileCorruptedError: If prd.json is invalid
        """
        try:
            with open(prd_file, encoding="utf-8") as f:
                prd_data = json.load(f)
        except json.JSONDecodeError as e:
            raise TasksFileCorruptedError(f"Failed to parse {prd_file}: {e}") from e
        except OSError as e:
            raise TasksFileNotFoundError(f"Failed to read {prd_file}: {e}") from e

        if not isinstance(prd_data, dict):
            raise TasksFileCorruptedError("prd.json must be a JSON object")

        # Extract tasks array
        tasks_array = prd_data.get("tasks", [])

        # Convert tasks to JSONL format
        migrated_tasks = []
        for task_data in tasks_array:
            if not isinstance(task_data, dict):
                continue

            # Create a copy to avoid mutating the original
            converted_task = dict(task_data)

            # Map old field names to new ones
            # - "type" -> "issue_type" (handled by Pydantic alias)
            # - "dependsOn" -> "depends_on" (handled by Pydantic alias)
            # Note: The Task model already handles these aliases via populate_by_name=True
            # So we can keep the original field names and they'll be parsed correctly

            migrated_tasks.append(converted_task)

        # Backup original prd.json
        backup_file = prd_file.parent / f"{prd_file.name}.bak"
        try:
            shutil.copy2(prd_file, backup_file)
        except OSError:
            # If backup fails, continue anyway
            pass

        # Save to tasks.jsonl
        self._save_tasks(migrated_tasks)

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
        Save tasks.jsonl file atomically with validation.

        Uses a temporary file and atomic rename to prevent corruption
        on write failures. Validates the written file before committing
        to catch any serialization issues.

        Args:
            tasks: List of task dictionaries to save

        Raises:
            TasksFileCorruptedError: If the written file fails validation
        """
        # Ensure .cub directory exists
        self.cub_dir.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first
        fd, temp_path = tempfile.mkstemp(dir=self.cub_dir, prefix=".tasks_", suffix=".jsonl.tmp")
        temp_path_obj = Path(temp_path)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for task in tasks:
                    # Use compact separators to ensure single-line output
                    json.dump(task, f, ensure_ascii=False, separators=(",", ":"))
                    f.write("\n")

            # Validate the temp file before committing
            self._validate_written_file(temp_path_obj, len(tasks))

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

    def _validate_written_file(self, file_path: Path, expected_count: int) -> None:
        """
        Validate a written JSONL file before committing.

        Args:
            file_path: Path to the file to validate
            expected_count: Expected number of task objects

        Raises:
            TasksFileCorruptedError: If validation fails
        """
        actual_count = 0
        try:
            with open(file_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        task_data = json.loads(line)
                        if not isinstance(task_data, dict):
                            raise TasksFileCorruptedError(
                                f"Write validation failed: line {line_num} is not a JSON object",
                                line_num=line_num,
                            )
                        actual_count += 1
                    except json.JSONDecodeError as e:
                        raise TasksFileCorruptedError(
                            f"Write validation failed: line {line_num} has invalid JSON - {e}",
                            line_num=line_num,
                        ) from e
        except OSError as e:
            raise TasksFileCorruptedError(
                f"Write validation failed: could not read file - {e}"
            ) from e

        if actual_count != expected_count:
            raise TasksFileCorruptedError(
                f"Write validation failed: expected {expected_count} tasks, got {actual_count}"
            )

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
        title: str | None = None,
        priority: int | None = None,
        notes: str | None = None,
    ) -> Task:
        """
        Update a task's fields.

        Args:
            task_id: Task to update
            status: New status
            assignee: New assignee
            description: New description
            labels: New labels list
            title: New title
            priority: New priority (0-4, where 0 is highest)
            notes: New notes/comments

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
        if title is not None:
            task.title = title
        if priority is not None:
            task.priority = TaskPriority(f"P{priority}")
        if notes is not None:
            task.notes = notes

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
            TaskCounts object with total, open, in_progress, closed, blocked counts
        """
        tasks = self._load_tasks()

        total = len(tasks)
        open_count = 0
        in_progress = 0
        closed = 0

        # Build set of closed task IDs for blocked count
        closed_ids = set()
        all_tasks = []

        for raw_task in tasks:
            status = raw_task.get("status", "open")
            if status == "open":
                open_count += 1
            elif status == "in_progress":
                in_progress += 1
            elif status == "closed":
                closed += 1

            # Parse task for dependency checking
            try:
                task = self._parse_task(raw_task)
                all_tasks.append(task)
                if task.status == TaskStatus.CLOSED:
                    closed_ids.add(task.id)
            except Exception:
                continue

        # Count blocked tasks (open with unclosed dependencies)
        blocked_count = 0
        for task in all_tasks:
            if task.status == TaskStatus.OPEN and task.depends_on:
                # Check if any dependency is not closed
                if not all(dep_id in closed_ids for dep_id in task.depends_on):
                    blocked_count += 1

        return TaskCounts(
            total=total,
            open=open_count,
            in_progress=in_progress,
            closed=closed,
            blocked=blocked_count,
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
        Bind a git branch to an epic using the branch store.

        Creates an association between a git branch and an epic, stored in
        .cub/branches.yaml. Uses the same format as beads for compatibility.

        Args:
            epic_id: Epic ID to bind
            branch_name: Git branch name
            base_branch: Base branch for merging

        Returns:
            True if binding was created, False if binding already exists
        """
        if yaml is None:
            # YAML support not available - can't create bindings
            return False

        # Read existing bindings
        bindings = self._read_branch_bindings()

        # Check if epic or branch is already bound
        for binding in bindings:
            if binding.get("epic_id") == epic_id:
                return False
            if binding.get("branch_name") == branch_name:
                return False

        # Create new binding
        now = datetime.now()
        new_binding = {
            "epic_id": epic_id,
            "branch_name": branch_name,
            "base_branch": base_branch,
            "status": "active",
            "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pr_number": None,
            "merged": False,
        }

        bindings.append(new_binding)

        # Save bindings atomically
        self._save_branch_bindings(bindings)

        return True

    def _read_branch_bindings(self) -> list[dict[str, Any]]:
        """
        Read branch bindings from .cub/branches.yaml.

        Returns:
            List of branch binding dictionaries
        """
        branches_file = self.cub_dir / "branches.yaml"

        if not branches_file.exists():
            return []

        try:
            content = branches_file.read_text()
            data = yaml.safe_load(content) or {}
            bindings = data.get("bindings", [])
            if isinstance(bindings, list):
                return bindings
            return []
        except Exception:
            # If YAML parsing fails, return empty list
            return []

    def _save_branch_bindings(self, bindings: list[dict[str, Any]]) -> None:
        """
        Save branch bindings to .cub/branches.yaml atomically.

        Args:
            bindings: List of branch binding dictionaries
        """
        # Ensure .cub directory exists
        self.cub_dir.mkdir(parents=True, exist_ok=True)

        branches_file = self.cub_dir / "branches.yaml"

        # Build YAML content
        header = """# Branch-Epic Bindings
# Managed by cub - do not edit manually
# Format: YAML with branch bindings array

"""
        data = {"bindings": bindings}

        # Use temporary file for atomic write
        fd, temp_path = tempfile.mkstemp(dir=self.cub_dir, prefix=".branches_", suffix=".yaml.tmp")

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(header)
                yaml_str = yaml.dump(
                    data,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
                f.write(yaml_str)

            # Atomic rename
            os.replace(temp_path, branches_file)

        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def add_dependency(self, task_id: str, depends_on_id: str) -> Task:
        """
        Add a dependency to a task.

        Args:
            task_id: Task to add dependency to
            depends_on_id: Task ID that must be completed first

        Returns:
            Updated task object with new dependency

        Raises:
            ValueError: If either task not found
        """
        # Get the task
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Verify dependency task exists
        depends_on_task = self.get_task(depends_on_id)
        if depends_on_task is None:
            raise ValueError(f"Dependency task {depends_on_id} not found")

        # Add dependency if not already present
        if depends_on_id not in task.depends_on:
            task.depends_on.append(depends_on_id)

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

    def remove_dependency(self, task_id: str, depends_on_id: str) -> Task:
        """
        Remove a dependency from a task.

        Args:
            task_id: Task to remove dependency from
            depends_on_id: Task ID to remove from dependencies

        Returns:
            Updated task object without the dependency

        Raises:
            ValueError: If task not found or dependency doesn't exist
        """
        # Get the task
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Check dependency exists
        if depends_on_id not in task.depends_on:
            raise ValueError(f"Task {task_id} does not depend on {depends_on_id}")

        # Remove dependency
        task.depends_on.remove(depends_on_id)

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

    def reopen_task(self, task_id: str, reason: str | None = None) -> Task:
        """
        Reopen a closed task.

        Args:
            task_id: Task to reopen
            reason: Optional reason for reopening

        Returns:
            Reopened task object

        Raises:
            ValueError: If task not found or not closed
        """
        # Get the task
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        if task.status != TaskStatus.CLOSED:
            raise ValueError(f"Task {task_id} is not closed (status: {task.status})")

        # Reopen the task using model method
        task.reopen()

        # Add note if reason provided
        if reason:
            if task.notes:
                task.notes += f"\n\n[Reopened: {datetime.now().isoformat()}] {reason}"
            else:
                task.notes = f"[Reopened: {datetime.now().isoformat()}] {reason}"

        # Update in file
        tasks = self._load_tasks()
        for i, raw_task in enumerate(tasks):
            if raw_task.get("id") == task_id:
                tasks[i] = self._task_to_dict(task)
                break

        self._save_tasks(tasks)

        return task

    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task permanently.

        WARNING: This is destructive and cannot be undone.

        Args:
            task_id: Task to delete

        Returns:
            True if task was deleted, False if not found

        Raises:
            ValueError: If task has dependents (other tasks depend on it)
        """
        tasks = self._load_tasks()

        # Check if any task depends on this task
        for raw_task in tasks:
            # Skip the task we're trying to delete
            if raw_task.get("id") == task_id:
                continue

            # Check dependencies
            depends_on = raw_task.get("depends_on", [])
            if task_id in depends_on:
                raise ValueError(
                    f"Cannot delete task {task_id}: task {raw_task.get('id')} depends on it"
                )

        # Find and remove the task
        task_index = None
        for i, raw_task in enumerate(tasks):
            if raw_task.get("id") == task_id:
                task_index = i
                break

        if task_index is None:
            return False

        # Remove task from list
        tasks.pop(task_index)

        # Save atomically
        self._save_tasks(tasks)

        return True

    def add_label(self, task_id: str, label: str) -> Task:
        """
        Add a label to a task.

        Args:
            task_id: Task to add label to
            label: Label to add

        Returns:
            Updated task object with new label

        Raises:
            ValueError: If task not found
        """
        # Get the task
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Add label using model method
        task.add_label(label)

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

    def remove_label(self, task_id: str, label: str) -> Task:
        """
        Remove a label from a task.

        Args:
            task_id: Task to remove label from
            label: Label to remove

        Returns:
            Updated task object without the label

        Raises:
            ValueError: If task not found or label doesn't exist
        """
        # Get the task
        task = self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Check label exists
        if label not in task.labels:
            raise ValueError(f"Label '{label}' not found on task {task_id}")

        # Remove label using model method
        task.remove_label(label)

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

    def search_tasks(self, query: str) -> list[Task]:
        """
        Search for tasks using case-insensitive substring matching.

        Searches across task titles and descriptions in memory using
        case-insensitive substring matching.

        Args:
            query: Search query string

        Returns:
            List of tasks matching the query

        Raises:
            ValueError: If search fails
        """
        all_tasks = self.list_tasks()
        query_lower = query.lower()

        matching_tasks = []
        for task in all_tasks:
            # Search in title
            if query_lower in task.title.lower():
                matching_tasks.append(task)
                continue

            # Search in description
            if task.description and query_lower in task.description.lower():
                matching_tasks.append(task)
                continue

        return matching_tasks
