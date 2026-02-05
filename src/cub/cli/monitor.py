"""
Cub CLI - Monitor command.

Display live dashboard for an active cub run, with real-time
progress on beads tasks.
"""

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from cub.core.status.writer import list_runs
from cub.dashboard.renderer import DashboardRenderer
from cub.dashboard.status import StatusWatcher

app = typer.Typer(
    name="monitor",
    help="Display live dashboard for cub run progress",
    no_args_is_help=False,
)

console = Console()


def _find_active_run(project_dir: Path) -> tuple[str, Path] | None:
    """
    Find the most recent active (or latest) run's status.json.

    Resolution order:
    1. Most recent status.json in .cub/ledger/by-run/ that is still active
    2. Most recent status.json in .cub/ledger/by-run/ (any phase)

    Args:
        project_dir: Project root directory

    Returns:
        Tuple of (run_id, status_path) or None if no runs found
    """
    import json

    # Scan .cub/ledger/by-run/ for the most recent active run
    runs_dir = project_dir / ".cub" / "ledger" / "by-run"
    if not runs_dir.exists():
        return None

    status_files = list(runs_dir.glob("*/status.json"))
    if not status_files:
        return None

    # Sort by modification time (most recent first)
    status_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Prefer an active (running/initializing) run
    for sf in status_files:
        try:
            with sf.open() as f:
                data = json.load(f)
            phase = data.get("phase", "")
            if phase in ("running", "initializing"):
                run_id = data.get("run_id", sf.parent.name)
                return (run_id, sf)
        except (json.JSONDecodeError, OSError):
            continue

    # Fall back to most recent run regardless of phase
    for sf in status_files:
        try:
            with sf.open() as f:
                data = json.load(f)
            run_id = data.get("run_id", sf.parent.name)
            return (run_id, sf)
        except (json.JSONDecodeError, OSError):
            continue

    return None


