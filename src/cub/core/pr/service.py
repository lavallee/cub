"""
PR service for managing pull requests.

Provides high-level operations for creating, managing, and merging
pull requests with optional CI/review handling via Claude.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from cub.core.branches import BranchStore, ResolvedTarget
from cub.core.github.client import GitHubClient, GitHubClientError


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

    def __init__(self, project_dir: Path | None = None) -> None:
        """
        Initialize PRService.

        Args:
            project_dir: Project directory (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self._console = Console()
        self._branch_store: BranchStore | None = None
        self._github_client: GitHubClient | None = None

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
    ) -> str:
        """
        Generate PR body from epic tasks.

        Args:
            epic_id: Epic ID to generate body for (optional)
            branch: Branch name for commits summary

        Returns:
            Markdown PR body
        """
        # Get epic info if available
        epic_title = "Pull Request"
        epic_description = ""
        completed_tasks: list[dict[str, str]] = []

        if epic_id:
            # Try to get epic from beads
            try:
                result = subprocess.run(
                    ["bd", "show", epic_id, "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    epic_data = json.loads(result.stdout)
                    epic_title = epic_data.get("title", epic_id)
                    epic_description = epic_data.get("description", "")
            except (json.JSONDecodeError, OSError, FileNotFoundError):
                pass

            # Get closed child tasks
            try:
                result = subprocess.run(
                    ["bd", "list", "--parent", epic_id, "--status", "closed", "--json"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    tasks = json.loads(result.stdout)
                    completed_tasks = [
                        {"id": t.get("id", ""), "title": t.get("title", "")} for t in tasks
                    ]
            except (json.JSONDecodeError, OSError, FileNotFoundError):
                pass

        # Build PR body
        body_parts = ["## Summary\n"]
        if epic_description:
            body_parts.append(f"{epic_description}\n")
        else:
            body_parts.append(f"{epic_title}\n")

        body_parts.append("\n## Changes\n")

        if completed_tasks:
            body_parts.append(f"### Completed Tasks ({len(completed_tasks)})\n")
            for task in completed_tasks:
                body_parts.append(f"- [x] {task['id']}: {task['title']}\n")
        else:
            body_parts.append("See commits for details.\n")

        body_parts.append("""
## Test Plan

- [ ] Code builds without errors
- [ ] Tests pass
- [ ] Manual testing completed

---
Generated with [cub](https://github.com/lavallee/cub)
""")

        return "".join(body_parts)

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
        resolved = self.resolve_input(target)

        # Get branch name
        branch = resolved.branch
        if not branch:
            if resolved.type == "pr":
                # Already have a PR - get its branch
                pr_info = self.github_client.get_pr(resolved.pr_number or 0)
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
            else:
                base = "main"

        # Check for existing PR
        existing_pr = self.github_client.get_pr_by_branch(branch, base)
        if existing_pr:
            pr_number = existing_pr.get("number")
            pr_url = existing_pr.get("url")
            pr_title = existing_pr.get("title")
            self._console.print(f"PR #{pr_number} already exists: {pr_url}")

            # Update binding if needed
            if resolved.binding and resolved.binding.pr_number != pr_number:
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
        current_branch = BranchStore.get_current_branch()
        if current_branch != branch:
            raise PRServiceError(
                f"Not on expected branch.\n"
                f"  Current: {current_branch}\n"
                f"  Expected: {branch}\n"
                f"Switch first: git checkout {branch}"
            )

        # Push if needed
        if push or self.github_client.needs_push(branch):
            if dry_run:
                self._console.print(f"[dry-run] Would push branch {branch}")
            else:
                self._console.print(f"Pushing branch {branch} to origin...")
                self.github_client.push_branch(branch)
                self._console.print("[green]Branch pushed[/green]")

        # Verify branch is on remote
        if not dry_run and not self.github_client.branch_exists_on_remote(branch):
            raise PRServiceError(
                f"Branch {branch} is not on remote.\n"
                "Push it first with: git push -u origin {branch}\n"
                "Or use --push flag."
            )

        # Get title
        if not title:
            if resolved.epic_id:
                # Try to get from beads
                try:
                    bd_result = subprocess.run(
                        ["bd", "show", resolved.epic_id, "--json"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if bd_result.returncode == 0:
                        epic_data = json.loads(bd_result.stdout)
                        title = epic_data.get("title", resolved.epic_id)
                except (json.JSONDecodeError, OSError, FileNotFoundError):
                    title = resolved.epic_id
            else:
                title = branch

        # Generate body
        body = self.generate_pr_body(resolved.epic_id, branch)

        if dry_run:
            self._console.print("[dry-run] Would create PR:")
            self._console.print(f"  Title: {title}")
            self._console.print(f"  Head: {branch}")
            self._console.print(f"  Base: {base}")
            self._console.print(f"  Draft: {draft}")
            return PRResult(
                url="(dry-run)",
                number=0,
                title=title or "",
                created=True,
            )

        # Create PR
        self._console.print(f"Creating PR: {title}")
        self._console.print(f"  {branch} -> {base}")

        try:
            result = self.github_client.create_pr(
                head=branch,
                base=base,
                title=title or branch,
                body=body,
                draft=draft,
            )
        except GitHubClientError as e:
            raise PRServiceError(str(e))

        pr_url = str(result["url"])
        pr_number = int(result["number"])

        # Update binding with PR number
        if resolved.binding and resolved.epic_id:
            self.branch_store.update_pr(resolved.epic_id, pr_number)

        self._console.print(f"[green]PR #{pr_number} created[/green]")
        self._console.print(f"  {pr_url}")

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
            self._console.print(f"PR #{pr_number} is already merged")
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
            self._console.print(
                f"[yellow]Warning: {len(pending_checks)} check(s) still pending[/yellow]"
            )

        if failed_checks:
            self._console.print(f"[red]Warning: {len(failed_checks)} check(s) failed[/red]")
            for check in failed_checks:
                self._console.print(f"  - {check.get('name')}: {check.get('conclusion')}")

        if dry_run:
            self._console.print(f"[dry-run] Would merge PR #{pr_number}")
            self._console.print(f"  Method: {method}")
            self._console.print(f"  Delete branch: {delete_branch}")
            return MergeResult(
                success=True,
                pr_number=pr_number,
                method=method,
                branch_deleted=delete_branch,
            )

        # Merge
        self._console.print(f"Merging PR #{pr_number} ({method})...")

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

        self._console.print(f"[green]PR #{pr_number} merged[/green]")

        return MergeResult(
            success=True,
            pr_number=pr_number,
            method=method,
            branch_deleted=delete_branch,
        )
