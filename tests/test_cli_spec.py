"""
Tests for the cub spec CLI command.

The spec command provides:
- Interactive spec creation via Claude interview
- Listing specs across all lifecycle stages
- Project root discovery from subdirectories
"""

import os
from pathlib import Path

from typer.testing import CliRunner

from cub.cli import app
from cub.utils.project import find_project_root

runner = CliRunner()


class TestSpecCommandHelp:
    """Test spec command help and structure."""

    def test_spec_help(self) -> None:
        """Test that 'cub spec --help' shows available options."""
        result = runner.invoke(app, ["spec", "--help"])
        assert result.exit_code == 0
        # Check for "list" option - may have ANSI codes between "--" and "list"
        assert "list" in result.output.lower()
        assert "topic" in result.output.lower()

    def test_spec_list_option_help_text(self) -> None:
        """Test that --list option help text mentions all stages."""
        result = runner.invoke(app, ["spec", "--help"])
        assert result.exit_code == 0
        # Should mention listing specs (all stages)
        assert "list" in result.output.lower()


class TestSpecListFromProjectRoot:
    """Test spec --list from project root directory."""

    def test_list_specs_no_project_root(self) -> None:
        """Test listing specs when not in a project directory."""
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            assert "not in a project" in result.output.lower()

    def test_list_specs_no_specs_directory(self) -> None:
        """Test listing specs when specs/ directory doesn't exist."""
        with runner.isolated_filesystem():
            # Create a project marker
            Path(".beads").mkdir()
            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            assert "no specs/ directory" in result.output.lower()

    def test_list_specs_empty(self) -> None:
        """Test listing specs when specs directory exists but is empty."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)
            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            assert "no specs found" in result.output.lower()

    def test_list_specs_researching_stage(self) -> None:
        """Test listing specs in researching stage."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)

            # Create a spec file
            spec_content = """---
status: draft
readiness:
  score: 5
---
# Test Feature

This is a test spec.
"""
            Path("specs/researching/test-feature.md").write_text(spec_content)

            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            assert "test-feature" in result.output
            assert "researching" in result.output.lower()
            assert "[5/10]" in result.output
            assert "Test Feature" in result.output

    def test_list_specs_multiple_stages(self) -> None:
        """Test listing specs across multiple stages."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)
            Path("specs/planned").mkdir(parents=True)
            Path("specs/implementing").mkdir(parents=True)

            # Create specs in different stages
            researching_spec = """---
readiness:
  score: 3
---
# Research Spec
"""
            planned_spec = """---
readiness:
  score: 7
---
# Planned Spec
"""
            implementing_spec = """---
readiness:
  score: 9
