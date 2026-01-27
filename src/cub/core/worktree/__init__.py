"""
Git worktree management for parallel task execution.

This module provides worktree management capabilities for cub, enabling
parallel task execution by creating isolated git worktrees for each task.

Example:
    >>> from cub.core.worktree import WorktreeManager
    >>> manager = WorktreeManager()
    >>> worktree_path = manager.get_for_task("cub-001")
    >>> print(f"Task worktree: {worktree_path}")

    >>> from cub.core.worktree import ParallelRunner
    >>> runner = ParallelRunner(project_dir)
    >>> result = runner.run(tasks, max_workers=3)
"""

from .manager import (
    Worktree,
    WorktreeError,
    WorktreeLockError,
    WorktreeManager,
    WorktreeNotFoundError,
)
from .parallel import ParallelRunner, ParallelRunResult, WorkerResult

__all__ = [
    "WorktreeManager",
    "Worktree",
    "WorktreeError",
    "WorktreeLockError",
    "WorktreeNotFoundError",
    "ParallelRunner",
    "ParallelRunResult",
    "WorkerResult",
]
