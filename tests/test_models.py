"""
Unit tests for Pydantic models.

Tests validation, serialization, and computed properties for Task, Config,
and Status models.
"""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from cub.core.config.models import (
    BudgetConfig,
    CubConfig,
    GuardrailsConfig,
    HarnessConfig,
    HooksConfig,
    InterviewConfig,
    InterviewQuestion,
    LoopConfig,
    ReviewConfig,
    StateConfig,
)
from cub.core.status.models import (
    BudgetStatus,
    EventLevel,
    EventLog,
    IterationInfo,
    RunPhase,
    RunStatus,
)
from cub.core.tasks.models import (
    Task,
    TaskCounts,
    TaskPriority,
    TaskStatus,
    TaskType,
)


# ==============================================================================
# Task Model Tests
# ==============================================================================


class TestTaskModel:
    """Test Task model validation and behavior."""

    def test_minimal_task_creation(self):
        """Test creating a task with minimal required fields."""
        task = Task(id="cub-001", title="Test task")
        assert task.id == "cub-001"
        assert task.title == "Test task"
        assert task.status == TaskStatus.OPEN
        assert task.priority == TaskPriority.P2
        assert task.type == TaskType.TASK

    def test_full_task_creation(self):
        """Test creating a task with all fields."""
        task = Task(
            id="cub-002",
            title="Full task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P0,
            type=TaskType.FEATURE,
            description="Detailed description",
            assignee="alice",
            labels=["bug", "urgent", "model:sonnet"],
            depends_on=["cub-001"],
            blocks=["cub-003"],
            parent="epic-001",
            notes="Some notes",
        )
        assert task.priority == TaskPriority.P0
        assert task.assignee == "alice"
        assert len(task.labels) == 3
        assert task.depends_on == ["cub-001"]

    def test_task_validation_empty_title(self):
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Task(id="cub-001", title="")
        assert "title" in str(exc_info.value)

    def test_task_priority_enum(self):
        """Test TaskPriority enum values and numeric conversion."""
        assert TaskPriority.P0.numeric_value == 0
        assert TaskPriority.P1.numeric_value == 1
        assert TaskPriority.P2.numeric_value == 2
        assert TaskPriority.P3.numeric_value == 3
        assert TaskPriority.P4.numeric_value == 4

    def test_model_label_extraction(self):
        """Test model_label computed field."""
        task = Task(
            id="cub-001",
            title="Test",
            labels=["bug", "model:haiku", "urgent"]
        )
        assert task.model_label == "haiku"

        task_no_model = Task(id="cub-002", title="Test", labels=["bug"])
        assert task_no_model.model_label is None

    def test_is_ready_computed_field(self):
        """Test is_ready computed property."""
        # Task with no dependencies is ready
        task1 = Task(id="cub-001", title="Ready task", status=TaskStatus.OPEN)
        assert task1.is_ready is True

        # Task with dependencies is not ready (even if status is open)
        task2 = Task(
            id="cub-002",
            title="Blocked task",
            status=TaskStatus.OPEN,
            depends_on=["cub-001"]
        )
        assert task2.is_ready is False

        # In-progress task is not ready
        task3 = Task(
            id="cub-003",
            title="In progress",
            status=TaskStatus.IN_PROGRESS
        )
        assert task3.is_ready is False

    def test_task_methods(self):
        """Test task convenience methods."""
        task = Task(id="cub-001", title="Test")

        # Test label operations
        task.add_label("bug")
        assert "bug" in task.labels
        task.add_label("bug")  # Should not duplicate
        assert task.labels.count("bug") == 1

        task.remove_label("bug")
        assert "bug" not in task.labels

        # Test status transitions
        task.mark_in_progress("alice")
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.assignee == "alice"

        task.close()
        assert task.status == TaskStatus.CLOSED
        assert task.closed_at is not None

        task.reopen()
        assert task.status == TaskStatus.OPEN
        assert task.closed_at is None

    def test_alias_support(self):
        """Test that both depends_on and dependsOn work."""
        # Using snake_case
        task1 = Task(
            id="cub-001",
            title="Test",
            depends_on=["cub-000"]
        )
        assert task1.depends_on == ["cub-000"]

        # Using camelCase (from beads JSON)
        data = {
            "id": "cub-002",
            "title": "Test",
            "dependsOn": ["cub-001"],
            "issue_type": "feature",
            "acceptanceCriteria": ["criterion 1"]
        }
        task2 = Task(**data)
        assert task2.depends_on == ["cub-001"]
        assert task2.type == TaskType.FEATURE
        assert task2.acceptance_criteria == ["criterion 1"]

    def test_parse_beads_json(self):
        """Test parsing actual beads JSON structure."""
        beads_data = {
            "id": "cub-054",
            "title": "Create Pydantic models",
            "description": "Define core models",
            "status": "in_progress",
            "priority": 0,
            "issue_type": "task",
            "assignee": "camel",
            "labels": ["model:sonnet", "phase-1"],
            "blocks": ["cub-055"]
        }
        task = Task(**beads_data)
        assert task.id == "cub-054"
        assert task.priority == TaskPriority.P0
        assert task.type == TaskType.TASK
        assert task.blocks == ["cub-055"]
        assert task.model_label == "sonnet"


