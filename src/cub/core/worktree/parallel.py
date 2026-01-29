"""
Parallel task execution using git worktrees.

This module provides the ParallelRunner class for executing multiple
independent tasks concurrently, each in its own git worktree.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from cub.core.worktree.manager import Worktree, WorktreeError, WorktreeManager

if TYPE_CHECKING:
    from cub.core.tasks.backend import TaskBackend
    from cub.core.tasks.models import Task

logger = logging.getLogger(__name__)


class ParallelRunnerCallback(Protocol):
    """Protocol for parallel runner event callbacks."""

    def on_start(self, num_tasks: int, num_workers: int) -> None:
        """Called when parallel execution starts.

        Args:
            num_tasks: Total number of tasks to execute
            num_workers: Number of parallel workers
        """
        ...

    def on_task_complete(
        self, task_id: str, task_title: str, success: bool, error: str | None = None
    ) -> None:
        """Called when a task completes.

        Args:
            task_id: ID of completed task
            task_title: Title of completed task
            success: Whether task succeeded
            error: Error message if failed
        """
        ...

    def on_task_exception(self, task_id: str, exception: str) -> None:
        """Called when a task raises an exception.

        Args:
            task_id: ID of failed task
            exception: Exception message
        """
        ...

    def on_debug(self, message: str) -> None:
        """Called for debug messages.

        Args:
            message: Debug message
        """
        ...


@dataclass
class WorkerResult:
    """
    Result from a parallel worker task execution.

    Attributes:
        task_id: ID of the task that was executed
        task_title: Title of the task
        success: Whether the task completed successfully
        exit_code: Process exit code
        duration_seconds: How long the task took
        worktree_path: Path to the worktree used
        error: Error message if failed
        tokens_used: Token count if available
        cost_usd: Cost in USD if available
    """

    task_id: str
    task_title: str
    success: bool
    exit_code: int
    duration_seconds: float
    worktree_path: Path
    error: str | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0


@dataclass
class ParallelRunResult:
    """
    Aggregate result from parallel task execution.

    Attributes:
        workers: Results from individual workers
        total_duration: Total wall-clock time
        tasks_completed: Number of successfully completed tasks
        tasks_failed: Number of failed tasks
        total_tokens: Total tokens used across all tasks
        total_cost: Total cost across all tasks
    """

    workers: list[WorkerResult] = field(default_factory=list)
    total_duration: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


class _NoOpCallback:
    """Default no-op callback implementation."""

    def on_start(self, num_tasks: int, num_workers: int) -> None:
        """No-op start handler."""
        pass

    def on_task_complete(
        self, task_id: str, task_title: str, success: bool, error: str | None = None
    ) -> None:
        """No-op task complete handler."""
        pass

    def on_task_exception(self, task_id: str, exception: str) -> None:
        """No-op exception handler."""
        pass

    def on_debug(self, message: str) -> None:
        """No-op debug handler."""
        pass


class ParallelRunner:
    """
    Executes multiple tasks in parallel using git worktrees.

    Each task runs in its own isolated worktree via a subprocess calling
    `cub run --task <id> --worktree`. This ensures complete isolation
    between parallel tasks.

    Example:
        >>> runner = ParallelRunner(project_dir)
        >>> tasks = [task1, task2, task3]
        >>> result = runner.run(tasks, max_workers=3)
        >>> print(f"Completed {result.tasks_completed} tasks")
    """

    def __init__(
        self,
        project_dir: Path,
        harness: str | None = None,
        model: str | None = None,
        debug: bool = False,
        stream: bool = False,
        callback: ParallelRunnerCallback | None = None,
    ):
        """
        Initialize the parallel runner.

        Args:
            project_dir: Root project directory
            harness: AI harness to use (claude, codex, etc.)
            model: Model to use (sonnet, opus, etc.)
            debug: Enable debug output
            stream: Stream harness output (per-worker)
            callback: Event callback for progress/status output
        """
        self.project_dir = project_dir
        self.harness = harness
        self.model = model
        self.debug = debug
        self.stream = stream
        self._callback = callback or _NoOpCallback()
        self._worktree_manager = WorktreeManager(project_dir)
        self._lock = threading.Lock()
        self._active_worktrees: dict[str, Path] = {}

    def find_independent_tasks(
        self,
        task_backend: TaskBackend,
        count: int,
        epic: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        """
        Find N independent tasks that can run in parallel.

        Independent tasks are those that:
        - Are ready to work on (OPEN status, dependencies satisfied)
        - Do not depend on each other (no mutual blocking relationships)

        Args:
            task_backend: Task backend to query
            count: Maximum number of tasks to return
            epic: Filter by parent epic
            label: Filter by label

        Returns:
            List of independent tasks (up to count)
        """
        # Get all ready tasks
        ready_tasks = task_backend.get_ready_tasks(parent=epic, label=label)

        if len(ready_tasks) <= 1:
            return ready_tasks[:count]

        # Filter out tasks that block each other
        # A task is independent if none of the other selected tasks depend on it
        independent: list[Task] = []

        for task in ready_tasks:
            if len(independent) >= count:
                break

            # Check if this task blocks any already-selected tasks
            is_independent = True
            for selected in independent:
                # If selected depends on this task, skip
                if task.id in selected.depends_on:
                    is_independent = False
                    break
                # If this task depends on selected, skip
                if selected.id in task.depends_on:
                    is_independent = False
                    break

            if is_independent:
                independent.append(task)

        return independent

    def run(
        self,
        tasks: list[Task],
        max_workers: int | None = None,
    ) -> ParallelRunResult:
        """
        Execute tasks in parallel.

        Args:
            tasks: Tasks to execute
            max_workers: Maximum concurrent workers (defaults to len(tasks))

        Returns:
            Aggregate result from all workers
        """
        if not tasks:
            return ParallelRunResult()

        max_workers = max_workers or len(tasks)
        max_workers = min(max_workers, len(tasks))

        result = ParallelRunResult()
        start_time = time.time()

        self._callback.on_start(len(tasks), max_workers)

        # Execute tasks using thread pool
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures: dict[Future[WorkerResult], Task] = {}
            for task in tasks:
                future = executor.submit(self._execute_task, task)
                futures[future] = task

            # Collect results as they complete
            for future in as_completed(futures):
                task = futures[future]
                try:
                    worker_result = future.result()
                    result.workers.append(worker_result)

                    if worker_result.success:
                        result.tasks_completed += 1
                        self._callback.on_task_complete(
                            task.id, task.title[:50], success=True
                        )
                    else:
                        result.tasks_failed += 1
                        error_msg = worker_result.error or "Unknown error"
                        self._callback.on_task_complete(
                            task.id, task.title[:50], success=False, error=error_msg[:50]
                        )

                    result.total_tokens += worker_result.tokens_used
                    result.total_cost += worker_result.cost_usd

                except Exception as e:
                    result.tasks_failed += 1
                    self._callback.on_task_exception(task.id, str(e))
                    result.workers.append(
                        WorkerResult(
                            task_id=task.id,
                            task_title=task.title,
                            success=False,
                            exit_code=-1,
                            duration_seconds=0.0,
                            worktree_path=Path("."),
                            error=str(e),
                        )
                    )

        result.total_duration = time.time() - start_time

        # Cleanup worktrees
        self._cleanup_worktrees()

        return result

    def _execute_task(self, task: Task) -> WorkerResult:
        """
        Execute a single task in its own worktree.

        Args:
            task: Task to execute

        Returns:
            WorkerResult with execution outcome
        """
        start_time = time.time()
        worktree_path: Path | None = None

        try:
            # Create worktree for this task
            worktree = self._create_worktree(task.id)
            worktree_path = worktree.path

            # Track active worktree
            with self._lock:
                self._active_worktrees[task.id] = worktree_path

            # Build cub run command
            cmd = self._build_run_command(task.id)

            if self.debug:
                self._callback.on_debug(f"{task.id}: {' '.join(cmd)}")

            # Execute cub run in worktree
            result = subprocess.run(
                cmd,
                cwd=worktree_path,
                capture_output=True,
                text=True,
            )

            duration = time.time() - start_time

            # Parse output for token/cost info if available
            tokens_used = 0
            cost_usd = 0.0

            # Try to extract from status file
            status_data = self._read_status_file(worktree_path, task.id)
            if status_data:
                budget_data = status_data.get("budget")
                if isinstance(budget_data, dict):
                    tokens_val = budget_data.get("tokens_used")
                    cost_val = budget_data.get("cost_usd")
                    if isinstance(tokens_val, int):
                        tokens_used = tokens_val
                    if isinstance(cost_val, (int, float)):
                        cost_usd = float(cost_val)

            return WorkerResult(
                task_id=task.id,
                task_title=task.title,
                success=result.returncode == 0,
                exit_code=result.returncode,
                duration_seconds=duration,
                worktree_path=worktree_path,
                error=result.stderr if result.returncode != 0 else None,
                tokens_used=tokens_used,
                cost_usd=cost_usd,
            )

        except WorktreeError as e:
            duration = time.time() - start_time
            return WorkerResult(
                task_id=task.id,
                task_title=task.title,
                success=False,
                exit_code=-1,
                duration_seconds=duration,
                worktree_path=worktree_path or Path("."),
                error=f"Worktree error: {e}",
            )

        except Exception as e:
            duration = time.time() - start_time
            return WorkerResult(
                task_id=task.id,
                task_title=task.title,
                success=False,
                exit_code=-1,
                duration_seconds=duration,
                worktree_path=worktree_path or Path("."),
                error=str(e),
            )

        finally:
            # Remove from active worktrees
            with self._lock:
                self._active_worktrees.pop(task.id, None)

    def _create_worktree(self, task_id: str) -> Worktree:
        """
        Create a worktree for a task.

        Args:
            task_id: Task ID (used as worktree name)

        Returns:
            Created Worktree object

        Raises:
            WorktreeError: If worktree creation fails
        """
        # Use worktree manager to create
        return self._worktree_manager.create(task_id, create_branch=False)

    def _build_run_command(self, task_id: str) -> list[str]:
        """
        Build the cub run command for a worker.

        Args:
            task_id: Task to run

        Returns:
            Command list for subprocess
        """
        # Get the path to cub executable
        # Use sys.executable to ensure we use the same Python
        cmd = [sys.executable, "-m", "cub", "run"]

        # Always run single task, single iteration
        cmd.extend(["--task", task_id])
        cmd.append("--once")

        # Don't use --worktree since we're already in a worktree
        # The worktree was created by ParallelRunner

        if self.harness:
            cmd.extend(["--harness", self.harness])

        if self.model:
            cmd.extend(["--model", self.model])

        if self.debug:
            cmd.append("--debug")

        if self.stream:
            cmd.append("--stream")

        return cmd

    def _read_status_file(
        self, worktree_path: Path, task_id: str
    ) -> dict[str, object] | None:
        """
        Read the status file from a worktree.

        Args:
            worktree_path: Path to worktree
            task_id: Task ID (for finding status file)

        Returns:
            Status dict if found, None otherwise
        """
        # Status files are in .cub/status/
        status_dir = worktree_path / ".cub" / "status"
        if not status_dir.exists():
            return None

        # Find the most recent status file
        status_files = sorted(status_dir.glob("*.json"), reverse=True)
        if not status_files:
            return None

        try:
            with status_files[0].open() as f:
                data: dict[str, object] = json.load(f)
                return data
        except (json.JSONDecodeError, OSError):
            return None

    def _cleanup_worktrees(self) -> None:
        """Clean up all worktrees created during parallel execution."""
        # Get list of worktrees to clean up
        with self._lock:
            worktrees_to_remove = list(self._active_worktrees.values())

        # Remove each worktree
        for worktree_path in worktrees_to_remove:
            try:
                self._worktree_manager.remove(worktree_path, force=False)
            except WorktreeError as e:
                if self.debug:
                    self._callback.on_debug(
                        f"Failed to cleanup worktree {worktree_path}: {e}"
                    )

        # Also try to clean up worktrees that completed
        # by listing all worktrees and removing cub-created ones
        try:
            all_worktrees = self._worktree_manager.list()
            for worktree in all_worktrees:
                # Skip main worktree
                if worktree.is_bare:
                    continue
                # Check if this is a parallel runner worktree
                if ".cub/worktrees" in str(worktree.path):
                    try:
                        self._worktree_manager.remove(worktree.path, force=False)
                    except WorktreeError:
                        pass
        except WorktreeError:
            pass


def get_independent_tasks(
    task_backend: TaskBackend,
    count: int,
    epic: str | None = None,
    label: str | None = None,
) -> list[Task]:
    """
    Find N independent tasks that can run in parallel.

    This is a convenience function that creates a temporary ParallelRunner
    just to find tasks. Use ParallelRunner directly for full functionality.

    Args:
        task_backend: Task backend to query
        count: Maximum number of tasks
        epic: Filter by epic
        label: Filter by label

    Returns:
        List of independent tasks
    """
    runner = ParallelRunner(Path.cwd())
    return runner.find_independent_tasks(task_backend, count, epic, label)
