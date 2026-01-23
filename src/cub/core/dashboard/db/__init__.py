"""
Database layer for cub dashboard.

Provides SQLite schema and connection management for aggregating
project data from multiple sources (specs, plans, tasks, ledger, changelog).

The database serves as the central data aggregation layer that powers
all dashboard API queries and the Kanban board UI.

Main components:
- schema.py: SQL schema definitions and migrations
- connection.py: Database connection management and query helpers

Usage:
    from cub.core.dashboard.db import get_connection, init_db

    # Initialize database
    conn = init_db(db_path)

    # Query entities
    with get_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM entities WHERE type = ?", ("spec",))
        specs = cursor.fetchall()
"""

from cub.core.dashboard.db.connection import get_connection, init_db
from cub.core.dashboard.db.schema import SCHEMA_VERSION, create_schema

__all__ = [
    "get_connection",
    "init_db",
    "create_schema",
    "SCHEMA_VERSION",
]
