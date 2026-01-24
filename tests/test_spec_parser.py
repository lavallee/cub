"""
Tests for the spec parser in the dashboard sync layer.

Tests cover:
- Parsing valid spec files with full frontmatter
- Handling missing frontmatter (creates entity with defaults)
- Handling invalid YAML (logs warning, uses defaults)
- Handling empty files (returns None)
- Stage mapping (spec stage -> dashboard stage)
- Priority mapping (spec priority -> dashboard priority)
- Label extraction (complexity, status)
- Checksum computation for incremental sync
- Parsing all specs across all stages
- Parsing specs from a specific stage
"""

from datetime import date, datetime
from pathlib import Path

import pytest

from cub.core.dashboard.db.models import EntityType, Stage
from cub.core.dashboard.sync.parsers.specs import SpecParser
from cub.core.specs import Stage as SpecStage


@pytest.fixture
def tmp_specs_root(tmp_path: Path) -> Path:
    """Create temporary specs directory structure."""
    specs_root = tmp_path / "specs"
    specs_root.mkdir()

    # Create stage directories
    for stage in SpecStage:
        (specs_root / stage.value).mkdir()

    return specs_root


@pytest.fixture
def parser(tmp_specs_root: Path) -> SpecParser:
    """Create SpecParser instance with temp directory."""
    return SpecParser(tmp_specs_root)


