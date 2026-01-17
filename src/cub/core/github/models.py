"""
GitHub data models for cub.

Defines Pydantic models for GitHub repository info and issues.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, computed_field


class RepoInfo(BaseModel):
    """
    GitHub repository information.

    Parsed from git remote URL (SSH or HTTPS format).

    Example:
        >>> RepoInfo.from_remote_url("git@github.com:user/repo.git")
        RepoInfo(owner='user', repo='repo')
        >>> RepoInfo.from_remote_url("https://github.com/user/repo.git")
        RepoInfo(owner='user', repo='repo')
    """

    owner: str = Field(..., description="Repository owner (user or organization)")
    repo: str = Field(..., description="Repository name")

    @computed_field
    @property
    def full_name(self) -> str:
        """Full repository name (owner/repo)."""
        return f"{self.owner}/{self.repo}"

    @computed_field
    @property
    def url(self) -> str:
        """GitHub URL for the repository."""
        return f"https://github.com/{self.owner}/{self.repo}"

    def issue_url(self, issue_number: int) -> str:
        """Get URL for a specific issue."""
        return f"{self.url}/issues/{issue_number}"

    @classmethod
    def from_remote_url(cls, remote_url: str) -> RepoInfo | None:
        """
        Parse repository info from a git remote URL.

        Handles formats:
        - git@github.com:user/repo.git
        - git@github.com:user/repo
        - https://github.com/user/repo.git
        - https://github.com/user/repo

        Args:
            remote_url: Git remote URL

        Returns:
            RepoInfo or None if not a valid GitHub URL
        """
        if not remote_url:
            return None

        # SSH format: git@github.com:user/repo.git
        ssh_match = re.match(
            r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
            remote_url,
        )
        if ssh_match:
            return cls(owner=ssh_match.group(1), repo=ssh_match.group(2))

        # HTTPS format: https://github.com/user/repo.git
        https_match = re.match(
            r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
            remote_url,
        )
        if https_match:
            return cls(owner=https_match.group(1), repo=https_match.group(2))

        return None


class GitHubIssue(BaseModel):
    """
    A GitHub issue.

    Represents data fetched from GitHub API via `gh api`.
    """

    number: int = Field(..., description="Issue number")
    title: str = Field(..., description="Issue title")
    body: str = Field(default="", description="Issue body (markdown)")
    state: str = Field(default="open", description="Issue state (open/closed)")
    labels: list[str] = Field(default_factory=list, description="Label names")
    assignees: list[str] = Field(default_factory=list, description="Assignee logins")
    url: str = Field(default="", description="HTML URL for the issue")

    @computed_field
    @property
    def is_open(self) -> bool:
        """Check if issue is open."""
        return self.state == "open"

    @computed_field
    @property
    def labels_str(self) -> str:
        """Labels as comma-separated string."""
        return ", ".join(self.labels) if self.labels else "(none)"

    @classmethod
    def from_gh_api(cls, data: dict[str, object]) -> GitHubIssue:
        """
        Create GitHubIssue from gh api response.

        Args:
            data: JSON response from `gh api repos/{owner}/{repo}/issues/{number}`

        Returns:
            GitHubIssue instance
        """
        # Extract label names from label objects
        labels_data = data.get("labels", [])
        labels: list[str] = []
        if isinstance(labels_data, list):
            for label in labels_data:
                if isinstance(label, dict) and "name" in label:
                    name = label["name"]
                    if isinstance(name, str):
                        labels.append(name)
                elif isinstance(label, str):
                    labels.append(label)

        # Extract assignee logins from assignee objects
        assignees_data = data.get("assignees", [])
        assignees: list[str] = []
        if isinstance(assignees_data, list):
            for assignee in assignees_data:
                if isinstance(assignee, dict) and "login" in assignee:
                    login = assignee["login"]
                    if isinstance(login, str):
                        assignees.append(login)

        # Get scalar values with type narrowing
        number = data.get("number", 0)
        title = data.get("title", "")
        body = data.get("body") or ""
        state = data.get("state", "open")
        url = data.get("html_url", "")

        return cls(
            number=int(number) if isinstance(number, (int, float)) else 0,
            title=str(title) if title else "",
            body=str(body) if body else "",
            state=str(state) if state else "open",
            labels=labels,
            assignees=assignees,
            url=str(url) if url else "",
        )
