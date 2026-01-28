"""
Budget tracking and enforcement for cub run sessions.

Provides business logic for token counting, cost accounting, and limit enforcement,
separated from CLI concerns. This module can be used by any interface (CLI, API, skills).

Basic Usage:
    >>> from cub.core.run.budget import BudgetManager, BudgetConfig, BudgetState
    >>> config = BudgetConfig(tokens_limit=100000, cost_limit=5.0)
    >>> manager = BudgetManager(config)
    >>> manager.record_usage(tokens=1000, cost_usd=0.05)
    >>> decision = manager.check_limit()
    >>> if decision.should_stop:
    ...     print(f"Budget exceeded: {decision.reason}")

Migration from cli/run.py pattern:

    Before (direct BudgetStatus manipulation):
        status.budget.tokens_used += result.usage.total_tokens
        if result.usage.cost_usd:
            status.budget.cost_usd += result.usage.cost_usd

        if status.budget.is_over_budget:
            console.print("[yellow]Budget exhausted. Stopping.[/yellow]")
            break

        budget_pct = status.budget.tokens_percentage or status.budget.cost_percentage
        if budget_pct and budget_pct >= threshold:
            console.print(f"[yellow]Budget warning: {budget_pct:.1f}% used[/yellow]")

    After (using BudgetManager):
        # Initialize manager from config
        from cub.core.run.budget import BudgetManager, BudgetConfig

        budget_config = BudgetConfig(
            tokens_limit=budget_tokens or config.budget.max_tokens_per_task,
            cost_limit=budget or config.budget.max_total_cost,
            tasks_limit=config.budget.max_tasks_per_session,
        )
        budget_manager = BudgetManager(budget_config)

        # Record usage
        budget_manager.record_usage(
            tokens=result.usage.total_tokens,
            cost_usd=result.usage.cost_usd or 0.0
        )

        # Check hard limits
        limit_check = budget_manager.check_limit()
        if limit_check.should_stop:
            console.print(f"[yellow]{limit_check.reason}. Stopping.[/yellow]")
            break

        # Check warning threshold
        warning = budget_manager.check_warning_threshold(0.8)
        if warning and not budget_warning_fired:
            budget_warning_fired = True
            console.print(f"[yellow]Budget warning: {warning.reason}[/yellow]")

        # Sync state back to status for persistence
        status.budget.tokens_used = budget_manager.state.tokens_used
        status.budget.cost_usd = budget_manager.state.cost_usd
        status.budget.tasks_completed = budget_manager.state.tasks_completed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class BudgetConfig(BaseModel):
    """
    Budget limits configuration.

    Defines the maximum allowed spending for a run session.
    All limits are optional - None or 0 means unlimited.
    """

    tokens_limit: int | None = Field(
        default=None, ge=1, description="Maximum tokens allowed (None = unlimited)"
    )
    cost_limit: float | None = Field(
        default=None, ge=0.0, description="Maximum cost in USD (None = unlimited)"
    )
    tasks_limit: int | None = Field(
        default=None, ge=1, description="Maximum tasks per session (None = unlimited)"
    )


class BudgetState(BaseModel):
    """
    Current budget usage state.

    Tracks accumulated spending during a run session.
    This model is mutable to allow incremental updates.
    """

    tokens_used: int = Field(default=0, ge=0, description="Total tokens consumed")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost in USD")
    tasks_completed: int = Field(default=0, ge=0, description="Number of tasks completed")

    model_config = {"validate_assignment": True}

    def record_tokens(self, tokens: int) -> None:
        """Record token usage."""
        if tokens < 0:
            raise ValueError(f"tokens must be >= 0, got {tokens}")
        self.tokens_used += tokens

    def record_cost(self, cost_usd: float) -> None:
        """Record cost in USD."""
        if cost_usd < 0:
            raise ValueError(f"cost_usd must be >= 0, got {cost_usd}")
        self.cost_usd += cost_usd

    def record_task_completion(self) -> None:
        """Record a completed task."""
        self.tasks_completed += 1


@dataclass(frozen=True)
class BudgetCheckResult:
    """
    Result of a budget limit check.

    Indicates whether execution should continue or stop based on budget limits.
    """

    should_stop: bool
    reason: str | None = None
    limit_type: Literal["tokens", "cost", "tasks"] | None = None
    percentage_used: float | None = None


class BudgetManager:
    """
    Manager for budget tracking and limit enforcement.

    Encapsulates all budget-related business logic including:
    - Token tracking
    - Cost accumulation
    - Limit checking
    - Warning thresholds

    Example:
        >>> config = BudgetConfig(tokens_limit=100000)
        >>> manager = BudgetManager(config)
        >>> manager.record_usage(tokens=1000, cost_usd=0.05)
        >>> result = manager.check_limit()
        >>> if result.should_stop:
        ...     print(f"Stop: {result.reason}")
    """

    def __init__(self, config: BudgetConfig, state: BudgetState | None = None) -> None:
        """
        Initialize the budget manager.

        Args:
            config: Budget limits configuration
            state: Optional existing state (for resuming sessions)
        """
        self._config = config
        self._state = state or BudgetState()

    @property
    def config(self) -> BudgetConfig:
        """Get the budget configuration."""
        return self._config

    @property
    def state(self) -> BudgetState:
        """Get the current budget state."""
        return self._state

    def record_usage(self, tokens: int = 0, cost_usd: float = 0.0) -> None:
        """
        Record token and cost usage.

        Args:
            tokens: Number of tokens used
            cost_usd: Cost in USD

        Raises:
            ValueError: If tokens or cost_usd are negative
        """
        if tokens > 0:
            self._state.record_tokens(tokens)
        if cost_usd > 0:
            self._state.record_cost(cost_usd)

    def record_task_completion(self) -> None:
        """Record a completed task."""
        self._state.record_task_completion()

    def check_limit(self) -> BudgetCheckResult:
        """
        Check if any budget limit has been exceeded.

        Returns:
            BudgetCheckResult indicating whether to stop and why

        Example:
            >>> manager = BudgetManager(BudgetConfig(tokens_limit=1000))
            >>> manager.record_usage(tokens=1001)
            >>> result = manager.check_limit()
            >>> result.should_stop
            True
            >>> result.limit_type
            'tokens'
        """
        # Check token limit
        if self._config.tokens_limit is not None and self._config.tokens_limit > 0:
            if self._state.tokens_used >= self._config.tokens_limit:
                pct = (self._state.tokens_used / self._config.tokens_limit) * 100
                reason = (
                    f"Token limit exceeded: {self._state.tokens_used:,} / "
                    f"{self._config.tokens_limit:,}"
                )
                return BudgetCheckResult(
                    should_stop=True,
                    reason=reason,
                    limit_type="tokens",
                    percentage_used=pct,
                )

        # Check cost limit
        if self._config.cost_limit is not None and self._config.cost_limit > 0:
            if self._state.cost_usd >= self._config.cost_limit:
                pct = (self._state.cost_usd / self._config.cost_limit) * 100
                reason = (
                    f"Cost limit exceeded: ${self._state.cost_usd:.4f} / "
                    f"${self._config.cost_limit:.4f}"
                )
                return BudgetCheckResult(
                    should_stop=True,
                    reason=reason,
                    limit_type="cost",
                    percentage_used=pct,
                )

        # Check task limit
        if self._config.tasks_limit is not None and self._config.tasks_limit > 0:
            if self._state.tasks_completed >= self._config.tasks_limit:
                pct = (self._state.tasks_completed / self._config.tasks_limit) * 100
                reason = (
                    f"Task limit exceeded: {self._state.tasks_completed} / "
                    f"{self._config.tasks_limit}"
                )
                return BudgetCheckResult(
                    should_stop=True,
                    reason=reason,
                    limit_type="tasks",
                    percentage_used=pct,
                )

        # No limits exceeded
        return BudgetCheckResult(should_stop=False)

    def check_warning_threshold(self, threshold: float = 0.8) -> BudgetCheckResult | None:
        """
        Check if budget usage is approaching any limit.

        Args:
            threshold: Warning threshold as a percentage (0.0-1.0)

        Returns:
            BudgetCheckResult if threshold exceeded, None otherwise

        Example:
            >>> manager = BudgetManager(BudgetConfig(tokens_limit=1000))
            >>> manager.record_usage(tokens=850)
            >>> result = manager.check_warning_threshold(0.8)
            >>> result is not None
            True
            >>> result.percentage_used
            85.0
        """
        if threshold < 0 or threshold > 1:
            raise ValueError(f"threshold must be between 0 and 1, got {threshold}")

        threshold_pct = threshold * 100

        # Check token warning
        if self._config.tokens_limit is not None and self._config.tokens_limit > 0:
            pct = (self._state.tokens_used / self._config.tokens_limit) * 100
            if pct >= threshold_pct:
                reason = (
                    f"Token budget at {pct:.1f}% ({self._state.tokens_used:,} / "
                    f"{self._config.tokens_limit:,})"
                )
                return BudgetCheckResult(
                    should_stop=False,
                    reason=reason,
                    limit_type="tokens",
                    percentage_used=pct,
                )

        # Check cost warning
        if self._config.cost_limit is not None and self._config.cost_limit > 0:
            pct = (self._state.cost_usd / self._config.cost_limit) * 100
            if pct >= threshold_pct:
                reason = (
                    f"Cost budget at {pct:.1f}% (${self._state.cost_usd:.4f} / "
                    f"${self._config.cost_limit:.4f})"
                )
                return BudgetCheckResult(
                    should_stop=False,
                    reason=reason,
                    limit_type="cost",
                    percentage_used=pct,
                )

        # Check task warning
        if self._config.tasks_limit is not None and self._config.tasks_limit > 0:
            pct = (self._state.tasks_completed / self._config.tasks_limit) * 100
            if pct >= threshold_pct:
                reason = (
                    f"Task budget at {pct:.1f}% ({self._state.tasks_completed} / "
                    f"{self._config.tasks_limit})"
                )
                return BudgetCheckResult(
                    should_stop=False,
                    reason=reason,
                    limit_type="tasks",
                    percentage_used=pct,
                )

        return None

    def get_percentage(self, limit_type: Literal["tokens", "cost", "tasks"]) -> float | None:
        """
        Get the percentage used for a specific limit type.

        Args:
            limit_type: Type of limit to check

        Returns:
            Percentage used (0-100+), or None if limit not set

        Example:
            >>> manager = BudgetManager(BudgetConfig(tokens_limit=1000))
            >>> manager.record_usage(tokens=250)
            >>> manager.get_percentage("tokens")
            25.0
        """
        if limit_type == "tokens":
            if self._config.tokens_limit is None or self._config.tokens_limit == 0:
                return None
            return (self._state.tokens_used / self._config.tokens_limit) * 100
        elif limit_type == "cost":
            if self._config.cost_limit is None or self._config.cost_limit == 0:
                return None
            return (self._state.cost_usd / self._config.cost_limit) * 100
        elif limit_type == "tasks":
            if self._config.tasks_limit is None or self._config.tasks_limit == 0:
                return None
            return (self._state.tasks_completed / self._config.tasks_limit) * 100
        else:
            raise ValueError(f"Invalid limit_type: {limit_type}")

    def has_any_limit(self) -> bool:
        """
        Check if any budget limit is configured.

        Returns:
            True if at least one limit is set, False otherwise
        """
        return (
            (self._config.tokens_limit is not None and self._config.tokens_limit > 0)
            or (self._config.cost_limit is not None and self._config.cost_limit > 0)
            or (self._config.tasks_limit is not None and self._config.tasks_limit > 0)
        )
