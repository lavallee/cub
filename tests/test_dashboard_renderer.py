"""
Unit tests for dashboard renderer.

Tests the Rich-based dashboard rendering for cub run monitoring.
"""

from datetime import datetime
from io import StringIO

import pytest
from rich.console import Console
from rich.layout import Layout

from cub.core.status.models import (
    BudgetStatus,
    EventLevel,
    EventLog,
    IterationInfo,
    RunPhase,
    RunStatus,
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

        # Add events
        status.add_event("Task cub-072 started", EventLevel.INFO, task_id="cub-072")
        status.add_event("Task cub-072 completed", EventLevel.INFO, task_id="cub-072")
        status.add_event("Committed: feat(cub-072): Add status writer", EventLevel.INFO)
        status.add_event("Task cub-073 started", EventLevel.INFO, task_id="cub-073")
        status.add_event(
            "Warning: Approaching token limit", EventLevel.WARNING, task_id="cub-073"
        )

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

    def test_render_returns_layout(self, renderer: DashboardRenderer, basic_status: RunStatus) -> None:
        """Test that render() returns a Layout."""
        layout = renderer.render(basic_status)
        assert isinstance(layout, Layout)

    def test_render_has_expected_structure(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test that rendered layout has expected panel structure."""
        layout = renderer.render(basic_status)

        # Check that expected panels exist
        assert layout["header"] is not None
        assert layout["body"] is not None
        assert layout["body"]["task"] is not None
        assert layout["body"]["budget"] is not None
        assert layout["body"]["task"]["current"] is not None
        assert layout["body"]["task"]["activity"] is not None

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
        # All sections should be populated
        assert layout["header"] is not None
        assert layout["body"]["task"]["current"] is not None
        assert layout["body"]["budget"] is not None
        assert layout["body"]["task"]["activity"] is not None

    def test_render_budget_no_limits(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering budget panel with no limits set."""
        basic_status.budget = BudgetStatus(
            tokens_used=50000,
            cost_usd=2.50,
        )
        layout = renderer.render(basic_status)

        assert layout is not None

    def test_render_budget_over_limit(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering budget panel when over limit."""
        basic_status.budget = BudgetStatus(
            tokens_used=1100000,
            tokens_limit=1000000,
        )
        layout = renderer.render(basic_status)

        assert layout is not None
        assert basic_status.budget.is_over_budget

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

    def test_render_activity_log_limits_to_10(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test that activity log only shows last 10 events."""
        # Add 15 events
        for i in range(15):
            basic_status.add_event(f"Event {i}", EventLevel.INFO)

        layout = renderer.render(basic_status)
        assert layout is not None

        # Should only show last 10
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

    def test_render_with_various_budget_combinations(
        self, renderer: DashboardRenderer, basic_status: RunStatus
    ) -> None:
        """Test rendering with different budget limit combinations."""
        # Only token limit
        basic_status.budget = BudgetStatus(
            tokens_used=100000,
            tokens_limit=500000,
        )
        layout1 = renderer.render(basic_status)
        assert layout1 is not None

        # Only cost limit
        basic_status.budget = BudgetStatus(
            cost_usd=5.0,
            cost_limit=10.0,
        )
        layout2 = renderer.render(basic_status)
        assert layout2 is not None

        # Only task limit
        basic_status.budget = BudgetStatus(
            tasks_completed=3,
            tasks_limit=10,
        )
        layout3 = renderer.render(basic_status)
        assert layout3 is not None

        # All limits
        basic_status.budget = BudgetStatus(
            tokens_used=100000,
            tokens_limit=500000,
            cost_usd=5.0,
            cost_limit=10.0,
            tasks_completed=3,
            tasks_limit=10,
        )
        layout4 = renderer.render(basic_status)
        assert layout4 is not None

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

        # Verify hierarchy
        assert layout["header"] is not None
        assert layout["body"]["task"]["current"] is not None
        assert layout["body"]["task"]["activity"] is not None
        assert layout["body"]["budget"] is not None
