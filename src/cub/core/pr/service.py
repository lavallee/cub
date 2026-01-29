"""
PR service for managing pull requests.

Provides high-level operations for creating, managing, and merging
pull requests with optional CI/review handling via Claude.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cub.core.branches import BranchStore, ResolvedTarget
from cub.core.github.client import GitHubClient, GitHubClientError
from cub.core.tasks.backend import TaskBackend, get_backend
from cub.core.tasks.models import TaskStatus

logger = logging.getLogger(__name__)


class PREventCallback(Protocol):
    """Protocol for PR service event callbacks."""

    def on_progress(self, message: str) -> None:
        """Called when a progress message should be displayed.

        Args:
            message: Progress message (e.g., "Resolving target...")
        """
        ...

    def on_status(self, message: str, level: str = "info") -> None:
        """Called when a status message should be displayed.

        Args:
            message: Status message (e.g., "Branch pushed")
            level: Message level (info, success, warning, error)
        """
        ...

    def on_info(self, message: str) -> None:
        """Called when an informational message should be displayed.

        Args:
            message: Informational message (e.g., "Creating PR: My Title")
        """
        ...


def _find_worktree_for_branch(project_dir: Path, branch: str) -> Path | None:
    """
    Find the worktree directory for a given branch.

    Checks both beads worktrees (.git/beads-worktrees/) and cub worktrees
    (.cub/worktrees/).

    Args:
        project_dir: Project root directory
        branch: Branch name to find

    Returns:
        Path to worktree directory, or None if not found
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            check=False,
        )
        if result.returncode != 0:
            return None

        # Parse worktree list
        current_path: str | None = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("worktree "):
                current_path = line[len("worktree ") :]
            elif line.startswith("branch "):
                worktree_branch = line[len("branch ") :]
                # Branch can be refs/heads/main or just main
                if worktree_branch.endswith(f"/{branch}") or worktree_branch == branch:
                    if current_path:
                        return Path(current_path)

        return None
    except (OSError, FileNotFoundError):
        return None


