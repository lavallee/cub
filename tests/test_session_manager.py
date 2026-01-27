"""Tests for run session manager."""

from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from cub.core.session.manager import RunSessionError, RunSessionManager
from cub.core.session.models import RunSession, SessionBudget, SessionStatus


def _make_run_id_factory() -> Iterator[str]:
    """Yield unique run_id values without sleeping."""
    counter = 0
    while True:
        counter += 1
        yield f"cub-20260127-{counter:06d}"


@pytest.fixture
def cub_dir(tmp_path: Path) -> Path:
    """Create a temporary .cub directory."""
    cub = tmp_path / ".cub"
    cub.mkdir()
    return cub


@pytest.fixture
def manager(cub_dir: Path) -> Iterator[RunSessionManager]:
    """Create a RunSessionManager with deterministic run IDs."""
    factory = _make_run_id_factory()
    with patch(
        "cub.core.session.manager.generate_run_id",
        side_effect=lambda: next(factory),
    ):
        yield RunSessionManager(cub_dir)


def test_init_creates_sessions_dir(manager: RunSessionManager) -> None:
    """Test that starting a session creates the sessions directory."""
    session = manager.start_session("claude")
    assert manager.sessions_dir.exists()
    assert session.harness == "claude"


def test_start_session_creates_file(manager: RunSessionManager) -> None:
    """Test that starting a session creates a session file."""
    session = manager.start_session("claude")

    session_file = manager.sessions_dir / f"{session.run_id}.json"
    assert session_file.exists()

    # Verify session properties
    assert session.status == SessionStatus.RUNNING
    assert session.harness == "claude"
    assert session.tasks_completed == 0
    assert session.tasks_failed == 0


def test_start_session_creates_active_symlink(manager: RunSessionManager) -> None:
    """Test that starting a session creates active-run.json symlink."""
    session = manager.start_session("claude")

    symlink = manager.active_symlink_path
    assert symlink.exists()
    assert symlink.is_symlink()

    # Verify symlink points to correct file
    resolved = symlink.resolve()
    assert resolved.stem == session.run_id


def test_start_session_with_budget(manager: RunSessionManager) -> None:
    """Test starting a session with custom budget."""
    budget = SessionBudget(tokens_limit=100000, cost_limit=1.0)
    session = manager.start_session("claude", budget=budget)

    assert session.budget.tokens_limit == 100000
    assert session.budget.cost_limit == 1.0


def test_start_session_with_project_dir(manager: RunSessionManager, tmp_path: Path) -> None:
    """Test starting a session with custom project directory."""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()

    session = manager.start_session("claude", project_dir=project_dir)
    assert session.project_dir == project_dir.resolve()


def test_get_active_session(manager: RunSessionManager) -> None:
    """Test retrieving the active session."""
    created_session = manager.start_session("claude")

    active_session = manager.get_active_session()
    assert active_session is not None
    assert active_session.run_id == created_session.run_id
    assert active_session.harness == "claude"


def test_get_active_session_no_active(manager: RunSessionManager) -> None:
    """Test get_active_session returns None when no active session."""
    active_session = manager.get_active_session()
    assert active_session is None


def test_get_active_session_missing_target(manager: RunSessionManager) -> None:
    """Test get_active_session handles missing symlink target gracefully."""
    # Create session and get its ID
    session = manager.start_session("claude")
    run_id = session.run_id

    # Delete the session file but leave symlink
    session_file = manager.sessions_dir / f"{run_id}.json"
    session_file.unlink()

    # Should return None and clean up symlink
    active_session = manager.get_active_session()
    assert active_session is None
    assert not manager.active_symlink_path.exists()


def test_update_session_tasks(manager: RunSessionManager) -> None:
    """Test updating session task counts."""
    session = manager.start_session("claude")

    updated = manager.update_session(
        session.run_id,
        tasks_completed=3,
        tasks_failed=1,
    )

    assert updated.tasks_completed == 3
    assert updated.tasks_failed == 1
    assert updated.tasks_total == 4


def test_update_session_current_task(manager: RunSessionManager) -> None:
    """Test updating current task ID."""
    session = manager.start_session("claude")

    updated = manager.update_session(
        session.run_id,
        current_task="beads-123",
    )

    assert updated.current_task == "beads-123"


def test_update_session_budget(manager: RunSessionManager) -> None:
    """Test updating session budget."""
    session = manager.start_session("claude")

    new_budget = SessionBudget(tokens_used=5000, cost_usd=0.25)
    updated = manager.update_session(session.run_id, budget=new_budget)

    assert updated.budget.tokens_used == 5000
    assert updated.budget.cost_usd == 0.25


def test_update_session_not_found(manager: RunSessionManager) -> None:
    """Test updating non-existent session raises error."""
    with pytest.raises(RunSessionError, match="Session file not found"):
        manager.update_session("cub-20260124-000000")


def test_end_session(manager: RunSessionManager) -> None:
    """Test ending a session."""
    session = manager.start_session("claude")

    ended = manager.end_session(session.run_id)

    assert ended.status == SessionStatus.COMPLETED
    assert ended.ended_at is not None
    assert ended.ended_at >= session.started_at


def test_end_session_clears_symlink(manager: RunSessionManager) -> None:
    """Test ending a session clears the active symlink."""
    session = manager.start_session("claude")
    assert manager.active_symlink_path.exists()

    manager.end_session(session.run_id)
    assert not manager.active_symlink_path.exists()


