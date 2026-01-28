"""
Configuration data models for cub.

These models define the structure of .cub.json and ~/.config/cub/config.json
files, with validation and type safety via Pydantic.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GuardrailsConfig(BaseModel):
    """
    Safety limits and guardrails for autonomous execution.

    These settings prevent runaway costs and infinite loops.
    """

    max_task_iterations: int = Field(
        default=3, ge=1, description="Maximum iterations per task before failing"
    )
    max_run_iterations: int = Field(
        default=50, ge=1, description="Maximum total iterations before stopping the run"
    )
    iteration_warning_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Warn when iterations reach this fraction of max (0.0-1.0)",
    )
    secret_patterns: list[str] = Field(
        default_factory=lambda: [
            "api[_-]?key",
            "password",
            "token",
            "secret",
            "authorization",
            "credentials",
        ],
        description="Regex patterns for detecting secrets in code",
    )


class BudgetConfig(BaseModel):
    """
    Token and cost budgets for AI operations.

    Controls spending limits for autonomous sessions.
    """

    max_tokens_per_task: int | None = Field(
        default=None, ge=1, description="Stop if a single task uses more than this many tokens"
    )
    max_tasks_per_session: int | None = Field(
        default=None, ge=1, description="Stop after completing this many tasks in one session"
    )
    max_total_cost: float | None = Field(
        default=None, ge=0.0, description="Stop if total spend exceeds this amount (in dollars)"
    )
    default: int | None = Field(
        default=None,
        ge=1,
        description="Default budget if not specified (for backward compatibility)",
    )


class StateConfig(BaseModel):
    """
    Pre-flight checks before running tasks.

    Ensures repository is in a safe state before autonomous execution.
    """

    require_clean: bool = Field(default=True, description="Fail if git has uncommitted changes")
    run_tests: bool = Field(default=False, description="Run tests and fail if they don't pass")
    run_typecheck: bool = Field(
        default=False, description="Run type checker and fail if there are errors"
    )
    run_lint: bool = Field(default=False, description="Run linter and fail if there are issues")


class LoopConfig(BaseModel):
    """
    Control autonomous loop behavior.

    Determines how cub handles the task processing loop.
    """

    max_iterations: int = Field(
        default=100, ge=1, description="Stop after N iterations (prevents infinite loops)"
    )
    on_task_failure: str = Field(
        default="stop",
        pattern="^(stop|continue)$",
        description="What to do when a task fails: 'stop' or 'continue'",
    )


class HooksConfig(BaseModel):
    """
    Lifecycle hooks configuration.

    Enables running custom scripts before/after events.
    """

    enabled: bool = Field(default=True, description="Enable/disable all hooks")
    fail_fast: bool = Field(default=False, description="Stop execution if a hook fails")
    async_notifications: bool = Field(
        default=True,
        description="Run post-task and on-error hooks asynchronously (non-blocking)",
    )


class InterviewQuestion(BaseModel):
    """A custom interview question for task planning."""

    category: str = Field(..., description="Question category/section")
    question: str = Field(..., description="The question to ask")
    applies_to: list[str] = Field(
        default_factory=list,
        description="Task types this question applies to (feature, task, bugfix)",
    )
    requires_labels: list[str] = Field(
        default_factory=list, description="Only ask if task has these labels"
    )
    requires_tech: list[str] = Field(
        default_factory=list, description="Only ask if task involves these technologies"
    )
    skip_if: dict[str, Any] | None = Field(
        default=None, description="Conditional skip logic based on previous answers"
    )


class InterviewConfig(BaseModel):
    """
    Task interview/specification configuration.

    Defines custom questions to ask during task planning.
    """

    custom_questions: list[InterviewQuestion] = Field(
        default_factory=list, description="Project-specific interview questions"
    )


class ReviewConfig(BaseModel):
    """
    Task and plan review configuration.

    Controls how strict cub is about reviewing work.
    """

    plan_strict: bool = Field(default=False, description="Require plan approval before execution")
    block_on_concerns: bool = Field(
        default=False, description="Block execution if review raises concerns"
    )


class CleanupConfig(BaseModel):
    """
    Working directory cleanup configuration.

    Controls what happens at the end of a cub run to ensure clean working directory.
    """

    enabled: bool = Field(default=True, description="Enable automatic cleanup after run completes")

    commit_artifacts: bool = Field(
        default=True,
        description="Commit useful artifacts (progress files, logs, reports) to git",
    )

    remove_temp_files: bool = Field(
        default=True,
        description="Remove clearly temporary files (*.bak, *.tmp, caches, etc.)",
    )

    # Patterns for files to commit (useful artifacts)
    artifact_patterns: list[str] = Field(
        default_factory=lambda: [
            ".cub/status.json",
            ".cub/prompt.md",
            ".cub/agent.md",
            "*.log",
        ],
        description="Glob patterns for files to commit as useful artifacts",
    )

    # Patterns for files to remove (temporary/disposable)
    temp_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.bak",
            "*.tmp",
            "*.orig",
            "*.swp",
            "*.swo",
            "*~",
            "__pycache__/**",
            ".pytest_cache/**",
            ".mypy_cache/**",
            ".ruff_cache/**",
            "*.pyc",
            ".coverage",
            "htmlcov/**",
            ".tox/**",
            "dist/**",
            "build/**",
            "*.egg-info/**",
            "node_modules/**",
            ".npm/**",
        ],
        description="Glob patterns for temporary files to remove",
    )

    # Patterns to always ignore (never touch these)
    ignore_patterns: list[str] = Field(
        default_factory=lambda: [
            ".git/**",
            ".beads/**",
            ".env",
            ".env.*",
            "*.key",
            "*.pem",
            "credentials*",
            "secrets*",
        ],
        description="Glob patterns for files to never modify during cleanup",
    )

    commit_message: str = Field(
        default="chore: cleanup working directory artifacts",
        description="Commit message for artifact commits",
    )


class LedgerConfig(BaseModel):
    """
    Ledger (completed work tracking) configuration.

    Controls whether ledger entries are created automatically when tasks close.
    """

    enabled: bool = Field(
        default=True,
        description="Enable automatic ledger entry creation on task completion",
    )


class SyncConfig(BaseModel):
    """
    Task sync configuration.

    Controls automatic synchronization of task state to the cub-sync branch.
    """

    enabled: bool = Field(
        default=True,
        description="Enable sync functionality (if False, sync commands will fail)",
    )
    auto_sync: str = Field(
        default="run",
        pattern="^(always|run|never)$",
        description=(
            "When to auto-sync: 'always' (after every task mutation), "
            "'run' (only during cub run), 'never' (manual sync only)"
        ),
    )


class CircuitBreakerConfig(BaseModel):
    """
    Circuit breaker configuration for stagnation detection.

    Monitors harness activity and stops execution if no progress is detected
    for the configured timeout period. This prevents infinite hangs where the
    harness becomes unresponsive but the process continues.
    """

    enabled: bool = Field(
        default=True,
        description="Enable circuit breaker stagnation detection",
    )
    timeout_minutes: int = Field(
        default=30,
        ge=1,
        description="Stop if no harness activity for this many minutes",
    )


class MapConfig(BaseModel):
    """
    Configuration for cub map command.

    Controls how the codebase map is generated, including token budgets,
    traversal depth, and what metadata to include.
    """

    token_budget: int = Field(
        default=1500,
        ge=1,
        description="Maximum tokens to allocate for the map output",
    )
    max_depth: int = Field(
        default=4,
        ge=1,
        description="Maximum directory depth to traverse",
    )
    include_code_intel: bool = Field(
        default=True,
        description="Include code intelligence (imports, exports, key functions)",
    )
    include_ledger_stats: bool = Field(
        default=True,
        description="Include statistics from the ledger (completed work)",
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "node_modules/**",
            ".git/**",
            ".venv/**",
            "venv/**",
            "__pycache__/**",
            "*.pyc",
            ".mypy_cache/**",
            ".pytest_cache/**",
            ".ruff_cache/**",
            "build/**",
            "dist/**",
            "*.egg-info/**",
            ".tox/**",
            "coverage/**",
            ".coverage",
            "htmlcov/**",
            ".DS_Store",
            "*.min.js",
            "*.min.css",
        ],
        description="Glob patterns to exclude from the map",
    )


class BackendConfig(BaseModel):
    """
    Task backend configuration.

    Specifies which task backend to use or enables dual-backend mode.
    """

    mode: str | None = Field(
        default=None,
        description=(
            "Backend mode: 'auto' (auto-detect), 'beads', 'jsonl', 'both' "
            "(dual-backend with divergence detection)"
        ),
    )


class TaskConfig(BaseModel):
    """
    Task identification and context configuration.

    Controls how tasks are identified in user prompts and how their details
    are provided as context to the AI harness.
    """

    id_pattern: str = Field(
        default=r"cub-[\w.-]+",
        description=(
            "Regex pattern for task ID detection in user prompts. "
            "Default: 'cub-[\\w.-]+' matches IDs like 'cub-042', 'cub-w3f.2'. "
            "Use configurable prefix for custom task ID formats."
        ),
    )
    inject_context: bool = Field(
        default=True,
        description="Inject task details as additionalContext when task ID is mentioned in prompt",
    )


class HarnessConfig(BaseModel):
    """
    AI harness configuration.

    Specifies which AI assistant to use and how to invoke it.
    """

    name: str | None = Field(
        default=None, description="Harness name: 'claude', 'codex', 'gemini', 'opencode', etc."
    )
    priority: list[str] = Field(
        default_factory=lambda: ["claude", "codex"], description="Auto-detection priority order"
    )
    model: str | None = Field(
        default=None, description="Specific model to use (e.g., 'sonnet', 'haiku')"
    )


class CubConfig(BaseModel):
    """
    Top-level cub configuration.

    This is the root configuration model that encompasses all settings.
    It's loaded from defaults, user config, project config, and env vars.

    Example:
        >>> config = CubConfig(
        ...     harness=HarnessConfig(name="claude"),
        ...     budget=BudgetConfig(max_tokens_per_task=500000),
        ...     state=StateConfig(require_clean=True, run_tests=True)
        ... )
        >>> config.state.require_clean
        True
    """

    # Core settings
    dev_mode: bool = Field(
        default=False,
        description=(
            "Development mode: use local uv-managed installation for hooks. "
            "Set to true when developing cub itself, false for production use."
        ),
    )
    backend: BackendConfig = Field(
        default_factory=BackendConfig, description="Task backend configuration"
    )
    task: TaskConfig = Field(
        default_factory=TaskConfig, description="Task identification and context configuration"
    )
    harness: HarnessConfig = Field(
        default_factory=HarnessConfig, description="AI harness configuration"
    )
    budget: BudgetConfig = Field(default_factory=BudgetConfig, description="Token and cost budgets")
    guardrails: GuardrailsConfig = Field(
        default_factory=GuardrailsConfig, description="Safety limits and guardrails"
    )

    # Execution control
    state: StateConfig = Field(default_factory=StateConfig, description="Pre-flight state checks")
    loop: LoopConfig = Field(default_factory=LoopConfig, description="Autonomous loop behavior")

    # Optional features
    hooks: HooksConfig = Field(default_factory=HooksConfig, description="Lifecycle hooks")
    interview: InterviewConfig = Field(
        default_factory=InterviewConfig, description="Task interview questions"
    )
    review: ReviewConfig = Field(
        default_factory=ReviewConfig, description="Review and approval settings"
    )
    cleanup: CleanupConfig = Field(
        default_factory=CleanupConfig, description="Post-run cleanup settings"
    )
    ledger: LedgerConfig = Field(
        default_factory=LedgerConfig, description="Ledger (completed work tracking) settings"
    )
    sync: SyncConfig = Field(default_factory=SyncConfig, description="Task sync settings")
    circuit_breaker: CircuitBreakerConfig = Field(
        default_factory=CircuitBreakerConfig,
        description="Circuit breaker stagnation detection settings",
    )
    map: MapConfig = Field(
        default_factory=MapConfig,
        description="Codebase map generation settings",
    )

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for forward compatibility
        validate_assignment=True,  # Validate on field assignment
    )

    @field_validator("harness", mode="before")
    @classmethod
    def validate_harness(
        cls, v: str | dict[str, Any] | HarnessConfig
    ) -> dict[str, Any] | HarnessConfig:
        """Convert string harness name to HarnessConfig."""
        if isinstance(v, str):
            return {"name": v}
        return v
