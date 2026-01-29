"""
Cub CLI - Status command.

Show current session status, task progress, and budget usage.
"""

import json as json_module
from typing import TypedDict

import typer
from rich.console import Console
from rich.table import Table

from cub.core.services.status import StatusService
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
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly markdown format",
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
        cub status --agent              # Agent-friendly markdown output
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

        # Use StatusService for project-level metrics
        status_service = StatusService.from_project_dir(project_dir)
        project_stats = status_service.summary()

        # Get the task backend for ready tasks list
        backend = get_backend()
        ready_tasks = backend.get_ready_tasks()

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

        # --agent wins over --json
        if agent:
            try:
                from cub.core.services.agent_format import AgentFormatter

                output = AgentFormatter.format_status(project_stats)
                console.print(output)
            except ImportError:
                # Fallback to simple markdown if AgentFormatter not available
                total = project_stats.total_tasks
                closed = project_stats.closed_tasks
                in_prog = project_stats.in_progress_tasks
                open_count = project_stats.open_tasks
                blocked = project_stats.blocked_tasks
                ready = project_stats.ready_tasks
                pct = project_stats.completion_percentage

                console.print("# cub status\n")
                console.print(
                    f"{total} tasks: {closed} closed ({pct:.0f}%), "
                    f"{in_prog} in progress, {open_count} open. "
                    f"{blocked} blocked, {ready} ready.\n"
                )
                console.print("## Breakdown\n")
                console.print("| Status | Count | Pct |")
                console.print("|--------|-------|-----|")
                if total > 0:
                    closed_pct = (closed / total) * 100
                    in_prog_pct = (in_prog / total) * 100
                    ready_pct = (ready / total) * 100
                    blocked_pct = (blocked / total) * 100
                    console.print(f"| Closed | {closed} | {closed_pct:.0f}% |")
                    console.print(f"| In Progress | {in_prog} | {in_prog_pct:.0f}% |")
                    console.print(f"| Ready | {ready} | {ready_pct:.0f}% |")
                    console.print(f"| Blocked | {blocked} | {blocked_pct:.0f}% |")
                else:
                    console.print("| No tasks | 0 | 0% |")
            raise typer.Exit(0)

        if json_output:
            # Output machine-readable JSON
            json_output_dict = {
                "task_counts": {
                    "total": project_stats.total_tasks,
                    "open": project_stats.open_tasks,
                    "in_progress": project_stats.in_progress_tasks,
                    "closed": project_stats.closed_tasks,
                    "completion_percentage": project_stats.completion_percentage,
                },
                "ready_tasks": project_stats.ready_tasks,
                "blocked_tasks": project_stats.blocked_tasks,
                "budget": {
                    "total_cost_usd": total_cost,
                    "total_tokens": total_tokens,
                    "tasks_with_cost": len(task_costs),
                },
                "ledger": {
                    "total_cost_usd": project_stats.total_cost_usd,
                    "total_tokens": project_stats.total_tokens,
                    "tasks_in_ledger": project_stats.tasks_in_ledger,
                },
                "git": {
                    "current_branch": project_stats.current_branch,
                    "has_uncommitted_changes": project_stats.has_uncommitted_changes,
                    "commits_since_main": project_stats.commits_since_main,
                },
                "task_costs": task_costs if verbose else None,
            }
            console.print(json_module.dumps(json_output_dict, indent=2))
            raise typer.Exit(0)

        # Display human-readable status
        # Task summary table
        summary_table = Table(title="Task Progress Summary", show_header=False)
        summary_table.add_column("Label", style="cyan")
        summary_table.add_column("Count", style="green", justify="right")

        summary_table.add_row("Total Tasks", str(project_stats.total_tasks))
        summary_table.add_row("Closed", f"[green]{project_stats.closed_tasks}[/green]")
        summary_table.add_row("In Progress", f"[yellow]{project_stats.in_progress_tasks}[/yellow]")
        summary_table.add_row("Open", str(project_stats.open_tasks))
        completion_pct = f"[cyan]{project_stats.completion_percentage:.1f}%[/cyan]"
        summary_table.add_row("Completion", completion_pct)

        console.print(summary_table)
        console.print()

        # Ready and blocked summary
        availability_table = Table(title="Task Availability", show_header=False)
        availability_table.add_column("Status", style="cyan")
        availability_table.add_column("Count", style="green", justify="right")

        availability_table.add_row("Ready to work", f"[green]{project_stats.ready_tasks}[/green]")
        availability_table.add_row("Blocked by dependencies", str(project_stats.blocked_tasks))

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

    except typer.Exit:
        # Re-raise exit signals without modification
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


__all__ = ["app"]
