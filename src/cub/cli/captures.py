"""
Cub CLI - Captures list and management commands.

List and manage captured ideas, notes, and observations.

Two-tier storage model:
- Global captures: ~/.local/share/cub/captures/{project}/ (default for new captures)
- Project captures: ./captures/ (version-controlled, imported from global)
"""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import frontmatter  # type: ignore[import-untyped]
import typer
from rich.console import Console
from rich.table import Table

from cub.core.captures.models import Capture, CaptureStatus
from cub.core.captures.project_id import get_project_id
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
    global_only: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Show only global captures",
    ),
    project_only: bool = typer.Option(
        False,
        "--project",
        "-P",
        help="Show only project captures",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    List captures from both global and project stores.

    By default, shows captures from both locations:
    - Global: ~/.local/share/cub/captures/{project}/ (default for new captures)
    - Project: ./captures/ (version-controlled)

    Use --global or --project to show only one location.

    Examples:
        cub captures                  # Show both global and project
        cub captures --global         # Global only
        cub captures --project        # Project only
        cub captures --tag feature    # Filter by tag
        cub captures --since 7d       # Last 7 days
        cub captures --search "auth"  # Search for "auth"
    """
    # If a subcommand was invoked, don't run the default callback
    if ctx.invoked_subcommand is not None:
        return

    debug = ctx.obj.get("debug", False)

    # Collect captures from both stores
    global_captures: list[tuple[Capture, CaptureStore]] = []
    project_captures: list[tuple[Capture, CaptureStore]] = []

    # Get global captures (unless --project specified)
    if not project_only:
        try:
            global_store = CaptureStore.global_store()
            for c in global_store.list_captures():
                global_captures.append((c, global_store))
        except FileNotFoundError:
            pass  # No global captures yet

    # Get project captures (unless --global specified)
    if not global_only:
        try:
            project_store = CaptureStore.project()
            for c in project_store.list_captures():
                project_captures.append((c, project_store))
        except FileNotFoundError:
            pass  # No project captures yet

    # Parse --since option
    since_date: datetime | None = None
    if since:
        since_date = _parse_since(since)

    def filter_captures(
        captures: list[tuple[Capture, CaptureStore]],
    ) -> list[tuple[Capture, CaptureStore]]:
        """Apply filters to a list of captures."""
        result = captures

        # Filter by date
        if since_date:
            result = [(c, s) for c, s in result if c.created >= since_date]

        # Filter by tag
        if tag:
            result = [(c, s) for c, s in result if tag in c.tags]

        # Filter by search term
        if search:
            search_lower = search.lower()
            filtered = []
            for capture, store in result:
                # Search in title
                if search_lower in capture.title.lower():
                    filtered.append((capture, store))
                    continue

                # Search in content (read file)
                try:
                    capture_file = store.get_captures_dir() / f"{capture.id}.md"
                    content = capture_file.read_text(encoding="utf-8")
                    if search_lower in content.lower():
                        filtered.append((capture, store))
                except Exception as e:
                    if debug:
                        console.print(f"[dim]Warning: Failed to read {capture.id}: {e}[/dim]")
                    continue
            result = filtered

        # Filter out archived
        result = [(c, s) for c, s in result if c.status == CaptureStatus.ACTIVE]

        return result

    # Apply filters
    global_captures = filter_captures(global_captures)
    project_captures = filter_captures(project_captures)

    # Check if we have any captures
    total_count = len(global_captures) + len(project_captures)
    if total_count == 0:
        if global_only:
            console.print("[yellow]No global captures found matching criteria.[/yellow]")
        elif project_only:
            console.print("[yellow]No project captures found matching criteria.[/yellow]")
        else:
            console.print("[yellow]No captures found matching criteria.[/yellow]")
            console.print(
                '\nCreate your first capture with: [bold]cub capture "Your idea here"[/bold]'
            )
        raise typer.Exit(0)

    # Output as JSON if requested
    if json_output:
        output = {
            "global": [
                {
                    "id": c.id,
                    "created": c.created.isoformat(),
                    "title": c.title,
                    "tags": c.tags,
                    "source": c.source.value,
                    "status": c.status.value,
                    "priority": c.priority,
                }
                for c, _ in global_captures
            ],
            "project": [
                {
                    "id": c.id,
                    "created": c.created.isoformat(),
                    "title": c.title,
                    "tags": c.tags,
                    "source": c.source.value,
                    "status": c.status.value,
                    "priority": c.priority,
                }
                for c, _ in project_captures
            ],
        }
        console.print(json.dumps(output, indent=2))
        return

    # Display captures in two sections
    project_id = get_project_id()

    # Display global captures
    if global_captures and not project_only:
        global_store = CaptureStore.global_store()
        _display_capture_table(
            f"Global ({project_id})",
            global_captures,
            all_captures,
            global_store.get_captures_dir(),
        )

    # Display project captures
    if project_captures and not global_only:
        project_store = CaptureStore.project()
        if global_captures and not project_only:
            console.print()  # Add spacing between tables
        _display_capture_table(
            "Project (./captures/)",
            project_captures,
            all_captures,
            project_store.get_captures_dir(),
        )

    # Show hint if no captures in one section
    if not project_only and not global_only:
        if not global_captures and project_captures:
            console.print(
                "\n[dim]No global captures. New captures go to global by default.[/dim]"
            )
        if not project_captures and global_captures:
            console.print(
                "\n[dim]No project captures. Use [bold]cub captures import[/bold] "
                "to import from global.[/dim]"
            )


def _display_capture_table(
    title: str,
    captures: list[tuple[Capture, CaptureStore]],
    show_all: bool,
    captures_dir: object,
) -> None:
    """Display captures in a Rich table."""
    total_count = len(captures)

    # Limit to last 20 unless --all specified
    display_captures = captures if show_all else captures[:20]

    table = Table(
        title=f"{title} - {captures_dir}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim", width=10)
    table.add_column("Date", width=12)
    table.add_column("Title", overflow="fold")
    table.add_column("Tags", width=20)
    table.add_column("Pri", width=3, justify="center")

    for capture, _ in display_captures:
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

    # Show count summary
    if not show_all and total_count > 20:
        console.print(f"[dim]Showing 20 of {total_count}. Use --all to see all.[/dim]")


def _find_capture(capture_id: str) -> tuple[Capture, CaptureStore, str]:
    """
    Find a capture by ID, searching both global and project stores.

    Returns:
        Tuple of (Capture, CaptureStore, location_name)

    Raises:
        typer.Exit: If capture not found
    """
    # Try global store first (more common)
    try:
        store = CaptureStore.global_store()
        capture = store.get_capture(capture_id)
        return capture, store, "global"
    except FileNotFoundError:
        pass

    # Try project store
    try:
        store = CaptureStore.project()
        capture = store.get_capture(capture_id)
        return capture, store, "project"
    except FileNotFoundError:
        pass

    console.print(f"[red]Error:[/red] Capture not found: {capture_id}")
    console.print("[dim]Searched in both global and project stores.[/dim]")
    raise typer.Exit(1)


@app.command()
def show(
    ctx: typer.Context,
    capture_id: str = typer.Argument(..., help="Capture ID to display (e.g., cap-001)"),
) -> None:
    """
    Display a capture in full.

    Shows the complete capture including all metadata and content.
    Searches both global and project stores automatically.

    Examples:
        cub captures show cap-001
        cub captures show cap-042
    """
    # Find capture in either store
    capture, store, location = _find_capture(capture_id)

    # Read full content
    capture_file = store.get_capture_file_path(capture_id)
    try:
        post = frontmatter.load(capture_file)
        content = post.content
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read capture: {e}")
        raise typer.Exit(1)

    # Display metadata
    console.print(f"[bold cyan]Capture {capture.id}[/bold cyan] ({location})")
    console.print(f"[dim]Location:[/dim] {capture_file}")
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
) -> None:
    """
    Edit a capture in your $EDITOR.

    Opens the capture file in your default text editor.
    Searches both global and project stores automatically.

    Examples:
        cub captures edit cap-001
        cub captures edit cap-042
    """
    # Find capture in either store
    _, store, location = _find_capture(capture_id)

    # Get editor
    editor = os.environ.get("EDITOR", "vim")

    # Get file path
    capture_file = store.get_capture_file_path(capture_id)

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

    console.print(f"[green]✓[/green] Edited {capture_id} ({location})")


@app.command("import")
def import_capture(
    ctx: typer.Context,
    capture_id: str = typer.Argument(
        ..., help="Capture ID to import from global store (e.g., cap-001)"
    ),
    keep: bool = typer.Option(
        False,
        "--keep",
        "-k",
        help="Keep the original global capture after import",
    ),
) -> None:
    """
    Import a global capture into the project.

    Moves a capture from global storage (~/.local/share/cub/captures/{project}/)
    into the project's ./captures/ directory for version control.

    By default, removes the global copy after import. Use --keep to preserve both.

    Examples:
        cub captures import cap-042
        cub captures import cap-042 --keep
    """
    # Load from global store
    global_store = CaptureStore.global_store()
    try:
        capture = global_store.get_capture(capture_id)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Capture not found in global store: {capture_id}")
        console.print(
            f"[dim]Global store: {global_store.get_captures_dir()}[/dim]"
        )
        raise typer.Exit(1)

    # Read full content
    global_capture_file = global_store.get_capture_file_path(capture_id)
    try:
        post = frontmatter.load(global_capture_file)
        content = post.content
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read capture: {e}")
        raise typer.Exit(1)

    # Save to project store (preserving filename from global store)
    project_store = CaptureStore.project()
    original_filename = global_capture_file.stem  # Preserve slug filename
    try:
        project_file = project_store.save_capture(capture, content, filename=original_filename)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to save capture: {e}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Imported {capture_id}")
    console.print(f"[dim]Project:[/dim] {project_file}")

    # Remove from global store unless --keep
    if not keep:
        try:
            global_capture_file.unlink()
            console.print("[dim]Removed from global store[/dim]")
        except OSError as e:
            console.print(f"[yellow]Warning:[/yellow] Could not remove global copy: {e}")


@app.command()
def archive(
    ctx: typer.Context,
    capture_id: str = typer.Argument(..., help="Capture ID to archive (e.g., cap-001)"),
) -> None:
    """
    Archive a capture.

    Marks the capture as archived, hiding it from default listings.
    Searches both global and project stores automatically.

    Examples:
        cub captures archive cap-001
        cub captures archive cap-042
    """
    # Find capture in either store
    capture, store, location = _find_capture(capture_id)

    # Check if already archived
    if capture.status == CaptureStatus.ARCHIVED:
        console.print(f"[yellow]Note:[/yellow] Capture {capture_id} is already archived.")
        raise typer.Exit(0)

    # Read full content
    capture_file = store.get_capture_file_path(capture_id)
    try:
        post = frontmatter.load(capture_file)
        content = post.content
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read capture: {e}")
        raise typer.Exit(1)

    # Update status
    capture.status = CaptureStatus.ARCHIVED

    # Save back (preserving original filename)
    original_filename = capture_file.stem
    try:
        store.save_capture(capture, content, filename=original_filename)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to save capture: {e}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Archived {capture_id} ({location})")


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
