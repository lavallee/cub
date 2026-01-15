"""
Task backend protocol and registry.

This module defines the TaskBackend protocol that all task backends
must implement, enabling pluggable task storage (beads, JSON, etc.).
"""

import os
from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

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
        status: Optional[TaskStatus] = None,
        parent: Optional[str] = None,
        label: Optional[str] = None,
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

    def get_task(self, task_id: str) -> Optional[Task]:
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
        parent: Optional[str] = None,
        label: Optional[str] = None,
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
        status: Optional[TaskStatus] = None,
        assignee: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[list[str]] = None,
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

    def close_task(self, task_id: str, reason: Optional[str] = None) -> Task:
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
        labels: Optional[list[str]] = None,
        depends_on: Optional[list[str]] = None,
        parent: Optional[str] = None,
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
    name: Optional[str] = None,
    project_dir: Optional[Path] = None,
) -> TaskBackend:
    """
    Get a task backend by name or auto-detect.

    If name is not provided, auto-detects based on:
    1. CUB_BACKEND environment variable
    2. Presence of .beads/ directory (beads backend)
    3. Presence of prd.json file (json backend)
    4. Default to json backend

    Args:
        name: Backend name ('beads', 'json', or None for auto-detect)
        project_dir: Project directory for auto-detection (defaults to cwd)

    Returns:
        TaskBackend instance

    Raises:
        ValueError: If backend name is invalid or backend not registered
    """
    # Auto-detect if name not provided
    if name is None:
        name = detect_backend(project_dir)

    # Get backend class from registry
    backend_class = _backends.get(name)
    if backend_class is None:
        raise ValueError(
            f"Backend '{name}' not registered. "
            f"Available backends: {', '.join(_backends.keys())}"
        )

    # Instantiate and return
    return backend_class()


def detect_backend(project_dir: Optional[Path] = None) -> str:
    """
    Auto-detect which task backend to use.

    Detection order:
    1. CUB_BACKEND environment variable (beads, json, or auto)
    2. Check for .beads/ directory -> beads backend
    3. Check for prd.json file -> json backend
    4. Default to json backend

    Args:
        project_dir: Project directory to check (defaults to cwd)

    Returns:
        Backend name ('beads' or 'json')
    """
    if project_dir is None:
        project_dir = Path.cwd()
    elif isinstance(project_dir, str):
        project_dir = Path(project_dir)

    # Check for explicit override
    backend_env = os.environ.get("CUB_BACKEND", "").lower()
    if backend_env in ("beads", "bd"):
        # Verify beads is available and initialized
        beads_dir = project_dir / ".beads"
        if beads_dir.exists() and beads_dir.is_dir():
            return "beads"
        # Fall through to auto-detect if .beads/ not found

    elif backend_env == "json" or backend_env == "prd":
        return "json"

    # Auto-detect based on directory contents
    beads_dir = project_dir / ".beads"
    if beads_dir.exists() and beads_dir.is_dir():
        return "beads"

    prd_file = project_dir / "prd.json"
    if prd_file.exists() and prd_file.is_file():
        return "json"

    # Default to json
    return "json"


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
