"""
Tests for task backend protocol and registry.

Tests the backend registry, auto-detection, and backend management functions.
"""

import pytest

from cub.core.tasks import backend as tasks_backend
from cub.core.tasks.backend import (
    detect_backend,
    get_backend,
    is_backend_available,
    list_backends,
    register_backend,
)
from cub.core.tasks.models import Task, TaskCounts, TaskStatus


class TestBackendRegistry:
    """Test backend registration and retrieval."""

    def test_register_backend(self):
        """Test registering a backend."""

        @register_backend("test-backend")
        class TestBackend:
            def __init__(self, project_dir=None):
                self.project_dir = project_dir

            def list_tasks(self, status=None, parent=None, label=None):
                return []

            def get_task(self, task_id: str):
                return None

            def get_ready_tasks(self, parent=None, label=None):
                return []

            def update_task(self, task_id: str, **kwargs):
                return Task(id=task_id, title="Updated")

            def close_task(self, task_id: str, reason=None):
                return Task(id=task_id, title="Closed", status=TaskStatus.CLOSED)

            def create_task(self, title: str, **kwargs):
                return Task(id="test-001", title=title)

            def get_task_counts(self):
                return TaskCounts(total=0, open=0, in_progress=0, closed=0)

            def add_task_note(self, task_id: str, note: str):
                return Task(id=task_id, title="Task with note")

        # Verify backend is registered
        assert "test-backend" in list_backends()

        # Clean up
        tasks_backend._backends.pop("test-backend", None)

    def test_get_backend_by_name(self):
        """Test getting a backend by name."""

        @register_backend("test-get")
        class TestBackend:
            def __init__(self, project_dir=None):
                self.project_dir = project_dir

            def list_tasks(self, **kwargs):
                return []

            def get_task(self, task_id: str):
                return None

            def get_ready_tasks(self, **kwargs):
                return []

            def update_task(self, task_id: str, **kwargs):
                return Task(id=task_id, title="Updated")

            def close_task(self, task_id: str, reason=None):
                return Task(id=task_id, title="Closed", status=TaskStatus.CLOSED)

            def create_task(self, title: str, **kwargs):
                return Task(id="test-001", title=title)

            def get_task_counts(self):
                return TaskCounts(total=0, open=0, in_progress=0, closed=0)

            def add_task_note(self, task_id: str, note: str):
                return Task(id=task_id, title="Task")

        backend = get_backend("test-get")
        assert isinstance(backend, TestBackend)

        # Clean up
        tasks_backend._backends.pop("test-get", None)

    def test_get_backend_invalid_name(self):
        """Test getting an invalid backend raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            get_backend("nonexistent-backend")

    def test_list_backends(self):
        """Test listing all registered backends."""
        # Clear any existing test backends
        test_backends = [k for k in list_backends() if k.startswith("test-")]
        for name in test_backends:
            tasks_backend._backends.pop(name, None)

        @register_backend("test-list-1")
        class TestBackend1:
            def list_tasks(self, **kwargs):
                return []

            def get_task(self, task_id: str):
                return None

            def get_ready_tasks(self, **kwargs):
                return []

            def update_task(self, task_id: str, **kwargs):
                return Task(id=task_id, title="")

            def close_task(self, task_id: str, reason=None):
                return Task(id=task_id, title="", status=TaskStatus.CLOSED)

            def create_task(self, title: str, **kwargs):
                return Task(id="test-001", title=title)

            def get_task_counts(self):
                return TaskCounts(total=0, open=0, in_progress=0, closed=0)

            def add_task_note(self, task_id: str, note: str):
                return Task(id=task_id, title="")

        @register_backend("test-list-2")
        class TestBackend2:
            def list_tasks(self, **kwargs):
                return []

            def get_task(self, task_id: str):
                return None

            def get_ready_tasks(self, **kwargs):
                return []

            def update_task(self, task_id: str, **kwargs):
                return Task(id=task_id, title="")

            def close_task(self, task_id: str, reason=None):
                return Task(id=task_id, title="", status=TaskStatus.CLOSED)

            def create_task(self, title: str, **kwargs):
                return Task(id="test-001", title=title)

            def get_task_counts(self):
                return TaskCounts(total=0, open=0, in_progress=0, closed=0)

            def add_task_note(self, task_id: str, note: str):
                return Task(id=task_id, title="")

        backends = list_backends()
        assert "test-list-1" in backends
        assert "test-list-2" in backends

        # Clean up
        tasks_backend._backends.pop("test-list-1", None)
        tasks_backend._backends.pop("test-list-2", None)


class TestBackendAvailability:
    """Test backend availability detection."""

    def test_is_backend_available_true(self):
        """Test is_backend_available returns True for registered backend."""

        @register_backend("test-available")
        class TestBackend:
            def list_tasks(self, **kwargs):
                return []

            def get_task(self, task_id: str):
                return None

            def get_ready_tasks(self, **kwargs):
                return []

            def update_task(self, task_id: str, **kwargs):
                return Task(id=task_id, title="")

            def close_task(self, task_id: str, reason=None):
                return Task(id=task_id, title="", status=TaskStatus.CLOSED)

            def create_task(self, title: str, **kwargs):
                return Task(id="test-001", title=title)

            def get_task_counts(self):
                return TaskCounts(total=0, open=0, in_progress=0, closed=0)

            def add_task_note(self, task_id: str, note: str):
                return Task(id=task_id, title="")

        assert is_backend_available("test-available") is True

        # Clean up
        tasks_backend._backends.pop("test-available", None)

    def test_is_backend_available_false(self):
        """Test is_backend_available returns False for nonexistent backend."""
        assert is_backend_available("does-not-exist") is False


class TestDetectBackend:
    """Test backend auto-detection."""

    def test_detect_backend_beads_directory(self, tmp_path):
        """Test detection of beads backend when .beads/ exists."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        beads_dir = project_dir / ".beads"
        beads_dir.mkdir()

        result = detect_backend(project_dir)
        assert result == "beads"

    def test_detect_backend_prd_json(self, tmp_path):
        """Test detection of jsonl backend when prd.json exists."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        prd_file = project_dir / "prd.json"
        prd_file.write_text("{}")

        result = detect_backend(project_dir)
        assert result == "jsonl"

    def test_detect_backend_default_json(self, tmp_path):
        """Test default to jsonl backend when nothing else found."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = detect_backend(project_dir)
        assert result == "jsonl"

    def test_detect_backend_env_variable_beads(self, tmp_path, monkeypatch):
        """Test detection from CUB_BACKEND environment variable (beads)."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        beads_dir = project_dir / ".beads"
        beads_dir.mkdir()

        monkeypatch.setenv("CUB_BACKEND", "beads")

        result = detect_backend(project_dir)
        assert result == "beads"

    def test_detect_backend_env_variable_bd(self, tmp_path, monkeypatch):
        """Test detection from CUB_BACKEND=bd."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        beads_dir = project_dir / ".beads"
        beads_dir.mkdir()

        monkeypatch.setenv("CUB_BACKEND", "bd")

        result = detect_backend(project_dir)
        assert result == "beads"

    def test_detect_backend_env_variable_json(self, tmp_path, monkeypatch):
        """Test detection from CUB_BACKEND=json."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.setenv("CUB_BACKEND", "json")

        result = detect_backend(project_dir)
        assert result == "jsonl"

    def test_detect_backend_env_variable_prd(self, tmp_path, monkeypatch):
        """Test detection from CUB_BACKEND=prd."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.setenv("CUB_BACKEND", "prd")

        result = detect_backend(project_dir)
        assert result == "jsonl"

    def test_detect_backend_beads_priority_over_prd(self, tmp_path):
        """Test beads backend has priority over json when both exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        beads_dir = project_dir / ".beads"
        beads_dir.mkdir()
        prd_file = project_dir / "prd.json"
        prd_file.write_text("{}")

        result = detect_backend(project_dir)
        assert result == "beads"

    def test_detect_backend_with_string_path(self, tmp_path):
        """Test detection with string path instead of Path object."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        beads_dir = project_dir / ".beads"
        beads_dir.mkdir()

        result = detect_backend(str(project_dir))
        assert result == "beads"

    def test_detect_backend_defaults_to_cwd(self, tmp_path, monkeypatch):
        """Test detection defaults to current working directory."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        beads_dir = project_dir / ".beads"
        beads_dir.mkdir()

        # Change to project directory
        monkeypatch.chdir(project_dir)

        result = detect_backend(None)
        assert result == "beads"

    def test_detect_backend_env_beads_falls_back_if_missing(self, tmp_path, monkeypatch):
        """Test env variable beads falls back to auto-detect if .beads/ missing."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        prd_file = project_dir / "prd.json"
        prd_file.write_text("{}")

        monkeypatch.setenv("CUB_BACKEND", "beads")

        # Should fall back to auto-detect and find jsonl
        result = detect_backend(project_dir)
        assert result == "jsonl"


