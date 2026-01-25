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
"""

import json
import os
import tempfile
from pathlib import Path

from cub.core.tools.models import Registry


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
