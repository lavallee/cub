"""
Tests for dashboard database schema and connection management.

Comprehensive tests for the dashboard SQLite database including:
- Schema creation and migrations
- Connection management
- Query helpers
- Data integrity constraints
- Transaction handling
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from cub.core.dashboard.db import (
    create_schema,
    get_connection,
    init_db,
)
from cub.core.dashboard.db.connection import (
    configure_connection,
    dict_factory,
    execute_one,
    execute_query,
    insert_entity,
    insert_relationship,
    upsert_metadata,
)
from cub.core.dashboard.db.schema import (
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    SCHEMA_VERSION,
    STAGES,
    get_schema_version,
    needs_migration,
    validate_entity_type,
    validate_relationship_type,
    validate_stage,
)


class TestDictFactory:
    """Tests for dict_factory row factory."""

    def test_dict_factory_returns_dict(self) -> None:
        """Test that dict_factory returns a dictionary."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = dict_factory
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'Alice')")

        cursor = conn.execute("SELECT * FROM test")
        row = cursor.fetchone()

        assert isinstance(row, dict)
        assert row["id"] == 1
        assert row["name"] == "Alice"

    def test_dict_factory_multiple_columns(self) -> None:
        """Test dict_factory with multiple columns."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = dict_factory
        conn.execute("CREATE TABLE test (a INT, b TEXT, c REAL)")
        conn.execute("INSERT INTO test VALUES (1, 'test', 3.14)")

        cursor = conn.execute("SELECT * FROM test")
        row = cursor.fetchone()

        assert row["a"] == 1
        assert row["b"] == "test"
        assert row["c"] == 3.14


class TestSchema:
    """Tests for schema creation and validation."""

    def test_create_schema_creates_tables(self) -> None:
        """Test that create_schema creates all required tables."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "schema_info" in tables
        assert "entities" in tables
        assert "relationships" in tables
        assert "metadata" in tables

    def test_create_schema_creates_indexes(self) -> None:
        """Test that create_schema creates indexes."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = [row[0] for row in cursor.fetchall()]

        # Check for key indexes
        assert any("idx_entities_type" in idx for idx in indexes)
        assert any("idx_entities_stage" in idx for idx in indexes)
        assert any("idx_relationships_from" in idx for idx in indexes)

    def test_create_schema_records_version(self) -> None:
        """Test that create_schema records the schema version."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        cursor = conn.execute("SELECT version FROM schema_info")
        version = cursor.fetchone()[0]

        assert version == SCHEMA_VERSION

    def test_create_schema_idempotent(self) -> None:
        """Test that create_schema can be called multiple times safely."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)
        create_schema(conn)  # Should not raise

        cursor = conn.execute("SELECT COUNT(*) FROM schema_info")
        count = cursor.fetchone()[0]

        assert count == 1  # Only one version record

    def test_get_schema_version_returns_current(self) -> None:
        """Test get_schema_version returns current version."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        version = get_schema_version(conn)

        assert version == SCHEMA_VERSION

    def test_get_schema_version_no_schema(self) -> None:
        """Test get_schema_version returns None when no schema exists."""
        conn = sqlite3.connect(":memory:")

        version = get_schema_version(conn)

        assert version is None

    def test_needs_migration_true_when_no_schema(self) -> None:
        """Test needs_migration returns True when database is empty."""
        conn = sqlite3.connect(":memory:")

        assert needs_migration(conn) is True

    def test_needs_migration_false_when_current(self) -> None:
        """Test needs_migration returns False when schema is current."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        assert needs_migration(conn) is False


class TestValidation:
    """Tests for validation functions."""

    def test_validate_entity_type_accepts_valid(self) -> None:
        """Test that validate_entity_type accepts all valid types."""
        for entity_type in ENTITY_TYPES:
            validate_entity_type(entity_type)  # Should not raise

    def test_validate_entity_type_rejects_invalid(self) -> None:
        """Test that validate_entity_type rejects invalid types."""
        with pytest.raises(ValueError) as exc_info:
            validate_entity_type("invalid")
        assert "Invalid entity type" in str(exc_info.value)

    def test_validate_stage_accepts_valid(self) -> None:
        """Test that validate_stage accepts all valid stages."""
        for stage in STAGES:
            validate_stage(stage)  # Should not raise

    def test_validate_stage_rejects_invalid(self) -> None:
        """Test that validate_stage rejects invalid stages."""
        with pytest.raises(ValueError) as exc_info:
            validate_stage("invalid")
        assert "Invalid stage" in str(exc_info.value)

    def test_validate_relationship_type_accepts_valid(self) -> None:
        """Test that validate_relationship_type accepts all valid types."""
        for rel_type in RELATIONSHIP_TYPES:
            validate_relationship_type(rel_type)  # Should not raise

    def test_validate_relationship_type_rejects_invalid(self) -> None:
        """Test that validate_relationship_type rejects invalid types."""
        with pytest.raises(ValueError) as exc_info:
            validate_relationship_type("invalid")
        assert "Invalid relationship type" in str(exc_info.value)


class TestConnection:
    """Tests for connection management."""

    def test_configure_connection_sets_row_factory(self) -> None:
        """Test that configure_connection sets dict row factory."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)

        assert conn.row_factory == dict_factory

    def test_configure_connection_enables_foreign_keys(self) -> None:
        """Test that configure_connection enables foreign key enforcement."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)

        cursor = conn.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        enabled = result["foreign_keys"] if isinstance(result, dict) else result[0]

        assert enabled == 1

    def test_init_db_creates_file(self) -> None:
        """Test that init_db creates database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            conn = init_db(db_path)
            conn.close()

            assert db_path.exists()

    def test_init_db_creates_schema(self) -> None:
        """Test that init_db creates schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            conn = init_db(db_path)

            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
            )
            result = cursor.fetchone()

            assert result is not None
            conn.close()

    def test_init_db_force_recreate(self) -> None:
        """Test that init_db force_recreate deletes existing database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Create initial database with data
            conn1 = init_db(db_path)
            insert_entity(conn1, "test-1", "spec", "Test", "planned")
            conn1.commit()
            conn1.close()

            # Force recreate
            conn2 = init_db(db_path, force_recreate=True)

            cursor = conn2.execute("SELECT COUNT(*) FROM entities")
            result = cursor.fetchone()
            count = result["COUNT(*)"] if isinstance(result, dict) else result[0]

            assert count == 0  # Data should be gone
            conn2.close()

    def test_get_connection_context_manager(self) -> None:
        """Test that get_connection works as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_db(db_path)

            with get_connection(db_path) as conn:
                cursor = conn.execute("SELECT 1 as value")
                result = cursor.fetchone()
                value = result["value"] if isinstance(result, dict) else result[0]
                assert value == 1

    def test_get_connection_initializes_if_missing(self) -> None:
        """Test that get_connection initializes database if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            with get_connection(db_path) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='entities'"
                )
                result = cursor.fetchone()
                assert result is not None


