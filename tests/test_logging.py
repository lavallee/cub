"""
Unit tests for structured JSONL logging.

Tests the CubLogger class to ensure it writes valid JSONL, handles timestamps
correctly, creates log directories, and handles errors gracefully.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from cub.utils import CubLogger, EventType


class TestCubLoggerInit:
    """Test CubLogger initialization."""

    def test_init_with_valid_path(self, tmp_path):
        """Logger initializes with valid file path."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)
        assert logger.log_file == log_file

    def test_init_creates_directory(self, tmp_path):
        """Logger creates parent directories if they don't exist."""
        log_file = tmp_path / "subdir" / "logs" / "test.jsonl"
        logger = CubLogger(log_file)
        assert logger.log_file.parent.exists()

    def test_init_static_method(self, tmp_path, monkeypatch):
        """Logger.init() creates log file in correct XDG location."""
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        logger = CubLogger.init("myproject", "session-123")

        expected_path = tmp_path / "data" / "cub" / "logs" / "myproject" / "session-123.jsonl"
        assert logger.log_file == expected_path
        assert logger.log_file.parent.exists()

    def test_init_uses_default_xdg_when_not_set(self, monkeypatch):
        """Logger.init() uses ~/.local/share when XDG_DATA_HOME not set."""
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        logger = CubLogger.init("testproject", "session-456")

        expected_path = (
            Path.home() / ".local" / "share" / "cub" / "logs" / "testproject" / "session-456.jsonl"
        )
        assert logger.log_file == expected_path

    def test_init_rejects_empty_project_name(self):
        """Logger.init() raises ValueError for empty project name."""
        with pytest.raises(ValueError, match="project_name cannot be empty"):
            CubLogger.init("", "session-123")

    def test_init_rejects_empty_session_id(self):
        """Logger.init() raises ValueError for empty session id."""
        with pytest.raises(ValueError, match="session_id cannot be empty"):
            CubLogger.init("myproject", "")


class TestCubLoggerLogEvent:
    """Test CubLogger.log_event() method."""

    def test_log_event_writes_json_line(self, tmp_path):
        """log_event writes a single JSON line to file."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_event(EventType.TASK_START, {"task_id": "cub-001"})

        # Read and verify the log line
        assert log_file.exists()
        with open(log_file) as f:
            line = f.readline()

        entry = json.loads(line)
        assert entry["event_type"] == "task_start"
        assert entry["data"]["task_id"] == "cub-001"
        assert "timestamp" in entry

    def test_log_event_timestamp_is_iso8601(self, tmp_path):
        """log_event timestamps are valid ISO 8601 format."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_event(EventType.TASK_START, {"task_id": "cub-001"})

        with open(log_file) as f:
            entry = json.loads(f.readline())

        # Should be able to parse as datetime
        timestamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)

    def test_log_event_with_empty_data(self, tmp_path):
        """log_event works with no data argument."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_event(EventType.LOOP_START)

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "loop_start"
        assert entry["data"] == {}

    def test_log_event_appends_multiple_entries(self, tmp_path):
        """log_event appends multiple entries to same file."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_event(EventType.TASK_START, {"task_id": "cub-001"})
        logger.log_event(EventType.TASK_END, {"task_id": "cub-001", "exit_code": 0})
        logger.log_event(EventType.TASK_START, {"task_id": "cub-002"})

        with open(log_file) as f:
            lines = f.readlines()

        assert len(lines) == 3
        entries = [json.loads(line) for line in lines]
        assert entries[0]["event_type"] == "task_start"
        assert entries[1]["event_type"] == "task_end"
        assert entries[2]["event_type"] == "task_start"

    def test_log_event_handles_complex_data(self, tmp_path):
        """log_event correctly serializes complex nested data."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        data = {
            "task_id": "cub-001",
            "metadata": {"labels": ["python", "urgent"], "budget": 5000, "options": None},
        }
        logger.log_event(EventType.TASK_START, data)

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["data"]["metadata"]["labels"] == ["python", "urgent"]
        assert entry["data"]["metadata"]["budget"] == 5000

    def test_log_event_handles_write_error_gracefully(self, tmp_path, monkeypatch):
        """log_event handles write errors gracefully without raising."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        # Make the log file read-only to cause a write error
        log_file.touch()
        log_file.chmod(0o444)

        # Should not raise, just print warning
        try:
            logger.log_event(EventType.TASK_START, {"task_id": "cub-001"})
        finally:
            # Restore permissions for cleanup
            log_file.chmod(0o644)


