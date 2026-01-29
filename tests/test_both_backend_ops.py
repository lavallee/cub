"""Tests for BothBackend operation delegation and comparison methods."""

from datetime import datetime
from pathlib import Path

import pytest

from cub.core.tasks.both import BothBackend, TaskDivergence
from cub.core.tasks.models import Task, TaskCounts, TaskPriority, TaskStatus, TaskType


def _make_task(
    task_id: str = "test-001",
    title: str = "Test Task",
    status: TaskStatus = TaskStatus.OPEN,
    priority: TaskPriority = TaskPriority.P2,
    description: str = "",
    assignee: str | None = None,
    labels: list[str] | None = None,
    depends_on: list[str] | None = None,
    parent: str | None = None,
) -> Task:
    return Task(
        id=task_id,
        title=title,
        type=TaskType.TASK,
        priority=priority,
        status=status,
        description=description,
        assignee=assignee,
        labels=labels or [],
        depends_on=depends_on or [],
        parent=parent,
    )


class MockBackend:
    """Configurable mock backend for testing BothBackend."""

    def __init__(
        self,
        name: str = "mock",
        tasks: list[Task] | None = None,
        counts: TaskCounts | None = None,
    ):
        self._name = name
        self._tasks = tasks or []
        self._counts = counts or TaskCounts(total=0, open=0, in_progress=0, closed=0)
        self.calls: list[tuple[str, tuple, dict]] = []

    @property
    def backend_name(self) -> str:
        return self._name

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        parent: str | None = None,
        label: str | None = None,
    ) -> list[Task]:
        self.calls.append(("list_tasks", (), {"status": status, "parent": parent, "label": label}))
        return self._tasks

    def get_task(self, task_id: str) -> Task | None:
        self.calls.append(("get_task", (task_id,), {}))
        for t in self._tasks:
            if t.id == task_id:
                return t
        return None

    def get_ready_tasks(self, parent: str | None = None, label: str | None = None) -> list[Task]:
        self.calls.append(("get_ready_tasks", (), {"parent": parent, "label": label}))
        return [t for t in self._tasks if t.status == TaskStatus.OPEN]

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        assignee: str | None = None,
        description: str | None = None,
        labels: list[str] | None = None,
    ) -> Task:
        self.calls.append(("update_task", (task_id,), {}))
        for t in self._tasks:
            if t.id == task_id:
                return t
        raise ValueError(f"Task {task_id} not found")

    def close_task(self, task_id: str, reason: str | None = None) -> Task:
        self.calls.append(("close_task", (task_id,), {"reason": reason}))
        for t in self._tasks:
            if t.id == task_id:
                return t
        raise ValueError(f"Task {task_id} not found")

    def create_task(
        self,
        title: str = "",
        description: str = "",
        task_type: str = "task",
        priority: int = 2,
        labels: list[str] | None = None,
        depends_on: list[str] | None = None,
        parent: str | None = None,
    ) -> Task:
        self.calls.append(("create_task", (), {"title": title}))
        return _make_task(title=title, description=description)

    def add_task_note(self, task_id: str, note: str) -> Task:
        self.calls.append(("add_task_note", (task_id, note), {}))
        for t in self._tasks:
            if t.id == task_id:
                return t
        raise ValueError(f"Task {task_id} not found")

    def import_tasks(self, tasks: list[Task]) -> list[Task]:
        self.calls.append(("import_tasks", (tasks,), {}))
        return tasks

    def get_task_counts(self) -> TaskCounts:
        self.calls.append(("get_task_counts", (), {}))
        return self._counts

    def get_agent_instructions(self, task_id: str) -> str:
        self.calls.append(("get_agent_instructions", (task_id,), {}))
        return f"Instructions for {task_id}"

    def bind_branch(self, epic_id: str, branch_name: str, base_branch: str = "main") -> bool:
        self.calls.append(("bind_branch", (epic_id, branch_name), {}))
        return True

    def try_close_epic(self, epic_id: str) -> tuple[bool, str]:
        self.calls.append(("try_close_epic", (epic_id,), {}))
        return (True, "All tasks complete")


