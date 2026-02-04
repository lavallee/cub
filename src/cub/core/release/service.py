"""
Release service for managing plan releases.

Provides high-level operations for:
- Marking plans as released in the ledger
- Updating CHANGELOG.md with release notes
- Creating git tags
- Moving spec files to specs/released/
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.writer import LedgerWriter

logger = logging.getLogger(__name__)


class ReleaseServiceError(Exception):
    """Error from release service operations."""

    pass


@dataclass
class ReleaseResult:
    """Result of a release operation."""

    plan_id: str
    version: str
    spec_file: Path | None
    spec_moved: bool
    changelog_updated: bool
    tag_created: bool
    ledger_updated: bool


class ReleaseService:
    """
    Service for managing plan releases.

    Provides high-level operations for:
    - Marking plans as released in the ledger
    - Updating CHANGELOG.md with release notes
    - Creating git tags
    - Moving spec files to specs/released/

    Example:
        >>> service = ReleaseService(Path.cwd())
        >>> result = service.release_plan("cub-048a", "v0.30")
        >>> print(f"Released {result.plan_id} as {result.version}")
    """

    def __init__(self, project_dir: Path | None = None) -> None:
        """
        Initialize ReleaseService.

        Args:
            project_dir: Project directory (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self.ledger_dir = self.project_dir / ".cub" / "ledger"
        self.specs_dir = self.project_dir / "specs"
        self.changelog_path = self.project_dir / "CHANGELOG.md"

        self._reader: LedgerReader | None = None
        self._writer: LedgerWriter | None = None

    @property
    def reader(self) -> LedgerReader:
        """Get ledger reader (lazy initialization)."""
        if self._reader is None:
            self._reader = LedgerReader(self.ledger_dir)
        return self._reader

    @property
    def writer(self) -> LedgerWriter:
        """Get ledger writer (lazy initialization)."""
        if self._writer is None:
            self._writer = LedgerWriter(self.ledger_dir)
        return self._writer

    def release_plan(
        self,
        plan_id: str,
        version: str,
        *,
        dry_run: bool = False,
        no_tag: bool = False,
    ) -> ReleaseResult:
        """
        Release a plan.

        Args:
            plan_id: Plan ID (e.g., "cub-048a")
            version: Version tag (e.g., "v0.30")
            dry_run: Show what would be done without making changes
            no_tag: Skip git tag creation

        Returns:
            ReleaseResult with details of what was done

        Raises:
            ReleaseServiceError: If release fails
        """
        logger.info(f"Releasing plan {plan_id} as {version}")

        result = ReleaseResult(
            plan_id=plan_id,
            version=version,
            spec_file=None,
            spec_moved=False,
            changelog_updated=False,
            tag_created=False,
            ledger_updated=False,
        )

        # Find the plan entry in the ledger
        plan_entry_path = self.ledger_dir / "by-plan" / plan_id / "entry.json"
        if not plan_entry_path.exists():
            raise ReleaseServiceError(
                f"Plan {plan_id} not found in ledger. "
                f"Expected: {plan_entry_path}"
            )

        # Load plan entry to get spec_id
        import json
        with plan_entry_path.open("r") as f:
            plan_data = json.load(f)
        spec_id = plan_data.get("spec_id")

        # Find and move spec file
        spec_file = self._find_spec_file(spec_id if spec_id else plan_id)
        if spec_file:
            result.spec_file = spec_file
            if not dry_run:
                result.spec_moved = self._move_spec_to_released(spec_file)
            else:
                result.spec_moved = True

        # Update CHANGELOG.md
        if not dry_run:
            result.changelog_updated = self._update_changelog(
                plan_id, version, plan_data
            )
        else:
            result.changelog_updated = True

        # Create git tag
        if not no_tag:
            if not dry_run:
                result.tag_created = self._create_git_tag(version, plan_id)
            else:
                result.tag_created = True

        # Update ledger status to "released"
        if not dry_run:
            result.ledger_updated = self._update_ledger_status(plan_id, version)
        else:
            result.ledger_updated = True

        return result

    def _find_spec_file(self, spec_id: str) -> Path | None:
        """
        Find the spec file for a given spec ID.

        Looks in specs/staged/ first, then other directories.

        Args:
            spec_id: Spec ID or plan ID to search for

        Returns:
            Path to spec file, or None if not found
        """
        # Extract base spec ID (remove plan suffix if present)
        # e.g., "cub-048a" -> "cub-048"
        base_spec_id = spec_id.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

        # Search in staged first
        for pattern in [f"{spec_id}*.md", f"{base_spec_id}*.md"]:
            for spec_file in (self.specs_dir / "staged").glob(pattern):
                if spec_file.is_file():
                    return spec_file

        # Search in other directories
        for subdir in ["planned", "researching"]:
            for pattern in [f"{spec_id}*.md", f"{base_spec_id}*.md"]:
                for spec_file in (self.specs_dir / subdir).glob(pattern):
                    if spec_file.is_file():
                        return spec_file

        return None

    def _move_spec_to_released(self, spec_file: Path) -> bool:
        """
        Move spec file to specs/released/.

        Args:
            spec_file: Path to spec file

        Returns:
            True if moved successfully
        """
        released_dir = self.specs_dir / "released"
        released_dir.mkdir(parents=True, exist_ok=True)

        dest_file = released_dir / spec_file.name

        try:
            # Move the file
            spec_file.rename(dest_file)
            logger.info(f"Moved {spec_file} to {dest_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to move spec file: {e}")
            return False

    def _update_changelog(
        self, plan_id: str, version: str, plan_data: dict[str, Any]
    ) -> bool:
        """
        Update CHANGELOG.md with release notes.

        Args:
            plan_id: Plan ID
            version: Version tag
            plan_data: Plan entry data from ledger

        Returns:
            True if updated successfully
        """
        try:
            # Read existing CHANGELOG
            if self.changelog_path.exists():
                changelog_content = self.changelog_path.read_text()
            else:
                # Create minimal CHANGELOG if it doesn't exist
                changelog_content = "# Changelog\n\n"

            # Extract plan info
            title = plan_data.get("title", plan_id)
            epics = plan_data.get("epics", [])
            completed_tasks = plan_data.get("completed_tasks", 0)
            total_cost = plan_data.get("total_cost", 0.0)

            # Generate release entry
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            release_entry = f"""
## [{version}] - {today}

### Added

- {title} ({plan_id})
  - {completed_tasks} tasks completed across {len(epics)} epic(s)
  - Total cost: ${total_cost:.2f}

"""

            # Insert after the header (after first occurrence of "##" or at end)
            lines = changelog_content.split("\n")
            insert_index = 0

            # Find where to insert (after "# Changelog" header)
            for i, line in enumerate(lines):
                if line.startswith("## ["):
                    insert_index = i
                    break
            else:
                # No existing releases, insert after header
                for i, line in enumerate(lines):
                    if line.startswith("# Changelog"):
                        insert_index = i + 1
                        # Skip any blank lines
                        while insert_index < len(lines) and not lines[insert_index].strip():
                            insert_index += 1
                        break

            # Insert the new release entry
            if insert_index > 0:
                new_lines = (
                    lines[:insert_index]
                    + release_entry.split("\n")
                    + lines[insert_index:]
                )
            else:
                new_lines = lines + release_entry.split("\n")

            # Write back
            new_content = "\n".join(new_lines)
            self.changelog_path.write_text(new_content)
            logger.info(f"Updated CHANGELOG.md with {version}")
            return True

        except Exception as e:
            logger.error(f"Failed to update CHANGELOG: {e}")
            return False

    def _create_git_tag(self, version: str, plan_id: str) -> bool:
        """
        Create a git tag.

        Args:
            version: Version tag (e.g., "v0.30")
            plan_id: Plan ID for commit message

        Returns:
            True if tag created successfully
        """
        try:
            # Create annotated tag
            result = subprocess.run(
                ["git", "tag", "-a", version, "-m", f"Release {version} ({plan_id})"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                check=False,
            )

            if result.returncode == 0:
                logger.info(f"Created git tag {version}")
                return True
            else:
                logger.warning(f"Failed to create git tag: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Failed to create git tag: {e}")
            return False

    def _update_ledger_status(self, plan_id: str, version: str) -> bool:
        """
        Update plan status to "released" in ledger.

        Args:
            plan_id: Plan ID
            version: Version tag

        Returns:
            True if updated successfully
        """
        try:
            plan_entry_path = self.ledger_dir / "by-plan" / plan_id / "entry.json"
            if not plan_entry_path.exists():
                return False

            # Load plan entry
            import json
            with plan_entry_path.open("r") as f:
                plan_data = json.load(f)

            # Update status and completed_at
            plan_data["status"] = "released"
            if not plan_data.get("completed_at"):
                plan_data["completed_at"] = datetime.now(timezone.utc).isoformat()

            # Write back
            with plan_entry_path.open("w") as f:
                json.dump(plan_data, f, indent=2)

            logger.info(f"Updated plan {plan_id} status to 'released'")
            return True

        except Exception as e:
            logger.error(f"Failed to update ledger status: {e}")
            return False
