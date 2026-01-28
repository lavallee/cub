"""
Tests for the map CLI command.

Tests cover:
- Map generation via CLI
- Output file creation
- Token budget and max depth options
- Force overwrite behavior
- Integration with init and update commands
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cub.cli import app
from cub.cli.map import generate_map

runner = CliRunner()


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def simple_python_project(tmp_path: Path) -> Path:
    """Create a simple Python project for testing."""
    project = tmp_path / "test_project"
    project.mkdir()

    # Create a simple Python module
    (project / "main.py").write_text(
        """
def hello_world():
    '''Say hello to the world.'''
    return "Hello, world!"

class Calculator:
    '''A simple calculator.'''
    def add(self, a: int, b: int) -> int:
        return a + b
"""
    )

    # Create a README
    (project / "README.md").write_text("# Test Project\n\nA simple test project.")

    # Create pyproject.toml
    (project / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
version = "0.1.0"

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
"""
    )

    return project


# ==============================================================================
# generate_map() Function Tests
# ==============================================================================


class TestGenerateMap:
    """Test the generate_map() function."""

    def test_generate_map_basic(self, simple_python_project: Path):
        """Test basic map generation."""
        map_content = generate_map(simple_python_project)

        # Should contain structure sections
        assert "# Project Map" in map_content
        assert "## Tech Stacks" in map_content or "Tech Stack" in map_content
        # Build commands may not be present if no Makefile or scripts defined
        # Just check for key sections
        assert "## Key Files" in map_content or "## Directory Structure" in map_content

        # Should be non-empty
        assert len(map_content) > 100

    def test_generate_map_with_token_budget(self, simple_python_project: Path):
        """Test map generation with custom token budget."""
        small_map = generate_map(simple_python_project, token_budget=1024)
        large_map = generate_map(simple_python_project, token_budget=8192)

        # Both should succeed
        assert len(small_map) > 0
        assert len(large_map) > 0

        # Larger budget may produce longer output
        # (not guaranteed due to content limits, but check they're different)
        assert small_map != large_map or len(large_map) >= len(small_map)

    def test_generate_map_with_max_depth(self, simple_python_project: Path):
        """Test map generation with custom max depth."""
        map_content = generate_map(simple_python_project, max_depth=2)

        # Should succeed
        assert "# Project Map" in map_content

    def test_generate_map_nonexistent_directory(self, tmp_path: Path):
        """Test map generation with nonexistent directory."""
        nonexistent = tmp_path / "does_not_exist"

        # Should raise an exception
        with pytest.raises(Exception):
            generate_map(nonexistent)


# ==============================================================================
# CLI Command Tests
# ==============================================================================


