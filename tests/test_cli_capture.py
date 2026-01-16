"""
Tests for the capture CLI command.

Tests the `cub capture` command for quick text capture functionality.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from cub.cli import app

runner = CliRunner()


class TestCaptureCommand:
    """Test the capture command functionality."""

    def test_capture_with_text_argument(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test capturing text provided as argument."""
        # Set up project directory
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["capture", "Add dark mode to UI"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "project" in result.output

        # Verify file was created
        capture_file = project_dir / "captures" / "cap-001.md"
        assert capture_file.exists()
        content = capture_file.read_text()
        assert "id: cap-001" in content
        assert "Add dark mode to UI" in content

    def test_capture_with_tags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test capturing text with tags."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["capture", "Add dark mode", "--tag", "feature", "--tag", "ui"])

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify tags in frontmatter
        capture_file = project_dir / "captures" / "cap-001.md"
        content = capture_file.read_text()
        assert "tags:" in content
        assert "- feature" in content
        assert "- ui" in content

    def test_capture_with_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test capturing text with priority."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["capture", "Critical bug fix", "--priority", "1"])

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify priority in frontmatter
        capture_file = project_dir / "captures" / "cap-001.md"
        content = capture_file.read_text()
        assert "priority: 1" in content

    def test_capture_to_global_store(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test capturing to global store."""
        # Mock XDG_DATA_HOME to use tmp_path
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

        result = runner.invoke(app, ["capture", "Global note", "--global"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "global" in result.output

        # Verify file was created in global location
        capture_file = global_dir / "cub" / "captures" / "cap-001.md"
        assert capture_file.exists()

    def test_capture_generates_sequential_ids(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that multiple captures get sequential IDs."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # First capture
        result1 = runner.invoke(app, ["capture", "First idea"])
        assert result1.exit_code == 0
        assert "cap-001" in result1.output

        # Second capture
        result2 = runner.invoke(app, ["capture", "Second idea"])
        assert result2.exit_code == 0
        assert "cap-002" in result2.output

        # Third capture
        result3 = runner.invoke(app, ["capture", "Third idea"])
        assert result3.exit_code == 0
        assert "cap-003" in result3.output

    def test_capture_with_empty_content_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that capturing empty content fails."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["capture", ""])

        assert result.exit_code == 1
        assert "empty" in result.output.lower()

    def test_capture_multiline_text(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test capturing multiline text."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        multiline_text = "First line\nSecond line\nThird line"
        result = runner.invoke(app, ["capture", multiline_text])

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify content preserved
        capture_file = project_dir / "captures" / "cap-001.md"
        content = capture_file.read_text()
        assert "First line" in content
        assert "Second line" in content
        assert "Third line" in content

    def test_capture_long_title_truncated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that very long titles are truncated in frontmatter."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Create text with first line over 80 chars
        long_title = "A" * 100
        result = runner.invoke(app, ["capture", long_title])

        assert result.exit_code == 0

        # Verify title was truncated
        capture_file = project_dir / "captures" / "cap-001.md"
        content = capture_file.read_text()
        # Title should be truncated to ~80 chars with "..."
        assert "title:" in content
        # Should contain ellipsis
        assert "..." in content

    def test_capture_help_output(self) -> None:
        """Test that capture command shows help."""
        result = runner.invoke(app, ["capture", "--help"])

        assert result.exit_code == 0
        assert "capture" in result.output.lower()
        assert "quick" in result.output.lower() or "idea" in result.output.lower()

    def test_capture_with_stdin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test capturing from stdin."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        stdin_text = "Text from stdin"
        result = runner.invoke(app, ["capture"], input=stdin_text)

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify content
        capture_file = project_dir / "captures" / "cap-001.md"
        content = capture_file.read_text()
        assert "Text from stdin" in content
        # When reading from stdin, source should be PIPE
        assert "source: pipe" in content


class TestCaptureErrorHandling:
    """Test error handling in capture command."""

    def test_capture_no_content_no_stdin_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that capture fails when no content provided and stdin is tty."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # When no input is provided and stdin is a tty, should fail
        # Note: In CliRunner, stdin is not a tty by default, but we can test the error message
        result = runner.invoke(app, ["capture"])

        # Should exit with error when no input
        assert result.exit_code != 0

    def test_capture_invalid_priority_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalid priority values are rejected."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)

        # Priority too high
        result = runner.invoke(app, ["capture", "Test", "--priority", "10"])
        assert result.exit_code != 0

        # Priority too low
        result = runner.invoke(app, ["capture", "Test", "--priority", "0"])
        assert result.exit_code != 0
