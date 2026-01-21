"""
Unit tests for dashboard renderer.

Tests the Rich-based dashboard rendering for cub run monitoring.
"""

from io import StringIO

import pytest
from rich.console import Console
from rich.layout import Layout

from cub.core.status.models import (
    BudgetStatus,
    EventLevel,
    IterationInfo,
    RunPhase,
    RunStatus,
    TaskEntry,
    TaskState,
)
from cub.dashboard.renderer import DashboardRenderer


class TestDashboardRenderer:
    """Test DashboardRenderer class."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console with string output."""
        return Console(file=StringIO(), width=120, legacy_windows=False)

    @pytest.fixture
    def renderer(self, console: Console) -> DashboardRenderer:
        """Create a test dashboard renderer."""
        return DashboardRenderer(console=console)

    @pytest.fixture
    def basic_status(self) -> RunStatus:
        """Create a basic run status for testing."""
        return RunStatus(
            run_id="test-run-001",
            session_name="test-session",
            phase=RunPhase.RUNNING,
            current_task_id="cub-001",
            current_task_title="Test task",
        )

    @pytest.fixture
    def full_status(self) -> RunStatus:
        """Create a fully populated run status for testing."""
        status = RunStatus(
            run_id="camel-20260115-120000",
            session_name="feature/dashboard",
            phase=RunPhase.RUNNING,
            current_task_id="cub-074",
            current_task_title="Implement Rich-based dashboard renderer",
            tasks_open=5,
            tasks_in_progress=1,
            tasks_closed=3,
            tasks_total=9,
            epic="cub-epic-001",
            label="feature",
            branch="feature/dashboard-improvements",
        )

        # Set iteration info
        status.iteration = IterationInfo(
            current=7,
            max=50,
            task_iteration=2,
            max_task_iteration=3,
        )

        # Set budget
        status.budget = BudgetStatus(
            tokens_used=450000,
            tokens_limit=1000000,
            cost_usd=5.25,
            cost_limit=10.0,
            tasks_completed=3,
            tasks_limit=10,
        )

        # Add task entries
        status.task_entries = [
            TaskEntry(task_id="cub-070", title="Setup project", state=TaskState.DONE),
            TaskEntry(task_id="cub-071", title="Add configuration", state=TaskState.DONE),
            TaskEntry(task_id="cub-072", title="Create models", state=TaskState.DONE),
            TaskEntry(task_id="cub-073", title="Implement API", state=TaskState.DOING),
            TaskEntry(task_id="cub-074", title="Add tests", state=TaskState.TODO),
            TaskEntry(task_id="cub-075", title="Documentation", state=TaskState.TODO),
        ]

        # Add events
        status.add_event("Task cub-072 started", EventLevel.INFO, task_id="cub-072")
        status.add_event("Task cub-072 completed", EventLevel.INFO, task_id="cub-072")
        status.add_event("Committed: feat(cub-072): Add status writer", EventLevel.INFO)
        status.add_event("Task cub-073 started", EventLevel.INFO, task_id="cub-073")
        status.add_event("Warning: Approaching token limit", EventLevel.WARNING, task_id="cub-073")

        return status

    def test_renderer_init_default_console(self) -> None:
        """Test renderer initialization with default console."""
        renderer = DashboardRenderer()
        assert renderer.console is not None
        assert isinstance(renderer.console, Console)

    def test_renderer_init_custom_console(self, console: Console) -> None:
        """Test renderer initialization with custom console."""
        renderer = DashboardRenderer(console=console)
        assert renderer.console is console

    def test_render_returns_layout(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test that render() returns a Layout."""
        layout = renderer.render(basic_status)
        assert isinstance(layout, Layout)

    def test_render_has_expected_structure(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test that rendered layout has expected panel structure (Kanban layout)."""
        layout = renderer.render(basic_status)

        # Check that expected panels exist (new Kanban structure)
        assert layout["header"] is not None
        assert layout["body"] is not None
        assert layout["body"]["kanban"] is not None
        assert layout["body"]["kanban"]["todo"] is not None
        assert layout["body"]["kanban"]["doing"] is not None
        assert layout["body"]["kanban"]["done"] is not None
        assert layout["body"]["activity"] is not None

    def test_render_initializing_phase(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering during INITIALIZING phase."""
        basic_status.phase = RunPhase.INITIALIZING
        layout = renderer.render(basic_status)

        # Should render without errors
        assert layout is not None

        # Status color should be blue for initializing
        assert renderer._get_status_color(RunPhase.INITIALIZING) == "blue"

    def test_render_running_phase(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering during RUNNING phase."""
        basic_status.phase = RunPhase.RUNNING
        layout = renderer.render(basic_status)

        assert layout is not None
        assert renderer._get_status_color(RunPhase.RUNNING) == "green"

    def test_render_completed_phase(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering during COMPLETED phase."""
        basic_status.phase = RunPhase.COMPLETED
        layout = renderer.render(basic_status)

        assert layout is not None
        assert renderer._get_status_color(RunPhase.COMPLETED) == "green"

    def test_render_failed_phase(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering during FAILED phase."""
        basic_status.phase = RunPhase.FAILED
        basic_status.last_error = "Test error message"
        layout = renderer.render(basic_status)

        assert layout is not None
        assert renderer._get_status_color(RunPhase.FAILED) == "red"

    def test_render_stopped_phase(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering during STOPPED phase."""
        basic_status.phase = RunPhase.STOPPED
        layout = renderer.render(basic_status)

        assert layout is not None
        assert renderer._get_status_color(RunPhase.STOPPED) == "yellow"

    def test_render_no_active_task(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering when no task is active."""
        basic_status.current_task_id = None
        basic_status.current_task_title = None
        layout = renderer.render(basic_status)

        assert layout is not None

    def test_render_with_full_status(
        self, renderer: DashboardRenderer, full_status: RunStatus
    ) -> None:
        """Test rendering with fully populated status."""
        layout = renderer.render(full_status)

        assert layout is not None
        # All sections should be populated (Kanban structure)
        assert layout["header"] is not None
        assert layout["body"]["kanban"]["todo"] is not None
        assert layout["body"]["kanban"]["doing"] is not None
        assert layout["body"]["kanban"]["done"] is not None
        assert layout["body"]["activity"] is not None

    def test_render_near_iteration_limit(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering when approaching iteration limit."""
        basic_status.iteration = IterationInfo(current=45, max=50)
        layout = renderer.render(basic_status)

        assert layout is not None
        assert basic_status.iteration.is_near_limit

    def test_render_activity_log_empty(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering activity log with no events."""
        basic_status.events = []
        layout = renderer.render(basic_status)

        assert layout is not None

    def test_render_activity_log_with_events(
        self, renderer: DashboardRenderer, full_status: RunStatus
    ) -> None:
        """Test rendering activity log with multiple events."""
        layout = renderer.render(full_status)

        assert layout is not None
        assert len(full_status.events) > 0

    def test_render_activity_log_limits_events(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test that activity log limits displayed events."""
        # Add 15 events
        for i in range(15):
            basic_status.add_event(f"Event {i}", EventLevel.INFO)

        layout = renderer.render(basic_status)
        assert layout is not None

        # Status should have all events
        assert len(basic_status.events) == 15

    def test_get_status_color(self, renderer: DashboardRenderer) -> None:
        """Test status color mapping."""
        assert renderer._get_status_color(RunPhase.INITIALIZING) == "blue"
        assert renderer._get_status_color(RunPhase.RUNNING) == "green"
        assert renderer._get_status_color(RunPhase.COMPLETED) == "green"
        assert renderer._get_status_color(RunPhase.FAILED) == "red"
        assert renderer._get_status_color(RunPhase.STOPPED) == "yellow"

    def test_get_event_style(self, renderer: DashboardRenderer) -> None:
        """Test event level style mapping."""
        assert renderer._get_event_style(EventLevel.DEBUG) == "dim"
        assert renderer._get_event_style(EventLevel.INFO) == ""
        assert renderer._get_event_style(EventLevel.WARNING) == "yellow"
        assert renderer._get_event_style(EventLevel.ERROR) == "bold red"

    def test_create_progress_bar(self, renderer: DashboardRenderer) -> None:
        """Test progress bar creation."""
        progress = renderer._create_progress_bar(
            completed=50,
            total=100,
            label="50/100",
        )
        assert progress is not None

    def test_create_progress_bar_zero_total(self, renderer: DashboardRenderer) -> None:
        """Test progress bar with zero total."""
        progress = renderer._create_progress_bar(
            completed=0,
            total=0,
            label="0/0",
        )
        assert progress is not None

    def test_create_progress_bar_float_values(self, renderer: DashboardRenderer) -> None:
        """Test progress bar with float values (for cost)."""
        progress = renderer._create_progress_bar(
            completed=5.25,
            total=10.0,
            label="$5.25/$10.00",
        )
        assert progress is not None

    def test_start_live(self, renderer: DashboardRenderer, basic_status: RunStatus) -> None:
        """Test starting a Live display."""
        live = renderer.start_live(basic_status)
        assert live is not None

        # Clean up
        live.stop()

    def test_render_with_task_id_only(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering with task ID but no title."""
        basic_status.current_task_title = None
        layout = renderer.render(basic_status)

        assert layout is not None

    def test_render_event_with_task_id(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering events that have task IDs."""
        basic_status.add_event(
            "Started processing",
            EventLevel.INFO,
            task_id="cub-001",
        )
        layout = renderer.render(basic_status)

        assert layout is not None
        assert len(basic_status.events) == 1
        assert basic_status.events[0].task_id == "cub-001"

    def test_render_maintains_panel_structure(
        self, renderer: DashboardRenderer, full_status: RunStatus
    ) -> None:
        """Test that complex status maintains proper panel structure."""
        layout = renderer.render(full_status)

        # Verify hierarchy (Kanban structure)
        assert layout["header"] is not None
        assert layout["body"]["kanban"]["todo"] is not None
        assert layout["body"]["kanban"]["doing"] is not None
        assert layout["body"]["kanban"]["done"] is not None
        assert layout["body"]["activity"] is not None

    def test_render_with_epic_and_label(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering with epic and label context."""
        basic_status.epic = "cub-abc"
        basic_status.label = "feature"
        basic_status.branch = "feature/test-branch"

        layout = renderer.render(basic_status)
        assert layout is not None

    def test_render_with_task_entries(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering with task entries in Kanban view."""
        # Add task entries
        basic_status.set_task_entries([
            ("cub-001", "First task"),
            ("cub-002", "Second task"),
            ("cub-003", "Third task"),
        ])

        # Move one to doing and one to done
        basic_status.start_task_entry("cub-001")
        basic_status.complete_task_entry("cub-001")
        basic_status.start_task_entry("cub-002")

        layout = renderer.render(basic_status)
        assert layout is not None

        # Verify task states
        todo_tasks = basic_status.get_tasks_by_state(TaskState.TODO)
        doing_tasks = basic_status.get_tasks_by_state(TaskState.DOING)
        done_tasks = basic_status.get_tasks_by_state(TaskState.DONE)

        assert len(todo_tasks) == 1  # cub-003
        assert len(doing_tasks) == 1  # cub-002
        assert len(done_tasks) == 1  # cub-001

    def test_render_fallback_to_current_task(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test that rendering falls back to current_task_id when task_entries is empty."""
        # No task_entries, but has current_task_id
        basic_status.task_entries = []
        basic_status.current_task_id = "cub-123"
        basic_status.current_task_title = "Fallback task"

        layout = renderer.render(basic_status)
        assert layout is not None

    def test_render_kanban_with_empty_columns(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering Kanban with empty columns."""
        basic_status.task_entries = []
        basic_status.current_task_id = None
        basic_status.current_task_title = None

        layout = renderer.render(basic_status)
        assert layout is not None

    def test_render_task_list_truncates_long_titles(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test that long task titles are truncated in the Kanban view."""
        long_title = "This is a very long task title that should be truncated in the display"
        basic_status.set_task_entries([
            ("cub-001", long_title),
        ])

        layout = renderer.render(basic_status)
        assert layout is not None


class TestRunStatusTaskEntries:
    """Test RunStatus task entry management methods."""

    def test_set_task_entries(self) -> None:
        """Test initializing task entries."""
        status = RunStatus(run_id="test-001")
        status.set_task_entries([
            ("task-1", "First task"),
            ("task-2", "Second task"),
        ])

        assert len(status.task_entries) == 2
        assert status.task_entries[0].task_id == "task-1"
        assert status.task_entries[0].title == "First task"
        assert status.task_entries[0].state == TaskState.TODO

    def test_start_task_entry(self) -> None:
        """Test marking a task as started."""
        status = RunStatus(run_id="test-001")
        status.set_task_entries([("task-1", "First task")])

        status.start_task_entry("task-1")

        assert status.task_entries[0].state == TaskState.DOING
        assert status.task_entries[0].started_at is not None

    def test_complete_task_entry(self) -> None:
        """Test marking a task as completed."""
        status = RunStatus(run_id="test-001")
        status.set_task_entries([("task-1", "First task")])

        status.start_task_entry("task-1")
        status.complete_task_entry("task-1")

        assert status.task_entries[0].state == TaskState.DONE
        assert status.task_entries[0].completed_at is not None

    def test_get_tasks_by_state(self) -> None:
        """Test filtering tasks by state."""
        status = RunStatus(run_id="test-001")
        status.set_task_entries([
            ("task-1", "First task"),
            ("task-2", "Second task"),
            ("task-3", "Third task"),
        ])

        # Move tasks through states
        status.start_task_entry("task-1")
        status.complete_task_entry("task-1")
        status.start_task_entry("task-2")

        todo = status.get_tasks_by_state(TaskState.TODO)
        doing = status.get_tasks_by_state(TaskState.DOING)
        done = status.get_tasks_by_state(TaskState.DONE)

        assert len(todo) == 1
        assert len(doing) == 1
        assert len(done) == 1

        assert todo[0].task_id == "task-3"
        assert doing[0].task_id == "task-2"
        assert done[0].task_id == "task-1"

    def test_start_nonexistent_task(self) -> None:
        """Test starting a task that doesn't exist (should be no-op)."""
        status = RunStatus(run_id="test-001")
        status.set_task_entries([("task-1", "First task")])

        # Should not raise, just do nothing
        status.start_task_entry("nonexistent")

        assert status.task_entries[0].state == TaskState.TODO

    def test_complete_nonexistent_task(self) -> None:
        """Test completing a task that doesn't exist (should be no-op)."""
        status = RunStatus(run_id="test-001")
        status.set_task_entries([("task-1", "First task")])

        # Should not raise, just do nothing
        status.complete_task_entry("nonexistent")

        assert status.task_entries[0].state == TaskState.TODO
