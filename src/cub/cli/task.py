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
from cub.core.tasks.backend import TaskBackend, get_backend
from cub.core.tasks.graph import DependencyGraph
from cub.core.tasks.models import Task, TaskStatus

console = Console()
app = typer.Typer(help="Manage tasks (backend-agnostic)")


def _try_build_graph(backend: TaskBackend) -> DependencyGraph | None:
    """Attempt to build a dependency graph from all tasks.

    Returns None if DependencyGraph is not available yet (e.g., during
    early development phases).

    Args:
        backend: Task backend to fetch tasks from

    Returns:
        DependencyGraph instance or None if unavailable
    """
    try:
        all_tasks = backend.list_tasks()
        return DependencyGraph(all_tasks)
    except Exception:
        # If graph construction fails for any reason, return None
        return None


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
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly markdown format",
    ),
) -> None:
    """
    Show detailed information about a task.

    Examples:
        cub task show cub-123
        cub task show cub-123 --json
        cub task show cub-123 --agent
    """
    backend = get_backend()
    task = backend.get_task(task_id)

    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        raise typer.Exit(1)

    # --agent wins over --json
    if agent:
        try:
            from cub.core.services.agent_format import AgentFormatter

            graph = _try_build_graph(backend)

            output = AgentFormatter.format_task_detail(task, graph)
            console.print(output)
        except ImportError:
            # Fallback to simple markdown if AgentFormatter not available
            console.print(f"# cub task show {task.id}\n")
            console.print(f"## {task.title}\n")
            console.print(f"- **Priority**: {task.priority.value}")
            console.print(f"- **Status**: {task.status.value}")
            console.print(f"- **Type**: {task.type.value}")
            if task.parent:
                console.print(f"- **Parent**: {task.parent}")
            if task.labels:
                console.print(f"- **Labels**: {', '.join(task.labels)}")
            if task.description:
                console.print(f"\n## Description\n\n{task.description}")
        return

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
    epic: str | None = typer.Option(
        None,
        "--epic",
        help="Filter by parent epic/task ID (alias for --parent)",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Filter by label",
    ),
    assignee: str | None = typer.Option(
        None,
        "--assignee",
        "-a",
        help="Filter by assignee",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly markdown format",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        help="Show all tasks (disable truncation in --agent mode)",
    ),
) -> None:
    """
    List tasks with optional filters.

    Examples:
        cub task list                           # All tasks
        cub task list --status open             # Open tasks only
        cub task list --parent cub-123          # Tasks under epic
        cub task list --epic cub-123            # Tasks under epic (same as --parent)
        cub task list --label bug               # Tasks with label
        cub task list --assignee agent-001      # Tasks assigned to agent-001
        cub task list --agent --all             # Show all tasks (no truncation)
    """
    backend = get_backend()

    # --epic is an alias for --parent (use epic if both provided, otherwise parent)
    parent_filter = epic or parent

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

    tasks = backend.list_tasks(status=task_status, parent=parent_filter, label=label)

    # Client-side filtering for assignee (since backend doesn't support it)
    if assignee:
        tasks = [t for t in tasks if t.assignee == assignee]

    # --agent wins over --json
    if agent:
        try:
            from cub.core.services.agent_format import AgentFormatter

            agent_output = AgentFormatter.format_list(
                tasks, limit=0 if show_all else None
            )
            console.print(agent_output)
        except ImportError:
            # Fallback to simple markdown if AgentFormatter not available
            console.print("# cub task list\n")
            task_count = len(tasks)
            plural = "s" if task_count != 1 else ""
            console.print(f"{task_count} task{plural} across all statuses.\n")
            if tasks:
                console.print("| ID | Title | Status | Pri |")
                console.print("|----|-------|--------|-----|")
                for task in tasks:
                    row = f"| {task.id} | {task.title} | {task.status.value}"
                    row += f" | {task.priority.value} |"
                    console.print(row)
            console.print(f"\n*Total: {task_count} tasks*")
        return

    if json_output:
        json_output_data = [t.model_dump(mode="json") for t in tasks]
        console.print(json.dumps(json_output_data, indent=2))
        return

    if not tasks:
        criteria_parts = []
        if status:
            criteria_parts.append(f"status={status}")
        if parent_filter:
            criteria_parts.append(f"parent={parent_filter}")
        if label:
            criteria_parts.append(f"label={label}")
        if assignee:
            criteria_parts.append(f"assignee={assignee}")
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
    title: str | None = typer.Option(
        None,
        "--title",
        help="Update title",
    ),
    priority: int | None = typer.Option(
        None,
        "--priority",
        "-p",
        help="Update priority (0-4, where 0 is highest)",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Update notes/comments",
    ),
) -> None:
    """
    Update a task's fields.

    Examples:
        cub task update cub-123 --status in_progress
        cub task update cub-123 --assignee "agent-001"
        cub task update cub-123 --add-label "priority:high"
        cub task update cub-123 --title "New title"
        cub task update cub-123 --priority 1
        cub task update cub-123 --notes "Additional context"
    """
    backend = get_backend()

    # First get the task to check if it exists and get current labels
    task = backend.get_task(task_id)
    if task is None:
        print_task_not_found_error(task_id)
        raise typer.Exit(ExitCode.USER_ERROR)

    # Validate priority if provided
    if priority is not None and not (0 <= priority <= 4):
        console.print(f"[red]Error:[/red] Priority must be between 0 and 4 (got {priority})")
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
            title=title,
            priority=priority,
            notes=notes,
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
def reopen(
    task_id: str = typer.Argument(..., help="Task ID to reopen"),
    reason: str | None = typer.Option(
        None,
        "--reason",
        "-r",
        help="Reason for reopening the task",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Reopen a closed task.

    Changes task status from CLOSED back to OPEN.

    Examples:
        cub task reopen cub-123
        cub task reopen cub-123 --reason "Issue not fully resolved"
    """
    backend = get_backend()

    try:
        task = backend.reopen_task(task_id, reason=reason)

        if json_output:
            console.print(json.dumps(task.model_dump(mode="json"), indent=2))
        else:
            console.print(f"[green]Reopened:[/green] {task.id} - {task.title}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def delete(
    task_id: str = typer.Argument(..., help="Task ID to delete"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON (only with --force)",
    ),
) -> None:
    """
    Delete a task permanently.

    WARNING: This is destructive and cannot be undone. A confirmation prompt
    is shown unless --force is passed.

    Examples:
        cub task delete cub-123              # Shows confirmation prompt
        cub task delete cub-123 --force      # Skips prompt
        cub task delete cub-123 -f           # Shorthand
    """
    backend = get_backend()

    # Get the task to display title in confirmation
    task = backend.get_task(task_id)
    if task is None:
        print_task_not_found_error(task_id)
        raise typer.Exit(ExitCode.USER_ERROR)

    # Show confirmation unless --force is passed
    if not force:
        confirmation = typer.confirm(
            f"Delete task {task_id} '{task.title}'?",
            default=False,
        )
        if not confirmation:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    try:
        deleted = backend.delete_task(task_id)

        if not deleted:
            console.print(f"[red]Error:[/red] Task not found: {task_id}")
            raise typer.Exit(1)

        if json_output:
            output = {
                "deleted": True,
                "task_id": task_id,
                "title": task.title,
            }
            console.print(json.dumps(output, indent=2))
        else:
            console.print(f"[green]Deleted:[/green] {task_id}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def claim(
    task_id: str = typer.Argument(..., help="Task ID to claim"),
) -> None:
    """
    Claim a task (set status to in_progress).

    This is a convenience command equivalent to:
        cub task update <task_id> --status in_progress

    Examples:
        cub task claim cub-123
    """
    backend = get_backend()

    # First check if task exists and get current status
    task = backend.get_task(task_id)
    if task is None:
        print_task_not_found_error(task_id)
        raise typer.Exit(ExitCode.USER_ERROR)

    # Check if already claimed (in_progress)
    if task.status == TaskStatus.IN_PROGRESS:
        console.print(f"[yellow]Warning:[/yellow] Task {task_id} is already in progress")
        if task.assignee:
            console.print(f"  Assignee: {task.assignee}")
        raise typer.Exit(0)

    # Check if already closed
    if task.status == TaskStatus.CLOSED:
        console.print(f"[yellow]Warning:[/yellow] Task {task_id} is already closed")
        raise typer.Exit(0)

    # Claim the task
    try:
        updated = backend.update_task(
            task_id=task_id,
            status=TaskStatus.IN_PROGRESS,
        )
        console.print(f"[green]Claimed:[/green] {updated.id}")
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
    epic: str | None = typer.Option(
        None,
        "--epic",
        help="Filter by parent epic/task ID (alias for --parent)",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Filter by label",
    ),
    by: str = typer.Option(
        "priority",
        "--by",
        help="Sort order: priority (default) or impact (transitive unblocks)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly markdown format",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        help="Show all tasks (disable truncation in --agent mode)",
    ),
) -> None:
    """
    List tasks ready to work on (no blockers).

    Ready tasks are:
    - Status is OPEN
    - All dependencies are CLOSED

    Examples:
        cub task ready                      # All ready tasks (by priority)
        cub task ready --parent cub-123     # Ready tasks under epic
        cub task ready --epic cub-123       # Ready tasks under epic (same as --parent)
        cub task ready --by priority        # Sort by priority (default)
        cub task ready --by impact          # Sort by impact (transitive unblocks)
        cub task ready --agent              # Agent-friendly markdown output
        cub task ready --agent --all        # Show all tasks (no truncation)
    """
    backend = get_backend()

    # --epic is an alias for --parent (use epic if both provided, otherwise parent)
    parent_filter = epic or parent

    # Validate --by option
    if by not in ("priority", "impact"):
        print_invalid_option_error(by, ["priority", "impact"])
        raise typer.Exit(ExitCode.USER_ERROR)

    tasks = backend.get_ready_tasks(parent=parent_filter, label=label)

    if not tasks:
        # --agent wins over --json
        if agent:
            console.print("# cub task ready\n")
            console.print("0 tasks ready to work on.")
        elif json_output:
            console.print(json.dumps([], indent=2))
        else:
            console.print("[yellow]No tasks ready to work on.[/yellow]")
        return

    # Sort tasks based on --by option
    if by == "impact":
        # Build dependency graph from all tasks and sort by transitive unblocks
        all_tasks = backend.list_tasks()
        graph = DependencyGraph(all_tasks)

        # Calculate impact scores for all ready tasks
        impact_scores: dict[str, int] = {}
        for task in tasks:
            impact_scores[task.id] = len(graph.transitive_unblocks(task.id))

        # Sort by impact (descending), then by priority (ascending)
        tasks.sort(key=lambda t: (-impact_scores.get(t.id, 0), t.priority_numeric))
    else:
        # Default: sort by priority (already done by backend, but ensure consistency)
        tasks.sort(key=lambda t: t.priority_numeric)

    # --agent wins over --json
    if agent:
        try:
            from cub.core.services.agent_format import AgentFormatter

            graph_result = _try_build_graph(backend)
            agent_output = AgentFormatter.format_ready(
                tasks, graph_result, limit=0 if show_all else None
            )
            console.print(agent_output)
        except ImportError:
            # Fallback to simple markdown if AgentFormatter not available
            console.print("# cub task ready\n")
            console.print(f"{len(tasks)} task{'s' if len(tasks) != 1 else ''} ready to work on.\n")
            console.print("## Ready Tasks\n")
            console.print("| ID | Title | Pri | Blocks |")
            console.print("|----|-------|-----|--------|")
            for task in tasks:
                blocks_count = len(task.blocks)
                if blocks_count == 0:
                    blocks_str = "none"
                else:
                    plural = 's' if blocks_count != 1 else ''
                    blocks_str = f"{blocks_count} task{plural}"
                console.print(
                    f"| {task.id} | {task.title} | {task.priority.value} | {blocks_str} |"
                )
        return

    if json_output:
        json_output_list = [t.model_dump(mode="json") for t in tasks]
        console.print(json.dumps(json_output_list, indent=2))
        return

    table = Table(
        title="Ready Tasks",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim")
    table.add_column("P", width=2, justify="center")
    table.add_column("Title", overflow="fold")

    # Add impact column if sorting by impact
    if by == "impact":
        table.add_column("Impact", width=8, justify="right")

    # Pre-compute impact scores if needed (avoid rebuilding graph in loop)
    impact_scores_display: dict[str, int] = {}
    if by == "impact":
        all_tasks = backend.list_tasks()
        graph = DependencyGraph(all_tasks)
        for task in tasks:
            impact_scores_display[task.id] = len(graph.transitive_unblocks(task.id))

    for task in tasks:
        row = [
            task.id,
            task.priority.value[1],
            task.title,
        ]

        # Add impact score if sorting by impact
        if by == "impact":
            impact = impact_scores_display.get(task.id, 0)
            row.append(str(impact) if impact > 0 else "-")

        table.add_row(*row)

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
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Add a dependency between tasks.

    The first task will depend on (be blocked by) the second task.

    Examples:
        cub task dep add cub-456 cub-123  # cub-456 depends on cub-123
    """
    backend = get_backend()

    try:
        updated = backend.add_dependency(task_id, depends_on)

        if json_output:
            console.print(json.dumps(updated.model_dump(mode="json"), indent=2))
        else:
            console.print(f"[green]Added dependency:[/green] {task_id} now depends on {depends_on}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@dep_app.command("remove")
def dep_remove(
    task_id: str = typer.Argument(..., help="Task to remove dependency from"),
    depends_on: str = typer.Argument(..., help="Dependency to remove"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Remove a dependency from a task.

    Examples:
        cub task dep remove cub-456 cub-123  # cub-456 no longer depends on cub-123
    """
    backend = get_backend()

    try:
        updated = backend.remove_dependency(task_id, depends_on)

        if json_output:
            console.print(json.dumps(updated.model_dump(mode="json"), indent=2))
        else:
            msg = f"[green]Removed dependency:[/green] {task_id} no longer depends on {depends_on}"
            console.print(msg)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@dep_app.command("list")
def dep_list(
    task_id: str = typer.Argument(..., help="Task ID to show dependencies for"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
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

    if json_output:
        # JSON output with both directions
        output = {
            "task_id": task.id,
            "depends_on": task.depends_on,
            "blocks": task.blocks,
        }
        console.print(json.dumps(output, indent=2))
        return

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


# Subcommand group for labels
label_app = typer.Typer(help="Manage task labels")
app.add_typer(label_app, name="label")


@label_app.command("add")
def label_add(
    task_id: str = typer.Argument(..., help="Task to add label to"),
    label: str = typer.Argument(..., help="Label to add"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Add a label to a task.

    Examples:
        cub task label add cub-123 bug
        cub task label add cub-456 "priority:high"
    """
    backend = get_backend()

    try:
        updated = backend.add_label(task_id, label)

        if json_output:
            console.print(json.dumps(updated.model_dump(mode="json"), indent=2))
        else:
            console.print(f"[green]Added label:[/green] '{label}' to {task_id}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@label_app.command("remove")
def label_remove(
    task_id: str = typer.Argument(..., help="Task to remove label from"),
    label: str = typer.Argument(..., help="Label to remove"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Remove a label from a task.

    Examples:
        cub task label remove cub-123 bug
        cub task label remove cub-456 "priority:high"
    """
    backend = get_backend()

    try:
        updated = backend.remove_label(task_id, label)

        if json_output:
            console.print(json.dumps(updated.model_dump(mode="json"), indent=2))
        else:
            console.print(f"[green]Removed label:[/green] '{label}' from {task_id}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@label_app.command("list")
def label_list(
    task_id: str = typer.Argument(..., help="Task to list labels for"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    List labels for a task.

    Examples:
        cub task label list cub-123
        cub task label list cub-123 --json
    """
    backend = get_backend()
    task = backend.get_task(task_id)

    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        raise typer.Exit(1)

    if json_output:
        output = {
            "task_id": task.id,
            "labels": task.labels,
        }
        console.print(json.dumps(output, indent=2))
        return

    console.print(f"[bold]Labels for {task.id}[/bold]")
    if task.labels:
        for label in task.labels:
            console.print(f"  • {label}")
    else:
        console.print("\n[dim]No labels[/dim]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly markdown format",
    ),
) -> None:
    """
    Search for tasks by title or description.

    Searches across task titles and descriptions using full-text search
    (beads backend) or case-insensitive substring matching (JSONL backend).

    Examples:
        cub task search "authentication"
        cub task search "bug" --json
        cub task search "database" --agent
    """
    backend = get_backend()

    try:
        tasks = backend.search_tasks(query)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        output = [t.model_dump(mode="json") for t in tasks]
        console.print(json.dumps(output, indent=2))
        return

    if agent:
        # Agent-friendly markdown output
        console.print(f"# Search Results: \"{query}\"\n")
        console.print(f"Found {len(tasks)} matching task(s)\n")

        if tasks:
            console.print("| ID | Priority | Status | Title |")
            console.print("|----|----------|--------|-------|")

            for task in tasks:
                console.print(
                    f"| {task.id} | {task.priority.value} | {task.status.value} | {task.title} |"
                )

        console.print(f"\n*Total: {len(tasks)} results*")
        return

    # Rich table output (default)
    if not tasks:
        console.print(f'[yellow]No tasks found matching "{query}"[/yellow]')
        return

    table = Table(
        title=f'Search Results: "{query}"',
        show_header=True,
        header_style="bold cyan",
    )
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
    console.print(f"\n[dim]Found {len(tasks)} matching task(s)[/dim]")


@app.command()
def blocked(
    epic: str | None = typer.Option(
        None,
        "--epic",
        help="Filter by epic/parent ID",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Include agent analysis (root blockers, chain lengths)",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        help="Show all tasks (disable truncation in --agent mode)",
    ),
) -> None:
    """
    Show blocked tasks (tasks with unresolved dependencies).

    Blocked tasks are:
    - Status is OPEN
    - Have at least one dependency that is not CLOSED

    Examples:
        cub task blocked                # All blocked tasks
        cub task blocked --epic cub-123 # Blocked tasks under epic
        cub task blocked --agent        # Include dependency analysis
        cub task blocked --agent --all  # Show all blocked tasks (no truncation)
    """
    from cub.core.tasks.graph import DependencyGraph

    backend = get_backend()
    blocked_tasks = backend.list_blocked_tasks(parent=epic)

    # --agent wins over --json
    if agent:
        # Build dependency graph from all tasks for analysis
        all_tasks = backend.list_tasks()
        graph = DependencyGraph(all_tasks)

        # Try to import AgentFormatter if available
        try:
            from cub.core.services.agent_format import AgentFormatter

            output = AgentFormatter.format_blocked(
                blocked_tasks, graph, limit=0 if show_all else None
            )
            console.print(output)
            return
        except ImportError:
            # Fallback to markdown table with analysis
            _format_blocked_agent_fallback(blocked_tasks, graph)
            return

    if json_output:
        json_output_data = [t.model_dump(mode="json") for t in blocked_tasks]
        console.print(json.dumps(json_output_data, indent=2))
        return

    if not blocked_tasks:
        console.print("[yellow]No blocked tasks found.[/yellow]")
        return

    # Rich table output (default)
    table = Table(
        title="Blocked Tasks",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim")
    table.add_column("P", width=2, justify="center")
    table.add_column("Title", overflow="fold")
    table.add_column("Blocked By", overflow="fold")

    for task in blocked_tasks:
        # Get open blockers
        open_blockers = []
        for dep_id in task.depends_on:
            dep_task = backend.get_task(dep_id)
            if dep_task and dep_task.status != TaskStatus.CLOSED:
                open_blockers.append(dep_id)

        table.add_row(
            task.id,
            task.priority.value[1],
            task.title,
            ", ".join(open_blockers) if open_blockers else "[dim]none[/dim]",
        )

    console.print(table)
    console.print(f"\n[dim]{len(blocked_tasks)} blocked tasks[/dim]")


def _format_blocked_agent_fallback(
    blocked_tasks: list[Task], graph: DependencyGraph
) -> None:
    """Format blocked tasks with dependency analysis.

    Fallback when AgentFormatter not available.
    """

    console.print("[bold cyan]# Blocked Tasks Analysis[/bold cyan]\n")

    # Show blocked tasks table
    console.print("[bold]## Blocked Tasks[/bold]\n")
    console.print("| ID | Priority | Title | Blocked By |")
    console.print("|----|----------|-------|------------|")

    backend = get_backend()
    for task in blocked_tasks:
        # Get open blockers
        open_blockers = []
        for dep_id in task.depends_on:
            dep_task = backend.get_task(dep_id)
            if dep_task and dep_task.status != TaskStatus.CLOSED:
                open_blockers.append(dep_id)

        blockers_str = ", ".join(open_blockers) if open_blockers else "none"
        console.print(f"| {task.id} | {task.priority.value} | {task.title} | {blockers_str} |")

    console.print(f"\n*Total: {len(blocked_tasks)} blocked tasks*\n")

    # Show root blockers analysis
    root_blockers = graph.root_blockers(limit=5)
    if root_blockers:
        console.print("[bold]## Root Blockers[/bold]\n")
        console.print("Completing these tasks would unblock the most other tasks:\n")
        for task_id, unblock_count in root_blockers:
            maybe_task = backend.get_task(task_id)
            title = maybe_task.title if maybe_task else "(not found)"
            console.print(f"- **{task_id}**: {title} (unblocks {unblock_count} tasks)")
        console.print()

    # Show longest dependency chains
    chains = graph.chains(limit=5)
    if chains:
        console.print("[bold]## Dependency Chains[/bold]\n")
        max_depth = len(chains[0]) if chains else 0
        console.print(f"Longest dependency chains (max depth: {max_depth}):\n")
        for i, chain in enumerate(chains, 1):
            chain_str = " → ".join(chain)
            console.print(f"{i}. {chain_str} (length: {len(chain)})")
        console.print()
