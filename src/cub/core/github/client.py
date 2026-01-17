"""
GitHub CLI wrapper for cub.

Provides functions to interact with GitHub via the `gh` CLI tool.
"""

from __future__ import annotations

import json
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