class TestQueryHelpers:
    """Tests for query helper functions."""

    def test_execute_query_returns_all_rows(self) -> None:
        """Test that execute_query returns all rows."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec 1", "planned")
        insert_entity(conn, "spec-2", "spec", "Spec 2", "planned")
        conn.commit()

        results = execute_query(conn, "SELECT * FROM entities WHERE type = ?", ("spec",))

        assert len(results) == 2
        assert results[0]["id"] == "spec-1"
        assert results[1]["id"] == "spec-2"

    def test_execute_query_empty_result(self) -> None:
        """Test that execute_query returns empty list when no results."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        results = execute_query(conn, "SELECT * FROM entities WHERE type = ?", ("spec",))

        assert results == []

    def test_execute_one_returns_first_row(self) -> None:
        """Test that execute_one returns first row."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec 1", "planned")
        insert_entity(conn, "spec-2", "spec", "Spec 2", "planned")
        conn.commit()

        result = execute_one(conn, "SELECT * FROM entities WHERE id = ?", ("spec-1",))

        assert result is not None
        assert result["id"] == "spec-1"

    def test_execute_one_returns_none_when_empty(self) -> None:
        """Test that execute_one returns None when no results."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        result = execute_one(conn, "SELECT * FROM entities WHERE id = ?", ("missing",))

        assert result is None


