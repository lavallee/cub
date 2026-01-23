"""
Changelog parser for the dashboard sync layer.

Parses CHANGELOG.md to detect which tasks/epics have been released.
The CHANGELOG contains release entries with task IDs that indicate
which entities have been shipped to production.

Handles:
- Various ID formats: `cub-xxx`, `cub-xxx.n`, `#123`
- Multiple releases with dates
- Graceful handling of missing CHANGELOG
- Unparseable content (malformed markdown)
- Empty changelog files

ID Patterns:
- Full ID: cub-xxx.n (e.g., cub-d2v.4)
- Epic ID: cub-xxx (e.g., cub-d2v)
- GitHub issue: #123
- PR reference: (#123)

Release Detection:
- Parses markdown headings like "## [0.27.1] - 2026-01-23"
- Extracts task IDs from release sections
- Maps task IDs to release version and date
"""

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ChangelogParserError(Exception):
    """Base exception for changelog parser errors."""

    pass


class Release:
    """Represents a single release in the changelog.

    Attributes:
        version: Release version (e.g., "0.27.1")
        date: Release date
        task_ids: Set of task/epic IDs mentioned in this release
    """

    def __init__(
        self, version: str, date: datetime | None = None, task_ids: set[str] | None = None
    ) -> None:
        self.version = version
        self.date = date
        self.task_ids = task_ids or set()

    def __repr__(self) -> str:
        date_str = self.date.strftime("%Y-%m-%d") if self.date else "no date"
        return f"Release({self.version}, {date_str}, {len(self.task_ids)} tasks)"


