"""
Cub CLI - Capture command.

Quick text capture for ideas, notes, and observations.
"""

import subprocess
import sys
from datetime import datetime, timezone

import typer
from rich.console import Console

from cub.core.captures.models import Capture, CaptureSource
from cub.core.captures.slug import generate_slug
from cub.core.captures.store import CaptureStore
from cub.core.captures.tagging import suggest_tags

console = Console()


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
    project_store: bool = typer.Option(
        False,
        "--project",
        "-P",
        help="Save to project captures directory (./captures/) instead of global",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Launch interactive capture session with Claude",
    ),
    no_auto_tags: bool = typer.Option(
        False,
        "--no-auto-tags",
        help="Disable automatic tag suggestion based on content",
    ),
    no_slug: bool = typer.Option(
        False,
        "--no-slug",
        help="Skip AI-generated slug, use ID as filename",
    ),
) -> None:
    """
    Capture quick ideas, notes, and observations.

    By default, captures are stored globally at ~/.local/share/cub/captures/{project}/
    to survive branch deletion. Use --project to save directly to ./captures/.

    Tags can be provided explicitly with --tag, or automatically suggested
    based on content.

    Examples:
        cub capture "Add dark mode to UI"
        cub capture "Refactor auth flow" --tag feature --tag auth
        echo "Meeting notes..." | cub capture
        cub capture --name "sprint-planning" "Q1 2026 sprint goals"
        cub capture -i "New feature idea"
        cub capture "Fix git merge bug" --no-auto-tags
        cub capture --project "Ready for version control"
    """
    debug = ctx.obj.get("debug", False)

    # Handle interactive mode
    if interactive:
        # Build the skill invocation
        skill_prompt = "/cub:capture"
        if content:
            skill_prompt += f" {content}"

        # Launch Claude with the capture skill
        try:
            result = subprocess.run(
                ["claude", skill_prompt],
                check=False,  # Don't raise on non-zero exit
            )

            # Exit with the same code as Claude
            raise typer.Exit(result.returncode)
        except FileNotFoundError:
            console.print(
                "[red]Error:[/red] Claude CLI not found. "
                "Please install Claude Code from https://claude.ai/download"
            )
            raise typer.Exit(1)

    # Read content from stdin if not provided as argument
    if content is None:
        if sys.stdin.isatty():
            console.print(
                "[red]Error:[/red] No content provided. Provide text as argument or via stdin."
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
    # Default is global (organized by project), use --project for version-controlled
    if project_store:
        store = CaptureStore.project()
        location = "project"
    else:
        store = CaptureStore.global_store()
        location = "global"

    # Generate next ID
    capture_id = store.next_id()

    # Generate title (first line or truncated content)
    title_lines = content.split("\n", 1)
    title = title_lines[0].strip()
    if len(title) > 80:
        title = title[:77] + "..."

    # Merge auto-suggested tags with user-provided tags
    all_tags = list(tag)  # Convert from tuple to list
    if not no_auto_tags:
        auto_suggested = suggest_tags(content)
        # Add auto-suggested tags that aren't already present
        for suggested_tag in auto_suggested:
            if suggested_tag not in all_tags:
                all_tags.append(suggested_tag)

    # Create capture object
    capture_obj = Capture(
        id=capture_id,
        created=datetime.now(timezone.utc),
        title=title,
        tags=all_tags,
        source=source,
        priority=priority,
    )

    # Generate filename: use explicit name, AI slug, or fall back to ID
    filename: str | None = None
    slug_source = "id"

    if name:
        # Explicit name provided
        filename = name
        slug_source = "explicit"
    elif not no_slug:
        # Try AI-generated slug
        ai_slug = generate_slug(content)
        if ai_slug:
            filename = ai_slug
            slug_source = "ai"

    # Save to disk with optional custom filename
    try:
        file_path = store.save_capture(capture_obj, content, filename=filename)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to save capture: {e}")
        raise typer.Exit(1)

    # Success output
    console.print(f"[green]✓[/green] Captured as [bold]{capture_id}[/bold] ({location})")
    console.print(f"  [dim]{file_path}[/dim]")

    if debug:
        console.print("\n[dim]Debug info:[/dim]")
        console.print(f"  Title: {title}")
        console.print(f"  Filename: {file_path.stem} ({slug_source})")
        console.print(f"  User Tags: {list(tag)}")
        console.print(f"  Final Tags: {all_tags}")
        if not no_auto_tags:
            auto_suggested = suggest_tags(content)
            console.print(f"  Auto-Suggested: {auto_suggested}")
        console.print(f"  Source: {source.value}")
        console.print(f"  Priority: {priority}")
