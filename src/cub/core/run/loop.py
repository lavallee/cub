"""
Run loop state machine.

Implements the core pick-task → execute → record → next cycle as a generator
that yields RunEvent objects. All business logic lives here; signal handling,
Rich rendering, and CLI concerns stay in cli/run.py.

The RunLoop coordinates:
- Task selection (from TaskBackend)
- Harness invocation (via AsyncHarnessBackend)
- Budget tracking (via BudgetManager)
- Result recording (via LedgerIntegration)
- Circuit breaker monitoring
- Hook lifecycle coordination

Usage:
    >>> from cub.core.run.loop import RunLoop
    >>> from cub.core.run.models import RunConfig
    >>> loop = RunLoop(config=config, task_backend=backend, harness_backend=harness)
    >>> for event in loop.execute():
    ...     # render event in CLI, API, etc.
    ...     handle(event)
    >>> result = loop.get_result()
"""

from __future__ import annotations

import time
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.circuit_breaker import CircuitBreaker, CircuitBreakerTrippedError
from cub.core.harness.models import HarnessResult, TaskInput
from cub.core.ledger.models import CommitRef
from cub.core.run.budget import BudgetConfig, BudgetManager
from cub.core.run.interrupt import InterruptHandler
from cub.core.run.models import RunConfig, RunEvent, RunEventType, RunResult
from cub.core.run.prompt_builder import (
    generate_system_prompt,
    generate_task_prompt,
)
from cub.core.tasks.models import NON_EXECUTABLE_TYPES, Task, TaskStatus

if TYPE_CHECKING:
    from cub.core.harness.async_backend import AsyncHarnessBackend
    from cub.core.ledger.integration import LedgerIntegration
    from cub.core.status.writer import StatusWriter
    from cub.core.sync.service import SyncService
    from cub.core.tasks.backend import TaskBackend


def _run_async(coro: object) -> object:
    """Run an async coroutine from a sync context."""
    import asyncio

    return asyncio.run(coro)  # type: ignore[arg-type]


