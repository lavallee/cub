"""Tests for cub new command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli import app

runner = CliRunner()


class TestNewCommand:
    """Tests for the cub new command."""

    def test_creates_directory_and_inits(self, tmp_path: Path) -> None:
        """New directory: create it, git init, cub init."""
        target = tmp_path / "myproject"

        with (
            patch("cub.cli.new.subprocess.run") as mock_run,
            patch("cub.cli.new.init_project") as mock_init,
        ):
            # git init succeeds
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 0
        assert target.exists()
        assert "Project ready" in result.output
        # Called git init
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "init"]
        # Called init_project
        mock_init.assert_called_once_with(target, force=False, install_hooks_flag=True)

    def test_existing_empty_directory(self, tmp_path: Path) -> None:
        """Existing empty directory: git init + cub init, no prompt."""
        target = tmp_path / "emptydir"
        target.mkdir()

        with patch("cub.cli.new.subprocess.run") as mock_run, patch("cub.cli.new.init_project"):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 0
        mock_run.assert_called_once()

    def test_existing_nonempty_directory_confirmed(self, tmp_path: Path) -> None:
        """Non-empty directory with user confirmation runs cub init."""
        target = tmp_path / "hasfiles"
        target.mkdir()
        (target / "README.md").write_text("hello")
        (target / ".git").mkdir()  # already has git

        with patch("cub.cli.new.init_project") as mock_init:
            # "y" confirms the prompt
            result = runner.invoke(app, ["new", str(target)], input="y\n")

        assert result.exit_code == 0
        # init_project was called (no git init since .git exists)
        mock_init.assert_called_once()

    def test_existing_nonempty_directory_declined(self, tmp_path: Path) -> None:
        """Non-empty directory with user declining exits cleanly."""
        target = tmp_path / "hasfiles"
        target.mkdir()
        (target / "README.md").write_text("hello")

        result = runner.invoke(app, ["new", str(target)], input="n\n")

        assert result.exit_code == 0

    def test_git_init_failure(self, tmp_path: Path) -> None:
        """Git init failure prints error and exits 1."""
        target = tmp_path / "newproject"

        with patch("cub.cli.new.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: error")
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 1
        assert "git init failed" in result.output

    def test_skips_git_init_when_git_exists(self, tmp_path: Path) -> None:
        """Skips git init when .git directory already exists in non-empty dir."""
        target = tmp_path / "gitproject"
        target.mkdir()
        (target / ".git").mkdir()
        (target / "README.md").write_text("hello")

        with patch("cub.cli.new.subprocess.run") as mock_run, patch("cub.cli.new.init_project"):
            # Confirm the prompt for non-empty directory
            result = runner.invoke(app, ["new", str(target)], input="y\n")

        assert result.exit_code == 0
        # No subprocess calls (git init was skipped)
        mock_run.assert_not_called()

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        """Creates nested parent directories."""
        target = tmp_path / "a" / "b" / "myproject"

        with patch("cub.cli.new.subprocess.run") as mock_run, patch("cub.cli.new.init_project"):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 0
        assert target.exists()
