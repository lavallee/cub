"""
Data models for the suggestion system.

Defines the Suggestion model and related types used to represent
smart action recommendations based on project state analysis.
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SuggestionCategory(str, Enum):
    """Categories of suggestions that can be made.

    These categories help organize and prioritize suggestions
    based on the type of action being recommended.
    """

    TASK = "task"  # Suggest working on a specific task
    REVIEW = "review"  # Suggest reviewing completed work
    MILESTONE = "milestone"  # Suggest milestone-related actions
    GIT = "git"  # Suggest git operations (commit, push, PR, etc.)
    CLEANUP = "cleanup"  # Suggest maintenance or cleanup actions
    PLAN = "plan"  # Suggest planning or architecture work

    @property
    def emoji(self) -> str:
        """Get emoji icon for this category."""
        return {
            SuggestionCategory.TASK: "📋",
            SuggestionCategory.REVIEW: "🔍",
            SuggestionCategory.MILESTONE: "🎯",
            SuggestionCategory.GIT: "🌿",
            SuggestionCategory.CLEANUP: "🧹",
            SuggestionCategory.PLAN: "📐",
        }[self]


class Suggestion(BaseModel):
    """A suggested action with rationale and context.

    Represents a concrete recommendation for what the user should
    do next, with scoring and explanation to help prioritization.

    Example:
        >>> suggestion = Suggestion(
        ...     category=SuggestionCategory.TASK,
        ...     title="Work on task cub-b1d.2",
        ...     description="Implement the suggestion ranking engine",
        ...     rationale="This task is ready and continues work on suggestions",
        ...     priority_score=0.85,
        ...     action="cub task claim cub-b1d.2 && cub run --task cub-b1d.2"
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )

    # Core fields
    category: SuggestionCategory = Field(
        ...,
        description="Category of suggestion (task, review, git, etc.)"
    )
    title: str = Field(
        ...,
        min_length=1,
        description="Short title summarizing the suggestion"
    )
    description: str = Field(
        default="",
        description="Detailed description of what should be done"
    )
    rationale: str = Field(
        ...,
        min_length=1,
        description="Explanation of why this action is suggested"
    )

    # Scoring and priority
    priority_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Priority score from 0.0-1.0 (higher = more important)"
    )

    # Action details
    action: str | None = Field(
        default=None,
        description="Specific command or action to execute (optional)"
    )

    # Metadata
    source: str = Field(
        default="unknown",
        description="Which data source generated this suggestion"
    )
    context: dict[str, str | int | float | bool | list[str] | None] = Field(
        default_factory=dict,
        description="Additional context data (task IDs, file paths, etc.)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this suggestion was created (UTC)"
    )

    @field_validator("priority_score")
    @classmethod
    def validate_priority_score(cls, v: float) -> float:
        """Ensure priority score is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Priority score must be between 0.0 and 1.0, got {v}")
        return v

    @property
    def formatted_title(self) -> str:
        """Get title with category emoji prefix."""
        return f"{self.category.emoji} {self.title}"

    @property
    def urgency_level(self) -> str:
        """Get urgency level based on priority score."""
        if self.priority_score >= 0.8:
            return "urgent"
        elif self.priority_score >= 0.6:
            return "high"
        elif self.priority_score >= 0.4:
            return "medium"
        else:
            return "low"


class ProjectSnapshot(BaseModel):
    """Snapshot of project state for suggestion generation.

    Aggregates data from multiple sources (tasks, git, ledger, milestones)
    to provide context for generating suggestions.

    This model is used as input to the ranking engine to decide
    which suggestions are most relevant.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )

    # Task state
    total_tasks: int = Field(default=0, ge=0, description="Total number of tasks")
    open_tasks: int = Field(default=0, ge=0, description="Number of open tasks")
    in_progress_tasks: int = Field(default=0, ge=0, description="Number of in-progress tasks")
    closed_tasks: int = Field(default=0, ge=0, description="Number of closed tasks")
    ready_tasks: int = Field(default=0, ge=0, description="Number of ready tasks (no blockers)")
    blocked_tasks: int = Field(default=0, ge=0, description="Number of blocked tasks")

    # Git state
    current_branch: str | None = Field(default=None, description="Current git branch")
    has_uncommitted_changes: bool = Field(
        default=False,
        description="Whether there are uncommitted changes"
    )
    commits_since_main: int = Field(
        default=0,
        ge=0,
        description="Number of commits ahead of main/master"
    )
    recent_commits: int = Field(
        default=0,
        ge=0,
        description="Number of commits in last 24 hours"
    )

    # Ledger state
    tasks_in_ledger: int = Field(
        default=0,
        ge=0,
        description="Number of completed tasks in ledger"
    )
    unreviewed_tasks: int = Field(
        default=0,
        ge=0,
        description="Number of completed tasks needing review"
    )
    failed_verifications: int = Field(
        default=0,
        ge=0,
        description="Number of tasks with failed verification"
    )
    total_cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Total cost of completed work (USD)"
    )

    # Milestone state
    total_milestones: int = Field(default=0, ge=0, description="Total number of milestones")
    active_milestones: int = Field(default=0, ge=0, description="Number of active milestones")
    completed_milestones: int = Field(
        default=0,
        ge=0,
        description="Number of completed milestones"
    )
    milestone_progress: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall milestone completion percentage"
    )

    # Temporal context
    snapshot_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this snapshot was taken (UTC)"
    )

    @property
    def completion_percentage(self) -> float:
        """Calculate overall task completion percentage."""
        if self.total_tasks == 0:
            return 0.0
        return (self.closed_tasks / self.total_tasks) * 100.0

    @property
    def work_in_progress(self) -> bool:
        """Check if there is active work in progress."""
        return self.in_progress_tasks > 0 or self.has_uncommitted_changes

    @property
    def needs_attention(self) -> bool:
        """Check if there are issues requiring attention."""
        return (
            self.failed_verifications > 0
            or self.unreviewed_tasks > 0
            or self.blocked_tasks > 0
        )
