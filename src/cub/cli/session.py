"""
Cub CLI - Direct Session Commands.

These commands are designed for manual harness sessions (Claude Code, Codex, OpenCode)
to record their work in the ledger. They bridge the gap between direct harness usage
and the structured ledger system that `cub run` uses automatically.

Direct session commands:
- cub log <message>: Add timestamped log entry
- cub done <task-id>: Mark task complete and create ledger entry
- cub wip <task-id>: Mark task as in-progress
"""

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from cub.core.config.loader import load_config
from cub.core.ledger.integration import LedgerIntegration
from cub.core.ledger.models import (
    Attempt,
    LedgerEntry,
    Lineage,
    Outcome,
    StateTransition,
    TaskSnapshot,
    TokenUsage,
    Verification,
    WorkflowState,
)
from cub.core.ledger.writer import LedgerWriter
from cub.core.tasks.backend import get_backend
from cub.core.tasks.models import TaskStatus

console = Console()
app = typer.Typer(
    help="Direct session commands for recording work",
    no_args_is_help=True,
)


def _get_session_log_path() -> Path:
    """Get the path to the session log file."""
    cub_dir = Path(".cub")
    cub_dir.mkdir(exist_ok=True)
    return cub_dir / "session.log"


def _get_ledger_dir() -> Path:
    """Get the ledger directory path."""
    config = load_config()
    if not config.ledger.enabled:
        console.print("[yellow]Warning:[/yellow] Ledger is disabled in config")
    return Path(".cub/ledger")


