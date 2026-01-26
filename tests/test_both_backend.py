"""Tests for BothBackend wrapper and detection logic."""

import json
import os
from pathlib import Path

import pytest

from cub.core.tasks.backend import detect_backend, get_backend
from cub.core.tasks.both import BothBackend
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType


class TestBothModeDetection:
    """Test backend detection logic for 'both' mode."""

    def test_detect_both_mode_with_env_var(self, tmp_path: Path):
        """Test that CUB_BACKEND=both is detected when both backends exist."""
        # Create both backend directories
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.touch()

        # Set environment variable
        os.environ["CUB_BACKEND"] = "both"
        try:
            result = detect_backend(tmp_path)
            assert result == "both"
        finally:
            os.environ.pop("CUB_BACKEND", None)

    def test_detect_both_mode_falls_back_if_beads_missing(self, tmp_path: Path):
        """Test that both mode falls back if .beads/ doesn't exist."""
        # Only create JSONL backend
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.touch()

        # Set environment variable to both
        os.environ["CUB_BACKEND"] = "both"
        try:
            result = detect_backend(tmp_path)
            # Should fall back to jsonl since beads is missing
            assert result == "jsonl"
        finally:
            os.environ.pop("CUB_BACKEND", None)

    def test_detect_both_mode_with_config_file(self, tmp_path: Path):
        """Test that backend.mode=both in .cub.json is detected."""
        # Clear config cache to ensure we load the test config
        from cub.core.config import clear_cache
        clear_cache()

        # Create both backend directories
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.touch()

        # Create config file
        config_file = tmp_path / ".cub.json"
        config_data = {
            "backend": {
                "mode": "both"
            }
        }
        config_file.write_text(json.dumps(config_data))

        result = detect_backend(tmp_path)
        assert result == "both"

        # Clean up
        clear_cache()

    def test_detect_both_mode_config_falls_back_if_jsonl_missing(self, tmp_path: Path):
        """Test that both mode from config falls back if tasks.jsonl doesn't exist."""
        # Only create beads backend
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()

        # Create config file requesting both mode
        config_file = tmp_path / ".cub.json"
        config_data = {
            "backend": {
                "mode": "both"
            }
        }
        config_file.write_text(json.dumps(config_data))

        result = detect_backend(tmp_path)
        # Should fall back to beads since jsonl is missing
        assert result == "beads"

    def test_detect_beads_mode_with_config(self, tmp_path: Path):
        """Test that backend.mode=beads in config is respected."""
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()

        config_file = tmp_path / ".cub.json"
        config_data = {
            "backend": {
                "mode": "beads"
            }
        }
        config_file.write_text(json.dumps(config_data))

        result = detect_backend(tmp_path)
        assert result == "beads"

    def test_detect_jsonl_mode_with_config(self, tmp_path: Path):
        """Test that backend.mode=jsonl in config is respected."""
        config_file = tmp_path / ".cub.json"
        config_data = {
            "backend": {
                "mode": "jsonl"
            }
        }
        config_file.write_text(json.dumps(config_data))

        result = detect_backend(tmp_path)
        assert result == "jsonl"

    def test_detect_auto_mode_with_beads(self, tmp_path: Path):
        """Test auto-detection with .beads/ directory present."""
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()

        result = detect_backend(tmp_path)
        assert result == "beads"

    def test_detect_auto_mode_with_jsonl(self, tmp_path: Path):
        """Test auto-detection with tasks.jsonl present."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.touch()

        result = detect_backend(tmp_path)
        assert result == "jsonl"

    def test_detect_defaults_to_jsonl(self, tmp_path: Path):
        """Test that detection defaults to jsonl when nothing exists."""
        result = detect_backend(tmp_path)
        assert result == "jsonl"


class TestGetBackendBothMode:
    """Test get_backend function with both mode."""

    def test_get_backend_instantiates_both_backend(self, tmp_path: Path, monkeypatch):
        """Test that get_backend('both') instantiates BothBackend."""
        # Mock BeadsBackend to avoid needing bd CLI
        class MockBeadsBackend:
            def __init__(self, project_dir=None):
                self.project_dir = project_dir or Path.cwd()

            @property
            def backend_name(self):
                return "beads"

            def list_tasks(self, status=None, parent=None, label=None):
                return []

        # Mock JsonlBackend
        class MockJsonlBackend:
            def __init__(self, project_dir=None):
                self.project_dir = project_dir or Path.cwd()

            @property
            def backend_name(self):
                return "jsonl"

            def list_tasks(self, status=None, parent=None, label=None):
                return []

        # Patch the imports in the modules where they're imported
        monkeypatch.setattr("cub.core.tasks.beads.BeadsBackend", MockBeadsBackend)
        monkeypatch.setattr("cub.core.tasks.jsonl.JsonlBackend", MockJsonlBackend)

        backend = get_backend(name="both", project_dir=tmp_path)

        assert isinstance(backend, BothBackend)
        assert backend.primary.backend_name == "beads"
        assert backend.secondary.backend_name == "jsonl"

    def test_get_backend_raises_error_if_both_initialization_fails(
        self, tmp_path: Path, monkeypatch
    ):
        """Test that get_backend raises ValueError if both mode can't be initialized."""
        # Mock BeadsBackend to raise an error
        class FailingBeadsBackend:
            def __init__(self, project_dir=None):
                raise RuntimeError("bd CLI not available")

        monkeypatch.setattr("cub.core.tasks.beads.BeadsBackend", FailingBeadsBackend)

        with pytest.raises(ValueError, match="Failed to initialize 'both' backend"):
            get_backend(name="both", project_dir=tmp_path)