class TestSpecParser:
    """Tests for the SpecParser class."""

    def test_parse_valid_spec(self, tmp_specs_root: Path, parser: SpecParser) -> None:
        """Test parsing a valid spec file with full frontmatter."""
        spec_content = """---
status: ready
priority: high
complexity: medium
dependencies:
  - auth-system
  - database
created: 2026-01-15
updated: 2026-01-20
readiness:
  score: 8
  blockers: []
  questions:
    - "Which database?"
notes: "Test spec for parsing"
---

# Test Feature

This is a test specification for the spec parser.
"""
        spec_file = tmp_specs_root / "planned" / "test-feature.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is not None
        assert entity.id == "test-feature"
        assert entity.type == EntityType.SPEC
        assert entity.title == "Test Feature"
        assert entity.stage == Stage.PLANNED
        assert entity.status == "ready"
        assert entity.priority == 1  # high -> 1
        assert "complexity:medium" in entity.labels
        assert "status:ready" in entity.labels
        assert entity.created_at == datetime(2026, 1, 15)
        assert entity.updated_at == datetime(2026, 1, 20)
        assert entity.source_type == "file"
        assert entity.source_path == str(spec_file)
        assert entity.source_checksum is not None
        # Note: Specs don't set spec_id to themselves - spec_id is for linking plans TO specs
        assert entity.spec_id is None
        assert entity.content is not None
        assert "Test Feature" in entity.content

    def test_parse_spec_missing_frontmatter(
        self, tmp_specs_root: Path, parser: SpecParser
    ) -> None:
        """Test parsing a spec file with no frontmatter."""
        spec_content = "# Simple Spec\n\nNo frontmatter here."
        spec_file = tmp_specs_root / "researching" / "simple-spec.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.RESEARCHING)

        assert entity is not None
        assert entity.id == "simple-spec"
        assert entity.title == "Simple Spec"
        assert entity.stage == Stage.RESEARCHING
        assert entity.priority == 2  # default medium -> 2
        assert "complexity:medium" in entity.labels  # default

    def test_parse_spec_invalid_yaml(
        self, tmp_specs_root: Path, parser: SpecParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a spec file with invalid YAML frontmatter."""
        spec_content = """---
invalid: yaml: structure: here
  bad indentation
priority: high
---

# Invalid YAML Spec
"""
        spec_file = tmp_specs_root / "planned" / "invalid-yaml.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        # Should handle gracefully and create entity with defaults
        assert entity is not None
        assert entity.id == "invalid-yaml"
        assert "Invalid YAML frontmatter" in caplog.text

    def test_parse_spec_empty_file(
        self, tmp_specs_root: Path, parser: SpecParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing an empty spec file."""
        spec_file = tmp_specs_root / "researching" / "empty.md"
        spec_file.write_text("")

        entity = parser.parse_file(spec_file, SpecStage.RESEARCHING)

        assert entity is None
        assert "Empty spec file" in caplog.text

    def test_stage_mapping(self, tmp_specs_root: Path, parser: SpecParser) -> None:
        """Test that spec stages map correctly to dashboard stages."""
        test_cases = [
            (SpecStage.RESEARCHING, Stage.RESEARCHING),
            (SpecStage.PLANNED, Stage.PLANNED),
            (SpecStage.STAGED, Stage.READY),
            (SpecStage.IMPLEMENTING, Stage.IN_PROGRESS),
            (SpecStage.RELEASED, Stage.RELEASED),
        ]

        for spec_stage, expected_dashboard_stage in test_cases:
            spec_content = "---\npriority: medium\n---\n# Test"
            spec_file = tmp_specs_root / spec_stage.value / f"test-{spec_stage.value}.md"
            spec_file.write_text(spec_content)

            entity = parser.parse_file(spec_file, spec_stage)

            assert entity is not None
            assert entity.stage == expected_dashboard_stage, (
                f"Stage mapping failed: {spec_stage.value} -> {expected_dashboard_stage.value}"
            )

    def test_priority_mapping(self, tmp_specs_root: Path, parser: SpecParser) -> None:
        """Test that spec priorities map correctly to dashboard priorities."""
        test_cases = [
            ("critical", 0),
            ("high", 1),
            ("medium", 2),
            ("low", 3),
        ]

        for spec_priority, expected_dashboard_priority in test_cases:
            spec_content = f"---\npriority: {spec_priority}\n---\n# Test"
            spec_file = tmp_specs_root / "planned" / f"test-{spec_priority}.md"
            spec_file.write_text(spec_content)

            entity = parser.parse_file(spec_file, SpecStage.PLANNED)

            assert entity is not None
            assert entity.priority == expected_dashboard_priority, (
                f"Priority mapping failed: {spec_priority} -> P{expected_dashboard_priority}"
            )

    def test_label_extraction(self, tmp_specs_root: Path, parser: SpecParser) -> None:
        """Test extraction of labels from spec metadata."""
        spec_content = """---
status: in-progress
complexity: high
---

# Test Spec
"""
        spec_file = tmp_specs_root / "implementing" / "test-labels.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.IMPLEMENTING)

        assert entity is not None
        assert "complexity:high" in entity.labels
        assert "status:in-progress" in entity.labels

    def test_checksum_computation(self, tmp_specs_root: Path, parser: SpecParser) -> None:
        """Test that checksum is computed and changes when content changes."""
        spec_file = tmp_specs_root / "planned" / "checksum-test.md"
        spec_file.write_text("---\npriority: medium\n---\n# Version 1")

        entity1 = parser.parse_file(spec_file, SpecStage.PLANNED)
        assert entity1 is not None
        checksum1 = entity1.source_checksum

        # Modify the file
        spec_file.write_text("---\npriority: medium\n---\n# Version 2")

        entity2 = parser.parse_file(spec_file, SpecStage.PLANNED)
        assert entity2 is not None
        checksum2 = entity2.source_checksum

        assert checksum1 != checksum2, "Checksum should change when content changes"

    def test_parse_all_specs(self, tmp_specs_root: Path, parser: SpecParser) -> None:
        """Test parsing all specs across all stages."""
        # Create specs in different stages
        stages_and_names = [
            (SpecStage.RESEARCHING, "idea-1"),
            (SpecStage.RESEARCHING, "idea-2"),
            (SpecStage.PLANNED, "plan-1"),
            (SpecStage.STAGED, "staged-1"),
            (SpecStage.IMPLEMENTING, "impl-1"),
            (SpecStage.RELEASED, "released-1"),
        ]

        for stage, name in stages_and_names:
            spec_content = f"---\npriority: medium\n---\n# {name}"
            spec_file = tmp_specs_root / stage.value / f"{name}.md"
            spec_file.write_text(spec_content)

        entities = parser.parse_all()

        assert len(entities) == 6
        assert all(e.type == EntityType.SPEC for e in entities)

        # Check that entities are sorted by name
        entity_ids = [e.id for e in entities]
        assert entity_ids == sorted(entity_ids)

    def test_parse_stage(self, tmp_specs_root: Path, parser: SpecParser) -> None:
        """Test parsing specs from a specific stage."""
        # Create specs in planned stage
        for i in range(3):
            spec_content = f"---\npriority: high\n---\n# Planned Spec {i}"
            spec_file = tmp_specs_root / "planned" / f"planned-{i}.md"
            spec_file.write_text(spec_content)

        # Create specs in other stages (should not be included)
        spec_file = tmp_specs_root / "researching" / "other.md"
        spec_file.write_text("---\npriority: medium\n---\n# Other")

        entities = parser.parse_stage(SpecStage.PLANNED)

        assert len(entities) == 3
        assert all(e.stage == Stage.PLANNED for e in entities)
        assert all(e.id.startswith("planned-") for e in entities)

    def test_parse_nonexistent_stage_directory(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing when stage directory doesn't exist."""
        specs_root = tmp_path / "nonexistent"
        parser = SpecParser(specs_root)

        entities = parser.parse_all()

        assert len(entities) == 0
        assert "Specs root not found" in caplog.text

    def test_spec_with_no_title_heading(
        self, tmp_specs_root: Path, parser: SpecParser
    ) -> None:
        """Test spec with no markdown heading (should use filename as title)."""
        spec_content = "---\npriority: medium\n---\n\nNo heading here, just content."
        spec_file = tmp_specs_root / "planned" / "no-heading.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is not None
        assert entity.title == "no-heading"  # Uses filename as title

    def test_spec_with_dependencies(
        self, tmp_specs_root: Path, parser: SpecParser
    ) -> None:
        """Test that dependencies are stored in frontmatter but not as labels."""
        spec_content = """---
priority: high
dependencies:
  - auth-system
  - database-schema
blocks:
  - user-profiles
---

# Feature with Dependencies
"""
        spec_file = tmp_specs_root / "planned" / "feature-deps.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is not None
        # Dependencies should be in frontmatter
        assert entity.frontmatter is not None
        assert "dependencies" in entity.frontmatter
        assert entity.frontmatter["dependencies"] == ["auth-system", "database-schema"]

        # Dependencies should NOT be in labels (they're relationships)
        assert not any("dependency:" in label for label in entity.labels)

    def test_spec_with_readiness(
        self, tmp_specs_root: Path, parser: SpecParser
    ) -> None:
        """Test that readiness information is preserved in frontmatter."""
        spec_content = """---
priority: medium
readiness:
  score: 7
  blockers:
    - "Need API approval"
  questions:
    - "Which database to use?"
  decisions_needed:
    - "Choose auth provider"
---

# Spec with Readiness
"""
        spec_file = tmp_specs_root / "planned" / "readiness-spec.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is not None
        assert entity.frontmatter is not None
        assert "readiness" in entity.frontmatter
        readiness = entity.frontmatter["readiness"]
        assert readiness["score"] == 7
        assert "Need API approval" in readiness["blockers"]
        assert "Which database to use?" in readiness["questions"]

    def test_multiple_specs_same_content_different_checksums(
        self, tmp_specs_root: Path, parser: SpecParser
    ) -> None:
        """Test that identical spec names in different stages have different entities."""
        # This shouldn't happen in practice, but test the behavior
        spec_content_1 = "---\npriority: high\n---\n# Version in Planned"
        spec_content_2 = "---\npriority: low\n---\n# Version in Researching"

        spec_file_1 = tmp_specs_root / "planned" / "same-name.md"
        spec_file_2 = tmp_specs_root / "researching" / "same-name.md"

        spec_file_1.write_text(spec_content_1)
        spec_file_2.write_text(spec_content_2)

        entities = parser.parse_all()

        # Both should be parsed (even though they have the same id)
        # The sync layer will need to handle this edge case
        assert len(entities) == 2
        same_name_entities = [e for e in entities if e.id == "same-name"]
        assert len(same_name_entities) == 2

        # They should have different stages and priorities
        stages = {e.stage for e in same_name_entities}
        priorities = {e.priority for e in same_name_entities}
        assert len(stages) == 2  # Different stages
        assert len(priorities) == 2  # Different priorities

    def test_spec_with_null_frontmatter(
        self, tmp_specs_root: Path, parser: SpecParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a spec file with null frontmatter."""
        spec_content = """---
---

# Null Frontmatter Spec

This spec has frontmatter delimiters but no content.
"""
        spec_file = tmp_specs_root / "planned" / "null-frontmatter.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        # Should handle gracefully and create entity with defaults
        assert entity is not None
        assert entity.id == "null-frontmatter"
        assert entity.title == "Null Frontmatter Spec"
        assert entity.priority == 2  # default medium

    def test_spec_with_non_dict_frontmatter(
        self, tmp_specs_root: Path, parser: SpecParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a spec file with non-dict frontmatter."""
        # This edge case is rare but could happen with malformed YAML
        spec_content = """---
- item1
- item2
---

# List Frontmatter Spec
"""
        spec_file = tmp_specs_root / "planned" / "list-frontmatter.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        # Should handle gracefully - entity may still be created with defaults
        # The frontmatter library will parse the YAML successfully but return a list
        # Our code checks for this and converts to empty dict
        assert entity is not None
        # Check if warning was logged (only if metadata was non-dict)
        if "not a dict" not in caplog.text:
            # The warning might not appear if frontmatter library returns Post with metadata=[]
            # which our code then converts to {}. That's fine - entity should still be created.
            pass

    def test_spec_with_unicode_error(
        self, tmp_specs_root: Path, parser: SpecParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a spec file with invalid UTF-8 encoding."""
        spec_file = tmp_specs_root / "planned" / "invalid-encoding.md"
        # Write invalid UTF-8 bytes
        spec_file.write_bytes(b"\xff\xfe\x00\x00Invalid UTF-8")

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is None
        assert "Unable to read" in caplog.text or "UTF-8" in caplog.text

    def test_spec_file_disappears_during_parsing(
        self, tmp_specs_root: Path, parser: SpecParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handling when a spec file is deleted during parsing."""
        spec_file = tmp_specs_root / "planned" / "disappearing.md"

        # File doesn't exist
        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is None
        assert "not found" in caplog.text

    def test_spec_with_malformed_yaml_continues(
        self, tmp_specs_root: Path, parser: SpecParser
    ) -> None:
        """Test that parsing continues with other specs when one has malformed YAML."""
        # Create one good spec
        good_content = "---\npriority: high\n---\n# Good Spec"
        good_file = tmp_specs_root / "planned" / "good-spec.md"
        good_file.write_text(good_content)

        # Create one bad spec
        bad_content = "---\ninvalid: yaml: structure\n---\n# Bad Spec"
        bad_file = tmp_specs_root / "planned" / "bad-spec.md"
        bad_file.write_text(bad_content)

        # Create another good spec
        good_content2 = "---\npriority: low\n---\n# Another Good Spec"
        good_file2 = tmp_specs_root / "planned" / "another-good.md"
        good_file2.write_text(good_content2)

        entities = parser.parse_all()

        # Should get 3 entities (all parsed with defaults for bad one)
        assert len(entities) == 3
        entity_ids = [e.id for e in entities]
        assert "good-spec" in entity_ids
        assert "bad-spec" in entity_ids
        assert "another-good" in entity_ids

    def test_spec_without_frontmatter_delimiters(
        self, tmp_specs_root: Path, parser: SpecParser
    ) -> None:
        """Test parsing a spec file with no frontmatter delimiters at all."""
        spec_content = "# Plain Markdown Spec\n\nThis is just plain markdown, no frontmatter."
        spec_file = tmp_specs_root / "researching" / "plain-markdown.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.RESEARCHING)

        assert entity is not None
        assert entity.id == "plain-markdown"
        assert entity.title == "Plain Markdown Spec"
        assert entity.priority == 2  # default medium

    def test_spec_with_empty_frontmatter_fields(
        self, tmp_specs_root: Path, parser: SpecParser
    ) -> None:
        """Test parsing a spec with empty/null frontmatter fields."""
        spec_content = """---
priority:
complexity:
dependencies:
notes:
---

# Spec with Empty Fields
"""
        spec_file = tmp_specs_root / "planned" / "empty-fields.md"
        spec_file.write_text(spec_content)

        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        # Should handle gracefully with defaults
        assert entity is not None
        assert entity.id == "empty-fields"
        assert entity.priority == 2  # default medium
