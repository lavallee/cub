"""
Harness log writer and reader for JSONL format.

Provides structured logging for harness execution events with streaming
support for large logs. Logs are written to:
.cub/ledger/by-task/{task_id}/{attempt:03d}-harness.jsonl
"""

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, Literal

from pydantic import BaseModel, Field, field_validator


class HarnessLogEvent(BaseModel):
    """Individual harness log event.

    Represents a single event in the harness execution log,
    such as tool calls, responses, errors, or status updates.
    """

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Event timestamp in ISO 8601 format (UTC)"
    )
    event_type: Literal[
        "start",
        "tool_call",
        "tool_result",
        "response",
        "error",
        "warning",
        "status",
        "complete"
    ] = Field(..., description="Type of event")
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data payload"
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate timestamp is ISO 8601 format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError as e:
            raise ValueError(f"Timestamp must be ISO 8601 format, got: {v}") from e

    @classmethod
    def start(cls, **data: Any) -> "HarnessLogEvent":
        """Create a start event."""
        return cls(event_type="start", data=data)

    @classmethod
    def tool_call(
        cls, tool_name: str, parameters: dict[str, Any], **extra: Any
    ) -> "HarnessLogEvent":
        """Create a tool call event."""
        return cls(
            event_type="tool_call",
            data={"tool_name": tool_name, "parameters": parameters, **extra}
        )

    @classmethod
    def tool_result(cls, tool_name: str, result: Any, **extra: Any) -> "HarnessLogEvent":
        """Create a tool result event."""
        return cls(
            event_type="tool_result",
            data={"tool_name": tool_name, "result": result, **extra}
        )

    @classmethod
    def response(cls, content: str, **extra: Any) -> "HarnessLogEvent":
        """Create a response event."""
        return cls(event_type="response", data={"content": content, **extra})

    @classmethod
    def error(cls, error_type: str, message: str, **extra: Any) -> "HarnessLogEvent":
        """Create an error event."""
        return cls(
            event_type="error",
            data={"error_type": error_type, "message": message, **extra}
        )

    @classmethod
    def warning(cls, message: str, **extra: Any) -> "HarnessLogEvent":
        """Create a warning event."""
        return cls(event_type="warning", data={"message": message, **extra})

    @classmethod
    def status(cls, message: str, **extra: Any) -> "HarnessLogEvent":
        """Create a status update event."""
        return cls(event_type="status", data={"message": message, **extra})

    @classmethod
    def complete(cls, success: bool, **data: Any) -> "HarnessLogEvent":
        """Create a completion event."""
        return cls(event_type="complete", data={"success": success, **data})


class HarnessLogWriter:
    """Write harness log events in JSONL format.

    Provides structured logging for harness execution with one JSON object
    per line for easy streaming and parsing.

    Example:
        >>> writer = HarnessLogWriter(Path(".cub/ledger"), "cub-abc", 1)
        >>> writer.write_event(HarnessLogEvent.start(harness="claude", model="sonnet"))
        >>> writer.write_event(HarnessLogEvent.tool_call("Read", {"file_path": "src/main.py"}))
        >>> writer.close()
    """

    def __init__(self, ledger_dir: Path, task_id: str, attempt_number: int) -> None:
        """Initialize harness log writer.

        Args:
            ledger_dir: Path to .cub/ledger directory
            task_id: Task ID (e.g., 'cub-abc')
            attempt_number: Attempt sequence number (1-based)
        """
        self.ledger_dir = ledger_dir
        self.task_id = task_id
        self.attempt_number = attempt_number

        # Create task directory structure
        self.task_dir = ledger_dir / "by-task" / task_id
        self.task_dir.mkdir(parents=True, exist_ok=True)

        # Log file path: by-task/{task_id}/{attempt:03d}-harness.jsonl
        attempt_str = f"{attempt_number:03d}"
        self.log_file = self.task_dir / f"{attempt_str}-harness.jsonl"

        # File handle (opened lazily on first write)
        self._file_handle: IO[str] | None = None

    def write_event(self, event: HarnessLogEvent) -> None:
        """Write a single log event.

        Args:
            event: HarnessLogEvent to write
        """
        # Open file lazily on first write
        if self._file_handle is None:
            self._file_handle = self.log_file.open("a", encoding="utf-8")

        # Write as single line of JSON
        json.dump(event.model_dump(mode="json"), self._file_handle, default=str)
        self._file_handle.write("\n")
        self._file_handle.flush()

    def write_start(self, **data: Any) -> None:
        """Convenience method to write a start event."""
        self.write_event(HarnessLogEvent.start(**data))

    def write_tool_call(self, tool_name: str, parameters: dict[str, Any], **extra: Any) -> None:
        """Convenience method to write a tool call event."""
        self.write_event(HarnessLogEvent.tool_call(tool_name, parameters, **extra))

    def write_tool_result(self, tool_name: str, result: Any, **extra: Any) -> None:
        """Convenience method to write a tool result event."""
        self.write_event(HarnessLogEvent.tool_result(tool_name, result, **extra))

    def write_response(self, content: str, **extra: Any) -> None:
        """Convenience method to write a response event."""
        self.write_event(HarnessLogEvent.response(content, **extra))

    def write_error(self, error_type: str, message: str, **extra: Any) -> None:
        """Convenience method to write an error event."""
        self.write_event(HarnessLogEvent.error(error_type, message, **extra))

    def write_warning(self, message: str, **extra: Any) -> None:
        """Convenience method to write a warning event."""
        self.write_event(HarnessLogEvent.warning(message, **extra))

    def write_status(self, message: str, **extra: Any) -> None:
        """Convenience method to write a status event."""
        self.write_event(HarnessLogEvent.status(message, **extra))

    def write_complete(self, success: bool, **data: Any) -> None:
        """Convenience method to write a completion event."""
        self.write_event(HarnessLogEvent.complete(success, **data))

    def close(self) -> None:
        """Close the log file handle."""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None

    def __enter__(self) -> "HarnessLogWriter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


