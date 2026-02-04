"""Tests for LedgerIntegration layer."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.ledger.integration import LedgerIntegration
from cub.core.ledger.models import (
    LedgerEntry,
    TokenUsage,
    Verification,
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
def writer(ledger_dir: Path) -> LedgerWriter:
    """Create a LedgerWriter instance."""
    return LedgerWriter(ledger_dir)


@pytest.fixture
def integration(writer: LedgerWriter) -> LedgerIntegration:
    """Create a LedgerIntegration instance."""
    return LedgerIntegration(writer)


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


class TestLedgerIntegrationInit:
    """Tests for LedgerIntegration initialization."""

    def test_init(self, writer: LedgerWriter) -> None:
        """Test integration initialization."""
        integration = LedgerIntegration(writer)
        assert integration.writer is writer
        assert integration._active_entries == {}
        assert integration._task_snapshots == {}


class TestOnTaskStart:
    """Tests for on_task_start method."""

    def test_on_task_start_basic(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test basic task start creates ledger entry."""
        run_id = "cub-20260124-163241"

        entry = integration.on_task_start(sample_task, run_id=run_id)

        # Check entry was created
        assert entry.id == sample_task.id
        assert entry.title == sample_task.title

        # Check task snapshot was captured
        assert entry.task is not None
        assert entry.task.title == sample_task.title
        assert entry.task.description == sample_task.description
        assert entry.task.priority == sample_task.priority_numeric
        assert entry.task.labels == sample_task.labels

        # Check started_at is set
        assert entry.started_at is not None

        # Check workflow state
        assert entry.workflow.stage == "dev_complete"

        # Check state history
        assert len(entry.state_history) == 1
        assert entry.state_history[0].stage == "dev_complete"
        assert entry.state_history[0].by == "cub-run"

    def test_on_task_start_with_epic(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test task start with epic ID."""
        run_id = "cub-20260124-163241"
        epic_id = "cub-xyz"

        entry = integration.on_task_start(sample_task, run_id=run_id, epic_id=epic_id)

        assert entry.lineage.epic_id == epic_id
        assert entry.epic_id == epic_id  # Legacy field

    def test_on_task_start_with_spec_and_plan(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test task start with spec and plan files."""
        run_id = "cub-20260124-163241"
        spec_file = "specs/planned/feature-x.md"
        plan_file = "plans/feature-x/plan.jsonl"

        entry = integration.on_task_start(
            sample_task,
            run_id=run_id,
            spec_file=spec_file,
            plan_file=plan_file,
        )

        assert entry.lineage.spec_file == spec_file
        assert entry.lineage.plan_file == plan_file

    def test_on_task_start_writes_entry(
        self,
        integration: LedgerIntegration,
        writer: LedgerWriter,
        sample_task: Task,
    ) -> None:
        """Test task start writes entry to disk."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        # Verify entry was written
        assert writer.entry_exists(sample_task.id)
        entry = writer.get_entry(sample_task.id)
        assert entry is not None
        assert entry.title == sample_task.title

    def test_on_task_start_caches_entry(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test task start caches the active entry."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        # Check it's in cache
        assert integration.has_active_entry(sample_task.id)
        cached = integration.get_active_entry(sample_task.id)
        assert cached is not None
        assert cached.id == sample_task.id

    def test_on_task_start_duplicate_raises(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test starting same task twice raises error."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        with pytest.raises(ValueError, match="already active"):
            integration.on_task_start(sample_task, run_id=run_id)


class TestOnAttemptStart:
    """Tests for on_attempt_start method."""

    def test_on_attempt_start_writes_prompt(
        self,
        integration: LedgerIntegration,
        ledger_dir: Path,
    ) -> None:
        """Test attempt start writes prompt file."""
        task_id = "cub-xyz"
        run_id = "cub-20260124-163241"
        prompt_content = "# Task: Fix bug\n\nFix the login bug..."

        prompt_path = integration.on_attempt_start(
            task_id,
            1,
            prompt_content,
            run_id=run_id,
            harness="claude",
            model="haiku",
        )

        # Verify file was created
        assert prompt_path.exists()
        assert prompt_path.name == "001-prompt.md"

        # Verify content
        content = prompt_path.read_text()
        assert "---" in content  # Has frontmatter
        assert "attempt: 1" in content
        assert "harness: claude" in content
        assert "model: haiku" in content
        assert "# Task: Fix bug" in content

    def test_on_attempt_start_multiple_attempts(
        self,
        integration: LedgerIntegration,
    ) -> None:
        """Test multiple attempt starts create separate files."""
        task_id = "cub-xyz"
        run_id = "cub-20260124-163241"

        path1 = integration.on_attempt_start(task_id, 1, "Attempt 1", run_id=run_id)
        path2 = integration.on_attempt_start(task_id, 2, "Attempt 2", run_id=run_id)
        path3 = integration.on_attempt_start(task_id, 3, "Attempt 3", run_id=run_id)

        assert path1.name == "001-prompt.md"
        assert path2.name == "002-prompt.md"
        assert path3.name == "003-prompt.md"


class TestOnAttemptEnd:
    """Tests for on_attempt_end method."""

    def test_on_attempt_end_writes_log(
        self,
        integration: LedgerIntegration,
        ledger_dir: Path,
    ) -> None:
        """Test attempt end writes harness log."""
        task_id = "cub-xyz"
        run_id = "cub-20260124-163241"
        log_content = "Harness output here...\nDone!"

        attempt = integration.on_attempt_end(
            task_id,
            1,
            log_content,
            run_id=run_id,
            success=True,
            harness="claude",
            model="haiku",
        )

        # Verify log file was created (using new flattened structure)
        log_path = ledger_dir / "by-task" / task_id / "001-harness.jsonl"
        assert log_path.exists()
        assert log_path.read_text() == log_content

        # Verify attempt record
        assert attempt.attempt_number == 1
        assert attempt.run_id == run_id
        assert attempt.success is True
        assert attempt.harness == "claude"
        assert attempt.model == "haiku"

    def test_on_attempt_end_with_tokens(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test attempt end records token usage."""
        run_id = "cub-20260124-163241"
        tokens = TokenUsage(input_tokens=1000, output_tokens=500)

        # Start task first
        integration.on_task_start(sample_task, run_id=run_id)

        attempt = integration.on_attempt_end(
            sample_task.id,
            1,
            "Log content",
            run_id=run_id,
            success=True,
            tokens=tokens,
            cost_usd=0.05,
            duration_seconds=30,
        )

        assert attempt.tokens.input_tokens == 1000
        assert attempt.tokens.output_tokens == 500
        assert attempt.cost_usd == 0.05
        assert attempt.duration_seconds == 30

    def test_on_attempt_end_updates_active_entry(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test attempt end updates the active entry."""
        run_id = "cub-20260124-163241"
        tokens = TokenUsage(input_tokens=1000, output_tokens=500)

        # Start task
        integration.on_task_start(sample_task, run_id=run_id)

        # First attempt
        integration.on_attempt_end(
            sample_task.id,
            1,
            "Log 1",
            run_id=run_id,
            success=False,
            tokens=tokens,
            cost_usd=0.05,
        )

        # Check entry was updated
        entry = integration.get_active_entry(sample_task.id)
        assert entry is not None
        assert len(entry.attempts) == 1
        assert entry.iterations == 1
        assert entry.cost_usd == 0.05

        # Second attempt
        integration.on_attempt_end(
            sample_task.id,
            2,
            "Log 2",
            run_id=run_id,
            success=True,
            tokens=tokens,
            cost_usd=0.03,
        )

        # Check aggregated
        entry = integration.get_active_entry(sample_task.id)
        assert entry is not None
        assert len(entry.attempts) == 2
        assert entry.iterations == 2
        assert entry.cost_usd == 0.08

    def test_on_attempt_end_with_error(
        self,
        integration: LedgerIntegration,
    ) -> None:
        """Test attempt end with error information."""
        task_id = "cub-xyz"
        run_id = "cub-20260124-163241"

        attempt = integration.on_attempt_end(
            task_id,
            1,
            "Error log...",
            run_id=run_id,
            success=False,
            error_category="timeout",
            error_summary="Task timed out after 10 minutes",
        )

        assert attempt.success is False
        assert attempt.error_category == "timeout"
        assert attempt.error_summary == "Task timed out after 10 minutes"


class TestOnTaskClose:
    """Tests for on_task_close method."""

    def test_on_task_close_basic(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test basic task close finalizes entry."""
        run_id = "cub-20260124-163241"

        # Start task
        integration.on_task_start(sample_task, run_id=run_id)

        # Add an attempt
        integration.on_attempt_end(
            sample_task.id,
            1,
            "Log",
            run_id=run_id,
            success=True,
            cost_usd=0.05,
            duration_seconds=30,
        )

        # Close task
        entry = integration.on_task_close(
            sample_task.id,
            success=True,
            final_model="haiku",
            files_changed=["src/feature.py"],
        )

        assert entry is not None
        assert entry.outcome is not None
        assert entry.outcome.success is True
        assert entry.outcome.total_cost_usd == 0.05
        assert entry.outcome.total_attempts == 1
        assert entry.outcome.total_duration_seconds == 30
        assert entry.outcome.final_model == "haiku"
        assert entry.outcome.files_changed == ["src/feature.py"]

    def test_on_task_close_with_verification(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test task close with verification status."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)
        integration.on_attempt_end(sample_task.id, 1, "Log", run_id=run_id, success=True)

        verification = Verification(
            status="pass",
            checked_at=datetime.now(timezone.utc),
            tests_passed=True,
            typecheck_passed=True,
            lint_passed=True,
        )

        entry = integration.on_task_close(
            sample_task.id,
            success=True,
            verification=verification,
        )

        assert entry is not None
        assert entry.verification.status == "pass"
        assert entry.verification.tests_passed is True

    def test_on_task_close_detects_escalation(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test task close detects model escalation."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        # First attempt with haiku
        integration.on_attempt_end(
            sample_task.id,
            1,
            "Log 1",
            run_id=run_id,
            success=False,
            model="haiku",
        )

        # Second attempt with sonnet (escalated)
        integration.on_attempt_end(
            sample_task.id,
            2,
            "Log 2",
            run_id=run_id,
            success=True,
            model="sonnet",
        )

        entry = integration.on_task_close(sample_task.id, success=True)

        assert entry is not None
        assert entry.outcome is not None
        assert entry.outcome.escalated is True
        assert entry.outcome.escalation_path == ["haiku", "sonnet"]

    def test_on_task_close_removes_from_cache(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test task close removes entry from cache."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)
        assert integration.has_active_entry(sample_task.id)

        integration.on_task_close(sample_task.id, success=True)
        assert not integration.has_active_entry(sample_task.id)

    def test_on_task_close_nonexistent_returns_none(
        self,
        integration: LedgerIntegration,
    ) -> None:
        """Test closing nonexistent task returns None."""
        entry = integration.on_task_close("nonexistent-task", success=True)
        assert entry is None


class TestDetectTaskChanged:
    """Tests for _detect_task_changed method."""

    def test_detect_no_changes(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test no drift detected when task unchanged."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        # Same task, no changes
        task_changed = integration._detect_task_changed(sample_task.id, sample_task)
        assert task_changed is None

    def test_detect_title_change(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test drift detected when title changes."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        # Modify task
        modified_task = Task(
            id=sample_task.id,
            title="Updated title",
            description=sample_task.description,
            priority=sample_task.priority,
            labels=list(sample_task.labels),
        )

        task_changed = integration._detect_task_changed(sample_task.id, modified_task)
        assert task_changed is not None
        assert "title" in task_changed.fields_changed
        assert "Updated title" in (task_changed.notes or "")

    def test_detect_description_change(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test drift detected when description changes."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        modified_task = Task(
            id=sample_task.id,
            title=sample_task.title,
            description="New description",
            priority=sample_task.priority,
        )

        task_changed = integration._detect_task_changed(sample_task.id, modified_task)
        assert task_changed is not None
        assert "description" in task_changed.fields_changed
        assert task_changed.original_description == sample_task.description
        assert task_changed.final_description == "New description"

    def test_detect_label_change(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test drift detected when labels change."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        modified_task = Task(
            id=sample_task.id,
            title=sample_task.title,
            description=sample_task.description,
            priority=sample_task.priority,
            labels=["phase-2", "new-label"],  # Changed
        )

        task_changed = integration._detect_task_changed(sample_task.id, modified_task)
        assert task_changed is not None
        assert "labels" in task_changed.fields_changed

    def test_detect_priority_change(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test drift detected when priority changes."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        modified_task = Task(
            id=sample_task.id,
            title=sample_task.title,
            description=sample_task.description,
            priority=TaskPriority.P0,  # Changed from P1
        )

        task_changed = integration._detect_task_changed(sample_task.id, modified_task)
        assert task_changed is not None
        assert "priority" in task_changed.fields_changed

    def test_detect_no_snapshot_returns_none(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test detection returns None when no snapshot exists."""
        # Don't start task (no snapshot)
        task_changed = integration._detect_task_changed(sample_task.id, sample_task)
        assert task_changed is None


class TestHelperMethods:
    """Tests for helper methods."""

    def test_has_active_entry(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test has_active_entry method."""
        run_id = "cub-20260124-163241"

        assert not integration.has_active_entry(sample_task.id)
        integration.on_task_start(sample_task, run_id=run_id)
        assert integration.has_active_entry(sample_task.id)

    def test_get_attempt_count(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test get_attempt_count method."""
        run_id = "cub-20260124-163241"

        assert integration.get_attempt_count(sample_task.id) == 0

        integration.on_task_start(sample_task, run_id=run_id)
        assert integration.get_attempt_count(sample_task.id) == 0

        integration.on_attempt_end(sample_task.id, 1, "Log", run_id=run_id, success=True)
        assert integration.get_attempt_count(sample_task.id) == 1

        integration.on_attempt_end(sample_task.id, 2, "Log", run_id=run_id, success=True)
        assert integration.get_attempt_count(sample_task.id) == 2

    def test_get_attempt_count_from_disk(
        self,
        integration: LedgerIntegration,
        writer: LedgerWriter,
    ) -> None:
        """Test get_attempt_count reads from disk when not in cache."""
        # Create an entry directly via writer
        from cub.core.ledger.models import Attempt

        entry = LedgerEntry(
            id="cub-disk",
            title="Task from disk",
            attempts=[
                Attempt(attempt_number=1, run_id="run-1", success=True),
                Attempt(attempt_number=2, run_id="run-1", success=True),
            ],
        )
        writer.create_entry(entry)

        # Not in cache, should read from disk
        assert integration.get_attempt_count("cub-disk") == 2


class TestFullWorkflow:
    """Test complete task execution workflows."""

    def test_single_successful_attempt(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test workflow with single successful attempt."""
        run_id = "cub-20260124-163241"

        # 1. Start task
        integration.on_task_start(
            sample_task,
            run_id=run_id,
            epic_id="cub-abc",
        )

        # 2. Start attempt
        prompt_path = integration.on_attempt_start(
            sample_task.id,
            1,
            "# Task\n\nFix the bug",
            run_id=run_id,
            harness="claude",
            model="haiku",
        )
        assert prompt_path.exists()

        # 3. End attempt (success)
        tokens = TokenUsage(input_tokens=1000, output_tokens=500)
        integration.on_attempt_end(
            sample_task.id,
            1,
            "Harness output",
            run_id=run_id,
            success=True,
            harness="claude",
            model="haiku",
            tokens=tokens,
            cost_usd=0.05,
            duration_seconds=45,
        )

        # 4. Close task
        verification = Verification(status="pass", tests_passed=True)
        entry = integration.on_task_close(
            sample_task.id,
            success=True,
            final_model="haiku",
            files_changed=["src/bug.py"],
            verification=verification,
        )

        # Verify final state
        assert entry is not None
        assert entry.outcome is not None
        assert entry.outcome.success is True
        assert entry.outcome.total_attempts == 1
        assert entry.outcome.escalated is False
        assert entry.outcome.final_model == "haiku"
        assert entry.verification.status == "pass"

    def test_multiple_attempts_with_escalation(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test workflow with multiple attempts and model escalation."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)

        # First attempt fails with haiku
        integration.on_attempt_start(
            sample_task.id, 1, "Prompt 1", run_id=run_id, harness="claude", model="haiku"
        )
        integration.on_attempt_end(
            sample_task.id,
            1,
            "Failed log",
            run_id=run_id,
            success=False,
            model="haiku",
            error_category="timeout",
            cost_usd=0.02,
        )

        # Second attempt fails with sonnet
        integration.on_attempt_start(
            sample_task.id, 2, "Prompt 2", run_id=run_id, harness="claude", model="sonnet"
        )
        integration.on_attempt_end(
            sample_task.id,
            2,
            "Failed again",
            run_id=run_id,
            success=False,
            model="sonnet",
            error_category="api_error",
            cost_usd=0.10,
        )

        # Third attempt succeeds with opus
        integration.on_attempt_start(
            sample_task.id, 3, "Prompt 3", run_id=run_id, harness="claude", model="opus"
        )
        integration.on_attempt_end(
            sample_task.id,
            3,
            "Success!",
            run_id=run_id,
            success=True,
            model="opus",
            cost_usd=0.50,
            duration_seconds=120,
        )

        entry = integration.on_task_close(sample_task.id, success=True)

        # Verify escalation
        assert entry is not None
        assert entry.outcome is not None
        assert entry.outcome.escalated is True
        assert entry.outcome.escalation_path == ["haiku", "sonnet", "opus"]
        assert entry.outcome.total_attempts == 3
        assert entry.outcome.total_cost_usd == 0.62  # 0.02 + 0.10 + 0.50

    def test_task_with_drift(
        self,
        integration: LedgerIntegration,
        sample_task: Task,
    ) -> None:
        """Test workflow with task drift detection."""
        run_id = "cub-20260124-163241"

        integration.on_task_start(sample_task, run_id=run_id)
        integration.on_attempt_end(
            sample_task.id, 1, "Log", run_id=run_id, success=True
        )

        # Task was modified during execution
        modified_task = Task(
            id=sample_task.id,
            title="Implement feature X (expanded scope)",  # Changed
            description="Extended description with new requirements",  # Changed
            priority=TaskPriority.P0,  # Changed from P1
            labels=["phase-1", "complexity:high"],  # Changed
        )

        entry = integration.on_task_close(
            sample_task.id,
            success=True,
            current_task=modified_task,
        )

        # Verify drift detection
        assert entry is not None
        assert entry.task_changed is not None
        assert "title" in entry.task_changed.fields_changed
        assert "description" in entry.task_changed.fields_changed
        assert "priority" in entry.task_changed.fields_changed
        assert "labels" in entry.task_changed.fields_changed
