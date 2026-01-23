"""
Delegated commands that invoke the bash version of cub.

These commands are not yet ported to Python, so they delegate to the
bash cub script with proper argument passing.
"""

import os
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from cub.core.bash_delegate import delegate_to_bash, find_bash_cub
from cub.utils.hooks import HookContext, run_hooks

console = Console()


def _delegate(command: str, args: list[str], ctx: typer.Context | None = None) -> None:
    """
    Delegate to bash with the provided arguments.

    Args:
        command: The bash command name
        args: Arguments to pass to the bash command
        ctx: Typer context (optional, for accessing debug flag)
    """
    # Extract debug flag from context if available
    debug = False
    if ctx and ctx.obj:
        debug = ctx.obj.get("debug", False)

    delegate_to_bash(command, args, debug=debug)


# Vision-to-Tasks Prep Pipeline (v0.14)


def prep(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Run full prep pipeline (triage→architect→plan→bootstrap)."""
    _delegate("prep", args or [], ctx)


def triage(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Stage 1: Requirements refinement."""
    _delegate("triage", args or [], ctx)


def architect(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Stage 2: Technical design."""
    _delegate("architect", args or [], ctx)


def plan(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Stage 3: Task decomposition."""
    _delegate("plan", args or [], ctx)


def stage(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Import tasks from plan to task backend."""
    _delegate("stage", args or [], ctx)


def spec(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Create feature specifications through interactive process."""
    _delegate("spec", args or [], ctx)


def bootstrap(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Stage 4: Initialize beads from prep artifacts."""
    _delegate("bootstrap", args or [], ctx)


def sessions(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """List and manage prep sessions."""
    _delegate("sessions", args or [], ctx)


# Task & Artifact Commands


def explain_task(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Show detailed task information."""
    _delegate("explain-task", args or [], ctx)


def artifacts(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """List task output artifacts."""
    _delegate("artifacts", args or [], ctx)


def validate(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Validate beads state and configuration."""
    _delegate("validate", args or [], ctx)


# Git Workflow Integration (v0.19)


def branch(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Create and bind branch to epic."""
    _delegate("branch", args or [], ctx)


def branches(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """List and manage branch-epic bindings."""
    _delegate("branches", args or [], ctx)


def checkpoints(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Manage review/approval gates."""
    _delegate("checkpoints", args or [], ctx)


# Interview Mode (v0.16)


def interview(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Deep dive on task specifications."""
    _delegate("interview", args or [], ctx)


def import_cmd(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Import tasks from external sources."""
    _delegate("import", args or [], ctx)


def guardrails(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Display and manage institutional memory."""
    _delegate("guardrails", args or [], ctx)


def update(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Update project templates and skills from installed cub."""
    _delegate("update", args or [], ctx)


# Project Initialization


def init(
    ctx: typer.Context,
    global_: bool = typer.Option(False, "--global", "-g", help="Set up global configuration"),
    args: list[str] | None = typer.Argument(None),
) -> None:
    """Initialize cub in a project or globally."""
    # Build arguments
    all_args = []
    if global_:
        all_args.append("--global")
    if args:
        all_args.extend(args)

    # Extract debug flag
    debug = False
    if ctx and ctx.obj:
        debug = ctx.obj.get("debug", False)

    # Run init command (custom delegation to capture exit code for hook)
    try:
        bash_cub = find_bash_cub()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    cmd = [str(bash_cub), "init"] + all_args
    env = os.environ.copy()
    if debug:
        env["CUB_DEBUG"] = "true"

    result = subprocess.run(cmd, env=env, check=False)

    # Fire post-init hook on success
    if result.returncode == 0:
        project_dir = Path.cwd()
        init_type = "global" if global_ else "project"
        context = HookContext(
            hook_name="post-init",
            project_dir=project_dir,
            init_type=init_type,
        )
        run_hooks("post-init", context, project_dir)

    raise typer.Exit(result.returncode)


# Utility & Maintenance


def doctor(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Diagnose and fix configuration issues."""
    _delegate("doctor", args or [], ctx)


# Task Commands (for agent use)


def close_task(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Close a task (for agent use)."""
    _delegate("close-task", args or [], ctx)


def verify_task(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """Verify task is closed (for agent use)."""
    _delegate("verify-task", args or [], ctx)
