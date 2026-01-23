"""
SQLite writer for dashboard sync layer.

Handles writing DashboardEntity objects and Relationship objects to SQLite.
Provides transaction-safe operations with proper error handling and validation.

Key features:
- Upsert semantics for entities (insert or update based on checksum)
- Duplicate prevention for relationships
- JSON serialization for complex fields (frontmatter, metadata)
- Transaction support for batch operations
- Incremental sync tracking via checksums

Usage:
    from cub.core.dashboard.sync.writer import EntityWriter

    with get_connection(db_path) as conn:
        writer = EntityWriter(conn)

        # Write single entity
        writer.write_entity(entity)

        # Write batch of entities
        writer.write_entities(entities)

        # Write relationships
        writer.write_relationship(relationship)

        conn.commit()
"""

import json
import logging
import sqlite3
from datetime import date, datetime
from typing import Any

from cub.core.dashboard.db.models import DashboardEntity, Relationship


def _json_serializer(obj: Any) -> str:
    """Custom JSON serializer for objects not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

logger = logging.getLogger(__name__)


class EntityWriter:
    """
    Writer for dashboard entities and relationships.

    Handles conversion from Pydantic models to SQLite rows with proper
    JSON serialization and checksum-based incremental sync.

    Example:
        >>> from cub.core.dashboard.db import get_connection
        >>> with get_connection(db_path) as conn:
        ...     writer = EntityWriter(conn)
        ...     writer.write_entity(entity)
        ...     conn.commit()
    """

    # Map Pydantic Stage enum values to SQLite schema stage values
    STAGE_MAPPING = {
        "CAPTURES": "backlog",  # Captures are in backlog
        "SPECS": "researching",  # Specs being researched
        "PLANNED": "planned",  # Planned
        "READY": "staged",  # Ready = staged in schema
        "IN_PROGRESS": "implementing",  # In progress = implementing
        "NEEDS_REVIEW": "verifying",  # Review = verifying
        "COMPLETE": "completed",  # Complete
        "RELEASED": "released",  # Released
    }

    def __init__(self, conn: sqlite3.Connection) -> None:
        """
        Initialize the EntityWriter.

        Args:
            conn: SQLite connection (must have dict row factory configured)
        """
        self.conn = conn

    def _entity_exists(self, entity_id: str) -> bool:
        """
        Check if an entity already exists in the database.

        Args:
            entity_id: Entity ID to check

        Returns:
            True if entity exists, False otherwise
        """
        cursor = self.conn.execute(
            "SELECT 1 FROM entities WHERE id = ? LIMIT 1",
            (entity_id,),
        )
        return cursor.fetchone() is not None

    def _entity_changed(self, entity_id: str, checksum: str) -> bool:
        """
        Check if an entity's content has changed based on checksum.

        Since source_checksum is stored in the data JSON field, we extract
        and compare it to detect changes.

        Args:
            entity_id: Entity ID to check
            checksum: New checksum to compare

        Returns:
            True if entity doesn't exist or checksum differs, False otherwise
        """
        cursor = self.conn.execute(
            "SELECT data FROM entities WHERE id = ?",
            (entity_id,),
        )
        row = cursor.fetchone()

        if row is None:
            return True  # Entity doesn't exist

        # Extract data JSON
        data_json = row["data"] if isinstance(row, dict) else row[0]

        if not data_json:
            return True  # No data, consider changed

        try:
            data: dict[str, Any] = json.loads(data_json)
            existing_checksum = data.get("source_checksum", "")
            return str(existing_checksum) != checksum
        except (json.JSONDecodeError, KeyError):
            return True  # Error parsing, consider changed

    def write_entity(self, entity: DashboardEntity) -> bool:
        """
        Write a single entity to the database.

        Uses upsert semantics:
        - If entity doesn't exist, insert it
        - If entity exists and checksum changed, update it
        - If entity exists and checksum unchanged, skip (no-op)

        Args:
            entity: DashboardEntity to write

        Returns:
            True if entity was written (inserted or updated), False if skipped

        Example:
            >>> writer.write_entity(entity)
            True  # Entity was written
        """
        # Check if update needed (based on checksum)
        if not self._entity_changed(entity.id, entity.source_checksum or ""):
            logger.debug(f"Skipping unchanged entity: {entity.id}")
            return False

        try:
            # Serialize complex fields to JSON
            data_json: str | None = None
            data: dict[str, Any] = {}
            if entity.frontmatter:
                data["frontmatter"] = entity.frontmatter
            if entity.content:
                data["content"] = entity.content
            if entity.source_checksum:
                data["source_checksum"] = entity.source_checksum
            data_json = json.dumps(data, default=_json_serializer) if data else None

            # Build search text for full-text search
            search_parts = [entity.title]
            if entity.description:
                search_parts.append(entity.description)
            if entity.labels:
                search_parts.extend(entity.labels)
            search_text = " ".join(search_parts)

            # Convert datetime to ISO format strings
            created_at = entity.created_at.isoformat() if entity.created_at else None
            updated_at = entity.updated_at.isoformat() if entity.updated_at else None
            completed_at = entity.completed_at.isoformat() if entity.completed_at else None

            # Map stage from Pydantic model to schema
            stage_value = self.STAGE_MAPPING.get(entity.stage.value, entity.stage.value)

            # Upsert entity
            self.conn.execute(
                """
                INSERT INTO entities (
                    id, type, title, stage, status, priority,
                    created_at, updated_at, completed_at,
                    cost_usd, tokens,
                    file_path, data, search_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    title = excluded.title,
                    stage = excluded.stage,
                    status = excluded.status,
                    priority = excluded.priority,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    completed_at = excluded.completed_at,
                    cost_usd = excluded.cost_usd,
                    tokens = excluded.tokens,
                    file_path = excluded.file_path,
                    data = excluded.data,
                    search_text = excluded.search_text
                """,
                (
                    entity.id,
                    entity.type.value,
                    entity.title,
                    stage_value,
                    entity.status,
                    entity.priority,
                    created_at,
                    updated_at,
                    completed_at,
                    entity.cost_usd,
                    entity.tokens,
                    entity.source_path,
                    data_json,
                    search_text,
                ),
            )

            # Store labels as metadata (one row per label)
            if entity.labels:
                for label in entity.labels:
                    self.conn.execute(
                        """
                        INSERT INTO metadata (entity_id, key, value)
                        VALUES (?, ?, ?)
                        ON CONFLICT(entity_id, key) DO UPDATE SET
                            value = excluded.value,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (entity.id, f"label:{label}", label),
                    )

            # Store hierarchy references as metadata
            for ref_name, ref_value in [
                ("parent_id", entity.parent_id),
                ("spec_id", entity.spec_id),
                ("plan_id", entity.plan_id),
                ("epic_id", entity.epic_id),
            ]:
                if ref_value:
                    self.conn.execute(
                        """
                        INSERT INTO metadata (entity_id, key, value)
                        VALUES (?, ?, ?)
                        ON CONFLICT(entity_id, key) DO UPDATE SET
                            value = excluded.value,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (entity.id, ref_name, ref_value),
                    )

            logger.debug(f"Wrote entity: {entity.id} ({entity.type.value})")
            return True

        except sqlite3.Error as e:
            logger.error(f"Failed to write entity {entity.id}: {e}")
            raise

    def write_entities(self, entities: list[DashboardEntity]) -> tuple[int, int]:
        """
        Write multiple entities in a batch.

        Args:
            entities: List of DashboardEntity objects to write

        Returns:
            Tuple of (written_count, skipped_count)

        Example:
            >>> written, skipped = writer.write_entities(entities)
            >>> print(f"Wrote {written}, skipped {skipped}")
        """
        written = 0
        skipped = 0

        for entity in entities:
            try:
                if self.write_entity(entity):
                    written += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Error writing entity {entity.id}: {e}")
                # Continue processing other entities
                skipped += 1

        logger.info(f"Batch write: {written} written, {skipped} skipped")
        return written, skipped

    def write_relationship(self, relationship: Relationship) -> bool:
        """
        Write a relationship between two entities.

        Args:
            relationship: Relationship to write

        Returns:
            True if relationship was written, False if it already exists

        Example:
            >>> rel = Relationship(
            ...     source_id="spec-1",
            ...     target_id="plan-1",
            ...     rel_type=RelationType.SPEC_TO_PLAN
            ... )
            >>> writer.write_relationship(rel)
            True
        """
        try:
            # Check if relationship already exists
            cursor = self.conn.execute(
                """
                SELECT 1 FROM relationships
                WHERE from_id = ? AND to_id = ? AND type = ?
                LIMIT 1
                """,
                (
                    relationship.source_id,
                    relationship.target_id,
                    relationship.rel_type.value,
                ),
            )
            if cursor.fetchone() is not None:
                logger.debug(
                    f"Skipping duplicate relationship: {relationship.source_id} -> "
                    f"{relationship.target_id}"
                )
                return False

            # Serialize metadata if present
            metadata_json = None
            if relationship.metadata:
                metadata_json = json.dumps(relationship.metadata, default=_json_serializer)

            # Insert relationship
            self.conn.execute(
                """
                INSERT INTO relationships (from_id, to_id, type, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    relationship.source_id,
                    relationship.target_id,
                    relationship.rel_type.value,
                    metadata_json,
                ),
            )

            logger.debug(
                f"Wrote relationship: {relationship.source_id} -> {relationship.target_id} "
                f"({relationship.rel_type.value})"
            )
            return True

        except sqlite3.Error as e:
            logger.error(
                f"Failed to write relationship {relationship.source_id} -> "
                f"{relationship.target_id}: {e}"
            )
            raise

    def write_relationships(self, relationships: list[Relationship]) -> tuple[int, int]:
        """
        Write multiple relationships in a batch.

        Args:
            relationships: List of Relationship objects to write

        Returns:
            Tuple of (written_count, skipped_count)

        Example:
            >>> written, skipped = writer.write_relationships(relationships)
        """
        written = 0
        skipped = 0

        for relationship in relationships:
            try:
                if self.write_relationship(relationship):
                    written += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(
                    f"Error writing relationship {relationship.source_id} -> "
                    f"{relationship.target_id}: {e}"
                )
                skipped += 1

        logger.info(f"Batch write: {written} relationships written, {skipped} skipped")
        return written, skipped

    def delete_entity(self, entity_id: str) -> bool:
        """
        Delete an entity and all its relationships.

        Cascading deletes handle relationships and metadata automatically
        via foreign key constraints.

        Args:
            entity_id: ID of entity to delete

        Returns:
            True if entity was deleted, False if it didn't exist

        Example:
            >>> writer.delete_entity("spec-1")
            True
        """
        try:
            cursor = self.conn.execute(
                "DELETE FROM entities WHERE id = ?",
                (entity_id,),
            )

            if cursor.rowcount > 0:
                logger.debug(f"Deleted entity: {entity_id}")
                return True
            else:
                logger.debug(f"Entity not found for deletion: {entity_id}")
                return False

        except sqlite3.Error as e:
            logger.error(f"Failed to delete entity {entity_id}: {e}")
            raise

    def clear_all_entities(self) -> int:
        """
        Delete all entities from the database.

        This is mainly useful for testing or full re-sync scenarios.

        Returns:
            Number of entities deleted

        Example:
            >>> count = writer.clear_all_entities()
            >>> print(f"Deleted {count} entities")
        """
        try:
            cursor = self.conn.execute("DELETE FROM entities")
            count = cursor.rowcount
            logger.info(f"Cleared {count} entities from database")
            return count

        except sqlite3.Error as e:
            logger.error(f"Failed to clear entities: {e}")
            raise
