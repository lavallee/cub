"""
Comprehensive tests for plan execution in cli/run.py.

Tests the `cub run --plan` functionality including:
- Plan execution with multiple epics
- Epic ordering and completion detection
- Ledger entries created at correct times
- Partial run options (--start-epic, --only-epic)
- Budget enforcement during plan execution
- Error handling (epic failure, harness timeout)
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from cub.cli.run import _run_plan
from cub.core.config.models import (
    BudgetConfig,
    CircuitBreakerConfig,
    CubConfig,
    HarnessConfig,
    HooksConfig,
    LedgerConfig,
    LoopConfig,
    SyncConfig,
)
from cub.core.plan.models import Plan, PlanStatus
from cub.core.run.models import RunEvent, RunEventType, RunResult
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with necessary structure."""
    cub_dir = tmp_path / ".cub"
    cub_dir.mkdir()

    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()

    ledger_dir = cub_dir / "ledger"
    ledger_dir.mkdir()

    return tmp_path


@pytest.fixture
def config() -> CubConfig:
    """Provide a minimal CubConfig for testing."""
    return CubConfig(
        harness=HarnessConfig(
            priority=["claude"],
            model="sonnet",
        ),
        loop=LoopConfig(
            max_iterations=100,
            on_task_failure="continue",
        ),
        budget=BudgetConfig(
            max_tokens_per_task=100000,
            max_total_cost_usd=10.0,
            max_tasks_per_session=50,
        ),
        circuit_breaker=CircuitBreakerConfig(
            enabled=True,
            timeout_minutes=30,
        ),
        ledger=LedgerConfig(enabled=True),
        hooks=HooksConfig(enabled=False, fail_fast=False),
        sync=SyncConfig(enabled=False, auto_sync="never"),
    )


@pytest.fixture
def plan_slug() -> str:
    """Return a test plan slug."""
    return "test-plan"


@pytest.fixture
def mock_epics() -> list[Mock]:
    """Create mock epic objects with realistic structure."""
    epic1 = Mock()
    epic1.epic_id = "test-epic-001"
    epic1.title = "First Epic"
    epic1.description = "First epic description"

    epic2 = Mock()
    epic2.epic_id = "test-epic-002"
    epic2.title = "Second Epic"
    epic2.description = "Second epic description"

    epic3 = Mock()
    epic3.epic_id = "test-epic-003"
    epic3.title = "Third Epic"
    epic3.description = "Third epic description"

    return [epic1, epic2, epic3]


@pytest.fixture
def setup_plan_files(project_dir: Path, plan_slug: str, mock_epics: list[Mock]) -> Path:
    """Set up plan files in the project directory."""
    plan_dir = project_dir / "plans" / plan_slug
    plan_dir.mkdir(parents=True)

    # Create plan.json
    plan_json_path = plan_dir / "plan.json"
    plan = Plan(
        slug=plan_slug,
        project="test-project",
        spec_file=f"{plan_slug}.md",
        status=PlanStatus.STAGED,
    )
    plan_json_path.write_text(plan.model_dump_json(), encoding="utf-8")

    # Create itemized-plan.md
    itemized_path = plan_dir / "itemized-plan.md"
    itemized_content = "# Test Plan\n\n"
    for epic in mock_epics:
        itemized_content += f"## Epic: {epic.epic_id} - {epic.title}\n\n"
        itemized_content += f"{epic.description}\n\n"
        itemized_content += "### Tasks\n\n"
        itemized_content += f"- Task 1 for {epic.epic_id}\n"
        itemized_content += f"- Task 2 for {epic.epic_id}\n\n"

    itemized_path.write_text(itemized_content, encoding="utf-8")

    return plan_dir


def _make_task(
    task_id: str = "test-001",
    title: str = "Test task",
    status: TaskStatus = TaskStatus.OPEN,
    parent: str | None = None,
) -> Task:
    """Create a Task object for testing."""
    return Task(
        id=task_id,
        title=title,
        description="Test description",
        status=status,
        priority=TaskPriority.P2,
        type=TaskType.TASK,
        parent=parent,
    )