@pytest.fixture
def task1() -> Task:
    return _make_task("test-001", "Task One")


@pytest.fixture
def task2() -> Task:
    return _make_task("test-002", "Task Two")


@pytest.fixture
def both(tmp_path: Path, task1: Task, task2: Task) -> BothBackend:
    primary = MockBackend("primary", [task1, task2])
    secondary = MockBackend("secondary", [task1, task2])
    return BothBackend(primary, secondary, divergence_log=tmp_path / ".cub" / "divergence.log")


class TestCompareTasks:
    """Tests for _compare_tasks helper."""

    def test_both_none_returns_none(self, both: BothBackend) -> None:
        assert both._compare_tasks(None, None) is None

    def test_primary_none(self, both: BothBackend, task1: Task) -> None:
        result = both._compare_tasks(None, task1)
        assert result is not None
        assert "Primary task is None" in result

    def test_secondary_none(self, both: BothBackend, task1: Task) -> None:
        result = both._compare_tasks(task1, None)
        assert result is not None
        assert "Secondary task is None" in result

    def test_identical_tasks(self, both: BothBackend, task1: Task) -> None:
        assert both._compare_tasks(task1, task1) is None

    def test_different_status(self, both: BothBackend) -> None:
        t1 = _make_task(status=TaskStatus.OPEN)
        t2 = _make_task(status=TaskStatus.CLOSED)
        result = both._compare_tasks(t1, t2)
        assert "status" in result

    def test_different_title(self, both: BothBackend) -> None:
        t1 = _make_task(title="Alpha")
        t2 = _make_task(title="Beta")
        result = both._compare_tasks(t1, t2)
        assert "title" in result

    def test_different_description_length(self, both: BothBackend) -> None:
        t1 = _make_task(description="short")
        t2 = _make_task(description="a much longer description here")
        result = both._compare_tasks(t1, t2)
        assert "description" in result
        assert "chars" in result

    def test_different_labels(self, both: BothBackend) -> None:
        t1 = _make_task(labels=["alpha"])
        t2 = _make_task(labels=["beta"])
        result = both._compare_tasks(t1, t2)
        assert "labels" in result

    def test_same_labels_different_order_no_divergence(self, both: BothBackend) -> None:
        """Labels in different order should NOT be flagged as a divergence."""
        t1 = _make_task(labels=["bug", "core", "phase-1"])
        t2 = _make_task(labels=["core", "phase-1", "bug"])
        result = both._compare_tasks(t1, t2)
        assert result is None

    def test_same_labels_reversed_order_no_divergence(self, both: BothBackend) -> None:
        """Reversed label order should NOT be flagged as a divergence."""
        t1 = _make_task(labels=["alpha", "beta", "gamma"])
        t2 = _make_task(labels=["gamma", "beta", "alpha"])
        result = both._compare_tasks(t1, t2)
        assert result is None

    def test_same_labels_two_elements_swapped_no_divergence(self, both: BothBackend) -> None:
        """Two-element label lists in swapped order should NOT be flagged."""
        t1 = _make_task(labels=["setup", "core"])
        t2 = _make_task(labels=["core", "setup"])
        result = both._compare_tasks(t1, t2)
        assert result is None

    def test_labels_subset_detected_as_divergence(self, both: BothBackend) -> None:
        """A subset of labels should be detected as a real divergence."""
        t1 = _make_task(labels=["alpha", "beta", "gamma"])
        t2 = _make_task(labels=["alpha", "beta"])
        result = both._compare_tasks(t1, t2)
        assert result is not None
        assert "labels" in result

    def test_labels_empty_vs_nonempty_detected_as_divergence(self, both: BothBackend) -> None:
        """Empty labels vs non-empty labels should be a real divergence."""
        t1 = _make_task(labels=[])
        t2 = _make_task(labels=["bug"])
        result = both._compare_tasks(t1, t2)
        assert result is not None
        assert "labels" in result

    def test_labels_both_empty_no_divergence(self, both: BothBackend) -> None:
        """Both empty label lists should NOT be flagged."""
        t1 = _make_task(labels=[])
        t2 = _make_task(labels=[])
        result = both._compare_tasks(t1, t2)
        assert result is None

    def test_different_depends_on(self, both: BothBackend) -> None:
        t1 = _make_task(depends_on=["dep-1"])
        t2 = _make_task(depends_on=["dep-2"])
        result = both._compare_tasks(t1, t2)
        assert "depends_on" in result

    def test_different_parent(self, both: BothBackend) -> None:
        t1 = _make_task(parent="epic-1")
        t2 = _make_task(parent="epic-2")
        result = both._compare_tasks(t1, t2)
        assert "parent" in result

    def test_different_priority(self, both: BothBackend) -> None:
        t1 = _make_task(priority=TaskPriority.P0)
        t2 = _make_task(priority=TaskPriority.P4)
        result = both._compare_tasks(t1, t2)
        assert "priority" in result

    def test_multiple_differences(self, both: BothBackend) -> None:
        t1 = _make_task(title="A", status=TaskStatus.OPEN)
        t2 = _make_task(title="B", status=TaskStatus.CLOSED)
        result = both._compare_tasks(t1, t2)
        assert "title" in result
        assert "status" in result


