"""
Toolsmith storage layer for reading/writing tool catalogs.

Manages the local tool catalog stored at .cub/toolsmith/catalog.json.
Provides load, save, and search operations with atomic writes for safety.

Example:
    # Default store
    store = ToolsmithStore.default()
    catalog = store.load_catalog()

    # Add a tool and save
    catalog.tools.append(new_tool)
    store.save_catalog(catalog)

    # Search for tools
    results = store.search("linter")
"""

import json
import tempfile
from pathlib import Path

from cub.core.toolsmith.models import Catalog, Tool


class ToolsmithStore:
    """
    Storage layer for tool catalogs.

    Manages reading/writing the tool catalog from .cub/toolsmith/catalog.json.
    Uses atomic writes to prevent corruption during saves.

    Example:
        # Project-level store
        store = ToolsmithStore.default()
        catalog = store.load_catalog()

        # Search
        results = store.search("eslint")

        # Save changes
        catalog.tools.append(new_tool)
        store.save_catalog(catalog)
    """

    def __init__(self, toolsmith_dir: Path) -> None:
        """
        Initialize store with a toolsmith directory.

        Args:
            toolsmith_dir: Directory containing catalog.json
        """
        self.toolsmith_dir = Path(toolsmith_dir)
        self.catalog_file = self.toolsmith_dir / "catalog.json"

    def load_catalog(self) -> Catalog:
        """
        Load the tool catalog from disk.

        Returns an empty catalog if the file doesn't exist yet.

        Returns:
            Catalog object (empty if file doesn't exist)

        Raises:
            ValueError: If catalog file is malformed
            json.JSONDecodeError: If catalog file contains invalid JSON
        """
        if not self.catalog_file.exists():
            # Return empty catalog with default version
            return Catalog(version="1.0.0", tools=[])

        with open(self.catalog_file, encoding="utf-8") as f:
            data = json.load(f)
            return Catalog.model_validate(data)

    def save_catalog(self, catalog: Catalog) -> Path:
        """
        Write a catalog to disk with atomic write.

        Creates the toolsmith directory if it doesn't exist.
        Uses atomic write (write to temp file, then rename) to prevent corruption.

        Args:
            catalog: Catalog object to save

        Returns:
            Path to the saved catalog file

        Raises:
            OSError: If file cannot be written
        """
        # Ensure directory exists
        self.toolsmith_dir.mkdir(parents=True, exist_ok=True)

        # Serialize catalog to JSON with nice formatting
        # Use mode='json' to convert datetime objects to ISO strings
        json_str = json.dumps(catalog.model_dump(mode='json'), indent=2)

        # Atomic write: write to temp file in same directory, then rename
        # This ensures we don't corrupt the catalog if write fails mid-way
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.toolsmith_dir,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(json_str)
            tmp.flush()
            tmp_path = Path(tmp.name)

        # Atomic rename (replaces existing file)
        tmp_path.replace(self.catalog_file)

        return self.catalog_file

    def search(self, query: str) -> list[Tool]:
        """
        Search for tools matching the query.

        Searches tool names and descriptions (case-insensitive).
        Query is split into terms; ALL terms must appear in either the name
        or description for a tool to match.

        Args:
            query: Search query string (e.g., "javascript linter")

        Returns:
            List of matching Tool objects (empty if no matches)

        Example:
            >>> store = ToolsmithStore.default()
            >>> results = store.search("javascript linter")
            >>> # Returns tools where "javascript" AND "linter" appear in name or description
        """
        catalog = self.load_catalog()

        if not query.strip():
            return []

        # Split query into terms and lowercase for case-insensitive matching
        terms = [term.lower() for term in query.split()]

        matches: list[Tool] = []
        for tool in catalog.tools:
            # Combine name and description for searching
            searchable_text = f"{tool.name} {tool.description}".lower()

            # Check if ALL terms appear in the searchable text
            if all(term in searchable_text for term in terms):
                matches.append(tool)

        return matches

    @classmethod
    def default(cls) -> "ToolsmithStore":
        """
        Create a store for the default toolsmith directory.

        The default location is .cub/toolsmith/ relative to the current directory.

        Returns:
            ToolsmithStore for .cub/toolsmith/
        """
        toolsmith_dir = Path.cwd() / ".cub" / "toolsmith"
        return cls(toolsmith_dir)
