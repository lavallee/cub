"""
Tests for the capture CLI command.

Tests the `cub capture` command for quick text capture functionality.

Two-tier storage model:
- Default: Global captures at ~/.local/share/cub/captures/{project}/
- With --project: Project captures at ./captures/
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cub.cli import app

runner = CliRunner()


@pytest.fixture
def isolated_capture_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up an isolated environment for capture tests."""
    # Set up project directory
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    # Set up global captures directory
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(global_dir))

    # Mock get_project_id to return a consistent value
    with patch("cub.core.captures.store.get_project_id", return_value="test-project"):
        with patch("cub.core.captures.project_id.get_project_id", return_value="test-project"):
            yield {
                "project_dir": project_dir,
                "global_dir": global_dir,
                "global_captures_dir": global_dir / "cub" / "captures" / "test-project",
                "project_captures_dir": project_dir / "captures",
            }


class TestCaptureCommand:
    """Test the capture command functionality."""

    def test_capture_with_text_argument(self, isolated_capture_env: dict) -> None:
        """Test capturing text provided as argument (default goes to global)."""
        result = runner.invoke(app, ["capture", "Add dark mode to UI"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "global" in result.output

        # Verify file was created in global location
        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        assert capture_file.exists()
        content = capture_file.read_text()
        assert "id: cap-001" in content
        assert "Add dark mode to UI" in content

    def test_capture_with_tags(self, isolated_capture_env: dict) -> None:
        """Test capturing text with tags."""
        result = runner.invoke(
            app, ["capture", "Add dark mode", "--tag", "feature", "--tag", "ui"]
        )

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify tags in frontmatter
        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        assert "tags:" in content
        assert "- feature" in content
        assert "- ui" in content

    def test_capture_with_priority(self, isolated_capture_env: dict) -> None:
        """Test capturing text with priority."""
        result = runner.invoke(
            app, ["capture", "Critical bug fix", "--priority", "1"]
        )

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify priority in frontmatter
        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        assert "priority: 1" in content

    def test_capture_to_project_store(self, isolated_capture_env: dict) -> None:
        """Test capturing to project store with --project flag."""
        result = runner.invoke(app, ["capture", "Project note", "--project"])

        assert result.exit_code == 0
        assert "cap-001" in result.output
        assert "project" in result.output

        # Verify file was created in project location
        capture_file = isolated_capture_env["project_captures_dir"] / "cap-001.md"
        assert capture_file.exists()

    def test_capture_generates_sequential_ids(self, isolated_capture_env: dict) -> None:
        """Test that multiple captures get sequential IDs."""
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

    def test_capture_with_empty_content_fails(self, isolated_capture_env: dict) -> None:
        """Test that capturing empty content fails."""
        result = runner.invoke(app, ["capture", ""])

        assert result.exit_code == 1
        assert "empty" in result.output.lower()

    def test_capture_multiline_text(self, isolated_capture_env: dict) -> None:
        """Test capturing multiline text."""
        multiline_text = "First line\nSecond line\nThird line"
        result = runner.invoke(app, ["capture", multiline_text])

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify content preserved
        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        assert "First line" in content
        assert "Second line" in content
        assert "Third line" in content

    def test_capture_long_title_truncated(self, isolated_capture_env: dict) -> None:
        """Test that very long titles are truncated in frontmatter."""
        # Create text with first line over 80 chars
        long_title = "A" * 100
        result = runner.invoke(app, ["capture", long_title])

        assert result.exit_code == 0

        # Verify title was truncated
        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
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
        # Should mention global being the default
        assert "global" in result.output.lower()

    def test_capture_with_stdin(self, isolated_capture_env: dict) -> None:
        """Test capturing from stdin."""
        stdin_text = "Text from stdin"
        result = runner.invoke(app, ["capture"], input=stdin_text)

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify content
        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
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


class TestCaptureAutoTagging:
    """Test auto-tagging functionality."""

    def test_capture_auto_tags_git_keyword(self, isolated_capture_env: dict) -> None:
        """Test that 'git' keyword triggers 'git' tag."""
        result = runner.invoke(app, ["capture", "Fix git merge conflict"])

        assert result.exit_code == 0
        assert "cap-001" in result.output

        # Verify tag was auto-suggested
        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        assert "tags:" in content
        assert "- git" in content

    def test_capture_auto_tags_ui_keyword(self, isolated_capture_env: dict) -> None:
        """Test that 'ui' keyword triggers 'ui' tag."""
        result = runner.invoke(app, ["capture", "Fix button styling in UI"])

        assert result.exit_code == 0

        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        assert "- ui" in content

    def test_capture_auto_tags_api_keyword(self, isolated_capture_env: dict) -> None:
        """Test that 'api' keyword triggers 'api' tag."""
        result = runner.invoke(app, ["capture", "Implement new API endpoint"])

        assert result.exit_code == 0

        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        assert "- api" in content

    def test_capture_auto_tags_multiple(self, isolated_capture_env: dict) -> None:
        """Test multiple auto-tags suggested from single content."""
        result = runner.invoke(
            app, ["capture", "Fix git merge conflict in API endpoint"]
        )

        assert result.exit_code == 0

        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        assert "- git" in content
        assert "- api" in content

    def test_capture_no_auto_tags_flag_disables_tagging(
        self, isolated_capture_env: dict
    ) -> None:
        """Test that --no-auto-tags disables auto-tagging."""
        result = runner.invoke(
            app, ["capture", "Fix git merge conflict", "--no-auto-tags"]
        )

        assert result.exit_code == 0

        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        # Should not have auto-suggested tags
        assert "- git" not in content
        # Should also not have 'tags:' key if no tags were provided
        lines = content.split("\n")
        # Find if tags: exists in frontmatter
        in_frontmatter = False
        has_tags = False
        for line in lines:
            if line.startswith("---"):
                in_frontmatter = not in_frontmatter
            elif in_frontmatter and line.startswith("tags:"):
                has_tags = True
        assert not has_tags

    def test_capture_user_tags_plus_auto_tags(self, isolated_capture_env: dict) -> None:
        """Test that user-provided tags are combined with auto-tags."""
        result = runner.invoke(
            app, ["capture", "Fix git merge conflict", "--tag", "urgent"]
        )

        assert result.exit_code == 0

        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        # Should have both user-provided and auto-suggested tags
        assert "- urgent" in content
        assert "- git" in content

    def test_capture_auto_tags_no_duplicates(self, isolated_capture_env: dict) -> None:
        """Test that user tags are not duplicated if auto-suggested."""
        result = runner.invoke(
            app, ["capture", "Fix git merge conflict", "--tag", "git"]
        )

        assert result.exit_code == 0

        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        # Should only have one 'git' tag, not duplicated
        git_count = content.count("- git")
        assert git_count == 1

    def test_capture_auto_tags_with_no_matches(
        self, isolated_capture_env: dict
    ) -> None:
        """Test that content with no matching keywords has no auto-tags."""
        result = runner.invoke(app, ["capture", "This is a generic note"])

        assert result.exit_code == 0

        capture_file = isolated_capture_env["global_captures_dir"] / "cap-001.md"
        content = capture_file.read_text()
        # Should not have tags key if no tags were assigned
        lines = content.split("\n")
        in_frontmatter = False
        has_tags = False
        for line in lines:
            if line.startswith("---"):
                in_frontmatter = not in_frontmatter
            elif in_frontmatter and line.startswith("tags:"):
                has_tags = True
        assert not has_tags
