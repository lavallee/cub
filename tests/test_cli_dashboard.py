"""
Tests for the cub dashboard CLI command.

The dashboard command provides:
- Main command to launch server with sync and browser opening
- Sync subcommand to sync data without starting server
- Project root discovery and validation
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cub.cli import app

runner = CliRunner()


class TestDashboardCommandHelp:
    """Test dashboard command help and structure."""

    def test_dashboard_help(self) -> None:
        """Test that 'cub dashboard --help' shows available options."""
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0
        assert "port" in result.output.lower()
        assert "browser" in result.output.lower()
        assert "sync" in result.output.lower()

    def test_dashboard_sync_help(self) -> None:
        """Test that 'cub dashboard sync --help' shows sync options."""
        result = runner.invoke(app, ["dashboard", "sync", "--help"])
        assert result.exit_code == 0
        assert "force" in result.output.lower()


class TestDashboardNoProject:
    """Test dashboard command when not in a project directory."""

    def test_dashboard_no_project_root(self) -> None:
        """Test launching dashboard when not in a project directory."""
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["dashboard", "--no-browser", "--no-sync"])
            assert result.exit_code == 1
            assert "not in a project" in result.output.lower()

    def test_dashboard_sync_no_project_root(self) -> None:
        """Test sync subcommand when not in a project directory."""
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["dashboard", "sync"])
            assert result.exit_code == 1
            assert "not in a project" in result.output.lower()


class TestDashboardSync:
    """Test dashboard sync subcommand."""

    def test_sync_empty_project(self) -> None:
        """Test syncing an empty project."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            result = runner.invoke(app, ["dashboard", "sync"])
            assert result.exit_code == 0
            assert "sync" in result.output.lower()

    def test_sync_with_specs(self) -> None:
        """Test syncing a project with specs."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)

            # Create a spec file
            spec_content = """---
status: draft
readiness:
  score: 5
---
# Test Feature

This is a test spec.
"""
            Path("specs/researching/test-feature.md").write_text(spec_content)

            result = runner.invoke(app, ["dashboard", "sync"])
            assert result.exit_code == 0
            assert "sync" in result.output.lower()
            assert "successful" in result.output.lower() or "complete" in result.output.lower()

    def test_sync_force_flag(self) -> None:
        """Test sync with --force flag."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            result = runner.invoke(app, ["dashboard", "sync", "--force"])
            assert result.exit_code == 0
            assert "sync" in result.output.lower()


class TestDashboardServer:
    """Test dashboard server launch (mocked)."""

    @patch("uvicorn.run")
    @patch("cub.core.dashboard.sync.SyncOrchestrator")
    def test_dashboard_launch_no_browser_no_sync(
        self, mock_orchestrator: MagicMock, mock_uvicorn: MagicMock
    ) -> None:
        """Test launching dashboard without browser or sync."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # Mock sync result
            mock_sync_result = MagicMock()
            mock_sync_result.success = True
            mock_sync_result.entities_added = 5
            mock_sync_result.warnings = []
            mock_orchestrator.return_value.sync.return_value = mock_sync_result

            runner.invoke(app, ["dashboard", "--no-browser", "--no-sync"])

            # Should start server
            assert mock_uvicorn.called
            # Should not sync when --no-sync is used
            assert not mock_orchestrator.return_value.sync.called

    @patch("uvicorn.run")
    @patch("cub.core.dashboard.sync.SyncOrchestrator")
    def test_dashboard_launch_with_sync(
        self, mock_orchestrator: MagicMock, mock_uvicorn: MagicMock
    ) -> None:
        """Test launching dashboard with sync enabled."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # Mock sync result
            mock_sync_result = MagicMock()
            mock_sync_result.success = True
            mock_sync_result.entities_added = 5
            mock_sync_result.warnings = []
            mock_orchestrator.return_value.sync.return_value = mock_sync_result

            runner.invoke(app, ["dashboard", "--no-browser"])

            # Should sync by default (check that SyncOrchestrator was instantiated)
            assert mock_orchestrator.called
            # And that sync was called on it
            assert mock_orchestrator.return_value.sync.called
            # Should start server
            assert mock_uvicorn.called

    @patch("uvicorn.run")
    @patch("cub.core.dashboard.sync.SyncOrchestrator")
    def test_dashboard_custom_port(
        self, mock_orchestrator: MagicMock, mock_uvicorn: MagicMock
    ) -> None:
        """Test launching dashboard with custom port."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # Mock sync result
            mock_sync_result = MagicMock()
            mock_sync_result.success = True
            mock_sync_result.entities_added = 5
            mock_sync_result.warnings = []
            mock_orchestrator.return_value.sync.return_value = mock_sync_result

            runner.invoke(
                app, ["dashboard", "--port", "3000", "--no-browser", "--no-sync"]
            )

            # Should start server with custom port
            assert mock_uvicorn.called
            call_kwargs = mock_uvicorn.call_args[1]
            assert call_kwargs["port"] == 3000

    @patch("uvicorn.run")
    @patch("cub.core.dashboard.sync.SyncOrchestrator")
    def test_dashboard_sync_failure_continues(
        self, mock_orchestrator: MagicMock, mock_uvicorn: MagicMock
    ) -> None:
        """Test that dashboard starts even if sync fails."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # Mock sync result with failure
            mock_sync_result = MagicMock()
            mock_sync_result.success = False
            mock_sync_result.entities_added = 0
            mock_sync_result.errors = ["Test error"]
            mock_sync_result.warnings = []
            mock_orchestrator.return_value.sync.return_value = mock_sync_result

            runner.invoke(app, ["dashboard", "--no-browser"])

            # Should still start server even with sync failure
            assert mock_uvicorn.called


