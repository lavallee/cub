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

import json
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from cub.core.config.loader import load_config
from cub.core.ledger.session_integration import SessionLedgerIntegration
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

        # Create synthetic session using SessionLedgerIntegration
        ledger_dir = _get_ledger_dir()
        writer = LedgerWriter(ledger_dir)
        integration = SessionLedgerIntegration(writer)

        now = datetime.now(timezone.utc)
        session_id = f"cub-done-{task_id}-{int(now.timestamp())}"

        # Create temporary forensics file with synthetic events
        forensics_dir = ledger_dir / "forensics"
        forensics_dir.mkdir(parents=True, exist_ok=True)
        forensics_path = forensics_dir / f"{session_id}.jsonl"

        # Write synthetic forensics events
        with forensics_path.open("w", encoding="utf-8") as f:
            # Session start event
            session_start = {
                "event_type": "session_start",
                "timestamp": now.isoformat(),
                "session_id": session_id,
                "cwd": str(Path.cwd()),
            }
            f.write(json.dumps(session_start) + "\n")

            # Task claim event
            task_claim = {
                "event_type": "task_claim",
                "timestamp": now.isoformat(),
                "session_id": session_id,
                "task_id": task_id,
                "command": f"cub done {task_id}",
            }
            f.write(json.dumps(task_claim) + "\n")

            # File write events for any specified files
            if files:
                for file_path in files:
                    file_write = {
                        "event_type": "file_write",
                        "timestamp": now.isoformat(),
                        "session_id": session_id,
                        "file_path": file_path,
                        "tool_name": "direct-session",
                        "file_category": "source",
                    }
                    f.write(json.dumps(file_write) + "\n")

            # Task close event
            task_close = {
                "event_type": "task_close",
                "timestamp": now.isoformat(),
                "session_id": session_id,
                "task_id": task_id,
                "command": f"cub done {task_id}",
                "reason": reason,
            }
            f.write(json.dumps(task_close) + "\n")

            # Session end event
            session_end = {
                "event_type": "session_end",
                "timestamp": now.isoformat(),
                "session_id": session_id,
            }
            f.write(json.dumps(session_end) + "\n")

        # Use SessionLedgerIntegration to create ledger entry
        entry = integration.on_session_end(
            session_id=session_id,
            forensics_path=forensics_path,
            task=task,
        )

        # Update outcome approach field if reason was provided
        if entry and reason and entry.outcome:
            entry.outcome.approach = reason
            writer.update_entry(entry)

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