@app.callback(invoke_without_command=True)
def monitor(
    ctx: typer.Context,
    session_id: str | None = typer.Argument(
        None,
        help="Run ID to monitor (auto-detects active run if not specified)",
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
        help="Show list of all runs",
    ),
) -> None:
    """
    Display live dashboard for an active cub run.

    Monitors the status file for a run and displays a live dashboard
    with real-time updates including:
    - Current task and iteration progress
    - Kanban board (To Do / Doing / Done)
    - Budget usage (tokens, cost, tasks)
    - Recent activity log

    If no run ID is provided, automatically attaches to the most
    recent active run.

    Examples:
        cub monitor                        # Monitor active run
        cub monitor cub-20260115-123456    # Monitor specific run
        cub monitor --refresh 0.5          # Faster refresh rate
        cub monitor --list                 # Show all runs
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Handle --list option
    if list_sessions:
        _show_runs(project_dir, debug)
        return

    # Resolve which run to monitor
    if session_id:
        # Explicit run ID provided
        status_path = project_dir / ".cub" / "ledger" / "by-run" / session_id / "status.json"
        run_id = session_id
    else:
        # Auto-detect active run
        result = _find_active_run(project_dir)
        if result is None:
            console.print(
                "[yellow]No runs found.[/yellow]\n"
                "Start a run with:\n"
                "  cub run\n\n"
                "Or list past runs:\n"
                "  cub monitor --list"
            )
            raise typer.Exit(1)
        run_id, status_path = result
        if debug:
            console.print(f"[dim]Auto-detected run: {run_id}[/dim]")

    if debug:
        console.print(f"[dim]Project: {project_dir}[/dim]")
        console.print(f"[dim]Status file: {status_path}[/dim]")
        console.print(f"[dim]Refresh interval: {refresh}s[/dim]")
        console.print()

    # Check if status file exists (wait up to 10s for it to appear)
    if not status_path.exists():
        console.print("[yellow]Waiting for run to start...[/yellow]")
        wait_start = time.time()
        max_wait = 10.0

        while not status_path.exists():
            if time.time() - wait_start > max_wait:
                console.print(
                    f"[red]Error: Status file not found: {status_path}[/red]\n"
                    f"Run '{run_id}' may not exist or hasn't started yet.\n"
                    "Check available runs:\n"
                    "  cub monitor --list"
                )
                raise typer.Exit(1)
            time.sleep(0.5)

    # Display run info header
    _display_run_info(status_path, console, debug)

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
    console.print(f"[bold]Monitoring run: {run_id}[/bold]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    try:
        with Live(
            renderer.render(status),
            console=console,
            refresh_per_second=1 / refresh,
            screen=False,
        ) as live:
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

                # Sleep for poll interval
                time.sleep(refresh)

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user[/yellow]")
        raise typer.Exit(0)

    # Display completion message
    console.print()
    if status.phase.value == "completed":
        console.print("[green]Run completed successfully[/green]")
    elif status.phase.value == "failed":
        console.print("[red]Run failed[/red]")
    elif status.phase.value == "stopped":
        console.print("[yellow]Run stopped[/yellow]")

    if debug:
        console.print(f"[dim]Final phase: {status.phase.value}[/dim]")

    raise typer.Exit(0)


def _display_run_info(status_path: Path, console: Console, debug: bool = False) -> None:
    """
    Display run information header from status.json.

    Args:
        status_path: Path to the status.json file
        console: Rich console for output
        debug: Enable debug output
    """
    import json

    try:
        with status_path.open() as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        if debug:
            console.print(f"[dim]Could not read run info: {e}[/dim]")
        return

    # Build info table
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold cyan")
    info_table.add_column()

    run_id = data.get("run_id", "unknown")
    phase = data.get("phase", "unknown")
    session_name = data.get("session_name", "")
    branch = data.get("branch", "")

    info_table.add_row("Run ID:", run_id)
    if session_name:
        info_table.add_row("Session:", session_name)
    if branch:
        info_table.add_row("Branch:", branch)
    info_table.add_row("Phase:", f"[yellow]{phase}[/yellow]")

    # Task counts
    tasks_closed = data.get("tasks_closed", 0)
    tasks_total = data.get("tasks_total", 0)
    if tasks_total > 0:
        info_table.add_row("Progress:", f"{tasks_closed}/{tasks_total} tasks")

    # Budget info
    budget = data.get("budget", {})
    tokens_used = budget.get("tokens_used", 0)
    tokens_limit = budget.get("tokens_limit")
    cost_usd = budget.get("cost_usd", 0.0)
    cost_limit = budget.get("cost_limit")

    if tokens_limit and tokens_limit > 0:
        pct = (tokens_used / tokens_limit) * 100
        info_table.add_row(
            "Token Budget:",
            f"{tokens_used:,} / {tokens_limit:,} ({pct:.1f}%)",
        )
    elif tokens_used > 0:
        info_table.add_row("Tokens Used:", f"{tokens_used:,}")

    if cost_limit and cost_limit > 0:
        pct = (cost_usd / cost_limit) * 100
        info_table.add_row(
            "Cost Budget:",
            f"${cost_usd:.4f} / ${cost_limit:.2f} ({pct:.1f}%)",
        )
    elif cost_usd > 0:
        info_table.add_row("Cost:", f"${cost_usd:.4f}")

    # Display in a panel
    panel = Panel(info_table, title="[bold]Run Info[/bold]", border_style="cyan")
    console.print(panel)
    console.print()


def _show_runs(project_dir: Path, debug: bool = False) -> None:
    """
    Show list of all runs.

    Args:
        project_dir: Project root directory
        debug: Enable debug output
    """
    runs = list_runs(project_dir)

    if not runs:
        console.print("[yellow]No runs found[/yellow]")
        return

    # Create table
    table = Table(title="Runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Session", style="green")
    table.add_column("Phase", style="yellow")
    table.add_column("Tasks Done", style="magenta")

    for run in runs:
        phase = run.get("phase", "unknown")
        # Color phase based on state
        if phase == "completed":
            phase_colored = f"[green]{phase}[/green]"
        elif phase in ("running", "initializing"):
            phase_colored = f"[yellow]{phase}[/yellow]"
        elif phase == "failed":
            phase_colored = f"[red]{phase}[/red]"
        else:
            phase_colored = phase

        table.add_row(
            run.get("run_id", "unknown"),
            run.get("session_name", ""),
            phase_colored,
            str(run.get("tasks_completed", 0)),
        )

    console.print(table)

    if debug:
        console.print(f"[dim]Found {len(runs)} runs[/dim]")


__all__ = ["app"]
