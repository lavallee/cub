"""
Cub CLI - Organize Captures command.

Normalizes manually-added capture files by adding missing frontmatter,
fixing filenames, and ensuring consistency.
"""

from datetime import datetime, timezone
from pathlib import Path

import frontmatter  # type: ignore[import-untyped]
import typer
from rich.console import Console
from rich.table import Table

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


def organize_captures(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be changed without making changes",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
    global_store: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Organize global captures directory (~/.local/share/cub/captures/)",
    ),
) -> None:
    """
    Organize and normalize capture files.

    Scans the captures directory for files needing normalization:
    - Adds missing frontmatter to files without it
    - Generates IDs for files without valid IDs
    - Renames files to follow date-slug format (YYYY-MM-DD-slug.md)
    - Ensures all required fields are present

    Examples:
        cub organize-captures
        cub organize-captures --dry-run
        cub organize-captures --yes
        cub organize-captures --global
    """
    debug = ctx.obj.get("debug", False)

    # Initialize the appropriate store
    if global_store:
        store = CaptureStore.global_store()
        location = "global"
    else:
        store = CaptureStore.project()
        location = "project"

    captures_dir = store.get_captures_dir()

    # Check if captures directory exists
    if not captures_dir.exists():
        console.print(f"[yellow]Warning:[/yellow] Captures directory not found: {captures_dir}")
        console.print("Nothing to organize.")
        raise typer.Exit(0)

    # Scan for all markdown files
    md_files = list(captures_dir.glob("*.md"))
    if not md_files:
        console.print(f"[dim]No markdown files found in {captures_dir}[/dim]")
        raise typer.Exit(0)

    console.print(f"[dim]Scanning {len(md_files)} markdown files in {location} captures...[/dim]\n")

    # Track changes to be made
    changes: list[dict[str, str | Path]] = []

    for md_file in md_files:
        change = analyze_file(md_file, store, debug)
        if change:
            changes.append(change)

    # Report findings
    if not changes:
        console.print("[green]✓[/green] All capture files are properly organized.")
        raise typer.Exit(0)

    # Display changes in a table
    table = Table(title="Proposed Changes", show_header=True, header_style="bold")
    table.add_column("File", style="cyan")
    table.add_column("Issue", style="yellow")
    table.add_column("Action", style="green")

    for change in changes:
        file_value = change["file"]
        issue_value = change.get("issue", "")
        action_value = change.get("action", "")

        table.add_row(
            str(file_value),
            str(issue_value) if issue_value else "",
            str(action_value) if action_value else "",
        )

    console.print(table)
    console.print(f"\n[bold]{len(changes)} files[/bold] need normalization.")

    # Confirm unless --yes or --dry-run
    if dry_run:
        console.print("\n[dim]Dry run mode - no changes made.[/dim]")
        raise typer.Exit(0)

    if not yes:
        confirm = typer.confirm("\nApply these changes?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    # Apply changes
    console.print("\n[dim]Applying changes...[/dim]")
    success_count = 0
    error_count = 0

    for change in changes:
        try:
            apply_change(change, store)
            success_count += 1
            if debug:
                console.print(f"[green]✓[/green] {change['file']}")
        except Exception as e:
            error_count += 1
            console.print(f"[red]✗[/red] {change['file']}: {e}")

    # Summary
    console.print(f"\n[green]✓[/green] Successfully organized {success_count} files.")
    if error_count > 0:
        console.print(f"[red]✗[/red] Failed to organize {error_count} files.")
        raise typer.Exit(1)


def analyze_file(
    md_file: Path,
    store: CaptureStore,
    debug: bool = False,
) -> dict[str, str | Path] | None:
    """
    Analyze a markdown file and determine what needs to be fixed.

    Args:
        md_file: Path to markdown file
        store: CaptureStore instance for ID generation
        debug: Whether to print debug info

    Returns:
        Dictionary describing the change to make, or None if file is OK
    """
    try:
        # Try to parse as frontmatter
        post = frontmatter.load(md_file)

        # Check if it has frontmatter
        if not post.metadata:
            # No frontmatter - needs full setup
            return {
                "file": md_file.name,
                "path": md_file,
                "issue": "Missing frontmatter",
                "action": "Add frontmatter with ID, title, timestamp",
                "fix_type": "add_frontmatter",
                "content": post.content,
            }

        # Has frontmatter - check for valid ID
        capture_id = post.metadata.get("id")
        if not capture_id or not isinstance(capture_id, str) or not capture_id.startswith("cap-"):
            return {
                "file": md_file.name,
                "path": md_file,
                "issue": "Invalid or missing ID",
                "action": "Generate valid cap-NNN ID",
                "fix_type": "fix_id",
                "metadata": post.metadata,
                "content": post.content,
            }

        # Check if filename follows convention (cap-NNN.md or YYYY-MM-DD-slug.md)
        filename = md_file.name
        is_cap_format = filename.startswith("cap-") and filename.endswith(".md")
        is_date_format = len(filename) > 10 and filename[:10].count("-") == 2

        if not is_cap_format and not is_date_format:
            # Suggest rename to date-slug format
            try:
                # Try to parse the capture to get created date
                capture = Capture.from_frontmatter_dict(post.metadata)
                date_str = capture.created.strftime("%Y-%m-%d")
                slug = generate_slug(capture.title)
                new_filename = f"{date_str}-{slug}.md"

                return {
                    "file": md_file.name,
                    "path": md_file,
                    "issue": "Non-standard filename",
                    "action": f"Rename to {new_filename}",
                    "fix_type": "rename",
                    "new_filename": new_filename,
                }
            except Exception:
                # If we can't parse the capture, just note the issue
                if debug:
                    console.print(f"[dim]Warning: Could not parse capture {md_file.name}[/dim]")

        # File looks OK
        return None

    except Exception as e:
        # Parse error - file is malformed
        return {
            "file": md_file.name,
            "path": md_file,
            "issue": f"Parse error: {e}",
            "action": "Manual review needed",
            "fix_type": "error",
        }


def apply_change(change: dict[str, str | Path], store: CaptureStore) -> None:
    """
    Apply a normalization change to a file.

    Args:
        change: Dictionary describing the change to make
        store: CaptureStore instance for ID generation

    Raises:
        Exception: If the change cannot be applied
    """
    fix_type = change.get("fix_type")
    md_file = change["path"]

    if not isinstance(md_file, Path):
        raise ValueError(f"Invalid path in change: {md_file}")

    if fix_type == "add_frontmatter":
        # Add frontmatter to file without it
        content = change.get("content", "")
        if not isinstance(content, str):
            content = str(content)

        # Generate new ID
        capture_id = store.next_id()

        # Extract title from content (first line or first 80 chars)
        lines = content.strip().split("\n")
        title = lines[0].strip() if lines else "Untitled capture"
        if len(title) > 80:
            title = title[:77] + "..."

        # Create capture object
        capture = Capture(
            id=capture_id,
            created=datetime.now(timezone.utc),
            title=title,
            tags=[],
            source=CaptureSource.MANUAL,
        )

        # Save with frontmatter
        store.save_capture(capture, content)

        # Remove old file if it has a different name
        expected_path = store.get_captures_dir() / f"{capture_id}.md"
        if md_file != expected_path:
            md_file.unlink()

    elif fix_type == "fix_id":
        # Fix missing or invalid ID
        metadata: dict[str, str | list[str] | int | None] = change.get("metadata", {})  # type: ignore[assignment]
        content = change.get("content", "")

        if not isinstance(metadata, dict):
            metadata = {}
        if not isinstance(content, str):
            content = str(content)

        # Generate new ID
        capture_id = store.next_id()
        metadata["id"] = capture_id

        # Ensure required fields exist
        if "created" not in metadata:
            metadata["created"] = datetime.now(timezone.utc).isoformat()

        if "title" not in metadata:
            # Extract from content
            lines = content.strip().split("\n")
            title = lines[0].strip() if lines else "Untitled capture"
            if len(title) > 80:
                title = title[:77] + "..."
            metadata["title"] = title

        # Ensure source is set
        if "source" not in metadata:
            metadata["source"] = CaptureSource.MANUAL.value

        # Write updated file
        post = frontmatter.Post(content)
        post.metadata = metadata

        new_path = store.get_captures_dir() / f"{capture_id}.md"
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))

        # Remove old file if different
        if md_file != new_path:
            md_file.unlink()

    elif fix_type == "rename":
        # Rename file to follow convention
        new_filename = change.get("new_filename")
        if not isinstance(new_filename, str):
            raise ValueError(f"Invalid new_filename: {new_filename}")

        new_path = md_file.parent / new_filename

        # Don't overwrite existing files
        if new_path.exists():
            raise FileExistsError(f"Target file already exists: {new_filename}")

        md_file.rename(new_path)

    elif fix_type == "error":
        # Manual review needed - skip
        raise ValueError(f"File needs manual review: {change.get('issue')}")

    else:
        raise ValueError(f"Unknown fix type: {fix_type}")