class TestCompareTaskLists:
    """Tests for _compare_task_lists helper."""

    def test_identical_lists(self, both: BothBackend, task1: Task, task2: Task) -> None:
        assert both._compare_task_lists([task1, task2], [task1, task2]) is None

    def test_different_lengths(self, both: BothBackend, task1: Task, task2: Task) -> None:
        result = both._compare_task_lists([task1, task2], [task1])
        assert "List length mismatch" in result

    def test_different_task_content(self, both: BothBackend) -> None:
        t1 = _make_task("t-1", "Alpha")
        t2 = _make_task("t-1", "Beta")
        result = both._compare_task_lists([t1], [t2])
        assert "title" in result


class TestCompareTaskCounts:
    """Tests for _compare_task_counts helper."""

    def test_identical_counts(self, both: BothBackend) -> None:
        c = TaskCounts(total=10, open=5, in_progress=3, closed=2)
        assert both._compare_task_counts(c, c) is None

    def test_different_total(self, both: BothBackend) -> None:
        c1 = TaskCounts(total=10, open=5, in_progress=3, closed=2)
        c2 = TaskCounts(total=11, open=5, in_progress=3, closed=3)
        result = both._compare_task_counts(c1, c2)
        assert "total" in result

    def test_different_open(self, both: BothBackend) -> None:
        c1 = TaskCounts(total=10, open=5, in_progress=3, closed=2)
        c2 = TaskCounts(total=10, open=4, in_progress=4, closed=2)
        result = both._compare_task_counts(c1, c2)
        assert "open" in result

    def test_multiple_differences(self, both: BothBackend) -> None:
        c1 = TaskCounts(total=10, open=5, in_progress=3, closed=2)
        c2 = TaskCounts(total=20, open=10, in_progress=6, closed=4)
        result = both._compare_task_counts(c1, c2)
        assert "total" in result
        assert "open" in result


