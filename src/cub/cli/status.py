"""
Cub CLI - Status command.

Show current session status, task progress, and budget usage.
"""


import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="status",
    help="Show current session status",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def status(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed status",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output status as JSON",
    ),
    session: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Show status for specific session ID",
    ),
) -> None:
    """
    Show current session status.

    Displays information about the current or specified session including:
    - Active tasks
    - Budget usage
    - Recent activity
    - Harness status

    Examples:
        cub status                      # Show current session
        cub status --verbose            # Show detailed status
        cub status --json               # JSON output
        cub status --session abc123     # Specific session
    """
    debug = ctx.obj.get("debug", False)

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Verbose: {verbose}[/dim]")
        console.print(f"[dim]JSON output: {json_output}[/dim]")
        console.print(f"[dim]Session: {session or 'current'}[/dim]")

    if json_output:
        console.print('{"status": "not_implemented"}')
        raise typer.Exit(0)

    # Example table output
    table = Table(title="Cub Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", "[yellow]Not yet implemented[/yellow]")
    table.add_row("Session", session or "N/A")
    table.add_row("Tasks", "0")
    table.add_row("Budget Used", "$0.00")

    console.print(table)
    raise typer.Exit(0)


__all__ = ["app"]
