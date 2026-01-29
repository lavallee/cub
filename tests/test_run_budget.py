"""
Unit tests for cub.core.run.budget.

Tests budget tracking and limit enforcement in isolation, imported directly
from the core package rather than via cli/run.py.
"""

from __future__ import annotations

import pytest

from cub.core.run.budget import (
    BudgetCheckResult,
    BudgetConfig,
    BudgetManager,
    BudgetState,
)


# ===========================================================================
# BudgetConfig model
# ===========================================================================


class TestBudgetConfig:
    """Tests for the BudgetConfig model."""

    def test_default_values(self) -> None:
        """Default config has no limits."""
        config = BudgetConfig()
        assert config.tokens_limit is None
        assert config.cost_limit is None
        assert config.tasks_limit is None

    def test_set_token_limit(self) -> None:
        """Can set token limit."""
        config = BudgetConfig(tokens_limit=100000)
        assert config.tokens_limit == 100000

    def test_set_cost_limit(self) -> None:
        """Can set cost limit."""
        config = BudgetConfig(cost_limit=5.0)
        assert config.cost_limit == 5.0

    def test_set_tasks_limit(self) -> None:
        """Can set tasks limit."""
        config = BudgetConfig(tasks_limit=10)
        assert config.tasks_limit == 10

    def test_set_all_limits(self) -> None:
        """Can set all limits at once."""
        config = BudgetConfig(tokens_limit=100000, cost_limit=5.0, tasks_limit=10)
        assert config.tokens_limit == 100000
        assert config.cost_limit == 5.0
        assert config.tasks_limit == 10

    def test_rejects_negative_token_limit(self) -> None:
        """Token limit must be >= 1 if provided."""
        with pytest.raises(ValueError):
            BudgetConfig(tokens_limit=0)

    def test_rejects_negative_cost_limit(self) -> None:
        """Cost limit must be >= 0 if provided."""
        with pytest.raises(ValueError):
            BudgetConfig(cost_limit=-1.0)

    def test_rejects_negative_tasks_limit(self) -> None:
        """Tasks limit must be >= 1 if provided."""
        with pytest.raises(ValueError):
            BudgetConfig(tasks_limit=0)


# ===========================================================================
# BudgetState model
# ===========================================================================


class TestBudgetState:
    """Tests for the BudgetState model."""

    def test_default_values(self) -> None:
        """Default state has zero usage."""
        state = BudgetState()
        assert state.tokens_used == 0
        assert state.cost_usd == 0.0
        assert state.tasks_completed == 0

    def test_record_tokens(self) -> None:
        """Can record token usage."""
        state = BudgetState()
        state.record_tokens(1000)
        assert state.tokens_used == 1000

    def test_record_tokens_accumulates(self) -> None:
        """Token recording accumulates."""
        state = BudgetState()
        state.record_tokens(1000)
        state.record_tokens(500)
        assert state.tokens_used == 1500

    def test_record_tokens_rejects_negative(self) -> None:
        """Cannot record negative tokens."""
        state = BudgetState()
        with pytest.raises(ValueError, match="tokens must be >= 0"):
            state.record_tokens(-100)

    def test_record_cost(self) -> None:
        """Can record cost."""
        state = BudgetState()
        state.record_cost(0.50)
        assert state.cost_usd == 0.50

    def test_record_cost_accumulates(self) -> None:
        """Cost recording accumulates."""
        state = BudgetState()
        state.record_cost(0.25)
        state.record_cost(0.75)
        assert state.cost_usd == 1.0

    def test_record_cost_rejects_negative(self) -> None:
        """Cannot record negative cost."""
        state = BudgetState()
        with pytest.raises(ValueError, match="cost_usd must be >= 0"):
            state.record_cost(-0.50)

    def test_record_task_completion(self) -> None:
        """Can record task completion."""
        state = BudgetState()
        state.record_task_completion()
        assert state.tasks_completed == 1

    def test_record_task_completion_increments(self) -> None:
        """Task completion increments counter."""
        state = BudgetState()
        state.record_task_completion()
        state.record_task_completion()
        state.record_task_completion()
        assert state.tasks_completed == 3

    def test_initial_state_with_values(self) -> None:
        """Can initialize state with existing values."""
        state = BudgetState(tokens_used=5000, cost_usd=2.5, tasks_completed=3)
        assert state.tokens_used == 5000
        assert state.cost_usd == 2.5
        assert state.tasks_completed == 3

    def test_validates_assignment(self) -> None:
        """State validates values on assignment."""
        state = BudgetState()
        with pytest.raises(ValueError):
            state.tokens_used = -100


# ===========================================================================
# BudgetCheckResult dataclass
# ===========================================================================


