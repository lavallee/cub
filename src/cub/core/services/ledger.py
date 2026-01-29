"""
Ledger service — clean API for ledger queries and stats.

Wraps core/ledger/ into a service that any interface (CLI, API, skills) can call.
The service is a stateless orchestrator that provides typed methods for ledger
operations without exposing internal implementation details.

Usage:
    >>> from cub.core.services.ledger import LedgerService
    >>> service = LedgerService.from_project_dir(project_dir)
    >>> stats = service.stats()
    >>> recent = service.recent(n=10)
    >>> entries = service.query(epic="cub-b1a", since="2026-01-01")
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.ledger.models import LedgerStats, VerificationStatus
from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.writer import LedgerWriter
from cub.utils.project import get_project_root

if TYPE_CHECKING:
    from cub.core.ledger.models import LedgerEntry, LedgerIndex


# ============================================================================
# Typed exceptions
# ============================================================================


class LedgerServiceError(Exception):
    """Base exception for LedgerService errors."""


class LedgerNotFoundError(LedgerServiceError):
    """Ledger does not exist (no tasks completed yet)."""


class TaskNotFoundError(LedgerServiceError):
    """Task entry not found in ledger."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' not found in ledger")


# ============================================================================
# Service inputs
# ============================================================================


@dataclass(frozen=True)
class LedgerQuery:
    """Filter parameters for ledger queries.

    Attributes:
        since: Only include tasks completed since this date (YYYY-MM-DD or datetime)
        epic: Only include tasks in this epic
        verification: Filter by verification status
        stage: Filter by workflow stage
        cost_above: Filter to tasks with cost above this threshold (USD)
        escalated: Filter to tasks that were escalated (True) or not (False)
    """

    since: str | datetime | None = None
    epic: str | None = None
    verification: VerificationStatus | str | None = None
    stage: str | None = None
    cost_above: float | None = None
    escalated: bool | None = None


@dataclass(frozen=True)
class StatsQuery:
    """Filter parameters for stats aggregation.

    Attributes:
        since: Only include tasks completed since this date (YYYY-MM-DD or datetime)
        epic: Only include tasks in this epic
    """

    since: str | datetime | None = None
    epic: str | None = None


# ============================================================================
# LedgerService
# ============================================================================


