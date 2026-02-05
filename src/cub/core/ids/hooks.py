"""
Git hooks for ID collision prevention.

Provides hook implementations that verify counter state before pushing
to prevent ID collisions when multiple worktrees are using the same
counter ranges.

The pre-push hook checks that locally-used spec/standalone numbers don't
conflict with the remote sync branch counters, catching collisions before
they're pushed upstream.

Public API:
    - verify_counters_before_push: Pre-push hook verification logic
    - format_hook_message: Format user-facing error messages

Example:
    >>> from cub.core.ids.hooks import verify_counters_before_push
    >>> ok, message = verify_counters_before_push()
    >>> if not ok:
    ...     print(f"Push blocked: {message}")
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from cub.core.ids.counters import COUNTERS_FILE, _scan_local_task_ids
from cub.core.sync.models import CounterState
from cub.core.sync.service import SyncService

logger = logging.getLogger(__name__)


def verify_counters_before_push(
    project_dir: Path | None = None,
    remote_name: str = "origin",
    branch_name: str = "cub-sync",
) -> tuple[bool, str]:
    """
    Verify that local counter usage doesn't conflict with remote sync branch.

    This function is called by the pre-push hook to check for ID collisions
    before pushing. It:
    1. Fetches the remote sync branch
    2. Reads remote and local counter states
    3. Scans local task IDs to find maximum used numbers
    4. Checks if any local IDs conflict with remote counters

    Args:
        project_dir: Project directory (defaults to current directory)
        remote_name: Git remote name (default: "origin")
        branch_name: Sync branch name (default: "cub-sync")

    Returns:
        Tuple of (success, message):
        - (True, ""): No conflicts, safe to push
        - (False, error_message): Conflicts detected, push should be blocked

    Example:
        >>> ok, message = verify_counters_before_push()
        >>> if not ok:
        ...     print(f"ERROR: {message}")
        ...     sys.exit(1)
    """
    project_path = (project_dir or Path.cwd()).resolve()

    # Initialize sync service
    sync_service = SyncService(project_dir=project_path, branch_name=branch_name)

    # Check if sync branch is initialized
    if not sync_service.is_initialized():
        # No sync branch yet - this is fine, nothing to check
        logger.debug("Sync branch not initialized, skipping counter verification")
        return (True, "")

    # Fetch remote sync branch to get latest counter state
    try:
        _fetch_remote_sync_branch(project_path, remote_name, branch_name)
    except GitError as e:
        # If remote doesn't exist or fetch fails, skip verification
        # This handles cases where remote isn't set up yet
        logger.debug(f"Could not fetch remote sync branch: {e}")
        return (True, "")

    # Read remote counter state
    try:
        remote_counters = _read_remote_counters(project_path, remote_name, branch_name)
    except Exception as e:
        # If we can't read remote counters, skip verification
        logger.debug(f"Could not read remote counters: {e}")
        return (True, "")

    # If remote has no counters.json, skip verification
    # This means counter tracking isn't set up on remote yet
    if remote_counters is None:
        logger.debug("Remote has no counters.json, skipping counter verification")
        return (True, "")

    # Scan local tasks to find maximum used IDs
    max_local_spec, max_local_standalone = _scan_local_task_ids(project_path)

    # Check for conflicts
    conflicts = []

    # Check spec number conflicts
    if max_local_spec is not None and max_local_spec >= remote_counters.spec_number:
        # Local has used a spec number that's >= remote's next counter
        # This means pushing would create a collision
        conflicts.append(
            f"Local spec number {max_local_spec} conflicts with "
            f"remote counter (next: {remote_counters.spec_number})"
        )

    # Check standalone number conflicts
    if (
        max_local_standalone is not None
        and max_local_standalone >= remote_counters.standalone_task_number
    ):
        # Local has used a standalone number that's >= remote's next counter
        conflicts.append(
            f"Local standalone task number {max_local_standalone} conflicts with "
            f"remote counter (next: {remote_counters.standalone_task_number})"
        )

    if conflicts:
        error_msg = format_hook_message(
            conflicts=conflicts,
            local_spec=max_local_spec,
            local_standalone=max_local_standalone,
            remote_spec=remote_counters.spec_number,
            remote_standalone=remote_counters.standalone_task_number,
        )
        return (False, error_msg)

    return (True, "")


def format_hook_message(
    conflicts: list[str],
    local_spec: int | None,
    local_standalone: int | None,
    remote_spec: int,
    remote_standalone: int,
) -> str:
    """
    Format a user-facing error message for counter conflicts.

    Args:
        conflicts: List of conflict descriptions
        local_spec: Maximum local spec number (or None)
        local_standalone: Maximum local standalone number (or None)
        remote_spec: Remote next spec number
        remote_standalone: Remote next standalone number

    Returns:
        Formatted error message with resolution instructions
    """
    lines = [
        "ERROR: ID collision detected!",
        "",
        "Your local task IDs conflict with the remote sync branch counters.",
        "This would create duplicate IDs if you push.",
        "",
        "Conflicts:",
    ]

    for conflict in conflicts:
        lines.append(f"  - {conflict}")

    lines.extend(
        [
            "",
            "Current state:",
            f"  Local max spec:        {local_spec if local_spec is not None else 'none'}",
            f"  Remote next spec:      {remote_spec}",
            (
                f"  Local max standalone:  "
                f"{local_standalone if local_standalone is not None else 'none'}"
            ),
            f"  Remote next standalone: {remote_standalone}",
            "",
            "Resolution:",
            "1. Pull the latest sync branch: git fetch origin cub-sync",
            "2. Sync your local counters: cub sync pull",
            "3. Renumber conflicting task IDs to use the updated counter range",
            "4. Try pushing again",
            "",
            "Or bypass this check (NOT RECOMMENDED): git push --no-verify",
        ]
    )

    return "\n".join(lines)


def _fetch_remote_sync_branch(
    project_dir: Path, remote_name: str, branch_name: str
) -> None:
    """
    Fetch the remote sync branch.

    Args:
        project_dir: Project directory
        remote_name: Git remote name
        branch_name: Sync branch name

    Raises:
        GitError: If fetch fails
    """
    try:
        result = subprocess.run(
            ["git", "fetch", remote_name, f"{branch_name}:{branch_name}"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            # Try fetch without updating local ref (for cases where branch exists)
            result = subprocess.run(
                ["git", "fetch", remote_name, branch_name],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise GitError(
                    f"Failed to fetch remote sync branch: {result.stderr}",
                    command=["git", "fetch", remote_name, branch_name],
                    stderr=result.stderr,
                )
    except subprocess.TimeoutExpired as e:
        raise GitError(
            "Timeout fetching remote sync branch",
            command=["git", "fetch", remote_name, branch_name],
        ) from e


def _read_remote_counters(
    project_dir: Path, remote_name: str, branch_name: str
) -> CounterState | None:
    """
    Read counter state from remote sync branch.

    Args:
        project_dir: Project directory
        remote_name: Git remote name
        branch_name: Sync branch name

    Returns:
        CounterState from remote, or None if counters.json doesn't exist

    Raises:
        RuntimeError: If counters can't be read due to timeout
    """
    # Try to read counters.json from remote branch
    remote_ref = f"{remote_name}/{branch_name}"

    try:
        result = subprocess.run(
            ["git", "show", f"{remote_ref}:{COUNTERS_FILE}"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            # Counters file doesn't exist on remote - return None to skip verification
            logger.debug("No counters.json on remote, skipping counter verification")
            return None

        # Parse the JSON
        return CounterState.model_validate_json(result.stdout)

    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Timeout reading remote counters") from e
    except Exception as e:
        logger.warning(f"Failed to parse remote counters: {e}")
        # Can't parse - return None to skip verification
        return None


class GitError(Exception):
    """Exception raised when a git operation fails."""

    def __init__(self, message: str, command: list[str] | None = None, stderr: str = ""):
        super().__init__(message)
        self.command = command
        self.stderr = stderr