class TestBudgetCheckResult:
    """Tests for the BudgetCheckResult dataclass."""

    def test_continue_result(self) -> None:
        """Result for continuing execution."""
        result = BudgetCheckResult(should_stop=False)
        assert result.should_stop is False
        assert result.reason is None
        assert result.limit_type is None
        assert result.percentage_used is None

    def test_stop_result_with_details(self) -> None:
        """Result for stopping execution with details."""
        result = BudgetCheckResult(
            should_stop=True,
            reason="Token limit exceeded",
            limit_type="tokens",
            percentage_used=105.5,
        )
        assert result.should_stop is True
        assert result.reason == "Token limit exceeded"
        assert result.limit_type == "tokens"
        assert result.percentage_used == 105.5

    def test_is_frozen(self) -> None:
        """Result is immutable."""
        result = BudgetCheckResult(should_stop=False)
        with pytest.raises(AttributeError):
            result.should_stop = True  # type: ignore[misc]


# ===========================================================================
# BudgetManager - Initialization
# ===========================================================================


class TestBudgetManagerInit:
    """Tests for BudgetManager initialization."""

    def test_init_with_config(self) -> None:
        """Can initialize with config."""
        config = BudgetConfig(tokens_limit=100000)
        manager = BudgetManager(config)
        assert manager.config == config
        assert manager.state.tokens_used == 0

    def test_init_with_config_and_state(self) -> None:
        """Can initialize with existing state."""
        config = BudgetConfig(tokens_limit=100000)
        state = BudgetState(tokens_used=5000, cost_usd=2.5)
        manager = BudgetManager(config, state)
        assert manager.config == config
        assert manager.state == state
        assert manager.state.tokens_used == 5000

    def test_init_creates_new_state_if_not_provided(self) -> None:
        """Creates fresh state if not provided."""
        config = BudgetConfig()
        manager = BudgetManager(config)
        assert isinstance(manager.state, BudgetState)
        assert manager.state.tokens_used == 0


# ===========================================================================
# BudgetManager - Recording usage
# ===========================================================================


class TestBudgetManagerRecordUsage:
    """Tests for BudgetManager.record_usage."""

    def test_record_tokens_only(self) -> None:
        """Can record token usage only."""
        manager = BudgetManager(BudgetConfig())
        manager.record_usage(tokens=1000)
        assert manager.state.tokens_used == 1000
        assert manager.state.cost_usd == 0.0

    def test_record_cost_only(self) -> None:
        """Can record cost only."""
        manager = BudgetManager(BudgetConfig())
        manager.record_usage(cost_usd=0.50)
        assert manager.state.tokens_used == 0
        assert manager.state.cost_usd == 0.50

    def test_record_both_tokens_and_cost(self) -> None:
        """Can record both tokens and cost."""
        manager = BudgetManager(BudgetConfig())
        manager.record_usage(tokens=1000, cost_usd=0.05)
        assert manager.state.tokens_used == 1000
        assert manager.state.cost_usd == 0.05

    def test_record_usage_accumulates(self) -> None:
        """Multiple record calls accumulate."""
        manager = BudgetManager(BudgetConfig())
        manager.record_usage(tokens=1000, cost_usd=0.05)
        manager.record_usage(tokens=500, cost_usd=0.03)
        assert manager.state.tokens_used == 1500
        assert manager.state.cost_usd == 0.08

    def test_record_usage_with_zero_values(self) -> None:
        """Zero values don't change state."""
        manager = BudgetManager(BudgetConfig())
        manager.record_usage(tokens=0, cost_usd=0.0)
        assert manager.state.tokens_used == 0
        assert manager.state.cost_usd == 0.0

    def test_record_task_completion(self) -> None:
        """Can record task completion."""
        manager = BudgetManager(BudgetConfig())
        manager.record_task_completion()
        assert manager.state.tasks_completed == 1


# ===========================================================================
# BudgetManager - Limit checking
# ===========================================================================