def _update_worktree(worktree_path: Path) -> bool:
    """
    Update a worktree by pulling from remote.

    Args:
        worktree_path: Path to the worktree

    Returns:
        True if update succeeded, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True,
            text=True,
            cwd=worktree_path,
            check=False,
        )
        return result.returncode == 0
    except (OSError, FileNotFoundError):
        return False


def _delete_local_branch(project_dir: Path, branch: str) -> bool:
    """
    Delete a local branch.

    Args:
        project_dir: Project root directory
        branch: Branch name to delete

    Returns:
        True if deletion succeeded or branch doesn't exist, False otherwise
    """
    try:
        # Check if we're currently on this branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            check=False,
        )
        current_branch = result.stdout.strip()
        if current_branch == branch:
            # Can't delete current branch
            return False

        # Delete the branch
        result = subprocess.run(
            ["git", "branch", "-d", branch],
            capture_output=True,
            text=True,
            cwd=project_dir,
            check=False,
        )
        # Success if deleted or branch doesn't exist
        return result.returncode == 0 or "not found" in result.stderr.lower()
    except (OSError, FileNotFoundError):
        return False


def _switch_to_branch(project_dir: Path, branch: str) -> tuple[bool, str]:
    """
    Switch to a different branch.

    Args:
        project_dir: Project root directory
        branch: Branch name to switch to

    Returns:
        Tuple of (success, error_message). error_message is empty on success.
    """
    try:
        result = subprocess.run(
            ["git", "switch", branch],
            capture_output=True,
            text=True,
            cwd=project_dir,
            check=False,
        )
        if result.returncode == 0:
            return (True, "")
        # Return the error message for display
        error_msg = result.stderr.strip() or result.stdout.strip()
        return (False, error_msg)
    except (OSError, FileNotFoundError) as e:
        return (False, str(e))


def _prune_remote_tracking(project_dir: Path) -> bool:
    """
    Prune stale remote-tracking branches.

    Args:
        project_dir: Project root directory

    Returns:
        True if prune succeeded
    """
    try:
        result = subprocess.run(
            ["git", "fetch", "--prune"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            check=False,
        )
        return result.returncode == 0
    except (OSError, FileNotFoundError):
        return False


class PRServiceError(Exception):
    """Error from PR service operations."""

    pass


@dataclass
class PRResult:
    """Result of a PR creation operation."""

    url: str
    number: int
    title: str
    created: bool  # True if newly created, False if existing


@dataclass
class MergeResult:
    """Result of a merge operation."""

    success: bool
    pr_number: int
    method: str
    branch_deleted: bool


class _NoOpCallback:
    """Default no-op callback implementation."""

    def on_progress(self, message: str) -> None:
        """No-op progress handler."""
        pass

    def on_status(self, message: str, level: str = "info") -> None:
        """No-op status handler."""
        pass

    def on_info(self, message: str) -> None:
        """No-op info handler."""
        pass


class PRService:
    """
    Service for managing pull requests.

    Provides high-level operations for:
    - Resolving user input (epic ID, branch, PR number) to targets
    - Creating PRs with auto-generated bodies
    - Waiting for CI and addressing reviews
    - Merging PRs and updating bindings

    Example:
        >>> service = PRService(Path.cwd())
        >>> result = service.create_pr("cub-vd6", title="My PR")
        >>> print(result.url)
    """

    def __init__(
        self,
        project_dir: Path | None = None,
        callback: PREventCallback | None = None,
        task_backend: TaskBackend | None = None,
    ) -> None:
        """
        Initialize PRService.

        Args:
            project_dir: Project directory (defaults to cwd)
            callback: Event callback for progress/status output
            task_backend: Task backend for querying tasks/epics (auto-detected if None)
        """
        self.project_dir = project_dir or Path.cwd()
        self._callback = callback or _NoOpCallback()
        self._branch_store: BranchStore | None = None
        self._github_client: GitHubClient | None = None
        self._task_backend: TaskBackend | None = task_backend

    @property
    def branch_store(self) -> BranchStore:
        """Get branch store (lazy initialization)."""
        if self._branch_store is None:
            self._branch_store = BranchStore(self.project_dir)
        return self._branch_store

    @property
    def github_client(self) -> GitHubClient:
        """Get GitHub client (lazy initialization)."""
        if self._github_client is None:
            self._github_client = GitHubClient.from_project_dir(self.project_dir)
        return self._github_client

    @property
    def task_backend(self) -> TaskBackend:
        """Get task backend (lazy initialization)."""
        if self._task_backend is None:
            self._task_backend = get_backend(project_dir=self.project_dir)
        return self._task_backend

    def resolve_input(self, target: str | None) -> ResolvedTarget:
        """
        Resolve user input to a target (epic, branch, or PR).

        Resolution order:
        1. If None, use current branch
        2. If looks like PR number (digits or #digits), return as PR
        3. Check branch bindings for epic ID
        4. Check branch bindings for branch name
        5. Check if valid git branch
        6. Assume unbound epic ID

        Args:
            target: User input (epic ID, branch, PR number, or None)

        Returns:
            ResolvedTarget with resolved information
        """
        # 1. If None, use current branch
        if target is None:
            branch = BranchStore.get_current_branch()
            if branch is None:
                raise PRServiceError("Could not determine current branch")
            target = branch

        # 2. If looks like PR number
        stripped = target.lstrip("#")
        if stripped.isdigit():
            return ResolvedTarget(type="pr", pr_number=int(stripped))

        # 3. Check branch bindings for epic ID
        binding = self.branch_store.get_binding(target)
        if binding:
            return ResolvedTarget(
                type="epic",
                epic_id=target,
                branch=binding.branch_name,
                binding=binding,
            )

        # 4. Check branch bindings for branch name
        binding = self.branch_store.get_binding_by_branch(target)
        if binding:
            return ResolvedTarget(
                type="branch",
                branch=target,
                epic_id=binding.epic_id,
                binding=binding,
            )

        # 5. Check if valid git branch
        if BranchStore.git_branch_exists(target):
            return ResolvedTarget(type="branch", branch=target, binding=None)

        # 6. Assume unbound epic ID
        return ResolvedTarget(type="epic", epic_id=target, binding=None)

    def generate_pr_body(
        self,
        epic_id: str | None,
        branch: str,
        base: str = "main",
    ) -> str:
        """
        Generate PR body from commits, file changes, and epic tasks.

        Args:
            epic_id: Epic ID to generate body for (optional)
            branch: Branch name (head)
            base: Base branch name for comparison

        Returns:
            Markdown PR body
        """
        # Get epic info if available
        epic_title = "Pull Request"
        epic_description = ""
        completed_tasks: list[dict[str, str]] = []

        if epic_id:
            try:
                epic = self.task_backend.get_task(epic_id)
                if epic:
                    epic_title = epic.title
                    epic_description = epic.description
            except Exception:
                pass

            # Get closed child tasks
            try:
                closed_tasks = self.task_backend.list_tasks(
                    status=TaskStatus.CLOSED, parent=epic_id
                )
                completed_tasks = [
                    {"id": t.id, "title": t.title} for t in closed_tasks
                ]
            except Exception:
                pass

        # Get git information
        commits = self.github_client.get_commits_between(base, branch)
        files_changed = self.github_client.get_files_changed(base, branch)
        diff_stat = self.github_client.get_diff_stat(base, branch)

        # Build PR body
        body_parts = ["## Summary\n"]
        if epic_description:
            body_parts.append(f"{epic_description}\n")
        else:
            body_parts.append(f"{epic_title}\n")

        # Add diff statistics
        if diff_stat["files"] > 0:
            stat_parts = [f"{diff_stat['files']} file(s) changed"]
            if diff_stat["insertions"] > 0:
                stat_parts.append(f"+{diff_stat['insertions']}")
            if diff_stat["deletions"] > 0:
                stat_parts.append(f"-{diff_stat['deletions']}")
            body_parts.append(f"\n**Stats:** {', '.join(stat_parts)}\n")

        body_parts.append("\n## Changes\n")

        # Add commits section
        if commits:
            body_parts.append(f"### Commits ({len(commits)})\n")
            for commit in commits:
                body_parts.append(f"- `{commit['sha']}` {commit['subject']}\n")
            body_parts.append("\n")

        # Add completed tasks if available
        if completed_tasks:
            body_parts.append(f"### Completed Tasks ({len(completed_tasks)})\n")
            for task in completed_tasks:
                body_parts.append(f"- [x] {task['id']}: {task['title']}\n")
            body_parts.append("\n")

        # Add files changed section
        total_files = (
            len(files_changed["added"])
            + len(files_changed["modified"])
            + len(files_changed["deleted"])
        )
        if total_files > 0:
            body_parts.append("### Files Changed\n")

            # Group files by directory for cleaner output
            if files_changed["added"]:
                body_parts.append(
                    f"**Added ({len(files_changed['added'])}):** "
                    f"{', '.join(self._format_file_list(files_changed['added']))}\n"
                )
            if files_changed["modified"]:
                body_parts.append(
                    f"**Modified ({len(files_changed['modified'])}):** "
                    f"{', '.join(self._format_file_list(files_changed['modified']))}\n"
                )
            if files_changed["deleted"]:
                body_parts.append(
                    f"**Deleted ({len(files_changed['deleted'])}):** "
                    f"{', '.join(self._format_file_list(files_changed['deleted']))}\n"
                )

        body_parts.append("""
## Test Plan

- [ ] Code builds without errors
- [ ] Tests pass
- [ ] Manual testing completed

---
Generated with [cub](https://github.com/lavallee/cub)
""")

        return "".join(body_parts)

    def _format_file_list(self, files: list[str], max_files: int = 10) -> list[str]:
        """
        Format a list of files for display.

        Args:
            files: List of file paths
            max_files: Maximum number of files to show before truncating

        Returns:
            List of formatted file names (with code formatting)
        """
        if len(files) <= max_files:
            return [f"`{f}`" for f in files]
        else:
            displayed = [f"`{f}`" for f in files[:max_files]]
            displayed.append(f"... and {len(files) - max_files} more")
            return displayed

    def create_pr(
        self,
        target: str | None = None,
        title: str | None = None,
        base: str | None = None,
        draft: bool = False,
        push: bool = False,
        dry_run: bool = False,
    ) -> PRResult:
        """
        Create a pull request.

        Args:
            target: Epic ID, branch name, or None for current branch
            title: PR title (auto-generated if not provided)
            base: Target branch (from binding or main if not provided)
            draft: Create as draft PR
            push: Push branch before creating PR
            dry_run: Show what would be done without making changes

        Returns:
            PRResult with URL, number, and creation status

        Raises:
            PRServiceError: If PR cannot be created
        """
        # Resolve input
        self._callback.on_progress("Resolving target...")
        logger.debug(f"target={target!r}")
        resolved = self.resolve_input(target)
        logger.debug(f"resolved.type={resolved.type!r}")
        logger.debug(f"resolved.branch={resolved.branch!r}")
        logger.debug(f"resolved.epic_id={resolved.epic_id!r}")
        logger.debug(f"resolved.binding={resolved.binding!r}")

        # Get branch name
        branch = resolved.branch
        if not branch:
            if resolved.type == "pr":
                # Already have a PR - get its branch
                self._callback.on_progress(f"Looking up existing PR #{resolved.pr_number}...")
                pr_info = self.github_client.get_pr(resolved.pr_number or 0)
                logger.debug(f"pr_info={pr_info!r}")
                if pr_info:
                    return PRResult(
                        url=str(pr_info.get("url", "")),
                        number=int(pr_info.get("number") or 0),
                        title=str(pr_info.get("title", "")),
                        created=False,
                    )
                raise PRServiceError(f"PR #{resolved.pr_number} not found")
            raise PRServiceError(
                f"No branch found for {target}. Bind a branch first with: cub branch <epic-id>"
            )

        # Get base branch
        if not base:
            if resolved.binding:
                base = resolved.binding.base_branch
                logger.debug(f"Using base branch from binding: {base}")
            else:
                base = "main"
                logger.debug("Using default base branch: main")
        # Strip remote prefix (e.g. "origin/main" -> "main") since
        # gh pr create --base expects a bare branch name
        if "/" in base:
            base = base.split("/", 1)[1]
        logger.debug(f"base={base!r}")

        # Check for existing PR
        self._callback.on_progress(f"Checking for existing PR ({branch} -> {base})...")
        existing_pr = self.github_client.get_pr_by_branch(branch, base)
        logger.debug(f"existing_pr={existing_pr!r}")
        if existing_pr:
            pr_number = existing_pr.get("number")
            pr_url = existing_pr.get("url")
            pr_title = existing_pr.get("title")
            self._callback.on_info(f"PR #{pr_number} already exists: {pr_url}")

            # Update binding if needed
            if resolved.binding and resolved.binding.pr_number != pr_number:
                logger.debug(
                    f"Updating binding PR number from {resolved.binding.pr_number} to {pr_number}"
                )
                if not dry_run:
                    self.branch_store.update_pr(
                        resolved.epic_id or resolved.binding.epic_id,
                        int(pr_number or 0),
                    )

            return PRResult(
                url=str(pr_url),
                number=int(pr_number or 0),
                title=str(pr_title),
                created=False,
            )

        # Check if on correct branch
        self._callback.on_progress("Validating current branch...")
        current_branch = BranchStore.get_current_branch()
        logger.debug(f"current_branch={current_branch!r}")
        logger.debug(f"expected_branch={branch!r}")
        if current_branch != branch:
            raise PRServiceError(
                f"Not on expected branch.\n"
                f"  Current: {current_branch}\n"
                f"  Expected: {branch}\n"
                f"Switch first: git checkout {branch}"
            )

        # Push if needed
        self._callback.on_progress("Checking if branch needs push...")
        needs_push = self.github_client.needs_push(branch)
        logger.debug(f"needs_push={needs_push!r}")
        logger.debug(f"push_flag={push!r}")
        if push or needs_push:
            if dry_run:
                self._callback.on_info(f"[dry-run] Would push branch {branch}")
            else:
                self._callback.on_progress(f"Pushing branch {branch} to origin...")
                self._callback.on_info(f"Pushing branch {branch} to origin...")
                self.github_client.push_branch(branch)
                self._callback.on_status("Branch pushed", level="success")

        # Verify branch is on remote
        self._callback.on_progress("Verifying branch exists on remote...")
        if not dry_run:
            branch_on_remote = self.github_client.branch_exists_on_remote(branch)
            logger.debug(f"branch_on_remote={branch_on_remote!r}")
            if not branch_on_remote:
                raise PRServiceError(
                    f"Branch {branch} is not on remote.\n"
                    "Push it first with: git push -u origin {branch}\n"
                    "Or use --push flag."
                )

        # Get title
        self._callback.on_progress("Determining PR title...")
        if not title:
            if resolved.epic_id:
                # Get title from task backend
                logger.debug(f"Fetching epic info: {resolved.epic_id}")
                try:
                    epic = self.task_backend.get_task(resolved.epic_id)
                    if epic:
                        title = epic.title
                        logger.debug(f"Got epic title: {title!r}")
                    else:
                        title = resolved.epic_id
                except Exception as e:
                    logger.debug(f"Failed to get epic title: {e}")
                    title = resolved.epic_id
            else:
                title = branch
        logger.debug(f"title={title!r}")

        # Generate body
        self._callback.on_progress("Generating PR body...")
        body = self.generate_pr_body(resolved.epic_id, branch, base)
        logger.debug(f"Generated PR body ({len(body)} chars)")

        if dry_run:
            self._callback.on_info("[dry-run] Would create PR:")
            self._callback.on_info(f"  Title: {title}")
            self._callback.on_info(f"  Head: {branch}")
            self._callback.on_info(f"  Base: {base}")
            self._callback.on_info(f"  Draft: {draft}")
            return PRResult(
                url="(dry-run)",
                number=0,
                title=title or "",
                created=True,
            )

        # Create PR
        self._callback.on_progress("Creating PR via GitHub API...")
        self._callback.on_info(f"Creating PR: {title}")
        self._callback.on_info(f"  {branch} -> {base}")
        logger.debug(f"draft={draft!r}")

        try:
            result = self.github_client.create_pr(
                head=branch,
                base=base,
                title=title or branch,
                body=body,
                draft=draft,
            )
            logger.debug(f"gh_pr_create_result={result!r}")
        except GitHubClientError as e:
            logger.debug(f"GitHub API error: {e}")
            raise PRServiceError(str(e))

        pr_url = str(result["url"])
        pr_number = int(result["number"])

        # Update binding with PR number
        if resolved.binding and resolved.epic_id:
            self._callback.on_progress("Updating branch binding with PR number...")
            logger.debug(f"Setting PR #{pr_number} on epic {resolved.epic_id}")
            self.branch_store.update_pr(resolved.epic_id, pr_number)

        self._callback.on_status(f"PR #{pr_number} created", level="success")
        self._callback.on_info(f"  {pr_url}")

        return PRResult(
            url=pr_url,
            number=pr_number,
            title=title or branch,
            created=True,
        )

    def get_claude_ci_prompt(
        self,
        pr_number: int,
        branch: str,
        base: str,
    ) -> str:
        """
        Generate Claude prompt for CI/review handling.

        Args:
            pr_number: PR number
            branch: Head branch name
            base: Base branch name

        Returns:
            Prompt string for Claude
        """
        return f"""You are managing PR #{pr_number} for branch '{branch}' -> '{base}'.

1. Wait for CI: gh pr checks {branch} --watch
   If failures: analyze logs, fix code, push, repeat

2. Address reviews: gh pr view {branch} --comments
   If comments need action: make changes, push, respond

3. Report when ready to merge (CI green, reviews addressed)"""

    def merge_pr(
        self,
        target: str,
        method: str = "squash",
        delete_branch: bool = True,
        dry_run: bool = False,
    ) -> MergeResult:
        """
        Merge a pull request.

        Args:
            target: Epic ID, branch name, or PR number
            method: Merge method (squash, merge, rebase)
            delete_branch: Delete branch after merge
            dry_run: Show what would be done

        Returns:
            MergeResult with merge status

        Raises:
            PRServiceError: If merge fails
        """
        # Resolve input
        resolved = self.resolve_input(target)

        # Get PR number
        pr_number: int | None = None

        if resolved.type == "pr":
            pr_number = resolved.pr_number
        elif resolved.binding and resolved.binding.pr_number:
            pr_number = resolved.binding.pr_number
        else:
            # Try to find PR by branch
            branch = resolved.branch
            if branch:
                base = resolved.binding.base_branch if resolved.binding else "main"
                existing = self.github_client.get_pr_by_branch(branch, base)
                if existing:
                    pr_number = int(existing.get("number") or 0)

        if not pr_number:
            raise PRServiceError(
                f"No PR found for {target}. Create one first with: cub pr {target}"
            )

        # Verify PR exists and is mergeable
        pr_info = self.github_client.get_pr(pr_number)
        if not pr_info:
            raise PRServiceError(f"PR #{pr_number} not found")

        pr_state = pr_info.get("state")
        if pr_state == "MERGED":
            self._callback.on_info(f"PR #{pr_number} is already merged")
            return MergeResult(
                success=True,
                pr_number=pr_number,
                method=method,
                branch_deleted=True,
            )

        if pr_state == "CLOSED":
            raise PRServiceError(f"PR #{pr_number} is closed (not merged)")

        # Check CI status
        checks = self.github_client.get_pr_checks(pr_number)
        failed_checks = [
            c for c in checks if c.get("conclusion") not in ("success", "skipped", None)
        ]
        pending_checks = [c for c in checks if c.get("status") != "completed"]

        if pending_checks:
            self._callback.on_status(
                f"Warning: {len(pending_checks)} check(s) still pending",
                level="warning",
            )

        if failed_checks:
            self._callback.on_status(
                f"Warning: {len(failed_checks)} check(s) failed",
                level="warning",
            )
            for check in failed_checks:
                self._callback.on_info(f"  - {check.get('name')}: {check.get('conclusion')}")

        if dry_run:
            self._callback.on_info(f"[dry-run] Would merge PR #{pr_number}")
            self._callback.on_info(f"  Method: {method}")
            self._callback.on_info(f"  Delete branch: {delete_branch}")
            return MergeResult(
                success=True,
                pr_number=pr_number,
                method=method,
                branch_deleted=delete_branch,
            )

        # Merge
        self._callback.on_info(f"Merging PR #{pr_number} ({method})...")

        try:
            self.github_client.merge_pr(
                pr_number=pr_number,
                method=method,
                delete_branch=delete_branch,
            )
        except GitHubClientError as e:
            raise PRServiceError(str(e))

        # Update binding status
        if resolved.binding and resolved.epic_id:
            self.branch_store.update_status(resolved.epic_id, "merged")

        self._callback.on_status(f"PR #{pr_number} merged", level="success")

        # Post-merge cleanup: update local main and clean up branches
        base_branch = resolved.binding.base_branch if resolved.binding else "main"
        feature_branch = resolved.branch

        # Update main in worktree (if worktree exists)
        main_worktree = _find_worktree_for_branch(self.project_dir, base_branch)
        if main_worktree:
            self._callback.on_info(f"Updating {base_branch} in worktree...")
            if _update_worktree(main_worktree):
                self._callback.on_status(f"{base_branch} updated", level="success")
            else:
                self._callback.on_status(
                    f"Could not update {base_branch} worktree",
                    level="warning",
                )

        # Prune stale remote-tracking branches
        _prune_remote_tracking(self.project_dir)

        # Try to switch to base branch before deleting feature branch
        # This allows the feature branch to be deleted since we can't delete the current branch
        switched_to_base = False
        if feature_branch:
            # Check if we're on the feature branch
            try:
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_dir,
                    check=False,
                )
                current_branch = result.stdout.strip()
                if current_branch == feature_branch:
                    # We're on the feature branch, try to switch to base
                    success, error_msg = _switch_to_branch(self.project_dir, base_branch)
                    if success:
                        self._callback.on_info(f"Switched to {base_branch}")
                        switched_to_base = True
                    else:
                        # Branch switch failed - this is OK, merge succeeded
                        self._callback.on_status(
                            f"Could not switch to {base_branch}",
                            level="warning",
                        )
                        if error_msg:
                            self._callback.on_info(f"  {error_msg}")
                        self._callback.on_info(f"  Staying on {feature_branch}")
            except (OSError, FileNotFoundError):
                pass  # Can't determine current branch, continue without switching

        # Delete local feature branch if delete_branch was requested
        if delete_branch and feature_branch:
            if _delete_local_branch(self.project_dir, feature_branch):
                self._callback.on_info(f"Deleted local branch {feature_branch}")
            else:
                if switched_to_base:
                    # We switched but still couldn't delete - unexpected
                    self._callback.on_status(
                        f"Could not delete local branch {feature_branch}",
                        level="warning",
                    )
                else:
                    # Expected - we're still on the branch
                    self._callback.on_info(
                        f"Local branch {feature_branch} kept (still on this branch)"
                    )

        return MergeResult(
            success=True,
            pr_number=pr_number,
            method=method,
            branch_deleted=delete_branch,
        )
