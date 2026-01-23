"""
Integration tests for run.py token usage persistence.

Tests that token usage data is correctly persisted to task.json
after task execution in the run loop.
"""

from datetime import datetime

import pytest

from cub.core.harness.models import HarnessResult, TokenUsage
from cub.core.status.models import TaskArtifact
from cub.core.status.writer import StatusWriter
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with required structure."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create .cub directory structure
    cub_dir = project_dir / ".cub"
    cub_dir.mkdir()

    return project_dir


@pytest.fixture
def mock_task():
    """Provide a sample Task for testing."""
    return Task(
        id="test-task-001",
        title="Test task for token persistence",
        description="Test task description",
        status=TaskStatus.OPEN,
        priority=TaskPriority.P1,
        type=TaskType.TASK,
    )


def test_task_artifact_creation_with_usage(temp_project_dir, mock_task):
    """Test that TaskArtifact can be created with token usage from HarnessResult."""
    # Simulate a harness result with token usage
    result = HarnessResult(
        output="Task completed successfully",
        usage=TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=200,
            cache_creation_tokens=100,
            cost_usd=0.0275,
            estimated=False,
        ),
        duration_seconds=2.5,
        exit_code=0,
    )

    # Create a TaskArtifact from the result (simulating what run.py does)
    priority_str = (
        mock_task.priority.value
        if hasattr(mock_task.priority, "value")
        else str(mock_task.priority)
    )
    task_artifact = TaskArtifact(
        task_id=mock_task.id,
        title=mock_task.title,
        priority=priority_str,
        status="completed",
        started_at=datetime.now(),
        completed_at=datetime.now(),
        iterations=1,
        exit_code=result.exit_code,
        usage=result.usage,
        duration_seconds=result.duration_seconds,
    )

    # Initialize status writer
    status_writer = StatusWriter(temp_project_dir, "test-run-001")

    # Write task artifact
    status_writer.write_task_artifact(mock_task.id, task_artifact)

    # Verify task artifact was written
    task_artifact_path = status_writer.get_task_dir(mock_task.id) / "task.json"
    assert task_artifact_path.exists(), "task.json should exist"

    # Read and verify the task artifact
    artifact = status_writer.read_task_artifact(mock_task.id)
    assert artifact is not None, "Should be able to read task artifact"
    assert artifact.task_id == mock_task.id
    assert artifact.status == "completed"
    assert artifact.usage is not None, "Usage data should be present"
    assert artifact.usage.input_tokens == 1000
    assert artifact.usage.output_tokens == 500
    assert artifact.usage.cache_read_tokens == 200
    assert artifact.usage.cache_creation_tokens == 100
    assert artifact.usage.cost_usd == 0.0275
    assert artifact.usage.total_tokens == 1500
    assert artifact.duration_seconds == 2.5


def test_task_artifact_creation_with_failure(temp_project_dir, mock_task):
    """Test that TaskArtifact can be created with token usage even on failure."""
    # Simulate a failed harness result with token usage
    result = HarnessResult(
        output="Task failed with error",
        usage=TokenUsage(
            input_tokens=800,
            output_tokens=300,
            cost_usd=0.0165,
            estimated=False,
        ),
        duration_seconds=1.2,
        exit_code=1,
        error="Simulated task failure",
    )

    # Create a TaskArtifact from the result (simulating what run.py does)
    priority_str = (
        mock_task.priority.value
        if hasattr(mock_task.priority, "value")
        else str(mock_task.priority)
    )
    task_artifact = TaskArtifact(
        task_id=mock_task.id,
        title=mock_task.title,
        priority=priority_str,
        status="failed",
        started_at=datetime.now(),
        completed_at=datetime.now(),
        iterations=1,
        exit_code=result.exit_code,
        usage=result.usage,
        duration_seconds=result.duration_seconds,
    )

    # Initialize status writer
    status_writer = StatusWriter(temp_project_dir, "test-run-002")

    # Write task artifact
    status_writer.write_task_artifact(mock_task.id, task_artifact)

    # Verify task artifact was written
    task_artifact_path = status_writer.get_task_dir(mock_task.id) / "task.json"
    assert task_artifact_path.exists(), "task.json should exist even on failure"

    # Read and verify the task artifact
    artifact = status_writer.read_task_artifact(mock_task.id)
    assert artifact is not None, "Should be able to read task artifact"
    assert artifact.task_id == mock_task.id
    assert artifact.status == "failed"
    assert artifact.usage is not None, "Usage data should be present even on failure"
    assert artifact.usage.input_tokens == 800
    assert artifact.usage.output_tokens == 300
    assert artifact.usage.cost_usd == 0.0165
    assert artifact.usage.total_tokens == 1100
    assert artifact.duration_seconds == 1.2
    assert artifact.exit_code == 1


