"""
Data models for launch service.

Defines typed inputs and outputs for environment detection and harness launching.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EnvironmentContext(str, Enum):
    """Execution environment context."""

    TERMINAL = "terminal"  # Regular terminal, no harness detected
    HARNESS = "harness"  # Inside a harness session
    NESTED = "nested"  # Inside a cub-managed harness (would nest)


@dataclass(frozen=True)
class EnvironmentInfo:
    """
    Environment detection result.

    Captures where cub is being executed and provides context
    for deciding whether to launch a harness or show inline status.

    Attributes:
        context: The execution environment (terminal, harness, nested)
        harness: Detected harness name if in harness context (e.g., "claude")
        session_id: Active session ID if in nested context
        project_dir: Claude Code project directory if available
    """

    context: EnvironmentContext
    harness: str | None = None
    session_id: str | None = None
    project_dir: str | None = None

    @property
    def is_nested(self) -> bool:
        """Whether we're in a nested cub session (should not launch)."""
        return self.context == EnvironmentContext.NESTED

    @property
    def in_harness(self) -> bool:
        """Whether we're already in a harness session."""
        return self.context in (EnvironmentContext.HARNESS, EnvironmentContext.NESTED)


@dataclass(frozen=True)
class LaunchConfig:
    """
    Configuration for harness launch.

    Specifies how to launch the harness, including the binary to use,
    flags to pass, and session management options.

    Attributes:
        harness_name: Name of harness to launch (e.g., "claude-code")
        binary_path: Full path to harness binary
        working_dir: Directory to launch from
        resume: Resume previous session if available
        continue_session: Continue from previous session (flag-specific behavior)
        session_id: Explicit session ID to resume
        project_context: Additional context to inject (suggestions, status)
        auto_approve: Whether to skip permission prompts
        debug: Enable debug mode
    """

    harness_name: str
    binary_path: str
    working_dir: str
    resume: bool = False
    continue_session: bool = False
    session_id: str | None = None
    project_context: str | None = None
    auto_approve: bool = False
    debug: bool = False


__all__ = [
    "EnvironmentContext",
    "EnvironmentInfo",
    "LaunchConfig",
]
