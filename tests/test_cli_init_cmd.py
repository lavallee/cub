"""
Tests for CLI init_cmd module.
"""

from pathlib import Path

import pytest

from cub.cli.init_cmd import generate_instruction_files


class TestGenerateInstructionFiles:
    """Tests for generate_instruction_files function."""

    def test_creates_both_files(self, tmp_path: Path) -> None:
        """Test that both AGENTS.md and CLAUDE.md are created."""
        generate_instruction_files(tmp_path, force=False)

        agents_file = tmp_path / "AGENTS.md"
        claude_file = tmp_path / "CLAUDE.md"

        assert agents_file.exists()
        assert claude_file.exists()
        assert len(agents_file.read_text()) > 0
        assert len(claude_file.read_text()) > 0

    def test_skips_existing_files_without_force(self, tmp_path: Path) -> None:
        """Test that existing files are not overwritten without force flag."""
        # Create initial files
        agents_file = tmp_path / "AGENTS.md"
        claude_file = tmp_path / "CLAUDE.md"

        agents_file.write_text("Original AGENTS content")
        claude_file.write_text("Original CLAUDE content")

        # Generate without force
        generate_instruction_files(tmp_path, force=False)

        # Files should still have original content
        assert agents_file.read_text() == "Original AGENTS content"
        assert claude_file.read_text() == "Original CLAUDE content"

    def test_overwrites_with_force_flag(self, tmp_path: Path) -> None:
        """Test that files are overwritten with force=True."""
        # Create initial files
        agents_file = tmp_path / "AGENTS.md"
        claude_file = tmp_path / "CLAUDE.md"

        agents_file.write_text("Original AGENTS content")
        claude_file.write_text("Original CLAUDE content")

        # Generate with force
        generate_instruction_files(tmp_path, force=True)

        # Files should have new content
        assert agents_file.read_text() != "Original AGENTS content"
        assert claude_file.read_text() != "Original CLAUDE content"
        assert "# Agent Instructions" in agents_file.read_text()
        assert "# Claude Code Instructions" in claude_file.read_text()

    def test_handles_missing_config_gracefully(self, tmp_path: Path) -> None:
        """Test that generation works even without existing config."""
        # Should not raise exception
        generate_instruction_files(tmp_path, force=False)

        # Files should still be created
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()

    def test_creates_valid_markdown_files(self, tmp_path: Path) -> None:
        """Test that generated files contain valid markdown."""
        generate_instruction_files(tmp_path, force=False)

        agents_content = (tmp_path / "AGENTS.md").read_text()
        claude_content = (tmp_path / "CLAUDE.md").read_text()

        # Check for markdown headers
        assert agents_content.startswith("# Agent Instructions")
        assert claude_content.startswith("# Claude Code Instructions")

        # Check for key sections
        assert "## Project Context" in agents_content
        assert "## Core Workflow" in claude_content

    def test_includes_project_specific_info(self, tmp_path: Path) -> None:
        """Test that generated files include project-specific information."""
        project_dir = tmp_path / "my-test-project"
        project_dir.mkdir()

        generate_instruction_files(project_dir, force=False)

        agents_content = (project_dir / "AGENTS.md").read_text()
        claude_content = (project_dir / "CLAUDE.md").read_text()

        # Should include project name
        assert "my-test-project" in agents_content
        assert "my-test-project" in claude_content