class TestBudgetManagerCheckLimit:
    """Tests for BudgetManager.check_limit."""

    def test_no_limits_configured(self) -> None:
        """Returns continue when no limits configured."""
        manager = BudgetManager(BudgetConfig())
        manager.record_usage(tokens=999999, cost_usd=999.99)
        result = manager.check_limit()
        assert result.should_stop is False

    def test_under_token_limit(self) -> None:
        """Returns continue when under token limit."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=5000)
        result = manager.check_limit()
        assert result.should_stop is False

    def test_at_token_limit(self) -> None:
        """Returns stop when at token limit."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=10000)
        result = manager.check_limit()
        assert result.should_stop is True
        assert result.limit_type == "tokens"
        assert "Token limit exceeded" in result.reason

    def test_over_token_limit(self) -> None:
        """Returns stop when over token limit."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=15000)
        result = manager.check_limit()
        assert result.should_stop is True
        assert result.limit_type == "tokens"
        assert result.percentage_used == 150.0

    def test_under_cost_limit(self) -> None:
        """Returns continue when under cost limit."""
        manager = BudgetManager(BudgetConfig(cost_limit=5.0))
        manager.record_usage(cost_usd=2.5)
        result = manager.check_limit()
        assert result.should_stop is False

    def test_at_cost_limit(self) -> None:
        """Returns stop when at cost limit."""
        manager = BudgetManager(BudgetConfig(cost_limit=5.0))
        manager.record_usage(cost_usd=5.0)
        result = manager.check_limit()
        assert result.should_stop is True
        assert result.limit_type == "cost"
        assert "Cost limit exceeded" in result.reason

    def test_over_cost_limit(self) -> None:
        """Returns stop when over cost limit."""
        manager = BudgetManager(BudgetConfig(cost_limit=5.0))
        manager.record_usage(cost_usd=7.5)
        result = manager.check_limit()
        assert result.should_stop is True
        assert result.limit_type == "cost"
        assert result.percentage_used == 150.0

    def test_under_tasks_limit(self) -> None:
        """Returns continue when under tasks limit."""
        manager = BudgetManager(BudgetConfig(tasks_limit=10))
        manager.record_task_completion()
        manager.record_task_completion()
        result = manager.check_limit()
        assert result.should_stop is False

    def test_at_tasks_limit(self) -> None:
        """Returns stop when at tasks limit."""
        manager = BudgetManager(BudgetConfig(tasks_limit=3))
        manager.record_task_completion()
        manager.record_task_completion()
        manager.record_task_completion()
        result = manager.check_limit()
        assert result.should_stop is True
        assert result.limit_type == "tasks"
        assert "Task limit exceeded" in result.reason

    def test_over_tasks_limit(self) -> None:
        """Returns stop when over tasks limit."""
        manager = BudgetManager(BudgetConfig(tasks_limit=5))
        for _ in range(10):
            manager.record_task_completion()
        result = manager.check_limit()
        assert result.should_stop is True
        assert result.limit_type == "tasks"
        assert result.percentage_used == 200.0

    def test_token_limit_takes_precedence(self) -> None:
        """Token limit checked first when multiple limits exceeded."""
        manager = BudgetManager(
            BudgetConfig(tokens_limit=1000, cost_limit=1.0, tasks_limit=5)
        )
        manager.record_usage(tokens=2000, cost_usd=2.0)
        for _ in range(10):
            manager.record_task_completion()
        result = manager.check_limit()
        assert result.should_stop is True
        assert result.limit_type == "tokens"

    def test_includes_formatted_numbers(self) -> None:
        """Result includes formatted numbers in reason."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=15000)
        result = manager.check_limit()
        assert "15,000" in result.reason
        assert "10,000" in result.reason


# ===========================================================================
# BudgetManager - Warning thresholds
# ===========================================================================