class LedgerService:
    """
    Service for querying completed work ledger.

    Provides a clean API for ledger operations without exposing internal
    reader/writer implementation details. All methods are stateless and
    raise typed exceptions.

    Example:
        >>> service = LedgerService.from_project_dir(Path.cwd())
        >>> stats = service.stats()
        >>> print(f"Total cost: ${stats.total_cost_usd:.2f}")
        >>> recent = service.recent(n=5)
    """

    def __init__(self, ledger_dir: Path) -> None:
        """
        Initialize service with ledger directory.

        Args:
            ledger_dir: Path to .cub/ledger directory

        Raises:
            LedgerNotFoundError: If ledger directory doesn't exist
        """
        self.ledger_dir = ledger_dir
        self._reader = LedgerReader(ledger_dir)
        self._writer = LedgerWriter(ledger_dir)

        if not self._reader.exists():
            raise LedgerNotFoundError(
                f"Ledger not found at {ledger_dir}. No tasks have been completed yet."
            )

    @classmethod
    def from_project_dir(cls, project_dir: Path | None = None) -> LedgerService:
        """
        Create service from project directory.

        Args:
            project_dir: Project root directory (auto-detected if None)

        Returns:
            Configured LedgerService instance

        Raises:
            LedgerNotFoundError: If ledger doesn't exist
        """
        if project_dir is None:
            project_dir = get_project_root()

        ledger_dir = project_dir / ".cub" / "ledger"
        return cls(ledger_dir)

    @classmethod
    def try_from_project_dir(cls, project_dir: Path | None = None) -> LedgerService | None:
        """
        Try to create service, returning None if ledger doesn't exist.

        Args:
            project_dir: Project root directory (auto-detected if None)

        Returns:
            LedgerService instance or None if ledger doesn't exist
        """
        try:
            return cls.from_project_dir(project_dir)
        except LedgerNotFoundError:
            return None

    # ============================================================================
    # Query methods
    # ============================================================================

    def query(self, filters: LedgerQuery | None = None) -> list[LedgerIndex]:
        """
        Query ledger entries with filters.

        Args:
            filters: Query filters (all optional)

        Returns:
            List of matching ledger index entries (compact records)

        Example:
            >>> query = LedgerQuery(epic="cub-b1a", since="2026-01-01")
            >>> entries = service.query(query)
        """
        if filters is None:
            filters = LedgerQuery()

        # Convert verification status if provided as string
        verification = None
        if filters.verification is not None:
            if isinstance(filters.verification, str):
                verification = VerificationStatus(filters.verification)
            else:
                verification = filters.verification

        # Convert since to string if datetime
        since = filters.since
        if isinstance(since, datetime):
            since = since.strftime("%Y-%m-%d")

        return self._reader.list_tasks(
            since=since,
            epic=filters.epic,
            verification=verification,
        )

    def recent(self, n: int = 10, epic: str | None = None) -> list[LedgerIndex]:
        """
        Get N most recent ledger entries.

        Args:
            n: Number of entries to return
            epic: Optional epic filter

        Returns:
            List of recent ledger index entries, newest first

        Example:
            >>> recent = service.recent(n=5)
            >>> for entry in recent:
            ...     print(f"{entry.id}: {entry.title}")
        """
        entries = self._reader.list_tasks(epic=epic)
        # Entries are already sorted by completion time (newest first)
        return entries[:n]

    def get_task(self, task_id: str) -> LedgerEntry:
        """
        Get full ledger entry for a task.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Full ledger entry with all details

        Raises:
            TaskNotFoundError: If task not found in ledger

        Example:
            >>> entry = service.get_task("cub-abc")
            >>> print(f"Cost: ${entry.cost_usd:.2f}")
        """
        entry = self._reader.get_task(task_id)
        if entry is None:
            raise TaskNotFoundError(task_id)
        return entry

    def search(
        self,
        query: str,
        fields: list[str] | None = None,
        filters: LedgerQuery | None = None,
    ) -> list[LedgerIndex]:
        """
        Search ledger entries by text query.

        Args:
            query: Search query string
            fields: Fields to search (title, files, spec). Default: all
            filters: Optional query filters

        Returns:
            List of matching ledger index entries

        Example:
            >>> results = service.search("authentication", fields=["title", "files"])
            >>> results = service.search("bug", filters=LedgerQuery(since="2026-01-01"))
        """
        if filters is None:
            filters = LedgerQuery()

        # Convert filters
        verification = None
        if filters.verification is not None:
            if isinstance(filters.verification, str):
                verification = VerificationStatus(filters.verification)
            else:
                verification = filters.verification

        since = filters.since
        if isinstance(since, datetime):
            since = since.strftime("%Y-%m-%d")

        return self._reader.search_tasks(
            query=query,
            fields=fields,
            since=since,
            epic=filters.epic,
            verification=verification,
            stage=filters.stage,
            cost_above=filters.cost_above,
            escalated=filters.escalated,
        )

    # ============================================================================
    # Stats methods
    # ============================================================================

    def stats(self, filters: StatsQuery | None = None) -> LedgerStats:
        """
        Get aggregate statistics for completed work.

        Args:
            filters: Optional filters for stats calculation

        Returns:
            LedgerStats with aggregated metrics

        Example:
            >>> stats = service.stats()
            >>> print(f"Total tasks: {stats.total_tasks}")
            >>> print(f"Total cost: ${stats.total_cost_usd:.2f}")
            >>> print(f"Verification rate: {stats.verification_rate * 100:.1f}%")
        """
        if filters is None:
            filters = StatsQuery()

        since = filters.since
        if isinstance(since, datetime):
            since = since.strftime("%Y-%m-%d")

        return self._reader.get_stats(since=since, epic=filters.epic)

    # ============================================================================
    # Writer methods (for workflow management)
    # ============================================================================

    def update_workflow_stage(
        self,
        task_id: str,
        stage: str,
        reason: str | None = None,
        by: str = "service",
    ) -> bool:
        """
        Update workflow stage for a task.

        Args:
            task_id: Task ID to update
            stage: New workflow stage (dev_complete, needs_review, validated, released)
            reason: Optional reason for transition
            by: Who initiated the transition (default: "service")

        Returns:
            True if successful

        Raises:
            TaskNotFoundError: If task not found in ledger
            ValueError: If stage is invalid

        Example:
            >>> service.update_workflow_stage("cub-abc", "needs_review")
            >>> service.update_workflow_stage("cub-abc", "validated", reason="Tests passed")
        """
        # Validate task exists
        if not self._writer.entry_exists(task_id):
            raise TaskNotFoundError(task_id)

        # Validate stage
        valid_stages = {"dev_complete", "needs_review", "validated", "released"}
        if stage not in valid_stages:
            raise ValueError(
                f"Invalid stage '{stage}'. Must be one of: {', '.join(sorted(valid_stages))}"
            )

        return self._writer.update_workflow_stage(task_id, stage, reason=reason, by=by)

    def entry_exists(self, task_id: str) -> bool:
        """
        Check if a task has a ledger entry.

        Args:
            task_id: Task ID to check

        Returns:
            True if entry exists, False otherwise

        Example:
            >>> if service.entry_exists("cub-abc"):
            ...     entry = service.get_task("cub-abc")
        """
        return self._writer.entry_exists(task_id)


__all__ = [
    "LedgerService",
    "LedgerServiceError",
    "LedgerNotFoundError",
    "TaskNotFoundError",
    "LedgerQuery",
    "StatsQuery",
]
