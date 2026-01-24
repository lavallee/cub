"""
Cub CLI - Workflow commands.

Manage post-completion workflow stages for tasks and epics.
Stages progress: needs_review -> validated -> released
"""

import typer
from rich.console import Console
from rich.table import Table

from cub.core.ledger.models import WorkflowStage
from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.writer import LedgerWriter
from cub.utils.project import get_project_root

app = typer.Typer(
    name="workflow",
    help="Manage post-completion workflow stages",
    no_args_is_help=True,
)

console = Console()


def _get_ledger_paths() -> tuple[LedgerReader, LedgerWriter]:
    """Get ledger reader and writer for current project."""
    project_root = get_project_root()
    ledger_dir = project_root / ".cub" / "ledger"
    return LedgerReader(ledger_dir), LedgerWriter(ledger_dir)


def _format_workflow_stage(stage: str | None) -> str:
    """Format workflow stage with color."""
    if stage is None:
        return "[dim]none[/dim]"
    stage_colors = {
        "needs_review": "[yellow]needs_review[/yellow]",
        "validated": "[blue]validated[/blue]",
        "released": "[green]released[/green]",
    }
    return stage_colors.get(stage, stage)


@app.command("set")
def set_stage(
    task_id: str = typer.Argument(..., help="Task ID to update"),
    stage: str = typer.Option(
        ...,
        "--stage",
        "-s",
        help="Workflow stage (needs_review, validated, or released)",
    ),
) -> None:
    """
    Set workflow stage for a completed task.

    Updates the post-completion workflow stage for a task that has a ledger entry.
    Stages must be one of: needs_review, validated, released

    Examples:
        cub workflow set cub-abc --stage needs_review
        cub workflow set cub-abc -s validated
        cub workflow set cub-abc --stage released
    """
    # Validate stage
    try:
        workflow_stage = WorkflowStage(stage)
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid stage: {stage}")
        console.print("Valid stages: needs_review, validated, released")
        raise typer.Exit(1)

    reader, writer = _get_ledger_paths()

    if not reader.exists():
        console.print(
            "[red]Error:[/red] No ledger found. "
            "Tasks must be completed before setting workflow stage."
        )
        raise typer.Exit(1)

    # Check if task exists in ledger
    entry = reader.get_task(task_id)
    if not entry:
        console.print(f"[red]Error:[/red] Task '{task_id}' not found in ledger")
        console.print("Tasks must be completed (in ledger) before setting workflow stage.")
        raise typer.Exit(1)

    # Update workflow stage
    success = writer.update_workflow_stage(task_id, workflow_stage)
    if not success:
        console.print(f"[red]Error:[/red] Failed to update workflow stage for '{task_id}'")
        raise typer.Exit(1)

    console.print(
        f"[green]Updated[/green] {task_id} workflow stage to "
        f"{_format_workflow_stage(workflow_stage.value)}"
    )


@app.command("show")
def show_stage(
    task_id: str = typer.Argument(..., help="Task ID to display"),
) -> None:
    """
    Show workflow status for a task.

    Displays the current workflow stage and when it was last updated.

    Examples:
        cub workflow show cub-abc
    """
    reader, _ = _get_ledger_paths()

    if not reader.exists():
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    entry = reader.get_task(task_id)
    if not entry:
        console.print(f"[red]Error:[/red] Task '{task_id}' not found in ledger")
        raise typer.Exit(1)

    # Display workflow info
    console.print(f"\n[bold]{entry.title}[/bold] ({entry.id})")
    console.print()
    stage_value = entry.workflow_stage.value if entry.workflow_stage else None
    console.print(f"Workflow Stage: {_format_workflow_stage(stage_value)}")
    if entry.workflow_stage_updated_at:
        console.print(
            f"Stage Updated: {entry.workflow_stage_updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
    console.print(f"Completed: {entry.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    console.print()


@app.command("list")
def list_by_stage(
    stage: str | None = typer.Option(
        None,
        "--stage",
        "-s",
        help="Filter by workflow stage (needs_review, validated, released)",
    ),
    all_tasks: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all completed tasks (including those without workflow stage)",
    ),
) -> None:
    """
    List tasks by workflow stage.

    Shows tasks grouped by their workflow stage. By default, only shows tasks
    that have a workflow stage set.

    Examples:
        cub workflow list
        cub workflow list --stage needs_review
        cub workflow list --all
    """
    reader, _ = _get_ledger_paths()

    if not reader.exists():
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    # Get all tasks
    entries = reader.list_tasks()

    if not entries:
        console.print("No completed tasks found in ledger")
        raise typer.Exit(0)

    # Filter by stage if specified
    if stage:
        try:
            WorkflowStage(stage)  # Validate stage
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid stage: {stage}")
            console.print("Valid stages: needs_review, validated, released")
            raise typer.Exit(1)

        filtered = [e for e in entries if e.workflow_stage == stage]
    elif all_tasks:
        filtered = entries
    else:
        # Show only tasks with workflow stage set
        filtered = [e for e in entries if e.workflow_stage is not None]

    if not filtered:
        if stage:
            console.print(f"No tasks found with workflow stage: {stage}")
        else:
            console.print("No tasks with workflow stage set")
            console.print("Use --all to show all completed tasks")
        raise typer.Exit(0)

    # Create table
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Completed")
    table.add_column("Workflow Stage")

    for entry in filtered:
        table.add_row(
            entry.id,
            entry.title[:50] + "..." if len(entry.title) > 50 else entry.title,
            entry.completed,
            _format_workflow_stage(entry.workflow_stage),
        )

    console.print()
    if stage:
        console.print(f"[bold]Tasks with stage: {stage}[/bold]")
    else:
        console.print("[bold]Tasks with Workflow Stages[/bold]")
    console.print()
    console.print(table)
    console.print()

    # Summary by stage
    stage_counts = {
        "needs_review": sum(1 for e in filtered if e.workflow_stage == "needs_review"),
        "validated": sum(1 for e in filtered if e.workflow_stage == "validated"),
        "released": sum(1 for e in filtered if e.workflow_stage == "released"),
        "none": sum(1 for e in filtered if e.workflow_stage is None),
    }

    console.print("[bold]Summary:[/bold]")
    if stage_counts["needs_review"]:
        console.print(f"  Needs Review: {stage_counts['needs_review']}")
    if stage_counts["validated"]:
        console.print(f"  Validated: {stage_counts['validated']}")
    if stage_counts["released"]:
        console.print(f"  Released: {stage_counts['released']}")
    if stage_counts["none"] and all_tasks:
        console.print(f"  No Stage: {stage_counts['none']}")
