"""
Bash delegation module for invoking legacy bash cub commands.

This module enables the Python cub CLI to delegate to the bash version
for commands not yet ported to Python. It handles:
- Locating the bash cub script (bundled or system)
- Delegating commands with proper argument passing
- Exit code and output passthrough
- Debug flag propagation via CUB_DEBUG environment variable
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from rich.console import Console

console = Console()


class BashCubNotFoundError(RuntimeError):
    """Raised when bash cub script cannot be located."""

    pass


def find_bash_cub() -> Path:
    """
    Locate the bash cub script.

    Search order:
    1. CUB_BASH_PATH environment variable (explicit override)
    2. Bundled with Python package (src/cub/bash/cub)
    3. Project root (for development - editable install)
    4. System PATH (installed version)

    Returns:
        Path to bash cub script

    Raises:
        BashCubNotFoundError: If bash cub script cannot be found
    """
    # 1. Check explicit override
    if bash_path := os.environ.get("CUB_BASH_PATH"):
        path = Path(bash_path)
        if path.exists() and path.is_file():
            return path
        raise BashCubNotFoundError(f"CUB_BASH_PATH points to non-existent file: {bash_path}")

    # 2. Check bundled location (installed with package)
    # When installed via pip, bash files are at cub/bash/cub
    package_bundled_path = Path(__file__).parent.parent / "bash" / "cub"
    if package_bundled_path.exists() and package_bundled_path.is_file():
        return package_bundled_path

    # 3. Check project root (for editable install / development)
    # The bash script should be at the project root, so we need to go up from src/cub/core
    package_dir = Path(__file__).parent.parent.parent.parent
    dev_path = package_dir / "cub"
    if dev_path.exists() and dev_path.is_file():
        return dev_path

    # 4. Check system PATH
    if system_path := shutil.which("cub"):
        # Make sure it's the bash version, not this Python script
        path = Path(system_path).resolve()
        # Check if it's a bash script (starts with shebang)
        try:
            with open(path, "rb") as f:
                first_line = f.readline()
                if first_line.startswith(b"#!/usr/bin/env bash") or first_line.startswith(
                    b"#!/bin/bash"
                ):
                    return path
        except (OSError, UnicodeDecodeError):
            pass

    raise BashCubNotFoundError(
        "Could not locate bash cub script. Install it or set CUB_BASH_PATH environment variable."
    )


def is_bash_command(command: str) -> bool:
    """
    Check if a command should be delegated to bash.

    Commands that are NOT yet ported to Python should delegate.
    Commands that ARE ported should NOT delegate.

    Args:
        command: The subcommand name (e.g., 'prep', 'triage')

    Returns:
        True if command should delegate to bash
    """
    # Commands that should delegate to bash
    bash_commands = {
        "prep",
        "triage",
        "architect",
        "plan",
        "bootstrap",
        "sessions",
        "validate",
        "migrate-layout",
        "interview",
        "import",
        "branch",
        "branches",
        "checkpoints",
        "pr",
        "guardrails",
        "explain",
        "artifacts",
        "agent-close",
        "agent-verify",
        "doctor",
        "upgrade",
    }

    return command in bash_commands


def delegate_to_bash(command: str, args: list[str], debug: bool = False) -> NoReturn:
    """
    Delegate to bash cub script and exit with its exit code.

    This function does NOT return - it exec's the bash script or exits
    with the bash script's exit code.

    Args:
        command: The subcommand to delegate (e.g., 'prep')
        args: Additional arguments to pass
        debug: Enable debug mode (sets CUB_DEBUG=true for bash script)

    Raises:
        BashCubNotFoundError: If bash cub script cannot be located
        SystemExit: Always exits with bash script's exit code
    """
    try:
        bash_cub = find_bash_cub()
    except BashCubNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]The bash version of cub is required for this command.[/dim]")
        console.print("[dim]Install it or set CUB_BASH_PATH to point to the bash script.[/dim]")
        sys.exit(1)

    # Build command: bash_cub <command> <args...>
    cmd = [str(bash_cub), command] + args

    # Pass through environment variables
    env = os.environ.copy()

    # Set debug flag from parameter or sys.argv fallback
    # Parameter takes precedence (from typer context)
    # sys.argv fallback catches cases where --debug was passed but context not available
    if debug or "--debug" in sys.argv or "-d" in sys.argv:
        env["CUB_DEBUG"] = "true"
        console.print(f"[dim]Delegating to bash: {bash_cub}[/dim]")
        console.print(f"[dim]Command: {command} {' '.join(args)}[/dim]")

    # Execute bash cub with exec semantics
    # This replaces the current process, so we never return
    try:
        result = subprocess.run(
            cmd,
            env=env,
            check=False,  # Don't raise on non-zero exit
        )
        sys.exit(result.returncode)
    except FileNotFoundError:
        console.print(f"[red]Error: Bash cub script not executable: {bash_cub}[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        # Pass through interrupt
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Error executing bash cub: {e}[/red]")
        sys.exit(1)
