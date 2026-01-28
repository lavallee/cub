"""
Cub CLI - Reconcile command.

Processes forensics logs to reconstruct ledger entries for sessions where
hooks didn't fire or partially failed. Ensures ledger completeness by
replaying unprocessed session events.
"""

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from cub.cli.errors import ExitCode, print_error
from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.session_integration import SessionLedgerIntegration
from cub.core.ledger.writer import LedgerWriter
from cub.core.tasks.backend import get_backend
from cub.utils.project import get_project_root

app = typer.Typer(
    name="reconcile",
    help="Reconstruct ledger entries from forensics logs",
    no_args_is_help=False,
    invoke_without_command=True,
)

console = Console()


def _get_ledger_paths() -> tuple[Path, Path, Path]:
    """Get ledger directory paths.

    Returns:
        Tuple of (ledger_dir, forensics_dir, by_task_dir)
    """
    project_root = get_project_root()
    ledger_dir = project_root / ".cub" / "ledger"
    forensics_dir = ledger_dir / "forensics"
    by_task_dir = ledger_dir / "by-task"
    return ledger_dir, forensics_dir, by_task_dir


def _parse_forensics_for_metadata(forensics_path: Path) -> dict[str, Any]:
    """Parse forensics file to extract metadata.

    Args:
        forensics_path: Path to forensics JSONL file

    Returns:
        Dict with session_id, task_id (if any), has_task_claim, has_task_close
    """
    metadata: dict[str, Any] = {
        "session_id": None,
        "task_id": None,
        "has_task_claim": False,
        "has_task_close": False,
        "event_count": 0,
    }

    if not forensics_path.exists():
        return metadata

    with forensics_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                metadata["event_count"] += 1

                # Extract session_id
                if metadata["session_id"] is None and "session_id" in event:
                    metadata["session_id"] = event["session_id"]

                # Track task claim
                if event.get("event_type") == "task_claim":
                    metadata["has_task_claim"] = True
                    metadata["task_id"] = event.get("task_id")

                # Track task close
                if event.get("event_type") == "task_close":
                    metadata["has_task_close"] = True
                    if metadata["task_id"] is None:
                        metadata["task_id"] = event.get("task_id")

            except json.JSONDecodeError:
                continue

    return metadata


