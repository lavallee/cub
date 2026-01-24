"""
MCP Official source adapter.

Fetches MCP servers from the official Model Context Protocol servers repository
at github.com/modelcontextprotocol/servers. Parses the README.md file to extract
server listings.

Example:
    >>> from cub.core.toolsmith.sources.mcp_official import MCPOfficialSource
    >>> source = MCPOfficialSource()
    >>> tools = source.fetch_tools()
    >>> len(tools) > 0
    True
    >>> results = source.search_live("github")
    >>> any("github" in tool.name.lower() for tool in results)
    True
"""

import re
from datetime import datetime, timezone

import httpx

from cub.core.toolsmith.models import Tool, ToolType
from cub.core.toolsmith.sources.base import register_source


@register_source("mcp-official")
class MCPOfficialSource:
    """
    Tool source for official MCP servers.

    Fetches server listings from the modelcontextprotocol/servers GitHub repository
    by parsing the README.md file. Extracts server name, description, and links.

    The README contains several sections:
    - Reference Servers (maintained by MCP steering group)
    - Archived Servers (deprecated/moved)
    - Third-Party Servers (community and official integrations)

    Each server entry typically follows this markdown format:
    - **[Server Name](link)** - Description text
    or
    - <img ... /> **[Server Name](link)** - Description text
    """

    README_URL = "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/README.md"

    @property
    def name(self) -> str:
        """Get the name of this source."""
        return "mcp-official"

    def fetch_tools(self) -> list[Tool]:
        """
        Fetch all available MCP servers from the official repository.

        Parses the README.md file from the MCP servers repository to extract
        server listings. Each server is converted to a Tool object with:
        - id: "mcp-official:{server-slug}"
        - name: Server name extracted from markdown
        - source: "mcp-official"
        - source_url: Link from markdown entry
        - tool_type: MCP_SERVER
        - description: Server description
        - tags: Extracted from section headers (reference, archived, third-party)

        Returns:
            List of Tool objects representing MCP servers

        Raises:
            httpx.HTTPError: If README fetch fails
        """
        try:
            response = httpx.get(self.README_URL, timeout=10.0, follow_redirects=True)
            response.raise_for_status()
            readme_content = response.text
        except httpx.HTTPError:
            # Gracefully handle network errors by returning empty list
            # Could also raise here depending on error handling preference
            return []

        return self._parse_readme(readme_content)

    def search_live(self, query: str) -> list[Tool]:
        """
        Search for MCP servers matching a query.

        Fetches all tools and filters them by query string matching against:
        - Tool name (case-insensitive)
        - Tool description (case-insensitive)

        Args:
            query: Search query string

        Returns:
            List of Tool objects matching the search query
        """
        all_tools = self.fetch_tools()
        query_lower = query.lower()

        return [
            tool
            for tool in all_tools
            if query_lower in tool.name.lower() or query_lower in tool.description.lower()
        ]

    def _parse_readme(self, content: str) -> list[Tool]:
        """
        Parse README content to extract MCP server entries.

        The README is structured with sections like:
        ## 🌟 Reference Servers
        ## Archived
        ## 🤝 Third-Party Servers
        ### 🎖️ Official Integrations

        Each server entry is a list item with format:
        - **[Server Name](link)** - Description
        or
        - <img ... /> **[Server Name](link)** - Description

        Args:
            content: README.md file content

        Returns:
            List of Tool objects parsed from the README
        """
        tools = []
        current_section = "unknown"
        current_tags = []

        lines = content.split("\n")

        for line in lines:
            # Track current section for tagging
            if line.startswith("## "):
                current_section = self._extract_section_name(line)
                current_tags = [current_section.lower().replace(" ", "-")]
            elif line.startswith("### "):
                subsection = self._extract_section_name(line)
                current_tags = [
                    current_section.lower().replace(" ", "-"),
                    subsection.lower().replace(" ", "-"),
                ]

            # Match server entries (list items with bold links)
            # Pattern: - optional(<img .../>) **[Name](url)** - description
            if line.strip().startswith("-"):
                tool = self._parse_server_entry(line, current_tags)
                if tool:
                    tools.append(tool)

        return tools

    def _extract_section_name(self, header_line: str) -> str:
        """
        Extract clean section name from markdown header.

        Args:
            header_line: Markdown header line (e.g., "## 🌟 Reference Servers")

        Returns:
            Clean section name (e.g., "Reference Servers")
        """
        # Remove markdown header markers and emoji
        cleaned = re.sub(r"^#{1,6}\s*", "", header_line)
        # Remove emoji and emoji variation selectors (more comprehensive pattern)
        # This handles both regular emoji and emoji with variation selectors
        cleaned = re.sub(r"[\U0001F000-\U0001F9FF\uFE00-\uFE0F]+", "", cleaned)
        return cleaned.strip()

    def _parse_server_entry(self, line: str, tags: list[str]) -> Tool | None:
        """
        Parse a single server entry line from the README.

        Expected format:
        - **[Server Name](url)** - Description text
        or
        - <img ... /> **[Server Name](link)** - Description

        Args:
            line: Markdown list item line
            tags: Tags to apply to this tool (from section context)

        Returns:
            Tool object if parsing succeeds, None otherwise
        """
        # Must be a list item (starts with "- ")
        if not line.strip().startswith("- "):
            return None

        # Pattern to match: **[Name](url)** - description
        # Allow optional <img> tag before the bold link
        pattern = r"\*\*\[([^\]]+)\]\(([^\)]+)\)\*\*\s*[-–]\s*(.+)"
        match = re.search(pattern, line)

        if not match:
            return None

        name = match.group(1).strip()
        url = match.group(2).strip()
        description = match.group(3).strip()

        # Generate slug from name (lowercase, replace spaces/special chars with hyphens)
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

        # Construct tool ID
        tool_id = f"mcp-official:{slug}"

        return Tool(
            id=tool_id,
            name=name,
            source="mcp-official",
            source_url=url,
            tool_type=ToolType.MCP_SERVER,
            description=description,
            tags=tags,
            last_seen=datetime.now(timezone.utc),
        )
