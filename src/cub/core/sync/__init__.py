"""
Git-based task synchronization service.

This module provides Python-native git sync capabilities using git plumbing
commands to commit to a sync branch without affecting the working tree.

The sync mechanism uses git plumbing (`write-tree`, `commit-tree`, `update-ref`)
to commit to the `cub-sync` branch without checking it out, keeping the working
tree clean. This is the same pattern beads uses, proven stable.

Example:
    >>> from cub.core.sync import SyncService, SyncResult
    >>> sync = SyncService(project_dir=Path("."))
    >>> if not sync.is_initialized():
    ...     sync.initialize()
    >>> sync.commit("Update tasks")
    >>> result = sync.pull()
    >>> if result.conflicts:
    ...     print(f"Resolved {len(result.conflicts)} conflicts")
"""

from cub.core.sync.models import (
    CounterState,
    SyncConflict,
    SyncResult,
    SyncState,
    SyncStatus,
)
from cub.core.sync.service import SyncService

__all__ = [
    "SyncService",
    "SyncState",
    "SyncResult",
    "SyncConflict",
    "SyncStatus",
    "CounterState",
]
