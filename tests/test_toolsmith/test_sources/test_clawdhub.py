"""Tests for ClawdHub source adapter."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from cub.core.toolsmith.exceptions import NetworkError
from cub.core.toolsmith.models import ToolType
from cub.core.toolsmith.sources.base import get_source
from cub.core.toolsmith.sources.clawdhub import ClawdHubSource


@pytest.fixture
def api_response_data() -> list[dict]:
    """Load sample GitHub API response from fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "clawdhub_api_response.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def pdf_skill_content() -> str:
    """Load sample PDF skill SKILL.md content."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "clawdhub_pdf_skill.md"
    return fixture_path.read_text()


@pytest.fixture
def docx_skill_content() -> str:
    """Load sample DOCX skill SKILL.md content."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "clawdhub_docx_skill.md"
    return fixture_path.read_text()


@pytest.fixture
def webapp_testing_skill_content() -> str:
    """Load sample webapp-testing skill SKILL.md content."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "clawdhub_webapp_testing_skill.md"
    )
    return fixture_path.read_text()


@pytest.fixture
def clawdhub_source() -> ClawdHubSource:
    """Create ClawdHubSource instance."""
    return ClawdHubSource()


class TestClawdHubSource:
    """Test suite for ClawdHubSource."""

    def test_source_registration(self) -> None:
        """Test that source is properly registered."""
        source = get_source("clawdhub")
        assert isinstance(source, ClawdHubSource)
        assert source.name == "clawdhub"

    def test_name_property(self, clawdhub_source: ClawdHubSource) -> None:
        """Test name property returns correct value."""
        assert clawdhub_source.name == "clawdhub"

    @patch("httpx.get")
    def test_fetch_tools_success(
        self,
        mock_get: Mock,
        clawdhub_source: ClawdHubSource,
        api_response_data: list[dict],
        pdf_skill_content: str,
        docx_skill_content: str,
        webapp_testing_skill_content: str,
    ) -> None:
        """Test successful tool fetching and parsing."""
        # Mock GitHub API response for directory listing
        mock_api_response = Mock()
        mock_api_response.json.return_value = api_response_data
        mock_api_response.raise_for_status = Mock()

        # Mock individual SKILL.md file responses
        def get_side_effect(url: str, **kwargs):
            if url == ClawdHubSource.API_URL:
                return mock_api_response
            elif "pdf/SKILL.md" in url:
                response = Mock()
                response.text = pdf_skill_content
                response.raise_for_status = Mock()
                return response
            elif "docx/SKILL.md" in url:
                response = Mock()
                response.text = docx_skill_content
                response.raise_for_status = Mock()
                return response
            elif "webapp-testing/SKILL.md" in url:
                response = Mock()
                response.text = webapp_testing_skill_content
                response.raise_for_status = Mock()
                return response
            else:
                # Return 404 for other files
                raise httpx.HTTPError("Not found")

        mock_get.side_effect = get_side_effect

        tools = clawdhub_source.fetch_tools()

        # Verify we got skills (should be 3: pdf, docx, webapp-testing)
        assert len(tools) == 3
        assert all(tool.source == "clawdhub" for tool in tools)
        assert all(tool.tool_type == ToolType.SKILL for tool in tools)
        assert all(tool.id.startswith("clawdhub:") for tool in tools)

        # Verify specific skills
        pdf_tool = next((t for t in tools if "pdf" in t.id), None)
        assert pdf_tool is not None
        assert pdf_tool.id == "clawdhub:pdf"
        assert pdf_tool.name == "pdf"
        assert "PDF manipulation" in pdf_tool.description

        docx_tool = next((t for t in tools if "docx" in t.id), None)
        assert docx_tool is not None
        assert docx_tool.id == "clawdhub:docx"
        assert "Word documents" in docx_tool.description

    @patch("time.sleep")  # Mock sleep to make retries instant
    @patch("httpx.get")
    def test_fetch_tools_network_error(
        self, mock_get: Mock, mock_sleep: Mock, clawdhub_source: ClawdHubSource
    ) -> None:
        """Test graceful handling of network errors."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Network error")

        # Should raise NetworkError after retries are exhausted
        with pytest.raises(NetworkError, match="HTTP error while fetching from GitHub API"):
            clawdhub_source.fetch_tools()

    @patch("time.sleep")  # Mock sleep to make retries instant
    @patch("httpx.get")
    def test_fetch_tools_skips_non_directories(
        self,
        mock_get: Mock,
        mock_sleep: Mock,
        clawdhub_source: ClawdHubSource,
        api_response_data: list[dict],
    ) -> None:
        """Test that non-directory items are skipped."""
        # Mock API response and individual skill fetches
        def get_side_effect(url: str, **kwargs):
            if url == ClawdHubSource.API_URL:
                response = Mock()
                response.json.return_value = api_response_data
                response.raise_for_status = Mock()
                return response
            else:
                # All skill fetches fail (we don't care about content, just filtering)
                raise httpx.HTTPError("Not found")

        mock_get.side_effect = get_side_effect

        tools = clawdhub_source.fetch_tools()

        # Should not include README.md (which is type="file")
        assert not any("README" in tool.id for tool in tools)

    def test_parse_frontmatter_basic(self, clawdhub_source: ClawdHubSource) -> None:
        """Test parsing basic YAML frontmatter."""
        content = """---
name: test-skill
description: A test skill for unit testing
---

# Test Skill Content
"""
        metadata = clawdhub_source._parse_frontmatter(content)

        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "A test skill for unit testing"

    def test_parse_frontmatter_with_extra_fields(
        self, clawdhub_source: ClawdHubSource
    ) -> None:
        """Test parsing frontmatter with additional fields."""
        content = """---
name: test-skill
description: A test skill
license: MIT
version: 1.0.0
---

Content here
"""
        metadata = clawdhub_source._parse_frontmatter(content)

        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "A test skill"
        assert metadata["license"] == "MIT"
        assert metadata["version"] == "1.0.0"

    def test_parse_frontmatter_missing(self, clawdhub_source: ClawdHubSource) -> None:
        """Test parsing content without frontmatter."""
        content = """# Regular Markdown

No frontmatter here.
"""
        metadata = clawdhub_source._parse_frontmatter(content)

        assert metadata == {}

    def test_parse_frontmatter_with_comments(
        self, clawdhub_source: ClawdHubSource
    ) -> None:
        """Test parsing frontmatter with YAML comments."""
        content = """---
# This is a comment
name: test-skill
# Another comment
description: Test description
---

Content
"""
        metadata = clawdhub_source._parse_frontmatter(content)

        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "Test description"
        assert "# This is a comment" not in metadata

    def test_extract_tags_simple(self, clawdhub_source: ClawdHubSource) -> None:
        """Test tag extraction from simple slug."""
        tags = clawdhub_source._extract_tags("pdf")
        assert tags == ["pdf"]

    def test_extract_tags_hyphenated(self, clawdhub_source: ClawdHubSource) -> None:
        """Test tag extraction from hyphenated slug."""
        tags = clawdhub_source._extract_tags("webapp-testing")
        assert tags == ["webapp", "testing"]

    def test_extract_tags_underscored(self, clawdhub_source: ClawdHubSource) -> None:
        """Test tag extraction from underscored slug."""
        tags = clawdhub_source._extract_tags("web_app_testing")
        assert tags == ["web", "app", "testing"]

    def test_extract_tags_mixed(self, clawdhub_source: ClawdHubSource) -> None:
        """Test tag extraction from mixed delimiter slug."""
        tags = clawdhub_source._extract_tags("web-app_testing")
        assert tags == ["web", "app", "testing"]

    @patch("httpx.get")
    def test_fetch_skill_metadata_success(
        self, mock_get: Mock, clawdhub_source: ClawdHubSource, pdf_skill_content: str
    ) -> None:
        """Test successful fetching of skill metadata."""
        # Mock SKILL.md response
        mock_response = Mock()
        mock_response.text = pdf_skill_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tool = clawdhub_source._fetch_skill_metadata(
            "pdf", "https://github.com/anthropics/skills/tree/main/skills/pdf"
        )

        assert tool is not None
        assert tool.id == "clawdhub:pdf"
        assert tool.name == "pdf"
        assert tool.source == "clawdhub"
        assert tool.tool_type == ToolType.SKILL
        assert "PDF manipulation" in tool.description
        assert tool.tags == ["pdf"]
        assert tool.last_seen is not None

    @patch("time.sleep")  # Mock sleep to make retries instant
    @patch("httpx.get")
    def test_fetch_skill_metadata_network_error(
        self, mock_get: Mock, mock_sleep: Mock, clawdhub_source: ClawdHubSource
    ) -> None:
        """Test handling of network error when fetching skill metadata."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Not found")

        tool = clawdhub_source._fetch_skill_metadata("nonexistent", "")

        # Should return None on error
        assert tool is None

    @patch("httpx.get")
    def test_fetch_skill_metadata_no_frontmatter(
        self, mock_get: Mock, clawdhub_source: ClawdHubSource
    ) -> None:
        """Test handling of SKILL.md without frontmatter."""
        # Mock response with no frontmatter
        mock_response = Mock()
        mock_response.text = "# Just a regular markdown file\n\nNo frontmatter."
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tool = clawdhub_source._fetch_skill_metadata("test", "https://example.com")

        # Should return None if no metadata
        assert tool is None

    @patch("httpx.get")
    def test_search_live_by_name(
        self,
        mock_get: Mock,
        clawdhub_source: ClawdHubSource,
        api_response_data: list[dict],
        pdf_skill_content: str,
        docx_skill_content: str,
        webapp_testing_skill_content: str,
    ) -> None:
        """Test live search filtering by name."""
        # Setup mocks
        def get_side_effect(url: str, **kwargs):
            if url == ClawdHubSource.API_URL:
                response = Mock()
                response.json.return_value = api_response_data
                response.raise_for_status = Mock()
                return response
            elif "pdf/SKILL.md" in url:
                response = Mock()
                response.text = pdf_skill_content
                response.raise_for_status = Mock()
                return response
            elif "docx/SKILL.md" in url:
                response = Mock()
                response.text = docx_skill_content
                response.raise_for_status = Mock()
                return response
            elif "webapp-testing/SKILL.md" in url:
                response = Mock()
                response.text = webapp_testing_skill_content
                response.raise_for_status = Mock()
                return response
            else:
                raise httpx.HTTPError("Not found")

        mock_get.side_effect = get_side_effect

        results = clawdhub_source.search_live("pdf")

        assert len(results) > 0
        assert any("pdf" in tool.name.lower() for tool in results)

    @patch("httpx.get")
    def test_search_live_by_description(
        self,
        mock_get: Mock,
        clawdhub_source: ClawdHubSource,
        api_response_data: list[dict],
        pdf_skill_content: str,
        docx_skill_content: str,
        webapp_testing_skill_content: str,
    ) -> None:
        """Test live search filtering by description."""
        # Setup mocks
        def get_side_effect(url: str, **kwargs):
            if url == ClawdHubSource.API_URL:
                response = Mock()
                response.json.return_value = api_response_data
                response.raise_for_status = Mock()
                return response
            elif "pdf/SKILL.md" in url:
                response = Mock()
                response.text = pdf_skill_content
                response.raise_for_status = Mock()
                return response
            elif "docx/SKILL.md" in url:
                response = Mock()
                response.text = docx_skill_content
                response.raise_for_status = Mock()
                return response
            elif "webapp-testing/SKILL.md" in url:
                response = Mock()
                response.text = webapp_testing_skill_content
                response.raise_for_status = Mock()
                return response
            else:
                raise httpx.HTTPError("Not found")

        mock_get.side_effect = get_side_effect

        results = clawdhub_source.search_live("Word documents")

        assert len(results) > 0
        docx_tool = next((t for t in results if "docx" in t.id), None)
        assert docx_tool is not None
        assert "Word documents" in docx_tool.description

    @patch("httpx.get")
    def test_search_live_case_insensitive(
        self,
        mock_get: Mock,
        clawdhub_source: ClawdHubSource,
        api_response_data: list[dict],
        pdf_skill_content: str,
        docx_skill_content: str,
        webapp_testing_skill_content: str,
    ) -> None:
        """Test that search is case-insensitive."""
        # Setup mocks
        def get_side_effect(url: str, **kwargs):
            if url == ClawdHubSource.API_URL:
                response = Mock()
                response.json.return_value = api_response_data
                response.raise_for_status = Mock()
                return response
            elif "pdf/SKILL.md" in url:
                response = Mock()
                response.text = pdf_skill_content
                response.raise_for_status = Mock()
                return response
            elif "docx/SKILL.md" in url:
                response = Mock()
                response.text = docx_skill_content
                response.raise_for_status = Mock()
                return response
            elif "webapp-testing/SKILL.md" in url:
                response = Mock()
                response.text = webapp_testing_skill_content
                response.raise_for_status = Mock()
                return response
            else:
                raise httpx.HTTPError("Not found")

        mock_get.side_effect = get_side_effect

        results_lower = clawdhub_source.search_live("pdf")
        results_upper = clawdhub_source.search_live("PDF")
        results_mixed = clawdhub_source.search_live("Pdf")

        # All should return the same results
        assert len(results_lower) == len(results_upper) == len(results_mixed)
        assert len(results_lower) > 0

    @patch("httpx.get")
    def test_search_live_no_matches(
        self,
        mock_get: Mock,
        clawdhub_source: ClawdHubSource,
        api_response_data: list[dict],
        pdf_skill_content: str,
        docx_skill_content: str,
        webapp_testing_skill_content: str,
    ) -> None:
        """Test search with no matching results."""
        # Setup mocks
        def get_side_effect(url: str, **kwargs):
            if url == ClawdHubSource.API_URL:
                response = Mock()
                response.json.return_value = api_response_data
                response.raise_for_status = Mock()
                return response
            elif "pdf/SKILL.md" in url:
                response = Mock()
                response.text = pdf_skill_content
                response.raise_for_status = Mock()
                return response
            elif "docx/SKILL.md" in url:
                response = Mock()
                response.text = docx_skill_content
                response.raise_for_status = Mock()
                return response
            elif "webapp-testing/SKILL.md" in url:
                response = Mock()
                response.text = webapp_testing_skill_content
                response.raise_for_status = Mock()
                return response
            else:
                raise httpx.HTTPError("Not found")

        mock_get.side_effect = get_side_effect

        results = clawdhub_source.search_live("nonexistent-skill-xyz-123")

        assert results == []

    @patch("httpx.get")
    def test_all_tools_have_required_fields(
        self,
        mock_get: Mock,
        clawdhub_source: ClawdHubSource,
        api_response_data: list[dict],
        pdf_skill_content: str,
        docx_skill_content: str,
        webapp_testing_skill_content: str,
    ) -> None:
        """Test that all parsed tools have required fields populated."""
        # Setup mocks
        def get_side_effect(url: str, **kwargs):
            if url == ClawdHubSource.API_URL:
                response = Mock()
                response.json.return_value = api_response_data
                response.raise_for_status = Mock()
                return response
            elif "pdf/SKILL.md" in url:
                response = Mock()
                response.text = pdf_skill_content
                response.raise_for_status = Mock()
                return response
            elif "docx/SKILL.md" in url:
                response = Mock()
                response.text = docx_skill_content
                response.raise_for_status = Mock()
                return response
            elif "webapp-testing/SKILL.md" in url:
                response = Mock()
                response.text = webapp_testing_skill_content
                response.raise_for_status = Mock()
                return response
            else:
                raise httpx.HTTPError("Not found")

        mock_get.side_effect = get_side_effect

        tools = clawdhub_source.fetch_tools()

        for tool in tools:
            # Required fields must be non-empty
            assert tool.id, f"Tool {tool.name} missing id"
            assert tool.name, "Tool missing name"
            assert tool.source == "clawdhub"
            assert tool.source_url, f"Tool {tool.name} missing source_url"
            assert tool.tool_type == ToolType.SKILL
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.last_seen is not None

            # ID format validation
            assert tool.id.startswith("clawdhub:")
            assert ":" in tool.id
            parts = tool.id.split(":")
            assert len(parts) == 2
            assert parts[1], "Tool slug cannot be empty"
