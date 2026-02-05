"""
Counter management for collision-free ID allocation.

Counters are stored on the sync branch in `.cub/counters.json` to enable
collision-free allocation of spec numbers and standalone task numbers
across multiple worktrees.

The implementation uses optimistic locking:
1. Read current counter state from sync branch
2. Increment counter locally
3. Attempt to commit updated state
4. If commit fails (concurrent modification), retry with fresh state

Public API:
    - read_counters: Read current counter state from sync branch
    - allocate_spec_number: Allocate next spec number with optimistic locking
    - allocate_standalone_number: Allocate next standalone number with optimistic locking

Example:
    >>> from cub.core.sync import SyncService
    >>> from cub.core.ids.counters import allocate_spec_number, read_counters
    >>> sync = SyncService()
    >>> counters = read_counters(sync)
    >>> print(f"Next spec: {counters.spec_number}")
    >>> spec_num = allocate_spec_number(sync)
    >>> print(f"Allocated: {spec_num}")
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.sync.models import CounterState

if TYPE_CHECKING:
    from cub.core.sync.service import SyncService

logger = logging.getLogger(__name__)

# File path for counters on the sync branch
COUNTERS_FILE = ".cub/counters.json"

# Retry configuration for optimistic locking
MAX_RETRIES = 5
RETRY_DELAY_MS = 50  # Base delay between retries
RETRY_BACKOFF = 1.5  # Exponential backoff multiplier


class CounterAllocationError(Exception):
    """Exception raised when counter allocation fails after retries."""

    def __init__(self, message: str, retries: int = 0):
        super().__init__(message)
        self.retries = retries


def read_counters(sync_service: SyncService) -> CounterState:
    """
    Read current counter state from the sync branch.

    This reads directly from the local sync branch without requiring
    network access. For the most up-to-date state, call sync_service.pull()
    first.

    If the counters file doesn't exist on the sync branch, returns a
    default CounterState with zeroed counters.

    Args:
        sync_service: The SyncService instance to read from.

    Returns:
        CounterState with current counter values.

    Raises:
        RuntimeError: If sync branch is not initialized.

    Example:
        >>> sync = SyncService()
        >>> counters = read_counters(sync)
        >>> print(f"Next spec number: {counters.spec_number}")
    """
    if not sync_service.is_initialized():
        raise RuntimeError(
            f"Sync branch '{sync_service.branch_name}' not initialized. "
            "Call sync_service.initialize() first."
        )

    # Read counters.json from sync branch using git show
    content = sync_service._get_file_from_ref(sync_service.branch_name, COUNTERS_FILE)

    if content is None:
        # Counters file doesn't exist - return defaults
        logger.info("No counters.json found on sync branch, using defaults")
        return CounterState()

    try:
        return CounterState.model_validate_json(content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(
            "Failed to parse counters.json from sync branch: %s. Using defaults.", e
        )
        return CounterState()


def counters_exist(sync_service: SyncService) -> bool:
    """
    Check if counters.json exists on the sync branch.

    Args:
        sync_service: The SyncService instance to check.

    Returns:
        True if counters.json exists on the sync branch, False otherwise.
    """
    if not sync_service.is_initialized():
        return False

    content = sync_service._get_file_from_ref(sync_service.branch_name, COUNTERS_FILE)
    return content is not None


def ensure_counters(
    sync_service: SyncService,
    project_dir: Path | None = None,
) -> CounterState:
    """
    Ensure counters.json exists on the sync branch, creating if needed.

    If counters don't exist, scans local tasks to find the maximum used
    spec and standalone numbers, then initializes counters to max+1 to
    avoid ID collisions.

    This should be called during:
    - `cub sync init` (after creating the sync branch)
    - `cub init` (if sync branch exists but counters don't)

    Args:
        sync_service: The SyncService instance.
        project_dir: Project directory for scanning tasks (defaults to cwd).

    Returns:
        The current (or newly created) CounterState.

    Raises:
        RuntimeError: If sync branch is not initialized.

    Example:
        >>> sync = SyncService()
        >>> sync.initialize()
        >>> counters = ensure_counters(sync)
        >>> print(f"Next spec: {counters.spec_number}")
    """
    if not sync_service.is_initialized():
        raise RuntimeError(
            f"Sync branch '{sync_service.branch_name}' not initialized. "
            "Call sync_service.initialize() first."
        )

    # Check if counters already exist
    content = sync_service._get_file_from_ref(sync_service.branch_name, COUNTERS_FILE)
    if content is not None:
        try:
            return CounterState.model_validate_json(content)
        except (json.JSONDecodeError, ValueError):
            pass  # Fall through to create new counters

    # Counters don't exist - scan local tasks to find max IDs
    project_path = (project_dir or Path.cwd()).resolve()
    max_spec, max_standalone = _scan_local_task_ids(project_path)

    # Initialize counters to max+1 (or 0 if no tasks)
    state = CounterState(
        spec_number=(max_spec + 1) if max_spec is not None else 0,
        standalone_task_number=(max_standalone + 1) if max_standalone is not None else 0,
    )

    logger.info(
        "Initializing counters: spec=%d, standalone=%d",
        state.spec_number,
        state.standalone_task_number,
    )

    # Commit counters to sync branch
    _commit_counters(sync_service, state, "Initialize counters")

    return state


def _scan_local_task_ids(project_dir: Path) -> tuple[int | None, int | None]:
    """
    Scan local tasks to find maximum used spec and standalone numbers.

    This is used during counter initialization to set starting values
    that won't conflict with existing task IDs.

    Args:
        project_dir: Project directory containing .cub/tasks.jsonl.

    Returns:
        Tuple of (max_spec_number, max_standalone_number).
        Returns (None, None) if no tasks found.
    """
    from cub.core.ids.parser import parse_id

    tasks_file = project_dir / ".cub" / "tasks.jsonl"

    if not tasks_file.exists():
        logger.debug("No tasks.jsonl found at %s", tasks_file)
        return (None, None)

    max_spec: int | None = None
    max_standalone: int | None = None

    try:
        with tasks_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    task = json.loads(line)
                    task_id = task.get("id")
                    if not task_id:
                        continue

                    # Try to parse the ID
                    parsed_id = parse_id(task_id)

                    # Check if it's a spec-based ID (EpicId or TaskId)
                    spec_num = None
                    if hasattr(parsed_id, "plan"):
                        # It's an EpicId: plan.spec.number
                        if hasattr(parsed_id.plan, "spec"):
                            spec_num = parsed_id.plan.spec.number
                    elif hasattr(parsed_id, "epic"):
                        # It's a TaskId: epic.plan.spec.number
                        if hasattr(parsed_id.epic, "plan"):
                            if hasattr(parsed_id.epic.plan, "spec"):
                                spec_num = parsed_id.epic.plan.spec.number

                    if spec_num is not None:
                        if max_spec is None or spec_num > max_spec:
                            max_spec = spec_num

                    # Check if it's a standalone ID
                    if hasattr(parsed_id, "project") and hasattr(parsed_id, "number"):
                        if not hasattr(parsed_id, "plan") and not hasattr(parsed_id, "epic"):
                            standalone_num = parsed_id.number
                            if max_standalone is None or standalone_num > max_standalone:
                                max_standalone = standalone_num

                except (json.JSONDecodeError, ValueError):
                    continue

    except OSError as e:
        logger.warning("Failed to read tasks file: %s", e)
        return (None, None)

    logger.debug(
        "Local task scan: max_spec=%s, max_standalone=%s",
        max_spec,
        max_standalone,
    )
    return (max_spec, max_standalone)


def _commit_counters(sync_service: SyncService, state: CounterState, message: str) -> str:
    """
    Commit counter state to the sync branch.

    Uses git plumbing commands to create a commit with the updated
    counters.json file on the sync branch without affecting the working tree.

    Args:
        sync_service: The SyncService instance to commit to.
        state: The CounterState to commit.
        message: Commit message.

    Returns:
        SHA of the created commit.

    Raises:
        RuntimeError: If sync branch is not initialized.
    """
    if not sync_service.is_initialized():
        raise RuntimeError(
            f"Sync branch '{sync_service.branch_name}' not initialized."
        )

    # Serialize state to JSON
    content = state.model_dump_json(indent=2)

    # Create blob with counters content
    blob_sha = sync_service._run_git(
        ["hash-object", "-w", "--stdin"],
        input_data=content,
    )
    logger.debug("Created counters blob: %s", blob_sha)

    # Get current tree from sync branch to preserve other files
    parent_sha = sync_service._get_branch_sha(sync_service.branch_ref)

    # Build new tree with updated counters.json
    # We need to merge the counters.json into the existing tree structure
    tree_sha = _create_tree_with_counters(sync_service, blob_sha, parent_sha)
    logger.debug("Created tree: %s", tree_sha)

    # Create commit
    if parent_sha:
        commit_sha = sync_service._run_git(
            ["commit-tree", tree_sha, "-p", parent_sha, "-m", message],
        )
    else:
        commit_sha = sync_service._run_git(
            ["commit-tree", tree_sha, "-m", message],
        )
    logger.debug("Created commit: %s", commit_sha)

    # Update branch ref
    sync_service._run_git(["update-ref", sync_service.branch_ref, commit_sha])
    logger.info("Committed counters to %s: %s", sync_service.branch_name, commit_sha[:8])

    return commit_sha


def _create_tree_with_counters(
    sync_service: SyncService,
    counters_blob_sha: str,
    parent_sha: str | None,
) -> str:
    """
    Create a tree that includes the counters.json blob.

    If there's a parent commit, we merge the new counters.json into
    the existing tree structure. Otherwise, we create a new tree.

    Args:
        sync_service: The SyncService instance.
        counters_blob_sha: SHA of the counters.json blob.
        parent_sha: SHA of the parent commit (or None for first commit).

    Returns:
        SHA of the created tree.
    """
    if parent_sha is None:
        # No parent - just create tree hierarchy for counters.json
        return sync_service._create_tree_for_path(counters_blob_sha, COUNTERS_FILE)

    # Get existing tree from parent
    parent_tree = sync_service._run_git(["rev-parse", f"{parent_sha}^{{tree}}"])

    # Read existing .cub subtree (if any)
    try:
        cub_tree = sync_service._run_git(
            ["rev-parse", f"{parent_sha}:.cub"],
            check=True,
        )
    except Exception:
        cub_tree = None

    # Build the .cub subtree with counters.json
    if cub_tree:
        # Read existing .cub tree entries
        existing_entries = sync_service._run_git(["ls-tree", cub_tree])

        # Parse entries and replace/add counters.json
        new_entries = []
        found_counters = False
        for line in existing_entries.splitlines():
            if not line.strip():
                continue
            # Format: <mode> <type> <sha>\t<name>
            parts = line.split("\t", 1)
            if len(parts) == 2:
                meta, name = parts
                if name == "counters.json":
                    # Replace with new blob
                    new_entries.append(f"100644 blob {counters_blob_sha}\tcounters.json")
                    found_counters = True
                else:
                    new_entries.append(line)

        if not found_counters:
            # Add counters.json
            new_entries.append(f"100644 blob {counters_blob_sha}\tcounters.json")

        # Create new .cub tree
        tree_input = "\n".join(new_entries) + "\n"
        new_cub_tree = sync_service._run_git(["mktree"], input_data=tree_input)
    else:
        # No .cub directory yet - create one with just counters.json
        tree_input = f"100644 blob {counters_blob_sha}\tcounters.json\n"
        new_cub_tree = sync_service._run_git(["mktree"], input_data=tree_input)

    # Now build the root tree with updated .cub
    # Read root tree entries
    root_entries = sync_service._run_git(["ls-tree", parent_tree])

    new_root_entries = []
    found_cub = False
    for line in root_entries.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            _, name = parts
            if name == ".cub":
                # Replace with updated .cub tree
                new_root_entries.append(f"040000 tree {new_cub_tree}\t.cub")
                found_cub = True
            else:
                new_root_entries.append(line)

    if not found_cub:
        # Add .cub directory
        new_root_entries.append(f"040000 tree {new_cub_tree}\t.cub")

    # Create new root tree
    root_input = "\n".join(new_root_entries) + "\n"
    new_root_tree = sync_service._run_git(["mktree"], input_data=root_input)

    return new_root_tree


def _get_current_branch_sha(sync_service: SyncService) -> str | None:
    """Get current SHA of the sync branch."""
    return sync_service._get_branch_sha(sync_service.branch_ref)


def allocate_spec_number(sync_service: SyncService, max_retries: int = MAX_RETRIES) -> int:
    """
    Allocate the next available spec number with optimistic locking.

    This atomically reads the current counter, increments it, and commits
    the updated state to the sync branch. If a concurrent allocation
    modified the counter, the operation is retried with fresh state.

    Args:
        sync_service: The SyncService instance.
        max_retries: Maximum number of retry attempts on conflict.

    Returns:
        The allocated spec number.

    Raises:
        CounterAllocationError: If allocation fails after max_retries.
        RuntimeError: If sync branch is not initialized.

    Example:
        >>> sync = SyncService()
        >>> spec_num = allocate_spec_number(sync)
        >>> print(f"Allocated spec number: {spec_num}")
    """
    if not sync_service.is_initialized():
        raise RuntimeError(
            f"Sync branch '{sync_service.branch_name}' not initialized. "
            "Call sync_service.initialize() first."
        )

    delay_ms = RETRY_DELAY_MS
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            # Get current state
            expected_sha = _get_current_branch_sha(sync_service)
            state = read_counters(sync_service)

            # Allocate number
            allocated = state.increment_spec_number()

            # Try to commit
            _commit_counters(
                sync_service,
                state,
                f"Allocate spec number {allocated}",
            )

            # Verify the branch still points to expected parent + our commit
            # This is our optimistic lock check
            new_sha = _get_current_branch_sha(sync_service)
            parent_of_new = sync_service._run_git(
                ["rev-parse", f"{new_sha}^"], check=False
            )

            if expected_sha and parent_of_new != expected_sha:
                # Another commit happened between our read and write
                # This shouldn't happen with our single-user model but handle it
                logger.warning(
                    "Concurrent modification detected during spec allocation "
                    "(attempt %d/%d)",
                    attempt + 1,
                    max_retries + 1,
                )
                if attempt < max_retries:
                    time.sleep(delay_ms / 1000)
                    delay_ms = int(delay_ms * RETRY_BACKOFF)
                    continue

            logger.info("Allocated spec number %d", allocated)
            return allocated

        except Exception as e:
            last_error = e
            logger.warning(
                "Spec allocation attempt %d/%d failed: %s",
                attempt + 1,
                max_retries + 1,
                e,
            )
            if attempt < max_retries:
                time.sleep(delay_ms / 1000)
                delay_ms = int(delay_ms * RETRY_BACKOFF)
            else:
                break

    raise CounterAllocationError(
        f"Failed to allocate spec number after {max_retries + 1} attempts: {last_error}",
        retries=max_retries + 1,
    )


def allocate_standalone_number(
    sync_service: SyncService, max_retries: int = MAX_RETRIES
) -> int:
    """
    Allocate the next available standalone task number with optimistic locking.

    This atomically reads the current counter, increments it, and commits
    the updated state to the sync branch. If a concurrent allocation
    modified the counter, the operation is retried with fresh state.

    Args:
        sync_service: The SyncService instance.
        max_retries: Maximum number of retry attempts on conflict.

    Returns:
        The allocated standalone task number.

    Raises:
        CounterAllocationError: If allocation fails after max_retries.
        RuntimeError: If sync branch is not initialized.

    Example:
        >>> sync = SyncService()
        >>> standalone_num = allocate_standalone_number(sync)
        >>> print(f"Allocated standalone number: {standalone_num}")
    """
    if not sync_service.is_initialized():
        raise RuntimeError(
            f"Sync branch '{sync_service.branch_name}' not initialized. "
            "Call sync_service.initialize() first."
        )

    delay_ms = RETRY_DELAY_MS
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            # Get current state
            expected_sha = _get_current_branch_sha(sync_service)
            state = read_counters(sync_service)

            # Allocate number
            allocated = state.increment_standalone_number()

            # Try to commit
            _commit_counters(
                sync_service,
                state,
                f"Allocate standalone task number {allocated}",
            )

            # Verify the branch still points to expected parent + our commit
            new_sha = _get_current_branch_sha(sync_service)
            parent_of_new = sync_service._run_git(
                ["rev-parse", f"{new_sha}^"], check=False
            )

            if expected_sha and parent_of_new != expected_sha:
                # Another commit happened between our read and write
                logger.warning(
                    "Concurrent modification detected during standalone allocation "
                    "(attempt %d/%d)",
                    attempt + 1,
                    max_retries + 1,
                )
                if attempt < max_retries:
                    time.sleep(delay_ms / 1000)
                    delay_ms = int(delay_ms * RETRY_BACKOFF)
                    continue

            logger.info("Allocated standalone task number %d", allocated)
            return allocated

        except Exception as e:
            last_error = e
            logger.warning(
                "Standalone allocation attempt %d/%d failed: %s",
                attempt + 1,
                max_retries + 1,
                e,
            )
            if attempt < max_retries:
                time.sleep(delay_ms / 1000)
                delay_ms = int(delay_ms * RETRY_BACKOFF)
            else:
                break

    raise CounterAllocationError(
        f"Failed to allocate standalone number after {max_retries + 1} attempts: {last_error}",
        retries=max_retries + 1,
    )
