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
    PlanEntry,
    PlanFilters,
    RunEntry,
    RunFilters,
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
        self.by_plan_dir = ledger_dir / "by-plan"
        self.by_run_dir = ledger_dir / "by-run"

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

    def _query_index(
        self,
        since: str | None = None,
        epic: str | None = None,
        verification: VerificationStatus | None = None,
        stage: str | None = None,
        cost_above: float | None = None,
        escalated: bool | None = None,
    ) -> list[LedgerIndex]:
        """Query index with filters for fast lookups.

        Args:
            since: Filter to tasks completed on or after this date (YYYY-MM-DD)
            epic: Filter to tasks in this epic
            verification: Filter by verification status
            stage: Filter by workflow stage
            cost_above: Filter to tasks with cost above this threshold (USD)
            escalated: Filter to tasks that were escalated (requires loading full entries)

        Returns:
            List of LedgerIndex entries matching the filters
        """
        entries = list(self._read_index())

        # Apply index-based filters
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

        if stage:
            entries = [e for e in entries if e.workflow_stage == stage]

        if cost_above is not None:
            entries = [e for e in entries if e.cost_usd > cost_above]

        # Escalated filter requires loading full entries
        if escalated is not None:
            filtered_entries = []
            for index_entry in entries:
                full_entry = self.get_task(index_entry.id)
                if full_entry:
                    # Check if task was escalated (via outcome or multiple harness changes)
                    is_escalated = False
                    if full_entry.outcome and full_entry.outcome.escalated:
                        is_escalated = True

                    # Match the filter
                    if is_escalated == escalated:
                        filtered_entries.append(index_entry)
            entries = filtered_entries

        return entries

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
        return self._query_index(since=since, epic=epic, verification=verification)

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
        since: str | None = None,
        epic: str | None = None,
        verification: VerificationStatus | None = None,
        stage: str | None = None,
        cost_above: float | None = None,
        escalated: bool | None = None,
    ) -> list[LedgerIndex]:
        """Search tasks by text query with optional filters.

        Args:
            query: Text to search for (case-insensitive)
            fields: Fields to search in (default: title, files, spec)
            since: Filter to tasks completed on or after this date (YYYY-MM-DD)
            epic: Filter to tasks in this epic
            verification: Filter by verification status
            stage: Filter by workflow stage
            cost_above: Filter to tasks with cost above this threshold (USD)
            escalated: Filter to tasks that were escalated

        Returns:
            List of matching LedgerIndex entries
        """
        if fields is None:
            fields = ["title", "files", "spec"]

        # First apply index-based filters for fast filtering
        entries = self._query_index(
            since=since,
            epic=epic,
            verification=verification,
            stage=stage,
            cost_above=cost_above,
            escalated=escalated,
        )

        # Then apply text search on filtered results
        query_lower = query.lower()
        results = []

        for entry in entries:
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

    def get_plan(self, plan_id: str) -> PlanEntry | None:
        """Get full plan entry for a plan.

        Args:
            plan_id: Plan ID to retrieve (e.g., 'cub-054A')

        Returns:
            Full PlanEntry or None if not found
        """
        # Check if plan directory exists
        plan_dir = self.by_plan_dir / plan_id
        if not plan_dir.exists():
            return None

        # Read the plan entry file
        plan_file = plan_dir / "entry.json"
        if not plan_file.exists():
            return None

        # Read and parse the full entry
        with open(plan_file, encoding="utf-8") as f:
            data = json.load(f)
            return PlanEntry.model_validate(data)

    def list_plans(self, filters: PlanFilters | None = None) -> list[PlanEntry]:
        """List plans from the ledger.

        Args:
            filters: Optional filters for status, date range, spec_id

        Returns:
            List of PlanEntry records matching the filters
        """
        # Check if by-plan directory exists
        if not self.by_plan_dir.exists():
            return []

        plans = []

        # Iterate through all plan directories
        for plan_dir in self.by_plan_dir.iterdir():
            if not plan_dir.is_dir():
                continue

            plan_file = plan_dir / "entry.json"
            if not plan_file.exists():
                continue

            # Read and parse plan entry
            with open(plan_file, encoding="utf-8") as f:
                data = json.load(f)
                plan = PlanEntry.model_validate(data)

            # Apply filters
            if filters:
                # Filter by status
                if filters.status and plan.status != filters.status:
                    continue

                # Filter by spec_id
                if filters.spec_id and plan.spec_id != filters.spec_id:
                    continue

                # Filter by date range (since)
                if filters.since:
                    since_date = datetime.strptime(filters.since, "%Y-%m-%d").date()
                    plan_start_date = plan.started_at.date()
                    if plan_start_date < since_date:
                        continue

                # Filter by date range (until)
                if filters.until:
                    until_date = datetime.strptime(filters.until, "%Y-%m-%d").date()
                    plan_start_date = plan.started_at.date()
                    if plan_start_date > until_date:
                        continue

            plans.append(plan)

        return plans

    def get_run(self, run_id: str) -> RunEntry | None:
        """Get full run entry for a run session.

        Args:
            run_id: Run session ID to retrieve (e.g., 'cub-20260204-161800')

        Returns:
            Full RunEntry or None if not found
        """
        # Check if run file exists
        run_file = self.by_run_dir / f"{run_id}.json"
        if not run_file.exists():
            return None

        # Read and parse the full entry
        with open(run_file, encoding="utf-8") as f:
            data = json.load(f)
            return RunEntry.model_validate(data)

    def list_runs(self, filters: RunFilters | None = None) -> list[RunEntry]:
        """List run sessions from the ledger.

        Args:
            filters: Optional filters for status, date range, cost

        Returns:
            List of RunEntry records matching the filters
        """
        # Check if by-run directory exists
        if not self.by_run_dir.exists():
            return []

        runs = []

        # Iterate through all run files
        for run_file in self.by_run_dir.iterdir():
            if not run_file.is_file() or not run_file.name.endswith(".json"):
                continue

            # Read and parse run entry
            with open(run_file, encoding="utf-8") as f:
                data = json.load(f)
                run = RunEntry.model_validate(data)

            # Apply filters
            if filters:
                # Filter by status
                if filters.status and run.status != filters.status:
                    continue

                # Filter by date range (since)
                if filters.since:
                    since_date = datetime.strptime(filters.since, "%Y-%m-%d").date()
                    run_start_date = run.started_at.date()
                    if run_start_date < since_date:
                        continue

                # Filter by date range (until)
                if filters.until:
                    until_date = datetime.strptime(filters.until, "%Y-%m-%d").date()
                    run_start_date = run.started_at.date()
                    if run_start_date > until_date:
                        continue

                # Filter by minimum cost
                if filters.min_cost is not None and run.total_cost < filters.min_cost:
                    continue

                # Filter by maximum cost
                if filters.max_cost is not None and run.total_cost > filters.max_cost:
                    continue

            runs.append(run)

        return runs
