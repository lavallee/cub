"""
Ledger data models for cub.

Defines Pydantic models for the Completed Work Ledger system that captures
task execution history, including token usage, costs, verification status,
and outcomes. These models support the knowledge retention system described
in specs/researching/knowledge-retention-system.md.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VerificationStatus(str, Enum):
    """Verification status for completed tasks.

    These statuses indicate the outcome of verification checks
    run on completed work (tests, builds, lints, etc.).
    """

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"
    PENDING = "pending"
    ERROR = "error"

    @property
    def is_successful(self) -> bool:
        """Check if verification was successful."""
        return self in (VerificationStatus.PASS, VerificationStatus.SKIP)

    @property
    def requires_attention(self) -> bool:
        """Check if verification requires human attention."""
        return self in (VerificationStatus.FAIL, VerificationStatus.ERROR)


class WorkflowStage(str, Enum):
    """Post-completion workflow stages for tasks and epics.

    These stages represent the progression of closed work through review
    and release processes. They are manually set via `cub workflow set`.

    Progression:
    - NEEDS_REVIEW: Work is done but awaiting review
    - VALIDATED: Work has been reviewed and approved
    - RELEASED: Work has been shipped/released
    """

    NEEDS_REVIEW = "needs_review"
    VALIDATED = "validated"
    RELEASED = "released"


class TokenUsage(BaseModel):
    """Token usage metrics for a task execution.

    Tracks input, output, cache read, and cache creation tokens
    consumed during harness execution.
    """

    input_tokens: int = Field(default=0, ge=0, description="Input tokens consumed")
    output_tokens: int = Field(default=0, ge=0, description="Output tokens generated")
    cache_read_tokens: int = Field(default=0, ge=0, description="Cache read tokens")
    cache_creation_tokens: int = Field(
        default=0, ge=0, description="Cache creation tokens (prompt caching write)"
    )

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens across all categories."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )


class CommitRef(BaseModel):
    """Reference to a git commit associated with task completion.

    Links completed work to specific commits for traceability.
    """

    hash: str = Field(..., min_length=7, max_length=40, description="Git commit hash")
    message: str = Field(default="", description="Commit message")
    author: str = Field(default="", description="Commit author")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Commit timestamp (UTC)",
    )

    @field_validator("hash")
    @classmethod
    def validate_hash(cls, v: str) -> str:
        """Validate git hash format (hex characters only)."""
        if not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("Git hash must contain only hexadecimal characters")
        return v.lower()

    @property
    def short_hash(self) -> str:
        """Get short form of commit hash (first 7 chars)."""
        return self.hash[:7]


class Lineage(BaseModel):
    """Lineage tracking for a task - links to spec, plan, and epic.

    Captures the genealogy of where a task came from to enable
    traceability between requirements and implementation.
    """

    spec_file: str | None = Field(default=None, description="Path to spec markdown file")
    plan_file: str | None = Field(default=None, description="Path to plan.jsonl file")
    epic_id: str | None = Field(default=None, description="Parent epic ID")


class TaskSnapshot(BaseModel):
    """Snapshot of task state at ledger entry creation.

    Captures the task state as it existed when work began,
    enabling drift detection if the task definition changes.
    """

    title: str = Field(..., min_length=1, description="Task title")
    description: str = Field(default="", description="Task description")
    type: str = Field(default="task", description="Task type (task, bug, epic, etc.)")
    priority: int = Field(default=0, description="Task priority level")
    labels: list[str] = Field(default_factory=list, description="Task labels/tags")
    created_at: datetime | None = Field(default=None, description="Task creation time")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When snapshot was captured (UTC)",
    )


class TaskChanged(BaseModel):
    """Record of task definition drift detection.

    Captures when a task's definition changes during implementation,
    which may indicate scope creep or requirement clarification.
    """

    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When drift was detected (UTC)",
    )
    fields_changed: list[str] = Field(
        default_factory=list, description="Names of fields that changed"
    )
    original_description: str = Field(default="", description="Original task description")
    final_description: str = Field(default="", description="Final task description")
    notes: str | None = Field(default=None, description="Additional notes about the change")


class Attempt(BaseModel):
    """Record of a single execution attempt on a task.

    Captures all details about one harness execution, including
    model used, cost, duration, and outcome.
    """

    attempt_number: int = Field(..., ge=1, description="Attempt sequence number (1-based)")
    run_id: str = Field(..., description="Run session ID this attempt belongs to")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Attempt start time (UTC)",
    )
    completed_at: datetime | None = Field(default=None, description="Attempt completion time (UTC)")
    harness: str = Field(default="", description="Harness used (e.g., 'claude', 'codex')")
    model: str = Field(default="", description="Model used (e.g., 'sonnet', 'haiku')")
    success: bool = Field(default=False, description="Whether attempt succeeded")
    error_category: str | None = Field(
        default=None, description="Category of error if failed (e.g., 'timeout', 'api_error')"
    )
    error_summary: str | None = Field(default=None, description="Brief error description if failed")
    tokens: TokenUsage = Field(
        default_factory=TokenUsage, description="Token usage for this attempt"
    )
    cost_usd: float = Field(default=0.0, ge=0.0, description="Cost for this attempt in USD")
    duration_seconds: int = Field(default=0, ge=0, description="Attempt duration in seconds")

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_seconds / 60.0


class Outcome(BaseModel):
    """Final outcome of task completion.

    Aggregates results across all attempts and captures
    the final state when the task is closed.
    """

    success: bool = Field(default=False, description="Whether task completed successfully")
    partial: bool = Field(
        default=False, description="Whether task was partially completed (incomplete success)"
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Task completion time (UTC)",
    )
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost across all attempts")
    total_attempts: int = Field(default=0, ge=0, description="Total number of attempts")
    total_duration_seconds: int = Field(
        default=0, ge=0, description="Total duration across all attempts"
    )
    final_model: str = Field(default="", description="Model used in final successful attempt")
    escalated: bool = Field(
        default=False, description="Whether task was escalated to a more capable model"
    )
    escalation_path: list[str] = Field(
        default_factory=list,
        description="Sequence of models if escalated (e.g., ['haiku', 'sonnet'])",
    )
    files_changed: list[str] = Field(
        default_factory=list, description="Files modified during task execution"
    )
    commits: list[CommitRef] = Field(
        default_factory=list, description="Git commits made during task execution"
    )
    approach: str | None = Field(default=None, description="Approach taken (markdown)")
    decisions: list[str] = Field(
        default_factory=list, description="Key decisions made during implementation"
    )
    lessons_learned: list[str] = Field(
        default_factory=list, description="Lessons learned during implementation"
    )

    @property
    def total_duration_minutes(self) -> float:
        """Get total duration in minutes."""
        return self.total_duration_seconds / 60.0


class DriftRecord(BaseModel):
    """Record of drift between specification and implementation.

    Tracks what was added beyond the spec, what was omitted
    from the spec, and the severity of drift.
    """

    additions: list[str] = Field(
        default_factory=list, description="Features/changes added beyond original spec"
    )
    omissions: list[str] = Field(
        default_factory=list, description="Features/changes omitted from original spec"
    )
    severity: str = Field(
        default="none",
        description="Drift severity: 'none', 'minor', 'significant'",
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Validate severity is one of allowed values."""
        allowed = {"none", "minor", "significant"}
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}, got '{v}'")
        return v


