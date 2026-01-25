"""Tests for epic aggregation functionality.

Tests ensure epic aggregation works correctly across multiple tasks, including:
- Epic auto-creation when first task closes
- Aggregates computation from child tasks
- Escalation rate calculation
- Epic stage computation based on child task stages
- Handling multiple tasks within the same epic
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.ledger import (
    LedgerEntry,
    LedgerIntegration,
    LedgerWriter,
    Lineage,
    Outcome,
    TaskSnapshot,
    TokenUsage,
    WorkflowState,
)
from cub.core.ledger.models import EpicEntry
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


class TestEpicAutoCreation:
    """Tests for automatic epic creation when tasks close."""

    def test_epic_created_on_first_task_close(
        self, writer: LedgerWriter, ledger_dir: Path
    ) -> None:
        """Test that epic is auto-created when first task closes."""
        epic_id = "cub-test-epic"
        task_id = "cub-test-epic.1"

        # Create and finalize a task entry
        now = datetime.now(timezone.utc)
        task_entry = LedgerEntry(
            id=task_id,
            title="First Task",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="First Task"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(success=True, total_cost_usd=0.10, total_attempts=1),
            started_at=now,
            completed_at=now,
        )

        # Write task entry
        writer.create_entry(task_entry)

        # Trigger epic creation/update
        integration = LedgerIntegration(writer)
        integration._update_or_create_epic(epic_id, None)

        # Verify epic was created
        epic_entry = writer.get_epic_entry(epic_id)
        assert epic_entry is not None
        assert epic_entry.id == epic_id
        assert epic_entry.title == epic_id  # Default fallback title
        assert task_id in epic_entry.task_ids

    def test_epic_with_custom_metadata(
        self, integration: LedgerIntegration, writer: LedgerWriter
    ) -> None:
        """Test epic auto-creation without parent_task attribute falls back to epic_id as title."""
        epic_id = "cub-custom-epic"

        # Create a parent task to use as metadata source
        # Note: The integration code looks for parent_task attribute, which is not present
        # in a standalone Task object. The fallback behavior is to use epic_id as title.
        parent_task = Task(
            id=epic_id,
            title="Custom Task Title",
            description="Task description",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            labels=["phase-1", "critical"],
        )

        # Trigger epic creation with parent task (but no parent_task attribute on it)
        integration._update_or_create_epic(epic_id, parent_task)

        # Verify epic was created with fallback title (epic_id)
        epic_entry = writer.get_epic_entry(epic_id)
        assert epic_entry is not None
        # Without parent_task attribute, defaults to epic_id as title
        assert epic_entry.title == epic_id


class TestAggregatesComputation:
    """Tests for computing aggregates from child tasks."""

    def test_aggregates_single_task(self, writer: LedgerWriter) -> None:
        """Test aggregates computation with single task."""
        epic_id = "cub-single-task-epic"
        task_id = f"{epic_id}.1"

        now = datetime.now(timezone.utc)
        task_entry = LedgerEntry(
            id=task_id,
            title="Task 1",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 1"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(
                success=True,
                total_cost_usd=0.15,
                total_attempts=2,
                total_duration_seconds=600,
                final_model="haiku",
            ),
            tokens=TokenUsage(input_tokens=3000, output_tokens=2000),
            started_at=now,
            completed_at=now,
            harness_model="haiku",
        )

        writer.create_entry(task_entry)

        # Create epic and update aggregates
        epic_entry = EpicEntry(
            id=epic_id,
            title="Test Epic",
            lineage=Lineage(),
            task_ids=[task_id],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        agg = updated_epic.aggregates
        assert agg.total_tasks == 1
        assert agg.tasks_completed == 1  # Only counts successful tasks
        assert agg.tasks_successful == 1
        assert agg.tasks_failed == 0
        assert agg.total_cost_usd == 0.15
        assert agg.avg_cost_per_task == 0.15
        assert agg.total_attempts == 2
        # Tokens: input (3000) + output (2000) = 5000
        assert agg.total_tokens == 5000
        assert agg.total_duration_seconds == 600
        assert agg.most_common_model == "haiku"

    def test_aggregates_multiple_tasks(self, writer: LedgerWriter) -> None:
        """Test aggregates computation with multiple tasks."""
        epic_id = "cub-multi-task-epic"
        now = datetime.now(timezone.utc)

        # Task 1: successful
        task1_entry = LedgerEntry(
            id=f"{epic_id}.1",
            title="Task 1",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 1"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(
                success=True,
                total_cost_usd=0.10,
                total_attempts=1,
                total_duration_seconds=300,
                final_model="haiku",
            ),
            tokens=TokenUsage(input_tokens=2000, output_tokens=1000),
            started_at=now,
            completed_at=now,
            harness_model="haiku",
        )

        # Task 2: successful
        task2_entry = LedgerEntry(
            id=f"{epic_id}.2",
            title="Task 2",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 2"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(
                success=True,
                total_cost_usd=0.20,
                total_attempts=2,
                total_duration_seconds=600,
                final_model="sonnet",
            ),
            tokens=TokenUsage(input_tokens=5000, output_tokens=3000),
            started_at=now,
            completed_at=now,
            harness_model="sonnet",
        )

        # Task 3: failed
        task3_entry = LedgerEntry(
            id=f"{epic_id}.3",
            title="Task 3",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 3"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(
                success=False,
                total_cost_usd=0.05,
                total_attempts=1,
                total_duration_seconds=150,
                final_model="haiku",
            ),
            tokens=TokenUsage(input_tokens=1200, output_tokens=800),
            started_at=now,
            completed_at=now,
            harness_model="haiku",
        )

        writer.create_entry(task1_entry)
        writer.create_entry(task2_entry)
        writer.create_entry(task3_entry)

        # Create epic and update aggregates
        epic_entry = EpicEntry(
            id=epic_id,
            title="Multi-Task Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1", f"{epic_id}.2", f"{epic_id}.3"],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        agg = updated_epic.aggregates

        # Task metrics
        assert agg.total_tasks == 3
        # tasks_completed only counts successful tasks (success=True)
        assert agg.tasks_completed == 2
        assert agg.tasks_successful == 2
        assert agg.tasks_failed == 1

        # Cost metrics
        assert agg.total_cost_usd == pytest.approx(0.35)
        assert agg.avg_cost_per_task == pytest.approx(0.35 / 3)
        assert agg.min_cost_usd == 0.05
        assert agg.max_cost_usd == 0.20

        # Attempt metrics
        assert agg.total_attempts == 4
        assert agg.avg_attempts_per_task == pytest.approx(4 / 3)

        # Token metrics: Task1(3000) + Task2(8000) + Task3(2000) = 13000
        assert agg.total_tokens == 13000
        assert agg.avg_tokens_per_task == 13000 // 3

        # Duration metrics
        assert agg.total_duration_seconds == 1050
        assert agg.avg_duration_seconds == 1050 // 3

        # Model tracking
        assert set(agg.models_used) == {"haiku", "sonnet"}
        assert agg.most_common_model == "haiku"  # Used in 2 out of 3

    def test_aggregates_with_empty_epic(self, writer: LedgerWriter) -> None:
        """Test aggregates computation with no tasks."""
        epic_id = "cub-empty-epic"

        epic_entry = EpicEntry(
            id=epic_id,
            title="Empty Epic",
            lineage=Lineage(),
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        agg = updated_epic.aggregates
        assert agg.total_tasks == 0
        assert agg.tasks_completed == 0
        assert agg.total_cost_usd == 0.0
        assert agg.total_tokens == 0


class TestEscalationRate:
    """Tests for escalation rate calculation in aggregates."""

    def test_escalation_rate_no_escalations(self, writer: LedgerWriter) -> None:
        """Test escalation rate when no tasks escalated."""
        epic_id = "cub-no-escalation-epic"
        now = datetime.now(timezone.utc)

        for i in range(3):
            task_entry = LedgerEntry(
                id=f"{epic_id}.{i+1}",
                title=f"Task {i+1}",
                lineage=Lineage(epic_id=epic_id),
                task=TaskSnapshot(title=f"Task {i+1}"),
                workflow=WorkflowState(stage="dev_complete"),
                outcome=Outcome(
                    success=True,
                    total_cost_usd=0.10,
                    total_attempts=1,
                    escalated=False,
                ),
                tokens=TokenUsage(input_tokens=600, output_tokens=400),
                started_at=now,
                completed_at=now,
            )
            writer.create_entry(task_entry)

        epic_entry = EpicEntry(
            id=epic_id,
            title="No Escalation Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1", f"{epic_id}.2", f"{epic_id}.3"],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        agg = updated_epic.aggregates
        assert agg.total_escalations == 0
        assert agg.escalation_rate == 0.0

    def test_escalation_rate_partial_escalations(self, writer: LedgerWriter) -> None:
        """Test escalation rate with some escalations."""
        epic_id = "cub-partial-escalation-epic"
        now = datetime.now(timezone.utc)

        # Task 1: escalated
        task1_entry = LedgerEntry(
            id=f"{epic_id}.1",
            title="Task 1",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 1"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(
                success=True,
                total_cost_usd=0.10,
                total_attempts=3,
                escalated=True,
            ),
            tokens=TokenUsage(input_tokens=600, output_tokens=400),
            started_at=now,
            completed_at=now,
        )

        # Task 2: escalated
        task2_entry = LedgerEntry(
            id=f"{epic_id}.2",
            title="Task 2",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 2"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(
                success=True,
                total_cost_usd=0.10,
                total_attempts=2,
                escalated=True,
            ),
            tokens=TokenUsage(input_tokens=600, output_tokens=400),
            started_at=now,
            completed_at=now,
        )

        # Task 3: not escalated
        task3_entry = LedgerEntry(
            id=f"{epic_id}.3",
            title="Task 3",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 3"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(
                success=True,
                total_cost_usd=0.10,
                total_attempts=1,
                escalated=False,
            ),
            tokens=TokenUsage(input_tokens=600, output_tokens=400),
            started_at=now,
            completed_at=now,
        )

        writer.create_entry(task1_entry)
        writer.create_entry(task2_entry)
        writer.create_entry(task3_entry)

        epic_entry = EpicEntry(
            id=epic_id,
            title="Partial Escalation Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1", f"{epic_id}.2", f"{epic_id}.3"],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        agg = updated_epic.aggregates
        assert agg.total_escalations == 2
        assert agg.escalation_rate == pytest.approx(2 / 3)

    def test_escalation_rate_all_escalations(self, writer: LedgerWriter) -> None:
        """Test escalation rate when all tasks escalated."""
        epic_id = "cub-all-escalation-epic"
        now = datetime.now(timezone.utc)

        for i in range(2):
            task_entry = LedgerEntry(
                id=f"{epic_id}.{i+1}",
                title=f"Task {i+1}",
                lineage=Lineage(epic_id=epic_id),
                task=TaskSnapshot(title=f"Task {i+1}"),
                workflow=WorkflowState(stage="dev_complete"),
                outcome=Outcome(
                    success=True,
                    total_cost_usd=0.10,
                    total_attempts=2,
                    escalated=True,
                ),
                tokens=TokenUsage(input_tokens=600, output_tokens=400),
                started_at=now,
                completed_at=now,
            )
            writer.create_entry(task_entry)

        epic_entry = EpicEntry(
            id=epic_id,
            title="All Escalation Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1", f"{epic_id}.2"],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        agg = updated_epic.aggregates
        assert agg.total_escalations == 2
        assert agg.escalation_rate == 1.0


class TestEpicStageComputation:
    """Tests for epic workflow stage computation based on child tasks."""

    def test_epic_stage_all_dev_complete(self, writer: LedgerWriter) -> None:
        """Test epic stage when all tasks are dev_complete."""
        epic_id = "cub-dev-complete-epic"
        now = datetime.now(timezone.utc)

        for i in range(2):
            task_entry = LedgerEntry(
                id=f"{epic_id}.{i+1}",
                title=f"Task {i+1}",
                lineage=Lineage(epic_id=epic_id),
                task=TaskSnapshot(title=f"Task {i+1}"),
                workflow=WorkflowState(stage="dev_complete"),
                outcome=Outcome(success=True, total_cost_usd=0.10),
                tokens=TokenUsage(input_tokens=600, output_tokens=400),
                started_at=now,
                completed_at=now,
            )
            writer.create_entry(task_entry)

        epic_entry = EpicEntry(
            id=epic_id,
            title="Dev Complete Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1", f"{epic_id}.2"],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        assert updated_epic.workflow.stage == "dev_complete"

    def test_epic_stage_mixed_stages(self, writer: LedgerWriter) -> None:
        """Test epic stage when tasks have different stages."""
        epic_id = "cub-mixed-stage-epic"
        now = datetime.now(timezone.utc)

        # Task 1: dev_complete
        task1_entry = LedgerEntry(
            id=f"{epic_id}.1",
            title="Task 1",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 1"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(success=True, total_cost_usd=0.10),
            tokens=TokenUsage(input_tokens=600, output_tokens=400),
            started_at=now,
            completed_at=now,
        )

        # Task 2: needs_review
        task2_entry = LedgerEntry(
            id=f"{epic_id}.2",
            title="Task 2",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 2"),
            workflow=WorkflowState(stage="needs_review"),
            outcome=Outcome(success=True, total_cost_usd=0.10),
            tokens=TokenUsage(input_tokens=600, output_tokens=400),
            started_at=now,
            completed_at=now,
        )

        writer.create_entry(task1_entry)
        writer.create_entry(task2_entry)

        epic_entry = EpicEntry(
            id=epic_id,
            title="Mixed Stage Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1", f"{epic_id}.2"],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        # Epic stage should be the least-progressed stage
        assert updated_epic.workflow.stage == "dev_complete"

    def test_epic_stage_all_released(self, writer: LedgerWriter) -> None:
        """Test epic stage when all tasks are released."""
        epic_id = "cub-released-epic"
        now = datetime.now(timezone.utc)

        for i in range(2):
            task_entry = LedgerEntry(
                id=f"{epic_id}.{i+1}",
                title=f"Task {i+1}",
                lineage=Lineage(epic_id=epic_id),
                task=TaskSnapshot(title=f"Task {i+1}"),
                workflow=WorkflowState(stage="released"),
                outcome=Outcome(success=True, total_cost_usd=0.10),
                tokens=TokenUsage(input_tokens=600, output_tokens=400),
                started_at=now,
                completed_at=now,
            )
            writer.create_entry(task_entry)

        epic_entry = EpicEntry(
            id=epic_id,
            title="Released Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1", f"{epic_id}.2"],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        assert updated_epic.workflow.stage == "released"


class TestMultipleTasksInEpic:
    """Tests for handling multiple tasks within the same epic."""

    def test_task_ids_updated_on_aggregation(self, writer: LedgerWriter) -> None:
        """Test that task_ids list is updated correctly during aggregation."""
        epic_id = "cub-task-tracking-epic"
        now = datetime.now(timezone.utc)

        task_ids = [f"{epic_id}.1", f"{epic_id}.2", f"{epic_id}.3"]

        for i, task_id in enumerate(task_ids):
            task_entry = LedgerEntry(
                id=task_id,
                title=f"Task {i+1}",
                lineage=Lineage(epic_id=epic_id),
                task=TaskSnapshot(title=f"Task {i+1}"),
                workflow=WorkflowState(stage="dev_complete"),
                outcome=Outcome(success=True, total_cost_usd=0.10),
                tokens=TokenUsage(input_tokens=600, output_tokens=400),
                started_at=now,
                completed_at=now,
            )
            writer.create_entry(task_entry)

        epic_entry = EpicEntry(
            id=epic_id,
            title="Task Tracking Epic",
            lineage=Lineage(),
            task_ids=[],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        assert set(updated_epic.task_ids) == set(task_ids)

    def test_add_task_to_epic(self, writer: LedgerWriter) -> None:
        """Test adding a task to an existing epic."""
        epic_id = "cub-add-task-epic"
        now = datetime.now(timezone.utc)

        # Create first task
        task1_entry = LedgerEntry(
            id=f"{epic_id}.1",
            title="Task 1",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 1"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(success=True, total_cost_usd=0.10),
            tokens=TokenUsage(input_tokens=600, output_tokens=400),
            started_at=now,
            completed_at=now,
        )
        writer.create_entry(task1_entry)

        # Create epic
        epic_entry = EpicEntry(
            id=epic_id,
            title="Add Task Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1"],
        )
        writer.create_epic_entry(epic_entry)

        # Add second task using add_task_to_epic
        task2_entry = LedgerEntry(
            id=f"{epic_id}.2",
            title="Task 2",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 2"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(success=True, total_cost_usd=0.15),
            tokens=TokenUsage(total_tokens=1500),
            started_at=now,
            completed_at=now,
        )
        writer.create_entry(task2_entry)

        # Add to epic
        result = writer.add_task_to_epic(epic_id, f"{epic_id}.2")
        assert result is True

        # Verify epic was updated
        updated_epic = writer.get_epic_entry(epic_id)
        assert updated_epic is not None
        assert f"{epic_id}.2" in updated_epic.task_ids

    def test_temporal_bounds_updated_from_tasks(self, writer: LedgerWriter) -> None:
        """Test that epic temporal bounds (started_at, completed_at) are updated from tasks."""
        epic_id = "cub-temporal-epic"

        start1 = datetime(2026, 1, 24, 10, 0, tzinfo=timezone.utc)
        end1 = datetime(2026, 1, 24, 11, 0, tzinfo=timezone.utc)

        start2 = datetime(2026, 1, 24, 9, 0, tzinfo=timezone.utc)  # Earlier
        end2 = datetime(2026, 1, 24, 12, 0, tzinfo=timezone.utc)  # Later

        # Task 1
        task1_entry = LedgerEntry(
            id=f"{epic_id}.1",
            title="Task 1",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 1"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(success=True, total_cost_usd=0.10),
            tokens=TokenUsage(input_tokens=600, output_tokens=400),
            started_at=start1,
            completed_at=end1,
        )

        # Task 2
        task2_entry = LedgerEntry(
            id=f"{epic_id}.2",
            title="Task 2",
            lineage=Lineage(epic_id=epic_id),
            task=TaskSnapshot(title="Task 2"),
            workflow=WorkflowState(stage="dev_complete"),
            outcome=Outcome(success=True, total_cost_usd=0.10),
            tokens=TokenUsage(input_tokens=600, output_tokens=400),
            started_at=start2,
            completed_at=end2,
        )

        writer.create_entry(task1_entry)
        writer.create_entry(task2_entry)

        epic_entry = EpicEntry(
            id=epic_id,
            title="Temporal Epic",
            lineage=Lineage(),
            task_ids=[f"{epic_id}.1", f"{epic_id}.2"],
        )
        writer.create_epic_entry(epic_entry)
        updated_epic = writer.update_epic_aggregates(epic_id)

        assert updated_epic is not None
        # Epic should start at earliest task start
        assert updated_epic.started_at == start2
        # Epic should complete at latest task completion
        assert updated_epic.completed_at == end2

    def test_add_task_to_nonexistent_epic_fails(self, writer: LedgerWriter) -> None:
        """Test that adding a task to non-existent epic returns False."""
        epic_id = "cub-nonexistent-epic"
        task_id = f"{epic_id}.1"

        result = writer.add_task_to_epic(epic_id, task_id)
        assert result is False
