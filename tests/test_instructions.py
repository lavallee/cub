"""
Tests for instruction file generation module.
"""

from pathlib import Path

from cub.core.config.models import CircuitBreakerConfig, CubConfig
from cub.core.instructions import (
    ESCAPE_HATCH_SECTION,
    generate_agents_md,
    generate_claude_md,
)


class TestGenerateAgentsMd:
    """Tests for generate_agents_md function."""

    def test_generates_valid_markdown(self, tmp_path: Path) -> None:
        """Test that generated AGENTS.md is valid markdown."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should be non-empty string
        assert isinstance(content, str)
        assert len(content) > 0

        # Should start with markdown header
        assert content.startswith("# Agent Instructions")

    def test_includes_project_name(self, tmp_path: Path) -> None:
        """Test that project name is included in output."""
        project_dir = tmp_path / "my-awesome-project"
        project_dir.mkdir()
        config = CubConfig()

        content = generate_agents_md(project_dir, config)

        assert "my-awesome-project" in content

    def test_includes_circuit_breaker_timeout(self, tmp_path: Path) -> None:
        """Test that circuit breaker timeout is included."""
        config = CubConfig(circuit_breaker=CircuitBreakerConfig(timeout_minutes=45))

        content = generate_agents_md(tmp_path, config)

        assert "45-minute timeout" in content

    def test_includes_task_management_workflow(self, tmp_path: Path) -> None:
        """Test that task management commands are documented."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should include bd commands
        assert "bd ready" in content
        assert "bd list --status open" in content
        assert "bd update" in content
        assert "bd close" in content
        assert "bd show" in content

        # Should include cub commands
        assert "cub status" in content
        assert "cub log" in content

    def test_includes_workflow_steps(self, tmp_path: Path) -> None:
        """Test that workflow steps are clearly documented."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should include the workflow steps
        assert "Find Available Tasks" in content
        assert "Claim a Task" in content
        assert "Do the Work" in content
        assert "Complete the Task" in content

    def test_includes_escape_hatch_section(self, tmp_path: Path) -> None:
        """Test that escape hatch language is included."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should include the escape hatch section
        assert "Escape Hatch: Signal When Stuck" in content
        assert "<stuck>" in content
        assert "genuinely blocked" in content

    def test_includes_examples(self, tmp_path: Path) -> None:
        """Test that concrete examples are provided."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should include example commands with placeholders
        assert "cub-abc.1" in content or "<task-id>" in content
        assert "bd close" in content
        assert "bd update" in content

    def test_includes_commands_reference(self, tmp_path: Path) -> None:
        """Test that a commands reference section exists."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should have a commands reference section
        assert "Commands Reference" in content or "Task Management" in content

    def test_uses_config_circuit_breaker_default(self, tmp_path: Path) -> None:
        """Test that default circuit breaker timeout is used."""
        config = CubConfig()  # Uses default timeout_minutes=30
        content = generate_agents_md(tmp_path, config)

        assert "30-minute timeout" in content

    def test_escape_hatch_section_standalone(self) -> None:
        """Test that ESCAPE_HATCH_SECTION constant is properly formatted."""
        # Should be a markdown section header
        assert ESCAPE_HATCH_SECTION.startswith("##")
        assert "Escape Hatch" in ESCAPE_HATCH_SECTION
        assert "<stuck>" in ESCAPE_HATCH_SECTION