class HarnessLogReader:
    """Read harness log events from JSONL format.

    Provides streaming access to log events without loading the entire
    file into memory, enabling efficient processing of large logs.

    Example:
        >>> reader = HarnessLogReader(Path(".cub/ledger"), "cub-abc", 1)
        >>> for event in reader.iter_events():
        ...     if event.event_type == "error":
        ...         print(f"Error: {event.data['message']}")
    """

    def __init__(self, ledger_dir: Path, task_id: str, attempt_number: int) -> None:
        """Initialize harness log reader.

        Args:
            ledger_dir: Path to .cub/ledger directory
            task_id: Task ID (e.g., 'cub-abc')
            attempt_number: Attempt sequence number (1-based)
        """
        self.ledger_dir = ledger_dir
        self.task_id = task_id
        self.attempt_number = attempt_number

        # Log file path: by-task/{task_id}/{attempt:03d}-harness.jsonl
        attempt_str = f"{attempt_number:03d}"
        self.log_file = ledger_dir / "by-task" / task_id / f"{attempt_str}-harness.jsonl"

    def exists(self) -> bool:
        """Check if log file exists.

        Returns:
            True if log file exists, False otherwise
        """
        return self.log_file.exists()

    def iter_events(self) -> Iterator[HarnessLogEvent]:
        """Iterate over all log events.

        Yields events one at a time without loading the entire file into memory.

        Yields:
            HarnessLogEvent for each line in the log file

        Raises:
            FileNotFoundError: If log file doesn't exist
        """
        if not self.log_file.exists():
            raise FileNotFoundError(f"Log file not found: {self.log_file}")

        with self.log_file.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    yield HarnessLogEvent.model_validate(data)
                except (json.JSONDecodeError, ValueError):
                    # Skip invalid lines with a warning
                    # (Could add logging here in the future)
                    continue

    def read_all(self) -> list[HarnessLogEvent]:
        """Read all log events into memory.

        Use this for small logs or when you need to process all events at once.
        For large logs, prefer iter_events() for streaming.

        Returns:
            List of all HarnessLogEvent objects

        Raises:
            FileNotFoundError: If log file doesn't exist
        """
        return list(self.iter_events())

    def filter_by_type(self, event_type: str) -> Iterator[HarnessLogEvent]:
        """Filter events by type.

        Args:
            event_type: Event type to filter for (e.g., "error", "tool_call")

        Yields:
            HarnessLogEvent objects matching the specified type
        """
        for event in self.iter_events():
            if event.event_type == event_type:
                yield event

    def get_errors(self) -> list[HarnessLogEvent]:
        """Get all error events.

        Returns:
            List of error events
        """
        return list(self.filter_by_type("error"))

    def get_warnings(self) -> list[HarnessLogEvent]:
        """Get all warning events.

        Returns:
            List of warning events
        """
        return list(self.filter_by_type("warning"))

    def get_tool_calls(self) -> list[HarnessLogEvent]:
        """Get all tool call events.

        Returns:
            List of tool call events
        """
        return list(self.filter_by_type("tool_call"))

    def was_successful(self) -> bool | None:
        """Check if the harness execution was successful.

        Looks for a completion event and returns its success status.

        Returns:
            True if successful, False if failed, None if no completion event found
        """
        for event in self.filter_by_type("complete"):
            success = event.data.get("success", False)
            # Ensure we return bool | None, not Any
            return bool(success) if success is not None else False
        return None
