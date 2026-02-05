"""
Session data models for cub.

Defines Pydantic models for run session tracking that monitors active
`cub run` executions. These models support the unified tracking system
that captures task execution history, costs, and progress.
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def generate_run_id() -> str:
    """
    Generate a unique run ID with timestamp format.

    Format: cub-YYYYMMDD-HHMMSS (e.g., 'cub-20260124-143022')

    Returns:
        Unique run ID string based on current UTC time
    """
    now = datetime.now(timezone.utc)
    return now.strftime("cub-%Y%m%d-%H%M%S")


class SessionStatus(str, Enum):
    """Status of a run session.

    - RUNNING: Session is currently active
    - COMPLETED: Session finished normally
    - ORPHANED: Session was abandoned (process died, crash, etc.)
    """

    RUNNING = "running"
    COMPLETED = "completed"
    ORPHANED = "orphaned"

    @property
    def is_active(self) -> bool:
        """Check if session is currently running."""
        return self == SessionStatus.RUNNING

    @property
    def is_terminal(self) -> bool:
        """Check if session has finished (completed or orphaned)."""
        return self in (SessionStatus.COMPLETED, SessionStatus.ORPHANED)


class SessionBudget(BaseModel):
    """
    Budget tracking for a run session.

    Tracks token usage and cost limits/consumption during execution.
    Supports both token-based and cost-based budgets.
    """

    tokens_used: int = Field(default=0, ge=0, description="Tokens consumed so far")
    tokens_limit: int = Field(default=0, ge=0, description="Maximum tokens allowed (0 = unlimited)")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost in USD")
    cost_limit: float = Field(
        default=0.0, ge=0.0, description="Maximum cost allowed (0.0 = unlimited)"
    )

    @property
    def tokens_remaining(self) -> int:
        """Calculate remaining token budget."""
        if self.tokens_limit == 0:
            return -1  # Unlimited
        return max(0, self.tokens_limit - self.tokens_used)

    @property
    def cost_remaining(self) -> float:
        """Calculate remaining cost budget."""
        if self.cost_limit == 0.0:
            return -1.0  # Unlimited
        return max(0.0, self.cost_limit - self.cost_usd)

    @property
    def is_tokens_exceeded(self) -> bool:
        """Check if token budget has been exceeded."""
        if self.tokens_limit == 0:
            return False
        return self.tokens_used >= self.tokens_limit

    @property
    def is_cost_exceeded(self) -> bool:
        """Check if cost budget has been exceeded."""
        if self.cost_limit == 0.0:
            return False
        return self.cost_usd >= self.cost_limit

    @property
    def is_exceeded(self) -> bool:
        """Check if any budget limit has been exceeded."""
        return self.is_tokens_exceeded or self.is_cost_exceeded

    @property
    def tokens_utilization(self) -> float:
        """Calculate token budget utilization percentage (0.0-1.0, or -1.0 for unlimited)."""
        if self.tokens_limit == 0:
            return -1.0
        return self.tokens_used / self.tokens_limit

    @property
    def cost_utilization(self) -> float:
        """Calculate cost budget utilization percentage (0.0-1.0, or -1.0 for unlimited)."""
        if self.cost_limit == 0.0:
            return -1.0
        return self.cost_usd / self.cost_limit


class RunSession(BaseModel):
    """
    Run session state for an active or completed `cub run` execution.

    Tracks the full lifecycle of a run including budget consumption,
    task progress, and session status. Stored in .cub/ledger/by-run/
    directory structure.

    Example:
        >>> session = RunSession(
        ...     run_id="cub-20260124-143022",
        ...     started_at=datetime.now(timezone.utc),
        ...     project_dir=Path.cwd(),
        ...     harness="claude",
        ...     budget=SessionBudget(tokens_limit=100000, cost_limit=1.0)
        ... )
        >>> session.status
        <SessionStatus.RUNNING: 'running'>
        >>> session.tasks_total
        0
    """

    # Core identification
    run_id: str = Field(
        ...,
        description="Unique run identifier (format: cub-YYYYMMDD-HHMMSS)",
        pattern=r"^cub-\d{8}-\d{6}$",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the run session started (UTC)",
    )

    # Project context
    project_dir: Path = Field(..., description="Absolute path to project directory")
    harness: str = Field(..., min_length=1, description="Harness name (e.g., 'claude', 'codex')")

    # Budget tracking
    budget: SessionBudget = Field(
        default_factory=SessionBudget, description="Token and cost budget tracking"
    )

    # Task progress
    tasks_completed: int = Field(default=0, ge=0, description="Number of tasks completed")
    tasks_failed: int = Field(default=0, ge=0, description="Number of tasks failed")
    current_task: str | None = Field(default=None, description="Currently executing task ID")

    # Session status
    status: SessionStatus = Field(
        default=SessionStatus.RUNNING, description="Current session status"
    )
    ended_at: datetime | None = Field(default=None, description="When the session ended (UTC)")
    orphaned_at: datetime | None = Field(
        default=None, description="When orphan was detected (UTC)"
    )
    orphaned_reason: str | None = Field(
        default=None, description="Reason for orphan status (process died, crash, etc.)"
    )

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    @property
    def tasks_total(self) -> int:
        """Calculate total tasks attempted (completed + failed)."""
        return self.tasks_completed + self.tasks_failed

    @property
    def duration_seconds(self) -> int:
        """Calculate session duration in seconds."""
        end_time = self.ended_at or datetime.now(timezone.utc)
        return int((end_time - self.started_at).total_seconds())

    @property
    def duration_minutes(self) -> float:
        """Calculate session duration in minutes."""
        return self.duration_seconds / 60.0

    @property
    def duration_hours(self) -> float:
        """Calculate session duration in hours."""
        return self.duration_seconds / 3600.0

    @property
    def is_active(self) -> bool:
        """Check if session is currently running."""
        return self.status.is_active

    @property
    def is_completed(self) -> bool:
        """Check if session finished normally."""
        return self.status == SessionStatus.COMPLETED

    @property
    def is_orphaned(self) -> bool:
        """Check if session was abandoned."""
        return self.status == SessionStatus.ORPHANED

    @property
    def success_rate(self) -> float:
        """Calculate task success rate (0.0-1.0)."""
        if self.tasks_total == 0:
            return 0.0
        return self.tasks_completed / self.tasks_total

    @property
    def average_cost_per_task(self) -> float:
        """Calculate average cost per completed task."""
        if self.tasks_completed == 0:
            return 0.0
        return self.budget.cost_usd / self.tasks_completed

    def mark_completed(self) -> None:
        """Mark session as completed normally."""
        self.status = SessionStatus.COMPLETED
        self.ended_at = datetime.now(timezone.utc)

    def mark_orphaned(self, reason: str) -> None:
        """Mark session as orphaned with reason.

        Args:
            reason: Explanation for why session was orphaned
        """
        self.status = SessionStatus.ORPHANED
        self.orphaned_at = datetime.now(timezone.utc)
        self.orphaned_reason = reason
        if self.ended_at is None:
            self.ended_at = self.orphaned_at
