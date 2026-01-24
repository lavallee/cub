"""
Shared fixtures for toolsmith tests.

Provides common fixtures used across toolsmith test modules including:
- Fixture loading utilities
- Mock store fixtures
- Sample response fixtures
- Common test utilities
"""

import json
from pathlib import Path
from typing import Callable
from unittest.mock import Mock

import pytest

from cub.core.toolsmith.store import ToolsmithStore


@pytest.fixture
def fixture_dir() -> Path:
    """
    Get path to test fixtures directory.

    Returns:
        Path to fixtures directory containing sample API responses
    """
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_store(tmp_path: Path) -> ToolsmithStore:
    """
    Create temporary toolsmith store for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        ToolsmithStore instance using temporary directory
    """
    return ToolsmithStore(tmp_path / "toolsmith")


@pytest.fixture
def smithery_response(fixture_dir: Path) -> dict:
    """
    Load Smithery API response fixture.

    Returns:
        Dict containing sample Smithery API response
    """
    return json.loads((fixture_dir / "smithery_response.json").read_text())


@pytest.fixture
def glama_response(fixture_dir: Path) -> dict:
    """
    Load Glama API response fixture.

    Returns:
        Dict containing sample Glama API response
    """
    return json.loads((fixture_dir / "glama_response.json").read_text())


@pytest.fixture
def skillsmp_response(fixture_dir: Path) -> dict:
    """
    Load SkillsMP API response fixture.

    Returns:
        Dict containing sample SkillsMP API response
    """
    return json.loads((fixture_dir / "skillsmp_response.json").read_text())


@pytest.fixture
def clawdhub_response(fixture_dir: Path) -> dict:
    """
    Load ClawdHub API response fixture.

    Returns:
        Dict containing sample ClawdHub API response
    """
    return json.loads((fixture_dir / "clawdhub_api_response.json").read_text())


@pytest.fixture
def mcp_official_readme(fixture_dir: Path) -> str:
    """
    Load MCP Official README fixture.

    Returns:
        String containing sample MCP Official README content
    """
    return (fixture_dir / "mcp_official_readme_sample.md").read_text()


@pytest.fixture
def all_source_responses(
    smithery_response: dict,
    glama_response: dict,
    skillsmp_response: dict,
    clawdhub_response: dict,
) -> dict[str, dict]:
    """
    Get all source responses as a dict mapping domain to response.

    Useful for mocking multiple sources in a single test.

    Returns:
        Dict mapping domain name to API response fixture
    """
    return {
        "smithery.ai": smithery_response,
        "glama.ai": glama_response,
        "skillsmp.com": skillsmp_response,
        "clawdhub.ai": clawdhub_response,
    }


@pytest.fixture
def mock_http_response_factory(
    smithery_response: dict,
    glama_response: dict,
    skillsmp_response: dict,
    clawdhub_response: dict,
    mcp_official_readme: str,
) -> Callable[[str], Mock]:
    """
    Create a factory for generating mock HTTP responses.

    Returns a function that takes a URL and returns an appropriate mock response
    based on the domain. Handles both JSON responses (most sources) and text
    responses (MCP Official README).

    Returns:
        Callable that takes a URL and returns a Mock response
    """

    def factory(url: str, **kwargs) -> Mock:
        """Generate mock response based on URL."""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()

        # MCP Official uses text response (README from GitHub)
        if "github" in url or "raw.githubusercontent.com" in url:
            mock_resp.text = mcp_official_readme
            return mock_resp

        # Map domains to JSON responses
        json_responses = {
            "smithery.ai": smithery_response,
            "glama.ai": glama_response,
            "skillsmp.com": skillsmp_response,
            "clawdhub.ai": clawdhub_response,
        }

        # Find matching domain and return response
        for domain, response in json_responses.items():
            if domain in url:
                mock_resp.json.return_value = response
                return mock_resp

        # Default empty JSON response for unknown sources
        mock_resp.json.return_value = {"items": [], "servers": [], "tools": []}
        return mock_resp

    return factory