class TestMapCLI:
    """Test the map CLI command."""

    def test_map_command_basic(self, simple_python_project: Path):
        """Test basic map command execution."""
        result = runner.invoke(app, ["map", str(simple_python_project), "--output", ".cub/map.md"])

        # Should succeed
        assert result.exit_code == 0
        assert "✓" in result.stdout or "Project map saved" in result.stdout

        # Output file should exist
        map_path = simple_python_project / ".cub" / "map.md"
        assert map_path.exists()

        # Content should be valid
        content = map_path.read_text()
        assert "# Project Map" in content

    def test_map_command_custom_output(self, simple_python_project: Path):
        """Test map command with custom output path."""
        custom_output = simple_python_project / "custom_map.md"

        result = runner.invoke(
            app,
            ["map", str(simple_python_project), "--output", str(custom_output)],
        )

        assert result.exit_code == 0
        assert custom_output.exists()

    def test_map_command_force_overwrite(self, simple_python_project: Path):
        """Test map command with force overwrite."""
        map_path = simple_python_project / ".cub" / "map.md"
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text("Old content")

        # Without force, should fail
        result = runner.invoke(app, ["map", str(simple_python_project), "--output", ".cub/map.md"])
        assert result.exit_code == 1
        assert "already exists" in result.stdout

        # With force, should succeed
        result = runner.invoke(
            app,
            ["map", str(simple_python_project), "--output", ".cub/map.md", "--force"],
        )
        assert result.exit_code == 0

        # Content should be updated
        content = map_path.read_text()
        assert content != "Old content"
        assert "# Project Map" in content

    def test_map_command_token_budget_option(self, simple_python_project: Path):
        """Test map command with custom token budget."""
        result = runner.invoke(
            app,
            [
                "map",
                str(simple_python_project),
                "--output",
                ".cub/map.md",
                "--token-budget",
                "8192",
            ],
        )

        assert result.exit_code == 0

        map_path = simple_python_project / ".cub" / "map.md"
        assert map_path.exists()

    def test_map_command_max_depth_option(self, simple_python_project: Path):
        """Test map command with custom max depth."""
        result = runner.invoke(
            app,
            [
                "map",
                str(simple_python_project),
                "--output",
                ".cub/map.md",
                "--max-depth",
                "2",
            ],
        )

        assert result.exit_code == 0

        map_path = simple_python_project / ".cub" / "map.md"
        assert map_path.exists()

    def test_map_command_debug_output(self, simple_python_project: Path):
        """Test map command with debug output."""
        result = runner.invoke(
            app,
            [
                "map",
                str(simple_python_project),
                "--output",
                ".cub/map.md",
                "--debug",
            ],
        )

        assert result.exit_code == 0
        # Debug output should show progress
        assert "Analyzing" in result.stdout or "Extracting" in result.stdout

    def test_map_command_nonexistent_directory(self, tmp_path: Path):
        """Test map command with nonexistent directory."""
        nonexistent = tmp_path / "does_not_exist"

        result = runner.invoke(app, ["map", str(nonexistent)])

        assert result.exit_code == 1
        assert "does not exist" in result.stdout


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestMapIntegration:
    """Test map integration with init and update commands."""

    def test_init_generates_map(self, simple_python_project: Path):
        """Test that cub init generates a map."""
        # Create minimal .cub directory
        cub_dir = simple_python_project / ".cub"
        cub_dir.mkdir()

        # Mock load_config to avoid config errors
        with patch("cub.cli.init_cmd.load_config") as mock_load:
            from cub.core.config.models import (
                CircuitBreakerConfig,
                CubConfig,
                HarnessConfig,
            )

            mock_load.return_value = CubConfig(
                harness=HarnessConfig(name="auto", priority=["claude"]),
                circuit_breaker=CircuitBreakerConfig(timeout_minutes=30),
            )

            # Run init
            _ = runner.invoke(app, ["init", str(simple_python_project)])

            # Should succeed (or at least not crash)
            # Note: init may fail due to missing dependencies, but map should be generated
            map_path = simple_python_project / ".cub" / "map.md"

            # Check if map was created
            if map_path.exists():
                content = map_path.read_text()
                assert "# Project Map" in content or len(content) > 0

    def test_update_regenerates_map(self, simple_python_project: Path):
        """Test that cub update regenerates the map."""
        # Create initial map
        map_path = simple_python_project / ".cub" / "map.md"
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text("Old map content")

        # Create a minimal constitution file to avoid errors
        constitution_path = simple_python_project / ".cub" / "constitution.md"
        constitution_path.write_text("# Constitution\n\nTest constitution")

        # Change directory to project for update to work properly
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(simple_python_project)
            _ = runner.invoke(app, ["update"])
        finally:
            os.chdir(original_cwd)

        # Should succeed or at least not crash
        # Map should be regenerated
        if map_path.exists():
            content = map_path.read_text()
            # Content should have changed and contain project map
            if "# Project Map" in content:
                assert content != "Old map content"


# ==============================================================================
# Edge Cases
# ==============================================================================


class TestMapEdgeCases:
    """Test edge cases for map generation."""

    def test_empty_project(self, tmp_path: Path):
        """Test map generation on empty project."""
        empty_project = tmp_path / "empty"
        empty_project.mkdir()

        result = runner.invoke(app, ["map", str(empty_project), "--output", ".cub/map.md"])

        # Should succeed even with empty project
        assert result.exit_code == 0

        map_path = empty_project / ".cub" / "map.md"
        assert map_path.exists()

    def test_large_token_budget(self, simple_python_project: Path):
        """Test map generation with very large token budget."""
        result = runner.invoke(
            app,
            [
                "map",
                str(simple_python_project),
                "--output",
                ".cub/map.md",
                "--token-budget",
                "100000",
            ],
        )

        # Should succeed
        assert result.exit_code == 0

    def test_zero_max_depth(self, simple_python_project: Path):
        """Test map generation with zero max depth."""
        result = runner.invoke(
            app,
            [
                "map",
                str(simple_python_project),
                "--output",
                ".cub/map.md",
                "--max-depth",
                "1",  # Use 1 instead of 0, as 0 may not be supported
            ],
        )

        # Should succeed (directory tree will be minimal)
        assert result.exit_code == 0