class TestBothBackendComparison:
    """Test BothBackend comparison functionality."""

    def test_compare_all_tasks_identical_backends(self, tmp_path: Path):
        """Test comparison when both backends have identical tasks."""
        # Create mock backends with identical tasks
        class MockBackend:
            def __init__(self, tasks):
                self.tasks = tasks

            @property
            def backend_name(self):
                return "mock"

            def list_tasks(self, status=None, parent=None, label=None):
                return self.tasks

        task1 = Task(
            id="test-001",
            title="Test Task 1",
            type=TaskType.TASK,
            priority=TaskPriority.P1,
            status=TaskStatus.OPEN,
        )
        task2 = Task(
            id="test-002",
            title="Test Task 2",
            type=TaskType.TASK,
            priority=TaskPriority.P2,
            status=TaskStatus.CLOSED,
        )

        primary = MockBackend([task1, task2])
        secondary = MockBackend([task1, task2])

        both = BothBackend(primary, secondary)
        divergences = both.compare_all_tasks()

        assert len(divergences) == 0

    def test_compare_all_tasks_with_differences(self, tmp_path: Path):
        """Test comparison when backends have different task states."""
        class MockBackend:
            def __init__(self, tasks):
                self.tasks = tasks

            @property
            def backend_name(self):
                return "mock"

            def list_tasks(self, status=None, parent=None, label=None):
                return self.tasks

        task1_primary = Task(
            id="test-001",
            title="Test Task 1",
            type=TaskType.TASK,
            priority=TaskPriority.P1,
            status=TaskStatus.OPEN,
        )
        task1_secondary = Task(
            id="test-001",
            title="Test Task 1",
            type=TaskType.TASK,
            priority=TaskPriority.P1,
            status=TaskStatus.CLOSED,  # Different status
        )

        primary = MockBackend([task1_primary])
        secondary = MockBackend([task1_secondary])

        both = BothBackend(primary, secondary)
        divergences = both.compare_all_tasks()

        assert len(divergences) == 1
        assert divergences[0].task_id == "test-001"
        assert "status" in divergences[0].difference_summary

    def test_compare_all_tasks_with_missing_task(self, tmp_path: Path):
        """Test comparison when a task exists in only one backend."""
        class MockBackend:
            def __init__(self, tasks):
                self.tasks = tasks

            @property
            def backend_name(self):
                return "mock"

            def list_tasks(self, status=None, parent=None, label=None):
                return self.tasks

        task1 = Task(
            id="test-001",
            title="Test Task 1",
            type=TaskType.TASK,
            priority=TaskPriority.P1,
            status=TaskStatus.OPEN,
        )
        task2 = Task(
            id="test-002",
            title="Test Task 2",
            type=TaskType.TASK,
            priority=TaskPriority.P2,
            status=TaskStatus.OPEN,
        )

        primary = MockBackend([task1, task2])
        secondary = MockBackend([task1])  # Missing task2

        both = BothBackend(primary, secondary)
        divergences = both.compare_all_tasks()

        assert len(divergences) == 1
        assert divergences[0].task_id == "test-002"
        assert "exists only in primary backend" in divergences[0].difference_summary

    def test_divergence_log_creation(self, tmp_path: Path):
        """Test that divergences are logged to file."""
        class MockBackend:
            def __init__(self, tasks):
                self.tasks = tasks

            @property
            def backend_name(self):
                return "mock"

            def list_tasks(self, status=None, parent=None, label=None):
                return self.tasks

            def get_task(self, task_id):
                for task in self.tasks:
                    if task.id == task_id:
                        return task
                return None

        task1_primary = Task(
            id="test-001",
            title="Test Task 1",
            type=TaskType.TASK,
            priority=TaskPriority.P1,
            status=TaskStatus.OPEN,
        )
        task1_secondary = Task(
            id="test-001",
            title="Different Title",  # Different title
            type=TaskType.TASK,
            priority=TaskPriority.P1,
            status=TaskStatus.OPEN,
        )

        primary = MockBackend([task1_primary])
        secondary = MockBackend([task1_secondary])

        divergence_log = tmp_path / ".cub" / "backend-divergence.log"
        both = BothBackend(primary, secondary, divergence_log=divergence_log)

        # Trigger a divergence by calling get_task
        both.get_task("test-001")

        # Check that log file was created and contains the divergence
        assert divergence_log.exists()
        log_content = divergence_log.read_text()
        assert "test-001" in log_content
        assert "title" in log_content

    def test_get_divergence_count(self, tmp_path: Path):
        """Test divergence count reporting."""
        divergence_log = tmp_path / ".cub" / "backend-divergence.log"
        divergence_log.parent.mkdir(parents=True)

        # Write some fake divergences
        with open(divergence_log, "w") as f:
            f.write('{"task_id": "test-001"}\n')
            f.write('{"task_id": "test-002"}\n')
            f.write('{"task_id": "test-003"}\n')

        class MockBackend:
            @property
            def backend_name(self):
                return "mock"

            def list_tasks(self, status=None, parent=None, label=None):
                return []

        both = BothBackend(MockBackend(), MockBackend(), divergence_log=divergence_log)
        count = both.get_divergence_count()

        assert count == 3
