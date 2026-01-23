"""
Database query functions for the dashboard API.

Provides high-level query functions for fetching and transforming
database data into Pydantic models for the API responses.

These functions bridge the gap between the raw SQLite data and
the typed Pydantic models used by the API.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from cub.core.dashboard.db.models import (
    BoardColumn,
    BoardResponse,
    BoardStats,
    ColumnConfig,
    DashboardEntity,
    DisplayConfig,
    EntityDetail,
    EntityType,
    FilterConfig,
    Relationship,
    RelationType,
    Stage,
    ViewConfig,
)

# Mapping from database stage names (lowercase) to Pydantic Stage enum (uppercase)
DB_STAGE_TO_MODEL_STAGE = {
    "backlog": Stage.CAPTURES,
    "researching": Stage.SPECS,
    "planned": Stage.PLANNED,
    "staged": Stage.READY,
    "implementing": Stage.IN_PROGRESS,
    "verifying": Stage.NEEDS_REVIEW,
    "completed": Stage.COMPLETE,
    "released": Stage.RELEASED,
}

# Reverse mapping from Pydantic Stage enum to database stage names
MODEL_STAGE_TO_DB_STAGE = {v: k for k, v in DB_STAGE_TO_MODEL_STAGE.items()}


def get_default_view_config() -> ViewConfig:
    """
    Get the default 8-column view configuration.

    Returns:
        Default view config with all 8 stages as separate columns

    Example:
        >>> view = get_default_view_config()
        >>> assert len(view.columns) == 8
        >>> assert view.id == "default"
    """
    return ViewConfig(
        id="default",
        name="Full Workflow",
        description="Complete workflow from captures to released",
        columns=[
            ColumnConfig(
                id="captures",
                title="Captures",
                stages=[Stage.CAPTURES],
            ),
            ColumnConfig(
                id="specs",
                title="Specs",
                stages=[Stage.SPECS],
            ),
            ColumnConfig(
                id="planned",
                title="Planned",
                stages=[Stage.PLANNED],
            ),
            ColumnConfig(
                id="ready",
                title="Ready",
                stages=[Stage.READY],
            ),
            ColumnConfig(
                id="in_progress",
                title="In Progress",
                stages=[Stage.IN_PROGRESS],
            ),
            ColumnConfig(
                id="needs_review",
                title="Needs Review",
                stages=[Stage.NEEDS_REVIEW],
            ),
            ColumnConfig(
                id="complete",
                title="Complete",
                stages=[Stage.COMPLETE],
            ),
            ColumnConfig(
                id="released",
                title="Released",
                stages=[Stage.RELEASED],
            ),
        ],
        filters=FilterConfig(
            exclude_labels=["archived"],
        ),
        display=DisplayConfig(
            show_cost=True,
            show_tokens=False,
            show_duration=False,
        ),
        is_default=True,
    )


def row_to_entity(row: dict[str, Any]) -> DashboardEntity:
    """
    Convert a database row to a DashboardEntity model.

    Args:
        row: Database row dictionary

    Returns:
        DashboardEntity instance

    Example:
        >>> row = {
        ...     "id": "task-1",
        ...     "type": "task",
        ...     "title": "Test Task",
        ...     "stage": "IN_PROGRESS",
        ...     "status": "in_progress",
        ...     "priority": 0,
        ...     "created_at": "2024-01-23 12:00:00",
        ...     "data": '{"labels": ["test"]}',
        ...     "file_path": ".beads/issues.jsonl",
        ... }
        >>> entity = row_to_entity(row)
        >>> assert entity.id == "task-1"
        >>> assert entity.type == EntityType.TASK
        >>> assert entity.stage == Stage.IN_PROGRESS
    """
    # Parse JSON data field
    data = json.loads(row.get("data", "{}")) if row.get("data") else {}

    # Parse timestamps
    def parse_timestamp(ts: str | None) -> datetime | None:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return None

    # Extract fields from row and data
    # Map database stage name to Pydantic Stage enum
    db_stage = row["stage"]
    model_stage = DB_STAGE_TO_MODEL_STAGE.get(db_stage, Stage.CAPTURES)

    return DashboardEntity(
        id=row["id"],
        type=EntityType(row["type"]),
        title=row["title"],
        description=data.get("description"),
        stage=model_stage,
        status=row.get("status"),
        priority=int(data.get("priority", 0)) if data.get("priority") is not None else None,
        labels=data.get("labels", []),
        created_at=parse_timestamp(row.get("created_at")),
        updated_at=parse_timestamp(row.get("updated_at")),
        completed_at=parse_timestamp(row.get("completed_at")),
        parent_id=data.get("parent_id"),
        spec_id=data.get("spec_id"),
        plan_id=data.get("plan_id"),
        epic_id=data.get("epic_id"),
        cost_usd=row.get("cost_usd"),
        tokens=row.get("tokens"),
        duration_seconds=data.get("duration_seconds"),
        verification_status=data.get("verification_status"),
        source_type=data.get("source_type", "unknown"),
        source_path=row.get("file_path") or "",
        source_checksum=data.get("source_checksum"),
        content=data.get("content"),
        frontmatter=data.get("frontmatter"),
    )


def get_all_entities(conn: sqlite3.Connection) -> list[DashboardEntity]:
    """
    Fetch all entities from the database.

    Args:
        conn: SQLite connection

    Returns:
        List of DashboardEntity instances

    Example:
        >>> import sqlite3
        >>> from cub.core.dashboard.db.connection import configure_connection
        >>> from cub.core.dashboard.db.schema import create_schema
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> entities = get_all_entities(conn)
        >>> assert isinstance(entities, list)
    """
    cursor = conn.execute(
        """
        SELECT * FROM entities
        ORDER BY created_at DESC
        """
    )

    rows = cursor.fetchall()
    return [row_to_entity(row) for row in rows]


def get_entities_by_stage(
    conn: sqlite3.Connection,
    stages: list[Stage],
) -> list[DashboardEntity]:
    """
    Fetch entities for specific stages.

    Args:
        conn: SQLite connection
        stages: List of stages to filter by

    Returns:
        List of DashboardEntity instances

    Example:
        >>> import sqlite3
        >>> from cub.core.dashboard.db.connection import configure_connection
        >>> from cub.core.dashboard.db.schema import create_schema
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> entities = get_entities_by_stage(conn, [Stage.IN_PROGRESS, Stage.READY])
        >>> assert isinstance(entities, list)
    """
    if not stages:
        return []

    # Build query with placeholders for each stage
    stage_values = [stage.value for stage in stages]
    placeholders = ",".join("?" * len(stage_values))

    cursor = conn.execute(
        f"""
        SELECT * FROM entities
        WHERE stage IN ({placeholders})
        ORDER BY created_at DESC
        """,
        stage_values,
    )

    rows = cursor.fetchall()
    return [row_to_entity(row) for row in rows]


def apply_filters(
    entities: list[DashboardEntity],
    filters: FilterConfig | None,
) -> list[DashboardEntity]:
    """
    Apply filters to a list of entities.

    Args:
        entities: List of entities to filter
        filters: Filter configuration

    Returns:
        Filtered list of entities

    Example:
        >>> entities = [
        ...     DashboardEntity(
        ...         id="t1", type=EntityType.TASK, title="Task 1",
        ...         stage=Stage.IN_PROGRESS, labels=["archived"],
        ...         source_type="beads", source_path=".beads/issues.jsonl"
        ...     ),
        ...     DashboardEntity(
        ...         id="t2", type=EntityType.TASK, title="Task 2",
        ...         stage=Stage.IN_PROGRESS, labels=["active"],
        ...         source_type="beads", source_path=".beads/issues.jsonl"
        ...     ),
        ... ]
        >>> filters = FilterConfig(exclude_labels=["archived"])
        >>> filtered = apply_filters(entities, filters)
        >>> assert len(filtered) == 1
        >>> assert filtered[0].id == "t2"
    """
    if not filters:
        return entities

    filtered = entities

    # Exclude labels
    if filters.exclude_labels:
        filtered = [
            e for e in filtered if not any(label in filters.exclude_labels for label in e.labels)
        ]

    # Include labels
    if filters.include_labels:
        filtered = [
            e for e in filtered if any(label in filters.include_labels for label in e.labels)
        ]

    # Exclude types
    if filters.exclude_types:
        filtered = [e for e in filtered if e.type not in filters.exclude_types]

    # Include types
    if filters.include_types:
        filtered = [e for e in filtered if e.type in filters.include_types]

    # Priority filters
    if filters.min_priority is not None:
        filtered = [
            e for e in filtered if e.priority is not None and e.priority >= filters.min_priority
        ]

    if filters.max_priority is not None:
        filtered = [
            e for e in filtered if e.priority is not None and e.priority <= filters.max_priority
        ]

    return filtered


def compute_board_stats(entities: list[DashboardEntity]) -> BoardStats:
    """
    Compute summary statistics for a list of entities.

    Args:
        entities: List of entities

    Returns:
        BoardStats with aggregated metrics

    Example:
        >>> entities = [
        ...     DashboardEntity(
        ...         id="t1", type=EntityType.TASK, title="Task 1",
        ...         stage=Stage.IN_PROGRESS, cost_usd=1.5, tokens=1000,
        ...         source_type="beads", source_path=".beads/issues.jsonl"
        ...     ),
        ...     DashboardEntity(
        ...         id="t2", type=EntityType.TASK, title="Task 2",
        ...         stage=Stage.READY, cost_usd=2.5, tokens=2000,
        ...         source_type="beads", source_path=".beads/issues.jsonl"
        ...     ),
        ... ]
        >>> stats = compute_board_stats(entities)
        >>> assert stats.total == 2
        >>> assert stats.cost_total == 4.0
        >>> assert stats.tokens_total == 3000
    """
    stats = BoardStats()

    for entity in entities:
        # Count totals
        stats.total += 1

        # Count by stage
        if entity.stage not in stats.by_stage:
            stats.by_stage[entity.stage] = 0
        stats.by_stage[entity.stage] += 1

        # Count by type
        if entity.type not in stats.by_type:
            stats.by_type[entity.type] = 0
        stats.by_type[entity.type] += 1

        # Sum costs
        if entity.cost_usd:
            stats.cost_total += entity.cost_usd

        if entity.tokens:
            stats.tokens_total += entity.tokens

        if entity.duration_seconds:
            stats.duration_total_seconds += entity.duration_seconds

    return stats


def get_board_data(
    conn: sqlite3.Connection,
    view: ViewConfig | None = None,
) -> BoardResponse:
    """
    Get full board data for the Kanban visualization.

    Fetches all entities, applies filters, groups by column/stage,
    and computes statistics.

    Args:
        conn: SQLite connection
        view: Optional view configuration (uses default if None)

    Returns:
        BoardResponse with columns and stats

    Example:
        >>> import sqlite3
        >>> from cub.core.dashboard.db.connection import configure_connection
        >>> from cub.core.dashboard.db.schema import create_schema
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> board = get_board_data(conn)
        >>> assert len(board.columns) == 8
        >>> assert board.view.id == "default"
    """
    # Use default view if not specified
    if view is None:
        view = get_default_view_config()

    # Fetch all entities
    all_entities = get_all_entities(conn)

    # Apply filters
    filtered_entities = apply_filters(all_entities, view.filters)

    # Group entities by column
    columns: list[BoardColumn] = []

    for col_config in view.columns:
        # Get entities for this column's stages
        col_entities = [e for e in filtered_entities if e.stage in col_config.stages]

        # Create board column
        column = BoardColumn(
            id=col_config.id,
            title=col_config.title,
            stage=col_config.stages[0],  # Use first stage as primary
            entities=col_entities,
            count=len(col_entities),
        )
        columns.append(column)

    # Compute statistics
    stats = compute_board_stats(filtered_entities)

    return BoardResponse(
        view=view,
        columns=columns,
        stats=stats,
    )


def get_entity_by_id(
    conn: sqlite3.Connection,
    entity_id: str,
) -> DashboardEntity | None:
    """
    Fetch a single entity by ID.

    Args:
        conn: SQLite connection
        entity_id: Entity ID to fetch

    Returns:
        DashboardEntity or None if not found

    Example:
        >>> import sqlite3
        >>> from cub.core.dashboard.db.connection import configure_connection
        >>> from cub.core.dashboard.db.schema import create_schema
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> entity = get_entity_by_id(conn, "task-1")
        >>> assert entity is None  # No data yet
    """
    cursor = conn.execute(
        """
        SELECT * FROM entities
        WHERE id = ?
        """,
        (entity_id,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    return row_to_entity(row)


def get_relationships(
    conn: sqlite3.Connection,
    entity_id: str,
) -> list[Relationship]:
    """
    Fetch all relationships for an entity (both incoming and outgoing).

    Args:
        conn: SQLite connection
        entity_id: Entity ID

    Returns:
        List of Relationship instances

    Example:
        >>> import sqlite3
        >>> from cub.core.dashboard.db.connection import configure_connection
        >>> from cub.core.dashboard.db.schema import create_schema
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> rels = get_relationships(conn, "task-1")
        >>> assert isinstance(rels, list)
    """
    cursor = conn.execute(
        """
        SELECT from_id, to_id, type, metadata
        FROM relationships
        WHERE from_id = ? OR to_id = ?
        """,
        (entity_id, entity_id),
    )

    rows = cursor.fetchall()
    relationships = []

    for row in rows:
        metadata = json.loads(row["metadata"]) if row.get("metadata") else None
        relationships.append(
            Relationship(
                source_id=row["from_id"],
                target_id=row["to_id"],
                rel_type=RelationType(row["type"]),
                metadata=metadata,
            )
        )

    return relationships


def get_entity_detail(
    conn: sqlite3.Connection,
    entity_id: str,
) -> EntityDetail | None:
    """
    Fetch detailed entity data with relationships.

    Returns the entity along with all related entities organized by
    relationship type. This powers the detail panel view in the UI.

    Args:
        conn: SQLite connection
        entity_id: Entity ID to fetch

    Returns:
        EntityDetail with entity, relationships, and content, or None if not found

    Example:
        >>> import sqlite3
        >>> from cub.core.dashboard.db.connection import configure_connection
        >>> from cub.core.dashboard.db.schema import create_schema
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> detail = get_entity_detail(conn, "task-1")
        >>> assert detail is None  # No data yet
    """
    # Fetch the entity
    entity = get_entity_by_id(conn, entity_id)
    if not entity:
        return None

    # Fetch all relationships for this entity
    relationships = get_relationships(conn, entity_id)

    # Organize relationships by type
    related_entities: dict[str, list[DashboardEntity] | DashboardEntity | None] = {
        "parent": None,
        "children": [],
        "blocks": [],
        "blocked_by": [],
        "depends_on": [],
        "spec": None,
        "plan": None,
        "epic": None,
        "tasks": [],
        "ledger": None,
        "releases": [],
    }

    # Process each relationship and fetch related entities
    for rel in relationships:
        # Determine the related entity ID based on direction
        if rel.source_id == entity_id:
            # Outgoing relationship
            related_id = rel.target_id
            is_outgoing = True
        else:
            # Incoming relationship
            related_id = rel.source_id
            is_outgoing = False

        # Fetch the related entity
        related_entity = get_entity_by_id(conn, related_id)
        if not related_entity:
            continue

        # Organize by relationship type
        if rel.rel_type == RelationType.CONTAINS:
            if is_outgoing:
                # This entity contains another (children)
                related_entities["children"].append(related_entity)  # type: ignore
            else:
                # This entity is contained by another (parent)
                related_entities["parent"] = related_entity

        elif rel.rel_type == RelationType.BLOCKS:
            if is_outgoing:
                # This entity blocks another
                related_entities["blocks"].append(related_entity)  # type: ignore
            else:
                # This entity is blocked by another
                related_entities["blocked_by"].append(related_entity)  # type: ignore

        elif rel.rel_type == RelationType.DEPENDS_ON:
            if is_outgoing:
                # This entity depends on another
                related_entities["depends_on"].append(related_entity)  # type: ignore
            # Note: Reverse of DEPENDS_ON is not stored separately

        elif rel.rel_type == RelationType.SPEC_TO_PLAN:
            if is_outgoing:
                # This spec created a plan
                if "plans" not in related_entities:
                    related_entities["plans"] = []
                related_entities["plans"].append(related_entity)  # type: ignore
            else:
                # This plan was created from a spec
                related_entities["spec"] = related_entity

        elif rel.rel_type == RelationType.PLAN_TO_EPIC:
            if is_outgoing:
                # This plan created an epic
                if "epics" not in related_entities:
                    related_entities["epics"] = []
                related_entities["epics"].append(related_entity)  # type: ignore
            else:
                # This epic was created from a plan
                related_entities["plan"] = related_entity

        elif rel.rel_type == RelationType.EPIC_TO_TASK:
            if is_outgoing:
                # This epic contains tasks
                related_entities["tasks"].append(related_entity)  # type: ignore
            else:
                # This task belongs to an epic
                related_entities["epic"] = related_entity

        elif rel.rel_type == RelationType.TASK_TO_LEDGER:
            if is_outgoing:
                # This task has a ledger entry
                related_entities["ledger"] = related_entity

        elif rel.rel_type == RelationType.TASK_TO_RELEASE:
            if is_outgoing:
                # This task is in a release
                related_entities["releases"].append(related_entity)  # type: ignore

    # Extract content from entity
    content = entity.content

    return EntityDetail(
        entity=entity,
        relationships=related_entities,
        content=content,
    )