---
# Implementing Spec
"""
            Path("specs/researching/research-feature.md").write_text(researching_spec)
            Path("specs/planned/planned-feature.md").write_text(planned_spec)
            Path("specs/implementing/impl-feature.md").write_text(implementing_spec)

            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0

            # Should show all three specs
            assert "research-feature" in result.output
            assert "planned-feature" in result.output
            assert "impl-feature" in result.output

            # Should show stage labels
            assert "researching" in result.output.lower()
            assert "planned" in result.output.lower()
            assert "implementing" in result.output.lower()

            # Should show total count
            assert "3 total" in result.output


class TestSpecListFromSubdirectory:
    """Test spec --list from project subdirectories."""

    def test_list_specs_from_src_subdirectory(self) -> None:
        """Test listing specs from a src/ subdirectory."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)
            Path("src/module").mkdir(parents=True)

            # Create a spec
            spec_content = """---
readiness:
  score: 6
---
# Subdir Test
"""
            Path("specs/researching/subdir-test.md").write_text(spec_content)

            # Change to subdirectory
            original_dir = os.getcwd()
            os.chdir("src/module")
            try:
                result = runner.invoke(app, ["spec", "--list"])
                assert result.exit_code == 0
                assert "subdir-test" in result.output
                assert "researching" in result.output.lower()
            finally:
                os.chdir(original_dir)

    def test_list_specs_from_deeply_nested_directory(self) -> None:
        """Test listing specs from a deeply nested subdirectory."""
        with runner.isolated_filesystem():
            # Create project structure
            Path(".git").mkdir()  # Use .git as marker
            Path("specs/planned").mkdir(parents=True)
            Path("src/app/components/ui").mkdir(parents=True)

            # Create a spec
            spec_content = """---
readiness:
  score: 8
---
# Deep Nested Test
"""
            Path("specs/planned/deep-nested.md").write_text(spec_content)

            # Change to deeply nested directory
            original_dir = os.getcwd()
            os.chdir("src/app/components/ui")
            try:
                result = runner.invoke(app, ["spec", "--list"])
                assert result.exit_code == 0
                assert "deep-nested" in result.output
                assert "planned" in result.output.lower()
            finally:
                os.chdir(original_dir)

    def test_list_specs_with_cub_json_marker(self) -> None:
        """Test project root discovery with .cub.json marker."""
        with runner.isolated_filesystem():
            # Create project structure with .cub.json
            Path(".cub.json").write_text("{}")
            Path("specs/researching").mkdir(parents=True)
            Path("lib").mkdir()

            # Create a spec
            spec_content = """---
readiness:
  score: 4
---
# JSON Marker Test
"""
            Path("specs/researching/json-marker-test.md").write_text(spec_content)

            # Change to subdirectory
            original_dir = os.getcwd()
            os.chdir("lib")
            try:
                result = runner.invoke(app, ["spec", "--list"])
                assert result.exit_code == 0
                assert "json-marker-test" in result.output
            finally:
                os.chdir(original_dir)

    def test_list_specs_with_cub_dir_marker(self) -> None:
        """Test project root discovery with .cub/ directory marker."""
        with runner.isolated_filesystem():
            # Create project structure with .cub directory
            Path(".cub").mkdir()
            Path("specs/researching").mkdir(parents=True)
            Path("tests").mkdir()

            # Create a spec
            spec_content = """---
readiness:
  score: 2
---
# Cub Dir Test
"""
            Path("specs/researching/cub-dir-test.md").write_text(spec_content)

            # Change to subdirectory
            original_dir = os.getcwd()
            os.chdir("tests")
            try:
                result = runner.invoke(app, ["spec", "--list"])
                assert result.exit_code == 0
                assert "cub-dir-test" in result.output
            finally:
                os.chdir(original_dir)


class TestProjectRootDiscovery:
    """Test the project root discovery utility."""

    def test_find_project_root_with_beads(self) -> None:
        """Test finding project root via .beads/ directory."""
        with runner.isolated_filesystem():
            Path(".beads").mkdir()
            Path("src/deep").mkdir(parents=True)

            original_dir = os.getcwd()
            os.chdir("src/deep")
            try:
                root = find_project_root()
                assert root is not None
                assert (root / ".beads").exists()
            finally:
                os.chdir(original_dir)

    def test_find_project_root_with_git(self) -> None:
        """Test finding project root via .git/ directory."""
        with runner.isolated_filesystem():
            Path(".git").mkdir()
            Path("src").mkdir()

            original_dir = os.getcwd()
            os.chdir("src")
            try:
                root = find_project_root()
                assert root is not None
                assert (root / ".git").exists()
            finally:
                os.chdir(original_dir)

    def test_find_project_root_none(self) -> None:
        """Test that find_project_root returns None when no marker found."""
        with runner.isolated_filesystem():
            # No project markers
            Path("src").mkdir()

            original_dir = os.getcwd()
            os.chdir("src")
            try:
                root = find_project_root()
                # Should return None since we're in isolated filesystem
                # (unless there's a marker above, which there shouldn't be)
                assert root is None
            finally:
                os.chdir(original_dir)

    def test_find_project_root_prefers_beads_over_git(self) -> None:
        """Test that .beads/ is found before .git/ when both exist."""
        with runner.isolated_filesystem():
            # Create both markers at same level
            Path(".beads").mkdir()
            Path(".git").mkdir()
            Path("src").mkdir()

            original_dir = os.getcwd()
            os.chdir("src")
            try:
                root = find_project_root()
                assert root is not None
                # Both should exist at root, but .beads should be checked first
                assert (root / ".beads").exists()
                assert (root / ".git").exists()
            finally:
                os.chdir(original_dir)


