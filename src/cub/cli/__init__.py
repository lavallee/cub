"""
Cub CLI - Main application entry point.

This module sets up the Typer CLI application with all subcommands.
"""

import sys

import typer
from rich.console import Console

from cub import __version__
from cub.cli import init_cmd, monitor, run, status
from cub.core.bash_delegate import delegate_to_bash, is_bash_command

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
app.add_typer(monitor.app, name="monitor")


def cli_main() -> None:
    """
    Main CLI entry point with bash delegation support.

    This checks if the command should be delegated to bash before
    invoking the Typer app.
    """
    # Check if we have a command and if it should be delegated
    if len(sys.argv) > 1:
        command = sys.argv[1]
        # Skip if it's a flag (starts with -)
        if not command.startswith("-") and is_bash_command(command):
            # Delegate to bash with all arguments after the command
            delegate_to_bash(command, sys.argv[2:])
            # delegate_to_bash never returns (exits with bash exit code)

    # Not a bash command, proceed with Python CLI
    app()


__all__ = ["app", "cli_main"]