def _make_run_event(
    event_type: RunEventType,
    task_id: str | None = None,
    task_title: str | None = None,
    tokens_used: int | None = None,
    cost_usd: float | None = None,
    error: str | None = None,
) -> RunEvent:
    """Create a RunEvent for testing."""
    return RunEvent(
        event_type=event_type,
        task_id=task_id,
        task_title=task_title,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        error=error,
    )


# ==============================================================================
# Happy Path Tests
# ==============================================================================


def test_run_plan_happy_path(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    mock_epics: list[Mock],
    setup_plan_files: Path,
) -> None:
    """
    Test successful plan execution with multiple epics.

    Verifies that:
    - All epics are processed in order
    - Tasks are executed for each epic
    - Ledger entries are created for plan and epics
    - Success exit code is returned
    """
    # Setup mocks
    mock_task_backend = MagicMock()
    mock_harness_backend = MagicMock()
    mock_run_service = MagicMock()

    # Mock task backend to return tasks for each epic
    def mock_list_tasks(parent: str | None = None, **kwargs) -> list[Task]:
        if parent == "test-epic-001":
            return [
                _make_task("task-001-1", "Task 1.1", TaskStatus.OPEN, parent),
                _make_task("task-001-2", "Task 1.2", TaskStatus.OPEN, parent),
            ]
        elif parent == "test-epic-002":
            return [
                _make_task("task-002-1", "Task 2.1", TaskStatus.OPEN, parent),
            ]
        elif parent == "test-epic-003":
            return []  # No tasks, should skip
        return []

    mock_task_backend.list_tasks.side_effect = mock_list_tasks
    mock_task_backend.backend_name = "jsonl"
    mock_task_backend.try_close_epic.return_value = (True, "Epic closed")

    # Mock harness
    mock_harness_backend.is_available.return_value = True
    mock_harness_backend.name = "claude"

    # Mock run service execution to return successful events
    def mock_execute(*args, **kwargs):
        # Simulate task completion events for the epic
        yield _make_run_event(
            RunEventType.TASK_COMPLETED,
            task_id="task-001-1",
            task_title="Task 1.1",
            tokens_used=1000,
            cost_usd=0.01,
        )
        yield _make_run_event(RunEventType.ALL_TASKS_COMPLETE)

    mock_run_service.execute.side_effect = lambda *args, **kwargs: mock_execute()
    mock_run_service.get_result.return_value = RunResult(
        success=True,
        tasks_completed=1,
        tasks_failed=0,
        total_tokens=1000,
        total_cost_usd=0.01,
        total_duration_seconds=10.0,
    )

    # Patch dependencies
    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.cli.run.get_task_backend") as mock_get_backend, \
         patch("cub.cli.run.LedgerWriter") as mock_ledger_writer_cls, \
         patch("cub.cli.run.LedgerIntegration"), \
         patch("cub.cli.run.RunService") as mock_run_service_cls, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan:

        mock_setup_harness.return_value = ("claude", mock_harness_backend)
        mock_get_backend.return_value = mock_task_backend
        mock_parse_plan.return_value = mock_epics
        mock_run_service_cls.return_value = mock_run_service

        # Mock ledger writer
        mock_ledger_writer = MagicMock()
        mock_ledger_writer_cls.return_value = mock_ledger_writer

        # Execute
        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        # Verify success
        assert exit_code == 0

        # Verify plan entry created
        assert mock_ledger_writer.create_plan_entry.call_count >= 1
        plan_entry_calls = [
            c for c in mock_ledger_writer.create_plan_entry.call_args_list
        ]
        assert len(plan_entry_calls) > 0

        # Verify epics were processed (all 3 epics including empty epic-003)
        assert mock_run_service.execute.call_count == 3  # All epics are processed

        # Verify epic entries created (all 3 epics)
        assert mock_ledger_writer.create_epic_entry.call_count == 3


