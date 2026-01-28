"""
End-to-end integration tests for symbiotic workflow (direct Claude Code sessions).

Tests the complete flow of hook events -> forensics -> ledger entries to verify
that direct harness sessions produce structurally equivalent ledger entries to
`cub run` sessions. This validates parity between the two execution paths.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cub.core.harness.hooks import (
    HookEventPayload,
    handle_post_tool_use,
    handle_session_end,
    handle_session_start,
    handle_stop,
)
from cub.core.ledger.models import LedgerEntry
from cub.core.ledger.writer import LedgerWriter
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with required structure."""
    project = tmp_path / "test-project"
    project.mkdir()

    # Create .cub directory structure
    cub_dir = project / ".cub"
    cub_dir.mkdir()

    # Create ledger directories
    ledger_dir = cub_dir / "ledger"
    ledger_dir.mkdir()
    (ledger_dir / "forensics").mkdir()
    (ledger_dir / "by-task").mkdir()

    # Create .beads directory for task backend
    beads_dir = project / ".beads"
    beads_dir.mkdir()
    (beads_dir / "issues.jsonl").write_text("")

    return project


@pytest.fixture
def ledger_dir(project_dir: Path) -> Path:
    """Get ledger directory from project."""
    return project_dir / ".cub" / "ledger"


@pytest.fixture
def forensics_dir(ledger_dir: Path) -> Path:
    """Get forensics directory from ledger."""
    return ledger_dir / "forensics"


