"""Tests for Glama source adapter."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

from cub.core.toolsmith.models import ToolType
from cub.core.toolsmith.sources.base import get_source
from cub.core.toolsmith.sources.glama import GlamaSource


@pytest.fixture
def sample_api_response() -> dict[str, Any]:
    """Load sample API response from fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "glama_response.json"
    return json.loads(fixture_path.read_text())  # type: ignore[no-any-return]


@pytest.fixture
def glama_source() -> GlamaSource:
    """Create GlamaSource instance."""
    return GlamaSource()


class TestGlamaSource:
    """Test suite for GlamaSource."""

    def test_source_registration(self) -> None:
        """Test that source is properly registered."""
        source = get_source("glama")
        assert isinstance(source, GlamaSource)
        assert source.name == "glama"

    def test_name_property(self, glama_source: GlamaSource) -> None:
        """Test name property returns correct value."""
        assert glama_source.name == "glama"

    @patch("httpx.get")
    def test_fetch_tools_success(
        self, mock_get: Mock, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test successful tool fetching from API."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = glama_source.fetch_tools()

        # Verify HTTP call
        mock_get.assert_called_once()
        call_args = mock_get.call_args

        # Check URL
        assert call_args.args[0] == f"{GlamaSource.API_BASE_URL}/servers"

        # Verify tools were parsed
        assert len(tools) == 10
        assert all(tool.source == "glama" for tool in tools)
        assert all(tool.tool_type == ToolType.MCP_SERVER for tool in tools)
        assert all(tool.id.startswith("glama:") for tool in tools)

    @patch("httpx.get")
    def test_fetch_tools_network_error(self, mock_get: Mock, glama_source: GlamaSource) -> None:
        """Test graceful handling of network errors."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Network error")

        tools = glama_source.fetch_tools()

        # Should return empty list on error
        assert tools == []

    @patch("httpx.get")
    def test_fetch_tools_pagination(self, mock_get: Mock, glama_source: GlamaSource) -> None:
        """Test pagination handling when fetching all tools."""
        # Create response for page 1
        page1_response = {
            "servers": [
                {
                    "id": "server1",
                    "name": "Server 1",
                    "slug": "server-1",
                    "namespace": "author",
                    "description": "Description 1",
                    "url": "https://glama.ai/mcp/servers/server1",
                    "repository": {"url": "https://github.com/author/server1"},
                    "spdxLicense": "MIT",
                    "attributes": ["hosting:remote-capable"],
                    "tools": [],
                }
            ],
            "pageInfo": {
                "hasNextPage": True,
                "hasPreviousPage": False,
                "startCursor": "cursor1",
                "endCursor": "cursor2",
            },
        }

        # Create response for page 2
        page2_response = {
            "servers": [
                {
                    "id": "server2",
                    "name": "Server 2",
                    "slug": "server-2",
                    "namespace": "author",
                    "description": "Description 2",
                    "url": "https://glama.ai/mcp/servers/server2",
                    "repository": {"url": "https://github.com/author/server2"},
                    "spdxLicense": "Apache-2.0",
                    "attributes": ["hosting:hybrid"],
                    "tools": [],
                }
            ],
            "pageInfo": {
                "hasNextPage": False,
                "hasPreviousPage": True,
                "startCursor": "cursor2",
                "endCursor": "cursor3",
            },
        }

        # Mock to return different responses for each page
        mock_response1 = Mock()
        mock_response1.json.return_value = page1_response
        mock_response1.raise_for_status = Mock()

        mock_response2 = Mock()
        mock_response2.json.return_value = page2_response
        mock_response2.raise_for_status = Mock()

        mock_get.side_effect = [mock_response1, mock_response2]

        tools = glama_source.fetch_tools()

        # Should have fetched both pages
        assert len(tools) == 2
        assert mock_get.call_count == 2
        assert any("server1" in tool.id for tool in tools)
        assert any("server2" in tool.id for tool in tools)

    def test_parse_server_basic(
        self, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test parsing a basic server entry."""
        server_data = sample_api_response["servers"][0]
        tool = glama_source._parse_server(server_data)

        assert tool.id == "glama:wl91nncvbq"
        assert tool.name == "TS-MCP"
        assert tool.source == "glama"
        assert tool.source_url == "https://glama.ai/mcp/servers/wl91nncvbq"
        assert tool.tool_type == ToolType.MCP_SERVER
        assert tool.description.startswith("An MCP server for conversational FHIR testing")
        assert tool.last_seen is not None

    def test_parse_server_with_repository(
        self, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that servers with repositories get install hints."""
        server_data = sample_api_response["servers"][0]
        tool = glama_source._parse_server(server_data)

        assert "github.com" in tool.install_hint
        assert "AEGISnetInc/TS-MCP" in tool.install_hint

    def test_parse_server_with_attributes(
        self, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that attributes are converted to tags."""
        server_data = sample_api_response["servers"][0]
        tool = glama_source._parse_server(server_data)

        assert "hosting:remote-capable" in tool.tags

    def test_parse_server_with_license(
        self, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that license info is added to tags."""
        # Find a server with a license (if any)
        server_data: dict[str, Any]
        for server_data in sample_api_response["servers"]:
            if server_data.get("spdxLicense"):
                tool = glama_source._parse_server(server_data)
                assert any(tag.startswith("license:") for tag in tool.tags)
                break

    def test_parse_server_without_repository(self, glama_source: GlamaSource) -> None:
        """Test that servers without valid repositories have no install hint."""
        server_data: dict[str, Any] = {
            "id": "test123",
            "name": "Test Server",
            "slug": "test-server",
            "namespace": "test",
            "description": "A test server",
            "url": "https://glama.ai/mcp/servers/test123",
            "repository": {"url": "https://github.com/undefined"},
            "spdxLicense": None,
            "attributes": [],
            "tools": [],
        }
        tool = glama_source._parse_server(server_data)

        assert tool.install_hint == ""

    @patch("httpx.get")
    def test_search_live_success(
        self, mock_get: Mock, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test live search with query."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results = glama_source.search_live("weather")

        # Verify HTTP call includes query parameter
        call_args = mock_get.call_args
        assert call_args.kwargs["params"]["query"] == "weather"

        # Should return tools
        assert len(results) > 0

    @patch("httpx.get")
    def test_search_live_network_error(self, mock_get: Mock, glama_source: GlamaSource) -> None:
        """Test that search handles network errors gracefully."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Network error")

        results = glama_source.search_live("test")

        # Should return empty list on error
        assert results == []

    @patch("httpx.get")
    def test_api_authentication_header(
        self, mock_get: Mock, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that API token is included in headers when available."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock environment variable
        with patch.dict("os.environ", {"GLAMA_API_TOKEN": "test-token-123"}):
            glama_source.fetch_tools()

        # Verify authorization header was included
        call_args = mock_get.call_args
        headers = call_args.kwargs["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-token-123"

    @patch("httpx.get")
    def test_api_without_authentication(
        self, mock_get: Mock, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that API calls work without authentication token."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Ensure no API token in environment
        with patch.dict("os.environ", {}, clear=True):
            glama_source.fetch_tools()

        # Verify no authorization header
        call_args = mock_get.call_args
        headers = call_args.kwargs["headers"]
        assert "Authorization" not in headers

    def test_all_tools_have_required_fields(
        self, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that all parsed tools have required fields populated."""
        servers = sample_api_response["servers"]

        for server_data in servers:
            tool = glama_source._parse_server(server_data)

            # Required fields must be non-empty
            assert tool.id, f"Tool {tool.name} missing id"
            assert tool.name, "Tool missing name"
            assert tool.source == "glama"
            assert tool.source_url, f"Tool {tool.name} missing source_url"
            assert tool.tool_type == ToolType.MCP_SERVER
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.last_seen is not None

            # ID format validation
            assert tool.id.startswith("glama:")
            assert ":" in tool.id
            parts = tool.id.split(":", 1)
            assert len(parts) == 2
            assert parts[1], "Tool server ID cannot be empty"

    @patch("httpx.get")
    def test_fetch_page_parameters(
        self, mock_get: Mock, glama_source: GlamaSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that _fetch_page passes correct parameters."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        glama_source._fetch_page(query="test", cursor="cursor123")

        # Verify parameters
        call_args = mock_get.call_args
        params = call_args.kwargs["params"]
        assert params["query"] == "test"
        assert params["cursor"] == "cursor123"

    @patch("httpx.get")
    def test_handles_missing_optional_fields(
        self, mock_get: Mock, glama_source: GlamaSource
    ) -> None:
        """Test that parser handles missing optional fields gracefully."""
        minimal_response = {
            "servers": [
                {
                    "id": "minimal123",
                    "name": "Minimal Server",
                    "slug": "minimal",
                    "namespace": "test",
                    "description": "A minimal server entry",
                    # Missing: url, repository, spdxLicense, attributes
                }
            ],
            "pageInfo": {
                "hasNextPage": False,
                "hasPreviousPage": False,
                "startCursor": "start",
                "endCursor": "end",
            },
        }

        mock_response = Mock()
        mock_response.json.return_value = minimal_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = glama_source.fetch_tools()

        assert len(tools) == 1
        tool = tools[0]
        assert tool.id == "glama:minimal123"
        assert tool.name == "Minimal Server"
        assert tool.description == "A minimal server entry"
        # Should use default URL based on ID
        assert "glama.ai/mcp/servers/minimal123" in tool.source_url

    @patch("httpx.get")
    def test_pagination_stops_when_no_next_page(
        self, mock_get: Mock, glama_source: GlamaSource
    ) -> None:
        """Test that pagination stops when hasNextPage is False."""
        response = {
            "servers": [
                {
                    "id": "only-server",
                    "name": "Only Server",
                    "slug": "only",
                    "namespace": "test",
                    "description": "Only server",
                    "url": "https://glama.ai/mcp/servers/only-server",
                }
            ],
            "pageInfo": {
                "hasNextPage": False,
                "hasPreviousPage": False,
                "startCursor": "start",
                "endCursor": "end",
            },
        }

        mock_response = Mock()
        mock_response.json.return_value = response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = glama_source.fetch_tools()

        # Should only call API once
        assert mock_get.call_count == 1
        assert len(tools) == 1
