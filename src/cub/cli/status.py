"""
Cub CLI - Status command.

Show current session status, task progress, and budget usage.
"""

import json as json_module
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.tasks.backend import get_backend

app = typer.Typer(
    name="status",
    help="Show current session status",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def status(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed status",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output status as JSON",
    ),
    session: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Show status for specific session ID",
    ),
) -> None:
    """
    Show current session status.

    Displays information about the current or specified session including:
    - Task progress summary
    - Ready and blocked tasks
    - Budget usage
    - Recent activity

    Examples:
        cub status                      # Show current session
        cub status --verbose            # Show detailed status
        cub status --json               # JSON output
        cub status --session abc123     # Specific session
    """
    debug = ctx.obj.get("debug", False)

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Verbose: {verbose}[/dim]")
        console.print(f"[dim]JSON output: {json_output}[/dim]")
        console.print(f"[dim]Session: {session or 'current'}[/dim]")

    try:
        # Get the task backend (auto-detects beads or json)
        backend = get_backend()

        # Get task counts
        counts = backend.get_task_counts()

        # Get ready and blocked tasks
        ready_tasks = backend.get_ready_tasks()
        all_tasks = backend.list_tasks()

        # Count blocked tasks (tasks that are open but have unmet dependencies)
        blocked_count = 0
        for task in all_tasks:
            if task.status.value == "open" and len(task.depends_on) > 0:
                blocked_count += 1

        if json_output:
            # Output machine-readable JSON
            output = {
                "task_counts": {
                    "total": counts.total,
                    "open": counts.open,
                    "in_progress": counts.in_progress,
                    "closed": counts.closed,
                    "completion_percentage": counts.completion_percentage,
                },
                "ready_tasks": len(ready_tasks),
                "blocked_tasks": blocked_count,
            }
            console.print(json_module.dumps(output, indent=2))
            raise typer.Exit(0)

        # Display human-readable status
        # Task summary table
        summary_table = Table(title="Task Progress Summary", show_header=False)
        summary_table.add_column("Label", style="cyan")
        summary_table.add_column("Count", style="green", justify="right")

        summary_table.add_row("Total Tasks", str(counts.total))
        summary_table.add_row("Closed", f"[green]{counts.closed}[/green]")
        summary_table.add_row("In Progress", f"[yellow]{counts.in_progress}[/yellow]")
        summary_table.add_row("Open", str(counts.open))
        summary_table.add_row(
            "Completion",
            f"[cyan]{counts.completion_percentage:.1f}%[/cyan]"
        )

        console.print(summary_table)
        console.print()

        # Ready and blocked summary
        availability_table = Table(title="Task Availability", show_header=False)
        availability_table.add_column("Status", style="cyan")
        availability_table.add_column("Count", style="green", justify="right")

        availability_table.add_row("Ready to work", f"[green]{len(ready_tasks)}[/green]")
        availability_table.add_row("Blocked by dependencies", str(blocked_count))

        console.print(availability_table)

        if verbose and ready_tasks:
            console.print()
            console.print("[bold cyan]Top Ready Tasks:[/bold cyan]")
            ready_table = Table(show_header=True)
            ready_table.add_column("ID", style="cyan")
            ready_table.add_column("Title", style="green")
            ready_table.add_column("Priority", style="yellow")

            for task in ready_tasks[:5]:
                ready_table.add_row(task.id, task.title, task.priority.value)

            console.print(ready_table)

        raise typer.Exit(0)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


__all__ = ["app"]
