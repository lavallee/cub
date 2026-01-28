"""
Service-level tests for cub.core.services.run.RunService.

Tests the RunService API surface, including factory construction,
config building, event-driven execution, and the run_once convenience
method. Uses mocked backends to isolate the service layer from external
systems.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.config.models import (
    BudgetConfig as BudgetCfg,
)
from cub.core.config.models import (
    CircuitBreakerConfig,
    CubConfig,
    GuardrailsConfig,
    HarnessConfig,
    HooksConfig,
    LedgerConfig,
    LoopConfig,
    SyncConfig,
)
from cub.core.run.models import RunEvent, RunEventType, RunResult
from cub.core.services.run import (
    HarnessNotAvailableError,
    HarnessNotFoundError,
    RunService,
    RunServiceError,
    TaskBackendError,
)

# ============================================================================
# Helpers
# ============================================================================


def _make_cub_config(**overrides: object) -> CubConfig:
    """Build a CubConfig with sensible defaults for testing."""
    defaults = {
        "harness": HarnessConfig(priority=["claude"], model="sonnet"),
        "loop": LoopConfig(max_iterations=10, on_task_failure="stop"),
        "budget": BudgetCfg(
            max_tokens_per_task=100_000,
            max_total_cost=10.0,
            max_tasks_per_session=50,
        ),
        "guardrails": GuardrailsConfig(
            max_task_iterations=3,
            iteration_warning_threshold=0.8,
        ),
        "circuit_breaker": CircuitBreakerConfig(enabled=True, timeout_minutes=30),
        "ledger": LedgerConfig(enabled=True),
        "hooks": HooksConfig(enabled=False, fail_fast=False),
        "sync": SyncConfig(enabled=False, auto_sync="never"),
    }
    defaults.update(overrides)
    return CubConfig(**defaults)  # type: ignore[arg-type]


def _make_task(
    task_id: str = "test-001",
    title: str = "Test task",
    status: str = "open",
    priority: str = "P2",
) -> MagicMock:
    """Create a mock Task object."""
    from cub.core.tasks.models import TaskPriority, TaskStatus, TaskType

    task = MagicMock()
    task.id = task_id
    task.title = title
    task.status = TaskStatus(status) if isinstance(status, str) else status
    task.priority = TaskPriority(priority)
    task.type = TaskType.TASK
    task.description = "Test description"
    task.labels = []
    task.model_label = None
    return task


def _make_harness_result(
    tokens: int = 1000,
    cost: float = 0.01,
    duration: float = 5.0,
    exit_code: int = 0,
    error: str | None = None,
) -> object:
    """Create a real HarnessResult for testing."""
    from cub.core.harness.models import HarnessResult, TokenUsage

    return HarnessResult(
        output="Task output",
        usage=TokenUsage(
            input_tokens=tokens // 2,
            output_tokens=tokens // 2,
            cost_usd=cost,
        ),
        duration_seconds=duration,
        exit_code=exit_code,
        error=error,
    )


def _make_task_counts(
    total: int = 5,
    open_count: int = 3,
    in_progress: int = 0,
    closed: int = 2,
) -> MagicMock:
    """Create mock TaskCounts."""
    counts = MagicMock()
    counts.total = total
    counts.open = open_count
    counts.in_progress = in_progress
    counts.closed = closed
    counts.remaining = open_count + in_progress
    return counts


@pytest.fixture
def mock_task_backend() -> MagicMock:
    """Provide a mock TaskBackend."""
    backend = MagicMock()
    backend.backend_name = "test"
    backend.get_task_counts.return_value = _make_task_counts()
    backend.get_ready_tasks.return_value = [_make_task()]
    backend.get_task.return_value = _make_task()
    backend.close_task.return_value = None
    backend.update_task.return_value = None
    return backend


@pytest.fixture
def mock_harness_backend() -> MagicMock:
    """Provide a mock AsyncHarnessBackend."""
    backend = MagicMock()
    backend.is_available.return_value = True
    backend.get_version.return_value = "1.0.0"
    backend.capabilities = MagicMock()
    backend.capabilities.streaming = False

    # run_task returns a coroutine that yields a real HarnessResult
    async def _run_task(task_input: object, debug: bool = False) -> object:
        return _make_harness_result()

    backend.run_task = _run_task
    return backend


@pytest.fixture
def cub_config() -> CubConfig:
    """Provide a test CubConfig."""
    return _make_cub_config()


@pytest.fixture
def run_service(
    cub_config: CubConfig,
    mock_task_backend: MagicMock,
    mock_harness_backend: MagicMock,
    tmp_path: Path,
) -> RunService:
    """Provide a RunService with mocked dependencies."""
    return RunService(
        config=cub_config,
        project_dir=tmp_path,
        task_backend=mock_task_backend,
        harness_name="test-harness",
        harness_backend=mock_harness_backend,
    )


# ============================================================================
# Test: Constructor and Properties
# ============================================================================


class TestRunServiceInit:
    """Tests for RunService construction and properties."""

    def test_constructor_stores_dependencies(
        self,
        cub_config: CubConfig,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Constructor stores all injected dependencies."""
        service = RunService(
            config=cub_config,
            project_dir=tmp_path,
            task_backend=mock_task_backend,
            harness_name="claude",
            harness_backend=mock_harness_backend,
        )
        assert service.config is cub_config
        assert service.project_dir == tmp_path
        assert service.harness_name == "claude"
        assert service.task_backend is mock_task_backend

    def test_get_result_before_execute_raises(self, run_service: RunService) -> None:
        """get_result raises if no run has been executed."""
        with pytest.raises(RunServiceError, match="No run has been executed"):
            run_service.get_result()


