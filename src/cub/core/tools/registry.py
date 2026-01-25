"""
Registry storage layer for reading/writing tool registries.

Manages tool registries at user-level (~/.config/cub/tools/registry.json)
and project-level (.cub/tools/registry.json). Provides load, save, and merge
operations with atomic writes for safety.

The registry is the source of truth for approved tools that can be executed.
Tools are adopted from the catalog into the registry, transitioning from
"known" to "runnable".

Storage locations:
- User: ~/.config/cub/tools/registry.json
- Project: .cub/tools/registry.json

Example:
    # User-level registry
    store = RegistryStore.user()
    registry = store.load()

    # Add a tool and save
    registry.add(tool_config)
    store.save(registry)

    # Project-level registry
    project_store = RegistryStore.project()
    project_registry = project_store.load()

    # Merge user and project registries (project overrides user)
    merged = RegistryStore.merge(registry, project_registry)

    # Use RegistryService for business logic
    service = RegistryService(store)
    merged_registry = service.load()
    service.adopt(tool, config)
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cub.core.tools.models import (
    CapabilityGapResult,
    Registry,
    ToolConfig,
    ToolSuggestion,
)


class RegistryStore:
    """
    Storage layer for tool registries.

    Manages reading/writing tool registries from disk with support for
    user-level and project-level registries. Uses atomic writes to prevent
    corruption during saves.

    Attributes:
        registry_file: Path to the registry JSON file

    Example:
        # User-level store
        store = RegistryStore.user()
        registry = store.load()

        # Save changes
        registry.add(tool_config)
        store.save(registry)

        # Merge user and project registries
        user_store = RegistryStore.user()
        project_store = RegistryStore.project()
        merged = RegistryStore.merge(user_store.load(), project_store.load())
    """

    def __init__(self, registry_file: Path) -> None:
        """
        Initialize store with a registry file path.

        Args:
            registry_file: Path to registry.json file
        """
        self.registry_file = Path(registry_file)

    def load(self) -> Registry:
        """
        Load the tool registry from disk.

        Returns an empty registry if the file doesn't exist yet.

        Returns:
            Registry object (empty if file doesn't exist)

        Raises:
            ValueError: If registry file is malformed
            json.JSONDecodeError: If registry file contains invalid JSON
        """
        if not self.registry_file.exists():
            # Return empty registry with default version
            return Registry(version="1.0.0", tools={})

        with open(self.registry_file, encoding="utf-8") as f:
            data = json.load(f)
            return Registry.model_validate(data)

    def save(self, registry: Registry) -> Path:
        """
        Write a registry to disk with atomic write.

        Creates parent directories if they don't exist.
        Uses atomic write (write to temp file, then rename) to prevent corruption.

        Args:
            registry: Registry object to save

        Returns:
            Path to the saved registry file

        Raises:
            OSError: If file cannot be written
        """
        # Ensure parent directory exists
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)

        # Serialize registry to JSON with nice formatting
        # Use mode='json' to convert datetime objects to ISO strings
        json_str = json.dumps(registry.model_dump(mode='json'), indent=2)

        # Atomic write: write to temp file in same directory, then rename
        # This ensures we don't corrupt the registry if write fails mid-way
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.registry_file.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(json_str)
            tmp.flush()
            tmp_path = Path(tmp.name)

        # Atomic rename (replaces existing file)
        tmp_path.replace(self.registry_file)

        return self.registry_file

    @classmethod
    def user(cls) -> "RegistryStore":
        """
        Create a store for the user-level registry.

        The user-level registry is stored at:
        - ~/.config/cub/tools/registry.json (or XDG_CONFIG_HOME equivalent)

        Returns:
            RegistryStore for user-level registry
        """
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        registry_file = config_home / "cub" / "tools" / "registry.json"
        return cls(registry_file)

    @classmethod
    def project(cls, project_dir: Path | None = None) -> "RegistryStore":
        """
        Create a store for the project-level registry.

        The project-level registry is stored at:
        - .cub/tools/registry.json (relative to project root)

        Args:
            project_dir: Project directory (defaults to current directory)

        Returns:
            RegistryStore for project-level registry
        """
        if project_dir is None:
            project_dir = Path.cwd()
        registry_file = project_dir / ".cub" / "tools" / "registry.json"
        return cls(registry_file)

    @staticmethod
    def merge(user_registry: Registry, project_registry: Registry) -> Registry:
        """
        Merge user and project registries.

        Project-level tools override user-level tools when there are conflicts.
        The merged registry uses the project registry's version and combines
        tools from both registries, with project tools taking precedence.

        Args:
            user_registry: User-level registry (lower priority)
            project_registry: Project-level registry (higher priority)

        Returns:
            Merged registry with project-level tools overriding user-level

        Example:
            >>> user_reg = Registry(version="1.0.0", tools={"tool-a": config_a})
            >>> proj_reg = Registry(version="1.0.0", tools={"tool-b": config_b})
            >>> merged = RegistryStore.merge(user_reg, proj_reg)
            >>> len(merged.tools)
            2
            >>> # If both have "tool-a", project version wins
        """
        # Start with user registry tools
        merged_tools = user_registry.tools.copy()

        # Override with project registry tools (project wins on conflicts)
        merged_tools.update(project_registry.tools)

        # Use project registry version
        return Registry(
            version=project_registry.version,
            tools=merged_tools,
        )


class RegistryService:
    """
    Business logic layer for registry operations.

    Provides high-level operations for tool adoption, capability lookup,
    approval checking, and version change detection. Handles loading merged
    user+project registries and persists changes to the appropriate level.

    The service encapsulates registry business logic and delegates storage
    operations to RegistryStore.

    Attributes:
        user_store: RegistryStore for user-level registry
        project_store: RegistryStore for project-level registry

    Example:
        # Initialize service
        service = RegistryService()

        # Load merged registry (user + project, project overrides)
        registry = service.load()

        # Adopt a tool from catalog
        config = service.adopt(catalog_tool, tool_config)

        # Check if tool is approved
        if service.is_approved("brave-search"):
            print("Tool is approved for use")

        # Check if tool needs re-approval due to version change
        if service.needs_reapproval("brave-search", new_hash):
            print("Tool has changed, re-approval needed")

        # Find tools by capability
        search_tools = service.find_by_capability("web_search")
    """

    def __init__(
        self,
        user_store: RegistryStore | None = None,
        project_store: RegistryStore | None = None,
    ) -> None:
        """
        Initialize the service with stores.

        Args:
            user_store: RegistryStore for user-level registry.
                       If None, defaults to RegistryStore.user()
            project_store: RegistryStore for project-level registry.
                          If None, defaults to RegistryStore.project()
        """
        self.user_store = user_store or RegistryStore.user()
        self.project_store = project_store or RegistryStore.project()

    def load(self) -> Registry:
        """
        Load and merge user and project registries.

        Loads both user-level and project-level registries and merges them,
        with project-level tools overriding user-level tools when there are
        conflicts. Always loads fresh from disk (no caching).

        Returns:
            Merged registry with project-level tools taking precedence

        Example:
            >>> service = RegistryService()
            >>> registry = service.load()
            >>> print(f"Total tools: {len(registry.tools)}")
        """
        user_registry = self.user_store.load()
        project_registry = self.project_store.load()
        return RegistryStore.merge(user_registry, project_registry)

    def adopt(self, tool_config: ToolConfig) -> ToolConfig:
        """
        Adopt a tool from the catalog into the project registry.

        Adds the tool to the project-level registry (not user-level) and saves
        it to disk. Generates a version_hash if not already present to enable
        future re-approval detection.

        The tool transitions from "known" (in catalog) to "runnable" (in registry).

        Args:
            tool_config: ToolConfig to add to the registry

        Returns:
            The adopted ToolConfig (with version_hash set if it was missing)

        Example:
            >>> service = RegistryService()
            >>> config = ToolConfig(
            ...     id="brave-search",
            ...     name="Brave Search",
            ...     adapter_type=AdapterType.HTTP,
            ...     http_config=HTTPConfig(...),
            ...     adopted_at=datetime.now(timezone.utc),
            ...     adopted_from="mcp-official"
            ... )
            >>> adopted = service.adopt(config)
            >>> print(f"Adopted: {adopted.id} with hash {adopted.version_hash}")
        """
        # Generate version_hash if not present
        if tool_config.version_hash is None:
            tool_config.version_hash = self._generate_version_hash(tool_config)

        # Update adopted_at to current time
        tool_config.adopted_at = datetime.now(timezone.utc)

        # Load project registry
        project_registry = self.project_store.load()

        # Add tool to project registry
        project_registry.add(tool_config)

        # Save project registry
        self.project_store.save(project_registry)

        return tool_config

    def find_by_capability(self, capability: str) -> list[ToolConfig]:
        """
        Find all tools that provide a specific capability.

        Searches the merged registry (user + project) for tools that provide
        the given capability. Always loads fresh registry from disk.

        Args:
            capability: The capability to search for (e.g., "web_search")

        Returns:
            List of ToolConfig objects that provide the capability (may be empty)

        Example:
            >>> service = RegistryService()
            >>> search_tools = service.find_by_capability("web_search")
            >>> for tool in search_tools:
            ...     print(f"Found: {tool.name}")
        """
        registry = self.load()
        return registry.find_by_capability(capability)

    def is_approved(self, tool_id: str) -> bool:
        """
        Check if a tool is approved (exists in registry).

        A tool is considered "approved" if it exists in either the user or
        project registry. This is the gate check before tool execution.

        Args:
            tool_id: The tool identifier to check

        Returns:
            True if tool is in the registry, False otherwise

        Example:
            >>> service = RegistryService()
            >>> if service.is_approved("brave-search"):
            ...     print("Tool is approved for execution")
            ... else:
            ...     print("Tool must be adopted first")
        """
        registry = self.load()
        return registry.get(tool_id) is not None

    def needs_reapproval(self, tool_id: str, current_hash: str) -> bool:
        """
        Check if a tool needs re-approval due to version changes.

        Compares the stored version_hash with a current hash. If they differ,
        the tool has changed and should be re-approved before execution.

        Args:
            tool_id: The tool identifier to check
            current_hash: The current version hash to compare against

        Returns:
            True if the tool needs re-approval (hash mismatch or tool not found),
            False if the hash matches (no re-approval needed)

        Example:
            >>> service = RegistryService()
            >>> current_hash = service._generate_version_hash(updated_config)
            >>> if service.needs_reapproval("brave-search", current_hash):
            ...     print("Tool has changed, please re-approve")
        """
        registry = self.load()
        tool = registry.get(tool_id)

        # If tool not found, it needs approval (not re-approval, but initial approval)
        if tool is None:
            return True

        # If tool has no version_hash, it needs re-approval
        if tool.version_hash is None:
            return True

        # Compare hashes
        return tool.version_hash != current_hash

    def remove(self, tool_id: str) -> bool:
        """
        Remove a tool from the project registry.

        Removes the tool from the project-level registry only (not user-level).
        If the tool exists in the user registry, it will still be available
        after removal from the project registry.

        Args:
            tool_id: The tool identifier to remove

        Returns:
            True if the tool was removed, False if it wasn't found

        Example:
            >>> service = RegistryService()
            >>> if service.remove("old-tool"):
            ...     print("Tool removed from project registry")
            ... else:
            ...     print("Tool not found in project registry")
        """
        # Load project registry
        project_registry = self.project_store.load()

        # Remove tool
        removed = project_registry.remove(tool_id)

        # Save if removed
        if removed:
            self.project_store.save(project_registry)

        return removed

    def query_capability(self, capability: str) -> CapabilityGapResult:
        """
        Query for tools that provide a specific capability.

        Searches both the registry (adopted tools) and the catalog (available tools)
        for tools that match the given capability. Returns adopted tools that are
        ready to use, plus suggestions for tools that could be adopted.

        Ranking:
        - Exact match: Capability exactly matches a tool's capability tag (score: 1.0)
        - Partial match: Capability appears in tool name or description (score: 0.5-0.8)
        - Fuzzy match: Related terms or similar capabilities (score: 0.3-0.5)

        Args:
            capability: The capability to search for (e.g., "web_search")

        Returns:
            CapabilityGapResult with adopted tools and suggestions

        Example:
            >>> service = RegistryService()
            >>> result = service.query_capability("web_search")
            >>> print(f"Found {len(result.adopted_tools)} adopted tools")
            >>> print(f"Found {len(result.suggestions)} suggestions")
            >>> for tool in result.adopted_tools:
            ...     print(f"Ready to use: {tool.name}")
            >>> for suggestion in result.suggestions:
            ...     print(f"Can adopt: {suggestion.name} (score: {suggestion.relevance_score})")
        """
        # Search registry for adopted tools
        adopted_tools = self.find_by_capability(capability)

        # Search catalog for suggestions
        suggestions: list[ToolSuggestion] = []

        # Try to load catalog from toolsmith store
        try:
            from cub.core.toolsmith.store import ToolsmithStore

            store = ToolsmithStore.default()
            catalog = store.load_catalog()

            # Get IDs of already adopted tools to filter them out
            adopted_tool_ids = {tool.id for tool in adopted_tools}

            # Normalize capability for comparison
            capability_lower = capability.lower().replace("_", " ")
            capability_parts = set(capability_lower.split())

            for catalog_tool in catalog.tools:
                # Skip tools that are already adopted
                if catalog_tool.id in adopted_tool_ids:
                    continue

                # Calculate relevance score and match type
                score, match_type = self._calculate_relevance(
                    capability,
                    capability_lower,
                    capability_parts,
                    catalog_tool,
                )

                # Only include tools with meaningful relevance
                if score > 0.0:
                    suggestions.append(
                        ToolSuggestion(
                            tool_id=catalog_tool.id,
                            name=catalog_tool.name,
                            description=catalog_tool.description,
                            source=catalog_tool.source,
                            source_url=catalog_tool.source_url,
                            tags=catalog_tool.tags,
                            relevance_score=score,
                            match_type=match_type,
                        )
                    )

            # Sort suggestions by relevance score (highest first)
            suggestions.sort(key=lambda s: s.relevance_score, reverse=True)

        except ImportError:
            # Toolsmith module not available, catalog search will be empty
            pass
        except Exception:
            # Catalog loading failed, but registry results are still valid
            # Silently continue with empty suggestions
            pass

        return CapabilityGapResult(
            capability=capability,
            adopted_tools=adopted_tools,
            suggestions=suggestions,
        )

    def _calculate_relevance(
        self,
        capability: str,
        capability_lower: str,
        capability_parts: set[str],
        catalog_tool: Any,
    ) -> tuple[float, str]:
        """
        Calculate relevance score and match type for a catalog tool.

        Implements the ranking logic:
        - Exact match: Capability exactly matches a tag (1.0)
        - Partial match: Capability appears in name/description/tags (0.5-0.8)
        - Fuzzy match: Some terms overlap (0.3-0.5)

        Args:
            capability: Original capability string
            capability_lower: Lowercased capability with underscores replaced
            capability_parts: Set of words in the capability
            catalog_tool: Tool from catalog to evaluate

        Returns:
            Tuple of (relevance_score, match_type)
        """
        # Exact match: capability tag matches exactly
        tool_tags_normalized = [tag.lower().replace("_", " ") for tag in catalog_tool.tags]
        if capability_lower in tool_tags_normalized or capability in catalog_tool.tags:
            return (1.0, "exact")

        # Check name and description for matches
        name_lower = catalog_tool.name.lower()
        desc_lower = catalog_tool.description.lower()
        searchable = f"{name_lower} {desc_lower} {' '.join(tool_tags_normalized)}"

        # Partial match: full capability string appears in searchable text
        if capability_lower in searchable:
            return (0.8, "partial")

        # Fuzzy match: calculate word overlap
        searchable_words = set(searchable.split())
        overlap = capability_parts & searchable_words

        if not overlap:
            return (0.0, "none")

        # Score based on proportion of capability words that match
        overlap_ratio = len(overlap) / len(capability_parts)

        if overlap_ratio >= 0.5:
            # At least half the words match - good partial match
            return (0.5 + (overlap_ratio * 0.3), "partial")
        else:
            # Some words match - fuzzy match
            return (0.3 + (overlap_ratio * 0.2), "fuzzy")

    def _generate_version_hash(self, tool_config: ToolConfig) -> str:
        """
        Generate a version hash for a tool configuration.

        Creates a deterministic hash based on tool metadata (name, source,
        adapter configuration) to detect when a tool has changed and may need
        re-approval.

        The hash includes:
        - Tool name
        - Source (adopted_from)
        - Adapter type
        - Serialized adapter configuration (HTTP/CLI/MCP config)

        Args:
            tool_config: ToolConfig to generate hash for

        Returns:
            SHA256 hash (hex string) of the tool metadata

        Note:
            This is an internal method. The hash is automatically generated
            during adoption if not already present.
        """
        # Collect hashable components
        components = [
            tool_config.name,
            tool_config.adopted_from,
            tool_config.adapter_type.value,
        ]

        # Include adapter configuration (serialized to ensure consistency)
        try:
            adapter_config = tool_config.get_adapter_config()
            # Use model_dump and json.dumps with sort_keys for deterministic serialization
            config_dict = adapter_config.model_dump(mode="json")
            config_json = json.dumps(config_dict, sort_keys=True)
            components.append(config_json)
        except ValueError:
            # If adapter config is missing, just use the adapter type
            # This shouldn't happen in normal usage but provides a fallback
            pass

        # Generate SHA256 hash of concatenated components
        hash_input = "|".join(components)
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
