"""Tests for ledger CLI commands."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from cub.cli.ledger import (
    _format_cost,
    _format_verification,
    _get_ledger_reader,
    app,
)
from cub.core.ledger.reader import LedgerReader


runner = CliRunner()


class TestFormatHelpers:
    """Tests for formatting helper functions."""

    def test_format_cost_zero(self) -> None:
        """Test zero cost formatting."""
        result = _format_cost(0)
        assert "[dim]$0.00[/dim]" == result

    def test_format_cost_positive(self) -> None:
        """Test positive cost formatting."""
        result = _format_cost(1.50)
        assert "[yellow]$1.50[/yellow]" == result

    def test_format_cost_small(self) -> None:
        """Test small cost formatting."""
        result = _format_cost(0.05)
        assert "[yellow]$0.05[/yellow]" == result

    def test_format_verification_pass(self) -> None:
        """Test pass status formatting."""
        result = _format_verification("pass")
        assert "[green]pass[/green]" == result

    def test_format_verification_fail(self) -> None:
        """Test fail status formatting."""
        result = _format_verification("fail")
        assert "[red]fail[/red]" == result

    def test_format_verification_warn(self) -> None:
        """Test warn status formatting."""
        result = _format_verification("warn")
        assert "[yellow]warn[/yellow]" == result

    def test_format_verification_skip(self) -> None:
        """Test skip status formatting."""
        result = _format_verification("skip")
        assert "[dim]skip[/dim]" == result

    def test_format_verification_pending(self) -> None:
        """Test pending status formatting."""
        result = _format_verification("pending")
        assert "[blue]pending[/blue]" == result

    def test_format_verification_error(self) -> None:
        """Test error status formatting."""
        result = _format_verification("error")
        assert "[red]error[/red]" == result

    def test_format_verification_unknown(self) -> None:
        """Test unknown status returns unchanged."""
        result = _format_verification("unknown")
        assert "unknown" == result


class TestGetLedgerReader:
    """Tests for _get_ledger_reader helper."""

    def test_returns_ledger_reader(self, tmp_path: Path) -> None:
        """Test that _get_ledger_reader returns a LedgerReader instance."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            reader = _get_ledger_reader()
            assert isinstance(reader, LedgerReader)
            assert reader.ledger_dir == tmp_path / ".cub" / "ledger"


class TestLedgerShowCommand:
    """Tests for ledger show command."""

    def test_show_no_ledger(self, tmp_path: Path) -> None:
        """Test show command when no ledger exists."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "beads-abc"])
            assert result.exit_code == 0
            assert "No ledger found" in result.output

    def test_show_task_not_found(self, tmp_path: Path) -> None:
        """Test show command when task doesn't exist."""
        # Create ledger dir but no task
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["show", "beads-abc"])
            assert result.exit_code == 1
            assert "not found" in result.output


class TestLedgerStatsCommand:
    """Tests for ledger stats command."""

    def test_stats_no_ledger(self, tmp_path: Path) -> None:
        """Test stats command when no ledger exists."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["stats"])
            assert result.exit_code == 0
            assert "No ledger found" in result.output

    def test_stats_empty_ledger(self, tmp_path: Path) -> None:
        """Test stats command with empty ledger."""
        # Create ledger dir but no entries
        ledger_dir = tmp_path / ".cub" / "ledger"
        ledger_dir.mkdir(parents=True)

        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["stats"])
            assert result.exit_code == 0
            # Displays stats even if empty (with 0 tasks)
            assert "Tasks: 0" in result.output


class TestLedgerSearchCommand:
    """Tests for ledger search command."""

    def test_search_no_ledger(self, tmp_path: Path) -> None:
        """Test search command when no ledger exists."""
        with patch("cub.cli.ledger.get_project_root") as mock_get_root:
            mock_get_root.return_value = tmp_path
            result = runner.invoke(app, ["search", "test"])
            assert result.exit_code == 0
            assert "No ledger found" in result.output
