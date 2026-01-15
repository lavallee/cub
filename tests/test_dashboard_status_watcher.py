"""
Tests for dashboard status watcher module.

Tests StatusWatcher polling, change detection, and error handling.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from cub.core.status.models import EventLevel, RunPhase, RunStatus
from cub.dashboard.status import StatusWatcher


class TestStatusWatcher:
    """Tests for StatusWatcher class."""

    def test_init_sets_defaults(self, temp_dir):
        """Test StatusWatcher initialization sets defaults."""
        status_path = temp_dir / "status.json"
        watcher = StatusWatcher(status_path)

        assert watcher.status_path == status_path
        assert watcher.on_change is None
        assert watcher.poll_interval == 1.0

    def test_init_accepts_custom_interval(self, temp_dir):
        """Test StatusWatcher accepts custom poll interval."""
        status_path = temp_dir / "status.json"
        watcher = StatusWatcher(status_path, poll_interval=0.5)

        assert watcher.poll_interval == 0.5

    def test_init_accepts_callback(self, temp_dir):
        """Test StatusWatcher accepts on_change callback."""
        status_path = temp_dir / "status.json"
        callback = Mock()
        watcher = StatusWatcher(status_path, on_change=callback)

        assert watcher.on_change == callback

    def test_poll_returns_none_when_file_missing(self, temp_dir):
        """Test poll() returns None when status.json doesn't exist."""
        status_path = temp_dir / "status.json"
        watcher = StatusWatcher(status_path)

        result = watcher.poll()

        assert result is None

    def test_poll_reads_valid_status_file(self, temp_dir):
        """Test poll() reads and returns valid status.json."""
        status_path = temp_dir / "status.json"
        now = datetime.now()
        original_status = RunStatus(
            run_id="test-run-001",
            session_name="test",
            phase=RunPhase.RUNNING,
            started_at=now,
        )

        # Write status file
        with status_path.open("w") as f:
            data = original_status.model_dump(mode="json")
            json.dump(data, f)

        watcher = StatusWatcher(status_path)
        result = watcher.poll()

        assert result is not None
        assert result.run_id == "test-run-001"
        assert result.phase == RunPhase.RUNNING

    def test_poll_handles_invalid_json(self, temp_dir):
        """Test poll() handles malformed JSON gracefully."""
        status_path = temp_dir / "status.json"
        status_path.write_text("{ invalid json }")

        watcher = StatusWatcher(status_path)
        result = watcher.poll()

        assert result is None

    def test_poll_handles_invalid_schema(self, temp_dir):
        """Test poll() handles invalid data schema."""
        status_path = temp_dir / "status.json"
        status_path.write_text(json.dumps({"invalid": "data"}))

        watcher = StatusWatcher(status_path)
        result = watcher.poll()

        assert result is None

    def test_poll_detects_changes_via_mtime(self, temp_dir):
        """Test poll() detects file changes using mtime."""
        status_path = temp_dir / "status.json"
        callback = Mock()
        watcher = StatusWatcher(status_path, on_change=callback)

        # Write initial status
        status1 = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )
        with status_path.open("w") as f:
            json.dump(status1.model_dump(mode="json"), f)

        # First poll - should detect change and invoke callback
        result1 = watcher.poll()
        assert result1 is not None
        assert callback.call_count == 1

        # Second poll without file change - should not invoke callback
        result2 = watcher.poll()
        assert result2 is not None
        assert callback.call_count == 1  # Still 1, not 2

        # Wait and modify file (change mtime)
        time.sleep(0.01)  # Ensure mtime changes
        status2 = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.COMPLETED,
            started_at=datetime.now(),
        )
        with status_path.open("w") as f:
            json.dump(status2.model_dump(mode="json"), f)

        # Poll again - should detect change and invoke callback
        result3 = watcher.poll()
        assert result3 is not None
        assert result3.phase == RunPhase.COMPLETED
        assert callback.call_count == 2

    def test_poll_caches_status_when_unchanged(self, temp_dir):
        """Test poll() returns cached status when file unchanged."""
        status_path = temp_dir / "status.json"
        status = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )

        with status_path.open("w") as f:
            json.dump(status.model_dump(mode="json"), f)

        watcher = StatusWatcher(status_path)

        # First poll reads from file
        result1 = watcher.poll()
        assert result1 is not None

        # Second poll should return cached result
        result2 = watcher.poll()
        assert result2 is result1  # Same object reference

    def test_poll_handles_deleted_file(self, temp_dir):
        """Test poll() handles file deletion gracefully."""
        status_path = temp_dir / "status.json"
        status = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )

        with status_path.open("w") as f:
            json.dump(status.model_dump(mode="json"), f)

        watcher = StatusWatcher(status_path)

        # First poll succeeds
        result1 = watcher.poll()
        assert result1 is not None

        # Delete file
        status_path.unlink()

        # Poll should handle gracefully
        result2 = watcher.poll()
        assert result2 is None

    def test_poll_handles_partial_write(self, temp_dir):
        """Test poll() handles incomplete JSON writes."""
        status_path = temp_dir / "status.json"
        status = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )

        # Write valid status
        with status_path.open("w") as f:
            json.dump(status.model_dump(mode="json"), f)

        watcher = StatusWatcher(status_path)

        # First poll reads valid status
        result1 = watcher.poll()
        assert result1 is not None

        # Write incomplete JSON (simulating partial write)
        with status_path.open("w") as f:
            f.write("{ incomplete")

        # Poll should handle gracefully and return last valid status
        result2 = watcher.poll()
        assert result2 is None

    def test_callback_not_invoked_when_content_unchanged(self, temp_dir):
        """Test callback not invoked if file mtime changes but content doesn't."""
        status_path = temp_dir / "status.json"
        callback = Mock()
        status = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )

        with status_path.open("w") as f:
            json.dump(status.model_dump(mode="json"), f)

        watcher = StatusWatcher(status_path, on_change=callback)

        # First poll
        watcher.poll()
        assert callback.call_count == 1

        # Force mtime change by rewriting identical content
        time.sleep(0.01)
        with status_path.open("w") as f:
            json.dump(status.model_dump(mode="json"), f)

        # Poll again - mtime changed but content is same
        watcher.poll()
        # Callback should not be invoked (content unchanged)
        assert callback.call_count == 1

    def test_get_interval(self, temp_dir):
        """Test get_interval() returns configured interval."""
        status_path = temp_dir / "status.json"
        watcher = StatusWatcher(status_path, poll_interval=2.5)

        assert watcher.get_interval() == 2.5

    def test_set_on_change(self, temp_dir):
        """Test set_on_change() updates callback."""
        status_path = temp_dir / "status.json"
        callback1 = Mock()
        callback2 = Mock()

        watcher = StatusWatcher(status_path, on_change=callback1)
        assert watcher.on_change == callback1

        watcher.set_on_change(callback2)
        assert watcher.on_change == callback2

    def test_poll_with_events(self, temp_dir):
        """Test poll() preserves event logs in status."""
        status_path = temp_dir / "status.json"
        status = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )
        status.add_event("Test event", level=EventLevel.INFO)

        with status_path.open("w") as f:
            json.dump(status.model_dump(mode="json"), f)

        watcher = StatusWatcher(status_path)
        result = watcher.poll()

        assert result is not None
        assert len(result.events) == 1
        assert result.events[0].message == "Test event"

    def test_callback_receives_correct_status(self, temp_dir):
        """Test callback receives the updated RunStatus object."""
        status_path = temp_dir / "status.json"
        callback = Mock()
        status = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )

        with status_path.open("w") as f:
            json.dump(status.model_dump(mode="json"), f)

        watcher = StatusWatcher(status_path, on_change=callback)
        watcher.poll()

        # Verify callback was invoked with correct status
        assert callback.call_count == 1
        called_status = callback.call_args[0][0]
        assert isinstance(called_status, RunStatus)
        assert called_status.run_id == "test-run-001"

    def test_poll_handles_empty_file(self, temp_dir):
        """Test poll() handles empty status.json file."""
        status_path = temp_dir / "status.json"
        status_path.write_text("")

        watcher = StatusWatcher(status_path)
        result = watcher.poll()

        assert result is None

    def test_poll_transitions_from_none_to_exists(self, temp_dir):
        """Test poll() handles file creation during polling."""
        status_path = temp_dir / "status.json"
        callback = Mock()
        watcher = StatusWatcher(status_path, on_change=callback)

        # First poll - file doesn't exist
        result1 = watcher.poll()
        assert result1 is None
        assert callback.call_count == 0

        # Create file
        status = RunStatus(
            run_id="test-run-001",
            phase=RunPhase.RUNNING,
            started_at=datetime.now(),
        )
        with status_path.open("w") as f:
            json.dump(status.model_dump(mode="json"), f)

        # Poll again - should detect file and invoke callback
        result2 = watcher.poll()
        assert result2 is not None
        assert callback.call_count == 1