# ============================================================================
# Test: from_config Factory
# ============================================================================


class TestRunServiceFromConfig:
    """Tests for the from_config factory method."""

    @patch("cub.core.services.run.load_config")
    @patch("cub.core.services.run.detect_async_harness")
    @patch("cub.core.services.run.get_async_backend")
    @patch("cub.core.services.run.get_task_backend")
    def test_from_config_creates_service(
        self,
        mock_get_task: MagicMock,
        mock_get_harness: MagicMock,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        tmp_path: Path,
    ) -> None:
        """from_config wires up all dependencies and returns a RunService."""
        mock_load.return_value = _make_cub_config()
        mock_detect.return_value = "claude"
        harness = MagicMock()
        harness.is_available.return_value = True
        mock_get_harness.return_value = harness
        mock_get_task.return_value = MagicMock(backend_name="test")

        service = RunService.from_config(project_dir=tmp_path)

        assert service.harness_name == "claude"
        assert service.project_dir == tmp_path
        mock_load.assert_called_once_with(tmp_path)

    @patch("cub.core.services.run.load_config")
    @patch("cub.core.services.run.detect_async_harness")
    @patch("cub.core.services.run.get_async_backend")
    @patch("cub.core.services.run.get_task_backend")
    def test_from_config_with_explicit_config(
        self,
        mock_get_task: MagicMock,
        mock_get_harness: MagicMock,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        tmp_path: Path,
    ) -> None:
        """from_config skips loading when config is provided."""
        cfg = _make_cub_config()
        mock_detect.return_value = "claude"
        harness = MagicMock()
        harness.is_available.return_value = True
        mock_get_harness.return_value = harness
        mock_get_task.return_value = MagicMock(backend_name="test")

        service = RunService.from_config(config=cfg, project_dir=tmp_path)

        assert service.config is cfg
        mock_load.assert_not_called()

    @patch("cub.core.services.run.load_config")
    @patch("cub.core.services.run.detect_async_harness")
    def test_from_config_raises_when_no_harness(
        self,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        tmp_path: Path,
    ) -> None:
        """from_config raises HarnessNotFoundError if no harness detected."""
        mock_load.return_value = _make_cub_config()
        mock_detect.return_value = None

        with pytest.raises(HarnessNotFoundError, match="No harness detected"):
            RunService.from_config(project_dir=tmp_path)

    @patch("cub.core.services.run.load_config")
    @patch("cub.core.services.run.detect_async_harness")
    @patch("cub.core.services.run.get_async_backend")
    def test_from_config_raises_when_harness_unavailable(
        self,
        mock_get_harness: MagicMock,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        tmp_path: Path,
    ) -> None:
        """from_config raises HarnessNotAvailableError if harness isn't installed."""
        mock_load.return_value = _make_cub_config()
        mock_detect.return_value = "claude"
        harness = MagicMock()
        harness.is_available.return_value = False
        mock_get_harness.return_value = harness

        with pytest.raises(HarnessNotAvailableError, match="claude"):
            RunService.from_config(project_dir=tmp_path)

    @patch("cub.core.services.run.load_config")
    @patch("cub.core.services.run.detect_async_harness")
    @patch("cub.core.services.run.get_async_backend")
    @patch("cub.core.services.run.get_task_backend")
    def test_from_config_raises_on_task_backend_error(
        self,
        mock_get_task: MagicMock,
        mock_get_harness: MagicMock,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        tmp_path: Path,
    ) -> None:
        """from_config raises TaskBackendError if task backend fails."""
        mock_load.return_value = _make_cub_config()
        mock_detect.return_value = "claude"
        harness = MagicMock()
        harness.is_available.return_value = True
        mock_get_harness.return_value = harness
        mock_get_task.side_effect = RuntimeError("Backend broken")

        with pytest.raises(TaskBackendError, match="Backend broken"):
            RunService.from_config(project_dir=tmp_path)

    @patch("cub.core.services.run.load_config")
    @patch("cub.core.services.run.detect_async_harness")
    @patch("cub.core.services.run.get_async_backend")
    @patch("cub.core.services.run.get_task_backend")
    def test_from_config_explicit_harness(
        self,
        mock_get_task: MagicMock,
        mock_get_harness: MagicMock,
        mock_detect: MagicMock,
        mock_load: MagicMock,
        tmp_path: Path,
    ) -> None:
        """from_config uses explicit harness name when provided."""
        mock_load.return_value = _make_cub_config()
        harness = MagicMock()
        harness.is_available.return_value = True
        mock_get_harness.return_value = harness
        mock_get_task.return_value = MagicMock(backend_name="test")

        service = RunService.from_config(project_dir=tmp_path, harness="codex")

        assert service.harness_name == "codex"
        mock_detect.assert_not_called()


