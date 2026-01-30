"""
Utilities for cub self-invocation in subprocesses.

When dev_mode is active, cub should use `uv run` to ensure the local
development version is used instead of a globally installed copy.

Usage:
    from cub.core.invoke import cub_command, cub_python_command

    # For `cub <subcommand>` invocations
    cmd = cub_command() + ["run", "--once"]

    # For `python -m cub` invocations
    cmd = cub_python_command() + ["run", "--once"]
"""

from __future__ import annotations

import os
import sys


def is_dev_mode() -> bool:
    """Check whether cub is running in development mode.

    Checks CUB_DEV_MODE env var first (fast path), then falls back
    to loading config from disk.

    Returns:
        True if dev_mode is active.
    """
    env_val = os.environ.get("CUB_DEV_MODE")
    if env_val is not None:
        return env_val.lower() not in ("false", "0", "")

    try:
        from cub.core.config import load_config

        return load_config().dev_mode
    except Exception:
        return False


def cub_command() -> list[str]:
    """Return the command prefix for invoking cub as a CLI.

    Returns ``["uv", "run", "cub"]`` in dev mode, ``["cub"]`` otherwise.
    """
    if is_dev_mode():
        return ["uv", "run", "cub"]
    return ["cub"]


def cub_python_command() -> list[str]:
    """Return the command prefix for invoking cub as a Python module.

    Returns ``["uv", "run", "python", "-m", "cub"]`` in dev mode,
    ``[sys.executable, "-m", "cub"]`` otherwise.
    """
    if is_dev_mode():
        return ["uv", "run", "python", "-m", "cub"]
    return [sys.executable, "-m", "cub"]
