"""
GitHub integration for cub.

Provides support for working on GitHub issues directly via `cub run --gh-issue`.
"""

from cub.core.github.client import GitHubClient, GitHubClientError
from cub.core.github.issue_mode import GitHubIssueMode
from cub.core.github.models import GitHubIssue, RepoInfo

__all__ = [
    "GitHubClient",
    "GitHubClientError",
    "GitHubIssue",
    "GitHubIssueMode",
    "RepoInfo",
]
