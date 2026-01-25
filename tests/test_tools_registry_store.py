"""
Tests for RegistryStore (load/save/merge).

Tests cover:
- load() with missing and existing files
- save() with directory creation and atomic writes
- merge() with user and project registries
- RegistryStore.user() and RegistryStore.project() factory methods
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.tools.models import (
    AdapterType,
    AuthConfig,
    HTTPConfig,
    Registry,
    ToolConfig,
)
from cub.core.tools.registry import RegistryStore


class TestLoad:
    """Tests for load() method."""

    def test_load_when_file_missing(self, tmp_path: Path) -> None:
        """load() returns empty registry when file doesn't exist."""
        registry_file = tmp_path / "registry.json"
        store = RegistryStore(registry_file)
        registry = store.load()

        assert isinstance(registry, Registry)
        assert registry.version == "1.0.0"
        assert registry.tools == {}

    def test_load_when_directory_missing(self, tmp_path: Path) -> None:
        """load() returns empty registry when directory doesn't exist."""
        non_existent = tmp_path / "nonexistent" / "registry.json"
        store = RegistryStore(non_existent)
        registry = store.load()

        assert isinstance(registry, Registry)
        assert registry.tools == {}

    def test_load_with_empty_registry(self, tmp_path: Path) -> None:
        """load() works with empty registry file."""
        registry_file = tmp_path / "registry.json"
        empty_registry = Registry(version="1.0.0")
        registry_file.write_text(json.dumps(empty_registry.model_dump(), indent=2))

        store = RegistryStore(registry_file)
        loaded = store.load()

        assert loaded.version == "1.0.0"
        assert loaded.tools == {}

    def test_load_with_tools(self, tmp_path: Path) -> None:
        """load() returns populated registry when file exists."""
        tool1 = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search"],
            http_config=HTTPConfig(
                base_url="https://api.brave.com",
                endpoints={"search": "/v1/web/search"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        tool2 = ToolConfig(
            id="gh-cli",
            name="GitHub CLI",
            adapter_type=AdapterType.CLI,
            capabilities=["github"],
            cli_config=None,  # Will fail get_adapter_config but OK for storage
            adopted_at=datetime.now(timezone.utc),
            adopted_from="custom",
        )

        # Create registry with tools dict (not list)
        registry = Registry(
            version="1.2.3",
            tools={
                "brave-search": tool1,
                "gh-cli": tool2,
            },
        )

        registry_file = tmp_path / "registry.json"
        registry_file.write_text(json.dumps(registry.model_dump(mode='json'), indent=2))

        store = RegistryStore(registry_file)
        loaded = store.load()

        assert loaded.version == "1.2.3"
        assert len(loaded.tools) == 2
        assert "brave-search" in loaded.tools
        assert "gh-cli" in loaded.tools
        assert loaded.tools["brave-search"].name == "Brave Search"

    def test_load_with_timestamps(self, tmp_path: Path) -> None:
        """load() preserves timestamps."""
        now = datetime.now(timezone.utc)
        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=now,
            adopted_from="test",
        )
        registry = Registry(version="1.0.0", tools={"test-tool": tool})

        registry_file = tmp_path / "registry.json"
        registry_file.write_text(json.dumps(registry.model_dump(mode='json'), indent=2))

        store = RegistryStore(registry_file)
        loaded = store.load()

        assert loaded.tools["test-tool"].adopted_at is not None
        # Compare timestamps (allowing small precision differences)
        assert abs((loaded.tools["test-tool"].adopted_at - now).total_seconds()) < 1

    def test_load_malformed_json_raises(self, tmp_path: Path) -> None:
        """load() raises on malformed JSON."""
        registry_file = tmp_path / "registry.json"
        registry_file.write_text("{invalid json")

        store = RegistryStore(registry_file)
        with pytest.raises(json.JSONDecodeError):
            store.load()

    def test_load_invalid_schema_raises(self, tmp_path: Path) -> None:
        """load() raises on invalid registry schema."""
        registry_file = tmp_path / "registry.json"
        # Invalid 'tools' field (should be dict, not list)
        registry_file.write_text('{"version": "1.0.0", "tools": []}')

        store = RegistryStore(registry_file)
        with pytest.raises(Exception):  # Pydantic ValidationError
            store.load()


class TestSave:
    """Tests for save() method."""

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """save() creates parent directories if they don't exist."""
        registry_file = tmp_path / "new_dir" / "registry.json"
        assert not registry_file.parent.exists()

        store = RegistryStore(registry_file)
        registry = Registry(version="1.0.0")
        result_path = store.save(registry)

        assert registry_file.parent.exists()
        assert result_path.exists()
        assert result_path == registry_file

    def test_save_writes_valid_json(self, tmp_path: Path) -> None:
        """save() writes valid JSON to registry.json."""
        registry_file = tmp_path / "registry.json"
        store = RegistryStore(registry_file)

        tool = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search"],
            http_config=HTTPConfig(
                base_url="https://api.brave.com",
                endpoints={"search": "/v1/web/search"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        registry = Registry(version="1.0.0", tools={"brave-search": tool})

        result_path = store.save(registry)

        # Verify file exists
        assert result_path.exists()
        assert result_path == registry_file

        # Verify it's valid JSON
        with open(result_path) as f:
            data = json.load(f)
        assert data["version"] == "1.0.0"
        assert "brave-search" in data["tools"]
        assert data["tools"]["brave-search"]["name"] == "Brave Search"

    def test_save_human_readable_formatting(self, tmp_path: Path) -> None:
        """save() uses indented JSON for readability."""
        registry_file = tmp_path / "registry.json"
        store = RegistryStore(registry_file)
        registry = Registry(version="1.0.0", tools={})

        store.save(registry)
        content = registry_file.read_text()

        # Check for indentation (human-readable format)
        assert "  " in content  # Has indentation
        assert "\n" in content  # Has newlines

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """save() overwrites existing registry file."""
        registry_file = tmp_path / "registry.json"
        registry_file.write_text('{"version": "0.0.1", "tools": {}}')

        store = RegistryStore(registry_file)
        new_registry = Registry(version="2.0.0", tools={})
        store.save(new_registry)

        # Verify new content replaced old
        with open(registry_file) as f:
            data = json.load(f)
        assert data["version"] == "2.0.0"

    def test_save_preserves_all_fields(self, tmp_path: Path) -> None:
        """save() preserves all registry and tool fields."""
        registry_file = tmp_path / "registry.json"
        now = datetime.now(timezone.utc)

        tool = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search", "current_events"],
            http_config=HTTPConfig(
                base_url="https://api.brave.com",
                endpoints={"search": "/v1/web/search"},
                headers={"Accept": "application/json"},
                auth_header="X-API-Key",
                auth_env_var="BRAVE_API_KEY",
            ),
            auth=AuthConfig(
                required=True,
                env_var="BRAVE_API_KEY",
                signup_url="https://brave.com/search/api/",
            ),
            adopted_at=now,
            adopted_from="catalog",
            version_hash="abc123",
        )

        registry = Registry(version="1.2.3", tools={"brave-search": tool})

        store = RegistryStore(registry_file)
        store.save(registry)

        # Reload and verify all fields
        loaded = store.load()
        assert loaded.version == "1.2.3"
        assert len(loaded.tools) == 1
        loaded_tool = loaded.tools["brave-search"]
        assert loaded_tool.capabilities == ["web_search", "current_events"]
        assert loaded_tool.version_hash == "abc123"
        assert loaded_tool.auth is not None
        assert loaded_tool.auth.required is True

    def test_save_atomic_write(self, tmp_path: Path) -> None:
        """save() uses atomic write (no partial corruption)."""
        registry_file = tmp_path / "registry.json"
        store = RegistryStore(registry_file)

        # Save once
        registry = Registry(version="1.0.0")
        store.save(registry)
        assert registry_file.exists()

        # Save again - should not leave temp files
        registry2 = Registry(version="2.0.0")
        store.save(registry2)

        # Check no temp files left behind
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_save_returns_path(self, tmp_path: Path) -> None:
        """save() returns path to saved file."""
        registry_file = tmp_path / "registry.json"
        store = RegistryStore(registry_file)
        registry = Registry(version="1.0.0")

        result_path = store.save(registry)

        assert isinstance(result_path, Path)
        assert result_path == registry_file
        assert result_path.exists()


class TestUserFactory:
    """Tests for RegistryStore.user() factory method."""

    def test_user_returns_store(self) -> None:
        """RegistryStore.user() returns RegistryStore instance."""
        store = RegistryStore.user()
        assert isinstance(store, RegistryStore)

    def test_user_uses_config_home_path(self) -> None:
        """RegistryStore.user() uses ~/.config/cub/tools/registry.json."""
        store = RegistryStore.user()
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        expected_file = config_home / "cub" / "tools" / "registry.json"
        assert store.registry_file == expected_file

    def test_user_respects_xdg_config_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RegistryStore.user() respects XDG_CONFIG_HOME environment variable."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        store = RegistryStore.user()
        expected_file = tmp_path / "cub" / "tools" / "registry.json"
        assert store.registry_file == expected_file


class TestProjectFactory:
    """Tests for RegistryStore.project() factory method."""

    def test_project_returns_store(self) -> None:
        """RegistryStore.project() returns RegistryStore instance."""
        store = RegistryStore.project()
        assert isinstance(store, RegistryStore)

    def test_project_uses_cub_tools_path(self) -> None:
        """RegistryStore.project() uses .cub/tools/registry.json."""
        store = RegistryStore.project()
        expected_file = Path.cwd() / ".cub" / "tools" / "registry.json"
        assert store.registry_file == expected_file

    def test_project_with_custom_directory(self, tmp_path: Path) -> None:
        """RegistryStore.project() accepts custom project directory."""
        store = RegistryStore.project(tmp_path)
        expected_file = tmp_path / ".cub" / "tools" / "registry.json"
        assert store.registry_file == expected_file


class TestMerge:
    """Tests for RegistryStore.merge() static method."""

    def test_merge_empty_registries(self) -> None:
        """merge() handles empty registries."""
        user_reg = Registry(version="1.0.0", tools={})
        proj_reg = Registry(version="2.0.0", tools={})

        merged = RegistryStore.merge(user_reg, proj_reg)

        assert merged.version == "2.0.0"  # Uses project version
        assert len(merged.tools) == 0

    def test_merge_user_only_tools(self) -> None:
        """merge() includes tools from user registry when project is empty."""
        tool = ToolConfig(
            id="user-tool",
            name="User Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="user",
        )
        user_reg = Registry(version="1.0.0", tools={"user-tool": tool})
        proj_reg = Registry(version="1.0.0", tools={})

        merged = RegistryStore.merge(user_reg, proj_reg)

        assert len(merged.tools) == 1
        assert "user-tool" in merged.tools
        assert merged.tools["user-tool"].name == "User Tool"

    def test_merge_project_only_tools(self) -> None:
        """merge() includes tools from project registry when user is empty."""
        tool = ToolConfig(
            id="project-tool",
            name="Project Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="project",
        )
        user_reg = Registry(version="1.0.0", tools={})
        proj_reg = Registry(version="2.0.0", tools={"project-tool": tool})

        merged = RegistryStore.merge(user_reg, proj_reg)

        assert merged.version == "2.0.0"  # Uses project version
        assert len(merged.tools) == 1
        assert "project-tool" in merged.tools

    def test_merge_non_overlapping_tools(self) -> None:
        """merge() combines tools from both registries when no conflicts."""
        user_tool = ToolConfig(
            id="user-tool",
            name="User Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.user.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="user",
        )
        proj_tool = ToolConfig(
            id="project-tool",
            name="Project Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.project.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="project",
        )

        user_reg = Registry(version="1.0.0", tools={"user-tool": user_tool})
        proj_reg = Registry(version="2.0.0", tools={"project-tool": proj_tool})

        merged = RegistryStore.merge(user_reg, proj_reg)

        assert len(merged.tools) == 2
        assert "user-tool" in merged.tools
        assert "project-tool" in merged.tools

    def test_merge_project_overrides_user(self) -> None:
        """merge() prefers project tool when both have same ID."""
        user_tool = ToolConfig(
            id="same-tool",
            name="User Version",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.user.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="user",
        )
        proj_tool = ToolConfig(
            id="same-tool",
            name="Project Version",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.project.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="project",
        )

        user_reg = Registry(version="1.0.0", tools={"same-tool": user_tool})
        proj_reg = Registry(version="2.0.0", tools={"same-tool": proj_tool})

        merged = RegistryStore.merge(user_reg, proj_reg)

        assert len(merged.tools) == 1
        assert merged.tools["same-tool"].name == "Project Version"
        assert merged.tools["same-tool"].adopted_from == "project"

    def test_merge_multiple_tools_with_conflicts(self) -> None:
        """merge() handles multiple tools with some conflicts."""
        user_tools = {
            "tool-a": ToolConfig(
                id="tool-a",
                name="User A",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.a.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="user",
            ),
            "tool-b": ToolConfig(
                id="tool-b",
                name="User B",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.b.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="user",
            ),
            "tool-c": ToolConfig(
                id="tool-c",
                name="User C",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.c.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="user",
            ),
        }

        proj_tools = {
            "tool-b": ToolConfig(
                id="tool-b",
                name="Project B",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.projb.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="project",
            ),
            "tool-d": ToolConfig(
                id="tool-d",
                name="Project D",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.d.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="project",
            ),
        }

        user_reg = Registry(version="1.0.0", tools=user_tools)
        proj_reg = Registry(version="2.0.0", tools=proj_tools)

        merged = RegistryStore.merge(user_reg, proj_reg)

        # Should have tool-a (user), tool-b (project), tool-c (user), tool-d (project)
        assert len(merged.tools) == 4
        assert merged.tools["tool-a"].name == "User A"
        assert merged.tools["tool-b"].name == "Project B"  # Project overrides
        assert merged.tools["tool-c"].name == "User C"
        assert merged.tools["tool-d"].name == "Project D"


class TestIntegration:
    """Integration tests for common workflows."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Save and load roundtrip preserves data."""
        registry_file = tmp_path / "registry.json"
        store = RegistryStore(registry_file)

        # Create registry with tools
        tools = {
            "brave-search": ToolConfig(
                id="brave-search",
                name="Brave Search",
                adapter_type=AdapterType.HTTP,
                capabilities=["web_search"],
                http_config=HTTPConfig(
                    base_url="https://api.brave.com",
                    endpoints={"search": "/v1/web/search"},
                ),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="catalog",
            ),
            "gh-cli": ToolConfig(
                id="gh-cli",
                name="GitHub CLI",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.github.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="custom",
            ),
        }
        original = Registry(version="1.0.0", tools=tools)

        # Save
        store.save(original)

        # Load
        loaded = store.load()

        # Verify
        assert loaded.version == original.version
        assert len(loaded.tools) == len(original.tools)
        assert "brave-search" in loaded.tools
        assert "gh-cli" in loaded.tools
        assert loaded.tools["brave-search"].name == "Brave Search"
        assert loaded.tools["gh-cli"].name == "GitHub CLI"

    def test_user_project_merge_workflow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Workflow: load user and project registries, merge them."""
        # Set up temporary directories
        user_config_dir = tmp_path / "user_config"
        project_dir = tmp_path / "project"

        monkeypatch.setenv("XDG_CONFIG_HOME", str(user_config_dir))

        # Create user registry
        user_store = RegistryStore.user()
        user_tool = ToolConfig(
            id="user-tool",
            name="User Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.user.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="user",
        )
        user_registry = Registry(version="1.0.0", tools={"user-tool": user_tool})
        user_store.save(user_registry)

        # Create project registry
        project_store = RegistryStore.project(project_dir)
        proj_tool = ToolConfig(
            id="project-tool",
            name="Project Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.project.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="project",
        )
        proj_registry = Registry(version="1.0.0", tools={"project-tool": proj_tool})
        project_store.save(proj_registry)

        # Load and merge
        user_loaded = user_store.load()
        proj_loaded = project_store.load()
        merged = RegistryStore.merge(user_loaded, proj_loaded)

        # Verify merged result
        assert len(merged.tools) == 2
        assert "user-tool" in merged.tools
        assert "project-tool" in merged.tools

    def test_incremental_updates(self, tmp_path: Path) -> None:
        """Workflow: incrementally update registry."""
        registry_file = tmp_path / "registry.json"
        store = RegistryStore(registry_file)

        # Save initial empty registry
        registry = Registry(version="1.0.0", tools={})
        store.save(registry)

        # Load and add first tool
        registry = store.load()
        registry.add(
            ToolConfig(
                id="tool-1",
                name="Tool 1",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.1.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="catalog",
            )
        )
        store.save(registry)

        # Load and add second tool
        registry = store.load()
        assert len(registry.tools) == 1
        registry.add(
            ToolConfig(
                id="tool-2",
                name="Tool 2",
                adapter_type=AdapterType.HTTP,
                http_config=HTTPConfig(base_url="https://api.2.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="catalog",
            )
        )
        store.save(registry)

        # Verify final state
        registry = store.load()
        assert len(registry.tools) == 2
        assert "tool-1" in registry.tools
        assert "tool-2" in registry.tools
