"""
Tests for ParallelRunner.

Tests parallel task execution using git worktrees.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType
from cub.core.worktree.parallel import (
    ParallelRunner,
    ParallelRunResult,
    WorkerResult,
    get_independent_tasks,
)


@pytest.fixture
def mock_worktree_manager():
    """Provide a mock WorktreeManager."""
    with patch("cub.core.worktree.parallel.WorktreeManager") as mock:
        manager = MagicMock()
        mock.return_value = manager

        # Mock create() to return a worktree
        def create_worktree(task_id, create_branch=True):
            worktree = MagicMock()
            worktree.path = Path(f"/tmp/worktrees/{task_id}")
            worktree.branch = task_id if create_branch else None
            worktree.commit = "abc123"
            return worktree

        manager.create.side_effect = create_worktree
        manager.list.return_value = []
        manager.remove.return_value = None

        yield manager


@pytest.fixture
def sample_tasks():
    """Provide sample tasks for testing."""
    return [
        Task(
            id="task-001",
            title="First task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            depends_on=[],
        ),
        Task(
            id="task-002",
            title="Second task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            depends_on=[],
        ),
        Task(
            id="task-003",
            title="Third task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P3,
            type=TaskType.TASK,
            depends_on=[],
        ),
    ]


@pytest.fixture
def dependent_tasks():
    """Provide tasks with dependencies for testing."""
    return [
        Task(
            id="task-001",
            title="First task",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            depends_on=[],
        ),
        Task(
            id="task-002",
            title="Second task (depends on first)",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P2,
            type=TaskType.TASK,
            depends_on=["task-001"],
        ),
        Task(
            id="task-003",
            title="Third task (independent)",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P3,
            type=TaskType.TASK,
            depends_on=[],
        ),
    ]


@pytest.fixture
def mock_task_backend(sample_tasks):
    """Provide a mock TaskBackend."""
    backend = MagicMock()
    backend.get_ready_tasks.return_value = sample_tasks
    backend.get_task.side_effect = lambda id: next((t for t in sample_tasks if t.id == id), None)
    return backend


class TestWorkerResult:
    """Test WorkerResult dataclass."""

    def test_worker_result_success(self):
        """Test creating a successful worker result."""
        result = WorkerResult(
            task_id="task-001",
            task_title="Test task",
            success=True,
            exit_code=0,
            duration_seconds=10.5,
            worktree_path=Path("/tmp/worktree"),
            tokens_used=1000,
            cost_usd=0.01,
        )

        assert result.task_id == "task-001"
        assert result.success is True
        assert result.exit_code == 0
        assert result.error is None

    def test_worker_result_failure(self):
        """Test creating a failed worker result."""
        result = WorkerResult(
            task_id="task-002",
            task_title="Failed task",
            success=False,
            exit_code=1,
            duration_seconds=5.0,
            worktree_path=Path("/tmp/worktree"),
            error="Task execution failed",
        )

        assert result.success is False
        assert result.exit_code == 1
        assert result.error == "Task execution failed"


class TestParallelRunResult:
    """Test ParallelRunResult dataclass."""

    def test_empty_result(self):
        """Test empty parallel run result."""
        result = ParallelRunResult()

        assert result.workers == []
        assert result.total_duration == 0.0
        assert result.tasks_completed == 0
        assert result.tasks_failed == 0
        assert result.total_tokens == 0
        assert result.total_cost == 0.0

    def test_result_with_workers(self):
        """Test parallel run result with worker results."""
        result = ParallelRunResult(
            workers=[
                WorkerResult(
                    task_id="task-001",
                    task_title="Task 1",
                    success=True,
                    exit_code=0,
                    duration_seconds=10.0,
                    worktree_path=Path("/tmp/w1"),
                    tokens_used=1000,
                ),
                WorkerResult(
                    task_id="task-002",
                    task_title="Task 2",
                    success=False,
                    exit_code=1,
                    duration_seconds=5.0,
                    worktree_path=Path("/tmp/w2"),
                    error="Failed",
                ),
            ],
            total_duration=15.0,
            tasks_completed=1,
            tasks_failed=1,
            total_tokens=1000,
            total_cost=0.01,
        )

        assert len(result.workers) == 2
        assert result.tasks_completed == 1
        assert result.tasks_failed == 1


class TestParallelRunnerInit:
    """Test ParallelRunner initialization."""

    def test_init_default(self, mock_worktree_manager, tmp_path):
        """Test default initialization."""
        runner = ParallelRunner(tmp_path)

        assert runner.project_dir == tmp_path
        assert runner.harness is None
        assert runner.model is None
        assert runner.debug is False
        assert runner.stream is False

    def test_init_with_options(self, mock_worktree_manager, tmp_path):
        """Test initialization with options."""
        runner = ParallelRunner(
            tmp_path,
            harness="claude",
            model="sonnet",
            debug=True,
            stream=True,
        )

        assert runner.harness == "claude"
        assert runner.model == "sonnet"
        assert runner.debug is True
        assert runner.stream is True


class TestFindIndependentTasks:
    """Test finding independent tasks."""

    def test_find_independent_all_independent(
        self, mock_worktree_manager, sample_tasks, mock_task_backend, tmp_path
    ):
        """Test finding tasks when all are independent."""
        runner = ParallelRunner(tmp_path)

        tasks = runner.find_independent_tasks(mock_task_backend, count=3)

        assert len(tasks) == 3
        assert tasks[0].id == "task-001"
        assert tasks[1].id == "task-002"
        assert tasks[2].id == "task-003"

    def test_find_independent_with_dependencies(
        self, mock_worktree_manager, dependent_tasks, tmp_path
    ):
        """Test finding tasks excludes dependent tasks."""
        backend = MagicMock()
        backend.get_ready_tasks.return_value = dependent_tasks

        runner = ParallelRunner(tmp_path)

        tasks = runner.find_independent_tasks(backend, count=3)

        # task-002 depends on task-001, so only task-001 and task-003 are independent
        assert len(tasks) == 2
        task_ids = [t.id for t in tasks]
        assert "task-001" in task_ids
        assert "task-003" in task_ids
        assert "task-002" not in task_ids

    def test_find_independent_respects_count(
        self, mock_worktree_manager, sample_tasks, mock_task_backend, tmp_path
    ):
        """Test finding tasks respects count limit."""
        runner = ParallelRunner(tmp_path)

        tasks = runner.find_independent_tasks(mock_task_backend, count=2)

        assert len(tasks) == 2

    def test_find_independent_empty(self, mock_worktree_manager, tmp_path):
        """Test finding tasks with no ready tasks."""
        backend = MagicMock()
        backend.get_ready_tasks.return_value = []

        runner = ParallelRunner(tmp_path)

        tasks = runner.find_independent_tasks(backend, count=3)

        assert len(tasks) == 0

    def test_find_independent_with_filters(self, mock_worktree_manager, sample_tasks, tmp_path):
        """Test finding tasks with epic and label filters."""
        backend = MagicMock()
        backend.get_ready_tasks.return_value = sample_tasks

        runner = ParallelRunner(tmp_path)

        runner.find_independent_tasks(backend, count=3, epic="my-epic", label="urgent")

        backend.get_ready_tasks.assert_called_once_with(parent="my-epic", label="urgent")


class TestBuildRunCommand:
    """Test building the cub run command."""

    def test_build_command_basic(self, mock_worktree_manager, tmp_path):
        """Test building basic command."""
        runner = ParallelRunner(tmp_path)

        cmd = runner._build_run_command("task-001")

        assert "run" in cmd
        assert "--task" in cmd
        assert "task-001" in cmd
        assert "--once" in cmd

    def test_build_command_with_harness(self, mock_worktree_manager, tmp_path):
        """Test building command with harness option."""
        runner = ParallelRunner(tmp_path, harness="claude")

        cmd = runner._build_run_command("task-001")

        assert "--harness" in cmd
        assert "claude" in cmd

    def test_build_command_with_model(self, mock_worktree_manager, tmp_path):
        """Test building command with model option."""
        runner = ParallelRunner(tmp_path, model="sonnet")

        cmd = runner._build_run_command("task-001")

        assert "--model" in cmd
        assert "sonnet" in cmd

    def test_build_command_with_debug(self, mock_worktree_manager, tmp_path):
        """Test building command with debug option."""
        runner = ParallelRunner(tmp_path, debug=True)

        cmd = runner._build_run_command("task-001")

        assert "--debug" in cmd

    def test_build_command_with_stream(self, mock_worktree_manager, tmp_path):
        """Test building command with stream option."""
        runner = ParallelRunner(tmp_path, stream=True)

        cmd = runner._build_run_command("task-001")

        assert "--stream" in cmd


class TestParallelRunnerRun:
    """Test parallel execution."""

    def test_run_empty_tasks(self, mock_worktree_manager, tmp_path):
        """Test running with no tasks."""
        runner = ParallelRunner(tmp_path)

        result = runner.run([])

        assert result.tasks_completed == 0
        assert result.tasks_failed == 0
        assert len(result.workers) == 0

    @patch("cub.core.worktree.parallel.subprocess.run")
    def test_run_single_task_success(
        self, mock_subprocess, mock_worktree_manager, sample_tasks, tmp_path
    ):
        """Test running a single task successfully."""
        # Mock subprocess to return success
        mock_subprocess.return_value = MagicMock(returncode=0, stderr="")

        runner = ParallelRunner(tmp_path)

        result = runner.run([sample_tasks[0]], max_workers=1)

        assert result.tasks_completed == 1
        assert result.tasks_failed == 0
        assert len(result.workers) == 1
        assert result.workers[0].success is True

    @patch("cub.core.worktree.parallel.subprocess.run")
    def test_run_single_task_failure(
        self, mock_subprocess, mock_worktree_manager, sample_tasks, tmp_path
    ):
        """Test running a single task that fails."""
        # Mock subprocess to return failure
        mock_subprocess.return_value = MagicMock(returncode=1, stderr="Task failed")

        runner = ParallelRunner(tmp_path)

        result = runner.run([sample_tasks[0]], max_workers=1)

        assert result.tasks_completed == 0
        assert result.tasks_failed == 1
        assert len(result.workers) == 1
        assert result.workers[0].success is False
        assert result.workers[0].error is not None

    @patch("cub.core.worktree.parallel.subprocess.run")
    def test_run_multiple_tasks(
        self, mock_subprocess, mock_worktree_manager, sample_tasks, tmp_path
    ):
        """Test running multiple tasks."""
        # Mock subprocess to return success for all
        mock_subprocess.return_value = MagicMock(returncode=0, stderr="")

        runner = ParallelRunner(tmp_path)

        result = runner.run(sample_tasks, max_workers=3)

        assert result.tasks_completed == 3
        assert result.tasks_failed == 0
        assert len(result.workers) == 3

    @patch("cub.core.worktree.parallel.subprocess.run")
    def test_run_mixed_results(
        self, mock_subprocess, mock_worktree_manager, sample_tasks, tmp_path
    ):
        """Test running with mixed success/failure."""
        # Mock subprocess to alternate success/failure
        call_count = [0]

        def mock_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                return MagicMock(returncode=1, stderr="Failed")
            return MagicMock(returncode=0, stderr="")

        mock_subprocess.side_effect = mock_run

        runner = ParallelRunner(tmp_path)

        result = runner.run(sample_tasks, max_workers=3)

        # Results may vary due to threading, but should have mix
        assert result.tasks_completed + result.tasks_failed == 3


class TestGetIndependentTasks:
    """Test the convenience function."""

    def test_get_independent_tasks(self, mock_worktree_manager, sample_tasks):
        """Test the standalone function."""
        backend = MagicMock()
        backend.get_ready_tasks.return_value = sample_tasks

        with patch("cub.core.worktree.parallel.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/tmp/project")

            tasks = get_independent_tasks(backend, count=2)

            assert len(tasks) == 2


class TestCleanup:
    """Test worktree cleanup."""

    @patch("cub.core.worktree.parallel.subprocess.run")
    def test_cleanup_worktrees(
        self, mock_subprocess, mock_worktree_manager, sample_tasks, tmp_path
    ):
        """Test that worktrees are cleaned up after run."""
        mock_subprocess.return_value = MagicMock(returncode=0, stderr="")

        runner = ParallelRunner(tmp_path)

        runner.run([sample_tasks[0]], max_workers=1)

        # Verify cleanup was called
        mock_worktree_manager.list.assert_called()
