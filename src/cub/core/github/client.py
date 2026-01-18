"""
GitHub CLI wrapper for cub.

Provides functions to interact with GitHub via the `gh` CLI tool.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from cub.core.github.models import GitHubIssue, RepoInfo


class GitHubClientError(Exception):
    """Error from GitHub client operations."""

    pass


class GitHubClient:
    """
    Client for GitHub operations via `gh` CLI.

    Wraps the GitHub CLI (`gh`) to provide issue management operations.
    Requires `gh` to be installed and authenticated.

    Example:
        >>> client = GitHubClient.from_project_dir(Path.cwd())
        >>> issue = client.get_issue(123)
        >>> print(issue.title)
    """

    def __init__(self, repo: RepoInfo) -> None:
        """
        Initialize GitHubClient.

        Args:
            repo: Repository information
        """
        self.repo = repo

    @classmethod
    def from_project_dir(cls, project_dir: Path | None = None) -> GitHubClient:
        """
        Create client from project directory by parsing git remote.

        Args:
            project_dir: Project directory (defaults to cwd)

        Returns:
            GitHubClient instance

        Raises:
            GitHubClientError: If not a GitHub repository or gh not available
        """
        if project_dir is None:
            project_dir = Path.cwd()

        # Check gh is available
        if not cls.is_gh_available():
            raise GitHubClientError(
                "GitHub CLI (gh) is not installed or not authenticated.\n"
                "Install: https://cli.github.com/\n"
                "Authenticate: gh auth login"
            )

        # Get remote URL
        remote_url = cls._get_remote_url(project_dir)
        if not remote_url:
            raise GitHubClientError("No git remote 'origin' found. Is this a git repository?")

        # Parse repo info
        repo = RepoInfo.from_remote_url(remote_url)
        if not repo:
            raise GitHubClientError(
                f"Remote URL is not a GitHub repository: {remote_url}\n"
                "--gh-issue requires a GitHub repository."
            )

        return cls(repo)

    @staticmethod
    def is_gh_available() -> bool:
        """
        Check if GitHub CLI is installed and authenticated.

        Returns:
            True if gh is available and authenticated
        """
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except (OSError, FileNotFoundError):
            return False

    @staticmethod
    def _get_remote_url(project_dir: Path) -> str | None:
        """
        Get git remote origin URL.

        Args:
            project_dir: Project directory

        Returns:
            Remote URL or None
        """
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (OSError, FileNotFoundError):
            return None

    def get_issue(self, issue_number: int) -> GitHubIssue:
        """
        Fetch issue details from GitHub.

        Args:
            issue_number: Issue number to fetch

        Returns:
            GitHubIssue instance

        Raises:
            GitHubClientError: If issue not found or API error
        """
        api_path = f"repos/{self.repo.owner}/{self.repo.repo}/issues/{issue_number}"

        try:
            result = subprocess.run(
                ["gh", "api", api_path],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown error"
                if "404" in error_msg or "Not Found" in error_msg:
                    raise GitHubClientError(f"Issue #{issue_number} not found")
                raise GitHubClientError(f"Failed to fetch issue: {error_msg}")

            data = json.loads(result.stdout)
            return GitHubIssue.from_gh_api(data)

        except json.JSONDecodeError as e:
            raise GitHubClientError(f"Failed to parse GitHub API response: {e}")
        except (OSError, FileNotFoundError) as e:
            raise GitHubClientError(f"Failed to run gh command: {e}")

    def add_comment(self, issue_number: int, body: str) -> None:
        """
        Add a comment to an issue.

        Args:
            issue_number: Issue number
            body: Comment body (markdown supported)

        Raises:
            GitHubClientError: If comment could not be added
        """
        api_path = f"repos/{self.repo.owner}/{self.repo.repo}/issues/{issue_number}/comments"

        try:
            result = subprocess.run(
                ["gh", "api", api_path, "-f", f"body={body}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown error"
                raise GitHubClientError(f"Failed to add comment: {error_msg}")

        except (OSError, FileNotFoundError) as e:
            raise GitHubClientError(f"Failed to run gh command: {e}")

    def close_issue(self, issue_number: int) -> None:
        """
        Close an issue.

        Args:
            issue_number: Issue number to close

        Raises:
            GitHubClientError: If issue could not be closed
        """
        api_path = f"repos/{self.repo.owner}/{self.repo.repo}/issues/{issue_number}"

        try:
            result = subprocess.run(
                ["gh", "api", api_path, "-X", "PATCH", "-f", "state=closed"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown error"
                raise GitHubClientError(f"Failed to close issue: {error_msg}")

        except (OSError, FileNotFoundError) as e:
            raise GitHubClientError(f"Failed to run gh command: {e}")

    def get_current_branch(self) -> str | None:
        """
        Get current git branch name.

        Returns:
            Branch name or None if not in a git repo
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (OSError, FileNotFoundError):
            return None

    def get_head_commit(self) -> str | None:
        """
        Get current HEAD commit SHA.

        Returns:
            Commit SHA or None
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (OSError, FileNotFoundError):
            return None

    def create_pr(
        self,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool = False,
    ) -> dict[str, str | int]:
        """
        Create a pull request.

        Args:
            head: Source branch name
            base: Target branch name
            title: PR title
            body: PR body (markdown)
            draft: Create as draft PR

        Returns:
            Dict with 'url' and 'number' keys

        Raises:
            GitHubClientError: If PR creation fails
        """
        cmd = [
            "gh",
            "pr",
            "create",
            "--head",
            head,
            "--base",
            base,
            "--title",
            title,
            "--body",
            body,
        ]
        if draft:
            cmd.append("--draft")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                raise GitHubClientError(f"Failed to create PR: {error_msg}")

            # Output is the PR URL
            pr_url = result.stdout.strip()

            # Extract PR number from URL
            pr_number: int | None = None
            if "/pull/" in pr_url:
                try:
                    pr_number = int(pr_url.split("/pull/")[-1].split("/")[0])
                except ValueError:
                    pass

            return {"url": pr_url, "number": pr_number or 0}

        except (OSError, FileNotFoundError) as e:
            raise GitHubClientError(f"Failed to run gh command: {e}")

    def get_pr_by_branch(
        self,
        branch: str,
        base: str = "main",
    ) -> dict[str, str | int | None] | None:
        """
        Get an existing PR for a branch.

        Args:
            branch: Head branch name
            base: Base branch name

        Returns:
            Dict with PR info or None if no PR exists
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--head",
                    branch,
                    "--base",
                    base,
                    "--json",
                    "number,url,title,state",
                    "--jq",
                    ".[0]",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return None

            output = result.stdout.strip()
            if not output or output == "null":
                return None

            data = json.loads(output)
            return {
                "number": data.get("number"),
                "url": data.get("url"),
                "title": data.get("title"),
                "state": data.get("state"),
            }

        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return None

    def get_pr(self, pr_ref: str | int) -> dict[str, str | int | None] | None:
        """
        Get PR details by number or branch.

        Args:
            pr_ref: PR number or branch name

        Returns:
            Dict with PR info or None if not found
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_ref),
                    "--json",
                    "number,url,title,state,headRefName,baseRefName,mergeable",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)
            return {
                "number": data.get("number"),
                "url": data.get("url"),
                "title": data.get("title"),
                "state": data.get("state"),
                "head": data.get("headRefName"),
                "base": data.get("baseRefName"),
                "mergeable": data.get("mergeable"),
            }

        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return None

    def get_pr_checks(self, pr_ref: str | int) -> list[dict[str, str]]:
        """
        Get CI check status for a PR.

        Args:
            pr_ref: PR number or branch name

        Returns:
            List of check dicts with 'name', 'status', 'conclusion' keys
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "checks",
                    str(pr_ref),
                    "--json",
                    "name,status,conclusion",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return []

            checks: list[dict[str, str]] = json.loads(result.stdout)
            return checks

        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return []

    def wait_for_checks(self, pr_ref: str | int, timeout: int = 600) -> bool:
        """
        Wait for PR checks to complete.

        Args:
            pr_ref: PR number or branch name
            timeout: Timeout in seconds

        Returns:
            True if all checks passed, False otherwise
        """
        try:
            result = subprocess.run(
                ["gh", "pr", "checks", str(pr_ref), "--watch"],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except (OSError, FileNotFoundError):
            return False

    def merge_pr(
        self,
        pr_number: int,
        method: str = "squash",
        delete_branch: bool = True,
    ) -> bool:
        """
        Merge a pull request.

        Args:
            pr_number: PR number to merge
            method: Merge method (squash, merge, rebase)
            delete_branch: Delete branch after merge

        Returns:
            True if merge succeeded

        Raises:
            GitHubClientError: If merge fails
        """
        cmd = ["gh", "pr", "merge", str(pr_number), f"--{method}"]
        if delete_branch:
            cmd.append("--delete-branch")
        else:
            cmd.append("--no-delete-branch")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                raise GitHubClientError(f"Failed to merge PR: {error_msg}")

            return True

        except (OSError, FileNotFoundError) as e:
            raise GitHubClientError(f"Failed to run gh command: {e}")

    def needs_push(self, branch: str) -> bool:
        """
        Check if a branch needs to be pushed to remote.

        Args:
            branch: Branch name to check

        Returns:
            True if branch has unpushed commits or no upstream
        """
        try:
            # Check if upstream exists
            result = subprocess.run(
                [
                    "git",
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    f"{branch}@{{upstream}}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return True  # No upstream means needs push

            upstream = result.stdout.strip()

            # Check if local is ahead of remote
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{upstream}..{branch}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return True

            ahead_count = int(result.stdout.strip())
            return ahead_count > 0

        except (OSError, FileNotFoundError, ValueError):
            return True

    def push_branch(self, branch: str) -> None:
        """
        Push a branch to origin.

        Args:
            branch: Branch name to push

        Raises:
            GitHubClientError: If push fails
        """
        try:
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown error"
                raise GitHubClientError(f"Failed to push branch: {error_msg}")

        except (OSError, FileNotFoundError) as e:
            raise GitHubClientError(f"Failed to run git command: {e}")

    def branch_exists_on_remote(self, branch: str) -> bool:
        """
        Check if a branch exists on the remote.

        Args:
            branch: Branch name to check

        Returns:
            True if branch exists on origin
        """
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", branch],
                capture_output=True,
                text=True,
                check=False,
            )
            return bool(result.stdout.strip())
        except (OSError, FileNotFoundError):
            return False

    def get_commits_between(
        self,
        base: str,
        head: str,
        max_commits: int = 50,
    ) -> list[dict[str, str]]:
        """
        Get commits between base and head branches.

        Args:
            base: Base branch name
            head: Head branch name
            max_commits: Maximum number of commits to return

        Returns:
            List of commit dicts with 'sha', 'subject', 'body' keys
        """
        try:
            # Format: hash|subject|body (body separated by newlines)
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"{base}..{head}",
                    f"--max-count={max_commits}",
                    "--format=%H|%s|%b%x00",  # null separator between commits
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return []

            commits = []
            # Split by null character, filter empty
            for entry in result.stdout.split("\x00"):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split("|", 2)
                if len(parts) >= 2:
                    commits.append(
                        {
                            "sha": parts[0][:7],  # Short SHA
                            "subject": parts[1],
                            "body": parts[2].strip() if len(parts) > 2 else "",
                        }
                    )

            return commits

        except (OSError, FileNotFoundError):
            return []

    def get_files_changed(
        self,
        base: str,
        head: str,
    ) -> dict[str, list[str]]:
        """
        Get files changed between base and head branches.

        Args:
            base: Base branch name
            head: Head branch name

        Returns:
            Dict with 'added', 'modified', 'deleted' lists of file paths
        """
        try:
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    f"{base}...{head}",
                    "--name-status",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return {"added": [], "modified": [], "deleted": []}

            added: list[str] = []
            modified: list[str] = []
            deleted: list[str] = []

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                status = parts[0]
                if status.startswith("A"):
                    added.append(parts[1])
                elif status.startswith("D"):
                    deleted.append(parts[1])
                elif status.startswith("M"):
                    modified.append(parts[1])
                elif status.startswith("R"):
                    # Renames have format: Rnn<tab>old_name<tab>new_name
                    # Use the new name (the renamed-to file)
                    if len(parts) >= 3:
                        modified.append(parts[2])
                    else:
                        modified.append(parts[1])

            return {"added": added, "modified": modified, "deleted": deleted}

        except (OSError, FileNotFoundError):
            return {"added": [], "modified": [], "deleted": []}

    def get_diff_stat(self, base: str, head: str) -> dict[str, int]:
        """
        Get diff statistics between base and head branches.

        Args:
            base: Base branch name
            head: Head branch name

        Returns:
            Dict with 'files', 'insertions', 'deletions' counts
        """
        try:
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    f"{base}...{head}",
                    "--shortstat",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return {"files": 0, "insertions": 0, "deletions": 0}

            output = result.stdout.strip()
            if not output:
                return {"files": 0, "insertions": 0, "deletions": 0}

            # Parse "X files changed, Y insertions(+), Z deletions(-)"
            files = insertions = deletions = 0

            if match := re.search(r"(\d+) files? changed", output):
                files = int(match.group(1))
            if match := re.search(r"(\d+) insertions?\(\+\)", output):
                insertions = int(match.group(1))
            if match := re.search(r"(\d+) deletions?\(-\)", output):
                deletions = int(match.group(1))

            return {"files": files, "insertions": insertions, "deletions": deletions}

        except (OSError, FileNotFoundError):
            return {"files": 0, "insertions": 0, "deletions": 0}
