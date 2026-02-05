"""
Git-based task synchronization service.

Uses git plumbing commands to commit to a sync branch without affecting
the working tree. This allows cub to persist task state in git without
interfering with the user's working directory.

The implementation uses:
- `git hash-object -w` to store file content as blobs
- `git mktree` to create tree objects
- `git commit-tree` to create commits without checkout
- `git update-ref` to move branch refs
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from cub.core.sync.models import SyncConflict, SyncResult, SyncState, SyncStatus

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Exception raised when a git operation fails."""

    def __init__(self, message: str, command: list[str] | None = None, stderr: str = ""):
        super().__init__(message)
        self.command = command
        self.stderr = stderr


class SyncService:
    """
    Service for syncing task state to a git branch.

    Uses git plumbing commands to commit to the sync branch without
    affecting the working tree. This keeps the user's checkout clean
    while persisting task state in git.

    Example:
        >>> sync = SyncService(project_dir=Path("."))
        >>> if not sync.is_initialized():
        ...     sync.initialize()
        >>> commit_sha = sync.commit("Update tasks")
        >>> print(f"Committed: {commit_sha}")
    """

    DEFAULT_BRANCH = "cub-sync"
    DEFAULT_TASKS_FILE = ".cub/tasks.jsonl"
    STATE_FILE = ".cub/.sync-state.json"

    def __init__(
        self,
        project_dir: Path | None = None,
        branch_name: str = DEFAULT_BRANCH,
        tasks_file: str = DEFAULT_TASKS_FILE,
    ) -> None:
        """
        Initialize the sync service.

        Args:
            project_dir: Root directory of the git repository.
                        Defaults to current working directory.
            branch_name: Name of the sync branch (default: "cub-sync").
            tasks_file: Relative path to the tasks file (default: ".cub/tasks.jsonl").
        """
        self.project_dir = (project_dir or Path.cwd()).resolve()
        self.branch_name = branch_name
        self.tasks_file = tasks_file
        self._state: SyncState | None = None

    @property
    def state_file_path(self) -> Path:
        """Full path to the sync state file."""
        return self.project_dir / self.STATE_FILE

    @property
    def tasks_file_path(self) -> Path:
        """Full path to the tasks file."""
        return self.project_dir / self.tasks_file

    @property
    def branch_ref(self) -> str:
        """Full git ref for the sync branch."""
        return f"refs/heads/{self.branch_name}"

    def _run_git(
        self,
        args: list[str],
        *,
        check: bool = True,
        capture_output: bool = True,
        input_data: str | None = None,
    ) -> str:
        """
        Run a git command and return its stdout.

        Args:
            args: Git command arguments (without "git" prefix).
            check: Whether to raise on non-zero exit code.
            capture_output: Whether to capture stdout/stderr.
            input_data: Optional stdin data to pass to the command.

        Returns:
            Command stdout as string (stripped).

        Raises:
            GitError: If the command fails and check=True.
        """
        cmd = ["git"] + args

        logger.debug("Running git command: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=capture_output,
                text=True,
                timeout=60,
                input=input_data,
            )

            if check and result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else ""
                raise GitError(
                    f"Git command failed: {' '.join(cmd)}",
                    command=cmd,
                    stderr=stderr,
                )

            return result.stdout.strip() if result.stdout else ""

        except subprocess.TimeoutExpired as e:
            raise GitError(f"Git command timed out: {' '.join(cmd)}", command=cmd) from e
        except FileNotFoundError as e:
            raise GitError("git not found in PATH", command=cmd) from e

    def _load_state(self) -> SyncState:
        """Load sync state from file or return default state."""
        if self._state is not None:
            return self._state

        if self.state_file_path.exists():
            try:
                content = self.state_file_path.read_text()
                self._state = SyncState.model_validate_json(content)
                return self._state
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to load sync state: %s", e)

        # Return default state
        self._state = SyncState(
            branch_name=self.branch_name,
            tasks_file=self.tasks_file,
        )
        return self._state

    def _save_state(self, state: SyncState) -> None:
        """Save sync state to file atomically."""
        self._state = state

        # Ensure .cub directory exists
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically via temp file
        temp_path = self.state_file_path.with_suffix(".tmp")
        try:
            temp_path.write_text(state.model_dump_json(indent=2))
            temp_path.replace(self.state_file_path)
        except OSError:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _is_git_repo(self) -> bool:
        """Check if we're in a git repository."""
        try:
            self._run_git(["rev-parse", "--git-dir"])
            return True
        except GitError:
            return False

    def _branch_exists(self, branch_ref: str) -> bool:
        """Check if a branch ref exists."""
        try:
            self._run_git(["show-ref", "--verify", "--quiet", branch_ref], check=True)
            return True
        except GitError:
            return False

    def _get_branch_sha(self, branch_ref: str) -> str | None:
        """Get the SHA of a branch, or None if it doesn't exist."""
        try:
            return self._run_git(["rev-parse", branch_ref])
        except GitError:
            return None

    def _hash_file_content(self, content: str) -> str:
        """Compute SHA-256 hash of file content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()

    def is_initialized(self) -> bool:
        """
        Check if the sync branch exists.

        Returns:
            True if the sync branch has been created, False otherwise.
        """
        if not self._is_git_repo():
            return False

        return self._branch_exists(self.branch_ref)

    def initialize(self) -> None:
        """
        Initialize the sync branch.

        Creates the sync branch from the current HEAD. If this is an
        empty repository (no commits), creates an initial commit with
        an empty tree.

        Raises:
            GitError: If git operations fail.
            RuntimeError: If not in a git repository.
        """
        if not self._is_git_repo():
            raise RuntimeError(f"Not a git repository: {self.project_dir}")

        if self.is_initialized():
            logger.info("Sync branch %s already exists", self.branch_name)
            return

        logger.info("Initializing sync branch: %s", self.branch_name)

        # Check if there are any commits
        try:
            head_sha = self._run_git(["rev-parse", "HEAD"])
            # Create branch from HEAD
            self._run_git(["update-ref", self.branch_ref, head_sha])
            logger.info("Created sync branch from HEAD (%s)", head_sha[:8])
        except GitError:
            # No commits yet - create branch from empty tree
            empty_tree_sha = self._create_empty_tree_commit()
            self._run_git(["update-ref", self.branch_ref, empty_tree_sha])
            logger.info("Created sync branch from empty tree (%s)", empty_tree_sha[:8])

        # Update state
        state = self._load_state()
        state.initialized = True
        self._save_state(state)

    def _create_empty_tree_commit(self) -> str:
        """
        Create an initial commit with an empty tree.

        Returns:
            SHA of the created commit.
        """
        # Create empty tree
        empty_tree_sha = self._run_git(["hash-object", "-t", "tree", "/dev/null"])

        # Create commit with empty tree
        commit_sha = self._run_git(
            ["commit-tree", empty_tree_sha, "-m", "Initialize cub-sync branch"],
        )

        return commit_sha

    def get_state(self) -> SyncState:
        """
        Get the current sync state.

        Returns:
            Current SyncState object.
        """
        return self._load_state()

    def _create_tree_for_path(self, blob_sha: str, file_path: str) -> str:
        """
        Create a tree object hierarchy for a file at the given path.

        Git's mktree command doesn't handle paths with slashes. For nested
        paths like '.cub/tasks.jsonl', we need to:
        1. Create a tree for the innermost directory containing the blob
        2. Create parent trees recursively, each containing the child tree
        3. Return the root tree SHA

        Args:
            blob_sha: SHA of the blob to include in the tree.
            file_path: Relative path like '.cub/tasks.jsonl'.

        Returns:
            SHA of the root tree containing the nested structure.
        """
        from pathlib import PurePosixPath

        path = PurePosixPath(file_path)
        parts = list(path.parts)

        if len(parts) == 1:
            # Simple case: file in root directory
            tree_entry = f"100644 blob {blob_sha}\t{parts[0]}\n"
            return self._run_git(["mktree"], input_data=tree_entry)

        # Build trees from innermost to outermost
        # For '.cub/tasks.jsonl': first create tree with tasks.jsonl,
        # then create tree with .cub pointing to that tree

        # Start with the file itself
        filename = parts[-1]
        tree_entry = f"100644 blob {blob_sha}\t{filename}\n"
        current_tree_sha = self._run_git(["mktree"], input_data=tree_entry)

        # Work backwards through parent directories
        for dirname in reversed(parts[:-1]):
            # Create tree entry for directory (mode 040000)
            tree_entry = f"040000 tree {current_tree_sha}\t{dirname}\n"
            current_tree_sha = self._run_git(["mktree"], input_data=tree_entry)

        return current_tree_sha

    def commit(self, message: str | None = None) -> str:
        """
        Commit current task state to the sync branch.

        Uses git plumbing commands to create a commit without affecting the
        working tree. The tasks file content is stored as a blob, a tree is
        created containing that blob, and a commit is created with the tree
        and the current sync branch tip as parent.

        Args:
            message: Commit message. Defaults to "Update tasks" if not provided.

        Returns:
            SHA of the created commit.

        Raises:
            RuntimeError: If sync branch not initialized or tasks file missing.
            GitError: If git operations fail.
        """
        if not self.is_initialized():
            raise RuntimeError(
                f"Sync branch '{self.branch_name}' not initialized. Call initialize() first."
            )

        # Check tasks file exists
        if not self.tasks_file_path.exists():
            raise RuntimeError(
                f"Tasks file not found: {self.tasks_file_path}. Create the file before committing."
            )

        # Read tasks file content
        tasks_content = self.tasks_file_path.read_text()

        # Compute content hash for change detection
        content_hash = self._hash_file_content(tasks_content)

        # Check if content has changed
        state = self._load_state()
        if state.last_tasks_hash == content_hash:
            logger.info("No changes to commit (content hash unchanged)")
            # Return the existing commit SHA if no changes
            if state.last_commit_sha:
                return state.last_commit_sha
            # If no previous commit, fall through to create initial commit

        # Use default message if not provided
        if message is None:
            message = "Update tasks"

        # Step 1: Store tasks.jsonl content as a blob using git hash-object
        # We pass content via stdin to handle any file content correctly
        blob_sha = self._run_git(
            ["hash-object", "-w", "--stdin"],
            input_data=tasks_content,
        )
        logger.debug("Created blob: %s", blob_sha)

        # Step 2: Create tree hierarchy for the nested path
        # git mktree doesn't support slashes in paths, so we build the tree
        # structure manually for paths like '.cub/tasks.jsonl'
        tree_sha = self._create_tree_for_path(blob_sha, self.tasks_file)
        logger.debug("Created tree: %s", tree_sha)

        # Step 3: Get parent commit from current sync branch
        parent_sha = self._get_branch_sha(self.branch_ref)

        # Step 4: Create commit with commit-tree
        if parent_sha:
            # Normal commit with parent
            commit_sha = self._run_git(
                ["commit-tree", tree_sha, "-p", parent_sha, "-m", message],
            )
        else:
            # Root commit (shouldn't happen if initialized, but handle it)
            commit_sha = self._run_git(
                ["commit-tree", tree_sha, "-m", message],
            )
        logger.debug("Created commit: %s", commit_sha)

        # Step 5: Update branch ref to point to new commit
        self._run_git(["update-ref", self.branch_ref, commit_sha])
        logger.info(
            "Committed to %s: %s (%s)",
            self.branch_name,
            commit_sha[:8],
            message,
        )

        # Step 6: Update sync state
        state.mark_synced(commit_sha, content_hash)
        self._save_state(state)

        return commit_sha

    def _remote_branch_exists(self) -> bool:
        """
        Check if the remote sync branch exists.

        Returns:
            True if the remote branch exists, False otherwise.
        """
        state = self._load_state()
        remote_ref = f"refs/remotes/{state.remote_name}/{self.branch_name}"
        return self._branch_exists(remote_ref)

    def _fetch_remote_branch(self) -> bool:
        """
        Fetch the sync branch from remote to remote-tracking branch.

        Fetches to remotes/origin/cub-sync (or equivalent) to avoid
        conflicts when local branch has diverged from remote.

        Returns:
            True if fetch succeeded, False if remote branch doesn't exist.

        Raises:
            GitError: If git fetch fails for reasons other than missing branch.
        """
        state = self._load_state()

        try:
            # Fetch to remote-tracking branch (not local branch)
            # This allows us to compare local vs remote without conflicts
            self._run_git([
                "fetch",
                state.remote_name,
                self.branch_name,
                "--no-tags",
            ])
            return True
        except GitError as e:
            # Check if the error is because the remote branch doesn't exist
            if "couldn't find remote ref" in e.stderr.lower():
                return False
            # Re-raise other errors
            raise

    def _get_file_from_ref(self, ref: str, file_path: str) -> str | None:
        """
        Get file content from a git ref (branch/commit).

        Args:
            ref: Git ref (e.g., "cub-sync", "origin/cub-sync", commit SHA).
            file_path: Relative path to the file in the tree.

        Returns:
            File content as string, or None if file doesn't exist in ref.
        """
        try:
            content = self._run_git(["show", f"{ref}:{file_path}"])
            return content
        except GitError:
            return None

    def _parse_tasks_from_jsonl(self, content: str) -> dict[str, dict[str, Any]]:
        """
        Parse JSONL content into a dict of tasks keyed by ID.

        Args:
            content: JSONL content (one JSON object per line).

        Returns:
            Dict mapping task ID to task dict.
        """
        tasks: dict[str, dict[str, Any]] = {}

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                task_data = json.loads(line)
                if isinstance(task_data, dict) and "id" in task_data:
                    tasks[task_data["id"]] = task_data
            except json.JSONDecodeError:
                # Skip invalid lines
                logger.warning("Skipping invalid JSONL line during pull")
                continue

        return tasks

    def _serialize_tasks_to_jsonl(self, tasks: dict[str, dict[str, Any]]) -> str:
        """
        Serialize tasks dict back to JSONL format.

        Args:
            tasks: Dict mapping task ID to task dict.

        Returns:
            JSONL content string.
        """
        lines = []
        for task in tasks.values():
            lines.append(json.dumps(task, ensure_ascii=False))
        return "\n".join(lines) + "\n" if lines else ""

    def _get_task_updated_at(self, task: dict[str, Any]) -> datetime | None:
        """
        Extract updated_at timestamp from a task dict.

        Args:
            task: Task dictionary.

        Returns:
            datetime if updated_at exists and is parseable, None otherwise.
        """
        updated_at = task.get("updated_at")
        if updated_at is None:
            return None

        if isinstance(updated_at, datetime):
            return updated_at

        if isinstance(updated_at, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except ValueError:
                pass

        return None

    def _merge_tasks(
        self,
        local_tasks: dict[str, dict[str, Any]],
        remote_tasks: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], list[SyncConflict], int]:
        """
        Merge remote tasks into local tasks using last-write-wins strategy.

        For each task:
        - If only in local: keep local version
        - If only in remote: add remote version
        - If in both with same content: no change
        - If in both with different content: use version with later updated_at

        Args:
            local_tasks: Local tasks dict (task_id -> task_data).
            remote_tasks: Remote tasks dict (task_id -> task_data).

        Returns:
            Tuple of (merged_tasks, conflicts, tasks_updated_count).
        """
        merged = dict(local_tasks)  # Start with local tasks
        conflicts: list[SyncConflict] = []
        tasks_updated = 0

        for task_id, remote_task in remote_tasks.items():
            if task_id not in local_tasks:
                # Task only exists remotely - add it
                merged[task_id] = remote_task
                tasks_updated += 1
                logger.debug("Added task %s from remote", task_id)
            else:
                local_task = local_tasks[task_id]

                # Check if tasks are identical
                if json.dumps(local_task, sort_keys=True) == json.dumps(
                    remote_task, sort_keys=True
                ):
                    # No conflict - same content
                    continue

                # Different content - resolve using last-write-wins
                local_updated = self._get_task_updated_at(local_task)
                remote_updated = self._get_task_updated_at(remote_task)

                # Determine winner
                winner: str
                if local_updated is None and remote_updated is None:
                    # No timestamps - prefer remote (incoming changes)
                    winner = "remote"
                elif local_updated is None:
                    # Only remote has timestamp - prefer remote
                    winner = "remote"
                elif remote_updated is None:
                    # Only local has timestamp - prefer local
                    winner = "local"
                elif remote_updated > local_updated:
                    # Remote is newer
                    winner = "remote"
                else:
                    # Local is newer or same time
                    winner = "local"

                # Record conflict
                conflict = SyncConflict(
                    task_id=task_id,
                    local_updated_at=local_updated,
                    remote_updated_at=remote_updated,
                    resolution="last_write_wins",
                    winner=winner,
                )
                conflicts.append(conflict)

                if winner == "remote":
                    merged[task_id] = remote_task
                    tasks_updated += 1
                    logger.info(
                        "Conflict on %s: using remote (updated %s vs local %s)",
                        task_id,
                        remote_updated,
                        local_updated,
                    )
                else:
                    logger.info(
                        "Conflict on %s: keeping local (updated %s vs remote %s)",
                        task_id,
                        local_updated,
                        remote_updated,
                    )

        return merged, conflicts, tasks_updated

    def pull(self) -> SyncResult:
        """
        Pull and merge remote changes into local task state.

        Fetches the sync branch from remote, compares with local tasks,
        detects conflicts, and applies last-write-wins resolution based
        on the `updated_at` timestamp. Commits the merged result locally.

        Conflict Resolution:
        - Same task modified in both local and remote triggers a conflict
        - The version with the later `updated_at` timestamp wins
        - If timestamps are missing, remote changes take precedence
        - All conflicts are logged as warnings

        Returns:
            SyncResult with success status, conflicts list, and tasks_updated count.

        Raises:
            RuntimeError: If sync branch not initialized.
        """
        started_at = datetime.now()

        # Check initialization
        if not self.is_initialized():
            return SyncResult(
                success=False,
                operation="pull",
                message="Sync branch not initialized. Call initialize() first.",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        state = self._load_state()
        remote_ref = f"{state.remote_name}/{self.branch_name}"

        # Step 1: Fetch remote sync branch
        logger.info("Fetching remote sync branch: %s", remote_ref)
        try:
            fetch_success = self._fetch_remote_branch()
        except GitError as e:
            return SyncResult(
                success=False,
                operation="pull",
                message=f"Failed to fetch remote: {e.stderr or str(e)}",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        if not fetch_success:
            # Remote branch doesn't exist - nothing to pull
            return SyncResult(
                success=True,
                operation="pull",
                message="No remote sync branch found. Nothing to pull.",
                tasks_updated=0,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Step 2: Get remote tasks content
        remote_content = self._get_file_from_ref(remote_ref, self.tasks_file)
        if remote_content is None:
            # Remote branch exists but has no tasks file
            return SyncResult(
                success=True,
                operation="pull",
                message="Remote sync branch has no tasks file. Nothing to merge.",
                tasks_updated=0,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Step 3: Get local tasks content
        local_content = ""
        if self.tasks_file_path.exists():
            local_content = self.tasks_file_path.read_text()

        # Step 4: Parse tasks
        remote_tasks = self._parse_tasks_from_jsonl(remote_content)
        local_tasks = self._parse_tasks_from_jsonl(local_content)

        # Step 5: Check if there's anything to merge
        if not remote_tasks:
            return SyncResult(
                success=True,
                operation="pull",
                message="Remote has no tasks. Nothing to merge.",
                tasks_updated=0,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Step 6: Merge tasks with conflict detection
        merged_tasks, conflicts, tasks_updated = self._merge_tasks(
            local_tasks, remote_tasks
        )

        # Log warnings for conflicts
        for conflict in conflicts:
            logger.warning(
                "Conflict detected for task %s: %s version used (local: %s, remote: %s)",
                conflict.task_id,
                conflict.winner,
                conflict.local_updated_at,
                conflict.remote_updated_at,
            )

        # Step 7: Write merged result if there were changes
        if tasks_updated > 0:
            merged_content = self._serialize_tasks_to_jsonl(merged_tasks)

            # Ensure .cub directory exists
            self.tasks_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write merged content atomically
            temp_path = self.tasks_file_path.with_suffix(".tmp")
            try:
                temp_path.write_text(merged_content)
                temp_path.replace(self.tasks_file_path)
            except OSError:
                if temp_path.exists():
                    temp_path.unlink()
                raise

            # Step 8: Commit merged result
            commit_message = f"Merge remote changes ({tasks_updated} tasks updated)"
            if conflicts:
                commit_message += f" [{len(conflicts)} conflicts resolved]"

            try:
                commit_sha = self.commit(commit_message)
            except (RuntimeError, GitError) as e:
                return SyncResult(
                    success=False,
                    operation="pull",
                    message=f"Merge succeeded but commit failed: {e}",
                    tasks_updated=tasks_updated,
                    conflicts=conflicts,
                    started_at=started_at,
                    completed_at=datetime.now(),
                )

            return SyncResult(
                success=True,
                operation="pull",
                commit_sha=commit_sha,
                message=f"Merged {tasks_updated} tasks from remote",
                tasks_updated=tasks_updated,
                conflicts=conflicts,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # No changes needed
        return SyncResult(
            success=True,
            operation="pull",
            message="Local tasks are up to date with remote",
            tasks_updated=0,
            conflicts=conflicts,
            started_at=started_at,
            completed_at=datetime.now(),
        )

    def push(self) -> bool:
        """
        Push local sync branch to remote.

        Pushes the sync branch to the configured remote (default: origin).
        If the remote branch doesn't exist, it will be created automatically.

        Returns:
            True if push succeeded, False otherwise.

        Raises:
            RuntimeError: If sync branch not initialized.
        """
        if not self.is_initialized():
            raise RuntimeError(
                f"Sync branch '{self.branch_name}' not initialized. Call initialize() first."
            )

        state = self._load_state()

        try:
            # Push sync branch to remote
            # Use --set-upstream to create remote branch if it doesn't exist
            self._run_git([
                "push",
                "--set-upstream",
                state.remote_name,
                self.branch_name,
            ])

            # Update state with successful push
            state.mark_pushed()
            self._save_state(state)

            logger.info("Pushed sync branch to %s/%s", state.remote_name, self.branch_name)
            return True

        except GitError as e:
            logger.error("Failed to push sync branch: %s", e.stderr or str(e))
            return False

    def get_status(self) -> SyncStatus:
        """
        Get sync status comparing local and remote branches.

        Compares the local sync branch with the remote tracking branch to
        determine if local is up-to-date, ahead, behind, or diverged.

        Returns:
            SyncStatus enum indicating the relationship between local and remote.
        """
        # Check if sync branch is initialized
        if not self.is_initialized():
            return SyncStatus.UNINITIALIZED

        state = self._load_state()
        remote_ref = f"{state.remote_name}/{self.branch_name}"

        # Try to fetch remote branch
        try:
            fetch_success = self._fetch_remote_branch()
        except GitError as e:
            logger.warning("Failed to fetch remote: %s", e.stderr or str(e))
            return SyncStatus.NO_REMOTE

        if not fetch_success:
            # Remote branch doesn't exist
            return SyncStatus.NO_REMOTE

        # Get local and remote commit SHAs
        local_sha = self._get_branch_sha(self.branch_ref)
        remote_sha = self._get_branch_sha(f"refs/remotes/{remote_ref}")

        if local_sha is None or remote_sha is None:
            return SyncStatus.NO_REMOTE

        # Check if they're the same
        if local_sha == remote_sha:
            return SyncStatus.UP_TO_DATE

        # Use git merge-base to determine relationship
        try:
            # Get common ancestor
            merge_base = self._run_git(["merge-base", local_sha, remote_sha])

            if merge_base == local_sha:
                # Local is ancestor of remote - we're behind
                return SyncStatus.BEHIND
            elif merge_base == remote_sha:
                # Remote is ancestor of local - we're ahead
                return SyncStatus.AHEAD
            else:
                # Branches have diverged
                return SyncStatus.DIVERGED

        except GitError:
            # merge-base failed - branches likely have no common history
            return SyncStatus.DIVERGED

    # Agent.md managed section sync methods

    MANAGED_SECTION_START = "<!-- BEGIN CUB MANAGED SECTION"
    MANAGED_SECTION_END = "<!-- END CUB MANAGED SECTION -->"
    AGENT_FILES = ["agent.md", "AGENT.md", "AGENTS.md", "CLAUDE.md"]

    def _find_agent_file(self, ref: str | None = None) -> str | None:
        """
        Find which agent.md variant exists.

        Args:
            ref: Git ref to check (None for working tree).

        Returns:
            Filename if found, None otherwise.
        """
        if ref is None:
            # Check working tree
            cub_dir = self.project_dir / ".cub"
            for filename in self.AGENT_FILES:
                path = cub_dir / filename
                if path.exists():
                    return str(cub_dir / filename)
            return None
        else:
            # Check git ref
            for filename in self.AGENT_FILES:
                file_path = f".cub/{filename}"
                content = self._get_file_from_ref(ref, file_path)
                if content is not None:
                    return file_path
            return None

    def _parse_managed_sections(self, content: str) -> dict[str, tuple[str, int, int]]:
        """
        Parse managed sections from agent.md content.

        Returns:
            Dict mapping section version to (content, start_pos, end_pos) tuple.
        """
        sections: dict[str, tuple[str, int, int]] = {}
        lines = content.splitlines(keepends=True)
        i = 0

        while i < len(lines):
            line = lines[i]

            # Look for section start marker
            if self.MANAGED_SECTION_START in line:
                # Extract version from marker (e.g., "v1")
                version = "v1"  # default
                if " v" in line:
                    # Extract version: "<!-- BEGIN CUB MANAGED SECTION v1 -->"
                    # Split by " v" and take everything after until " " or "-->"
                    version_part = line.split(" v")[-1].strip()
                    # Remove trailing " -->" if present
                    version_part = version_part.rstrip("-->").strip()
                    if version_part:
                        version = "v" + version_part

                start_line = i
                i += 1

                # Skip optional sha256 line
                if i < len(lines) and "sha256:" in lines[i]:
                    i += 1

                # Find end marker
                section_lines: list[str] = []
                while i < len(lines):
                    if self.MANAGED_SECTION_END in lines[i]:
                        # Found end marker
                        section_content = "".join(section_lines)

                        # Calculate positions in original content
                        start_pos = sum(len(lines[j]) for j in range(start_line))
                        end_pos = sum(len(lines[j]) for j in range(i + 1))

                        sections[version] = (section_content, start_pos, end_pos)
                        break
                    else:
                        section_lines.append(lines[i])
                        i += 1

            i += 1

        return sections

    def _inject_managed_sections(
        self,
        content: str,
        sections: dict[str, tuple[str, int, int]],
    ) -> str:
        """
        Inject managed sections into content, replacing existing sections.

        Args:
            content: Base content to inject into.
            sections: Dict mapping version to (new_content, _, _) - positions ignored.

        Returns:
            Modified content with sections replaced.
        """
        # Parse existing sections to find positions
        existing_sections = self._parse_managed_sections(content)

        # Build replacement map: version -> new content
        replacements: dict[str, str] = {}
        for version, (new_content, _, _) in sections.items():
            replacements[version] = new_content

        # Apply replacements in reverse order (by position) to preserve indices
        result = content
        for version, (old_content, start_pos, end_pos) in sorted(
            existing_sections.items(),
            key=lambda x: x[1][1],
            reverse=True,
        ):
            if version in replacements:
                # Compute new section content with markers
                new_content = replacements[version]
                content_hash = hashlib.sha256(new_content.encode()).hexdigest()

                new_section = (
                    f"{self.MANAGED_SECTION_START} {version} -->\n"
                    f"<!-- sha256:{content_hash} -->\n"
                    f"{new_content}"
                    f"{self.MANAGED_SECTION_END}\n"
                )

                # Replace old section with new
                result = result[:start_pos] + new_section + result[end_pos:]

        return result

    def _detect_agent_sync_conflicts(
        self,
        local_content: str,
        remote_content: str,
    ) -> list[str]:
        """
        Detect conflicts in managed sections between local and remote.

        A conflict exists when both local and remote have the same section version
        but with different content AND different content hashes.

        For a proper conflict check, we need to compare the sha256 hashes in the
        markers. If the hashes differ, it means both sides were modified independently.

        Returns:
            List of conflicting section versions.
        """
        local_sections = self._parse_managed_sections(local_content)
        remote_sections = self._parse_managed_sections(remote_content)

        conflicts: list[str] = []

        # Parse sha256 hashes from content
        def extract_hash(content: str) -> str | None:
            for line in content.splitlines():
                if "sha256:" in line:
                    # Extract hash from comment like "<!-- sha256:abc123 -->"
                    parts = line.split("sha256:")
                    if len(parts) > 1:
                        hash_part = parts[1].split("-->")[0].strip()
                        return hash_part
            return None

        for version in set(local_sections.keys()) | set(remote_sections.keys()):
            if version not in local_sections or version not in remote_sections:
                continue  # One side doesn't have this section - no conflict

            local_text, _, _ = local_sections[version]
            remote_text, _, _ = remote_sections[version]

            # Check if content is identical - no conflict
            if local_text.strip() == remote_text.strip():
                continue

            # Check hashes to detect true conflicts (both modified)
            # If we can't find hashes or they're the same, assume no conflict (remote wins)
            local_hash = extract_hash(local_content)
            remote_hash = extract_hash(remote_content)

            # Only conflict if both have different hashes (both modified independently)
            if local_hash and remote_hash and local_hash != remote_hash:
                conflicts.append(version)

        return conflicts

    def sync_agent_pull(self) -> SyncResult:
        """
        Pull managed sections from sync branch to local agent.md.

        Reads managed sections from agent.md on the sync branch and
        injects them into the local working tree agent.md file.

        Returns:
            SyncResult with operation details.
        """
        started_at = datetime.now()

        # Check initialization
        if not self.is_initialized():
            return SyncResult(
                success=False,
                operation="agent_pull",
                message="Sync branch not initialized. Run 'cub sync init' first.",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Find agent file locally
        local_agent_path_str = self._find_agent_file(ref=None)
        if local_agent_path_str is None:
            return SyncResult(
                success=False,
                operation="agent_pull",
                message="No agent.md file found in .cub/",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        local_agent_path = Path(local_agent_path_str)

        # Find agent file on sync branch
        remote_agent_file = self._find_agent_file(ref=self.branch_ref)
        if remote_agent_file is None:
            return SyncResult(
                success=True,
                operation="agent_pull",
                message="No agent.md on sync branch. Nothing to pull.",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Read remote content
        remote_content = self._get_file_from_ref(self.branch_ref, remote_agent_file)
        if remote_content is None:
            return SyncResult(
                success=False,
                operation="agent_pull",
                message=f"Failed to read {remote_agent_file} from sync branch",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Parse remote managed sections
        remote_sections = self._parse_managed_sections(remote_content)
        if not remote_sections:
            return SyncResult(
                success=True,
                operation="agent_pull",
                message="No managed sections found on sync branch",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Read local content
        local_content = local_agent_path.read_text()

        # Check for conflicts
        conflicts_list = self._detect_agent_sync_conflicts(local_content, remote_content)
        if conflicts_list:
            conflicts = [
                SyncConflict(
                    task_id=f"agent.md section {v}",
                    resolution="manual_required",
                    winner="none",
                )
                for v in conflicts_list
            ]
            return SyncResult(
                success=False,
                operation="agent_pull",
                message=f"Conflicts detected in sections: {', '.join(conflicts_list)}",
                conflicts=conflicts,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Inject remote sections into local content
        updated_content = self._inject_managed_sections(local_content, remote_sections)

        # Check if anything changed
        if updated_content == local_content:
            return SyncResult(
                success=True,
                operation="agent_pull",
                message="Local agent.md already up to date",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Write updated content
        local_agent_path.write_text(updated_content)

        return SyncResult(
            success=True,
            operation="agent_pull",
            message=f"Pulled {len(remote_sections)} managed sections to {local_agent_path.name}",
            tasks_updated=len(remote_sections),
            started_at=started_at,
            completed_at=datetime.now(),
        )

    def sync_agent_push(self) -> SyncResult:
        """
        Push managed sections from local agent.md to sync branch.

        Reads managed sections from local working tree agent.md and
        commits them to the sync branch.

        Returns:
            SyncResult with operation details.
        """
        started_at = datetime.now()

        # Check initialization
        if not self.is_initialized():
            return SyncResult(
                success=False,
                operation="agent_push",
                message="Sync branch not initialized. Run 'cub sync init' first.",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Find local agent file
        local_agent_path_str = self._find_agent_file(ref=None)
        if local_agent_path_str is None:
            return SyncResult(
                success=False,
                operation="agent_push",
                message="No agent.md file found in .cub/",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        local_agent_path = Path(local_agent_path_str)

        # Read local content
        local_content = local_agent_path.read_text()

        # Parse local managed sections
        local_sections = self._parse_managed_sections(local_content)
        if not local_sections:
            return SyncResult(
                success=True,
                operation="agent_push",
                message="No managed sections found in local agent.md",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Determine target filename on sync branch
        relative_path = f".cub/{local_agent_path.name}"

        # Get current content from sync branch (if exists)
        sync_branch_content = self._get_file_from_ref(self.branch_ref, relative_path)

        if sync_branch_content is None:
            # File doesn't exist on sync branch - create with just managed sections
            new_content_lines = []
            for version, (content, _, _) in sorted(local_sections.items()):
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                new_content_lines.append(f"{self.MANAGED_SECTION_START} {version} -->")
                new_content_lines.append(f"<!-- sha256:{content_hash} -->")
                new_content_lines.append(content.rstrip())
                new_content_lines.append(self.MANAGED_SECTION_END)
                new_content_lines.append("")
            new_content = "\n".join(new_content_lines)
        else:
            # Inject local sections into sync branch content
            new_content = self._inject_managed_sections(sync_branch_content, local_sections)

        # Check if anything changed
        if new_content == sync_branch_content:
            return SyncResult(
                success=True,
                operation="agent_push",
                message="Sync branch agent.md already up to date",
                started_at=started_at,
                completed_at=datetime.now(),
            )

        # Create blob for new content
        blob_sha = self._run_git(["hash-object", "-w", "--stdin"], input_data=new_content)

        # Create tree with the agent file
        tree_sha = self._create_tree_for_path(blob_sha, relative_path)

        # Get parent commit
        parent_sha = self._get_branch_sha(self.branch_ref)

        # Create commit
        commit_message = f"Update managed sections in {local_agent_path.name}"
        if parent_sha:
            commit_sha = self._run_git(
                ["commit-tree", tree_sha, "-p", parent_sha, "-m", commit_message]
            )
        else:
            commit_sha = self._run_git(["commit-tree", tree_sha, "-m", commit_message])

        # Update branch ref
        self._run_git(["update-ref", self.branch_ref, commit_sha])

        logger.info(
            "Pushed managed sections to %s: %s",
            self.branch_name,
            commit_sha[:8],
        )

        return SyncResult(
            success=True,
            operation="agent_push",
            commit_sha=commit_sha,
            message=f"Pushed {len(local_sections)} managed sections to sync branch",
            tasks_updated=len(local_sections),
            started_at=started_at,
            completed_at=datetime.now(),
        )