def test_task_artifact_fields(temp_project_dir):
    """Test that TaskArtifact correctly handles all fields including TokenUsage."""
    # Create a task artifact with full token usage
    usage = TokenUsage(
        input_tokens=1500,
        output_tokens=750,
        cache_read_tokens=300,
        cache_creation_tokens=150,
        cost_usd=0.0412,
        estimated=False,
    )

    artifact = TaskArtifact(
        task_id="test-artifact-001",
        title="Test artifact",
        priority="high",
        status="completed",
        started_at=datetime.now(),
        completed_at=datetime.now(),
        iterations=1,
        exit_code=0,
        usage=usage,
        duration_seconds=3.5,
    )

    # Write to disk
    status_writer = StatusWriter(temp_project_dir, "test-run")
    status_writer.write_task_artifact("test-artifact-001", artifact)

    # Read back and verify
    read_artifact = status_writer.read_task_artifact("test-artifact-001")
    assert read_artifact is not None
    assert read_artifact.task_id == "test-artifact-001"
    assert read_artifact.usage is not None
    assert read_artifact.usage.input_tokens == 1500
    assert read_artifact.usage.output_tokens == 750
    assert read_artifact.usage.cache_read_tokens == 300
    assert read_artifact.usage.cache_creation_tokens == 150
    assert read_artifact.usage.cost_usd == 0.0412
    assert read_artifact.usage.total_tokens == 2250
    assert read_artifact.usage.effective_input_tokens == 1200  # 1500 - 300


def test_task_artifact_persistence_to_json(temp_project_dir):
    """Test that TaskArtifact serializes correctly to JSON with all nested fields."""
    import json

    # Create a task artifact with token usage
    usage = TokenUsage(
        input_tokens=2000,
        output_tokens=1000,
        cache_read_tokens=400,
        cache_creation_tokens=200,
        cost_usd=0.055,
        estimated=False,
    )

    artifact = TaskArtifact(
        task_id="test-json-001",
        title="JSON serialization test",
        priority="critical",
        status="completed",
        started_at=datetime(2026, 1, 22, 10, 0, 0),
        completed_at=datetime(2026, 1, 22, 10, 5, 30),
        iterations=2,
        exit_code=0,
        usage=usage,
        duration_seconds=330.5,
    )

    # Write to disk
    status_writer = StatusWriter(temp_project_dir, "test-run-json")
    status_writer.write_task_artifact("test-json-001", artifact)

    # Read the raw JSON file to verify structure
    task_json_path = status_writer.get_task_dir("test-json-001") / "task.json"
    with open(task_json_path) as f:
        json_data = json.load(f)

    # Verify top-level fields
    assert json_data["task_id"] == "test-json-001"
    assert json_data["title"] == "JSON serialization test"
    assert json_data["priority"] == "critical"
    assert json_data["status"] == "completed"
    assert json_data["iterations"] == 2
    assert json_data["exit_code"] == 0
    assert json_data["duration_seconds"] == 330.5

    # Verify nested usage object
    assert "usage" in json_data
    assert json_data["usage"]["input_tokens"] == 2000
    assert json_data["usage"]["output_tokens"] == 1000
    assert json_data["usage"]["cache_read_tokens"] == 400
    assert json_data["usage"]["cache_creation_tokens"] == 200
    assert json_data["usage"]["cost_usd"] == 0.055
    assert json_data["usage"]["estimated"] is False
