"""Git operations for cub run command.

This module provides run-specific git operations including branch creation,
title retrieval from external systems (GitHub, beads), and slug generation.

These functions are business logic that should be accessible from any interface,
not just the CLI.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class BranchCreationResult:
    """Result of branch creation operation.

    Attributes:
        success: Whether the branch was created or switched to successfully
        branch_name: The name of the branch
        created: True if a new branch was created, False if existing branch was used
        error: Error message if success is False
    """
    success: bool
    branch_name: str
    created: bool
    error: str | None = None


@dataclass
class EpicContext:
    """Context information about an epic.

    Attributes:
        epic_id: The epic identifier
        title: The epic title, if available
    """
    epic_id: str
    title: str | None


@dataclass
class IssueContext:
    """Context information about a GitHub issue.

    Attributes:
        issue_number: The issue number
        title: The issue title, if available
    """
    issue_number: int
    title: str | None


def slugify(text: str, max_length: int = 40) -> str:
    """Convert text to a URL/branch-friendly slug.

    Args:
        text: Text to convert to a slug
        max_length: Maximum length for the slug (default: 40)

    Returns:
        URL-friendly slug string

    Example:
        >>> slugify("Add User Authentication")
        'add-user-authentication'
        >>> slugify("Fix Bug #123 - API Error")
        'fix-bug-123-api-error'
        >>> slugify("Very Long Feature Name That Exceeds Maximum Length Limit")
        'very-long-feature-name-that-exceeds'
    """
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove non-alphanumeric characters (except hyphens)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate to max length (at word boundary if possible)
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug


def get_epic_context(epic_id: str) -> EpicContext:
    """Get context information about an epic from beads.

    Args:
        epic_id: The epic identifier

    Returns:
        EpicContext with epic ID and title (if available)

    Example:
        >>> context = get_epic_context("cub-b1a")
        >>> context.epic_id
        'cub-b1a'
        >>> context.title
        'Core/interface refactor'
    """
    title = _get_epic_title(epic_id)
    return EpicContext(epic_id=epic_id, title=title)


def get_issue_context(issue_number: int) -> IssueContext:
    """Get context information about a GitHub issue.

    Args:
        issue_number: The GitHub issue number

    Returns:
        IssueContext with issue number and title (if available)

    Example:
        >>> context = get_issue_context(123)
        >>> context.issue_number
        123
        >>> context.title
        'Fix authentication bug'
    """
    title = _get_gh_issue_title(issue_number)
    return IssueContext(issue_number=issue_number, title=title)


def create_run_branch(
    branch_name: str,
    base_branch: str,
) -> BranchCreationResult:
    """Create a new git branch from a base branch for a cub run.

    This function handles:
    - Checking if the branch already exists
    - Switching to existing branch if it exists
    - Verifying base branch exists (trying both local and remote)
    - Creating and checking out the new branch from base

    Args:
        branch_name: Name for the new branch
        base_branch: Branch to create from (e.g., "main", "origin/main")

    Returns:
        BranchCreationResult with success status and details

    Example:
        >>> result = create_run_branch("feature/new-feature", "origin/main")
        >>> result.success
        True
        >>> result.created
        True
        >>> result.branch_name
        'feature/new-feature'
    """
    from cub.core.branches.store import BranchStore

    # Check if branch already exists
    if BranchStore.git_branch_exists(branch_name):
        # Switch to existing branch
        result = subprocess.run(
            ["git", "checkout", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return BranchCreationResult(
                success=False,
                branch_name=branch_name,
                created=False,
                error=f"Failed to switch to branch: {result.stderr}",
            )
        return BranchCreationResult(
            success=True,
            branch_name=branch_name,
            created=False,
        )

    # Verify base branch exists
    if not BranchStore.git_branch_exists(base_branch):
        # Try with origin/ prefix for remote branches
        remote_base = f"origin/{base_branch}"
        if BranchStore.git_branch_exists(remote_base):
            base_branch = remote_base
        else:
            return BranchCreationResult(
                success=False,
                branch_name=branch_name,
                created=False,
                error=f"Base branch '{base_branch}' does not exist",
            )

    # Create and checkout new branch from base
    result = subprocess.run(
        ["git", "checkout", "-b", branch_name, base_branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return BranchCreationResult(
            success=False,
            branch_name=branch_name,
            created=False,
            error=f"Failed to create branch: {result.stderr}",
        )

    return BranchCreationResult(
        success=True,
        branch_name=branch_name,
        created=True,
    )


def _get_gh_issue_title(issue_number: int) -> str | None:
    """Get the title of a GitHub issue.

    Internal function that calls gh CLI to retrieve issue title.
    Returns None if gh CLI is not available or command fails.

    Args:
        issue_number: The GitHub issue number

    Returns:
        Issue title string or None if unavailable
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title", "-q", ".title"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (OSError, FileNotFoundError):
        return None


def _get_epic_title(epic_id: str) -> str | None:
    """Get the title of an epic from beads.

    Internal function that calls bd CLI to retrieve epic title.
    Returns None if bd CLI is not available or command fails.

    Args:
        epic_id: The epic identifier

    Returns:
        Epic title string or None if unavailable
    """
    try:
        result = subprocess.run(
            ["bd", "show", epic_id, "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # bd show returns a list with one element
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            if isinstance(data, dict):
                title = data.get("title")
                if isinstance(title, str):
                    return title
        return None
    except (OSError, FileNotFoundError, json.JSONDecodeError):
        return None
