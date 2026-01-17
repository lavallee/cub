"""
Cub CLI - Captures list and management commands.

List and manage captured ideas, notes, and observations.
"""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import frontmatter  # type: ignore[import-untyped]
import typer
from rich.console import Console
from rich.table import Table

from cub.core.captures.models import CaptureStatus
from cub.core.captures.store import CaptureStore

console = Console()
app = typer.Typer(help="List and manage captures")


@app.callback(invoke_without_command=True)
def list_captures(
    ctx: typer.Context,
    all_captures: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all captures (default: last 20)",
    ),
    tag: str | None = typer.Option(
        None,
        "--tag",
        "-t",
        help="Filter by tag",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Filter by date (e.g., '2026-01-01', '7d', '1w')",
    ),
    search: str | None = typer.Option(
        None,
        "--search",
        "-s",
        help="Full-text search in title and content",
    ),
    global_store: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="List global captures instead of project captures",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    List captures.

    By default, shows the last 20 captures in a table format.
    Use --all to show all captures, or combine with filters to narrow results.

    Examples:
        cub captures                  # Show last 20
        cub captures --all            # Show all
        cub captures --tag feature    # Filter by tag
        cub captures --since 7d       # Last 7 days
        cub captures --search "auth"  # Search for "auth"
    """
    # If a subcommand was invoked, don't run the default callback
    if ctx.invoked_subcommand is not None:
        return

    debug = ctx.obj.get("debug", False)

    # Initialize store
    try:
        if global_store:
            store = CaptureStore.global_store()
            location = "global"
        else:
            store = CaptureStore.project()
            location = "project"

        captures = store.list_captures()
    except FileNotFoundError as e:
        console.print(f"[yellow]Warning:[/yellow] {e}")
        console.print(f"\nNo captures found in {location} store.")
        console.print('Create your first capture with: [bold]cub capture "Your idea here"[/bold]')
        raise typer.Exit(0)

    # Parse --since option
    since_date: datetime | None = None
    if since:
        since_date = _parse_since(since)
        if since_date:
            captures = [c for c in captures if c.created >= since_date]

    # Filter by tag
    if tag:
        captures = [c for c in captures if tag in c.tags]

    # Filter by search term
    if search:
        search_lower = search.lower()
        filtered = []
        for capture in captures:
            # Search in title
            if search_lower in capture.title.lower():
                filtered.append(capture)
                continue

            # Search in content (read file)
            try:
                capture_file = store.get_captures_dir() / f"{capture.id}.md"
                content = capture_file.read_text(encoding="utf-8")
                if search_lower in content.lower():
                    filtered.append(capture)
            except Exception as e:
                if debug:
                    console.print(f"[dim]Warning: Failed to read {capture.id}: {e}[/dim]")
                continue

        captures = filtered

    # Filter out archived unless explicitly searching for them
    captures = [c for c in captures if c.status == CaptureStatus.ACTIVE]

    # Limit to last 20 unless --all specified
    if not all_captures and len(captures) > 20:
        captures = captures[:20]

    if not captures:
        console.print("[yellow]No captures found matching criteria.[/yellow]")
        raise typer.Exit(0)

    # Output as JSON if requested
    if json_output:
        output = [
            {
                "id": c.id,
                "created": c.created.isoformat(),
                "title": c.title,
                "tags": c.tags,
                "source": c.source.value,
                "status": c.status.value,
                "priority": c.priority,
            }
            for c in captures
        ]
        console.print(json.dumps(output, indent=2))
        return

    # Display as Rich table
    table = Table(title=f"Captures ({location})", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Date", width=12)
    table.add_column("Title", overflow="fold")
    table.add_column("Tags", width=20)
    table.add_column("Pri", width=3, justify="center")

    for capture in captures:
        # Format date
        date_str = _format_date(capture.created)

        # Truncate and format tags
        tags_str = ", ".join(capture.tags[:3])
        if len(capture.tags) > 3:
            tags_str += f" +{len(capture.tags) - 3}"
        if not tags_str:
            tags_str = "[dim]-[/dim]"

        # Format priority
        pri_str = str(capture.priority) if capture.priority else "[dim]-[/dim]"

        table.add_row(capture.id, date_str, capture.title, tags_str, pri_str)

    console.print(table)

    # Show summary
    if not all_captures and len(store.list_captures()) > 20:
        total = len(store.list_captures())
        console.print(f"\n[dim]Showing last 20 of {total} captures. Use --all to see all.[/dim]")


@app.command()
def show(
    ctx: typer.Context,
    capture_id: str = typer.Argument(..., help="Capture ID to display (e.g., cap-001)"),
    global_store: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Show global capture instead of project capture",
    ),
) -> None:
    """
    Display a capture in full.

    Shows the complete capture including all metadata and content.

    Examples:
        cub captures show cap-001
        cub captures show cap-042 --global
    """
    # Initialize store
    if global_store:
        store = CaptureStore.global_store()
    else:
        store = CaptureStore.project()

    # Read capture
    try:
        capture = store.get_capture(capture_id)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Capture not found: {capture_id}")
        raise typer.Exit(1)

    # Read full content
    capture_file = store.get_captures_dir() / f"{capture_id}.md"
    try:
        post = frontmatter.load(capture_file)
        content = post.content
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read capture: {e}")
        raise typer.Exit(1)

    # Display metadata
    console.print(f"[bold cyan]Capture {capture.id}[/bold cyan]")
    console.print(f"[dim]Created:[/dim] {capture.created.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"[dim]Title:[/dim] {capture.title}")

    if capture.tags:
        console.print(f"[dim]Tags:[/dim] {', '.join(capture.tags)}")

    if capture.priority:
        console.print(f"[dim]Priority:[/dim] {capture.priority}")

    console.print(f"[dim]Status:[/dim] {capture.status.value}")
    console.print(f"[dim]Source:[/dim] {capture.source.value}")

    # Display content
    console.print("\n[bold]Content:[/bold]")
    console.print(content)


@app.command()
def edit(
    ctx: typer.Context,
    capture_id: str = typer.Argument(..., help="Capture ID to edit (e.g., cap-001)"),
    global_store: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Edit global capture instead of project capture",
    ),
) -> None:
    """
    Edit a capture in your $EDITOR.

    Opens the capture file in your default text editor.

    Examples:
        cub captures edit cap-001
        cub captures edit cap-042 --global
    """
    # Initialize store
    if global_store:
        store = CaptureStore.global_store()
    else:
        store = CaptureStore.project()

    # Verify capture exists
    try:
        store.get_capture(capture_id)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Capture not found: {capture_id}")
        raise typer.Exit(1)

    # Get editor
    editor = os.environ.get("EDITOR", "vim")

    # Get file path
    capture_file = store.get_captures_dir() / f"{capture_id}.md"

    # Open in editor
    try:
        result = subprocess.run([editor, str(capture_file)], check=False)
        if result.returncode != 0:
            console.print(f"[yellow]Warning:[/yellow] Editor exited with code {result.returncode}")
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Editor not found: {editor}")
        console.print("Set your $EDITOR environment variable to your preferred editor.")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to open editor: {e}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Edited {capture_id}")


@app.command()
def import_capture(
    ctx: typer.Context,
    capture_id: str = typer.Argument(
        ..., help="Capture ID to import from global store (e.g., cap-001)"
    ),
    new_id: bool = typer.Option(
        False,
        "--reassign",
        "-r",
        help="Reassign to next project sequence ID",
    ),
) -> None:
    """
    Import a global capture into the project.

    Copies a capture from the global store (~/.local/share/cub/captures/)
    into the current project's captures/ directory.

    By default, preserves the original ID. Use --reassign to get a new
    project-level ID.

    Examples:
        cub captures import cap-042
        cub captures import cap-042 --reassign
    """
    # Load from global store
    global_store = CaptureStore.global_store()
    try:
        capture = global_store.get_capture(capture_id)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Capture not found in global store: {capture_id}")
        raise typer.Exit(1)

    # Read full content
    global_capture_file = global_store.get_captures_dir() / f"{capture_id}.md"
    try:
        post = frontmatter.load(global_capture_file)
        content = post.content
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read capture: {e}")
        raise typer.Exit(1)

    # Optionally reassign to project sequence
    if new_id:
        project_store = CaptureStore.project()
        new_capture_id = project_store.next_id()
        capture.id = new_capture_id
    else:
        new_capture_id = capture_id

    # Save to project store
    try:
        project_store = CaptureStore.project()
        project_store.save_capture(capture, content)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to save capture: {e}")
        raise typer.Exit(1)

    project_captures_dir = project_store.get_captures_dir()
    console.print(f"[green]✓[/green] Imported {capture_id} as {new_capture_id}")
    console.print(f"[dim]Location:[/dim] {project_captures_dir / f'{new_capture_id}.md'}")


@app.command()
def archive(
    ctx: typer.Context,
    capture_id: str = typer.Argument(..., help="Capture ID to archive (e.g., cap-001)"),
    global_store: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Archive global capture instead of project capture",
    ),
) -> None:
    """
    Archive a capture.

    Marks the capture as archived, hiding it from default listings.

    Examples:
        cub captures archive cap-001
        cub captures archive cap-042 --global
    """
    # Initialize store
    if global_store:
        store = CaptureStore.global_store()
    else:
        store = CaptureStore.project()

    # Read capture
    try:
        capture = store.get_capture(capture_id)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Capture not found: {capture_id}")
        raise typer.Exit(1)

    # Check if already archived
    if capture.status == CaptureStatus.ARCHIVED:
        console.print(f"[yellow]Note:[/yellow] Capture {capture_id} is already archived.")
        raise typer.Exit(0)

    # Read full content
    capture_file = store.get_captures_dir() / f"{capture_id}.md"
    try:
        post = frontmatter.load(capture_file)
        content = post.content
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read capture: {e}")
        raise typer.Exit(1)

    # Update status
    capture.status = CaptureStatus.ARCHIVED

    # Save back
    try:
        store.save_capture(capture, content)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to save capture: {e}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Archived {capture_id}")


def _parse_since(since: str) -> datetime | None:
    """
    Parse --since argument into a datetime.

    Supports formats:
    - ISO date: 2026-01-01
    - Relative: 7d, 1w, 2m (days, weeks, months)

    Returns:
        datetime object or None if parse fails
    """
    # Try ISO date format first
    try:
        return datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Try relative format (7d, 1w, 2m)
    if len(since) >= 2:
        unit = since[-1]
        try:
            amount = int(since[:-1])

            if unit == "d":
                return datetime.now(timezone.utc) - timedelta(days=amount)
            elif unit == "w":
                return datetime.now(timezone.utc) - timedelta(weeks=amount)
            elif unit == "m":
                return datetime.now(timezone.utc) - timedelta(days=amount * 30)
        except ValueError:
            pass

    console.print(f"[yellow]Warning:[/yellow] Invalid --since format: {since}")
    console.print("Supported formats: ISO date (2026-01-01) or relative (7d, 1w, 2m)")
    return None


def _format_date(dt: datetime) -> str:
    """
    Format a datetime for display in the table.

    Returns:
        Formatted date string (relative or absolute)
    """
    now = datetime.now(timezone.utc)
    delta = now - dt

    if delta.days == 0:
        return "Today"
    elif delta.days == 1:
        return "Yesterday"
    elif delta.days < 7:
        return f"{delta.days}d ago"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks}w ago"
    else:
        return dt.strftime("%Y-%m-%d")
