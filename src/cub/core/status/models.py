"""
Run status models for cub dashboard.

These models represent the real-time state of a cub run and are
serialized to status.json for consumption by the dashboard UI.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from cub.core.harness.models import TokenUsage


class RunPhase(str, Enum):
    """Current phase of a cub run."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class EventLevel(str, Enum):
    """Event log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EventLog(BaseModel):
    """
    A single event in the run history.

    Events track significant occurrences during task execution,
    such as task starts, completions, errors, and state changes.
    """

    timestamp: datetime = Field(default_factory=datetime.now, description="When the event occurred")
    level: EventLevel = Field(default=EventLevel.INFO, description="Event severity level")
    message: str = Field(..., description="Event description")
    task_id: str | None = Field(default=None, description="Associated task ID, if applicable")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")


class IterationInfo(BaseModel):
    """
    Information about current iteration state.

    Tracks progress through the task processing loop.
    """

    current: int = Field(default=0, ge=0, description="Current iteration number")
    max: int = Field(default=100, ge=1, description="Maximum allowed iterations")
    task_iteration: int = Field(default=0, ge=0, description="Current iteration within the task")
    max_task_iteration: int = Field(default=3, ge=1, description="Maximum iterations per task")

    @computed_field
    @property
    def percentage(self) -> float:
        """Percentage of max iterations used (0-100)."""
        if self.max == 0:
            return 0.0
        return (self.current / self.max) * 100

    @computed_field
    @property
    def task_percentage(self) -> float:
        """Percentage of max task iterations used (0-100)."""
        if self.max_task_iteration == 0:
            return 0.0
        return (self.task_iteration / self.max_task_iteration) * 100

    @computed_field
    @property
    def is_near_limit(self) -> bool:
        """Check if approaching iteration limit (>80%)."""
        return self.percentage >= 80.0


class TaskState(str, Enum):
    """State of a task in the Kanban view."""

    TODO = "todo"
    DOING = "doing"
    DONE = "done"


class TaskEntry(BaseModel):
    """
    A task entry for the Kanban-style dashboard view.

    Tracks individual task state and timestamps for display.
    """

    task_id: str = Field(..., description="Task identifier")
    title: str = Field(default="", description="Task title")
    state: TaskState = Field(default=TaskState.TODO, description="Current task state")
    started_at: datetime | None = Field(default=None, description="When task was started")
    completed_at: datetime | None = Field(default=None, description="When task was completed")


class BudgetStatus(BaseModel):
    """
    Token and cost budget tracking.

    Monitors spending during autonomous execution.
    """

    tokens_used: int = Field(default=0, ge=0, description="Total tokens consumed")
    tokens_limit: int | None = Field(default=None, ge=1, description="Maximum allowed tokens")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost in USD")
    cost_limit: float | None = Field(
        default=None, ge=0.0, description="Maximum allowed cost in USD"
    )
    tasks_completed: int = Field(default=0, ge=0, description="Number of tasks completed")
    tasks_limit: int | None = Field(default=None, ge=1, description="Maximum tasks per session")

    @computed_field
    @property
    def tokens_percentage(self) -> float | None:
        """Percentage of token budget used (0-100), or None if no limit."""
        if self.tokens_limit is None or self.tokens_limit == 0:
            return None
        return (self.tokens_used / self.tokens_limit) * 100

    @computed_field
    @property
    def cost_percentage(self) -> float | None:
        """Percentage of cost budget used (0-100), or None if no limit."""
        if self.cost_limit is None or self.cost_limit == 0:
            return None
        return (self.cost_usd / self.cost_limit) * 100

    @computed_field
    @property
    def tasks_percentage(self) -> float | None:
        """Percentage of task limit used (0-100), or None if no limit."""
        if self.tasks_limit is None or self.tasks_limit == 0:
            return None
        return (self.tasks_completed / self.tasks_limit) * 100

    @computed_field
    @property
    def is_over_budget(self) -> bool:
        """Check if any budget limit has been exceeded."""
        if self.tokens_limit and self.tokens_used >= self.tokens_limit:
            return True
        if self.cost_limit and self.cost_usd >= self.cost_limit:
            return True
        if self.tasks_limit and self.tasks_completed >= self.tasks_limit:
            return True
        return False


class RunArtifact(BaseModel):
    """
    Run artifact metadata for run.json files.

    Represents the schema of run.json files stored in
    .cub/runs/{run_id}/run.json. This model captures run-level
    metadata, aggregate budget totals, and completion statistics
    that persist after runs complete.

    Example:
        >>> artifact = RunArtifact(
        ...     run_id="camel-20260114-231701",
        ...     session_name="camel",
        ...     started_at=datetime.now(),
        ...     status="completed"
        ... )
        >>> artifact.run_id
        'camel-20260114-231701'
    """

    run_id: str = Field(..., description="Unique run identifier")
    session_name: str = Field(default="default", description="Session/branch name")
    started_at: datetime = Field(default_factory=datetime.now, description="When the run started")
    completed_at: datetime | None = Field(default=None, description="When the run completed")
    status: str = Field(default="in_progress", description="Run status (e.g., 'in_progress', 'completed', 'failed')")
    config: dict[str, Any] = Field(default_factory=dict, description="Configuration snapshot")
    tasks_completed: int = Field(default=0, ge=0, description="Number of tasks completed")
    tasks_failed: int = Field(default=0, ge=0, description="Number of tasks failed")
    budget: BudgetStatus | None = Field(default=None, description="Aggregate budget totals")

    model_config = ConfigDict(
        validate_assignment=True,
    )


class TaskArtifact(BaseModel):
    """
    Task artifact metadata for task.json files.

    Represents the schema of task.json files stored in
    .cub/runs/{run_id}/tasks/{task_id}/task.json. This model
    captures task execution state, timing, and cost data that
    persists after runs complete.

    Example:
        >>> artifact = TaskArtifact(
        ...     task_id="cub-001",
        ...     title="Implement feature X",
        ...     status="completed",
        ...     iterations=1
        ... )
        >>> artifact.task_id
        'cub-001'
    """

    task_id: str = Field(..., description="Task identifier")
    title: str = Field(default="", description="Task title/description")
    priority: str = Field(default="normal", description="Task priority (e.g., 'normal', 'high')")
    status: str = Field(default="in_progress", description="Task status (e.g., 'in_progress', 'completed', 'failed')")
    started_at: datetime | None = Field(default=None, description="When task execution started")
    completed_at: datetime | None = Field(default=None, description="When task execution completed")
    iterations: int = Field(default=0, ge=0, description="Number of iterations completed")
    exit_code: int | None = Field(default=None, description="Exit code from task execution")
    usage: TokenUsage | None = Field(default=None, description="Token usage and cost data")
    duration_seconds: float | None = Field(default=None, ge=0.0, description="Task execution duration in seconds")

    model_config = ConfigDict(
        validate_assignment=True,
    )


class RunStatus(BaseModel):
    """
    Current status of a cub run.

    This is the top-level model serialized to status.json for
    real-time monitoring via the dashboard. It captures all
    relevant state needed to display run progress.

    Example:
        >>> status = RunStatus(
        ...     run_id="camel-20260114-231701",
        ...     phase=RunPhase.RUNNING,
        ...     current_task_id="cub-054",
        ...     current_task_title="Create Pydantic models"
        ... )
        >>> status.phase
        <RunPhase.RUNNING: 'running'>
        >>> status.is_active
        True
    """

    # Run identification
    run_id: str = Field(..., description="Unique run identifier")
    session_name: str = Field(default="default", description="Session/branch name")
    started_at: datetime = Field(default_factory=datetime.now, description="When the run started")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last status update time"
    )
    completed_at: datetime | None = Field(
        default=None, description="When the run completed/failed/stopped"
    )

    # Run context (display parameters)
    epic: str | None = Field(default=None, description="Epic filter for this run")
    label: str | None = Field(default=None, description="Label filter for this run")
    branch: str | None = Field(default=None, description="Git branch for this run")

    # Current state
    phase: RunPhase = Field(default=RunPhase.INITIALIZING, description="Current run phase")
    current_task_id: str | None = Field(default=None, description="ID of currently executing task")
    current_task_title: str | None = Field(
        default=None, description="Title of currently executing task"
    )

    # Progress tracking
    iteration: IterationInfo = Field(default_factory=IterationInfo, description="Iteration state")
    budget: BudgetStatus = Field(default_factory=BudgetStatus, description="Budget tracking")

    # Task statistics
    tasks_open: int = Field(default=0, ge=0, description="Open tasks remaining")
    tasks_in_progress: int = Field(default=0, ge=0, description="Tasks currently in progress")
    tasks_closed: int = Field(default=0, ge=0, description="Tasks completed")
    tasks_total: int = Field(default=0, ge=0, description="Total number of tasks")

    # Task list for Kanban view
    task_entries: list[TaskEntry] = Field(
        default_factory=list, description="Task entries for Kanban display"
    )

    # Event history
    events: list[EventLog] = Field(default_factory=list, description="Chronological event log")

    # Error tracking
    last_error: str | None = Field(default=None, description="Most recent error message, if any")

    model_config = ConfigDict(
        validate_assignment=True,
    )

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if run is currently active."""
        return self.phase in (RunPhase.INITIALIZING, RunPhase.RUNNING)

    @computed_field
    @property
    def is_finished(self) -> bool:
        """Check if run has finished (completed, failed, or stopped)."""
        return self.phase in (RunPhase.COMPLETED, RunPhase.FAILED, RunPhase.STOPPED)

    @computed_field
    @property
    def tasks_remaining(self) -> int:
        """Number of non-closed tasks."""
        return self.tasks_open + self.tasks_in_progress

    @computed_field
    @property
    def completion_percentage(self) -> float:
        """Task completion percentage (0-100)."""
        if self.tasks_total == 0:
            return 0.0
        return (self.tasks_closed / self.tasks_total) * 100

    @computed_field
    @property
    def duration_seconds(self) -> float:
        """Run duration in seconds."""
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()

    def add_event(
        self,
        message: str,
        level: EventLevel = EventLevel.INFO,
        task_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Add an event to the event log."""
        event = EventLog(message=message, level=level, task_id=task_id, metadata=metadata)
        self.events.append(event)
        self.updated_at = datetime.now()

    def mark_completed(self) -> None:
        """Mark run as completed."""
        self.phase = RunPhase.COMPLETED
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()
        self.add_event("Run completed successfully", EventLevel.INFO)

    def mark_failed(self, error: str) -> None:
        """Mark run as failed with error message."""
        self.phase = RunPhase.FAILED
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()
        self.last_error = error
        self.add_event(f"Run failed: {error}", EventLevel.ERROR)

    def mark_stopped(self) -> None:
        """Mark run as stopped by user."""
        self.phase = RunPhase.STOPPED
        self.completed_at = datetime.now()
        self.updated_at = datetime.now()
        self.add_event("Run stopped by user", EventLevel.INFO)

    def set_task_entries(self, tasks: list[tuple[str, str]]) -> None:
        """
        Initialize task entries from a list of (task_id, title) tuples.

        Args:
            tasks: List of (task_id, title) tuples to initialize
        """
        self.task_entries = [
            TaskEntry(task_id=task_id, title=title, state=TaskState.TODO)
            for task_id, title in tasks
        ]
        self.updated_at = datetime.now()

    def start_task_entry(self, task_id: str) -> None:
        """
        Mark a task entry as started (DOING state).

        Args:
            task_id: Task ID to mark as started
        """
        for entry in self.task_entries:
            if entry.task_id == task_id:
                entry.state = TaskState.DOING
                entry.started_at = datetime.now()
                break
        self.updated_at = datetime.now()

    def complete_task_entry(self, task_id: str) -> None:
        """
        Mark a task entry as completed (DONE state).

        Args:
            task_id: Task ID to mark as completed
        """
        for entry in self.task_entries:
            if entry.task_id == task_id:
                entry.state = TaskState.DONE
                entry.completed_at = datetime.now()
                break
        self.updated_at = datetime.now()

    def get_tasks_by_state(self, state: TaskState) -> list[TaskEntry]:
        """
        Get all task entries with the given state.

        Args:
            state: TaskState to filter by

        Returns:
            List of TaskEntry objects with the specified state
        """
        return [entry for entry in self.task_entries if entry.state == state]
