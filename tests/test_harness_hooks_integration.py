"""
Integration tests for harness hook handlers with SessionLedgerIntegration.

Tests the complete flow of hook events writing forensics and synthesizing
ledger entries via SessionLedgerIntegration.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.harness.hooks import (
    HookEventPayload,
    handle_post_tool_use,
    handle_session_end,
    handle_session_start,
    handle_stop,
)
from cub.core.ledger.writer import LedgerWriter
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    project = tmp_path / "test-project"
    project.mkdir()
    return project


@pytest.fixture
def ledger_dir(project_dir: Path) -> Path:
    """Create ledger directory."""
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
def sample_task() -> Task:
    """Create a sample task for testing."""
    return Task(
        id="cub-test.1",
        title="Test integration task",
        description="Test task for hook integration",
        status=TaskStatus.OPEN,
        priority=TaskPriority.P1,
        type=TaskType.TASK,
        labels=["test"],
        parent="cub-test",
        created_at=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
    )


def read_forensics(forensics_path: Path) -> list[dict]:
    """Helper to read forensics JSONL."""
    events = []
    if forensics_path.exists():
        with forensics_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


class TestSessionStartIntegration:
    """Tests for handle_session_start integration."""

    @pytest.mark.asyncio
    async def test_session_start_writes_forensics(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that session_start writes forensics event."""
        session_id = "test-session-123"
        payload = HookEventPayload(
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "cwd": str(project_dir),
            }
        )

        result = await handle_session_start(payload)

        assert result.continue_execution is True

        # Check forensics were written
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        assert forensics_path.exists()

        events = read_forensics(forensics_path)
        assert len(events) == 1
        assert events[0]["event_type"] == "session_start"
        assert events[0]["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_session_start_injects_project_context(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that session_start injects project context with tasks."""
        # Set up a task backend with some tasks
        tasks_dir = project_dir / ".cub"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        tasks_file = tasks_dir / "tasks.jsonl"

        # Create some test tasks
        test_tasks = [
            {
                "id": "cub-001",
                "title": "Implement feature A",
                "status": "open",
                "priority": "P0",
                "type": "task",
            },
            {
                "id": "cub-002",
                "title": "Fix bug B",
                "status": "open",
                "priority": "P1",
                "type": "bug",
                "depends_on": [],
            },
            {
                "id": "cub-003",
                "title": "Working on feature C",
                "status": "in_progress",
                "priority": "P2",
                "type": "task",
            },
        ]

        # Write tasks to jsonl file
        with tasks_file.open("w", encoding="utf-8") as f:
            for task in test_tasks:
                json.dump(task, f)
                f.write("\n")

        session_id = "test-session-context"
        payload = HookEventPayload(
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "cwd": str(project_dir),
            }
        )

        result = await handle_session_start(payload)

        assert result.continue_execution is True
        assert result.hook_specific is not None
        assert "additionalContext" in result.hook_specific

        context = result.hook_specific["additionalContext"]
        assert context is not None

        # Verify context includes project name
        assert project_dir.name in context

        # Verify context includes ready tasks
        assert "Ready Tasks:" in context
        assert "cub-001" in context
        assert "Implement feature A" in context
        assert "[P0]" in context

        # Verify context includes in-progress tasks
        assert "In Progress:" in context
        assert "cub-003" in context
        assert "Working on feature C" in context

    @pytest.mark.asyncio
    async def test_session_start_handles_missing_tasks(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that session_start handles projects without tasks gracefully."""
        session_id = "test-session-no-tasks"
        payload = HookEventPayload(
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "cwd": str(project_dir),
            }
        )

        result = await handle_session_start(payload)

        assert result.continue_execution is True

        # May or may not have context, depending on backend availability
        # The important thing is it doesn't crash
        if result.hook_specific and "additionalContext" in result.hook_specific:
            context = result.hook_specific["additionalContext"]
            # Should mention project name
            assert project_dir.name in context


class TestPostToolUseIntegration:
    """Tests for handle_post_tool_use integration."""

    @pytest.mark.asyncio
    async def test_file_write_creates_forensics(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that file writes create forensics events."""
        session_id = "test-session-456"
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": session_id,
                "cwd": str(project_dir),
                "tool_name": "Write",
                "tool_input": {"file_path": "src/test.py"},
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        # Check forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        assert forensics_path.exists()

        events = read_forensics(forensics_path)
        assert len(events) == 1
        assert events[0]["event_type"] == "file_write"
        assert events[0]["file_path"] == "src/test.py"

    @pytest.mark.asyncio
    async def test_task_claim_creates_forensics(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that task claims create forensics events."""
        session_id = "test-session-789"
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": session_id,
                "cwd": str(project_dir),
                "tool_name": "Bash",
                "tool_input": {"command": "bd update cub-test.1 --status in_progress"},
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        # Check forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        events = read_forensics(forensics_path)
        assert len(events) == 1
        assert events[0]["event_type"] == "task_claim"
        assert events[0]["task_id"] == "cub-test.1"

    @pytest.mark.asyncio
    async def test_task_close_creates_forensics(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that task closes create forensics events."""
        session_id = "test-session-close"
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": session_id,
                "cwd": str(project_dir),
                "tool_name": "Bash",
                "tool_input": {"command": "bd close cub-test.1"},
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        # Check forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        events = read_forensics(forensics_path)
        assert len(events) == 1
        assert events[0]["event_type"] == "task_close"
        assert events[0]["task_id"] == "cub-test.1"

    @pytest.mark.asyncio
    async def test_cub_task_claim_creates_forensics(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that cub task claim creates forensics events."""
        session_id = "test-session-cub-claim"
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": session_id,
                "cwd": str(project_dir),
                "tool_name": "Bash",
                "tool_input": {"command": "cub task claim cub-test.2"},
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        # Check forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        events = read_forensics(forensics_path)
        assert len(events) == 1
        assert events[0]["event_type"] == "task_claim"
        assert events[0]["task_id"] == "cub-test.2"

    @pytest.mark.asyncio
    async def test_cub_task_close_creates_forensics(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that cub task close creates forensics events."""
        session_id = "test-session-cub-close"
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": session_id,
                "cwd": str(project_dir),
                "tool_name": "Bash",
                "tool_input": {"command": 'cub task close cub-test.2 --reason "done"'},
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        # Check forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        events = read_forensics(forensics_path)
        assert len(events) == 1
        assert events[0]["event_type"] == "task_close"
        assert events[0]["task_id"] == "cub-test.2"
        assert events[0]["reason"] == "done"

    @pytest.mark.asyncio
    async def test_git_commit_creates_forensics(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """Test that git commits create forensics events."""
        session_id = "test-session-commit"
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": session_id,
                "cwd": str(project_dir),
                "tool_name": "Bash",
                "tool_input": {"command": 'git commit -m "test commit"'},
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        # Check forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        events = read_forensics(forensics_path)
        assert len(events) == 1
        assert events[0]["event_type"] == "git_commit"


class TestStopIntegration:
    """Tests for handle_stop integration with ledger synthesis."""

    @pytest.mark.asyncio
    async def test_stop_without_task_no_ledger_entry(
        self,
        project_dir: Path,
        forensics_dir: Path,
        ledger_dir: Path,
    ) -> None:
        """Test that stop without task doesn't create ledger entry."""
        session_id = "test-session-no-task"

        # Write some forensics (session start + session end)
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        with forensics_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "event_type": "session_start",
                    "timestamp": "2026-01-28T10:00:00+00:00",
                    "session_id": session_id,
                },
                f,
            )
            f.write("\n")

        # Handle stop
        payload = HookEventPayload(
            {
                "hook_event_name": "Stop",
                "session_id": session_id,
                "cwd": str(project_dir),
            }
        )

        result = await handle_stop(payload)

        assert result.continue_execution is True

        # Check no ledger entry was created
        by_task_dir = ledger_dir / "by-task"
        if by_task_dir.exists():
            assert len(list(by_task_dir.iterdir())) == 0

    @pytest.mark.asyncio
    async def test_stop_with_task_creates_ledger_entry(
        self,
        project_dir: Path,
        forensics_dir: Path,
        ledger_dir: Path,
    ) -> None:
        """Test that stop with task creates ledger entry."""
        session_id = "test-session-with-task"

        # Write forensics with task claim and close
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        with forensics_path.open("w", encoding="utf-8") as f:
            events = [
                {
                    "event_type": "session_start",
                    "timestamp": "2026-01-28T10:00:00+00:00",
                    "session_id": session_id,
                },
                {
                    "event_type": "task_claim",
                    "timestamp": "2026-01-28T10:05:00+00:00",
                    "session_id": session_id,
                    "task_id": "cub-test.1",
                },
                {
                    "event_type": "file_write",
                    "timestamp": "2026-01-28T10:10:00+00:00",
                    "session_id": session_id,
                    "file_path": "src/test.py",
                    "tool_name": "Write",
                },
                {
                    "event_type": "task_close",
                    "timestamp": "2026-01-28T10:30:00+00:00",
                    "session_id": session_id,
                    "task_id": "cub-test.1",
                },
            ]
            for event in events:
                json.dump(event, f)
                f.write("\n")

        # Handle stop
        payload = HookEventPayload(
            {
                "hook_event_name": "Stop",
                "session_id": session_id,
                "cwd": str(project_dir),
            }
        )

        result = await handle_stop(payload)

        assert result.continue_execution is True

        # Check ledger entry was created
        writer = LedgerWriter(ledger_dir)
        entry = writer.get_entry("cub-test.1")
        assert entry is not None
        assert entry.id == "cub-test.1"
        assert len(entry.attempts) == 1
        assert entry.attempts[0].run_id == session_id
        assert entry.attempts[0].success is True  # Task was closed
        assert entry.outcome is not None
        assert entry.outcome.success is True


class TestSessionEndIntegration:
    """Tests for handle_session_end integration with ledger synthesis."""

    @pytest.mark.asyncio
    async def test_session_end_creates_ledger_entry(
        self,
        project_dir: Path,
        forensics_dir: Path,
        ledger_dir: Path,
    ) -> None:
        """Test that session_end with task creates ledger entry."""
        session_id = "test-session-end-task"

        # Write forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        with forensics_path.open("w", encoding="utf-8") as f:
            events = [
                {
                    "event_type": "session_start",
                    "timestamp": "2026-01-28T10:00:00+00:00",
                    "session_id": session_id,
                },
                {
                    "event_type": "task_claim",
                    "timestamp": "2026-01-28T10:05:00+00:00",
                    "session_id": session_id,
                    "task_id": "cub-test.2",
                },
                {
                    "event_type": "task_close",
                    "timestamp": "2026-01-28T10:30:00+00:00",
                    "session_id": session_id,
                    "task_id": "cub-test.2",
                },
            ]
            for event in events:
                json.dump(event, f)
                f.write("\n")

        # Handle session end
        payload = HookEventPayload(
            {
                "hook_event_name": "SessionEnd",
                "session_id": session_id,
                "cwd": str(project_dir),
            }
        )

        result = await handle_session_end(payload)

        assert result.continue_execution is True

        # Check ledger entry was created
        writer = LedgerWriter(ledger_dir)
        entry = writer.get_entry("cub-test.2")
        assert entry is not None
        assert entry.id == "cub-test.2"


class TestCompleteWorkflow:
    """Tests for complete workflow from session start to end."""

    @pytest.mark.asyncio
    async def test_complete_session_workflow(
        self,
        project_dir: Path,
        forensics_dir: Path,
        ledger_dir: Path,
    ) -> None:
        """Test complete session workflow with all events."""
        session_id = "test-complete-workflow"

        # 1. Session start
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # 2. Task claim
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-workflow.1 --status in_progress"},
                }
            )
        )

        # 3. Write some files
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "src/feature.py"},
                }
            )
        )

        # 4. Git commit
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": 'git commit -m "implement feature"'},
                }
            )
        )

        # 5. Task close
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd close cub-workflow.1"},
                }
            )
        )

        # 6. Session end
        await handle_session_end(
            HookEventPayload(
                {
                    "hook_event_name": "SessionEnd",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        events = read_forensics(forensics_path)
        assert len(events) == 6
        assert events[0]["event_type"] == "session_start"
        assert events[1]["event_type"] == "task_claim"
        assert events[2]["event_type"] == "file_write"
        assert events[3]["event_type"] == "git_commit"
        assert events[4]["event_type"] == "task_close"
        assert events[5]["event_type"] == "session_end"

        # Verify ledger entry
        writer = LedgerWriter(ledger_dir)
        entry = writer.get_entry("cub-workflow.1")
        assert entry is not None
        assert entry.id == "cub-workflow.1"
        assert len(entry.attempts) == 1
        assert entry.attempts[0].run_id == session_id
        assert entry.attempts[0].success is True
        assert entry.outcome.success is True
        assert "src/feature.py" in entry.outcome.files_changed