@app.callback(invoke_without_command=True)
def reconcile(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be reconciled without making changes",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force reconciliation even if ledger entry exists",
    ),
    session_id: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Reconcile specific session ID only",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    Reconstruct ledger entries from forensics logs.

    Scans .cub/ledger/forensics/ for session logs and creates ledger entries
    for sessions that have task associations but no corresponding ledger entry.
    This handles cases where hooks didn't fire or partially failed.

    The command is idempotent - running it multiple times will not create
    duplicate entries.

    Examples:
        cub reconcile                  # Reconcile all unprocessed sessions
        cub reconcile --dry-run        # Show what would be reconciled
        cub reconcile --session abc123 # Reconcile specific session
        cub reconcile --force          # Re-process all sessions
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    try:
        # Get ledger paths
        ledger_dir, forensics_dir, by_task_dir = _get_ledger_paths()

        if not forensics_dir.exists():
            console.print(
                "[yellow]No forensics directory found. Nothing to reconcile.[/yellow]"
            )
            raise typer.Exit(0)

        # Set up ledger infrastructure
        writer = LedgerWriter(ledger_dir)
        reader = LedgerReader(ledger_dir)
        integration = SessionLedgerIntegration(writer)

        # Get all forensics files
        forensics_files = list(forensics_dir.glob("*.jsonl"))
        if not forensics_files:
            console.print(
                "[yellow]No forensics files found. Nothing to reconcile.[/yellow]"
            )
            raise typer.Exit(0)

        # Filter by session_id if specified
        if session_id:
            forensics_files = [
                f for f in forensics_files if f.stem == session_id
            ]
            if not forensics_files:
                console.print(
                    f"[red]Session not found:[/red] {session_id}"
                )
                raise typer.Exit(ExitCode.USER_ERROR)

        # Process each forensics file
        results: dict[str, Any] = {
            "processed": 0,
            "skipped": 0,
            "created": 0,
            "errors": 0,
            "sessions": [],
        }

        for forensics_path in forensics_files:
            session_id_from_file = forensics_path.stem

            if debug:
                console.print(f"[dim]Processing: {forensics_path.name}[/dim]")

            # Parse forensics to check if it has a task
            metadata = _parse_forensics_for_metadata(forensics_path)

            # Skip if no task association
            if not metadata["has_task_claim"]:
                results["skipped"] += 1
                results["sessions"].append({
                    "session_id": session_id_from_file,
                    "status": "skipped",
                    "reason": "no_task_association",
                })
                if debug:
                    console.print(
                        "  [dim]Skipped: No task claimed[/dim]"
                    )
                continue

            task_id = metadata["task_id"]
            if not task_id:
                results["skipped"] += 1
                results["sessions"].append({
                    "session_id": session_id_from_file,
                    "status": "skipped",
                    "reason": "no_task_id",
                })
                if debug:
                    console.print(
                        "  [dim]Skipped: No task ID found[/dim]"
                    )
                continue

            # Check if ledger entry already exists
            existing_entry = reader.get_task(task_id)
            if existing_entry and not force:
                results["skipped"] += 1
                results["sessions"].append({
                    "session_id": session_id_from_file,
                    "task_id": task_id,
                    "status": "skipped",
                    "reason": "entry_exists",
                })
                if debug:
                    console.print(
                        f"  [dim]Skipped: Entry already exists for {task_id}[/dim]"
                    )
                continue

            # Get task from backend for additional context
            try:
                backend = get_backend()
                task = backend.get_task(task_id)
            except Exception as e:
                if debug:
                    console.print(f"  [yellow]Warning: Could not load task {task_id}: {e}[/yellow]")
                task = None

            # Process session (dry-run or actual)
            if dry_run:
                results["processed"] += 1
                results["sessions"].append({
                    "session_id": session_id_from_file,
                    "task_id": task_id,
                    "status": "would_create",
                    "reason": "dry_run",
                })
                if debug:
                    console.print(
                        f"  [blue]Would create entry for {task_id}[/blue]"
                    )
            else:
                try:
                    entry = integration.on_session_end(
                        session_id=session_id_from_file,
                        forensics_path=forensics_path,
                        task=task,
                    )

                    if entry:
                        results["created"] += 1
                        results["sessions"].append({
                            "session_id": session_id_from_file,
                            "task_id": task_id,
                            "status": "created",
                            "entry_id": entry.id,
                        })
                        if debug:
                            console.print(
                                f"  [green]Created entry for {task_id}[/green]"
                            )
                    else:
                        results["skipped"] += 1
                        results["sessions"].append({
                            "session_id": session_id_from_file,
                            "task_id": task_id,
                            "status": "skipped",
                            "reason": "no_entry_created",
                        })
                        if debug:
                            console.print(
                                f"  [yellow]No entry created for {task_id}[/yellow]"
                            )

                    results["processed"] += 1

                except Exception as e:
                    results["errors"] += 1
                    results["sessions"].append({
                        "session_id": session_id_from_file,
                        "task_id": task_id,
                        "status": "error",
                        "error": str(e),
                    })
                    console.print(
                        f"  [red]Error processing {session_id_from_file}: {e}[/red]"
                    )

        # Output results
        if json_output:
            console.print(json.dumps(results, indent=2))
        else:
            # Create summary table
            table = Table(title="Reconciliation Summary", show_header=False)
            table.add_column("Metric", style="cyan")
            table.add_column("Count", style="green", justify="right")

            table.add_row("Total Sessions", str(len(forensics_files)))
            table.add_row("Processed", str(results["processed"]))
            table.add_row("Skipped", str(results["skipped"]))

            if dry_run:
                table.add_row("Would Create", f"[blue]{results['processed']}[/blue]")
            else:
                table.add_row("Created", f"[green]{results['created']}[/green]")

            if results["errors"] > 0:
                table.add_row("Errors", f"[red]{results['errors']}[/red]")

            console.print()
            console.print(table)

            # Show individual session results if requested
            if debug and results["sessions"]:
                console.print("\n[bold]Session Details:[/bold]")
                detail_table = Table()
                detail_table.add_column("Session ID", style="cyan")
                detail_table.add_column("Task ID", style="yellow")
                detail_table.add_column("Status", style="green")
                detail_table.add_column("Notes", style="dim")

                for session in results["sessions"]:
                    status_color = {
                        "created": "[green]created[/green]",
                        "would_create": "[blue]would_create[/blue]",
                        "skipped": "[dim]skipped[/dim]",
                        "error": "[red]error[/red]",
                    }.get(session["status"], session["status"])

                    detail_table.add_row(
                        session.get("session_id", "N/A"),
                        session.get("task_id", "N/A"),
                        status_color,
                        session.get("reason", session.get("error", "")),
                    )

                console.print(detail_table)

            # Success message
            if dry_run:
                console.print(
                    f"\n[blue]Dry run complete. "
                    f"{results['processed']} entries would be created.[/blue]"
                )
            elif results["created"] > 0:
                console.print(
                    f"\n[green]✓[/green] Reconciliation complete. "
                    f"Created {results['created']} ledger entries."
                )
            else:
                console.print(
                    "\n[yellow]No new entries created. All sessions already processed.[/yellow]"
                )

        raise typer.Exit(0)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(
            "Reconciliation failed",
            reason=str(e),
            solution="Check forensics logs and ledger directory permissions",
        )
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(ExitCode.GENERAL_ERROR)