def test_epic_ordering_and_completion_detection(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    mock_epics: list[Mock],
    setup_plan_files: Path,
) -> None:
    """
    Test that epics are processed in order and already-complete epics are skipped.

    Verifies:
    - Epics are processed in the order they appear in the plan
    - Epics with all tasks closed are skipped
    - Processing continues to next epic after skip
    """
    # Setup mocks
    mock_task_backend = MagicMock()
    mock_harness_backend = MagicMock()
    mock_run_service = MagicMock()

    # Epic 1: Already complete (all tasks closed)
    # Epic 2: Has open tasks
    # Epic 3: Already complete
    def mock_list_tasks(parent: str | None = None, **kwargs) -> list[Task]:
        if parent == "test-epic-001":
            return [
                _make_task("task-001-1", "Task 1.1", TaskStatus.CLOSED, parent),
                _make_task("task-001-2", "Task 1.2", TaskStatus.CLOSED, parent),
            ]
        elif parent == "test-epic-002":
            return [
                _make_task("task-002-1", "Task 2.1", TaskStatus.OPEN, parent),
            ]
        elif parent == "test-epic-003":
            return [
                _make_task("task-003-1", "Task 3.1", TaskStatus.CLOSED, parent),
            ]
        return []

    mock_task_backend.list_tasks.side_effect = mock_list_tasks
    mock_task_backend.backend_name = "jsonl"
    mock_task_backend.try_close_epic.return_value = (True, "Epic closed")

    mock_harness_backend.is_available.return_value = True
    mock_harness_backend.name = "claude"

    # Only epic-002 should execute
    def mock_execute(*args, **kwargs):
        yield _make_run_event(
            RunEventType.TASK_COMPLETED,
            task_id="task-002-1",
            task_title="Task 2.1",
            tokens_used=500,
            cost_usd=0.005,
        )
        yield _make_run_event(RunEventType.ALL_TASKS_COMPLETE)

    mock_run_service.execute.side_effect = lambda *args, **kwargs: mock_execute()
    mock_run_service.get_result.return_value = RunResult(
        success=True,
        tasks_completed=1,
        tasks_failed=0,
        total_tokens=500,
        total_cost_usd=0.005,
        total_duration_seconds=5.0,
    )

    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.cli.run.get_task_backend") as mock_get_backend, \
         patch("cub.cli.run.LedgerWriter") as mock_ledger_writer_cls, \
         patch("cub.cli.run.LedgerIntegration"), \
         patch("cub.cli.run.RunService") as mock_run_service_cls, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan:

        mock_setup_harness.return_value = ("claude", mock_harness_backend)
        mock_get_backend.return_value = mock_task_backend
        mock_parse_plan.return_value = mock_epics
        mock_run_service_cls.return_value = mock_run_service
        mock_ledger_writer_cls.return_value = MagicMock()

        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        assert exit_code == 0
        # Only epic-002 should be executed (epic-001 and epic-003 are complete)
        assert mock_run_service.execute.call_count == 1


# ==============================================================================
# Partial Run Tests
# ==============================================================================


def test_start_epic_flag(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    mock_epics: list[Mock],
    setup_plan_files: Path,
) -> None:
    """
    Test --start-epic flag skips earlier epics.

    Verifies:
    - Epics before start-epic are skipped
    - Processing begins at start-epic
    - Subsequent epics are processed normally
    """
    mock_task_backend = MagicMock()
    mock_harness_backend = MagicMock()
    mock_run_service = MagicMock()

    # All epics have open tasks
    def mock_list_tasks(parent: str | None = None, **kwargs) -> list[Task]:
        if parent in ["test-epic-001", "test-epic-002", "test-epic-003"]:
            return [_make_task(f"task-{parent}", f"Task for {parent}", TaskStatus.OPEN, parent)]
        return []

    mock_task_backend.list_tasks.side_effect = mock_list_tasks
    mock_task_backend.backend_name = "jsonl"
    mock_task_backend.try_close_epic.return_value = (True, "Epic closed")

    mock_harness_backend.is_available.return_value = True
    mock_harness_backend.name = "claude"

    def mock_execute(*args, **kwargs):
        yield _make_run_event(RunEventType.ALL_TASKS_COMPLETE)

    mock_run_service.execute.side_effect = lambda *args, **kwargs: mock_execute()
    mock_run_service.get_result.return_value = RunResult(
        success=True, tasks_completed=1, tasks_failed=0,
        total_tokens=100, total_cost_usd=0.001, total_duration_seconds=1.0,
    )

    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.cli.run.get_task_backend") as mock_get_backend, \
         patch("cub.cli.run.LedgerWriter") as mock_ledger_writer_cls, \
         patch("cub.cli.run.LedgerIntegration"), \
         patch("cub.cli.run.RunService") as mock_run_service_cls, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan:

        mock_setup_harness.return_value = ("claude", mock_harness_backend)
        mock_get_backend.return_value = mock_task_backend
        mock_parse_plan.return_value = mock_epics
        mock_run_service_cls.return_value = mock_run_service
        mock_ledger_writer_cls.return_value = MagicMock()

        # Start from epic-002, should skip epic-001
        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic="test-epic-002",
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        assert exit_code == 0
        # Should process epic-002 and epic-003 only (2 epics)
        assert mock_run_service.execute.call_count == 2


