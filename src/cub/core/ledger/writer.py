"""
Ledger writer for cub.

Provides write access to the completed work ledger stored in
.cub/ledger/. Writes ledger entries and updates index.jsonl.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cub.core.ledger.models import LedgerEntry, LedgerIndex, WorkflowStage


class LedgerWriter:
    """Write completed task records to the ledger.

    Writes full LedgerEntry to .cub/ledger/by-task/{task_id}.json and
    appends a compact index entry to .cub/ledger/index.jsonl for fast queries.

    Example:
        >>> writer = LedgerWriter(Path(".cub/ledger"))
        >>> entry = LedgerEntry(id="cub-m4j.6", title="Wire ledger creation")
        >>> writer.create_entry(entry)
    """

    def __init__(self, ledger_dir: Path) -> None:
        """Initialize ledger writer.

        Args:
            ledger_dir: Path to .cub/ledger directory
        """
        self.ledger_dir = ledger_dir
        self.index_file = ledger_dir / "index.jsonl"
        self.by_task_dir = ledger_dir / "by-task"

    def create_entry(self, entry: LedgerEntry) -> None:
        """Create a new ledger entry.

        Writes the full entry to by-task/{task_id}.json and appends
        a compact index entry to index.jsonl.

        Args:
            entry: LedgerEntry to write

        Raises:
            IOError: If write fails
        """
        # Ensure directories exist
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.by_task_dir.mkdir(parents=True, exist_ok=True)

        # Write full entry to by-task/
        task_file = self.by_task_dir / f"{entry.id}.json"
        with task_file.open("w", encoding="utf-8") as f:
            json.dump(entry.model_dump(mode="json"), f, indent=2, default=str)

        # Append to index
        self._append_to_index(entry)

    def _append_to_index(self, entry: LedgerEntry) -> None:
        """Append entry to index.jsonl.

        Args:
            entry: LedgerEntry to index
        """
        index_entry = LedgerIndex.from_ledger_entry(entry)

        # Append as single line
        with self.index_file.open("a", encoding="utf-8") as f:
            json.dump(index_entry.model_dump(mode="json"), f, default=str)
            f.write("\n")

    def update_entry(self, entry: LedgerEntry) -> None:
        """Update an existing ledger entry.

        Updates the full entry file and rebuilds the index.

        Args:
            entry: Updated LedgerEntry

        Raises:
            FileNotFoundError: If entry doesn't exist
        """
        task_file = self.by_task_dir / f"{entry.id}.json"
        if not task_file.exists():
            raise FileNotFoundError(f"Ledger entry {entry.id} not found")

        # Update full entry
        with task_file.open("w", encoding="utf-8") as f:
            json.dump(entry.model_dump(mode="json"), f, indent=2, default=str)

        # Rebuild index (simple approach - could be optimized)
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild index.jsonl from all task files.

        This is called after updates to ensure index consistency.
        """
        if not self.by_task_dir.exists():
            return

        # Read all task files
        entries = []
        for task_file in sorted(self.by_task_dir.glob("*.json")):
            with task_file.open(encoding="utf-8") as f:
                data = json.load(f)
                entry = LedgerEntry.model_validate(data)
                entries.append(entry)

        # Rewrite index
        with self.index_file.open("w", encoding="utf-8") as f:
            for entry in entries:
                index_entry = LedgerIndex.from_ledger_entry(entry)
                json.dump(index_entry.model_dump(mode="json"), f, default=str)
                f.write("\n")

    def entry_exists(self, task_id: str) -> bool:
        """Check if a ledger entry exists for a task.

        Args:
            task_id: Task ID to check

        Returns:
            True if entry exists, False otherwise
        """
        task_file = self.by_task_dir / f"{task_id}.json"
        return task_file.exists()

    def update_workflow_stage(self, task_id: str, stage: WorkflowStage) -> bool:
        """Update workflow stage for an existing ledger entry.

        Updates just the workflow_stage and workflow_stage_updated_at fields
        without modifying other entry data. This is used by `cub workflow set`
        to progress tasks through post-completion stages.

        Args:
            task_id: Task ID to update
            stage: New workflow stage (needs_review, validated, or released)

        Returns:
            True if updated successfully, False if entry doesn't exist

        Example:
            >>> writer = LedgerWriter(Path(".cub/ledger"))
            >>> writer.update_workflow_stage("cub-m4j.6", WorkflowStage.VALIDATED)
            True
        """
        task_file = self.by_task_dir / f"{task_id}.json"
        if not task_file.exists():
            return False

        # Read existing entry
        with task_file.open(encoding="utf-8") as f:
            data = json.load(f)

        # Update workflow stage fields
        data["workflow_stage"] = stage.value
        data["workflow_stage_updated_at"] = datetime.now(timezone.utc).isoformat()

        # Write updated entry
        with task_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        # Rebuild index to reflect the change
        self._rebuild_index()

        return True

    def get_entry(self, task_id: str) -> LedgerEntry | None:
        """Get a ledger entry by task ID.

        Args:
            task_id: Task ID to retrieve

        Returns:
            LedgerEntry if found, None otherwise
        """
        task_file = self.by_task_dir / f"{task_id}.json"
        if not task_file.exists():
            return None

        with task_file.open(encoding="utf-8") as f:
            data = json.load(f)
            return LedgerEntry.model_validate(data)

    def write_prompt_file(
        self,
        task_id: str,
        attempt_number: int,
        prompt_content: str,
        *,
        harness: str = "",
        model: str = "",
        run_id: str = "",
        started_at: datetime | None = None,
    ) -> Path:
        """Write a prompt file with YAML frontmatter for an attempt.

        Creates the attempts directory if needed and writes a prompt file
        with YAML frontmatter containing execution context metadata.

        Args:
            task_id: Task ID (e.g., 'cub-abc')
            attempt_number: Attempt sequence number (1-based)
            prompt_content: The prompt content (markdown)
            harness: Harness name (e.g., 'claude')
            model: Model name (e.g., 'haiku', 'sonnet')
            run_id: Run session ID this attempt belongs to
            started_at: Attempt start time (defaults to now)

        Returns:
            Path to the written prompt file

        Example:
            >>> writer = LedgerWriter(Path(".cub/ledger"))
            >>> path = writer.write_prompt_file(
            ...     "cub-abc", 1, "# Task: Fix login\\n...",
            ...     harness="claude", model="haiku", run_id="cub-20260124-123456"
            ... )
            >>> # Creates: .cub/ledger/by-task/cub-abc/attempts/001-prompt.md
        """
        # Ensure task directory exists
        task_dir = self.by_task_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # Ensure attempts directory exists
        attempts_dir = task_dir / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)

        # Format attempt number as zero-padded 3 digits
        attempt_str = f"{attempt_number:03d}"
        prompt_file = attempts_dir / f"{attempt_str}-prompt.md"

        # Prepare frontmatter
        frontmatter = {
            "attempt": attempt_number,
            "harness": harness,
            "model": model,
            "run_id": run_id,
            "started_at": (started_at or datetime.now(timezone.utc)).isoformat(),
        }

        # Build the full content with YAML frontmatter
        content_parts = [
            "---",
            yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip(),
            "---",
            "",
            prompt_content,
        ]
        full_content = "\n".join(content_parts)

        # Write to file
        prompt_file.write_text(full_content, encoding="utf-8")

        return prompt_file

    def write_harness_log(
        self,
        task_id: str,
        attempt_number: int,
        log_content: str,
    ) -> Path:
        """Write a harness log file for an attempt.

        Creates the attempts directory if needed and writes the harness
        output log.

        Args:
            task_id: Task ID (e.g., 'cub-abc')
            attempt_number: Attempt sequence number (1-based)
            log_content: The harness log content

        Returns:
            Path to the written log file

        Example:
            >>> writer = LedgerWriter(Path(".cub/ledger"))
            >>> path = writer.write_harness_log(
            ...     "cub-abc", 1, "Harness output here..."
            ... )
            >>> # Creates: .cub/ledger/by-task/cub-abc/attempts/001-harness.log
        """
        # Ensure task directory exists
        task_dir = self.by_task_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # Ensure attempts directory exists
        attempts_dir = task_dir / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)

        # Format attempt number as zero-padded 3 digits
        attempt_str = f"{attempt_number:03d}"
        log_file = attempts_dir / f"{attempt_str}-harness.log"

        # Write log content
        log_file.write_text(log_content, encoding="utf-8")

        return log_file
