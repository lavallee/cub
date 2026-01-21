"""
Cub CLI - Main application entry point.

This module sets up the Typer CLI application with all subcommands.
"""

import typer
from rich.console import Console

from cub import __version__
from cub.cli import (
    audit,
    capture,
    captures,
    delegated,
    merge,
    monitor,
    organize_captures,
    plan,
    pr,
    run,
    sandbox,
    spec,
    stage,
    status,
    triage,
    uninstall,
    update,
    upgrade,
    worktree,
)

# Help panel names for command grouping
PANEL_KEY = "Key Commands"
PANEL_STATUS = "See What a Run is Doing"
PANEL_TASKS = "Work with Tasks"
PANEL_PLAN = "Plan from Specs"
PANEL_EPICS = "Manage Epics (Groups of Tasks)"
PANEL_PROJECT = "Improve Your Project"
PANEL_ROADMAP = "Manage Your Roadmap"
PANEL_INSTALL = "Manage Your Cub Installation"

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


# =============================================================================
# Key Commands
# =============================================================================

app.command(name="init", rich_help_panel=PANEL_KEY)(delegated.init)
app.add_typer(run.app, name="run", rich_help_panel=PANEL_KEY)


# =============================================================================
# See What a Run is Doing
# =============================================================================

app.add_typer(status.app, name="status", rich_help_panel=PANEL_STATUS)
app.add_typer(monitor.app, name="monitor", rich_help_panel=PANEL_STATUS)
app.add_typer(sandbox.app, name="sandbox", rich_help_panel=PANEL_STATUS)
app.command(name="artifacts", rich_help_panel=PANEL_STATUS)(delegated.artifacts)


# =============================================================================
# Work with Tasks
# =============================================================================

app.command(name="interview", rich_help_panel=PANEL_TASKS)(delegated.interview)
app.command(name="explain-task", rich_help_panel=PANEL_TASKS)(delegated.explain_task)
app.command(name="close-task", rich_help_panel=PANEL_TASKS)(delegated.close_task)
app.command(name="verify-task", rich_help_panel=PANEL_TASKS)(delegated.verify_task)


# =============================================================================
# Plan from Specs
# =============================================================================

app.add_typer(plan.app, name="plan", rich_help_panel=PANEL_PLAN)
app.add_typer(stage.app, name="stage", rich_help_panel=PANEL_PLAN)


# =============================================================================
# Manage Epics (Groups of Tasks)
# =============================================================================

app.command(name="branch", rich_help_panel=PANEL_EPICS)(delegated.branch)
app.command(name="branches", rich_help_panel=PANEL_EPICS)(delegated.branches)
app.add_typer(worktree.app, name="worktree", rich_help_panel=PANEL_EPICS)
app.command(name="checkpoints", rich_help_panel=PANEL_EPICS)(delegated.checkpoints)
app.add_typer(pr.app, name="pr", rich_help_panel=PANEL_EPICS)
app.add_typer(merge.app, name="merge", rich_help_panel=PANEL_EPICS)


# =============================================================================
# Improve Your Project
# =============================================================================

app.command(name="guardrails", rich_help_panel=PANEL_PROJECT)(delegated.guardrails)
app.add_typer(audit.app, name="audit", rich_help_panel=PANEL_PROJECT)


# =============================================================================
# Manage Your Roadmap
# =============================================================================

app.command(name="capture", rich_help_panel=PANEL_ROADMAP)(capture.capture)
app.add_typer(captures.app, name="captures", rich_help_panel=PANEL_ROADMAP)
app.command(name="spec", rich_help_panel=PANEL_ROADMAP)(spec.spec)
app.add_typer(triage.app, name="triage", rich_help_panel=PANEL_ROADMAP)
app.command(name="organize-captures", rich_help_panel=PANEL_ROADMAP)(
    organize_captures.organize_captures
)
app.command(name="import", rich_help_panel=PANEL_ROADMAP)(delegated.import_cmd)


# =============================================================================
# Manage Your Cub Installation
# =============================================================================


@app.command(rich_help_panel=PANEL_INSTALL)
def version() -> None:
    """Show cub version and exit."""
    console.print(f"cub version {__version__}")
    raise typer.Exit(0)


app.add_typer(update.app, name="update", rich_help_panel=PANEL_INSTALL)
app.add_typer(upgrade.app, name="system-upgrade", rich_help_panel=PANEL_INSTALL)
app.add_typer(uninstall.app, name="uninstall", rich_help_panel=PANEL_INSTALL)
app.command(name="doctor", rich_help_panel=PANEL_INSTALL)(delegated.doctor)


# =============================================================================
# Deprecated Commands (for backwards compatibility)
# =============================================================================
#
# Note: The old `cub triage` command from the prep pipeline has been replaced
# by `cub plan orient`. However, `triage` is now used for capture processing
# (a different feature), so we don't register a deprecated `triage` command.

app.command(name="prep", hidden=True)(delegated.prep)
app.command(name="bootstrap", hidden=True)(delegated.bootstrap)


def cli_main() -> None:
    """
    Main CLI entry point.

    All commands (including bash-delegated ones) are now registered
    in the Typer app, so we just invoke it directly.
    """
    app()


__all__ = ["app", "cli_main"]
