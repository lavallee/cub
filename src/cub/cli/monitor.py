"""
Cub CLI - Monitor command.

Display live dashboard for an active cub run session.
"""

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from cub.core.session.manager import RunSessionManager
from cub.core.session.models import RunSession
from cub.core.status.writer import list_runs
from cub.dashboard.renderer import DashboardRenderer
from cub.dashboard.status import StatusWatcher

app = typer.Typer(
    name="monitor",
    help="Display live dashboard for cub run session",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def monitor(
    ctx: typer.Context,
    session_id: str | None = typer.Argument(
        None,
        help="Session ID or run ID to monitor (auto-detects latest if not specified)",
    ),
    refresh: float = typer.Option(
        1.0,
        "--refresh",
        "-r",
        help="Dashboard refresh interval in seconds",
        min=0.1,
        max=10.0,
    ),
    list_sessions: bool = typer.Option(
        False,
        "--list",
        help="Show list of running sessions",
    ),
) -> None:
    """
    Display live dashboard for an active cub run session.

    Monitors the status file for the specified session and displays
    a live dashboard with real-time updates including:
    - Current task and iteration progress
    - Budget usage (tokens, cost, tasks)
    - Recent activity log

    If no session ID is provided, automatically attaches to the most recent session.

    Examples:
        cub monitor                        # Monitor latest session
        cub monitor cub-20260115-123456    # Monitor specific session
        cub monitor --refresh 0.5          # Faster refresh rate
        cub monitor --list                 # Show running sessions
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()
    cub_dir = project_dir / ".cub"

    # Initialize session manager
    session_manager = RunSessionManager(cub_dir)

    # Handle --list option
    if list_sessions:
        _show_running_sessions(project_dir, debug)
        return

    # Auto-detect session ID if not provided
    if not session_id:
        # Try to get active session via symlink
        active_session = session_manager.get_active_session()

        if not active_session:
            console.print(
                "[red]Error: No active session found[/red]\nStart a session with:\n  cub run"
            )
            raise typer.Exit(1)

        session_id = active_session.run_id
        if debug:
            console.print(f"[dim]Auto-detected session: {session_id}[/dim]")

    # Construct status file path
    status_path = project_dir / ".cub" / "runs" / session_id / "status.json"

    if debug:
        console.print(f"[dim]Project: {project_dir}[/dim]")
        console.print(f"[dim]Status file: {status_path}[/dim]")
        console.print(f"[dim]Refresh interval: {refresh}s[/dim]")
        console.print()

    # Check if status file exists
    if not status_path.exists():
        # Wait for status file to be created (up to 10 seconds)
        console.print("[yellow]Waiting for session to start...[/yellow]")
        wait_start = time.time()
        max_wait = 10.0

        while not status_path.exists():
            if time.time() - wait_start > max_wait:
                console.print(
                    f"[red]Error: Status file not found: {status_path}[/red]\n"
                    f"Session '{session_id}' may not exist or hasn't started yet.\n"
                    "Check available sessions:\n"
                    "  cub status --list-sessions"
                )
                raise typer.Exit(1)
            time.sleep(0.5)

    # Display session info header
    try:
        session = session_manager._read_session_file(session_id)
        _display_session_info(session, console)
    except Exception as e:
        if debug:
            console.print(f"[dim]Could not read session info: {e}[/dim]")

    # Initialize dashboard components
    renderer = DashboardRenderer(console=console)
    watcher = StatusWatcher(
        status_path=status_path,
        poll_interval=refresh,
    )

    # Initial poll to get starting status
    status = watcher.poll()
    if status is None:
        console.print(
            f"[red]Error: Failed to read status file: {status_path}[/red]\n"
            "The file may be corrupted or still being written."
        )
        raise typer.Exit(1)

    # Start live display
    console.print(f"[bold]Monitoring session: {session_id}[/bold]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    try:
        with Live(
            renderer.render(status),
            console=console,
            refresh_per_second=1 / refresh,
            screen=False,
        ) as live:
            last_session_check = time.time()
            session_check_interval = 5.0  # Check session file every 5 seconds

            while True:
                # Poll for status updates
                new_status = watcher.poll()

                if new_status is not None:
                    # Update display
                    live.update(renderer.render(new_status))
                    status = new_status

                    # Check if run has completed
                    if status.is_finished:
                        # Give a moment for final update to be visible
                        time.sleep(2)
                        break

                # Periodically refresh session data (for budget/task updates)
                current_time = time.time()
                if current_time - last_session_check >= session_check_interval:
                    try:
                        session = session_manager._read_session_file(session_id)
                        # Session data is read but not displayed in live view
                        # (could be used to detect orphaned status or budget exceeded)
                        if session.is_orphaned:
                            console.print("\n[red]Session was orphaned[/red]")
                            break
                        last_session_check = current_time
                    except Exception:
                        # Ignore errors reading session file during monitoring
                        pass

                # Sleep for poll interval
                time.sleep(refresh)

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user[/yellow]")
        raise typer.Exit(0)

    # Display completion message
    console.print()
    if status.phase.value == "completed":
        console.print("[green]Session completed successfully[/green]")
    elif status.phase.value == "failed":
        console.print("[red]Session failed[/red]")
    elif status.phase.value == "stopped":
        console.print("[yellow]Session stopped[/yellow]")

    if debug:
        console.print(f"[dim]Final phase: {status.phase.value}[/dim]")

    raise typer.Exit(0)


def _display_session_info(session: RunSession, console: Console) -> None:
    """
    Display session information header.

    Args:
        session: RunSession to display
        console: Rich console for output
    """

    # Build session info table
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold cyan")
    info_table.add_column()

    info_table.add_row("Run ID:", session.run_id)
    info_table.add_row("Harness:", session.harness)
    info_table.add_row("Status:", f"[yellow]{session.status.value}[/yellow]")
    info_table.add_row("Tasks Completed:", str(session.tasks_completed))
    info_table.add_row("Tasks Failed:", str(session.tasks_failed))

    # Budget info
    budget = session.budget
    if budget.tokens_limit > 0:
        tokens_pct = (budget.tokens_used / budget.tokens_limit) * 100
        info_table.add_row(
            "Token Budget:",
            f"{budget.tokens_used:,} / {budget.tokens_limit:,} ({tokens_pct:.1f}%)",
        )
    else:
        info_table.add_row("Tokens Used:", f"{budget.tokens_used:,}")

    if budget.cost_limit > 0:
        cost_pct = (budget.cost_usd / budget.cost_limit) * 100
        info_table.add_row(
            "Cost Budget:", f"${budget.cost_usd:.4f} / ${budget.cost_limit:.2f} ({cost_pct:.1f}%)"
        )
    else:
        info_table.add_row("Cost:", f"${budget.cost_usd:.4f}")

    # Display in a panel
    panel = Panel(info_table, title="[bold]Session Info[/bold]", border_style="cyan")
    console.print(panel)
    console.print()


def _show_running_sessions(project_dir: Path, debug: bool = False) -> None:
    """
    Show list of running sessions.

    Args:
        project_dir: Project root directory
        debug: Enable debug output
    """
    runs = list_runs(project_dir)

    if not runs:
        console.print("[yellow]No sessions found[/yellow]")
        return

    # Create table
    table = Table(title="Running Sessions")
    table.add_column("Run ID", style="cyan")
    table.add_column("Session Name", style="green")
    table.add_column("Phase", style="yellow")
    table.add_column("Tasks Done", style="magenta")

    for run in runs:
        phase = run.get("phase", "unknown")
        # Color phase based on state
        if phase == "completed":
            phase_colored = f"[green]{phase}[/green]"
        elif phase == "running":
            phase_colored = f"[yellow]{phase}[/yellow]"
        elif phase == "failed":
            phase_colored = f"[red]{phase}[/red]"
        else:
            phase_colored = phase

        table.add_row(
            run.get("run_id", "unknown"),
            run.get("session_name", "unknown"),
            phase_colored,
            str(run.get("tasks_completed", 0)),
        )

    console.print(table)

    if debug:
        console.print(f"[dim]Found {len(runs)} sessions[/dim]")


__all__ = ["app"]
