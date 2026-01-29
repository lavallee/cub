"""
Unit tests for the status CLI command with --agent flag.

Tests the agent-friendly markdown output for cub status.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli.status import app
from cub.core.services.models import ProjectStats

runner = CliRunner()


@pytest.fixture
def mock_project_stats() -> ProjectStats:
    """Create mock project stats."""
    return ProjectStats(
        total_tasks=10,
        open_tasks=4,
        in_progress_tasks=2,
        closed_tasks=4,
        ready_tasks=2,
        blocked_tasks=2,
        total_epics=2,
        active_epics=1,
        completion_percentage=40.0,
        total_cost_usd=5.50,
        total_tokens=15000,
        tasks_in_ledger=4,
        current_branch="main",
        has_uncommitted_changes=False,
        commits_since_main=0,
    )


class TestStatusAgent:
    """Test cub status command with --agent flag."""

    def test_status_agent_basic(self, mock_project_stats: ProjectStats) -> None:
        """Test status with --agent flag."""
        with (
            patch("cub.cli.status.get_project_root", return_value="/fake/path"),
            patch("cub.cli.status.StatusService") as mock_service_class,
            patch("cub.cli.status.get_backend") as mock_backend,
            patch("cub.cli.status.get_latest_status", return_value=None),
        ):
            mock_service = MagicMock()
            mock_service.summary.return_value = mock_project_stats
            mock_service_class.from_project_dir.return_value = mock_service

            mock_backend_instance = MagicMock()
            mock_backend_instance.get_ready_tasks.return_value = []
            mock_backend.return_value = mock_backend_instance

            result = runner.invoke(app, ["--agent"], obj={})

        assert result.exit_code == 0
        assert "# cub status" in result.stdout
        assert "10 tasks:" in result.stdout
        assert "## Breakdown" in result.stdout

    def test_status_agent_wins_over_json(self, mock_project_stats: ProjectStats) -> None:
        """Test that --agent takes precedence over --json."""
        with (
            patch("cub.cli.status.get_project_root", return_value="/fake/path"),
            patch("cub.cli.status.StatusService") as mock_service_class,
            patch("cub.cli.status.get_backend") as mock_backend,
            patch("cub.cli.status.get_latest_status", return_value=None),
        ):
            mock_service = MagicMock()
            mock_service.summary.return_value = mock_project_stats
            mock_service_class.from_project_dir.return_value = mock_service

            mock_backend_instance = MagicMock()
            mock_backend_instance.get_ready_tasks.return_value = []
            mock_backend.return_value = mock_backend_instance

            result = runner.invoke(app, ["--agent", "--json"], obj={})

        assert result.exit_code == 0
        # Should be markdown, not JSON
        assert "# cub status" in result.stdout
        assert '"total_tasks":' not in result.stdout
