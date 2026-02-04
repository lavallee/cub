"""
Tests for instruction file generation module.
"""

import hashlib
from pathlib import Path

from cub.core.config.models import CubConfig
from cub.core.instructions import (
    ESCAPE_HATCH_SECTION,
    SectionInfo,
    UpsertAction,
    UpsertResult,
    _content_hash,
    _format_managed_block,
    create_agents_symlink,
    detect_managed_section,
    generate_agents_md,
    generate_claude_md,
    generate_managed_section,
    upsert_managed_section,
)


class TestGenerateManagedSection:
    """Tests for generate_managed_section function."""

    def test_generic_harness_generates_valid_content(self, tmp_path: Path) -> None:
        """Test that generic harness generates valid markdown content."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="generic")

        # Should be non-empty string
        assert isinstance(content, str)
        assert len(content) > 0

        # Should start with markdown header (now uses Claude Code branding for all)
        assert content.startswith("# Cub Task Workflow (Claude Code)")

    def test_claude_harness_generates_valid_content(self, tmp_path: Path) -> None:
        """Test that claude harness generates valid markdown content."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="claude")

        # Should be non-empty string
        assert isinstance(content, str)
        assert len(content) > 0

        # Should start with markdown header
        assert content.startswith("# Cub Task Workflow (Claude Code)")

    def test_includes_project_name(self, tmp_path: Path) -> None:
        """Test that project name is included in output."""
        project_dir = tmp_path / "my-awesome-project"
        project_dir.mkdir()
        config = CubConfig()

        content = generate_managed_section(project_dir, config, harness="generic")

        assert "my-awesome-project" in content

    def test_includes_map_reference(self, tmp_path: Path) -> None:
        """Test that content references @.cub/map.md."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="generic")

        assert "@.cub/map.md" in content

    def test_includes_constitution_reference(self, tmp_path: Path) -> None:
        """Test that content references @.cub/constitution.md."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="generic")

        assert "@.cub/constitution.md" in content

    def test_includes_agent_md_reference(self, tmp_path: Path) -> None:
        """Test that content references @.cub/agent.md."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="generic")

        assert "@.cub/agent.md" in content

    def test_includes_task_workflow(self, tmp_path: Path) -> None:
        """Test that condensed task workflow is included."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="generic")

        # Should include workflow steps
        assert "cub task ready" in content
        assert "cub task claim" in content
        assert "cub task close" in content

    def test_includes_escape_hatch_summary(self, tmp_path: Path) -> None:
        """Test that escape hatch summary is included."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="generic")

        assert "<stuck>" in content
        assert "When Stuck" in content

    def test_generic_is_condensed(self, tmp_path: Path) -> None:
        """Test that generic content is condensed (~15-20 lines)."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="generic")

        # Count lines (excluding empty lines for better measurement)
        lines = [line for line in content.splitlines() if line.strip()]
        # Should be around 15-25 lines
        assert 10 <= len(lines) <= 30, f"Expected 10-30 lines, got {len(lines)}"

    def test_claude_includes_plan_mode_tip(self, tmp_path: Path) -> None:
        """Test that Claude-specific content includes plan mode tip."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="claude")

        assert "plan mode" in content.lower() or "Plan mode" in content

    def test_claude_includes_skills_reference(self, tmp_path: Path) -> None:
        """Test that Claude-specific content mentions skills."""
        config = CubConfig()
        content = generate_managed_section(tmp_path, config, harness="claude")

        assert "skill" in content.lower() or "/commit" in content

    def test_both_harness_types_return_same_content(self, tmp_path: Path) -> None:
        """Test that both harness types return identical content.

        As of cub 1.x, both harness types return the same Claude Code content
        since AGENTS.md is a symlink to CLAUDE.md.
        """
        config = CubConfig()
        generic = generate_managed_section(tmp_path, config, harness="generic")
        claude = generate_managed_section(tmp_path, config, harness="claude")

        # Both should be identical now
        assert generic == claude

    def test_invalid_harness_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid harness type raises ValueError."""
        config = CubConfig()

        try:
            generate_managed_section(tmp_path, config, harness="invalid")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown harness type" in str(e)


