"""Tests for MCP Official source adapter."""

from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from cub.core.toolsmith.exceptions import NetworkError
from cub.core.toolsmith.models import ToolType
from cub.core.toolsmith.sources.base import get_source
from cub.core.toolsmith.sources.mcp_official import MCPOfficialSource


@pytest.fixture
def sample_readme_content() -> str:
    """Load sample README content from fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "mcp_official_readme_sample.md"
    return fixture_path.read_text()


@pytest.fixture
def mcp_source() -> MCPOfficialSource:
    """Create MCPOfficialSource instance."""
    return MCPOfficialSource()


class TestMCPOfficialSource:
    """Test suite for MCPOfficialSource."""

    def test_source_registration(self) -> None:
        """Test that source is properly registered."""
        source = get_source("mcp-official")
        assert isinstance(source, MCPOfficialSource)
        assert source.name == "mcp-official"

    def test_name_property(self, mcp_source: MCPOfficialSource) -> None:
        """Test name property returns correct value."""
        assert mcp_source.name == "mcp-official"

    @patch("httpx.get")
    def test_fetch_tools_success(
        self, mock_get: Mock, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test successful tool fetching and parsing."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = sample_readme_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = mcp_source.fetch_tools()

        # Verify HTTP call
        mock_get.assert_called_once_with(
            MCPOfficialSource.README_URL, timeout=30.0, follow_redirects=True
        )

        # Verify tools were parsed
        assert len(tools) > 0
        assert all(tool.source == "mcp-official" for tool in tools)
        assert all(tool.tool_type == ToolType.MCP_SERVER for tool in tools)
        assert all(tool.id.startswith("mcp-official:") for tool in tools)

    @patch("time.sleep")
    @patch("httpx.get")
    def test_fetch_tools_network_error(
        self, mock_get: Mock, mock_sleep: Mock, mcp_source: MCPOfficialSource
    ) -> None:
        """Test graceful handling of network errors."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Network error")

        with pytest.raises(NetworkError, match="HTTP error"):
            mcp_source.fetch_tools()

    def test_parse_readme_reference_servers(
        self, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test parsing of reference servers section."""
        tools = mcp_source._parse_readme(sample_readme_content)

        # Find reference servers
        reference_tools = [
            t
            for t in tools
            if "reference-servers" in t.tags or "reference servers" in " ".join(t.tags)
        ]

        assert len(reference_tools) > 0

        # Check specific servers
        fetch_tool = next((t for t in tools if "Fetch" in t.name), None)
        assert fetch_tool is not None
        assert fetch_tool.id == "mcp-official:fetch"
        assert fetch_tool.name == "Fetch"
        assert "Web content fetching" in fetch_tool.description
        assert fetch_tool.source_url == "src/fetch"
        assert fetch_tool.last_seen is not None

        git_tool = next((t for t in tools if "Git" == t.name), None)
        assert git_tool is not None
        assert git_tool.id == "mcp-official:git"
        assert "Git repositories" in git_tool.description

    def test_parse_readme_archived_servers(
        self, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test parsing of archived servers section."""
        tools = mcp_source._parse_readme(sample_readme_content)

        # Find archived servers
        github_tool = next(
            (
                t
                for t in tools
                if "GitHub" in t.name and "Repository management" in t.description
            ),
            None,
        )
        assert github_tool is not None
        assert github_tool.id == "mcp-official:github"
        assert "https://github.com/modelcontextprotocol/servers-archived" in github_tool.source_url

    def test_parse_readme_third_party_servers(
        self, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test parsing of third-party servers with favicon images."""
        tools = mcp_source._parse_readme(sample_readme_content)

        # Find third-party servers
        algolia_tool = next((t for t in tools if "Algolia" in t.name), None)
        assert algolia_tool is not None
        assert algolia_tool.id == "mcp-official:algolia"
        assert "search indices" in algolia_tool.description
        assert algolia_tool.source_url == "https://github.com/algolia/mcp"

        apify_tool = next((t for t in tools if "Apify" in t.name), None)
        assert apify_tool is not None
        assert "6,000+" in apify_tool.description

    def test_parse_readme_handles_special_chars_in_name(
        self, mcp_source: MCPOfficialSource
    ) -> None:
        """Test that server names with special characters are slugified correctly."""
        content = """
## Test Section

- **[Sequential Thinking](src/test)** - Test description.
- **[Apollo MCP Server](https://example.com)** - Another test.
"""
        tools = mcp_source._parse_readme(content)

        assert len(tools) == 2

        sequential_tool = next((t for t in tools if "Sequential" in t.name), None)
        assert sequential_tool is not None
        assert sequential_tool.id == "mcp-official:sequential-thinking"

        apollo_tool = next((t for t in tools if "Apollo" in t.name), None)
        assert apollo_tool is not None
        assert apollo_tool.id == "mcp-official:apollo-mcp-server"

    def test_extract_section_name(self, mcp_source: MCPOfficialSource) -> None:
        """Test section name extraction from headers."""
        result = mcp_source._extract_section_name("## 🌟 Reference Servers")
        assert result == "Reference Servers"
        result = mcp_source._extract_section_name("### 🎖️ Official Integrations")
        assert result == "Official Integrations"
        assert mcp_source._extract_section_name("## Archived") == "Archived"

    def test_parse_server_entry_basic(self, mcp_source: MCPOfficialSource) -> None:
        """Test parsing a basic server entry."""
        line = "- **[Git](src/git)** - Tools to read, search, and manipulate Git repositories."
        tool = mcp_source._parse_server_entry(line, ["reference-servers"])

        assert tool is not None
        assert tool.id == "mcp-official:git"
        assert tool.name == "Git"
        assert tool.source_url == "src/git"
        assert tool.description == "Tools to read, search, and manipulate Git repositories."
        assert "reference-servers" in tool.tags

    def test_parse_server_entry_with_image(self, mcp_source: MCPOfficialSource) -> None:
        """Test parsing a server entry with favicon image."""
        line = (
            '- <img height="12" width="12" src="https://algolia.com/favicon.ico" /> '
            '**[Algolia](https://github.com/algolia/mcp)** - '
            "Use AI agents to provision search indices."
        )
        tool = mcp_source._parse_server_entry(
            line, ["third-party", "official-integrations"]
        )

        assert tool is not None
        assert tool.id == "mcp-official:algolia"
        assert tool.name == "Algolia"
        assert tool.source_url == "https://github.com/algolia/mcp"
        assert "search indices" in tool.description
        assert "third-party" in tool.tags
        assert "official-integrations" in tool.tags

    def test_parse_server_entry_invalid(self, mcp_source: MCPOfficialSource) -> None:
        """Test parsing invalid server entry returns None."""
        # Missing bold markers
        line = "- [Git](src/git) - Tools to read Git repositories."
        assert mcp_source._parse_server_entry(line, []) is None

        # Not a list item
        line = "This is just text **[Git](src/git)** - Description"
        assert mcp_source._parse_server_entry(line, []) is None

        # Missing description separator
        line = "- **[Git](src/git)** Tools to read Git repositories."
        assert mcp_source._parse_server_entry(line, []) is None

    @patch("httpx.get")
    def test_search_live_by_name(
        self, mock_get: Mock, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test live search filtering by name."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = sample_readme_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results = mcp_source.search_live("Git")

        assert len(results) > 0
        assert any("git" in tool.name.lower() for tool in results)

    @patch("httpx.get")
    def test_search_live_by_description(
        self, mock_get: Mock, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test live search filtering by description."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = sample_readme_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results = mcp_source.search_live("GraphQL")

        assert len(results) > 0
        apollo_tool = next((t for t in results if "Apollo" in t.name), None)
        assert apollo_tool is not None
        assert "GraphQL" in apollo_tool.description

    @patch("httpx.get")
    def test_search_live_case_insensitive(
        self, mock_get: Mock, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test that search is case-insensitive."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = sample_readme_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results_lower = mcp_source.search_live("git")
        results_upper = mcp_source.search_live("GIT")
        results_mixed = mcp_source.search_live("Git")

        # All should return the same results
        assert len(results_lower) == len(results_upper) == len(results_mixed)
        assert len(results_lower) > 0

    @patch("httpx.get")
    def test_search_live_no_matches(
        self, mock_get: Mock, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test search with no matching results."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.text = sample_readme_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results = mcp_source.search_live("nonexistent-tool-xyz-123")

        assert results == []

    def test_all_tools_have_required_fields(
        self, mcp_source: MCPOfficialSource, sample_readme_content: str
    ) -> None:
        """Test that all parsed tools have required fields populated."""
        tools = mcp_source._parse_readme(sample_readme_content)

        for tool in tools:
            # Required fields must be non-empty
            assert tool.id, f"Tool {tool.name} missing id"
            assert tool.name, "Tool missing name"
            assert tool.source == "mcp-official"
            assert tool.source_url, f"Tool {tool.name} missing source_url"
            assert tool.tool_type == ToolType.MCP_SERVER
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.last_seen is not None

            # ID format validation
            assert tool.id.startswith("mcp-official:")
            assert ":" in tool.id
            parts = tool.id.split(":")
            assert len(parts) == 2
            assert parts[1], "Tool slug cannot be empty"
