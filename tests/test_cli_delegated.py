"""
Tests for CLI delegated commands.

These tests verify that delegated commands are properly registered in the CLI
and correctly pass through to the bash implementation.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from cub.cli import app

runner = CliRunner()


class TestDelegatedCommandsHelp:
    """Test that delegated commands show help text correctly."""

    @pytest.mark.parametrize(
        "command",
        [
            "prep",
            "triage",
            "architect",
            "plan",
            "bootstrap",
            "sessions",
            "interview",
            "branch",
            "branches",
            "checkpoints",
            "pr",
            "explain",
            "artifacts",
            "validate",
            "guardrails",
            "doctor",
            "upgrade",
            "migrate-layout",
            "agent-close",
            "agent-verify",
        ],
    )
    def test_delegated_command_registered(self, command: str) -> None:
        """Test that delegated commands are registered in the app."""
        # Get all command names from the app
        commands = [cmd.name for cmd in app.registered_commands]
        assert command in commands, f"Command '{command}' not registered in app"


class TestDelegatedCommandPassthrough:
    """Test that delegated commands pass arguments through to bash."""

    def test_prep_command_delegates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that 'cub prep' delegates to bash with correct args."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\necho 'prep called'\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["prep"])

            # Should delegate and exit with 0
            assert result.exit_code == 0
            mock_run.assert_called_once()
            # Verify the command was built correctly
            call_args = mock_run.call_args
            assert call_args[0][0] == [str(bash_script), "prep"]

    def test_triage_command_delegates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'cub triage' delegates to bash."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["triage"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [str(bash_script), "triage"]

    def test_interview_with_args_delegates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'cub interview' passes args correctly."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["interview", "task-123"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [str(bash_script), "interview", "task-123"]

    def test_branch_with_multiple_args_delegates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'cub branch' passes multiple args correctly."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["branch", "cub-123"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [str(bash_script), "branch", "cub-123"]

    def test_delegated_command_passes_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that delegated commands pass through exit codes."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 42\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 42

        with patch("subprocess.run", return_value=mock_result):
            result = runner.invoke(app, ["prep"])

            assert result.exit_code == 42

    def test_delegated_command_with_no_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test delegated command with no additional args."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["sessions"])

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            # Should have just the command, no extra args
            assert call_args[0][0] == [str(bash_script), "sessions"]


class TestDelegatedCommandsDebugFlag:
    """Test that debug flag is preserved in delegated commands."""

    def test_debug_flag_preserved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that --debug flag is passed to bash script."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        # Add --debug to sys.argv to simulate user passing it
        import sys
        with patch.object(sys, "argv", ["cub", "--debug", "prep"]):
            mock_result = Mock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                # Global --debug flag before command
                result = runner.invoke(app, ["--debug", "prep"])

                assert result.exit_code == 0
                mock_run.assert_called_once()
                # Check that CUB_DEBUG env var was set
                call_args = mock_run.call_args
                assert call_args[1]["env"]["CUB_DEBUG"] == "true"


class TestDelegatedCommandsErrorHandling:
    """Test error handling in delegated commands."""

    def test_missing_bash_script_shows_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing bash script shows helpful error."""
        monkeypatch.delenv("CUB_BASH_PATH", raising=False)

        with patch("cub.core.bash_delegate.find_bash_cub") as mock_find:
            from cub.core.bash_delegate import BashCubNotFoundError

            mock_find.side_effect = BashCubNotFoundError("Not found")

            result = runner.invoke(app, ["prep"])

            assert result.exit_code == 1

    def test_keyboard_interrupt_handled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that KeyboardInterrupt is handled gracefully."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        with patch("subprocess.run", side_effect=KeyboardInterrupt):
            result = runner.invoke(app, ["prep"])

            # Should exit with 130 (standard for SIGINT)
            assert result.exit_code == 130


class TestSpecificDelegatedCommands:
    """Test specific delegated commands for regression testing."""

    @pytest.mark.parametrize(
        "command,args",
        [
            ("prep", []),
            ("triage", []),
            ("architect", []),
            ("plan", []),
            ("bootstrap", []),
            ("sessions", []),
            ("interview", ["task-456"]),
            ("branch", ["cub-789"]),
            ("branches", []),
            ("checkpoints", []),
            ("pr", ["cub-001"]),
            ("explain", ["task-123"]),
            ("artifacts", []),
            ("validate", []),
            ("guardrails", []),
            ("doctor", []),
            ("upgrade", []),
            ("migrate-layout", []),
            ("agent-close", ["task-123"]),
            ("agent-verify", ["task-123"]),
        ],
    )
    def test_command_with_args_structure(
        self,
        command: str,
        args: list[str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that various commands and arg combinations work correctly."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, [command] + args)

            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            expected_cmd = [str(bash_script), command] + args
            assert call_args[0][0] == expected_cmd
