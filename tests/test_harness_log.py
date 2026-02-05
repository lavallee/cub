"""
Tests for harness log writer and reader.

Tests JSONL format, streaming capabilities, and data integrity
for the harness log system.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.ledger.harness_log import (
    HarnessLogEvent,
    HarnessLogReader,
    HarnessLogWriter,
)


class TestHarnessLogEvent:
    """Tests for HarnessLogEvent model."""

    def test_create_with_defaults(self) -> None:
        """Test creating event with defaults."""
        event = HarnessLogEvent(event_type="status", data={"message": "test"})
        assert event.event_type == "status"
        assert event.data == {"message": "test"}
        # Check timestamp is ISO 8601
        assert "T" in event.timestamp
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))

    def test_create_with_custom_timestamp(self) -> None:
        """Test creating event with custom timestamp."""
        ts = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc).isoformat()
        event = HarnessLogEvent(
            timestamp=ts,
            event_type="status",
            data={"message": "test"}
        )
        assert event.timestamp == ts

    def test_invalid_timestamp_raises(self) -> None:
        """Test that invalid timestamp raises ValueError."""
        with pytest.raises(ValueError, match="Timestamp must be ISO 8601 format"):
            HarnessLogEvent(
                timestamp="not-a-timestamp",
                event_type="status",
                data={}
            )

    def test_start_event(self) -> None:
        """Test creating start event."""
        event = HarnessLogEvent.start(harness="claude", model="sonnet")
        assert event.event_type == "start"
        assert event.data["harness"] == "claude"
        assert event.data["model"] == "sonnet"

    def test_tool_call_event(self) -> None:
        """Test creating tool call event."""
        event = HarnessLogEvent.tool_call(
            "Read",
            {"file_path": "src/main.py"},
            extra_field="value"
        )
        assert event.event_type == "tool_call"
        assert event.data["tool_name"] == "Read"
        assert event.data["parameters"] == {"file_path": "src/main.py"}
        assert event.data["extra_field"] == "value"

    def test_tool_result_event(self) -> None:
        """Test creating tool result event."""
        event = HarnessLogEvent.tool_result(
            "Read",
            "file contents here",
            execution_time_ms=150
        )
        assert event.event_type == "tool_result"
        assert event.data["tool_name"] == "Read"
        assert event.data["result"] == "file contents here"
        assert event.data["execution_time_ms"] == 150

    def test_response_event(self) -> None:
        """Test creating response event."""
        event = HarnessLogEvent.response(
            "I'll help you with that task",
            tokens=50
        )
        assert event.event_type == "response"
        assert event.data["content"] == "I'll help you with that task"
        assert event.data["tokens"] == 50

    def test_error_event(self) -> None:
        """Test creating error event."""
        event = HarnessLogEvent.error(
            "timeout",
            "Request timed out after 30s",
            retryable=True
        )
        assert event.event_type == "error"
        assert event.data["error_type"] == "timeout"
        assert event.data["message"] == "Request timed out after 30s"
        assert event.data["retryable"] is True

    def test_warning_event(self) -> None:
        """Test creating warning event."""
        event = HarnessLogEvent.warning(
            "API rate limit approaching",
            remaining_requests=10
        )
        assert event.event_type == "warning"
        assert event.data["message"] == "API rate limit approaching"
        assert event.data["remaining_requests"] == 10

    def test_status_event(self) -> None:
        """Test creating status event."""
        event = HarnessLogEvent.status(
            "Processing iteration 3/5",
            progress=0.6
        )
        assert event.event_type == "status"
        assert event.data["message"] == "Processing iteration 3/5"
        assert event.data["progress"] == 0.6

    def test_complete_event(self) -> None:
        """Test creating completion event."""
        event = HarnessLogEvent.complete(
            True,
            duration_seconds=120,
            iterations=3
        )
        assert event.event_type == "complete"
        assert event.data["success"] is True
        assert event.data["duration_seconds"] == 120
        assert event.data["iterations"] == 3


class TestHarnessLogWriter:
    """Tests for HarnessLogWriter."""

    @pytest.fixture
    def temp_ledger(self, tmp_path: Path) -> Path:
        """Create a temporary ledger directory."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)
        return ledger_dir

    def test_create_writer(self, temp_ledger: Path) -> None:
        """Test creating a writer."""
        writer = HarnessLogWriter(temp_ledger, "cub-test", 1)
        assert writer.task_id == "cub-test"
        assert writer.attempt_number == 1
        assert writer.log_file == temp_ledger / "by-task" / "cub-test" / "001-harness.jsonl"

    def test_write_event(self, temp_ledger: Path) -> None:
        """Test writing a single event."""
        writer = HarnessLogWriter(temp_ledger, "cub-test", 1)
        event = HarnessLogEvent.start(harness="claude", model="sonnet")
        writer.write_event(event)
        writer.close()

        # Verify file was created
        assert writer.log_file.exists()

        # Verify content
        content = writer.log_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1

        # Verify JSON is valid
        data = json.loads(lines[0])
        assert data["event_type"] == "start"
        assert data["data"]["harness"] == "claude"
        assert data["data"]["model"] == "sonnet"

    def test_write_multiple_events(self, temp_ledger: Path) -> None:
        """Test writing multiple events."""
        writer = HarnessLogWriter(temp_ledger, "cub-test", 1)
        writer.write_start(harness="claude", model="sonnet")
        writer.write_tool_call("Read", {"file_path": "src/main.py"})
        writer.write_tool_result("Read", "contents here")
        writer.write_complete(True)
        writer.close()

        # Verify file contents
        content = writer.log_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 4

        # Verify each line is valid JSON
        for line in lines:
            data = json.loads(line)
            assert "timestamp" in data
            assert "event_type" in data
            assert "data" in data

    def test_context_manager(self, temp_ledger: Path) -> None:
        """Test using writer as context manager."""
        with HarnessLogWriter(temp_ledger, "cub-test", 1) as writer:
            writer.write_start(harness="claude")
            writer.write_complete(True)

        # File should be closed and written
        log_file = temp_ledger / "by-task" / "cub-test" / "001-harness.jsonl"
        assert log_file.exists()
        content = log_file.read_text()
        assert len(content.strip().split("\n")) == 2

    def test_multiple_attempts(self, temp_ledger: Path) -> None:
        """Test writing logs for multiple attempts."""
        # Attempt 1
        writer1 = HarnessLogWriter(temp_ledger, "cub-test", 1)
        writer1.write_start(harness="claude", model="haiku")
        writer1.write_complete(False)
        writer1.close()

        # Attempt 2
        writer2 = HarnessLogWriter(temp_ledger, "cub-test", 2)
        writer2.write_start(harness="claude", model="sonnet")
        writer2.write_complete(True)
        writer2.close()

        # Verify both files exist
        task_dir = temp_ledger / "by-task" / "cub-test"
        assert (task_dir / "001-harness.jsonl").exists()
        assert (task_dir / "002-harness.jsonl").exists()

    def test_zero_padded_attempt_numbers(self, temp_ledger: Path) -> None:
        """Test that attempt numbers are zero-padded correctly."""
        writer = HarnessLogWriter(temp_ledger, "cub-test", 7)
        writer.write_start()
        writer.close()

        log_file = temp_ledger / "by-task" / "cub-test" / "007-harness.jsonl"
        assert log_file.exists()

    def test_convenience_methods(self, temp_ledger: Path) -> None:
        """Test all convenience methods."""
        writer = HarnessLogWriter(temp_ledger, "cub-test", 1)
        writer.write_start(harness="claude")
        writer.write_tool_call("Edit", {"file_path": "test.py", "old_string": "a"})
        writer.write_tool_result("Edit", "success")
        writer.write_response("Done editing")
        writer.write_error("syntax_error", "Invalid syntax on line 5")
        writer.write_warning("File is large")
        writer.write_status("Running tests")
        writer.write_complete(True, iterations=1)
        writer.close()

        # Verify all events were written
        content = writer.log_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 8

        # Verify event types
        event_types = [json.loads(line)["event_type"] for line in lines]
        assert event_types == [
            "start",
            "tool_call",
            "tool_result",
            "response",
            "error",
            "warning",
            "status",
            "complete"
        ]


