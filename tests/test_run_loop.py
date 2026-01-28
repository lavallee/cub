"""
Unit tests for cub.core.run.loop.

Tests the run loop state machine in isolation, with mocked task backend,
harness backend, and ledger integration. Validates the event-driven
generator interface and all loop behaviors.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.run.loop import RunLoop
from cub.core.run.models import RunConfig, RunEvent, RunEventType, RunResult

# ===========================================================================
# Test Fixtures
# ===========================================================================


def _make_task(
    task_id: str = "test-001",
    title: str = "Test task",
    status: str = "open",
    priority: str = "P2",
    model_label: str | None = None,
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
    task.model_label = model_label
    return task


def _make_harness_result(
    success: bool = True,
    tokens: int = 1000,
    cost: float = 0.01,
    duration: float = 5.0,
    exit_code: int = 0,
    error: str | None = None,
) -> MagicMock:
    """Create a mock HarnessResult."""
    result = MagicMock()
    result.success = success
    result.duration_seconds = duration
    result.exit_code = exit_code
    result.error = error
    result.usage = MagicMock()
    result.usage.total_tokens = tokens
    result.usage.cost_usd = cost
    result.usage.input_tokens = tokens // 2
    result.usage.output_tokens = tokens // 2
    result.usage.cache_read_tokens = 0
    result.usage.cache_creation_tokens = 0
    return result


def _make_task_counts(
    total: int = 5,
    open_count: int = 3,
    in_progress: int = 0,
    closed: int = 2,
) -> MagicMock:
    """Create a mock TaskCounts."""
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
    backend.capabilities = MagicMock()
    backend.capabilities.streaming = False
    backend.is_available.return_value = True
    backend.get_version.return_value = "1.0.0"
    return backend


@pytest.fixture
def base_config(tmp_path: Path) -> RunConfig:
    """Provide a base RunConfig for testing (single iteration)."""
    return RunConfig(
        once=True,
        harness_name="test-harness",
        debug=False,
        max_iterations=1,
        on_task_failure="stop",
        circuit_breaker_enabled=False,
        ledger_enabled=False,
        hooks_enabled=False,
        sync_enabled=False,
        project_dir=str(tmp_path),
    )


# ===========================================================================
# RunConfig model tests
# ===========================================================================


class TestRunConfig:
    """Tests for the RunConfig model."""

    def test_default_values(self) -> None:
        """Default config has sensible defaults."""
        config = RunConfig()
        assert config.once is False
        assert config.task_id is None
        assert config.epic is None
        assert config.label is None
        assert config.max_iterations == 100
        assert config.on_task_failure == "stop"
        assert config.circuit_breaker_enabled is True
        assert config.ledger_enabled is True
        assert config.hooks_enabled is True

    def test_once_mode(self) -> None:
        """Once mode is configurable."""
        config = RunConfig(once=True)
        assert config.once is True

    def test_task_id_filtering(self) -> None:
        """Can specify a specific task."""
        config = RunConfig(task_id="cub-123")
        assert config.task_id == "cub-123"

    def test_budget_limits(self) -> None:
        """Budget limits can be set."""
        config = RunConfig(
            budget_tokens=100000,
            budget_cost=5.0,
            budget_tasks=10,
        )
        assert config.budget_tokens == 100000
        assert config.budget_cost == 5.0
        assert config.budget_tasks == 10

    def test_frozen_dataclass(self) -> None:
        """RunConfig is immutable."""
        config = RunConfig()
        with pytest.raises(AttributeError):
            config.once = True  # type: ignore[misc]


# ===========================================================================
# RunEvent model tests
# ===========================================================================


class TestRunEvent:
    """Tests for the RunEvent model."""

    def test_basic_event(self) -> None:
        """Can create a basic event."""
        event = RunEvent(
            event_type=RunEventType.RUN_STARTED,
            message="Starting run",
        )
        assert event.event_type == RunEventType.RUN_STARTED
        assert event.message == "Starting run"
        assert event.task_id is None
        assert event.timestamp is not None

    def test_task_event(self) -> None:
        """Task events carry task context."""
        event = RunEvent(
            event_type=RunEventType.TASK_COMPLETED,
            message="Done",
            task_id="cub-123",
            task_title="Fix bug",
            duration_seconds=5.0,
            tokens_used=1000,
        )
        assert event.task_id == "cub-123"
        assert event.task_title == "Fix bug"
        assert event.duration_seconds == 5.0
        assert event.tokens_used == 1000

    def test_error_event(self) -> None:
        """Error events carry error info."""
        event = RunEvent(
            event_type=RunEventType.HARNESS_ERROR,
            error="Connection failed",
        )
        assert event.error == "Connection failed"

    def test_event_data(self) -> None:
        """Events can carry arbitrary data."""
        event = RunEvent(
            event_type=RunEventType.RUN_COMPLETED,
            data={"custom_key": "value"},
        )
        assert event.data["custom_key"] == "value"


# ===========================================================================
# RunEventType enum tests
# ===========================================================================


class TestRunEventType:
    """Tests for the RunEventType enum."""

    def test_lifecycle_events(self) -> None:
        """Lifecycle event types exist."""
        assert RunEventType.RUN_STARTED.value == "run_started"
        assert RunEventType.RUN_COMPLETED.value == "run_completed"
        assert RunEventType.RUN_FAILED.value == "run_failed"
        assert RunEventType.RUN_STOPPED.value == "run_stopped"

    def test_task_events(self) -> None:
        """Task event types exist."""
        assert RunEventType.TASK_SELECTED.value == "task_selected"
        assert RunEventType.TASK_STARTED.value == "task_started"
        assert RunEventType.TASK_COMPLETED.value == "task_completed"
        assert RunEventType.TASK_FAILED.value == "task_failed"

    def test_budget_events(self) -> None:
        """Budget event types exist."""
        assert RunEventType.BUDGET_UPDATED.value == "budget_updated"
        assert RunEventType.BUDGET_WARNING.value == "budget_warning"
        assert RunEventType.BUDGET_EXHAUSTED.value == "budget_exhausted"

    def test_string_enum(self) -> None:
        """RunEventType is a string enum."""
        assert isinstance(RunEventType.RUN_STARTED, str)
        assert RunEventType.RUN_STARTED == "run_started"


# ===========================================================================
# RunResult model tests
# ===========================================================================


class TestRunResult:
    """Tests for the RunResult model."""

    def test_default_result(self) -> None:
        """Default result indicates no work done."""
        result = RunResult()
        assert result.success is False
        assert result.iterations_completed == 0
        assert result.tasks_completed == 0

    def test_successful_result(self) -> None:
        """Can represent a successful run."""
        result = RunResult(
            run_id="test-run",
            success=True,
            phase="completed",
            iterations_completed=3,
            tasks_completed=3,
            total_tokens=5000,
            total_cost_usd=0.50,
        )
        assert result.success is True
        assert result.tasks_completed == 3
        assert result.total_tokens == 5000


# ===========================================================================
# RunLoop - Basic lifecycle tests
# ===========================================================================


class TestRunLoopLifecycle:
    """Tests for RunLoop lifecycle (start, stop, complete)."""

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    def test_run_started_event(
        self,
        mock_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Loop yields RUN_STARTED event first."""
        # No tasks available → loop ends immediately
        mock_task_backend.get_ready_tasks.return_value = []
        mock_task_backend.get_task_counts.return_value = _make_task_counts(
            total=0, open_count=0, closed=0
        )

        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        events = list(loop.execute())
        assert len(events) >= 2
        assert events[0].event_type == RunEventType.RUN_STARTED

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    def test_all_tasks_complete(
        self,
        mock_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Loop yields ALL_TASKS_COMPLETE when no tasks remain."""
        mock_task_backend.get_ready_tasks.return_value = []
        mock_task_backend.get_task_counts.return_value = _make_task_counts(
            total=5, open_count=0, in_progress=0, closed=5
        )

        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        events = list(loop.execute())
        event_types = [e.event_type for e in events]
        assert RunEventType.ALL_TASKS_COMPLETE in event_types

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    def test_no_tasks_available_blocked(
        self,
        mock_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Loop yields NO_TASKS_AVAILABLE when tasks are blocked."""
        mock_task_backend.get_ready_tasks.return_value = []
        mock_task_backend.get_task_counts.return_value = _make_task_counts(
            total=5, open_count=3, in_progress=0, closed=2
        )

        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        events = list(loop.execute())
        event_types = [e.event_type for e in events]
        assert RunEventType.NO_TASKS_AVAILABLE in event_types

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    def test_interrupt_stops_loop(
        self,
        mock_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Setting interrupted flag stops the loop."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )
        loop.interrupted = True

        events = list(loop.execute())
        event_types = [e.event_type for e in events]
        assert RunEventType.INTERRUPT_RECEIVED in event_types

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    def test_get_result_after_empty_run(
        self,
        mock_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """get_result() returns summary after consuming generator."""
        mock_task_backend.get_ready_tasks.return_value = []
        mock_task_backend.get_task_counts.return_value = _make_task_counts(
            total=0, open_count=0, closed=0
        )

        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        list(loop.execute())  # consume generator
        result = loop.get_result()

        assert isinstance(result, RunResult)
        assert result.tasks_completed == 0
        assert result.iterations_completed <= 1


# ===========================================================================
# RunLoop - Task selection tests
# ===========================================================================


class TestRunLoopTaskSelection:
    """Tests for task selection behavior."""

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_selects_first_ready_task(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Loop selects the first ready task from backend."""
        task = _make_task(task_id="cub-001", title="First task")
        mock_task_backend.get_ready_tasks.return_value = [task]

        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        # Mock the harness invocation
        with patch.object(loop, "_invoke_harness", return_value=_make_harness_result()):
            events = list(loop.execute())

        event_types = [e.event_type for e in events]
        assert RunEventType.TASK_SELECTED in event_types

        selected = next(e for e in events if e.event_type == RunEventType.TASK_SELECTED)
        assert selected.task_id == "cub-001"

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    def test_specific_task_not_found(
        self,
        mock_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When specific task not found, yields failure event."""
        mock_task_backend.get_task.return_value = None

        config = RunConfig(
            once=True,
            task_id="nonexistent",
            harness_name="test",
            circuit_breaker_enabled=False,
            ledger_enabled=False,
            hooks_enabled=False,
            project_dir=str(tmp_path),
        )

        loop = RunLoop(
            config=config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        events = list(loop.execute())
        event_types = [e.event_type for e in events]
        assert RunEventType.RUN_FAILED in event_types

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    def test_specific_task_already_closed(
        self,
        mock_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When specific task is closed, yields completion event."""

        closed_task = _make_task(task_id="cub-done", status="closed")
        mock_task_backend.get_task.return_value = closed_task

        config = RunConfig(
            once=True,
            task_id="cub-done",
            harness_name="test",
            circuit_breaker_enabled=False,
            ledger_enabled=False,
            hooks_enabled=False,
            project_dir=str(tmp_path),
        )

        loop = RunLoop(
            config=config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        events = list(loop.execute())
        event_types = [e.event_type for e in events]
        assert RunEventType.ALL_TASKS_COMPLETE in event_types


# ===========================================================================
# RunLoop - Task execution tests
# ===========================================================================


class TestRunLoopTaskExecution:
    """Tests for task execution and result handling."""

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_successful_task_yields_completed(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Successful task execution yields TASK_COMPLETED event."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(loop, "_invoke_harness", return_value=_make_harness_result()):
            events = list(loop.execute())

        event_types = [e.event_type for e in events]
        assert RunEventType.TASK_COMPLETED in event_types
        assert RunEventType.BUDGET_UPDATED in event_types

        completed = next(e for e in events if e.event_type == RunEventType.TASK_COMPLETED)
        assert completed.tokens_used == 1000
        assert completed.cost_usd == 0.01

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_failed_task_yields_failed(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Failed task execution yields TASK_FAILED event."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        failed_result = _make_harness_result(
            success=False, error="Test error", exit_code=1
        )
        with patch.object(loop, "_invoke_harness", return_value=failed_result):
            events = list(loop.execute())

        event_types = [e.event_type for e in events]
        assert RunEventType.TASK_FAILED in event_types

        failed = next(e for e in events if e.event_type == RunEventType.TASK_FAILED)
        assert failed.error == "Test error"

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_harness_exception_yields_error(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Harness exception yields HARNESS_ERROR event."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(
            loop, "_invoke_harness", side_effect=RuntimeError("Connection lost")
        ):
            events = list(loop.execute())

        event_types = [e.event_type for e in events]
        assert RunEventType.HARNESS_ERROR in event_types

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_successful_task_closes_in_backend(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Successful task is closed in the backend."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(loop, "_invoke_harness", return_value=_make_harness_result()):
            list(loop.execute())

        mock_task_backend.close_task.assert_called_once()

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_task_claimed_before_execution(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Task is claimed (set to in_progress) before harness execution."""
        from cub.core.tasks.models import TaskStatus

        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(loop, "_invoke_harness", return_value=_make_harness_result()):
            list(loop.execute())

        mock_task_backend.update_task.assert_called()
        call_args = mock_task_backend.update_task.call_args
        assert call_args.kwargs.get("status") == TaskStatus.IN_PROGRESS


# ===========================================================================
# RunLoop - Budget tracking tests
# ===========================================================================


class TestRunLoopBudget:
    """Tests for budget tracking and enforcement."""

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_budget_updated_after_task(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Budget is updated after each task execution."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(
            loop, "_invoke_harness",
            return_value=_make_harness_result(tokens=5000, cost=0.50),
        ):
            events = list(loop.execute())

        budget_events = [e for e in events if e.event_type == RunEventType.BUDGET_UPDATED]
        assert len(budget_events) == 1
        assert budget_events[0].tokens_used == 5000
        assert budget_events[0].cost_usd == 0.50

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    def test_budget_exhausted_stops_loop(
        self,
        mock_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Loop stops when budget is exhausted."""
        config = RunConfig(
            once=False,
            harness_name="test",
            max_iterations=10,
            budget_tokens=100,  # Very low budget
            circuit_breaker_enabled=False,
            ledger_enabled=False,
            hooks_enabled=False,
            project_dir=str(tmp_path),
        )

        loop = RunLoop(
            config=config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        # Pre-exhaust the budget
        loop._budget_manager.record_usage(tokens=200, cost_usd=0.0)

        events = list(loop.execute())
        event_types = [e.event_type for e in events]
        assert RunEventType.BUDGET_EXHAUSTED in event_types

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_budget_warning_fires_once(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Budget warning event fires once when threshold is crossed."""
        config = RunConfig(
            once=False,
            harness_name="test",
            max_iterations=3,
            budget_tokens=1000,
            iteration_warning_threshold=0.5,  # 50% warning
            circuit_breaker_enabled=False,
            ledger_enabled=False,
            hooks_enabled=False,
            project_dir=str(tmp_path),
        )

        # Create tasks for 3 iterations
        tasks = [
            _make_task(task_id=f"t-{i}", title=f"Task {i}") for i in range(3)
        ]
        mock_task_backend.get_ready_tasks.side_effect = [
            [tasks[0]], [tasks[1]], [tasks[2]],
        ]

        loop = RunLoop(
            config=config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        # Each task uses 400 tokens → after 2 tasks, 80% used (over 50% threshold)
        with patch.object(
            loop, "_invoke_harness",
            return_value=_make_harness_result(tokens=400, cost=0.0),
        ):
            events = list(loop.execute())

        warnings = [e for e in events if e.event_type == RunEventType.BUDGET_WARNING]
        assert len(warnings) <= 1  # Fires at most once


# ===========================================================================
# RunLoop - Result tracking tests
# ===========================================================================


class TestRunLoopResult:
    """Tests for RunLoop.get_result()."""

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_result_tracks_completed_tasks(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Result tracks number of completed tasks."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(loop, "_invoke_harness", return_value=_make_harness_result()):
            list(loop.execute())

        result = loop.get_result()
        assert result.tasks_completed == 1
        assert result.tasks_failed == 0

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_result_tracks_failed_tasks(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Result tracks number of failed tasks."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        failed_result = _make_harness_result(success=False, error="fail")
        with patch.object(loop, "_invoke_harness", return_value=failed_result):
            list(loop.execute())

        result = loop.get_result()
        assert result.tasks_completed == 0
        assert result.tasks_failed == 1

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_result_tracks_tokens(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Result tracks total token usage."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(
            loop, "_invoke_harness",
            return_value=_make_harness_result(tokens=3000, cost=0.30),
        ):
            list(loop.execute())

        result = loop.get_result()
        assert result.total_tokens == 3000
        assert result.total_cost_usd == 0.30

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_result_includes_events(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        base_config: RunConfig,
    ) -> None:
        """Result includes all events from the run."""
        loop = RunLoop(
            config=base_config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(loop, "_invoke_harness", return_value=_make_harness_result()):
            list(loop.execute())

        result = loop.get_result()
        assert len(result.events) > 0
        assert any(e.event_type == RunEventType.RUN_STARTED for e in result.events)


# ===========================================================================
# RunLoop - Multi-iteration tests
# ===========================================================================


class TestRunLoopMultiIteration:
    """Tests for multi-iteration loop behavior."""

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    @patch("cub.core.run.loop.time.sleep")  # Don't actually sleep
    def test_max_iterations_reached(
        self,
        mock_sleep: MagicMock,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Loop stops at max iterations."""
        config = RunConfig(
            once=False,
            harness_name="test",
            max_iterations=3,
            circuit_breaker_enabled=False,
            ledger_enabled=False,
            hooks_enabled=False,
            project_dir=str(tmp_path),
        )

        # Return fresh tasks for each iteration
        tasks = [_make_task(task_id=f"t-{i}") for i in range(5)]
        mock_task_backend.get_ready_tasks.side_effect = [
            [tasks[0]], [tasks[1]], [tasks[2]],
        ]

        loop = RunLoop(
            config=config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        with patch.object(loop, "_invoke_harness", return_value=_make_harness_result()):
            events = list(loop.execute())

        event_types = [e.event_type for e in events]
        assert RunEventType.MAX_ITERATIONS_REACHED in event_types

        result = loop.get_result()
        assert result.iterations_completed == 3

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_on_task_failure_stop(
        self,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        tmp_path: Path,
    ) -> None:
        """With on_task_failure=stop, loop stops on first failure."""
        config = RunConfig(
            once=False,
            harness_name="test",
            max_iterations=5,
            on_task_failure="stop",
            circuit_breaker_enabled=False,
            ledger_enabled=False,
            hooks_enabled=False,
            project_dir=str(tmp_path),
        )

        loop = RunLoop(
            config=config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        failed = _make_harness_result(success=False, error="fail")
        with patch.object(loop, "_invoke_harness", return_value=failed):
            list(loop.execute())

        result = loop.get_result()
        assert result.tasks_failed == 1
        assert result.phase == "failed"

    @patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt")
    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    @patch("cub.core.run.loop.time.sleep")
    def test_on_task_failure_continue(
        self,
        mock_sleep: MagicMock,
        mock_task_prompt: MagicMock,
        mock_sys_prompt: MagicMock,
        mock_task_backend: MagicMock,
        mock_harness_backend: MagicMock,
        tmp_path: Path,
    ) -> None:
        """With on_task_failure=continue, loop continues after failure."""
        config = RunConfig(
            once=False,
            harness_name="test",
            max_iterations=3,
            on_task_failure="continue",
            circuit_breaker_enabled=False,
            ledger_enabled=False,
            hooks_enabled=False,
            project_dir=str(tmp_path),
        )

        tasks = [_make_task(task_id=f"t-{i}") for i in range(3)]
        mock_task_backend.get_ready_tasks.side_effect = [
            [tasks[0]], [tasks[1]], [tasks[2]],
        ]

        loop = RunLoop(
            config=config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )

        # First fails, second succeeds, third fails
        results = [
            _make_harness_result(success=False, error="fail"),
            _make_harness_result(success=True),
            _make_harness_result(success=False, error="fail 2"),
        ]
        with patch.object(loop, "_invoke_harness", side_effect=results):
            list(loop.execute())

        result = loop.get_result()
        assert result.tasks_completed == 1
        assert result.tasks_failed == 2
        assert result.iterations_completed == 3


# ===========================================================================
# RunLoop - Import and re-export tests
# ===========================================================================


class TestRunLoopImports:
    """Tests that RunLoop and models can be imported from the package."""

    def test_import_from_package(self) -> None:
        """Can import from cub.core.run package."""
        from cub.core.run import RunConfig, RunEvent, RunEventType, RunLoop, RunResult

        assert RunConfig is not None
        assert RunEvent is not None
        assert RunEventType is not None
        assert RunLoop is not None
        assert RunResult is not None

    def test_import_models_directly(self) -> None:
        """Can import from cub.core.run.models directly."""
        from cub.core.run.models import RunConfig

        assert RunConfig is not None

    def test_import_loop_directly(self) -> None:
        """Can import from cub.core.run.loop directly."""
        from cub.core.run.loop import RunLoop

        assert RunLoop is not None