class Verification(BaseModel):
    """Verification and quality gate status.

    Tracks results of automated checks (tests, typecheck, lint)
    run on completed work.
    """

    status: str = Field(
        default="pending",
        description="Overall verification status: 'pending', 'pass', 'fail'",
    )
    checked_at: datetime | None = Field(
        default=None, description="When verification checks were run (UTC)"
    )
    tests_passed: bool | None = Field(default=None, description="Whether tests passed")
    typecheck_passed: bool | None = Field(default=None, description="Whether typecheck passed")
    lint_passed: bool | None = Field(default=None, description="Whether lint passed")
    notes: list[str] = Field(default_factory=list, description="Verification notes and details")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of allowed values."""
        allowed = {"pending", "pass", "fail"}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}, got '{v}'")
        return v


class StateTransition(BaseModel):
    """Record of a workflow stage transition.

    Captures state changes with attribution and reason,
    building an audit trail of task progression.
    """

    stage: str = Field(..., description="Workflow stage transitioned to")
    at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When transition occurred (UTC)",
    )
    by: str = Field(
        default="cub-run",
        description="Who/what caused transition (e.g., 'cub-run', 'dashboard:user', 'cli')",
    )
    reason: str | None = Field(default=None, description="Reason for transition")


class WorkflowState(BaseModel):
    """Current workflow state for a task or epic.

    Tracks the current post-completion stage and when it was set.
    """

    stage: str = Field(
        default="dev_complete",
        description="Current stage: 'dev_complete', 'needs_review', 'validated', 'released'",
    )
    stage_updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When stage was last updated (UTC)",
    )

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        """Validate stage is one of allowed values."""
        allowed = {"dev_complete", "needs_review", "validated", "released"}
        if v not in allowed:
            raise ValueError(f"Stage must be one of {allowed}, got '{v}'")
        return v


class CICheckRecord(BaseModel):
    """Record of a CI check result from PR monitoring.

    Captures the state of individual CI checks for audit trail
    and retry decision-making.
    """

    name: str = Field(..., description="Check name (e.g., 'tests', 'lint')")
    state: str = Field(
        default="pending",
        description="Check state (pending, running, success, failure, error, timed_out)",
    )
    url: str | None = Field(default=None, description="URL to check details")
    completed_at: datetime | None = Field(default=None, description="When check completed (UTC)")


class CIRetryRecord(BaseModel):
    """Record of a CI retry attempt.

    Captures when and why a retry was triggered for session forensics.
    """

    attempt_number: int = Field(..., ge=1, description="Retry attempt number")
    reason: str = Field(
        default="unknown",
        description="Reason for retry (flaky_test, rate_limit, service_error, timeout)",
    )
    triggered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When retry was triggered (UTC)",
    )
    failed_checks: list[str] = Field(
        default_factory=list, description="Names of checks that were failing"
    )
    success: bool = Field(default=False, description="Whether retry resolved the failure")


class CIMonitorSummary(BaseModel):
    """Summary of CI monitoring for a PR associated with a task.

    Recorded in the ledger when a task's PR goes through automated
    check monitoring and retry logic.
    """

    pr_number: int = Field(..., ge=1, description="PR number that was monitored")
    final_state: str = Field(
        default="unknown",
        description="Final monitor state (succeeded, exhausted, timed_out)",
    )
    total_retries: int = Field(default=0, ge=0, description="Total retry attempts")
    retry_records: list[CIRetryRecord] = Field(
        default_factory=list, description="Individual retry attempt records"
    )
    check_records: list[CICheckRecord] = Field(
        default_factory=list, description="Final check states"
    )
    started_at: datetime | None = Field(
        default=None, description="When monitoring started (UTC)"
    )
    completed_at: datetime | None = Field(
        default=None, description="When monitoring completed (UTC)"
    )
    duration_seconds: float = Field(
        default=0.0, ge=0.0, description="Total monitoring duration in seconds"
    )


class LedgerEntry(BaseModel):
    """Individual task completion record for the ledger.

    Captures what was built, why, how, and the outcome. This is the
    core data structure written to .cub/ledger/by-task/{task-id}.md
    and indexed in .cub/ledger/index.jsonl.

    Example:
        >>> entry = LedgerEntry(
        ...     id="beads-abc123",
        ...     title="Implement user authentication",
        ...     completed_at=datetime(2026, 1, 18, 10, 45, tzinfo=timezone.utc),
        ...     cost_usd=0.09,
        ...     tokens=TokenUsage(input_tokens=45000, output_tokens=12000),
        ...     files_changed=["src/auth/middleware.ts", "src/auth/jwt.ts"],
        ...     commits=[CommitRef(hash="abc123f", message="feat: implement auth")]
        ... )
        >>> entry.duration_minutes
        45.0
    """

    # Schema version for backward compatibility
    version: int = Field(default=1, description="Schema version number")

    # Core identification
    id: str = Field(..., description="Task ID (e.g., 'beads-abc123')")
    title: str = Field(..., min_length=1, description="Task title")

    # Lineage tracking - NEW
    lineage: Lineage = Field(
        default_factory=Lineage, description="Links to spec, plan, and epic"
    )

    # Task snapshot - NEW
    task: TaskSnapshot | None = Field(
        default=None, description="Snapshot of task state at capture time"
    )

    # Task change detection - NEW
    task_changed: TaskChanged | None = Field(
        default=None, description="Record of task definition drift (if detected)"
    )

    # Attempt tracking - NEW
    attempts: list[Attempt] = Field(
        default_factory=list, description="All execution attempts on this task"
    )

    # Final outcome - NEW
    outcome: Outcome | None = Field(
        default=None, description="Final completion outcome (set on task close)"
    )

    # Drift tracking - NEW
    drift: DriftRecord = Field(
        default_factory=DriftRecord, description="Spec vs implementation drift"
    )

    # Verification tracking - NEW (replaces old verification_status/notes)
    verification: Verification = Field(
        default_factory=Verification, description="Quality gate status"
    )

    # Workflow state - NEW (replaces old workflow_stage/workflow_stage_updated_at)
    workflow: WorkflowState = Field(
        default_factory=WorkflowState, description="Current workflow state"
    )

    # State history - NEW
    state_history: list[StateTransition] = Field(
        default_factory=list, description="Workflow stage transition history"
    )

    # CI monitoring - NEW
    ci_monitor: CIMonitorSummary | None = Field(
        default=None, description="CI check monitoring and retry summary (if PR was monitored)"
    )

    # Temporal tracking
    started_at: datetime | None = Field(
        default=None, description="When task execution started (UTC)"
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When task was completed (UTC)",
    )

    # Cost and resource tracking (DEPRECATED - use outcome.* for new entries)
    tokens: TokenUsage = Field(default_factory=TokenUsage, description="Token usage for this task")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Estimated cost in USD")
    duration_seconds: int = Field(default=0, ge=0, description="Task duration in seconds")
    iterations: int = Field(default=1, ge=1, description="Number of harness iterations (runs)")

    # Implementation details (DEPRECATED - use outcome.* for new entries)
    approach: str = Field(default="", description="Approach taken (markdown)")
    decisions: list[str] = Field(
        default_factory=list, description="Key decisions made during implementation"
    )
    lessons_learned: list[str] = Field(
        default_factory=list, description="Lessons learned during implementation"
    )

    # File and commit tracking (DEPRECATED - use outcome.* for new entries)
    files_changed: list[str] = Field(
        default_factory=list, description="List of files modified or created"
    )
    commits: list[CommitRef] = Field(
        default_factory=list, description="Git commits associated with this task"
    )

    # References and context (DEPRECATED - use lineage.* for new entries)
    spec_file: str | None = Field(
        default=None, description="Reference to specification file (e.g., 'specs/planned/auth.md')"
    )
    run_log_path: str | None = Field(
        default=None,
        description="Path to run log directory (e.g., '.cub/ledger/by-run/session-123/tasks/beads-abc')",
    )
    epic_id: str | None = Field(
        default=None,
        description=(
            "Parent epic ID if this task is part of an epic (DEPRECATED - use lineage.epic_id)"
        ),
    )

    # Verification tracking (DEPRECATED - use verification.* for new entries)
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.PENDING, description="Overall verification status"
    )
    verification_notes: list[str] = Field(
        default_factory=list, description="Verification check results and notes"
    )

    # Harness metadata (DEPRECATED - use attempts[].harness and attempts[].model for new entries)
    harness_name: str = Field(default="", description="Harness used (e.g., 'claude', 'codex')")
    harness_model: str = Field(default="", description="Model used (e.g., 'sonnet', 'haiku')")

    # Workflow stage tracking (DEPRECATED - use workflow.* for new entries)
    workflow_stage: WorkflowStage | None = Field(
        default=None,
        description="Post-completion workflow stage (needs_review/validated/released)",
    )
    workflow_stage_updated_at: datetime | None = Field(
        default=None, description="When workflow stage was last updated (UTC)"
    )

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_seconds / 60.0

    @property
    def primary_commit(self) -> CommitRef | None:
        """Get the primary (first) commit for this task."""
        return self.commits[0] if self.commits else None

    @property
    def cost_per_token(self) -> float:
        """Calculate cost per token (useful for cost analysis)."""
        total = self.tokens.total_tokens
        return self.cost_usd / total if total > 0 else 0.0


class LedgerIndex(BaseModel):
    """Quick-lookup index entry for .cub/ledger/index.jsonl.

    Each line in index.jsonl is a compact representation of a completed
    task, enabling fast queries without reading full markdown files.

    Example:
        >>> index = LedgerIndex(
        ...     id="beads-abc",
        ...     title="Implement auth",
        ...     completed="2026-01-18",
        ...     cost_usd=0.09,
        ...     files=["src/auth/"],
        ...     commit="abc123f",
        ...     spec="specs/planned/auth.md"
        ... )
    """

    id: str = Field(..., description="Task ID")
    title: str = Field(..., description="Task title")
    completed: str = Field(..., description="Completion date (YYYY-MM-DD)")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Task cost in USD")
    files: list[str] = Field(default_factory=list, description="Changed files or directories")
    commit: str = Field(default="", description="Primary commit hash (short form)")
    spec: str | None = Field(default=None, description="Spec file reference")
    epic: str | None = Field(default=None, description="Epic ID if part of an epic")
    verification: str = Field(
        default="pending", description="Verification status (pass/fail/warn/skip/pending/error)"
    )
    tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    workflow_stage: str | None = Field(
        default=None, description="Post-completion workflow stage (needs_review/validated/released)"
    )

    @field_validator("completed")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError as e:
            raise ValueError("Date must be in YYYY-MM-DD format") from e

    @classmethod
    def from_ledger_entry(cls, entry: LedgerEntry) -> "LedgerIndex":
        """Create index entry from full ledger entry.

        Args:
            entry: Full ledger entry

        Returns:
            Compact index entry suitable for JSONL storage
        """
        return cls(
            id=entry.id,
            title=entry.title,
            completed=entry.completed_at.strftime("%Y-%m-%d"),
            cost_usd=entry.cost_usd,
            files=entry.files_changed,
            commit=entry.primary_commit.short_hash if entry.primary_commit else "",
            spec=entry.spec_file,
            epic=entry.epic_id,
            verification=entry.verification_status.value,
            tokens=entry.tokens.total_tokens,
            workflow_stage=entry.workflow_stage.value if entry.workflow_stage else None,
        )


class EpicSummary(BaseModel):
    """Summary of completed epic with aggregated task metrics.

    Written to .cub/ledger/by-epic/{epic-id}.md, this provides
    a rollup view of all tasks in an epic including total cost,
    duration, and spec drift analysis.

    Example:
        >>> summary = EpicSummary(
        ...     epic_id="cub-m4j",
        ...     title="Ledger Core",
        ...     status="completed",
        ...     task_ids=["cub-m4j.1", "cub-m4j.2"],
        ...     total_cost_usd=0.47,
        ...     total_duration_seconds=15600
        ... )
        >>> summary.tasks_completed
        2
    """

    # Epic identification
    epic_id: str = Field(..., description="Epic ID")
    title: str = Field(..., min_length=1, description="Epic title")
    status: str = Field(default="in_progress", description="Epic status")

    # Task aggregation
    task_ids: list[str] = Field(default_factory=list, description="List of task IDs in this epic")
    tasks_total: int = Field(default=0, ge=0, description="Total number of tasks")
    tasks_completed: int = Field(default=0, ge=0, description="Number of completed tasks")

    # Aggregated metrics
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost across all tasks")
    total_duration_seconds: int = Field(
        default=0, ge=0, description="Total duration across all tasks"
    )
    total_tokens: int = Field(default=0, ge=0, description="Total tokens across all tasks")

    # Temporal tracking
    started_at: datetime | None = Field(default=None, description="Epic start time (UTC)")
    completed_at: datetime | None = Field(default=None, description="Epic completion time (UTC)")

    # Commit range
    first_commit: str | None = Field(default=None, description="First commit in epic")
    last_commit: str | None = Field(default=None, description="Last commit in epic")

    # Spec drift tracking
    spec_file: str | None = Field(default=None, description="Primary spec file for epic")
    drift_notes: list[str] = Field(
        default_factory=list,
        description="Notes on divergence from spec (what was changed, added, or skipped)",
    )

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage (0-100)."""
        if self.tasks_total == 0:
            return 0.0
        return (self.tasks_completed / self.tasks_total) * 100

    @property
    def average_cost_per_task(self) -> float:
        """Calculate average cost per completed task."""
        if self.tasks_completed == 0:
            return 0.0
        return self.total_cost_usd / self.tasks_completed

    @property
    def is_complete(self) -> bool:
        """Check if epic is fully complete."""
        return self.tasks_total > 0 and self.tasks_completed == self.tasks_total