class ChangelogParser:
    """
    Parser for extracting release information from CHANGELOG.md.

    The ChangelogParser reads CHANGELOG.md and extracts which tasks
    and epics have been released, enabling the dashboard to move
    entities to the RELEASED stage.

    Example:
        >>> parser = ChangelogParser(changelog_path=Path("./CHANGELOG.md"))
        >>> releases = parser.parse()
        >>> for release in releases:
        ...     print(f"{release.version}: {release.task_ids}")
        >>> released_ids = parser.get_released_task_ids()
        >>> print(f"Released: {released_ids}")
    """

    # Regex patterns for ID extraction
    # Matches: cub-xxx, cub-xxx.n, epic:cub-xxx
    TASK_ID_PATTERN = re.compile(
        r"\b(?:epic:)?(cub-[a-z0-9]+(?:\.\d+)?)\b", re.IGNORECASE
    )

    # Matches: #123, (#123)
    GITHUB_ISSUE_PATTERN = re.compile(r"#(\d+)")

    # Matches: ## [0.27.1] - 2026-01-23 (with optional date)
    RELEASE_HEADER_PATTERN = re.compile(
        r"^##\s+\[([^\]]+)\](?:\s*-\s*(.+))?", re.MULTILINE
    )

    def __init__(self, changelog_path: Path) -> None:
        """
        Initialize the ChangelogParser.

        Args:
            changelog_path: Path to CHANGELOG.md file
        """
        self.changelog_path = Path(changelog_path)

    def _compute_checksum(self, content: str) -> str:
        """
        Compute MD5 checksum of changelog content for change detection.

        Args:
            content: Changelog file content

        Returns:
            Hex digest string of MD5 hash
        """
        return hashlib.md5(content.encode()).hexdigest()

    def _extract_task_ids(self, text: str) -> set[str]:
        """
        Extract all task IDs from a section of text.

        Finds both cub-style IDs and GitHub issue numbers.

        Args:
            text: Text to search for task IDs

        Returns:
            Set of normalized task IDs (lowercase)
        """
        task_ids: set[str] = set()

        # Extract cub-xxx and cub-xxx.n patterns
        for match in self.TASK_ID_PATTERN.finditer(text):
            task_id = match.group(1).lower()
            task_ids.add(task_id)

        # Extract GitHub issue numbers (#123)
        for match in self.GITHUB_ISSUE_PATTERN.finditer(text):
            issue_num = match.group(1)
            task_ids.add(f"#{issue_num}")

        return task_ids

    def _parse_release_header(self, line: str) -> tuple[str, datetime | None] | None:
        """
        Parse a release header line to extract version and date.

        Args:
            line: Markdown line to parse

        Returns:
            Tuple of (version, date) or None if not a release header
        """
        match = self.RELEASE_HEADER_PATTERN.match(line)
        if not match:
            return None

        version = match.group(1)
        date_str = match.group(2)

        # Parse date if present
        date = None
        if date_str:
            date_str = date_str.strip()

            # Extract just the date part (YYYY-MM-DD) if present
            # Handles formats like "2026-01-23 (PR #24)" or "2026-01-23"
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
            if date_match:
                date_str_clean = date_match.group(1)
                try:
                    date = datetime.strptime(date_str_clean, "%Y-%m-%d")
                except ValueError:
                    logger.warning(f"Invalid date format in release header: {date_str}")
                    date = None
            else:
                logger.debug(f"No date found in release header: {date_str}")
                date = None

        return (version, date)

    def parse(self) -> list[Release]:
        """
        Parse CHANGELOG.md and extract all releases with their task IDs.

        Returns:
            List of Release objects, ordered by appearance in changelog
        """
        if not self.changelog_path.exists():
            logger.warning(f"CHANGELOG not found: {self.changelog_path}")
            return []

        try:
            content = self.changelog_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read CHANGELOG {self.changelog_path}: {e}")
            return []

        if not content.strip():
            logger.warning(f"CHANGELOG is empty: {self.changelog_path}")
            return []

        return self._parse_content(content)

    def _parse_content(self, content: str) -> list[Release]:
        """
        Parse changelog content and extract releases.

        This method scans through the changelog line by line,
        identifying release headers and extracting task IDs
        from each release section.

        Args:
            content: Full CHANGELOG.md content

        Returns:
            List of Release objects
        """
        releases: list[Release] = []
        current_release: Release | None = None
        lines = content.split("\n")

        for line in lines:
            # Check if this is a release header
            header_match = self._parse_release_header(line)
            if header_match:
                # Save previous release if exists
                if current_release is not None:
                    releases.append(current_release)

                # Start new release
                version, date = header_match
                current_release = Release(version, date)
                continue

            # Extract task IDs from current line (if we're in a release section)
            if current_release is not None:
                # Stop processing if we hit the next major section marker
                if line.startswith("---") or line.startswith("## Version Summary"):
                    # Save current release and stop
                    releases.append(current_release)
                    current_release = None
                    continue

                # Extract IDs from this line
                task_ids = self._extract_task_ids(line)
                current_release.task_ids.update(task_ids)

        # Don't forget the last release
        if current_release is not None:
            releases.append(current_release)

        logger.info(
            f"Parsed {len(releases)} releases from {self.changelog_path} "
            f"with {sum(len(r.task_ids) for r in releases)} total task references"
        )

        return releases

    def get_released_task_ids(self) -> set[str]:
        """
        Get the set of all task IDs that have been released.

        This is a convenience method that flattens all task IDs
        across all releases.

        Returns:
            Set of all released task IDs (normalized to lowercase)
        """
        releases = self.parse()
        all_ids: set[str] = set()

        for release in releases:
            all_ids.update(release.task_ids)

        return all_ids

    def get_task_release(self, task_id: str) -> Release | None:
        """
        Find which release a specific task was included in.

        If a task appears in multiple releases, returns the first one.

        Args:
            task_id: Task ID to search for (case-insensitive)

        Returns:
            Release object if found, None otherwise
        """
        normalized_id = task_id.lower()
        releases = self.parse()

        for release in releases:
            if normalized_id in release.task_ids:
                return release

        return None

    def is_released(self, task_id: str) -> bool:
        """
        Check if a task ID has been released.

        Args:
            task_id: Task ID to check (case-insensitive)

        Returns:
            True if the task appears in any release
        """
        normalized_id = task_id.lower()
        return normalized_id in self.get_released_task_ids()
