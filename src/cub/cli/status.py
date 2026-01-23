"""
Cub CLI - Status command.

Show current session status, task progress, and budget usage.
"""

import json as json_module
from typing import TypedDict

import typer
from rich.console import Console
from rich.table import Table

from cub.core.status.writer import StatusWriter, get_latest_status
from cub.core.tasks.backend import get_backend
from cub.utils.project import get_project_root


class TaskCost(TypedDict):
    """Type definition for task cost data."""

    task_id: str
    title: str
    cost: float
    tokens: int
    status: str

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
        help="Show status for specific session/run ID",
    ),
) -> None:
    """
    Show current session status.

    Displays information about the current or specified session including:
    - Task progress summary
    - Ready and blocked tasks
    - Budget usage and cost breakdown
    - Recent activity

    Examples:
        cub status                      # Show current session
        cub status --verbose            # Show detailed status with per-task cost
        cub status --json               # JSON output
        cub status --session abc123     # Specific session/run
    """
    debug = ctx.obj.get("debug", False)

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Verbose: {verbose}[/dim]")
        console.print(f"[dim]JSON output: {json_output}[/dim]")
        console.print(f"[dim]Session: {session or 'current'}[/dim]")

    try:
        # Get project root
        project_dir = get_project_root()

        # Load run status (from persisted data or latest)
        run_status = None
        writer = None

        if session:
            # Load specific session
            writer = StatusWriter(project_dir, session)
            run_status = writer.read()
            if not run_status:
                console.print(f"[red]Error: Session '{session}' not found[/red]")
                raise typer.Exit(1)
        else:
            # Load latest run status
            run_status = get_latest_status(project_dir)
            if run_status:
                writer = StatusWriter(project_dir, run_status.run_id)

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

        # Load cost data from persisted artifacts if available
        total_cost = 0.0
        total_tokens = 0
        task_costs: list[TaskCost] = []

        if writer:
            # Load run artifact for aggregate costs
            run_artifact = writer.read_run_artifact()
            if run_artifact and run_artifact.budget:
                total_cost = run_artifact.budget.cost_usd
                total_tokens = run_artifact.budget.tokens_used

            # Load task artifacts for per-task costs
            task_artifacts = writer.list_task_artifacts()
            for artifact in task_artifacts:
                if artifact.usage and artifact.usage.cost_usd:
                    task_cost: TaskCost = {
                        "task_id": artifact.task_id,
                        "title": artifact.title,
                        "cost": artifact.usage.cost_usd,
                        "tokens": artifact.usage.total_tokens,
                        "status": artifact.status,
                    }
                    task_costs.append(task_cost)

        # Use in-memory data if available (for active runs)
        if run_status:
            # Override with in-memory data if it's more recent
            if run_status.budget.cost_usd > total_cost:
                total_cost = run_status.budget.cost_usd
            if run_status.budget.tokens_used > total_tokens:
                total_tokens = run_status.budget.tokens_used

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
                "budget": {
                    "total_cost_usd": total_cost,
                    "total_tokens": total_tokens,
                    "tasks_with_cost": len(task_costs),
                },
                "task_costs": task_costs if verbose else None,
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
        summary_table.add_row("Completion", f"[cyan]{counts.completion_percentage:.1f}%[/cyan]")

        console.print(summary_table)
        console.print()

        # Ready and blocked summary
        availability_table = Table(title="Task Availability", show_header=False)
        availability_table.add_column("Status", style="cyan")
        availability_table.add_column("Count", style="green", justify="right")

        availability_table.add_row("Ready to work", f"[green]{len(ready_tasks)}[/green]")
        availability_table.add_row("Blocked by dependencies", str(blocked_count))

        console.print(availability_table)
        console.print()

        # Budget and cost summary
        budget_table = Table(title="Budget & Cost Summary", show_header=False)
        budget_table.add_column("Metric", style="cyan")
        budget_table.add_column("Value", style="green", justify="right")

        budget_table.add_row("Total Cost", f"${total_cost:.4f}" if total_cost > 0 else "$0.0000")
        budget_table.add_row("Total Tokens", f"{total_tokens:,}")
        if task_costs:
            budget_table.add_row("Tasks with Cost Data", str(len(task_costs)))

        console.print(budget_table)

        if verbose and task_costs:
            console.print()
            console.print("[bold cyan]Per-Task Cost Breakdown:[/bold cyan]")
            cost_table = Table(show_header=True)
            cost_table.add_column("Task ID", style="cyan")
            cost_table.add_column("Title", style="white", max_width=40)
            cost_table.add_column("Status", style="yellow")
            cost_table.add_column("Tokens", style="blue", justify="right")
            cost_table.add_column("Cost", style="green", justify="right")

            # Sort by cost (highest first)
            sorted_costs = sorted(task_costs, key=lambda x: x["cost"], reverse=True)

            for task_cost in sorted_costs:
                # Truncate title if too long
                title = task_cost["title"]
                display_title = title[:37] + "..." if len(title) > 40 else title

                cost_table.add_row(
                    task_cost["task_id"],
                    display_title,
                    task_cost["status"],
                    f"{task_cost['tokens']:,}",
                    f"${task_cost['cost']:.4f}",
                )

            console.print(cost_table)

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
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


__all__ = ["app"]
