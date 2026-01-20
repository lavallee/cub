"""
Tests for --direct flag functionality in cub run command.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from cub.cli.run import (
    _read_direct_input,
    generate_direct_task_prompt,
)


class TestReadDirectInput:
    """Tests for _read_direct_input function."""

    def test_read_plain_string(self):
        """Test reading a plain string as direct input."""
        result = _read_direct_input("Add a logout button")
        assert result == "Add a logout button"

    def test_read_plain_string_with_whitespace(self):
        """Test reading string with leading/trailing whitespace."""
        result = _read_direct_input("  Fix the typo  ")
        assert result == "Fix the typo"

    def test_read_from_file(self, tmp_path: Path):
        """Test reading task content from a file with @ prefix."""
        task_file = tmp_path / "task.txt"
        task_file.write_text("Implement user authentication\nwith JWT tokens")

        result = _read_direct_input(f"@{task_file}")
        assert result == "Implement user authentication\nwith JWT tokens"

    def test_read_from_file_strips_whitespace(self, tmp_path: Path):
        """Test that file content whitespace is stripped."""
        task_file = tmp_path / "task.txt"
        task_file.write_text("\n  Add dark mode  \n\n")

        result = _read_direct_input(f"@{task_file}")
        assert result == "Add dark mode"

    def test_read_from_nonexistent_file(self, tmp_path: Path):
        """Test reading from nonexistent file raises Exit."""
        with pytest.raises(typer.Exit) as exc_info:
            _read_direct_input(f"@{tmp_path}/nonexistent.txt")
        assert exc_info.value.exit_code == 1

    def test_read_from_stdin(self):
        """Test reading task content from stdin."""
        with patch.object(sys, "stdin", io.StringIO("Task from stdin\n")):
            with patch.object(sys.stdin, "isatty", return_value=False):
                result = _read_direct_input("-")
        assert result == "Task from stdin"

    def test_read_from_stdin_tty_error(self):
        """Test that stdin from TTY raises Exit with helpful message."""
        with patch.object(sys.stdin, "isatty", return_value=True):
            with pytest.raises(typer.Exit) as exc_info:
                _read_direct_input("-")
        assert exc_info.value.exit_code == 1


class TestGenerateDirectTaskPrompt:
    """Tests for generate_direct_task_prompt function."""

    def test_basic_prompt_generation(self):
        """Test basic prompt contains task content."""
        prompt = generate_direct_task_prompt("Add a logout button")

        assert "Add a logout button" in prompt
        assert "## CURRENT TASK" in prompt
        assert "Mode: Direct" in prompt

    def test_prompt_contains_completion_instructions(self):
        """Test prompt includes completion instructions."""
        prompt = generate_direct_task_prompt("Fix the bug")

        assert "When complete:" in prompt
        assert "Run feedback loops" in prompt
        assert "Commit changes" in prompt

    def test_prompt_notes_no_task_backend(self):
        """Test prompt mentions no task ID to close."""
        prompt = generate_direct_task_prompt("Update docs")

        assert "No task ID to close" in prompt
        assert "direct task without a task backend" in prompt

    def test_prompt_preserves_multiline_content(self):
        """Test prompt preserves multiline task descriptions."""
        content = """Implement feature X:
- First do A
- Then do B
- Finally do C"""

        prompt = generate_direct_task_prompt(content)

        assert "First do A" in prompt
        assert "Then do B" in prompt
        assert "Finally do C" in prompt


class TestDirectFlagValidation:
    """Tests for --direct flag validation with incompatible flags."""

    @pytest.fixture
    def mock_run_deps(self):
        """Mock dependencies for run command."""
        with (
            patch("cub.cli.run.load_config") as mock_config,
            patch("cub.cli.run.detect_async_harness") as mock_detect,
            patch("cub.cli.run.get_async_backend") as mock_harness,
            patch("cub.cli.run._read_direct_input") as mock_read,
        ):
            # Setup mock config
            mock_config_obj = MagicMock()
            mock_config_obj.harness.priority = ["claude"]
            mock_config_obj.harness.model = None
            mock_config.return_value = mock_config_obj

            mock_detect.return_value = "claude"

            # Setup mock harness
            mock_harness_backend = MagicMock()
            mock_harness_backend.is_available.return_value = True
            mock_harness_backend.get_version.return_value = "1.0"
            mock_harness_backend.capabilities.streaming = False
            mock_harness.return_value = mock_harness_backend

            mock_read.return_value = "Test task"

            yield {
                "config": mock_config,
                "detect": mock_detect,
                "harness": mock_harness,
                "read": mock_read,
            }

    def test_direct_with_task_id_fails(self, mock_run_deps):
        """Test --direct cannot be combined with --task."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--direct", "Test", "--task", "cub-123"])

        assert result.exit_code == 1
        assert "--direct cannot be used with --task" in result.output

    def test_direct_with_epic_fails(self, mock_run_deps):
        """Test --direct cannot be combined with --epic."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--direct", "Test", "--epic", "epic-1"])

        assert result.exit_code == 1
        assert "--direct cannot be used with --epic" in result.output

    def test_direct_with_label_fails(self, mock_run_deps):
        """Test --direct cannot be combined with --label."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--direct", "Test", "--label", "urgent"])

        assert result.exit_code == 1
        assert "--direct cannot be used with --label" in result.output

    def test_direct_with_ready_fails(self, mock_run_deps):
        """Test --direct cannot be combined with --ready."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--direct", "Test", "--ready"])

        assert result.exit_code == 1
        assert "--direct cannot be used with --ready" in result.output

    def test_direct_with_parallel_fails(self, mock_run_deps):
        """Test --direct cannot be combined with --parallel."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--direct", "Test", "--parallel", "3"])

        assert result.exit_code == 1
        assert "--direct cannot be used with --parallel" in result.output


class TestGhIssueFlagValidation:
    """Tests for --gh-issue flag validation with incompatible flags."""

    def test_gh_issue_with_task_id_fails(self):
        """Test --gh-issue cannot be combined with --task."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--gh-issue", "123", "--task", "cub-123"])

        assert result.exit_code == 1
        assert "--gh-issue cannot be used with --task" in result.output

    def test_gh_issue_with_epic_fails(self):
        """Test --gh-issue cannot be combined with --epic."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--gh-issue", "123", "--epic", "epic-1"])

        assert result.exit_code == 1
        assert "--gh-issue cannot be used with --epic" in result.output

    def test_gh_issue_with_label_fails(self):
        """Test --gh-issue cannot be combined with --label."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--gh-issue", "123", "--label", "urgent"])

        assert result.exit_code == 1
        assert "--gh-issue cannot be used with --label" in result.output

    def test_gh_issue_with_ready_fails(self):
        """Test --gh-issue cannot be combined with --ready."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--gh-issue", "123", "--ready"])

        assert result.exit_code == 1
        assert "--gh-issue cannot be used with --ready" in result.output

    def test_gh_issue_with_parallel_fails(self):
        """Test --gh-issue cannot be combined with --parallel."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--gh-issue", "123", "--parallel", "3"])

        assert result.exit_code == 1
        assert "--gh-issue cannot be used with --parallel" in result.output

    def test_gh_issue_with_direct_fails(self):
        """Test --gh-issue cannot be combined with --direct."""
        from typer.testing import CliRunner

        from cub.cli.run import app

        runner = CliRunner()
        result = runner.invoke(app, ["--gh-issue", "123", "--direct", "Test"])

        assert result.exit_code == 1
        assert "--gh-issue cannot be used with --direct" in result.output
