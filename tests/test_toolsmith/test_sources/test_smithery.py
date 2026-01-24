"""Tests for Smithery source adapter."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from cub.core.toolsmith.exceptions import NetworkError
from cub.core.toolsmith.models import ToolType
from cub.core.toolsmith.sources.base import get_source
from cub.core.toolsmith.sources.smithery import SmitherySource


@pytest.fixture
def sample_api_response() -> dict:
    """Load sample API response from fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "smithery_response.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def smithery_source() -> SmitherySource:
    """Create SmitherySource instance."""
    return SmitherySource()


class TestSmitherySource:
    """Test suite for SmitherySource."""

    def test_source_registration(self) -> None:
        """Test that source is properly registered."""
        source = get_source("smithery")
        assert isinstance(source, SmitherySource)
        assert source.name == "smithery"

    def test_name_property(self, smithery_source: SmitherySource) -> None:
        """Test name property returns correct value."""
        assert smithery_source.name == "smithery"

    @patch("httpx.get")
    def test_fetch_tools_success(
        self, mock_get: Mock, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test successful tool fetching from API."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = smithery_source.fetch_tools()

        # Verify HTTP call
        mock_get.assert_called_once()
        call_args = mock_get.call_args

        # Check URL and parameters
        assert call_args.args[0] == f"{SmitherySource.API_BASE_URL}/servers"
        assert call_args.kwargs["params"]["page"] == "1"
        assert call_args.kwargs["params"]["pageSize"] == "50"

        # Verify tools were parsed
        assert len(tools) == 5
        assert all(tool.source == "smithery" for tool in tools)
        assert all(tool.tool_type == ToolType.MCP_SERVER for tool in tools)
        assert all(tool.id.startswith("smithery:") for tool in tools)

    @patch("time.sleep")
    @patch("httpx.get")
    def test_fetch_tools_network_error(
        self, mock_get: Mock, mock_sleep: Mock, smithery_source: SmitherySource
    ) -> None:
        """Test graceful handling of network errors."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Network error")

        with pytest.raises(NetworkError, match="HTTP error"):
            smithery_source.fetch_tools()

    @patch("httpx.get")
    def test_fetch_tools_pagination(self, mock_get: Mock, smithery_source: SmitherySource) -> None:
        """Test pagination handling when fetching all tools."""
        # Create response for page 1
        page1_response = {
            "servers": [
                {
                    "qualifiedName": "author/server1",
                    "displayName": "Server 1",
                    "description": "Description 1",
                    "homepage": "https://smithery.ai/server/author/server1",
                    "useCount": 100,
                    "isDeployed": True,
                    "remote": True,
                    "createdAt": "2024-01-01T00:00:00Z",
                }
            ],
            "pagination": {"currentPage": 1, "pageSize": 1, "totalPages": 2, "totalCount": 2},
        }

        # Create response for page 2
        page2_response = {
            "servers": [
                {
                    "qualifiedName": "author/server2",
                    "displayName": "Server 2",
                    "description": "Description 2",
                    "homepage": "https://smithery.ai/server/author/server2",
                    "useCount": 50,
                    "isDeployed": True,
                    "remote": True,
                    "createdAt": "2024-01-02T00:00:00Z",
                }
            ],
            "pagination": {"currentPage": 2, "pageSize": 1, "totalPages": 2, "totalCount": 2},
        }

        # Mock to return different responses for each page
        mock_response1 = Mock()
        mock_response1.json.return_value = page1_response
        mock_response1.raise_for_status = Mock()

        mock_response2 = Mock()
        mock_response2.json.return_value = page2_response
        mock_response2.raise_for_status = Mock()

        mock_get.side_effect = [mock_response1, mock_response2]

        tools = smithery_source.fetch_tools()

        # Should have fetched both pages
        assert len(tools) == 2
        assert mock_get.call_count == 2
        assert any("server1" in tool.id for tool in tools)
        assert any("server2" in tool.id for tool in tools)

    def test_parse_server_basic(
        self, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test parsing a basic server entry."""
        server_data = sample_api_response["servers"][0]
        tool = smithery_source._parse_server(server_data)

        assert tool.id == "smithery:modelcontextprotocol/fetch"
        assert tool.name == "Fetch"
        assert tool.source == "smithery"
        assert tool.source_url == "https://smithery.ai/server/modelcontextprotocol/fetch"
        assert tool.tool_type == ToolType.MCP_SERVER
        assert tool.description == "Fetch web content and convert to markdown"
        assert tool.last_seen is not None

    def test_parse_server_with_install_hint(
        self, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test that deployed servers get install hints."""
        server_data = sample_api_response["servers"][0]  # isDeployed: true
        tool = smithery_source._parse_server(server_data)

        assert tool.install_hint == "smithery install modelcontextprotocol/fetch"
        assert "deployed" in tool.tags
        assert "remote" in tool.tags

    def test_parse_server_not_deployed(
        self, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test that non-deployed servers have no install hint."""
        server_data = sample_api_response["servers"][2]  # isDeployed: false
        tool = smithery_source._parse_server(server_data)

        assert tool.install_hint == ""
        assert "deployed" not in tool.tags

    def test_parse_server_qualified_name_in_id(
        self, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test that qualified names are preserved in tool IDs."""
        # Test with qualified name containing slash
        server_data = sample_api_response["servers"][1]  # weather/openweather
        tool = smithery_source._parse_server(server_data)

        assert tool.id == "smithery:weather/openweather"

        # Test with longer qualified name
        server_data = sample_api_response["servers"][3]  # analytics/google-analytics
        tool = smithery_source._parse_server(server_data)

        assert tool.id == "smithery:analytics/google-analytics"

    def test_parse_server_timestamp_parsing(
        self, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test that timestamps are parsed correctly."""
        server_data = sample_api_response["servers"][0]
        tool = smithery_source._parse_server(server_data)

        assert tool.last_seen is not None
        assert tool.last_seen.year == 2024
        assert tool.last_seen.month == 1
        assert tool.last_seen.day == 15

    @patch("httpx.get")
    def test_search_live_success(
        self, mock_get: Mock, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test live search with query."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results = smithery_source.search_live("weather")

        # Verify HTTP call includes query parameter
        call_args = mock_get.call_args
        assert call_args.kwargs["params"]["q"] == "weather"

        # Should return tools
        assert len(results) > 0

    @patch("time.sleep")
    @patch("httpx.get")
    def test_search_live_network_error(
        self, mock_get: Mock, mock_sleep: Mock, smithery_source: SmitherySource
    ) -> None:
        """Test that search handles network errors gracefully."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Network error")

        with pytest.raises(NetworkError, match="HTTP error"):
            smithery_source.search_live("test")

    @patch("httpx.get")
    def test_api_authentication_header(
        self, mock_get: Mock, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test that API token is included in headers when available."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock environment variable
        with patch.dict("os.environ", {"SMITHERY_API_TOKEN": "test-token-123"}):
            smithery_source.fetch_tools()

        # Verify authorization header was included
        call_args = mock_get.call_args
        headers = call_args.kwargs["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-token-123"

    @patch("httpx.get")
    def test_api_without_authentication(
        self, mock_get: Mock, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test that API calls work without authentication token."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Ensure no API token in environment
        with patch.dict("os.environ", {}, clear=True):
            smithery_source.fetch_tools()

        # Verify no authorization header
        call_args = mock_get.call_args
        headers = call_args.kwargs["headers"]
        assert "Authorization" not in headers

    def test_all_tools_have_required_fields(
        self, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test that all parsed tools have required fields populated."""
        servers = sample_api_response["servers"]

        for server_data in servers:
            tool = smithery_source._parse_server(server_data)

            # Required fields must be non-empty
            assert tool.id, f"Tool {tool.name} missing id"
            assert tool.name, "Tool missing name"
            assert tool.source == "smithery"
            assert tool.source_url, f"Tool {tool.name} missing source_url"
            assert tool.tool_type == ToolType.MCP_SERVER
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.last_seen is not None

            # ID format validation
            assert tool.id.startswith("smithery:")
            assert ":" in tool.id
            parts = tool.id.split(":", 1)
            assert len(parts) == 2
            assert parts[1], "Tool qualified name cannot be empty"

    @patch("httpx.get")
    def test_fetch_page_parameters(
        self, mock_get: Mock, smithery_source: SmitherySource, sample_api_response: dict
    ) -> None:
        """Test that _fetch_page passes correct parameters."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        smithery_source._fetch_page(query="test", page=2, page_size=25)

        # Verify parameters
        call_args = mock_get.call_args
        params = call_args.kwargs["params"]
        assert params["q"] == "test"
        assert params["page"] == "2"
        assert params["pageSize"] == "25"

    @patch("httpx.get")
    def test_handles_missing_optional_fields(
        self, mock_get: Mock, smithery_source: SmitherySource
    ) -> None:
        """Test that parser handles missing optional fields gracefully."""
        minimal_response = {
            "servers": [
                {
                    "qualifiedName": "minimal/server",
                    "displayName": "Minimal Server",
                    "description": "A minimal server entry",
                    # Missing: homepage, iconUrl, useCount, isDeployed, remote, createdAt
                }
            ],
            "pagination": {"currentPage": 1, "pageSize": 50, "totalPages": 1, "totalCount": 1},
        }

        mock_response = Mock()
        mock_response.json.return_value = minimal_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = smithery_source.fetch_tools()

        assert len(tools) == 1
        tool = tools[0]
        assert tool.id == "smithery:minimal/server"
        assert tool.name == "Minimal Server"
        assert tool.description == "A minimal server entry"
        # Should use default homepage
        assert "smithery.ai/server/minimal/server" in tool.source_url
