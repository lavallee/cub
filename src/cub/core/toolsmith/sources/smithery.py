"""
Smithery.ai source adapter.

Fetches MCP servers from the Smithery community marketplace at smithery.ai.
Uses the Smithery Registry API to discover servers, descriptions, and metadata.

Example:
    >>> from cub.core.toolsmith.sources.smithery import SmitherySource
    >>> source = SmitherySource()
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
from pydantic import ValidationError

from cub.core.toolsmith.exceptions import NetworkError, ParseError
from cub.core.toolsmith.http import with_retry
from cub.core.toolsmith.models import Tool, ToolType
from cub.core.toolsmith.sources.base import register_source


@register_source("smithery")
class SmitherySource:
    """
    Tool source for Smithery.ai MCP server marketplace.

    Fetches server listings from the Smithery Registry API. The API provides
    server metadata including qualified names, descriptions, homepage URLs,
    deployment status, and usage statistics.

    The API requires authentication via a bearer token. Set the environment
    variable SMITHERY_API_TOKEN to authenticate requests. If not set, the
    source will attempt to fetch without authentication (may have rate limits).

    API Endpoints:
    - List/Search: GET https://registry.smithery.ai/servers?q={query}&page={page}&pageSize={pageSize}
    - Get Server: GET https://registry.smithery.ai/servers/{qualifiedName}

    Response Format:
    {
      "servers": [
        {
          "qualifiedName": "author/server-name",
          "displayName": "Server Name",
          "description": "Server description",
          "homepage": "https://smithery.ai/server/author/server-name",
          "iconUrl": "https://...",
          "useCount": 100,
          "isDeployed": true,
          "remote": true,
          "createdAt": "2024-01-01T00:00:00Z"
        }
      ],
      "pagination": {
        "currentPage": 1,
        "pageSize": 50,
        "totalPages": 5,
        "totalCount": 250
      }
    }
    """

    API_BASE_URL = "https://registry.smithery.ai"

    @property
    def name(self) -> str:
        """Get the name of this source."""
        return "smithery"

    def fetch_tools(self) -> list[Tool]:
        """
        Fetch all available MCP servers from Smithery.ai.

        Queries the Smithery Registry API to retrieve all servers, paginating
        through results as needed. Each server is converted to a Tool object with:
        - id: "smithery:{qualified-name}"
        - name: Display name from API
        - source: "smithery"
        - source_url: Homepage URL
        - tool_type: MCP_SERVER
        - description: Server description
        - install_hint: CLI command if available
        - tags: Metadata tags (verified, deployed, remote)

        Returns:
            List of Tool objects representing Smithery MCP servers

        Raises:
            NetworkError: If API request fails
            ParseError: If response parsing fails
        """
        all_tools = []
        page = 1
        page_size = 50

        while True:
            try:
                servers, pagination = self._fetch_page(page=page, page_size=page_size)
                all_tools.extend(servers)

                # Check if we've fetched all pages
                if page >= pagination.get("totalPages", 1):
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
        Search for MCP servers matching a query on Smithery.ai.

        Uses the Smithery Registry API search endpoint with the query parameter.
        The API performs server-side filtering, making this more efficient than
        client-side filtering.

        Args:
            query: Search query string

        Returns:
            List of Tool objects matching the search query

        Raises:
            NetworkError: If API request fails
            ParseError: If response parsing fails
        """
        tools, _ = self._fetch_page(query=query, page=1, page_size=50)
        return tools

    @with_retry(max_retries=3, base_delay=1.0, multiplier=2.0)
    def _make_request(
        self, url: str, params: dict[str, str], headers: dict[str, str]
    ) -> httpx.Response:
        """
        Make HTTP GET request with retry logic.

        Retries on transient errors (5xx, timeout, connection errors).
        Does not retry on 4xx errors (client errors).

        Args:
            url: URL to request
            params: Query parameters
            headers: Request headers

        Returns:
            HTTP response object

        Raises:
            httpx.HTTPStatusError: On HTTP errors
            httpx.TimeoutException: On timeout
            httpx.RequestError: On network errors
        """
        response = httpx.get(
            url, params=params, headers=headers, timeout=30.0, follow_redirects=True
        )
        response.raise_for_status()
        return response

    def _fetch_page(
        self, query: str = "", page: int = 1, page_size: int = 50
    ) -> tuple[list[Tool], dict[str, Any]]:
        """
        Fetch a single page of servers from the Smithery Registry API.

        Args:
            query: Optional search query to filter servers
            page: Page number (1-indexed)
            page_size: Number of results per page

        Returns:
            Tuple of (list of Tool objects, pagination metadata dict)

        Raises:
            NetworkError: If API request fails
            ParseError: If response parsing fails
        """
        # Build API URL with query parameters
        params = {"page": str(page), "pageSize": str(page_size)}
        if query:
            params["q"] = query

        # Prepare headers
        headers = {"Accept": "application/json"}

        # Add authentication if available
        api_token = os.environ.get("SMITHERY_API_TOKEN")
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        # Make API request with retry logic
        url = f"{self.API_BASE_URL}/servers"
        try:
            response = self._make_request(url, params, headers)
        except httpx.TimeoutException as e:
            raise NetworkError(
                "smithery",
                "Request timed out while fetching servers from Smithery API",
                url=url,
                timeout=30.0,
            ) from e
        except httpx.HTTPStatusError as e:
            raise NetworkError(
                "smithery",
                f"HTTP {e.response.status_code} error from Smithery API",
                url=url,
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(
                "smithery",
                f"Network error while fetching from Smithery API: {e}",
                url=url,
            ) from e
        except httpx.HTTPError as e:
            raise NetworkError(
                "smithery",
                f"HTTP error while fetching data: {e}",
                url=url,
            ) from e

        # Parse JSON response
        try:
            data = response.json()
        except Exception as e:
            raise ParseError(
                "smithery",
                "Failed to parse JSON response from Smithery API",
                url=url,
            ) from e

        # Extract data with error handling
        try:
            servers_data = data.get("servers", [])
            pagination = data.get("pagination", {})
        except AttributeError as e:
            raise ParseError(
                "smithery",
                "Response is not a valid JSON object",
                url=url,
                response_type=type(data).__name__,
            ) from e

        # Convert server entries to Tool objects
        try:
            tools = [self._parse_server(server) for server in servers_data]
        except (KeyError, ValueError, ValidationError) as e:
            raise ParseError(
                "smithery",
                f"Failed to parse server data: {e}",
                url=url,
            ) from e

        return tools, pagination

    def _parse_server(self, server: dict[str, Any]) -> Tool:
        """
        Parse a server entry from the API response into a Tool object.

        Args:
            server: Server dictionary from API response

        Returns:
            Tool object representing the server
        """
        qualified_name = server.get("qualifiedName", "")
        display_name = server.get("displayName", qualified_name)
        description = server.get("description", "")
        homepage = server.get("homepage", f"https://smithery.ai/server/{qualified_name}")
        is_deployed = server.get("isDeployed", False)
        is_remote = server.get("remote", False)
        created_at = server.get("createdAt")

        # Generate tool ID from qualified name
        # Qualified name format: "author/server-name"
        # Tool ID format: "smithery:author/server-name"
        tool_id = f"smithery:{qualified_name}"

        # Build tags
        tags = []
        if is_deployed:
            tags.append("deployed")
        if is_remote:
            tags.append("remote")

        # Build install hint if server is deployed
        install_hint = ""
        if is_deployed:
            install_hint = f"smithery install {qualified_name}"

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
            name=display_name,
            source="smithery",
            source_url=homepage,
            tool_type=ToolType.MCP_SERVER,
            description=description,
            install_hint=install_hint,
            tags=tags,
            last_seen=last_seen,
        )
