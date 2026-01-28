"""
Working directory cleanup service.

Handles post-run cleanup operations:
- Identify and commit useful artifacts (progress files, logs, reports)
- Identify and remove temporary files (*.bak, *.tmp, caches)
- Ensure working directory is clean after cub run completes
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cub.core.config.models import CleanupConfig


@dataclass
class CleanupResult:
    """Results of a cleanup operation."""

    # Files that were committed
    committed_files: list[str] = field(default_factory=list)

    # Files that were removed
    removed_files: list[str] = field(default_factory=list)

    # Files that couldn't be committed (errors)
    commit_errors: list[str] = field(default_factory=list)

    # Files that couldn't be removed (errors)
    removal_errors: list[str] = field(default_factory=list)

    # Whether git status is clean after cleanup
    is_clean: bool = False

    # Any remaining uncommitted files
    remaining_files: list[str] = field(default_factory=list)

    # Error message if cleanup failed
    error: str | None = None

    def summary(self) -> str:
        """Generate a human-readable summary of the cleanup."""
        parts = []

        if self.committed_files:
            parts.append(f"Committed {len(self.committed_files)} file(s)")

        if self.removed_files:
            parts.append(f"Removed {len(self.removed_files)} temporary file(s)")

        if self.commit_errors:
            parts.append(f"Failed to commit {len(self.commit_errors)} file(s)")

        if self.removal_errors:
            parts.append(f"Failed to remove {len(self.removal_errors)} file(s)")

        if self.is_clean:
            parts.append("Working directory is clean")
        elif self.remaining_files:
            parts.append(f"{len(self.remaining_files)} file(s) remain uncommitted")

        if not parts:
            return "No cleanup actions needed"

        return ", ".join(parts)


class CleanupService:
    """
    Service for cleaning up working directory after cub run.

    Handles:
    - Committing useful artifacts (logs, reports)
    - Removing temporary files (*.bak, *.tmp, caches)
    - Ensuring clean working directory state

    Example:
        >>> from cub.core.config.models import CleanupConfig
        >>> config = CleanupConfig()
        >>> service = CleanupService(config, project_dir=Path("."))
        >>> result = service.cleanup()
        >>> print(result.summary())
        Committed 3 file(s), Removed 5 temporary file(s), Working directory is clean
    """

    def __init__(
        self,
        config: CleanupConfig,
        project_dir: Path,
        debug: bool = False,
    ):
        """
        Initialize the cleanup service.

        Args:
            config: Cleanup configuration with patterns and settings.
            project_dir: Project root directory.
            debug: Enable debug output.
        """
        self.config = config
        self.project_dir = project_dir
        self.debug = debug

    def cleanup(self, commit_message: str | None = None) -> CleanupResult:
        """
        Perform full cleanup of working directory.

        Executes in order:
        1. Get list of uncommitted files (git status)
        2. Remove temporary files matching temp_patterns
        3. Stage and commit artifact files matching artifact_patterns
        4. Verify working directory is clean

        Args:
            commit_message: Custom commit message (uses config default if not provided).

        Returns:
            CleanupResult with details of what was done.
        """
        result = CleanupResult()

        if not self.config.enabled:
            result.is_clean = self._check_clean()
            return result

        try:
            # Step 1: Get uncommitted files
            uncommitted = self._get_uncommitted_files()

            if not uncommitted:
                result.is_clean = True
                return result

            # Step 2: Remove temporary files
            if self.config.remove_temp_files:
                removed, errors = self._remove_temp_files(uncommitted)
                result.removed_files = removed
                result.removal_errors = errors

                # Update uncommitted list after removal
                uncommitted = self._get_uncommitted_files()

            # Step 3: Commit useful artifacts
            if self.config.commit_artifacts and uncommitted:
                committed, errors = self._commit_artifacts(
                    uncommitted, commit_message or self.config.commit_message
                )
                result.committed_files = committed
                result.commit_errors = errors

            # Step 4: Final check
            result.remaining_files = self._get_uncommitted_files()
            result.is_clean = len(result.remaining_files) == 0

        except Exception as e:
            result.error = str(e)
            result.is_clean = False

        return result

    def _get_uncommitted_files(self) -> list[str]:
        """Get list of uncommitted files from git status."""
        try:
            # Get both staged and unstaged changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return []

            files = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    # Format: "XY path" or "XY path -> newpath" for renames
                    # X = index status, Y = worktree status
                    # Skip the first 3 chars (status + space)
                    path = line[3:].strip()
                    # Handle renames: "old -> new"
                    if " -> " in path:
                        path = path.split(" -> ")[1]
                    files.append(path)

            return files

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def _check_clean(self) -> bool:
        """Check if working directory is clean."""
        return len(self._get_uncommitted_files()) == 0

    def _matches_pattern(self, filepath: str, patterns: list[str]) -> bool:
        """Check if filepath matches any of the given glob patterns."""
        for pattern in patterns:
            # Handle ** patterns (recursive matching)
            if "**" in pattern:
                # Convert glob pattern to match
                # e.g., "__pycache__/**" should match "__pycache__/foo.pyc"
                parts = pattern.split("**")
                if len(parts) == 2:
                    prefix, suffix = parts
                    # Check if file starts with prefix
                    if prefix and not filepath.startswith(prefix.rstrip("/")):
                        continue
                    # Check if file ends with suffix (if any)
                    if suffix and not filepath.endswith(suffix.lstrip("/")):
                        continue
                    # If both conditions pass (or are empty), it's a match
                    if filepath.startswith(prefix.rstrip("/")):
                        return True

            # Standard fnmatch for simple patterns
            if fnmatch.fnmatch(filepath, pattern):
                return True

            # Also match against basename for patterns like "*.bak"
            basename = os.path.basename(filepath)
            if fnmatch.fnmatch(basename, pattern):
                return True

        return False

    def _is_ignored(self, filepath: str) -> bool:
        """Check if file should be ignored during cleanup."""
        return self._matches_pattern(filepath, self.config.ignore_patterns)

    def _remove_temp_files(self, files: list[str]) -> tuple[list[str], list[str]]:
        """
        Remove files matching temp patterns.

        Args:
            files: List of uncommitted files to consider.

        Returns:
            Tuple of (removed_files, error_files).
        """
        removed = []
        errors = []

        for filepath in files:
            # Skip ignored files
            if self._is_ignored(filepath):
                continue

            # Check if matches temp patterns
            if not self._matches_pattern(filepath, self.config.temp_patterns):
                continue

            # Try to remove
            full_path = self.project_dir / filepath
            try:
                if full_path.is_file():
                    full_path.unlink()
                    removed.append(filepath)
                elif full_path.is_dir():
                    # For directories, use git clean or rmtree
                    import shutil

                    shutil.rmtree(full_path)
                    removed.append(filepath)
            except OSError as e:
                errors.append(f"{filepath}: {e}")

        return removed, errors

    def _commit_artifacts(
        self, files: list[str], commit_message: str
    ) -> tuple[list[str], list[str]]:
        """
        Stage and commit files matching artifact patterns.

        Args:
            files: List of uncommitted files to consider.
            commit_message: Git commit message.

        Returns:
            Tuple of (committed_files, error_files).
        """
        # Find files to commit
        to_commit = []
        for filepath in files:
            # Skip ignored files
            if self._is_ignored(filepath):
                continue

            # Check if matches artifact patterns
            if self._matches_pattern(filepath, self.config.artifact_patterns):
                to_commit.append(filepath)

        if not to_commit:
            return [], []

        errors = []

        # Stage files
        try:
            result = subprocess.run(
                ["git", "add", "--"] + to_commit,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                # Failed to stage
                return [], [f"git add failed: {result.stderr}"]
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return [], [f"git add failed: {e}"]

        # Check if anything was actually staged
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            staged = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            if not staged:
                return [], []
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Assume files were staged
            staged = to_commit

        # Commit
        try:
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                # Check if "nothing to commit"
                if "nothing to commit" in result.stdout.lower():
                    return [], []
                errors.append(f"git commit failed: {result.stderr}")
                return [], errors
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            errors.append(f"git commit failed: {e}")
            return [], errors

        return staged, []

    def get_cleanup_preview(self) -> dict[str, list[str]]:
        """
        Preview what cleanup would do without making changes.

        Returns:
            Dict with keys:
            - 'to_commit': Files that would be committed
            - 'to_remove': Files that would be removed
            - 'ignored': Files that would be left alone
            - 'unmatched': Files that don't match any pattern
        """
        uncommitted = self._get_uncommitted_files()

        preview: dict[str, list[str]] = {
            "to_commit": [],
            "to_remove": [],
            "ignored": [],
            "unmatched": [],
        }

        for filepath in uncommitted:
            if self._is_ignored(filepath):
                preview["ignored"].append(filepath)
            elif self._matches_pattern(filepath, self.config.temp_patterns):
                preview["to_remove"].append(filepath)
            elif self._matches_pattern(filepath, self.config.artifact_patterns):
                preview["to_commit"].append(filepath)
            else:
                preview["unmatched"].append(filepath)

        return preview
