"""
Cub CLI - Main application entry point.

This module sets up the Typer CLI application with all subcommands.
"""

import typer
from rich.console import Console

from cub import __version__
from cub.cli import init_cmd, run, status

# Create the main Typer app
app = typer.Typer(
    name="cub",
    help="AI Coding Assistant Loop - autonomous task execution with Claude, Codex, and more",
    no_args_is_help=True,
    add_completion=True,
)

console = Console()


@app.callback()
def main(
    ctx: typer.Context,
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output",
    ),
) -> None:
    """
    Cub - AI Coding Assistant Loop.

    A CLI tool that wraps AI coding assistants for autonomous task execution.
    """
    # Store debug flag in context for subcommands
    ctx.obj = {"debug": debug}


@app.command()
def version() -> None:
    """Show cub version and exit."""
    console.print(f"cub version {__version__}")
    raise typer.Exit(0)


# Register subcommands
app.add_typer(run.app, name="run")
app.add_typer(status.app, name="status")
app.add_typer(init_cmd.app, name="init")


__all__ = ["app"]
