"""
Session-based ledger integration for direct harness sessions.

This module provides ledger integration for direct harness sessions (Claude Code, etc.)
where events arrive incrementally across separate process invocations. Unlike the run
loop's LedgerIntegration which maintains state in memory, SessionLedgerIntegration
reconstructs state from forensics logs on each invocation.

Key Differences from LedgerIntegration:
- Stateless: Each method call reads forensics JSONL to rebuild session state
- Task association: Tasks may be claimed mid-session, not at start
- Synthesis: Ledger entry is synthesized at session end from forensics log
- Partial data: Session may end without task association (no ledger entry)

Example:
    >>> from cub.core.ledger import SessionLedgerIntegration, LedgerWriter
    >>> from pathlib import Path
    >>>
    >>> ledger_dir = Path(".cub/ledger")
    >>> writer = LedgerWriter(ledger_dir)
    >>> integration = SessionLedgerIntegration(writer)
    >>>
    >>> # On session end (reads forensics to synthesize entry)
    >>> entry = integration.on_session_end(
    ...     session_id="claude-20260128-123456",
    ...     forensics_path=Path(".cub/ledger/forensics/claude-20260128-123456.jsonl")
    ... )
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cub.core.ledger.models import (
    Attempt,
    CommitRef,
    LedgerEntry,
    Lineage,
    Outcome,
    StateTransition,
    TaskSnapshot,
    TokenUsage,
    Verification,
    WorkflowState,
)
from cub.core.ledger.writer import LedgerWriter

if TYPE_CHECKING:
    from cub.core.tasks.models import Task


class SessionState:
    """Reconstructed state from forensics log.

    This class holds the state extracted from a forensics JSONL file,
    representing what happened during a direct harness session.

    Attributes:
        session_id: Session identifier
        started_at: When the session started
        ended_at: When the session ended (if available)
        task_id: Task ID if claimed during session
        task_claimed_at: When the task was claimed
        task_closed_at: When the task was closed
        task_close_reason: Reason for task closure
        files_written: List of files written during session
        plan_files: List of plan files written
        spec_files: List of spec files written
        git_commits: List of git commit commands detected
        transcript_path: Path to session transcript
        has_task: Whether a task was associated
    """

    def __init__(self) -> None:
        """Initialize empty session state."""
        self.session_id: str | None = None
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.task_id: str | None = None
        self.task_claimed_at: datetime | None = None
        self.task_closed_at: datetime | None = None
        self.task_close_reason: str | None = None
        self.files_written: list[str] = []
        self.plan_files: list[str] = []
        self.spec_files: list[str] = []
        self.git_commits: list[dict[str, Any]] = []
        self.transcript_path: str | None = None

    @property
    def has_task(self) -> bool:
        """Check if a task was associated with this session."""
        return self.task_id is not None

    @property
    def duration_seconds(self) -> int:
        """Calculate session duration in seconds."""
        if not self.started_at or not self.ended_at:
            return 0
        return int((self.ended_at - self.started_at).total_seconds())


class SessionLedgerIntegration:
    """Ledger integration for direct harness sessions.

    This class provides ledger integration for sessions where work is done directly
    in a harness (Claude Code, etc.) rather than via `cub run`. It reconstructs
    session state from forensics logs and synthesizes ledger entries at session end.

    The integration is stateless - each method call reads the forensics log from
    scratch to rebuild the current state. This matches the hook execution model
    where each hook invocation is a separate process.

    Attributes:
        writer: The underlying LedgerWriter for file operations
    """

    def __init__(self, writer: LedgerWriter) -> None:
        """Initialize session ledger integration.

        Args:
            writer: LedgerWriter instance for file operations
        """
        self.writer = writer

    def read_forensics(self, forensics_path: Path) -> SessionState:
        """Read and parse forensics JSONL to reconstruct session state.

        Reads the forensics log line by line, parsing each event and building
        up the session state incrementally.

        Args:
            forensics_path: Path to forensics JSONL file

        Returns:
            SessionState object with reconstructed state

        Raises:
            FileNotFoundError: If forensics file doesn't exist
        """
        state = SessionState()

        if not forensics_path.exists():
            raise FileNotFoundError(f"Forensics file not found: {forensics_path}")

        with forensics_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                self._process_event(state, event)

        return state

    def _process_event(self, state: SessionState, event: dict[str, Any]) -> None:
        """Process a single forensics event and update state.

        Args:
            state: SessionState to update
            event: Parsed event dictionary from forensics log
        """
        event_type = event.get("event_type")
        timestamp_str = event.get("timestamp")

        # Parse timestamp
        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                pass

        # Extract session_id if available
        if not state.session_id and "session_id" in event:
            state.session_id = event["session_id"]

        # Process event by type
        if event_type == "session_start":
            state.started_at = timestamp

        elif event_type == "session_end":
            state.ended_at = timestamp
            if "transcript_path" in event:
                state.transcript_path = event["transcript_path"]

        elif event_type == "task_claim":
            state.task_id = event.get("task_id")
            state.task_claimed_at = timestamp

        elif event_type == "task_close":
            state.task_closed_at = timestamp
            state.task_close_reason = event.get("reason")

        elif event_type == "file_write":
            file_path = event.get("file_path")
            if file_path:
                state.files_written.append(file_path)

                # Categorize by file type
                file_category = event.get("file_category")
                if file_category == "plan":
                    state.plan_files.append(file_path)
                elif file_category == "spec":
                    state.spec_files.append(file_path)

        elif event_type == "git_commit":
            commit_info = {
                "command": event.get("command", ""),
                "message_preview": event.get("message_preview", ""),
                "timestamp": timestamp_str or "",
            }
            state.git_commits.append(commit_info)

    def on_session_end(
        self,
        session_id: str,
        forensics_path: Path,
        *,
        task: Task | None = None,
    ) -> LedgerEntry | None:
        """Handle session end - synthesize ledger entry from forensics.

        This is the main entry point for creating ledger entries from direct
        sessions. It reads the forensics log, reconstructs what happened, and
        creates a ledger entry if a task was associated.

        Args:
            session_id: Session identifier
            forensics_path: Path to forensics JSONL file
            task: Optional Task object for additional context (can load from backend)

        Returns:
            LedgerEntry if a task was associated, None otherwise

        Notes:
            - If no task was claimed during the session, only forensics are kept
            - The ledger entry is synthesized with a single "attempt" representing
              the entire session
            - Token/cost data requires post-hoc transcript parsing (not done here)
        """
        # Read forensics to reconstruct state
        try:
            state = self.read_forensics(forensics_path)
        except FileNotFoundError:
            # No forensics file - nothing to do
            return None

        # If no task was associated, finalize forensics only
        if not state.has_task:
            return None

        task_id = state.task_id
        if not task_id:
            return None

        # Check if entry already exists (may have been created by run loop)
        existing_entry = self.writer.get_entry(task_id)
        if existing_entry and existing_entry.outcome:
            # Entry already finalized - don't overwrite
            return existing_entry

        now = datetime.now(timezone.utc)

        # Create task snapshot if we have task context
        task_snapshot = None
        if task:
            task_snapshot = TaskSnapshot(
                title=task.title,
                description=task.description,
                type=task.type.value if hasattr(task.type, "value") else str(task.type),
                priority=task.priority_numeric,
                labels=list(task.labels),
                created_at=task.created_at,
                captured_at=state.task_claimed_at or state.started_at or now,
            )

        # Create lineage (extract from plan/spec files if available)
        spec_file = state.spec_files[0] if state.spec_files else None
        plan_file = state.plan_files[0] if state.plan_files else None
        epic_id = task.parent if task else None

        lineage = Lineage(
            spec_file=spec_file,
            plan_file=plan_file,
            epic_id=epic_id,
        )

        # Create single attempt representing the entire session
        # Note: tokens/cost require transcript parsing (not implemented here)
        started_at = state.task_claimed_at or state.started_at or now
        completed_at = state.task_closed_at or state.ended_at or now

        # Calculate duration from attempt timestamps (not session duration)
        duration = int((completed_at - started_at).total_seconds())
        # Ensure duration is non-negative
        if duration < 0:
            duration = 0

        attempt = Attempt(
            attempt_number=1,
            run_id=session_id,
            started_at=started_at,
            completed_at=completed_at,
            harness="claude",  # TODO: Extract from session metadata
            model="",  # TODO: Extract from transcript
            success=state.task_closed_at is not None,  # Closed = successful
            error_category=None,
            error_summary=None,
            tokens=TokenUsage(),  # TODO: Parse from transcript
            cost_usd=0.0,  # TODO: Calculate from transcript
            duration_seconds=duration,
        )

        # Parse git commits into CommitRef objects
        commits: list[CommitRef] = []
        for commit_info in state.git_commits:
            # Extract commit hash from message preview if available
            # Format is typically "commit message" but we don't have the hash here
            # This would need to be enriched from actual git log
            pass  # Skip for now - requires git log parsing

        # Create outcome
        outcome = Outcome(
            success=attempt.success,
            partial=False,
            completed_at=attempt.completed_at or now,
            total_cost_usd=attempt.cost_usd,
            total_attempts=1,
            total_duration_seconds=attempt.duration_seconds,
            final_model=attempt.model,
            escalated=False,
            escalation_path=[],
            files_changed=state.files_written,
            commits=commits,
            approach=None,  # TODO: Extract from transcript
            decisions=[],
            lessons_learned=[],
        )

        # Create workflow state
        workflow = WorkflowState(
            stage="dev_complete",
            stage_updated_at=now,
        )

        # Create state history
        state_history = [
            StateTransition(
                stage="dev_complete",
                at=now,
                by="direct-session",
                reason=f"Session {session_id} completed",
            )
        ]

        # Create verification record (default pending)
        verification = Verification(
            status="pending",
            checked_at=None,
            tests_passed=None,
            typecheck_passed=None,
            lint_passed=None,
            notes=[],
        )

        # Create or update ledger entry
        if existing_entry:
            # Update existing entry (add session attempt)
            existing_entry.attempts.append(attempt)
            existing_entry.outcome = outcome
            existing_entry.verification = verification
            existing_entry.workflow = workflow
            existing_entry.state_history.append(state_history[0])
            existing_entry.completed_at = now

            # Update legacy fields
            existing_entry.iterations = len(existing_entry.attempts)
            existing_entry.tokens = TokenUsage(
                input_tokens=existing_entry.tokens.input_tokens + attempt.tokens.input_tokens,
                output_tokens=existing_entry.tokens.output_tokens + attempt.tokens.output_tokens,
                cache_read_tokens=(
                    existing_entry.tokens.cache_read_tokens + attempt.tokens.cache_read_tokens
                ),
                cache_creation_tokens=(
                    existing_entry.tokens.cache_creation_tokens
                    + attempt.tokens.cache_creation_tokens
                ),
            )
            existing_entry.cost_usd += attempt.cost_usd
            existing_entry.duration_seconds += attempt.duration_seconds
            existing_entry.files_changed = state.files_written
            existing_entry.commits = commits

            self.writer.update_entry(existing_entry)
            return existing_entry
        else:
            # Create new entry
            entry = LedgerEntry(
                id=task_id,
                title=task.title if task else task_id,
                lineage=lineage,
                task=task_snapshot,
                attempts=[attempt],
                outcome=outcome,
                verification=verification,
                workflow=workflow,
                state_history=state_history,
                started_at=state.task_claimed_at or state.started_at or now,
                completed_at=now,
                # Legacy fields
                epic_id=epic_id,
                run_log_path=str(self.writer.by_task_dir / task_id),
                iterations=1,
                tokens=attempt.tokens,
                cost_usd=attempt.cost_usd,
                duration_seconds=attempt.duration_seconds,
                harness_name=attempt.harness,
                harness_model=attempt.model,
                files_changed=state.files_written,
                commits=commits,
                approach="",
                decisions=[],
                lessons_learned=[],
            )

            self.writer.create_entry(entry)
            return entry

    def finalize_forensics(self, forensics_path: Path) -> SessionState | None:
        """Finalize forensics log without creating ledger entry.

        This is used when a session ends but no task was associated. The
        forensics log is kept for audit purposes but no ledger entry is created.

        Args:
            forensics_path: Path to forensics JSONL file

        Returns:
            SessionState if forensics exist, None otherwise
        """
        try:
            state = self.read_forensics(forensics_path)
            return state
        except FileNotFoundError:
            return None

    def get_session_state(self, forensics_path: Path) -> SessionState | None:
        """Get current session state by reading forensics.

        Utility method for inspecting session state at any point.

        Args:
            forensics_path: Path to forensics JSONL file

        Returns:
            SessionState if forensics exist, None otherwise
        """
        try:
            return self.read_forensics(forensics_path)
        except FileNotFoundError:
            return None