class TestDashboardIntegration:
    """Integration tests for dashboard command."""

    def test_dashboard_creates_db(self) -> None:
        """Test that dashboard sync creates the database file."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            result = runner.invoke(app, ["dashboard", "sync"])
            assert result.exit_code == 0

            # Check that database was created
            db_path = Path(".cub/dashboard.db")
            assert db_path.exists()

    def test_dashboard_creates_cub_dir(self) -> None:
        """Test that dashboard creates .cub directory if it doesn't exist."""
        with runner.isolated_filesystem():
            # Create project structure (no .cub directory)
            Path(".beads").mkdir()
            Path("specs").mkdir()

            result = runner.invoke(app, ["dashboard", "sync"])
            assert result.exit_code == 0

            # Check that .cub directory was created
            cub_dir = Path(".cub")
            assert cub_dir.exists()
            assert cub_dir.is_dir()


class TestDashboardExport:
    """Test dashboard export subcommand."""

    def test_export_help(self) -> None:
        """Test that 'cub dashboard export --help' shows export options."""
        result = runner.invoke(app, ["dashboard", "export", "--help"])
        assert result.exit_code == 0
        assert "output" in result.output.lower()
        assert "pretty" in result.output.lower()
        assert "compact" in result.output.lower()

    def test_export_no_project_root(self) -> None:
        """Test export subcommand when not in a project directory."""
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["dashboard", "export"])
            assert result.exit_code == 1
            assert "not in a project" in result.output.lower()

    def test_export_no_database(self) -> None:
        """Test export when database doesn't exist."""
        with runner.isolated_filesystem():
            # Create project structure but no database
            Path(".beads").mkdir()
            Path(".cub").mkdir()
            Path("specs").mkdir()

            result = runner.invoke(app, ["dashboard", "export"])
            assert result.exit_code == 1
            assert "database not found" in result.output.lower()
            assert "sync" in result.output.lower()

    def test_export_to_stdout(self) -> None:
        """Test export to stdout produces valid JSON."""
        import json

        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # First sync to create database
            sync_result = runner.invoke(app, ["dashboard", "sync"])
            assert sync_result.exit_code == 0

            # Then export
            result = runner.invoke(app, ["dashboard", "export"])
            assert result.exit_code == 0

            # Verify it's valid JSON
            data = json.loads(result.output)
            assert "view" in data
            assert "columns" in data
            assert "stats" in data
            assert len(data["columns"]) == 8  # Default 8 columns

    def test_export_to_file(self) -> None:
        """Test export to file."""
        import json

        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # First sync
            runner.invoke(app, ["dashboard", "sync"])

            # Export to file
            result = runner.invoke(app, ["dashboard", "export", "-o", "board.json"])
            assert result.exit_code == 0
            assert "exported" in result.output.lower()

            # Verify file contents
            assert Path("board.json").exists()
            data = json.loads(Path("board.json").read_text())
            assert "view" in data
            assert "columns" in data
            assert "stats" in data

    def test_export_compact(self) -> None:
        """Test export with --compact option produces minified JSON."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # First sync
            runner.invoke(app, ["dashboard", "sync"])

            # Export compact
            result = runner.invoke(app, ["dashboard", "export", "--compact"])
            assert result.exit_code == 0

            # Compact JSON should have no newlines (single line)
            lines = result.output.strip().split("\n")
            assert len(lines) == 1  # All JSON on one line

    def test_export_pretty(self) -> None:
        """Test export with --pretty option produces indented JSON."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # First sync
            runner.invoke(app, ["dashboard", "sync"])

            # Export pretty (default)
            result = runner.invoke(app, ["dashboard", "export", "--pretty"])
            assert result.exit_code == 0

            # Pretty JSON should have multiple lines
            lines = result.output.strip().split("\n")
            assert len(lines) > 1  # Multiple lines with indentation

    def test_export_creates_parent_dirs(self) -> None:
        """Test export creates parent directories if needed."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs").mkdir()

            # First sync
            runner.invoke(app, ["dashboard", "sync"])

            # Export to nested path
            result = runner.invoke(
                app, ["dashboard", "export", "-o", "exports/backup/board.json"]
            )
            assert result.exit_code == 0

            # Verify file was created with parent dirs
            assert Path("exports/backup/board.json").exists()