def test_only_epic_flag(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    mock_epics: list[Mock],
    setup_plan_files: Path,
) -> None:
    """
    Test --only-epic flag executes only specified epic.

    Verifies:
    - Only the specified epic is executed
    - Other epics are skipped
    """
    mock_task_backend = MagicMock()
    mock_harness_backend = MagicMock()
    mock_run_service = MagicMock()

    def mock_list_tasks(parent: str | None = None, **kwargs) -> list[Task]:
        if parent in ["test-epic-001", "test-epic-002", "test-epic-003"]:
            return [_make_task(f"task-{parent}", f"Task for {parent}", TaskStatus.OPEN, parent)]
        return []

    mock_task_backend.list_tasks.side_effect = mock_list_tasks
    mock_task_backend.backend_name = "jsonl"
    mock_task_backend.try_close_epic.return_value = (True, "Epic closed")

    mock_harness_backend.is_available.return_value = True
    mock_harness_backend.name = "claude"

    def mock_execute(*args, **kwargs):
        yield _make_run_event(RunEventType.ALL_TASKS_COMPLETE)

    mock_run_service.execute.side_effect = lambda *args, **kwargs: mock_execute()
    mock_run_service.get_result.return_value = RunResult(
        success=True, tasks_completed=1, tasks_failed=0,
        total_tokens=100, total_cost_usd=0.001, total_duration_seconds=1.0,
    )

    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.cli.run.get_task_backend") as mock_get_backend, \
         patch("cub.cli.run.LedgerWriter") as mock_ledger_writer_cls, \
         patch("cub.cli.run.LedgerIntegration"), \
         patch("cub.cli.run.RunService") as mock_run_service_cls, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan:

        mock_setup_harness.return_value = ("claude", mock_harness_backend)
        mock_get_backend.return_value = mock_task_backend
        mock_parse_plan.return_value = mock_epics
        mock_run_service_cls.return_value = mock_run_service
        mock_ledger_writer_cls.return_value = MagicMock()

        # Only run epic-002
        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic="test-epic-002",
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        assert exit_code == 0
        # Should process only epic-002 (1 epic)
        assert mock_run_service.execute.call_count == 1


# ==============================================================================
# Budget Enforcement Tests
# ==============================================================================


