"""
Tests for constitution management module.
"""

from pathlib import Path

import pytest

from cub.core.constitution import ensure_constitution, read_constitution


class TestEnsureConstitution:
    """Tests for ensure_constitution function."""

    def test_creates_when_missing(self, tmp_path: Path) -> None:
        """Test that constitution is created when it doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = ensure_constitution(project_dir)

        assert result == project_dir / ".cub" / "constitution.md"
        assert result.exists()

        # Verify content was copied from template
        content = result.read_text()
        assert "A constitution for developing software with AI" in content
        assert "Serve, don't extract" in content

    def test_creates_cub_dir_if_missing(self, tmp_path: Path) -> None:
        """Test that .cub/ directory is created if it doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = ensure_constitution(project_dir)

        assert (project_dir / ".cub").exists()
        assert result.exists()

    def test_skips_when_exists(self, tmp_path: Path) -> None:
        """Test that existing constitution is not overwritten by default."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        cub_dir = project_dir / ".cub"
        cub_dir.mkdir()

        constitution_path = cub_dir / "constitution.md"
        original_content = "# Custom Constitution\n\nMy own rules."
        constitution_path.write_text(original_content)

        result = ensure_constitution(project_dir)

        assert result == constitution_path
        assert result.read_text() == original_content

    def test_overwrites_with_force(self, tmp_path: Path) -> None:
        """Test that force=True overwrites existing constitution."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        cub_dir = project_dir / ".cub"
        cub_dir.mkdir()

        constitution_path = cub_dir / "constitution.md"
        original_content = "# Custom Constitution\n\nMy own rules."
        constitution_path.write_text(original_content)

        result = ensure_constitution(project_dir, force=True)

        assert result == constitution_path
        # Should now contain template content
        content = result.read_text()
        assert content != original_content
        assert "A constitution for developing software with AI" in content

    def test_raises_if_template_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that FileNotFoundError is raised if template is missing."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Mock _find_templates_dir to return a directory without constitution.md
        empty_templates = tmp_path / "empty_templates"
        empty_templates.mkdir()

        import cub.core.constitution as const_mod
        monkeypatch.setattr(const_mod, "_find_templates_dir", lambda: empty_templates)

        with pytest.raises(FileNotFoundError, match="Constitution template not found"):
            ensure_constitution(project_dir)


class TestReadConstitution:
    """Tests for read_constitution function."""

    def test_returns_content_when_exists(self, tmp_path: Path) -> None:
        """Test that constitution content is returned when it exists."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        cub_dir = project_dir / ".cub"
        cub_dir.mkdir()

        constitution_path = cub_dir / "constitution.md"
        content = "# My Constitution\n\n1. First rule\n2. Second rule"
        constitution_path.write_text(content)

        result = read_constitution(project_dir)

        assert result == content

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        """Test that None is returned when constitution doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = read_constitution(project_dir)

        assert result is None

    def test_returns_none_when_cub_dir_missing(self, tmp_path: Path) -> None:
        """Test that None is returned when .cub/ directory doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = read_constitution(project_dir)

        assert result is None
