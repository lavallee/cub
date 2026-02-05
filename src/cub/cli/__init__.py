"""
Cub CLI - Main application entry point.

This module sets up the Typer CLI application with all subcommands.
"""

import sys

import typer
from rich.console import Console

from cub import __version__
from cub.cli import (
    audit,
    capture,
    captures,
    dashboard,
    delegated,
    docs,
    doctor,
    hooks,
    init_cmd,
    learn,
    ledger,
    map,
    merge,
    monitor,
    new,
    organize_captures,
    plan,
    pr,
    punchlist,
    reconcile,
    release,
    retro,
    review,
    routes,
    run,
    sandbox,
    session,
    spec,
    stage,
    status,
    suggest,
    sync,
    task,
    tools,
    toolsmith,
    uninstall,
    update,
    upgrade,
    verify,
    workbench,
    workflow,
    worktree,
)
from cub.cli.argv import preprocess_argv
from cub.core.config.env import load_layered_env

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
    help="Autonomous AI coding agent for reliable task execution",
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output with detailed logging",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Resume previous harness session",
    ),
    continue_session: bool = typer.Option(
        False,
        "--continue",
        help="Continue from previous harness session",
    ),
) -> None:
    """
    Cub - AI Coding Assistant Loop.

    An autonomous coding agent that executes tasks with Claude, Codex, Gemini,
    or other AI harnesses. Handles task management, clean state verification,
    budget tracking, and structured logging.

    When run without a subcommand, cub launches your default harness with
    project context and smart suggestions. Use --resume or --continue to
    pick up where you left off.

    Quick Start:
        1. cub init                  # Initialize your project
        2. cub task create "Title"   # Create a task
        3. cub run                   # Start the autonomous loop

    Interactive Mode:
        cub                          # Launch default harness
        cub --resume                 # Resume previous session
        cub --continue               # Continue previous session

    Common Workflows:
        # Plan new work
        cub capture "idea"           # Quick capture
        cub spec                     # Create detailed spec
        cub plan run                 # Plan implementation
        cub task create              # Create tasks from plan

        # Execute tasks
        cub run                      # Pick up tasks automatically
        cub run --task cub-123       # Work on specific task
        cub run --epic backend-v2    # Work on an epic
        cub run --once               # Single iteration

        # Monitor and review
        cub status                   # Show session status
        cub monitor                  # Live dashboard
        cub ledger                   # View completed work
        cub review                   # Deep review of completion

        # Git integration
        cub branch cub-123           # Create feature branch
        cub pr cub-123               # Create pull request
        cub merge                    # Merge PR

    Documentation:
        cub --help                   # This message
        cub <command> --help         # Help for specific command
        https://github.com/anthropics/cub
    """
    # Load layered env files early so API keys etc. are available to all commands.
    # Precedence: OS env > project .env > user .env
    load_layered_env()

    # Store debug flag in context for subcommands
    ctx.obj = {"debug": debug}

    # If a subcommand is being invoked, let it handle things
    if ctx.invoked_subcommand is not None:
        return

    # Bare `cub` — launch default command handler
    from cub.cli.default import default_command

    default_command(
        resume=resume,
        continue_session=continue_session,
        debug=debug,
    )


# =============================================================================
# Key Commands
# =============================================================================

app.command(name="init", rich_help_panel=PANEL_KEY)(init_cmd.main)
app.command(name="new", rich_help_panel=PANEL_KEY)(new.new)
app.add_typer(run.app, name="run", rich_help_panel=PANEL_KEY)


# =============================================================================
# See What a Run is Doing
# =============================================================================

app.add_typer(status.app, name="status", rich_help_panel=PANEL_STATUS)
app.add_typer(suggest.app, name="suggest", rich_help_panel=PANEL_STATUS)
app.add_typer(monitor.app, name="monitor", rich_help_panel=PANEL_STATUS)
app.add_typer(sandbox.app, name="sandbox", rich_help_panel=PANEL_STATUS)
app.add_typer(ledger.app, name="ledger", rich_help_panel=PANEL_STATUS)
app.add_typer(reconcile.app, name="reconcile", rich_help_panel=PANEL_STATUS)
app.add_typer(review.app, name="review", rich_help_panel=PANEL_STATUS)
app.add_typer(dashboard.app, name="dashboard", rich_help_panel=PANEL_STATUS)
app.command(name="artifacts", rich_help_panel=PANEL_STATUS)(delegated.artifacts)


# =============================================================================
# Work with Tasks
# =============================================================================

app.add_typer(task.app, name="task", rich_help_panel=PANEL_TASKS)
app.add_typer(punchlist.app, name="punchlist", rich_help_panel=PANEL_TASKS)
app.add_typer(workflow.app, name="workflow", rich_help_panel=PANEL_TASKS)
app.add_typer(sync.app, name="sync", rich_help_panel=PANEL_TASKS)
app.add_typer(session.app, name="session", rich_help_panel=PANEL_TASKS)
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
app.add_typer(verify.app, name="verify", rich_help_panel=PANEL_PROJECT)
app.add_typer(learn.app, name="learn", rich_help_panel=PANEL_PROJECT)
app.command(name="map", rich_help_panel=PANEL_PROJECT)(map.main)
app.add_typer(routes.app, name="routes", rich_help_panel=PANEL_PROJECT)


# =============================================================================
# Manage Your Roadmap
# =============================================================================

app.command(name="capture", rich_help_panel=PANEL_ROADMAP)(capture.capture)
app.add_typer(captures.app, name="captures", rich_help_panel=PANEL_ROADMAP)
app.command(name="spec", rich_help_panel=PANEL_ROADMAP)(spec.spec)
app.command(name="triage", rich_help_panel=PANEL_ROADMAP)(delegated.triage)
app.command(name="organize-captures", rich_help_panel=PANEL_ROADMAP)(
    organize_captures.organize_captures
)
app.command(name="import", rich_help_panel=PANEL_ROADMAP)(delegated.import_cmd)
app.add_typer(release.app, name="release", rich_help_panel=PANEL_ROADMAP)
app.add_typer(retro.app, name="retro", rich_help_panel=PANEL_ROADMAP)
app.add_typer(tools.app, name="tools", rich_help_panel=PANEL_ROADMAP)
app.add_typer(toolsmith.app, name="toolsmith", rich_help_panel=PANEL_ROADMAP)
app.add_typer(workbench.app, name="workbench", rich_help_panel=PANEL_ROADMAP)


# =============================================================================
# Manage Your Cub Installation
# =============================================================================


@app.command(rich_help_panel=PANEL_INSTALL)
def version() -> None:
    """Show cub version and exit."""
    console.print(f"cub version {__version__}")
    raise typer.Exit(0)


app.command(name="docs", rich_help_panel=PANEL_INSTALL)(docs.docs)
app.add_typer(update.app, name="update", rich_help_panel=PANEL_INSTALL)
app.add_typer(upgrade.app, name="system-upgrade", rich_help_panel=PANEL_INSTALL)
app.add_typer(uninstall.app, name="uninstall", rich_help_panel=PANEL_INSTALL)
app.add_typer(doctor.app, name="doctor", rich_help_panel=PANEL_INSTALL)
app.add_typer(hooks.app, name="hooks", rich_help_panel=PANEL_INSTALL)


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

    The argv preprocessor normalizes common patterns before Typer
    parses them (e.g. ``cub --version``, ``cub help run``,
    ``cub run --debug``).
    """
    sys.argv[1:] = preprocess_argv(sys.argv[1:])
    app()


__all__ = ["app", "cli_main"]