class TestTaskCounts:
    """Test TaskCounts model."""

    def test_task_counts_computed_fields(self):
        """Test computed fields for task counts."""
        counts = TaskCounts(total=10, open=3, in_progress=2, closed=5)
        assert counts.remaining == 5
        assert counts.completion_percentage == 50.0

    def test_task_counts_zero_division(self):
        """Test that completion percentage handles zero total."""
        counts = TaskCounts(total=0, open=0, in_progress=0, closed=0)
        assert counts.completion_percentage == 0.0


# ==============================================================================
# Config Model Tests
# ==============================================================================


class TestConfigModels:
    """Test configuration models."""

    def test_guardrails_config_defaults(self):
        """Test GuardrailsConfig default values."""
        config = GuardrailsConfig()
        assert config.max_task_iterations == 3
        assert config.max_run_iterations == 50
        assert config.iteration_warning_threshold == 0.8
        assert "api" in " ".join(config.secret_patterns)

    def test_guardrails_config_validation(self):
        """Test GuardrailsConfig validation."""
        # Valid config
        config = GuardrailsConfig(max_task_iterations=5)
        assert config.max_task_iterations == 5

        # Invalid: max_task_iterations must be >= 1
        with pytest.raises(ValidationError):
            GuardrailsConfig(max_task_iterations=0)

        # Invalid: threshold must be 0-1
        with pytest.raises(ValidationError):
            GuardrailsConfig(iteration_warning_threshold=1.5)

    def test_budget_config(self):
        """Test BudgetConfig model."""
        config = BudgetConfig(
            max_tokens_per_task=500000,
            max_total_cost=50.0
        )
        assert config.max_tokens_per_task == 500000
        assert config.max_total_cost == 50.0
        assert config.max_tasks_per_session is None

    def test_state_config(self):
        """Test StateConfig model."""
        config = StateConfig(
            require_clean=True,
            run_tests=True
        )
        assert config.require_clean is True
        assert config.run_tests is True
        assert config.run_typecheck is False

    def test_loop_config_validation(self):
        """Test LoopConfig validation."""
        config = LoopConfig(max_iterations=100, on_task_failure="stop")
        assert config.on_task_failure == "stop"

        # Invalid on_task_failure value
        with pytest.raises(ValidationError):
            LoopConfig(on_task_failure="invalid")

    def test_interview_question(self):
        """Test InterviewQuestion model."""
        question = InterviewQuestion(
            category="Technical",
            question="What is the impact?",
            applies_to=["feature", "task"],
            requires_labels=["backend"]
        )
        assert question.category == "Technical"
        assert len(question.applies_to) == 2

    def test_cub_config_full(self):
        """Test full CubConfig with nested models."""
        config = CubConfig(
            harness=HarnessConfig(name="claude"),
            budget=BudgetConfig(max_tokens_per_task=500000),
            state=StateConfig(require_clean=True, run_tests=True),
            loop=LoopConfig(max_iterations=50)
        )
        assert config.harness.name == "claude"
        assert config.budget.max_tokens_per_task == 500000
        assert config.state.require_clean is True
        assert config.loop.max_iterations == 50

    def test_parse_cub_json(self):
        """Test parsing actual .cub.json structure."""
        cub_json = {
            "harness": "claude",
            "budget": {
                "max_tokens_per_task": 500000,
                "max_tasks_per_session": None,
                "max_total_cost": None
            },
            "state": {
                "require_clean": True,
                "run_tests": True,
                "run_typecheck": False,
                "run_lint": False
            },
            "loop": {
                "max_iterations": 100,
                "on_task_failure": "stop"
            },
            "hooks": {
                "enabled": True,
                "fail_fast": False
            },
            "interview": {
                "custom_questions": []
            }
        }
        config = CubConfig(**cub_json)
        assert config.state.require_clean is True
        assert config.loop.max_iterations == 100


# ==============================================================================
# Status Model Tests
# ==============================================================================


