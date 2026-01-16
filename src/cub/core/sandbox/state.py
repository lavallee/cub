"""
Sandbox state tracking.

This module manages the current sandbox state, storing the active
sandbox ID so that CLI commands can operate on it.
"""

import json
from pathlib import Path

from pydantic import BaseModel


class ActiveSandbox(BaseModel):
    """
    Active sandbox state.

    Tracks the currently running or kept sandbox so that CLI
    commands know which sandbox to operate on.
    """

    sandbox_id: str
    provider: str
    project_dir: str


def get_state_file(project_dir: Path) -> Path:
    """
    Get path to sandbox state file.

    Args:
        project_dir: Project root directory

    Returns:
        Path to .cub/sandbox.json
    """
    return project_dir / ".cub" / "sandbox.json"


def save_sandbox_state(
    project_dir: Path,
    sandbox_id: str,
    provider: str,
) -> None:
    """
    Save active sandbox state.

    Args:
        project_dir: Project root directory
        sandbox_id: Sandbox identifier
        provider: Provider name (docker, etc.)
    """
    state = ActiveSandbox(
        sandbox_id=sandbox_id,
        provider=provider,
        project_dir=str(project_dir.resolve()),
    )

    state_file = get_state_file(project_dir)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    with state_file.open("w") as f:
        json.dump(state.model_dump(), f, indent=2)


def load_sandbox_state(project_dir: Path) -> ActiveSandbox | None:
    """
    Load active sandbox state.

    Args:
        project_dir: Project root directory

    Returns:
        ActiveSandbox if exists, None otherwise
    """
    state_file = get_state_file(project_dir)

    if not state_file.exists():
        return None

    try:
        with state_file.open() as f:
            data = json.load(f)
        return ActiveSandbox.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        # Corrupted state file
        return None


def clear_sandbox_state(project_dir: Path) -> None:
    """
    Clear active sandbox state.

    Args:
        project_dir: Project root directory
    """
    state_file = get_state_file(project_dir)
    if state_file.exists():
        state_file.unlink()
