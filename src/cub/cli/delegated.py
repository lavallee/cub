"""
Delegated commands that invoke the bash version of cub.

These commands are not yet ported to Python, so they delegate to the
bash cub script with proper argument passing.
"""


import typer

from cub.core.bash_delegate import delegate_to_bash


def _delegate(command: str, args: list[str]) -> None:
    """
    Delegate to bash with the provided arguments.

    Args:
        command: The bash command name
        args: Arguments to pass to the bash command
    """
    delegate_to_bash(command, args)


# Vision-to-Tasks Prep Pipeline (v0.14)


def prep(args: list[str] | None = typer.Argument(None)) -> None:
    """Run full prep pipeline (triage→architect→plan→bootstrap)."""
    _delegate("prep", args or [])


def triage(args: list[str] | None = typer.Argument(None)) -> None:
    """Stage 1: Requirements refinement."""
    _delegate("triage", args or [])


def architect(args: list[str] | None = typer.Argument(None)) -> None:
    """Stage 2: Technical design."""
    _delegate("architect", args or [])


def plan(args: list[str] | None = typer.Argument(None)) -> None:
    """Stage 3: Task decomposition."""
    _delegate("plan", args or [])


def bootstrap(args: list[str] | None = typer.Argument(None)) -> None:
    """Stage 4: Initialize beads from prep artifacts."""
    _delegate("bootstrap", args or [])


def sessions(args: list[str] | None = typer.Argument(None)) -> None:
    """List and manage prep sessions."""
    _delegate("sessions", args or [])


# Task & Artifact Commands


def explain(args: list[str] | None = typer.Argument(None)) -> None:
    """Show detailed task information."""
    _delegate("explain", args or [])


def artifacts(args: list[str] | None = typer.Argument(None)) -> None:
    """List task output artifacts."""
    _delegate("artifacts", args or [])


def validate(args: list[str] | None = typer.Argument(None)) -> None:
    """Validate beads state and configuration."""
    _delegate("validate", args or [])


# Git Workflow Integration (v0.19)


def branch(args: list[str] | None = typer.Argument(None)) -> None:
    """Create and bind branch to epic."""
    _delegate("branch", args or [])


def branches(args: list[str] | None = typer.Argument(None)) -> None:
    """List and manage branch-epic bindings."""
    _delegate("branches", args or [])


def checkpoints(args: list[str] | None = typer.Argument(None)) -> None:
    """Manage review/approval gates."""
    _delegate("checkpoints", args or [])


def pr(args: list[str] | None = typer.Argument(None)) -> None:
    """Create pull request for epic."""
    _delegate("pr", args or [])


# Interview Mode (v0.16)


def interview(args: list[str] | None = typer.Argument(None)) -> None:
    """Deep dive on task specifications."""
    _delegate("interview", args or [])


def import_cmd(args: list[str] | None = typer.Argument(None)) -> None:
    """Import tasks from external sources."""
    _delegate("import", args or [])


def guardrails(args: list[str] | None = typer.Argument(None)) -> None:
    """Display and manage institutional memory."""
    _delegate("guardrails", args or [])


# Project Initialization


def init(args: list[str] | None = typer.Argument(None)) -> None:
    """Initialize cub in a project or globally."""
    _delegate("init", args or [])


# Utility & Maintenance


def doctor(args: list[str] | None = typer.Argument(None)) -> None:
    """Diagnose and fix configuration issues."""
    _delegate("doctor", args or [])


def upgrade(args: list[str] | None = typer.Argument(None)) -> None:
    """Upgrade cub to newer version."""
    _delegate("upgrade", args or [])


def migrate_layout(args: list[str] | None = typer.Argument(None)) -> None:
    """Migrate legacy layout to new .cub/ structure."""
    _delegate("migrate-layout", args or [])


# Agent Commands (internal use)


def agent_close(args: list[str] | None = typer.Argument(None)) -> None:
    """Close a task (for agent use)."""
    _delegate("agent-close", args or [])


def agent_verify(args: list[str] | None = typer.Argument(None)) -> None:
    """Verify task is closed (for agent use)."""
    _delegate("agent-verify", args or [])
