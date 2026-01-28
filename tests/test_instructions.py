"""
Tests for instruction file generation module.
"""

import hashlib
from pathlib import Path

from cub.core.config.models import CircuitBreakerConfig, CubConfig
from cub.core.instructions import (
    ESCAPE_HATCH_SECTION,
    SectionInfo,
    UpsertAction,
    UpsertResult,
    _content_hash,
    _format_managed_block,
    detect_managed_section,
    generate_agents_md,
    generate_claude_md,
    upsert_managed_section,
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
        """Test that .cub/agent.md is referenced for build instructions."""
        config = CubConfig()
        content = generate_claude_md(tmp_path, config)

        # Should reference .cub/agent.md (build/test instructions)
        assert ".cub/agent.md" in content

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
        # (though it may reference .cub/agent.md for build instructions)
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
        assert ".cub/agent.md" in content

    def test_custom_circuit_breaker_timeout_propagates(self, tmp_path: Path) -> None:
        """Test that custom circuit breaker timeout appears in AGENTS.md."""
        config = CubConfig(circuit_breaker=CircuitBreakerConfig(timeout_minutes=60))

        content = generate_agents_md(tmp_path, config)

        assert "60-minute timeout" in content
        assert "30-minute timeout" not in content


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
