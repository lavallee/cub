"""
Run service — clean API for run loop orchestration.

Wraps core/run/ into a service that any interface (CLI, API, skills) can call
without reaching into domain internals. The service is a stateless orchestrator:
it wires up dependencies (task backend, harness, ledger, etc.) and delegates
to RunLoop for actual execution.

Usage:
    >>> from cub.core.services.run import RunService
    >>> service = RunService.from_config(config)
    >>> for event in service.execute(run_config):
    ...     handle(event)       # render in CLI, push to websocket, etc.
    >>> result = service.get_result()

    # Or, for one-shot convenience:
    >>> result = service.run_once("cub-123")
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.config.loader import load_config
from cub.core.config.models import CubConfig
from cub.core.harness.async_backend import detect_async_harness, get_async_backend
from cub.core.ledger.integration import LedgerIntegration
from cub.core.ledger.writer import LedgerWriter
from cub.core.run.interrupt import InterruptHandler
from cub.core.run.loop import RunLoop
from cub.core.run.models import RunConfig, RunEvent, RunResult
from cub.core.status.writer import StatusWriter
from cub.core.sync.service import SyncService
from cub.core.tasks.backend import TaskBackend
from cub.core.tasks.backend import get_backend as get_task_backend

if TYPE_CHECKING:
    from cub.core.harness.async_backend import AsyncHarnessBackend


# ============================================================================
# Typed exceptions
# ============================================================================


class RunServiceError(Exception):
    """Base exception for RunService errors."""


class HarnessNotFoundError(RunServiceError):
    """No suitable harness could be detected or resolved."""


class HarnessNotAvailableError(RunServiceError):
    """The requested harness is not installed or not available."""

    def __init__(self, harness_name: str) -> None:
        self.harness_name = harness_name
        super().__init__(f"Harness '{harness_name}' is not available or not installed")


class TaskBackendError(RunServiceError):
    """Failed to initialize or communicate with the task backend."""


# ============================================================================
# Service inputs / outputs
# ============================================================================


@dataclass(frozen=True)
class RunOnceRequest:
    """
    Input for the ``run_once`` convenience method.

    Attributes:
        task_id: The task to execute.
        model: Model override (e.g., "sonnet", "opus").
        stream: Stream harness output in real-time.
        debug: Enable debug logging.
        budget_tokens: Token budget limit for this single run.
        budget_cost: Cost budget limit (USD) for this single run.
    """

    task_id: str
    model: str | None = None
    stream: bool = False
    debug: bool = False
    budget_tokens: int | None = None
    budget_cost: float | None = None


# ============================================================================
# RunService
# ============================================================================


class RunService:
    """
    Service layer for run loop orchestration.

    Provides a clean API surface for executing autonomous task loops. All
    dependency wiring (task backend, harness, ledger, sync, status) is
    encapsulated here so callers only interact with typed inputs/outputs.

    Create via the ``from_config`` factory method, then call ``execute``
    to drive the run loop, or ``run_once`` for single-task convenience.

    This class is **not** thread-safe — one service instance drives one
    run at a time.
    """

    def __init__(
        self,
        *,
        config: CubConfig,
        project_dir: Path,
        task_backend: TaskBackend,
        harness_name: str,
        harness_backend: AsyncHarnessBackend,
        ledger_integration: LedgerIntegration | None = None,
        sync_service: SyncService | None = None,
        status_writer: StatusWriter | None = None,
        interrupt_handler: InterruptHandler | None = None,
    ) -> None:
        """
        Initialize the service with pre-wired dependencies.

        Prefer ``from_config`` for typical usage; use this constructor
        when you need to inject specific mocks/stubs (e.g., in tests).
        """
        self._config = config
        self._project_dir = project_dir
        self._task_backend = task_backend
        self._harness_name = harness_name
        self._harness_backend = harness_backend
        self._ledger_integration = ledger_integration
        self._sync_service = sync_service
        self._status_writer = status_writer
        self._interrupt_handler = interrupt_handler

        # Holds the most recent RunLoop instance so callers can
        # get the result after consuming the generator.
        self._current_loop: RunLoop | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        config: CubConfig | None = None,
        *,
        project_dir: Path | None = None,
        harness: str | None = None,
        enable_sync: bool | None = None,
        enable_ledger: bool | None = None,
    ) -> RunService:
        """
        Create a RunService from configuration.

        Loads config, detects/validates harness, initializes backends.
        This is the standard entry point for production usage.

        Args:
            config: Pre-loaded configuration. If ``None``, loads from
                ``project_dir`` using the standard loader.
            project_dir: Project root directory. Defaults to cwd.
            harness: Explicit harness name, or ``None`` for auto-detect.
            enable_sync: Override config sync setting. If ``None``, uses
                config defaults.
            enable_ledger: Override config ledger setting. If ``None``,
                uses config defaults.

        Returns:
            A fully-wired ``RunService`` ready for ``execute`` or ``run_once``.

        Raises:
            HarnessNotFoundError: If no harness could be detected.
            HarnessNotAvailableError: If the harness is not installed.
            TaskBackendError: If the task backend could not be initialized.
        """
        resolved_dir = project_dir or Path.cwd()

        # Load config
        resolved_config = config or load_config(resolved_dir)

        # Detect and validate harness
        harness_name = harness or detect_async_harness(resolved_config.harness.priority)
        if not harness_name:
            raise HarnessNotFoundError(
                "No harness detected. Install one of: claude, codex, gemini, opencode"
            )

        try:
            harness_backend: AsyncHarnessBackend = get_async_backend(harness_name)
        except ValueError as exc:
            raise HarnessNotFoundError(str(exc)) from exc

        if not harness_backend.is_available():
            raise HarnessNotAvailableError(harness_name)

        # Initialize task backend
        try:
            task_backend = get_task_backend(project_dir=resolved_dir)
        except Exception as exc:
            raise TaskBackendError(f"Failed to initialize task backend: {exc}") from exc

        # Initialize ledger
        ledger_integration: LedgerIntegration | None = None
        should_enable_ledger = (
            enable_ledger if enable_ledger is not None else resolved_config.ledger.enabled
        )
        if should_enable_ledger:
            ledger_dir = resolved_dir / ".cub" / "ledger"
            ledger_writer = LedgerWriter(ledger_dir)
            ledger_integration = LedgerIntegration(ledger_writer)

        # Initialize sync service
        sync_service: SyncService | None = None
        should_enable_sync = (
            enable_sync
            if enable_sync is not None
            else (
                resolved_config.sync.enabled and resolved_config.sync.auto_sync in ("run", "always")
            )
        )
        backend_name = task_backend.backend_name
        if should_enable_sync and ("jsonl" in backend_name or "both" in backend_name):
            sync_service = SyncService(project_dir=resolved_dir)
            if not sync_service.is_initialized():
                try:
                    sync_service.initialize()
                except Exception:
                    sync_service = None  # Disable if initialization fails

        # Status writer (run_id assigned later during execute)
        # We defer full status_writer creation to execute() so each run gets its own.

        # Interrupt handler
        interrupt_handler = InterruptHandler()

        return cls(
            config=resolved_config,
            project_dir=resolved_dir,
            task_backend=task_backend,
            harness_name=harness_name,
            harness_backend=harness_backend,
            ledger_integration=ledger_integration,
            sync_service=sync_service,
            interrupt_handler=interrupt_handler,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def config(self) -> CubConfig:
        """The resolved cub configuration."""
        return self._config

    @property
    def project_dir(self) -> Path:
        """The project root directory."""
        return self._project_dir

    @property
    def harness_name(self) -> str:
        """The name of the active harness."""
        return self._harness_name

    @property
    def task_backend(self) -> TaskBackend:
        """The active task backend."""
        return self._task_backend

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        run_config: RunConfig,
        *,
        run_id: str | None = None,
    ) -> Generator[RunEvent, None, None]:
        """
        Execute a run loop, yielding events as they occur.

        The caller iterates the returned generator to drive the loop.
        Each yielded ``RunEvent`` describes a state transition that the
        caller can render, log, or otherwise handle.

        After the generator is exhausted, call ``get_result()`` to obtain
        the final ``RunResult``.

        Args:
            run_config: Configuration for this specific run.
            run_id: Explicit run ID. Auto-generated if ``None``.

        Yields:
            ``RunEvent`` instances for each state transition.

        Example:
            >>> for event in service.execute(run_config):
            ...     if event.event_type == RunEventType.TASK_COMPLETED:
            ...         print(f"Done: {event.task_title}")
            >>> result = service.get_result()
            >>> print(result.success)
        """
        # Create a status writer for this run
        effective_run_id = run_id or run_config.session_name or None
        status_writer = self._status_writer
        if status_writer is None and effective_run_id is not None:
            status_writer = StatusWriter(self._project_dir, effective_run_id)

        # Register interrupt handler
        if self._interrupt_handler is not None:
            self._interrupt_handler.register()

        # Create the RunLoop
        self._current_loop = RunLoop(
            config=run_config,
            task_backend=self._task_backend,
            harness_backend=self._harness_backend,
            ledger_integration=self._ledger_integration,
            sync_service=self._sync_service,
            status_writer=status_writer,
            run_id=effective_run_id,
            interrupt_handler=self._interrupt_handler,
        )

        try:
            yield from self._current_loop.execute()
        finally:
            # Unregister interrupt handler
            if self._interrupt_handler is not None:
                try:
                    self._interrupt_handler.unregister()
                except Exception:
                    pass  # Non-fatal

    def get_result(self) -> RunResult:
        """
        Get the result of the most recent ``execute()`` call.

        Must be called after the generator from ``execute()`` is fully
        consumed (i.e., after the ``for`` loop completes or ``StopIteration``
        is raised).

        Returns:
            ``RunResult`` summarizing the run.

        Raises:
            RunServiceError: If no run has been executed yet.
        """
        if self._current_loop is None:
            raise RunServiceError("No run has been executed yet. Call execute() first.")
        return self._current_loop.get_result()

    def run_once(
        self,
        task_id: str,
        *,
        model: str | None = None,
        stream: bool = False,
        debug: bool = False,
        budget_tokens: int | None = None,
        budget_cost: float | None = None,
    ) -> RunResult:
        """
        Execute a single task and return the result.

        Convenience method that builds a ``RunConfig`` for a single-task
        run, drives the loop to completion (discarding events), and
        returns the final ``RunResult``.

        Args:
            task_id: The task ID to execute.
            model: Model override.
            stream: Stream harness output.
            debug: Enable debug logging.
            budget_tokens: Token budget limit.
            budget_cost: Cost budget limit (USD).

        Returns:
            ``RunResult`` with success/failure and metrics.
        """
        run_config = self._build_run_once_config(
            task_id=task_id,
            model=model,
            stream=stream,
            debug=debug,
            budget_tokens=budget_tokens,
            budget_cost=budget_cost,
        )

        # Drive the loop, collecting all events
        events: list[RunEvent] = []
        for event in self.execute(run_config):
            events.append(event)

        return self.get_result()

    # ------------------------------------------------------------------
    # Config builders
    # ------------------------------------------------------------------

    def build_run_config(
        self,
        *,
        once: bool = False,
        task_id: str | None = None,
        epic: str | None = None,
        label: str | None = None,
        model: str | None = None,
        session_name: str | None = None,
        stream: bool = False,
        debug: bool = False,
        max_iterations: int | None = None,
        budget_tokens: int | None = None,
        budget_cost: float | None = None,
        no_circuit_breaker: bool = False,
        no_sync: bool = False,
    ) -> RunConfig:
        """
        Build a ``RunConfig`` from high-level parameters and loaded config.

        Merges caller-supplied overrides with the project's ``CubConfig``
        to produce a fully-resolved ``RunConfig``. This mirrors the CLI's
        arg-to-config translation but without CLI dependencies.

        Args:
            once: Run a single iteration then exit.
            task_id: Run specific task by ID.
            epic: Only work on tasks in this epic.
            label: Only work on tasks with this label.
            model: Model override.
            session_name: Session name for tracking.
            stream: Stream harness output.
            debug: Enable debug logging.
            max_iterations: Override max iterations.
            budget_tokens: Token budget limit.
            budget_cost: Cost budget limit (USD).
            no_circuit_breaker: Disable circuit breaker.
            no_sync: Disable auto-sync.

        Returns:
            A fully-resolved ``RunConfig``.
        """
        cfg = self._config

        resolved_max_iterations = 1 if once else (max_iterations or cfg.loop.max_iterations)
        circuit_breaker_enabled = cfg.circuit_breaker.enabled and not no_circuit_breaker
        sync_enabled = self._sync_service is not None and not no_sync

        return RunConfig(
            once=once,
            task_id=task_id,
            epic=epic,
            label=label,
            model=model or cfg.harness.model,
            harness_name=self._harness_name,
            session_name=session_name,
            stream=stream,
            debug=debug,
            max_iterations=resolved_max_iterations,
            max_task_iterations=cfg.guardrails.max_task_iterations,
            on_task_failure=cfg.loop.on_task_failure,
            budget_tokens=budget_tokens or cfg.budget.max_tokens_per_task,
            budget_cost=budget_cost or cfg.budget.max_total_cost,
            budget_tasks=cfg.budget.max_tasks_per_session,
            circuit_breaker_enabled=circuit_breaker_enabled,
            circuit_breaker_timeout_minutes=cfg.circuit_breaker.timeout_minutes,
            ledger_enabled=cfg.ledger.enabled,
            hooks_enabled=cfg.hooks.enabled,
            hooks_fail_fast=cfg.hooks.fail_fast,
            sync_enabled=sync_enabled,
            iteration_warning_threshold=cfg.guardrails.iteration_warning_threshold,
            project_dir=str(self._project_dir),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_run_once_config(
        self,
        *,
        task_id: str,
        model: str | None = None,
        stream: bool = False,
        debug: bool = False,
        budget_tokens: int | None = None,
        budget_cost: float | None = None,
    ) -> RunConfig:
        """Build a RunConfig for a single-task execution."""
        return self.build_run_config(
            once=True,
            task_id=task_id,
            model=model,
            stream=stream,
            debug=debug,
            budget_tokens=budget_tokens,
            budget_cost=budget_cost,
        )