class TestBudgetManagerCheckWarningThreshold:
    """Tests for BudgetManager.check_warning_threshold."""

    def test_no_warning_when_under_threshold(self) -> None:
        """Returns None when under warning threshold."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=7000)
        result = manager.check_warning_threshold(0.8)
        assert result is None

    def test_warning_at_threshold(self) -> None:
        """Returns result when at warning threshold."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=8000)
        result = manager.check_warning_threshold(0.8)
        assert result is not None
        assert result.should_stop is False
        assert result.limit_type == "tokens"
        assert result.percentage_used == 80.0

    def test_warning_over_threshold(self) -> None:
        """Returns result when over warning threshold."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=9500)
        result = manager.check_warning_threshold(0.8)
        assert result is not None
        assert result.percentage_used == 95.0

    def test_cost_warning(self) -> None:
        """Can warn on cost threshold."""
        manager = BudgetManager(BudgetConfig(cost_limit=5.0))
        manager.record_usage(cost_usd=4.5)
        result = manager.check_warning_threshold(0.8)
        assert result is not None
        assert result.limit_type == "cost"
        assert result.percentage_used == 90.0

    def test_tasks_warning(self) -> None:
        """Can warn on tasks threshold."""
        manager = BudgetManager(BudgetConfig(tasks_limit=10))
        for _ in range(9):
            manager.record_task_completion()
        result = manager.check_warning_threshold(0.8)
        assert result is not None
        assert result.limit_type == "tasks"
        assert result.percentage_used == 90.0

    def test_custom_warning_threshold(self) -> None:
        """Can use custom warning threshold."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=9000)
        # At 90%, threshold 0.9 should trigger
        result = manager.check_warning_threshold(0.9)
        assert result is not None
        # At 90%, threshold 0.95 should not trigger
        result = manager.check_warning_threshold(0.95)
        assert result is None

    def test_rejects_invalid_threshold(self) -> None:
        """Rejects threshold outside 0-1 range."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
            manager.check_warning_threshold(1.5)
        with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
            manager.check_warning_threshold(-0.1)

    def test_no_warning_when_no_limits(self) -> None:
        """Returns None when no limits configured."""
        manager = BudgetManager(BudgetConfig())
        manager.record_usage(tokens=999999)
        result = manager.check_warning_threshold(0.8)
        assert result is None

    def test_token_warning_takes_precedence(self) -> None:
        """Token warning checked first when multiple over threshold."""
        manager = BudgetManager(
            BudgetConfig(tokens_limit=1000, cost_limit=1.0, tasks_limit=10)
        )
        manager.record_usage(tokens=850, cost_usd=0.85)
        for _ in range(9):
            manager.record_task_completion()
        result = manager.check_warning_threshold(0.8)
        assert result is not None
        assert result.limit_type == "tokens"


# ===========================================================================
# BudgetManager - Percentage calculations
# ===========================================================================


class TestBudgetManagerGetPercentage:
    """Tests for BudgetManager.get_percentage."""

    def test_token_percentage(self) -> None:
        """Can get token percentage."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        manager.record_usage(tokens=2500)
        pct = manager.get_percentage("tokens")
        assert pct == 25.0

    def test_cost_percentage(self) -> None:
        """Can get cost percentage."""
        manager = BudgetManager(BudgetConfig(cost_limit=5.0))
        manager.record_usage(cost_usd=1.25)
        pct = manager.get_percentage("cost")
        assert pct == 25.0

    def test_tasks_percentage(self) -> None:
        """Can get tasks percentage."""
        manager = BudgetManager(BudgetConfig(tasks_limit=10))
        manager.record_task_completion()
        manager.record_task_completion()
        pct = manager.get_percentage("tasks")
        assert pct == 20.0

    def test_returns_none_when_no_limit(self) -> None:
        """Returns None when limit not set."""
        manager = BudgetManager(BudgetConfig())
        assert manager.get_percentage("tokens") is None
        assert manager.get_percentage("cost") is None
        assert manager.get_percentage("tasks") is None

    def test_over_100_percent(self) -> None:
        """Can return percentage over 100."""
        manager = BudgetManager(BudgetConfig(tokens_limit=1000))
        manager.record_usage(tokens=1500)
        pct = manager.get_percentage("tokens")
        assert pct == 150.0

    def test_rejects_invalid_limit_type(self) -> None:
        """Rejects invalid limit type."""
        manager = BudgetManager(BudgetConfig())
        with pytest.raises(ValueError, match="Invalid limit_type"):
            manager.get_percentage("invalid")  # type: ignore[arg-type]


# ===========================================================================
# BudgetManager - Utility methods
# ===========================================================================


class TestBudgetManagerUtilities:
    """Tests for BudgetManager utility methods."""

    def test_has_any_limit_false_when_none(self) -> None:
        """Returns False when no limits configured."""
        manager = BudgetManager(BudgetConfig())
        assert manager.has_any_limit() is False

    def test_has_any_limit_true_for_token_limit(self) -> None:
        """Returns True when token limit configured."""
        manager = BudgetManager(BudgetConfig(tokens_limit=10000))
        assert manager.has_any_limit() is True

    def test_has_any_limit_true_for_cost_limit(self) -> None:
        """Returns True when cost limit configured."""
        manager = BudgetManager(BudgetConfig(cost_limit=5.0))
        assert manager.has_any_limit() is True

    def test_has_any_limit_true_for_tasks_limit(self) -> None:
        """Returns True when tasks limit configured."""
        manager = BudgetManager(BudgetConfig(tasks_limit=10))
        assert manager.has_any_limit() is True

    def test_has_any_limit_true_for_multiple_limits(self) -> None:
        """Returns True when multiple limits configured."""
        manager = BudgetManager(
            BudgetConfig(tokens_limit=10000, cost_limit=5.0, tasks_limit=10)
        )
        assert manager.has_any_limit() is True


# ===========================================================================
# Import compatibility (from cub.core.run)
# ===========================================================================


class TestPackageReexports:
    """Verify budget classes are accessible from the cub.core.run package."""

    def test_import_from_core_run(self) -> None:
        """All budget classes importable from cub.core.run."""
        from cub.core.run import BudgetCheckResult as C1
        from cub.core.run import BudgetConfig as C2
        from cub.core.run import BudgetManager as C3
        from cub.core.run import BudgetState as C4

        assert C1 is BudgetCheckResult
        assert C2 is BudgetConfig
        assert C3 is BudgetManager
        assert C4 is BudgetState
