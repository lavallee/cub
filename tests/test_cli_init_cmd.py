"""
Tests for CLI init_cmd module.
"""

from pathlib import Path

from cub.cli.init_cmd import generate_instruction_files


class TestGenerateInstructionFiles:
    """Tests for generate_instruction_files function."""

    def test_creates_both_files(self, tmp_path: Path) -> None:
        """Test that both AGENTS.md and CLAUDE.md are created."""
        generate_instruction_files(tmp_path, force=False)

        agents_file = tmp_path / "AGENTS.md"
        claude_file = tmp_path / "CLAUDE.md"
        constitution_file = tmp_path / ".cub" / "constitution.md"
        runloop_file = tmp_path / ".cub" / "runloop.md"

        assert agents_file.exists()
        assert claude_file.exists()
        assert constitution_file.exists()
        assert runloop_file.exists()
        assert len(agents_file.read_text()) > 0
        assert len(claude_file.read_text()) > 0

        # Check for managed section markers
        agents_content = agents_file.read_text()
        claude_content = claude_file.read_text()
        assert "<!-- BEGIN CUB MANAGED SECTION" in agents_content
        assert "<!-- END CUB MANAGED SECTION" in claude_content

    def test_skips_existing_files_without_force(self, tmp_path: Path) -> None:
        """Test that managed sections are appended to existing files."""
        # Create initial files with user content
        agents_file = tmp_path / "AGENTS.md"
        claude_file = tmp_path / "CLAUDE.md"

        agents_file.write_text("Original AGENTS content\n")
        claude_file.write_text("Original CLAUDE content\n")

        # Generate without force - should APPEND managed section
        generate_instruction_files(tmp_path, force=False)

        # Files should have both original content AND managed section
        agents_content = agents_file.read_text()
        claude_content = claude_file.read_text()

        assert "Original AGENTS content" in agents_content
        assert "Original CLAUDE content" in claude_content
        assert "<!-- BEGIN CUB MANAGED SECTION" in agents_content
        assert "<!-- BEGIN CUB MANAGED SECTION" in claude_content

    def test_overwrites_with_force_flag(self, tmp_path: Path) -> None:
        """Test that constitution and runloop are overwritten with force=True."""
        # Create initial constitution and runloop
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        constitution_file = cub_dir / "constitution.md"
        runloop_file = cub_dir / "runloop.md"

        constitution_file.write_text("Original constitution")
        runloop_file.write_text("Original runloop")

        # Generate with force
        generate_instruction_files(tmp_path, force=True)

        # Constitution and runloop should be overwritten
        assert constitution_file.read_text() != "Original constitution"
        assert runloop_file.read_text() != "Original runloop"
        assert len(constitution_file.read_text()) > 100
        assert len(runloop_file.read_text()) > 100

    def test_handles_missing_config_gracefully(self, tmp_path: Path) -> None:
        """Test that generation works even without existing config."""
        # Should not raise exception
        generate_instruction_files(tmp_path, force=False)

        # Files should still be created
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()

    def test_creates_valid_markdown_files(self, tmp_path: Path) -> None:
        """Test that generated files contain valid markdown with managed sections."""
        generate_instruction_files(tmp_path, force=False)

        agents_content = (tmp_path / "AGENTS.md").read_text()
        claude_content = (tmp_path / "CLAUDE.md").read_text()

        # Check for managed section markers
        assert "<!-- BEGIN CUB MANAGED SECTION" in agents_content
        assert "<!-- END CUB MANAGED SECTION" in agents_content
        assert "<!-- BEGIN CUB MANAGED SECTION" in claude_content
        assert "<!-- END CUB MANAGED SECTION" in claude_content

        # Check for key content (using actual content from managed sections)
        assert "**Context:**" in agents_content or "context" in agents_content.lower()
        assert "workflow" in claude_content.lower()

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
