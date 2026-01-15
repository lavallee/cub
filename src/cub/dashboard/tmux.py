"""
tmux integration for launching cub with live dashboard.

Provides functions to launch cub run in a tmux session with a split pane
showing a live dashboard. Handles tmux detection, session creation, and
graceful fallback when tmux is not available.
"""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from rich.console import Console

console = Console()


def is_tmux_available() -> bool:
    """
    Check if tmux is installed and available.

    Returns:
        True if tmux command exists, False otherwise
    """
    return shutil.which("tmux") is not None


def is_inside_tmux() -> bool:
    """
    Check if we're currently running inside a tmux session.

    Returns:
        True if TMUX environment variable is set
    """
    return "TMUX" in os.environ


def launch_with_dashboard(
    run_args: list[str],
    session_name: str,
    pane_size: int = 35,
) -> NoReturn:
    """
    Launch cub run in tmux with a live dashboard in split pane.

    Creates a new tmux session with two panes:
    - Left pane (65%): Main cub run execution
    - Right pane (35%): Live dashboard monitor

    Args:
        run_args: Arguments to pass to cub run (e.g., ["--once", "--harness", "claude"])
        session_name: Name for the tmux session (should match run_id)
        pane_size: Width percentage for dashboard pane (default: 35)

    Raises:
        SystemExit: Always exits after launching tmux session

    Example:
        >>> launch_with_dashboard(
        ...     run_args=["--once", "--harness", "claude"],
        ...     session_name="cub-20260115-123456",
        ...     pane_size=35
        ... )
    """
    # Validate tmux availability
    if not is_tmux_available():
        console.print(
            "[red]Error: tmux is not installed or not in PATH[/red]\n"
            "Install tmux to use --monitor flag:\n"
            "  macOS:   brew install tmux\n"
            "  Ubuntu:  sudo apt-get install tmux\n"
            "  Fedora:  sudo dnf install tmux"
        )
        sys.exit(1)

    if is_inside_tmux():
        console.print(
            "[yellow]Warning: Already inside a tmux session[/yellow]\n"
            "The --monitor flag creates a new tmux session with split panes.\n"
            "To use --monitor, either:\n"
            "  1. Exit your current tmux session (detach with Ctrl+b d)\n"
            "  2. Run cub without --monitor flag"
        )
        sys.exit(1)

    # Get the python executable
    python_exec = sys.executable

    # Build the cub run command (without --monitor)
    # Filter out --monitor from run_args
    filtered_args = [arg for arg in run_args if arg != "--monitor"]
    run_cmd_parts = [python_exec, "-m", "cub", "run"] + filtered_args
    run_cmd = shlex.join(run_cmd_parts)

    # Build the cub monitor command
    # The monitor command will read from the status file for this session
    monitor_cmd_parts = [python_exec, "-m", "cub", "monitor", session_name]
    monitor_cmd = shlex.join(monitor_cmd_parts)

    # Get project directory for logging
    project_dir = Path.cwd()
    status_dir = project_dir / ".cub" / "runs" / session_name

    console.print(f"[bold]Launching tmux session: {session_name}[/bold]")
    console.print(f"[dim]Status directory: {status_dir}[/dim]")
    console.print()
    console.print("To detach: Ctrl+b d")
    console.print("To exit: Ctrl+c in main pane")
    console.print()

    try:
        # Create new tmux session with main pane
        # -d: start detached
        # -s: session name
        # -n: window name
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session_name,
                "-n",
                "main",
                run_cmd,
            ],
            check=True,
        )

        # Split window horizontally for dashboard
        # -h: horizontal split (side by side)
        # -p: pane size percentage
        # -t: target session
        subprocess.run(
            [
                "tmux",
                "split-window",
                "-h",
                "-p",
                str(pane_size),
                "-t",
                f"{session_name}:main",
                monitor_cmd,
            ],
            check=True,
        )

        # Set main pane as active (left pane)
        subprocess.run(
            ["tmux", "select-pane", "-t", f"{session_name}:main.0"],
            check=True,
        )

        # Attach to the session
        # This replaces the current process
        os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to create tmux session: {e}[/red]")
        sys.exit(1)
    except FileNotFoundError:
        # This shouldn't happen since we checked is_tmux_available()
        console.print("[red]Error: tmux command not found[/red]")
        sys.exit(1)


def get_dashboard_pane_size(config_size: int | None = None) -> int:
    """
    Get the dashboard pane size, validating and applying defaults.

    Args:
        config_size: Configured pane size from config file

    Returns:
        Validated pane size (percentage between 20 and 50)
    """
    default_size = 35

    if config_size is None:
        return default_size

    # Validate range
    if config_size < 20 or config_size > 50:
        console.print(
            f"[yellow]Warning: dashboard.pane_size={config_size} out of range (20-50), "
            f"using default {default_size}[/yellow]"
        )
        return default_size

    return config_size
