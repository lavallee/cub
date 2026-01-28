"""Tests for cub reconcile command."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli.reconcile import (
    _get_ledger_paths,
    _parse_forensics_for_metadata,
    app,
)
from cub.core.ledger.models import (
    Attempt,
    LedgerEntry,
    Lineage,
    Outcome,
    TokenUsage,
)
from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.writer import LedgerWriter
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType

runner = CliRunner()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    project = tmp_path / "project"
    project.mkdir()
    return project


@pytest.fixture
def ledger_dir(project_dir: Path) -> Path:
    """Create a temporary ledger directory."""
    ledger = project_dir / ".cub" / "ledger"
    ledger.mkdir(parents=True)
    return ledger


@pytest.fixture
def forensics_dir(ledger_dir: Path) -> Path:
    """Create forensics directory."""
    forensics = ledger_dir / "forensics"
    forensics.mkdir(parents=True)
    return forensics


@pytest.fixture
def by_task_dir(ledger_dir: Path) -> Path:
    """Create by-task directory."""
    by_task = ledger_dir / "by-task"
    by_task.mkdir(parents=True)
    return by_task


def write_forensics(forensics_path: Path, events: list[dict]) -> None:
    """Helper to write forensics JSONL."""
    with forensics_path.open("w", encoding="utf-8") as f:
        for event in events:
            json.dump(event, f)
            f.write("\n")


def create_sample_forensics_with_task(
    forensics_dir: Path, session_id: str, task_id: str
) -> Path:
    """Create a forensics file with task claim and close events."""
    forensics_path = forensics_dir / f"{session_id}.jsonl"
    events = [
        {
            "event_type": "session_start",
            "timestamp": "2026-01-28T10:00:00+00:00",
            "session_id": session_id,
            "cwd": "/project",
        },
        {
            "event_type": "task_claim",
            "timestamp": "2026-01-28T10:05:00+00:00",
            "session_id": session_id,
            "task_id": task_id,
            "command": f"cub task claim {task_id}",
        },
        {
            "event_type": "file_write",
            "timestamp": "2026-01-28T10:10:00+00:00",
            "session_id": session_id,
            "file_path": "src/feature.py",
            "tool_name": "Write",
            "file_category": "source",
        },
        {
            "event_type": "git_commit",
            "timestamp": "2026-01-28T10:25:00+00:00",
            "session_id": session_id,
            "command": "git commit -m 'implement feature'",
            "message_preview": "implement feature",
        },
        {
            "event_type": "task_close",
            "timestamp": "2026-01-28T10:30:00+00:00",
            "session_id": session_id,
            "task_id": task_id,
            "command": f"cub task close {task_id}",
            "reason": "completed successfully",
        },
        {
            "event_type": "session_end",
            "timestamp": "2026-01-28T10:35:00+00:00",
            "session_id": session_id,
            "transcript_path": None,
        },
    ]
    write_forensics(forensics_path, events)
    return forensics_path


def create_sample_forensics_without_task(forensics_dir: Path, session_id: str) -> Path:
    """Create a forensics file without task association."""
    forensics_path = forensics_dir / f"{session_id}.jsonl"
    events = [
        {
            "event_type": "session_start",
            "timestamp": "2026-01-28T10:00:00+00:00",
            "session_id": session_id,
            "cwd": "/project",
        },
        {
            "event_type": "file_write",
            "timestamp": "2026-01-28T10:10:00+00:00",
            "session_id": session_id,
            "file_path": "src/feature.py",
            "tool_name": "Write",
            "file_category": "source",
        },
        {
            "event_type": "session_end",
            "timestamp": "2026-01-28T10:35:00+00:00",
            "session_id": session_id,
            "transcript_path": None,
        },
    ]
    write_forensics(forensics_path, events)
    return forensics_path


class TestParseForensicsForMetadata:
    """Tests for _parse_forensics_for_metadata helper."""

    def test_parse_forensics_with_task_claim(
        self, forensics_dir: Path
    ) -> None:
        """Test parsing forensics with task claim."""
        session_id = "test-session-123"
        task_id = "cub-abc.1"
        forensics_path = create_sample_forensics_with_task(
            forensics_dir, session_id, task_id
        )

        metadata = _parse_forensics_for_metadata(forensics_path)

        assert metadata["session_id"] == session_id
        assert metadata["task_id"] == task_id
        assert metadata["has_task_claim"] is True
        assert metadata["has_task_close"] is True
        assert metadata["event_count"] == 6

    def test_parse_forensics_without_task(
        self, forensics_dir: Path
    ) -> None:
        """Test parsing forensics without task."""
        session_id = "test-session-456"
        forensics_path = create_sample_forensics_without_task(
            forensics_dir, session_id
        )

        metadata = _parse_forensics_for_metadata(forensics_path)

        assert metadata["session_id"] == session_id
        assert metadata["task_id"] is None
        assert metadata["has_task_claim"] is False
        assert metadata["has_task_close"] is False
        assert metadata["event_count"] == 3

    def test_parse_forensics_nonexistent_file(
        self, tmp_path: Path
    ) -> None:
        """Test parsing nonexistent forensics file."""
        forensics_path = tmp_path / "nonexistent.jsonl"

        metadata = _parse_forensics_for_metadata(forensics_path)

        assert metadata["session_id"] is None
        assert metadata["task_id"] is None
        assert metadata["has_task_claim"] is False
        assert metadata["has_task_close"] is False
        assert metadata["event_count"] == 0

    def test_parse_forensics_with_invalid_json(
        self, forensics_dir: Path
    ) -> None:
        """Test parsing forensics with invalid JSON lines."""
        forensics_path = forensics_dir / "invalid.jsonl"
        with forensics_path.open("w") as f:
            f.write('{"event_type": "session_start", "session_id": "test-123"}\n')
            f.write('invalid json line\n')
            f.write('{"event_type": "task_claim", "task_id": "cub-abc.1"}\n')

        metadata = _parse_forensics_for_metadata(forensics_path)

        # Should still parse valid lines
        assert metadata["session_id"] == "test-123"
        assert metadata["task_id"] == "cub-abc.1"
        assert metadata["event_count"] == 2


class TestReconcileCommand:
    """Tests for cub reconcile command."""

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_no_forensics_directory(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
    ) -> None:
        """Test reconcile when no forensics directory exists."""
        mock_project_root.return_value = project_dir

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "No forensics directory found" in result.stdout

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_empty_forensics_directory(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test reconcile with empty forensics directory."""
        mock_project_root.return_value = project_dir

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "No forensics files found" in result.stdout

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_skip_sessions_without_task(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test reconcile skips sessions without task association."""
        mock_project_root.return_value = project_dir

        # Create forensics without task
        create_sample_forensics_without_task(forensics_dir, "session-no-task")

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "Skipped" in result.stdout

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_create_entry(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
        by_task_dir: Path,
    ) -> None:
        """Test reconcile creates ledger entry."""
        mock_project_root.return_value = project_dir

        # Create task mock
        task = Task(
            id="cub-abc.1",
            title="Test task",
            description="Test description",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            labels=[],
            created_at=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
        )
        mock_backend.return_value.get.return_value = task

        # Create forensics with task
        create_sample_forensics_with_task(forensics_dir, "session-with-task", "cub-abc.1")

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        # Should show creation in output
        assert "Created" in result.stdout or "Processed" in result.stdout

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_skip_existing_entry(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
        ledger_dir: Path,
        by_task_dir: Path,
    ) -> None:
        """Test reconcile skips sessions with existing ledger entries."""
        mock_project_root.return_value = project_dir

        # Create existing ledger entry
        writer = LedgerWriter(ledger_dir)
        entry = LedgerEntry(
            id="cub-abc.1",
            title="Test task",
            lineage=Lineage(),
            attempts=[
                Attempt(
                    attempt_number=1,
                    run_id="test-run",
                    started_at=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
                    completed_at=datetime(2026, 1, 28, 10, 30, tzinfo=timezone.utc),
                    harness="claude",
                    model="sonnet",
                    success=True,
                    tokens=TokenUsage(),
                    cost_usd=0.0,
                    duration_seconds=1800,
                )
            ],
            outcome=Outcome(
                success=True,
                completed_at=datetime(2026, 1, 28, 10, 30, tzinfo=timezone.utc),
            ),
        )
        writer.create_entry(entry)

        # Create forensics
        create_sample_forensics_with_task(forensics_dir, "session-existing", "cub-abc.1")

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        # Should skip because entry exists
        assert "Skipped" in result.stdout or "No new entries created" in result.stdout

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_force_reprocess(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
        ledger_dir: Path,
        by_task_dir: Path,
    ) -> None:
        """Test reconcile with --force reprocesses existing entries."""
        mock_project_root.return_value = project_dir

        # Create task mock
        task = Task(
            id="cub-abc.1",
            title="Test task",
            description="Test description",
            status=TaskStatus.CLOSED,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            labels=[],
            created_at=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
        )
        mock_backend.return_value.get.return_value = task

        # Create existing ledger entry
        writer = LedgerWriter(ledger_dir)
        entry = LedgerEntry(
            id="cub-abc.1",
            title="Test task",
            lineage=Lineage(),
            attempts=[],
        )
        writer.create_entry(entry)

        # Create forensics
        create_sample_forensics_with_task(forensics_dir, "session-force", "cub-abc.1")

        result = runner.invoke(app, ["--force"])

        assert result.exit_code == 0

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_dry_run(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
        by_task_dir: Path,
    ) -> None:
        """Test reconcile with --dry-run doesn't create entries."""
        mock_project_root.return_value = project_dir

        # Create task mock
        task = Task(
            id="cub-abc.1",
            title="Test task",
            description="Test description",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            labels=[],
            created_at=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
        )
        mock_backend.return_value.get.return_value = task

        # Create forensics
        create_sample_forensics_with_task(forensics_dir, "session-dry-run", "cub-abc.1")

        result = runner.invoke(app, ["--dry-run"])

        assert result.exit_code == 0
        assert "Dry run complete" in result.stdout or "would be created" in result.stdout

        # Verify no ledger entry was created
        entry_file = by_task_dir / "cub-abc.1.json"
        assert not entry_file.exists()

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_specific_session(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
        by_task_dir: Path,
    ) -> None:
        """Test reconcile with --session filters to specific session."""
        mock_project_root.return_value = project_dir

        # Create task mock
        task = Task(
            id="cub-abc.1",
            title="Test task",
            description="Test description",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            labels=[],
            created_at=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
        )
        mock_backend.return_value.get.return_value = task

        # Create multiple forensics files
        create_sample_forensics_with_task(forensics_dir, "session-1", "cub-abc.1")
        create_sample_forensics_with_task(forensics_dir, "session-2", "cub-def.2")

        result = runner.invoke(app, ["--session", "session-1"])

        assert result.exit_code == 0
        # Should only process session-1
        assert "Processed" in result.stdout or "Created" in result.stdout

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_specific_session_not_found(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test reconcile with --session for nonexistent session."""
        mock_project_root.return_value = project_dir

        # Create at least one forensics file so we pass the empty check
        create_sample_forensics_without_task(forensics_dir, "other-session")

        result = runner.invoke(app, ["--session", "nonexistent-session"])

        assert result.exit_code == 2
        assert "Session not found" in result.stdout

    @patch("cub.cli.reconcile.get_project_root")
    @patch("cub.cli.reconcile.get_backend")
    def test_reconcile_json_output(
        self,
        mock_backend: MagicMock,
        mock_project_root: MagicMock,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test reconcile with --json outputs JSON."""
        mock_project_root.return_value = project_dir

        # Create forensics without task
        create_sample_forensics_without_task(forensics_dir, "session-json")

        result = runner.invoke(app, ["--json"])

        assert result.exit_code == 0
        # Verify JSON output
        output = json.loads(result.stdout)
        assert "processed" in output
        assert "skipped" in output
        assert "created" in output
        assert "sessions" in output
