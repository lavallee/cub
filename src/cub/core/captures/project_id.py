"""
Project ID inference and storage for capture organization.

The project ID is used to organize global captures by project. It is stored
in .cub/config.json and auto-inferred from the git remote origin if not set.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any


def get_project_id(project_dir: Path | None = None) -> str:
    """
    Get or infer the project identifier.

    Resolution order:
    1. Check .cub/config.json for explicit project_id
    2. Infer from git remote origin
    3. Fall back to directory basename

    Once inferred, the ID is saved to .cub/config.json for consistency.

    Args:
        project_dir: Project root directory (defaults to current directory)

    Returns:
        Project identifier string (e.g., "cub", "my-project")
    """
    if project_dir is None:
        project_dir = Path.cwd()

    # 1. Check .cub/config.json
    config = _load_project_config(project_dir)
    if config and config.get("project_id"):
        return str(config["project_id"])

    # 2. Infer from git remote
    project_id = _infer_from_git_remote(project_dir)

    if not project_id:
        # 3. Fall back to directory name
        project_id = project_dir.name

    # Normalize the project ID
    project_id = _normalize_project_id(project_id)

    # Save for consistency
    _save_project_id(project_dir, project_id)

    return project_id


def _load_project_config(project_dir: Path) -> dict[str, Any] | None:
    """
    Load project configuration from .cub/config.json.

    Args:
        project_dir: Project root directory

    Returns:
        Configuration dict or None if file doesn't exist
    """
    config_file = project_dir / ".cub" / "config.json"
    if not config_file.exists():
        return None

    try:
        with open(config_file, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data
    except (json.JSONDecodeError, OSError):
        return None


def _save_project_id(project_dir: Path, project_id: str) -> None:
    """
    Save project ID to .cub/config.json.

    Creates the .cub directory if it doesn't exist. Preserves existing
    configuration values.

    Args:
        project_dir: Project root directory
        project_id: Project identifier to save
    """
    config_dir = project_dir / ".cub"
    config_file = config_dir / "config.json"

    # Load existing config or create new
    config = _load_project_config(project_dir) or {}
    config["project_id"] = project_id

    # Ensure directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    # Write config
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
    except OSError:
        # Don't fail if we can't write config
        pass


def _infer_from_git_remote(project_dir: Path) -> str | None:
    """
    Infer project ID from git remote origin.

    Handles formats:
    - git@github.com:user/project.git -> project
    - https://github.com/user/project.git -> project
    - https://github.com/user/project -> project

    Args:
        project_dir: Project root directory

    Returns:
        Project name from remote URL, or None if not available
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None

        remote_url = result.stdout.strip()
        return _extract_repo_name(remote_url)
    except (OSError, FileNotFoundError):
        return None


def _extract_repo_name(remote_url: str) -> str | None:
    """
    Extract repository name from a git remote URL.

    Args:
        remote_url: Git remote URL (SSH or HTTPS)

    Returns:
        Repository name or None if parsing fails
    """
    if not remote_url:
        return None

    # SSH format: git@github.com:user/project.git
    ssh_match = re.match(r"git@[^:]+:(?:[^/]+/)?([^/]+?)(?:\.git)?$", remote_url)
    if ssh_match:
        return ssh_match.group(1)

    # HTTPS format: https://github.com/user/project.git
    https_match = re.match(r"https?://[^/]+/(?:[^/]+/)?([^/]+?)(?:\.git)?/?$", remote_url)
    if https_match:
        return https_match.group(1)

    return None


def _normalize_project_id(project_id: str) -> str:
    """
    Normalize a project ID for filesystem use.

    - Convert to lowercase
    - Replace spaces and special characters with hyphens
    - Remove leading/trailing hyphens

    Args:
        project_id: Raw project identifier

    Returns:
        Normalized project identifier
    """
    # Convert to lowercase
    normalized = project_id.lower()

    # Replace non-alphanumeric characters (except hyphens) with hyphens
    normalized = re.sub(r"[^a-z0-9-]", "-", normalized)

    # Collapse multiple hyphens
    normalized = re.sub(r"-+", "-", normalized)

    # Remove leading/trailing hyphens
    normalized = normalized.strip("-")

    return normalized or "default"
