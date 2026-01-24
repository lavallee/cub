"""
Glama.ai source adapter.

Fetches MCP servers from Glama.ai, the largest directory of Model Context Protocol servers.
Uses the Glama public API to discover servers, descriptions, and metadata.

Example:
    >>> from cub.core.toolsmith.sources.glama import GlamaSource
    >>> source = GlamaSource()
    >>> tools = source.fetch_tools()
    >>> len(tools) > 0
    True
    >>> results = source.search_live("weather")
    >>> any("weather" in tool.name.lower() for tool in results)
    True
"""

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from cub.core.toolsmith.models import Tool, ToolType
from cub.core.toolsmith.sources.base import register_source


@register_source("glama")
class GlamaSource:
    """
    Tool source for Glama.ai MCP server directory.

    Fetches server listings from the Glama public API. The API provides
    server metadata including names, descriptions, repository URLs,
    environment variables, and tool definitions.

    API Endpoints:
    - List: GET https://glama.ai/api/mcp/v1/servers?cursor={cursor}
    - Search: GET https://glama.ai/api/mcp/v1/servers?query={query}
    - Get Server: GET https://glama.ai/api/mcp/v1/servers/{namespace}/{slug}

    Response Format:
    {
      "servers": [
        {
          "id": "server-id",
          "name": "Server Name",
          "slug": "server-slug",
          "namespace": "author",
          "description": "Server description",
          "url": "https://glama.ai/mcp/servers/server-id",
          "repository": {
            "url": "https://github.com/author/repo"
          },
          "spdxLicense": "MIT",
          "attributes": ["hosting:remote-capable"],
          "tools": [],
          "environmentVariablesJsonSchema": {...}
        }
      ],
      "pageInfo": {
        "hasNextPage": true,
        "hasPreviousPage": false,
        "startCursor": "...",
        "endCursor": "..."
      }
    }
    """

    API_BASE_URL = "https://glama.ai/api/mcp/v1"

    @property
    def name(self) -> str:
        """Get the name of this source."""
        return "glama"

    def fetch_tools(self) -> list[Tool]:
        """
        Fetch all available MCP servers from Glama.ai.

        Queries the Glama API to retrieve all servers, paginating through
        results using cursor-based pagination. Each server is converted to
        a Tool object with:
        - id: "glama:{server-id}"
        - name: Display name from API
        - source: "glama"
        - source_url: Server URL on Glama
        - tool_type: MCP_SERVER
        - description: Server description
        - install_hint: Repository URL if available
        - tags: Attributes from API (hosting type, etc.)

        Returns:
            List of Tool objects representing Glama MCP servers

        Raises:
            httpx.HTTPError: If API request fails
        """
        all_tools = []
        cursor = None

        while True:
            try:
                servers, page_info = self._fetch_page(cursor=cursor)
                all_tools.extend(servers)

                # Check if there are more pages
                if not page_info.get("hasNextPage", False):
                    break

                cursor = page_info.get("endCursor")
                if not cursor:
                    break

            except httpx.HTTPError:
                # Gracefully handle network errors
                # If we already have some results, return them
                # Otherwise, return empty list
                break

        return all_tools

    def search_live(self, query: str) -> list[Tool]:
        """
        Search for MCP servers matching a query on Glama.ai.

        Uses the Glama API search parameter to filter servers. The API
        performs server-side filtering, making this more efficient than
        client-side filtering.

        Args:
            query: Search query string

        Returns:
            List of Tool objects matching the search query
        """
        try:
            tools, _ = self._fetch_page(query=query)
            return tools
        except httpx.HTTPError:
            # Gracefully handle network errors by returning empty list
            return []

    def _fetch_page(
        self, query: str = "", cursor: str | None = None
    ) -> tuple[list[Tool], dict[str, Any]]:
        """
        Fetch a single page of servers from the Glama API.

        Args:
            query: Optional search query to filter servers
            cursor: Optional pagination cursor for next page

        Returns:
            Tuple of (list of Tool objects, pageInfo dict)

        Raises:
            httpx.HTTPError: If API request fails
        """
        # Build API URL with query parameters
        params: dict[str, str] = {}
        if query:
            params["query"] = query
        if cursor:
            params["cursor"] = cursor

        # Prepare headers
        headers = {"Accept": "application/json"}

        # Add authentication if available (optional for Glama)
        api_token = os.environ.get("GLAMA_API_TOKEN")
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        # Make API request
        url = f"{self.API_BASE_URL}/servers"
        response = httpx.get(
            url, params=params, headers=headers, timeout=30.0, follow_redirects=True
        )
        response.raise_for_status()

        # Parse JSON response
        data = response.json()
        servers_data = data.get("servers", [])
        page_info = data.get("pageInfo", {})

        # Convert server entries to Tool objects
        tools = [self._parse_server(server) for server in servers_data]

        return tools, page_info

    def _parse_server(self, server: dict[str, Any]) -> Tool:
        """
        Parse a server entry from the API response into a Tool object.

        Args:
            server: Server dictionary from API response

        Returns:
            Tool object representing the server
        """
        server_id = server.get("id", "")
        name = server.get("name", "")
        description = server.get("description", "")
        url = server.get("url", f"https://glama.ai/mcp/servers/{server_id}")
        repository = server.get("repository", {})
        repo_url = repository.get("url", "") if repository else ""
        license_info = server.get("spdxLicense", "")
        attributes = server.get("attributes", [])

        # Generate tool ID from server ID
        # Tool ID format: "glama:{server-id}"
        tool_id = f"glama:{server_id}"

        # Build tags from attributes
        tags = list(attributes) if attributes else []
        if license_info:
            tags.append(f"license:{license_info}")

        # Build install hint from repository URL
        install_hint = ""
        if repo_url and repo_url != "https://github.com/undefined":
            install_hint = f"See installation instructions at: {repo_url}"

        # Use current time as last_seen since API doesn't provide timestamp
        last_seen = datetime.now(timezone.utc)

        return Tool(
            id=tool_id,
            name=name,
            source="glama",
            source_url=url,
            tool_type=ToolType.MCP_SERVER,
            description=description,
            install_hint=install_hint,
            tags=tags,
            last_seen=last_seen,
        )