class TestBothBackendOperations:
    """Tests for delegated operations."""

    def test_backend_name(self, both: BothBackend) -> None:
        assert both.backend_name == "both(primary+secondary)"

    def test_list_tasks_delegates_to_both(self, both: BothBackend) -> None:
        result = both.list_tasks()
        assert len(result) == 2
        assert any(c[0] == "list_tasks" for c in both.primary.calls)
        assert any(c[0] == "list_tasks" for c in both.secondary.calls)

    def test_list_tasks_returns_primary_result(self, tmp_path: Path) -> None:
        t1 = _make_task("t-1", "Primary Only")
        t2 = _make_task("t-2", "Secondary Only")
        primary = MockBackend("primary", [t1])
        secondary = MockBackend("secondary", [t2])
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")
        result = b.list_tasks()
        assert len(result) == 1
        assert result[0].title == "Primary Only"

    def test_get_task_delegates(self, both: BothBackend) -> None:
        result = both.get_task("test-001")
        assert result is not None
        assert result.id == "test-001"

    def test_get_ready_tasks_delegates(self, both: BothBackend) -> None:
        result = both.get_ready_tasks()
        assert isinstance(result, list)

    def test_update_task_delegates(self, both: BothBackend) -> None:
        result = both.update_task("test-001", status=TaskStatus.IN_PROGRESS)
        assert result.id == "test-001"
        assert any(c[0] == "update_task" for c in both.primary.calls)
        assert any(c[0] == "update_task" for c in both.secondary.calls)

    def test_close_task_delegates(self, both: BothBackend) -> None:
        result = both.close_task("test-001", reason="done")
        assert result.id == "test-001"

    def test_create_task_delegates(self, both: BothBackend) -> None:
        result = both.create_task(title="New Task", description="desc")
        assert result.title == "New Task"

    def test_add_task_note_delegates(self, both: BothBackend) -> None:
        result = both.add_task_note("test-001", "a note")
        assert result.id == "test-001"

    def test_import_tasks_delegates(self, both: BothBackend, task1: Task) -> None:
        result = both.import_tasks([task1])
        assert len(result) == 1

    def test_get_task_counts_delegates(self, tmp_path: Path) -> None:
        counts = TaskCounts(total=10, open=5, in_progress=3, closed=2)
        primary = MockBackend("primary", counts=counts)
        secondary = MockBackend("secondary", counts=counts)
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")
        result = b.get_task_counts()
        assert result.total == 10

    def test_get_agent_instructions_delegates_primary_only(self, both: BothBackend) -> None:
        result = both.get_agent_instructions("test-001")
        assert "test-001" in result
        # Should only call primary
        assert any(c[0] == "get_agent_instructions" for c in both.primary.calls)

    def test_bind_branch_delegates(self, both: BothBackend) -> None:
        result = both.bind_branch("epic-1", "feature/test")
        assert result is True

    def test_try_close_epic_delegates(self, both: BothBackend) -> None:
        closed, msg = both.try_close_epic("epic-1")
        assert closed is True


class TestSecondaryBackendErrors:
    """Tests for error handling when secondary backend fails."""

    def test_update_task_secondary_failure(self, tmp_path: Path) -> None:
        task = _make_task()
        primary = MockBackend("primary", [task])

        class FailingBackend(MockBackend):
            def update_task(self, task_id, **kwargs):
                raise RuntimeError("secondary broke")

        secondary = FailingBackend("secondary", [task])
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")

        # Should not raise; returns primary result
        result = b.update_task("test-001")
        assert result.id == "test-001"

    def test_close_task_secondary_failure(self, tmp_path: Path) -> None:
        task = _make_task()
        primary = MockBackend("primary", [task])

        class FailingBackend(MockBackend):
            def close_task(self, task_id, reason=None):
                raise RuntimeError("secondary broke")

        secondary = FailingBackend("secondary", [task])
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")

        result = b.close_task("test-001")
        assert result.id == "test-001"

    def test_create_task_secondary_failure(self, tmp_path: Path) -> None:
        primary = MockBackend("primary")

        class FailingBackend(MockBackend):
            def create_task(self, **kwargs):
                raise RuntimeError("secondary broke")

        secondary = FailingBackend("secondary")
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")

        result = b.create_task(title="Test")
        assert result.title == "Test"

    def test_add_task_note_secondary_failure(self, tmp_path: Path) -> None:
        task = _make_task()
        primary = MockBackend("primary", [task])

        class FailingBackend(MockBackend):
            def add_task_note(self, task_id, note):
                raise RuntimeError("secondary broke")

        secondary = FailingBackend("secondary", [task])
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")

        result = b.add_task_note("test-001", "note")
        assert result.id == "test-001"

    def test_import_tasks_secondary_failure(self, tmp_path: Path) -> None:
        task = _make_task()
        primary = MockBackend("primary", [task])

        class FailingBackend(MockBackend):
            def import_tasks(self, tasks):
                raise RuntimeError("secondary broke")

        secondary = FailingBackend("secondary")
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")

        result = b.import_tasks([task])
        assert len(result) == 1

    def test_bind_branch_secondary_failure(self, tmp_path: Path) -> None:
        primary = MockBackend("primary")

        class FailingBackend(MockBackend):
            def bind_branch(self, epic_id, branch_name, base_branch="main"):
                raise RuntimeError("secondary broke")

        secondary = FailingBackend("secondary")
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")

        result = b.bind_branch("epic-1", "feature/test")
        assert result is True

    def test_try_close_epic_secondary_failure(self, tmp_path: Path) -> None:
        primary = MockBackend("primary")

        class FailingBackend(MockBackend):
            def try_close_epic(self, epic_id):
                raise RuntimeError("secondary broke")

        secondary = FailingBackend("secondary")
        b = BothBackend(primary, secondary, divergence_log=tmp_path / "d.log")

        closed, msg = b.try_close_epic("epic-1")
        assert closed is True


