"""
Tests for status models module.

Tests the TaskArtifact model and related status models.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from cub.core.harness.models import TokenUsage
from cub.core.status.models import BudgetStatus, RunArtifact, TaskArtifact


class TestTaskArtifact:
    """Tests for TaskArtifact model."""

    def test_minimal_creation(self):
        """Test TaskArtifact with only required fields."""
        artifact = TaskArtifact(task_id="cub-001")

        assert artifact.task_id == "cub-001"
        assert artifact.title == ""
        assert artifact.priority == "normal"
        assert artifact.status == "in_progress"
        assert artifact.started_at is None
        assert artifact.completed_at is None
        assert artifact.iterations == 0
        assert artifact.exit_code is None
        assert artifact.usage is None
        assert artifact.duration_seconds is None

    def test_full_creation(self):
        """Test TaskArtifact with all fields populated."""
        started = datetime(2026, 1, 15, 10, 0, 0)
        completed = datetime(2026, 1, 15, 10, 5, 30)
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=200,
            cache_creation_tokens=100,
            cost_usd=0.05,
        )

        artifact = TaskArtifact(
            task_id="cub-123",
            title="Implement feature X",
            priority="high",
            status="completed",
            started_at=started,
            completed_at=completed,
            iterations=3,
            exit_code=0,
            usage=usage,
            duration_seconds=330.5,
        )

        assert artifact.task_id == "cub-123"
        assert artifact.title == "Implement feature X"
        assert artifact.priority == "high"
        assert artifact.status == "completed"
        assert artifact.started_at == started
        assert artifact.completed_at == completed
        assert artifact.iterations == 3
        assert artifact.exit_code == 0
        assert artifact.usage == usage
        assert artifact.duration_seconds == 330.5

    def test_usage_field_with_token_usage(self):
        """Test usage field accepts TokenUsage model."""
        usage = TokenUsage(
            input_tokens=2000,
            output_tokens=1000,
            cache_read_tokens=500,
            cache_creation_tokens=250,
            cost_usd=0.15,
            estimated=False,
        )

        artifact = TaskArtifact(
            task_id="cub-456",
            usage=usage,
        )

        assert artifact.usage is not None
        assert artifact.usage.input_tokens == 2000
        assert artifact.usage.output_tokens == 1000
        assert artifact.usage.cache_read_tokens == 500
        assert artifact.usage.cache_creation_tokens == 250
        assert artifact.usage.cost_usd == 0.15
        assert artifact.usage.estimated is False

    def test_usage_field_none(self):
        """Test usage field can be None."""
        artifact = TaskArtifact(task_id="cub-789")

        assert artifact.usage is None

    def test_iterations_defaults_to_zero(self):
        """Test iterations field defaults to 0."""
        artifact = TaskArtifact(task_id="cub-001")

        assert artifact.iterations == 0

    def test_iterations_validation_non_negative(self):
        """Test iterations must be non-negative."""
        # Valid: zero iterations
        artifact = TaskArtifact(task_id="cub-001", iterations=0)
        assert artifact.iterations == 0

        # Valid: positive iterations
        artifact = TaskArtifact(task_id="cub-002", iterations=5)
        assert artifact.iterations == 5

        # Invalid: negative iterations
        with pytest.raises(ValidationError) as exc_info:
            TaskArtifact(task_id="cub-003", iterations=-1)

        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_duration_seconds_validation_non_negative(self):
        """Test duration_seconds must be non-negative."""
        # Valid: zero duration
        artifact = TaskArtifact(task_id="cub-001", duration_seconds=0.0)
        assert artifact.duration_seconds == 0.0

        # Valid: positive duration
        artifact = TaskArtifact(task_id="cub-002", duration_seconds=123.45)
        assert artifact.duration_seconds == 123.45

        # Invalid: negative duration
        with pytest.raises(ValidationError) as exc_info:
            TaskArtifact(task_id="cub-003", duration_seconds=-1.5)

        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_duration_seconds_none(self):
        """Test duration_seconds can be None."""
        artifact = TaskArtifact(task_id="cub-001")

        assert artifact.duration_seconds is None

    def test_exit_code_validation(self):
        """Test exit_code accepts various integer values."""
        # Success exit code
        artifact = TaskArtifact(task_id="cub-001", exit_code=0)
        assert artifact.exit_code == 0

        # Failure exit code
        artifact = TaskArtifact(task_id="cub-002", exit_code=1)
        assert artifact.exit_code == 1

        # High exit code
        artifact = TaskArtifact(task_id="cub-003", exit_code=255)
        assert artifact.exit_code == 255

        # None exit code (task not completed)
        artifact = TaskArtifact(task_id="cub-004")
        assert artifact.exit_code is None

    def test_task_id_required(self):
        """Test task_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            TaskArtifact()

        assert "task_id" in str(exc_info.value).lower()
        assert "required" in str(exc_info.value).lower()

    def test_serialization_to_dict(self):
        """Test TaskArtifact serialization to dict."""
        started = datetime(2026, 1, 15, 10, 0, 0)
        usage = TokenUsage(input_tokens=1000, output_tokens=500, cost_usd=0.05)

        artifact = TaskArtifact(
            task_id="cub-999",
            title="Test task",
            status="completed",
            started_at=started,
            iterations=2,
            exit_code=0,
            usage=usage,
            duration_seconds=60.0,
        )

        data = artifact.model_dump()

        assert data["task_id"] == "cub-999"
        assert data["title"] == "Test task"
        assert data["status"] == "completed"
        assert data["started_at"] == started
        assert data["iterations"] == 2
        assert data["exit_code"] == 0
        assert data["duration_seconds"] == 60.0
        assert isinstance(data["usage"], dict)
        assert data["usage"]["input_tokens"] == 1000
        assert data["usage"]["output_tokens"] == 500
        assert data["usage"]["cost_usd"] == 0.05

    def test_serialization_to_json(self):
        """Test TaskArtifact serialization to JSON."""
        started = datetime(2026, 1, 15, 10, 0, 0)
        usage = TokenUsage(input_tokens=1000, output_tokens=500, cost_usd=0.05)

        artifact = TaskArtifact(
            task_id="cub-888",
            title="JSON test",
            started_at=started,
            usage=usage,
        )

        json_str = artifact.model_dump_json()

        assert "cub-888" in json_str
        assert "JSON test" in json_str
        assert "2026-01-15" in json_str
        assert "1000" in json_str  # input_tokens

    def test_deserialization_from_dict(self):
        """Test TaskArtifact deserialization from dict."""
        data = {
            "task_id": "cub-777",
            "title": "Deserialized task",
            "priority": "low",
            "status": "failed",
            "started_at": "2026-01-15T10:00:00",
            "completed_at": "2026-01-15T10:30:00",
            "iterations": 1,
            "exit_code": 1,
            "usage": {
                "input_tokens": 500,
                "output_tokens": 250,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "cost_usd": 0.025,
                "estimated": False,
            },
            "duration_seconds": 1800.0,
        }

        artifact = TaskArtifact(**data)

        assert artifact.task_id == "cub-777"
        assert artifact.title == "Deserialized task"
        assert artifact.priority == "low"
        assert artifact.status == "failed"
        assert artifact.iterations == 1
        assert artifact.exit_code == 1
        assert artifact.duration_seconds == 1800.0
        assert artifact.usage is not None
        assert artifact.usage.input_tokens == 500
        assert artifact.usage.cost_usd == 0.025

    def test_deserialization_minimal_dict(self):
        """Test TaskArtifact deserialization with minimal data."""
        data = {"task_id": "cub-minimal"}

        artifact = TaskArtifact(**data)

        assert artifact.task_id == "cub-minimal"
        assert artifact.title == ""
        assert artifact.priority == "normal"
        assert artifact.status == "in_progress"
        assert artifact.iterations == 0
        assert artifact.usage is None

    def test_validate_assignment(self):
        """Test validate_assignment is enabled via model_config."""
        artifact = TaskArtifact(task_id="cub-001", iterations=0)

        # Valid assignment
        artifact.iterations = 5
        assert artifact.iterations == 5

        # Invalid assignment should raise ValidationError
        with pytest.raises(ValidationError):
            artifact.iterations = -1

    def test_datetime_fields(self):
        """Test datetime fields accept datetime objects."""
        started = datetime(2026, 1, 15, 9, 0, 0)
        completed = datetime(2026, 1, 15, 9, 30, 0)

        artifact = TaskArtifact(
            task_id="cub-time",
            started_at=started,
            completed_at=completed,
        )

        assert artifact.started_at == started
        assert artifact.completed_at == completed

    def test_datetime_fields_none(self):
        """Test datetime fields can be None."""
        artifact = TaskArtifact(task_id="cub-no-time")

        assert artifact.started_at is None
        assert artifact.completed_at is None

    def test_usage_with_all_fields(self):
        """Test usage field with all TokenUsage fields populated."""
        usage = TokenUsage(
            input_tokens=5000,
            output_tokens=2500,
            cache_read_tokens=1000,
            cache_creation_tokens=500,
            cost_usd=0.25,
            estimated=True,
        )

        artifact = TaskArtifact(task_id="cub-full-usage", usage=usage)

        assert artifact.usage.input_tokens == 5000
        assert artifact.usage.output_tokens == 2500
        assert artifact.usage.cache_read_tokens == 1000
        assert artifact.usage.cache_creation_tokens == 500
        assert artifact.usage.cost_usd == 0.25
        assert artifact.usage.estimated is True

    def test_priority_accepts_string_values(self):
        """Test priority field accepts various string values."""
        # Common priority values
        for priority in ["low", "normal", "high", "critical"]:
            artifact = TaskArtifact(task_id=f"cub-{priority}", priority=priority)
            assert artifact.priority == priority

    def test_status_accepts_string_values(self):
        """Test status field accepts various string values."""
        # Common status values
        for status in ["in_progress", "completed", "failed", "blocked"]:
            artifact = TaskArtifact(task_id=f"cub-{status}", status=status)
            assert artifact.status == status

    def test_realistic_workflow(self):
        """Test realistic task workflow: start -> execute -> complete."""
        # Task starts
        artifact = TaskArtifact(
            task_id="cub-workflow",
            title="Complete end-to-end feature",
            priority="high",
            status="in_progress",
            started_at=datetime(2026, 1, 15, 10, 0, 0),
            iterations=0,
        )

        assert artifact.status == "in_progress"
        assert artifact.exit_code is None
        assert artifact.completed_at is None

        # Task completes successfully
        artifact.status = "completed"
        artifact.completed_at = datetime(2026, 1, 15, 10, 30, 0)
        artifact.exit_code = 0
        artifact.iterations = 1
        artifact.usage = TokenUsage(
            input_tokens=10000,
            output_tokens=5000,
            cache_read_tokens=2000,
            cache_creation_tokens=1000,
            cost_usd=0.75,
        )
        artifact.duration_seconds = 1800.0

        assert artifact.status == "completed"
        assert artifact.exit_code == 0
        assert artifact.iterations == 1
        assert artifact.usage.cost_usd == 0.75
        assert artifact.duration_seconds == 1800.0


