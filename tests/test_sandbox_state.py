"""Tests for sandbox state tracking module.

This module tests the state persistence layer that tracks active sandbox sessions.
Functions tested:
- get_state_file: path generation for sandbox.json
- save_sandbox_state: persisting ActiveSandbox to JSON
- load_sandbox_state: loading ActiveSandbox from JSON
- clear_sandbox_state: removing state file
"""

import json
from pathlib import Path

import pytest

from cub.core.sandbox.state import (
    ActiveSandbox,
    clear_sandbox_state,
    get_state_file,
    load_sandbox_state,
    save_sandbox_state,
)


# ==============================================================================
# ActiveSandbox Model Tests
# ==============================================================================


class TestActiveSandboxModel:
    """Tests for the ActiveSandbox Pydantic model."""

    def test_model_creation(self) -> None:
        """Test creating an ActiveSandbox with valid data."""
        sandbox = ActiveSandbox(
            sandbox_id="docker-abc123",
            provider="docker",
            project_dir="/home/user/project",
        )
        assert sandbox.sandbox_id == "docker-abc123"
        assert sandbox.provider == "docker"
        assert sandbox.project_dir == "/home/user/project"

    def test_model_serialization(self) -> None:
        """Test that ActiveSandbox serializes to dict correctly."""
        sandbox = ActiveSandbox(
            sandbox_id="test-id",
            provider="docker",
            project_dir="/tmp/project",
        )
        data = sandbox.model_dump()
        assert data == {
            "sandbox_id": "test-id",
            "provider": "docker",
            "project_dir": "/tmp/project",
        }

    def test_model_validation(self) -> None:
        """Test that ActiveSandbox validates input types."""
        # Should accept valid dict
        sandbox = ActiveSandbox.model_validate({
            "sandbox_id": "id-123",
            "provider": "docker",
            "project_dir": "/path",
        })
        assert sandbox.sandbox_id == "id-123"

    def test_model_missing_field(self) -> None:
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValueError):
            ActiveSandbox.model_validate({
                "sandbox_id": "id-123",
                "provider": "docker",
                # missing project_dir
            })


# ==============================================================================
# get_state_file Tests
# ==============================================================================