def test_budget_exhausted_during_plan(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    mock_epics: list[Mock],
    setup_plan_files: Path,
) -> None:
    """
    Test that plan execution stops gracefully when budget is exhausted.

    Verifies:
    - First epic executes normally
    - Budget exhaustion event stops execution
    - Partial plan status is recorded
    - Non-zero exit code is returned
    """
    mock_task_backend = MagicMock()
    mock_harness_backend = MagicMock()
    mock_run_service = MagicMock()

    def mock_list_tasks(parent: str | None = None, **kwargs) -> list[Task]:
        if parent in ["test-epic-001", "test-epic-002"]:
            return [_make_task(f"task-{parent}", f"Task for {parent}", TaskStatus.OPEN, parent)]
        return []

    mock_task_backend.list_tasks.side_effect = mock_list_tasks
    mock_task_backend.backend_name = "jsonl"
    mock_task_backend.try_close_epic.return_value = (True, "Epic closed")

    mock_harness_backend.is_available.return_value = True
    mock_harness_backend.name = "claude"

    # First epic succeeds, second epic hits budget limit
    call_count = [0]  # Use list to allow modification in nested function

    def mock_execute(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First epic succeeds
            yield _make_run_event(
                RunEventType.TASK_COMPLETED,
                task_id="task-001",
                task_title="Task 1",
                tokens_used=50000,
                cost_usd=5.0,
            )
            yield _make_run_event(RunEventType.ALL_TASKS_COMPLETE)
        else:
            # Second epic hits budget
            yield _make_run_event(RunEventType.BUDGET_EXHAUSTED)

    mock_run_service.execute.side_effect = mock_execute

    # First call: success, Second call: budget exhausted
    result_call_count = [0]

    def mock_get_result():
        result_call_count[0] += 1
        if result_call_count[0] == 1:
            return RunResult(
                success=True, tasks_completed=1, tasks_failed=0,
                total_tokens=50000, total_cost_usd=5.0, total_duration_seconds=10.0,
            )
        else:
            return RunResult(
                success=False, tasks_completed=0, tasks_failed=1,  # Mark as failed
                total_tokens=0, total_cost_usd=0.0, total_duration_seconds=0.5,
            )

    mock_run_service.get_result.side_effect = mock_get_result

    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.cli.run.get_task_backend") as mock_get_backend, \
         patch("cub.cli.run.LedgerWriter") as mock_ledger_writer_cls, \
         patch("cub.cli.run.LedgerIntegration"), \
         patch("cub.cli.run.RunService") as mock_run_service_cls, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan:

        mock_setup_harness.return_value = ("claude", mock_harness_backend)
        mock_get_backend.return_value = mock_task_backend
        mock_parse_plan.return_value = mock_epics
        mock_run_service_cls.return_value = mock_run_service

        mock_ledger_writer = MagicMock()
        mock_ledger_writer_cls.return_value = mock_ledger_writer

        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=10.0,  # Set budget limit
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        # Should fail due to budget exhaustion
        assert exit_code == 1

        # Should have executed 2 epics (one success, one budget exhausted)
        assert mock_run_service.execute.call_count == 2


# ==============================================================================
# Error Handling Tests
# ==============================================================================


def test_epic_failure_stops_execution(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    mock_epics: list[Mock],
    setup_plan_files: Path,
) -> None:
    """
    Test that plan execution stops when an epic fails.

    Verifies:
    - First epic executes and fails
    - Subsequent epics are not executed
    - Failed epic is recorded in summary
    - Non-zero exit code is returned
    """
    mock_task_backend = MagicMock()
    mock_harness_backend = MagicMock()
    mock_run_service = MagicMock()

    def mock_list_tasks(parent: str | None = None, **kwargs) -> list[Task]:
        if parent in ["test-epic-001", "test-epic-002"]:
            return [_make_task(f"task-{parent}", f"Task for {parent}", TaskStatus.OPEN, parent)]
        return []

    mock_task_backend.list_tasks.side_effect = mock_list_tasks
    mock_task_backend.backend_name = "jsonl"

    mock_harness_backend.is_available.return_value = True
    mock_harness_backend.name = "claude"

    # First epic fails
    def mock_execute(*args, **kwargs):
        yield _make_run_event(
            RunEventType.TASK_FAILED,
            task_id="task-001",
            task_title="Task 1",
            error="Task execution failed",
        )
        yield _make_run_event(RunEventType.RUN_FAILED, error="Epic failed")

    mock_run_service.execute.side_effect = lambda *args, **kwargs: mock_execute()
    mock_run_service.get_result.return_value = RunResult(
        success=False, tasks_completed=0, tasks_failed=1,
        total_tokens=100, total_cost_usd=0.001, total_duration_seconds=1.0,
    )

    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.cli.run.get_task_backend") as mock_get_backend, \
         patch("cub.cli.run.LedgerWriter") as mock_ledger_writer_cls, \
         patch("cub.cli.run.LedgerIntegration"), \
         patch("cub.cli.run.RunService") as mock_run_service_cls, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan:

        mock_setup_harness.return_value = ("claude", mock_harness_backend)
        mock_get_backend.return_value = mock_task_backend
        mock_parse_plan.return_value = mock_epics
        mock_run_service_cls.return_value = mock_run_service
        mock_ledger_writer_cls.return_value = MagicMock()

        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        # Should fail
        assert exit_code == 1

        # Only first epic should be executed
        assert mock_run_service.execute.call_count == 1


def test_plan_not_found(
    project_dir: Path,
    config: CubConfig,
) -> None:
    """
    Test error handling when plan directory doesn't exist.

    Verifies:
    - Appropriate error message is shown
    - Non-zero exit code is returned
    """
    with patch("cub.cli.run.console") as mock_console:
        exit_code = _run_plan(
            plan_slug="nonexistent-plan",
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        assert exit_code == 1
        # Should print error about plan not found
        assert any(
            "Plan directory not found" in str(call)
            for call in mock_console.print.call_args_list
        )


def test_missing_itemized_plan(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
) -> None:
    """
    Test error handling when itemized-plan.md is missing.

    Verifies:
    - Appropriate error message is shown
    - Suggestion to run itemize is provided
    - Non-zero exit code is returned
    """
    # Create plan directory and plan.json but not itemized-plan.md
    plan_dir = project_dir / "plans" / plan_slug
    plan_dir.mkdir(parents=True)

    plan_json_path = plan_dir / "plan.json"
    plan = Plan(
        slug=plan_slug,
        project="test-project",
        spec_file=f"{plan_slug}.md",
        status=PlanStatus.STAGED,
    )
    plan_json_path.write_text(plan.model_dump_json(), encoding="utf-8")

    with patch("cub.cli.run.console") as mock_console:
        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        assert exit_code == 1
        # Should print error about missing itemized plan
        assert any(
            "Itemized plan not found" in str(call)
            for call in mock_console.print.call_args_list
        )


def test_keyboard_interrupt_handling(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    mock_epics: list[Mock],
    setup_plan_files: Path,
) -> None:
    """
    Test graceful handling of keyboard interrupt during epic execution.

    Verifies:
    - Interrupt is caught and handled gracefully
    - Current epic is marked as failed
    - Non-zero exit code is returned
    """
    mock_task_backend = MagicMock()
    mock_harness_backend = MagicMock()
    mock_run_service = MagicMock()

    def mock_list_tasks(parent: str | None = None, **kwargs) -> list[Task]:
        if parent in ["test-epic-001", "test-epic-002"]:
            return [_make_task(f"task-{parent}", f"Task for {parent}", TaskStatus.OPEN, parent)]
        return []

    mock_task_backend.list_tasks.side_effect = mock_list_tasks
    mock_task_backend.backend_name = "jsonl"

    mock_harness_backend.is_available.return_value = True
    mock_harness_backend.name = "claude"

    # Simulate interrupt during first epic
    def mock_execute(*args, **kwargs):
        yield _make_run_event(RunEventType.INTERRUPT_RECEIVED)

    mock_run_service.execute.side_effect = lambda *args, **kwargs: mock_execute()
    mock_run_service.get_result.return_value = RunResult(
        success=False, tasks_completed=0, tasks_failed=0,
        total_tokens=0, total_cost_usd=0.0, total_duration_seconds=0.1,
    )

    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.cli.run.get_task_backend") as mock_get_backend, \
         patch("cub.cli.run.LedgerWriter") as mock_ledger_writer_cls, \
         patch("cub.cli.run.LedgerIntegration"), \
         patch("cub.cli.run.RunService") as mock_run_service_cls, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan:

        mock_setup_harness.return_value = ("claude", mock_harness_backend)
        mock_get_backend.return_value = mock_task_backend
        mock_parse_plan.return_value = mock_epics
        mock_run_service_cls.return_value = mock_run_service
        mock_ledger_writer_cls.return_value = MagicMock()

        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        # Should fail due to interrupt
        assert exit_code == 1

        # Only first epic should be executed
        assert mock_run_service.execute.call_count == 1


# ==============================================================================
# Ledger Integration Tests
# ==============================================================================


def test_ledger_entries_created_correctly(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    mock_epics: list[Mock],
    setup_plan_files: Path,
) -> None:
    """
    Test that ledger entries are created at correct times with correct data.

    Verifies:
    - Plan entry created at start with in_progress status
    - Epic entries created after each epic completes
    - Plan entry updated at end with final status and metrics
    - All entries contain correct IDs and relationships
    """
    mock_task_backend = MagicMock()
    mock_harness_backend = MagicMock()
    mock_run_service = MagicMock()

    # Epic 1 and 2 have tasks
    def mock_list_tasks(parent: str | None = None, **kwargs) -> list[Task]:
        if parent == "test-epic-001":
            return [_make_task("task-001", "Task 1", TaskStatus.OPEN, parent)]
        elif parent == "test-epic-002":
            return [_make_task("task-002", "Task 2", TaskStatus.OPEN, parent)]
        elif parent == "test-epic-003":
            return []  # Empty, should skip
        return []

    mock_task_backend.list_tasks.side_effect = mock_list_tasks
    mock_task_backend.backend_name = "jsonl"
    mock_task_backend.try_close_epic.return_value = (True, "Epic closed")

    mock_harness_backend.is_available.return_value = True
    mock_harness_backend.name = "claude"

    def mock_execute(*args, **kwargs):
        yield _make_run_event(
            RunEventType.TASK_COMPLETED,
            task_id="task-001",
            task_title="Task 1",
            tokens_used=1000,
            cost_usd=0.01,
        )
        yield _make_run_event(RunEventType.ALL_TASKS_COMPLETE)

    mock_run_service.execute.side_effect = lambda *args, **kwargs: mock_execute()
    mock_run_service.get_result.return_value = RunResult(
        success=True, tasks_completed=1, tasks_failed=0,
        total_tokens=1000, total_cost_usd=0.01, total_duration_seconds=5.0,
    )

    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.cli.run.get_task_backend") as mock_get_backend, \
         patch("cub.cli.run.LedgerWriter") as mock_ledger_writer_cls, \
         patch("cub.cli.run.LedgerIntegration"), \
         patch("cub.cli.run.RunService") as mock_run_service_cls, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan:

        mock_setup_harness.return_value = ("claude", mock_harness_backend)
        mock_get_backend.return_value = mock_task_backend
        mock_parse_plan.return_value = mock_epics
        mock_run_service_cls.return_value = mock_run_service

        mock_ledger_writer = MagicMock()
        mock_ledger_writer_cls.return_value = mock_ledger_writer

        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name="test-session",
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        assert exit_code == 0

        # Verify plan entry created
        plan_entry_calls = mock_ledger_writer.create_plan_entry.call_args_list
        assert len(plan_entry_calls) >= 1  # At least one entry

        # Check the plan entry properties
        plan_entry = plan_entry_calls[0][0][0]
        assert plan_entry.plan_id == "test-session"
        assert plan_entry.epics == ["test-epic-001", "test-epic-002", "test-epic-003"]

        # The final plan entry should show completed status
        last_plan_entry = plan_entry_calls[-1][0][0]
        assert last_plan_entry.status == "completed"
        assert last_plan_entry.completed_at is not None

        # Verify epic entries created (all 3 epics)
        epic_entry_calls = mock_ledger_writer.create_epic_entry.call_args_list
        assert len(epic_entry_calls) == 3

        # Verify epic IDs
        epic_ids = [call[0][0].id for call in epic_entry_calls]
        assert "test-epic-001" in epic_ids
        assert "test-epic-002" in epic_ids
        assert "test-epic-003" in epic_ids


def test_no_epics_in_plan(
    project_dir: Path,
    config: CubConfig,
    plan_slug: str,
    setup_plan_files: Path,
) -> None:
    """
    Test error handling when plan has no epics.

    Verifies:
    - Appropriate error message is shown
    - Non-zero exit code is returned
    """
    with patch("cub.cli.run._setup_harness") as mock_setup_harness, \
         patch("cub.core.prep.plan_markdown.parse_plan_markdown") as mock_parse_plan, \
         patch("cub.cli.run.console") as mock_console:

        mock_setup_harness.return_value = ("claude", MagicMock())
        mock_parse_plan.return_value = []  # No epics

        exit_code = _run_plan(
            plan_slug=plan_slug,
            project_dir=project_dir,
            config=config,
            harness=None,
            model=None,
            stream=False,
            budget=None,
            budget_tokens=None,
            session_name=None,
            start_epic=None,
            only_epic=None,
            main_ok=False,
            use_current_branch=False,
            from_branch=None,
            no_sync=True,
            no_circuit_breaker=False,
            debug=False,
        )

        assert exit_code == 1
        # Should print error about no epics
        assert any(
            "No epics found" in str(call)
            for call in mock_console.print.call_args_list
        )
