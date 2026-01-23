"""
Ledger reader for cub.

Provides query and read access to the completed work ledger stored in
.cub/ledger/. Reads from index.jsonl for fast lookups and individual
task files for full details.
"""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from cub.core.ledger.models import (
    LedgerEntry,
    LedgerIndex,
    LedgerStats,
    VerificationStatus,
)


class LedgerReader:
    """Read and query the completed work ledger.

    Provides access to task completion records stored in .cub/ledger/.
    Uses index.jsonl for fast lookups and by-task/ directory for full
    details.

    Example:
        >>> reader = LedgerReader(Path(".cub/ledger"))
        >>> for entry in reader.list_tasks():
        ...     print(f"{entry.id}: {entry.title}")
        >>> full_entry = reader.get_task("beads-abc")
        >>> stats = reader.get_stats()
    """

    def __init__(self, ledger_dir: Path) -> None:
        """Initialize ledger reader.

        Args:
            ledger_dir: Path to .cub/ledger directory
        """
        self.ledger_dir = ledger_dir
        self.index_file = ledger_dir / "index.jsonl"
        self.by_task_dir = ledger_dir / "by-task"

    def exists(self) -> bool:
        """Check if ledger directory exists."""
        return self.ledger_dir.exists()

    def _read_index(self) -> Iterator[LedgerIndex]:
        """Read all entries from index.jsonl.

        Yields:
            LedgerIndex entries from the index file
        """
        if not self.index_file.exists():
            return

        with open(self.index_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    yield LedgerIndex.model_validate(data)

    def list_tasks(
        self,
        since: str | None = None,
        epic: str | None = None,
        verification: VerificationStatus | None = None,
    ) -> list[LedgerIndex]:
        """List tasks from the ledger index.

        Args:
            since: Filter to tasks completed on or after this date (YYYY-MM-DD)
            epic: Filter to tasks in this epic
            verification: Filter by verification status

        Returns:
            List of LedgerIndex entries matching the filters
        """
        entries = list(self._read_index())

        # Apply filters
        if since:
            since_date = datetime.strptime(since, "%Y-%m-%d").date()
            entries = [
                e for e in entries
                if datetime.strptime(e.completed, "%Y-%m-%d").date() >= since_date
            ]

        if epic:
            entries = [e for e in entries if e.epic == epic]

        if verification:
            entries = [e for e in entries if e.verification == verification.value]

        return entries

    def get_task(self, task_id: str) -> LedgerEntry | None:
        """Get full ledger entry for a task.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Full LedgerEntry or None if not found
        """
        # Check if task file exists
        task_file = self.by_task_dir / f"{task_id}.json"
        if not task_file.exists():
            return None

        # Read and parse the full entry
        with open(task_file, encoding="utf-8") as f:
            data = json.load(f)
            return LedgerEntry.model_validate(data)

    def search_tasks(
        self,
        query: str,
        fields: list[str] | None = None,
    ) -> list[LedgerIndex]:
        """Search tasks by text query.

        Args:
            query: Text to search for (case-insensitive)
            fields: Fields to search in (default: title, files, spec)

        Returns:
            List of matching LedgerIndex entries
        """
        if fields is None:
            fields = ["title", "files", "spec"]

        query_lower = query.lower()
        results = []

        for entry in self._read_index():
            # Check each field for match
            for field in fields:
                value = getattr(entry, field, None)
                if value is None:
                    continue

                # Handle list fields (like files)
                if isinstance(value, list):
                    if any(query_lower in str(v).lower() for v in value):
                        results.append(entry)
                        break
                # Handle string fields
                elif query_lower in str(value).lower():
                    results.append(entry)
                    break

        return results

    def get_stats(
        self,
        since: str | None = None,
        epic: str | None = None,
    ) -> LedgerStats:
        """Calculate aggregate statistics across the ledger.

        Args:
            since: Only include tasks completed on or after this date (YYYY-MM-DD)
            epic: Only include tasks in this epic

        Returns:
            LedgerStats with aggregated metrics
        """
        entries = self.list_tasks(since=since, epic=epic)

        if not entries:
            return LedgerStats()

        # Calculate aggregates
        total_cost = sum(e.cost_usd for e in entries)
        total_tokens = sum(e.tokens for e in entries)

        # Get verification counts
        verified_count = sum(
            1 for e in entries
            if e.verification in [VerificationStatus.PASS.value, VerificationStatus.SKIP.value]
        )
        failed_count = sum(
            1 for e in entries
            if e.verification in [VerificationStatus.FAIL.value, VerificationStatus.ERROR.value]
        )

        # Collect unique files
        all_files = []
        for e in entries:
            all_files.extend(e.files)
        unique_files = len(set(all_files))

        # Calculate temporal bounds
        dates = [datetime.strptime(e.completed, "%Y-%m-%d") for e in entries]
        first_date = min(dates) if dates else None
        last_date = max(dates) if dates else None

        # Build stats
        stats = LedgerStats(
            total_tasks=len(entries),
            total_epics=len({e.epic for e in entries if e.epic}),
            total_cost_usd=total_cost,
            average_cost_per_task=total_cost / len(entries) if entries else 0.0,
            min_cost_usd=min(e.cost_usd for e in entries) if entries else 0.0,
            max_cost_usd=max(e.cost_usd for e in entries) if entries else 0.0,
            total_tokens=total_tokens,
            average_tokens_per_task=total_tokens // len(entries) if entries else 0,
            total_duration_seconds=0,  # Not tracked in index
            average_duration_seconds=0,  # Not tracked in index
            tasks_verified=verified_count,
            tasks_failed=failed_count,
            verification_rate=verified_count / len(entries) if entries else 0.0,
            total_files_changed=len(all_files),
            unique_files_changed=unique_files,
            first_task_date=first_date,
            last_task_date=last_date,
        )

        return stats
