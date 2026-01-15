"""
Cub CLI - Main application entry point.

This module sets up the Typer CLI application with all subcommands.
"""

import typer
from rich.console import Console

from cub import __version__
from cub.cli import delegated, monitor, run, status, upgrade

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
app.add_typer(monitor.app, name="monitor")
app.add_typer(upgrade.app, name="upgrade")

# Register delegated commands (bash cub commands not yet ported)
app.command(name="init")(delegated.init)
app.command(name="prep")(delegated.prep)
app.command(name="triage")(delegated.triage)
app.command(name="architect")(delegated.architect)
app.command(name="plan")(delegated.plan)
app.command(name="bootstrap")(delegated.bootstrap)
app.command(name="sessions")(delegated.sessions)
app.command(name="explain")(delegated.explain)
app.command(name="artifacts")(delegated.artifacts)
app.command(name="validate")(delegated.validate)
app.command(name="branch")(delegated.branch)
app.command(name="branches")(delegated.branches)
app.command(name="checkpoints")(delegated.checkpoints)
app.command(name="pr")(delegated.pr)
app.command(name="interview")(delegated.interview)
app.command(name="import")(delegated.import_cmd)
app.command(name="guardrails")(delegated.guardrails)
app.command(name="doctor")(delegated.doctor)
app.command(name="migrate-layout")(delegated.migrate_layout)
app.command(name="agent-close")(delegated.agent_close)
app.command(name="agent-verify")(delegated.agent_verify)


def cli_main() -> None:
    """
    Main CLI entry point.

    All commands (including bash-delegated ones) are now registered
    in the Typer app, so we just invoke it directly.
    """
    app()


__all__ = ["app", "cli_main"]
