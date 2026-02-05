"""
Data models for the sync service.

Defines Pydantic models for sync state, results, and counters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SyncStatus(str, Enum):
    """Status of sync branch relative to remote."""

    UP_TO_DATE = "up_to_date"
    AHEAD = "ahead"
    BEHIND = "behind"
    DIVERGED = "diverged"
    NO_REMOTE = "no_remote"
    UNINITIALIZED = "uninitialized"


class SyncState(BaseModel):
    """
    Persistent sync state stored in `.cub/.sync-state.json`.

    Tracks the current state of the sync branch including the last
    commit SHA, timestamps, and any pending changes.

    Example:
        >>> state = SyncState(
        ...     branch_name="cub-sync",
        ...     last_commit_sha="abc123",
        ...     last_sync_at=datetime.now(),
        ... )
        >>> state.model_dump_json(indent=2)
    """

    # Branch configuration
    branch_name: str = Field(
        default="cub-sync",
        description="Name of the sync branch",
    )

    # Tracked file
    tasks_file: str = Field(
        default=".cub/tasks.jsonl",
        description="Relative path to the tasks file being synced",
    )

    # Last sync information
    last_commit_sha: str | None = Field(
        default=None,
        description="SHA of the last sync commit",
    )

    last_sync_at: datetime | None = Field(
        default=None,
        description="Timestamp of the last sync",
    )

    last_tasks_hash: str | None = Field(
        default=None,
        description="Hash of tasks.jsonl content at last sync (for change detection)",
    )

    # Remote tracking
    remote_name: str = Field(
        default="origin",
        description="Name of the remote to sync with",
    )

    last_push_sha: str | None = Field(
        default=None,
        description="SHA of the last pushed commit",
    )

    last_push_at: datetime | None = Field(
        default=None,
        description="Timestamp of the last push",
    )

    # State flags
    initialized: bool = Field(
        default=False,
        description="Whether the sync branch has been created",
    )

    def has_unpushed_changes(self) -> bool:
        """Check if there are local commits not pushed to remote."""
        if self.last_commit_sha is None:
            return False
        return self.last_commit_sha != self.last_push_sha

    def mark_synced(self, commit_sha: str, tasks_hash: str) -> None:
        """Update state after a successful local sync."""
        self.last_commit_sha = commit_sha
        self.last_sync_at = datetime.now()
        self.last_tasks_hash = tasks_hash

    def mark_pushed(self) -> None:
        """Update state after a successful push."""
        self.last_push_sha = self.last_commit_sha
        self.last_push_at = datetime.now()


class SyncConflict(BaseModel):
    """
    Represents a conflict detected during sync pull.

    When the same task is modified both locally and remotely,
    this captures both versions for resolution.
    """

    task_id: str = Field(description="ID of the conflicting task")

    local_updated_at: datetime | None = Field(
        default=None,
        description="When the local version was last modified",
    )

    remote_updated_at: datetime | None = Field(
        default=None,
        description="When the remote version was last modified",
    )

    resolution: str = Field(
        default="last_write_wins",
        description="How the conflict was resolved (last_write_wins, local, remote)",
    )

    winner: str = Field(
        default="",
        description="Which version won (local or remote)",
    )


class SyncResult(BaseModel):
    """
    Result of a sync operation (pull/push/commit).

    Provides detailed feedback about what happened during the sync.
    """

    success: bool = Field(description="Whether the operation succeeded")

    operation: str = Field(
        description="Type of operation (commit, pull, push, initialize)",
    )

    commit_sha: str | None = Field(
        default=None,
        description="SHA of the resulting commit (if any)",
    )

    message: str = Field(
        default="",
        description="Human-readable result message",
    )

    # For pull operations
    tasks_updated: int = Field(
        default=0,
        description="Number of tasks updated during pull",
    )

    conflicts: list[SyncConflict] = Field(
        default_factory=list,
        description="List of conflicts detected and resolved",
    )

    # Timing
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate operation duration in seconds."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None

    def summary(self) -> str:
        """Generate a human-readable summary of the result."""
        if not self.success:
            return f"{self.operation} failed: {self.message}"

        parts = [f"{self.operation} succeeded"]

        if self.commit_sha:
            parts.append(f"commit {self.commit_sha[:8]}")

        if self.tasks_updated > 0:
            parts.append(f"{self.tasks_updated} tasks updated")

        if self.conflicts:
            parts.append(f"{len(self.conflicts)} conflicts resolved")

        if self.message:
            parts.append(self.message)

        return ", ".join(parts)


class CounterState(BaseModel):
    """
    Counter state stored on the sync branch in `.cub/counters.json`.

    Tracks the next available spec number and standalone task number
    for collision-free ID allocation across worktrees.

    The counters are stored on the sync branch and updated atomically
    using optimistic locking to handle concurrent allocation attempts.

    Example:
        >>> state = CounterState(spec_number=54, standalone_task_number=17)
        >>> state.spec_number
        54
        >>> state.model_dump_json(indent=2)
    """

    model_config = ConfigDict(frozen=False)

    spec_number: int = Field(
        default=0,
        ge=0,
        description=(
            "Next available spec number (0-indexed). "
            "The next spec ID will use this number."
        ),
    )

    standalone_task_number: int = Field(
        default=0,
        ge=0,
        description=(
            "Next available standalone task number (0-indexed). "
            "The next standalone ID will use this number."
        ),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of the last counter update",
    )

    def increment_spec_number(self) -> int:
        """
        Increment and return the next spec number.

        Returns:
            The allocated spec number (before incrementing).
        """
        allocated = self.spec_number
        self.spec_number += 1
        self.updated_at = datetime.now(timezone.utc)
        return allocated

    def increment_standalone_number(self) -> int:
        """
        Increment and return the next standalone task number.

        Returns:
            The allocated standalone task number (before incrementing).
        """
        allocated = self.standalone_task_number
        self.standalone_task_number += 1
        self.updated_at = datetime.now(timezone.utc)
        return allocated
