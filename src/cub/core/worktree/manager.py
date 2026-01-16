"""
Git worktree manager implementation.

This module provides the WorktreeManager class for creating, listing, and
managing git worktrees for parallel task execution.
"""

import builtins
from dataclasses import dataclass
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo


class WorktreeError(Exception):
    """Base exception for worktree operations."""

    pass


class WorktreeNotFoundError(WorktreeError):
    """Raised when a worktree cannot be found."""

    pass


class WorktreeLockError(WorktreeError):
    """Raised when a worktree is locked and cannot be removed."""

    pass


@dataclass
class Worktree:
    """
    Represents a git worktree.

    Attributes:
        path: Absolute path to the worktree directory
        branch: Branch name (None for detached HEAD)
        commit: Commit SHA
        is_bare: Whether this is the bare repository
        is_locked: Whether the worktree is locked
    """

    path: Path
    branch: str | None
    commit: str
    is_bare: bool = False
    is_locked: bool = False


class WorktreeManager:
    """
    Manages git worktrees for parallel task execution.

    This class provides a high-level interface to git worktree operations,
    handling worktree creation, listing, removal, and cleanup of merged branches.

    Example:
        >>> manager = WorktreeManager()
        >>> worktree = manager.create("cub-001", "feature/task-001")
        >>> print(f"Created worktree at: {worktree.path}")
        >>> worktrees = manager.list()
        >>> manager.remove(worktree.path)
    """

    def __init__(self, repo_path: Path | None = None):
        """
        Initialize the worktree manager.

        Args:
            repo_path: Path to git repository (defaults to current directory)

        Raises:
            WorktreeError: If not in a git repository
        """
        self.repo_path = repo_path or Path.cwd()

        try:
            self.repo = Repo(self.repo_path, search_parent_directories=True)
        except InvalidGitRepositoryError as e:
            raise WorktreeError(f"Not a git repository: {self.repo_path}") from e

        # Base directory for worktrees
        self.worktree_base = Path(self.repo.working_dir) / ".cub" / "worktrees"

    def create(
        self,
        task_id: str,
        branch: str | None = None,
        create_branch: bool = True,
    ) -> Worktree:
        """
        Create a new worktree for a task.

        Args:
            task_id: Task ID (used for worktree directory name)
            branch: Branch name (defaults to task ID if create_branch=True)
            create_branch: Whether to create a new branch if it doesn't exist

        Returns:
            Worktree object representing the created worktree

        Raises:
            WorktreeError: If worktree creation fails
        """
        # Determine branch name
        if branch is None and create_branch:
            branch = task_id

        # Worktree path: .cub/worktrees/{task-id}/
        worktree_path = self.worktree_base / task_id

        # Check if worktree already exists
        if worktree_path.exists():
            raise WorktreeError(f"Worktree already exists at: {worktree_path}")

        # Create parent directory if needed
        self.worktree_base.mkdir(parents=True, exist_ok=True)

        try:
            # Build git worktree add command
            # Format: git worktree add [-b <new-branch>] <path> [<commit-ish>]
            cmd = ["worktree", "add"]

            if create_branch and branch:
                # Create new branch: git worktree add -b <branch> <path>
                cmd.extend(["-b", branch])
                cmd.append(str(worktree_path))
            elif branch:
                # Use existing branch: git worktree add <branch> <path>
                cmd.append(branch)
                cmd.append(str(worktree_path))
            else:
                # Detached HEAD: git worktree add <path> HEAD
                cmd.append(str(worktree_path))
                cmd.append("HEAD")

            # Execute git worktree add
            self.repo.git.execute(cmd)

            # Get commit SHA
            worktree_repo = Repo(worktree_path)
            commit_sha = worktree_repo.head.commit.hexsha

            return Worktree(
                path=worktree_path,
                branch=branch,
                commit=commit_sha,
                is_bare=False,
                is_locked=False,
            )

        except GitCommandError as e:
            raise WorktreeError(f"Failed to create worktree: {e.stderr}") from e

    def list(self) -> list[Worktree]:
        """
        List all worktrees in the repository.

        Returns:
            List of Worktree objects

        Raises:
            WorktreeError: If listing worktrees fails
        """
        try:
            # Execute git worktree list --porcelain
            output = self.repo.git.worktree("list", "--porcelain")

            worktrees: list[Worktree] = []
            current_worktree: dict[str, str | bool] = {}

            for line in output.splitlines():
                line = line.strip()
                if not line:
                    # Empty line indicates end of worktree entry
                    if current_worktree:
                        worktrees.append(self._parse_worktree(current_worktree))
                        current_worktree = {}
                    continue

                if line.startswith("worktree "):
                    current_worktree["path"] = line[len("worktree ") :]
                elif line.startswith("HEAD "):
                    current_worktree["commit"] = line[len("HEAD ") :]
                elif line.startswith("branch "):
                    current_worktree["branch"] = line[len("branch ") :]
                elif line == "bare":
                    current_worktree["is_bare"] = True
                elif line == "locked":
                    current_worktree["is_locked"] = True

            # Handle last worktree if no trailing empty line
            if current_worktree:
                worktrees.append(self._parse_worktree(current_worktree))

            return worktrees

        except GitCommandError as e:
            raise WorktreeError(f"Failed to list worktrees: {e.stderr}") from e

    def _parse_worktree(self, data: dict[str, str | bool]) -> Worktree:
        """Parse worktree data dict into Worktree object."""
        return Worktree(
            path=Path(str(data.get("path", ""))),
            branch=str(data["branch"]) if "branch" in data else None,
            commit=str(data.get("commit", "")),
            is_bare=bool(data.get("is_bare", False)),
            is_locked=bool(data.get("is_locked", False)),
        )

    def remove(self, path: Path, force: bool = False) -> None:
        """
        Remove a worktree.

        Args:
            path: Path to the worktree directory
            force: Force removal even if worktree has uncommitted changes

        Raises:
            WorktreeNotFoundError: If worktree doesn't exist
            WorktreeLockError: If worktree is locked and force=False
            WorktreeError: If removal fails
        """
        # Check if worktree exists
        if not path.exists():
            raise WorktreeNotFoundError(f"Worktree not found: {path}")

        # Check if it's actually a worktree
        worktrees = self.list()
        worktree = next((w for w in worktrees if w.path == path), None)

        if not worktree:
            raise WorktreeNotFoundError(f"Not a worktree: {path}")

        if worktree.is_bare:
            raise WorktreeError("Cannot remove bare repository worktree")

        if worktree.is_locked and not force:
            raise WorktreeLockError(f"Worktree is locked: {path}")

        try:
            # Build git worktree remove command
            cmd = ["worktree", "remove"]
            if force:
                cmd.append("--force")
            cmd.append(str(path))

            # Execute git worktree remove
            self.repo.git.execute(cmd)

        except GitCommandError as e:
            raise WorktreeError(f"Failed to remove worktree: {e.stderr}") from e

    def get_for_task(self, task_id: str, create_if_missing: bool = True) -> Path:
        """
        Get worktree path for a task, creating it if needed.

        Args:
            task_id: Task ID
            create_if_missing: Whether to create worktree if it doesn't exist

        Returns:
            Path to the task's worktree directory

        Raises:
            WorktreeNotFoundError: If worktree doesn't exist and create_if_missing=False
            WorktreeError: If worktree creation fails
        """
        # Check if worktree already exists
        worktree_path = self.worktree_base / task_id

        if worktree_path.exists():
            return worktree_path

        if not create_if_missing:
            raise WorktreeNotFoundError(f"Worktree not found for task: {task_id}")

        # Create new worktree
        worktree = self.create(task_id)
        return worktree.path

    def cleanup_merged(self, base_branch: str = "main") -> builtins.list[Path]:
        """
        Remove worktrees for branches that have been merged.

        Args:
            base_branch: Base branch to check for merged branches (default: "main")

        Returns:
            List of removed worktree paths

        Raises:
            WorktreeError: If cleanup fails
        """
        try:
            # Get list of merged branches
            merged_output = self.repo.git.branch("--merged", base_branch)
            merged_branches = {branch.strip().lstrip("* ") for branch in merged_output.splitlines()}

            # Get all worktrees
            worktrees = self.list()
            removed_paths: list[Path] = []

            for worktree in worktrees:
                # Skip bare repository and worktrees without branches
                if worktree.is_bare or not worktree.branch:
                    continue

                # Extract branch name (remove refs/heads/ prefix if present)
                branch_name = worktree.branch
                if branch_name.startswith("refs/heads/"):
                    branch_name = branch_name[len("refs/heads/") :]

                # Skip the base branch itself
                if branch_name == base_branch:
                    continue

                # Check if branch is merged
                if branch_name in merged_branches:
                    try:
                        self.remove(worktree.path, force=False)
                        removed_paths.append(worktree.path)
                    except (WorktreeError, WorktreeLockError):
                        # Skip locked or problematic worktrees
                        continue

            return removed_paths

        except GitCommandError as e:
            raise WorktreeError(f"Failed to cleanup merged worktrees: {e.stderr}") from e

    def prune(self) -> None:
        """
        Prune stale worktree administrative data.

        Removes worktree administrative files for worktrees that no longer exist
        on disk. This is equivalent to 'git worktree prune'.

        Raises:
            WorktreeError: If prune operation fails
        """
        try:
            self.repo.git.worktree("prune")
        except GitCommandError as e:
            raise WorktreeError(f"Failed to prune worktrees: {e.stderr}") from e
