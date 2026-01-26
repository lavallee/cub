"""
Cub CLI - Unified Task Interface.

Backend-agnostic CLI for task management. LLMs should use this
instead of calling `bd` directly for consistent cross-backend behavior.
"""

import json

import typer
from rich.console import Console
from rich.table import Table

from cub.cli.errors import (
    ExitCode,
    print_invalid_option_error,
    print_no_tasks_found_error,
    print_task_not_found_error,
)
from cub.core.tasks.backend import get_backend
from cub.core.tasks.models import TaskStatus

console = Console()
app = typer.Typer(help="Manage tasks (backend-agnostic)")


@app.command()
def create(
    title: str = typer.Argument(..., help="Task title"),
    task_type: str = typer.Option(
        "task",
        "--type",
        "-t",
        help="Task type: task, feature, bug, epic, gate",
    ),
    priority: int = typer.Option(
        2,
        "--priority",
        "-p",
        help="Priority level (0-4, where 0 is highest)",
    ),
    parent: str | None = typer.Option(
        None,
        "--parent",
        help="Parent epic/task ID",
    ),
    labels: list[str] | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Task labels (can be repeated)",
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        "-d",
        help="Task description",
    ),
    depends_on: list[str] | None = typer.Option(
        None,
        "--depends-on",
        help="Task IDs this task depends on (can be repeated)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Create a new task.

    Examples:
        cub task create "Fix login bug" --type bug --priority 1
        cub task create "Add user profile" --type feature --parent cub-123
        cub task create "Write tests" --label testing --depends-on cub-456
    """
    backend = get_backend()

    try:
        task = backend.create_task(
            title=title,
            description=description or "",
            task_type=task_type,
            priority=priority,
            labels=labels or [],
            depends_on=depends_on or [],
            parent=parent,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        console.print(json.dumps(task.model_dump(mode="json"), indent=2))
    else:
        console.print(f"[green]Created:[/green] {task.id}")
        if task.parent:
            console.print(f"  Parent: {task.parent}")


@app.command()
def show(
    task_id: str = typer.Argument(..., help="Task ID to display"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Show detailed information about a task.

    Examples:
        cub task show cub-123
        cub task show cub-123 --json
    """
    backend = get_backend()
    task = backend.get_task(task_id)

    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        raise typer.Exit(1)

    if json_output:
        console.print(json.dumps(task.model_dump(mode="json"), indent=2))
        return

    # Display task details
    console.print(f"[bold cyan]{task.id}[/bold cyan] - {task.title}")
    console.print(f"[dim]Status:[/dim] {task.status.value}")
    console.print(f"[dim]Type:[/dim] {task.type.value}")
    console.print(f"[dim]Priority:[/dim] {task.priority.value}")

    if task.parent:
        console.print(f"[dim]Parent:[/dim] {task.parent}")

    if task.labels:
        console.print(f"[dim]Labels:[/dim] {', '.join(task.labels)}")

    if task.depends_on:
        console.print(f"[dim]Depends on:[/dim] {', '.join(task.depends_on)}")

    if task.blocks:
        console.print(f"[dim]Blocks:[/dim] {', '.join(task.blocks)}")

    if task.assignee:
        console.print(f"[dim]Assignee:[/dim] {task.assignee}")

    if task.description:
        console.print(f"\n[bold]Description:[/bold]\n{task.description}")


@app.command("list")
def list_tasks(
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status: open, in_progress, closed",
    ),
    parent: str | None = typer.Option(
        None,
        "--parent",
        help="Filter by parent epic/task ID",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Filter by label",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    List tasks with optional filters.

    Examples:
        cub task list                           # All tasks
        cub task list --status open             # Open tasks only
        cub task list --parent cub-123          # Tasks under epic
        cub task list --label bug               # Tasks with label
    """
    backend = get_backend()

    # Convert status string to TaskStatus
    task_status: TaskStatus | None = None
    if status:
        try:
            task_status = TaskStatus(status.lower())
        except ValueError:
            print_invalid_option_error(
                status,
                [s.value for s in TaskStatus]
            )
            raise typer.Exit(ExitCode.USER_ERROR)

    tasks = backend.list_tasks(status=task_status, parent=parent, label=label)

    if json_output:
        output = [t.model_dump(mode="json") for t in tasks]
        console.print(json.dumps(output, indent=2))
        return

    if not tasks:
        criteria_parts = []
        if status:
            criteria_parts.append(f"status={status}")
        if parent:
            criteria_parts.append(f"parent={parent}")
        if label:
            criteria_parts.append(f"label={label}")
        criteria_str = " ".join(criteria_parts) if criteria_parts else None
        print_no_tasks_found_error(criteria_str)
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("P", width=2, justify="center")
    table.add_column("Status", width=12)
    table.add_column("Title", overflow="fold")

    for task in tasks:
        status_color = {
            TaskStatus.OPEN: "white",
            TaskStatus.IN_PROGRESS: "yellow",
            TaskStatus.CLOSED: "green",
        }.get(task.status, "white")

        table.add_row(
            task.id,
            task.priority.value[1],  # Just the number
            f"[{status_color}]{task.status.value}[/{status_color}]",
            task.title,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(tasks)} tasks[/dim]")


@app.command()
def update(
    task_id: str = typer.Argument(..., help="Task ID to update"),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="New status: open, in_progress, closed",
    ),
    assignee: str | None = typer.Option(
        None,
        "--assignee",
        "-a",
        help="Set assignee",
    ),
    add_label: list[str] | None = typer.Option(
        None,
        "--add-label",
        help="Add a label (can be repeated)",
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        "-d",
        help="Update description",
    ),
) -> None:
    """
    Update a task's fields.

    Examples:
        cub task update cub-123 --status in_progress
        cub task update cub-123 --assignee "agent-001"
        cub task update cub-123 --add-label "priority:high"
    """
    backend = get_backend()

    # First get the task to check if it exists and get current labels
    task = backend.get_task(task_id)
    if task is None:
        print_task_not_found_error(task_id)
        raise typer.Exit(ExitCode.USER_ERROR)

    # Convert status string to TaskStatus
    task_status: TaskStatus | None = None
    if status:
        try:
            task_status = TaskStatus(status.lower())
        except ValueError:
            print_invalid_option_error(
                status,
                [s.value for s in TaskStatus]
            )
            raise typer.Exit(ExitCode.USER_ERROR)

    # Handle label additions
    new_labels: list[str] | None = None
    if add_label:
        new_labels = list(task.labels)
        for label in add_label:
            if label not in new_labels:
                new_labels.append(label)

    try:
        updated = backend.update_task(
            task_id=task_id,
            status=task_status,
            assignee=assignee,
            description=description,
            labels=new_labels,
        )
        console.print(f"[green]Updated:[/green] {updated.id}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def close(
    task_id: str = typer.Argument(..., help="Task ID to close"),
    reason: str | None = typer.Option(
        None,
        "--reason",
        "-r",
        help="Reason for closing the task",
    ),
) -> None:
    """
    Close a task.

    Examples:
        cub task close cub-123
        cub task close cub-123 --reason "Completed in PR #456"
    """
    backend = get_backend()

    try:
        task = backend.close_task(task_id, reason=reason)
        console.print(f"[green]Closed:[/green] {task.id}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def ready(
    parent: str | None = typer.Option(
        None,
        "--parent",
        help="Filter by parent epic/task ID",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Filter by label",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    List tasks ready to work on (no blockers).

    Ready tasks are:
    - Status is OPEN
    - All dependencies are CLOSED

    Examples:
        cub task ready                  # All ready tasks
        cub task ready --parent cub-123 # Ready tasks under epic
    """
    backend = get_backend()
    tasks = backend.get_ready_tasks(parent=parent, label=label)

    if json_output:
        output = [t.model_dump(mode="json") for t in tasks]
        console.print(json.dumps(output, indent=2))
        return

    if not tasks:
        console.print("[yellow]No tasks ready to work on.[/yellow]")
        return

    table = Table(
        title="Ready Tasks",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim")
    table.add_column("P", width=2, justify="center")
    table.add_column("Title", overflow="fold")

    for task in tasks:
        table.add_row(
            task.id,
            task.priority.value[1],
            task.title,
        )

    console.print(table)
    console.print(f"\n[dim]{len(tasks)} tasks ready[/dim]")


@app.command()
def counts(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Show task statistics.

    Examples:
        cub task counts
        cub task counts --json
    """
    backend = get_backend()
    stats = backend.get_task_counts()

    if json_output:
        console.print(json.dumps(stats.model_dump(), indent=2))
        return

    console.print("[bold]Task Statistics[/bold]")
    console.print(f"  Total:       {stats.total}")
    console.print(f"  Open:        {stats.open}")
    console.print(f"  In Progress: {stats.in_progress}")
    console.print(f"  Closed:      {stats.closed}")
    console.print()
    console.print(f"  Remaining:   {stats.remaining}")
    console.print(f"  Completion:  {stats.completion_percentage:.1f}%")


# Subcommand group for dependencies
dep_app = typer.Typer(help="Manage task dependencies")
app.add_typer(dep_app, name="dep")


@dep_app.command("add")
def dep_add(
    task_id: str = typer.Argument(..., help="Task that depends on another"),
    depends_on: str = typer.Argument(..., help="Task that must be completed first"),
) -> None:
    """
    Add a dependency between tasks.

    The first task will depend on (be blocked by) the second task.

    Examples:
        cub task dep add cub-456 cub-123  # cub-456 depends on cub-123
    """
    backend = get_backend()

    # Get both tasks to verify they exist
    task = backend.get_task(task_id)
    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        raise typer.Exit(1)

    blocker = backend.get_task(depends_on)
    if blocker is None:
        console.print(f"[red]Error:[/red] Task not found: {depends_on}")
        raise typer.Exit(1)

    # Add dependency via update
    new_deps = list(task.depends_on)
    if depends_on not in new_deps:
        new_deps.append(depends_on)

    # Note: depends_on is not directly updatable via update_task in the protocol
    # This would need backend-specific implementation
    # For now, we'll use create_task with the dep, or suggest using backend directly
    console.print(
        f"[yellow]Note:[/yellow] Dependency management varies by backend. "
        f"Consider using: bd dep add {task_id} {depends_on}"
    )


@dep_app.command("list")
def dep_list(
    task_id: str = typer.Argument(..., help="Task ID to show dependencies for"),
) -> None:
    """
    List dependencies for a task.

    Shows what tasks this task depends on (blockers) and
    what tasks are blocked by this task.

    Examples:
        cub task dep list cub-123
    """
    backend = get_backend()
    task = backend.get_task(task_id)

    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        raise typer.Exit(1)

    console.print(f"[bold]Dependencies for {task.id}[/bold]")

    if task.depends_on:
        console.print("\n[dim]Depends on (blocked by):[/dim]")
        for dep_id in task.depends_on:
            dep_task = backend.get_task(dep_id)
            if dep_task:
                is_done = dep_task.status == TaskStatus.CLOSED
                status_icon = "[green]✓[/green]" if is_done else "[yellow]○[/yellow]"
                console.print(f"  {status_icon} {dep_id}: {dep_task.title}")
            else:
                console.print(f"  [red]?[/red] {dep_id} (not found)")
    else:
        console.print("\n[dim]No dependencies (not blocked)[/dim]")

    if task.blocks:
        console.print("\n[dim]Blocks:[/dim]")
        for blocked_id in task.blocks:
            blocked_task = backend.get_task(blocked_id)
            if blocked_task:
                console.print(f"  {blocked_id}: {blocked_task.title}")
            else:
                console.print(f"  {blocked_id} (not found)")
    else:
        console.print("\n[dim]Not blocking any tasks[/dim]")