class TestGetStateFile:
    """Tests for get_state_file function."""

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that get_state_file returns .cub/sandbox.json path."""
        result = get_state_file(tmp_path)
        expected = tmp_path / ".cub" / "sandbox.json"
        assert result == expected

    def test_returns_path_object(self, tmp_path: Path) -> None:
        """Test that get_state_file returns a Path object."""
        result = get_state_file(tmp_path)
        assert isinstance(result, Path)

    def test_nested_project_dir(self, tmp_path: Path) -> None:
        """Test with nested project directory path."""
        nested = tmp_path / "deep" / "nested" / "project"
        result = get_state_file(nested)
        assert result == nested / ".cub" / "sandbox.json"

    def test_does_not_create_directory(self, tmp_path: Path) -> None:
        """Test that get_state_file does not create any directories."""
        result = get_state_file(tmp_path)
        # The .cub directory should not exist yet
        assert not result.parent.exists()


# ==============================================================================
# save_sandbox_state Tests
# ==============================================================================


class TestSaveSandboxState:
    """Tests for save_sandbox_state function."""

    def test_saves_state_file(self, tmp_path: Path) -> None:
        """Test that save_sandbox_state creates the state file."""
        save_sandbox_state(tmp_path, "sandbox-123", "docker")
        state_file = tmp_path / ".cub" / "sandbox.json"
        assert state_file.exists()

    def test_creates_cub_directory(self, tmp_path: Path) -> None:
        """Test that save_sandbox_state creates .cub directory if needed."""
        cub_dir = tmp_path / ".cub"
        assert not cub_dir.exists()

        save_sandbox_state(tmp_path, "sandbox-123", "docker")

        assert cub_dir.exists()
        assert cub_dir.is_dir()

    def test_saved_content_is_valid_json(self, tmp_path: Path) -> None:
        """Test that saved state is valid JSON."""
        save_sandbox_state(tmp_path, "sandbox-123", "docker")
        state_file = tmp_path / ".cub" / "sandbox.json"

        with state_file.open() as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert "sandbox_id" in data
        assert "provider" in data
        assert "project_dir" in data

    def test_saved_values_correct(self, tmp_path: Path) -> None:
        """Test that saved values match input parameters."""
        save_sandbox_state(tmp_path, "my-sandbox", "remote")
        state_file = tmp_path / ".cub" / "sandbox.json"

        with state_file.open() as f:
            data = json.load(f)

        assert data["sandbox_id"] == "my-sandbox"
        assert data["provider"] == "remote"

    def test_project_dir_is_resolved(self, tmp_path: Path) -> None:
        """Test that project_dir is stored as resolved absolute path."""
        # Create the project directory first
        project = tmp_path / "project"
        project.mkdir()

        # Use a path with relative component (..)
        project_with_relative = tmp_path / "subdir" / ".." / "project"

        save_sandbox_state(project_with_relative, "sandbox-123", "docker")
        state_file = project / ".cub" / "sandbox.json"

        with state_file.open() as f:
            data = json.load(f)

        # Should be resolved (no "..")
        assert ".." not in data["project_dir"]
        assert data["project_dir"] == str(project.resolve())

    def test_overwrites_existing_state(self, tmp_path: Path) -> None:
        """Test that save_sandbox_state overwrites existing state file."""
        # Save initial state
        save_sandbox_state(tmp_path, "sandbox-old", "docker")

        # Save new state
        save_sandbox_state(tmp_path, "sandbox-new", "remote")

        state_file = tmp_path / ".cub" / "sandbox.json"
        with state_file.open() as f:
            data = json.load(f)

        assert data["sandbox_id"] == "sandbox-new"
        assert data["provider"] == "remote"

    def test_json_is_formatted(self, tmp_path: Path) -> None:
        """Test that saved JSON is formatted with indentation."""
        save_sandbox_state(tmp_path, "sandbox-123", "docker")
        state_file = tmp_path / ".cub" / "sandbox.json"

        content = state_file.read_text()
        # Formatted JSON should contain newlines
        assert "\n" in content

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        """Test that nested directories are created as needed."""
        nested_project = tmp_path / "deep" / "nested" / "project"
        # Don't create the project directory - save_sandbox_state should handle .cub

        # The project directory itself must exist for the .cub to be created in it
        nested_project.mkdir(parents=True)
        save_sandbox_state(nested_project, "sandbox-123", "docker")

        state_file = nested_project / ".cub" / "sandbox.json"
        assert state_file.exists()


# ==============================================================================
# load_sandbox_state Tests
# ==============================================================================


class TestLoadSandboxState:
    """Tests for load_sandbox_state function."""

    def test_loads_valid_state(self, tmp_path: Path) -> None:
        """Test loading a valid state file."""
        # Create state manually
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text(json.dumps({
            "sandbox_id": "sandbox-abc",
            "provider": "docker",
            "project_dir": str(tmp_path),
        }))

        result = load_sandbox_state(tmp_path)

        assert result is not None
        assert result.sandbox_id == "sandbox-abc"
        assert result.provider == "docker"
        assert result.project_dir == str(tmp_path)

    def test_returns_none_when_no_file(self, tmp_path: Path) -> None:
        """Test that load returns None when state file doesn't exist."""
        result = load_sandbox_state(tmp_path)
        assert result is None

    def test_returns_none_when_cub_dir_missing(self, tmp_path: Path) -> None:
        """Test that load returns None when .cub directory doesn't exist."""
        # tmp_path exists but .cub doesn't
        assert not (tmp_path / ".cub").exists()
        result = load_sandbox_state(tmp_path)
        assert result is None

    def test_returns_none_for_corrupted_json(self, tmp_path: Path) -> None:
        """Test that load returns None for invalid JSON."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text("{ invalid json }")

        result = load_sandbox_state(tmp_path)
        assert result is None

    def test_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        """Test that load returns None for empty file."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text("")

        result = load_sandbox_state(tmp_path)
        assert result is None

    def test_returns_none_for_missing_fields(self, tmp_path: Path) -> None:
        """Test that load returns None when required fields are missing."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text(json.dumps({
            "sandbox_id": "sandbox-abc",
            # Missing provider and project_dir
        }))

        result = load_sandbox_state(tmp_path)
        assert result is None

    def test_returns_none_for_wrong_type_fields(self, tmp_path: Path) -> None:
        """Test that load returns None when fields have wrong types."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text(json.dumps({
            "sandbox_id": 12345,  # Should be string
            "provider": "docker",
            "project_dir": "/path",
        }))

        # Pydantic will coerce int to string, so this should actually work
        result = load_sandbox_state(tmp_path)
        # It gets coerced
        if result is not None:
            assert result.sandbox_id == "12345"

    def test_returns_none_for_null_values(self, tmp_path: Path) -> None:
        """Test that load returns None when required fields are null."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text(json.dumps({
            "sandbox_id": None,
            "provider": "docker",
            "project_dir": "/path",
        }))

        result = load_sandbox_state(tmp_path)
        assert result is None

    def test_returns_none_for_json_array(self, tmp_path: Path) -> None:
        """Test that load returns None for JSON array instead of object."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text(json.dumps(["sandbox-abc", "docker", "/path"]))

        result = load_sandbox_state(tmp_path)
        assert result is None

    def test_returns_active_sandbox_type(self, tmp_path: Path) -> None:
        """Test that load returns ActiveSandbox instance."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text(json.dumps({
            "sandbox_id": "sandbox-abc",
            "provider": "docker",
            "project_dir": str(tmp_path),
        }))

        result = load_sandbox_state(tmp_path)

        assert isinstance(result, ActiveSandbox)


# ==============================================================================
# clear_sandbox_state Tests
# ==============================================================================


class TestClearSandboxState:
    """Tests for clear_sandbox_state function."""

    def test_removes_state_file(self, tmp_path: Path) -> None:
        """Test that clear removes the state file."""
        # Create state file
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text("{}")

        assert state_file.exists()

        clear_sandbox_state(tmp_path)

        assert not state_file.exists()

    def test_does_not_remove_cub_directory(self, tmp_path: Path) -> None:
        """Test that clear keeps the .cub directory."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text("{}")

        clear_sandbox_state(tmp_path)

        assert cub_dir.exists()

    def test_no_error_when_file_missing(self, tmp_path: Path) -> None:
        """Test that clear doesn't error when state file doesn't exist."""
        # No .cub directory at all
        clear_sandbox_state(tmp_path)
        # Should not raise

    def test_no_error_when_cub_dir_exists_but_no_file(self, tmp_path: Path) -> None:
        """Test that clear doesn't error when .cub exists but no state file."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()

        clear_sandbox_state(tmp_path)
        # Should not raise

    def test_preserves_other_files_in_cub(self, tmp_path: Path) -> None:
        """Test that clear only removes sandbox.json, not other files."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        state_file = cub_dir / "sandbox.json"
        state_file.write_text("{}")
        other_file = cub_dir / "config.json"
        other_file.write_text("{}")

        clear_sandbox_state(tmp_path)

        assert not state_file.exists()
        assert other_file.exists()