@app.command()
def log(
    message: str = typer.Argument(..., help="Log message to record"),
) -> None:
    """
    Add a timestamped entry to the session log.

    This creates a running log of work done in direct harness sessions,
    providing an audit trail similar to what `cub run` creates automatically.

    Examples:
        cub log "Started working on authentication feature"
        cub log "Fixed bug in user validation logic"
        cub log "All tests passing, ready to commit"
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    log_path = _get_session_log_path()

    # Append to session log
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

    console.print(f"[green]✓[/green] Logged: {message}")
    console.print(f"[dim]  → {log_path}[/dim]")


@app.command()
def done(
    task_id: str = typer.Argument(..., help="Task ID to mark as complete"),
    reason: str | None = typer.Option(
        None,
        "--reason",
        "-r",
        help="Reason or summary of completion",
    ),
    files: list[str] | None = typer.Option(
        None,
        "--file",
        "-f",
        help="Files changed during task (can be repeated)",
    ),
) -> None:
    """
    Mark a task as complete and create a ledger entry.

    This command records task completion in both the task backend and the
    ledger system, creating the same audit trail that `cub run` would create.
    All ledger entries created by this command are tagged with
    source="direct_session" for traceability.

    Examples:
        cub done cub-123
        cub done cub-456 --reason "Implemented user authentication"
        cub done cub-789 --file src/auth.py --file tests/test_auth.py
    """
    backend = get_backend()

    # Get task to verify it exists
    task = backend.get_task(task_id)
    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        raise typer.Exit(1)

    # Check if already closed
    if task.status == TaskStatus.CLOSED:
        console.print(f"[yellow]Warning:[/yellow] Task {task_id} is already closed")

    try:
        # Close task in backend
        backend.close_task(task_id, reason=reason)

        # Create ledger entry
        ledger_dir = _get_ledger_dir()
        writer = LedgerWriter(ledger_dir)
        integration = LedgerIntegration(writer)

        now = datetime.now(timezone.utc)

        # Check if entry already exists
        existing_entry = writer.get_entry(task_id)
        if existing_entry:
            # Update existing entry
            console.print(f"[yellow]Note:[/yellow] Updating existing ledger entry for {task_id}")

            # Finalize the entry
            integration.on_task_close(
                task_id,
                success=True,
                partial=False,
                final_model="direct-session",
                files_changed=files or [],
                commits=[],
                approach=reason,
                decisions=[],
                lessons_learned=[],
                verification=Verification(status="pending", notes=[]),
                current_task=task,
            )
        else:
            # Create new entry from scratch
            # Create task snapshot
            task_snapshot = TaskSnapshot(
                title=task.title,
                description=task.description,
                type=task.type.value if hasattr(task.type, "value") else str(task.type),
                priority=task.priority_numeric,
                labels=list(task.labels),
                created_at=task.created_at,
                captured_at=now,
            )

            # Create lineage
            lineage = Lineage(
                epic_id=task.parent,
            )

            # Create workflow state
            workflow = WorkflowState(
                stage="dev_complete",
                stage_updated_at=now,
            )

            # Create state history
            state_history = [
                StateTransition(
                    stage="dev_complete",
                    at=now,
                    by="direct-session",
                    reason=reason or "Task completed in direct session",
                )
            ]

            # Create a single attempt representing the direct session work
            attempt = Attempt(
                attempt_number=1,
                run_id="direct-session",
                started_at=now,
                completed_at=now,
                harness="direct-session",
                model="direct-session",
                success=True,
                tokens=TokenUsage(),
                cost_usd=0.0,
                duration_seconds=0,
            )

            # Create outcome
            outcome = Outcome(
                success=True,
                partial=False,
                completed_at=now,
                total_cost_usd=0.0,
                total_attempts=1,
                total_duration_seconds=0,
                final_model="direct-session",
                escalated=False,
                escalation_path=[],
                files_changed=files or [],
                commits=[],
                approach=reason,
                decisions=[],
                lessons_learned=[],
            )

            # Create ledger entry
            entry = LedgerEntry(
                id=task.id,
                title=task.title,
                lineage=lineage,
                task=task_snapshot,
                attempts=[attempt],
                outcome=outcome,
                started_at=now,
                completed_at=now,
                workflow=workflow,
                state_history=state_history,
                verification=Verification(status="pending", notes=[]),
                # Legacy fields
                epic_id=task.parent,
                run_log_path=str(ledger_dir / "by-task" / task.id),
                tokens=TokenUsage(),
                cost_usd=0.0,
                duration_seconds=0,
                iterations=1,
                harness_name="direct-session",
                harness_model="direct-session",
                files_changed=files or [],
                commits=[],
                approach=reason or "",
                decisions=[],
                lessons_learned=[],
            )

            writer.create_entry(entry)

        console.print(f"[green]✓[/green] Task {task_id} marked as complete")
        if reason:
            console.print(f"[dim]  Reason: {reason}[/dim]")
        ledger_path = ledger_dir / "by-task" / f"{task_id}.json"
        console.print(f"[dim]  → Ledger entry created at {ledger_path}[/dim]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to complete task: {e}")
        raise typer.Exit(1)


@app.command()
def wip(
    task_id: str = typer.Argument(..., help="Task ID to mark as in-progress"),
) -> None:
    """
    Mark a task as in-progress.

    This updates the task status in the backend to indicate active work.
    Use this when starting work on a task in a direct harness session.

    Examples:
        cub wip cub-123
    """
    backend = get_backend()

    # Get task to verify it exists
    task = backend.get_task(task_id)
    if task is None:
        console.print(f"[red]Error:[/red] Task not found: {task_id}")
        raise typer.Exit(1)

    # Check if already in progress
    if task.status == TaskStatus.IN_PROGRESS:
        console.print(f"[yellow]Note:[/yellow] Task {task_id} is already in progress")
        return

    try:
        # Update task status
        backend.update_task(task_id, status=TaskStatus.IN_PROGRESS)
        console.print(f"[green]✓[/green] Task {task_id} marked as in-progress")

        # Log to session log
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        log_path = _get_session_log_path()
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] Started work on {task_id}: {task.title}\n")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to update task: {e}")
        raise typer.Exit(1)
