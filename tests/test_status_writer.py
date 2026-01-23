"""
Tests for status writer module.

Tests StatusWriter, get_latest_status, and list_runs functions.
"""

import json
from datetime import datetime

import pytest

from cub.core.status.models import BudgetStatus, RunArtifact, RunPhase, RunStatus
from cub.core.status.writer import StatusWriter, get_latest_status, list_runs


class TestStatusWriter:
    """Tests for StatusWriter class."""

    def test_init_creates_run_directory(self, temp_dir):
        """Test StatusWriter creates .cub/runs/{run_id} directory."""
        writer = StatusWriter(temp_dir, "test-run-001")

        assert writer.run_dir.exists()
        assert writer.run_dir == temp_dir / ".cub" / "runs" / "test-run-001"
        assert writer.status_path == writer.run_dir / "status.json"

    def test_write_creates_status_file(self, temp_dir):
        """Test write() creates status.json file."""
        writer = StatusWriter(temp_dir, "test-run-001")
        status = RunStatus(
            run_id="test-run-001",
            session_name="test",
            phase=RunPhase.INITIALIZING,
            started_at=datetime.now(),
        )

        writer.write(status)

        assert writer.status_path.exists()

    def test_write_serializes_run_status(self, temp_dir):
        """Test write() serializes RunStatus to valid JSON."""
        writer = StatusWriter(temp_dir, "test-run-001")
        now = datetime.now()
        status = RunStatus(
            run_id="test-run-001",
            session_name="test-session",
            phase=RunPhase.RUNNING,
            started_at=now,
        )

        writer.write(status)

        # Read and verify JSON
        with writer.status_path.open() as f:
            data = json.load(f)

        assert data["run_id"] == "test-run-001"
        assert data["session_name"] == "test-session"
        assert data["phase"] == "running"

    def test_write_updates_timestamp(self, temp_dir):
        """Test write() updates the updated_at timestamp."""
        writer = StatusWriter(temp_dir, "test-run-001")
        status = RunStatus(
            run_id="test-run-001",
            session_name="test",
            phase=RunPhase.INITIALIZING,
            started_at=datetime.now(),
        )

        # First write
        writer.write(status)
        first_updated = status.updated_at

        # Second write (should update timestamp)
        import time

        time.sleep(0.01)  # Small delay to ensure different timestamp
        writer.write(status)
        second_updated = status.updated_at

        assert second_updated > first_updated

    def test_write_is_atomic(self, temp_dir):
        """Test write() uses atomic write (temp file + rename)."""
        writer = StatusWriter(temp_dir, "test-run-001")
        status = RunStatus(
            run_id="test-run-001",
            session_name="test",
            phase=RunPhase.INITIALIZING,
            started_at=datetime.now(),
        )

        writer.write(status)

        # Temp file should not exist after successful write
        temp_file = writer.status_path.with_suffix(".json.tmp")
        assert not temp_file.exists()

        # Status file should exist
        assert writer.status_path.exists()

    def test_write_with_task_info(self, temp_dir):
        """Test write() serializes task info correctly."""
        writer = StatusWriter(temp_dir, "test-run-001")
        status = RunStatus(
            run_id="test-run-001",
            session_name="test",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
            current_task_id="cub-001",
            current_task_title="Test task",
        )

        writer.write(status)

        # Read and verify task info
        with writer.status_path.open() as f:
            data = json.load(f)

        assert data["current_task_id"] == "cub-001"
        assert data["current_task_title"] == "Test task"

    def test_read_existing_status(self, temp_dir):
        """Test read() loads existing status.json."""
        writer = StatusWriter(temp_dir, "test-run-001")
        original_status = RunStatus(
            run_id="test-run-001",
            session_name="test-session",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )

        writer.write(original_status)
        loaded_status = writer.read()

        assert loaded_status is not None
        assert loaded_status.run_id == "test-run-001"
        assert loaded_status.session_name == "test-session"
        assert loaded_status.phase == RunPhase.RUNNING

    def test_read_nonexistent_status(self, temp_dir):
        """Test read() returns None when status.json doesn't exist."""
        writer = StatusWriter(temp_dir, "test-run-001")

        status = writer.read()

        assert status is None

    def test_read_invalid_json(self, temp_dir):
        """Test read() returns None for invalid JSON."""
        writer = StatusWriter(temp_dir, "test-run-001")
        writer.run_dir.mkdir(parents=True, exist_ok=True)

        # Write invalid JSON
        writer.status_path.write_text("{ invalid json }")

        status = writer.read()

        assert status is None

    def test_read_incomplete_data(self, temp_dir):
        """Test read() uses defaults for missing optional fields."""
        writer = StatusWriter(temp_dir, "test-run-001")
        writer.run_dir.mkdir(parents=True, exist_ok=True)

        # Write JSON with only run_id (other fields use defaults)
        writer.status_path.write_text('{"run_id": "test-001"}')

        status = writer.read()

        # Should load with defaults
        assert status is not None
        assert status.run_id == "test-001"
        assert status.session_name == "default"
        assert status.phase == RunPhase.INITIALIZING

    def test_json_serializer_datetime(self, temp_dir):
        """Test _json_serializer handles datetime objects."""
        writer = StatusWriter(temp_dir, "test-run-001")
        now = datetime(2026, 1, 15, 12, 30, 45)

        result = writer._json_serializer(now)

        assert result == "2026-01-15T12:30:45"

    def test_json_serializer_enum(self, temp_dir):
        """Test _json_serializer handles enum objects."""
        writer = StatusWriter(temp_dir, "test-run-001")

        result = writer._json_serializer(RunPhase.RUNNING)

        assert result == "running"

    def test_json_serializer_unsupported_type(self, temp_dir):
        """Test _json_serializer raises TypeError for unsupported types."""
        writer = StatusWriter(temp_dir, "test-run-001")

        with pytest.raises(TypeError, match="not JSON serializable"):
            writer._json_serializer(object())

    def test_write_run_artifact_creates_file(self, temp_dir):
        """Test write_run_artifact() creates run.json file."""
        writer = StatusWriter(temp_dir, "test-run-001")
        now = datetime.now()
        artifact = RunArtifact(
            run_id="test-run-001",
            session_name="test-session",
            started_at=now,
            completed_at=now,
            status="completed",
            budget=BudgetStatus(tokens_used=1000, cost_usd=0.05, tasks_completed=3),
        )

        writer.write_run_artifact(artifact)

        assert writer.run_artifact_path.exists()

    def test_write_run_artifact_serializes_correctly(self, temp_dir):
        """Test write_run_artifact() serializes RunArtifact to valid JSON."""
        writer = StatusWriter(temp_dir, "test-run-001")
        now = datetime.now()
        artifact = RunArtifact(
            run_id="test-run-001",
            session_name="test-session",
            started_at=now,
            completed_at=now,
            status="completed",
            config={"test": "value"},
            tasks_completed=5,
            tasks_failed=1,
            budget=BudgetStatus(
                tokens_used=2000,
                tokens_limit=10000,
                cost_usd=0.10,
                cost_limit=1.0,
                tasks_completed=5,
                tasks_limit=10,
            ),
        )

        writer.write_run_artifact(artifact)

        # Read and verify JSON
        with writer.run_artifact_path.open() as f:
            data = json.load(f)

        assert data["run_id"] == "test-run-001"
        assert data["session_name"] == "test-session"
        assert data["status"] == "completed"
        assert data["tasks_completed"] == 5
        assert data["tasks_failed"] == 1
        assert data["config"]["test"] == "value"
        assert data["budget"]["tokens_used"] == 2000
        assert data["budget"]["cost_usd"] == 0.10
        assert data["budget"]["tasks_completed"] == 5

    def test_write_run_artifact_is_atomic(self, temp_dir):
        """Test write_run_artifact() uses atomic write (temp file + rename)."""
        writer = StatusWriter(temp_dir, "test-run-001")
        artifact = RunArtifact(
            run_id="test-run-001",
            session_name="test",
            started_at=datetime.now(),
            status="in_progress",
        )

        writer.write_run_artifact(artifact)

        # Temp file should not exist after successful write
        temp_file = writer.run_artifact_path.with_suffix(".json.tmp")
        assert not temp_file.exists()

        # Run artifact file should exist
        assert writer.run_artifact_path.exists()

    def test_read_run_artifact_existing(self, temp_dir):
        """Test read_run_artifact() loads existing run.json."""
        writer = StatusWriter(temp_dir, "test-run-001")
        now = datetime.now()
        original_artifact = RunArtifact(
            run_id="test-run-001",
            session_name="test-session",
            started_at=now,
            completed_at=now,
            status="completed",
            budget=BudgetStatus(tokens_used=1500, cost_usd=0.08, tasks_completed=4),
        )

        writer.write_run_artifact(original_artifact)
        loaded_artifact = writer.read_run_artifact()

        assert loaded_artifact is not None
        assert loaded_artifact.run_id == "test-run-001"
        assert loaded_artifact.session_name == "test-session"
        assert loaded_artifact.status == "completed"
        assert loaded_artifact.budget is not None
        assert loaded_artifact.budget.tokens_used == 1500
        assert loaded_artifact.budget.tasks_completed == 4

    def test_read_run_artifact_nonexistent(self, temp_dir):
        """Test read_run_artifact() returns None when run.json doesn't exist."""
        writer = StatusWriter(temp_dir, "test-run-001")

        artifact = writer.read_run_artifact()

        assert artifact is None

    def test_read_run_artifact_invalid_json(self, temp_dir):
        """Test read_run_artifact() returns None for invalid JSON."""
        writer = StatusWriter(temp_dir, "test-run-001")
        writer.run_dir.mkdir(parents=True, exist_ok=True)

        # Write invalid JSON
        writer.run_artifact_path.write_text("{ invalid json }")

        artifact = writer.read_run_artifact()

        assert artifact is None


