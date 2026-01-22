"""
Rich-based dashboard renderer for cub.

Provides real-time terminal UI for monitoring autonomous cub run sessions.
"""

from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

from cub.core.status.models import EventLevel, RunPhase, RunStatus


class DashboardRenderer:
    """
    Render a live dashboard for cub run status using Rich.

    The dashboard displays:
    - Header: session name, run status
    - Current task: task ID, title, iteration
    - Budget: progress bars for tokens, tasks, cost
    - Activity log: recent events with timestamps

    Example:
        >>> status = RunStatus(run_id="camel-20260115", phase=RunPhase.RUNNING)
        >>> renderer = DashboardRenderer()
        >>> renderer.render(status)  # Returns Rich Layout
    """

    def __init__(self, console: Console | None = None):
        """
        Initialize the dashboard renderer.

        Args:
            console: Rich console for rendering. If None, creates a new one.
        """
        self.console = console or Console()

    def render(self, status: RunStatus) -> Layout:
        """
        Render the full dashboard layout from run status.

        Args:
            status: Current run status to display

        Returns:
            Rich Layout containing all dashboard panels
        """
        # Create root layout with header and body
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
        )

        # Split body into left (task info) and right (budget)
        layout["body"].split_row(
            Layout(name="task", ratio=2),
            Layout(name="budget", ratio=1),
        )

        # Split task area into current task and activity log
        layout["task"].split_column(
            Layout(name="current", size=7),
            Layout(name="activity"),
        )

        # Populate panels
        layout["header"].update(self._render_header(status))
        layout["current"].update(self._render_current_task(status))
        layout["budget"].update(self._render_budget(status))
        layout["activity"].update(self._render_activity_log(status))

        return layout

    def _render_header(self, status: RunStatus) -> Panel:
        """Render the header panel with session info and status."""
        # Status indicator with color
        status_color = self._get_status_color(status.phase)
        status_text = Text()
        status_text.append("Status: ", style="bold")
        status_text.append(status.phase.value.upper(), style=f"bold {status_color}")

        # Build header content
        lines = [
            Text("CUB DASHBOARD", style="bold cyan", justify="center"),
            Text(f"Session: {status.session_name}  |  Run: {status.run_id}", justify="center"),
            status_text,
        ]

        return Panel(
            Group(*lines),
            border_style=status_color,
            padding=(0, 1),
        )

    def _render_current_task(self, status: RunStatus) -> Panel:
        """Render the current task panel."""
        if status.current_task_id:
            # Active task display
            content = Table.grid(padding=(0, 2))
            content.add_column(style="bold cyan", justify="right")
            content.add_column()

            content.add_row("Task:", status.current_task_id)
            if status.current_task_title:
                content.add_row("Title:", status.current_task_title)

            content.add_row(
                "Iteration:",
                f"{status.iteration.task_iteration}/{status.iteration.max_task_iteration}",
            )
            content.add_row(
                "Total:",
                f"{status.iteration.current}/{status.iteration.max}",
            )

            # Warning if nearing iteration limit
            warning = None
            if status.iteration.is_near_limit:
                warning = Text(
                    f"⚠️  Approaching iteration limit ({status.iteration.percentage:.0f}%)",
                    style="bold yellow",
                )

            panel_content: RenderableType = Group(content, warning) if warning else content
        else:
            # No active task
            panel_content = Text(
                "No active task",
                style="dim italic",
                justify="center",
            )

        return Panel(
            panel_content,
            title="[bold]Current Task[/bold]",
            border_style="blue",
            padding=(1, 2),
        )

    def _render_budget(self, status: RunStatus) -> Panel:
        """Render the budget panel with progress bars."""
        # Create progress display
        content: list[Text | Progress] = []

        # Task completion progress
        if status.tasks_total > 0:
            content.append(Text("Tasks", style="bold"))
            task_bar = self._create_progress_bar(
                completed=status.tasks_closed,
                total=status.tasks_total,
                label=f"{status.tasks_closed}/{status.tasks_total}",
            )
            content.append(task_bar)
            content.append(Text(f"{status.completion_percentage:.1f}% complete\n", style="dim"))

        # Token usage progress
        if status.budget.tokens_limit:
            content.append(Text("Tokens", style="bold"))
            token_bar = self._create_progress_bar(
                completed=status.budget.tokens_used,
                total=status.budget.tokens_limit,
                label=f"{status.budget.tokens_used:,}/{status.budget.tokens_limit:,}",
            )
            content.append(token_bar)
            if status.budget.tokens_percentage is not None:
                content.append(Text(f"{status.budget.tokens_percentage:.1f}% used\n", style="dim"))

        # Cost tracking
        if status.budget.cost_limit or status.budget.cost_usd > 0:
            content.append(Text("Cost", style="bold"))
            if status.budget.cost_limit:
                cost_bar = self._create_progress_bar(
                    completed=status.budget.cost_usd,
                    total=status.budget.cost_limit,
                    label=f"${status.budget.cost_usd:.2f}/${status.budget.cost_limit:.2f}",
                )
                content.append(cost_bar)
                if status.budget.cost_percentage is not None:
                    content.append(Text(f"{status.budget.cost_percentage:.1f}% spent", style="dim"))
            else:
                content.append(Text(f"${status.budget.cost_usd:.2f}", style="dim"))

        # Budget warning
        if status.budget.is_over_budget:
            content.append(Text("\n⚠️  Budget limit exceeded", style="bold red"))

        panel_content: RenderableType = (
            Group(*content) if content else Text("No budget limits set", style="dim italic")
        )

        return Panel(
            panel_content,
            title="[bold]Budget[/bold]",
            border_style="green" if not status.budget.is_over_budget else "red",
            padding=(1, 2),
        )

    def _render_activity_log(self, status: RunStatus) -> Panel:
        """Render the activity log panel with recent events."""
        # Get recent events (last 10)
        recent_events = status.events[-10:] if status.events else []

        if not recent_events:
            content: RenderableType = Text(
                "No activity yet",
                style="dim italic",
                justify="center",
            )
        else:
            # Build event table
            table = Table.grid(padding=(0, 1))
            table.add_column(style="dim", width=8)  # Timestamp
            table.add_column()  # Message

            for event in reversed(recent_events):  # Most recent first
                timestamp = event.timestamp.strftime("%H:%M:%S")
                message_style = self._get_event_style(event.level)

                # Add task ID prefix if present
                message = event.message
                if event.task_id:
                    message = f"[{event.task_id}] {message}"

                table.add_row(timestamp, Text(message, style=message_style))

            content = table

        return Panel(
            content,
            title="[bold]Recent Activity[/bold]",
            border_style="yellow",
            padding=(1, 2),
        )

    def _create_progress_bar(
        self, completed: int | float, total: int | float, label: str
    ) -> Progress:
        """Create a progress bar with label."""
        progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(bar_width=None),
            expand=True,
        )
        # Calculate percentage
        pct = (completed / total * 100) if total > 0 else 0
        progress.add_task(label, total=100, completed=int(pct))
        return progress

    def _get_status_color(self, phase: RunPhase) -> str:
        """Get color for run phase."""
        color_map = {
            RunPhase.INITIALIZING: "blue",
            RunPhase.RUNNING: "green",
            RunPhase.COMPLETED: "green",
            RunPhase.FAILED: "red",
            RunPhase.STOPPED: "yellow",
        }
        return color_map.get(phase, "white")

    def _get_event_style(self, level: EventLevel) -> str:
        """Get Rich style for event level."""
        style_map = {
            EventLevel.DEBUG: "dim",
            EventLevel.INFO: "",
            EventLevel.WARNING: "yellow",
            EventLevel.ERROR: "bold red",
        }
        return style_map.get(level, "")

    def start_live(self, status: RunStatus) -> Live:
        """
        Start a Live display that auto-refreshes.

        Args:
            status: Initial run status

        Returns:
            Live context manager for updating the display
        """
        layout = self.render(status)
        return Live(
            layout,
            console=self.console,
            refresh_per_second=1,
            screen=False,
        )
