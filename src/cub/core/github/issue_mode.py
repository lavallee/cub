"""
GitHub Issue Mode for cub.

Provides single-issue execution mode for working on GitHub issues directly.
"""

from __future__ import annotations

from pathlib import Path

from cub.core.github.client import GitHubClient, GitHubClientError
from cub.core.github.models import GitHubIssue, RepoInfo


class GitHubIssueMode:
    """
    Single-issue execution mode for GitHub issues.

    Coordinates the workflow of:
    1. Fetching issue details
    2. Posting progress comments
    3. Generating prompts for harness
    4. Detecting when to close the issue

    Example:
        >>> mode = GitHubIssueMode.from_project_dir(123, Path.cwd())
        >>> mode.post_start_comment()
        >>> prompt = mode.generate_prompt()
        >>> # Run harness with prompt...
        >>> if mode.should_close_issue():
        ...     mode.close_with_completion_comment()
    """

    def __init__(
        self,
        client: GitHubClient,
        issue: GitHubIssue,
        initial_commit: str | None = None,
    ) -> None:
        """
        Initialize GitHubIssueMode.

        Args:
            client: GitHub client
            issue: The issue to work on
            initial_commit: HEAD commit SHA at start (for closure detection)
        """
        self.client = client
        self.issue = issue
        self.initial_commit = initial_commit

    @classmethod
    def from_project_dir(
        cls,
        issue_number: int,
        project_dir: Path | None = None,
    ) -> GitHubIssueMode:
        """
        Create issue mode from project directory.

        Args:
            issue_number: GitHub issue number to work on
            project_dir: Project directory (defaults to cwd)

        Returns:
            GitHubIssueMode instance

        Raises:
            GitHubClientError: If setup fails
        """
        if project_dir is None:
            project_dir = Path.cwd()

        # Create client (validates gh availability and GitHub repo)
        client = GitHubClient.from_project_dir(project_dir)

        # Fetch issue
        issue = client.get_issue(issue_number)

        # Check issue is open
        if not issue.is_open:
            raise GitHubClientError(
                f"Issue #{issue_number} is already closed.\nCannot work on closed issues."
            )

        # Get initial commit for closure detection
        initial_commit = client.get_head_commit()

        return cls(client=client, issue=issue, initial_commit=initial_commit)

    @property
    def repo(self) -> RepoInfo:
        """Get repository info."""
        return self.client.repo

    def generate_prompt(self) -> str:
        """
        Generate task prompt for the harness.

        Returns:
            Task prompt string
        """
        parts = []

        parts.append("## CURRENT TASK\n")
        parts.append(f"GitHub Issue: #{self.issue.number}")
        parts.append(f"Repository: {self.repo.full_name}")
        parts.append(f"URL: {self.issue.url}")
        parts.append("")
        parts.append(f"Title: {self.issue.title}")
        parts.append("")
        parts.append("Description:")
        parts.append(self.issue.body or "(No description provided)")
        parts.append("")

        if self.issue.labels:
            parts.append(f"Labels: {self.issue.labels_str}")
            parts.append("")

        parts.append("When complete:")
        parts.append("1. Run feedback loops (typecheck, test, lint) if code was changed")
        parts.append(f'2. Commit with message: "fix: description (fixes #{self.issue.number})"')
        parts.append("")
        parts.append("Note: Working on GitHub issue. No bd/beads commands needed.")

        return "\n".join(parts)

    def post_start_comment(self) -> None:
        """
        Post a comment indicating work is starting.

        Posts a comment to the issue announcing that cub is beginning work.
        """
        branch = self.client.get_current_branch()
        branch_info = f" on branch `{branch}`" if branch else ""

        comment = (
            f"🤖 **Cub** is starting work on this issue{branch_info}.\n\n"
            "I'll post an update when complete."
        )

        try:
            self.client.add_comment(self.issue.number, comment)
        except GitHubClientError:
            # Don't fail if comment posting fails
            pass

    def post_completion_comment(self, on_main: bool) -> None:
        """
        Post a comment indicating work is complete.

        Args:
            on_main: Whether changes were committed to main/master
        """
        if on_main:
            comment = (
                "✅ **Cub** completed work on this issue.\n\n"
                "Changes have been committed to the main branch. "
                "Closing issue."
            )
        else:
            branch = self.client.get_current_branch()
            comment = (
                f"🔄 **Cub** completed work on this issue.\n\n"
                f"Changes have been committed to branch `{branch}`. "
                "Issue will close when merged to main via PR with `fixes #` syntax."
            )

        try:
            self.client.add_comment(self.issue.number, comment)
        except GitHubClientError:
            # Don't fail if comment posting fails
            pass

    def should_close_issue(self) -> bool:
        """
        Determine if issue should be auto-closed.

        Returns True if:
        - Working on main/master branch
        - HEAD commit has changed since start (new commits)

        Returns:
            True if issue should be closed
        """
        branch = self.client.get_current_branch()

        # Only auto-close on main branches
        if branch not in ("main", "master"):
            return False

        # Check if new commits since start
        current_commit = self.client.get_head_commit()
        if current_commit is None or self.initial_commit is None:
            return False

        return current_commit != self.initial_commit

    def close_with_completion_comment(self) -> None:
        """
        Post completion comment and close the issue.
        """
        self.post_completion_comment(on_main=True)

        try:
            self.client.close_issue(self.issue.number)
        except GitHubClientError:
            # Don't fail if close fails
            pass

    def finish(self) -> None:
        """
        Handle issue completion.

        Checks if issue should be closed and posts appropriate comments.
        """
        if self.should_close_issue():
            self.close_with_completion_comment()
        else:
            self.post_completion_comment(on_main=False)
