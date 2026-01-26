"""
Standardized error handling and exit codes for Cub CLI.

This module provides consistent error messaging with actionable guidance
and standardized exit codes across all CLI commands.
"""

from enum import IntEnum

from rich.console import Console

console = Console()


class ExitCode(IntEnum):
    """Standard exit codes for Cub CLI operations."""

    SUCCESS = 0
    """Operation completed successfully."""

    GENERAL_ERROR = 1
    """Generic error or user-triggered error."""

    USER_ERROR = 2
    """User configuration or input error (actionable by user)."""

    SIGINT = 130
    """Terminated by SIGINT (Ctrl+C) - Unix standard."""


def print_error(
    problem: str,
    *,
    reason: str | None = None,
    solution: str | None = None,
    doc_url: str | None = None,
) -> None:
    """
    Print a standardized error message with actionable guidance.

    Args:
        problem: Brief description of what went wrong
        reason: Optional explanation of why it happened
        solution: Optional command or action to fix it
        doc_url: Optional documentation URL for more help

    Example:
        >>> print_error(
        ...     "No harness available",
        ...     reason="Cub requires an AI harness to execute tasks",
        ...     solution="pip install anthropic-claude",
        ...     doc_url="https://docs.anthropic.com/claude-code"
        ... )
    """
    console.print(f"[red]Error:[/red] {problem}")

    if reason:
        console.print(f"[dim]{reason}[/dim]")

    if solution:
        console.print(f"[cyan]→ Try:[/cyan] {solution}")

    if doc_url:
        console.print(f"[dim]Docs: {doc_url}[/dim]")


def print_harness_not_found_error() -> None:
    """Print error when no harness is available."""
    print_error(
        "No AI harness available",
        reason="Cub requires Claude, Codex, Gemini, or another supported harness to execute tasks",
        solution="pip install anthropic-claude  # or another harness",
        doc_url="https://docs.anthropic.com/claude-code",
    )


def print_harness_not_installed_error(harness_name: str) -> None:
    """Print error when a specific harness is not installed or available."""
    harness_install = {
        "claude": "pip install anthropic-claude",
        "codex": "pip install openai",
        "gemini": "pip install google-generativeai",
        "opencode": "pip install opencode-ai",
    }

    install_cmd = harness_install.get(harness_name, f"Check installation for '{harness_name}'")

    print_error(
        f"Harness '{harness_name}' is not available",
        reason="The harness may not be installed or configured correctly",
        solution=install_cmd,
    )


def print_not_git_repo_error() -> None:
    """Print error when not in a git repository."""
    print_error(
        "Not a git repository",
        reason="Cub requires git for version control and task tracking",
        solution="git init  # or cd to your project root",
    )


def print_not_project_root_error() -> None:
    """Print error when not in a Cub project directory."""
    print_error(
        "Not in a Cub project directory",
        reason="Could not find .cub/, .beads/, .cub.json, or .git/",
        solution="cub init  # or cd to your project root",
    )


def print_no_tasks_found_error(criteria: str | None = None) -> None:
    """Print error when no tasks match the search criteria."""
    reason_msg = (
        f"No tasks match the criteria: {criteria}" if criteria else "The task backend is empty"
    )

    print_error(
        "No tasks found",
        reason=reason_msg,
        solution="cub task create 'Your task title'  # or cub task list --all",
    )


def print_task_not_found_error(task_id: str) -> None:
    """Print error when a specific task is not found."""
    print_error(
        f"Task not found: {task_id}",
        reason="The task ID may be incorrect or the task may have been deleted",
        solution="cub task list  # to see available tasks",
    )


def print_sync_not_initialized_error() -> None:
    """Print error when sync branch is not initialized."""
    print_error(
        "Sync branch not initialized",
        reason="Task persistence across git clones requires the cub-sync branch",
        solution="cub sync init",
    )


def print_backend_not_initialized_error() -> None:
    """Print error when task backend is not initialized."""
    print_error(
        "Task backend not initialized",
        reason="No task storage found (.cub/tasks.jsonl or .beads/)",
        solution="cub init  # to set up the project",
    )


def print_dirty_working_tree_error(change_count: int) -> None:
    """Print error when the working tree has uncommitted changes."""
    print_error(
        f"Uncommitted changes detected ({change_count} files)",
        reason="Running on a dirty working tree may cause unexpected behavior",
        solution="git commit -am 'WIP'  # or git stash",
    )


def print_incompatible_flags_error(flag1: str, flag2: str, reason: str | None = None) -> None:
    """Print error when incompatible CLI flags are used together."""
    problem = f"Cannot use {flag1} with {flag2}"

    if reason:
        print_error(problem, reason=reason)
    else:
        print_error(problem, solution=f"Remove one of the flags: {flag1} or {flag2}")


def print_missing_dependency_error(
    tool: str, install_url: str | None = None, install_cmd: str | None = None
) -> None:
    """Print error when a required tool is not installed."""
    print_error(
        f"Required tool not found: {tool}",
        reason=f"The '{tool}' command is required but not in PATH",
        solution=install_cmd,
        doc_url=install_url,
    )


def print_main_branch_error(branch: str) -> None:
    """Print error when trying to run on main/master without permission."""
    print_error(
        f"Cannot run on '{branch}' branch",
        reason="Running directly on main/master can create messy history",
        solution="Remove --use-current-branch (auto-creates feature branch)\n"
        "       [cyan]→ Or:[/cyan] Add --main-ok to explicitly allow it",
    )


def print_invalid_option_error(option: str, valid_options: list[str]) -> None:
    """Print error when an invalid option value is provided."""
    valid_str = ", ".join(valid_options)
    print_error(
        f"Invalid option: {option}",
        reason=f"Valid options are: {valid_str}",
        solution=f"Use one of: {valid_str}",
    )


__all__ = [
    "ExitCode",
    "print_error",
    "print_harness_not_found_error",
    "print_harness_not_installed_error",
    "print_not_git_repo_error",
    "print_not_project_root_error",
    "print_no_tasks_found_error",
    "print_task_not_found_error",
    "print_sync_not_initialized_error",
    "print_backend_not_initialized_error",
    "print_dirty_working_tree_error",
    "print_incompatible_flags_error",
    "print_missing_dependency_error",
    "print_main_branch_error",
    "print_invalid_option_error",
]
