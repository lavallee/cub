"""Tests for SessionLedgerIntegration."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.ledger.models import LedgerEntry
from cub.core.ledger.session_integration import (
    SessionLedgerIntegration,
    SessionState,
)
from cub.core.ledger.writer import LedgerWriter
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType


@pytest.fixture
def ledger_dir(tmp_path: Path) -> Path:
    """Create a temporary ledger directory."""
    ledger = tmp_path / ".cub" / "ledger"
    ledger.mkdir(parents=True)
    return ledger


@pytest.fixture
def forensics_dir(ledger_dir: Path) -> Path:
    """Create forensics directory."""
    forensics = ledger_dir / "forensics"
    forensics.mkdir(parents=True)
    return forensics


@pytest.fixture
def writer(ledger_dir: Path) -> LedgerWriter:
    """Create a LedgerWriter instance."""
    return LedgerWriter(ledger_dir)


@pytest.fixture
def integration(writer: LedgerWriter) -> SessionLedgerIntegration:
    """Create a SessionLedgerIntegration instance."""
    return SessionLedgerIntegration(writer)


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task for testing."""
    return Task(
        id="cub-abc.1",
        title="Implement feature X",
        description="This is the task description",
        status=TaskStatus.OPEN,
        priority=TaskPriority.P1,
        type=TaskType.TASK,
        labels=["phase-1", "complexity:medium"],
        parent="cub-abc",
        created_at=datetime(2026, 1, 24, 10, 0, tzinfo=timezone.utc),
    )


def write_forensics(forensics_path: Path, events: list[dict]) -> None:
    """Helper to write forensics JSONL."""
    with forensics_path.open("w", encoding="utf-8") as f:
        for event in events:
            json.dump(event, f)
            f.write("\n")


class TestSessionStateInit:
    """Tests for SessionState initialization."""

    def test_init_empty(self) -> None:
        """Test empty SessionState initialization."""
        state = SessionState()

        assert state.session_id is None
        assert state.started_at is None
        assert state.ended_at is None
        assert state.task_id is None
        assert state.task_claimed_at is None
        assert state.task_closed_at is None
        assert state.task_close_reason is None
        assert state.files_written == []
        assert state.plan_files == []
        assert state.spec_files == []
        assert state.git_commits == []
        assert state.transcript_path is None

    def test_has_task_false(self) -> None:
        """Test has_task property when no task."""
        state = SessionState()
        assert state.has_task is False

    def test_has_task_true(self) -> None:
        """Test has_task property when task set."""
        state = SessionState()
        state.task_id = "cub-123"
        assert state.has_task is True

    def test_duration_seconds_no_timestamps(self) -> None:
        """Test duration calculation with no timestamps."""
        state = SessionState()
        assert state.duration_seconds == 0

    def test_duration_seconds_with_timestamps(self) -> None:
        """Test duration calculation with timestamps."""
        state = SessionState()
        state.started_at = datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc)
        state.ended_at = datetime(2026, 1, 28, 10, 5, 30, tzinfo=timezone.utc)
        assert state.duration_seconds == 330  # 5 minutes 30 seconds


class TestSessionLedgerIntegrationInit:
    """Tests for SessionLedgerIntegration initialization."""

    def test_init(self, writer: LedgerWriter) -> None:
        """Test integration initialization."""
        integration = SessionLedgerIntegration(writer)
        assert integration.writer is writer


