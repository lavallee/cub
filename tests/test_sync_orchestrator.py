"""
Tests for the sync orchestrator and SQLite writer.

Tests cover:
- EntityWriter: Writing entities and relationships to SQLite
- SyncOrchestrator: Coordinating sync from multiple sources
- Checksum-based incremental sync
- Transaction handling and error recovery
- Batch operations
- Database integrity constraints
"""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from cub.core.dashboard.db import get_connection, init_db
from cub.core.dashboard.db.models import (
    DashboardEntity,
    EntityType,
    Relationship,
    RelationType,
    Stage,
)
from cub.core.dashboard.sync.orchestrator import SyncOrchestrator
from cub.core.dashboard.sync.writer import EntityWriter
from cub.core.specs import Stage as SpecStage


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Create temporary database for testing."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def writer(tmp_db: Path) -> EntityWriter:
    """Create EntityWriter with temp database."""
    with get_connection(tmp_db) as conn:
        yield EntityWriter(conn)


@pytest.fixture
def tmp_specs_root(tmp_path: Path) -> Path:
    """Create temporary specs directory structure."""
    specs_root = tmp_path / "specs"
    specs_root.mkdir()

    # Create stage directories
    for stage in SpecStage:
        (specs_root / stage.value).mkdir()

    return specs_root