class TestStatusModels:
    """Test status/dashboard models."""

    def test_event_log_creation(self):
        """Test EventLog model."""
        event = EventLog(
            message="Task started",
            level=EventLevel.INFO,
            task_id="cub-001"
        )
        assert event.message == "Task started"
        assert event.level == EventLevel.INFO
        assert event.task_id == "cub-001"
        assert isinstance(event.timestamp, datetime)

    def test_iteration_info_computed_fields(self):
        """Test IterationInfo computed fields."""
        info = IterationInfo(current=40, max=50)
        assert info.percentage == 80.0
        assert info.is_near_limit is True

        info2 = IterationInfo(current=10, max=50)
        assert info2.percentage == 20.0
        assert info2.is_near_limit is False

    def test_budget_status_computed_fields(self):
        """Test BudgetStatus computed properties."""
        budget = BudgetStatus(
            tokens_used=100000,
            tokens_limit=200000,
            cost_usd=2.5,
            cost_limit=10.0,
            tasks_completed=3,
            tasks_limit=5
        )
        assert budget.tokens_percentage == 50.0
        assert budget.cost_percentage == 25.0
        assert budget.tasks_percentage == 60.0
        assert budget.is_over_budget is False

    def test_budget_status_over_budget(self):
        """Test budget over-limit detection."""
        # Over token limit
        budget1 = BudgetStatus(
            tokens_used=250000,
            tokens_limit=200000
        )
        assert budget1.is_over_budget is True

        # Over cost limit
        budget2 = BudgetStatus(
            cost_usd=15.0,
            cost_limit=10.0
        )
        assert budget2.is_over_budget is True

    def test_budget_status_no_limits(self):
        """Test budget with no limits set."""
        budget = BudgetStatus(tokens_used=100000, cost_usd=5.0)
        assert budget.tokens_percentage is None
        assert budget.cost_percentage is None
        assert budget.is_over_budget is False

    def test_run_status_creation(self):
        """Test RunStatus model creation."""
        status = RunStatus(
            run_id="test-run-001",
            session_name="camel",
            phase=RunPhase.RUNNING,
            current_task_id="cub-001",
            current_task_title="Test task"
        )
        assert status.run_id == "test-run-001"
        assert status.phase == RunPhase.RUNNING
        assert status.is_active is True
        assert status.is_finished is False

    def test_run_status_computed_fields(self):
        """Test RunStatus computed fields."""
        status = RunStatus(
            run_id="test-001",
            tasks_total=10,
            tasks_closed=6,
            tasks_open=3,
            tasks_in_progress=1
        )
        assert status.tasks_remaining == 4
        assert status.completion_percentage == 60.0

    def test_run_status_methods(self):
        """Test RunStatus state transition methods."""
        status = RunStatus(run_id="test-001", phase=RunPhase.RUNNING)

        # Add event
        status.add_event("Task started", task_id="cub-001")
        assert len(status.events) == 1
        assert status.events[0].message == "Task started"

        # Mark completed
        status.mark_completed()
        assert status.phase == RunPhase.COMPLETED
        assert status.completed_at is not None
        assert status.is_finished is True

        # Mark failed
        status2 = RunStatus(run_id="test-002", phase=RunPhase.RUNNING)
        status2.mark_failed("Something went wrong")
        assert status2.phase == RunPhase.FAILED
        assert status2.last_error == "Something went wrong"

    def test_run_status_serialization(self):
        """Test RunStatus can be serialized to JSON."""
        status = RunStatus(
            run_id="test-001",
            current_task_id="cub-001",
            phase=RunPhase.RUNNING
        )
        status.add_event("Test event")

        # Serialize to JSON
        json_str = status.model_dump_json()
        assert json_str is not None

        # Deserialize back
        data = json.loads(json_str)
        assert data["run_id"] == "test-001"
        assert data["phase"] == "running"


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestModelIntegration:
    """Test interactions between different models."""

    def test_task_to_json_and_back(self):
        """Test task serialization round-trip."""
        original = Task(
            id="cub-001",
            title="Test task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P1,
            labels=["bug", "model:sonnet"],
            depends_on=["cub-000"]
        )

        # Serialize to dict
        task_dict = original.model_dump()

        # Deserialize back
        restored = Task(**task_dict)

        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.status == original.status
        assert restored.priority == original.priority
        assert restored.model_label == "sonnet"

    def test_config_to_json_and_back(self):
        """Test config serialization round-trip."""
        original = CubConfig(
            budget=BudgetConfig(max_tokens_per_task=500000),
            state=StateConfig(require_clean=True)
        )

        # Serialize to JSON string
        json_str = original.model_dump_json()

        # Deserialize back
        data = json.loads(json_str)
        restored = CubConfig(**data)

        assert restored.budget.max_tokens_per_task == 500000
        assert restored.state.require_clean is True
