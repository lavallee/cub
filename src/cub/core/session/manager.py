"""
Run session manager for cub.

This module provides the RunSessionManager class that handles the lifecycle
of run sessions: creating files, managing the symlink, detecting orphans,
and updating progress.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from cub.core.session.models import RunSession, SessionBudget, SessionStatus, generate_run_id


class RunSessionError(Exception):
    """Error from run session manager operations."""

    pass


class RunSessionManager:
    """
    Manages run session lifecycle and persistence.

    Handles creation, updates, and detection of orphaned run sessions.
    Uses symlink-based detection to identify active sessions and mark
    abandoned ones.

    Directory structure:
        .cub/ledger/by-run/
        ├── cub-20260124-143022.json
        ├── cub-20260124-150315.json
        └── active-run.json -> cub-20260124-150315.json

    Example:
        >>> manager = RunSessionManager(Path.cwd() / ".cub")
        >>> session = manager.start_session("claude", SessionBudget(tokens_limit=100000))
        >>> manager.update_session(session.run_id, tasks_completed=1)
        >>> manager.end_session(session.run_id)
    """

    SESSIONS_DIR = "ledger/by-run"
    ACTIVE_SYMLINK = "active-run.json"

    def __init__(self, cub_dir: Path) -> None:
        """
        Initialize RunSessionManager.

        Args:
            cub_dir: Path to .cub directory (e.g., /path/to/project/.cub)
        """
        self.cub_dir = cub_dir
        self.sessions_dir = cub_dir / self.SESSIONS_DIR
        self.active_symlink_path = self.sessions_dir / self.ACTIVE_SYMLINK

    def _ensure_sessions_dir(self) -> None:
        """Ensure ledger/by-run directory exists."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_file_path(self, run_id: str) -> Path:
        """Get path to session file for a run ID."""
        return self.sessions_dir / f"{run_id}.json"

    def _read_session_file(self, run_id: str) -> RunSession:
        """
        Read and parse a session file.

        Args:
            run_id: Run ID to read

        Returns:
            RunSession object

        Raises:
            RunSessionError: If file doesn't exist or is invalid
        """
        session_file = self._get_session_file_path(run_id)
        if not session_file.exists():
            raise RunSessionError(f"Session file not found: {run_id}")

        try:
            content = session_file.read_text()
            data = json.loads(content)
            return RunSession.model_validate(data)
        except json.JSONDecodeError as e:
            raise RunSessionError(f"Invalid JSON in session file {run_id}: {e}") from e
        except Exception as e:
            raise RunSessionError(f"Failed to parse session file {run_id}: {e}") from e

    def _write_session_file(self, session: RunSession) -> None:
        """
        Write session to file.

        Args:
            session: RunSession to write
        """
        self._ensure_sessions_dir()
        session_file = self._get_session_file_path(session.run_id)

        # Convert to JSON with pretty formatting
        data = session.model_dump(mode="json")
        content = json.dumps(data, indent=2, ensure_ascii=False)
        session_file.write_text(content)

    def _update_active_symlink(self, run_id: str) -> None:
        """
        Update active-run.json symlink to point to current session.

        Uses atomic unlink + symlink to avoid race conditions.

        Args:
            run_id: Run ID to symlink to
        """
        self._ensure_sessions_dir()

        # Target file (relative to sessions dir)
        target = f"{run_id}.json"

        # Remove existing symlink if it exists
        if self.active_symlink_path.exists() or self.active_symlink_path.is_symlink():
            self.active_symlink_path.unlink()

        # Create new symlink
        self.active_symlink_path.symlink_to(target)

    def _clear_active_symlink(self) -> None:
        """Remove active-run.json symlink if it exists."""
        if self.active_symlink_path.exists() or self.active_symlink_path.is_symlink():
            self.active_symlink_path.unlink()

    def _mark_orphaned(self, run_id: str, reason: str) -> RunSession:
        """
        Mark a session as orphaned and save.

        Args:
            run_id: Run ID to mark as orphaned
            reason: Reason for orphan status

        Returns:
            Updated RunSession
        """
        session = self._read_session_file(run_id)
        session.mark_orphaned(reason)
        self._write_session_file(session)
        return session

    def start_session(
        self,
        harness: str,
        budget: SessionBudget | None = None,
        project_dir: Path | None = None,
    ) -> RunSession:
        """
        Start a new run session.

        Creates session file and updates active symlink.

        Args:
            harness: Harness name (e.g., "claude", "codex")
            budget: Session budget (defaults to unlimited)
            project_dir: Project directory (defaults to cub_dir parent)

        Returns:
            Created RunSession

        Raises:
            RunSessionError: If session creation fails
        """
        # Generate unique run ID
        run_id = generate_run_id()

        # Default budget to unlimited
        if budget is None:
            budget = SessionBudget()

        # Default project_dir to cub_dir parent
        if project_dir is None:
            project_dir = self.cub_dir.parent

        # Create session
        session = RunSession(
            run_id=run_id,
            started_at=datetime.now(timezone.utc),
            project_dir=project_dir.resolve(),
            harness=harness,
            budget=budget,
            status=SessionStatus.RUNNING,
        )

        # Write session file
        self._write_session_file(session)

        # Update active symlink
        self._update_active_symlink(run_id)

        return session

    def get_active_session(self) -> RunSession | None:
        """
        Get the currently active session.

        Follows the active-run.json symlink to read the current session.

        Returns:
            Active RunSession or None if no active session

        Raises:
            RunSessionError: If symlink exists but points to invalid file
        """
        if not self.active_symlink_path.exists():
            return None

        # Resolve symlink to get run ID
        try:
            resolved = self.active_symlink_path.resolve()
            run_id = resolved.stem  # Remove .json extension
            return self._read_session_file(run_id)
        except RunSessionError:
            # Symlink exists but target is gone or invalid
            self._clear_active_symlink()
            return None

    def update_session(
        self,
        run_id: str,
        tasks_completed: int | None = None,
        tasks_failed: int | None = None,
        current_task: str | None = None,
        budget: SessionBudget | None = None,
    ) -> RunSession:
        """
        Update an existing session.

        Args:
            run_id: Run ID to update
            tasks_completed: Number of tasks completed (optional)
            tasks_failed: Number of tasks failed (optional)
            current_task: Currently executing task ID (optional)
            budget: Updated budget tracking (optional)

        Returns:
            Updated RunSession

        Raises:
            RunSessionError: If session not found or update fails
        """
        # Read current session
        session = self._read_session_file(run_id)

        # Update fields if provided
        if tasks_completed is not None:
            session.tasks_completed = tasks_completed
        if tasks_failed is not None:
            session.tasks_failed = tasks_failed
        if current_task is not None:
            session.current_task = current_task
        if budget is not None:
            session.budget = budget

        # Write updated session
        self._write_session_file(session)

        return session

    def end_session(self, run_id: str) -> RunSession:
        """
        End a run session normally.

        Marks session as completed and clears active symlink.

        Args:
            run_id: Run ID to end

        Returns:
            Completed RunSession

        Raises:
            RunSessionError: If session not found
        """
        # Read current session
        session = self._read_session_file(run_id)

        # Mark as completed
        session.mark_completed()

        # Write updated session
        self._write_session_file(session)

        # Clear active symlink if it points to this session
        active = self.get_active_session()
        if active and active.run_id == run_id:
            self._clear_active_symlink()

        return session

    def detect_orphans(self) -> list[RunSession]:
        """
        Detect and mark orphaned run sessions.

        A session is orphaned if:
        1. It has status=RUNNING
        2. It's not the current active session

        Returns:
            List of newly detected orphaned sessions

        Raises:
            RunSessionError: If detection fails
        """
        orphaned_sessions: list[RunSession] = []

        # Ensure directory exists
        if not self.sessions_dir.exists():
            return orphaned_sessions

        # Get active session run_id (if any)
        active_session = self.get_active_session()
        active_run_id = active_session.run_id if active_session else None

        # Scan all session files
        for session_file in self.sessions_dir.glob("*.json"):
            # Skip the symlink itself
            if session_file.name == self.ACTIVE_SYMLINK:
                continue

            run_id = session_file.stem

            try:
                session = self._read_session_file(run_id)

                # Check if session should be marked orphaned
                if session.status == SessionStatus.RUNNING and run_id != active_run_id:
                    # Mark as orphaned
                    orphaned_session = self._mark_orphaned(
                        run_id,
                        reason="Session was still running but not active (process died or crash)",
                    )
                    orphaned_sessions.append(orphaned_session)

            except RunSessionError:
                # Skip invalid session files
                continue

        return orphaned_sessions
