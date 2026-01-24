"""
Toolsmith service layer for catalog synchronization and management.

Coordinates sync operations across multiple tool sources, merges results
into the catalog, and provides catalog statistics.

Example:
    # Create service with store and sources
    store = ToolsmithStore.default()
    sources = [SmitherySource(), GlamaSource()]
    service = ToolsmithService(store, sources)

    # Sync all sources
    result = service.sync()
    print(f"Added {result.tools_added}, updated {result.tools_updated}")

    # Sync specific sources
    result = service.sync(source_names=["smithery"])

    # Get catalog statistics
    stats = service.stats()
    print(f"Total tools: {stats.total_tools}")
"""

from collections.abc import Sequence
from datetime import datetime, timezone

from cub.core.toolsmith.models import CatalogStats, SyncResult, Tool
from cub.core.toolsmith.sources.base import ToolSource
from cub.core.toolsmith.store import ToolsmithStore


class ToolsmithService:
    """
    Service layer for toolsmith catalog operations.

    Coordinates sync operations across multiple sources, merging tools
    into the catalog with update-or-insert logic. Provides catalog
    statistics and handles source errors gracefully.

    Example:
        # Initialize with store and sources
        store = ToolsmithStore.default()
        sources = [SmitherySource(), GlamaSource()]
        service = ToolsmithService(store, sources)

        # Sync all sources
        result = service.sync()

        # Sync specific sources
        result = service.sync(source_names=["smithery"])

        # Get statistics
        stats = service.stats()
    """

    def __init__(self, store: ToolsmithStore, sources: Sequence[ToolSource]):
        """
        Initialize the service with a store and sources.

        Args:
            store: ToolsmithStore for reading/writing the catalog
            sources: Sequence of ToolSource instances to sync from
        """
        self.store = store
        self.sources = sources

    def sync(self, source_names: list[str] | None = None) -> SyncResult:
        """
        Sync tools from sources into the catalog.

        Fetches tools from each source (or specified sources), merges them
        into the catalog using update-or-insert logic, and saves the result.
        Handles source errors gracefully by continuing with other sources.

        Args:
            source_names: Optional list of source names to sync.
                         If None, syncs all registered sources.

        Returns:
            SyncResult with tools_added, tools_updated, and any errors

        Example:
            # Sync all sources
            result = service.sync()

            # Sync only smithery
            result = service.sync(source_names=["smithery"])

            # Check results
            if result.errors:
                print(f"Errors: {result.errors}")
            print(f"Added {result.tools_added}, updated {result.tools_updated}")
        """
        # Load existing catalog
        catalog = self.store.load_catalog()

        # Build index of existing tools by ID for fast lookup
        existing_tools: dict[str, Tool] = {tool.id: tool for tool in catalog.tools}

        # Track sync results
        tools_added = 0
        tools_updated = 0
        errors: list[str] = []

        # Determine which sources to sync
        sources_to_sync = self.sources
        if source_names is not None:
            # Filter sources by name
            source_map = {source.name: source for source in self.sources}
            sources_to_sync = []
            for name in source_names:
                if name not in source_map:
                    errors.append(f"Source '{name}' not found in registered sources")
                else:
                    sources_to_sync.append(source_map[name])

        # Track which sources were successfully synced
        synced_sources: set[str] = set()

        # Fetch from each source
        now = datetime.now(timezone.utc)
        for source in sources_to_sync:
            try:
                tools = source.fetch_tools()

                # Merge tools into catalog
                for tool in tools:
                    # Update last_seen timestamp
                    tool.last_seen = now

                    if tool.id in existing_tools:
                        # Update existing tool
                        existing_tools[tool.id] = tool
                        tools_updated += 1
                    else:
                        # Add new tool
                        existing_tools[tool.id] = tool
                        tools_added += 1

                # Track successfully synced source
                synced_sources.add(source.name)

            except Exception as e:
                # Log error but continue with other sources
                error_msg = f"Error syncing source '{source.name}': {e}"
                errors.append(error_msg)

        # Update catalog with merged tools
        catalog.tools = list(existing_tools.values())

        # Update catalog metadata
        catalog.last_sync = now

        # Update sources_synced with newly synced sources
        # Merge with existing sources_synced to preserve history
        all_synced = set(catalog.sources_synced) | synced_sources
        catalog.sources_synced = sorted(all_synced)

        # Save catalog
        self.store.save_catalog(catalog)

        return SyncResult(
            tools_added=tools_added,
            tools_updated=tools_updated,
            errors=errors,
        )

    def stats(self) -> CatalogStats:
        """
        Get statistics about the catalog.

        Returns summary information including total tools, breakdowns
        by source and type, and sync metadata.

        Returns:
            CatalogStats with catalog statistics

        Example:
            >>> stats = service.stats()
            >>> print(f"Total tools: {stats.total_tools}")
            >>> print(f"By source: {stats.by_source}")
            >>> print(f"By type: {stats.by_type}")
        """
        catalog = self.store.load_catalog()

        # Count tools by source
        by_source: dict[str, int] = {}
        for tool in catalog.tools:
            by_source[tool.source] = by_source.get(tool.source, 0) + 1

        # Count tools by type
        by_type: dict[str, int] = {}
        for tool in catalog.tools:
            type_str = tool.tool_type.value
            by_type[type_str] = by_type.get(type_str, 0) + 1

        return CatalogStats(
            total_tools=len(catalog.tools),
            by_source=by_source,
            by_type=by_type,
            last_sync=catalog.last_sync,
            sources_synced=catalog.sources_synced,
        )
