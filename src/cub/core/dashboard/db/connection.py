"""
Database connection management for cub dashboard.

Provides connection pooling, transaction management, and query helpers
for the dashboard SQLite database.

The connection module follows SQLite best practices:
- WAL mode for better concurrency
- Foreign key enforcement
- Row factory for dict-like access
- Context managers for safe transaction handling

Usage:
    from cub.core.dashboard.db import get_connection, init_db

    # Initialize database
    db_path = Path(".cub/dashboard.db")
    init_db(db_path)

    # Query with context manager
    with get_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM entities WHERE type = ?", ("spec",))
        for row in cursor:
            print(row["id"], row["title"])

    # Transaction handling
    with get_connection(db_path) as conn:
        conn.execute("INSERT INTO entities (...) VALUES (...)")
        conn.commit()  # Auto-commits on successful exit
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cub.core.dashboard.db.schema import create_schema, needs_migration


def dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    """
    Row factory that returns rows as dictionaries.

    Enables dict-like access to query results: row["column_name"]
    instead of positional access: row[0].

    Args:
        cursor: SQLite cursor
        row: Raw row tuple from database

    Returns:
        Dictionary mapping column names to values

    Example:
        >>> conn = sqlite3.connect(":memory:")
        >>> conn.row_factory = dict_factory
        >>> conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        >>> conn.execute("INSERT INTO test VALUES (1, 'Alice')")
        >>> cursor = conn.execute("SELECT * FROM test")
        >>> row = cursor.fetchone()
        >>> assert row["id"] == 1
        >>> assert row["name"] == "Alice"
    """
    fields = [column[0] for column in cursor.description]
    return dict(zip(fields, row))


def configure_connection(conn: sqlite3.Connection) -> None:
    """
    Configure a SQLite connection with optimal settings.

    Settings applied:
    - WAL mode: Better concurrency for reads/writes
    - Foreign keys: Enforce referential integrity
    - dict_factory: Enable dict-like row access

    Args:
        conn: SQLite connection to configure

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> # Foreign keys are now enforced
        >>> # Rows return as dicts
    """
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")

    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys=ON")

    # Use dict row factory for convenient access
    conn.row_factory = dict_factory


def init_db(db_path: Path | str, *, force_recreate: bool = False) -> sqlite3.Connection:
    """
    Initialize the dashboard database.

    Creates the database file if it doesn't exist, applies the schema,
    and returns a configured connection.

    Args:
        db_path: Path to the SQLite database file
        force_recreate: If True, delete existing database and recreate

    Returns:
        Configured SQLite connection

    Example:
        >>> from pathlib import Path
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     db_path = Path(tmpdir) / "test.db"
        ...     conn = init_db(db_path)
        ...     assert conn is not None
        ...     assert db_path.exists()
        ...     conn.close()
    """
    db_path = Path(db_path)

    # Force recreate if requested
    if force_recreate and db_path.exists():
        db_path.unlink()

    # Create parent directory if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect and configure
    conn = sqlite3.connect(str(db_path))
    configure_connection(conn)

    # Create or migrate schema
    if needs_migration(conn):
        create_schema(conn)

    return conn


@contextmanager
def get_connection(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    """
    Get a database connection as a context manager.

    The connection is automatically closed when the context exits.
    If an exception occurs, the transaction is rolled back.

    Args:
        db_path: Path to the SQLite database file

    Yields:
        Configured SQLite connection

    Example:
        >>> from pathlib import Path
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     db_path = Path(tmpdir) / "test.db"
        ...     init_db(db_path)
        ...     with get_connection(db_path) as conn:
        ...         conn.execute("SELECT 1")
        ...         # Connection auto-closes on exit
        <sqlite3.Cursor object at ...>
    """
    db_path = Path(db_path)

    # Initialize if doesn't exist
    if not db_path.exists():
        init_db(db_path)

    conn = sqlite3.connect(str(db_path))
    configure_connection(conn)

    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Execute a query and return all results as a list of dicts.

    Helper function for simple SELECT queries that need all results.

    Args:
        conn: SQLite connection
        query: SQL query string
        params: Query parameters (tuple or dict)

    Returns:
        List of row dictionaries

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> results = execute_query(conn, "SELECT * FROM entities WHERE type = ?", ("spec",))
        >>> assert isinstance(results, list)
    """
    if params is None:
        params = ()

    cursor = conn.execute(query, params)
    return cursor.fetchall()