@pytest.fixture
def writer(ledger_dir: Path) -> LedgerWriter:
    """Create a LedgerWriter instance."""
    return LedgerWriter(ledger_dir)


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task for testing."""
    return Task(
        id="cub-r9d.3",
        title="End-to-end integration tests",
        description="Implement complete symbiotic workflow tests",
        status=TaskStatus.OPEN,
        priority=TaskPriority.P0,
        type=TaskType.TASK,
        labels=["phase-1", "symbiotic-workflow"],
        parent="cub-r9d",
        created_at=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
    )


def read_forensics(forensics_path: Path) -> list[dict[str, Any]]:
    """Helper to read forensics JSONL."""
    events = []
    if forensics_path.exists():
        with forensics_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


class TestCompleteSymbioticWorkflow:
    """Test complete workflow from session start to ledger entry creation."""

    @pytest.mark.asyncio
    async def test_successful_task_completion_workflow(
        self,
        project_dir: Path,
        forensics_dir: Path,
        ledger_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Simulate a complete successful Claude Code session with task completion.

        Flow: SessionStart -> Write plan -> Claim task -> Write files -> Git commit
              -> Close task -> Stop
        """
        session_id = "claude-e2e-success-123"

        # 1. SessionStart event
        result = await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )
        assert result.continue_execution is True

        # 2. Write plan file (PostToolUse)
        result = await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "plans/symbiotic-workflow/plan.md"},
                }
            )
        )
        assert result.continue_execution is True

        # 3. Claim task (PostToolUse with Bash)
        result = await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-r9d.3 --status in_progress"},
                }
            )
        )
        assert result.continue_execution is True

        # 4. Write source files
        result = await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {
                        "file_path": "tests/integration/test_symbiotic_workflow.py"
                    },
                }
            )
        )
        assert result.continue_execution is True

        # 5. Git commit (PostToolUse with Bash)
        result = await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": 'git commit -m "task(cub-r9d.3): End-to-end integration tests"'
                    },
                }
            )
        )
        assert result.continue_execution is True

        # 6. Close task (PostToolUse with Bash)
        result = await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd close cub-r9d.3"},
                }
            )
        )
        assert result.continue_execution is True

        # 7. Stop event (triggers ledger synthesis)
        result = await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )
        assert result.continue_execution is True

        # Verify forensics were created correctly
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        assert forensics_path.exists()

        events = read_forensics(forensics_path)
        assert len(events) == 7  # includes session_end from Stop handler

        # Verify event types and order
        assert events[0]["event_type"] == "session_start"
        assert events[1]["event_type"] == "file_write"
        assert events[1]["file_path"] == "plans/symbiotic-workflow/plan.md"
        assert events[1]["file_category"] == "plan"
        assert events[2]["event_type"] == "task_claim"
        assert events[2]["task_id"] == "cub-r9d.3"
        assert events[3]["event_type"] == "file_write"
        assert events[3]["file_path"] == "tests/integration/test_symbiotic_workflow.py"
        assert events[4]["event_type"] == "git_commit"
        assert events[5]["event_type"] == "task_close"
        assert events[5]["task_id"] == "cub-r9d.3"
        assert events[6]["event_type"] == "session_end"

        # Verify ledger entry was created
        assert writer.entry_exists("cub-r9d.3")
        entry = writer.get_entry("cub-r9d.3")
        assert entry is not None

        # Verify ledger entry structure (parity with cub run)
        self._verify_ledger_entry_structure(entry, session_id, success=True)

    @pytest.mark.asyncio
    async def test_session_with_no_task_claimed(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Test session without task claim - no ledger entry, forensics only.

        Flow: SessionStart -> Write files -> Stop (no task claimed)
        """
        session_id = "claude-e2e-no-task-456"

        # 1. SessionStart
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # 2. Write some files (no task context)
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "README.md"},
                }
            )
        )

        # 3. Stop
        await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify forensics exist
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        assert forensics_path.exists()

        events = read_forensics(forensics_path)
        # Note: README.md is not categorized, so no file_write event
        # Only session_start and session_end
        assert len(events) == 2
        assert events[0]["event_type"] == "session_start"
        assert events[1]["event_type"] == "session_end"

        # Verify no ledger entry was created
        assert not (project_dir / ".cub" / "ledger" / "by-task").exists() or len(
            list((project_dir / ".cub" / "ledger" / "by-task").iterdir())
        ) == 0

    @pytest.mark.asyncio
    async def test_session_with_multiple_task_claims(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Test session with multiple task claims - last task wins.

        Flow: SessionStart -> Claim task A -> Claim task B -> Close task B -> Stop
        """
        session_id = "claude-e2e-multi-task-789"

        # 1. SessionStart
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # 2. Claim first task
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-first.1 --status in_progress"},
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
                    "tool_input": {"file_path": "src/feature_a.py"},
                }
            )
        )

        # 4. Claim second task (switches context)
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-second.2 --status in_progress"},
                }
            )
        )

        # 5. Write more files
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "src/feature_b.py"},
                }
            )
        )

        # 6. Close second task
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd close cub-second.2"},
                }
            )
        )

        # 7. Stop
        await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        events = read_forensics(forensics_path)
        assert len(events) == 7  # includes session_end from Stop handler

        # Verify only the last task got a ledger entry
        assert writer.entry_exists("cub-second.2")
        entry = writer.get_entry("cub-second.2")
        assert entry is not None
        assert entry.id == "cub-second.2"

        # Both files should be in the entry (all files written during session)
        assert "src/feature_a.py" in entry.outcome.files_changed
        assert "src/feature_b.py" in entry.outcome.files_changed

    @pytest.mark.asyncio
    async def test_session_interrupted_before_stop(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Test session interrupted before Stop event.

        No ledger entry should be created, but forensics should be recoverable.

        Flow: SessionStart -> Claim task -> Write files -> [INTERRUPT - no Stop]
        """
        session_id = "claude-e2e-interrupted-abc"

        # 1. SessionStart
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # 2. Claim task
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-int.1 --status in_progress"},
                }
            )
        )

        # 3. Write files
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "src/partial.py"},
                }
            )
        )

        # [INTERRUPT - no Stop or SessionEnd event]

        # Verify forensics exist and are readable
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        assert forensics_path.exists()

        events = read_forensics(forensics_path)
        assert len(events) == 3
        assert events[0]["event_type"] == "session_start"
        assert events[1]["event_type"] == "task_claim"
        assert events[2]["event_type"] == "file_write"

        # Verify no ledger entry was created (Stop never triggered synthesis)
        assert not writer.entry_exists("cub-int.1")

        # Verify forensics are structurally valid and could be recovered
        assert all("event_type" in e for e in events)
        assert all("timestamp" in e for e in events)
        assert all("session_id" in e for e in events)

    @pytest.mark.asyncio
    async def test_task_claimed_but_not_closed(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Test session where task is claimed but never closed.

        Ledger entry should be created with success=False.

        Flow: SessionStart -> Claim task -> Write files -> Stop (no close)
        """
        session_id = "claude-e2e-unclosed-def"

        # 1. SessionStart
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # 2. Claim task
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-unc.1 --status in_progress"},
                }
            )
        )

        # 3. Write files
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "src/incomplete.py"},
                }
            )
        )

        # 4. Stop (no close)
        await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify forensics
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        events = read_forensics(forensics_path)
        assert len(events) == 4  # includes session_end from Stop handler

        # Verify ledger entry was created
        assert writer.entry_exists("cub-unc.1")
        entry = writer.get_entry("cub-unc.1")
        assert entry is not None

        # Verify entry shows unsuccessful completion
        assert entry.attempts[0].success is False
        assert entry.outcome.success is False

    @pytest.mark.asyncio
    async def test_session_end_vs_stop_both_trigger_synthesis(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Test that both Stop and SessionEnd events trigger ledger synthesis.

        This ensures redundancy - if one is missed, the other still works.
        """
        session_id = "claude-e2e-dual-trigger-ghi"

        # Setup: Create forensics with task
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
                    "task_id": "cub-dual.1",
                },
                {
                    "event_type": "task_close",
                    "timestamp": "2026-01-28T10:30:00+00:00",
                    "session_id": session_id,
                    "task_id": "cub-dual.1",
                },
            ]
            for event in events:
                json.dump(event, f)
                f.write("\n")

        # Trigger Stop (first synthesis)
        await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify entry was created
        assert writer.entry_exists("cub-dual.1")
        entry_from_stop = writer.get_entry("cub-dual.1")
        assert entry_from_stop is not None

        # Trigger SessionEnd (should not overwrite if already finalized)
        await handle_session_end(
            HookEventPayload(
                {
                    "hook_event_name": "SessionEnd",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify entry still exists and wasn't corrupted
        entry_from_session_end = writer.get_entry("cub-dual.1")
        assert entry_from_session_end is not None
        assert entry_from_session_end.id == entry_from_stop.id

    def _verify_ledger_entry_structure(
        self, entry: LedgerEntry, session_id: str, success: bool
    ) -> None:
        """
        Verify ledger entry has the same structure as `cub run` produces.

        This validates parity between the two execution paths.
        """
        # Core fields (required for parity)
        assert entry.id is not None
        assert entry.title is not None

        # Attempts (must have exactly one for direct session)
        assert len(entry.attempts) == 1
        attempt = entry.attempts[0]
        assert attempt.run_id == session_id
        assert attempt.success == success
        assert attempt.harness == "claude"
        assert attempt.started_at is not None
        assert attempt.completed_at is not None

        # Outcome (required for parity)
        assert entry.outcome is not None
        assert entry.outcome.success == success
        assert entry.outcome.total_attempts == 1
        assert entry.outcome.files_changed is not None

        # Workflow state
        assert entry.workflow.stage == "dev_complete"

        # Verification (initial state)
        assert entry.verification.status == "pending"

        # Lineage (may be None if no spec/plan files)
        assert entry.lineage is not None

        # State history (should have transitions)
        assert len(entry.state_history) > 0


class TestLedgerEntryParity:
    """
    Test that symbiotic workflow ledger entries match `cub run` structure.

    These tests validate that the required fields are populated with
    equivalent data, ensuring the two paths are truly interchangeable.
    """

    @pytest.mark.asyncio
    async def test_ledger_entry_has_required_fields(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Verify ledger entry has all required fields that `cub run` produces.
        """
        session_id = "claude-parity-jkl"

        # Simulate complete session
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-par.1 --status in_progress"},
                }
            )
        )

        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "src/parity.py"},
                }
            )
        )

        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd close cub-par.1"},
                }
            )
        )

        await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify entry
        entry = writer.get_entry("cub-par.1")
        assert entry is not None

        # Required fields for parity with `cub run`
        required_fields = [
            "id",
            "title",
            "attempts",
            "outcome",
            "lineage",
            "workflow",
            "verification",
            "state_history",
        ]

        for field in required_fields:
            assert hasattr(entry, field), f"Missing required field: {field}"
            assert getattr(entry, field) is not None, f"Field {field} is None"

        # Verify nested required fields
        assert entry.attempts[0].run_id is not None
        assert entry.attempts[0].success is not None
        assert entry.attempts[0].harness is not None

        assert entry.outcome.success is not None
        assert entry.outcome.total_attempts is not None
        assert entry.outcome.files_changed is not None

        assert entry.workflow.stage is not None

    @pytest.mark.asyncio
    async def test_files_changed_matches_forensics(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Verify that outcome.files_changed matches forensics file_write events.
        """
        session_id = "claude-files-mno"

        # Simulate session with multiple file writes
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-files.1 --status in_progress"},
                }
            )
        )

        # Write multiple files
        files = ["src/feature.py", "tests/test_feature.py", "README.md"]
        for file_path in files:
            await handle_post_tool_use(
                HookEventPayload(
                    {
                        "hook_event_name": "PostToolUse",
                        "session_id": session_id,
                        "cwd": str(project_dir),
                        "tool_name": "Write",
                        "tool_input": {"file_path": file_path},
                    }
                )
            )

        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd close cub-files.1"},
                }
            )
        )

        await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify entry
        entry = writer.get_entry("cub-files.1")
        assert entry is not None

        # Verify tracked files (README.md is not categorized, so not tracked)
        tracked_files = ["src/feature.py", "tests/test_feature.py"]
        assert set(entry.outcome.files_changed) == set(tracked_files)

    @pytest.mark.asyncio
    async def test_lineage_extracted_from_file_writes(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Verify that lineage.spec_file and lineage.plan_file are extracted.
        """
        session_id = "claude-lineage-pqr"

        # Simulate session with spec and plan files
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Write spec file
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "specs/feature.md"},
                }
            )
        )

        # Write plan file
        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Write",
                    "tool_input": {"file_path": "plans/feature/plan.md"},
                }
            )
        )

        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-lin.1 --status in_progress"},
                }
            )
        )

        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd close cub-lin.1"},
                }
            )
        )

        await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify entry
        entry = writer.get_entry("cub-lin.1")
        assert entry is not None

        # Verify lineage was extracted
        assert entry.lineage.spec_file == "specs/feature.md"
        assert entry.lineage.plan_file == "plans/feature/plan.md"


