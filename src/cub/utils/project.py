"""
Project root discovery utilities for cub.

This module provides functions for discovering project boundaries
by searching for marker files like .beads/, .git/, .cub/, or .cub.json.
"""

from pathlib import Path

# Markers that indicate a project root, in order of priority
PROJECT_ROOT_MARKERS = [
    ".beads",  # Beads task tracking
    ".cub",  # Cub configuration directory
    ".cub.json",  # Cub configuration file
    ".git",  # Git repository
]


def find_project_root(start: Path | None = None) -> Path | None:
    """
    Find the project root directory by searching upward for marker files.

    Searches from the start directory upward through parent directories,
    looking for common project markers like .beads/, .git/, .cub/, or .cub.json.

    Args:
        start: Directory to start searching from. Defaults to current working directory.

    Returns:
        Path to the project root directory, or None if not found.

    Example:
        >>> find_project_root()  # From /project/src/module/
        PosixPath('/project')

        >>> find_project_root(Path("/project/deep/nested/dir"))
        PosixPath('/project')
    """
    if start is None:
        start = Path.cwd()

    # Ensure we have an absolute path
    start = start.resolve()

    # Search upward through parent directories
    current = start
    while current != current.parent:  # Stop at filesystem root
        for marker in PROJECT_ROOT_MARKERS:
            marker_path = current / marker
            if marker_path.exists():
                return current
        current = current.parent

    # Check the root itself (edge case for /project at root level)
    for marker in PROJECT_ROOT_MARKERS:
        marker_path = current / marker
        if marker_path.exists():
            return current

    return None


def get_project_root(start: Path | None = None) -> Path:
    """
    Get the project root directory, raising an error if not found.

    This is a convenience wrapper around find_project_root that raises
    a clear error message when the project root cannot be determined.

    Args:
        start: Directory to start searching from. Defaults to current working directory.

    Returns:
        Path to the project root directory.

    Raises:
        FileNotFoundError: If no project root can be found.

    Example:
        >>> get_project_root()
        PosixPath('/project')
    """
    root = find_project_root(start)
    if root is None:
        start_dir = start.resolve() if start else Path.cwd()
        raise FileNotFoundError(
            f"Could not find project root from {start_dir}. "
            f"Expected one of: {', '.join(PROJECT_ROOT_MARKERS)}"
        )
    return root
