"""
Handoff utilities for Claude Code slash command invocation.

This module provides functionality to automatically invoke `/cub:` slash commands
within Claude Code after plan stage completion, enabling seamless workflow continuation.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import Enum


class HandoffResult(Enum):
    """Result of a handoff attempt."""

    SUCCESS = "success"
    CLAUDE_NOT_FOUND = "claude_not_found"
    EXECUTION_FAILED = "execution_failed"
    NOT_IN_CLAUDE_CODE = "not_in_claude_code"


@dataclass
class HandoffOutcome:
    """Outcome of a handoff attempt."""

    result: HandoffResult
    message: str
    exit_code: int | None = None


# Commands that have corresponding /cub: slash command skills
SLASH_COMMAND_MAP: dict[str, str] = {
    "plan architect": "architect",
    "plan itemize": "itemize",
    "plan orient": "orient",
}


def is_claude_code_environment() -> bool:
    """
    Detect if we're running inside Claude Code.

    Returns:
        True if running inside Claude Code, False otherwise.
    """
    # Claude Code sets specific environment variables
    # CLAUDE_CODE is set when running inside Claude Code
    return os.environ.get("CLAUDE_CODE") == "1"


def attempt_handoff(
    command: str,
    args: str | None = None,
    *,
    wait: bool = False,
) -> HandoffOutcome:
    """
    Attempt to invoke a /cub: slash command in Claude Code.

    This function tries to invoke the specified command using the `claude` CLI.
    If successful, it signals Claude Code to execute the slash command.

    Args:
        command: The slash command skill name (e.g., "architect", "itemize").
        args: Optional arguments to pass to the command.
        wait: If True, wait for the command to complete.

    Returns:
        HandoffOutcome with the result and a message.

    Examples:
        >>> attempt_handoff("architect", "my-plan")
        HandoffOutcome(result=HandoffResult.SUCCESS, message="Handoff initiated")
    """
    # Build the slash command
    skill_prompt = f"/cub:{command}"
    if args:
        skill_prompt += f" {args}"

    try:
        # Try to invoke claude with the slash command
        result = subprocess.run(
            ["claude", skill_prompt],
            check=False,
            capture_output=not wait,
            timeout=5 if not wait else None,  # Short timeout for non-blocking check
        )

        if result.returncode == 0:
            return HandoffOutcome(
                result=HandoffResult.SUCCESS,
                message=f"Handoff to `/cub:{command}` initiated",
                exit_code=result.returncode,
            )
        else:
            return HandoffOutcome(
                result=HandoffResult.EXECUTION_FAILED,
                message=f"Claude CLI returned exit code {result.returncode}",
                exit_code=result.returncode,
            )

    except FileNotFoundError:
        return HandoffOutcome(
            result=HandoffResult.CLAUDE_NOT_FOUND,
            message="Claude CLI not found. Install Claude Code from https://claude.ai/download",
        )
    except subprocess.TimeoutExpired:
        # Timeout is expected for non-blocking calls - treat as success
        return HandoffOutcome(
            result=HandoffResult.SUCCESS,
            message=f"Handoff to `/cub:{command}` initiated",
            exit_code=0,
        )
    except Exception as e:
        return HandoffOutcome(
            result=HandoffResult.EXECUTION_FAILED,
            message=f"Handoff failed: {e}",
        )


def format_slash_command(skill: str, args: str | None = None) -> str:
    """
    Format a slash command for display.

    Args:
        skill: The skill name (e.g., "architect", "itemize").
        args: Optional arguments.

    Returns:
        Formatted slash command string with backticks.
    """
    if args:
        return f"`/cub:{skill} {args}`"
    return f"`/cub:{skill}`"


def format_shell_command(command: str, args: str | None = None) -> str:
    """
    Format a shell command for display (fallback).

    Args:
        command: The command (e.g., "plan architect", "stage").
        args: Optional arguments.

    Returns:
        Formatted shell command string with backticks.
    """
    base = f"cub {command}"
    if args:
        return f"`{base} {args}`"
    return f"`{base}`"


def get_next_step_message(
    command: str,
    args: str | None = None,
    *,
    prefer_slash: bool = True,
) -> str:
    """
    Get the appropriate "next step" message based on environment.

    Args:
        command: The command to run (e.g., "plan architect", "stage").
        args: Optional arguments for the command.
        prefer_slash: If True, prefer slash command syntax when available.

    Returns:
        Formatted next step message.
    """
    # Check if this command has a slash command equivalent
    skill = SLASH_COMMAND_MAP.get(command)

    if prefer_slash and skill:
        slash_cmd = format_slash_command(skill, args)
        return f"Run: {slash_cmd}"
    else:
        shell_cmd = format_shell_command(command, args)
        return f"Run: {shell_cmd}"


def try_handoff_or_message(
    command: str,
    args: str | None = None,
) -> tuple[bool, str]:
    """
    Try to perform a handoff, returning success status and message.

    This is the main entry point for the handoff system. It provides
    the appropriate next step message based on whether the command
    has a slash command equivalent.

    Args:
        command: The command to run (e.g., "plan architect", "stage").
        args: Optional arguments for the command.

    Returns:
        A tuple of (success, message) where:
        - success: True if handoff was initiated, False if fallback needed
        - message: User-facing message about the handoff or next step

    Note:
        Automatic handoff (invoking the slash command via subprocess) launches
        a new Claude session rather than continuing the current one, so it's
        not suitable for seamless handoff. Instead, we provide clear instructions
        using slash command syntax when available.

    Examples:
        >>> try_handoff_or_message("plan architect", "my-plan")
        (False, "[bold]Next step:[/bold] Run: `/cub:architect my-plan`")

        >>> try_handoff_or_message("stage", "my-plan")
        (False, "[bold]Next step:[/bold] Run: `cub stage my-plan`")
    """
    # Check if this command has a slash command equivalent
    skill = SLASH_COMMAND_MAP.get(command)

    if skill:
        # Use slash command syntax for plan stages
        slash_cmd = format_slash_command(skill, args)
        return (False, f"[bold]Next step:[/bold] Run: {slash_cmd}")
    else:
        # Use shell command syntax for commands without slash equivalents
        shell_cmd = format_shell_command(command, args)
        return (False, f"[bold]Next step:[/bold] Run: {shell_cmd}")
