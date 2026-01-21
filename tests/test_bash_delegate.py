"""
Tests for bash delegation module.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cub.core.bash_delegate import (
    BashCubNotFoundError,
    delegate_to_bash,
    find_bash_cub,
    is_bash_command,
)


class TestFindBashCub:
    """Tests for find_bash_cub function."""

    def test_finds_via_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test finding bash cub via CUB_BASH_PATH."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        result = find_bash_cub()
        assert result == bash_script

    def test_env_var_nonexistent_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that non-existent CUB_BASH_PATH raises error."""
        monkeypatch.setenv("CUB_BASH_PATH", "/nonexistent/path")

        with pytest.raises(BashCubNotFoundError, match="non-existent file"):
            find_bash_cub()

    def test_finds_bundled_script(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test finding bundled bash script in package bash/ directory."""
        # Unset CUB_BASH_PATH
        monkeypatch.delenv("CUB_BASH_PATH", raising=False)

        # Mock __file__ location to simulate package structure
        # __file__ = .../cub/core/bash_delegate.py
        # bundled = .../cub/bash/cub (i.e., __file__.parent.parent / "bash" / "cub")
        mock_file = tmp_path / "src" / "cub" / "core" / "bash_delegate.py"
        bash_dir = tmp_path / "src" / "cub" / "bash"
        bash_dir.mkdir(parents=True, exist_ok=True)
        bash_script = bash_dir / "cub"
        bash_script.write_text("#!/usr/bin/env bash\n")

        with patch("cub.core.bash_delegate.__file__", str(mock_file)):
            result = find_bash_cub()
            assert result == bash_script

    def test_finds_system_path_bash_script(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test finding bash cub in system PATH."""
        monkeypatch.delenv("CUB_BASH_PATH", raising=False)

        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\necho 'bash cub'\n")

        # Mock __file__ to point somewhere that doesn't have bundled script
        fake_file = tmp_path / "other" / "location" / "bash_delegate.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("cub.core.bash_delegate.__file__", str(fake_file)):
            with patch("shutil.which", return_value=str(bash_script)):
                result = find_bash_cub()
                assert result == bash_script.resolve()

    def test_raises_if_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that BashCubNotFoundError is raised when script not found."""
        monkeypatch.delenv("CUB_BASH_PATH", raising=False)

        # Mock __file__ to point somewhere without bundled script
        fake_file = tmp_path / "other" / "location" / "bash_delegate.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("cub.core.bash_delegate.__file__", str(fake_file)):
            with patch("shutil.which", return_value=None):
                with pytest.raises(BashCubNotFoundError, match="Could not locate"):
                    find_bash_cub()


class TestIsBashCommand:
    """Tests for is_bash_command function."""

    def test_python_commands_return_false(self) -> None:
        """Test that ported Python commands return False."""
        python_commands = ["run", "status", "init", "monitor", "version"]
        for cmd in python_commands:
            assert is_bash_command(cmd) is False

    def test_bash_commands_return_true(self) -> None:
        """Test that bash-only commands return True."""
        bash_commands = [
            # prep pipeline commands removed - now using native cub plan
            "interview",
            "doctor",
            "branch",
            "branches",
            "checkpoints",
        ]
        for cmd in bash_commands:
            assert is_bash_command(cmd) is True

    def test_unknown_command_returns_false(self) -> None:
        """Test that unknown commands return False (don't delegate)."""
        assert is_bash_command("unknown") is False
        assert is_bash_command("foobar") is False


class TestDelegateToBash:
    """Tests for delegate_to_bash function."""

    def test_delegates_with_correct_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that delegate_to_bash calls bash cub with correct args."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                delegate_to_bash("interview", ["--help"])

            assert exc_info.value.code == 0
            mock_run.assert_called_once()
            args = mock_run.call_args
            assert args[0][0] == [str(bash_script), "interview", "--help"]

    def test_passes_through_exit_codes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that exit codes are passed through correctly."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 42\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 42

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(SystemExit) as exc_info:
                delegate_to_bash("interview", ["task-123"])

            assert exc_info.value.code == 42

    def test_preserves_debug_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that debug flag is preserved in environment."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\nexit 0\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        # Mock sys.argv to include --debug
        with patch.object(sys, "argv", ["cub", "--debug", "interview", "task-123"]):
            mock_result = Mock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                with pytest.raises(SystemExit):
                    delegate_to_bash("interview", ["task-123"])

                # Check that CUB_DEBUG was set in env
                call_args = mock_run.call_args
                assert call_args[1]["env"]["CUB_DEBUG"] == "true"

    def test_handles_keyboard_interrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that KeyboardInterrupt is handled with exit code 130."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        with patch("subprocess.run", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                delegate_to_bash("interview", ["task-123"])

            assert exc_info.value.code == 130

    def test_handles_file_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that FileNotFoundError is handled gracefully."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(SystemExit) as exc_info:
                delegate_to_bash("interview", ["task-123"])

            assert exc_info.value.code == 1

    def test_handles_bash_cub_not_found(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test handling when bash cub cannot be located."""
        monkeypatch.delenv("CUB_BASH_PATH", raising=False)

        with patch("cub.core.bash_delegate.find_bash_cub") as mock_find:
            mock_find.side_effect = BashCubNotFoundError("Not found")

            with pytest.raises(SystemExit) as exc_info:
                delegate_to_bash("interview", ["task-123"])

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            # Rich console.print outputs to stdout, not stderr
            assert "Error: Not found" in captured.out
            assert "bash version of cub is required" in captured.out

    def test_passes_additional_args(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that additional arguments are passed correctly."""
        bash_script = tmp_path / "cub"
        bash_script.write_text("#!/usr/bin/env bash\n")
        monkeypatch.setenv("CUB_BASH_PATH", str(bash_script))

        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with pytest.raises(SystemExit):
                delegate_to_bash("interview", ["task-123", "--auto"])

            args = mock_run.call_args
            assert args[0][0] == [str(bash_script), "interview", "task-123", "--auto"]