class TestEntityWriter:
    """Tests for the EntityWriter class."""

    def test_write_entity_minimal(self, tmp_db: Path) -> None:
        """Test writing entity with minimal required fields."""
        entity = DashboardEntity(
            id="spec-1",
            type=EntityType.SPEC,
            title="Test Spec",
            stage=Stage.PLANNED,
            source_type="file",
            source_path="/path/to/spec.md",
        )

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)
            result = writer.write_entity(entity)
            conn.commit()

            assert result is True  # Entity was written

            # Verify entity in database
            cursor = conn.execute("SELECT * FROM entities WHERE id = ?", ("spec-1",))
            row = cursor.fetchone()

            assert row is not None
            assert row["id"] == "spec-1"
            assert row["type"] == "spec"
            assert row["title"] == "Test Spec"
            assert row["stage"] == "planned"  # Schema uses lowercase

    def test_write_entity_full_fields(self, tmp_db: Path) -> None:
        """Test writing entity with all optional fields."""
        entity = DashboardEntity(
            id="spec-2",
            type=EntityType.SPEC,
            title="Full Spec",
            description="Detailed description",
            stage=Stage.IN_PROGRESS,
            status="ready",
            priority=1,
            labels=["complexity:high", "frontend"],
            created_at=datetime(2026, 1, 15),
            updated_at=datetime(2026, 1, 20),
            parent_id="parent-spec",
            spec_id="spec-2",
            cost_usd=2.50,
            tokens=50000,
            source_type="file",
            source_path="/path/to/full-spec.md",
            source_checksum="abc123",
            content="# Full Spec\n\nContent here",
            frontmatter={"priority": "high", "status": "ready"},
        )

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)
            writer.write_entity(entity)
            conn.commit()

            # Verify entity
            cursor = conn.execute("SELECT * FROM entities WHERE id = ?", ("spec-2",))
            row = cursor.fetchone()

            assert row["id"] == "spec-2"
            assert row["priority"] == "1"  # Stored as TEXT in schema
            assert row["status"] == "ready"
            assert row["cost_usd"] == 2.50
            assert row["tokens"] == 50000

            # Verify metadata (labels and references)
            cursor = conn.execute(
                "SELECT key, value FROM metadata WHERE entity_id = ?", ("spec-2",)
            )
            metadata = {row["key"]: row["value"] for row in cursor.fetchall()}

            assert "label:complexity:high" in metadata
            assert "label:frontend" in metadata
            assert metadata["parent_id"] == "parent-spec"
            assert metadata["spec_id"] == "spec-2"

    def test_write_entity_checksum_unchanged_skips(self, tmp_db: Path) -> None:
        """Test that writing entity with same checksum skips update."""
        entity = DashboardEntity(
            id="spec-3",
            type=EntityType.SPEC,
            title="Checksum Test",
            stage=Stage.PLANNED,
            source_type="file",
            source_path="/path/to/spec.md",
            source_checksum="checksum-v1",
        )

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)

            # First write
            result1 = writer.write_entity(entity)
            assert result1 is True

            conn.commit()

            # Second write with same checksum
            result2 = writer.write_entity(entity)
            assert result2 is False  # Skipped

    def test_write_entity_checksum_changed_updates(self, tmp_db: Path) -> None:
        """Test that writing entity with different checksum updates it."""
        entity1 = DashboardEntity(
            id="spec-4",
            type=EntityType.SPEC,
            title="Version 1",
            stage=Stage.PLANNED,
            source_type="file",
            source_path="/path/to/spec.md",
            source_checksum="checksum-v1",
        )

        entity2 = DashboardEntity(
            id="spec-4",
            type=EntityType.SPEC,
            title="Version 2",
            stage=Stage.IN_PROGRESS,
            source_type="file",
            source_path="/path/to/spec.md",
            source_checksum="checksum-v2",
        )

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)

            # Write first version
            writer.write_entity(entity1)
            conn.commit()

            # Write second version
            result = writer.write_entity(entity2)
            assert result is True

            conn.commit()

            # Verify updated
            cursor = conn.execute("SELECT title, stage FROM entities WHERE id = ?", ("spec-4",))
            row = cursor.fetchone()

            assert row["title"] == "Version 2"
            assert row["stage"] == "implementing"  # Schema uses lowercase

    def test_write_entities_batch(self, tmp_db: Path) -> None:
        """Test writing multiple entities in batch."""
        entities = [
            DashboardEntity(
                id=f"spec-{i}",
                type=EntityType.SPEC,
                title=f"Spec {i}",
                stage=Stage.PLANNED,
                source_type="file",
                source_path=f"/path/{i}.md",
                source_checksum=f"checksum-{i}",
            )
            for i in range(5)
        ]

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)
            written, skipped = writer.write_entities(entities)
            conn.commit()

            assert written == 5
            assert skipped == 0

            # Verify all entities written
            cursor = conn.execute("SELECT COUNT(*) as count FROM entities")
            row = cursor.fetchone()
            count = row["count"] if isinstance(row, dict) else row[0]

            assert count == 5

    def test_write_relationship(self, tmp_db: Path) -> None:
        """Test writing relationship between entities."""
        # Create two entities
        entity1 = DashboardEntity(
            id="spec-1",
            type=EntityType.SPEC,
            title="Spec 1",
            stage=Stage.PLANNED,
            source_type="file",
            source_path="/path/spec.md",
        )
        entity2 = DashboardEntity(
            id="plan-1",
            type=EntityType.PLAN,
            title="Plan 1",
            stage=Stage.READY,
            source_type="file",
            source_path="/path/plan.jsonl",
        )

        relationship = Relationship(
            source_id="spec-1",
            target_id="plan-1",
            rel_type=RelationType.SPEC_TO_PLAN,
        )

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)

            # Write entities first
            writer.write_entity(entity1)
            writer.write_entity(entity2)

            # Write relationship
            result = writer.write_relationship(relationship)
            conn.commit()

            assert result is True

            # Verify relationship
            cursor = conn.execute(
                "SELECT * FROM relationships WHERE from_id = ? AND to_id = ?",
                ("spec-1", "plan-1"),
            )
            row = cursor.fetchone()

            assert row is not None
            assert row["from_id"] == "spec-1"
            assert row["to_id"] == "plan-1"
            assert row["type"] == "spec_to_plan"

    def test_write_relationship_duplicate_skipped(self, tmp_db: Path) -> None:
        """Test that duplicate relationships are skipped."""
        # Create entities
        entity1 = DashboardEntity(
            id="spec-1",
            type=EntityType.SPEC,
            title="Spec",
            stage=Stage.PLANNED,
            source_type="file",
            source_path="/path/spec.md",
        )
        entity2 = DashboardEntity(
            id="plan-1",
            type=EntityType.PLAN,
            title="Plan",
            stage=Stage.READY,
            source_type="file",
            source_path="/path/plan.jsonl",
        )

        relationship = Relationship(
            source_id="spec-1",
            target_id="plan-1",
            rel_type=RelationType.SPEC_TO_PLAN,
        )

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)
            writer.write_entity(entity1)
            writer.write_entity(entity2)

            # Write relationship twice
            result1 = writer.write_relationship(relationship)
            conn.commit()

            result2 = writer.write_relationship(relationship)

            assert result1 is True
            assert result2 is False  # Duplicate skipped

    def test_write_relationships_batch(self, tmp_db: Path) -> None:
        """Test writing multiple relationships in batch."""
        # Create entities
        entities = [
            DashboardEntity(
                id=f"entity-{i}",
                type=EntityType.SPEC,
                title=f"Entity {i}",
                stage=Stage.PLANNED,
                source_type="file",
                source_path=f"/path/{i}.md",
            )
            for i in range(3)
        ]

        relationships = [
            Relationship(
                source_id="entity-0",
                target_id="entity-1",
                rel_type=RelationType.DEPENDS_ON,
            ),
            Relationship(
                source_id="entity-1",
                target_id="entity-2",
                rel_type=RelationType.DEPENDS_ON,
            ),
        ]

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)

            # Write entities
            writer.write_entities(entities)

            # Write relationships
            written, skipped = writer.write_relationships(relationships)
            conn.commit()

            assert written == 2
            assert skipped == 0

            # Verify relationships
            cursor = conn.execute("SELECT COUNT(*) as count FROM relationships")
            row = cursor.fetchone()
            count = row["count"] if isinstance(row, dict) else row[0]

            assert count == 2

    def test_delete_entity(self, tmp_db: Path) -> None:
        """Test deleting an entity."""
        entity = DashboardEntity(
            id="spec-delete",
            type=EntityType.SPEC,
            title="Delete Me",
            stage=Stage.PLANNED,
            source_type="file",
            source_path="/path/spec.md",
        )

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)
            writer.write_entity(entity)
            conn.commit()

            # Delete entity
            result = writer.delete_entity("spec-delete")
            conn.commit()

            assert result is True

            # Verify deleted
            cursor = conn.execute("SELECT * FROM entities WHERE id = ?", ("spec-delete",))
            row = cursor.fetchone()

            assert row is None

    def test_delete_entity_cascades_relationships(self, tmp_db: Path) -> None:
        """Test that deleting entity cascades to relationships."""
        entity1 = DashboardEntity(
            id="spec-1",
            type=EntityType.SPEC,
            title="Spec",
            stage=Stage.PLANNED,
            source_type="file",
            source_path="/path/spec.md",
        )
        entity2 = DashboardEntity(
            id="plan-1",
            type=EntityType.PLAN,
            title="Plan",
            stage=Stage.READY,
            source_type="file",
            source_path="/path/plan.jsonl",
        )

        relationship = Relationship(
            source_id="spec-1",
            target_id="plan-1",
            rel_type=RelationType.SPEC_TO_PLAN,
        )

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)
            writer.write_entity(entity1)
            writer.write_entity(entity2)
            writer.write_relationship(relationship)
            conn.commit()

            # Delete spec
            writer.delete_entity("spec-1")
            conn.commit()

            # Verify relationship deleted
            cursor = conn.execute(
                "SELECT * FROM relationships WHERE from_id = ?", ("spec-1",)
            )
            row = cursor.fetchone()

            assert row is None

    def test_clear_all_entities(self, tmp_db: Path) -> None:
        """Test clearing all entities from database."""
        entities = [
            DashboardEntity(
                id=f"spec-{i}",
                type=EntityType.SPEC,
                title=f"Spec {i}",
                stage=Stage.PLANNED,
                source_type="file",
                source_path=f"/path/{i}.md",
            )
            for i in range(3)
        ]

        with get_connection(tmp_db) as conn:
            writer = EntityWriter(conn)
            writer.write_entities(entities)
            conn.commit()

            # Clear all
            count = writer.clear_all_entities()
            conn.commit()

            assert count == 3

            # Verify empty
            cursor = conn.execute("SELECT COUNT(*) as count FROM entities")
            row = cursor.fetchone()
            remaining = row["count"] if isinstance(row, dict) else row[0]

            assert remaining == 0


