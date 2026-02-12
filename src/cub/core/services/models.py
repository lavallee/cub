"""
Service layer data models.

Defines Pydantic models used across service layer for inputs/outputs.
These models provide a clean API surface for all cub interfaces.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectStats(BaseModel):
    """Aggregate project statistics from tasks, ledger, and git.

    Combines data from multiple sources to provide a comprehensive
    view of project state.
    """

    # Task counts
    total_tasks: int = Field(default=0, ge=0, description="Total tasks in project")
    open_tasks: int = Field(default=0, ge=0, description="Open tasks")
    in_progress_tasks: int = Field(default=0, ge=0, description="In-progress tasks")
    retry_tasks: int = Field(default=0, ge=0, description="Tasks awaiting retry")
    closed_tasks: int = Field(default=0, ge=0, description="Closed tasks")
    ready_tasks: int = Field(default=0, ge=0, description="Tasks ready to work (no blockers)")
    blocked_tasks: int = Field(default=0, ge=0, description="Tasks blocked by dependencies")

    # Epic counts
    total_epics: int = Field(default=0, ge=0, description="Total epics")
    active_epics: int = Field(default=0, ge=0, description="Epics with open tasks")

    # Completion metrics
    completion_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percentage of tasks completed"
    )

    # Ledger metrics (if ledger exists)
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost from ledger")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    tasks_in_ledger: int = Field(default=0, ge=0, description="Tasks with ledger entries")

    # Git metrics
    current_branch: str = Field(default="", description="Current git branch")
    has_uncommitted_changes: bool = Field(
        default=False, description="Whether working directory has uncommitted changes"
    )
    commits_since_main: int = Field(
        default=0, ge=0, description="Number of commits ahead of main/master"
    )


class EpicProgress(BaseModel):
    """Progress tracking for a specific epic.

    Aggregates task completion and cost data for an epic and its children.
    """

    # Epic identification
    epic_id: str = Field(..., description="Epic ID")
    epic_title: str = Field(default="", description="Epic title")

    # Task breakdown
    total_tasks: int = Field(default=0, ge=0, description="Total child tasks")
    open_tasks: int = Field(default=0, ge=0, description="Open tasks")
    in_progress_tasks: int = Field(default=0, ge=0, description="In-progress tasks")
    closed_tasks: int = Field(default=0, ge=0, description="Closed tasks")
    ready_tasks: int = Field(default=0, ge=0, description="Ready tasks (no blockers)")

    # Completion metrics
    completion_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percentage of tasks completed"
    )

    # Cost metrics (from ledger)
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost for epic tasks")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    tasks_with_cost: int = Field(default=0, ge=0, description="Tasks with ledger cost data")

    # Temporal tracking
    first_task_started: datetime | None = Field(
        default=None, description="When first task was started"
    )
    last_task_completed: datetime | None = Field(
        default=None, description="When last task was completed"
    )

    # Workflow stage (from epic entry if available)
    workflow_stage: str = Field(
        default="planned", description="Epic workflow stage (planned, in_progress, complete)"
    )


# Re-export LedgerStats from ledger models for convenience
# This allows services to use a single import point
from cub.core.ledger.models import LedgerStats  # noqa: E402, F401

__all__ = [
    "ProjectStats",
    "EpicProgress",
    "LedgerStats",
]
