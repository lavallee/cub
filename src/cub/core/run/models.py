"""
Run loop configuration and event models.

Provides typed models for configuring and observing the run loop state machine,
separated from CLI/rendering concerns. These models define:

- RunConfig: All parameters needed to configure a run loop execution
- RunEvent: Discriminated union of events yielded by the loop generator
- RunResult: Final outcome of a complete run loop execution

Any interface (CLI, API, skill) can create a RunConfig, iterate RunEvents,
and handle them appropriately for its rendering context.

Usage:
    >>> from cub.core.run.models import RunConfig, RunEvent, RunEventType
    >>> config = RunConfig(once=True, epic="cub-b1a")
    >>> # Pass to RunLoop.execute() to get RunEvent generator
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# ===========================================================================
# RunConfig - All loop configuration
# ===========================================================================


@dataclass(frozen=True)
class RunConfig:
    """
    Configuration for a run loop execution.

    Captures all parameters that affect loop behavior. Created from CLI args,
    API requests, or programmatic callers. Immutable once created.

    Attributes:
        once: Run a single iteration then exit.
        task_id: Run a specific task by ID (skip task selection).
        epic: Only work on tasks in this epic.
        label: Only work on tasks with this label.
        model: Model override (e.g., "sonnet", "opus").
        harness_name: Resolved harness name.
        session_name: Session name for tracking (auto-generated if None).
        stream: Stream harness output in real-time.
        debug: Enable debug logging.
        max_iterations: Maximum loop iterations (from config or --once).
        max_task_iterations: Maximum retries per task (from guardrails).
        on_task_failure: What to do on task failure ("stop" or "continue").
        budget_tokens: Token budget limit.
        budget_cost: Cost budget limit (USD).
        budget_tasks: Task count budget limit.
        circuit_breaker_enabled: Whether circuit breaker is active.
        circuit_breaker_timeout_minutes: Timeout for circuit breaker.
        ledger_enabled: Whether to record ledger entries.
        hooks_enabled: Whether to run lifecycle hooks.
        hooks_fail_fast: Whether hook failures stop the run.
        sync_enabled: Whether to auto-sync task state.
        iteration_warning_threshold: Budget warning threshold (0.0–1.0).
        project_dir: Project directory path (as string for serializability).
    """

    # Execution mode
    once: bool = False
    task_id: str | None = None
    epic: str | None = None
    label: str | None = None

    # Harness configuration
    model: str | None = None
    harness_name: str = ""
    session_name: str | None = None
    stream: bool = False
    debug: bool = False

    # Loop limits
    max_iterations: int = 100
    max_task_iterations: int = 3
    on_task_failure: str = "stop"

    # Budget limits
    budget_tokens: int | None = None
    budget_cost: float | None = None
    budget_tasks: int | None = None

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_timeout_minutes: int = 30

    # Subsystems
    ledger_enabled: bool = True
    hooks_enabled: bool = True
    hooks_fail_fast: bool = False
    sync_enabled: bool = False
    iteration_warning_threshold: float = 0.8

    # Project context
    project_dir: str = "."


# ===========================================================================
# RunEventType - All possible loop events
# ===========================================================================


class RunEventType(str, Enum):
    """
    Discriminator for run loop events.

    Each event type corresponds to a specific point in the loop lifecycle.
    CLI renderers switch on this to display appropriate output.
    """

    # Lifecycle events
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_STOPPED = "run_stopped"

    # Iteration events
    ITERATION_STARTED = "iteration_started"

    # Task events
    TASK_SELECTED = "task_selected"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Budget events
    BUDGET_UPDATED = "budget_updated"
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXHAUSTED = "budget_exhausted"

    # Operational events
    NO_TASKS_AVAILABLE = "no_tasks_available"
    ALL_TASKS_COMPLETE = "all_tasks_complete"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    CIRCUIT_BREAKER_TRIPPED = "circuit_breaker_tripped"
    HARNESS_ERROR = "harness_error"
    HOOK_FAILED = "hook_failed"

    # Informational events
    DEBUG_INFO = "debug_info"
    INTERRUPT_RECEIVED = "interrupt_received"


# ===========================================================================
# RunEvent - Event objects yielded by the loop
# ===========================================================================


@dataclass
class RunEvent:
    """
    Event yielded by the run loop generator.

    Each iteration of RunLoop.execute() yields one or more RunEvent instances.
    The CLI (or any consumer) handles rendering/logging based on event_type.

    Attributes:
        event_type: Discriminator for switching on event kind.
        message: Human-readable description of the event.
        task_id: Associated task ID (if applicable).
        task_title: Associated task title (if applicable).
        iteration: Current iteration number.
        max_iterations: Maximum iteration count.
        duration_seconds: Duration of the completed operation (if applicable).
        tokens_used: Tokens consumed in this operation (if applicable).
        cost_usd: Cost incurred in this operation (if applicable).
        exit_code: Exit code from harness (if applicable).
        error: Error message (if applicable).
        data: Arbitrary extra data for the event.
        timestamp: When the event occurred.
    """

    event_type: RunEventType
    message: str = ""

    # Context
    task_id: str | None = None
    task_title: str | None = None
    iteration: int = 0
    max_iterations: int = 0

    # Metrics
    duration_seconds: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    exit_code: int | None = None

    # Error info
    error: str | None = None

    # Budget snapshot
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    tasks_completed: int = 0
    budget_percentage: float | None = None

    # Extensible data
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


# ===========================================================================
# RunResult - Final outcome
# ===========================================================================


@dataclass
class RunResult:
    """
    Final result of a complete run loop execution.

    Returned after the generator is fully consumed. Summarizes the run
    for persistence (run artifacts, ledger entries) and exit code determination.

    Attributes:
        run_id: Unique identifier for this run.
        success: Whether the run completed successfully.
        phase: Final phase (completed, failed, stopped).
        iterations_completed: Number of iterations executed.
        tasks_completed: Number of tasks completed successfully.
        tasks_failed: Number of tasks that failed.
        total_tokens: Total tokens consumed.
        total_cost_usd: Total cost incurred.
        total_duration_seconds: Wall clock duration of the run.
        error: Error message if failed.
        events: All events produced during the run.
    """

    run_id: str = ""
    success: bool = False
    phase: str = "completed"
    iterations_completed: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    error: str | None = None
    events: list[RunEvent] = field(default_factory=list)