class TestGetLatestStatus:
    """Tests for get_latest_status function."""

    def test_get_latest_status_no_runs(self, temp_dir):
        """Test get_latest_status returns None when no runs exist."""
        status = get_latest_status(temp_dir)

        assert status is None

    def test_get_latest_status_no_runs_dir(self, temp_dir):
        """Test get_latest_status returns None when .cub/runs doesn't exist."""
        status = get_latest_status(temp_dir)

        assert status is None

    def test_get_latest_status_single_run(self, temp_dir):
        """Test get_latest_status returns status from single run."""
        writer = StatusWriter(temp_dir, "run-001")
        original = RunStatus(
            run_id="run-001",
            session_name="test",
            phase=RunPhase.COMPLETED,
            started_at=datetime.now(),
        )
        writer.write(original)

        status = get_latest_status(temp_dir)

        assert status is not None
        assert status.run_id == "run-001"

    def test_get_latest_status_multiple_runs(self, temp_dir):
        """Test get_latest_status returns most recent run."""
        import time

        # Create older run
        writer1 = StatusWriter(temp_dir, "run-001")
        status1 = RunStatus(
            run_id="run-001",
            session_name="old",
            phase=RunPhase.COMPLETED,
            started_at=datetime.now(),
        )
        writer1.write(status1)

        # Wait to ensure different mtime
        time.sleep(0.01)

        # Create newer run
        writer2 = StatusWriter(temp_dir, "run-002")
        status2 = RunStatus(
            run_id="run-002",
            session_name="new",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )
        writer2.write(status2)

        status = get_latest_status(temp_dir)

        assert status is not None
        assert status.run_id == "run-002"

    def test_get_latest_status_invalid_json(self, temp_dir):
        """Test get_latest_status returns None if latest status is invalid."""
        runs_dir = temp_dir / ".cub" / "runs" / "run-001"
        runs_dir.mkdir(parents=True)
        status_file = runs_dir / "status.json"
        status_file.write_text("{ invalid json }")

        status = get_latest_status(temp_dir)

        assert status is None


