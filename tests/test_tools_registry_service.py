"""
Tests for RegistryService business logic layer.

Tests cover:
- load() merging user and project registries
- adopt() adding tools to project registry with version_hash generation
- find_by_capability() searching merged registry
- is_approved() checking tool presence
- needs_reapproval() detecting version changes
- remove() removing from project registry
- _generate_version_hash() deterministic hash generation
"""

from datetime import datetime, timezone
from pathlib import Path

from cub.core.tools.models import (
    AdapterType,
    CLIConfig,
    HTTPConfig,
    Registry,
    ToolConfig,
)
from cub.core.tools.registry import RegistryService, RegistryStore


class TestRegistryServiceLoad:
    """Tests for load() method."""

    def test_load_empty_registries(self, tmp_path: Path) -> None:
        """load() returns empty merged registry when both stores are empty."""
        user_store = RegistryStore(tmp_path / "user" / "registry.json")
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(user_store, project_store)

        registry = service.load()

        assert isinstance(registry, Registry)
        assert len(registry.tools) == 0

    def test_load_merges_user_and_project(self, tmp_path: Path) -> None:
        """load() merges user and project registries with project overriding."""
        # Setup user registry
        user_store = RegistryStore(tmp_path / "user" / "registry.json")
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

        # Setup project registry
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        project_tool = ToolConfig(
            id="project-tool",
            name="Project Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.project.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="project",
        )
        project_registry = Registry(version="1.0.0", tools={"project-tool": project_tool})
        project_store.save(project_registry)

        # Load merged
        service = RegistryService(user_store, project_store)
        merged = service.load()

        assert len(merged.tools) == 2
        assert "user-tool" in merged.tools
        assert "project-tool" in merged.tools

    def test_load_project_overrides_user(self, tmp_path: Path) -> None:
        """load() gives project registry priority when IDs conflict."""
        # Setup user registry
        user_store = RegistryStore(tmp_path / "user" / "registry.json")
        user_tool = ToolConfig(
            id="same-tool",
            name="User Version",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.user.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="user",
        )
        user_registry = Registry(version="1.0.0", tools={"same-tool": user_tool})
        user_store.save(user_registry)

        # Setup project registry with same tool ID
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        project_tool = ToolConfig(
            id="same-tool",
            name="Project Version",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.project.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="project",
        )
        project_registry = Registry(version="1.0.0", tools={"same-tool": project_tool})
        project_store.save(project_registry)

        # Load merged
        service = RegistryService(user_store, project_store)
        merged = service.load()

        assert len(merged.tools) == 1
        assert merged.tools["same-tool"].name == "Project Version"
        assert merged.tools["same-tool"].adopted_from == "project"


class TestRegistryServiceAdopt:
    """Tests for adopt() method."""

    def test_adopt_adds_tool_to_project_registry(self, tmp_path: Path) -> None:
        """adopt() adds tool to project registry and saves."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        tool_config = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(
                base_url="https://api.brave.com",
                endpoints={"search": "/v1/web/search"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )

        adopted = service.adopt(tool_config)

        # Verify tool was adopted
        assert adopted.id == "brave-search"
        assert adopted.version_hash is not None

        # Verify it was saved to project registry
        loaded_registry = project_store.load()
        assert "brave-search" in loaded_registry.tools

    def test_adopt_generates_version_hash_if_missing(self, tmp_path: Path) -> None:
        """adopt() generates version_hash if not already present."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        tool_config = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
            version_hash=None,
        )

        adopted = service.adopt(tool_config)

        assert adopted.version_hash is not None
        assert len(adopted.version_hash) == 64  # SHA256 hex string length

    def test_adopt_preserves_existing_version_hash(self, tmp_path: Path) -> None:
        """adopt() preserves version_hash if already set."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        existing_hash = "abc123def456"
        tool_config = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
            version_hash=existing_hash,
        )

        adopted = service.adopt(tool_config)

        assert adopted.version_hash == existing_hash

    def test_adopt_updates_adopted_at_timestamp(self, tmp_path: Path) -> None:
        """adopt() updates adopted_at to current time."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        old_timestamp = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        tool_config = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=old_timestamp,
            adopted_from="test",
        )

        before_adopt = datetime.now(timezone.utc)
        adopted = service.adopt(tool_config)
        after_adopt = datetime.now(timezone.utc)

        # adopted_at should be updated to current time
        assert adopted.adopted_at >= before_adopt
        assert adopted.adopted_at <= after_adopt
        assert adopted.adopted_at != old_timestamp


