"""
Cub CLI - Init command.

Initialize cub in a project or globally.
"""

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="init",
    help="Initialize cub in a project",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def init(
    ctx: typer.Context,
    path: Path | None = typer.Argument(
        None,
        help="Path to initialize (defaults to current directory)",
    ),
    global_init: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Initialize global cub configuration",
    ),
    harness: str | None = typer.Option(
        None,
        "--harness",
        "-h",
        help="Default harness to use (claude, codex, gemini, opencode)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration",
    ),
) -> None:
    """
    Initialize cub in a project or globally.

    Creates configuration files and sets up the project structure for cub.

    Examples:
        cub init                        # Initialize in current directory
        cub init /path/to/project       # Initialize in specific directory
        cub init --global               # Initialize global config
        cub init --harness claude       # Set default harness
        cub init --force                # Overwrite existing config
    """
    debug = ctx.obj.get("debug", False)

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Path: {path or Path.cwd()}[/dim]")
        console.print(f"[dim]Global: {global_init}[/dim]")
        console.print(f"[dim]Harness: {harness or 'default'}[/dim]")
        console.print(f"[dim]Force: {force}[/dim]")

    target_path = path or Path.cwd()

    if global_init:
        console.print("[cyan]Initializing global cub configuration...[/cyan]")
    else:
        console.print(f"[cyan]Initializing cub in {target_path}...[/cyan]")

    console.print("[yellow]Init command not yet implemented[/yellow]")
    console.print("This will create .cub.json and set up project structure.")
    raise typer.Exit(0)


__all__ = ["app"]