class EpicSnapshot(BaseModel):
    """Snapshot of epic state at ledger entry creation.

    Captures the epic state as it existed when work began,
    enabling drift detection if the epic definition changes.
    """

    title: str = Field(..., min_length=1, description="Epic title")
    description: str = Field(default="", description="Epic description")
    status: str = Field(default="open", description="Epic status")
    priority: int = Field(default=0, description="Epic priority level")
    labels: list[str] = Field(default_factory=list, description="Epic labels/tags")
    created_at: datetime | None = Field(default=None, description="Epic creation time")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When snapshot was captured (UTC)",
    )


class EpicAggregates(BaseModel):
    """Computed aggregates from child task ledger entries.

    Provides project-level visibility into completion, cost, and quality metrics
    derived from all tasks within an epic.
    """

    # Task completion metrics
    total_tasks: int = Field(default=0, ge=0, description="Total number of tasks in epic")
    tasks_completed: int = Field(default=0, ge=0, description="Number of completed tasks")
    tasks_successful: int = Field(
        default=0, ge=0, description="Number of successfully completed tasks"
    )
    tasks_failed: int = Field(default=0, ge=0, description="Number of failed tasks")

    # Cost metrics
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost across all tasks")
    avg_cost_per_task: float = Field(default=0.0, ge=0.0, description="Average cost per task")
    min_cost_usd: float = Field(default=0.0, ge=0.0, description="Minimum task cost")
    max_cost_usd: float = Field(default=0.0, ge=0.0, description="Maximum task cost")

    # Escalation metrics
    total_escalations: int = Field(default=0, ge=0, description="Number of tasks that escalated")
    escalation_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Percentage of tasks that escalated (0.0-1.0)"
    )

    # Attempt metrics
    total_attempts: int = Field(default=0, ge=0, description="Total attempts across all tasks")
    avg_attempts_per_task: float = Field(
        default=0.0, ge=0.0, description="Average attempts per task"
    )

    # Token metrics
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    avg_tokens_per_task: int = Field(default=0, ge=0, description="Average tokens per task")

    # Duration metrics
    total_duration_seconds: int = Field(
        default=0, ge=0, description="Total duration across all tasks"
    )
    avg_duration_seconds: int = Field(default=0, ge=0, description="Average duration per task")

    # Model usage tracking
    models_used: list[str] = Field(
        default_factory=list, description="Unique models used across tasks"
    )
    most_common_model: str = Field(default="", description="Most frequently used model")

    @property
    def completion_rate(self) -> float:
        """Calculate task completion rate (0.0-1.0)."""
        if self.total_tasks == 0:
            return 0.0
        return self.tasks_completed / self.total_tasks

    @property
    def success_rate(self) -> float:
        """Calculate task success rate (0.0-1.0)."""
        if self.tasks_completed == 0:
            return 0.0
        return self.tasks_successful / self.tasks_completed

    @property
    def total_duration_hours(self) -> float:
        """Get total duration in hours."""
        return self.total_duration_seconds / 3600.0

    @property
    def avg_duration_minutes(self) -> float:
        """Get average duration in minutes."""
        return self.avg_duration_seconds / 60.0


