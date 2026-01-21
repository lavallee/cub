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

from cub.core.status.models import EventLevel, RunPhase, RunStatus, TaskEntry, TaskState


class DashboardRenderer:
    """
    Render a live dashboard for cub run status using Rich.

    The dashboard displays:
    - Header: run type (epic/label), branch, task progress (X/Y)
    - Kanban board: To Do, Doing, Done columns with timestamps
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
            Layout(name="header", size=5),
            Layout(name="body"),
        )

        # Split body into kanban (main) and activity (bottom)
        layout["body"].split_column(
            Layout(name="kanban", ratio=2),
            Layout(name="activity", ratio=1),
        )

        # Split kanban into three columns: To Do, Doing, Done
        layout["kanban"].split_row(
            Layout(name="todo", ratio=1),
            Layout(name="doing", ratio=1),
            Layout(name="done", ratio=1),
        )

        # Populate panels
        layout["header"].update(self._render_header(status))
        layout["todo"].update(self._render_todo_panel(status))
        layout["doing"].update(self._render_doing_panel(status))
        layout["done"].update(self._render_done_panel(status))
        layout["activity"].update(self._render_activity_log(status))

        return layout

    def _render_header(self, status: RunStatus) -> Panel:
        """Render the header panel with run context and progress."""
        status_color = self._get_status_color(status.phase)

        # Build run type line
        run_type_parts = []
        if status.epic:
            run_type_parts.append(f"--epic {status.epic}")
        if status.label:
            run_type_parts.append(f"--label {status.label}")
        run_type = "  ".join(run_type_parts) if run_type_parts else "all tasks"

        # Build branch line
        branch_display = status.branch or status.session_name or "unknown"

        # Build progress line (X/Y format)
        progress_str = f"{status.tasks_closed}/{status.tasks_total}"

        # Status indicator
        status_text = Text()
        status_text.append("Status: ", style="bold")
        status_text.append(status.phase.value.upper(), style=f"bold {status_color}")

        # Build header content as a grid
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan", justify="right", width=10)
        grid.add_column()

        grid.add_row("Run:", run_type)
        grid.add_row("Branch:", branch_display)
        grid.add_row("Progress:", f"{progress_str} tasks completed")

        return Panel(
            Group(
                Text("CUB MONITOR", style="bold cyan", justify="center"),
                Text(""),
                grid,
                status_text,
            ),
            border_style=status_color,
            padding=(0, 1),
        )

    def _render_todo_panel(self, status: RunStatus) -> Panel:
        """Render the To Do column with pending tasks."""
        todo_tasks = status.get_tasks_by_state(TaskState.TODO)

        if not todo_tasks:
            content: RenderableType = Text(
                "No pending tasks",
                style="dim italic",
                justify="center",
            )
        else:
            content = self._render_task_list(todo_tasks, show_started=False)

        return Panel(
            content,
            title=f"[bold]To Do[/bold] ({len(todo_tasks)})",
            border_style="blue",
            padding=(0, 1),
        )

    def _render_doing_panel(self, status: RunStatus) -> Panel:
        """Render the Doing column with in-progress tasks."""
        doing_tasks = status.get_tasks_by_state(TaskState.DOING)

        if not doing_tasks:
            # Fall back to current_task_id if task_entries not populated
            if status.current_task_id:
                content: RenderableType = self._render_current_task_fallback(status)
            else:
                content = Text(
                    "No active task",
                    style="dim italic",
                    justify="center",
                )
        else:
            content = self._render_task_list(doing_tasks, show_started=True)

        doing_count = len(doing_tasks) or (1 if status.current_task_id else 0)
        return Panel(
            content,
            title=f"[bold]Doing[/bold] ({doing_count})",
            border_style="yellow",
            padding=(0, 1),
        )

    def _render_done_panel(self, status: RunStatus) -> Panel:
        """Render the Done column with completed tasks."""
        done_tasks = status.get_tasks_by_state(TaskState.DONE)

        if not done_tasks:
            content: RenderableType = Text(
                "No completed tasks",
                style="dim italic",
                justify="center",
            )
        else:
            # Show most recent completed tasks first, limit to 10
            content = self._render_task_list(
                list(reversed(done_tasks))[:10], show_completed=True
            )

        return Panel(
            content,
            title=f"[bold]Done[/bold] ({len(done_tasks)})",
            border_style="green",
            padding=(0, 1),
        )

    def _render_task_list(
        self,
        tasks: list[TaskEntry],
        show_started: bool = False,
        show_completed: bool = False,
    ) -> Table:
        """
        Render a list of tasks as a table.

        Args:
            tasks: List of TaskEntry objects
            show_started: Show started_at timestamp
            show_completed: Show completed_at timestamp

        Returns:
            Rich Table with task information
        """
        table = Table.grid(padding=(0, 1))
        table.add_column(style="cyan", width=12)  # Task ID
        table.add_column()  # Title
        if show_started or show_completed:
            table.add_column(style="dim", width=10)  # Timestamp

        for task in tasks:
            row: list[str | Text] = [
                task.task_id[:12],  # Truncate long IDs
                Text(task.title[:40] + ("..." if len(task.title) > 40 else "")),
            ]

            if show_started and task.started_at:
                row.append(task.started_at.strftime("%H:%M:%S"))
            elif show_completed and task.completed_at:
                row.append(task.completed_at.strftime("%H:%M:%S"))
            elif show_started or show_completed:
                row.append("")

            table.add_row(*row)

        return table

    def _render_current_task_fallback(self, status: RunStatus) -> RenderableType:
        """
        Render current task info when task_entries is not populated.

        Used for backward compatibility when task_entries list is empty.
        """
        content = Table.grid(padding=(0, 2))
        content.add_column(style="bold cyan", justify="right")
        content.add_column()

        content.add_row("Task:", status.current_task_id or "")
        if status.current_task_title:
            title_display = status.current_task_title
            if len(title_display) > 35:
                title_display = title_display[:35] + "..."
            content.add_row("Title:", title_display)

        content.add_row(
            "Iter:",
            f"{status.iteration.task_iteration}/{status.iteration.max_task_iteration}",
        )

        # Warning if nearing iteration limit
        warning = None
        if status.iteration.is_near_limit:
            warning = Text(
                f"Near limit ({status.iteration.percentage:.0f}%)",
                style="bold yellow",
            )

        return Group(content, warning) if warning else content

    def _render_activity_log(self, status: RunStatus) -> Panel:
        """Render the activity log panel with recent events."""
        # Get recent events (last 8 for compact display)
        recent_events = status.events[-8:] if status.events else []

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

                # Truncate long messages
                if len(message) > 60:
                    message = message[:60] + "..."

                table.add_row(timestamp, Text(message, style=message_style))

            content = table

        return Panel(
            content,
            title="[bold]Recent Activity[/bold]",
            border_style="magenta",
            padding=(0, 1),
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
