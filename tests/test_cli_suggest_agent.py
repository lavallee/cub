"""
Unit tests for the suggest CLI command with --agent flag.

Tests the agent-friendly markdown output for cub suggest.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli.suggest import app
from cub.core.suggestions.models import Suggestion, SuggestionCategory

runner = CliRunner()


@pytest.fixture
def mock_suggestions() -> list[Suggestion]:
    """Create mock suggestions."""
    return [
        Suggestion(
            category=SuggestionCategory.TASK,
            title="Work on high-priority task",
            rationale="Task cub-001 is P1 and ready to start",
            priority_score=0.9,
            action="cub task claim cub-001",
        ),
        Suggestion(
            category=SuggestionCategory.GIT,
            title="Commit changes",
            rationale="You have uncommitted changes",
            priority_score=0.7,
            action="git commit -am 'WIP'",
        ),
    ]


class TestSuggestAgent:
    """Test cub suggest command with --agent flag."""

    def test_suggest_agent_basic(self, mock_suggestions: list[Suggestion]) -> None:
        """Test suggest with --agent flag."""
        with (
            patch("cub.cli.suggest.get_project_root", return_value="/fake/path"),
            patch("cub.cli.suggest.SuggestionService") as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.get_suggestions.return_value = mock_suggestions
            mock_service_class.from_project_dir.return_value = mock_service

            result = runner.invoke(app, ["--agent"], obj={})

        assert result.exit_code == 0
        assert "# cub suggest" in result.stdout
        assert "2 recommendations" in result.stdout
        assert "## Suggestions" in result.stdout

    def test_suggest_agent_empty(self) -> None:
        """Test suggest with --agent when no suggestions."""
        with (
            patch("cub.cli.suggest.get_project_root", return_value="/fake/path"),
            patch("cub.cli.suggest.SuggestionService") as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.get_suggestions.return_value = []
            mock_service_class.from_project_dir.return_value = mock_service

            result = runner.invoke(app, ["--agent"], obj={})

        assert result.exit_code == 0
        assert "# cub suggest" in result.stdout
        assert "0 recommendations" in result.stdout

    def test_suggest_agent_wins_over_json(
        self, mock_suggestions: list[Suggestion]
    ) -> None:
        """Test that --agent takes precedence over --json."""
        with (
            patch("cub.cli.suggest.get_project_root", return_value="/fake/path"),
            patch("cub.cli.suggest.SuggestionService") as mock_service_class,
        ):
            mock_service = MagicMock()
            mock_service.get_suggestions.return_value = mock_suggestions
            mock_service_class.from_project_dir.return_value = mock_service

            result = runner.invoke(app, ["--agent", "--json"], obj={})

        assert result.exit_code == 0
        # Should be markdown, not JSON
        assert "# cub suggest" in result.stdout
        assert '"total_suggestions":' not in result.stdout
