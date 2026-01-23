"""
Ledger data models for cub.

Defines Pydantic models for the Completed Work Ledger system that captures
task execution history, including token usage, costs, verification status,
and outcomes. These models support the knowledge retention system described
in specs/researching/knowledge-retention-system.md.
"""

from datetime import datetime, timezone
from enum import Enum

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

    # Core identification
    id: str = Field(..., description="Task ID (e.g., 'beads-abc123')")
    title: str = Field(..., min_length=1, description="Task title")

    # Temporal tracking
    started_at: datetime | None = Field(
        default=None, description="When task execution started (UTC)"
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When task was completed (UTC)",
    )

    # Cost and resource tracking
    tokens: TokenUsage = Field(default_factory=TokenUsage, description="Token usage for this task")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Estimated cost in USD")
    duration_seconds: int = Field(default=0, ge=0, description="Task duration in seconds")
    iterations: int = Field(default=1, ge=1, description="Number of harness iterations (runs)")

    # Implementation details
    approach: str = Field(default="", description="Approach taken (markdown)")
    decisions: list[str] = Field(
        default_factory=list, description="Key decisions made during implementation"
    )
    lessons_learned: list[str] = Field(
        default_factory=list, description="Lessons learned during implementation"
    )

    # File and commit tracking
    files_changed: list[str] = Field(
        default_factory=list, description="List of files modified or created"
    )
    commits: list[CommitRef] = Field(
        default_factory=list, description="Git commits associated with this task"
    )

    # References and context
    spec_file: str | None = Field(
        default=None, description="Reference to specification file (e.g., 'specs/planned/auth.md')"
    )
    run_log_path: str | None = Field(
        default=None,
        description="Path to run log directory (e.g., '.cub/runs/session-123/tasks/beads-abc')",
    )
    epic_id: str | None = Field(
        default=None, description="Parent epic ID if this task is part of an epic"
    )

    # Verification tracking
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.PENDING, description="Overall verification status"
    )
    verification_notes: list[str] = Field(
        default_factory=list, description="Verification check results and notes"
    )

    # Harness metadata
    harness_name: str = Field(default="", description="Harness used (e.g., 'claude', 'codex')")
    harness_model: str = Field(default="", description="Model used (e.g., 'sonnet', 'haiku')")

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
