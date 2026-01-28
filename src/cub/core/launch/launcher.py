"""
Harness launcher for launch service.

Handles harness binary resolution, flag assembly, environment setup,
and exec-based launch.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from cub.core.launch.models import LaunchConfig


class LauncherError(Exception):
    """Base exception for launcher errors."""


class HarnessBinaryNotFoundError(LauncherError):
    """Harness binary not found in PATH."""

    def __init__(self, harness_name: str, binary_path: str) -> None:
        self.harness_name = harness_name
        self.binary_path = binary_path
        super().__init__(
            f"Harness binary '{binary_path}' for '{harness_name}' not found in PATH"
        )


def resolve_harness_binary(harness_name: str) -> str:
    """
    Resolve the binary path for a harness.

    Args:
        harness_name: Name of the harness (e.g., "claude-code")

    Returns:
        Full path to the harness binary

    Raises:
        HarnessBinaryNotFoundError: If binary not found in PATH

    Examples:
        >>> # Claude Code
        >>> path = resolve_harness_binary("claude-code")
        >>> assert path.endswith("claude")

        >>> # Not found
        >>> resolve_harness_binary("nonexistent")
        Traceback (most recent call last):
        ...
        HarnessBinaryNotFoundError: ...
    """
    # Map harness names to binary names
    binary_map = {
        "claude-code": "claude",
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
    }

    binary_name = binary_map.get(harness_name, harness_name)
    binary_path = shutil.which(binary_name)

    if not binary_path:
        raise HarnessBinaryNotFoundError(harness_name, binary_name)

    return binary_path


def build_launch_args(config: LaunchConfig) -> list[str]:
    """
    Build command-line arguments for harness launch.

    Assembles flags for resume, continue, debug, etc. based on LaunchConfig.

    Args:
        config: Launch configuration

    Returns:
        List of command-line arguments

    Examples:
        >>> config = LaunchConfig(
        ...     harness_name="claude-code",
        ...     binary_path="/usr/bin/claude",
        ...     working_dir="/project",
        ...     resume=True,
        ...     debug=True
        ... )
        >>> args = build_launch_args(config)
        >>> assert "--resume" in args
        >>> assert "--debug" in args
    """
    args: list[str] = []

    # Session management flags
    if config.resume:
        args.append("--resume")
    if config.continue_session:
        args.append("--continue")

    # Debug flag
    if config.debug:
        args.append("--debug")

    # Auto-approve flag (skip permissions)
    if config.auto_approve:
        # This is harness-specific, Claude Code uses --dangerously-skip-permissions
        if config.harness_name in ("claude-code", "claude"):
            args.append("--dangerously-skip-permissions")

    return args


def build_launch_env(config: LaunchConfig) -> dict[str, str]:
    """
    Build environment variables for harness launch.

    Sets CUB_SESSION_ACTIVE and CUB_SESSION_ID to prevent nesting
    and enable detection in nested contexts.

    Args:
        config: Launch configuration

    Returns:
        Dictionary of environment variables to set

    Examples:
        >>> config = LaunchConfig(
        ...     harness_name="claude-code",
        ...     binary_path="/usr/bin/claude",
        ...     working_dir="/project"
        ... )
        >>> env = build_launch_env(config)
        >>> assert env["CUB_SESSION_ACTIVE"] == "1"
        >>> assert "CUB_SESSION_ID" in env
    """
    env = os.environ.copy()

    # Set session tracking variables
    env["CUB_SESSION_ACTIVE"] = "1"

    # Use provided session ID or generate new one
    session_id = config.session_id or str(uuid.uuid4())
    env["CUB_SESSION_ID"] = session_id

    return env


def launch_harness(config: LaunchConfig) -> None:
    """
    Launch harness with exec (replaces current process).

    This function does NOT return on success - it replaces the current
    process with the harness process via os.execve().

    Args:
        config: Launch configuration

    Raises:
        HarnessBinaryNotFoundError: If harness binary not found
        OSError: If exec fails

    Examples:
        >>> # This will replace the current process
        >>> config = LaunchConfig(
        ...     harness_name="claude-code",
        ...     binary_path="/usr/bin/claude",
        ...     working_dir="/project"
        ... )
        >>> launch_harness(config)
        # Process replaced, does not return
    """
    # Resolve binary path if not provided
    binary_path = config.binary_path
    if not Path(binary_path).is_absolute() or not Path(binary_path).exists():
        binary_path = resolve_harness_binary(config.harness_name)

    # Build command args
    args = [binary_path] + build_launch_args(config)

    # Build environment
    env = build_launch_env(config)

    # Change to working directory
    os.chdir(config.working_dir)

    # Exec (replaces process, does not return)
    os.execve(binary_path, args, env)


__all__ = [
    "LauncherError",
    "HarnessBinaryNotFoundError",
    "resolve_harness_binary",
    "build_launch_args",
    "build_launch_env",
    "launch_harness",
]