class TestRunArtifact:
    """Tests for RunArtifact model."""

    def test_minimal_creation(self):
        """Test RunArtifact with only required fields."""
        artifact = RunArtifact(run_id="camel-20260114-231701")

        assert artifact.run_id == "camel-20260114-231701"
        assert artifact.session_name == "default"
        assert artifact.started_at is not None
        assert artifact.completed_at is None
        assert artifact.status == "in_progress"
        assert artifact.config == {}
        assert artifact.tasks_completed == 0
        assert artifact.tasks_failed == 0
        assert artifact.budget is None

    def test_full_creation(self):
        """Test RunArtifact with all fields populated."""
        started = datetime(2026, 1, 15, 10, 0, 0)
        completed = datetime(2026, 1, 15, 12, 0, 0)
        budget = BudgetStatus(
            tokens_used=50000,
            tokens_limit=100000,
            cost_usd=5.50,
            cost_limit=10.0,
            tasks_completed=5,
            tasks_limit=10,
        )
        config = {
            "guardrails": {
                "max_task_iterations": 3,
                "max_run_iterations": 50,
            }
        }

        artifact = RunArtifact(
            run_id="camel-20260114-231701",
            session_name="camel",
            started_at=started,
            completed_at=completed,
            status="completed",
            config=config,
            tasks_completed=5,
            tasks_failed=1,
            budget=budget,
        )

        assert artifact.run_id == "camel-20260114-231701"
        assert artifact.session_name == "camel"
        assert artifact.started_at == started
        assert artifact.completed_at == completed
        assert artifact.status == "completed"
        assert artifact.config == config
        assert artifact.tasks_completed == 5
        assert artifact.tasks_failed == 1
        assert artifact.budget == budget

    def test_budget_field_with_budget_status(self):
        """Test budget field accepts BudgetStatus model."""
        budget = BudgetStatus(
            tokens_used=25000,
            tokens_limit=50000,
            cost_usd=2.75,
            cost_limit=5.0,
            tasks_completed=3,
            tasks_limit=5,
        )

        artifact = RunArtifact(
            run_id="test-run-001",
            budget=budget,
        )

        assert artifact.budget is not None
        assert artifact.budget.tokens_used == 25000
        assert artifact.budget.tokens_limit == 50000
        assert artifact.budget.cost_usd == 2.75
        assert artifact.budget.cost_limit == 5.0
        assert artifact.budget.tasks_completed == 3
        assert artifact.budget.tasks_limit == 5

    def test_budget_field_none(self):
        """Test budget field can be None."""
        artifact = RunArtifact(run_id="test-run-002")

        assert artifact.budget is None

    def test_tasks_completed_defaults_to_zero(self):
        """Test tasks_completed field defaults to 0."""
        artifact = RunArtifact(run_id="test-run-003")

        assert artifact.tasks_completed == 0

    def test_tasks_failed_defaults_to_zero(self):
        """Test tasks_failed field defaults to 0."""
        artifact = RunArtifact(run_id="test-run-004")

        assert artifact.tasks_failed == 0

    def test_tasks_completed_validation_non_negative(self):
        """Test tasks_completed must be non-negative."""
        # Valid: zero tasks
        artifact = RunArtifact(run_id="test-run-005", tasks_completed=0)
        assert artifact.tasks_completed == 0

        # Valid: positive tasks
        artifact = RunArtifact(run_id="test-run-006", tasks_completed=10)
        assert artifact.tasks_completed == 10

        # Invalid: negative tasks
        with pytest.raises(ValidationError) as exc_info:
            RunArtifact(run_id="test-run-007", tasks_completed=-1)

        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_tasks_failed_validation_non_negative(self):
        """Test tasks_failed must be non-negative."""
        # Valid: zero tasks
        artifact = RunArtifact(run_id="test-run-008", tasks_failed=0)
        assert artifact.tasks_failed == 0

        # Valid: positive tasks
        artifact = RunArtifact(run_id="test-run-009", tasks_failed=3)
        assert artifact.tasks_failed == 3

        # Invalid: negative tasks
        with pytest.raises(ValidationError) as exc_info:
            RunArtifact(run_id="test-run-010", tasks_failed=-1)

        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_run_id_required(self):
        """Test run_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            RunArtifact()

        assert "run_id" in str(exc_info.value).lower()
        assert "required" in str(exc_info.value).lower()

    def test_serialization_to_dict(self):
        """Test RunArtifact serialization to dict."""
        started = datetime(2026, 1, 15, 10, 0, 0)
        budget = BudgetStatus(
            tokens_used=10000,
            cost_usd=1.25,
            tasks_completed=2,
        )
        config = {"test": "value"}

        artifact = RunArtifact(
            run_id="test-run-serialize",
            session_name="test-session",
            started_at=started,
            status="completed",
            config=config,
            tasks_completed=2,
            budget=budget,
        )

        data = artifact.model_dump()

        assert data["run_id"] == "test-run-serialize"
        assert data["session_name"] == "test-session"
        assert data["started_at"] == started
        assert data["status"] == "completed"
        assert data["config"] == config
        assert data["tasks_completed"] == 2
        assert isinstance(data["budget"], dict)
        assert data["budget"]["tokens_used"] == 10000
        assert data["budget"]["cost_usd"] == 1.25

    def test_serialization_to_json(self):
        """Test RunArtifact serialization to JSON."""
        started = datetime(2026, 1, 15, 10, 0, 0)
        budget = BudgetStatus(tokens_used=5000, cost_usd=0.50)

        artifact = RunArtifact(
            run_id="test-run-json",
            session_name="json-test",
            started_at=started,
            budget=budget,
        )

        json_str = artifact.model_dump_json()

        assert "test-run-json" in json_str
        assert "json-test" in json_str
        assert "2026-01-15" in json_str
        assert "5000" in json_str  # tokens_used

    def test_deserialization_from_dict(self):
        """Test RunArtifact deserialization from dict."""
        data = {
            "run_id": "test-run-deserialize",
            "session_name": "deser-session",
            "started_at": "2026-01-15T10:00:00",
            "completed_at": "2026-01-15T12:00:00",
            "status": "completed",
            "config": {"key": "value"},
            "tasks_completed": 8,
            "tasks_failed": 2,
            "budget": {
                "tokens_used": 30000,
                "tokens_limit": 50000,
                "cost_usd": 3.50,
                "cost_limit": 5.0,
                "tasks_completed": 8,
                "tasks_limit": 10,
            },
        }

        artifact = RunArtifact(**data)

        assert artifact.run_id == "test-run-deserialize"
        assert artifact.session_name == "deser-session"
        assert artifact.status == "completed"
        assert artifact.config == {"key": "value"}
        assert artifact.tasks_completed == 8
        assert artifact.tasks_failed == 2
        assert artifact.budget is not None
        assert artifact.budget.tokens_used == 30000
        assert artifact.budget.cost_usd == 3.50

    def test_deserialization_minimal_dict(self):
        """Test RunArtifact deserialization with minimal data."""
        data = {"run_id": "minimal-run"}

        artifact = RunArtifact(**data)

        assert artifact.run_id == "minimal-run"
        assert artifact.session_name == "default"
        assert artifact.status == "in_progress"
        assert artifact.config == {}
        assert artifact.tasks_completed == 0
        assert artifact.tasks_failed == 0
        assert artifact.budget is None

    def test_validate_assignment(self):
        """Test validate_assignment is enabled via model_config."""
        artifact = RunArtifact(run_id="test-validate", tasks_completed=0)

        # Valid assignment
        artifact.tasks_completed = 5
        assert artifact.tasks_completed == 5

        # Invalid assignment should raise ValidationError
        with pytest.raises(ValidationError):
            artifact.tasks_completed = -1

    def test_datetime_fields(self):
        """Test datetime fields accept datetime objects."""
        started = datetime(2026, 1, 15, 9, 0, 0)
        completed = datetime(2026, 1, 15, 10, 0, 0)

        artifact = RunArtifact(
            run_id="test-datetime",
            started_at=started,
            completed_at=completed,
        )

        assert artifact.started_at == started
        assert artifact.completed_at == completed

    def test_completed_at_field_none(self):
        """Test completed_at field can be None."""
        artifact = RunArtifact(run_id="test-no-complete-time")

        assert artifact.completed_at is None

    def test_status_accepts_string_values(self):
        """Test status field accepts various string values."""
        # Common status values
        for status in ["in_progress", "completed", "failed", "stopped"]:
            artifact = RunArtifact(run_id=f"test-{status}", status=status)
            assert artifact.status == status

    def test_config_with_nested_structure(self):
        """Test config field accepts nested dictionary structures."""
        config = {
            "guardrails": {
                "max_task_iterations": 3,
                "max_run_iterations": 50,
                "secret_patterns": ["api_key", "password"],
            },
            "review": {
                "plan_strict": False,
                "block_on_concerns": False,
            },
        }

        artifact = RunArtifact(run_id="test-config", config=config)

        assert artifact.config == config
        assert artifact.config["guardrails"]["max_task_iterations"] == 3
        assert len(artifact.config["guardrails"]["secret_patterns"]) == 2

    def test_realistic_workflow(self):
        """Test realistic run workflow: start -> execute -> complete."""
        # Run starts
        artifact = RunArtifact(
            run_id="camel-20260114-231701",
            session_name="camel",
            started_at=datetime(2026, 1, 15, 10, 0, 0),
            status="in_progress",
            config={"guardrails": {"max_task_iterations": 3}},
            tasks_completed=0,
            tasks_failed=0,
        )

        assert artifact.status == "in_progress"
        assert artifact.completed_at is None
        assert artifact.tasks_completed == 0

        # Run progresses
        artifact.tasks_completed = 5
        artifact.tasks_failed = 1
        artifact.budget = BudgetStatus(
            tokens_used=50000,
            tokens_limit=100000,
            cost_usd=5.50,
            cost_limit=10.0,
            tasks_completed=5,
            tasks_limit=10,
        )

        assert artifact.tasks_completed == 5
        assert artifact.tasks_failed == 1
        assert artifact.budget.cost_usd == 5.50

        # Run completes
        artifact.status = "completed"
        artifact.completed_at = datetime(2026, 1, 15, 12, 0, 0)

        assert artifact.status == "completed"
        assert artifact.completed_at is not None
        assert artifact.tasks_completed == 5
