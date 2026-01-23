"""
Sync orchestrator for dashboard data aggregation.

Coordinates parsing and writing of all data sources (specs, plans, tasks, ledger)
into the SQLite database for the Kanban board.

Architecture:
- SyncOrchestrator coordinates the sync process
- Delegates parsing to specialized parsers (SpecParser, PlanParser, TaskParser)
- Uses RelationshipResolver to resolve relationships and enrich entities
- Uses EntityWriter to write parsed entities and relationships to SQLite
- Tracks sync state for incremental sync via checksums
- Returns SyncResult with metrics and any errors

Sync Flow:
1. Phase 1: Parse entities from all sources (specs, plans, tasks)
2. Phase 2: Resolve relationships and enrich with ledger/changelog data
3. Phase 3: Write entities to database
4. Phase 4: Write relationships to database
5. Commit transaction if no errors, rollback otherwise

Partial Failure Handling:
- Each parser runs independently - if one fails, others continue
- Errors are collected and reported in SyncResult
- Transaction is rolled back if any errors occur

Usage:
    from cub.core.dashboard.sync import SyncOrchestrator

    orchestrator = SyncOrchestrator(
        db_path=Path(".cub/dashboard.db"),
        specs_root=Path("./specs"),
        plans_root=Path(".cub/sessions"),
        tasks_backend="beads",
        ledger_path=Path(".cub/ledger"),
        changelog_path=Path("CHANGELOG.md")
    )

    result = orchestrator.sync()
    print(f"Synced {result.entities_added} entities, {result.relationships_added} relationships")
"""

import logging
import time
from pathlib import Path
from typing import Any

from cub.core.dashboard.db import get_connection, init_db
from cub.core.dashboard.db.models import SyncResult
from cub.core.dashboard.sync.parsers import PlanParser, SpecParser, TaskParser
from cub.core.dashboard.sync.resolver import RelationshipResolver
from cub.core.dashboard.sync.writer import EntityWriter
from cub.core.tasks.backend import get_backend

logger = logging.getLogger(__name__)


