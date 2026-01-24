"""
SQLite schema for cub dashboard database.

Defines the database schema for aggregating project data from multiple sources.
The schema supports the 8-stage Kanban board visualization and entity relationships.

Schema Design:
- entities: Core table for specs, plans, tasks, ledger entries
- relationships: Links between entities (spec -> plan -> task -> ledger)
- metadata: Key-value store for entity-specific metadata
- schema_info: Version tracking for migrations

Entity Types:
- spec: Specification files (specs/**/*.md)
- plan: Plans from sessions (.cub/sessions/*/plan.jsonl)
- epic: Epic tasks (parent tasks)
- task: Individual tasks (beads or JSON)
- ledger: Completed work ledger entries
- release: CHANGELOG.md releases

Stages (9 columns for Kanban board):
- backlog: Not yet started
- researching: Active research/exploration
- planned: Plan exists, not staged
- staged: Tasks created, ready to build
- implementing: Active implementation
- verifying: Testing/verification
- validated: Reviewed and validated
- completed: Done but not released
- released: Shipped and available
"""

import sqlite3

# Schema version for migrations
SCHEMA_VERSION = 2

# Entity types
ENTITY_TYPES = [
    "spec",
    "plan",
    "epic",
    "task",
    "ledger",
    "release",
]

# Valid stages for the Kanban board (9 columns)
STAGES = [
    "backlog",
    "researching",
    "planned",
    "staged",
    "implementing",
    "verifying",
    "validated",
    "completed",
    "released",
]

# Relationship types
RELATIONSHIP_TYPES = [
    "spec_to_plan",  # spec -> plan
    "plan_to_epic",  # plan -> epic
    "epic_to_task",  # epic -> task
    "task_to_ledger",  # task -> ledger entry
    "task_to_release",  # task -> release
    "depends_on",  # task -> task (dependency)
    "blocks",  # task -> task (blocking)
]


# SQLite schema DDL
SCHEMA_DDL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Core entities table
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('spec', 'plan', 'epic', 'task', 'ledger', 'release')),
    title TEXT NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN ('backlog', 'researching', 'planned', 'staged',
                                        'implementing', 'verifying', 'validated',
                                        'completed', 'released')),
    status TEXT,
    priority TEXT,

    -- Timestamps
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Cost tracking
    cost_usd REAL DEFAULT 0.0,
    tokens INTEGER DEFAULT 0,

    -- File references
    file_path TEXT,

    -- JSON blob for type-specific data
    data JSON,

    -- Search and filtering
    search_text TEXT,

    -- Indexing
    UNIQUE(id)
);

-- Relationships between entities
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('spec_to_plan', 'plan_to_epic', 'epic_to_task',
                                      'task_to_ledger', 'task_to_release', 'depends_on', 'blocks')),

    -- Optional metadata
    metadata JSON,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (from_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES entities(id) ON DELETE CASCADE,

    -- Prevent duplicate relationships
    UNIQUE(from_id, to_id, type)
);

-- Key-value metadata for entities
CREATE TABLE IF NOT EXISTS metadata (
    entity_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,

    PRIMARY KEY (entity_id, key)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_stage ON entities(stage);
CREATE INDEX IF NOT EXISTS idx_entities_status ON entities(status);
CREATE INDEX IF NOT EXISTS idx_entities_priority ON entities(priority);
CREATE INDEX IF NOT EXISTS idx_entities_created_at ON entities(created_at);
CREATE INDEX IF NOT EXISTS idx_entities_search ON entities(search_text);

CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(type);

CREATE INDEX IF NOT EXISTS idx_metadata_key ON metadata(key);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """
    Create the database schema.

    Executes all DDL statements to create tables and indexes.
    This is idempotent - safe to call multiple times.

    Args:
        conn: SQLite database connection

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> create_schema(conn)
        >>> cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        >>> tables = [row[0] for row in cursor.fetchall()]
        >>> assert "entities" in tables
        >>> assert "relationships" in tables
    """
    # Execute schema DDL
    conn.executescript(SCHEMA_DDL)

    # Record schema version
    conn.execute(
        """
        INSERT OR REPLACE INTO schema_info (version, description)
        VALUES (?, ?)
        """,
        (SCHEMA_VERSION, "Initial schema with entities, relationships, and metadata"),
    )

    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int | None:
    """
    Get the current schema version from the database.

    Args:
        conn: SQLite database connection

    Returns:
        Current schema version, or None if schema_info table doesn't exist

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> create_schema(conn)
        >>> version = get_schema_version(conn)
        >>> assert version == SCHEMA_VERSION
    """
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_info")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else None
    except sqlite3.OperationalError:
        # schema_info table doesn't exist
        return None


def needs_migration(conn: sqlite3.Connection) -> bool:
    """
    Check if database needs migration to current schema version.

    Args:
        conn: SQLite database connection

    Returns:
        True if migration is needed, False otherwise

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> assert needs_migration(conn) is True  # No schema yet
        >>> create_schema(conn)
        >>> assert needs_migration(conn) is False  # Up to date
    """
    current_version = get_schema_version(conn)
    if current_version is None:
        return True
    return current_version < SCHEMA_VERSION


def validate_entity_type(entity_type: str) -> None:
    """
    Validate that entity type is one of the allowed types.

    Args:
        entity_type: Entity type to validate

    Raises:
        ValueError: If entity type is invalid

    Example:
        >>> validate_entity_type("spec")  # OK
        >>> validate_entity_type("invalid")  # Raises ValueError
        Traceback (most recent call last):
        ...
        ValueError: Invalid entity type: invalid. Must be one of: spec, ...
    """
    if entity_type not in ENTITY_TYPES:
        raise ValueError(
            f"Invalid entity type: {entity_type}. Must be one of: {', '.join(ENTITY_TYPES)}"
        )


def validate_stage(stage: str) -> None:
    """
    Validate that stage is one of the allowed stages.

    Args:
        stage: Stage to validate

    Raises:
        ValueError: If stage is invalid

    Example:
        >>> validate_stage("planned")  # OK
        >>> validate_stage("invalid")  # Raises ValueError
        Traceback (most recent call last):
        ...
        ValueError: Invalid stage: invalid. Must be one of: backlog, ...
    """
    if stage not in STAGES:
        raise ValueError(f"Invalid stage: {stage}. Must be one of: {', '.join(STAGES)}")


def validate_relationship_type(rel_type: str) -> None:
    """
    Validate that relationship type is one of the allowed types.

    Args:
        rel_type: Relationship type to validate

    Raises:
        ValueError: If relationship type is invalid

    Example:
        >>> validate_relationship_type("spec_to_plan")  # OK
        >>> validate_relationship_type("invalid")  # Raises ValueError
        Traceback (most recent call last):
        ...
        ValueError: Invalid relationship type: invalid. Must be one of: ...
    """
    if rel_type not in RELATIONSHIP_TYPES:
        raise ValueError(
            f"Invalid relationship type: {rel_type}. "
            f"Must be one of: {', '.join(RELATIONSHIP_TYPES)}"
        )