def execute_one(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Execute a query and return the first result as a dict.

    Helper function for queries that expect a single result.

    Args:
        conn: SQLite connection
        query: SQL query string
        params: Query parameters (tuple or dict)

    Returns:
        First row as dictionary, or None if no results

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> result = execute_one(conn, "SELECT * FROM entities WHERE id = ?", ("spec-1",))
        >>> assert result is None  # No data yet
    """
    if params is None:
        params = ()

    cursor = conn.execute(query, params)
    result = cursor.fetchone()
    # fetchone() returns dict[str, Any] or None when dict_factory is configured
    return result  # type: ignore[no-any-return]


def insert_entity(
    conn: sqlite3.Connection,
    entity_id: str,
    entity_type: str,
    title: str,
    stage: str,
    **kwargs: Any,
) -> None:
    """
    Insert an entity into the database.

    Helper function for inserting entities with common fields.
    Additional fields can be passed as keyword arguments.

    Args:
        conn: SQLite connection
        entity_id: Unique entity identifier
        entity_type: Entity type (spec, plan, epic, task, ledger, release)
        title: Entity title
        stage: Current stage
        **kwargs: Additional fields (status, priority, cost_usd, etc.)

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> insert_entity(
        ...     conn,
        ...     "spec-1",
        ...     "spec",
        ...     "Test Spec",
        ...     "planned",
        ...     status="ready",
        ...     priority="high"
        ... )
        >>> conn.commit()
        >>> result = execute_one(conn, "SELECT * FROM entities WHERE id = ?", ("spec-1",))
        >>> assert result["title"] == "Test Spec"
    """
    # Build column and value lists
    columns = ["id", "type", "title", "stage"]
    values: list[Any] = [entity_id, entity_type, title, stage]

    # Add optional fields
    for key, value in kwargs.items():
        columns.append(key)
        values.append(value)

    # Build and execute query
    placeholders = ",".join("?" * len(columns))
    query = f"INSERT INTO entities ({','.join(columns)}) VALUES ({placeholders})"

    conn.execute(query, tuple(values))


def insert_relationship(
    conn: sqlite3.Connection,
    from_id: str,
    to_id: str,
    rel_type: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Insert a relationship between two entities.

    Helper function for creating entity relationships.

    Args:
        conn: SQLite connection
        from_id: Source entity ID
        to_id: Target entity ID
        rel_type: Relationship type
        metadata: Optional metadata dictionary

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        >>> insert_entity(conn, "plan-1", "plan", "Plan", "staged")
        >>> insert_relationship(conn, "spec-1", "plan-1", "spec_to_plan")
        >>> conn.commit()
    """
    import json

    metadata_json = json.dumps(metadata) if metadata else None

    conn.execute(
        """
        INSERT INTO relationships (from_id, to_id, type, metadata)
        VALUES (?, ?, ?, ?)
        """,
        (from_id, to_id, rel_type, metadata_json),
    )


def upsert_metadata(
    conn: sqlite3.Connection,
    entity_id: str,
    key: str,
    value: str,
) -> None:
    """
    Insert or update metadata for an entity.

    Args:
        conn: SQLite connection
        entity_id: Entity ID
        key: Metadata key
        value: Metadata value

    Example:
        >>> import sqlite3
        >>> conn = sqlite3.connect(":memory:")
        >>> configure_connection(conn)
        >>> create_schema(conn)
        >>> insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        >>> upsert_metadata(conn, "spec-1", "complexity", "high")
        >>> conn.commit()
    """
    conn.execute(
        """
        INSERT INTO metadata (entity_id, key, value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(entity_id, key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (entity_id, key, value),
    )