class SyncOrchestrator:
    """
    Orchestrates syncing of all data sources to the dashboard database.

    The orchestrator coordinates:
    1. Parsing entities from various sources (specs, plans, tasks, ledger)
    2. Writing entities and relationships to SQLite
    3. Tracking sync state for incremental updates
    4. Reporting sync results and errors

    For the vertical slice, only spec parsing is implemented. Other sources
    will be added in future tasks.

    Example:
        >>> orchestrator = SyncOrchestrator(
        ...     db_path=Path(".cub/dashboard.db"),
        ...     specs_root=Path("./specs")
        ... )
        >>> result = orchestrator.sync()
        >>> print(f"Success: {result.success}")
        >>> print(f"Entities added: {result.entities_added}")
    """

    def __init__(
        self,
        db_path: Path | str,
        specs_root: Path | str | None = None,
        plans_root: Path | str | None = None,
        tasks_backend: str | None = None,
        ledger_path: Path | str | None = None,
        changelog_path: Path | str | None = None,
    ) -> None:
        """
        Initialize the SyncOrchestrator.

        Args:
            db_path: Path to SQLite database file
            specs_root: Root directory for specs (e.g., ./specs)
            plans_root: Root directory for plans (e.g., .cub/sessions)
            tasks_backend: Task backend type ("beads" or "json")
            ledger_path: Path to ledger directory (e.g., .cub/ledger)
            changelog_path: Path to CHANGELOG.md

        Example:
            >>> orchestrator = SyncOrchestrator(
            ...     db_path=Path(".cub/dashboard.db"),
            ...     specs_root=Path("./specs"),
            ...     plans_root=Path(".cub/sessions"),
            ...     tasks_backend="beads",
            ...     ledger_path=Path(".cub/ledger"),
            ...     changelog_path=Path("CHANGELOG.md")
            ... )
        """
        self.db_path = Path(db_path)
        self.specs_root = Path(specs_root) if specs_root else None
        self.plans_root = Path(plans_root) if plans_root else None
        self.tasks_backend = tasks_backend
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.changelog_path = Path(changelog_path) if changelog_path else None

        # Initialize database if needed
        self._ensure_db_initialized()

    def _ensure_db_initialized(self) -> None:
        """
        Ensure the database exists and has the current schema.

        Creates the database and applies schema if it doesn't exist.
        """
        if not self.db_path.exists():
            logger.info(f"Initializing database: {self.db_path}")
            init_db(self.db_path)
        else:
            logger.debug(f"Using existing database: {self.db_path}")

    def sync(self, *, force_full_sync: bool = False) -> SyncResult:
        """
        Run the sync process for all data sources.

        This is the main entry point for syncing dashboard data. It:
        1. Parses entities from all configured sources (specs, plans, tasks)
        2. Resolves relationships and enriches entities (via RelationshipResolver)
        3. Writes entities and relationships to SQLite
        4. Reports sync results and errors

        Args:
            force_full_sync: If True, ignore checksums and re-sync everything
                           (not yet implemented, for future incremental sync)

        Returns:
            SyncResult with metrics and any errors

        Example:
            >>> result = orchestrator.sync()
            >>> if result.success:
            ...     print(f"Synced {result.entities_added} entities")
            ... else:
            ...     print(f"Sync failed: {result.errors}")
        """
        start_time = time.time()
        errors: list[str] = []
        warnings: list[str] = []
        sources_synced: list[str] = []

        entities_added = 0
        entities_updated = 0
        entities_removed = 0
        relationships_added = 0
        relationships_removed = 0

        logger.info("Starting dashboard sync")

        try:
            with get_connection(self.db_path) as conn:
                writer = EntityWriter(conn)

                # Phase 1: Parse entities from all sources
                # Collect all entities before writing to enable relationship resolution
                all_entities = []

                # Sync specs
                if self.specs_root:
                    try:
                        logger.info("Parsing specs...")
                        spec_parser = SpecParser(self.specs_root)
                        spec_entities = spec_parser.parse_all()
                        all_entities.extend(spec_entities)
                        sources_synced.append("specs")
                        logger.info(f"Parsed {len(spec_entities)} spec entities")
                    except Exception as e:
                        error_msg = f"Spec parsing failed: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        # Continue with other sources

                # Sync plans
                if self.plans_root:
                    try:
                        logger.info("Parsing plans...")
                        plan_parser = PlanParser(self.plans_root)
                        plan_entities = plan_parser.parse_all()
                        all_entities.extend(plan_entities)
                        sources_synced.append("plans")
                        logger.info(f"Parsed {len(plan_entities)} plan entities")
                    except Exception as e:
                        error_msg = f"Plan parsing failed: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        # Continue with other sources

                # Sync tasks
                if self.tasks_backend:
                    try:
                        logger.info("Parsing tasks...")
                        backend = get_backend()
                        task_parser = TaskParser(backend)
                        task_entities = task_parser.parse_all()
                        all_entities.extend(task_entities)
                        sources_synced.append("tasks")
                        logger.info(f"Parsed {len(task_entities)} task entities")
                    except Exception as e:
                        error_msg = f"Task parsing failed: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        # Continue with other sources

                # Phase 2: Resolve relationships and enrich entities
                try:
                    logger.info("Resolving relationships and enriching entities...")
                    resolver = RelationshipResolver(
                        changelog_path=self.changelog_path,
                        ledger_path=self.ledger_path,
                    )
                    resolved_entities, relationships = resolver.resolve(all_entities)
                    logger.info(
                        f"Resolved {len(resolved_entities)} entities with "
                        f"{len(relationships)} relationships"
                    )
                except Exception as e:
                    error_msg = f"Relationship resolution failed: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    # Use original entities if resolution fails
                    resolved_entities = all_entities
                    relationships = []

                # Phase 3: Write entities to database
                if resolved_entities:
                    try:
                        logger.info("Writing entities to database...")
                        written, skipped = writer.write_entities(resolved_entities)
                        entities_added = written
                        logger.info(f"Wrote {written} entities ({skipped} skipped)")
                    except Exception as e:
                        error_msg = f"Entity writing failed: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Phase 4: Write relationships to database
                if relationships:
                    try:
                        logger.info("Writing relationships to database...")
                        rel_written, rel_skipped = writer.write_relationships(relationships)
                        relationships_added = rel_written
                        logger.info(f"Wrote {rel_written} relationships ({rel_skipped} skipped)")
                    except Exception as e:
                        error_msg = f"Relationship writing failed: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Commit transaction if no errors
                if not errors:
                    conn.commit()
                    logger.info("Sync transaction committed successfully")
                else:
                    conn.rollback()
                    logger.error("Sync transaction rolled back due to errors")

        except Exception as e:
            error_msg = f"Fatal sync error: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        # Calculate duration
        duration = time.time() - start_time

        # Build result
        success = len(errors) == 0
        result = SyncResult(
            success=success,
            entities_added=entities_added,
            entities_updated=entities_updated,
            entities_removed=entities_removed,
            relationships_added=relationships_added,
            relationships_removed=relationships_removed,
            errors=errors,
            warnings=warnings,
            duration_seconds=duration,
            sources_synced=sources_synced,
        )

        if success:
            logger.info(
                f"Sync completed successfully in {duration:.2f}s: "
                f"{result.total_changes} total changes"
            )
        else:
            logger.error(f"Sync completed with {len(errors)} errors in {duration:.2f}s")

        return result

    def get_stats(self) -> dict[str, Any]:
        """
        Get current database statistics.

        Returns:
            Dict with entity counts by type and stage

        Example:
            >>> stats = orchestrator.get_stats()
            >>> print(f"Total entities: {stats['total']}")
            >>> print(f"Specs: {stats['by_type']['spec']}")
        """
        try:
            with get_connection(self.db_path) as conn:
                # Get total count
                cursor = conn.execute("SELECT COUNT(*) as count FROM entities")
                row = cursor.fetchone()
                total = row["count"] if isinstance(row, dict) else row[0]

                # Get counts by type
                cursor = conn.execute("SELECT type, COUNT(*) as count FROM entities GROUP BY type")
                by_type = {}
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        by_type[row["type"]] = row["count"]
                    else:
                        by_type[row[0]] = row[1]

                # Get counts by stage
                cursor = conn.execute(
                    "SELECT stage, COUNT(*) as count FROM entities GROUP BY stage"
                )
                by_stage = {}
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        by_stage[row["stage"]] = row["count"]
                    else:
                        by_stage[row[0]] = row[1]

                return {
                    "total": total,
                    "by_type": by_type,
                    "by_stage": by_stage,
                }

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"total": 0, "by_type": {}, "by_stage": {}}
