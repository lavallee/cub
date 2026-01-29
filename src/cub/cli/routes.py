"""
Routes CLI - View and manage learned command routes.

This module provides commands to:
- View compiled routes (learned-routes.md)
- Manually trigger route compilation
- Clear route logs
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from cub.core.routes.compiler import compile_and_write_routes

app = typer.Typer(
    name="routes",
    help="View and manage learned command routes",
    no_args_is_help=True,
)

console = Console()


@app.command()
def show() -> None:
    """
    Display learned routes from .cub/learned-routes.md.

    Shows the compiled markdown table of frequently-used commands.
    If the file doesn't exist, suggests running 'cub routes compile' first.
    """
    routes_file = Path.cwd() / ".cub" / "learned-routes.md"

    if not routes_file.exists():
        console.print(
            "[yellow]No learned routes found.[/yellow]\n"
            "Run [cyan]cub routes compile[/cyan] to generate routes from your command log."
        )
        raise typer.Exit(0)

    # Read and render markdown
    content = routes_file.read_text()
    md = Markdown(content)

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Learned Command Routes[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()
    console.print(md)
    console.print()


@app.command()
def compile(
    min_frequency: Annotated[
        int,
        typer.Option(
            "--min-frequency",
            "-f",
            help="Minimum command frequency to include (default: 3)",
        ),
    ] = 3,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Force compilation even if log file is empty",
        ),
    ] = False,
) -> None:
    """
    Compile routes from route-log.jsonl.

    Reads the raw command log, normalizes commands, aggregates by frequency,
    and writes the result to .cub/learned-routes.md.

    This is normally triggered automatically by the Stop hook at session end,
    but can be run manually for testing or troubleshooting.

    Args:
        min_frequency: Minimum command frequency to include
        force: Force compilation even if log file is empty
    """
    log_file = Path.cwd() / ".cub" / "route-log.jsonl"
    output_file = Path.cwd() / ".cub" / "learned-routes.md"

    if not log_file.exists():
        if not force:
            console.print(
                "[yellow]No route log found at .cub/route-log.jsonl[/yellow]\n"
                "The hook will create this automatically as you use cub commands.\n"
                "Use --force to create an empty learned-routes.md file."
            )
            raise typer.Exit(1)
        else:
            # Create empty log file
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.touch()

    console.print(f"[cyan]Compiling routes from {log_file}...[/cyan]")

    try:
        compile_and_write_routes(log_file, output_file, min_frequency)
        console.print(f"[green]✓[/green] Routes compiled to {output_file}")

        # Show preview
        if output_file.exists():
            content = output_file.read_text()
            # Count routes (lines starting with |, excluding header)
            route_lines = [
                line for line in content.split('\n')
                if line.startswith('| `') and '`' in line
            ]
            console.print(f"[dim]Found {len(route_lines)} route(s)[/dim]")

    except Exception as e:
        console.print(f"[red]Error compiling routes: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def clear() -> None:
    """
    Clear the route log file.

    Deletes .cub/route-log.jsonl to start fresh.
    The learned-routes.md file is preserved.

    Useful for:
    - Resetting after major workflow changes
    - Testing route compilation
    - Cleaning up after development
    """
    log_file = Path.cwd() / ".cub" / "route-log.jsonl"

    if not log_file.exists():
        console.print("[yellow]Route log already empty (file doesn't exist)[/yellow]")
        raise typer.Exit(0)

    # Ask for confirmation
    confirm = typer.confirm(
        "This will delete all logged commands. Continue?",
        default=False,
    )

    if not confirm:
        console.print("[dim]Cancelled[/dim]")
        raise typer.Exit(0)

    log_file.unlink()
    console.print("[green]✓[/green] Route log cleared")
    console.print(
        "[dim]Hint: Run 'cub routes compile' after using cub to rebuild routes[/dim]"
    )
