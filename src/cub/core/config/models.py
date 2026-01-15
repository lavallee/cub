"""
Configuration data models for cub.

These models define the structure of .cub.json and ~/.config/cub/config.json
files, with validation and type safety via Pydantic.
"""

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GuardrailsConfig(BaseModel):
    """
    Safety limits and guardrails for autonomous execution.

    These settings prevent runaway costs and infinite loops.
    """
    max_task_iterations: int = Field(
        default=3,
        ge=1,
        description="Maximum iterations per task before failing"
    )
    max_run_iterations: int = Field(
        default=50,
        ge=1,
        description="Maximum total iterations before stopping the run"
    )
    iteration_warning_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Warn when iterations reach this fraction of max (0.0-1.0)"
    )
    secret_patterns: list[str] = Field(
        default_factory=lambda: [
            "api[_-]?key",
            "password",
            "token",
            "secret",
            "authorization",
            "credentials"
        ],
        description="Regex patterns for detecting secrets in code"
    )


class BudgetConfig(BaseModel):
    """
    Token and cost budgets for AI operations.

    Controls spending limits for autonomous sessions.
    """
    max_tokens_per_task: Optional[int] = Field(
        default=None,
        ge=1,
        description="Stop if a single task uses more than this many tokens"
    )
    max_tasks_per_session: Optional[int] = Field(
        default=None,
        ge=1,
        description="Stop after completing this many tasks in one session"
    )
    max_total_cost: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Stop if total spend exceeds this amount (in dollars)"
    )
    default: Optional[int] = Field(
        default=None,
        ge=1,
        description="Default budget if not specified (for backward compatibility)"
    )


class StateConfig(BaseModel):
    """
    Pre-flight checks before running tasks.

    Ensures repository is in a safe state before autonomous execution.
    """
    require_clean: bool = Field(
        default=True,
        description="Fail if git has uncommitted changes"
    )
    run_tests: bool = Field(
        default=False,
        description="Run tests and fail if they don't pass"
    )
    run_typecheck: bool = Field(
        default=False,
        description="Run type checker and fail if there are errors"
    )
    run_lint: bool = Field(
        default=False,
        description="Run linter and fail if there are issues"
    )


class LoopConfig(BaseModel):
    """
    Control autonomous loop behavior.

    Determines how cub handles the task processing loop.
    """
    max_iterations: int = Field(
        default=100,
        ge=1,
        description="Stop after N iterations (prevents infinite loops)"
    )
    on_task_failure: str = Field(
        default="stop",
        pattern="^(stop|continue)$",
        description="What to do when a task fails: 'stop' or 'continue'"
    )


class HooksConfig(BaseModel):
    """
    Lifecycle hooks configuration.

    Enables running custom scripts before/after events.
    """
    enabled: bool = Field(
        default=True,
        description="Enable/disable all hooks"
    )
    fail_fast: bool = Field(
        default=False,
        description="Stop execution if a hook fails"
    )


class InterviewQuestion(BaseModel):
    """A custom interview question for task planning."""
    category: str = Field(..., description="Question category/section")
    question: str = Field(..., description="The question to ask")
    applies_to: list[str] = Field(
        default_factory=list,
        description="Task types this question applies to (feature, task, bugfix)"
    )
    requires_labels: list[str] = Field(
        default_factory=list,
        description="Only ask if task has these labels"
    )
    requires_tech: list[str] = Field(
        default_factory=list,
        description="Only ask if task involves these technologies"
    )
    skip_if: Optional[dict[str, Any]] = Field(
        default=None,
        description="Conditional skip logic based on previous answers"
    )


class InterviewConfig(BaseModel):
    """
    Task interview/specification configuration.

    Defines custom questions to ask during task planning.
    """
    custom_questions: list[InterviewQuestion] = Field(
        default_factory=list,
        description="Project-specific interview questions"
    )


class ReviewConfig(BaseModel):
    """
    Task and plan review configuration.

    Controls how strict cub is about reviewing work.
    """
    plan_strict: bool = Field(
        default=False,
        description="Require plan approval before execution"
    )
    block_on_concerns: bool = Field(
        default=False,
        description="Block execution if review raises concerns"
    )


class HarnessConfig(BaseModel):
    """
    AI harness configuration.

    Specifies which AI assistant to use and how to invoke it.
    """
    name: Optional[str] = Field(
        default=None,
        description="Harness name: 'claude', 'codex', 'gemini', 'opencode', etc."
    )
    priority: list[str] = Field(
        default_factory=lambda: ["claude", "codex"],
        description="Auto-detection priority order"
    )
    model: Optional[str] = Field(
        default=None,
        description="Specific model to use (e.g., 'sonnet', 'haiku')"
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
    harness: HarnessConfig = Field(
        default_factory=HarnessConfig,
        description="AI harness configuration"
    )
    budget: BudgetConfig = Field(
        default_factory=BudgetConfig,
        description="Token and cost budgets"
    )
    guardrails: GuardrailsConfig = Field(
        default_factory=GuardrailsConfig,
        description="Safety limits and guardrails"
    )

    # Execution control
    state: StateConfig = Field(
        default_factory=StateConfig,
        description="Pre-flight state checks"
    )
    loop: LoopConfig = Field(
        default_factory=LoopConfig,
        description="Autonomous loop behavior"
    )

    # Optional features
    hooks: HooksConfig = Field(
        default_factory=HooksConfig,
        description="Lifecycle hooks"
    )
    interview: InterviewConfig = Field(
        default_factory=InterviewConfig,
        description="Task interview questions"
    )
    review: ReviewConfig = Field(
        default_factory=ReviewConfig,
        description="Review and approval settings"
    )

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for forward compatibility
        validate_assignment=True,  # Validate on field assignment
    )

    @field_validator('harness', mode='before')
    @classmethod
    def validate_harness(cls, v: Union[str, dict, HarnessConfig]) -> Union[dict, HarnessConfig]:
        """Convert string harness name to HarnessConfig."""
        if isinstance(v, str):
            return {"name": v}
        return v
