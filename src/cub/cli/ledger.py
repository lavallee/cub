"""
Cub CLI - Ledger commands.

Query and display completed work records from the ledger system.
"""

import json
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from cub.core.ledger.models import VerificationStatus
from cub.core.ledger.reader import LedgerReader
from cub.utils.project import get_project_root

if TYPE_CHECKING:
    from cub.core.ledger.models import LedgerEntry

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


def _format_duration(seconds: int) -> str:
    """Format duration in a human-readable way."""
    if seconds == 0:
        return "[dim]0s[/dim]"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def _format_workflow_stage(stage: str | None) -> str:
    """Format workflow stage with color."""
    if not stage:
        return "[dim]dev_complete[/dim]"

    stage_colors = {
        "dev_complete": "[dim]dev_complete[/dim]",
        "needs_review": "[yellow]needs_review[/yellow]",
        "validated": "[green]validated[/green]",
        "released": "[blue]released[/blue]",
    }
    return stage_colors.get(stage, stage)


def _show_attempt_detail(entry: "LedgerEntry", attempt_num: int) -> None:
    """Show detailed information for a specific attempt."""
    from cub.core.ledger.models import LedgerEntry  # noqa: F401

    # Find the attempt
    attempt_obj = None
    for att in entry.attempts:
        if att.attempt_number == attempt_num:
            attempt_obj = att
            break

    if not attempt_obj:
        console.print(
            f"[red]Error:[/red] Attempt {attempt_num} not found. "
            f"Task has {len(entry.attempts)} attempt(s)."
        )
        raise typer.Exit(1)

    # Display attempt details
    console.print(f"\n[bold]Attempt #{attempt_obj.attempt_number}[/bold] for {entry.id}")
    console.print()

    # Basic info
    console.print(f"Run ID: {attempt_obj.run_id}")
    console.print(f"Harness: {attempt_obj.harness}")
    console.print(f"Model: {attempt_obj.model}")
    console.print()

    # Timing
    console.print(f"Started: {attempt_obj.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if attempt_obj.completed_at:
        console.print(f"Completed: {attempt_obj.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    console.print(f"Duration: {_format_duration(attempt_obj.duration_seconds)}")
    console.print()

    # Cost and tokens
    console.print(f"Cost: {_format_cost(attempt_obj.cost_usd)}")
    console.print(f"Tokens: {attempt_obj.tokens.total_tokens:,}")
    if attempt_obj.tokens.total_tokens > 0:
        console.print(f"  Input: {attempt_obj.tokens.input_tokens:,}")
        console.print(f"  Output: {attempt_obj.tokens.output_tokens:,}")
        if attempt_obj.tokens.cache_read_tokens > 0:
            console.print(f"  Cache read: {attempt_obj.tokens.cache_read_tokens:,}")
        if attempt_obj.tokens.cache_creation_tokens > 0:
            console.print(f"  Cache creation: {attempt_obj.tokens.cache_creation_tokens:,}")
    console.print()

    # Status
    if attempt_obj.success:
        console.print("Status: [green]Success ✓[/green]")
    else:
        console.print("Status: [red]Failed ✗[/red]")
        if attempt_obj.error_category:
            console.print(f"Error Category: [red]{attempt_obj.error_category}[/red]")
        if attempt_obj.error_summary:
            console.print(f"Error Summary: {attempt_obj.error_summary}")


@app.command()
def show(
    task_id: str = typer.Argument(..., help="Task ID to display"),
    attempt: int | None = typer.Option(
        None,
        "--attempt",
        "-a",
        help="Show details for a specific attempt number",
    ),
    changes: bool = typer.Option(
        False,
        "--changes",
        "-c",
        help="Show detailed file changes and commits",
    ),
    history: bool = typer.Option(
        False,
        "--history",
        "-h",
        help="Show workflow stage transition history",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Show detailed ledger entry for a task.

    Displays the full ledger record including lineage, attempts, outcome,
    approach, decisions, commits, files changed, token usage, verification
    status, and workflow stage.

    Examples:
        cub ledger show beads-abc
        cub ledger show beads-abc --attempt 2
        cub ledger show beads-abc --changes
        cub ledger show beads-abc --history
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

    # If --attempt flag is used, show only that specific attempt
    if attempt is not None:
        _show_attempt_detail(entry, attempt)
        return

    # Rich formatted output
    console.print(f"\n[bold]{entry.title}[/bold] ({entry.id})")
    console.print()

    # Lineage tracking (NEW)
    console.print("[bold]Lineage:[/bold]")
    if entry.lineage.epic_id:
        console.print(f"  Epic: {entry.lineage.epic_id}")
    if entry.lineage.spec_file:
        console.print(f"  Spec: {entry.lineage.spec_file}")
    if entry.lineage.plan_file:
        console.print(f"  Plan: {entry.lineage.plan_file}")
    if not entry.lineage.epic_id and not entry.lineage.spec_file and not entry.lineage.plan_file:
        console.print("  [dim]No lineage tracked[/dim]")
    console.print()

    # Workflow stage (NEW)
    current_stage = entry.workflow.stage if entry.workflow else "dev_complete"
    console.print(f"Workflow Stage: {_format_workflow_stage(current_stage)}")
    if entry.workflow and entry.workflow.stage_updated_at:
        console.print(
            f"  Updated: {entry.workflow.stage_updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
    console.print()

    # Outcome summary (NEW)
    if entry.outcome:
        console.print("[bold]Outcome:[/bold]")
        status = "[green]Success[/green]" if entry.outcome.success else "[red]Failed[/red]"
        if entry.outcome.partial:
            status = "[yellow]Partial[/yellow]"
        console.print(f"  Status: {status}")
        console.print(f"  Total Cost: {_format_cost(entry.outcome.total_cost_usd)}")
        console.print(f"  Total Duration: {_format_duration(entry.outcome.total_duration_seconds)}")
        console.print(f"  Total Attempts: {entry.outcome.total_attempts}")
        if entry.outcome.escalated:
            console.print("  [yellow]Escalated:[/yellow] Yes")
            if entry.outcome.escalation_path:
                console.print(f"    Path: {' → '.join(entry.outcome.escalation_path)}")
        if entry.outcome.final_model:
            console.print(f"  Final Model: {entry.outcome.final_model}")
        console.print()

    # Attempts summary (NEW)
    if entry.attempts:
        console.print(f"[bold]Attempts ({len(entry.attempts)}):[/bold]")
        attempts_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        attempts_table.add_column("#", style="cyan", width=3)
        attempts_table.add_column("Model", style="yellow")
        attempts_table.add_column("Duration", justify="right")
        attempts_table.add_column("Cost", justify="right")
        attempts_table.add_column("Status")

        for att in entry.attempts[:10]:  # Show first 10 attempts in summary
            status = "[green]✓[/green]" if att.success else "[red]✗[/red]"
            if att.error_category:
                status = f"[red]✗ {att.error_category}[/red]"

            attempts_table.add_row(
                str(att.attempt_number),
                att.model or att.harness or "[dim]unknown[/dim]",
                _format_duration(att.duration_seconds),
                f"${att.cost_usd:.2f}",
                status,
            )

        console.print(attempts_table)
        if len(entry.attempts) > 10:
            console.print(f"  ... and {len(entry.attempts) - 10} more attempts")
        console.print("  [dim]Use --attempt N to see details[/dim]")
        console.print()

    # Basic info (keep for backward compatibility)
    if entry.completed_at:
        console.print(f"Completed: {entry.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if entry.started_at:
        console.print(f"Started: {entry.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    if entry.duration_seconds > 0:
        console.print(f"Duration: {_format_duration(entry.duration_seconds)}")
    console.print()

    # Cost and tokens (legacy fields)
    if not entry.outcome:  # Only show if outcome doesn't exist
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

    # Harness (legacy)
    if entry.harness_name and not entry.attempts:
        console.print(f"Harness: {entry.harness_name}", end="")
        if entry.harness_model:
            console.print(f" ({entry.harness_model})")
        else:
            console.print()

    # Verification (updated to use new verification object)
    if entry.verification:
        console.print(f"Verification: {_format_verification(entry.verification.status)}")
        if entry.verification.notes:
            for note in entry.verification.notes:
                console.print(f"  • {note}")
        if entry.verification.checked_at:
            console.print(
                f"  Checked: {entry.verification.checked_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
    else:
        # Fallback to legacy fields
        console.print(f"Verification: {_format_verification(entry.verification_status.value)}")
        if entry.verification_notes:
            for note in entry.verification_notes:
                console.print(f"  • {note}")
    console.print()

    # Task change detection (NEW)
    if entry.task_changed:
        console.print("[bold][yellow]Task Changed During Implementation:[/yellow][/bold]")
        console.print(
            f"  Detected: {entry.task_changed.detected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        if entry.task_changed.fields_changed:
            console.print(f"  Fields: {', '.join(entry.task_changed.fields_changed)}")
        if entry.task_changed.notes:
            console.print(f"  Notes: {entry.task_changed.notes}")
        console.print()

    # Approach (prefer outcome.approach if available)
    approach_text = (
        entry.outcome.approach
        if entry.outcome and entry.outcome.approach
        else entry.approach
    )
    if approach_text:
        console.print("[bold]Approach:[/bold]")
        console.print(approach_text)
        console.print()

    # Decisions (prefer outcome.decisions if available)
    decisions_list = (
        entry.outcome.decisions
        if entry.outcome and entry.outcome.decisions
        else entry.decisions
    )
    if decisions_list:
        console.print("[bold]Key Decisions:[/bold]")
        for decision in decisions_list:
            console.print(f"  • {decision}")
        console.print()

    # Lessons learned (prefer outcome.lessons_learned if available)
    lessons_list = (
        entry.outcome.lessons_learned
        if entry.outcome and entry.outcome.lessons_learned
        else entry.lessons_learned
    )
    if lessons_list:
        console.print("[bold]Lessons Learned:[/bold]")
        for lesson in lessons_list:
            console.print(f"  • {lesson}")
        console.print()

    # Workflow history (NEW - shown with --history flag)
    if history and entry.state_history:
        console.print(f"[bold]Workflow History ({len(entry.state_history)}):[/bold]")
        history_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        history_table.add_column("Stage", style="cyan")
        history_table.add_column("When")
        history_table.add_column("By", style="dim")
        history_table.add_column("Reason", style="dim")

        for transition in entry.state_history:
            history_table.add_row(
                _format_workflow_stage(transition.stage),
                transition.at.strftime("%Y-%m-%d %H:%M:%S"),
                transition.by or "[dim]unknown[/dim]",
                transition.reason or "[dim]—[/dim]",
            )

        console.print(history_table)
        console.print()

    # Files changed (with --changes flag for detailed view)
    files_list = (
        entry.outcome.files_changed
        if entry.outcome and entry.outcome.files_changed
        else entry.files_changed
    )
    if files_list:
        if changes:
            console.print(f"[bold]Files Changed ({len(files_list)}):[/bold]")
            for file in files_list:
                console.print(f"  • {file}")
        else:
            console.print(f"[bold]Files Changed ({len(files_list)}):[/bold]")
            for file in files_list[:10]:  # Show first 10
                console.print(f"  • {file}")
            if len(files_list) > 10:
                console.print(f"  ... and {len(files_list) - 10} more")
                console.print("  [dim]Use --changes to see all files[/dim]")
        console.print()

    # Commits (with --changes flag for detailed view)
    commits_list = (
        entry.outcome.commits if entry.outcome and entry.outcome.commits else entry.commits
    )
    if commits_list:
        if changes:
            console.print(f"[bold]Commits ({len(commits_list)}):[/bold]")
            for commit in commits_list:
                console.print(f"  • {commit.short_hash} - {commit.message}")
                if commit.author:
                    console.print(f"    Author: {commit.author}")
                console.print(
                    f"    Time: {commit.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
        else:
            console.print(f"[bold]Commits ({len(commits_list)}):[/bold]")
            for commit in commits_list[:5]:  # Show first 5
                console.print(f"  • {commit.short_hash} - {commit.message}")
            if len(commits_list) > 5:
                console.print(f"  ... and {len(commits_list) - 5} more")
                console.print("  [dim]Use --changes to see all commits[/dim]")
        console.print()

    # Drift tracking (NEW)
    if entry.drift and (entry.drift.additions or entry.drift.omissions):
        console.print("[bold]Spec Drift:[/bold]")
        console.print(f"  Severity: {entry.drift.severity}")
        if entry.drift.additions:
            console.print("  Additions beyond spec:")
            for addition in entry.drift.additions:
                console.print(f"    • {addition}")
        if entry.drift.omissions:
            console.print("  Omissions from spec:")
            for omission in entry.drift.omissions:
                console.print(f"    • {omission}")
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
