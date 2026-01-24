"""
Ledger integration layer for cub.

Coordinates all ledger writes during task execution, providing a clean interface
for the run loop. This layer bridges the gap between task execution events and
the underlying ledger storage.

The integration handles:
- Task start: Create initial ledger entry with task snapshot
- Attempt start: Write prompt file with YAML frontmatter
- Attempt end: Write harness log and append attempt record
- Task close: Finalize ledger entry with outcome and drift detection

Example:
    >>> from cub.core.ledger import LedgerIntegration, LedgerWriter
    >>> from pathlib import Path
    >>>
    >>> ledger_dir = Path(".cub/ledger")
    >>> writer = LedgerWriter(ledger_dir)
    >>> integration = LedgerIntegration(writer)
    >>>
    >>> # On task start
    >>> integration.on_task_start(task, run_id="cub-20260124-163241", epic_id="cub-l7e")
    >>>
    >>> # On each attempt
    >>> integration.on_attempt_start(task.id, 1, prompt, harness="claude", model="haiku")
    >>> integration.on_attempt_end(task.id, 1, harness_output, result, duration=45)
    >>>
    >>> # On task close
    >>> integration.on_task_close(task.id, success=True, final_model="haiku")
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.ledger.models import (
    Attempt,
    LedgerEntry,
    Lineage,
    Outcome,
    StateTransition,
    TaskChanged,
    TaskSnapshot,
    TokenUsage,
    Verification,
    WorkflowState,
)
from cub.core.ledger.writer import LedgerWriter

if TYPE_CHECKING:
    from cub.core.tasks.models import Task


class LedgerIntegration:
    """Coordinate ledger writes during task execution.

    Provides a high-level interface for the run loop to interact with the ledger
    system. Manages the lifecycle of ledger entries from task start to close.

    Attributes:
        writer: The underlying LedgerWriter for file operations
        _active_entries: Cache of in-progress ledger entries keyed by task_id
        _task_snapshots: Original task snapshots for drift detection
    """

    def __init__(self, writer: LedgerWriter) -> None:
        """Initialize the ledger integration.

        Args:
            writer: LedgerWriter instance for file operations
        """
        self.writer = writer
        self._active_entries: dict[str, LedgerEntry] = {}
        self._task_snapshots: dict[str, TaskSnapshot] = {}

    def on_task_start(
        self,
        task: Task,
        *,
        run_id: str,
        epic_id: str | None = None,
        spec_file: str | None = None,
        plan_file: str | None = None,
    ) -> LedgerEntry:
        """Handle task start event - creates initial ledger entry.

        Creates a new ledger entry with a snapshot of the task state. This
        captures the task definition at the start of execution for drift
        detection later.

        Args:
            task: The Task object being started
            run_id: Current run session ID
            epic_id: Optional parent epic ID
            spec_file: Optional path to spec file
            plan_file: Optional path to plan file

        Returns:
            The created LedgerEntry (in-progress)

        Raises:
            ValueError: If a ledger entry already exists for this task in this session
        """
        if task.id in self._active_entries:
            raise ValueError(f"Ledger entry already active for task {task.id}")

        now = datetime.now(timezone.utc)

        # Create task snapshot for drift detection
        task_snapshot = TaskSnapshot(
            title=task.title,
            description=task.description,
            type=task.type.value if hasattr(task.type, "value") else str(task.type),
            priority=task.priority_numeric,
            labels=list(task.labels),
            created_at=task.created_at,
            captured_at=now,
        )
        self._task_snapshots[task.id] = task_snapshot

        # Create lineage
        lineage = Lineage(
            spec_file=spec_file,
            plan_file=plan_file,
            epic_id=epic_id or task.parent,
        )

        # Create initial workflow state
        workflow = WorkflowState(
            stage="dev_complete",
            stage_updated_at=now,
        )

        # Create initial state history
        state_history = [
            StateTransition(
                stage="dev_complete",
                at=now,
                by="cub-run",
                reason="Task execution started",
            )
        ]

        # Create ledger entry
        entry = LedgerEntry(
            id=task.id,
            title=task.title,
            lineage=lineage,
            task=task_snapshot,
            attempts=[],
            started_at=now,
            completed_at=now,  # Will be updated on close
            workflow=workflow,
            state_history=state_history,
            # Legacy fields for backward compatibility
            epic_id=epic_id or task.parent,
            run_log_path=str(self.writer.by_task_dir / task.id),
        )

        # Cache active entry
        self._active_entries[task.id] = entry

        # Write initial entry to disk
        self.writer.create_entry(entry)

        return entry

    def on_attempt_start(
        self,
        task_id: str,
        attempt_number: int,
        prompt_content: str,
        *,
        run_id: str,
        harness: str = "",
        model: str = "",
    ) -> Path:
        """Handle attempt start event - writes prompt file.

        Writes the prompt file with YAML frontmatter capturing execution context.
        This creates an audit trail of what was sent to the harness.

        Args:
            task_id: Task ID being worked on
            attempt_number: Attempt sequence number (1-based)
            prompt_content: The prompt content (markdown)
            run_id: Current run session ID
            harness: Harness name (e.g., 'claude')
            model: Model name (e.g., 'haiku', 'sonnet')

        Returns:
            Path to the written prompt file

        Note:
            This method doesn't require an active entry - it can be called
            for tasks that weren't started through on_task_start() (e.g.,
            resumed tasks or legacy tasks).
        """
        now = datetime.now(timezone.utc)

        prompt_path = self.writer.write_prompt_file(
            task_id,
            attempt_number,
            prompt_content,
            harness=harness,
            model=model,
            run_id=run_id,
            started_at=now,
        )

        return prompt_path

    def on_attempt_end(
        self,
        task_id: str,
        attempt_number: int,
        log_content: str,
        *,
        run_id: str,
        success: bool,
        harness: str = "",
        model: str = "",
        tokens: TokenUsage | None = None,
        cost_usd: float = 0.0,
        duration_seconds: int = 0,
        error_category: str | None = None,
        error_summary: str | None = None,
        started_at: datetime | None = None,
    ) -> Attempt:
        """Handle attempt end event - writes log and records attempt.

        Writes the harness output log and appends an attempt record to the
        ledger entry's attempts list.

        Args:
            task_id: Task ID being worked on
            attempt_number: Attempt sequence number (1-based)
            log_content: The harness output log content
            run_id: Current run session ID
            success: Whether the attempt succeeded
            harness: Harness name (e.g., 'claude')
            model: Model name (e.g., 'haiku', 'sonnet')
            tokens: Token usage for this attempt
            cost_usd: Cost for this attempt in USD
            duration_seconds: Attempt duration in seconds
            error_category: Category of error if failed
            error_summary: Brief error description if failed
            started_at: When the attempt started (for duration calculation)

        Returns:
            The Attempt record that was created

        Note:
            If no active entry exists for this task, a minimal entry will be
            created to store the attempt data.
        """
        now = datetime.now(timezone.utc)

        # Write harness log
        self.writer.write_harness_log(task_id, attempt_number, log_content)

        # Create attempt record
        attempt = Attempt(
            attempt_number=attempt_number,
            run_id=run_id,
            started_at=started_at or now,
            completed_at=now,
            harness=harness,
            model=model,
            success=success,
            error_category=error_category,
            error_summary=error_summary,
            tokens=tokens or TokenUsage(),
            cost_usd=cost_usd,
            duration_seconds=duration_seconds,
        )

        # Update active entry if we have one
        if task_id in self._active_entries:
            entry = self._active_entries[task_id]
            entry.attempts.append(attempt)
            # Update legacy token tracking
            entry.tokens = TokenUsage(
                input_tokens=entry.tokens.input_tokens + (tokens.input_tokens if tokens else 0),
                output_tokens=entry.tokens.output_tokens + (tokens.output_tokens if tokens else 0),
                cache_read_tokens=entry.tokens.cache_read_tokens
                + (tokens.cache_read_tokens if tokens else 0),
                cache_creation_tokens=entry.tokens.cache_creation_tokens
                + (tokens.cache_creation_tokens if tokens else 0),
            )
            entry.cost_usd += cost_usd
            entry.duration_seconds += duration_seconds
            entry.iterations = len(entry.attempts)
            # Update harness info with latest
            entry.harness_name = harness
            entry.harness_model = model
            # Write updated entry
            self.writer.update_entry(entry)
        else:
            # No active entry - try to load from disk and update
            existing_entry = self.writer.get_entry(task_id)
            if existing_entry:
                existing_entry.attempts.append(attempt)
                existing_entry.iterations = len(existing_entry.attempts)
                self.writer.update_entry(existing_entry)

        return attempt

    def on_task_close(
        self,
        task_id: str,
        *,
        success: bool,
        partial: bool = False,
        final_model: str = "",
        files_changed: list[str] | None = None,
        approach: str | None = None,
        decisions: list[str] | None = None,
        lessons_learned: list[str] | None = None,
        verification: Verification | None = None,
        current_task: Task | None = None,
    ) -> LedgerEntry | None:
        """Handle task close event - finalizes ledger entry.

        Finalizes the ledger entry with outcome, drift detection, and
        verification status. This completes the task record.

        Args:
            task_id: Task ID being closed
            success: Whether the task completed successfully
            partial: Whether the task was partially completed
            final_model: Model used in final successful attempt
            files_changed: Files modified during task execution
            approach: Approach taken (markdown)
            decisions: Key decisions made during implementation
            lessons_learned: Lessons learned during implementation
            verification: Verification and quality gate status
            current_task: Current task state for drift detection

        Returns:
            The finalized LedgerEntry, or None if no entry exists
        """
        now = datetime.now(timezone.utc)

        # Get entry (from cache or disk)
        entry = self._active_entries.get(task_id)
        if not entry:
            entry = self.writer.get_entry(task_id)
        if not entry:
            return None

        # Calculate aggregates from attempts
        total_cost = sum(a.cost_usd for a in entry.attempts)
        total_duration = sum(a.duration_seconds for a in entry.attempts)
        total_attempts = len(entry.attempts)

        # Detect escalation (model changes across attempts)
        models_used = [a.model for a in entry.attempts if a.model]
        unique_models = list(dict.fromkeys(models_used))  # Preserve order, remove duplicates
        escalated = len(unique_models) > 1

        # Create outcome
        outcome = Outcome(
            success=success,
            partial=partial,
            completed_at=now,
            total_cost_usd=total_cost,
            total_attempts=total_attempts,
            total_duration_seconds=total_duration,
            final_model=final_model or (entry.attempts[-1].model if entry.attempts else ""),
            escalated=escalated,
            escalation_path=unique_models if escalated else [],
            files_changed=files_changed or [],
            approach=approach,
            decisions=decisions or [],
            lessons_learned=lessons_learned or [],
        )
        entry.outcome = outcome

        # Detect task drift
        if current_task:
            task_changed = self._detect_task_changed(task_id, current_task)
            if task_changed:
                entry.task_changed = task_changed

        # Update verification if provided
        if verification:
            entry.verification = verification

        # Update workflow stage
        stage = "dev_complete" if success else "dev_complete"
        entry.workflow = WorkflowState(stage=stage, stage_updated_at=now)
        entry.state_history.append(
            StateTransition(
                stage=stage,
                at=now,
                by="cub-run",
                reason="Task closed" + (" successfully" if success else " with errors"),
            )
        )

        # Update legacy fields
        entry.completed_at = now
        entry.files_changed = files_changed or []
        entry.approach = approach or ""
        entry.decisions = decisions or []
        entry.lessons_learned = lessons_learned or []

        # Write finalized entry
        self.writer.update_entry(entry)

        # Cleanup cache
        self._active_entries.pop(task_id, None)
        self._task_snapshots.pop(task_id, None)

        return entry

    def _detect_task_changed(
        self,
        task_id: str,
        current_task: Task,
    ) -> TaskChanged | None:
        """Detect if task definition changed during implementation.

        Compares the current task state with the snapshot captured at
        task start to detect drift (scope creep, requirement changes, etc.).

        Args:
            task_id: Task ID to check
            current_task: Current task state

        Returns:
            TaskChanged record if drift detected, None otherwise
        """
        original = self._task_snapshots.get(task_id)
        if not original:
            return None

        now = datetime.now(timezone.utc)
        fields_changed: list[str] = []
        notes_parts: list[str] = []

        # Check title change
        if current_task.title != original.title:
            fields_changed.append("title")
            notes_parts.append(f"Title: '{original.title}' -> '{current_task.title}'")

        # Check description change
        if current_task.description != original.description:
            fields_changed.append("description")

        # Check priority change
        if current_task.priority_numeric != original.priority:
            fields_changed.append("priority")
            notes_parts.append(f"Priority: {original.priority} -> {current_task.priority_numeric}")

        # Check labels change
        current_labels = set(current_task.labels)
        original_labels = set(original.labels)
        if current_labels != original_labels:
            fields_changed.append("labels")
            added = current_labels - original_labels
            removed = original_labels - current_labels
            if added:
                notes_parts.append(f"Labels added: {', '.join(added)}")
            if removed:
                notes_parts.append(f"Labels removed: {', '.join(removed)}")

        # Check type change
        if hasattr(current_task.type, "value"):
            current_type = current_task.type.value
        else:
            current_type = str(current_task.type)
        if current_type != original.type:
            fields_changed.append("type")
            notes_parts.append(f"Type: {original.type} -> {current_type}")

        # If no changes detected, return None
        if not fields_changed:
            return None

        return TaskChanged(
            detected_at=now,
            fields_changed=fields_changed,
            original_description=original.description,
            final_description=current_task.description,
            notes="; ".join(notes_parts) if notes_parts else None,
        )

    def get_active_entry(self, task_id: str) -> LedgerEntry | None:
        """Get the active (in-progress) ledger entry for a task.

        Args:
            task_id: Task ID to look up

        Returns:
            The active LedgerEntry or None if not found
        """
        return self._active_entries.get(task_id)

    def has_active_entry(self, task_id: str) -> bool:
        """Check if there's an active ledger entry for a task.

        Args:
            task_id: Task ID to check

        Returns:
            True if an active entry exists
        """
        return task_id in self._active_entries

    def get_attempt_count(self, task_id: str) -> int:
        """Get the number of attempts for a task.

        Args:
            task_id: Task ID to check

        Returns:
            Number of attempts (0 if no entry exists)
        """
        entry = self._active_entries.get(task_id)
        if entry:
            return len(entry.attempts)

        # Check disk
        entry = self.writer.get_entry(task_id)
        if entry:
            return len(entry.attempts)

        return 0