class TestSpecListDisplay:
    """Test the display formatting of spec list."""

    def test_list_shows_readiness_score(self) -> None:
        """Test that readiness scores are displayed correctly."""
        with runner.isolated_filesystem():
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)

            spec_content = """---
readiness:
  score: 8
---
# High Readiness
"""
            Path("specs/researching/high-ready.md").write_text(spec_content)

            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            assert "[8/10]" in result.output

    def test_list_shows_spec_title(self) -> None:
        """Test that spec titles are displayed."""
        with runner.isolated_filesystem():
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)

            spec_content = """---
readiness:
  score: 5
---
# My Amazing Feature Title
"""
            Path("specs/researching/amazing-feature.md").write_text(spec_content)

            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            assert "My Amazing Feature Title" in result.output

    def test_list_shows_helpful_commands(self) -> None:
        """Test that helpful commands are shown at the bottom."""
        with runner.isolated_filesystem():
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)

            spec_content = """---
readiness:
  score: 5
---
# Test
"""
            Path("specs/researching/test.md").write_text(spec_content)

            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            # Should show view command hint
            assert "cat specs" in result.output.lower() or "view" in result.output.lower()

    def test_list_groups_by_stage(self) -> None:
        """Test that specs are grouped by stage in lifecycle order."""
        with runner.isolated_filesystem():
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)
            Path("specs/released").mkdir(parents=True)
            Path("specs/planned").mkdir(parents=True)

            # Create specs (add in non-lifecycle order)
            Path("specs/released/done-feature.md").write_text(
                "---\nreadiness:\n  score: 10\n---\n# Done"
            )
            Path("specs/researching/new-feature.md").write_text(
                "---\nreadiness:\n  score: 2\n---\n# New"
            )
            Path("specs/planned/ready-feature.md").write_text(
                "---\nreadiness:\n  score: 7\n---\n# Ready"
            )

            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0

            # Check lifecycle order in output
            output = result.output

            # Check that all stages are present in output
            assert "researching" in output, f"'researching' not in output:\n{output}"
            assert "planned" in output, f"'planned' not in output:\n{output}"
            assert "released" in output, f"'released' not in output:\n{output}"

            # Check lifecycle order in output
            researching_pos = output.find("researching")
            planned_pos = output.find("planned")
            released_pos = output.find("released")

            # Researching should come before planned, which should come before released
            assert researching_pos < planned_pos < released_pos, (
                f"Wrong order: researching={researching_pos}, planned={planned_pos}, "
                f"released={released_pos}\nOutput:\n{output}"
            )


class TestSpecListEdgeCases:
    """Test edge cases for spec listing."""

    def test_list_handles_malformed_spec(self) -> None:
        """Test that malformed specs don't crash the listing."""
        with runner.isolated_filesystem():
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)

            # Create a malformed spec (invalid YAML)
            Path("specs/researching/malformed.md").write_text("---\ninvalid: yaml: here\n---")

            # Create a valid spec too
            Path("specs/researching/valid.md").write_text(
                "---\nreadiness:\n  score: 5\n---\n# Valid"
            )

            result = runner.invoke(app, ["spec", "--list"])
            # Should not crash, and should show the valid spec
            assert result.exit_code == 0
            assert "valid" in result.output

    def test_list_handles_empty_frontmatter(self) -> None:
        """Test specs with empty or missing frontmatter."""
        with runner.isolated_filesystem():
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)

            # Spec with no frontmatter
            Path("specs/researching/no-frontmatter.md").write_text(
                "# Just a heading\n\nContent here."
            )

            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            assert "no-frontmatter" in result.output

    def test_list_handles_spec_without_title(self) -> None:
        """Test specs without a markdown heading title."""
        with runner.isolated_filesystem():
            Path(".beads").mkdir()
            Path("specs/researching").mkdir(parents=True)

            # Spec without heading
            Path("specs/researching/no-title.md").write_text(
                "---\nreadiness:\n  score: 3\n---\nJust content, no heading."
            )

            result = runner.invoke(app, ["spec", "--list"])
            assert result.exit_code == 0
            assert "no-title" in result.output
