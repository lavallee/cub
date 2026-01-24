"""
ClawdHub source adapter.

Fetches Claude skills from the official Anthropic skills repository
at github.com/anthropics/skills. Uses the GitHub API to list skill directories
and parses individual SKILL.md files to extract skill metadata.

Example:
    >>> from cub.core.toolsmith.sources.clawdhub import ClawdHubSource
    >>> source = ClawdHubSource()
    >>> tools = source.fetch_tools()
    >>> len(tools) > 0
    True
    >>> results = source.search_live("pdf")
    >>> any("pdf" in tool.name.lower() for tool in results)
    True
"""

import re
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from cub.core.toolsmith.exceptions import NetworkError, ParseError
from cub.core.toolsmith.models import Tool, ToolType
from cub.core.toolsmith.sources.base import register_source


@register_source("clawdhub")
class ClawdHubSource:
    """
    Tool source for Claude skills from Anthropic's official skills repository.

    Fetches skill listings from the anthropics/skills GitHub repository
    using the GitHub API to list directories, then fetches each skill's
    SKILL.md file to extract metadata (name, description).

    Each skill is a directory containing a SKILL.md file with YAML frontmatter:
    ---
    name: my-skill-name
    description: A clear description of what this skill does
    ---

    The repository structure:
    anthropics/skills/
    └── skills/
        ├── pdf/
        │   └── SKILL.md
        ├── docx/
        │   └── SKILL.md
        └── webapp-testing/
            └── SKILL.md
    """

    API_URL = "https://api.github.com/repos/anthropics/skills/contents/skills"
    RAW_BASE_URL = "https://raw.githubusercontent.com/anthropics/skills/main/skills"

    @property
    def name(self) -> str:
        """Get the name of this source."""
        return "clawdhub"

    def fetch_tools(self) -> list[Tool]:
        """
        Fetch all available Claude skills from the Anthropic skills repository.

        Uses the GitHub API to list skill directories, then fetches each
        SKILL.md file to extract metadata. Each skill is converted to a Tool
        object with:
        - id: "clawdhub:{skill-slug}"
        - name: Skill name from frontmatter
        - source: "clawdhub"
        - source_url: GitHub directory URL
        - tool_type: SKILL
        - description: Skill description from frontmatter
        - tags: Extracted from skill directory name and categories

        Returns:
            List of Tool objects representing Claude skills

        Raises:
            NetworkError: If API request fails
            ParseError: If response parsing fails
        """
        url = self.API_URL
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise NetworkError(
                "clawdhub",
                "Request timed out while fetching skills from GitHub API",
                url=url,
                timeout=10.0,
            ) from e
        except httpx.HTTPStatusError as e:
            raise NetworkError(
                "clawdhub",
                f"HTTP {e.response.status_code} error from GitHub API",
                url=url,
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(
                "clawdhub",
                f"Network error while fetching from GitHub API: {e}",
                url=url,
            ) from e

        # Parse JSON response
        try:
            directories = response.json()
        except Exception as e:
            raise ParseError(
                "clawdhub",
                "Failed to parse JSON response from GitHub API",
                url=url,
            ) from e

        tools = []
        for item in directories:
            # Only process directories (type == "dir")
            if item.get("type") != "dir":
                continue

            skill_slug = item.get("name", "")
            if not skill_slug:
                continue

            # Attempt to fetch SKILL.md for this skill
            tool = self._fetch_skill_metadata(skill_slug, item.get("html_url", ""))
            if tool:
                tools.append(tool)

        return tools

    def search_live(self, query: str) -> list[Tool]:
        """
        Search for Claude skills matching a query.

        Fetches all tools and filters them by query string matching against:
        - Tool name (case-insensitive)
        - Tool description (case-insensitive)
        - Tool slug/ID (case-insensitive)

        Args:
            query: Search query string

        Returns:
            List of Tool objects matching the search query

        Raises:
            NetworkError: If API request fails
            ParseError: If response parsing fails
        """
        all_tools = self.fetch_tools()
        query_lower = query.lower()

        return [
            tool
            for tool in all_tools
            if query_lower in tool.name.lower()
            or query_lower in tool.description.lower()
            or query_lower in tool.id.lower()
        ]

    def _fetch_skill_metadata(self, skill_slug: str, html_url: str) -> Tool | None:
        """
        Fetch metadata for a single skill by reading its SKILL.md file.

        Fetches the raw SKILL.md content from GitHub and parses the YAML
        frontmatter to extract skill name and description.

        Args:
            skill_slug: The skill directory name (e.g., "pdf", "webapp-testing")
            html_url: GitHub HTML URL for the skill directory

        Returns:
            Tool object if successful, None if fetch/parse fails
        """
        skill_md_url = f"{self.RAW_BASE_URL}/{skill_slug}/SKILL.md"

        try:
            response = httpx.get(skill_md_url, timeout=10.0, follow_redirects=True)
            response.raise_for_status()
            content = response.text
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError):
            # Skill doesn't have SKILL.md or fetch failed - skip it
            return None

        # Parse frontmatter
        try:
            metadata = self._parse_frontmatter(content)
        except (ValueError, ValidationError):
            # Parsing failed - skip this skill
            return None

        if not metadata:
            return None

        name = metadata.get("name", skill_slug)
        description = metadata.get("description", "")

        # If no description in frontmatter, use slug as fallback
        if not description:
            description = f"Claude skill: {skill_slug}"

        # Generate tool ID
        tool_id = f"clawdhub:{skill_slug}"

        # Extract tags from skill slug (e.g., "webapp-testing" -> ["webapp", "testing"])
        tags = self._extract_tags(skill_slug)

        return Tool(
            id=tool_id,
            name=name,
            source="clawdhub",
            source_url=html_url or f"https://github.com/anthropics/skills/tree/main/skills/{skill_slug}",
            tool_type=ToolType.SKILL,
            description=description,
            tags=tags,
            last_seen=datetime.now(timezone.utc),
        )

    def _parse_frontmatter(self, content: str) -> dict[str, str]:
        """
        Parse YAML frontmatter from SKILL.md content.

        Expected format:
        ---
        name: my-skill-name
        description: Skill description here
        ---

        Args:
            content: SKILL.md file content

        Returns:
            Dictionary with frontmatter fields (name, description)
        """
        # Match YAML frontmatter between --- delimiters
        pattern = r"^---\s*\n(.*?)\n---"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

        if not match:
            return {}

        frontmatter_text = match.group(1)
        metadata: dict[str, str] = {}

        # Parse simple YAML key-value pairs
        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Match "key: value" pattern
            if ":" in line:
                key, _, value = line.partition(":")
                metadata[key.strip()] = value.strip()

        return metadata

    def _extract_tags(self, skill_slug: str) -> list[str]:
        """
        Extract tags from skill slug.

        Splits hyphenated slugs into individual words for tagging.

        Args:
            skill_slug: The skill directory name (e.g., "webapp-testing")

        Returns:
            List of tags extracted from slug
        """
        # Split on hyphens and underscores
        parts = re.split(r"[-_]", skill_slug)
        # Filter out empty parts and return
        return [part.lower() for part in parts if part]
