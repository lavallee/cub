"""
SkillsMP.com source adapter.

Fetches skills from SkillsMP, a community marketplace for Claude and Codex agent skills.
Uses the SkillsMP public API to discover skills, descriptions, and metadata.

Example:
    >>> from cub.core.toolsmith.sources.skillsmp import SkillsMPSource
    >>> source = SkillsMPSource()
    >>> tools = source.fetch_tools()
    >>> len(tools) > 0
    True
    >>> results = source.search_live("documentation")
    >>> any("documentation" in tool.name.lower() for tool in results)
    True
"""

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from cub.core.toolsmith.exceptions import NetworkError, ParseError
from cub.core.toolsmith.models import Tool, ToolType
from cub.core.toolsmith.sources.base import register_source


@register_source("skillsmp")
class SkillsMPSource:
    """
    Tool source for SkillsMP.com skills marketplace.

    Fetches skill listings from the SkillsMP API. The API provides skill metadata
    including names, descriptions, GitHub repository URLs, categories, and usage stats.

    The API supports both keyword search and AI-powered semantic search. Authentication
    is optional but recommended for higher rate limits. Set the environment variable
    SKILLSMP_API_TOKEN to authenticate requests.

    API Endpoints:
    - Keyword Search: GET https://skillsmp.com/api/v1/skills/search?q={query}&page={page}&limit={limit}
    - AI Search: GET https://skillsmp.com/api/v1/skills/ai-search?q={query}&page={page}&limit={limit}
    - Get Skill: GET https://skillsmp.com/api/v1/skills/{skill-id}

    Response Format (expected based on standard patterns):
    {
      "skills": [
        {
          "id": "skill-id-or-slug",
          "name": "Skill Name",
          "description": "Skill description",
          "url": "https://skillsmp.com/skills/...",
          "repository": {
            "url": "https://github.com/author/repo",
            "path": "path/to/SKILL.md"
          },
          "category": "documentation",
          "tags": ["api", "docs"],
          "author": "username",
          "stars": 10,
          "createdAt": "2025-01-01T00:00:00Z"
        }
      ],
      "pagination": {
        "page": 1,
        "limit": 50,
        "total": 250,
        "hasNext": true
      }
    }
    """

    API_BASE_URL = "https://skillsmp.com/api/v1"

    @property
    def name(self) -> str:
        """Get the name of this source."""
        return "skillsmp"

    def fetch_tools(self) -> list[Tool]:
        """
        Fetch all available skills from SkillsMP.

        Queries the SkillsMP API to retrieve all skills, paginating through
        results as needed. Each skill is converted to a Tool object with:
        - id: "skillsmp:{skill-slug}"
        - name: Display name from API
        - source: "skillsmp"
        - source_url: Skill URL on SkillsMP
        - tool_type: SKILL
        - description: Skill description
        - install_hint: CLI command for installation
        - tags: Categories and tags from API

        Returns:
            List of Tool objects representing SkillsMP skills

        Raises:
            NetworkError: If API request fails
            ParseError: If response parsing fails
        """
        all_tools = []
        page = 1
        limit = 50

        while True:
            try:
                skills, pagination = self._fetch_page(page=page, limit=limit)
                all_tools.extend(skills)

                # Check if there are more pages
                if not pagination.get("hasNext", False):
                    break

                page += 1

            except (NetworkError, ParseError):
                # If we already have some results, return them
                # Otherwise, re-raise to let caller handle it
                if all_tools:
                    break
                raise

        return all_tools

    def search_live(self, query: str) -> list[Tool]:
        """
        Search for skills matching a query on SkillsMP.

        Uses the SkillsMP API keyword search endpoint. For more advanced
        semantic search, the API also provides an ai-search endpoint, but
        we use the standard search for consistency with other sources.

        Args:
            query: Search query string

        Returns:
            List of Tool objects matching the search query

        Raises:
            NetworkError: If API request fails
            ParseError: If response parsing fails
        """
        tools, _ = self._fetch_page(query=query, page=1, limit=50)
        return tools

    def _fetch_page(
        self, query: str = "", page: int = 1, limit: int = 50
    ) -> tuple[list[Tool], dict[str, Any]]:
        """
        Fetch a single page of skills from the SkillsMP API.

        Args:
            query: Optional search query to filter skills
            page: Page number (1-indexed)
            limit: Number of results per page

        Returns:
            Tuple of (list of Tool objects, pagination metadata dict)

        Raises:
            NetworkError: If API request fails
            ParseError: If response parsing fails
        """
        # Build API URL with query parameters
        params: dict[str, str] = {
            "page": str(page),
            "limit": str(limit),
        }
        if query:
            params["q"] = query

        # Prepare headers
        headers = {"Accept": "application/json"}

        # Add authentication if available
        api_token = os.environ.get("SKILLSMP_API_TOKEN")
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        # Make API request
        # Use /search endpoint for keyword search
        url = f"{self.API_BASE_URL}/skills/search"
        try:
            response = httpx.get(
                url, params=params, headers=headers, timeout=30.0, follow_redirects=True
            )
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise NetworkError(
                "skillsmp",
                "Request timed out while fetching skills from SkillsMP API",
                url=url,
                timeout=30.0,
            ) from e
        except httpx.HTTPStatusError as e:
            raise NetworkError(
                "skillsmp",
                f"HTTP {e.response.status_code} error from SkillsMP API",
                url=url,
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(
                "skillsmp",
                f"Network error while fetching from SkillsMP API: {e}",
                url=url,
            ) from e

        # Parse JSON response
        try:
            data = response.json()
        except Exception as e:
            raise ParseError(
                "skillsmp",
                "Failed to parse JSON response from SkillsMP API",
                url=url,
            ) from e

        # Extract data with error handling
        try:
            skills_data = data.get("skills", [])
            pagination = data.get("pagination", {})
        except AttributeError as e:
            raise ParseError(
                "skillsmp",
                "Response is not a valid JSON object",
                url=url,
                response_type=type(data).__name__,
            ) from e

        # Convert skill entries to Tool objects
        try:
            tools = [self._parse_skill(skill) for skill in skills_data]
        except (KeyError, ValueError, ValidationError) as e:
            raise ParseError(
                "skillsmp",
                f"Failed to parse skill data: {e}",
                url=url,
            ) from e

        return tools, pagination

    def _parse_skill(self, skill: dict[str, Any]) -> Tool:
        """
        Parse a skill entry from the API response into a Tool object.

        Args:
            skill: Skill dictionary from API response

        Returns:
            Tool object representing the skill
        """
        skill_id = skill.get("id", "")
        skill_slug = skill.get("slug", skill_id)
        name = skill.get("name", skill_slug)
        description = skill.get("description", "")
        url = skill.get("url", f"https://skillsmp.com/skills/{skill_slug}")
        repository = skill.get("repository", {})
        repo_url = repository.get("url", "") if repository else ""
        category = skill.get("category", "")
        tags_list = skill.get("tags", [])
        author = skill.get("author", "")
        created_at = skill.get("createdAt")

        # Generate tool ID from skill slug
        # Tool ID format: "skillsmp:{skill-slug}"
        tool_id = f"skillsmp:{skill_slug}"

        # Build tags from category and tags
        tags = []
        if category:
            tags.append(category)
        if tags_list:
            tags.extend(tags_list)
        if author:
            tags.append(f"author:{author}")

        # Build install hint
        # Skills can typically be installed via Claude Code or copied from repo
        install_hint = ""
        if repo_url:
            install_hint = f"claude skill add {repo_url}"
        else:
            install_hint = f"See installation instructions at: {url}"

        # Parse created_at timestamp
        last_seen = None
        if created_at:
            try:
                last_seen = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                # If parsing fails, use current time
                last_seen = datetime.now(timezone.utc)
        else:
            last_seen = datetime.now(timezone.utc)

        return Tool(
            id=tool_id,
            name=name,
            source="skillsmp",
            source_url=url,
            tool_type=ToolType.SKILL,
            description=description,
            install_hint=install_hint,
            tags=tags,
            last_seen=last_seen,
        )
