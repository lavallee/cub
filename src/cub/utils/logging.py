"""
Structured JSONL logging for cub.

Provides a CubLogger class that writes timestamped JSON Lines events for
debugging and analytics. Events are written to ~/.local/share/cub/logs/{project}/{session}.jsonl

Each log line is valid JSON with the format:
{
  "timestamp": "2026-01-15T12:34:56.789Z",
  "event_type": "task_start",
  "data": { ... event-specific data ... }
}
"""

import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """Types of events that can be logged."""

    TASK_START = "task_start"
    TASK_END = "task_end"
    LOOP_START = "loop_start"
    LOOP_END = "loop_end"
    BUDGET_WARNING = "budget_warning"
    ERROR = "error"


class LogEntry(BaseModel):
    """A single structured log entry in JSONL format."""

    model_config = ConfigDict(use_enum_values=True)

    timestamp: datetime = Field(..., description="When the event occurred (ISO 8601 format)")
    event_type: EventType = Field(..., description="Type of event")
    data: dict[str, Any] = Field(default_factory=dict, description="Event-specific data")


class CubLogger:
    """
    Structured JSONL logger for cub events.

    Writes timestamped JSON Lines to ~/.local/share/cub/logs/{project}/{session}.jsonl
    Each line is valid JSON that can be queried with jq.

    Example:
        logger = CubLogger.init("my_project", "session-123")
        logger.log_event(EventType.TASK_START, {"task_id": "cub-001"})
        logger.log_event(EventType.TASK_END, {"task_id": "cub-001", "exit_code": 0})
    """

    def __init__(self, log_file: Path):
        """
        Initialize logger with a log file path.

        Args:
            log_file: Path to the JSONL log file (will be created if needed)
        """
        self.log_file = Path(log_file)
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        """Create log directory if it doesn't exist."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def init(project_name: str, session_id: str) -> "CubLogger":
        """
        Initialize a logger for a project session.

        Logs are written to ~/.local/share/cub/logs/{project_name}/{session_id}.jsonl

        Args:
            project_name: Name of the project (used for directory)
            session_id: Unique session identifier (used for filename)

        Returns:
            CubLogger instance ready to log events

        Raises:
            ValueError: If project_name or session_id are empty
        """
        if not project_name:
            raise ValueError("project_name cannot be empty")
        if not session_id:
            raise ValueError("session_id cannot be empty")

        # Get XDG data home directory
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if not xdg_data_home:
            xdg_data_home = os.path.expanduser("~/.local/share")

        log_dir = Path(xdg_data_home) / "cub" / "logs" / project_name
        log_file = log_dir / f"{session_id}.jsonl"

        return CubLogger(log_file)

    def log_event(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        """
        Write a log event to the JSONL file.

        Args:
            event_type: Type of event (from EventType enum)
            data: Event-specific data (optional, defaults to {})

        Raises:
            IOError: If unable to write to log file
            ValueError: If data is not serializable to JSON
        """
        if data is None:
            data = {}

        try:
            # Create log entry with current timestamp
            entry = LogEntry(timestamp=datetime.now(timezone.utc), event_type=event_type, data=data)

            # Serialize to JSON using pydantic's model_dump_json
            log_line = entry.model_dump_json(exclude_none=True, by_alias=False) + "\n"

            # Write to log file in append mode
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_line)

        except OSError as e:
            # Gracefully handle write errors
            # In production, we might want to log this somewhere, but
            # we avoid raising to prevent logging from blocking execution
            print(f"Warning: Failed to write to log file {self.log_file}: {e}", flush=True)

    def log_task_start(self, task_id: str, task_title: str, harness: str) -> None:
        """
        Log the start of a task.

        Args:
            task_id: Unique task identifier (e.g., "cub-123")
            task_title: Human-readable task title
            harness: Harness being used (e.g., "claude", "codex")
        """
        self.log_event(
            EventType.TASK_START, {"task_id": task_id, "task_title": task_title, "harness": harness}
        )

    def log_task_end(
        self,
        task_id: str,
        exit_code: int,
        duration_sec: float,
        tokens_used: int = 0,
        budget_remaining: int | None = None,
        budget_total: int | None = None,
    ) -> None:
        """
        Log the end of a task.

        Args:
            task_id: Unique task identifier
            exit_code: Exit code from task execution
            duration_sec: Duration in seconds
            tokens_used: Number of tokens used (optional, defaults to 0)
            budget_remaining: Remaining budget tokens (optional)
            budget_total: Total budget tokens (optional)
        """
        data = {
            "task_id": task_id,
            "exit_code": exit_code,
            "duration_sec": duration_sec,
            "tokens_used": tokens_used,
        }

        if budget_remaining is not None:
            data["budget_remaining"] = budget_remaining
        if budget_total is not None:
            data["budget_total"] = budget_total

        self.log_event(EventType.TASK_END, data)

    def log_loop_start(self, iteration: int) -> None:
        """
        Log the start of a processing loop.

        Args:
            iteration: Loop iteration number
        """
        self.log_event(EventType.LOOP_START, {"iteration": iteration})

    def log_loop_end(self, iteration: int, tasks_processed: int, duration_sec: float) -> None:
        """
        Log the end of a processing loop.

        Args:
            iteration: Loop iteration number
            tasks_processed: Number of tasks processed in this iteration
            duration_sec: Duration in seconds
        """
        self.log_event(
            EventType.LOOP_END,
            {
                "iteration": iteration,
                "tasks_processed": tasks_processed,
                "duration_sec": duration_sec,
            },
        )

    def log_budget_warning(self, remaining: int, threshold: int, total: int) -> None:
        """
        Log a budget warning.

        Args:
            remaining: Remaining budget tokens
            threshold: Warning threshold
            total: Total budget tokens
        """
        self.log_event(
            EventType.BUDGET_WARNING,
            {
                "remaining": remaining,
                "threshold": threshold,
                "total": total,
                "percentage_remaining": round(100 * remaining / total, 1) if total > 0 else 0,
            },
        )

    def log_error(self, message: str, context: dict[str, Any] | None = None) -> None:
        """
        Log an error event.

        Args:
            message: Error message
            context: Additional error context (optional)
        """
        data: dict[str, Any] = {"message": message}
        if context:
            data["context"] = context

        self.log_event(EventType.ERROR, data)

    def get_log_file(self) -> Path:
        """Get the path to the log file."""
        return self.log_file
