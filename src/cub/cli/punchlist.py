"""
Cub CLI - Punchlist command.

Process punchlist markdown files into epics with child tasks.
Punchlists contain small bugs/features separated by em-dash delimiters.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.punchlist import parse_punchlist, process_punchlist
from cub.core.punchlist.models import HydratedItem, PunchlistResult

console = Console()
app = typer.Typer(help="Process punchlist files into epics with tasks")

# Default directory for punchlists
DEFAULT_PUNCHLIST_DIR = Path("plans/_punchlists")


@app.callback(invoke_without_command=True)
def punchlist(
    ctx: typer.Context,
    file: Path = typer.Argument(
        None,
        help="Punchlist markdown file to process",
        exists=True,
        readable=True,
    ),
    epic_title: str | None = typer.Option(
        None,
        "--epic-title",
        "-t",
        help="Custom title for the epic (default: derived from filename)",
    ),
    labels: list[str] | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Additional labels for the epic (can be repeated)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be created without creating tasks",
    ),
    no_write_back: bool = typer.Option(
        False,
        "--no-write-back",
        help="Don't update the punchlist file with structured format",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed progress during processing",
    ),
    list_files: bool = typer.Option(
        False,
        "--list",
        help="List punchlist files in plans/_punchlists/",
    ),
) -> None:
    """
    Process a punchlist into an epic with child tasks.

    Punchlists are markdown files with items separated by em-dash
    delimiters (—— or --). Each item becomes a task under a single epic.

    Examples:

        # Process a punchlist
        cub punchlist plans/_punchlists/v0.27.0-bugs.md

        # With custom epic title
        cub punchlist bugs.md --epic-title "Sprint 12 Bugs"

        # Dry run to preview
        cub punchlist bugs.md --dry-run

        # List available punchlists
        cub punchlist --list
    """
    # If --list flag, show available punchlists
    if list_files:
        _list_punchlists()
        return

    # If a subcommand was invoked, don't run the default callback
    if ctx.invoked_subcommand is not None:
        return

    # File is required for processing
    if file is None:
        console.print("[red]Error:[/red] Punchlist file is required.")
        console.print("\nUsage: cub punchlist <file>")
        console.print("       cub punchlist --list  (to see available files)")
        raise typer.Exit(1)

    # Parse first to show count
    try:
        items = parse_punchlist(file)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] File not found: {file}")
        raise typer.Exit(1)
    except PermissionError:
        console.print(f"[red]Error:[/red] Permission denied: {file}")
        raise typer.Exit(1)

    if not items:
        console.print(f"[yellow]Warning:[/yellow] No items found in {file}")
        console.print("\nPunchlist items should be separated by em-dash lines (—— or --)")
        raise typer.Exit(1)

    console.print(f"Processing: [bold]{file}[/bold]")
    console.print(f"Parsed [cyan]{len(items)}[/cyan] items")

    if verbose:
        console.print("\n[dim]Items found:[/dim]")
        for i, item in enumerate(items, 1):
            preview = item.raw_text[:60].replace("\n", " ")
            if len(item.raw_text) > 60:
                preview += "..."
            console.print(f"  {i}. {preview}")
        console.print()

    # Progress callback for hydration
    def on_hydrated(current: int, total: int, hydrated: HydratedItem) -> None:
        if verbose:
            console.print(f'  [{current + 1}/{total}] "{hydrated.title}"')

    console.print("\nHydrating items with Claude...")

    # Process the punchlist
    try:
        result = process_punchlist(
            path=file,
            epic_title=epic_title,
            labels=labels or [],
            dry_run=dry_run,
            write_back=not no_write_back,
            on_item_hydrated=on_hydrated if verbose else None,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Show results
    console.print()
    if dry_run:
        console.print("[yellow]Dry run - no tasks created[/yellow]\n")
        _show_dry_run_result(result)
    else:
        _show_result(result)

    # Suggest next steps
    if not dry_run:
        console.print(f"\nNext: [bold]cub run --epic {result.epic.id}[/bold]")


def _list_punchlists() -> None:
    """List available punchlist files."""
    # Check default directory
    punchlist_dir = DEFAULT_PUNCHLIST_DIR

    if not punchlist_dir.exists():
        console.print(f"[yellow]No punchlist directory found:[/yellow] {punchlist_dir}")
        console.print("\nCreate the directory and add .md files with items separated by ——")
        return

    # Find all markdown files
    files = sorted(punchlist_dir.glob("*.md"))

    if not files:
        console.print(f"[yellow]No punchlist files found in:[/yellow] {punchlist_dir}")
        console.print("\nAdd .md files with items separated by —— (em-dash)")
        return

    table = Table(
        title=f"Punchlists in {punchlist_dir}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("File", style="bold")
    table.add_column("Items", justify="right")
    table.add_column("Size")

    for f in files:
        # Count items
        try:
            items = parse_punchlist(f)
            item_count = str(len(items))
        except Exception:
            item_count = "[dim]?[/dim]"

        # File size
        size = f.stat().st_size
        if size < 1024:
            size_str = f"{size} B"
        else:
            size_str = f"{size / 1024:.1f} KB"

        table.add_row(f.name, item_count, size_str)

    console.print(table)
    console.print("\nProcess with: [bold]cub punchlist <filename>[/bold]")


def _show_dry_run_result(result: PunchlistResult) -> None:
    """Display dry run results."""
    console.print(f"[bold]Epic:[/bold] {result.epic.title}")
    stem = result.source_file.stem if result.source_file else "unknown"
    console.print(f"[dim]Labels:[/dim] punchlist, punchlist:{stem}")
    console.print()

    table = Table(
        title=f"Tasks ({result.task_count})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", width=3)
    table.add_column("Title", overflow="fold")

    for i, task in enumerate(result.tasks, 1):
        table.add_row(str(i), task.title)

    console.print(table)


def _show_result(result: PunchlistResult) -> None:
    """Display processing results."""
    console.print("[green]Created:[/green]")
    epic_info = f"[bold]{result.epic.id}[/bold] ({result.epic.title})"
    console.print(f"  Epic: {epic_info} - {result.task_count} tasks")

    if result.task_count <= 10:
        console.print("\n[dim]Tasks:[/dim]")
        for task in result.tasks:
            console.print(f"  • {task.id}: {task.title}")