class EpicEntry(BaseModel):
    """Epic-level ledger entry with child task aggregation.

    Provides project-level visibility into development progress, costs,
    and patterns across all tasks within an epic. Written to
    .cub/ledger/by-epic/{epic-id}.md.

    Example:
        >>> entry = EpicEntry(
        ...     id="cub-e2p",
        ...     title="Unified Tracking Model",
        ...     epic=EpicSnapshot(title="Unified Tracking Model"),
        ...     aggregates=EpicAggregates(total_tasks=5, tasks_completed=3),
        ...     lineage=Lineage(spec_file="specs/planned/unified-tracking.md")
        ... )
    """

    # Schema version for backward compatibility
    version: int = Field(default=1, description="Schema version number")

    # Core identification
    id: str = Field(..., description="Epic ID (e.g., 'cub-e2p')")
    title: str = Field(..., min_length=1, description="Epic title")

    # Lineage tracking
    lineage: Lineage = Field(
        default_factory=Lineage, description="Links to spec, plan, and parent epic"
    )

    # Epic snapshot
    epic: EpicSnapshot | None = Field(
        default=None, description="Snapshot of epic state at capture time"
    )

    # Child task tracking
    task_ids: list[str] = Field(
        default_factory=list, description="List of task IDs in this epic"
    )

    # Aggregated metrics from child tasks
    aggregates: EpicAggregates = Field(
        default_factory=EpicAggregates, description="Computed aggregates from child tasks"
    )

    # Workflow state
    workflow: WorkflowState = Field(
        default_factory=WorkflowState, description="Current workflow state"
    )

    # State history
    state_history: list[StateTransition] = Field(
        default_factory=list, description="Workflow stage transition history"
    )

    # Temporal tracking
    started_at: datetime | None = Field(
        default=None, description="When first task in epic started (UTC)"
    )
    completed_at: datetime | None = Field(
        default=None, description="When last task in epic completed (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When epic entry was last updated (UTC)",
    )

    # Commit range
    first_commit: CommitRef | None = Field(
        default=None, description="First commit in epic"
    )
    last_commit: CommitRef | None = Field(
        default=None, description="Most recent commit in epic"
    )

    # Drift tracking
    drift: DriftRecord = Field(
        default_factory=DriftRecord, description="Spec vs implementation drift"
    )

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    @property
    def is_complete(self) -> bool:
        """Check if all tasks in epic are complete."""
        return (
            self.aggregates.total_tasks > 0
            and self.aggregates.tasks_completed == self.aggregates.total_tasks
        )

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage (0-100)."""
        return self.aggregates.completion_rate * 100


class LedgerStats(BaseModel):
    """Aggregate statistics across the entire ledger.

    Provides summary metrics for cost tracking, resource usage,
    and work patterns. Can be used for dashboards and reports.

    Example:
        >>> stats = LedgerStats(
        ...     total_tasks=50,
        ...     total_cost_usd=5.23,
        ...     total_tokens=523000,
        ...     average_cost_per_task=0.10
        ... )
    """

    # Task counts
    total_tasks: int = Field(default=0, ge=0, description="Total completed tasks")
    total_epics: int = Field(default=0, ge=0, description="Total epics tracked")

    # Cost metrics
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total spend across all tasks")
    average_cost_per_task: float = Field(default=0.0, ge=0.0, description="Average cost per task")
    min_cost_usd: float = Field(default=0.0, ge=0.0, description="Minimum task cost")
    max_cost_usd: float = Field(default=0.0, ge=0.0, description="Maximum task cost")

    # Token metrics
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    average_tokens_per_task: int = Field(default=0, ge=0, description="Average tokens per task")

    # Time metrics
    total_duration_seconds: int = Field(
        default=0, ge=0, description="Total time spent across all tasks"
    )
    average_duration_seconds: int = Field(default=0, ge=0, description="Average task duration")

    # Verification metrics
    tasks_verified: int = Field(default=0, ge=0, description="Tasks with passing verification")
    tasks_failed: int = Field(default=0, ge=0, description="Tasks with failed verification")
    verification_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Pass rate for verified tasks (0.0-1.0)"
    )

    # File metrics
    total_files_changed: int = Field(default=0, ge=0, description="Total files changed")
    unique_files_changed: int = Field(
        default=0, ge=0, description="Unique files changed (deduplicated)"
    )

    # Temporal tracking
    first_task_date: datetime | None = Field(
        default=None, description="Date of first completed task"
    )
    last_task_date: datetime | None = Field(
        default=None, description="Date of most recent completed task"
    )

    @property
    def total_duration_hours(self) -> float:
        """Get total duration in hours."""
        return self.total_duration_seconds / 3600.0

    @property
    def average_duration_minutes(self) -> float:
        """Get average duration in minutes."""
        return self.average_duration_seconds / 60.0


def compute_aggregates(task_entries: list[LedgerEntry]) -> EpicAggregates:
    """Compute epic aggregates from child task ledger entries.

    Args:
        task_entries: List of completed task ledger entries

    Returns:
        Computed aggregates for the epic

    Example:
        >>> tasks = [
        ...     LedgerEntry(id="task-1", title="Task 1", cost_usd=0.10, ...),
        ...     LedgerEntry(id="task-2", title="Task 2", cost_usd=0.15, ...)
        ... ]
        >>> agg = compute_aggregates(tasks)
        >>> agg.total_cost_usd
        0.25
    """
    if not task_entries:
        return EpicAggregates()

    total_tasks = len(task_entries)
    tasks_completed = sum(1 for t in task_entries if t.outcome and t.outcome.success)
    tasks_failed = total_tasks - tasks_completed

    # Cost metrics
    costs = [t.outcome.total_cost_usd if t.outcome else t.cost_usd for t in task_entries]
    total_cost = sum(costs)
    avg_cost = total_cost / total_tasks if total_tasks > 0 else 0.0
    min_cost = min(costs) if costs else 0.0
    max_cost = max(costs) if costs else 0.0

    # Escalation metrics
    escalations = sum(1 for t in task_entries if t.outcome and t.outcome.escalated)
    escalation_rate = escalations / total_tasks if total_tasks > 0 else 0.0

    # Attempt metrics
    total_attempts = sum(
        t.outcome.total_attempts if t.outcome else t.iterations for t in task_entries
    )
    avg_attempts = total_attempts / total_tasks if total_tasks > 0 else 0.0

    # Token metrics
    total_tokens = sum(t.tokens.total_tokens for t in task_entries)
    avg_tokens = total_tokens // total_tasks if total_tasks > 0 else 0

    # Duration metrics
    total_duration = sum(
        t.outcome.total_duration_seconds if t.outcome else t.duration_seconds
        for t in task_entries
    )
    avg_duration = total_duration // total_tasks if total_tasks > 0 else 0

    # Model usage tracking
    models_used_set: set[str] = set()
    model_counts: dict[str, int] = {}

    for task in task_entries:
        if task.outcome and task.outcome.final_model:
            model = task.outcome.final_model
            models_used_set.add(model)
            model_counts[model] = model_counts.get(model, 0) + 1
        elif task.harness_model:
            model = task.harness_model
            models_used_set.add(model)
            model_counts[model] = model_counts.get(model, 0) + 1

    models_used = sorted(list(models_used_set))
    most_common_model = max(model_counts.items(), key=lambda x: x[1])[0] if model_counts else ""

    return EpicAggregates(
        total_tasks=total_tasks,
        tasks_completed=tasks_completed,
        tasks_successful=tasks_completed,  # Assuming completed = successful for now
        tasks_failed=tasks_failed,
        total_cost_usd=total_cost,
        avg_cost_per_task=avg_cost,
        min_cost_usd=min_cost,
        max_cost_usd=max_cost,
        total_escalations=escalations,
        escalation_rate=escalation_rate,
        total_attempts=total_attempts,
        avg_attempts_per_task=avg_attempts,
        total_tokens=total_tokens,
        avg_tokens_per_task=avg_tokens,
        total_duration_seconds=total_duration,
        avg_duration_seconds=avg_duration,
        models_used=models_used,
        most_common_model=most_common_model,
    )


class PlanEntry(BaseModel):
    """Plan-level aggregation record.

    Stored in .cub/ledger/by-plan/{plan_id}/entry.json.
    Aggregates metrics from all epics in a plan, providing visibility
    into overall plan progress, costs, and completion status.

    Example:
        >>> entry = PlanEntry(
        ...     plan_id="cub-054A",
        ...     spec_id="cub-054",
        ...     title="Ledger Consolidation",
        ...     epics=["cub-054A-0", "cub-054A-1"],
        ...     status="in_progress",
        ...     started_at=datetime.now(timezone.utc),
        ...     total_cost=1.23,
        ...     total_tokens=150000,
        ...     total_tasks=10,
        ...     completed_tasks=5
        ... )
    """

    # Schema version for backward compatibility
    version: int = Field(default=1, description="Schema version number")

    # Core identification
    plan_id: str = Field(..., description="Plan ID (e.g., 'cub-054A')")
    spec_id: str = Field(..., description="Parent spec ID (e.g., 'cub-054')")
    title: str = Field(..., min_length=1, description="Plan title")

    # Epic tracking
    epics: list[str] = Field(default_factory=list, description="List of epic IDs in this plan")

    # Status tracking
    status: Literal["in_progress", "completed", "released"] = Field(
        default="in_progress", description="Plan completion status"
    )

    # Temporal tracking
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When first epic in plan started (UTC)",
    )
    completed_at: datetime | None = Field(
        default=None, description="When last epic in plan completed (UTC)"
    )

    # Aggregated metrics
    total_cost: float = Field(default=0.0, ge=0.0, description="Total cost across all epics in USD")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed across all epics")
    total_tasks: int = Field(default=0, ge=0, description="Total number of tasks in plan")
    completed_tasks: int = Field(default=0, ge=0, description="Number of completed tasks in plan")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage (0-100)."""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def is_complete(self) -> bool:
        """Check if all tasks in plan are complete."""
        return self.total_tasks > 0 and self.completed_tasks == self.total_tasks