class TestGenerateClaudeMd:
    """Tests for generate_claude_md function."""

    def test_generates_valid_markdown(self, tmp_path: Path) -> None:
        """Test that generated CLAUDE.md is valid markdown."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should be non-empty string
        assert isinstance(content, str)
        assert len(content) > 0

        # Should start with markdown header
        assert content.startswith("# Claude Code Instructions")

    def test_includes_project_name(self, tmp_path: Path) -> None:
        """Test that project name is included in output."""
        project_dir = tmp_path / "my-claude-project"
        project_dir.mkdir()
        config = CubConfig()

        content = generate_claude_md(project_dir, config)

        assert "my-claude-project" in content

    def test_references_agents_md(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md references AGENTS.md for core workflow."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should reference AGENTS.md
        assert "AGENTS.md" in content
        assert "See AGENTS.md" in content or "Read AGENTS.md" in content

    def test_includes_plan_mode_instructions(self, tmp_path: Path) -> None:
        """Test that plan mode integration is documented."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should include plan mode guidance
        assert "plan mode" in content.lower()
        assert "plans/" in content
        assert "plan.md" in content

    def test_includes_plan_file_format_example(self, tmp_path: Path) -> None:
        """Test that plan file format example is provided."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should include plan structure guidance
        assert "Summary" in content
        assert "Approach" in content
        assert "Steps" in content

    def test_includes_claude_best_practices(self, tmp_path: Path) -> None:
        """Test that Claude Code-specific best practices are included."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should have best practices section
        assert "Best Practices" in content or "Before Starting Work" in content

    def test_includes_reference_to_agent_md(self, tmp_path: Path) -> None:
        """Test that AGENT.md is referenced for build instructions."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should reference AGENT.md (build/test instructions)
        assert "AGENT.md" in content

    def test_shorter_than_agents_md(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md is shorter since it references AGENTS.md."""
        config = CubConfig()
        agents_content = generate_agents_md(tmp_path, config)
        claude_content = generate_claude_md(tmp_path, config)

        # CLAUDE.md should be shorter since it delegates to AGENTS.md
        assert len(claude_content) < len(agents_content)

    def test_includes_escape_hatch_reference(self, tmp_path: Path) -> None:
        """Test that escape hatch is mentioned (via AGENTS.md reference)."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should mention the escape hatch (either directly or via reference)
        assert "stuck" in content.lower() or "AGENTS.md" in content


class TestInstructionIntegration:
    """Integration tests for instruction generation."""

    def test_both_files_can_be_written(self, tmp_path: Path) -> None:
        """Test that both instruction files can be written to disk."""
        config = CubConfig()

        # Generate and write both files
        agents_content = generate_agents_md(tmp_path, config)
        claude_content = generate_claude_md(tmp_path, config)

        agents_file = tmp_path / "AGENTS.md"
        claude_file = tmp_path / "CLAUDE.md"

        agents_file.write_text(agents_content)
        claude_file.write_text(claude_content)

        # Verify files exist and are readable
        assert agents_file.exists()
        assert claude_file.exists()
        assert len(agents_file.read_text()) > 0
        assert len(claude_file.read_text()) > 0

    def test_generated_files_are_different(self, tmp_path: Path) -> None:
        """Test that AGENTS.md and CLAUDE.md have different content."""
        config = CubConfig()

        agents_content = generate_agents_md(tmp_path, config)
        claude_content = generate_claude_md(tmp_path, config)

        # Files should have different content
        assert agents_content != claude_content

    def test_consistent_workflow_between_files(self, tmp_path: Path) -> None:
        """Test that both files mention the same core commands."""
        config = CubConfig()

        agents_content = generate_agents_md(tmp_path, config)
        claude_content = generate_claude_md(tmp_path, config)

        # Both should reference core commands
        core_commands = ["bd ready", "bd close", "bd update", "cub status"]

        for cmd in core_commands:
            # AGENTS.md should have all commands
            assert cmd in agents_content

            # CLAUDE.md should at least reference AGENTS.md which has them
            # (or include them directly)
            assert cmd in claude_content or "AGENTS.md" in claude_content

    def test_agents_md_is_self_contained(self, tmp_path: Path) -> None:
        """Test that AGENTS.md is self-contained (no external references required)."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should have complete workflow without requiring other files
        # (though it may reference AGENT.md for build instructions)
        assert "bd ready" in content
        assert "bd close" in content
        assert "Escape Hatch" in content
        assert "Workflow Summary" in content or "Commands Reference" in content

    def test_claude_md_references_external_docs(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md appropriately references external documentation."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should reference other documentation files
        assert "AGENTS.md" in content
        assert "AGENT.md" in content

    def test_custom_circuit_breaker_timeout_propagates(self, tmp_path: Path) -> None:
        """Test that custom circuit breaker timeout appears in AGENTS.md."""
        config = CubConfig(circuit_breaker=CircuitBreakerConfig(timeout_minutes=60))

        content = generate_agents_md(tmp_path, config)

        assert "60-minute timeout" in content
        assert "30-minute timeout" not in content
