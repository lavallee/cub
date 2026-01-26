"""
Task backend protocol and registry.

This module defines the TaskBackend protocol that all task backends
must implement, enabling pluggable task storage (beads, JSON, etc.).
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from .models import Task, TaskCounts, TaskStatus


@runtime_checkable
class TaskBackend(Protocol):
    """
    Protocol for task backend implementations.

    All task backends (beads, JSON, etc.) must implement this interface
    to be compatible with the cub task management system.

    Backends are responsible for:
    - Reading and writing task data from their storage format
    - Filtering tasks by status, dependencies, and other criteria
    - Managing task lifecycle (create, update, close)
    - Validating task data and dependencies
    """

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
        ...

    def get_task(self, task_id: str) -> Task | None:
        """
        Get a specific task by ID.

        Args:
            task_id: Unique task identifier

        Returns:
            Task object if found, None otherwise
        """
        ...

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
        ...

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
        ...

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
        ...

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
        ...

    def get_task_counts(self) -> TaskCounts:
        """
        Get count statistics for tasks.

        Returns:
            TaskCounts object with total, open, in_progress, closed counts
        """
        ...

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
        ...

    def import_tasks(self, tasks: list[Task]) -> list[Task]:
        """
        Bulk import tasks, preserving explicit IDs.

        This method enables efficient bulk import of multiple tasks at once.
        Backends should implement this efficiently (e.g., single file write,
        single CLI call) rather than simply looping over create_task().

        IMPORTANT: If a task has an explicit ID set, that ID MUST be preserved.
        This is critical for staging plans where task IDs are pre-defined and
        dependencies reference those specific IDs. Only generate new IDs for
        tasks that don't have one set.

        Args:
            tasks: List of Task objects to import

        Returns:
            List of imported Task objects with their IDs preserved

        Raises:
            ValueError: If import fails or duplicate IDs detected
        """
        ...

    @property
    def backend_name(self) -> str:
        """
        Get the name of this backend.

        Returns:
            Backend name (e.g., 'beads', 'json')
        """
        ...

    def get_agent_instructions(self, task_id: str) -> str:
        """
        Get instructions for an AI agent on how to interact with this backend.

        Returns backend-specific instructions including:
        - How to close a task
        - How to check task status
        - How to list tasks

        Args:
            task_id: The current task ID for context

        Returns:
            Multiline string with agent instructions
        """
        ...

    def bind_branch(
        self,
        epic_id: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> bool:
        """
        Bind a git branch to an epic/task.

        Creates an association between a git branch and an epic, useful for
        tracking which branch is being used to implement which epic.

        Args:
            epic_id: Epic or task ID to bind
            branch_name: Git branch name
            base_branch: Base branch for merging (default: main)

        Returns:
            True if binding was created, False if binding already exists
            or backend doesn't support branch bindings
        """
        ...

    def try_close_epic(self, epic_id: str) -> tuple[bool, str]:
        """
        Attempt to close an epic if all its tasks are complete.

        Checks all tasks belonging to the epic and closes the epic if
        all tasks have status CLOSED. This is a no-op if:
        - The epic doesn't exist
        - The epic is already closed
        - Some tasks are still open or in progress
        - The backend doesn't support epic closure

        Args:
            epic_id: The epic ID to potentially close

        Returns:
            Tuple of (closed: bool, message: str) where:
            - closed: True if epic was closed, False otherwise
            - message: Human-readable explanation of the result
        """
        ...


# Backend registry
_backends: dict[str, type[TaskBackend]] = {}


def register_backend(name: str) -> Callable[[type[TaskBackend]], type[TaskBackend]]:
    """
    Decorator to register a task backend implementation.

    Usage:
        @register_backend('beads')
        class BeadsBackend:
            def list_tasks(self, ...):
                ...

    Args:
        name: Backend name (e.g., 'beads', 'json')

    Returns:
        Decorator function
    """

    def decorator(backend_class: type[TaskBackend]) -> type[TaskBackend]:
        _backends[name] = backend_class
        return backend_class

    return decorator


def get_backend(
    name: str | None = None,
    project_dir: Path | None = None,
) -> TaskBackend:
    """
    Get a task backend by name or auto-detect.

    If name is not provided, auto-detects based on:
    1. CUB_BACKEND environment variable
    2. .cub.json config file backend.mode setting
    3. Presence of .beads/ directory (beads backend)
    4. Presence of .cub/tasks.jsonl (jsonl backend)
    5. Presence of prd.json file (jsonl backend with migration)
    6. Default to jsonl backend

    Args:
        name: Backend name ('beads', 'jsonl', 'both', or None for auto-detect)
        project_dir: Project directory for auto-detection (defaults to cwd)

    Returns:
        TaskBackend instance

    Raises:
        ValueError: If backend name is invalid or backend not registered
    """
    # Auto-detect if name not provided
    if name is None:
        name = detect_backend(project_dir)

    # Handle "both" mode specially - instantiate BothBackend with primary and secondary
    if name == "both":
        from .beads import BeadsBackend
        from .both import BothBackend
        from .jsonl import JsonlBackend

        try:
            primary = BeadsBackend(project_dir=project_dir)
            secondary = JsonlBackend(project_dir=project_dir)
            return BothBackend(primary, secondary)
        except Exception as e:
            raise ValueError(f"Failed to initialize 'both' backend: {e}")

    # Get backend class from registry
    backend_class = _backends.get(name)
    if backend_class is None:
        raise ValueError(
            f"Backend '{name}' not registered. Available backends: {', '.join(_backends.keys())}"
        )

    # Instantiate and return (type ignore for project_dir - Protocol doesn't specify __init__)
    return backend_class(project_dir=project_dir)  # type: ignore[call-arg]


def detect_backend(project_dir: Path | None = None) -> str:
    """
    Auto-detect which task backend to use.

    Detection order:
    1. CUB_BACKEND environment variable (beads, jsonl, both, or auto)
    2. .cub.json config file backend.mode setting
    3. Check for .beads/ directory -> beads backend
    4. Check for .cub/tasks.jsonl -> jsonl backend
    5. Check for prd.json file -> jsonl backend (with migration)
    6. Default to jsonl backend

    Args:
        project_dir: Project directory to check (defaults to cwd)

    Returns:
        Backend name ('beads', 'jsonl', or 'both')
    """
    if project_dir is None:
        project_dir = Path.cwd()
    elif isinstance(project_dir, str):
        project_dir = Path(project_dir)

    # Check for explicit environment variable override
    backend_env = os.environ.get("CUB_BACKEND", "").lower()
    if backend_env in ("beads", "bd"):
        # Verify beads is available and initialized
        beads_dir = project_dir / ".beads"
        if beads_dir.exists() and beads_dir.is_dir():
            return "beads"
        # Fall through to auto-detect if .beads/ not found

    elif backend_env in ("json", "jsonl", "prd"):
        return "jsonl"

    elif backend_env == "both":
        # Only use "both" if both backends are available
        beads_dir = project_dir / ".beads"
        tasks_file = project_dir / ".cub" / "tasks.jsonl"
        if beads_dir.exists() and beads_dir.is_dir() and tasks_file.exists():
            return "both"
        # Fall through to auto-detect if not both available

    # Check .cub.json configuration file
    try:
        from cub.core.config import load_config

        config = load_config(project_dir=project_dir)
        if config.backend.mode:
            mode = config.backend.mode.lower()
            if mode == "both":
                # Verify both backends are available
                beads_dir = project_dir / ".beads"
                tasks_file = project_dir / ".cub" / "tasks.jsonl"
                if beads_dir.exists() and beads_dir.is_dir() and tasks_file.exists():
                    return "both"
            elif mode in ("beads", "bd"):
                beads_dir = project_dir / ".beads"
                if beads_dir.exists() and beads_dir.is_dir():
                    return "beads"
            elif mode in ("jsonl", "json", "prd"):
                return "jsonl"
            # If mode is "auto" or invalid, fall through to auto-detect
    except Exception:
        # Config loading failed, fall through to auto-detect
        pass

    # Auto-detect based on directory contents
    beads_dir = project_dir / ".beads"
    tasks_file = project_dir / ".cub" / "tasks.jsonl"

    # If both exist, default to beads (existing behavior)
    if beads_dir.exists() and beads_dir.is_dir():
        return "beads"

    # Check for JSONL backend
    if tasks_file.exists() and tasks_file.is_file():
        return "jsonl"

    # Check for legacy prd.json (will be migrated to JSONL)
    prd_file = project_dir / "prd.json"
    if prd_file.exists() and prd_file.is_file():
        return "jsonl"

    # Default to jsonl
    return "jsonl"


def list_backends() -> list[str]:
    """
    List all registered backend names.

    Returns:
        List of backend names
    """
    return list(_backends.keys())


def is_backend_available(name: str) -> bool:
    """
    Check if a backend is available.

    Args:
        name: Backend name to check

    Returns:
        True if backend is registered
    """
    return name in _backends
