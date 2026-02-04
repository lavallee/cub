"""
Hook management commands for Claude Code integration.

Provides commands to install, uninstall, and validate Claude Code hooks
that enable the symbiotic workflow (artifact tracking in direct sessions).

Also provides commands to view hook forensics logs, which are auto-generated
event streams capturing session activity (file writes, task claims, commits, etc.).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from cub.core.hooks.installer import install_hooks, uninstall_hooks, validate_hooks
from cub.utils.project import get_project_root

app = typer.Typer(
    name="hooks",
    help="Manage Claude Code hooks for symbiotic workflow",
    no_args_is_help=True,
)

console = Console()


@app.command(name="install")
def install(
    project_dir: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project directory (default: current directory)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing hook configuration",
    ),
) -> None:
    """
    Install Claude Code hooks for symbiotic workflow.

    This command installs hooks in .claude/settings.json that enable
    cub to track file writes, task claims, and git commits when you
    work directly in Claude Code (outside of 'cub run').

    The hooks capture session events and write them to forensics logs
    in .cub/ledger/forensics/, enabling full context recovery across
    sessions.

    Examples:
        cub hooks install              # Install in current project
        cub hooks install --force      # Reinstall/overwrite existing
        cub hooks install -p ../other  # Install in different project
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    if not project_path.is_dir():
        console.print(f"[red]Error: Not a directory: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Installing hooks in:[/blue] {project_path}")

    result = install_hooks(project_path, force=force)

    if result.success:
        console.print(f"[green]✓[/green] {result.message}")
        if result.hooks_installed:
            console.print(f"  Installed hooks: {', '.join(result.hooks_installed)}")
        if result.settings_file:
            console.print(f"  Settings file: {result.settings_file}")

        # Show warnings if any
        for issue in result.issues:
            if issue.severity == "warning":
                console.print(f"[yellow]⚠[/yellow] {issue.message}")
            elif issue.severity == "info":
                console.print(f"[blue]ℹ[/blue] {issue.message}")

        raise typer.Exit(0)
    else:
        console.print(f"[red]✗[/red] {result.message}")

        # Show all issues
        for issue in result.issues:
            if issue.severity == "error":
                console.print(f"[red]Error:[/red] {issue.message}")
            elif issue.severity == "warning":
                console.print(f"[yellow]Warning:[/yellow] {issue.message}")
            else:
                console.print(f"[blue]Info:[/blue] {issue.message}")

        raise typer.Exit(1)


@app.command(name="uninstall")
def uninstall(
    project_dir: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project directory (default: current directory)",
    ),
) -> None:
    """
    Remove Claude Code hooks configuration.

    This command removes cub hooks from .claude/settings.json while
    preserving other settings and non-cub hooks.

    Note: This does not delete the hook script from .cub/scripts/hooks/,
    only removes the configuration from settings.json.

    Examples:
        cub hooks uninstall         # Remove hooks from current project
        cub hooks uninstall -p ..   # Remove from parent directory
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Removing hooks from:[/blue] {project_path}")

    uninstall_hooks(project_path)

    console.print("[green]✓[/green] Hooks removed from .claude/settings.json")


@app.command(name="check")
def check(
    project_dir: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project directory (default: current directory)",
    ),
) -> None:
    """
    Validate hook installation.

    Checks that:
    - .claude/settings.json exists and is valid JSON
    - Hook script exists and is executable
    - All expected hooks are configured
    - Python handler module is importable

    This is a subset of 'cub doctor' focused on hooks only.

    Examples:
        cub hooks check           # Check current project
        cub hooks check -p ..     # Check parent directory
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Checking hooks in:[/blue] {project_path}\n")

    issues = validate_hooks(project_path)

    if not issues:
        console.print("[green]✓[/green] All hooks validated successfully")
        raise typer.Exit(0)

    # Group issues by severity
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    # Display issues in a table
    table = Table(title="Hook Validation Issues", show_header=True, header_style="bold")
    table.add_column("Severity", style="white", width=10)
    table.add_column("Issue", style="white")
    table.add_column("Hook/File", style="dim")

    for issue in errors:
        table.add_row(
            "[red]ERROR[/red]",
            issue.message,
            issue.hook_name or issue.file_path or "",
        )

    for issue in warnings:
        table.add_row(
            "[yellow]WARNING[/yellow]",
            issue.message,
            issue.hook_name or issue.file_path or "",
        )

    for issue in infos:
        table.add_row(
            "[blue]INFO[/blue]",
            issue.message,
            issue.hook_name or issue.file_path or "",
        )

    console.print(table)
    console.print()

    # Summary
    if errors:
        console.print(f"[red]✗[/red] Found {len(errors)} error(s)")
        console.print("  Run 'cub hooks install --force' to fix")
        raise typer.Exit(1)
    elif warnings:
        console.print(f"[yellow]⚠[/yellow] Found {len(warnings)} warning(s)")
        raise typer.Exit(0)
    else:
        console.print(f"[blue]ℹ[/blue] Found {len(infos)} info message(s)")
        raise typer.Exit(0)


def _format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return timestamp_str


def _format_event_type(event_type: str) -> str:
    """Format event type with color."""
    type_colors = {
        "session_start": "[green]session_start[/green]",
        "session_end": "[green]session_end[/green]",
        "session_checkpoint": "[yellow]session_checkpoint[/yellow]",
        "file_write": "[blue]file_write[/blue]",
        "task_claim": "[cyan]task_claim[/cyan]",
        "task_close": "[cyan]task_close[/cyan]",
        "task_mention": "[dim]task_mention[/dim]",
        "git_commit": "[magenta]git_commit[/magenta]",
    }
    return type_colors.get(event_type, event_type)


