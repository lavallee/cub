"""
Tests for prep command argument passing.

Issue #46: cub prep should honor arguments and pass them in to the process.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from cub.cli import app

runner = CliRunner()


class TestPrepArgumentPassing:
    """Test that prep command properly passes arguments to bash script."""

    def test_prep_with_vision_file_argument(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'cub prep specs/researching/new-idea.md' passes the file path."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\necho \"$@\"\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["prep", "specs/researching/new-idea.md"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            # Should pass the vision file argument to bash script
            assert call_args[0][0] == [
                str(bash_script),
                "prep",
                "specs/researching/new-idea.md",
            ]

    @pytest.mark.skip(
        reason="prep command now uses 'cub plan' pipeline - doesn't support --session flag"
    )
    def test_prep_with_multiple_arguments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that prep can handle multiple positional arguments."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Use positional arguments - flags like --session need to be passed
            # after -- to avoid Typer intercepting them
            result = runner.invoke(
                app, ["prep", "myproj-123", "specs/doc.md"]
            )

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [
                str(bash_script),
                "prep",
                "myproj-123",
                "specs/doc.md",
            ]

    @pytest.mark.skip(
        reason="prep command now uses 'cub plan' pipeline - doesn't support --vision flag"
    )
    def test_prep_with_vision_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that prep passes flags after -- separator to bash."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Use -- to pass flags through to bash without Typer intercepting them
            result = runner.invoke(app, ["prep", "--", "--vision", "specs/doc.md"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [
                str(bash_script),
                "prep",
                "--vision",
                "specs/doc.md",
            ]

    def test_triage_with_vision_argument(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'cub triage specs/doc.md' passes the file path."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["triage", "specs/doc.md"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [str(bash_script), "triage", "specs/doc.md"]

    @pytest.mark.skip(
        reason="'cub architect' is now 'cub plan architect' - Python native, not bash"
    )
    def test_architect_with_session_argument(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'cub architect session-id' passes the session ID."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["architect", "myproj-20260120-123456"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [
                str(bash_script),
                "architect",
                "myproj-20260120-123456",
            ]

    @pytest.mark.skip(
        reason="'cub plan' is now Python native with subcommands - use 'cub plan orient/architect/itemize'"
    )
    def test_plan_with_session_argument(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'cub plan session-id' passes the session ID."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["plan", "myproj-20260120-123456"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [
                str(bash_script),
                "plan",
                "myproj-20260120-123456",
            ]

    def test_bootstrap_with_session_argument(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'cub bootstrap session-id' passes the session ID."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["bootstrap", "myproj-20260120-123456"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [
                str(bash_script),
                "bootstrap",
                "myproj-20260120-123456",
            ]
