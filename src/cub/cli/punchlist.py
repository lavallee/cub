"""
Cub CLI - Punchlist command.

Process punchlist markdown files into itemized-plan.md files
suitable for staging with `cub stage`.
"""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.hydrate.models import HydrationResult, HydrationStatus
from cub.core.punchlist import parse_punchlist, process_punchlist
from cub.core.punchlist.models import PunchlistResult

console = Console()
app = typer.Typer(help="Process punchlist files into itemized plans")

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
        help="Show what would be generated without writing files",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output path for the plan file",
    ),
    stream: bool = typer.Option(
        False,
        "--stream",
        "-s",
        help="Stream Claude's output in real-time",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show debug information (prompts, raw responses)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show full raw text before each item",
    ),
    list_files: bool = typer.Option(
        False,
        "--list",
        help="List punchlist files in plans/_punchlists/",
    ),
) -> None:
    """
    Process a punchlist into an itemized plan.

    Punchlists are markdown files with items separated by em-dash
    delimiters (-- or --). Each item is hydrated with Claude and
    written to an itemized-plan.md file for staging.

    Examples:

        # Process a punchlist
        cub punchlist plans/_punchlists/v0.27.0-bugs.md

        # Preview without writing
        cub punchlist bugs.md --dry-run

        # Stream Claude's output
        cub punchlist bugs.md --stream

        # Custom output path
        cub punchlist bugs.md -o plans/my-feature/itemized-plan.md

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
        console.print("\nPunchlist items should be separated by em-dash lines (-- or --)")
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

    # Progress callbacks (always active)
    def on_start(index: int, total: int, source_text: str) -> None:
        preview = source_text[:50].replace("\n", " ")
        if len(source_text) > 50:
            preview += "..."
        console.print(f"  [{index + 1}/{total}] Hydrating: {preview}")
        if verbose:
            console.print(f"  [dim]{source_text}[/dim]")

    def on_complete(index: int, total: int, result: HydrationResult) -> None:
        status_label = "OK" if result.status == HydrationStatus.SUCCESS else "fallback"
        console.print(f'  [{index + 1}/{total}] {status_label} "{result.title}"')

    # Stream callback
    def on_stream(line: str) -> None:
        sys.stdout.write(line)
        sys.stdout.flush()

    # Debug callback
    def on_debug(msg: str) -> None:
        console.print(f"[dim]{msg}[/dim]")

    console.print("\nHydrating items with Claude...")

    # Process the punchlist
    try:
        result = process_punchlist(
            path=file,
            epic_title=epic_title,
            labels=labels or [],
            dry_run=dry_run,
            output=output,
            stream=stream,
            debug=debug,
            stream_callback=on_stream if stream else None,
            debug_callback=on_debug if debug else None,
            on_start=on_start,
            on_complete=on_complete,
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Show results
    console.print()
    if dry_run:
        console.print("[yellow]Dry run - no files written[/yellow]\n")
        _show_dry_run_result(result)
    else:
        _show_result(result)


def _list_punchlists() -> None:
    """List available punchlist files."""
    punchlist_dir = DEFAULT_PUNCHLIST_DIR

    if not punchlist_dir.exists():
        console.print(f"[yellow]No punchlist directory found:[/yellow] {punchlist_dir}")
        console.print("\nCreate the directory and add .md files with items separated by --")
        return

    # Find all markdown files
    files = sorted(punchlist_dir.glob("*.md"))

    if not files:
        console.print(f"[yellow]No punchlist files found in:[/yellow] {punchlist_dir}")
        console.print("\nAdd .md files with items separated by -- (em-dash)")
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
        try:
            items = parse_punchlist(f)
            item_count = str(len(items))
        except Exception:
            item_count = "[dim]?[/dim]"

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
    console.print(f"[bold]Epic:[/bold] {result.epic_title}")
    stem = result.source_file.stem if result.source_file else "unknown"
    console.print(f"[dim]Labels:[/dim] punchlist, punchlist:{stem}")
    console.print(f"[dim]Output would be:[/dim] {result.output_file}")
    console.print()

    table = Table(
        title=f"Tasks ({result.task_count})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", justify="right", width=3)
    table.add_column("Title", overflow="fold")
    table.add_column("Status", width=8)

    for i, item in enumerate(result.items, 1):
        is_ok = item.status == HydrationStatus.SUCCESS
        status_str = "[green]OK[/green]" if is_ok else "[yellow]fallback[/yellow]"
        table.add_row(str(i), item.title, status_str)

    console.print(table)


def _show_result(result: PunchlistResult) -> None:
    """Display processing results."""
    console.print("[green]Generated:[/green]")
    console.print(f"  Epic: [bold]{result.epic_title}[/bold] - {result.task_count} tasks")
    console.print(f"  Plan: [bold]{result.output_file}[/bold]")

    if result.task_count <= 10:
        console.print("\n[dim]Tasks:[/dim]")
        for i, item in enumerate(result.items, 1):
            status_icon = "+" if item.status == HydrationStatus.SUCCESS else "~"
            console.print(f"  {status_icon} {item.title}")

    # Suggest next steps
    console.print(f"\nNext: [bold]cub stage {result.output_file}[/bold]")
