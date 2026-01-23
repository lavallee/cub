"""
Cub CLI - Ledger commands.

Query and display completed work records from the ledger system.
"""

import json

import typer
from rich.console import Console
from rich.table import Table

from cub.core.ledger.models import VerificationStatus
from cub.core.ledger.reader import LedgerReader
from cub.utils.project import get_project_root

app = typer.Typer(
    name="ledger",
    help="Query completed work ledger",
    no_args_is_help=True,
)

console = Console()


def _get_ledger_reader() -> LedgerReader:
    """Get ledger reader for current project."""
    project_root = get_project_root()
    ledger_dir = project_root / ".cub" / "ledger"
    return LedgerReader(ledger_dir)


def _format_cost(cost: float) -> str:
    """Format cost as USD with color."""
    if cost == 0:
        return "[dim]$0.00[/dim]"
    return f"[yellow]${cost:.2f}[/yellow]"


def _format_verification(status: str) -> str:
    """Format verification status with color."""
    status_colors = {
        "pass": "[green]pass[/green]",
        "fail": "[red]fail[/red]",
        "warn": "[yellow]warn[/yellow]",
        "skip": "[dim]skip[/dim]",
        "pending": "[blue]pending[/blue]",
        "error": "[red]error[/red]",
    }
    return status_colors.get(status, status)


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
    Show detailed ledger entry for a task.

    Displays the full ledger record including approach, decisions,
    commits, files changed, token usage, and verification status.

    Examples:
        cub ledger show beads-abc
        cub ledger show beads-abc --json
    """
    reader = _get_ledger_reader()

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

    if json_output:
        console.print(entry.model_dump_json(indent=2))
        return

    # Rich formatted output
    console.print(f"\n[bold]{entry.title}[/bold] ({entry.id})")
    console.print()

    # Basic info
    if entry.completed_at:
        console.print(f"Completed: {entry.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if entry.started_at:
        console.print(f"Started: {entry.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if entry.duration_seconds > 0:
        console.print(f"Duration: {entry.duration_minutes:.1f} minutes")
    console.print()

    # Cost and tokens
    console.print(f"Cost: {_format_cost(entry.cost_usd)}")
    console.print(f"Tokens: {entry.tokens.total_tokens:,}")
    if entry.tokens.total_tokens > 0:
        console.print(f"  Input: {entry.tokens.input_tokens:,}")
        console.print(f"  Output: {entry.tokens.output_tokens:,}")
        if entry.tokens.cache_read_tokens > 0:
            console.print(f"  Cache read: {entry.tokens.cache_read_tokens:,}")
        if entry.tokens.cache_creation_tokens > 0:
            console.print(f"  Cache creation: {entry.tokens.cache_creation_tokens:,}")
    console.print()

    # Harness
    if entry.harness_name:
        console.print(f"Harness: {entry.harness_name}", end="")
        if entry.harness_model:
            console.print(f" ({entry.harness_model})")
        else:
            console.print()

    # Verification
    console.print(f"Verification: {_format_verification(entry.verification_status.value)}")
    if entry.verification_notes:
        for note in entry.verification_notes:
            console.print(f"  • {note}")
    console.print()

    # Epic and spec
    if entry.epic_id:
        console.print(f"Epic: {entry.epic_id}")
    if entry.spec_file:
        console.print(f"Spec: {entry.spec_file}")
    console.print()

    # Approach
    if entry.approach:
        console.print("[bold]Approach:[/bold]")
        console.print(entry.approach)
        console.print()

    # Decisions
    if entry.decisions:
        console.print("[bold]Key Decisions:[/bold]")
        for decision in entry.decisions:
            console.print(f"  • {decision}")
        console.print()

    # Lessons learned
    if entry.lessons_learned:
        console.print("[bold]Lessons Learned:[/bold]")
        for lesson in entry.lessons_learned:
            console.print(f"  • {lesson}")
        console.print()

    # Files changed
    if entry.files_changed:
        console.print(f"[bold]Files Changed ({len(entry.files_changed)}):[/bold]")
        for file in entry.files_changed[:10]:  # Show first 10
            console.print(f"  • {file}")
        if len(entry.files_changed) > 10:
            console.print(f"  ... and {len(entry.files_changed) - 10} more")
        console.print()

    # Commits
    if entry.commits:
        console.print(f"[bold]Commits ({len(entry.commits)}):[/bold]")
        for commit in entry.commits:
            console.print(f"  • {commit.short_hash} - {commit.message}")
        console.print()

    # Run log
    if entry.run_log_path:
        console.print(f"Run log: {entry.run_log_path}")


@app.command()
def stats(
    since: str | None = typer.Option(
        None,
        "--since",
        help="Only include tasks completed since date (YYYY-MM-DD)",
    ),
    epic: str | None = typer.Option(
        None,
        "--epic",
        help="Only include tasks in this epic",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Show aggregate statistics for completed work.

    Displays summary metrics including total tasks, cost, tokens,
    verification rates, and file changes.

    Examples:
        cub ledger stats
        cub ledger stats --since 2026-01-01
        cub ledger stats --epic cub-vd6
        cub ledger stats --json
    """
    reader = _get_ledger_reader()

    if not reader.exists():
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    stats = reader.get_stats(since=since, epic=epic)

    if json_output:
        console.print(stats.model_dump_json(indent=2))
        return

    # Rich formatted output
    console.print("\n[bold]Ledger Statistics[/bold]")
    if since:
        console.print(f"Since: {since}")
    if epic:
        console.print(f"Epic: {epic}")
    console.print()

    # Task counts
    console.print(f"[bold]Tasks:[/bold] {stats.total_tasks}")
    if stats.total_epics > 0:
        console.print(f"[bold]Epics:[/bold] {stats.total_epics}")
    console.print()

    # Cost metrics
    console.print(f"[bold]Total Cost:[/bold] {_format_cost(stats.total_cost_usd)}")
    if stats.total_tasks > 0:
        console.print(f"Average per task: {_format_cost(stats.average_cost_per_task)}")
        console.print(
            f"Min: {_format_cost(stats.min_cost_usd)} / "
            f"Max: {_format_cost(stats.max_cost_usd)}"
        )
    console.print()

    # Token metrics
    console.print(f"[bold]Total Tokens:[/bold] {stats.total_tokens:,}")
    if stats.total_tasks > 0:
        console.print(f"Average per task: {stats.average_tokens_per_task:,}")
    console.print()

    # Time metrics
    if stats.total_duration_seconds > 0:
        console.print(f"[bold]Total Time:[/bold] {stats.total_duration_hours:.1f} hours")
        console.print(f"Average per task: {stats.average_duration_minutes:.1f} minutes")
        console.print()

    # Verification
    console.print("[bold]Verification:[/bold]")
    console.print(f"  Verified: [green]{stats.tasks_verified}[/green]")
    console.print(f"  Failed: [red]{stats.tasks_failed}[/red]")
    if stats.total_tasks > 0:
        console.print(f"  Rate: {stats.verification_rate * 100:.1f}%")
    console.print()

    # File metrics
    console.print("[bold]Files:[/bold]")
    console.print(f"  Total changes: {stats.total_files_changed}")
    console.print(f"  Unique files: {stats.unique_files_changed}")
    console.print()

    # Temporal
    if stats.first_task_date:
        console.print(f"First task: {stats.first_task_date.strftime('%Y-%m-%d')}")
    if stats.last_task_date:
        console.print(f"Last task: {stats.last_task_date.strftime('%Y-%m-%d')}")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    fields: list[str] | None = typer.Option(
        None,
        "--field",
        "-f",
        help="Fields to search (title, files, spec). Can be repeated. Default: all",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Only include tasks completed since date (YYYY-MM-DD)",
    ),
    epic: str | None = typer.Option(
        None,
        "--epic",
        help="Only include tasks in this epic",
    ),
    verification: str | None = typer.Option(
        None,
        "--verification",
        help="Filter by verification status (pass, fail, warn, skip, pending, error)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Search for tasks in the ledger.

    Searches task titles, files changed, and spec files for the query string.
    Returns matching tasks with basic information.

    Examples:
        cub ledger search "auth"
        cub ledger search "api" --field files
        cub ledger search "bug" --since 2026-01-01
        cub ledger search "login" --epic cub-vd6 --json
    """
    reader = _get_ledger_reader()

    if not reader.exists():
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    # Parse verification status
    verification_status = None
    if verification:
        try:
            verification_status = VerificationStatus(verification)
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid verification status: {verification}")
            console.print("Valid values: pass, fail, warn, skip, pending, error")
            raise typer.Exit(1)

    # Search tasks
    results = reader.search_tasks(query, fields=fields)

    # Apply additional filters
    if since:
        results = [r for r in results if r.completed >= since]
    if epic:
        results = [r for r in results if r.epic == epic]
    if verification_status:
        results = [r for r in results if r.verification == verification_status.value]

    if not results:
        console.print(f"No tasks found matching '{query}'")
        raise typer.Exit(0)

    if json_output:
        data = [r.model_dump() for r in results]
        console.print(json.dumps(data, indent=2))
        return

    # Rich formatted table
    console.print(f"\n[bold]Found {len(results)} task(s) matching '{query}'[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Date")
    table.add_column("Cost", justify="right")
    table.add_column("Verify")
    table.add_column("Epic", style="dim")

    for entry in results:
        table.add_row(
            entry.id,
            entry.title[:50] + "..." if len(entry.title) > 50 else entry.title,
            entry.completed,
            f"${entry.cost_usd:.2f}",
            _format_verification(entry.verification),
            entry.epic or "",
        )

    console.print(table)
    console.print()
    console.print(f"Total cost: {_format_cost(sum(r.cost_usd for r in results))}")
