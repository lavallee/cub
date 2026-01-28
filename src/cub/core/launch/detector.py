"""
Environment detection for launch service.

Detects whether cub is running in a terminal, harness, or nested session
by examining environment variables.
"""

from __future__ import annotations

import os

from cub.core.launch.models import EnvironmentContext, EnvironmentInfo


def detect_environment() -> EnvironmentInfo:
    """
    Detect the current execution environment.

    Checks environment variables to determine if we're in a terminal,
    harness session, or nested cub session.

    Returns:
        EnvironmentInfo describing the detected environment

    Environment Variables Checked:
        - CUB_SESSION_ACTIVE: Set when cub launches a harness
        - CUB_SESSION_ID: Session ID for the active cub session
        - CLAUDE_CODE: Set when running inside Claude Code
        - CLAUDE_PROJECT_DIR: Project directory when in Claude Code

    Examples:
        >>> # In a terminal
        >>> env = detect_environment()
        >>> assert env.context == EnvironmentContext.TERMINAL
        >>> assert not env.in_harness

        >>> # Inside Claude Code
        >>> os.environ["CLAUDE_CODE"] = "1"
        >>> env = detect_environment()
        >>> assert env.context == EnvironmentContext.HARNESS
        >>> assert env.harness == "claude"

        >>> # Nested (cub run already launched a harness)
        >>> os.environ["CUB_SESSION_ACTIVE"] = "1"
        >>> os.environ["CUB_SESSION_ID"] = "session-123"
        >>> env = detect_environment()
        >>> assert env.is_nested
        >>> assert env.session_id == "session-123"
    """
    # Check for nesting (highest priority)
    # If CUB_SESSION_ACTIVE is set, cub already launched a harness
    # and we should not nest another one
    if os.environ.get("CUB_SESSION_ACTIVE") == "1":
        return EnvironmentInfo(
            context=EnvironmentContext.NESTED,
            session_id=os.environ.get("CUB_SESSION_ID"),
            project_dir=os.environ.get("CLAUDE_PROJECT_DIR"),
        )

    # Check for Claude Code harness
    # CLAUDE_CODE=1 is set when running inside Claude Code
    if os.environ.get("CLAUDE_CODE") == "1":
        return EnvironmentInfo(
            context=EnvironmentContext.HARNESS,
            harness="claude",
            project_dir=os.environ.get("CLAUDE_PROJECT_DIR"),
        )

    # Default: running in a terminal
    return EnvironmentInfo(context=EnvironmentContext.TERMINAL)


__all__ = ["detect_environment"]