def _get_event_details(event: dict[str, Any]) -> str:
    """Extract relevant details from an event for display."""
    event_type = event.get("event_type", "")

    if event_type == "session_start":
        cwd = event.get("cwd", "")
        return f"cwd: {cwd}" if cwd else ""
    elif event_type == "file_write":
        file_path = event.get("file_path", "")
        tool = event.get("tool_name", "")
        category = event.get("file_category", "")
        parts = []
        if file_path:
            # Show just filename for brevity
            parts.append(Path(file_path).name)
        if tool:
            parts.append(f"({tool})")
        if category:
            parts.append(f"[{category}]")
        return " ".join(parts)
    elif event_type == "task_claim":
        task_id = event.get("task_id", "")
        return f"task: {task_id}" if task_id else ""
    elif event_type == "task_close":
        task_id = event.get("task_id", "")
        reason = event.get("reason", "")
        if reason:
            return f"task: {task_id} - {reason[:30]}"
        return f"task: {task_id}" if task_id else ""
    elif event_type == "git_commit":
        message = event.get("message_preview", "")
        return message[:50] if message else ""
    elif event_type == "session_end":
        return ""
    elif event_type == "session_checkpoint":
        reason = event.get("reason", "")
        return reason if reason else ""
    elif event_type == "task_mention":
        task_id = event.get("task_id", "")
        return f"task: {task_id}" if task_id else ""
    else:
        return ""


@app.command(name="log")
def log_cmd(
    session: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Filter by specific session ID",
    ),
    event_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by event type (session_start, file_write, task_claim, git_commit, etc.)",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Number of events to show (default: 20)",
    ),
    project_dir: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project directory (default: current directory)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    View recent hook forensics events.

    Hook forensics are auto-generated event streams that capture session
    activity when using Claude Code with cub hooks installed. Events include
    file writes, task claims/closes, git commits, and session lifecycle.

    These logs are useful for troubleshooting session issues, understanding
    what happened during a session, and debugging hook behavior.

    Note: Forensics files are auto-generated by hooks and should not be
    manually edited.

    Examples:
        cub hooks log                      # Show last 20 events
        cub hooks log --limit 50           # Show last 50 events
        cub hooks log --session abc123     # Filter by session ID
        cub hooks log --type file_write    # Filter by event type
        cub hooks log --json               # Output as JSON
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    # Use get_project_root if in current directory, otherwise use provided path
    if project_dir == ".":
        try:
            project_path = get_project_root()
        except Exception:
            pass  # Use current directory if project root not found

    forensics_dir = project_path / ".cub" / "ledger" / "forensics"

    if not forensics_dir.exists():
        console.print(
            "[yellow]No forensics found.[/yellow] "
            "Hook forensics are created when you use Claude Code with cub hooks installed."
        )
        console.print()
        console.print("To install hooks: [cyan]cub hooks install[/cyan]")
        raise typer.Exit(0)

    # Collect all events from forensics files
    all_events: list[dict[str, Any]] = []

    # Get all forensics files
    forensics_files = sorted(
        forensics_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True
    )

    if not forensics_files:
        console.print("[yellow]No forensics files found.[/yellow]")
        raise typer.Exit(0)

    # If filtering by session, only read that specific file
    if session:
        target_file = forensics_dir / f"{session}.jsonl"
        if target_file.exists():
            forensics_files = [target_file]
        else:
            # Try partial match
            matching_files = [f for f in forensics_files if session in f.stem]
            if matching_files:
                forensics_files = matching_files
            else:
                console.print(f"[yellow]No forensics found for session: {session}[/yellow]")
                raise typer.Exit(0)

    # Read events from files
    for forensics_file in forensics_files:
        try:
            with forensics_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        # Add source file info for context
                        event["_source_file"] = forensics_file.stem

                        # Apply event type filter if specified
                        if event_type and event.get("event_type") != event_type:
                            continue

                        all_events.append(event)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue

    if not all_events:
        if event_type:
            console.print(f"[yellow]No events of type '{event_type}' found.[/yellow]")
        else:
            console.print("[yellow]No events found in forensics files.[/yellow]")
        raise typer.Exit(0)

    # Sort events by timestamp (most recent first)
    all_events.sort(
        key=lambda e: e.get("timestamp", ""),
        reverse=True
    )

    # Apply limit
    events_to_show = all_events[:limit]

    # JSON output
    if json_output:
        # Remove internal fields
        clean_events = []
        for event in events_to_show:
            clean = {k: v for k, v in event.items() if not k.startswith("_")}
            clean_events.append(clean)
        console.print(json.dumps(clean_events, indent=2))
        return

    # Rich table output
    console.print()
    num_showing = len(events_to_show)
    num_total = len(all_events)
    console.print(f"[bold]Hook Forensics[/bold] (showing {num_showing} of {num_total} events)")
    console.print()

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Time", style="dim", width=19)
    table.add_column("Type", width=18)
    table.add_column("Session", style="dim", width=20)
    table.add_column("Details")

    for event in events_to_show:
        timestamp = _format_timestamp(event.get("timestamp", ""))
        ev_type = _format_event_type(event.get("event_type", "unknown"))
        session_id = event.get("session_id", "")
        # Truncate session ID for display
        if session_id and len(session_id) > 18:
            session_id = session_id[:15] + "..."
        details = _get_event_details(event)

        table.add_row(timestamp, ev_type, session_id, details)

    console.print(table)

    # Show session count
    unique_sessions = {e.get("session_id") for e in all_events if e.get("session_id")}
    console.print()
    console.print(f"[dim]Events from {len(unique_sessions)} session(s)[/dim]")
    console.print(f"[dim]Forensics location: {forensics_dir}[/dim]")
