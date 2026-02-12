"""
Tests for RETRY status, non-executable type filtering, and failure path retry state.

Covers:
- TaskStatus.RETRY enum value
- NON_EXECUTABLE_TYPES constant
- Task.is_ready excludes epics/gates and includes RETRY
- Task.mark_retry() method
- TaskCounts.retry field and remaining calculation
- JsonlBackend.get_ready_tasks excludes epics/gates, includes RETRY, sorts correctly
- JsonlBackend.get_task_counts counts RETRY
- JsonlBackend.try_close_epic blocks on RETRY children
- RunLoop failure paths set RETRY status
- RunLoop._select_task rejects epic/gate types
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from cub.core.tasks.models import (
    NON_EXECUTABLE_TYPES,
    Task,
    TaskCounts,
    TaskPriority,
    TaskStatus,
    TaskType,
)

if TYPE_CHECKING:
    from cub.core.run.loop import RunLoop


# ==============================================================================
# Model Tests
# ==============================================================================


class TestTaskStatusRetry:
    """Test RETRY status enum value."""

    def test_retry_enum_exists(self) -> None:
        assert TaskStatus.RETRY == "retry"
        assert TaskStatus("retry") == TaskStatus.RETRY

    def test_retry_between_in_progress_and_closed(self) -> None:
        members = list(TaskStatus)
        assert members.index(TaskStatus.RETRY) > members.index(TaskStatus.IN_PROGRESS)
        assert members.index(TaskStatus.RETRY) < members.index(TaskStatus.CLOSED)


class TestNonExecutableTypes:
    """Test NON_EXECUTABLE_TYPES constant."""

    def test_contains_epic_and_gate(self) -> None:
        assert TaskType.EPIC in NON_EXECUTABLE_TYPES
        assert TaskType.GATE in NON_EXECUTABLE_TYPES

    def test_does_not_contain_regular_types(self) -> None:
        assert TaskType.TASK not in NON_EXECUTABLE_TYPES
        assert TaskType.FEATURE not in NON_EXECUTABLE_TYPES
        assert TaskType.BUG not in NON_EXECUTABLE_TYPES
        assert TaskType.BUGFIX not in NON_EXECUTABLE_TYPES

    def test_is_frozenset(self) -> None:
        assert isinstance(NON_EXECUTABLE_TYPES, frozenset)


class TestIsReadyWithRetry:
    """Test Task.is_ready with RETRY status and non-executable types."""

    def test_open_task_is_ready(self) -> None:
        task = Task(id="t-1", title="Test", status=TaskStatus.OPEN)
        assert task.is_ready is True

    def test_retry_task_is_ready(self) -> None:
        task = Task(id="t-1", title="Test", status=TaskStatus.RETRY)
        assert task.is_ready is True

    def test_in_progress_task_not_ready(self) -> None:
        task = Task(id="t-1", title="Test", status=TaskStatus.IN_PROGRESS)
        assert task.is_ready is False

    def test_closed_task_not_ready(self) -> None:
        task = Task(id="t-1", title="Test", status=TaskStatus.CLOSED)
        assert task.is_ready is False

    def test_epic_not_ready_even_if_open(self) -> None:
        task = Task(id="t-1", title="Epic", status=TaskStatus.OPEN, type=TaskType.EPIC)
        assert task.is_ready is False

    def test_gate_not_ready_even_if_open(self) -> None:
        task = Task(id="t-1", title="Gate", status=TaskStatus.OPEN, type=TaskType.GATE)
        assert task.is_ready is False

    def test_epic_not_ready_even_if_retry(self) -> None:
        task = Task(id="t-1", title="Epic", status=TaskStatus.RETRY, type=TaskType.EPIC)
        assert task.is_ready is False

    def test_retry_task_with_deps_not_ready(self) -> None:
        task = Task(id="t-1", title="Test", status=TaskStatus.RETRY, depends_on=["t-0"])
        assert task.is_ready is False


class TestMarkRetry:
    """Test Task.mark_retry() method."""

    def test_mark_retry_sets_status(self) -> None:
        task = Task(id="t-1", title="Test", status=TaskStatus.IN_PROGRESS)
        task.mark_retry()
        assert task.status == TaskStatus.RETRY
        assert task.updated_at is not None

    def test_mark_retry_with_reason(self) -> None:
        task = Task(id="t-1", title="Test", status=TaskStatus.IN_PROGRESS)
        task.mark_retry("Circuit breaker tripped")
        assert task.status == TaskStatus.RETRY
        assert "Circuit breaker tripped" in task.notes

    def test_mark_retry_appends_to_existing_notes(self) -> None:
        task = Task(id="t-1", title="Test", status=TaskStatus.IN_PROGRESS, notes="Existing")
        task.mark_retry("Harness error")
        assert task.notes.startswith("Existing\n")
        assert "Harness error" in task.notes


class TestTaskCountsRetry:
    """Test TaskCounts with retry field."""

    def test_retry_field_default_zero(self) -> None:
        counts = TaskCounts(total=5, open=3, in_progress=1, closed=1)
        assert counts.retry == 0

    def test_retry_in_remaining(self) -> None:
        counts = TaskCounts(total=10, open=3, in_progress=2, retry=1, closed=4)
        assert counts.remaining == 6  # 3 + 2 + 1

    def test_retry_field_explicit(self) -> None:
        counts = TaskCounts(total=5, open=2, in_progress=1, retry=1, closed=1)
        assert counts.retry == 1


# ==============================================================================
# JSONL Backend Tests
# ==============================================================================


class TestJsonlGetReadyTasksFiltering:
    """Test get_ready_tasks excludes epics/gates and includes RETRY."""

    @pytest.fixture
    def backend_with_tasks(self, tmp_path: Path):
        """Create a JSONL backend with diverse task types."""
        from cub.core.tasks.jsonl import JsonlBackend

        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        tasks = [
            {
                "id": "t-1",
                "title": "Open task",
                "status": "open",
                "issue_type": "task",
                "priority": "P2",
            },
            {
                "id": "t-2",
                "title": "Retry task",
                "status": "retry",
                "issue_type": "task",
                "priority": "P1",
            },
            {
                "id": "t-3",
                "title": "Epic open",
                "status": "open",
                "issue_type": "epic",
                "priority": "P0",
            },
            {
                "id": "t-4",
                "title": "Gate open",
                "status": "open",
                "issue_type": "gate",
                "priority": "P0",
            },
            {"id": "t-5", "title": "In progress", "status": "in_progress", "issue_type": "task"},
            {"id": "t-6", "title": "Closed task", "status": "closed", "issue_type": "task"},
            {
                "id": "t-7",
                "title": "Open P0",
                "status": "open",
                "issue_type": "task",
                "priority": "P0",
            },
            {
                "id": "t-8",
                "title": "Retry P0",
                "status": "retry",
                "issue_type": "task",
                "priority": "P0",
            },
        ]
        lines = [json.dumps(t) for t in tasks]
        tasks_file.write_text("\n".join(lines) + "\n")

        return JsonlBackend(project_dir=tmp_path)

    def test_get_ready_tasks_excludes_epics(self, backend_with_tasks) -> None:
        ready = backend_with_tasks.get_ready_tasks()
        ready_ids = {t.id for t in ready}
        assert "t-3" not in ready_ids  # epic

    def test_get_ready_tasks_excludes_gates(self, backend_with_tasks) -> None:
        ready = backend_with_tasks.get_ready_tasks()
        ready_ids = {t.id for t in ready}
        assert "t-4" not in ready_ids  # gate

    def test_get_ready_tasks_includes_retry(self, backend_with_tasks) -> None:
        ready = backend_with_tasks.get_ready_tasks()
        ready_ids = {t.id for t in ready}
        assert "t-2" in ready_ids  # retry task
        assert "t-8" in ready_ids  # retry P0 task

    def test_get_ready_tasks_excludes_in_progress(self, backend_with_tasks) -> None:
        ready = backend_with_tasks.get_ready_tasks()
        ready_ids = {t.id for t in ready}
        assert "t-5" not in ready_ids

    def test_get_ready_tasks_excludes_closed(self, backend_with_tasks) -> None:
        ready = backend_with_tasks.get_ready_tasks()
        ready_ids = {t.id for t in ready}
        assert "t-6" not in ready_ids

    def test_get_ready_tasks_open_before_retry(self, backend_with_tasks) -> None:
        """OPEN tasks sort before RETRY at same priority level."""
        ready = backend_with_tasks.get_ready_tasks()
        # At P0: t-7 (open) should come before t-8 (retry)
        p0_tasks = [t for t in ready if t.priority == TaskPriority.P0]
        assert len(p0_tasks) == 2
        assert p0_tasks[0].id == "t-7"  # open
        assert p0_tasks[1].id == "t-8"  # retry

    def test_get_ready_tasks_sorted_by_priority(self, backend_with_tasks) -> None:
        """Higher priority first, then OPEN before RETRY."""
        ready = backend_with_tasks.get_ready_tasks()
        # Expected order: t-7 (P0 open), t-8 (P0 retry), t-2 (P1 retry), t-1 (P2 open)
        assert ready[0].id == "t-7"
        assert ready[1].id == "t-8"
        assert ready[2].id == "t-2"
        assert ready[3].id == "t-1"


class TestJsonlGetTaskCountsRetry:
    """Test get_task_counts includes retry count."""

    def test_task_counts_includes_retry(self, tmp_path: Path) -> None:
        from cub.core.tasks.jsonl import JsonlBackend

        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        tasks = [
            {"id": "t-1", "title": "Open", "status": "open"},
            {"id": "t-2", "title": "Retry", "status": "retry"},
            {"id": "t-3", "title": "Retry 2", "status": "retry"},
            {"id": "t-4", "title": "Closed", "status": "closed"},
            {"id": "t-5", "title": "In progress", "status": "in_progress"},
        ]
        tasks_file.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")

        backend = JsonlBackend(project_dir=tmp_path)
        counts = backend.get_task_counts()

        assert counts.total == 5
        assert counts.open == 1
        assert counts.retry == 2
        assert counts.in_progress == 1
        assert counts.closed == 1
        assert counts.remaining == 4  # 1 + 1 + 2


class TestTryCloseEpicBlocksOnRetry:
    """Test try_close_epic blocks when child tasks are in RETRY state."""

    def test_try_close_epic_blocks_on_retry(self, tmp_path: Path) -> None:
        from cub.core.tasks.jsonl import JsonlBackend

        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        tasks = [
            {"id": "epic-1", "title": "Epic", "status": "open", "issue_type": "epic"},
            {"id": "t-1", "title": "Done", "status": "closed", "parent": "epic-1"},
            {"id": "t-2", "title": "Retrying", "status": "retry", "parent": "epic-1"},
        ]
        tasks_file.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")

        backend = JsonlBackend(project_dir=tmp_path)
        closed, message = backend.try_close_epic("epic-1")

        assert closed is False
        assert "retry" in message.lower()


# ==============================================================================
# Run Loop Tests
# ==============================================================================


def _make_mock_task(
    task_id: str = "test-001",
    title: str = "Test task",
    status: str = "open",
    task_type: str = "task",
) -> MagicMock:
    """Create a mock Task."""
    task = MagicMock()
    task.id = task_id
    task.title = title
    task.status = TaskStatus(status)
    task.type = TaskType(task_type)
    task.priority = TaskPriority.P2
    task.description = "Test"
    task.labels = []
    task.model_label = None
    task.parent = None
    return task


def _make_loop(
    tmp_path: Path,
    mock_task_backend: MagicMock,
    mock_harness_backend: MagicMock,
    **config_overrides: object,
) -> RunLoop:
    """Create a RunLoop with mocked dependencies."""
    from cub.core.run.loop import RunLoop
    from cub.core.run.models import RunConfig

    defaults: dict[str, object] = {
        "once": True,
        "harness_name": "test-harness",
        "debug": False,
        "max_iterations": 1,
        "on_task_failure": "stop",
        "circuit_breaker_enabled": False,
        "ledger_enabled": False,
        "hooks_enabled": False,
        "sync_enabled": False,
        "project_dir": str(tmp_path),
    }
    defaults.update(config_overrides)

    config = RunConfig(**defaults)  # type: ignore[arg-type]

    with patch("cub.core.run.loop.generate_system_prompt", return_value="system prompt"):
        return RunLoop(
            config=config,
            task_backend=mock_task_backend,
            harness_backend=mock_harness_backend,
        )


class TestSelectTaskRejectsEpic:
    """Test _select_task returns None for epic/gate types."""

    def test_select_task_rejects_epic(self, tmp_path: Path) -> None:
        task_backend = MagicMock()
        epic = _make_mock_task(task_id="epic-1", task_type="epic")
        task_backend.get_task.return_value = epic

        harness_backend = MagicMock()
        loop = _make_loop(tmp_path, task_backend, harness_backend, task_id="epic-1")

        result = loop._select_task()
        assert result is None

    def test_select_task_rejects_gate(self, tmp_path: Path) -> None:
        task_backend = MagicMock()
        gate = _make_mock_task(task_id="gate-1", task_type="gate")
        task_backend.get_task.return_value = gate

        harness_backend = MagicMock()
        loop = _make_loop(tmp_path, task_backend, harness_backend, task_id="gate-1")

        result = loop._select_task()
        assert result is None

    def test_select_task_allows_regular_task(self, tmp_path: Path) -> None:
        task_backend = MagicMock()
        task = _make_mock_task(task_id="t-1", task_type="task")
        task_backend.get_task.return_value = task

        harness_backend = MagicMock()
        loop = _make_loop(tmp_path, task_backend, harness_backend, task_id="t-1")

        result = loop._select_task()
        assert result is not None
        assert result.id == "t-1"


class TestFailurePathsSetRetry:
    """Test that failure paths set task status to RETRY."""

    @pytest.fixture
    def task_backend(self) -> MagicMock:
        backend = MagicMock()
        backend.backend_name = "test"
        backend.get_task_counts.return_value = MagicMock(
            total=1, open=1, in_progress=0, closed=0, remaining=1
        )
        task = _make_mock_task()
        backend.get_ready_tasks.return_value = [task]
        backend.get_task.return_value = task
        return backend

    @pytest.fixture
    def harness_backend(self) -> MagicMock:
        backend = MagicMock()
        backend.capabilities = MagicMock()
        backend.capabilities.streaming = False
        return backend

    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_circuit_breaker_sets_retry(
        self,
        mock_task_prompt: MagicMock,
        tmp_path: Path,
        task_backend: MagicMock,
        harness_backend: MagicMock,
    ) -> None:
        """Verify update_task called with RETRY on circuit breaker trip."""
        from cub.core.circuit_breaker import CircuitBreakerTrippedError

        loop = _make_loop(tmp_path, task_backend, harness_backend)

        # Simulate circuit breaker trip during _invoke_harness
        with patch.object(
            loop,
            "_invoke_harness",
            side_effect=CircuitBreakerTrippedError(30),
        ):
            list(loop.execute())

        # Verify update_task was called with RETRY status
        found_retry = any(
            call == (("test-001",), {"status": TaskStatus.RETRY})
            for call in task_backend.update_task.call_args_list
        )
        assert found_retry, (
            f"Expected update_task('test-001', status=RETRY), "
            f"got calls: {task_backend.update_task.call_args_list}"
        )

    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_harness_error_sets_retry(
        self,
        mock_task_prompt: MagicMock,
        tmp_path: Path,
        task_backend: MagicMock,
        harness_backend: MagicMock,
    ) -> None:
        """Verify update_task called with RETRY on harness error."""
        loop = _make_loop(tmp_path, task_backend, harness_backend)

        with patch.object(
            loop,
            "_invoke_harness",
            side_effect=RuntimeError("Harness crashed"),
        ):
            list(loop.execute())

        found_retry = any(
            call == (("test-001",), {"status": TaskStatus.RETRY})
            for call in task_backend.update_task.call_args_list
        )
        assert found_retry, f"Expected RETRY call, got: {task_backend.update_task.call_args_list}"

    @patch("cub.core.run.loop.generate_task_prompt", return_value="task prompt")
    def test_task_failure_sets_retry(
        self,
        mock_task_prompt: MagicMock,
        tmp_path: Path,
        task_backend: MagicMock,
        harness_backend: MagicMock,
    ) -> None:
        """Verify update_task called with RETRY when harness returns success=False."""
        result = MagicMock()
        result.success = False
        result.duration_seconds = 5.0
        result.exit_code = 1
        result.error = "Tests failed"
        result.usage = MagicMock()
        result.usage.total_tokens = 100
        result.usage.cost_usd = 0.01
        result.usage.input_tokens = 50
        result.usage.output_tokens = 50
        result.usage.cache_read_tokens = 0
        result.usage.cache_creation_tokens = 0

        loop = _make_loop(tmp_path, task_backend, harness_backend)

        with patch.object(loop, "_invoke_harness", return_value=result):
            list(loop.execute())

        found_retry = any(
            call == (("test-001",), {"status": TaskStatus.RETRY})
            for call in task_backend.update_task.call_args_list
        )
        assert found_retry, f"Expected RETRY call, got: {task_backend.update_task.call_args_list}"


# ==============================================================================
# Backward Compatibility
# ==============================================================================


class TestBackwardCompatibility:
    """Test that existing JSONL files without 'retry' status still parse."""

    def test_legacy_jsonl_without_retry(self, tmp_path: Path) -> None:
        from cub.core.tasks.jsonl import JsonlBackend

        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        # Legacy format: only open/in_progress/closed
        tasks = [
            {"id": "t-1", "title": "Open", "status": "open"},
            {"id": "t-2", "title": "WIP", "status": "in_progress"},
            {"id": "t-3", "title": "Done", "status": "closed"},
        ]
        tasks_file.write_text("\n".join(json.dumps(t) for t in tasks) + "\n")

        backend = JsonlBackend(project_dir=tmp_path)

        # Should load fine
        all_tasks = backend.list_tasks()
        assert len(all_tasks) == 3

        # Counts should work with 0 retry
        counts = backend.get_task_counts()
        assert counts.retry == 0
        assert counts.remaining == 2  # open + in_progress

        # Ready tasks should work
        ready = backend.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t-1"
