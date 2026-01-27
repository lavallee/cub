"""Tests for cub new command."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli import app

runner = CliRunner()


@pytest.fixture
def mock_bash_cub(tmp_path: Path) -> Path:
    """Create a fake bash cub script."""
    script = tmp_path / "cub-bash"
    script.write_text("#!/bin/bash\nexit 0\n")
    script.chmod(0o755)
    return script


class TestNewCommand:
    """Tests for the cub new command."""

    def test_creates_directory_and_inits(
        self, tmp_path: Path, mock_bash_cub: Path
    ) -> None:
        """New directory: create it, git init, cub init."""
        target = tmp_path / "myproject"

        with patch("cub.cli.new.find_bash_cub", return_value=mock_bash_cub), patch(
            "cub.cli.new.subprocess.run"
        ) as mock_run, patch("cub.cli.new.run_hooks"):
            # git init succeeds, cub init succeeds
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),
                MagicMock(returncode=0),
            ]
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 0
        assert target.exists()
        assert "Project ready" in result.output
        # Called git init and cub init
        assert mock_run.call_count == 2
        # First call is git init
        assert mock_run.call_args_list[0][0][0] == ["git", "init"]

    def test_existing_empty_directory(
        self, tmp_path: Path, mock_bash_cub: Path
    ) -> None:
        """Existing empty directory: git init + cub init, no prompt."""
        target = tmp_path / "emptydir"
        target.mkdir()

        with patch("cub.cli.new.find_bash_cub", return_value=mock_bash_cub), patch(
            "cub.cli.new.subprocess.run"
        ) as mock_run, patch("cub.cli.new.run_hooks"):
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),
                MagicMock(returncode=0),
            ]
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 0
        assert mock_run.call_count == 2

    def test_existing_nonempty_directory_confirmed(
        self, tmp_path: Path, mock_bash_cub: Path
    ) -> None:
        """Non-empty directory with user confirmation runs cub init."""
        target = tmp_path / "hasfiles"
        target.mkdir()
        (target / "README.md").write_text("hello")
        (target / ".git").mkdir()  # already has git

        with patch("cub.cli.new.find_bash_cub", return_value=mock_bash_cub), patch(
            "cub.cli.new.subprocess.run"
        ) as mock_run, patch("cub.cli.new.run_hooks"):
            mock_run.return_value = MagicMock(returncode=0)
            # "y" confirms the prompt
            result = runner.invoke(app, ["new", str(target)], input="y\n")

        assert result.exit_code == 0
        # Only cub init (git already exists)
        assert mock_run.call_count == 1

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
            mock_run.return_value = MagicMock(
                returncode=128, stdout="", stderr="fatal: error"
            )
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 1
        assert "git init failed" in result.output

    def test_cub_init_failure(
        self, tmp_path: Path, mock_bash_cub: Path
    ) -> None:
        """cub init failure prints error and exits with its code."""
        target = tmp_path / "newproject"

        with patch("cub.cli.new.find_bash_cub", return_value=mock_bash_cub), patch(
            "cub.cli.new.subprocess.run"
        ) as mock_run, patch("cub.cli.new.run_hooks"):
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),  # git init ok
                MagicMock(returncode=1),  # cub init fails
            ]
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 1
        assert "cub init failed" in result.output

    def test_bash_cub_not_found(self, tmp_path: Path) -> None:
        """Missing bash cub prints error."""
        target = tmp_path / "newproject"

        with patch(
            "cub.cli.new.find_bash_cub",
            side_effect=RuntimeError("not found"),
        ), patch("cub.cli.new.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 1

    def test_skips_git_init_when_git_exists(
        self, tmp_path: Path, mock_bash_cub: Path
    ) -> None:
        """Skips git init when .git directory already exists in non-empty dir."""
        target = tmp_path / "gitproject"
        target.mkdir()
        (target / ".git").mkdir()
        (target / "README.md").write_text("hello")

        with patch("cub.cli.new.find_bash_cub", return_value=mock_bash_cub), patch(
            "cub.cli.new.subprocess.run"
        ) as mock_run, patch("cub.cli.new.run_hooks"):
            mock_run.return_value = MagicMock(returncode=0)
            # Confirm the prompt for non-empty directory
            result = runner.invoke(app, ["new", str(target)], input="y\n")

        assert result.exit_code == 0
        # Only cub init, no git init (because .git already exists)
        assert mock_run.call_count == 1
        assert mock_run.call_args[0][0] == [str(mock_bash_cub), "init"]

    def test_creates_nested_directories(
        self, tmp_path: Path, mock_bash_cub: Path
    ) -> None:
        """Creates nested parent directories."""
        target = tmp_path / "a" / "b" / "myproject"

        with patch("cub.cli.new.find_bash_cub", return_value=mock_bash_cub), patch(
            "cub.cli.new.subprocess.run"
        ) as mock_run, patch("cub.cli.new.run_hooks"):
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),
                MagicMock(returncode=0),
            ]
            result = runner.invoke(app, ["new", str(target)])

        assert result.exit_code == 0
        assert target.exists()