class TestReadForensics:
    """Tests for read_forensics method."""

    def test_read_empty_file(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading empty forensics file."""
        forensics_path = forensics_dir / "test-session.jsonl"
        forensics_path.write_text("")

        state = integration.read_forensics(forensics_path)
        assert state.session_id is None
        assert state.started_at is None

    def test_read_nonexistent_file(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading nonexistent forensics file raises error."""
        forensics_path = forensics_dir / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError):
            integration.read_forensics(forensics_path)

    def test_read_session_start_event(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading session_start event."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
                "cwd": "/project",
            }
        ]
        write_forensics(forensics_path, events)

        state = integration.read_forensics(forensics_path)
        assert state.session_id == "claude-123"
        assert state.started_at == datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc)

    def test_read_task_claim_event(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading task_claim event."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
                "command": "bd update cub-abc.1 --status in_progress",
            }
        ]
        write_forensics(forensics_path, events)

        state = integration.read_forensics(forensics_path)
        assert state.task_id == "cub-abc.1"
        assert state.task_claimed_at == datetime(2026, 1, 28, 10, 5, 0, tzinfo=timezone.utc)

    def test_read_task_close_event(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading task_close event."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "task_close",
                "timestamp": "2026-01-28T10:30:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
                "command": "bd close cub-abc.1",
                "reason": "implemented successfully",
            }
        ]
        write_forensics(forensics_path, events)

        state = integration.read_forensics(forensics_path)
        assert state.task_closed_at == datetime(2026, 1, 28, 10, 30, 0, tzinfo=timezone.utc)
        assert state.task_close_reason == "implemented successfully"

    def test_read_file_write_events(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading file_write events."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:10:00+00:00",
                "session_id": "claude-123",
                "file_path": "src/feature.py",
                "tool_name": "Write",
                "file_category": "source",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:15:00+00:00",
                "session_id": "claude-123",
                "file_path": "plans/feature-x/plan.md",
                "tool_name": "Write",
                "file_category": "plan",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:20:00+00:00",
                "session_id": "claude-123",
                "file_path": "specs/feature-x.md",
                "tool_name": "Write",
                "file_category": "spec",
            },
        ]
        write_forensics(forensics_path, events)

        state = integration.read_forensics(forensics_path)
        assert len(state.files_written) == 3
        assert "src/feature.py" in state.files_written
        assert "plans/feature-x/plan.md" in state.files_written
        assert "specs/feature-x.md" in state.files_written
        assert len(state.plan_files) == 1
        assert state.plan_files[0] == "plans/feature-x/plan.md"
        assert len(state.spec_files) == 1
        assert state.spec_files[0] == "specs/feature-x.md"

    def test_read_git_commit_event(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading git_commit event."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "git_commit",
                "timestamp": "2026-01-28T10:25:00+00:00",
                "session_id": "claude-123",
                "command": 'git commit -m "implement feature"',
                "message_preview": "implement feature",
            }
        ]
        write_forensics(forensics_path, events)

        state = integration.read_forensics(forensics_path)
        assert len(state.git_commits) == 1
        assert state.git_commits[0]["command"] == 'git commit -m "implement feature"'
        assert state.git_commits[0]["message_preview"] == "implement feature"

    def test_read_session_end_event(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading session_end event."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
                "transcript_path": "/path/to/transcript.jsonl",
            }
        ]
        write_forensics(forensics_path, events)

        state = integration.read_forensics(forensics_path)
        assert state.ended_at == datetime(2026, 1, 28, 10, 35, 0, tzinfo=timezone.utc)
        assert state.transcript_path == "/path/to/transcript.jsonl"

    def test_read_full_session(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test reading complete session with all event types."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:10:00+00:00",
                "session_id": "claude-123",
                "file_path": "src/feature.py",
                "tool_name": "Write",
            },
            {
                "event_type": "git_commit",
                "timestamp": "2026-01-28T10:25:00+00:00",
                "session_id": "claude-123",
                "command": "git commit",
            },
            {
                "event_type": "task_close",
                "timestamp": "2026-01-28T10:30:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        state = integration.read_forensics(forensics_path)
        assert state.session_id == "claude-123"
        assert state.started_at is not None
        assert state.ended_at is not None
        assert state.task_id == "cub-abc.1"
        assert state.task_claimed_at is not None
        assert state.task_closed_at is not None
        assert len(state.files_written) == 1
        assert len(state.git_commits) == 1
        assert state.has_task is True

    def test_read_malformed_json_skipped(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test that malformed JSON lines are skipped."""
        forensics_path = forensics_dir / "test.jsonl"
        with forensics_path.open("w", encoding="utf-8") as f:
            f.write('{"event_type": "session_start", "timestamp": "2026-01-28T10:00:00+00:00"}\n')
            f.write("this is not json\n")
            f.write('{"event_type": "session_end", "timestamp": "2026-01-28T10:35:00+00:00"}\n')

        state = integration.read_forensics(forensics_path)
        assert state.started_at is not None
        assert state.ended_at is not None


class TestOnSessionEnd:
    """Tests for on_session_end method."""

    def test_on_session_end_no_task(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test session end without task association returns None."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        entry = integration.on_session_end("claude-123", forensics_path)
        assert entry is None

    def test_on_session_end_with_task(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
        sample_task: Task,
    ) -> None:
        """Test session end with task creates ledger entry."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:10:00+00:00",
                "session_id": "claude-123",
                "file_path": "src/feature.py",
                "tool_name": "Write",
            },
            {
                "event_type": "task_close",
                "timestamp": "2026-01-28T10:30:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        entry = integration.on_session_end("claude-123", forensics_path, task=sample_task)

        assert entry is not None
        assert entry.id == "cub-abc.1"
        assert entry.title == "Implement feature X"
        assert len(entry.attempts) == 1
        assert entry.attempts[0].run_id == "claude-123"
        assert entry.attempts[0].success is True
        assert entry.outcome is not None
        assert entry.outcome.success is True
        assert entry.outcome.files_changed == ["src/feature.py"]

    def test_on_session_end_creates_task_snapshot(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
        sample_task: Task,
    ) -> None:
        """Test session end creates task snapshot."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        entry = integration.on_session_end("claude-123", forensics_path, task=sample_task)

        assert entry is not None
        assert entry.task is not None
        assert entry.task.title == sample_task.title
        assert entry.task.description == sample_task.description
        assert entry.task.priority == sample_task.priority_numeric
        assert entry.task.labels == sample_task.labels

    def test_on_session_end_extracts_lineage(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
        sample_task: Task,
    ) -> None:
        """Test session end extracts lineage from files."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:10:00+00:00",
                "session_id": "claude-123",
                "file_path": "specs/feature-x.md",
                "tool_name": "Write",
                "file_category": "spec",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:15:00+00:00",
                "session_id": "claude-123",
                "file_path": "plans/feature-x/plan.md",
                "tool_name": "Write",
                "file_category": "plan",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        entry = integration.on_session_end("claude-123", forensics_path, task=sample_task)

        assert entry is not None
        assert entry.lineage.spec_file == "specs/feature-x.md"
        assert entry.lineage.plan_file == "plans/feature-x/plan.md"
        assert entry.lineage.epic_id == "cub-abc"

    def test_on_session_end_nonexistent_forensics(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test session end with nonexistent forensics returns None."""
        forensics_path = forensics_dir / "nonexistent.jsonl"

        entry = integration.on_session_end("claude-123", forensics_path)
        assert entry is None

    def test_on_session_end_writes_to_disk(
        self,
        integration: SessionLedgerIntegration,
        writer: LedgerWriter,
        forensics_dir: Path,
        sample_task: Task,
    ) -> None:
        """Test session end writes entry to disk."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "task_close",
                "timestamp": "2026-01-28T10:30:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
        ]
        write_forensics(forensics_path, events)

        integration.on_session_end("claude-123", forensics_path, task=sample_task)

        # Verify entry was written
        assert writer.entry_exists("cub-abc.1")
        entry = writer.get_entry("cub-abc.1")
        assert entry is not None
        assert entry.id == "cub-abc.1"

    def test_on_session_end_existing_entry_not_overwritten(
        self,
        integration: SessionLedgerIntegration,
        writer: LedgerWriter,
        forensics_dir: Path,
        sample_task: Task,
    ) -> None:
        """Test session end doesn't overwrite finalized entry."""
        # Create an existing finalized entry
        from cub.core.ledger.models import Outcome

        existing_entry = LedgerEntry(
            id="cub-abc.1",
            title="Original title",
            outcome=Outcome(
                success=True,
                total_attempts=1,
                total_cost_usd=0.5,
                total_duration_seconds=100,
            ),
        )
        writer.create_entry(existing_entry)

        # Try to create entry from session
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
        ]
        write_forensics(forensics_path, events)

        entry = integration.on_session_end("claude-123", forensics_path, task=sample_task)

        # Should return existing entry without changes
        assert entry is not None
        assert entry.title == "Original title"

    def test_on_session_end_task_not_closed(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
        sample_task: Task,
    ) -> None:
        """Test session end with task claimed but not closed."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:10:00+00:00",
                "session_id": "claude-123",
                "file_path": "src/feature.py",
                "tool_name": "Write",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        entry = integration.on_session_end("claude-123", forensics_path, task=sample_task)

        assert entry is not None
        assert entry.attempts[0].success is False  # Not closed = not successful


class TestFinalizeForensics:
    """Tests for finalize_forensics method."""

    def test_finalize_forensics_exists(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test finalizing existing forensics."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        state = integration.finalize_forensics(forensics_path)
        assert state is not None
        assert state.session_id == "claude-123"

    def test_finalize_forensics_nonexistent(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test finalizing nonexistent forensics."""
        forensics_path = forensics_dir / "nonexistent.jsonl"

        state = integration.finalize_forensics(forensics_path)
        assert state is None


class TestGetSessionState:
    """Tests for get_session_state method."""

    def test_get_session_state_exists(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test getting session state for existing forensics."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
        ]
        write_forensics(forensics_path, events)

        state = integration.get_session_state(forensics_path)
        assert state is not None
        assert state.session_id == "claude-123"
        assert state.task_id == "cub-abc.1"

    def test_get_session_state_nonexistent(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
    ) -> None:
        """Test getting session state for nonexistent forensics."""
        forensics_path = forensics_dir / "nonexistent.jsonl"

        state = integration.get_session_state(forensics_path)
        assert state is None


class TestFullWorkflow:
    """Test complete session workflows."""

    def test_complete_successful_session(
        self,
        integration: SessionLedgerIntegration,
        forensics_dir: Path,
        sample_task: Task,
    ) -> None:
        """Test complete successful session workflow."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
                "cwd": "/project",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:05:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:10:00+00:00",
                "session_id": "claude-123",
                "file_path": "specs/feature-x.md",
                "tool_name": "Write",
                "file_category": "spec",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:12:00+00:00",
                "session_id": "claude-123",
                "file_path": "plans/feature-x/plan.md",
                "tool_name": "Write",
                "file_category": "plan",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:15:00+00:00",
                "session_id": "claude-123",
                "file_path": "src/feature.py",
                "tool_name": "Write",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:20:00+00:00",
                "session_id": "claude-123",
                "file_path": "tests/test_feature.py",
                "tool_name": "Write",
            },
            {
                "event_type": "git_commit",
                "timestamp": "2026-01-28T10:25:00+00:00",
                "session_id": "claude-123",
                "command": 'git commit -m "implement feature X"',
                "message_preview": "implement feature X",
            },
            {
                "event_type": "task_close",
                "timestamp": "2026-01-28T10:30:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-abc.1",
                "reason": "implemented and tested",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
                "transcript_path": "/path/to/transcript.jsonl",
            },
        ]
        write_forensics(forensics_path, events)

        entry = integration.on_session_end("claude-123", forensics_path, task=sample_task)

        assert entry is not None
        assert entry.id == "cub-abc.1"
        assert entry.title == "Implement feature X"

        # Check task snapshot
        assert entry.task is not None
        assert entry.task.title == sample_task.title

        # Check lineage
        assert entry.lineage.spec_file == "specs/feature-x.md"
        assert entry.lineage.plan_file == "plans/feature-x/plan.md"
        assert entry.lineage.epic_id == "cub-abc"

        # Check attempt
        assert len(entry.attempts) == 1
        assert entry.attempts[0].run_id == "claude-123"
        assert entry.attempts[0].success is True
        assert entry.attempts[0].harness == "claude"

        # Check outcome
        assert entry.outcome is not None
        assert entry.outcome.success is True
        assert entry.outcome.total_attempts == 1
        assert entry.outcome.files_changed == [
            "specs/feature-x.md",
            "plans/feature-x/plan.md",
            "src/feature.py",
            "tests/test_feature.py",
        ]

        # Check verification
        assert entry.verification.status == "pending"

        # Check workflow
        assert entry.workflow.stage == "dev_complete"

    def test_session_without_task_no_entry(
        self,
        integration: SessionLedgerIntegration,
        writer: LedgerWriter,
        forensics_dir: Path,
    ) -> None:
        """Test session without task doesn't create ledger entry."""
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "file_write",
                "timestamp": "2026-01-28T10:10:00+00:00",
                "session_id": "claude-123",
                "file_path": "README.md",
                "tool_name": "Edit",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        entry = integration.on_session_end("claude-123", forensics_path)

        assert entry is None
        # Verify no ledger entry was created
        # (We don't have a way to list all entries, so we just check None was returned)


class TestEnrichFromTranscript:
    """Tests for transcript enrichment functionality."""

    def test_enriches_entry_with_transcript_data(
        self,
        integration: SessionLedgerIntegration,
        writer: LedgerWriter,
        forensics_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that transcript data enriches ledger entry."""
        # Create forensics with task
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:01:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-xyz.1",
            },
            {
                "event_type": "task_close",
                "timestamp": "2026-01-28T10:30:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-xyz.1",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
                "transcript_path": "/path/to/transcript.jsonl",
            },
        ]
        write_forensics(forensics_path, events)

        # Create transcript
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_lines = [
            json.dumps({"type": "input", "content": "User message"}),
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {
                    "input_tokens": 10000,
                    "output_tokens": 5000,
                    "cache_read_input_tokens": 2000,
                    "cache_creation_input_tokens": 500,
                },
            }),
            json.dumps({"type": "input", "content": "Continue"}),
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {
                    "input_tokens": 8000,
                    "output_tokens": 3000,
                    "cache_read_input_tokens": 1000,
                    "cache_creation_input_tokens": 0,
                },
            }),
        ]
        transcript_path.write_text("\n".join(transcript_lines) + "\n")

        # Create ledger entry
        entry = integration.on_session_end("claude-123", forensics_path)
        assert entry is not None

        # Initial state should have zero tokens
        assert entry.attempts[0].tokens.input_tokens == 0
        assert entry.attempts[0].tokens.output_tokens == 0
        assert entry.attempts[0].model == ""
        assert entry.attempts[0].cost_usd == 0.0

        # Enrich with transcript
        enriched = integration.enrich_from_transcript("cub-xyz.1", transcript_path)

        assert enriched is not None
        assert enriched.id == "cub-xyz.1"

        # Check that tokens were updated
        assert enriched.attempts[0].tokens.input_tokens == 18000  # 10k + 8k
        assert enriched.attempts[0].tokens.output_tokens == 8000  # 5k + 3k
        assert enriched.attempts[0].tokens.cache_read_tokens == 3000  # 2k + 1k
        assert enriched.attempts[0].tokens.cache_creation_tokens == 500  # 500 + 0

        # Check that model was updated
        assert enriched.attempts[0].model == "sonnet"

        # Check that cost was calculated
        # (18000*3 + 8000*15 + 3000*0.3 + 500*3.75) / 1M
        # = (54000 + 120000 + 900 + 1875) / 1M = 0.176775
        assert abs(enriched.attempts[0].cost_usd - 0.176775) < 0.0001

        # Check that outcome was updated
        assert enriched.outcome is not None
        assert enriched.outcome.final_model == "sonnet"
        assert abs(enriched.outcome.total_cost_usd - 0.176775) < 0.0001

        # Check that legacy fields were updated
        assert enriched.harness_model == "sonnet"
        assert abs(enriched.cost_usd - 0.176775) < 0.0001
        assert enriched.tokens.input_tokens == 18000

    def test_handles_missing_transcript(
        self,
        integration: SessionLedgerIntegration,
        writer: LedgerWriter,
        forensics_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that missing transcript doesn't crash."""
        # Create forensics with task
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:01:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-xyz.1",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        # Create ledger entry
        entry = integration.on_session_end("claude-123", forensics_path)
        assert entry is not None

        # Try to enrich with nonexistent transcript
        nonexistent = tmp_path / "nonexistent.jsonl"
        enriched = integration.enrich_from_transcript("cub-xyz.1", nonexistent)

        # Should return the entry unchanged
        assert enriched is not None
        assert enriched.attempts[0].tokens.input_tokens == 0
        assert enriched.attempts[0].cost_usd == 0.0

    def test_returns_none_for_nonexistent_entry(
        self,
        integration: SessionLedgerIntegration,
        tmp_path: Path,
    ) -> None:
        """Test that enriching nonexistent entry returns None."""
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_path.write_text(
            json.dumps({
                "type": "output",
                "model": "claude-sonnet-4-5-20250929",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            })
            + "\n"
        )

        result = integration.enrich_from_transcript("nonexistent", transcript_path)

        assert result is None

    def test_handles_empty_transcript(
        self,
        integration: SessionLedgerIntegration,
        writer: LedgerWriter,
        forensics_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that empty transcript results in zero tokens."""
        # Create forensics with task
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:01:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-xyz.1",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        # Create ledger entry
        entry = integration.on_session_end("claude-123", forensics_path)
        assert entry is not None

        # Create empty transcript
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_path.write_text("")

        # Enrich with empty transcript
        enriched = integration.enrich_from_transcript("cub-xyz.1", transcript_path)

        assert enriched is not None
        # Empty transcript should result in zero tokens/cost
        assert enriched.attempts[0].tokens.input_tokens == 0
        assert enriched.attempts[0].tokens.output_tokens == 0
        assert enriched.attempts[0].cost_usd == 0.0
        assert enriched.attempts[0].model == ""  # No model in empty transcript

    def test_enrichment_updates_persisted_entry(
        self,
        integration: SessionLedgerIntegration,
        writer: LedgerWriter,
        forensics_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that enrichment persists to storage."""
        # Create forensics with task
        forensics_path = forensics_dir / "test.jsonl"
        events = [
            {
                "event_type": "session_start",
                "timestamp": "2026-01-28T10:00:00+00:00",
                "session_id": "claude-123",
            },
            {
                "event_type": "task_claim",
                "timestamp": "2026-01-28T10:01:00+00:00",
                "session_id": "claude-123",
                "task_id": "cub-xyz.1",
            },
            {
                "event_type": "session_end",
                "timestamp": "2026-01-28T10:35:00+00:00",
                "session_id": "claude-123",
            },
        ]
        write_forensics(forensics_path, events)

        # Create transcript
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_path.write_text(
            json.dumps({
                "type": "output",
                "model": "claude-opus-4-5",
                "usage": {
                    "input_tokens": 5000,
                    "output_tokens": 2000,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            })
            + "\n"
        )

        # Create and enrich entry
        entry = integration.on_session_end("claude-123", forensics_path)
        assert entry is not None

        enriched = integration.enrich_from_transcript("cub-xyz.1", transcript_path)
        assert enriched is not None

        # Read entry again from storage
        reloaded = writer.get_entry("cub-xyz.1")
        assert reloaded is not None

        # Verify enrichment was persisted
        assert reloaded.attempts[0].tokens.input_tokens == 5000
        assert reloaded.attempts[0].tokens.output_tokens == 2000
        assert reloaded.attempts[0].model == "opus"
        # (5000*15 + 2000*75) / 1M = (75000 + 150000) / 1M = 0.225
        assert abs(reloaded.attempts[0].cost_usd - 0.225) < 0.0001