class TestForensicsRecovery:
    """Test that forensics logs are recoverable even if ledger synthesis fails."""

    @pytest.mark.asyncio
    async def test_forensics_readable_after_crash(
        self,
        project_dir: Path,
        forensics_dir: Path,
    ) -> None:
        """
        Verify forensics can be read even if process crashes before synthesis.
        """
        session_id = "claude-crash-stu"

        # Simulate partial session
        await handle_session_start(
            HookEventPayload(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        await handle_post_tool_use(
            HookEventPayload(
                {
                    "hook_event_name": "PostToolUse",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                    "tool_name": "Bash",
                    "tool_input": {"command": "bd update cub-crash.1 --status in_progress"},
                }
            )
        )

        # [SIMULATE CRASH - no Stop or SessionEnd]

        # Verify forensics are intact and readable
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        assert forensics_path.exists()

        events = read_forensics(forensics_path)
        assert len(events) == 2
        assert events[0]["event_type"] == "session_start"
        assert events[1]["event_type"] == "task_claim"

        # Verify structure allows recovery
        for event in events:
            assert "event_type" in event
            assert "timestamp" in event
            assert "session_id" in event
            assert event["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_malformed_forensics_line_skipped(
        self,
        project_dir: Path,
        forensics_dir: Path,
        writer: LedgerWriter,
    ) -> None:
        """
        Verify that malformed forensics lines don't crash ledger synthesis.
        """
        session_id = "claude-malformed-vwx"

        # Manually create forensics with malformed line
        forensics_path = forensics_dir / f"{session_id}.jsonl"
        with forensics_path.open("w", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "event_type": "session_start",
                        "timestamp": "2026-01-28T10:00:00+00:00",
                        "session_id": session_id,
                    }
                )
                + "\n"
            )
            f.write("this is not valid json\n")
            f.write(
                json.dumps(
                    {
                        "event_type": "task_claim",
                        "timestamp": "2026-01-28T10:05:00+00:00",
                        "session_id": session_id,
                        "task_id": "cub-mal.1",
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "event_type": "task_close",
                        "timestamp": "2026-01-28T10:30:00+00:00",
                        "session_id": session_id,
                        "task_id": "cub-mal.1",
                    }
                )
                + "\n"
            )

        # Trigger synthesis
        await handle_stop(
            HookEventPayload(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "cwd": str(project_dir),
                }
            )
        )

        # Verify entry was still created (malformed line skipped)
        entry = writer.get_entry("cub-mal.1")
        assert entry is not None
        assert entry.id == "cub-mal.1"
