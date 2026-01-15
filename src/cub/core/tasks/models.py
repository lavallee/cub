"""
Task data models for cub.

Defines the core Task model and related enums that represent tasks
from both beads and JSON backends. These models replace the ad-hoc
JSON parsing in Bash with type-safe, validated Pydantic models.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class TaskStatus(str, Enum):
    """Task status values.

    These match the status values used in both beads and prd.json.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class TaskPriority(str, Enum):
    """Task priority levels.

    P0 = Critical (highest priority)
    P1 = High
    P2 = Medium (default)
    P3 = Low
    P4 = Backlog (lowest priority)
    """

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

    @property
    def numeric_value(self) -> int:
        """Get numeric value for sorting (0 = highest priority)."""
        return int(self.value[1])


class TaskType(str, Enum):
    """Task type/issue type values."""

    TASK = "task"
    FEATURE = "feature"
    BUG = "bug"
    BUGFIX = "bugfix"
    EPIC = "epic"
    GATE = "gate"


class Task(BaseModel):
    """
    A task in the cub system.

    This model represents tasks from both beads (.beads/issues.jsonl)
    and JSON (prd.json) backends. It provides validation, serialization,
    and convenient access to task properties.

    Example:
        >>> task = Task(
        ...     id="cub-001",
        ...     title="Implement feature X",
        ...     status=TaskStatus.OPEN,
        ...     priority=TaskPriority.P2,
        ...     type=TaskType.TASK
        ... )
        >>> task.model_label
        None
        >>> task_with_label = Task(
        ...     id="cub-002",
        ...     title="Use Sonnet",
        ...     labels=["model:sonnet"]
        ... )
        >>> task_with_label.model_label
        'sonnet'
    """

    # Required fields
    id: str = Field(..., description="Unique task identifier (e.g., 'cub-001' or 'prd-abc4')")
    title: str = Field(..., min_length=1, description="Task title")
    status: TaskStatus = Field(default=TaskStatus.OPEN, description="Current task status")

    # Common fields with defaults
    priority: TaskPriority = Field(default=TaskPriority.P2, description="Task priority level")
    type: TaskType = Field(default=TaskType.TASK, description="Task type", alias="issue_type")
    description: str = Field(
        default="", description="Detailed task description (may contain markdown)"
    )

    # Optional metadata
    assignee: str | None = Field(default=None, description="Assigned user or session name")
    labels: list[str] = Field(default_factory=list, description="Task labels/tags")

    # Dependencies
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of task IDs that must be completed before this task",
        alias="dependsOn",
    )
    blocks: list[str] = Field(
        default_factory=list, description="List of task IDs that this task blocks"
    )

    # Parent-child relationships (for epics)
    parent: str | None = Field(default=None, description="Parent epic/task ID")

    # Timestamps
    created_at: datetime | None = Field(default=None, description="When the task was created")
    updated_at: datetime | None = Field(
        default=None, description="When the task was last updated"
    )
    closed_at: datetime | None = Field(default=None, description="When the task was closed")

    # Acceptance criteria
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="List of acceptance criteria (parsed from description or explicit field)",
        alias="acceptanceCriteria",
    )

    # Notes/comments
    notes: str = Field(default="", description="Additional notes or comments")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'depends_on' and 'dependsOn'
    )

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, v: int | str | TaskPriority) -> TaskPriority:
        """Convert numeric priority (0-4) to TaskPriority enum."""
        if isinstance(v, TaskPriority):
            return v
        if isinstance(v, int):
            return TaskPriority(f"P{v}")
        if isinstance(v, str):
            # Handle both "P0" and "0"
            if v.startswith("P"):
                return TaskPriority(v)
            else:
                return TaskPriority(f"P{v}")
        return v

    @computed_field
    @property
    def model_label(self) -> str | None:
        """
        Extract model name from labels.

        Looks for labels matching pattern "model:X" and returns X.
        Used to identify which AI model should be used for this task.

        Returns:
            Model name (e.g., "sonnet", "haiku") or None if no model label found
        """
        for label in self.labels:
            if label.startswith("model:"):
                return label.split(":", 1)[1]
        return None

    @computed_field
    @property
    def is_ready(self) -> bool:
        """
        Check if task is ready to be worked on.

        A task is ready if:
        - Status is OPEN
        - Has no dependencies, OR all dependencies are complete

        Note: This doesn't check if dependencies actually exist,
        only looks at the depends_on list. Use with a task backend
        to properly validate dependencies.

        Returns:
            True if task can be started
        """
        return self.status == TaskStatus.OPEN and len(self.depends_on) == 0

    @computed_field
    @property
    def priority_numeric(self) -> int:
        """Get numeric priority for sorting (0 = highest priority)."""
        if isinstance(self.priority, str):
            # When serialized, priority becomes a string
            return int(self.priority[1])
        return self.priority.numeric_value

    def has_label(self, label: str) -> bool:
        """Check if task has a specific label."""
        return label in self.labels

    def add_label(self, label: str) -> None:
        """Add a label if not already present."""
        if label not in self.labels:
            self.labels.append(label)

    def remove_label(self, label: str) -> None:
        """Remove a label if present."""
        if label in self.labels:
            self.labels.remove(label)

    def mark_in_progress(self, assignee: str | None = None) -> None:
        """Mark task as in progress, optionally setting assignee."""
        self.status = TaskStatus.IN_PROGRESS
        if assignee:
            self.assignee = assignee
        self.updated_at = datetime.now()

    def close(self) -> None:
        """Mark task as closed."""
        self.status = TaskStatus.CLOSED
        self.closed_at = datetime.now()
        self.updated_at = datetime.now()

    def reopen(self) -> None:
        """Reopen a closed task."""
        self.status = TaskStatus.OPEN
        self.closed_at = None
        self.updated_at = datetime.now()


class TaskCounts(BaseModel):
    """
    Task count statistics.

    Used for displaying project health and progress.
    """

    total: int = Field(default=0, description="Total number of tasks")
    open: int = Field(default=0, description="Number of open tasks")
    in_progress: int = Field(default=0, description="Number of in-progress tasks")
    closed: int = Field(default=0, description="Number of closed tasks")

    @computed_field
    @property
    def remaining(self) -> int:
        """Number of non-closed tasks."""
        return self.open + self.in_progress

    @computed_field
    @property
    def completion_percentage(self) -> float:
        """Percentage of tasks completed (0-100)."""
        if self.total == 0:
            return 0.0
        return (self.closed / self.total) * 100