def test_end_session_keeps_symlink_if_different(manager: RunSessionManager) -> None:
    """Test ending a session doesn't clear symlink if another session is active."""
    # Start first session
    session1 = manager.start_session("claude")

    # Manually create second session file
    session2 = RunSession(
        run_id="cub-20260124-999999",
        started_at=datetime.now(timezone.utc),
        project_dir=manager.cub_dir.parent,
        harness="codex",
        status=SessionStatus.RUNNING,
    )
    manager._write_session_file(session2)

    # Update symlink to point to session2
    manager._update_active_symlink(session2.run_id)

    # End session1 - symlink should remain
    manager.end_session(session1.run_id)
    assert manager.active_symlink_path.exists()

    # Verify symlink still points to session2
    active = manager.get_active_session()
    assert active is not None
    assert active.run_id == session2.run_id


def test_detect_orphans_empty(manager: RunSessionManager) -> None:
    """Test detect_orphans with no sessions."""
    orphans = manager.detect_orphans()
    assert orphans == []


def test_detect_orphans_no_orphans(manager: RunSessionManager) -> None:
    """Test detect_orphans with active session."""
    manager.start_session("claude")

    orphans = manager.detect_orphans()
    assert orphans == []


def test_detect_orphans_finds_abandoned_session(manager: RunSessionManager) -> None:
    """Test detect_orphans finds abandoned running sessions."""
    # Create first session
    session1 = manager.start_session("claude")
    run_id1 = session1.run_id

    # Create second session (simulates new run)
    manager.start_session("claude")

    # Now session1 should be detected as orphaned
    orphans = manager.detect_orphans()
    assert len(orphans) == 1
    assert orphans[0].run_id == run_id1
    assert orphans[0].status == SessionStatus.ORPHANED
    assert orphans[0].orphaned_reason is not None
    assert "process died or crash" in orphans[0].orphaned_reason.lower()


def test_detect_orphans_marks_session_file(manager: RunSessionManager) -> None:
    """Test detect_orphans updates session file."""
    # Create first session
    session1 = manager.start_session("claude")
    run_id1 = session1.run_id

    # Create second session
    manager.start_session("claude")

    # Detect orphans
    manager.detect_orphans()

    # Read session1 file and verify it's marked orphaned
    updated_session = manager._read_session_file(run_id1)
    assert updated_session.status == SessionStatus.ORPHANED
    assert updated_session.orphaned_at is not None


def test_detect_orphans_ignores_completed(manager: RunSessionManager) -> None:
    """Test detect_orphans ignores completed sessions."""
    # Create and end a session
    session1 = manager.start_session("claude")
    manager.end_session(session1.run_id)

    # Create new active session
    manager.start_session("claude")

    # Should not detect completed session as orphan
    orphans = manager.detect_orphans()
    assert orphans == []


def test_detect_orphans_ignores_already_orphaned(manager: RunSessionManager) -> None:
    """Test detect_orphans doesn't re-mark already orphaned sessions."""
    # Create first session
    manager.start_session("claude")

    # Create second session (orphans first)
    manager.start_session("claude")

    # First detection
    orphans1 = manager.detect_orphans()
    assert len(orphans1) == 1

    # Second detection - should not return already orphaned
    orphans2 = manager.detect_orphans()
    assert orphans2 == []


def test_update_active_symlink_atomic_replacement(manager: RunSessionManager) -> None:
    """Test active symlink replacement is atomic."""
    # Create first session
    manager.start_session("claude")

    # Manually create second session
    session2 = RunSession(
        run_id="cub-20260124-888888",
        started_at=datetime.now(timezone.utc),
        project_dir=manager.cub_dir.parent,
        harness="codex",
        status=SessionStatus.RUNNING,
    )
    manager._write_session_file(session2)

    # Update symlink to session2
    manager._update_active_symlink(session2.run_id)

    # Verify symlink was updated
    active = manager.get_active_session()
    assert active is not None
    assert active.run_id == session2.run_id


def test_read_session_invalid_json(manager: RunSessionManager, cub_dir: Path) -> None:
    """Test reading session with invalid JSON raises error."""
    # Create invalid session file
    sessions_dir = cub_dir / "run-sessions"
    sessions_dir.mkdir(exist_ok=True)
    invalid_file = sessions_dir / "cub-20260124-000000.json"
    invalid_file.write_text("{ invalid json }")

    with pytest.raises(RunSessionError, match="Invalid JSON"):
        manager._read_session_file("cub-20260124-000000")


def test_multiple_sessions_in_sequence(manager: RunSessionManager) -> None:
    """Test creating multiple sessions in sequence."""
    # Session 1
    session1 = manager.start_session("claude")
    manager.update_session(session1.run_id, tasks_completed=5)
    manager.end_session(session1.run_id)

    # Session 2
    session2 = manager.start_session("codex")

    # Verify both files exist
    assert (manager.sessions_dir / f"{session1.run_id}.json").exists()
    assert (manager.sessions_dir / f"{session2.run_id}.json").exists()

    # Verify session2 is active
    active = manager.get_active_session()
    assert active is not None
    assert active.run_id == session2.run_id

    # Verify session1 is completed
    completed = manager._read_session_file(session1.run_id)
    assert completed.status == SessionStatus.COMPLETED
    assert completed.tasks_completed == 5
