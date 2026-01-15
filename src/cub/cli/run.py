"""
Cub CLI - Run command.

Execute autonomous task loop with specified harness.
"""


import typer
from rich.console import Console

app = typer.Typer(
    name="run",
    help="Execute autonomous task loop",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    harness: str | None = typer.Option(
        None,
        "--harness",
        "-h",
        help="AI harness to use (claude, codex, gemini, opencode)",
    ),
    once: bool = typer.Option(
        False,
        "--once",
        help="Run a single iteration then exit",
    ),
    task_id: str | None = typer.Option(
        None,
        "--task",
        "-t",
        help="Run specific task by ID",
    ),
    budget: float | None = typer.Option(
        None,
        "--budget",
        "-b",
        help="Maximum budget in USD (default: from config)",
    ),
) -> None:
    """
    Execute autonomous task loop.

    Runs the main cub loop, picking up tasks and executing them with the
    specified AI harness until stopped or budget is exhausted.

    Examples:
        cub run                         # Run with default harness
        cub run --harness claude        # Run with Claude
        cub run --once                  # Run one iteration
        cub run --task cub-123          # Run specific task
        cub run --budget 5.0            # Set budget to $5
    """
    debug = ctx.obj.get("debug", False)

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Harness: {harness or 'default'}[/dim]")
        console.print(f"[dim]Once: {once}[/dim]")
        console.print(f"[dim]Task: {task_id or 'auto'}[/dim]")
        console.print(f"[dim]Budget: {budget or 'from config'}[/dim]")

    console.print("[yellow]Run command not yet implemented[/yellow]")
    console.print("This will execute the main autonomous task loop.")
    raise typer.Exit(0)


__all__ = ["app"]