class TestDivergenceLogging:
    """Tests for divergence detection and logging during operations."""

    def test_list_tasks_logs_divergence(self, tmp_path: Path) -> None:
        t1 = _make_task("t-1", "Same")
        t2 = _make_task("t-1", "Different")
        primary = MockBackend("primary", [t1])
        secondary = MockBackend("secondary", [t2])
        log_path = tmp_path / "d.log"
        b = BothBackend(primary, secondary, divergence_log=log_path)

        b.list_tasks()
        assert log_path.exists()

    def test_get_task_counts_logs_divergence(self, tmp_path: Path) -> None:
        c1 = TaskCounts(total=10, open=5, in_progress=3, closed=2)
        c2 = TaskCounts(total=20, open=10, in_progress=6, closed=4)
        primary = MockBackend("primary", counts=c1)
        secondary = MockBackend("secondary", counts=c2)
        log_path = tmp_path / "d.log"
        b = BothBackend(primary, secondary, divergence_log=log_path)

        b.get_task_counts()
        assert log_path.exists()


class TestTaskDivergence:
    """Tests for TaskDivergence dataclass."""

    def test_to_dict(self) -> None:
        d = TaskDivergence(
            timestamp=datetime(2026, 1, 27, 12, 0, 0),
            operation="get_task",
            task_id="test-001",
            primary_result="primary",
            secondary_result="secondary",
            difference_summary="things differ",
        )
        result = d.to_dict()
        assert result["operation"] == "get_task"
        assert result["task_id"] == "test-001"
        assert result["difference_summary"] == "things differ"

    def test_serialize_task(self) -> None:
        task = _make_task()
        d = TaskDivergence(
            timestamp=datetime(2026, 1, 27),
            operation="test",
            task_id=None,
            primary_result=task,
            secondary_result=None,
            difference_summary="test",
        )
        result = d.to_dict()
        assert isinstance(result["primary_result"], dict)
        assert result["primary_result"]["id"] == "test-001"

    def test_serialize_task_list(self) -> None:
        tasks = [_make_task("t-1"), _make_task("t-2")]
        d = TaskDivergence(
            timestamp=datetime(2026, 1, 27),
            operation="test",
            task_id=None,
            primary_result=tasks,
            secondary_result=None,
            difference_summary="test",
        )
        result = d.to_dict()
        assert isinstance(result["primary_result"], list)
        assert len(result["primary_result"]) == 2

    def test_serialize_task_counts(self) -> None:
        counts = TaskCounts(total=10, open=5, in_progress=3, closed=2)
        d = TaskDivergence(
            timestamp=datetime(2026, 1, 27),
            operation="test",
            task_id=None,
            primary_result=counts,
            secondary_result=None,
            difference_summary="test",
        )
        result = d.to_dict()
        assert result["primary_result"]["total"] == 10

    def test_serialize_bool(self) -> None:
        d = TaskDivergence(
            timestamp=datetime(2026, 1, 27),
            operation="test",
            task_id=None,
            primary_result=True,
            secondary_result=False,
            difference_summary="test",
        )
        result = d.to_dict()
        assert result["primary_result"] is True

    def test_serialize_tuple(self) -> None:
        d = TaskDivergence(
            timestamp=datetime(2026, 1, 27),
            operation="test",
            task_id=None,
            primary_result=(True, "msg"),
            secondary_result=None,
            difference_summary="test",
        )
        result = d.to_dict()
        assert result["primary_result"] == [True, "msg"]
