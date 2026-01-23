"""
Tests for view configuration loader.

Tests validate:
- Loading built-in default views
- Loading custom views from .cub/views/
- YAML parsing and validation
- Cache invalidation
- Error handling for invalid configurations
- Integration with API endpoints
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from cub.core.dashboard.db.models import Stage, ViewConfig, ViewSummary
from cub.core.dashboard.views import get_view_config, list_views
from cub.core.dashboard.views.defaults import (
    get_built_in_view_summaries,
    get_built_in_views,
    get_default_view,
    get_ideas_view,
    get_sprint_view,
)
from cub.core.dashboard.views.loader import (
    get_views_directory,
    invalidate_cache,
    load_all_views,
    load_custom_views,
    load_view_from_yaml,
)


class TestBuiltInViews:
    """Tests for built-in default views."""

    def test_get_default_view(self):
        """Test that default view is properly configured."""
        view = get_default_view()

        assert view.id == "default"
        assert view.name == "Full Workflow"
        assert view.is_default is True
        assert len(view.columns) == 8
        assert view.filters is not None
        assert view.display is not None

    def test_get_sprint_view(self):
        """Test that sprint view is properly configured."""
        view = get_sprint_view()

        assert view.id == "sprint"
        assert view.name == "Sprint View"
        assert view.is_default is False
        assert len(view.columns) == 4
        # Should have Ready, In Progress, Needs Review, Complete
        column_stages = [col.stages[0] for col in view.columns]
        assert Stage.READY in column_stages
        assert Stage.IN_PROGRESS in column_stages
        assert Stage.NEEDS_REVIEW in column_stages
        assert Stage.COMPLETE in column_stages

    def test_get_ideas_view(self):
        """Test that ideas view is properly configured."""
        view = get_ideas_view()

        assert view.id == "ideas"
        assert view.name == "Ideas View"
        assert view.is_default is False
        assert len(view.columns) == 3
        # Should have Captures, Specs, Planned
        column_stages = [col.stages[0] for col in view.columns]
        assert Stage.CAPTURES in column_stages
        assert Stage.SPECS in column_stages
        assert Stage.PLANNED in column_stages

    def test_get_built_in_views(self):
        """Test that all built-in views are returned."""
        views = get_built_in_views()

        assert isinstance(views, dict)
        assert len(views) == 3
        assert "default" in views
        assert "sprint" in views
        assert "ideas" in views

        # Verify all are ViewConfig instances
        for view_id, view in views.items():
            assert isinstance(view, ViewConfig)
            assert view.id == view_id

    def test_get_built_in_view_summaries(self):
        """Test that view summaries are returned."""
        summaries = get_built_in_view_summaries()

        assert isinstance(summaries, list)
        assert len(summaries) == 3

        # Should have exactly one default
        default_count = sum(1 for s in summaries if s.is_default)
        assert default_count == 1

        # Verify all are ViewSummary instances
        for summary in summaries:
            assert isinstance(summary, ViewSummary)
            assert summary.id
            assert summary.name


class TestViewLoader:
    """Tests for view loader functionality."""

    def test_get_views_directory(self):
        """Test that views directory path is correct."""
        views_dir = get_views_directory()

        assert isinstance(views_dir, Path)
        assert str(views_dir).endswith(".cub/views")

    def test_load_all_views_returns_defaults(self):
        """Test that load_all_views returns at least built-in views."""
        views = load_all_views(use_cache=False)

        assert isinstance(views, dict)
        assert len(views) >= 3
        assert "default" in views
        assert "sprint" in views
        assert "ideas" in views

    def test_load_all_views_caching(self):
        """Test that view caching works."""
        # Clear cache first
        invalidate_cache()

        # First load
        views1 = load_all_views(use_cache=True)

        # Second load should use cache
        views2 = load_all_views(use_cache=True)

        assert views1.keys() == views2.keys()

    def test_invalidate_cache(self):
        """Test that cache invalidation works."""
        # Load views to populate cache
        load_all_views(use_cache=True)

        # Invalidate cache
        invalidate_cache()

        # This should reload from disk
        views = load_all_views(use_cache=True)
        assert len(views) >= 3

    def test_get_view_config_default(self):
        """Test getting default view config."""
        view = get_view_config("default", use_cache=False)

        assert view is not None
        assert view.id == "default"
        assert view.is_default is True

    def test_get_view_config_sprint(self):
        """Test getting sprint view config."""
        view = get_view_config("sprint", use_cache=False)

        assert view is not None
        assert view.id == "sprint"
        assert view.is_default is False

    def test_get_view_config_nonexistent(self):
        """Test getting nonexistent view returns None."""
        view = get_view_config("nonexistent", use_cache=False)

        assert view is None

    def test_list_views(self):
        """Test listing all views."""
        summaries = list_views(use_cache=False)

        assert isinstance(summaries, list)
        assert len(summaries) >= 3

        # Should be sorted by name
        names = [s.name for s in summaries]
        assert names == sorted(names)

        # Should have exactly one default
        default_count = sum(1 for s in summaries if s.is_default)
        assert default_count == 1


class TestCustomViewLoading:
    """Tests for loading custom views from YAML files."""

    def test_load_view_from_yaml_valid(self, tmp_path, monkeypatch):
        """Test loading a valid custom view from YAML."""
        # Create a custom view YAML file
        view_data = {
            "id": "custom",
            "name": "Custom View",
            "description": "A custom view for testing",
            "is_default": False,
            "columns": [
                {
                    "id": "ready",
                    "title": "Ready",
                    "stages": ["READY"],
                },
                {
                    "id": "in_progress",
                    "title": "In Progress",
                    "stages": ["IN_PROGRESS"],
                },
            ],
            "filters": {
                "exclude_labels": ["archived"],
            },
            "display": {
                "show_cost": True,
                "show_tokens": False,
            },
        }

        yaml_file = tmp_path / "custom.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(view_data, f)

        # Load the view
        view = load_view_from_yaml(yaml_file)

        assert view is not None
        assert view.id == "custom"
        assert view.name == "Custom View"
        assert len(view.columns) == 2

    def test_load_view_from_yaml_invalid_structure(self, tmp_path):
        """Test loading YAML with invalid structure."""
        yaml_file = tmp_path / "invalid.yaml"
        with open(yaml_file, "w") as f:
            f.write("- not a dict\n- invalid structure")

        view = load_view_from_yaml(yaml_file)
        assert view is None

    def test_load_view_from_yaml_missing_required_fields(self, tmp_path):
        """Test loading YAML missing required fields."""
        view_data = {
            "id": "incomplete",
            # Missing 'name' and 'columns'
        }

        yaml_file = tmp_path / "incomplete.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(view_data, f)

        view = load_view_from_yaml(yaml_file)
        assert view is None

    def test_load_view_from_yaml_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML syntax."""
        yaml_file = tmp_path / "bad.yaml"
        with open(yaml_file, "w") as f:
            f.write("{\ninvalid: yaml: syntax:\n")

        view = load_view_from_yaml(yaml_file)
        assert view is None

    def test_load_view_from_yaml_nonexistent(self, tmp_path):
        """Test loading from nonexistent file."""
        yaml_file = tmp_path / "nonexistent.yaml"

        view = load_view_from_yaml(yaml_file)
        assert view is None

    def test_load_custom_views_no_directory(self, tmp_path, monkeypatch):
        """Test loading custom views when directory doesn't exist."""
        # Monkeypatch the views directory to a nonexistent location
        monkeypatch.setattr(
            "cub.core.dashboard.views.loader.get_views_directory",
            lambda: tmp_path / "nonexistent",
        )

        views = load_custom_views()
        assert isinstance(views, dict)
        assert len(views) == 0

    def test_load_custom_views_with_valid_files(self, tmp_path, monkeypatch):
        """Test loading custom views from directory with valid files."""
        views_dir = tmp_path / ".cub" / "views"
        views_dir.mkdir(parents=True)

        # Monkeypatch the views directory
        monkeypatch.setattr(
            "cub.core.dashboard.views.loader.get_views_directory",
            lambda: views_dir,
        )

        # Create two custom view files
        view1_data = {
            "id": "custom1",
            "name": "Custom View 1",
            "description": "First custom view",
            "is_default": False,
            "columns": [
                {"id": "ready", "title": "Ready", "stages": ["READY"]},
            ],
        }

        view2_data = {
            "id": "custom2",
            "name": "Custom View 2",
            "description": "Second custom view",
            "is_default": False,
            "columns": [
                {"id": "in_progress", "title": "In Progress", "stages": ["IN_PROGRESS"]},
            ],
        }

        with open(views_dir / "custom1.yaml", "w") as f:
            yaml.dump(view1_data, f)

        with open(views_dir / "custom2.yml", "w") as f:
            yaml.dump(view2_data, f)

        # Load custom views
        invalidate_cache()
        views = load_custom_views()

        assert len(views) == 2
        assert "custom1" in views
        assert "custom2" in views

    def test_load_custom_views_skips_invalid(self, tmp_path, monkeypatch):
        """Test that invalid custom views are skipped."""
        views_dir = tmp_path / ".cub" / "views"
        views_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "cub.core.dashboard.views.loader.get_views_directory",
            lambda: views_dir,
        )

        # Create one valid and one invalid view
        valid_data = {
            "id": "valid",
            "name": "Valid View",
            "columns": [
                {"id": "ready", "title": "Ready", "stages": ["READY"]},
            ],
        }

        with open(views_dir / "valid.yaml", "w") as f:
            yaml.dump(valid_data, f)

        with open(views_dir / "invalid.yaml", "w") as f:
            f.write("invalid: yaml: {{{")

        # Load custom views
        invalidate_cache()
        views = load_custom_views()

        # Should load only the valid one
        assert len(views) == 1
        assert "valid" in views

    def test_custom_views_override_built_in(self, tmp_path, monkeypatch):
        """Test that custom views can override built-in views."""
        views_dir = tmp_path / ".cub" / "views"
        views_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "cub.core.dashboard.views.loader.get_views_directory",
            lambda: views_dir,
        )

        # Create a custom view with ID "default" to override built-in
        custom_default = {
            "id": "default",
            "name": "Custom Default View",
            "description": "Overriding the built-in default",
            "is_default": True,
            "columns": [
                {"id": "ready", "title": "Ready", "stages": ["READY"]},
            ],
        }

        with open(views_dir / "default.yaml", "w") as f:
            yaml.dump(custom_default, f)

        # Load all views
        invalidate_cache()
        views = load_all_views(use_cache=False)

        # Should have custom default
        assert "default" in views
        assert views["default"].name == "Custom Default View"
        assert len(views["default"].columns) == 1