class TestRegistryServiceFindByCapability:
    """Tests for find_by_capability() method."""

    def test_find_by_capability_returns_matching_tools(self, tmp_path: Path) -> None:
        """find_by_capability() returns tools with matching capability."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Adopt tools with different capabilities
        tool1 = ToolConfig(
            id="tool-1",
            name="Tool 1",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search", "current_events"],
            http_config=HTTPConfig(base_url="https://api.1.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        tool2 = ToolConfig(
            id="tool-2",
            name="Tool 2",
            adapter_type=AdapterType.HTTP,
            capabilities=["database", "query"],
            http_config=HTTPConfig(base_url="https://api.2.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        tool3 = ToolConfig(
            id="tool-3",
            name="Tool 3",
            adapter_type=AdapterType.HTTP,
            capabilities=["web_search", "database"],
            http_config=HTTPConfig(base_url="https://api.3.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )

        service.adopt(tool1)
        service.adopt(tool2)
        service.adopt(tool3)

        # Search for "web_search"
        found = service.find_by_capability("web_search")
        assert len(found) == 2
        assert set(t.id for t in found) == {"tool-1", "tool-3"}

    def test_find_by_capability_returns_empty_for_no_matches(
        self, tmp_path: Path
    ) -> None:
        """find_by_capability() returns empty list when no tools match."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            capabilities=["search"],
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        service.adopt(tool)

        found = service.find_by_capability("nonexistent")
        assert len(found) == 0

    def test_find_by_capability_searches_merged_registry(self, tmp_path: Path) -> None:
        """find_by_capability() searches both user and project registries."""
        # Setup user registry with one tool
        user_store = RegistryStore(tmp_path / "user" / "registry.json")
        user_tool = ToolConfig(
            id="user-tool",
            name="User Tool",
            adapter_type=AdapterType.HTTP,
            capabilities=["search"],
            http_config=HTTPConfig(base_url="https://api.user.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="user",
        )
        user_registry = Registry(version="1.0.0", tools={"user-tool": user_tool})
        user_store.save(user_registry)

        # Setup project registry with another tool
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        project_tool = ToolConfig(
            id="project-tool",
            name="Project Tool",
            adapter_type=AdapterType.HTTP,
            capabilities=["search"],
            http_config=HTTPConfig(base_url="https://api.project.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="project",
        )
        project_registry = Registry(version="1.0.0", tools={"project-tool": project_tool})
        project_store.save(project_registry)

        # Search should find both
        service = RegistryService(user_store, project_store)
        found = service.find_by_capability("search")

        assert len(found) == 2
        assert set(t.id for t in found) == {"user-tool", "project-tool"}


class TestRegistryServiceIsApproved:
    """Tests for is_approved() method."""

    def test_is_approved_returns_true_for_existing_tool(self, tmp_path: Path) -> None:
        """is_approved() returns True if tool exists in registry."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        tool = ToolConfig(
            id="approved-tool",
            name="Approved Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        service.adopt(tool)

        assert service.is_approved("approved-tool") is True

    def test_is_approved_returns_false_for_nonexistent_tool(
        self, tmp_path: Path
    ) -> None:
        """is_approved() returns False if tool doesn't exist in registry."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        assert service.is_approved("nonexistent-tool") is False

    def test_is_approved_checks_both_user_and_project(self, tmp_path: Path) -> None:
        """is_approved() returns True if tool is in either user or project registry."""
        # Setup user registry
        user_store = RegistryStore(tmp_path / "user" / "registry.json")
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

        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(user_store, project_store)

        # Tool only in user registry, should still be approved
        assert service.is_approved("user-tool") is True


class TestRegistryServiceNeedsReapproval:
    """Tests for needs_reapproval() method."""

    def test_needs_reapproval_returns_false_for_matching_hash(
        self, tmp_path: Path
    ) -> None:
        """needs_reapproval() returns False when hash matches."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        adopted = service.adopt(tool)

        # Use the same hash
        assert service.needs_reapproval("test-tool", adopted.version_hash or "") is False

    def test_needs_reapproval_returns_true_for_different_hash(
        self, tmp_path: Path
    ) -> None:
        """needs_reapproval() returns True when hash differs."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        service.adopt(tool)

        # Use a different hash
        different_hash = "different123"
        assert service.needs_reapproval("test-tool", different_hash) is True

    def test_needs_reapproval_returns_true_for_missing_tool(
        self, tmp_path: Path
    ) -> None:
        """needs_reapproval() returns True if tool not in registry."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        assert service.needs_reapproval("nonexistent-tool", "any-hash") is True

    def test_needs_reapproval_returns_true_for_missing_version_hash(
        self, tmp_path: Path
    ) -> None:
        """needs_reapproval() returns True if tool has no version_hash."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        # Save a tool directly without using adopt() to skip hash generation
        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
            version_hash=None,
        )
        registry = Registry(version="1.0.0", tools={"test-tool": tool})
        project_store.save(registry)

        service = RegistryService(project_store=project_store)
        assert service.needs_reapproval("test-tool", "any-hash") is True


class TestRegistryServiceRemove:
    """Tests for remove() method."""

    def test_remove_deletes_tool_from_project_registry(self, tmp_path: Path) -> None:
        """remove() deletes tool from project registry and saves."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        service.adopt(tool)

        # Verify it was added
        assert service.is_approved("test-tool") is True

        # Remove it
        removed = service.remove("test-tool")
        assert removed is True

        # Verify it's gone
        assert service.is_approved("test-tool") is False

    def test_remove_returns_false_for_nonexistent_tool(self, tmp_path: Path) -> None:
        """remove() returns False if tool not found."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        removed = service.remove("nonexistent-tool")
        assert removed is False

    def test_remove_only_affects_project_registry(self, tmp_path: Path) -> None:
        """remove() only removes from project registry, not user registry."""
        # Setup user registry
        user_store = RegistryStore(tmp_path / "user" / "registry.json")
        user_tool = ToolConfig(
            id="shared-tool",
            name="User Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.user.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="user",
        )
        user_registry = Registry(version="1.0.0", tools={"shared-tool": user_tool})
        user_store.save(user_registry)

        # Setup project registry with same tool
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        project_tool = ToolConfig(
            id="shared-tool",
            name="Project Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.project.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="project",
        )
        project_registry = Registry(version="1.0.0", tools={"shared-tool": project_tool})
        project_store.save(project_registry)

        # Remove from project
        service = RegistryService(user_store, project_store)
        removed = service.remove("shared-tool")
        assert removed is True

        # Tool should still exist in merged registry (from user)
        assert service.is_approved("shared-tool") is True

        # But project registry should be empty
        project_loaded = project_store.load()
        assert "shared-tool" not in project_loaded.tools


class TestRegistryServiceGenerateVersionHash:
    """Tests for _generate_version_hash() method."""

    def test_generate_version_hash_produces_sha256(self, tmp_path: Path) -> None:
        """_generate_version_hash() returns SHA256 hex string."""
        service = RegistryService()

        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )

        hash_value = service._generate_version_hash(tool)

        # SHA256 hex string is 64 characters
        assert len(hash_value) == 64
        # Should be hex (all chars in 0-9a-f)
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_generate_version_hash_is_deterministic(self, tmp_path: Path) -> None:
        """_generate_version_hash() produces same hash for same tool."""
        service = RegistryService()

        tool1 = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(
                base_url="https://api.test.com",
                endpoints={"search": "/search"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        tool2 = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(
                base_url="https://api.test.com",
                endpoints={"search": "/search"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )

        hash1 = service._generate_version_hash(tool1)
        hash2 = service._generate_version_hash(tool2)

        assert hash1 == hash2

    def test_generate_version_hash_differs_for_different_tools(
        self, tmp_path: Path
    ) -> None:
        """_generate_version_hash() produces different hashes for different tools."""
        service = RegistryService()

        tool1 = ToolConfig(
            id="test-tool-1",
            name="Test Tool 1",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test1.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        tool2 = ToolConfig(
            id="test-tool-2",
            name="Test Tool 2",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test2.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )

        hash1 = service._generate_version_hash(tool1)
        hash2 = service._generate_version_hash(tool2)

        assert hash1 != hash2

    def test_generate_version_hash_includes_adapter_config(self, tmp_path: Path) -> None:
        """_generate_version_hash() changes when adapter config changes."""
        service = RegistryService()

        tool1 = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(
                base_url="https://api.test.com",
                endpoints={"search": "/v1/search"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        tool2 = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(
                base_url="https://api.test.com",
                endpoints={"search": "/v2/search"},  # Different endpoint
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )

        hash1 = service._generate_version_hash(tool1)
        hash2 = service._generate_version_hash(tool2)

        assert hash1 != hash2

    def test_generate_version_hash_for_cli_tool(self, tmp_path: Path) -> None:
        """_generate_version_hash() works for CLI tools."""
        service = RegistryService()

        tool = ToolConfig(
            id="gh-cli",
            name="GitHub CLI",
            adapter_type=AdapterType.CLI,
            cli_config=CLIConfig(
                command="gh",
                args_template="{action} {params}",
                output_format="json",
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="custom",
        )

        hash_value = service._generate_version_hash(tool)

        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestRegistryServiceIntegration:
    """Integration tests for common workflows."""

    def test_adopt_and_approve_workflow(self, tmp_path: Path) -> None:
        """Workflow: adopt tool, verify approval, check re-approval."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Initially not approved
        assert service.is_approved("brave-search") is False

        # Adopt tool
        tool = ToolConfig(
            id="brave-search",
            name="Brave Search",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(
                base_url="https://api.brave.com",
                endpoints={"search": "/v1/web/search"},
            ),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="catalog",
        )
        adopted = service.adopt(tool)

        # Now approved
        assert service.is_approved("brave-search") is True

        # Same hash doesn't need re-approval
        assert service.needs_reapproval("brave-search", adopted.version_hash or "") is False

        # Different hash needs re-approval
        assert service.needs_reapproval("brave-search", "different-hash") is True

    def test_capability_search_across_multiple_tools(self, tmp_path: Path) -> None:
        """Workflow: adopt multiple tools and search by capability."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Adopt multiple tools
        tools = [
            ToolConfig(
                id="brave-search",
                name="Brave Search",
                adapter_type=AdapterType.HTTP,
                capabilities=["web_search", "current_events"],
                http_config=HTTPConfig(base_url="https://api.brave.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="catalog",
            ),
            ToolConfig(
                id="postgres-cli",
                name="PostgreSQL CLI",
                adapter_type=AdapterType.CLI,
                capabilities=["database", "query"],
                cli_config=CLIConfig(command="psql"),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="custom",
            ),
            ToolConfig(
                id="duckduckgo",
                name="DuckDuckGo Search",
                adapter_type=AdapterType.HTTP,
                capabilities=["web_search"],
                http_config=HTTPConfig(base_url="https://api.duckduckgo.com", endpoints={}),
                adopted_at=datetime.now(timezone.utc),
                adopted_from="catalog",
            ),
        ]

        for tool in tools:
            service.adopt(tool)

        # Search for web_search capability
        search_tools = service.find_by_capability("web_search")
        assert len(search_tools) == 2
        assert set(t.id for t in search_tools) == {"brave-search", "duckduckgo"}

        # Search for database capability
        db_tools = service.find_by_capability("database")
        assert len(db_tools) == 1
        assert db_tools[0].id == "postgres-cli"

    def test_remove_and_re_adopt_workflow(self, tmp_path: Path) -> None:
        """Workflow: adopt, remove, re-adopt tool."""
        project_store = RegistryStore(tmp_path / "project" / "registry.json")
        service = RegistryService(project_store=project_store)

        # Adopt tool
        tool = ToolConfig(
            id="test-tool",
            name="Test Tool",
            adapter_type=AdapterType.HTTP,
            http_config=HTTPConfig(base_url="https://api.test.com", endpoints={}),
            adopted_at=datetime.now(timezone.utc),
            adopted_from="test",
        )
        first_adoption = service.adopt(tool)
        first_hash = first_adoption.version_hash

        # Verify approved
        assert service.is_approved("test-tool") is True

        # Remove
        removed = service.remove("test-tool")
        assert removed is True
        assert service.is_approved("test-tool") is False

        # Re-adopt (should generate new hash with updated timestamp)
        second_adoption = service.adopt(tool)
        assert service.is_approved("test-tool") is True
        # Hash should be the same (same tool config)
        assert second_adoption.version_hash == first_hash
