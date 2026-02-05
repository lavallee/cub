"""
Hook discovery for lifecycle hooks.

This module discovers executable hook scripts in project and global hook
directories. It's part of the new lifecycle hooks system that supports:
- pre-session: Before harness session starts
- end-of-task: After a task completes
- end-of-epic: After all tasks in an epic complete
- end-of-plan: After all epics in a plan complete

Hook scripts are discovered in:
- Project: {project_dir}/.cub/hooks/{hook_name}/
- Global: ~/.config/cub/hooks/{hook_name}/

Discovery rules:
- Only executable files are returned
- Scripts are sorted by filename (for execution order)
- Global hooks run before project hooks
- Hidden files (starting with .) are ignored
- Only files with execute permission are included

Example directory structure:
    .cub/hooks/
        pre-session/
            01-setup.sh
            02-notify.sh
        end-of-task/
            slack-notify.py
        end-of-epic/
            update-dashboard.sh

Usage:
    from cub.core.hooks.discovery import discover_hooks

    # Find all pre-session hooks
    scripts = discover_hooks("pre-session", project_dir)
    for script in scripts:
        print(f"Found hook: {script}")
"""

import os
from pathlib import Path

from cub.core.config.loader import get_xdg_config_home
from cub.core.hooks.models import HookConfig


def discover_hooks(
    hook_name: str,
    project_dir: Path,
    hook_config: HookConfig | None = None,
) -> list[Path]:
    """
    Discover executable hook scripts for a given lifecycle hook.

    Searches both global and project hook directories for executable scripts
    matching the hook name. Returns scripts in sorted order (global first,
    then project) to ensure consistent execution order.

    Args:
        hook_name: Lifecycle hook name (pre-session, end-of-task, etc.)
        project_dir: Project root directory
        hook_config: Optional hook configuration (uses defaults if not provided)

    Returns:
        List of Path objects to executable hook scripts, sorted by:
        1. Source (global before project)
        2. Filename (alphabetical within each source)

    Example:
        >>> from pathlib import Path
        >>> scripts = discover_hooks("pre-session", Path.cwd())
        >>> for script in scripts:
        ...     print(script)
        /home/user/.config/cub/hooks/pre-session/01-setup.sh
        /home/user/project/.cub/hooks/pre-session/02-notify.py

    Notes:
        - Hidden files (starting with .) are ignored
        - Only files with execute permission are included
        - Directories and non-executable files are skipped
        - Scripts are returned in sorted order for deterministic execution
    """
    if not hook_name:
        raise ValueError("hook_name is required and cannot be empty")

    if not project_dir:
        raise ValueError("project_dir is required and cannot be None")

    # Use provided config or create default
    config = hook_config or HookConfig()

    all_scripts: list[Path] = []

    # Discover global hooks
    # If config doesn't specify global_hooks_dir, use default
    global_hooks_path = config.get_global_hooks_path()
    if global_hooks_path is None:
        global_hooks_path = get_default_global_hooks_dir()

    global_hook_dir = global_hooks_path / hook_name
    all_scripts.extend(_discover_in_directory(global_hook_dir))

    # Discover project hooks
    project_hooks_path = config.get_project_hooks_path(project_dir)
    project_hook_dir = project_hooks_path / hook_name
    all_scripts.extend(_discover_in_directory(project_hook_dir))

    return all_scripts


def _discover_in_directory(hook_dir: Path) -> list[Path]:
    """
    Discover executable scripts in a single hook directory.

    Args:
        hook_dir: Directory to search for hooks

    Returns:
        List of executable script paths, sorted by filename

    Notes:
        - Returns empty list if directory doesn't exist or isn't a directory
        - Hidden files (starting with .) are ignored
        - Only files with execute permission are included
    """
    if not hook_dir.exists() or not hook_dir.is_dir():
        return []

    scripts: list[Path] = []

    for entry in sorted(hook_dir.iterdir()):
        # Skip hidden files
        if entry.name.startswith("."):
            continue

        # Only include executable regular files
        if entry.is_file() and os.access(entry, os.X_OK):
            scripts.append(entry)

    return scripts


def get_default_global_hooks_dir() -> Path:
    """
    Get the default global hooks directory path.

    Uses XDG config home standard to locate the global hooks directory.
    This is typically ~/.config/cub/hooks/ on Unix systems.

    Returns:
        Path to default global hooks directory

    Example:
        >>> hooks_dir = get_default_global_hooks_dir()
        >>> print(hooks_dir)
        /home/user/.config/cub/hooks
    """
    return get_xdg_config_home() / "cub" / "hooks"