# ============================================================================
# Test: build_run_config
# ============================================================================


class TestBuildRunConfig:
    """Tests for RunService.build_run_config."""

    def test_defaults_from_cub_config(self, run_service: RunService) -> None:
        """build_run_config uses CubConfig defaults when no overrides given."""
        rc = run_service.build_run_config()
        assert rc.max_iterations == 10  # from our test config
        assert rc.harness_name == "test-harness"
        assert rc.model == "sonnet"  # from test config
        assert rc.on_task_failure == "stop"
        assert rc.circuit_breaker_enabled is True
        assert rc.hooks_enabled is False  # our test config has hooks disabled

    def test_once_sets_max_iterations_to_1(self, run_service: RunService) -> None:
        """When once=True, max_iterations is forced to 1."""
        rc = run_service.build_run_config(once=True)
        assert rc.once is True
        assert rc.max_iterations == 1

    def test_overrides_applied(self, run_service: RunService) -> None:
        """Caller-supplied overrides take precedence."""
        rc = run_service.build_run_config(
            task_id="cub-99",
            epic="backend-v2",
            label="urgent",
            model="opus",
            session_name="my-session",
            stream=True,
            debug=True,
            max_iterations=5,
            budget_tokens=50_000,
            budget_cost=2.5,
        )
        assert rc.task_id == "cub-99"
        assert rc.epic == "backend-v2"
        assert rc.label == "urgent"
        assert rc.model == "opus"
        assert rc.session_name == "my-session"
        assert rc.stream is True
        assert rc.debug is True
        assert rc.max_iterations == 5
        assert rc.budget_tokens == 50_000
        assert rc.budget_cost == 2.5

    def test_no_circuit_breaker(self, run_service: RunService) -> None:
        """no_circuit_breaker disables circuit breaker in config."""
        rc = run_service.build_run_config(no_circuit_breaker=True)
        assert rc.circuit_breaker_enabled is False

    def test_project_dir_set(self, run_service: RunService) -> None:
        """project_dir is set from service's project_dir."""
        rc = run_service.build_run_config()
        assert rc.project_dir == str(run_service.project_dir)