class RunEntry(BaseModel):
    """Run session record.

    Stored in .cub/ledger/by-run/{run_id}.json.
    Captures metadata and metrics for a single execution of the run loop,
    whether running a single task, an epic, or an entire plan.

    Example:
        >>> entry = RunEntry(
        ...     run_id="cub-20260204-161800",
        ...     started_at=datetime.now(timezone.utc),
        ...     status="running",
        ...     config={"harness": "claude", "model": "sonnet"},
        ...     tasks_attempted=["cub-054A-1.1", "cub-054A-1.2"],
        ...     tasks_completed=["cub-054A-1.1"],
        ...     total_cost=0.15,
        ...     total_tokens=25000,
        ...     iterations=1
        ... )
    """

    # Schema version for backward compatibility
    version: int = Field(default=1, description="Schema version number")

    # Core identification
    run_id: str = Field(..., description="Run session ID (e.g., 'cub-20260204-161800')")

    # Temporal tracking
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When run session started (UTC)",
    )
    completed_at: datetime | None = Field(
        default=None, description="When run session completed (UTC)"
    )

    # Status tracking
    status: Literal["running", "completed", "failed", "interrupted"] = Field(
        default="running", description="Run session status"
    )

    # Configuration
    config: dict[str, str | int | bool | None] = Field(
        default_factory=dict,
        description="Serialized run configuration (harness, model, flags, etc.)",
    )

    # Task tracking
    tasks_attempted: list[str] = Field(
        default_factory=list, description="List of task IDs that were attempted"
    )
    tasks_completed: list[str] = Field(
        default_factory=list, description="List of task IDs that were completed successfully"
    )

    # Resource tracking
    total_cost: float = Field(default=0.0, ge=0.0, description="Total cost for this run in USD")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed in this run")
    iterations: int = Field(default=0, ge=0, description="Number of task iterations in this run")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both snake_case and camelCase
    )

    @property
    def duration_seconds(self) -> int:
        """Calculate duration in seconds if completed."""
        if self.completed_at is None or self.started_at is None:
            return 0
        return int((self.completed_at - self.started_at).total_seconds())

    @property
    def success_rate(self) -> float:
        """Calculate task success rate (0.0-1.0)."""
        if not self.tasks_attempted:
            return 0.0
        return len(self.tasks_completed) / len(self.tasks_attempted)
