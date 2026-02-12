"""
Status service — clean API for project status aggregation.

Aggregates project state from multiple sources (tasks, ledger, git) to provide
a comprehensive view of project health. The service is stateless and provides
typed methods for different levels of detail.

Usage:
    >>> from cub.core.services.status import StatusService
    >>> service = StatusService.from_project_dir(project_dir)
    >>> summary = service.summary()
    >>> print(f"Tasks: {summary.closed_tasks}/{summary.total_tasks} complete")
    >>> epic_progress = service.progress("cub-b1a")
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from cub.core.services.ledger import LedgerService
from cub.core.services.models import EpicProgress, ProjectStats
from cub.core.tasks.backend import TaskBackend
from cub.core.tasks.backend import get_backend as get_task_backend
from cub.core.tasks.models import TaskStatus
from cub.utils.project import get_project_root

# ============================================================================
# Typed exceptions
# ============================================================================


class StatusServiceError(Exception):
    """Base exception for StatusService errors."""


class EpicNotFoundError(StatusServiceError):
    """Epic not found in task backend."""

    def __init__(self, epic_id: str) -> None:
        self.epic_id = epic_id
        super().__init__(f"Epic '{epic_id}' not found")


# ============================================================================
# StatusService
# ============================================================================


class StatusService:
    """
    Service for aggregating project status from multiple sources.

    Combines data from task backend, ledger, and git to provide
    comprehensive project statistics and progress tracking.

    Example:
        >>> service = StatusService.from_project_dir(Path.cwd())
        >>> summary = service.summary()
        >>> print(f"Completion: {summary.completion_percentage:.1f}%")
    """

    def __init__(
        self,
        project_dir: Path,
        task_backend: TaskBackend,
        ledger_service: LedgerService | None = None,
    ) -> None:
        """
        Initialize service with dependencies.

        Args:
            project_dir: Project root directory
            task_backend: Task backend for task queries
            ledger_service: Optional ledger service for cost data
        """
        self.project_dir = project_dir
        self._task_backend = task_backend
        self._ledger_service = ledger_service

    @classmethod
    def from_project_dir(cls, project_dir: Path | None = None) -> StatusService:
        """
        Create service from project directory.

        Args:
            project_dir: Project root directory (auto-detected if None)

        Returns:
            Configured StatusService instance
        """
        if project_dir is None:
            project_dir = get_project_root()

        task_backend = get_task_backend()
        ledger_service = LedgerService.try_from_project_dir(project_dir)

        return cls(project_dir, task_backend, ledger_service)

    # ============================================================================
    # Summary methods
    # ============================================================================

    def summary(self) -> ProjectStats:
        """
        Get comprehensive project statistics.

        Aggregates data from tasks, ledger, and git to provide
        a complete view of project state.

        Returns:
            ProjectStats with all available metrics

        Example:
            >>> stats = service.summary()
            >>> print(f"Ready tasks: {stats.ready_tasks}")
            >>> print(f"Total cost: ${stats.total_cost_usd:.2f}")
        """
        # Get task counts
        counts = self._task_backend.get_task_counts()

        # Get ready and blocked tasks
        ready_tasks = self._task_backend.get_ready_tasks()
        all_tasks = self._task_backend.list_tasks()

        # Count blocked tasks (open with dependencies)
        blocked_count = 0
        for task in all_tasks:
            if task.status == TaskStatus.OPEN and len(task.depends_on) > 0:
                blocked_count += 1

        # Count epics
        epic_tasks = [t for t in all_tasks if t.type.value == "epic"]
        active_epics = [
            e for e in epic_tasks if e.status in (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)
        ]

        # Get ledger metrics if available
        total_cost = 0.0
        total_tokens = 0
        tasks_in_ledger = 0

        if self._ledger_service:
            try:
                ledger_stats = self._ledger_service.stats()
                total_cost = ledger_stats.total_cost_usd
                total_tokens = ledger_stats.total_tokens
                tasks_in_ledger = ledger_stats.total_tasks
            except Exception:
                # Ledger stats failed, continue with zeros
                pass

        # Get git metrics
        current_branch = self._get_current_branch()
        has_uncommitted = self._has_uncommitted_changes()
        commits_since_main = self._get_commits_ahead_of_main()

        return ProjectStats(
            total_tasks=counts.total,
            open_tasks=counts.open,
            in_progress_tasks=counts.in_progress,
            retry_tasks=counts.retry,
            closed_tasks=counts.closed,
            ready_tasks=len(ready_tasks),
            blocked_tasks=blocked_count,
            total_epics=len(epic_tasks),
            active_epics=len(active_epics),
            completion_percentage=counts.completion_percentage,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            tasks_in_ledger=tasks_in_ledger,
            current_branch=current_branch,
            has_uncommitted_changes=has_uncommitted,
            commits_since_main=commits_since_main,
        )

    def progress(self, epic_id: str) -> EpicProgress:
        """
        Get progress metrics for a specific epic.

        Args:
            epic_id: Epic ID to analyze

        Returns:
            EpicProgress with task breakdown and cost metrics

        Raises:
            EpicNotFoundError: If epic doesn't exist

        Example:
            >>> progress = service.progress("cub-b1a")
            >>> print(f"Epic: {progress.epic_title}")
            >>> print(f"Completion: {progress.completion_percentage:.1f}%")
        """
        # Get the epic task
        epic = self._task_backend.get_task(epic_id)
        if not epic:
            raise EpicNotFoundError(epic_id)

        # Get child tasks
        child_tasks = [t for t in self._task_backend.list_tasks() if t.parent == epic_id]

        # Count tasks by status
        total = len(child_tasks)
        open_count = len([t for t in child_tasks if t.status == TaskStatus.OPEN])
        in_progress = len([t for t in child_tasks if t.status == TaskStatus.IN_PROGRESS])
        closed = len([t for t in child_tasks if t.status == TaskStatus.CLOSED])

        # Get ready tasks (no blockers)
        ready = len(
            [t for t in child_tasks if t.status == TaskStatus.OPEN and len(t.depends_on) == 0]
        )

        # Calculate completion percentage
        completion = (closed / total * 100) if total > 0 else 0.0

        # Get cost metrics from ledger if available
        total_cost = 0.0
        total_tokens = 0
        tasks_with_cost = 0
        first_started = None
        last_completed = None

        if self._ledger_service:
            try:
                # Get all ledger entries for this epic's tasks
                for task in child_tasks:
                    if self._ledger_service.entry_exists(task.id):
                        try:
                            entry = self._ledger_service.get_task(task.id)
                            total_cost += entry.cost_usd
                            total_tokens += entry.tokens.total_tokens
                            tasks_with_cost += 1

                            # Track temporal bounds
                            if entry.started_at:
                                if first_started is None or entry.started_at < first_started:
                                    first_started = entry.started_at
                            if entry.completed_at:
                                if last_completed is None or entry.completed_at > last_completed:
                                    last_completed = entry.completed_at
                        except Exception:
                            # Skip this task if entry read fails
                            continue
            except Exception:
                # Ledger query failed, continue with zeros
                pass

        # Determine workflow stage
        workflow_stage = "planned"
        if in_progress > 0 or closed > 0:
            workflow_stage = "in_progress"
        if closed == total and total > 0:
            workflow_stage = "complete"

        return EpicProgress(
            epic_id=epic_id,
            epic_title=epic.title,
            total_tasks=total,
            open_tasks=open_count,
            in_progress_tasks=in_progress,
            closed_tasks=closed,
            ready_tasks=ready,
            completion_percentage=completion,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            tasks_with_cost=tasks_with_cost,
            first_task_started=first_started,
            last_task_completed=last_completed,
            workflow_stage=workflow_stage,
        )

    # ============================================================================
    # Git helper methods
    # ============================================================================

    def _get_current_branch(self) -> str:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    def _has_uncommitted_changes(self) -> bool:
        """Check if working directory has uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return bool(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _get_commits_ahead_of_main(self) -> int:
        """Get number of commits ahead of main/master."""
        # Try main first, then master
        for base_branch in ["main", "master"]:
            try:
                result = subprocess.run(
                    ["git", "rev-list", "--count", f"{base_branch}..HEAD"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return int(result.stdout.strip())
            except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
                continue
        return 0


__all__ = [
    "StatusService",
    "StatusServiceError",
    "EpicNotFoundError",
]