class TestGenerateAgentsMd:
    """Tests for generate_agents_md function (deprecated, returns same as claude)."""

    def test_generates_valid_markdown(self, tmp_path: Path) -> None:
        """Test that generated AGENTS.md is valid markdown."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should be non-empty string
        assert isinstance(content, str)
        assert len(content) > 0

        # Should start with markdown header (now uses Claude Code branding)
        assert content.startswith("# Cub Task Workflow (Claude Code)")

    def test_includes_project_name(self, tmp_path: Path) -> None:
        """Test that project name is included in output."""
        project_dir = tmp_path / "my-awesome-project"
        project_dir.mkdir()
        config = CubConfig()

        content = generate_agents_md(project_dir, config)

        assert "my-awesome-project" in content

    def test_includes_task_management_workflow(self, tmp_path: Path) -> None:
        """Test that task management commands are documented."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should include cub task commands
        assert "cub task ready" in content
        assert "cub task list --status open" in content
        assert "cub task claim" in content
        assert "cub task close" in content
        assert "cub task show" in content

        # Should include other cub commands
        assert "cub status" in content
        assert "cub log" in content

    def test_includes_escape_hatch_section(self, tmp_path: Path) -> None:
        """Test that escape hatch language is included."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should include the escape hatch section
        assert "<stuck>" in content
        assert "When Stuck" in content or "stuck" in content.lower()

    def test_includes_map_and_constitution_references(self, tmp_path: Path) -> None:
        """Test that content references map and constitution files."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should reference external context files
        assert "@.cub/map.md" in content
        assert "@.cub/constitution.md" in content

    def test_includes_agent_md_reference(self, tmp_path: Path) -> None:
        """Test that content references agent.md for build/test instructions."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should reference agent.md
        assert "@.cub/agent.md" in content

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
        assert content.startswith("# Cub Task Workflow (Claude Code)")

    def test_includes_project_name(self, tmp_path: Path) -> None:
        """Test that project name is included in output."""
        project_dir = tmp_path / "my-claude-project"
        project_dir.mkdir()
        config = CubConfig()

        content = generate_claude_md(project_dir, config)

        assert "my-claude-project" in content

    def test_includes_plan_mode_instructions(self, tmp_path: Path) -> None:
        """Test that plan mode integration is documented."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should include plan mode guidance
        assert "plan mode" in content.lower() or "Plan mode" in content

    def test_includes_skills_reference(self, tmp_path: Path) -> None:
        """Test that skills are mentioned."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should mention skills
        assert "skill" in content.lower() or "/commit" in content

    def test_includes_reference_to_agent_md(self, tmp_path: Path) -> None:
        """Test that .cub/agent.md is referenced for build instructions."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should reference .cub/agent.md (build/test instructions)
        assert "@.cub/agent.md" in content

    def test_includes_map_and_constitution_references(self, tmp_path: Path) -> None:
        """Test that content references map and constitution files."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should reference external context files
        assert "@.cub/map.md" in content
        assert "@.cub/constitution.md" in content

    def test_includes_escape_hatch_reference(self, tmp_path: Path) -> None:
        """Test that escape hatch is mentioned."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should mention the escape hatch
        assert "<stuck>" in content


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

    def test_generated_files_are_identical(self, tmp_path: Path) -> None:
        """Test that generate_agents_md and generate_claude_md return same content.

        As of cub 1.x, AGENTS.md is a symlink to CLAUDE.md, so both functions
        return identical content.
        """
        config = CubConfig()

        agents_content = generate_agents_md(tmp_path, config)
        claude_content = generate_claude_md(tmp_path, config)

        # Both functions now return identical content
        assert agents_content == claude_content

    def test_consistent_workflow_between_files(self, tmp_path: Path) -> None:
        """Test that both files mention the same core commands."""
        config = CubConfig()

        agents_content = generate_agents_md(tmp_path, config)
        claude_content = generate_claude_md(tmp_path, config)

        # Both should reference core commands
        core_commands = ["cub task ready", "cub task close", "cub task claim", "cub status"]

        for cmd in core_commands:
            # Both should have all commands
            assert cmd in agents_content
            assert cmd in claude_content

    def test_agents_md_references_context_files(self, tmp_path: Path) -> None:
        """Test that AGENTS.md references external context files."""
        config = CubConfig()
        content = generate_agents_md(tmp_path, config)

        # Should reference external context files
        assert "@.cub/map.md" in content
        assert "@.cub/constitution.md" in content
        assert "@.cub/agent.md" in content

    def test_claude_md_references_external_docs(self, tmp_path: Path) -> None:
        """Test that CLAUDE.md appropriately references external documentation."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should reference context files
        assert "@.cub/map.md" in content
        assert "@.cub/constitution.md" in content
        assert "@.cub/agent.md" in content

    def test_both_are_condensed(self, tmp_path: Path) -> None:
        """Test that both generated files are condensed (~15-25 lines)."""
        config = CubConfig()

        agents_content = generate_agents_md(tmp_path, config)
        claude_content = generate_claude_md(tmp_path, config)

        # Count non-empty lines
        agents_lines = [line for line in agents_content.splitlines() if line.strip()]
        claude_lines = [line for line in claude_content.splitlines() if line.strip()]

        # Both should be condensed
        assert 10 <= len(agents_lines) <= 30, f"AGENTS.md has {len(agents_lines)} lines"
        assert 10 <= len(claude_lines) <= 35, f"CLAUDE.md has {len(claude_lines)} lines"


class TestContentHash:
    """Tests for the _content_hash helper."""

    def test_returns_sha256_hex(self) -> None:
        """Test that _content_hash returns a valid sha256 hex digest."""
        h = _content_hash("hello world")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self) -> None:
        """Test that the same input always produces the same hash."""
        assert _content_hash("test") == _content_hash("test")

    def test_different_inputs_different_hashes(self) -> None:
        """Test that different inputs produce different hashes."""
        assert _content_hash("foo") != _content_hash("bar")

    def test_matches_hashlib_directly(self) -> None:
        """Test that _content_hash matches hashlib.sha256 directly."""
        text = "some content to hash"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert _content_hash(text) == expected


class TestFormatManagedBlock:
    """Tests for _format_managed_block helper."""

    def test_includes_begin_marker_with_version(self) -> None:
        """Test that the block starts with a versioned begin marker."""
        block = _format_managed_block("content", version=1)
        assert block.startswith("<!-- BEGIN CUB MANAGED SECTION v1 -->")

    def test_includes_end_marker(self) -> None:
        """Test that the block ends with the end marker."""
        block = _format_managed_block("content", version=1)
        assert block.endswith("<!-- END CUB MANAGED SECTION -->")

    def test_includes_hash_line(self) -> None:
        """Test that the block includes a sha256 hash comment."""
        block = _format_managed_block("content", version=2)
        h = _content_hash("content")
        assert f"<!-- sha256:{h} -->" in block

    def test_includes_content(self) -> None:
        """Test that the block includes the provided content."""
        block = _format_managed_block("my managed content", version=1)
        assert "my managed content" in block

    def test_strips_content(self) -> None:
        """Test that content is stripped of leading/trailing whitespace."""
        block = _format_managed_block("  padded  \n", version=1)
        # Content should be stripped, hash should be of stripped content
        h = _content_hash("padded")
        assert f"<!-- sha256:{h} -->" in block
        assert "\n  padded  \n" not in block

    def test_version_in_marker(self) -> None:
        """Test that version number is in the begin marker."""
        block = _format_managed_block("x", version=42)
        assert "<!-- BEGIN CUB MANAGED SECTION v42 -->" in block


class TestSectionInfoModel:
    """Tests for the SectionInfo Pydantic model."""

    def test_default_values(self) -> None:
        """Test that SectionInfo has sensible defaults."""
        info = SectionInfo()
        assert info.found is False
        assert info.version is None
        assert info.start_line is None
        assert info.end_line is None
        assert info.content_hash is None
        assert info.actual_hash is None
        assert info.has_begin is False
        assert info.has_end is False
        assert info.content_modified is False

    def test_full_construction(self) -> None:
        """Test constructing a SectionInfo with all fields."""
        info = SectionInfo(
            found=True,
            version=2,
            start_line=5,
            end_line=10,
            content_hash="abc123",
            actual_hash="def456",
            has_begin=True,
            has_end=True,
            content_modified=True,
        )
        assert info.found is True
        assert info.version == 2
        assert info.start_line == 5
        assert info.end_line == 10
        assert info.content_modified is True


class TestUpsertResultModel:
    """Tests for the UpsertResult Pydantic model."""

    def test_minimal_construction(self, tmp_path: Path) -> None:
        """Test creating UpsertResult with minimal fields."""
        result = UpsertResult(
            action=UpsertAction.CREATED,
            file_path=tmp_path / "test.md",
            version=1,
            content_hash="abc123",
        )
        assert result.action == UpsertAction.CREATED
        assert result.previous_hash is None
        assert result.content_was_modified is False
        assert result.warnings == []

    def test_action_enum_values(self) -> None:
        """Test that UpsertAction enum has expected values."""
        assert UpsertAction.CREATED == "created"
        assert UpsertAction.APPENDED == "appended"
        assert UpsertAction.REPLACED == "replaced"


class TestDetectManagedSection:
    """Tests for detect_managed_section function."""

    def test_file_not_exists(self, tmp_path: Path) -> None:
        """Test detection on a nonexistent file returns empty SectionInfo."""
        info = detect_managed_section(tmp_path / "nonexistent.md")
        assert info.found is False
        assert info.has_begin is False
        assert info.has_end is False

    def test_empty_file(self, tmp_path: Path) -> None:
        """Test detection on an empty file returns empty SectionInfo."""
        f = tmp_path / "empty.md"
        f.write_text("")
        info = detect_managed_section(f)
        assert info.found is False

    def test_file_without_markers(self, tmp_path: Path) -> None:
        """Test detection on a file with no markers."""
        f = tmp_path / "plain.md"
        f.write_text("# My Project\n\nSome content here.\n")
        info = detect_managed_section(f)
        assert info.found is False
        assert info.has_begin is False
        assert info.has_end is False

    def test_complete_section(self, tmp_path: Path) -> None:
        """Test detection of a complete managed section."""
        content = "managed content here"
        h = _content_hash(content)
        f = tmp_path / "test.md"
        f.write_text(
            f"# Header\n\n"
            f"<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            f"<!-- sha256:{h} -->\n"
            f"{content}\n"
            f"<!-- END CUB MANAGED SECTION -->\n"
        )
        info = detect_managed_section(f)
        assert info.found is True
        assert info.version == 1
        assert info.start_line == 2
        assert info.end_line == 5
        assert info.content_hash == h
        assert info.actual_hash == h
        assert info.content_modified is False
        assert info.has_begin is True
        assert info.has_end is True

    def test_version_extraction(self, tmp_path: Path) -> None:
        """Test that version is correctly extracted from marker."""
        f = tmp_path / "test.md"
        f.write_text(
            "<!-- BEGIN CUB MANAGED SECTION v42 -->\n"
            "<!-- sha256:0000000000000000000000000000000000000000000000000000000000000000 -->\n"
            "stuff\n"
            "<!-- END CUB MANAGED SECTION -->\n"
        )
        info = detect_managed_section(f)
        assert info.version == 42

    def test_tampered_content_detected(self, tmp_path: Path) -> None:
        """Test that manually edited content is detected via hash mismatch."""
        original = "original content"
        h = _content_hash(original)
        f = tmp_path / "test.md"
        f.write_text(
            f"<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            f"<!-- sha256:{h} -->\n"
            f"tampered content that was manually edited\n"
            f"<!-- END CUB MANAGED SECTION -->\n"
        )
        info = detect_managed_section(f)
        assert info.found is True
        assert info.content_modified is True
        assert info.content_hash == h
        assert info.actual_hash != h

    def test_begin_without_end(self, tmp_path: Path) -> None:
        """Test detection with begin marker but no end marker."""
        f = tmp_path / "test.md"
        f.write_text(
            "# Header\n"
            "<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            "<!-- sha256:abc -->\n"
            "orphaned content\n"
        )
        info = detect_managed_section(f)
        assert info.found is False
        assert info.has_begin is True
        assert info.has_end is False
        assert info.version == 1

    def test_end_without_begin(self, tmp_path: Path) -> None:
        """Test detection with end marker but no begin marker."""
        f = tmp_path / "test.md"
        f.write_text(
            "# Header\n"
            "some content\n"
            "<!-- END CUB MANAGED SECTION -->\n"
        )
        info = detect_managed_section(f)
        assert info.found is False
        assert info.has_begin is False
        assert info.has_end is True

    def test_section_with_multiline_content(self, tmp_path: Path) -> None:
        """Test detection with multi-line managed content."""
        content = "line one\nline two\nline three"
        h = _content_hash(content)
        f = tmp_path / "test.md"
        f.write_text(
            f"<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            f"<!-- sha256:{h} -->\n"
            f"{content}\n"
            f"<!-- END CUB MANAGED SECTION -->\n"
        )
        info = detect_managed_section(f)
        assert info.found is True
        assert info.content_modified is False

    def test_section_with_surrounding_content(self, tmp_path: Path) -> None:
        """Test detection with user content before and after section."""
        content = "managed"
        h = _content_hash(content)
        f = tmp_path / "test.md"
        f.write_text(
            "# My Project\n\nUser content above.\n\n"
            f"<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            f"<!-- sha256:{h} -->\n"
            f"{content}\n"
            f"<!-- END CUB MANAGED SECTION -->\n\n"
            "User content below.\n"
        )
        info = detect_managed_section(f)
        assert info.found is True
        assert info.start_line == 4
        assert info.end_line == 7
        assert info.content_modified is False


class TestUpsertManagedSection:
    """Tests for upsert_managed_section function."""

    def test_create_new_file(self, tmp_path: Path) -> None:
        """Test creating a managed section in a new file."""
        f = tmp_path / "NEW.md"
        result = upsert_managed_section(f, "new content", version=1)

        assert result.action == UpsertAction.CREATED
        assert f.exists()
        text = f.read_text()
        assert "<!-- BEGIN CUB MANAGED SECTION v1 -->" in text
        assert "<!-- END CUB MANAGED SECTION -->" in text
        assert "new content" in text
        assert result.content_hash == _content_hash("new content")

    def test_create_in_subdirectory(self, tmp_path: Path) -> None:
        """Test creating a file in a non-existent subdirectory."""
        f = tmp_path / "sub" / "dir" / "NEW.md"
        result = upsert_managed_section(f, "content", version=1)

        assert result.action == UpsertAction.CREATED
        assert f.exists()

    def test_append_to_existing_file_no_markers(self, tmp_path: Path) -> None:
        """Test appending managed section to existing file without markers."""
        f = tmp_path / "EXISTING.md"
        f.write_text("# My Project\n\nExisting user content.\n")

        result = upsert_managed_section(f, "managed content", version=1)

        assert result.action == UpsertAction.APPENDED
        text = f.read_text()
        # User content preserved
        assert "# My Project" in text
        assert "Existing user content." in text
        # Managed section appended
        assert "<!-- BEGIN CUB MANAGED SECTION v1 -->" in text
        assert "managed content" in text
        assert "<!-- END CUB MANAGED SECTION -->" in text

    def test_append_to_empty_file(self, tmp_path: Path) -> None:
        """Test appending managed section to an empty file."""
        f = tmp_path / "EMPTY.md"
        f.write_text("")

        result = upsert_managed_section(f, "managed content", version=1)

        assert result.action == UpsertAction.APPENDED
        text = f.read_text()
        assert "<!-- BEGIN CUB MANAGED SECTION v1 -->" in text
        assert "managed content" in text

    def test_replace_existing_section(self, tmp_path: Path) -> None:
        """Test replacing content in an existing managed section."""
        old_content = "old content"
        old_hash = _content_hash(old_content)
        f = tmp_path / "test.md"
        f.write_text(
            f"# Header\n\n"
            f"<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            f"<!-- sha256:{old_hash} -->\n"
            f"{old_content}\n"
            f"<!-- END CUB MANAGED SECTION -->\n\n"
            f"Footer content.\n"
        )

        result = upsert_managed_section(f, "new content", version=2)

        assert result.action == UpsertAction.REPLACED
        assert result.version == 2
        assert result.previous_hash == old_hash
        text = f.read_text()
        assert "# Header" in text
        assert "Footer content." in text
        assert "old content" not in text
        assert "new content" in text
        assert "<!-- BEGIN CUB MANAGED SECTION v2 -->" in text

    def test_replace_preserves_surrounding_content(self, tmp_path: Path) -> None:
        """Test that replacing preserves user content before and after."""
        content = "managed"
        h = _content_hash(content)
        f = tmp_path / "test.md"
        f.write_text(
            "# Title\n\nParagraph one.\n\n"
            f"<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            f"<!-- sha256:{h} -->\n"
            f"{content}\n"
            f"<!-- END CUB MANAGED SECTION -->\n\n"
            "## Footer Section\n\nParagraph two.\n"
        )

        upsert_managed_section(f, "updated managed", version=2)

        text = f.read_text()
        assert "# Title" in text
        assert "Paragraph one." in text
        assert "## Footer Section" in text
        assert "Paragraph two." in text
        assert "updated managed" in text
        assert "managed" not in text or "updated managed" in text

    def test_replace_tampered_section_warns(self, tmp_path: Path) -> None:
        """Test that replacing a tampered section produces a warning."""
        original = "original content"
        h = _content_hash(original)
        f = tmp_path / "test.md"
        f.write_text(
            f"<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            f"<!-- sha256:{h} -->\n"
            f"manually edited content\n"
            f"<!-- END CUB MANAGED SECTION -->\n"
        )

        result = upsert_managed_section(f, "fresh content", version=1)

        assert result.action == UpsertAction.REPLACED
        assert result.content_was_modified is True
        assert len(result.warnings) > 0
        assert "manually edited" in result.warnings[0] or "hash mismatch" in result.warnings[0]

    def test_begin_without_end_recovery(self, tmp_path: Path) -> None:
        """Test error recovery when begin marker exists without end."""
        f = tmp_path / "test.md"
        f.write_text(
            "# Header\n"
            "<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            "<!-- sha256:abc -->\n"
            "orphaned content\n"
        )

        result = upsert_managed_section(f, "fixed content", version=1)

        assert result.action == UpsertAction.REPLACED
        assert len(result.warnings) > 0
        text = f.read_text()
        assert "# Header" in text
        assert "fixed content" in text
        assert "<!-- BEGIN CUB MANAGED SECTION v1 -->" in text
        assert "<!-- END CUB MANAGED SECTION -->" in text
        assert "orphaned content" not in text

    def test_end_without_begin_recovery(self, tmp_path: Path) -> None:
        """Test error recovery when end marker exists without begin."""
        f = tmp_path / "test.md"
        f.write_text(
            "orphaned content\n"
            "<!-- END CUB MANAGED SECTION -->\n"
            "# Footer\n"
        )

        result = upsert_managed_section(f, "fixed content", version=1)

        assert result.action == UpsertAction.REPLACED
        assert len(result.warnings) > 0
        text = f.read_text()
        assert "# Footer" in text
        assert "fixed content" in text
        assert "<!-- BEGIN CUB MANAGED SECTION v1 -->" in text
        assert "<!-- END CUB MANAGED SECTION -->" in text
        assert "orphaned content" not in text

    def test_version_upgrade(self, tmp_path: Path) -> None:
        """Test upgrading from v1 to v2 managed section."""
        content = "v1 content"
        h = _content_hash(content)
        f = tmp_path / "test.md"
        f.write_text(
            f"<!-- BEGIN CUB MANAGED SECTION v1 -->\n"
            f"<!-- sha256:{h} -->\n"
            f"{content}\n"
            f"<!-- END CUB MANAGED SECTION -->\n"
        )

        result = upsert_managed_section(f, "v2 content", version=2)

        assert result.action == UpsertAction.REPLACED
        assert result.version == 2
        text = f.read_text()
        assert "<!-- BEGIN CUB MANAGED SECTION v2 -->" in text
        assert "v1" not in text or "v2" in text
        assert "v2 content" in text

    def test_idempotent_upsert(self, tmp_path: Path) -> None:
        """Test that upserting the same content twice is idempotent."""
        f = tmp_path / "test.md"
        content = "stable content"

        result1 = upsert_managed_section(f, content, version=1)
        text1 = f.read_text()

        result2 = upsert_managed_section(f, content, version=1)
        text2 = f.read_text()

        assert result1.action == UpsertAction.CREATED
        assert result2.action == UpsertAction.REPLACED
        assert result1.content_hash == result2.content_hash
        # Content should be the same after both upserts
        assert text1 == text2

    def test_file_ends_with_newline(self, tmp_path: Path) -> None:
        """Test that output files always end with a newline."""
        f = tmp_path / "test.md"

        # Create
        upsert_managed_section(f, "content", version=1)
        assert f.read_text().endswith("\n")

        # Replace
        upsert_managed_section(f, "updated", version=1)
        assert f.read_text().endswith("\n")

    def test_roundtrip_detect_after_upsert(self, tmp_path: Path) -> None:
        """Test that detect_managed_section works on upserted content."""
        f = tmp_path / "test.md"
        content = "roundtrip test content"

        upsert_managed_section(f, content, version=3)

        info = detect_managed_section(f)
        assert info.found is True
        assert info.version == 3
        assert info.content_modified is False
        assert info.content_hash == _content_hash(content)

    def test_roundtrip_with_existing_user_content(self, tmp_path: Path) -> None:
        """Test roundtrip with user content surrounding the section."""
        f = tmp_path / "test.md"
        f.write_text("# My Project\n\nUser writes here.\n")

        upsert_managed_section(f, "managed part", version=1)

        text = f.read_text()
        assert "# My Project" in text
        assert "User writes here." in text

        info = detect_managed_section(f)
        assert info.found is True
        assert info.content_modified is False

        # Update again
        upsert_managed_section(f, "updated managed", version=2)
        text2 = f.read_text()
        assert "# My Project" in text2
        assert "User writes here." in text2
        assert "updated managed" in text2

    def test_upsert_result_has_path(self, tmp_path: Path) -> None:
        """Test that UpsertResult contains the correct file path."""
        f = tmp_path / "result.md"
        result = upsert_managed_section(f, "content", version=1)
        assert result.file_path == f

    def test_multiline_content(self, tmp_path: Path) -> None:
        """Test upserting multi-line content."""
        f = tmp_path / "test.md"
        content = "## Section\n\n- Item 1\n- Item 2\n\nParagraph here."

        result = upsert_managed_section(f, content, version=1)
        assert result.action == UpsertAction.CREATED

        info = detect_managed_section(f)
        assert info.found is True
        assert info.content_modified is False

        text = f.read_text()
        assert "## Section" in text
        assert "- Item 1" in text
        assert "- Item 2" in text


class TestCreateAgentsSymlink:
    """Tests for create_agents_symlink function."""

    def test_creates_symlink_when_claude_exists(self, tmp_path: Path) -> None:
        """Test that symlink is created when CLAUDE.md exists."""
        claude_path = tmp_path / "CLAUDE.md"
        agents_path = tmp_path / "AGENTS.md"
        claude_path.write_text("# CLAUDE.md content")

        result = create_agents_symlink(tmp_path)

        assert result is True
        assert agents_path.is_symlink()
        assert agents_path.resolve() == claude_path.resolve()
        assert agents_path.read_text() == "# CLAUDE.md content"

    def test_returns_false_when_claude_missing(self, tmp_path: Path) -> None:
        """Test that symlink is not created when CLAUDE.md doesn't exist."""
        result = create_agents_symlink(tmp_path)

        assert result is False
        assert not (tmp_path / "AGENTS.md").exists()

    def test_returns_true_for_correct_existing_symlink(self, tmp_path: Path) -> None:
        """Test that True is returned if correct symlink already exists."""
        claude_path = tmp_path / "CLAUDE.md"
        agents_path = tmp_path / "AGENTS.md"
        claude_path.write_text("# Content")
        agents_path.symlink_to("CLAUDE.md")

        result = create_agents_symlink(tmp_path)

        assert result is True
        assert agents_path.is_symlink()

    def test_returns_false_for_existing_file_without_force(self, tmp_path: Path) -> None:
        """Test that False is returned for existing non-symlink file without force."""
        claude_path = tmp_path / "CLAUDE.md"
        agents_path = tmp_path / "AGENTS.md"
        claude_path.write_text("# CLAUDE")
        agents_path.write_text("# Existing AGENTS content")

        result = create_agents_symlink(tmp_path, force=False)

        assert result is False
        assert not agents_path.is_symlink()
        assert agents_path.read_text() == "# Existing AGENTS content"

    def test_replaces_existing_file_with_force(self, tmp_path: Path) -> None:
        """Test that existing file is replaced with symlink when force=True."""
        claude_path = tmp_path / "CLAUDE.md"
        agents_path = tmp_path / "AGENTS.md"
        claude_path.write_text("# CLAUDE content")
        agents_path.write_text("# Old AGENTS content")

        result = create_agents_symlink(tmp_path, force=True)

        assert result is True
        assert agents_path.is_symlink()
        assert agents_path.read_text() == "# CLAUDE content"

    def test_replaces_wrong_symlink_with_force(self, tmp_path: Path) -> None:
        """Test that wrong symlink is replaced with correct one when force=True."""
        claude_path = tmp_path / "CLAUDE.md"
        other_path = tmp_path / "OTHER.md"
        agents_path = tmp_path / "AGENTS.md"
        claude_path.write_text("# CLAUDE")
        other_path.write_text("# OTHER")
        agents_path.symlink_to("OTHER.md")

        result = create_agents_symlink(tmp_path, force=True)

        assert result is True
        assert agents_path.is_symlink()
        assert agents_path.readlink() == Path("CLAUDE.md")

    def test_symlink_target_is_relative(self, tmp_path: Path) -> None:
        """Test that symlink uses relative path, not absolute."""
        claude_path = tmp_path / "CLAUDE.md"
        agents_path = tmp_path / "AGENTS.md"
        claude_path.write_text("# Content")

        create_agents_symlink(tmp_path)

        # Readlink returns the target as stored, should be relative
        target = agents_path.readlink()
        assert target == Path("CLAUDE.md")
        assert not target.is_absolute()

    def test_symlink_content_accessible(self, tmp_path: Path) -> None:
        """Test that content is accessible through symlink."""
        claude_path = tmp_path / "CLAUDE.md"
        agents_path = tmp_path / "AGENTS.md"
        claude_path.write_text("# Test Content\n\nThis is a test.")

        create_agents_symlink(tmp_path)

        # Content should be identical when read through either path
        assert agents_path.read_text() == claude_path.read_text()

        # Modifying through one path should be visible through the other
        claude_path.write_text("# Updated Content")
        assert agents_path.read_text() == "# Updated Content"
