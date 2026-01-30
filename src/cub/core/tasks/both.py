"""
BothBackend wrapper implementation.

This backend wraps two backends (primary and secondary) and delegates all
operations to both backends in sequence. The primary backend's result is
returned, while the secondary backend's result is used for validation.

This is useful for transitioning from one backend to another while ensuring
both stay in sync, or for validating a new backend implementation against
a trusted reference implementation.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .backend import TaskBackend, TaskBackendDefaults, register_backend
from .models import Task, TaskCounts, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class TaskDivergence:
    """
    Record of a divergence between primary and secondary backends.

    Tracks when the two backends return different results for the same
    operation, including the operation type, timestamp, and details about
    the differences detected.
    """

    timestamp: datetime
    operation: str
    task_id: str | None
    primary_result: Any
    secondary_result: Any
    difference_summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert divergence to a dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "task_id": self.task_id,
            "primary_result": self._serialize(self.primary_result),
            "secondary_result": self._serialize(self.secondary_result),
            "difference_summary": self.difference_summary,
        }

    def _serialize(self, obj: Any) -> Any:
        """Serialize objects for JSON encoding."""
        if isinstance(obj, Task):
            return obj.model_dump(mode="json")
        elif isinstance(obj, list) and obj and isinstance(obj[0], Task):
            return [t.model_dump(mode="json") for t in obj]
        elif isinstance(obj, TaskCounts):
            return {
                "total": obj.total,
                "open": obj.open,
                "in_progress": obj.in_progress,
                "closed": obj.closed,
            }
        elif isinstance(obj, bool):
            return obj
        elif isinstance(obj, tuple):
            return list(obj)
        return str(obj)


@register_backend("both")  # type: ignore[arg-type]
class BothBackend(TaskBackendDefaults):
    """
    Backend wrapper that delegates to two backends (primary and secondary).

    This backend executes all operations on both the primary and secondary
    backends, returning the primary backend's result while comparing it with
    the secondary backend's result for validation. Any divergences are logged
    to a divergence log file for review.

    The primary backend is typically the production/trusted backend (e.g., beads),
    while the secondary backend is the one being validated (e.g., jsonl).

    Note: This class inherits from TaskBackendDefaults to provide default
    implementations for methods like add_label, remove_label, etc. These
    defaults will use the delegated methods (get_task, update_task, etc.)
    which are already implemented to compare both backends.

    Example:
        >>> from .beads import BeadsBackend
        >>> from .jsonl import JsonlBackend
        >>> primary = BeadsBackend()
        >>> secondary = JsonlBackend()
        >>> backend = BothBackend(primary, secondary)
        >>> tasks = backend.list_tasks(status=TaskStatus.OPEN)  # Uses both
    """

    def __init__(
        self,
        primary: TaskBackend,
        secondary: TaskBackend,
        divergence_log: Path | None = None,
    ):
        """
        Initialize the BothBackend wrapper.

        Args:
            primary: Primary backend (result is returned)
            secondary: Secondary backend (result is validated)
            divergence_log: Path to divergence log file (defaults to .cub/backend-divergence.log)
        """
        self.primary = primary
        self.secondary = secondary
        self.divergence_log = divergence_log or Path.cwd() / ".cub" / "backend-divergence.log"
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        """Ensure the divergence log directory exists."""
        self.divergence_log.parent.mkdir(parents=True, exist_ok=True)

    def _log_divergence(self, divergence: TaskDivergence) -> None:
        """
        Log a divergence to the divergence log file.

        Args:
            divergence: TaskDivergence object to log
        """
        try:
            with open(self.divergence_log, "a", encoding="utf-8") as f:
                json.dump(divergence.to_dict(), f)
                f.write("\n")
        except Exception as e:
            logger.warning(f"Failed to log divergence: {e}")

    def _compare_tasks(self, primary_task: Task | None, secondary_task: Task | None) -> str | None:
        """
        Compare two tasks and return a summary of differences.

        Args:
            primary_task: Task from primary backend
            secondary_task: Task from secondary backend

        Returns:
            String describing differences, or None if tasks are equivalent
        """
        if primary_task is None and secondary_task is None:
            return None

        if primary_task is None:
            return "Primary task is None, secondary is not"

        if secondary_task is None:
            return "Secondary task is None, primary is not"

        # Compare all important fields
        differences = []

        if primary_task.id != secondary_task.id:
            differences.append(f"id: {primary_task.id} != {secondary_task.id}")

        if primary_task.title != secondary_task.title:
            differences.append(f"title: {primary_task.title} != {secondary_task.title}")

        if primary_task.status != secondary_task.status:
            differences.append(f"status: {primary_task.status} != {secondary_task.status}")

        if primary_task.priority != secondary_task.priority:
            differences.append(f"priority: {primary_task.priority} != {secondary_task.priority}")

        if primary_task.type != secondary_task.type:
            differences.append(f"type: {primary_task.type} != {secondary_task.type}")

        if primary_task.description != secondary_task.description:
            p_len = len(primary_task.description)
            s_len = len(secondary_task.description)
            differences.append(f"description: {p_len} chars != {s_len} chars")

        if primary_task.assignee != secondary_task.assignee:
            differences.append(f"assignee: {primary_task.assignee} != {secondary_task.assignee}")

        if set(primary_task.labels) != set(secondary_task.labels):
            differences.append(f"labels: {primary_task.labels} != {secondary_task.labels}")

        if set(primary_task.depends_on) != set(secondary_task.depends_on):
            differences.append(
                f"depends_on: {primary_task.depends_on} != {secondary_task.depends_on}"
            )

        if primary_task.parent != secondary_task.parent:
            differences.append(f"parent: {primary_task.parent} != {secondary_task.parent}")

        return "; ".join(differences) if differences else None

    def _compare_task_lists(
        self, primary_tasks: list[Task], secondary_tasks: list[Task]
    ) -> str | None:
        """
        Compare two task lists and return a summary of differences.

        Args:
            primary_tasks: Task list from primary backend
            secondary_tasks: Task list from secondary backend

        Returns:
            String describing differences, or None if lists are equivalent
        """
        if len(primary_tasks) != len(secondary_tasks):
            return f"List length mismatch: {len(primary_tasks)} != {len(secondary_tasks)}"

        # Sort both lists by ID for comparison
        primary_sorted = sorted(primary_tasks, key=lambda t: t.id)
        secondary_sorted = sorted(secondary_tasks, key=lambda t: t.id)

        differences = []
        for i, (p_task, s_task) in enumerate(zip(primary_sorted, secondary_sorted)):
            diff = self._compare_tasks(p_task, s_task)
            if diff:
                differences.append(f"Task {i} ({p_task.id}): {diff}")

        return "; ".join(differences) if differences else None

    def _compare_task_counts(
        self, primary_counts: TaskCounts, secondary_counts: TaskCounts
    ) -> str | None:
        """
        Compare two TaskCounts objects and return a summary of differences.

        Args:
            primary_counts: TaskCounts from primary backend
            secondary_counts: TaskCounts from secondary backend

        Returns:
            String describing differences, or None if counts are equivalent
        """
        differences = []

        if primary_counts.total != secondary_counts.total:
            differences.append(f"total: {primary_counts.total} != {secondary_counts.total}")

        if primary_counts.open != secondary_counts.open:
            differences.append(f"open: {primary_counts.open} != {secondary_counts.open}")

        if primary_counts.in_progress != secondary_counts.in_progress:
            differences.append(
                f"in_progress: {primary_counts.in_progress} != {secondary_counts.in_progress}"
            )

        if primary_counts.closed != secondary_counts.closed:
            differences.append(f"closed: {primary_counts.closed} != {secondary_counts.closed}")

        return "; ".join(differences) if differences else None

    @property
    def backend_name(self) -> str:
        """Get the backend name."""
        return f"both({self.primary.backend_name}+{self.secondary.backend_name})"

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """
        List all tasks with optional filtering.

        Delegates to both backends and compares results.

        Args:
            status: Filter by task status
            parent: Filter by parent epic ID
            label: Filter by label

        Returns:
            List of tasks from primary backend
        """
        primary_result = self.primary.list_tasks(status=status, parent=parent, label=label)
        secondary_result = self.secondary.list_tasks(status=status, parent=parent, label=label)

        # Compare results
        diff = self._compare_task_lists(primary_result, secondary_result)
        if diff:
            divergence = TaskDivergence(
                timestamp=datetime.now(),
                operation="list_tasks",
                task_id=None,
                primary_result=primary_result,
                secondary_result=secondary_result,
                difference_summary=diff,
            )
            self._log_divergence(divergence)
            logger.warning(f"Backend divergence detected in list_tasks: {diff}")

        return primary_result

    def get_task(self, task_id: str) -> Task | None:
        """
        Retrieve a specific task by ID.

        Delegates to both backends and compares results.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task object from primary backend, or None if not found
        """
        primary_result = self.primary.get_task(task_id)
        secondary_result = self.secondary.get_task(task_id)

        # Compare results
        diff = self._compare_tasks(primary_result, secondary_result)
        if diff:
            divergence = TaskDivergence(
                timestamp=datetime.now(),
                operation="get_task",
                task_id=task_id,
                primary_result=primary_result,
                secondary_result=secondary_result,
                difference_summary=diff,
            )
            self._log_divergence(divergence)
            logger.warning(f"Backend divergence detected in get_task({task_id}): {diff}")

        return primary_result

    def get_ready_tasks(self, parent: str | None = None, label: str | None = None) -> list[Task]:
        """
        Get tasks ready to work on (no dependencies blocking them).

        Delegates to both backends and compares results.

        Args:
            parent: Filter by parent epic ID
            label: Filter by label

        Returns:
            List of ready tasks from primary backend
        """
        primary_result = self.primary.get_ready_tasks(parent=parent, label=label)
        secondary_result = self.secondary.get_ready_tasks(parent=parent, label=label)

        # Compare results
        diff = self._compare_task_lists(primary_result, secondary_result)
        if diff:
            divergence = TaskDivergence(
                timestamp=datetime.now(),
                operation="get_ready_tasks",
                task_id=None,
                primary_result=primary_result,
                secondary_result=secondary_result,
                difference_summary=diff,
            )
            self._log_divergence(divergence)
            logger.warning(f"Backend divergence detected in get_ready_tasks: {diff}")

        return primary_result

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

        Delegates to both backends and compares results.

        Args:
            task_id: Task ID to update
            status: New status (optional)
            assignee: New assignee (optional)
            description: New description (optional)
            labels: New labels (optional)
            title: New title (optional)
            priority: New priority (optional)
            notes: New notes (optional)

        Returns:
            Updated task from primary backend

        Raises:
            ValueError: If task not found in primary backend
        """
        primary_result = self.primary.update_task(
            task_id, status=status, assignee=assignee, description=description,
            labels=labels, title=title, priority=priority, notes=notes,
        )

        try:
            secondary_result = self.secondary.update_task(
                task_id, status=status, assignee=assignee, description=description,
                labels=labels, title=title, priority=priority, notes=notes,
            )

            # Compare results
            diff = self._compare_tasks(primary_result, secondary_result)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="update_task",
                    task_id=task_id,
                    primary_result=primary_result,
                    secondary_result=secondary_result,
                    difference_summary=diff,
                )
                self._log_divergence(divergence)
                logger.warning(f"Backend divergence detected in update_task({task_id}): {diff}")
        except Exception as e:
            logger.warning(f"Secondary backend update_task failed: {e}")

        return primary_result

    def close_task(self, task_id: str, reason: str | None = None) -> Task:
        """
        Mark a task as closed.

        Delegates to both backends and compares results.

        Args:
            task_id: Task ID to close
            reason: Optional reason for closing

        Returns:
            Closed task from primary backend

        Raises:
            ValueError: If task not found or already closed in primary backend
        """
        primary_result = self.primary.close_task(task_id, reason=reason)

        try:
            secondary_result = self.secondary.close_task(task_id, reason=reason)

            # Compare results
            diff = self._compare_tasks(primary_result, secondary_result)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="close_task",
                    task_id=task_id,
                    primary_result=primary_result,
                    secondary_result=secondary_result,
                    difference_summary=diff,
                )
                self._log_divergence(divergence)
                logger.warning(f"Backend divergence detected in close_task({task_id}): {diff}")
        except Exception as e:
            logger.warning(f"Secondary backend close_task failed: {e}")

        return primary_result

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

        Delegates to both backends and compares results.

        Args:
            title: Task title
            description: Task description
            task_type: Task type (task, feature, bug, etc.)
            priority: Priority level (0-4, where 0 is highest)
            labels: Task labels
            depends_on: Task IDs this task depends on
            parent: Parent epic ID

        Returns:
            Created task from primary backend

        Raises:
            ValueError: If task creation fails in primary backend
        """
        primary_result = self.primary.create_task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            labels=labels,
            depends_on=depends_on,
            parent=parent,
        )

        try:
            secondary_result = self.secondary.create_task(
                title=title,
                description=description,
                task_type=task_type,
                priority=priority,
                labels=labels,
                depends_on=depends_on,
                parent=parent,
            )

            # Compare results (IDs may differ, so compare other fields)
            if primary_result.title != secondary_result.title:
                logger.warning(
                    f"Backend divergence in create_task: titles differ "
                    f"({primary_result.title} != {secondary_result.title})"
                )
        except Exception as e:
            logger.warning(f"Secondary backend create_task failed: {e}")

        return primary_result

    def get_task_counts(self) -> TaskCounts:
        """
        Get count statistics for tasks.

        Delegates to both backends and compares results.

        Returns:
            TaskCounts from primary backend
        """
        primary_result = self.primary.get_task_counts()
        secondary_result = self.secondary.get_task_counts()

        # Compare results
        diff = self._compare_task_counts(primary_result, secondary_result)
        if diff:
            divergence = TaskDivergence(
                timestamp=datetime.now(),
                operation="get_task_counts",
                task_id=None,
                primary_result=primary_result,
                secondary_result=secondary_result,
                difference_summary=diff,
            )
            self._log_divergence(divergence)
            logger.warning(f"Backend divergence detected in get_task_counts: {diff}")

        return primary_result

    def add_task_note(self, task_id: str, note: str) -> Task:
        """
        Add a note/comment to a task.

        Delegates to both backends and compares results.

        Args:
            task_id: Task ID to add note to
            note: Note text to add

        Returns:
            Updated task from primary backend

        Raises:
            ValueError: If task not found in primary backend
        """
        primary_result = self.primary.add_task_note(task_id, note)

        try:
            secondary_result = self.secondary.add_task_note(task_id, note)

            # Compare results
            diff = self._compare_tasks(primary_result, secondary_result)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="add_task_note",
                    task_id=task_id,
                    primary_result=primary_result,
                    secondary_result=secondary_result,
                    difference_summary=diff,
                )
                self._log_divergence(divergence)
                logger.warning(f"Backend divergence detected in add_task_note({task_id}): {diff}")
        except Exception as e:
            logger.warning(f"Secondary backend add_task_note failed: {e}")

        return primary_result

    def import_tasks(self, tasks: list[Task]) -> list[Task]:
        """
        Bulk import multiple tasks.

        Delegates to both backends. Note that task IDs may differ between
        backends after import, so divergence detection is limited.

        Args:
            tasks: List of tasks to import

        Returns:
            List of imported tasks from primary backend
        """
        primary_result = self.primary.import_tasks(tasks)

        try:
            secondary_result = self.secondary.import_tasks(tasks)

            # Compare counts only (IDs may differ)
            if len(primary_result) != len(secondary_result):
                logger.warning(
                    f"Backend divergence in import_tasks: count mismatch "
                    f"({len(primary_result)} != {len(secondary_result)})"
                )
        except Exception as e:
            logger.warning(f"Secondary backend import_tasks failed: {e}")

        return primary_result

    def get_agent_instructions(self, task_id: str) -> str:
        """
        Get backend-specific instructions for AI agents.

        Returns instructions from the primary backend.

        Args:
            task_id: Task ID to get instructions for

        Returns:
            Multiline string with agent instructions from primary backend
        """
        return self.primary.get_agent_instructions(task_id)

    def bind_branch(self, epic_id: str, branch_name: str, base_branch: str = "main") -> bool:
        """
        Bind a git branch to an epic/task.

        Delegates to both backends.

        Args:
            epic_id: Epic/task ID to bind branch to
            branch_name: Name of git branch
            base_branch: Base branch name (default: main)

        Returns:
            True if binding created in primary backend, False if already exists or unsupported
        """
        primary_result = self.primary.bind_branch(epic_id, branch_name, base_branch)

        try:
            secondary_result = self.secondary.bind_branch(epic_id, branch_name, base_branch)

            if primary_result != secondary_result:
                logger.warning(
                    f"Backend divergence in bind_branch({epic_id}): "
                    f"{primary_result} != {secondary_result}"
                )
        except Exception as e:
            logger.warning(f"Secondary backend bind_branch failed: {e}")

        return primary_result

    def try_close_epic(self, epic_id: str) -> tuple[bool, str]:
        """
        Attempt to close an epic if all tasks are complete.

        Delegates to both backends.

        Args:
            epic_id: Epic ID to try closing

        Returns:
            Tuple of (closed: bool, message: str) from primary backend
        """
        primary_result = self.primary.try_close_epic(epic_id)

        try:
            secondary_result = self.secondary.try_close_epic(epic_id)

            if primary_result != secondary_result:
                logger.warning(
                    f"Backend divergence in try_close_epic({epic_id}): "
                    f"{primary_result} != {secondary_result}"
                )
        except Exception as e:
            logger.warning(f"Secondary backend try_close_epic failed: {e}")

        return primary_result

    def compare_all_tasks(self) -> list[TaskDivergence]:
        """
        Compare all tasks between primary and secondary backends.

        This method performs a full comparison of all tasks in both backends,
        identifying any divergences. Useful for validating backend sync or
        debugging issues.

        Returns:
            List of TaskDivergence objects for any differences found
        """
        divergences: list[TaskDivergence] = []

        # Get all tasks from both backends
        try:
            primary_tasks = self.primary.list_tasks()
            secondary_tasks = self.secondary.list_tasks()
        except Exception as e:
            # If we can't fetch tasks, log it as a divergence
            divergence = TaskDivergence(
                timestamp=datetime.now(),
                operation="compare_all_tasks",
                task_id=None,
                primary_result=None,
                secondary_result=None,
                difference_summary=f"Failed to fetch tasks: {e}",
            )
            divergences.append(divergence)
            return divergences

        # Create maps for quick lookup
        primary_map = {task.id: task for task in primary_tasks}
        secondary_map = {task.id: task for task in secondary_tasks}

        # Find tasks only in primary
        primary_only = set(primary_map.keys()) - set(secondary_map.keys())
        for task_id in primary_only:
            divergence = TaskDivergence(
                timestamp=datetime.now(),
                operation="compare_all_tasks",
                task_id=task_id,
                primary_result=primary_map[task_id],
                secondary_result=None,
                difference_summary=f"Task {task_id} exists only in primary backend",
            )
            divergences.append(divergence)

        # Find tasks only in secondary
        secondary_only = set(secondary_map.keys()) - set(primary_map.keys())
        for task_id in secondary_only:
            divergence = TaskDivergence(
                timestamp=datetime.now(),
                operation="compare_all_tasks",
                task_id=task_id,
                primary_result=None,
                secondary_result=secondary_map[task_id],
                difference_summary=f"Task {task_id} exists only in secondary backend",
            )
            divergences.append(divergence)

        # Compare tasks that exist in both
        common_ids = set(primary_map.keys()) & set(secondary_map.keys())
        for task_id in common_ids:
            primary_task = primary_map[task_id]
            secondary_task = secondary_map[task_id]

            diff = self._compare_tasks(primary_task, secondary_task)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="compare_all_tasks",
                    task_id=task_id,
                    primary_result=primary_task,
                    secondary_result=secondary_task,
                    difference_summary=diff,
                )
                divergences.append(divergence)

        return divergences

    def get_divergence_count(self) -> int:
        """
        Get the count of divergences logged to the divergence log file.

        This reads the divergence log and counts the number of entries,
        providing a quick way to check if backends are staying in sync.

        Returns:
            Number of divergences logged since the log was last cleared
        """
        if not self.divergence_log.exists():
            return 0

        try:
            with open(self.divergence_log, encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception as e:
            logger.warning(f"Failed to read divergence log: {e}")
            return 0

    def add_dependency(self, task_id: str, depends_on_id: str) -> Task:
        """
        Add a dependency to a task.

        Delegates to both backends and compares results.

        Args:
            task_id: Task to add dependency to
            depends_on_id: Task ID that must be completed first

        Returns:
            Updated task from primary backend

        Raises:
            ValueError: If either task not found or dependency would create a cycle
        """
        primary_result = self.primary.add_dependency(task_id, depends_on_id)

        try:
            secondary_result = self.secondary.add_dependency(task_id, depends_on_id)

            # Compare results
            diff = self._compare_tasks(primary_result, secondary_result)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="add_dependency",
                    task_id=task_id,
                    primary_result=primary_result,
                    secondary_result=secondary_result,
                    difference_summary=diff,
                )
                self._log_divergence(divergence)
                logger.warning(
                    f"Backend divergence detected in add_dependency"
                    f"({task_id}, {depends_on_id}): {diff}"
                )
        except Exception as e:
            logger.warning(f"Secondary backend add_dependency failed: {e}")

        return primary_result

    def remove_dependency(self, task_id: str, depends_on_id: str) -> Task:
        """
        Remove a dependency from a task.

        Delegates to both backends and compares results.

        Args:
            task_id: Task to remove dependency from
            depends_on_id: Task ID to remove from dependencies

        Returns:
            Updated task from primary backend

        Raises:
            ValueError: If task not found or dependency doesn't exist
        """
        primary_result = self.primary.remove_dependency(task_id, depends_on_id)

        try:
            secondary_result = self.secondary.remove_dependency(task_id, depends_on_id)

            # Compare results
            diff = self._compare_tasks(primary_result, secondary_result)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="remove_dependency",
                    task_id=task_id,
                    primary_result=primary_result,
                    secondary_result=secondary_result,
                    difference_summary=diff,
                )
                self._log_divergence(divergence)
                logger.warning(
                    f"Backend divergence detected in remove_dependency"
                    f"({task_id}, {depends_on_id}): {diff}"
                )
        except Exception as e:
            logger.warning(f"Secondary backend remove_dependency failed: {e}")

        return primary_result

    def list_blocked_tasks(
        self,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """
        List all blocked tasks.

        Delegates to both backends and compares results.

        A task is blocked if:
        - Status is OPEN
        - Has at least one dependency that is not CLOSED

        Args:
            parent: Filter by parent epic/task ID
            label: Filter by label

        Returns:
            List of blocked tasks from primary backend
        """
        primary_result = self.primary.list_blocked_tasks(parent=parent, label=label)
        secondary_result = self.secondary.list_blocked_tasks(parent=parent, label=label)

        # Compare results
        diff = self._compare_task_lists(primary_result, secondary_result)
        if diff:
            divergence = TaskDivergence(
                timestamp=datetime.now(),
                operation="list_blocked_tasks",
                task_id=None,
                primary_result=primary_result,
                secondary_result=secondary_result,
                difference_summary=diff,
            )
            self._log_divergence(divergence)
            logger.warning(f"Backend divergence detected in list_blocked_tasks: {diff}")

        return primary_result

    def reopen_task(self, task_id: str, reason: str | None = None) -> Task:
        """
        Reopen a closed task.

        Delegates to both backends and compares results.

        Args:
            task_id: Task to reopen
            reason: Optional reason for reopening

        Returns:
            Reopened task from primary backend

        Raises:
            ValueError: If task not found or not closed
        """
        primary_result = self.primary.reopen_task(task_id, reason=reason)

        try:
            secondary_result = self.secondary.reopen_task(task_id, reason=reason)

            # Compare results
            diff = self._compare_tasks(primary_result, secondary_result)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="reopen_task",
                    task_id=task_id,
                    primary_result=primary_result,
                    secondary_result=secondary_result,
                    difference_summary=diff,
                )
                self._log_divergence(divergence)
                logger.warning(f"Backend divergence detected in reopen_task({task_id}): {diff}")
        except Exception as e:
            logger.warning(f"Secondary backend reopen_task failed: {e}")

        return primary_result

    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task permanently.

        Delegates to both backends.

        WARNING: This is destructive and cannot be undone.

        Args:
            task_id: Task to delete

        Returns:
            True if task was deleted from primary backend, False if not found

        Raises:
            ValueError: If task has dependents (other tasks depend on it)
        """
        primary_result = self.primary.delete_task(task_id)

        try:
            secondary_result = self.secondary.delete_task(task_id)

            if primary_result != secondary_result:
                logger.warning(
                    f"Backend divergence in delete_task({task_id}): "
                    f"{primary_result} != {secondary_result}"
                )
        except Exception as e:
            logger.warning(f"Secondary backend delete_task failed: {e}")

        return primary_result

    def add_label(self, task_id: str, label: str) -> Task:
        """
        Add a label to a task.

        Delegates to both backends and compares results.

        Args:
            task_id: Task to add label to
            label: Label to add (e.g., "bug", "model:sonnet")

        Returns:
            Updated task from primary backend

        Raises:
            ValueError: If task not found
        """
        primary_result = self.primary.add_label(task_id, label)

        try:
            secondary_result = self.secondary.add_label(task_id, label)

            # Compare results
            diff = self._compare_tasks(primary_result, secondary_result)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="add_label",
                    task_id=task_id,
                    primary_result=primary_result,
                    secondary_result=secondary_result,
                    difference_summary=diff,
                )
                self._log_divergence(divergence)
                logger.warning(
                    f"Backend divergence detected in add_label({task_id}, {label}): {diff}"
                )
        except Exception as e:
            logger.warning(f"Secondary backend add_label failed: {e}")

        return primary_result

    def remove_label(self, task_id: str, label: str) -> Task:
        """
        Remove a label from a task.

        Delegates to both backends and compares results.

        Args:
            task_id: Task to remove label from
            label: Label to remove

        Returns:
            Updated task from primary backend

        Raises:
            ValueError: If task not found or label doesn't exist
        """
        primary_result = self.primary.remove_label(task_id, label)

        try:
            secondary_result = self.secondary.remove_label(task_id, label)

            # Compare results
            diff = self._compare_tasks(primary_result, secondary_result)
            if diff:
                divergence = TaskDivergence(
                    timestamp=datetime.now(),
                    operation="remove_label",
                    task_id=task_id,
                    primary_result=primary_result,
                    secondary_result=secondary_result,
                    difference_summary=diff,
                )
                self._log_divergence(divergence)
                logger.warning(
                    f"Backend divergence detected in remove_label({task_id}, {label}): {diff}"
                )
        except Exception as e:
            logger.warning(f"Secondary backend remove_label failed: {e}")

        return primary_result