class TestSyncOrchestrator:
    """Tests for the SyncOrchestrator class."""

    def test_init_creates_database(self, tmp_path: Path, tmp_specs_root: Path) -> None:
        """Test that orchestrator initializes database on init."""
        db_path = tmp_path / "new.db"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=tmp_specs_root)

        assert db_path.exists()
        assert orchestrator.db_path == db_path

    def test_sync_empty_specs(self, tmp_path: Path, tmp_specs_root: Path) -> None:
        """Test syncing with no specs available."""
        db_path = tmp_path / "test.db"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=tmp_specs_root)

        result = orchestrator.sync()

        assert result.success is True
        assert result.entities_added == 0
        assert "specs" in result.sources_synced

    def test_sync_specs_creates_entities(
        self, tmp_path: Path, tmp_specs_root: Path
    ) -> None:
        """Test syncing specs creates entities in database."""
        # Create some spec files
        spec_content = """---
priority: high
complexity: medium
---

# Test Spec

This is a test specification.
"""
        for i in range(3):
            spec_file = tmp_specs_root / "planned" / f"spec-{i}.md"
            spec_file.write_text(spec_content)

        db_path = tmp_path / "test.db"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=tmp_specs_root)

        result = orchestrator.sync()

        assert result.success is True
        assert result.entities_added == 3
        assert result.entities_updated == 0
        assert "specs" in result.sources_synced

        # Verify entities in database
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM entities WHERE type = 'spec'")
            row = cursor.fetchone()
            count = row["count"] if isinstance(row, dict) else row[0]

            assert count == 3

    def test_sync_incremental_skips_unchanged(
        self, tmp_path: Path, tmp_specs_root: Path
    ) -> None:
        """Test that incremental sync skips unchanged specs."""
        # Create spec file
        spec_file = tmp_specs_root / "planned" / "spec-1.md"
        spec_file.write_text("---\npriority: high\n---\n# Spec 1")

        db_path = tmp_path / "test.db"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=tmp_specs_root)

        # First sync
        result1 = orchestrator.sync()
        assert result1.entities_added == 1

        # Second sync (nothing changed)
        result2 = orchestrator.sync()
        assert result2.entities_added == 0  # Skipped

    def test_sync_incremental_updates_changed(
        self, tmp_path: Path, tmp_specs_root: Path
    ) -> None:
        """Test that incremental sync updates changed specs."""
        spec_file = tmp_specs_root / "planned" / "spec-1.md"
        spec_file.write_text("---\npriority: high\n---\n# Version 1")

        db_path = tmp_path / "test.db"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=tmp_specs_root)

        # First sync
        result1 = orchestrator.sync()
        assert result1.entities_added == 1

        # Modify spec file
        spec_file.write_text("---\npriority: high\n---\n# Version 2")

        # Second sync (content changed)
        result2 = orchestrator.sync()
        assert result2.entities_added == 1  # Re-added

        # Verify title updated
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT title FROM entities WHERE id = ?", ("spec-1",))
            row = cursor.fetchone()
            title = row["title"] if isinstance(row, dict) else row[0]

            assert title == "Version 2"

    def test_sync_nonexistent_specs_root(self, tmp_path: Path) -> None:
        """Test sync with nonexistent specs root."""
        db_path = tmp_path / "test.db"
        specs_root = tmp_path / "nonexistent"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=specs_root)

        result = orchestrator.sync()

        assert result.success is True  # Not an error, just no specs
        assert result.entities_added == 0

    def test_sync_transaction_rollback_on_error(
        self, tmp_path: Path, tmp_specs_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that sync rolls back transaction on error."""
        # Create spec file
        spec_file = tmp_specs_root / "planned" / "spec-1.md"
        spec_file.write_text("---\npriority: high\n---\n# Spec")

        db_path = tmp_path / "test.db"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=tmp_specs_root)

        # Mock writer to raise an error
        original_write_entities = EntityWriter.write_entities

        def failing_write_entities(self, entities):
            raise RuntimeError("Simulated error")

        monkeypatch.setattr(EntityWriter, "write_entities", failing_write_entities)

        result = orchestrator.sync()

        assert result.success is False
        assert len(result.errors) > 0

        # Verify no entities written (transaction rolled back)
        with get_connection(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM entities")
            row = cursor.fetchone()
            count = row["count"] if isinstance(row, dict) else row[0]

            assert count == 0

    def test_get_stats(self, tmp_path: Path, tmp_specs_root: Path) -> None:
        """Test getting database statistics."""
        # Create specs in different stages
        for stage in ["researching", "planned", "staged"]:
            spec_file = tmp_specs_root / stage / f"spec-{stage}.md"
            spec_file.write_text(f"---\npriority: medium\n---\n# {stage.title()}")

        db_path = tmp_path / "test.db"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=tmp_specs_root)
        orchestrator.sync()

        stats = orchestrator.get_stats()

        assert stats["total"] == 3
        assert stats["by_type"]["spec"] == 3
        assert len(stats["by_stage"]) > 0  # At least one stage has entities

    def test_sync_without_specs_root(self, tmp_path: Path) -> None:
        """Test orchestrator without specs_root configured."""
        db_path = tmp_path / "test.db"

        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=None)

        result = orchestrator.sync()

        assert result.success is True
        assert result.entities_added == 0
        assert "specs" not in result.sources_synced


class TestIntegration:
    """Integration tests for the full sync pipeline."""

    def test_full_sync_pipeline(self, tmp_path: Path) -> None:
        """Test complete sync pipeline from files to database to stats."""
        # Create project structure
        specs_root = tmp_path / "specs"
        specs_root.mkdir()

        for stage in SpecStage:
            stage_dir = specs_root / stage.value
            stage_dir.mkdir()

            # Create 2 specs per stage
            for i in range(2):
                spec_content = f"""---
priority: high
complexity: medium
status: ready
---

# {stage.value.title()} Spec {i}

Test content for {stage.value} stage.
"""
                spec_file = stage_dir / f"{stage.value}-{i}.md"
                spec_file.write_text(spec_content)

        db_path = tmp_path / "dashboard.db"

        # Initialize orchestrator and sync
        orchestrator = SyncOrchestrator(db_path=db_path, specs_root=specs_root)
        result = orchestrator.sync()

        # Verify sync results
        assert result.success is True
        assert result.entities_added == 10  # 2 specs × 5 stages
        assert result.duration_seconds > 0

        # Verify database stats
        stats = orchestrator.get_stats()
        assert stats["total"] == 10
        assert stats["by_type"]["spec"] == 10

        # Verify entities queryable
        with get_connection(db_path) as conn:
            cursor = conn.execute(
                "SELECT id, title, stage FROM entities ORDER BY id"
            )
            entities = cursor.fetchall()

            assert len(entities) == 10

            # Verify first entity
            first = entities[0]
            assert "id" in first
            assert "title" in first
            assert "stage" in first
