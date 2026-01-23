"""
Sync orchestrator for dashboard data aggregation.

Coordinates parsing and writing of all data sources (specs, plans, tasks, ledger)
into the SQLite database for the Kanban board.

For the vertical slice (cub-k8d), we only sync specs. Other sources will be
added incrementally in future tasks.

Architecture:
- SyncOrchestrator coordinates the sync process
- Delegates parsing to specialized parsers (SpecParser, PlanParser, etc.)
- Uses EntityWriter to write parsed entities to SQLite
- Tracks sync state for incremental sync (future enhancement)
- Returns SyncResult with metrics and any errors

Usage:
    from cub.core.dashboard.sync import SyncOrchestrator

    orchestrator = SyncOrchestrator(
        db_path=Path(".cub/dashboard.db"),
        specs_root=Path("./specs")
    )

    result = orchestrator.sync()
    print(f"Synced {result.entities_added} entities")
"""

import logging
import time
from pathlib import Path
from typing import Any

from cub.core.dashboard.db import get_connection, init_db
from cub.core.dashboard.db.models import SyncResult
from cub.core.dashboard.sync.parsers.specs import SpecParser
from cub.core.dashboard.sync.writer import EntityWriter

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
    ) -> None:
        """
        Initialize the SyncOrchestrator.

        Args:
            db_path: Path to SQLite database file
            specs_root: Root directory for specs (e.g., ./specs)
            plans_root: Root directory for plans (e.g., .cub/sessions) - not yet implemented
            tasks_backend: Task backend type ("beads" or "json") - not yet implemented
            ledger_path: Path to ledger file - not yet implemented

        Example:
            >>> orchestrator = SyncOrchestrator(
            ...     db_path=Path(".cub/dashboard.db"),
            ...     specs_root=Path("./specs")
            ... )
        """
        self.db_path = Path(db_path)
        self.specs_root = Path(specs_root) if specs_root else None
        self.plans_root = Path(plans_root) if plans_root else None
        self.tasks_backend = tasks_backend
        self.ledger_path = Path(ledger_path) if ledger_path else None

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

    def _sync_specs(self, writer: EntityWriter) -> dict[str, Any]:
        """
        Sync specs from specs_root directory.

        Args:
            writer: EntityWriter for writing to database

        Returns:
            Dict with sync metrics: {"added": int, "updated": int, "skipped": int}
        """
        if not self.specs_root:
            logger.warning("Specs root not configured, skipping spec sync")
            return {"added": 0, "updated": 0, "skipped": 0}

        if not self.specs_root.exists():
            logger.warning(f"Specs root does not exist: {self.specs_root}")
            return {"added": 0, "updated": 0, "skipped": 0}

        logger.info(f"Syncing specs from {self.specs_root}")

        try:
            # Parse all specs
            parser = SpecParser(self.specs_root)
            entities = parser.parse_all()

            if not entities:
                logger.info("No specs found to sync")
                return {"added": 0, "updated": 0, "skipped": 0}

            # Write entities to database
            written, skipped = writer.write_entities(entities)

            logger.info(f"Spec sync complete: {written} written, {skipped} skipped")

            # For now, we can't distinguish between added and updated
            # (would need to track this in writer or query before)
            return {"added": written, "updated": 0, "skipped": skipped}

        except Exception as e:
            logger.error(f"Error syncing specs: {e}")
            raise

    def _sync_plans(self, writer: EntityWriter) -> dict[str, Any]:
        """
        Sync plans from .cub/sessions directory.

        NOT YET IMPLEMENTED - placeholder for future task.

        Args:
            writer: EntityWriter for writing to database

        Returns:
            Dict with sync metrics
        """
        logger.debug("Plan sync not yet implemented")
        return {"added": 0, "updated": 0, "skipped": 0}

    def _sync_tasks(self, writer: EntityWriter) -> dict[str, Any]:
        """
        Sync tasks from task backend (beads or JSON).

        NOT YET IMPLEMENTED - placeholder for future task.

        Args:
            writer: EntityWriter for writing to database

        Returns:
            Dict with sync metrics
        """
        logger.debug("Task sync not yet implemented")
        return {"added": 0, "updated": 0, "skipped": 0}

    def _sync_ledger(self, writer: EntityWriter) -> dict[str, Any]:
        """
        Sync ledger entries.

        NOT YET IMPLEMENTED - placeholder for future task.

        Args:
            writer: EntityWriter for writing to database

        Returns:
            Dict with sync metrics
        """
        logger.debug("Ledger sync not yet implemented")
        return {"added": 0, "updated": 0, "skipped": 0}

    def sync(self, *, force_full_sync: bool = False) -> SyncResult:
        """
        Run the sync process for all data sources.

        This is the main entry point for syncing dashboard data.

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

                # Sync specs
                if self.specs_root:
                    try:
                        spec_result = self._sync_specs(writer)
                        entities_added += spec_result["added"]
                        entities_updated += spec_result["updated"]
                        sources_synced.append("specs")
                    except Exception as e:
                        error_msg = f"Spec sync failed: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Sync plans (not yet implemented)
                if self.plans_root:
                    try:
                        plan_result = self._sync_plans(writer)
                        entities_added += plan_result["added"]
                        entities_updated += plan_result["updated"]
                        sources_synced.append("plans")
                    except Exception as e:
                        error_msg = f"Plan sync failed: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Sync tasks (not yet implemented)
                if self.tasks_backend:
                    try:
                        task_result = self._sync_tasks(writer)
                        entities_added += task_result["added"]
                        entities_updated += task_result["updated"]
                        sources_synced.append("tasks")
                    except Exception as e:
                        error_msg = f"Task sync failed: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Sync ledger (not yet implemented)
                if self.ledger_path:
                    try:
                        ledger_result = self._sync_ledger(writer)
                        entities_added += ledger_result["added"]
                        entities_updated += ledger_result["updated"]
                        sources_synced.append("ledger")
                    except Exception as e:
                        error_msg = f"Ledger sync failed: {e}"
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
                cursor = conn.execute(
                    "SELECT type, COUNT(*) as count FROM entities GROUP BY type"
                )
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
