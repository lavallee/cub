"""
Tests for the project utility module.

Tests cover:
- Project root discovery from various directories
- Different marker file types (.beads, .git, .cub, .cub.json)
- Edge cases like no markers found
"""

import os
from pathlib import Path

import pytest

from cub.utils.project import (
    PROJECT_ROOT_MARKERS,
    find_project_root,
    get_project_root,
)


class TestFindProjectRoot:
    """Tests for find_project_root function."""

    def test_find_from_root_with_beads(self, tmp_path: Path) -> None:
        """Test finding root when .beads/ exists at start directory."""
        (tmp_path / ".beads").mkdir()
        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_find_from_root_with_git(self, tmp_path: Path) -> None:
        """Test finding root when .git/ exists at start directory."""
        (tmp_path / ".git").mkdir()
        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_find_from_root_with_cub_dir(self, tmp_path: Path) -> None:
        """Test finding root when .cub/ exists at start directory."""
        (tmp_path / ".cub").mkdir()
        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_find_from_root_with_cub_json(self, tmp_path: Path) -> None:
        """Test finding root when .cub.json exists at start directory."""
        (tmp_path / ".cub.json").write_text("{}")
        result = find_project_root(tmp_path)
        assert result == tmp_path

    def test_find_from_subdirectory(self, tmp_path: Path) -> None:
        """Test finding root from a subdirectory."""
        (tmp_path / ".beads").mkdir()
        subdir = tmp_path / "src" / "module"
        subdir.mkdir(parents=True)

        result = find_project_root(subdir)
        assert result == tmp_path

    def test_find_from_deeply_nested_directory(self, tmp_path: Path) -> None:
        """Test finding root from a deeply nested directory."""
        (tmp_path / ".git").mkdir()
        deep_subdir = tmp_path / "src" / "app" / "components" / "ui" / "buttons"
        deep_subdir.mkdir(parents=True)

        result = find_project_root(deep_subdir)
        assert result == tmp_path

    def test_returns_none_when_no_markers(self, tmp_path: Path) -> None:
        """Test that None is returned when no markers exist."""
        subdir = tmp_path / "some" / "directory"
        subdir.mkdir(parents=True)

        result = find_project_root(subdir)
        assert result is None

    def test_marker_priority_order(self, tmp_path: Path) -> None:
        """Test that markers are checked in priority order."""
        # Create all markers at the same level
        for marker in PROJECT_ROOT_MARKERS:
            marker_path = tmp_path / marker
            if marker.endswith(".json"):
                marker_path.write_text("{}")
            else:
                marker_path.mkdir()

        subdir = tmp_path / "src"
        subdir.mkdir()

        result = find_project_root(subdir)
        assert result == tmp_path

    def test_finds_closest_root_in_nested_projects(self, tmp_path: Path) -> None:
        """Test that the closest project root is found in nested projects."""
        # Create an outer project
        (tmp_path / ".git").mkdir()

        # Create an inner project
        inner_project = tmp_path / "packages" / "inner"
        inner_project.mkdir(parents=True)
        (inner_project / ".beads").mkdir()

        # Create a subdir in inner project
        inner_subdir = inner_project / "src"
        inner_subdir.mkdir()

        # Should find the inner project root, not the outer one
        result = find_project_root(inner_subdir)
        assert result == inner_project

    def test_uses_cwd_when_start_is_none(self, tmp_path: Path) -> None:
        """Test that current working directory is used when start is None."""
        (tmp_path / ".beads").mkdir()

        original_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = find_project_root()
            assert result == tmp_path
        finally:
            os.chdir(original_dir)

    def test_handles_relative_path_input(self, tmp_path: Path) -> None:
        """Test that relative paths are resolved correctly."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src"
        subdir.mkdir()

        original_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            # Use relative path
            result = find_project_root(Path("src"))
            assert result == tmp_path
        finally:
            os.chdir(original_dir)


class TestGetProjectRoot:
    """Tests for get_project_root function."""

    def test_returns_root_when_found(self, tmp_path: Path) -> None:
        """Test that root is returned when found."""
        (tmp_path / ".beads").mkdir()
        result = get_project_root(tmp_path)
        assert result == tmp_path

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised when root not found."""
        subdir = tmp_path / "no" / "markers" / "here"
        subdir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError) as exc_info:
            get_project_root(subdir)

        # Check error message contains useful info
        assert "Could not find project root" in str(exc_info.value)
        assert str(subdir) in str(exc_info.value)

    def test_error_message_lists_markers(self, tmp_path: Path) -> None:
        """Test that error message lists expected markers."""
        subdir = tmp_path / "empty"
        subdir.mkdir()

        with pytest.raises(FileNotFoundError) as exc_info:
            get_project_root(subdir)

        error_msg = str(exc_info.value)
        # Should mention at least some of the markers
        assert ".beads" in error_msg or ".git" in error_msg


class TestProjectRootMarkers:
    """Tests for PROJECT_ROOT_MARKERS constant."""

    def test_markers_include_beads(self) -> None:
        """Test that .beads is included as a marker."""
        assert ".beads" in PROJECT_ROOT_MARKERS

    def test_markers_include_git(self) -> None:
        """Test that .git is included as a marker."""
        assert ".git" in PROJECT_ROOT_MARKERS

    def test_markers_include_cub(self) -> None:
        """Test that .cub is included as a marker."""
        assert ".cub" in PROJECT_ROOT_MARKERS

    def test_markers_include_cub_json(self) -> None:
        """Test that .cub.json is included as a marker."""
        assert ".cub.json" in PROJECT_ROOT_MARKERS

    def test_beads_has_highest_priority(self) -> None:
        """Test that .beads has highest priority (first in list)."""
        assert PROJECT_ROOT_MARKERS[0] == ".beads"