class TestEntityOperations:
    """Tests for entity CRUD operations."""

    def test_insert_entity_minimal(self) -> None:
        """Test inserting entity with minimal fields."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Test Spec", "planned")
        conn.commit()

        result = execute_one(conn, "SELECT * FROM entities WHERE id = ?", ("spec-1",))

        assert result is not None
        assert result["id"] == "spec-1"
        assert result["type"] == "spec"
        assert result["title"] == "Test Spec"
        assert result["stage"] == "planned"

    def test_insert_entity_with_optional_fields(self) -> None:
        """Test inserting entity with optional fields."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(
            conn,
            "spec-1",
            "spec",
            "Test Spec",
            "planned",
            status="ready",
            priority="high",
            cost_usd=0.50,
            tokens=10000,
            file_path="specs/planned/test.md",
        )
        conn.commit()

        result = execute_one(conn, "SELECT * FROM entities WHERE id = ?", ("spec-1",))

        assert result["status"] == "ready"
        assert result["priority"] == "high"
        assert result["cost_usd"] == 0.50
        assert result["tokens"] == 10000
        assert result["file_path"] == "specs/planned/test.md"

    def test_insert_entity_duplicate_id_fails(self) -> None:
        """Test that inserting duplicate entity ID raises error."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Test Spec", "planned")
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            insert_entity(conn, "spec-1", "spec", "Another Spec", "planned")

    def test_entity_type_constraint(self) -> None:
        """Test that invalid entity type is rejected by database."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO entities (id, type, title, stage)
                VALUES (?, ?, ?, ?)
                """,
                ("test-1", "invalid", "Test", "planned"),
            )

    def test_entity_stage_constraint(self) -> None:
        """Test that invalid stage is rejected by database."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO entities (id, type, title, stage)
                VALUES (?, ?, ?, ?)
                """,
                ("test-1", "spec", "Test", "invalid"),
            )


class TestRelationshipOperations:
    """Tests for relationship CRUD operations."""

    def test_insert_relationship(self) -> None:
        """Test inserting relationship between entities."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        insert_entity(conn, "plan-1", "plan", "Plan", "staged")
        insert_relationship(conn, "spec-1", "plan-1", "spec_to_plan")
        conn.commit()

        result = execute_one(
            conn,
            "SELECT * FROM relationships WHERE from_id = ? AND to_id = ?",
            ("spec-1", "plan-1"),
        )

        assert result is not None
        assert result["from_id"] == "spec-1"
        assert result["to_id"] == "plan-1"
        assert result["type"] == "spec_to_plan"

    def test_insert_relationship_with_metadata(self) -> None:
        """Test inserting relationship with metadata."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        insert_entity(conn, "plan-1", "plan", "Plan", "staged")
        insert_relationship(
            conn, "spec-1", "plan-1", "spec_to_plan", metadata={"note": "test"}
        )
        conn.commit()

        result = execute_one(
            conn,
            "SELECT * FROM relationships WHERE from_id = ?",
            ("spec-1",),
        )

        assert result is not None
        assert result["metadata"] is not None
        metadata = json.loads(result["metadata"])
        assert metadata["note"] == "test"

    def test_relationship_duplicate_prevented(self) -> None:
        """Test that duplicate relationships are prevented."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        insert_entity(conn, "plan-1", "plan", "Plan", "staged")
        insert_relationship(conn, "spec-1", "plan-1", "spec_to_plan")
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            insert_relationship(conn, "spec-1", "plan-1", "spec_to_plan")

    def test_relationship_foreign_key_enforced(self) -> None:
        """Test that foreign key constraints are enforced."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        with pytest.raises(sqlite3.IntegrityError):
            insert_relationship(conn, "missing-1", "missing-2", "spec_to_plan")

    def test_relationship_cascade_delete(self) -> None:
        """Test that relationships are deleted when entity is deleted."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        insert_entity(conn, "plan-1", "plan", "Plan", "staged")
        insert_relationship(conn, "spec-1", "plan-1", "spec_to_plan")
        conn.commit()

        # Delete the spec
        conn.execute("DELETE FROM entities WHERE id = ?", ("spec-1",))
        conn.commit()

        # Relationship should be gone
        result = execute_one(
            conn,
            "SELECT * FROM relationships WHERE from_id = ?",
            ("spec-1",),
        )

        assert result is None


class TestMetadataOperations:
    """Tests for metadata CRUD operations."""

    def test_upsert_metadata_insert(self) -> None:
        """Test inserting new metadata."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        upsert_metadata(conn, "spec-1", "complexity", "high")
        conn.commit()

        result = execute_one(
            conn,
            "SELECT * FROM metadata WHERE entity_id = ? AND key = ?",
            ("spec-1", "complexity"),
        )

        assert result is not None
        assert result["value"] == "high"

    def test_upsert_metadata_update(self) -> None:
        """Test updating existing metadata."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        upsert_metadata(conn, "spec-1", "complexity", "low")
        conn.commit()

        upsert_metadata(conn, "spec-1", "complexity", "high")
        conn.commit()

        result = execute_one(
            conn,
            "SELECT * FROM metadata WHERE entity_id = ? AND key = ?",
            ("spec-1", "complexity"),
        )

        assert result is not None
        assert result["value"] == "high"

    def test_metadata_cascade_delete(self) -> None:
        """Test that metadata is deleted when entity is deleted."""
        conn = sqlite3.connect(":memory:")
        configure_connection(conn)
        create_schema(conn)

        insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        upsert_metadata(conn, "spec-1", "complexity", "high")
        conn.commit()

        conn.execute("DELETE FROM entities WHERE id = ?", ("spec-1",))
        conn.commit()

        result = execute_one(
            conn,
            "SELECT * FROM metadata WHERE entity_id = ?",
            ("spec-1",),
        )

        assert result is None


class TestIndexPerformance:
    """Tests to verify indexes exist for common queries."""

    def test_entities_type_index_exists(self) -> None:
        """Test that type index exists for filtering by entity type."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_entities_type'"
        )
        result = cursor.fetchone()

        assert result is not None

    def test_entities_stage_index_exists(self) -> None:
        """Test that stage index exists for Kanban queries."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_entities_stage'"
        )
        result = cursor.fetchone()

        assert result is not None

    def test_relationships_from_index_exists(self) -> None:
        """Test that from_id index exists for relationship queries."""
        conn = sqlite3.connect(":memory:")
        create_schema(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_relationships_from'"
        )
        result = cursor.fetchone()

        assert result is not None