class TestHarnessLogReader:
    """Tests for HarnessLogReader."""

    @pytest.fixture
    def temp_ledger_with_logs(self, tmp_path: Path) -> Path:
        """Create a temporary ledger with sample logs."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        # Write sample logs
        writer = HarnessLogWriter(ledger_dir, "cub-test", 1)
        writer.write_start(harness="claude", model="sonnet")
        writer.write_tool_call("Read", {"file_path": "src/main.py"})
        writer.write_tool_result("Read", "file contents")
        writer.write_response("I read the file")
        writer.write_error("api_error", "Rate limit exceeded")
        writer.write_warning("Retrying in 1s")
        writer.write_status("Retry successful")
        writer.write_complete(True, duration_seconds=30)
        writer.close()

        return ledger_dir

    def test_create_reader(self, temp_ledger_with_logs: Path) -> None:
        """Test creating a reader."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        assert reader.task_id == "cub-test"
        assert reader.attempt_number == 1
        assert reader.log_file == (
            temp_ledger_with_logs / "by-task" / "cub-test" / "001-harness.jsonl"
        )

    def test_exists(self, temp_ledger_with_logs: Path) -> None:
        """Test checking if log file exists."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        assert reader.exists()

        reader_missing = HarnessLogReader(temp_ledger_with_logs, "cub-missing", 1)
        assert not reader_missing.exists()

    def test_iter_events(self, temp_ledger_with_logs: Path) -> None:
        """Test iterating over events."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        events = list(reader.iter_events())

        assert len(events) == 8
        assert events[0].event_type == "start"
        assert events[0].data["harness"] == "claude"
        assert events[1].event_type == "tool_call"
        assert events[2].event_type == "tool_result"
        assert events[3].event_type == "response"
        assert events[4].event_type == "error"
        assert events[5].event_type == "warning"
        assert events[6].event_type == "status"
        assert events[7].event_type == "complete"

    def test_iter_events_missing_file(self, temp_ledger_with_logs: Path) -> None:
        """Test iterating when file doesn't exist raises error."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-missing", 1)
        with pytest.raises(FileNotFoundError):
            list(reader.iter_events())

    def test_read_all(self, temp_ledger_with_logs: Path) -> None:
        """Test reading all events into memory."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        events = reader.read_all()

        assert len(events) == 8
        assert all(isinstance(e, HarnessLogEvent) for e in events)

    def test_filter_by_type(self, temp_ledger_with_logs: Path) -> None:
        """Test filtering events by type."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        tool_calls = list(reader.filter_by_type("tool_call"))

        assert len(tool_calls) == 1
        assert tool_calls[0].event_type == "tool_call"
        assert tool_calls[0].data["tool_name"] == "Read"

    def test_get_errors(self, temp_ledger_with_logs: Path) -> None:
        """Test getting all error events."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        errors = reader.get_errors()

        assert len(errors) == 1
        assert errors[0].event_type == "error"
        assert errors[0].data["error_type"] == "api_error"
        assert errors[0].data["message"] == "Rate limit exceeded"

    def test_get_warnings(self, temp_ledger_with_logs: Path) -> None:
        """Test getting all warning events."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        warnings = reader.get_warnings()

        assert len(warnings) == 1
        assert warnings[0].event_type == "warning"
        assert warnings[0].data["message"] == "Retrying in 1s"

    def test_get_tool_calls(self, temp_ledger_with_logs: Path) -> None:
        """Test getting all tool call events."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        tool_calls = reader.get_tool_calls()

        assert len(tool_calls) == 1
        assert tool_calls[0].data["tool_name"] == "Read"

    def test_was_successful(self, temp_ledger_with_logs: Path) -> None:
        """Test checking if execution was successful."""
        reader = HarnessLogReader(temp_ledger_with_logs, "cub-test", 1)
        assert reader.was_successful() is True

    def test_was_successful_no_completion(self, tmp_path: Path) -> None:
        """Test was_successful returns None when no completion event."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        writer = HarnessLogWriter(ledger_dir, "cub-test", 1)
        writer.write_start()
        writer.write_status("In progress")
        writer.close()

        reader = HarnessLogReader(ledger_dir, "cub-test", 1)
        assert reader.was_successful() is None

    def test_streaming_large_log(self, tmp_path: Path) -> None:
        """Test streaming works efficiently for large logs."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        # Write a large log file
        writer = HarnessLogWriter(ledger_dir, "cub-test", 1)
        for i in range(1000):
            writer.write_status(f"Processing item {i}")
        writer.close()

        # Read back with streaming (should not load all into memory at once)
        reader = HarnessLogReader(ledger_dir, "cub-test", 1)
        count = 0
        for event in reader.iter_events():
            count += 1
            if count == 10:
                break  # Early termination to demonstrate streaming

        assert count == 10

    def test_invalid_json_lines_skipped(self, tmp_path: Path) -> None:
        """Test that invalid JSON lines are skipped gracefully."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        task_dir = ledger_dir / "by-task" / "cub-test"
        task_dir.mkdir(parents=True)

        # Write log with some invalid lines
        log_file = task_dir / "001-harness.jsonl"
        with log_file.open("w") as f:
            # Valid line
            f.write(
                '{"timestamp": "2026-01-15T10:00:00+00:00", '
                '"event_type": "start", "data": {}}\n'
            )
            # Invalid JSON
            f.write('not valid json\n')
            # Empty line
            f.write('\n')
            # Valid line
            f.write(
                '{"timestamp": "2026-01-15T10:01:00+00:00", '
                '"event_type": "complete", "data": {"success": true}}\n'
            )

        reader = HarnessLogReader(ledger_dir, "cub-test", 1)
        events = reader.read_all()

        # Should only get the 2 valid events
        assert len(events) == 2
        assert events[0].event_type == "start"
        assert events[1].event_type == "complete"


class TestWriterReaderRoundTrip:
    """Tests for writer -> reader round-trip."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """Test writing events and reading them back."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        # Write events
        with HarnessLogWriter(ledger_dir, "cub-abc", 3) as writer:
            writer.write_start(harness="claude", model="opus")
            writer.write_tool_call("Edit", {"file_path": "test.py"}, description="Fix bug")
            writer.write_tool_result("Edit", "success", lines_changed=5)
            writer.write_response("Fixed the bug in test.py")
            writer.write_complete(True, duration_seconds=45, cost_usd=0.08)

        # Read events back
        reader = HarnessLogReader(ledger_dir, "cub-abc", 3)
        events = reader.read_all()

        assert len(events) == 5

        # Verify start event
        assert events[0].event_type == "start"
        assert events[0].data["harness"] == "claude"
        assert events[0].data["model"] == "opus"

        # Verify tool call event
        assert events[1].event_type == "tool_call"
        assert events[1].data["tool_name"] == "Edit"
        assert events[1].data["parameters"]["file_path"] == "test.py"
        assert events[1].data["description"] == "Fix bug"

        # Verify tool result event
        assert events[2].event_type == "tool_result"
        assert events[2].data["tool_name"] == "Edit"
        assert events[2].data["result"] == "success"
        assert events[2].data["lines_changed"] == 5

        # Verify response event
        assert events[3].event_type == "response"
        assert events[3].data["content"] == "Fixed the bug in test.py"

        # Verify completion event
        assert events[4].event_type == "complete"
        assert events[4].data["success"] is True
        assert events[4].data["duration_seconds"] == 45
        assert events[4].data["cost_usd"] == 0.08

        # Verify was_successful
        assert reader.was_successful() is True

    def test_timestamps_preserved(self, tmp_path: Path) -> None:
        """Test that timestamps are preserved in round-trip."""
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        # Create event with specific timestamp
        ts = "2026-01-15T10:30:00+00:00"
        event = HarnessLogEvent(
            timestamp=ts,
            event_type="status",
            data={"message": "test"}
        )

        # Write and read back
        writer = HarnessLogWriter(ledger_dir, "cub-test", 1)
        writer.write_event(event)
        writer.close()

        reader = HarnessLogReader(ledger_dir, "cub-test", 1)
        events = reader.read_all()

        assert len(events) == 1
        assert events[0].timestamp == ts