class TestListRuns:
    """Tests for list_runs function."""

    def test_list_runs_no_runs_dir(self, temp_dir):
        """Test list_runs returns empty list when .cub/runs doesn't exist."""
        runs = list_runs(temp_dir)

        assert runs == []

    def test_list_runs_empty_dir(self, temp_dir):
        """Test list_runs returns empty list when no runs exist."""
        runs_dir = temp_dir / ".cub" / "runs"
        runs_dir.mkdir(parents=True)

        runs = list_runs(temp_dir)

        assert runs == []

    def test_list_runs_single_run(self, temp_dir):
        """Test list_runs returns single run summary."""
        writer = StatusWriter(temp_dir, "run-001")
        now = datetime.now()
        status = RunStatus(
            run_id="run-001",
            session_name="test-session",
            phase=RunPhase.RUNNING,
            started_at=now,
        )
        writer.write(status)

        runs = list_runs(temp_dir)

        assert len(runs) == 1
        assert runs[0]["run_id"] == "run-001"
        assert runs[0]["session_name"] == "test-session"
        assert runs[0]["phase"] == "running"

    def test_list_runs_multiple_runs(self, temp_dir):
        """Test list_runs returns all runs sorted by started_at."""
        import time

        # Create runs with different timestamps
        statuses = [
            ("run-001", "2026-01-15T10:00:00"),
            ("run-002", "2026-01-15T11:00:00"),
            ("run-003", "2026-01-15T09:00:00"),
        ]

        for run_id, started_at in statuses:
            writer = StatusWriter(temp_dir, run_id)
            status = RunStatus(
                run_id=run_id,
                session_name=f"session-{run_id}",
                phase=RunPhase.COMPLETED,
                started_at=datetime.fromisoformat(started_at),
            )
            writer.write(status)
            time.sleep(0.01)  # Ensure different mtime

        runs = list_runs(temp_dir)

        # Should be sorted by started_at (most recent first)
        assert len(runs) == 3
        assert runs[0]["run_id"] == "run-002"  # 11:00:00
        assert runs[1]["run_id"] == "run-001"  # 10:00:00
        assert runs[2]["run_id"] == "run-003"  # 09:00:00

    def test_list_runs_skips_invalid_json(self, temp_dir):
        """Test list_runs skips runs with invalid JSON."""
        # Valid run
        writer = StatusWriter(temp_dir, "run-001")
        status = RunStatus(
            run_id="run-001",
            session_name="test",
            phase=RunPhase.COMPLETED,
            started_at=datetime.now(),
        )
        writer.write(status)

        # Invalid run
        runs_dir = temp_dir / ".cub" / "runs" / "run-002"
        runs_dir.mkdir(parents=True)
        (runs_dir / "status.json").write_text("{ invalid }")

        runs = list_runs(temp_dir)

        # Should only return valid run
        assert len(runs) == 1
        assert runs[0]["run_id"] == "run-001"

    def test_list_runs_includes_task_count(self, temp_dir):
        """Test list_runs includes tasks_completed from budget."""
        writer = StatusWriter(temp_dir, "run-001")
        status = RunStatus(
            run_id="run-001",
            session_name="test",
            phase=RunPhase.COMPLETED,
            started_at=datetime.now(),
        )
        status.budget.tasks_completed = 5
        writer.write(status)

        runs = list_runs(temp_dir)

        assert len(runs) == 1
        assert runs[0]["tasks_completed"] == 5

    def test_list_runs_handles_missing_budget(self, temp_dir):
        """Test list_runs handles runs without budget data."""
        runs_dir = temp_dir / ".cub" / "runs" / "run-001"
        runs_dir.mkdir(parents=True)

        # Write minimal status without budget
        minimal_status = {
            "run_id": "run-001",
            "session_name": "test",
            "phase": "running",
            "started_at": "2026-01-15T10:00:00",
        }
        (runs_dir / "status.json").write_text(json.dumps(minimal_status))

        runs = list_runs(temp_dir)

        assert len(runs) == 1
        assert runs[0]["tasks_completed"] == 0  # Default value