class TestGetBackendAutoDetect:
    """Test get_backend with auto-detection."""

    def test_get_backend_auto_detects(self, tmp_path, monkeypatch):
        """Test get_backend auto-detects when name is None."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        beads_dir = project_dir / ".beads"
        beads_dir.mkdir()

        # Mock _is_bd_available to return True so the real BeadsBackend can be instantiated
        # even when bd CLI isn't installed (e.g., in CI)
        from cub.core.tasks.beads import BeadsBackend as RealBeadsBackend

        monkeypatch.setattr(RealBeadsBackend, "_is_bd_available", lambda self: True)
        monkeypatch.chdir(project_dir)

        backend = get_backend(None, project_dir)
        assert backend is not None

    def test_get_backend_with_explicit_project_dir(self, tmp_path):
        """Test get_backend with explicit project_dir argument."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Register json backend if not already registered
        if "json" not in list_backends():

            @register_backend("json")
            class JsonBackend:
                def list_tasks(self, **kwargs):
                    return []

                def get_task(self, task_id: str):
                    return None

                def get_ready_tasks(self, **kwargs):
                    return []

                def update_task(self, task_id: str, **kwargs):
                    return Task(id=task_id, title="")

                def close_task(self, task_id: str, reason=None):
                    return Task(id=task_id, title="", status=TaskStatus.CLOSED)

                def create_task(self, title: str, **kwargs):
                    return Task(id="test-001", title=title)

                def get_task_counts(self):
                    return TaskCounts(total=0, open=0, in_progress=0, closed=0)

                def add_task_note(self, task_id: str, note: str):
                    return Task(id=task_id, title="")

        backend = get_backend(None, project_dir)
        assert backend is not None
