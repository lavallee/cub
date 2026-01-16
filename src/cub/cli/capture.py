"""
Cub CLI - Capture command.

Quick text capture for ideas, notes, and observations.
"""

import sys
from datetime import datetime, timezone

import typer
from rich.console import Console

from cub.core.captures.models import Capture, CaptureSource
from cub.core.captures.store import CaptureStore

console = Console()


def generate_slug(text: str, max_length: int = 50) -> str:
    """
    Generate a slug from text for use in filenames.

    Args:
        text: Input text to slugify
        max_length: Maximum slug length

    Returns:
        Slugified text suitable for filenames
    """
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = text.lower()
    slug = "".join(c if c.isalnum() or c in " -_" else "-" for c in slug)
    slug = "-".join(slug.split())  # Collapse whitespace to single hyphens
    slug = slug.strip("-")  # Remove leading/trailing hyphens

    # Truncate to max length
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]  # Cut at word boundary

    return slug or "capture"


def capture(
    ctx: typer.Context,
    content: str | None = typer.Argument(
        None,
        help="Text to capture (or read from stdin if not provided)",
    ),
    tag: list[str] = typer.Option(
        [],
        "--tag",
        "-t",
        help="Add tag to capture (repeatable)",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Explicit filename (without .md extension)",
    ),
    priority: int | None = typer.Option(
        None,
        "--priority",
        "-p",
        help="Priority level (1-5, lower is higher priority)",
        min=1,
        max=5,
    ),
    global_store: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Save to global captures directory (~/.local/share/cub/captures/)",
    ),
) -> None:
    """
    Capture quick ideas, notes, and observations.

    Captures are stored as Markdown files with YAML frontmatter in the
    captures/ directory (or globally with --global).

    Examples:
        cub capture "Add dark mode to UI"
        cub capture "Refactor auth flow" --tag feature --tag auth
        echo "Meeting notes..." | cub capture
        cub capture --name "sprint-planning" "Q1 2026 sprint goals"
    """
    debug = ctx.obj.get("debug", False)

    # Read content from stdin if not provided as argument
    if content is None:
        if sys.stdin.isatty():
            console.print(
                "[red]Error:[/red] No content provided. "
                "Provide text as argument or via stdin."
            )
            console.print("\nExamples:")
            console.print('  cub capture "Your idea here"')
            console.print('  echo "Your idea" | cub capture')
            raise typer.Exit(1)

        # Read from stdin
        content = sys.stdin.read().strip()
        source = CaptureSource.PIPE
    else:
        source = CaptureSource.CLI

    if not content:
        console.print("[red]Error:[/red] Content cannot be empty.")
        raise typer.Exit(1)

    # Initialize the appropriate store
    if global_store:
        store = CaptureStore.global_store()
        location = "global"
    else:
        store = CaptureStore.project()
        location = "project"

    # Generate next ID
    capture_id = store.next_id()

    # Generate title (first line or truncated content)
    title_lines = content.split("\n", 1)
    title = title_lines[0].strip()
    if len(title) > 80:
        title = title[:77] + "..."

    # Create capture object
    capture_obj = Capture(
        id=capture_id,
        created=datetime.now(timezone.utc),
        title=title,
        tags=list(tag),  # Convert from tuple to list
        source=source,
        priority=priority,
    )

    # Save to disk
    try:
        store.save_capture(capture_obj, content)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to save capture: {e}")
        raise typer.Exit(1)

    # Get the actual file path for display
    captures_dir = store.get_captures_dir()
    file_path = captures_dir / f"{capture_id}.md"

    # Success output
    console.print(f"[green]✓[/green] Captured as [bold]{capture_id}[/bold] ({location})")
    console.print(f"  [dim]{file_path}[/dim]")

    if debug:
        console.print("\n[dim]Debug info:[/dim]")
        console.print(f"  Title: {title}")
        console.print(f"  Tags: {tag}")
        console.print(f"  Source: {source.value}")
        console.print(f"  Priority: {priority}")
