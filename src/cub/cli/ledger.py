"""
Cub CLI - Ledger commands.

Query and display completed work records from the ledger system.
"""

import csv
import json
import sys
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from cub.core.ledger.extractor import extract_insights
from cub.core.ledger.models import VerificationStatus
from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.writer import LedgerWriter
from cub.core.services.ledger import LedgerQuery, LedgerService, StatsQuery
from cub.core.tasks.backend import get_backend as get_task_backend
from cub.utils.project import get_project_root

if TYPE_CHECKING:
    from cub.core.ledger.models import LedgerEntry

app = typer.Typer(
    name="ledger",
    help="Query completed work ledger",
    no_args_is_help=True,
)

console = Console()


def _get_ledger_service() -> LedgerService | None:
    """Get ledger service for current project, or None if ledger doesn't exist."""
    project_root = get_project_root()
    return LedgerService.try_from_project_dir(project_root)


def _get_ledger_reader() -> LedgerReader:
    """Get ledger reader for current project."""
    project_root = get_project_root()
    ledger_dir = project_root / ".cub" / "ledger"
    return LedgerReader(ledger_dir)


def _get_ledger_writer() -> LedgerWriter:
    """Get ledger writer for current project."""
    project_root = get_project_root()
    ledger_dir = project_root / ".cub" / "ledger"
    return LedgerWriter(ledger_dir)


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
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly markdown format",
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
    service = _get_ledger_service()

    if not service:
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    try:
        entry = service.get_task(task_id)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # --agent wins over --json
    if agent:
        # Agent-friendly markdown output for a single ledger entry
        output = f"# cub ledger show {entry.id}\n\n"
        output += f"## {entry.title}\n\n"

        # Summary
        if entry.outcome:
            status = "Success" if entry.outcome.success else "Failed"
            if entry.outcome.partial:
                status = "Partial"
            output += f"**Status**: {status}  \n"
            output += f"**Cost**: ${entry.outcome.total_cost_usd:.2f}  \n"
            output += f"**Duration**: {_format_duration(entry.outcome.total_duration_seconds)}  \n"
            output += f"**Attempts**: {entry.outcome.total_attempts}  \n"
        else:
            output += f"**Cost**: ${entry.cost_usd:.2f}  \n"
            output += f"**Duration**: {_format_duration(entry.duration_seconds)}  \n"

        # Verification
        if entry.verification:
            output += f"**Verification**: {entry.verification.status}  \n"
        else:
            output += f"**Verification**: {entry.verification_status.value}  \n"

        # Workflow stage
        current_stage = entry.workflow.stage if entry.workflow else "dev_complete"
        output += f"**Workflow Stage**: {current_stage}  \n"

        # Approach
        approach_text = (
            entry.outcome.approach
            if entry.outcome and entry.outcome.approach
            else entry.approach
        )
        if approach_text:
            output += f"\n## Approach\n\n{approach_text}\n"

        # Decisions
        decisions_list = (
            entry.outcome.decisions
            if entry.outcome and entry.outcome.decisions
            else entry.decisions
        )
        if decisions_list:
            output += "\n## Key Decisions\n\n"
            for decision in decisions_list:
                output += f"- {decision}\n"

        # Files changed
        files_list = (
            entry.outcome.files_changed
            if entry.outcome and entry.outcome.files_changed
            else entry.files_changed
        )
        if files_list:
            output += f"\n## Files Changed ({len(files_list)})\n\n"
            for file in files_list[:10]:
                output += f"- {file}\n"
            if len(files_list) > 10:
                output += f"\n*... and {len(files_list) - 10} more*\n"

        console.print(output.rstrip())
        return

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
def update(
    task_id: str = typer.Argument(..., help="Task ID to update"),
    stage: str = typer.Option(
        ...,
        "--stage",
        "-s",
        help="New workflow stage: dev_complete, needs_review, validated, or released",
    ),
    reason: str | None = typer.Option(
        None,
        "--reason",
        "-r",
        help="Reason for the stage transition",
    ),
) -> None:
    """
    Update workflow stage for a completed task.

    Transitions a task through post-completion stages and records the change
    in the task's state history. Use this to mark tasks as reviewed, validated,
    or released after development is complete.

    Examples:
        cub ledger update cub-abc --stage needs_review
        cub ledger update cub-abc --stage validated --reason "Tests passed"
        cub ledger update cub-abc -s released -r "Deployed to production"
    """
    service = _get_ledger_service()

    if not service:
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(1)

    # Update the workflow stage using service
    try:
        service.update_workflow_stage(task_id, stage, reason=reason, by="cli")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Display confirmation
    console.print()
    console.print(f"[green]✓[/green] Updated workflow stage for {task_id}")
    console.print(f"  Stage: {_format_workflow_stage(stage)}")
    if reason:
        console.print(f"  Reason: {reason}")
    console.print()


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
    service = _get_ledger_service()

    if not service:
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(0)

    query = StatsQuery(since=since, epic=epic)
    stats = service.stats(query)

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
    stage: str | None = typer.Option(
        None,
        "--stage",
        help="Filter by workflow stage (dev_complete, needs_review, validated, released)",
    ),
    cost_above: float | None = typer.Option(
        None,
        "--cost-above",
        help="Filter to tasks with cost above this threshold (USD)",
    ),
    escalated: bool | None = typer.Option(
        None,
        "--escalated",
        help="Filter to tasks that were escalated (true) or not escalated (false)",
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
    Returns matching tasks with basic information. Supports filtering by
    workflow stage, cost threshold, and escalation status.

    Examples:
        cub ledger search "auth"
        cub ledger search "api" --field files
        cub ledger search "bug" --since 2026-01-01
        cub ledger search "login" --epic cub-vd6 --json
        cub ledger search "feature" --stage needs_review
        cub ledger search "complex" --cost-above 0.50
        cub ledger search "hard" --escalated true
    """
    service = _get_ledger_service()

    if not service:
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

    # Validate stage
    if stage:
        valid_stages = {"dev_complete", "needs_review", "validated", "released"}
        if stage not in valid_stages:
            console.print(
                f"[red]Error:[/red] Invalid stage '{stage}'. "
                f"Must be one of: {', '.join(sorted(valid_stages))}"
            )
            raise typer.Exit(1)

    # Build query filters
    filters = LedgerQuery(
        since=since,
        epic=epic,
        verification=verification_status,
        stage=stage,
        cost_above=cost_above,
        escalated=escalated,
    )

    # Search tasks using service
    results = service.search(query, fields=fields, filters=filters)

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


@app.command()
def export(
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json or csv",
    ),
    epic: str | None = typer.Option(
        None,
        "--epic",
        "-e",
        help="Only export tasks in this epic",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Only include tasks completed since date (YYYY-MM-DD)",
    ),
) -> None:
    """
    Export ledger data for external analysis or reporting.

    Exports completed task data in JSON or CSV format for use in spreadsheets,
    reporting tools, or custom analysis scripts.

    Examples:
        cub ledger export --format json --output ledger.json
        cub ledger export --format csv --epic cub-vd6 --output epic.csv
        cub ledger export --format json --since 2026-01-01 > recent.json
    """
    service = _get_ledger_service()

    if not service:
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "Tasks have not been completed yet."
        )
        raise typer.Exit(1)

    # Validate format
    if format not in ["json", "csv"]:
        console.print(f"[red]Error:[/red] Invalid format '{format}'. Must be 'json' or 'csv'")
        raise typer.Exit(1)

    # Get entries using service
    filters = LedgerQuery(since=since, epic=epic)
    entries = service.query(filters)

    if not entries:
        console.print("[yellow]Warning:[/yellow] No tasks found matching filters")
        raise typer.Exit(0)

    # Get full entries for export
    full_entries = []
    for index_entry in entries:
        try:
            full_entry = service.get_task(index_entry.id)
            full_entries.append(full_entry)
        except Exception:
            # Skip entries that fail to load
            continue

    # Export data
    if format == "json":
        _export_json(full_entries, output)
    else:
        _export_csv(full_entries, output)

    # Print confirmation if writing to file
    if output:
        console.print(f"[green]✓[/green] Exported {len(full_entries)} task(s) to {output}")


def _export_json(entries: list["LedgerEntry"], output: str | None) -> None:
    """Export entries as JSON."""
    data = [entry.model_dump(mode="json") for entry in entries]
    json_str = json.dumps(data, indent=2, default=str)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(json_str)
    else:
        sys.stdout.write(json_str)
        sys.stdout.write("\n")


def _export_csv(entries: list["LedgerEntry"], output: str | None) -> None:
    """Export entries as CSV with flattened fields."""
    if not entries:
        return

    # Define flattened fields for CSV
    fieldnames = [
        "id",
        "title",
        "completed_at",
        "started_at",
        "duration_seconds",
        "cost_usd",
        "tokens_total",
        "tokens_input",
        "tokens_output",
        "tokens_cache_read",
        "tokens_cache_creation",
        "harness_name",
        "harness_model",
        "verification_status",
        "workflow_stage",
        "epic_id",
        "spec_file",
        "files_changed_count",
        "commits_count",
        "iterations",
        "outcome_success",
        "outcome_partial",
        "outcome_total_attempts",
        "outcome_total_cost_usd",
        "outcome_escalated",
        "outcome_final_model",
    ]

    # Prepare rows
    rows = []
    for entry in entries:
        # Handle outcome fields (prefer outcome data if available)
        outcome_success = entry.outcome.success if entry.outcome else False
        outcome_partial = entry.outcome.partial if entry.outcome else False
        outcome_total_attempts = entry.outcome.total_attempts if entry.outcome else entry.iterations
        outcome_total_cost_usd = entry.outcome.total_cost_usd if entry.outcome else entry.cost_usd
        outcome_escalated = entry.outcome.escalated if entry.outcome else False
        outcome_final_model = entry.outcome.final_model if entry.outcome else entry.harness_model

        # Handle workflow stage (prefer workflow object if available)
        workflow_stage = entry.workflow.stage if entry.workflow else (
            entry.workflow_stage.value if entry.workflow_stage else "dev_complete"
        )

        row = {
            "id": entry.id,
            "title": entry.title,
            "completed_at": entry.completed_at.isoformat() if entry.completed_at else "",
            "started_at": entry.started_at.isoformat() if entry.started_at else "",
            "duration_seconds": entry.duration_seconds,
            "cost_usd": entry.cost_usd,
            "tokens_total": entry.tokens.total_tokens,
            "tokens_input": entry.tokens.input_tokens,
            "tokens_output": entry.tokens.output_tokens,
            "tokens_cache_read": entry.tokens.cache_read_tokens,
            "tokens_cache_creation": entry.tokens.cache_creation_tokens,
            "harness_name": entry.harness_name,
            "harness_model": entry.harness_model,
            "verification_status": entry.verification_status.value,
            "workflow_stage": workflow_stage,
            "epic_id": entry.epic_id or "",
            "spec_file": entry.spec_file or "",
            "files_changed_count": len(entry.files_changed),
            "commits_count": len(entry.commits),
            "iterations": entry.iterations,
            "outcome_success": outcome_success,
            "outcome_partial": outcome_partial,
            "outcome_total_attempts": outcome_total_attempts,
            "outcome_total_cost_usd": outcome_total_cost_usd,
            "outcome_escalated": outcome_escalated,
            "outcome_final_model": outcome_final_model,
        }
        rows.append(row)

    # Write CSV
    if output:
        with open(output, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


@app.command()
def gc(
    keep_latest: int = typer.Option(
        5,
        "--keep-latest",
        "-k",
        help="Number of latest attempts to keep per task",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run",
        help="Show what would be deleted without actually deleting (always true for now)",
    ),
) -> None:
    """
    Garbage collect old attempt files.

    Scans all task directories and identifies attempt files that would be
    deleted based on the retention policy. Currently runs in dry-run mode only
    (shows what would be deleted without actually deleting).

    For each task, keeps only the N most recent attempt files (prompt and log),
    and identifies older attempts that could be removed.

    Examples:
        cub ledger gc
        cub ledger gc --keep-latest 3
        cub ledger gc -k 10
    """
    reader = _get_ledger_reader()

    if not reader.exists():
        console.print(
            "[yellow]Warning:[/yellow] No ledger found. "
            "No attempt files to garbage collect."
        )
        raise typer.Exit(0)

    ledger_dir = reader.ledger_dir
    by_task_dir = ledger_dir / "by-task"

    if not by_task_dir.exists():
        console.print(
            "[yellow]Warning:[/yellow] No task directories found. "
            "No attempt files to garbage collect."
        )
        raise typer.Exit(0)

    # Scan all task directories for attempt files
    total_files = 0
    total_size_bytes = 0
    task_summary = []

    for task_dir in sorted(by_task_dir.iterdir()):
        if not task_dir.is_dir():
            continue

        attempts_dir = task_dir / "attempts"
        if not attempts_dir.exists():
            continue

        # Get all attempt files, sorted by modification time (oldest first)
        attempt_files = sorted(
            attempts_dir.iterdir(),
            key=lambda p: p.stat().st_mtime
        )

        if not attempt_files:
            continue

        # Determine which files to keep
        # Keep only the latest attempt files based on attempt number
        files_to_delete = []
        if len(attempt_files) > keep_latest:
            files_to_delete = attempt_files[:-keep_latest]

        if files_to_delete:
            files_count = len(files_to_delete)
            files_size = sum(f.stat().st_size for f in files_to_delete)
            total_files += files_count
            total_size_bytes += files_size

            task_summary.append({
                "task_id": task_dir.name,
                "files_to_delete": files_count,
                "size_bytes": files_size,
                "files": [f.name for f in files_to_delete],
            })

    # Display summary
    console.print()
    console.print("[bold]Ledger Garbage Collection (Dry Run)[/bold]")
    console.print()

    if total_files == 0:
        console.print("[dim]No attempt files would be deleted.[/dim]")
        console.print(f"All tasks have {keep_latest} or fewer attempt files.")
        raise typer.Exit(0)

    # Show details for tasks with files to delete
    if task_summary:
        console.print(f"[bold]Tasks with old attempt files ({len(task_summary)}):[/bold]\n")

        details_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        details_table.add_column("Task ID", style="cyan")
        details_table.add_column("Files to Delete", justify="right")
        details_table.add_column("Size", justify="right")

        for summary in task_summary:
            size_bytes: float = summary["size_bytes"]  # type: ignore
            size_mb = size_bytes / (1024 * 1024)
            files_to_delete: int = summary["files_to_delete"]  # type: ignore
            task_id: str = summary["task_id"]  # type: ignore
            details_table.add_row(
                task_id,
                str(files_to_delete),
                f"{size_mb:.2f} MB" if size_mb > 0 else "~0 MB",
            )

        console.print(details_table)
        console.print()

    # Summary line
    total_size_float: float = float(total_size_bytes)
    size_mb = total_size_float / (1024 * 1024)
    console.print("[bold]Summary:[/bold]")
    console.print(
        f"Would delete [yellow]{total_files}[/yellow] file(s), "
        f"freeing [yellow]~{size_mb:.2f} MB[/yellow]"
    )
    console.print()
    console.print("[dim]Note: This is a dry-run. Files are not actually deleted.[/dim]")
    console.print("[dim]Future versions will support actual deletion with --dry-run=false.[/dim]")


@app.command()
def extract(
    task_id: str | None = typer.Argument(None, help="Task ID to extract insights for (or --all)"),
    all_tasks: bool = typer.Option(
        False,
        "--all",
        help="Extract insights for all tasks with empty lessons_learned",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Re-extract insights even if already present",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed extraction output",
    ),
) -> None:
    """
    Extract insights (approach, decisions, lessons learned) from task execution logs.

    Uses Claude Haiku to analyze harness execution logs and extract structured
    insights. Can process a single task or batch process all tasks.

    Examples:
        cub ledger extract cub-abc       # Extract for single task
        cub ledger extract --all         # Extract for all tasks
        cub ledger extract --all --force # Re-extract all tasks
    """
    service = _get_ledger_service()

    if not service:
        console.print("[yellow]Warning:[/yellow] No ledger found.")
        raise typer.Exit(1)

    # Get writer for low-level file access (prompt/log files)
    writer = _get_ledger_writer()

    # Determine which tasks to process
    tasks_to_process: list[str] = []
    if all_tasks:
        # Get all task IDs from service
        index_entries = service.query()
        for index_entry in index_entries:
            # Get full entry to check for insights
            if not force:
                try:
                    full_entry = service.get_task(index_entry.id)
                except Exception:
                    continue
                if full_entry and full_entry.outcome:
                    has_insights = (
                        full_entry.outcome.approach
                        or full_entry.outcome.decisions
                        or full_entry.outcome.lessons_learned
                    )
                    if has_insights:
                        continue
            tasks_to_process.append(index_entry.id)
    elif task_id:
        tasks_to_process = [task_id]
    else:
        console.print("[red]Error:[/red] Must specify task ID or use --all")
        raise typer.Exit(1)

    if not tasks_to_process:
        console.print("[dim]No tasks need insight extraction.[/dim]")
        raise typer.Exit(0)

    console.print(f"[bold]Extracting insights for {len(tasks_to_process)} task(s)...[/bold]\n")

    # Get task backend for task context
    try:
        task_backend = get_task_backend()
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Could not load task backend: {e}")
        task_backend = None

    # Process each task
    success_count = 0
    skip_count = 0
    error_count = 0

    for idx, tid in enumerate(tasks_to_process, 1):
        console.print(f"[{idx}/{len(tasks_to_process)}] Processing [cyan]{tid}[/cyan]...")

        # Get ledger entry
        try:
            entry = service.get_task(tid)
        except Exception:
            console.print("  [red]✗[/red] Entry not found")
            error_count += 1
            continue

        # Check if extraction needed
        if not force and entry.outcome:
            has_insights = (
                entry.outcome.approach
                or entry.outcome.decisions
                or entry.outcome.lessons_learned
            )
            if has_insights:
                console.print(
                    "  [dim]↷[/dim] Already has insights (use --force to re-extract)"
                )
                skip_count += 1
                continue

        # Get harness log from first attempt
        if not entry.attempts:
            console.print("  [yellow]⚠[/yellow] No attempts found")
            skip_count += 1
            continue

        # Read harness log file
        attempt_num = entry.attempts[0].attempt_number
        log_filename = f"{attempt_num:03d}-harness.log"
        log_path = writer.ledger_dir / "by-task" / tid / "attempts" / log_filename
        if not log_path.exists():
            console.print(f"  [yellow]⚠[/yellow] Harness log not found: {log_path.name}")
            skip_count += 1
            continue

        try:
            harness_log = log_path.read_text()
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed to read log: {e}")
            error_count += 1
            continue

        # Get task object for context
        task = None
        if task_backend:
            try:
                task = task_backend.get_task(tid)
            except Exception:
                pass  # Task might not exist in backend anymore

        # Create minimal task if not found
        if not task:
            from cub.core.tasks.models import Task
            task = Task(
                id=tid,
                title=entry.title,
                description=entry.task.description if entry.task else "",
            )

        # Extract insights
        try:
            insights = extract_insights(harness_log, task)
        except Exception as e:
            console.print(f"  [red]✗[/red] Extraction failed: {e}")
            error_count += 1
            continue

        if not insights.success:
            console.print(f"  [red]✗[/red] Extraction failed: {insights.error}")
            error_count += 1
            continue

        # Update ledger entry
        if entry.outcome:
            entry.outcome.approach = insights.approach
            entry.outcome.decisions = insights.decisions
            entry.outcome.lessons_learned = insights.lessons_learned

        # Update legacy fields
        entry.approach = insights.approach or ""
        entry.decisions = insights.decisions
        entry.lessons_learned = insights.lessons_learned

        # Write updated entry
        try:
            writer.update_entry(entry)
            console.print("  [green]✓[/green] Extracted insights")
            if verbose:
                if insights.approach:
                    console.print(f"    Approach: {insights.approach[:80]}...")
                console.print(f"    Decisions: {len(insights.decisions)}")
                console.print(f"    Lessons: {len(insights.lessons_learned)}")
            success_count += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed to update entry: {e}")
            error_count += 1

    # Summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Success: [green]{success_count}[/green]")
    console.print(f"  Skipped: [dim]{skip_count}[/dim]")
    console.print(f"  Errors: [red]{error_count}[/red]")

    if error_count > 0:
        raise typer.Exit(1)
