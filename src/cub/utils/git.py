"""
Git utilities for cub.

Provides functions for interacting with git repositories,
primarily for capturing commit information during task execution.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone


def get_commits_since(since: datetime | str) -> list[dict[str, str]]:
    """Get git commits made since a given time.

    Args:
        since: Either a datetime or an ISO format string (YYYY-MM-DDTHH:MM:SS)

    Returns:
        List of commit dictionaries with keys: hash, message, timestamp

    Example:
        >>> from datetime import datetime, timedelta
        >>> commits = get_commits_since(datetime.now() - timedelta(hours=1))
        >>> for c in commits:
        ...     print(f"{c['hash'][:7]}: {c['message']}")
    """
    if isinstance(since, datetime):
        since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        since_str = since

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--since={since_str}",
                "--format=%H|%s|%aI",
                "--no-merges",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 2)
            if len(parts) >= 3:
                commits.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "timestamp": parts[2],
                })

        return commits

    except subprocess.CalledProcessError:
        return []
    except FileNotFoundError:
        # Git not installed
        return []


def get_current_commit() -> str | None:
    """Get the current HEAD commit hash.

    Returns:
        Full commit hash or None if not in a git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_commits_between(from_commit: str, to_commit: str = "HEAD") -> list[dict[str, str]]:
    """Get commits between two commits.

    Args:
        from_commit: Starting commit (exclusive)
        to_commit: Ending commit (inclusive), defaults to HEAD

    Returns:
        List of commit dictionaries with keys: hash, message, timestamp
    """
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"{from_commit}..{to_commit}",
                "--format=%H|%s|%aI",
                "--no-merges",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 2)
            if len(parts) >= 3:
                commits.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "timestamp": parts[2],
                })

        return commits

    except subprocess.CalledProcessError:
        return []
    except FileNotFoundError:
        return []


def parse_commit_timestamp(timestamp_str: str) -> datetime:
    """Parse a git timestamp string to datetime.

    Args:
        timestamp_str: ISO format timestamp from git (e.g., 2026-01-24T15:30:00-05:00)

    Returns:
        UTC datetime object
    """
    # Handle timezone offset in ISO format
    dt = datetime.fromisoformat(timestamp_str)
    return dt.astimezone(timezone.utc)