class TestCubLoggerConvenienceMethods:
    """Test convenience methods for specific event types."""

    def test_log_task_start(self, tmp_path):
        """log_task_start records task metadata."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_task_start("cub-001", "Implement feature X", "claude")

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "task_start"
        assert entry["data"]["task_id"] == "cub-001"
        assert entry["data"]["task_title"] == "Implement feature X"
        assert entry["data"]["harness"] == "claude"

    def test_log_task_end(self, tmp_path):
        """log_task_end records task completion details."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_task_end("cub-001", exit_code=0, duration_sec=42.5, tokens_used=1500)

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "task_end"
        assert entry["data"]["task_id"] == "cub-001"
        assert entry["data"]["exit_code"] == 0
        assert entry["data"]["duration_sec"] == 42.5
        assert entry["data"]["tokens_used"] == 1500

    def test_log_task_end_with_budget(self, tmp_path):
        """log_task_end includes budget information when provided."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_task_end(
            "cub-001",
            exit_code=0,
            duration_sec=42.5,
            tokens_used=1500,
            budget_remaining=3500,
            budget_total=5000,
        )

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["data"]["budget_remaining"] == 3500
        assert entry["data"]["budget_total"] == 5000

    def test_log_loop_start(self, tmp_path):
        """log_loop_start records loop iteration."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_loop_start(1)

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "loop_start"
        assert entry["data"]["iteration"] == 1

    def test_log_loop_end(self, tmp_path):
        """log_loop_end records loop completion."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_loop_end(iteration=1, tasks_processed=3, duration_sec=125.5)

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "loop_end"
        assert entry["data"]["iteration"] == 1
        assert entry["data"]["tasks_processed"] == 3
        assert entry["data"]["duration_sec"] == 125.5

    def test_log_budget_warning(self, tmp_path):
        """log_budget_warning records budget alert."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_budget_warning(remaining=500, threshold=1000, total=5000)

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "budget_warning"
        assert entry["data"]["remaining"] == 500
        assert entry["data"]["threshold"] == 1000
        assert entry["data"]["total"] == 5000
        assert entry["data"]["percentage_remaining"] == 10.0

    def test_log_error(self, tmp_path):
        """log_error records error with optional context."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_error("Task failed", context={"task_id": "cub-001", "reason": "timeout"})

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "error"
        assert entry["data"]["message"] == "Task failed"
        assert entry["data"]["context"]["task_id"] == "cub-001"

    def test_log_error_without_context(self, tmp_path):
        """log_error works without context data."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_error("Configuration error")

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "error"
        assert entry["data"]["message"] == "Configuration error"
        assert "context" not in entry["data"]


class TestCubLoggerJqQueryability:
    """Test that log entries are queryable with jq."""

    def test_logs_queryable_with_jq(self, tmp_path):
        """Log entries can be queried with jq."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_task_start("cub-001", "Task 1", "claude")
        logger.log_task_start("cub-002", "Task 2", "claude")
        logger.log_task_end("cub-001", 0, 42.5)

        # Simulate jq query: select task_start events
        import subprocess

        result = subprocess.run(
            ["jq", "-s", 'map(select(.event_type == "task_start"))', str(log_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        task_starts = json.loads(result.stdout)
        assert len(task_starts) == 2
        assert task_starts[0]["data"]["task_id"] == "cub-001"
        assert task_starts[1]["data"]["task_id"] == "cub-002"

    def test_logs_queryable_by_task_id(self, tmp_path):
        """Log entries can be filtered by task_id."""
        log_file = tmp_path / "test.jsonl"
        logger = CubLogger(log_file)

        logger.log_task_start("cub-001", "Task 1", "claude")
        logger.log_task_start("cub-002", "Task 2", "claude")
        logger.log_task_end("cub-001", 0, 42.5)
        logger.log_task_end("cub-002", 1, 15.3)

        # Simulate jq query: get all events for cub-001
        import subprocess

        result = subprocess.run(
            ["jq", "-s", 'map(select(.data.task_id == "cub-001"))', str(log_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        task_001_events = json.loads(result.stdout)
        assert len(task_001_events) == 2
        assert all(e["data"]["task_id"] == "cub-001" for e in task_001_events)


class TestEventType:
    """Test EventType enum."""

    def test_event_type_values(self):
        """EventType enum has correct values."""
        assert EventType.TASK_START.value == "task_start"
        assert EventType.TASK_END.value == "task_end"
        assert EventType.LOOP_START.value == "loop_start"
        assert EventType.LOOP_END.value == "loop_end"
        assert EventType.BUDGET_WARNING.value == "budget_warning"
        assert EventType.ERROR.value == "error"

    def test_all_event_types_represented(self):
        """All expected event types are defined."""
        expected = {"task_start", "task_end", "loop_start", "loop_end", "budget_warning", "error"}
        actual = {e.value for e in EventType}
        assert expected == actual