class TestViewLoaderIntegration:
    """Integration tests for view loader with API."""

    def test_api_uses_view_loader(self):
        """Test that API endpoints use the view loader."""
        from fastapi.testclient import TestClient

        from cub.core.dashboard.api.app import app

        client = TestClient(app)

        response = client.get("/api/views")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 3

        # Should have default, sprint, and ideas
        view_ids = [v["id"] for v in data]
        assert "default" in view_ids
        assert "sprint" in view_ids
        assert "ideas" in view_ids

    def test_board_uses_view_loader(self):
        """Test that board endpoint uses view loader for default view."""
        from fastapi.testclient import TestClient

        from cub.core.dashboard.api.app import app

        client = TestClient(app)

        # Get board (may be empty if no database exists)
        response = client.get("/api/board")
        assert response.status_code == 200

        data = response.json()
        assert "view" in data
        assert data["view"]["id"] == "default"


class TestViewLoaderEdgeCases:
    """Tests for edge cases in view loader."""

    def test_yaml_with_unicode_characters(self, tmp_path, monkeypatch):
        """Test loading YAML with unicode characters."""
        views_dir = tmp_path / ".cub" / "views"
        views_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "cub.core.dashboard.views.loader.get_views_directory",
            lambda: views_dir,
        )

        view_data = {
            "id": "unicode",
            "name": "View with 日本語 and émojis 🚀",
            "description": "Testing unicode support",
            "columns": [
                {"id": "ready", "title": "Ready", "stages": ["READY"]},
            ],
        }

        with open(views_dir / "unicode.yaml", "w", encoding="utf-8") as f:
            yaml.dump(view_data, f, allow_unicode=True)

        invalidate_cache()
        views = load_custom_views()

        assert "unicode" in views
        assert "日本語" in views["unicode"].name
        assert "🚀" in views["unicode"].name

    def test_duplicate_view_ids(self, tmp_path, monkeypatch):
        """Test that duplicate view IDs are handled (last one wins)."""
        views_dir = tmp_path / ".cub" / "views"
        views_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "cub.core.dashboard.views.loader.get_views_directory",
            lambda: views_dir,
        )

        # Create two files with same ID
        view1 = {
            "id": "duplicate",
            "name": "First Version",
            "columns": [
                {"id": "ready", "title": "Ready", "stages": ["READY"]},
            ],
        }

        view2 = {
            "id": "duplicate",
            "name": "Second Version",
            "columns": [
                {"id": "in_progress", "title": "In Progress", "stages": ["IN_PROGRESS"]},
            ],
        }

        with open(views_dir / "dup1.yaml", "w") as f:
            yaml.dump(view1, f)

        with open(views_dir / "dup2.yaml", "w") as f:
            yaml.dump(view2, f)

        invalidate_cache()
        views = load_custom_views()

        # Should have only one with ID "duplicate"
        assert len([v for v in views.values() if v.id == "duplicate"]) == 1

    def test_empty_views_directory(self, tmp_path, monkeypatch):
        """Test loading from empty views directory."""
        views_dir = tmp_path / ".cub" / "views"
        views_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "cub.core.dashboard.views.loader.get_views_directory",
            lambda: views_dir,
        )

        invalidate_cache()
        views = load_custom_views()

        assert isinstance(views, dict)
        assert len(views) == 0

    def test_view_with_all_optional_fields(self, tmp_path, monkeypatch):
        """Test loading view with all optional fields populated."""
        views_dir = tmp_path / ".cub" / "views"
        views_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "cub.core.dashboard.views.loader.get_views_directory",
            lambda: views_dir,
        )

        view_data = {
            "id": "complete",
            "name": "Complete View",
            "description": "View with all fields",
            "is_default": False,
            "columns": [
                {
                    "id": "grouped",
                    "title": "Grouped Column",
                    "stages": ["IN_PROGRESS"],
                    "group_by": "epic_id",
                },
            ],
            "filters": {
                "exclude_labels": ["archived", "wontfix"],
                "include_labels": ["p0"],
                "exclude_types": ["capture"],
                "include_types": ["task", "epic"],
                "min_priority": 0,
                "max_priority": 2,
            },
            "display": {
                "show_cost": True,
                "show_tokens": True,
                "show_duration": True,
                "card_size": "detailed",
                "group_collapsed": True,
            },
        }

        with open(views_dir / "complete.yaml", "w") as f:
            yaml.dump(view_data, f)

        invalidate_cache()
        views = load_custom_views()

        assert "complete" in views
        view = views["complete"]
        assert view.columns[0].group_by == "epic_id"
        assert view.filters is not None
        assert view.filters.min_priority == 0
        assert view.filters.max_priority == 2
        assert view.display is not None
        assert view.display.card_size == "detailed"