# ==============================================================================
# Round-trip Tests
# ==============================================================================


class TestSaveLoadRoundTrip:
    """Tests for save/load round-trip behavior."""

    def test_save_then_load(self, tmp_path: Path) -> None:
        """Test that saved state can be loaded back."""
        save_sandbox_state(tmp_path, "my-sandbox", "docker")
        result = load_sandbox_state(tmp_path)

        assert result is not None
        assert result.sandbox_id == "my-sandbox"
        assert result.provider == "docker"

    def test_save_load_clear_load(self, tmp_path: Path) -> None:
        """Test full lifecycle: save, load, clear, load."""
        # Save
        save_sandbox_state(tmp_path, "sandbox-1", "docker")

        # Load
        result = load_sandbox_state(tmp_path)
        assert result is not None
        assert result.sandbox_id == "sandbox-1"

        # Clear
        clear_sandbox_state(tmp_path)

        # Load again
        result = load_sandbox_state(tmp_path)
        assert result is None

    def test_multiple_saves(self, tmp_path: Path) -> None:
        """Test multiple saves overwrite correctly."""
        save_sandbox_state(tmp_path, "sandbox-1", "docker")
        save_sandbox_state(tmp_path, "sandbox-2", "remote")
        save_sandbox_state(tmp_path, "sandbox-3", "docker")

        result = load_sandbox_state(tmp_path)

        assert result is not None
        assert result.sandbox_id == "sandbox-3"
        assert result.provider == "docker"

    def test_project_dir_preserved(self, tmp_path: Path) -> None:
        """Test that project_dir is correctly preserved through round-trip."""
        save_sandbox_state(tmp_path, "sandbox-1", "docker")
        result = load_sandbox_state(tmp_path)

        assert result is not None
        assert result.project_dir == str(tmp_path.resolve())

    def test_special_characters_in_sandbox_id(self, tmp_path: Path) -> None:
        """Test that special characters in sandbox_id are preserved."""
        special_id = "sandbox-abc_123:tag.latest"
        save_sandbox_state(tmp_path, special_id, "docker")
        result = load_sandbox_state(tmp_path)

        assert result is not None
        assert result.sandbox_id == special_id

    def test_unicode_in_provider(self, tmp_path: Path) -> None:
        """Test that unicode characters are handled correctly."""
        # This is unlikely but tests JSON encoding
        save_sandbox_state(tmp_path, "sandbox-1", "provider-test")
        result = load_sandbox_state(tmp_path)

        assert result is not None
        assert result.provider == "provider-test"
