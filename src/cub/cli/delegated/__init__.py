"""
Delegated commands that invoke the bash version of cub.

These commands are not yet ported to Python, so they delegate to the
bash cub script with proper argument passing.
"""

import typer
from rich.console import Console

from cub.cli.delegated.runner import delegate_to_bash

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
    """[DEPRECATED] Run full prep pipeline. Use 'cub plan' instead."""
    _delegate("prep", args or [], ctx)


def triage(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Refine requirements through interactive questions.

    Analyzes capture files or text to understand the problem space.
    Generates structured requirements (acceptance criteria, constraints, etc).

    Examples:
        cub triage my-idea.md        # Triage a capture file
        cub triage --all             # Triage all open captures
        cub triage --help            # Show triage-specific options
    """
    _delegate("triage", args or [], ctx)


def architect(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Design the technical solution.

    Takes refined requirements and generates architecture decisions,
    including tech choices, design patterns, and implementation approach.

    Examples:
        cub architect <spec-id>      # Design solution for a spec
        cub architect --all          # Architect all ready specs
        cub architect --help         # Show architect-specific options
    """
    _delegate("architect", args or [], ctx)


def plan(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Break architecture into actionable tasks.

    Takes architecture decisions and decomposes them into concrete,
    implementable tasks that can be picked up by cub run.

    Examples:
        cub plan <spec-id>           # Plan implementation for a spec
        cub plan --help              # Show plan-specific options
    """
    _delegate("plan", args or [], ctx)


def stage(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Import tasks from a plan into the task backend.

    Takes completed plan tasks and loads them into the task management system
    (beads, JSON, or JSONL) so they can be executed via cub run.

    Examples:
        cub stage <plan-id>          # Import tasks from a specific plan
        cub stage --all              # Import all ready plans
        cub stage --list             # Show available plans
        cub stage --help             # Show stage-specific options
    """
    _delegate("stage", args or [], ctx)


def spec(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Create a feature specification through interactive interview.

    Guides you through detailed questions to create a formal spec document
    including requirements, constraints, acceptance criteria, and edge cases.

    Examples:
        cub spec                     # Start interactive spec creation
        cub spec --list              # List existing specs
        cub spec --help              # Show spec-specific options
    """
    _delegate("spec", args or [], ctx)


def bootstrap(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Initialize task backend from prep artifacts.

    Takes artifacts from the triage/architect/plan pipeline and creates
    an initial task set in your task management system (beads, JSON, JSONL).

    Examples:
        cub bootstrap <session-id>   # Initialize tasks from a session
        cub bootstrap --all          # Bootstrap all ready sessions
        cub bootstrap --help         # Show bootstrap-specific options
    """
    _delegate("bootstrap", args or [], ctx)


def sessions(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    List and manage prep sessions.

    Shows all saved planning sessions and allows you to view, resume,
    or archive them. Sessions track the state of triage/architect/plan work.

    Examples:
        cub sessions                 # List all sessions
        cub sessions --status active # List active sessions only
        cub sessions --help          # Show sessions-specific options
    """
    _delegate("sessions", args or [], ctx)


# Task & Artifact Commands


def explain_task(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Show detailed task information and context.

    Displays the complete task definition, dependencies, and related artifacts
    to understand scope and requirements before starting work.

    Examples:
        cub explain-task cub-123     # Show task details
        cub explain-task --json      # Output as JSON
        cub explain-task --help      # Show available options
    """
    _delegate("explain-task", args or [], ctx)


def artifacts(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    List and manage task output artifacts.

    Shows files generated during task execution (logs, code, reports).
    Use this to find and review work produced by previous runs.

    Examples:
        cub artifacts <task-id>      # Show artifacts for a task
        cub artifacts --all          # List all artifacts
        cub artifacts --help         # Show available options
    """
    _delegate("artifacts", args or [], ctx)


def validate(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Validate task backend state and configuration.

    Checks the integrity of your task backend (beads, JSON, or JSONL),
    detects corruption, and verifies configuration consistency.

    Examples:
        cub validate                 # Check task backend health
        cub validate --fix           # Auto-fix any issues found
        cub validate --verbose       # Show detailed validation output
        cub validate --help          # Show available options
    """
    _delegate("validate", args or [], ctx)


# Git Workflow Integration (v0.19)


def branch(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Create and bind a feature branch to an epic.

    Creates a new git branch for an epic and establishes the relationship
    for tracking and PR generation. Used to start work on epic implementation.

    Examples:
        cub branch cub-123           # Create and bind branch to epic
        cub branch cub-123 --name feature/auth-v2  # Custom branch name
        cub branch cub-123 --bind-only             # Bind existing branch
        cub branch --help            # Show available options
    """
    _delegate("branch", args or [], ctx)


def branches(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    List and manage branch-epic bindings.

    Shows all branches bound to epics, their status, and relationships.
    Use to track work across branches and clean up merged branches.

    Examples:
        cub branches                 # List all branch bindings
        cub branches --status active # Show active branches only
        cub branches --cleanup       # Remove merged branches
        cub branches --json          # Output as JSON
        cub branches --help          # Show available options
    """
    _delegate("branches", args or [], ctx)


def checkpoints(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Manage review/approval gates blocking task execution.

    Checkpoints are gates that can block tasks until approved by a human.
    Useful for requiring code review, design approval, or other gates.

    Examples:
        cub checkpoints              # List all checkpoints
        cub checkpoints --epic cub-123  # Show checkpoints for an epic
        cub checkpoints approve <checkpoint-id>  # Approve a checkpoint
        cub checkpoints --help       # Show available options
    """
    _delegate("checkpoints", args or [], ctx)


# Interview Mode (v0.16)


def interview(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Deep dive on task specifications through interactive questioning.

    Refines a task's definition by asking targeted questions about requirements,
    constraints, edge cases, and acceptance criteria. Useful before starting work.

    Examples:
        cub interview cub-123        # Interview a specific task
        cub interview --all          # Interview all open tasks
        cub interview --all --auto   # Auto-answer with AI
        cub interview --help         # Show available options
    """
    _delegate("interview", args or [], ctx)


def import_cmd(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Import tasks from external sources into your task backend.

    Loads tasks from various formats (CSV, JSON, GitHub issues) into your
    task management system so they can be tracked and executed via cub.

    Examples:
        cub import github cub-planning  # Import GitHub issues
        cub import csv tasks.csv        # Import from CSV file
        cub import --format=jira url    # Import from Jira
        cub import --help               # Show available options
    """
    _delegate("import", args or [], ctx)


def guardrails(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Display and manage institutional memory (guardrails).

    Guardrails are documented constraints, patterns, and best practices
    that guide autonomous code execution. Shown to agents before each run.

    Examples:
        cub guardrails               # Show all guardrails
        cub guardrails --add "pattern"  # Add a new guardrail
        cub guardrails --remove id   # Remove a guardrail
        cub guardrails --help        # Show available options
    """
    _delegate("guardrails", args or [], ctx)


def update(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Update project templates and skills from installed cub.

    Refreshes project templates and tool definitions to match your installed
    version of cub. Run after upgrading cub to get latest features.

    Examples:
        cub update                   # Update all templates and skills
        cub update --templates-only  # Update only templates
        cub update --skills-only     # Update only skills
        cub update --dry-run         # Preview changes
        cub update --help            # Show available options
    """
    _delegate("update", args or [], ctx)


# Utility & Maintenance
# (doctor command migrated to Python - see cub.cli.doctor)


# Task Commands (for agent use)


def close_task(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Close a completed task.

    Marks a task as done in the task backend (beads, JSON, or JSONL).
    This is typically called by autonomous agents after completing work.

    Examples:
        cub close-task cub-123       # Close a specific task
        cub close-task cub-123 -r "reason"  # Close with reason/notes
        cub close-task --help        # Show available options
    """
    _delegate("close-task", args or [], ctx)


def verify_task(ctx: typer.Context, args: list[str] | None = typer.Argument(None)) -> None:
    """
    Verify a task is closed.

    Checks that a task has been properly marked as closed and all associated
    work has been recorded. Used by agents to confirm completion state.

    Examples:
        cub verify-task cub-123      # Check task status
        cub verify-task --json       # Output result as JSON
        cub verify-task --help       # Show available options
    """
    _delegate("verify-task", args or [], ctx)