class RunLoop:
    """
    Core run loop state machine.

    Implements the autonomous task execution cycle as a generator. Each call
    to execute() yields RunEvent objects that describe what happened. The
    consumer (CLI, API, etc.) is responsible for rendering and signal handling.

    The loop follows this cycle:
        1. Check for interruption
        2. Check budget limits
        3. Select next task
        4. Claim task
        5. Generate prompt
        6. Invoke harness
        7. Record result
        8. Update budget
        9. Repeat or stop

    Attributes:
        config: Run configuration (immutable).
        task_backend: Task selection and management.
        harness_backend: AI harness for task execution.
        interrupt_handler: Optional interrupt handler for signal management.
        interrupted: Set to True externally to trigger graceful shutdown (deprecated,
                    use interrupt_handler instead).
    """

    def __init__(
        self,
        *,
        config: RunConfig,
        task_backend: TaskBackend,
        harness_backend: AsyncHarnessBackend,
        ledger_integration: LedgerIntegration | None = None,
        sync_service: SyncService | None = None,
        status_writer: StatusWriter | None = None,
        run_id: str | None = None,
        interrupt_handler: InterruptHandler | None = None,
    ) -> None:
        """
        Initialize the run loop.

        Args:
            config: Run configuration.
            task_backend: Backend for task selection and management.
            harness_backend: AI harness backend for execution.
            ledger_integration: Optional ledger for recording execution history.
            sync_service: Optional sync service for auto-syncing state.
            status_writer: Optional status writer for prompt/log persistence.
            run_id: Explicit run ID (auto-generated if None).
            interrupt_handler: Optional interrupt handler for signal management.
        """
        self.config = config
        self.task_backend = task_backend
        self.harness_backend = harness_backend
        self.ledger_integration = ledger_integration
        self.sync_service = sync_service
        self.status_writer = status_writer

        # Generate run ID
        self.run_id = (
            run_id or config.session_name or (f"cub-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        )

        # Interrupt handling
        self.interrupt_handler = interrupt_handler
        # External interrupt flag - set by signal handler in CLI (for backward compatibility)
        # When interrupt_handler is provided, we check that instead
        self.interrupted = False

        # Initialize budget manager
        budget_config = BudgetConfig(
            tokens_limit=config.budget_tokens,
            cost_limit=config.budget_cost,
            tasks_limit=config.budget_tasks,
        )
        self._budget_manager = BudgetManager(budget_config)

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            timeout_minutes=config.circuit_breaker_timeout_minutes,
            enabled=config.circuit_breaker_enabled,
        )

        # Loop state
        self._iteration = 0
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_tokens = 0
        self._total_cost_usd = 0.0
        self._start_time: float = 0.0
        self._phase = "initializing"
        self._error: str | None = None
        self._events: list[RunEvent] = []
        self._budget_warning_fired = False
        # Per-task attempt counts for enforcing max_task_iterations
        self._task_attempt_counts: dict[str, int] = {}
        # Tasks skipped in last _select_task due to retry exhaustion
        self._retries_exhausted: list[str] = []
        # When on_task_failure="retry", holds the task ID to retry next iteration
        self._retry_task_id: str | None = None

        # Generate system prompt once
        self._system_prompt = generate_system_prompt(Path(config.project_dir))

    @property
    def budget_manager(self) -> BudgetManager:
        """Access the budget manager for external queries."""
        return self._budget_manager

    def _make_event(
        self,
        event_type: RunEventType,
        message: str = "",
        **kwargs: object,
    ) -> RunEvent:
        """Create a RunEvent with current loop state baked in."""
        event = RunEvent(
            event_type=event_type,
            message=message,
            iteration=self._iteration,
            max_iterations=self.config.max_iterations,
            total_tokens_used=self._total_tokens,
            total_cost_usd=self._total_cost_usd,
            tasks_completed=self._tasks_completed,
            budget_percentage=self._get_budget_percentage(),
            **kwargs,  # type: ignore[arg-type]
        )
        self._events.append(event)
        return event

    def execute(self) -> Generator[RunEvent, None, None]:
        """
        Execute the run loop, yielding events.

        This is the main entry point. It implements the state machine:
        pick task → execute → record → next. Each significant state
        transition yields a RunEvent for the consumer to handle.

        Yields:
            RunEvent objects describing each state transition.

        Example:
            >>> loop = RunLoop(config=config, ...)
            >>> for event in loop.execute():
            ...     if event.event_type == RunEventType.TASK_COMPLETED:
            ...         print(f"Done: {event.task_id}")
        """
        self._start_time = time.time()
        self._phase = "running"

        # Yield run started
        yield self._make_event(
            RunEventType.RUN_STARTED,
            f"Starting run: {self.run_id}",
            data={"run_id": self.run_id, "harness": self.config.harness_name},
        )

        try:
            # Run pre-loop hooks
            if self.config.hooks_enabled:
                hook_ok = self._run_hook("pre-loop")
                if not hook_ok and self.config.hooks_fail_fast:
                    self._phase = "failed"
                    self._error = "Pre-loop hook failed"
                    yield self._make_event(
                        RunEventType.HOOK_FAILED,
                        "Pre-loop hook failed",
                        error="Pre-loop hook failed",
                    )
                    return

            # Run pre-session hook (lifecycle hook before harness invocation)
            if self.config.hooks_enabled:
                from cub.core.hooks.lifecycle import invoke_pre_session_hook

                hook_ok = invoke_pre_session_hook(self.config, self.task_backend, self.run_id)
                if not hook_ok and self.config.hooks_fail_fast:
                    self._phase = "failed"
                    self._error = "Pre-session hook failed"
                    yield self._make_event(
                        RunEventType.HOOK_FAILED,
                        "Pre-session hook failed",
                        error="Pre-session hook failed",
                    )
                    return

            # Main loop
            while self._iteration < self.config.max_iterations:
                # Check interrupt (prefer interrupt_handler if available)
                is_interrupted = (
                    self.interrupt_handler.interrupted
                    if self.interrupt_handler
                    else self.interrupted
                )
                if is_interrupted:
                    yield self._make_event(
                        RunEventType.INTERRUPT_RECEIVED,
                        "Stopping due to interrupt",
                    )
                    self._phase = "stopped"
                    break

                # Check budget
                limit_check = self._budget_manager.check_limit()
                if limit_check.should_stop:
                    yield self._make_event(
                        RunEventType.BUDGET_EXHAUSTED,
                        limit_check.reason or "Budget exhausted",
                    )
                    self._phase = "completed"
                    break

                # Increment iteration
                self._iteration += 1

                yield self._make_event(
                    RunEventType.ITERATION_STARTED,
                    f"Iteration {self._iteration}/{self.config.max_iterations}",
                )

                # Select task
                task = self._select_task()
                if task is None:
                    # Emit events for any tasks that exhausted retries
                    for exhausted_id in self._retries_exhausted:
                        yield self._make_event(
                            RunEventType.TASK_RETRIES_EXHAUSTED,
                            f"Task {exhausted_id} exceeded max retries "
                            f"({self.config.max_task_iterations})",
                            task_id=exhausted_id,
                        )
                    event = self._handle_no_task()
                    yield event
                    break

                yield self._make_event(
                    RunEventType.TASK_SELECTED,
                    f"Selected task: {task.title}",
                    task_id=task.id,
                    task_title=task.title,
                )

                # Execute task
                yield from self._execute_task(task)

                # Check if execution set a terminal phase
                if self._phase in ("failed", "stopped"):
                    break

                # If running specific task, exit after one iteration
                if self.config.task_id:
                    break

                # Brief pause between iterations
                if not self.config.once and self._iteration < self.config.max_iterations:
                    time.sleep(2)

            else:
                # Loop completed all iterations
                yield self._make_event(
                    RunEventType.MAX_ITERATIONS_REACHED,
                    f"Reached max iterations ({self.config.max_iterations})",
                )
                self._phase = "stopped"

        except Exception as e:
            self._phase = "failed"
            self._error = str(e)
            yield self._make_event(
                RunEventType.RUN_FAILED,
                f"Unexpected error: {e}",
                error=str(e),
            )
            # Run post-loop hooks even on failure
            if self.config.hooks_enabled:
                self._run_hook("post-loop")
            return

        # Run post-loop hooks
        if self.config.hooks_enabled:
            self._run_hook("post-loop")

        # Determine final phase
        if self._phase == "running":
            self._phase = "completed"

        # Yield completion event
        total_duration = time.time() - self._start_time
        final_event_type = {
            "completed": RunEventType.RUN_COMPLETED,
            "failed": RunEventType.RUN_FAILED,
            "stopped": RunEventType.RUN_STOPPED,
        }.get(self._phase, RunEventType.RUN_COMPLETED)

        yield self._make_event(
            final_event_type,
            f"Run {self._phase}: {self._tasks_completed} tasks completed",
            duration_seconds=total_duration,
            data={
                "phase": self._phase,
                "tasks_completed": self._tasks_completed,
                "tasks_failed": self._tasks_failed,
            },
        )

    def get_result(self) -> RunResult:
        """
        Get the final result after the loop completes.

        Call this after fully consuming the execute() generator.

        Returns:
            RunResult summarizing the run execution.
        """
        total_duration = time.time() - self._start_time if self._start_time else 0.0
        return RunResult(
            run_id=self.run_id,
            success=self._phase == "completed" and self._tasks_failed == 0,
            phase=self._phase,
            iterations_completed=self._iteration,
            tasks_completed=self._tasks_completed,
            tasks_failed=self._tasks_failed,
            total_tokens=self._total_tokens,
            total_cost_usd=self._total_cost_usd,
            total_duration_seconds=total_duration,
            error=self._error,
            events=list(self._events),
        )

    # -----------------------------------------------------------------------
    # Task selection
    # -----------------------------------------------------------------------

    def _select_task(self) -> Task | None:
        """
        Select the next task to execute.

        Priority order:
        1. ``_retry_task_id`` (set when on_task_failure="retry" and a task just failed)
        2. ``config.task_id`` (explicit task requested via CLI)
        3. Next ready task from backend (filtered by max_task_iterations)

        Populates ``_retries_exhausted`` with IDs of skipped tasks.

        Returns:
            The selected Task, or None if no tasks are available.
        """
        self._retries_exhausted = []
        max_attempts = self.config.max_task_iterations

        # Check for pending retry (on_task_failure="retry")
        if self._retry_task_id:
            retry_id = self._retry_task_id
            self._retry_task_id = None  # Consume it
            task = self.task_backend.get_task(retry_id)
            if task is not None and task.status != TaskStatus.CLOSED:
                if self._task_attempt_counts.get(task.id, 0) < max_attempts:
                    return task
                # Exhausted retries on this task
                self._retries_exhausted.append(task.id)
                try:
                    self.task_backend.close_task(
                        task.id,
                        reason=f"Exceeded max retries ({max_attempts})",
                    )
                except Exception:
                    pass  # Non-fatal
                # Fall through to normal selection

        if self.config.task_id:
            # Specific task requested
            task = self.task_backend.get_task(self.config.task_id)
            if task is None:
                return None
            if task.status == TaskStatus.CLOSED:
                return None
            # Reject non-executable types (epics, gates)
            if task.type in NON_EXECUTABLE_TYPES:
                return None
            # Check retry limit for specific task
            if self._task_attempt_counts.get(task.id, 0) >= max_attempts:
                self._retries_exhausted.append(task.id)
                return None
            return task

        # Get next ready task, filtering out exhausted retries
        ready_tasks = self.task_backend.get_ready_tasks(
            parent=self.config.epic,
            label=self.config.label,
        )
        if not ready_tasks:
            return None

        for task in ready_tasks:
            attempts = self._task_attempt_counts.get(task.id, 0)
            if attempts < max_attempts:
                return task
            # Task has exceeded retry limit - mark it as closed/failed
            self._retries_exhausted.append(task.id)
            try:
                self.task_backend.close_task(
                    task.id,
                    reason=f"Exceeded max retries ({max_attempts})",
                )
            except Exception:
                pass  # Non-fatal

        return None

    def _handle_no_task(self) -> RunEvent:
        """Handle the case where no task is available."""
        if self.config.task_id:
            # Specific task not found or already closed
            task = self.task_backend.get_task(self.config.task_id)
            if task is None:
                self._phase = "failed"
                self._error = f"Task {self.config.task_id} not found"
                return self._make_event(
                    RunEventType.RUN_FAILED,
                    f"Task {self.config.task_id} not found",
                    task_id=self.config.task_id,
                    error=f"Task {self.config.task_id} not found",
                )
            if task.status == TaskStatus.CLOSED:
                self._phase = "completed"
                return self._make_event(
                    RunEventType.ALL_TASKS_COMPLETE,
                    f"Task {self.config.task_id} is already closed",
                    task_id=self.config.task_id,
                )

        # Check if all tasks done or blocked
        counts = self.task_backend.get_task_counts()
        if counts.remaining == 0:
            self._phase = "completed"
            return self._make_event(
                RunEventType.ALL_TASKS_COMPLETE,
                "All tasks complete!",
                data={"total": counts.total, "closed": counts.closed},
            )

        self._phase = "completed"
        return self._make_event(
            RunEventType.NO_TASKS_AVAILABLE,
            f"{counts.remaining} tasks remaining but all have unmet dependencies",
            data={"remaining": counts.remaining},
        )

    # -----------------------------------------------------------------------
    # Task execution
    # -----------------------------------------------------------------------

    def _execute_task(self, task: Task) -> Generator[RunEvent, None, None]:
        """
        Execute a single task: claim, invoke harness, record result.

        Yields RunEvent objects for each step of the execution.
        """
        project_dir = Path(self.config.project_dir)

        # Track per-task attempt count for max_task_iterations enforcement
        self._task_attempt_counts[task.id] = self._task_attempt_counts.get(task.id, 0) + 1

        # Run pre-task hooks
        if self.config.hooks_enabled:
            hook_ok = self._run_hook(
                "pre-task",
                task_id=task.id,
                task_title=task.title,
            )
            if not hook_ok and self.config.hooks_fail_fast:
                self._phase = "failed"
                self._error = f"Pre-task hook failed for {task.id}"
                yield self._make_event(
                    RunEventType.HOOK_FAILED,
                    f"Pre-task hook failed for {task.id}",
                    task_id=task.id,
                    error=f"Pre-task hook failed for {task.id}",
                )
                return

        # Claim task (mark as in_progress)
        try:
            self.task_backend.update_task(
                task.id, status=TaskStatus.IN_PROGRESS, assignee=self.run_id
            )
        except Exception:
            pass  # Non-fatal

        # Capture git state at task start for commit tracking
        task_start_commit = self._get_current_commit()

        # Create ledger entry for task start
        if self.ledger_integration and self.config.ledger_enabled:
            try:
                self.ledger_integration.on_task_start(
                    task,
                    run_id=self.run_id,
                    epic_id=self.config.epic,
                )
            except Exception:
                pass  # Non-fatal

        # Generate task prompt
        task_prompt = generate_task_prompt(
            task,
            self.task_backend,
            self.ledger_integration if self.config.ledger_enabled else None,
        )

        # Get model from task label, CLI arg, or default
        task_model = self.config.model or task.model_label

        yield self._make_event(
            RunEventType.TASK_STARTED,
            f"Running {self.config.harness_name}...",
            task_id=task.id,
            task_title=task.title,
        )

        # Track attempt start time
        attempt_start_time = datetime.now()
        attempt_number = 1

        # Invoke harness
        try:
            task_input = TaskInput(
                prompt=task_prompt,
                system_prompt=self._system_prompt,
                model=task_model,
                working_dir=str(project_dir),
                auto_approve=True,
            )

            # Write prompt audit trail
            if self.status_writer:
                try:
                    self.status_writer.write_prompt(task.id, self._system_prompt, task_prompt)
                except Exception:
                    pass

            # Record attempt start in ledger
            if self.ledger_integration and self.config.ledger_enabled:
                try:
                    attempt_number = self.ledger_integration.get_attempt_count(task.id) + 1
                    combined_prompt = (
                        f"# System Prompt\n\n{self._system_prompt}\n\n"
                        f"# Task Prompt\n\n{task_prompt}"
                    )
                    self.ledger_integration.on_attempt_start(
                        task.id,
                        attempt_number,
                        combined_prompt,
                        run_id=self.run_id,
                        harness=self.config.harness_name,
                        model=task_model or "",
                    )
                except Exception:
                    pass

            # Get harness log path
            harness_log_path: Path | None = None
            if self.status_writer:
                harness_log_path = self.status_writer.get_harness_log_path(task.id)

            # Invoke harness with circuit breaker
            result = self._invoke_harness(task_input, harness_log_path)

            # Record attempt end in ledger
            self._record_attempt_end(
                task, attempt_number, result, attempt_start_time, harness_log_path
            )

        except CircuitBreakerTrippedError as e:
            # Circuit breaker timeout
            self._record_circuit_breaker_trip(task, attempt_number, attempt_start_time, e)
            self._tasks_failed += 1
            # Mark task for retry so it can be picked up again
            try:
                self.task_backend.update_task(task.id, status=TaskStatus.RETRY)
            except Exception:
                pass  # Non-fatal
            yield self._make_event(
                RunEventType.CIRCUIT_BREAKER_TRIPPED,
                f"Circuit breaker tripped after {e.timeout_minutes} minutes",
                task_id=task.id,
                error=e.message,
            )
            if self.config.on_task_failure == "stop":
                self._phase = "failed"
                self._error = e.message
            elif self.config.on_task_failure == "retry":
                self._retry_task_id = task.id
            return

        except Exception as e:
            # Harness invocation failed
            self._record_harness_error(task, attempt_number, attempt_start_time, e)
            self._tasks_failed += 1
            # Mark task for retry so it can be picked up again
            try:
                self.task_backend.update_task(task.id, status=TaskStatus.RETRY)
            except Exception:
                pass  # Non-fatal

            yield self._make_event(
                RunEventType.HARNESS_ERROR,
                f"Harness invocation failed: {e}",
                task_id=task.id,
                error=str(e),
            )

            if self.config.on_task_failure == "stop":
                self._phase = "failed"
                self._error = str(e)
            elif self.config.on_task_failure == "retry":
                self._retry_task_id = task.id
            return

        # Process result
        duration = result.duration_seconds

        # Update budget tracking
        tokens = result.usage.total_tokens
        cost = result.usage.cost_usd or 0.0
        self._budget_manager.record_usage(tokens=tokens, cost_usd=cost)
        self._total_tokens += tokens
        self._total_cost_usd += cost

        # Yield budget update
        yield self._make_event(
            RunEventType.BUDGET_UPDATED,
            f"Tokens: {tokens:,}, Cost: ${cost:.4f}",
            task_id=task.id,
            tokens_used=tokens,
            cost_usd=cost,
        )

        # Check budget warning
        warning = self._budget_manager.check_warning_threshold(
            self.config.iteration_warning_threshold
        )
        if warning and not self._budget_warning_fired:
            self._budget_warning_fired = True
            yield self._make_event(
                RunEventType.BUDGET_WARNING,
                warning.reason or "Budget warning threshold reached",
            )

        if result.success:
            self._tasks_completed += 1
            self._budget_manager.record_task_completion()

            yield self._make_event(
                RunEventType.TASK_COMPLETED,
                f"Task completed in {duration:.1f}s",
                task_id=task.id,
                task_title=task.title,
                duration_seconds=duration,
                tokens_used=tokens,
                cost_usd=cost,
                exit_code=result.exit_code,
            )

            # Close task in backend
            try:
                self.task_backend.close_task(
                    task.id,
                    reason="Completed by autonomous execution",
                )
            except Exception:
                pass  # Non-fatal, work is done

            # Finalize ledger entry BEFORE committing so it's included
            self._finalize_ledger(
                task,
                success=True,
                task_model=task_model,
                task_start_commit=task_start_commit,
            )

            # Run end-of-task lifecycle hook
            if self.config.hooks_enabled:
                from cub.core.hooks.lifecycle import invoke_end_of_task_hook

                invoke_end_of_task_hook(
                    self.config,
                    task,
                    success=True,
                    duration_seconds=duration,
                    run_id=self.run_id,
                    iterations=1,
                    error=None,
                )

            # Auto-close parent epic if all its tasks are complete
            if task.parent:
                try:
                    closed, message = self.task_backend.try_close_epic(task.parent)
                    if closed:
                        # Finalize epic ledger entry before committing
                        self._finalize_epic_ledger(task.parent)

                        yield self._make_event(
                            RunEventType.EPIC_CLOSED,
                            message,
                            task_id=task.parent,
                        )

                        # Run end-of-epic lifecycle hook
                        if self.config.hooks_enabled:
                            from cub.core.hooks.lifecycle import invoke_end_of_epic_hook

                            invoke_end_of_epic_hook(
                                self.config,
                                self.task_backend,
                                task.parent,
                                self.run_id,
                            )
                except Exception:
                    pass  # Non-fatal

            # Commit code changes and ledger files to working tree
            # This ensures ledger files are included in the task completion commit
            try:
                self._commit_task_completion(task.id, task.parent)
            except Exception:
                pass  # Non-fatal

            # Auto-sync task state to sync branch (if enabled)
            if self.sync_service and self.config.sync_enabled:
                try:
                    self.sync_service.commit(message=f"Task {task.id} completed")
                except Exception:
                    pass  # Non-fatal

            # Run post-task hooks
            if self.config.hooks_enabled:
                self._run_hook(
                    "post-task",
                    task_id=task.id,
                    task_title=task.title,
                    async_hook=True,
                )
        else:
            self._tasks_failed += 1
            # Mark task for retry so it can be picked up again
            try:
                self.task_backend.update_task(task.id, status=TaskStatus.RETRY)
            except Exception:
                pass  # Non-fatal

            yield self._make_event(
                RunEventType.TASK_FAILED,
                f"Task failed: {result.error or 'Unknown error'}",
                task_id=task.id,
                task_title=task.title,
                duration_seconds=duration,
                tokens_used=tokens,
                cost_usd=cost,
                exit_code=result.exit_code,
                error=result.error,
            )

            # Finalize ledger entry for failure
            self._finalize_ledger(
                task,
                success=False,
                task_model=task_model,
                task_start_commit=task_start_commit,
            )

            # Run end-of-task lifecycle hook for failures
            if self.config.hooks_enabled:
                from cub.core.hooks.lifecycle import invoke_end_of_task_hook

                invoke_end_of_task_hook(
                    self.config,
                    task,
                    success=False,
                    duration_seconds=duration,
                    run_id=self.run_id,
                    iterations=1,
                    error=result.error,
                )

            # Run on-error hooks
            if self.config.hooks_enabled:
                self._run_hook(
                    "on-error",
                    task_id=task.id,
                    task_title=task.title,
                    async_hook=True,
                )

            if self.config.on_task_failure == "stop":
                self._phase = "failed"
                self._error = result.error or "Task execution failed"
            elif self.config.on_task_failure == "retry":
                self._retry_task_id = task.id

    # -----------------------------------------------------------------------
    # Harness invocation
    # -----------------------------------------------------------------------

    def _invoke_harness(
        self,
        task_input: TaskInput,
        harness_log_path: Path | None = None,
    ) -> HarnessResult:
        """
        Invoke the harness backend with optional circuit breaker.

        Args:
            task_input: Task parameters for the harness.
            harness_log_path: Optional path for harness log output.

        Returns:
            HarnessResult from the harness execution.

        Raises:
            CircuitBreakerTrippedError: If circuit breaker timeout exceeded.
            Exception: On harness invocation failure.
        """
        from cub.core.run._harness import invoke_harness_async

        coro = invoke_harness_async(
            self.harness_backend,
            task_input,
            stream=self.config.stream,
            debug=self.config.debug,
            harness_log_path=harness_log_path,
        )

        if self._circuit_breaker.enabled:
            coro = self._circuit_breaker.execute(coro)

        return _run_async(coro)  # type: ignore[return-value]

    # -----------------------------------------------------------------------
    # Ledger recording
    # -----------------------------------------------------------------------

    def _record_attempt_end(
        self,
        task: Task,
        attempt_number: int,
        result: HarnessResult,
        attempt_start_time: datetime,
        harness_log_path: Path | None,
    ) -> None:
        """Record attempt end in ledger."""
        if not self.ledger_integration or not self.config.ledger_enabled:
            return

        try:
            log_content = ""
            if harness_log_path and harness_log_path.exists():
                log_content = harness_log_path.read_text(encoding="utf-8")

            from cub.core.ledger.models import TokenUsage as LedgerTokenUsage

            ledger_tokens = LedgerTokenUsage(
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cache_read_tokens=result.usage.cache_read_tokens,
                cache_creation_tokens=result.usage.cache_creation_tokens,
            )

            self.ledger_integration.on_attempt_end(
                task.id,
                attempt_number,
                log_content,
                run_id=self.run_id,
                success=result.success,
                harness=self.config.harness_name,
                model=self.config.model or task.model_label or "",
                tokens=ledger_tokens,
                cost_usd=result.usage.cost_usd or 0.0,
                duration_seconds=int(result.duration_seconds),
                started_at=attempt_start_time,
            )
        except Exception:
            pass  # Non-fatal

    def _record_circuit_breaker_trip(
        self,
        task: Task,
        attempt_number: int,
        attempt_start_time: datetime,
        error: CircuitBreakerTrippedError,
    ) -> None:
        """Record circuit breaker trip in ledger."""
        if not self.ledger_integration or not self.config.ledger_enabled:
            return

        try:
            self.ledger_integration.on_attempt_end(
                task.id,
                attempt_number,
                log_content="",
                run_id=self.run_id,
                success=False,
                harness=self.config.harness_name,
                model=self.config.model or task.model_label or "",
                error_category="circuit_breaker_timeout",
                error_summary=error.message,
                started_at=attempt_start_time,
            )
        except Exception:
            pass  # Non-fatal

    def _record_harness_error(
        self,
        task: Task,
        attempt_number: int,
        attempt_start_time: datetime,
        error: Exception,
    ) -> None:
        """Record harness invocation failure in ledger."""
        if not self.ledger_integration or not self.config.ledger_enabled:
            return

        try:
            self.ledger_integration.on_attempt_end(
                task.id,
                attempt_number,
                log_content="",
                run_id=self.run_id,
                success=False,
                harness=self.config.harness_name,
                model=self.config.model or task.model_label or "",
                error_category="harness_failure",
                error_summary=str(error),
                started_at=attempt_start_time,
            )
        except Exception:
            pass  # Non-fatal

    def _finalize_ledger(
        self,
        task: Task,
        *,
        success: bool,
        task_model: str | None,
        task_start_commit: str | None,
    ) -> None:
        """Finalize ledger entry after task completion or failure."""
        if not self.ledger_integration or not self.config.ledger_enabled:
            return

        try:
            current_task_state = self.task_backend.get_task(task.id)

            # Collect commits made during task execution
            task_commits: list[CommitRef] = []
            if task_start_commit:
                from cub.utils.git import get_commits_between, parse_commit_timestamp

                raw_commits = get_commits_between(task_start_commit)
                for rc in raw_commits:
                    task_commits.append(
                        CommitRef(
                            hash=rc["hash"],
                            message=rc["message"],
                            timestamp=parse_commit_timestamp(rc["timestamp"]),
                        )
                    )

            self.ledger_integration.on_task_close(
                task.id,
                success=success,
                partial=not success,
                final_model=task_model or "",
                commits=task_commits,
                current_task=current_task_state,
            )
        except Exception:
            pass  # Non-fatal

    def _finalize_epic_ledger(self, epic_id: str) -> None:
        """Finalize epic ledger entry when all tasks complete."""
        if not self.ledger_integration or not self.config.ledger_enabled:
            return

        try:
            # Update epic aggregates from all completed child tasks
            self.ledger_integration.writer.update_epic_aggregates(epic_id)
        except Exception:
            pass  # Non-fatal

    def _commit_task_completion(self, task_id: str, epic_id: str | None) -> None:
        """Amend the task completion commit to include ledger files.

        After the agent commits their changes, this method:
        - Stages ledger entry file (.cub/ledger/by-task/{id}.json)
        - Stages index file (.cub/ledger/index.jsonl)
        - Stages epic entry file if epic was closed
        - Amends the last commit to include these files
        - Updates commit message to mention ledger update

        Args:
            task_id: Task ID that was completed
            epic_id: Optional epic ID if epic was also closed
        """
        import subprocess

        project_dir = Path(self.config.project_dir)

        # Check if we're in a git repo
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=project_dir,
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return  # Not a git repo, skip

        # Get the last commit message to check if it's the task commit
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            last_commit_msg = result.stdout.strip()
        except Exception:
            return  # Can't get last commit, skip

        # Only amend if the last commit is for this task
        # (format: "type(task-id): description" per runloop.md)
        if not last_commit_msg or f"({task_id})" not in last_commit_msg:
            return  # Last commit isn't for this task, don't amend

        # Add ledger files to staging
        ledger_files = [
            f".cub/ledger/by-task/{task_id}.json",
            ".cub/ledger/index.jsonl",
        ]

        if epic_id:
            ledger_files.append(f".cub/ledger/by-epic/{epic_id}/entry.json")

        files_to_stage = []
        for ledger_file in ledger_files:
            file_path = project_dir / ledger_file
            if file_path.exists():
                files_to_stage.append(ledger_file)
                try:
                    subprocess.run(
                        ["git", "add", ledger_file],
                        cwd=project_dir,
                        capture_output=True,
                        check=False,  # Don't fail if file isn't tracked
                    )
                except Exception:
                    pass  # Non-fatal

        # Check if there are staged changes
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=project_dir,
                capture_output=True,
            )
            # Exit code 1 means there are changes, 0 means no changes
            if diff_result.returncode == 0:
                return  # No ledger files to add
        except Exception:
            return  # Can't determine status, skip

        # Amend the commit to include ledger files
        # Append ledger update info to the commit message
        updated_msg = last_commit_msg
        if epic_id:
            updated_msg += f"\n\nIncludes ledger updates for task {task_id} and epic {epic_id}"
        else:
            updated_msg += f"\n\nIncludes ledger update for task {task_id}"

        try:
            subprocess.run(
                ["git", "commit", "--amend", "-m", updated_msg, "--no-verify"],
                cwd=project_dir,
                capture_output=True,
                check=False,  # Don't fail on commit errors
            )
        except Exception:
            pass  # Non-fatal

    # -----------------------------------------------------------------------
    # Hooks
    # -----------------------------------------------------------------------

    def _run_hook(
        self,
        hook_name: str,
        task_id: str | None = None,
        task_title: str | None = None,
        async_hook: bool = False,
        **kwargs: object,
    ) -> bool:
        """
        Run a lifecycle hook.

        Args:
            hook_name: Hook name (pre-loop, post-loop, pre-task, post-task, etc.)
            task_id: Optional task ID context.
            task_title: Optional task title context.
            async_hook: If True, fire and forget (async notification).

        Returns:
            True if hook succeeded or hooks disabled, False if failed.
        """
        if not self.config.hooks_enabled:
            return True

        try:
            from cub.utils.hooks import HookContext as _HookContext
            from cub.utils.hooks import run_hooks, run_hooks_async

            project_dir = Path(self.config.project_dir)
            context = _HookContext(
                hook_name=hook_name,
                project_dir=project_dir,
                task_id=task_id,
                task_title=task_title,
                harness=self.config.harness_name,
                session_id=self.run_id,
            )

            if async_hook:
                run_hooks_async(hook_name, context, project_dir)
                return True
            else:
                return run_hooks(hook_name, context, project_dir)
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    def _get_budget_percentage(self) -> float | None:
        """Get the highest budget percentage across all limit types."""
        percentages = []
        for limit_type in ("tokens", "cost", "tasks"):
            pct = self._budget_manager.get_percentage(limit_type)
            if pct is not None:
                percentages.append(pct)
        return max(percentages) if percentages else None

    @staticmethod
    def _get_current_commit() -> str | None:
        """Get current git commit hash."""
        try:
            from cub.utils.git import get_current_commit

            return get_current_commit()
        except Exception:
            return None
