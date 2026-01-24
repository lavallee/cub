"""Tests for SkillsMP source adapter."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

from cub.core.toolsmith.exceptions import NetworkError
from cub.core.toolsmith.models import ToolType
from cub.core.toolsmith.sources.base import get_source
from cub.core.toolsmith.sources.skillsmp import SkillsMPSource


@pytest.fixture
def sample_api_response() -> dict[str, Any]:
    """Load sample API response from fixture file."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "skillsmp_response.json"
    return json.loads(fixture_path.read_text())  # type: ignore[no-any-return]


@pytest.fixture
def skillsmp_source() -> SkillsMPSource:
    """Create SkillsMPSource instance."""
    return SkillsMPSource()


class TestSkillsMPSource:
    """Test suite for SkillsMPSource."""

    def test_source_registration(self) -> None:
        """Test that source is properly registered."""
        source = get_source("skillsmp")
        assert isinstance(source, SkillsMPSource)
        assert source.name == "skillsmp"

    def test_name_property(self, skillsmp_source: SkillsMPSource) -> None:
        """Test name property returns correct value."""
        assert skillsmp_source.name == "skillsmp"

    @patch("httpx.get")
    def test_fetch_tools_success(
        self,
        mock_get: Mock,
        skillsmp_source: SkillsMPSource,
        sample_api_response: dict[str, Any],
    ) -> None:
        """Test successful tool fetching from API."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = skillsmp_source.fetch_tools()

        # Verify HTTP call
        mock_get.assert_called_once()
        call_args = mock_get.call_args

        # Check URL
        assert call_args.args[0] == f"{SkillsMPSource.API_BASE_URL}/skills/search"

        # Verify tools were parsed
        assert len(tools) == 5
        assert all(tool.source == "skillsmp" for tool in tools)
        assert all(tool.tool_type == ToolType.SKILL for tool in tools)
        assert all(tool.id.startswith("skillsmp:") for tool in tools)

    @patch("time.sleep")
    @patch("httpx.get")
    def test_fetch_tools_network_error(
        self, mock_get: Mock, mock_sleep: Mock, skillsmp_source: SkillsMPSource
    ) -> None:
        """Test graceful handling of network errors."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Network error")

        with pytest.raises(NetworkError, match="HTTP error"):
            skillsmp_source.fetch_tools()

    @patch("httpx.get")
    def test_fetch_tools_pagination(
        self, mock_get: Mock, skillsmp_source: SkillsMPSource
    ) -> None:
        """Test pagination handling when fetching all tools."""
        # Create response for page 1
        page1_response = {
            "skills": [
                {
                    "id": "skill-1",
                    "slug": "skill-one",
                    "name": "Skill One",
                    "description": "Description one",
                    "url": "https://skillsmp.com/skills/skill-one",
                    "repository": {"url": "https://github.com/user/skill-one"},
                    "category": "testing",
                    "tags": ["test"],
                    "author": "user1",
                    "createdAt": "2025-01-01T00:00:00Z",
                }
            ],
            "pagination": {
                "page": 1,
                "limit": 50,
                "total": 2,
                "hasNext": True,
            },
        }

        # Create response for page 2
        page2_response = {
            "skills": [
                {
                    "id": "skill-2",
                    "slug": "skill-two",
                    "name": "Skill Two",
                    "description": "Description two",
                    "url": "https://skillsmp.com/skills/skill-two",
                    "repository": {"url": "https://github.com/user/skill-two"},
                    "category": "documentation",
                    "tags": ["docs"],
                    "author": "user2",
                    "createdAt": "2025-01-02T00:00:00Z",
                }
            ],
            "pagination": {
                "page": 2,
                "limit": 50,
                "total": 2,
                "hasNext": False,
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

        tools = skillsmp_source.fetch_tools()

        # Should have fetched both pages
        assert len(tools) == 2
        assert mock_get.call_count == 2
        assert any("skill-one" in tool.id for tool in tools)
        assert any("skill-two" in tool.id for tool in tools)

    def test_parse_skill_basic(
        self, skillsmp_source: SkillsMPSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test parsing a basic skill entry."""
        skill_data = sample_api_response["skills"][0]
        tool = skillsmp_source._parse_skill(skill_data)

        assert tool.id == "skillsmp:api-documentation-generator"
        assert tool.name == "API Documentation Generator"
        assert tool.source == "skillsmp"
        assert tool.source_url == "https://skillsmp.com/skills/api-documentation-generator"
        assert tool.tool_type == ToolType.SKILL
        assert tool.description.startswith("Automatically generates comprehensive")
        assert tool.last_seen is not None

    def test_parse_skill_with_repository(
        self, skillsmp_source: SkillsMPSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that skills with repositories get install hints."""
        skill_data = sample_api_response["skills"][0]
        tool = skillsmp_source._parse_skill(skill_data)

        assert "claude skill add" in tool.install_hint
        assert "github.com" in tool.install_hint

    def test_parse_skill_with_category_and_tags(
        self, skillsmp_source: SkillsMPSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that category and tags are converted to tool tags."""
        skill_data = sample_api_response["skills"][0]
        tool = skillsmp_source._parse_skill(skill_data)

        assert "documentation" in tool.tags
        assert "api" in tool.tags
        assert "docs" in tool.tags
        assert "openapi" in tool.tags

    def test_parse_skill_with_author(
        self, skillsmp_source: SkillsMPSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that author info is added to tags."""
        skill_data = sample_api_response["skills"][0]
        tool = skillsmp_source._parse_skill(skill_data)

        assert any(tag.startswith("author:") for tag in tool.tags)
        assert "author:example-user" in tool.tags

    def test_parse_skill_without_repository(
        self, skillsmp_source: SkillsMPSource
    ) -> None:
        """Test that skills without repositories get fallback install hint."""
        skill_data: dict[str, Any] = {
            "id": "skill-999",
            "slug": "test-skill",
            "name": "Test Skill",
            "description": "A test skill",
            "url": "https://skillsmp.com/skills/test-skill",
            "category": "testing",
            "tags": [],
            "author": "test",
        }
        tool = skillsmp_source._parse_skill(skill_data)

        assert "See installation instructions at:" in tool.install_hint
        assert "skillsmp.com" in tool.install_hint

    @patch("httpx.get")
    def test_search_live_success(
        self,
        mock_get: Mock,
        skillsmp_source: SkillsMPSource,
        sample_api_response: dict[str, Any],
    ) -> None:
        """Test live search with query."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        results = skillsmp_source.search_live("documentation")

        # Verify HTTP call includes query parameter
        call_args = mock_get.call_args
        assert call_args.kwargs["params"]["q"] == "documentation"

        # Should return tools
        assert len(results) > 0

    @patch("time.sleep")
    @patch("httpx.get")
    def test_search_live_network_error(
        self, mock_get: Mock, mock_sleep: Mock, skillsmp_source: SkillsMPSource
    ) -> None:
        """Test that search handles network errors gracefully."""
        # Mock network error
        mock_get.side_effect = httpx.HTTPError("Network error")

        with pytest.raises(NetworkError, match="HTTP error"):
            skillsmp_source.search_live("test")

    @patch("httpx.get")
    def test_api_authentication_header(
        self,
        mock_get: Mock,
        skillsmp_source: SkillsMPSource,
        sample_api_response: dict[str, Any],
    ) -> None:
        """Test that API token is included in headers when available."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock environment variable
        with patch.dict("os.environ", {"SKILLSMP_API_TOKEN": "sk_live_test-token-123"}):
            skillsmp_source.fetch_tools()

        # Verify authorization header was included
        call_args = mock_get.call_args
        headers = call_args.kwargs["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer sk_live_test-token-123"

    @patch("httpx.get")
    def test_api_without_authentication(
        self,
        mock_get: Mock,
        skillsmp_source: SkillsMPSource,
        sample_api_response: dict[str, Any],
    ) -> None:
        """Test that API calls work without authentication token."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Ensure no API token in environment
        with patch.dict("os.environ", {}, clear=True):
            skillsmp_source.fetch_tools()

        # Verify no authorization header
        call_args = mock_get.call_args
        headers = call_args.kwargs["headers"]
        assert "Authorization" not in headers

    def test_all_tools_have_required_fields(
        self, skillsmp_source: SkillsMPSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that all parsed tools have required fields populated."""
        skills = sample_api_response["skills"]

        for skill_data in skills:
            tool = skillsmp_source._parse_skill(skill_data)

            # Required fields must be non-empty
            assert tool.id, f"Tool {tool.name} missing id"
            assert tool.name, "Tool missing name"
            assert tool.source == "skillsmp"
            assert tool.source_url, f"Tool {tool.name} missing source_url"
            assert tool.tool_type == ToolType.SKILL
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.last_seen is not None

            # ID format validation
            assert tool.id.startswith("skillsmp:")
            assert ":" in tool.id
            parts = tool.id.split(":", 1)
            assert len(parts) == 2
            assert parts[1], "Tool skill slug cannot be empty"

    @patch("httpx.get")
    def test_fetch_page_parameters(
        self,
        mock_get: Mock,
        skillsmp_source: SkillsMPSource,
        sample_api_response: dict[str, Any],
    ) -> None:
        """Test that _fetch_page passes correct parameters."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        skillsmp_source._fetch_page(query="testing", page=2, limit=25)

        # Verify parameters
        call_args = mock_get.call_args
        params = call_args.kwargs["params"]
        assert params["q"] == "testing"
        assert params["page"] == "2"
        assert params["limit"] == "25"

    @patch("httpx.get")
    def test_handles_missing_optional_fields(
        self, mock_get: Mock, skillsmp_source: SkillsMPSource
    ) -> None:
        """Test that parser handles missing optional fields gracefully."""
        minimal_response = {
            "skills": [
                {
                    "id": "minimal-123",
                    "slug": "minimal-skill",
                    "name": "Minimal Skill",
                    "description": "A minimal skill entry",
                    # Missing: url, repository, category, tags, author, createdAt
                }
            ],
            "pagination": {
                "page": 1,
                "limit": 50,
                "total": 1,
                "hasNext": False,
            },
        }

        mock_response = Mock()
        mock_response.json.return_value = minimal_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = skillsmp_source.fetch_tools()

        assert len(tools) == 1
        tool = tools[0]
        assert tool.id == "skillsmp:minimal-skill"
        assert tool.name == "Minimal Skill"
        assert tool.description == "A minimal skill entry"
        # Should use default URL based on slug
        assert "skillsmp.com/skills/minimal-skill" in tool.source_url

    @patch("httpx.get")
    def test_pagination_stops_when_no_next_page(
        self, mock_get: Mock, skillsmp_source: SkillsMPSource
    ) -> None:
        """Test that pagination stops when hasNext is False."""
        response = {
            "skills": [
                {
                    "id": "only-skill",
                    "slug": "only",
                    "name": "Only Skill",
                    "description": "Only skill",
                    "url": "https://skillsmp.com/skills/only",
                }
            ],
            "pagination": {
                "page": 1,
                "limit": 50,
                "total": 1,
                "hasNext": False,
            },
        }

        mock_response = Mock()
        mock_response.json.return_value = response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        tools = skillsmp_source.fetch_tools()

        # Should only call API once
        assert mock_get.call_count == 1
        assert len(tools) == 1

    def test_parse_skill_created_at_timestamp(
        self, skillsmp_source: SkillsMPSource, sample_api_response: dict[str, Any]
    ) -> None:
        """Test that createdAt timestamp is properly parsed."""
        skill_data = sample_api_response["skills"][0]
        tool = skillsmp_source._parse_skill(skill_data)

        # Should have parsed the timestamp
        assert tool.last_seen is not None
        # Should be timezone-aware
        assert tool.last_seen.tzinfo is not None

    def test_parse_skill_handles_invalid_timestamp(
        self, skillsmp_source: SkillsMPSource
    ) -> None:
        """Test that invalid timestamps fall back to current time."""
        skill_data: dict[str, Any] = {
            "id": "skill-bad-timestamp",
            "slug": "bad-timestamp",
            "name": "Bad Timestamp Skill",
            "description": "Skill with invalid timestamp",
            "url": "https://skillsmp.com/skills/bad-timestamp",
            "createdAt": "invalid-date-format",
        }
        tool = skillsmp_source._parse_skill(skill_data)

        # Should still have a last_seen timestamp (current time)
        assert tool.last_seen is not None
        assert tool.last_seen.tzinfo is not None
