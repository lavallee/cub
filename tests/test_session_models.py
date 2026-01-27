"""Tests for session data models (SessionBudget, RunSession, SessionStatus)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.session.models import (
    RunSession,
    SessionBudget,
    SessionStatus,
    generate_run_id,
)


class TestGenerateRunId:
    """Tests for generate_run_id function."""

    def test_format_matches_expected_pattern(self) -> None:
        """Run ID should match cub-YYYYMMDD-HHMMSS pattern."""
        run_id = generate_run_id()
        assert run_id.startswith("cub-")
        # Should be cub-YYYYMMDD-HHMMSS (19 chars)
        assert len(run_id) == 19
        # Date and time parts should be digits
        parts = run_id.split("-")
        assert len(parts) == 3
        assert parts[1].isdigit() and len(parts[1]) == 8
        assert parts[2].isdigit() and len(parts[2]) == 6

    def test_unique_on_successive_calls(self) -> None:
        """Two rapid calls should either differ or at least not crash."""
        id1 = generate_run_id()
        id2 = generate_run_id()
        # Both should be valid
        assert id1.startswith("cub-")
        assert id2.startswith("cub-")


class TestSessionStatus:
    """Tests for SessionStatus enum properties."""

    def test_running_is_active(self) -> None:
        assert SessionStatus.RUNNING.is_active is True

    def test_completed_is_not_active(self) -> None:
        assert SessionStatus.COMPLETED.is_active is False

    def test_orphaned_is_not_active(self) -> None:
        assert SessionStatus.ORPHANED.is_active is False

    def test_running_is_not_terminal(self) -> None:
        assert SessionStatus.RUNNING.is_terminal is False

    def test_completed_is_terminal(self) -> None:
        assert SessionStatus.COMPLETED.is_terminal is True

    def test_orphaned_is_terminal(self) -> None:
        assert SessionStatus.ORPHANED.is_terminal is True


class TestSessionBudget:
    """Tests for SessionBudget model properties."""

    def test_default_budget(self) -> None:
        budget = SessionBudget()
        assert budget.tokens_used == 0
        assert budget.tokens_limit == 0
        assert budget.cost_usd == 0.0
        assert budget.cost_limit == 0.0

    def test_tokens_remaining_unlimited(self) -> None:
        budget = SessionBudget(tokens_limit=0)
        assert budget.tokens_remaining == -1

    def test_tokens_remaining_with_limit(self) -> None:
        budget = SessionBudget(tokens_used=3000, tokens_limit=10000)
        assert budget.tokens_remaining == 7000

    def test_tokens_remaining_exceeded(self) -> None:
        budget = SessionBudget(tokens_used=12000, tokens_limit=10000)
        assert budget.tokens_remaining == 0

    def test_cost_remaining_unlimited(self) -> None:
        budget = SessionBudget(cost_limit=0.0)
        assert budget.cost_remaining == -1.0

    def test_cost_remaining_with_limit(self) -> None:
        budget = SessionBudget(cost_usd=0.30, cost_limit=1.00)
        assert budget.cost_remaining == pytest.approx(0.70)

    def test_cost_remaining_exceeded(self) -> None:
        budget = SessionBudget(cost_usd=1.50, cost_limit=1.00)
        assert budget.cost_remaining == 0.0

    def test_is_tokens_exceeded_unlimited(self) -> None:
        budget = SessionBudget(tokens_used=999999, tokens_limit=0)
        assert budget.is_tokens_exceeded is False

    def test_is_tokens_exceeded_under_limit(self) -> None:
        budget = SessionBudget(tokens_used=5000, tokens_limit=10000)
        assert budget.is_tokens_exceeded is False

    def test_is_tokens_exceeded_at_limit(self) -> None:
        budget = SessionBudget(tokens_used=10000, tokens_limit=10000)
        assert budget.is_tokens_exceeded is True

    def test_is_tokens_exceeded_over_limit(self) -> None:
        budget = SessionBudget(tokens_used=15000, tokens_limit=10000)
        assert budget.is_tokens_exceeded is True

    def test_is_cost_exceeded_unlimited(self) -> None:
        budget = SessionBudget(cost_usd=999.0, cost_limit=0.0)
        assert budget.is_cost_exceeded is False

    def test_is_cost_exceeded_under_limit(self) -> None:
        budget = SessionBudget(cost_usd=0.50, cost_limit=1.00)
        assert budget.is_cost_exceeded is False

    def test_is_cost_exceeded_at_limit(self) -> None:
        budget = SessionBudget(cost_usd=1.00, cost_limit=1.00)
        assert budget.is_cost_exceeded is True

    def test_is_exceeded_neither(self) -> None:
        budget = SessionBudget(tokens_used=5000, tokens_limit=10000, cost_usd=0.50, cost_limit=1.00)
        assert budget.is_exceeded is False

    def test_is_exceeded_tokens_only(self) -> None:
        budget = SessionBudget(
            tokens_used=15000, tokens_limit=10000, cost_usd=0.50, cost_limit=1.00
        )
        assert budget.is_exceeded is True

    def test_is_exceeded_cost_only(self) -> None:
        budget = SessionBudget(tokens_used=5000, tokens_limit=10000, cost_usd=1.50, cost_limit=1.00)
        assert budget.is_exceeded is True

    def test_tokens_utilization_unlimited(self) -> None:
        budget = SessionBudget(tokens_limit=0)
        assert budget.tokens_utilization == -1.0

    def test_tokens_utilization_half(self) -> None:
        budget = SessionBudget(tokens_used=5000, tokens_limit=10000)
        assert budget.tokens_utilization == pytest.approx(0.5)

    def test_tokens_utilization_full(self) -> None:
        budget = SessionBudget(tokens_used=10000, tokens_limit=10000)
        assert budget.tokens_utilization == pytest.approx(1.0)

    def test_cost_utilization_unlimited(self) -> None:
        budget = SessionBudget(cost_limit=0.0)
        assert budget.cost_utilization == -1.0

    def test_cost_utilization_quarter(self) -> None:
        budget = SessionBudget(cost_usd=0.25, cost_limit=1.00)
        assert budget.cost_utilization == pytest.approx(0.25)


class TestRunSession:
    """Tests for RunSession model properties and methods."""

    @pytest.fixture
    def session(self, tmp_path: Path) -> RunSession:
        """Create a basic RunSession for testing."""
        return RunSession(
            run_id="cub-20260127-120000",
            started_at=datetime(2026, 1, 27, 12, 0, 0, tzinfo=timezone.utc),
            project_dir=tmp_path,
            harness="claude",
            budget=SessionBudget(tokens_limit=10000, cost_limit=1.00),
        )

    def test_tasks_total_zero(self, session: RunSession) -> None:
        assert session.tasks_total == 0

    def test_tasks_total_sum(self, tmp_path: Path) -> None:
        session = RunSession(
            run_id="cub-20260127-120000",
            project_dir=tmp_path,
            harness="claude",
            tasks_completed=5,
            tasks_failed=2,
        )
        assert session.tasks_total == 7

    def test_duration_seconds_with_ended(self, tmp_path: Path) -> None:
        session = RunSession(
            run_id="cub-20260127-120000",
            started_at=datetime(2026, 1, 27, 12, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 1, 27, 12, 5, 30, tzinfo=timezone.utc),
            project_dir=tmp_path,
            harness="claude",
        )
        assert session.duration_seconds == 330

    def test_duration_minutes(self, tmp_path: Path) -> None:
        session = RunSession(
            run_id="cub-20260127-120000",
            started_at=datetime(2026, 1, 27, 12, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 1, 27, 12, 5, 30, tzinfo=timezone.utc),
            project_dir=tmp_path,
            harness="claude",
        )
        assert session.duration_minutes == pytest.approx(5.5)

    def test_duration_hours(self, tmp_path: Path) -> None:
        session = RunSession(
            run_id="cub-20260127-120000",
            started_at=datetime(2026, 1, 27, 10, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 1, 27, 12, 30, 0, tzinfo=timezone.utc),
            project_dir=tmp_path,
            harness="claude",
        )
        assert session.duration_hours == pytest.approx(2.5)

    def test_is_active_when_running(self, session: RunSession) -> None:
        assert session.is_active is True

    def test_is_active_when_completed(self, session: RunSession) -> None:
        session.mark_completed()
        assert session.is_active is False

    def test_is_completed(self, session: RunSession) -> None:
        assert session.is_completed is False
        session.mark_completed()
        assert session.is_completed is True

    def test_is_orphaned(self, session: RunSession) -> None:
        assert session.is_orphaned is False
        session.mark_orphaned("process died")
        assert session.is_orphaned is True

    def test_success_rate_no_tasks(self, session: RunSession) -> None:
        assert session.success_rate == 0.0

    def test_success_rate_all_success(self, tmp_path: Path) -> None:
        session = RunSession(
            run_id="cub-20260127-120000",
            project_dir=tmp_path,
            harness="claude",
            tasks_completed=10,
            tasks_failed=0,
        )
        assert session.success_rate == pytest.approx(1.0)

    def test_success_rate_mixed(self, tmp_path: Path) -> None:
        session = RunSession(
            run_id="cub-20260127-120000",
            project_dir=tmp_path,
            harness="claude",
            tasks_completed=7,
            tasks_failed=3,
        )
        assert session.success_rate == pytest.approx(0.7)

    def test_average_cost_per_task_no_tasks(self, session: RunSession) -> None:
        assert session.average_cost_per_task == 0.0

    def test_average_cost_per_task(self, tmp_path: Path) -> None:
        session = RunSession(
            run_id="cub-20260127-120000",
            project_dir=tmp_path,
            harness="claude",
            tasks_completed=5,
            budget=SessionBudget(cost_usd=2.50),
        )
        assert session.average_cost_per_task == pytest.approx(0.50)

    def test_mark_completed_sets_status_and_ended_at(self, session: RunSession) -> None:
        session.mark_completed()
        assert session.status == SessionStatus.COMPLETED
        assert session.ended_at is not None
        assert session.ended_at.tzinfo == timezone.utc

    def test_mark_orphaned_sets_all_fields(self, session: RunSession) -> None:
        session.mark_orphaned("process crashed")
        assert session.status == SessionStatus.ORPHANED
        assert session.orphaned_at is not None
        assert session.orphaned_reason == "process crashed"
        assert session.ended_at is not None
        # ended_at should equal orphaned_at when it wasn't set before
        assert session.ended_at == session.orphaned_at

    def test_mark_orphaned_preserves_existing_ended_at(self, tmp_path: Path) -> None:
        ended = datetime(2026, 1, 27, 13, 0, 0, tzinfo=timezone.utc)
        session = RunSession(
            run_id="cub-20260127-120000",
            project_dir=tmp_path,
            harness="claude",
            ended_at=ended,
        )
        session.mark_orphaned("late detection")
        # ended_at should not be overwritten
        assert session.ended_at == ended