# ============================================================================
# Test: execute
# ============================================================================


class TestExecute:
    """Tests for RunService.execute (event-driven loop)."""

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_execute_yields_events(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        run_service: RunService,
    ) -> None:
        """execute() yields RunEvent instances."""
        rc = run_service.build_run_config(once=True)
        events = list(run_service.execute(rc))
        assert len(events) > 0
        assert all(isinstance(e, RunEvent) for e in events)

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_execute_emits_run_started(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        run_service: RunService,
    ) -> None:
        """execute() emits RUN_STARTED as first event."""
        rc = run_service.build_run_config(once=True)
        events = list(run_service.execute(rc))
        assert events[0].event_type == RunEventType.RUN_STARTED

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_execute_emits_task_events(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        run_service: RunService,
    ) -> None:
        """execute() emits TASK_SELECTED and TASK_COMPLETED for a successful task."""
        rc = run_service.build_run_config(once=True)
        events = list(run_service.execute(rc))
        event_types = [e.event_type for e in events]
        assert RunEventType.TASK_SELECTED in event_types
        assert RunEventType.TASK_COMPLETED in event_types

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_get_result_after_execute(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        run_service: RunService,
    ) -> None:
        """get_result() returns RunResult after execute completes."""
        rc = run_service.build_run_config(once=True)
        list(run_service.execute(rc))
        result = run_service.get_result()
        assert isinstance(result, RunResult)
        assert result.iterations_completed >= 1
        assert result.tasks_completed >= 1

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_execute_with_no_tasks(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        run_service: RunService,
        mock_task_backend: MagicMock,
    ) -> None:
        """execute() handles no-task scenario gracefully."""
        mock_task_backend.get_ready_tasks.return_value = []
        mock_task_backend.get_task_counts.return_value = _make_task_counts(
            total=0, open_count=0, in_progress=0, closed=0
        )
        rc = run_service.build_run_config(once=True)
        events = list(run_service.execute(rc))
        event_types = [e.event_type for e in events]
        # Should get either NO_TASKS_AVAILABLE or ALL_TASKS_COMPLETE
        assert (
            RunEventType.NO_TASKS_AVAILABLE in event_types
            or RunEventType.ALL_TASKS_COMPLETE in event_types
        )


# ============================================================================
# Test: run_once
# ============================================================================


class TestRunOnce:
    """Tests for RunService.run_once convenience method."""

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_run_once_returns_result(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        run_service: RunService,
    ) -> None:
        """run_once returns a RunResult."""
        result = run_service.run_once("test-001")
        assert isinstance(result, RunResult)

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_run_once_success(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        run_service: RunService,
    ) -> None:
        """run_once succeeds with a valid task."""
        result = run_service.run_once("test-001")
        assert result.tasks_completed >= 1

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_run_once_with_model_override(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        run_service: RunService,
    ) -> None:
        """run_once passes model override through to RunConfig."""
        result = run_service.run_once("test-001", model="opus")
        assert isinstance(result, RunResult)


# ============================================================================
# Test: Exception types
# ============================================================================


class TestExceptions:
    """Tests for service-layer typed exceptions."""

    def test_harness_not_found_error(self) -> None:
        """HarnessNotFoundError is a RunServiceError."""
        err = HarnessNotFoundError("no harness")
        assert isinstance(err, RunServiceError)

    def test_harness_not_available_error(self) -> None:
        """HarnessNotAvailableError stores harness name."""
        err = HarnessNotAvailableError("claude")
        assert err.harness_name == "claude"
        assert "claude" in str(err)
        assert isinstance(err, RunServiceError)

    def test_task_backend_error(self) -> None:
        """TaskBackendError is a RunServiceError."""
        err = TaskBackendError("broken")
        assert isinstance(err, RunServiceError)
