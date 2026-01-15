"""
Cub CLI - Monitor command.

Display live dashboard for an active cub run session.
"""

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live

from cub.dashboard.renderer import DashboardRenderer
from cub.dashboard.status import StatusWatcher

app = typer.Typer(
    name="monitor",
    help="Display live dashboard for cub run session",
    no_args_is_help=True,
)

console = Console()


@app.callback(invoke_without_command=True)
def monitor(
    ctx: typer.Context,
    session_id: str = typer.Argument(
        ...,
        help="Session ID or run ID to monitor",
    ),
    refresh: float = typer.Option(
        1.0,
        "--refresh",
        "-r",
        help="Dashboard refresh interval in seconds",
        min=0.1,
        max=10.0,
    ),
) -> None:
    """
    Display live dashboard for an active cub run session.

    Monitors the status file for the specified session and displays
    a live dashboard with real-time updates including:
    - Current task and iteration progress
    - Budget usage (tokens, cost, tasks)
    - Recent activity log

    Examples:
        cub monitor cub-20260115-123456    # Monitor specific session
        cub monitor --refresh 0.5          # Faster refresh rate
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

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
            while True:
                # Poll for updates
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


__all__ = ["app"]
