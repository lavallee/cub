"""Tests for the dashboard API entity update endpoints.

Tests validate:
- PATCH /api/entity/{id} endpoint workflow stage updates
- Invalid stage validation (400 status code)
- Entity not found handling (404 status code)
- Ledger writeback on successful updates
- Workflow stage persistence
"""

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cub.core.dashboard.api.app import app
from cub.core.dashboard.db.connection import configure_connection, insert_entity
from cub.core.dashboard.db.schema import create_schema
from cub.core.ledger.models import (
    LedgerEntry,
    TokenUsage,
    VerificationStatus,
    WorkflowStage,
)
from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.writer import LedgerWriter

# Create test client
client = TestClient(app)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        configure_connection(conn)
        create_schema(conn)
        conn.commit()
        conn.close()
        yield db_path


@pytest.fixture
def temp_ledger_dir(tmp_path: Path) -> Path:
    """Create a temporary ledger directory."""
    ledger = tmp_path / ".cub" / "ledger"
    ledger.mkdir(parents=True)
    return ledger


@pytest.fixture
def sample_entity_in_db(temp_db) -> str:
    """Create a sample entity in the test database.

    Returns the entity ID.
    """
    entity_id = "task-1"
    conn = sqlite3.connect(str(temp_db))
    configure_connection(conn)

    insert_entity(
        conn,
        entity_id,
        "task",
        "Test Task",
        "implementing",
        status="in_progress",
        priority="high",
        cost_usd=1.5,
        tokens=1000,
        data='{"labels": ["test"], "content": "Test content"}',
    )

    conn.commit()
    conn.close()
    return entity_id


@pytest.fixture
def sample_ledger_entry(temp_ledger_dir: Path) -> tuple[str, LedgerEntry]:
    """Create a sample ledger entry and write it to disk.

    Returns tuple of (task_id, entry).
    """
    task_id = "cub-m4j.1"
    entry = LedgerEntry(
        id=task_id,
        title="Test task for workflow",
        epic_id="cub-m4j",
        spec_file="specs/planned/test.md",
        files_changed=["src/test.py"],
        tokens=TokenUsage(input_tokens=800, output_tokens=200),
        cost_usd=0.05,
        harness_name="claude",
        completed_at=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        verification_status=VerificationStatus.PASS,
    )

    writer = LedgerWriter(temp_ledger_dir)
    writer.create_entry(entry)

    return task_id, entry


class TestPatchEntityWorkflow:
    """Tests for PATCH /api/entity/{id} endpoint."""

    def test_patch_entity_update_to_validated(self, temp_db, sample_entity_in_db):
        """Test updating entity workflow stage to validated."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "validated"}, "reason": "Tests passed"},
            )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "entity" in data
        assert "relationships" in data

    def test_patch_entity_update_to_needs_review(self, temp_db, sample_entity_in_db):
        """Test updating entity to needs_review stage."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "needs_review"}},
            )

        assert response.status_code == 200
        data = response.json()
        assert "entity" in data

    def test_patch_entity_update_to_released(self, temp_db, sample_entity_in_db):
        """Test updating entity to released stage."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "released"}},
            )

        assert response.status_code == 200
        data = response.json()
        assert "entity" in data

    def test_patch_entity_update_to_complete(self, temp_db, sample_entity_in_db):
        """Test clearing workflow stage by setting to COMPLETE."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            # First set to validated
            client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "validated"}},
            )

            # Then set back to COMPLETE
            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "complete"}},
            )

        assert response.status_code == 200

    def test_patch_entity_with_reason(self, temp_db, sample_entity_in_db):
        """Test PATCH endpoint accepts reason parameter."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                f"/api/entity/{entity_id}",
                json={
                    "workflow": {"stage": "validated"},
                    "reason": "Thoroughly tested and approved",
                },
            )

        assert response.status_code == 200

    def test_patch_entity_case_insensitive_stage(self, temp_db, sample_entity_in_db):
        """Test that stage names are case-insensitive."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            # Test with lowercase
            response1 = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "validated"}},
            )
            assert response1.status_code == 200

            # Test with uppercase
            response2 = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "VALIDATED"}},
            )
            assert response2.status_code == 200

            # Test with mixed case
            response3 = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "VaLiDaTeD"}},
            )
            assert response3.status_code == 200


class TestInvalidStageValidation:
    """Tests for invalid stage validation."""

    def test_patch_entity_invalid_stage(self, temp_db, sample_entity_in_db):
        """Test that invalid stage returns 400 error."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "invalid_stage"}},
            )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid workflow stage" in data["detail"]

    def test_patch_entity_invalid_stage_message(self, temp_db, sample_entity_in_db):
        """Test that error message lists valid stages."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "not_a_stage"}},
            )

        assert response.status_code == 400
        data = response.json()
        detail = data["detail"]

        # Verify valid stages are mentioned
        assert "COMPLETE" in detail
        assert "NEEDS_REVIEW" in detail
        assert "VALIDATED" in detail
        assert "RELEASED" in detail

    def test_patch_entity_empty_stage(self, temp_db, sample_entity_in_db):
        """Test that empty stage returns error."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": ""}},
            )

        # Empty string is treated as invalid stage
        assert response.status_code == 400

    def test_patch_entity_none_stage(self, temp_db, sample_entity_in_db):
        """Test that null stage returns validation error."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": None}},
            )

        # Should fail validation
        assert response.status_code in [400, 422]


class TestEntityNotFoundHandling:
    """Tests for 404 handling when entity doesn't exist."""

    def test_patch_nonexistent_entity(self, temp_db):
        """Test updating non-existent entity returns 404."""
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            response = client.patch(
                "/api/entity/nonexistent-id",
                json={"workflow": {"stage": "validated"}},
            )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Entity not found" in data["detail"]
        assert "nonexistent-id" in data["detail"]

    def test_patch_entity_no_database(self):
        """Test updating entity when database doesn't exist."""
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = Path("/tmp/nonexistent_db_12345.db")

            response = client.patch(
                "/api/entity/any-id",
                json={"workflow": {"stage": "validated"}},
            )

        assert response.status_code == 404


class TestLedgerWriteback:
    """Tests for ledger writeback when updating workflow stage."""

    def test_ledger_updated_on_workflow_change(
        self, temp_db, sample_ledger_entry, temp_ledger_dir
    ):
        """Test that ledger is updated when workflow stage changes."""
        task_id, entry = sample_ledger_entry

        # Add the entity to the database
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)
        create_schema(conn)

        insert_entity(
            conn,
            task_id,
            "task",
            "Test Task",
            "completed",
            status="completed",
            priority="medium",
            cost_usd=0.05,
            tokens=1000,
            data="{}",
        )
        conn.commit()
        conn.close()

        # Patch with both db and ledger paths
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_db:
            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_db.return_value = temp_db
                mock_cwd.return_value = temp_ledger_dir.parent.parent

                response = client.patch(
                    f"/api/entity/{task_id}",
                    json={"workflow": {"stage": "validated"}},
                )

        assert response.status_code == 200

        # Verify ledger was updated
        reader = LedgerReader(temp_ledger_dir)
        updated_entry = reader.get_task(task_id)
        assert updated_entry is not None
        assert updated_entry.workflow.stage == "validated"

    def test_ledger_cleared_on_complete_stage(
        self, temp_db, sample_ledger_entry, temp_ledger_dir
    ):
        """Test that ledger workflow stage is cleared when set to COMPLETE."""
        task_id, entry = sample_ledger_entry

        # Set entry to validated first
        entry.workflow_stage = WorkflowStage.VALIDATED
        writer = LedgerWriter(temp_ledger_dir)
        writer.update_entry(entry)

        # Add entity to database
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)
        create_schema(conn)

        insert_entity(
            conn,
            task_id,
            "task",
            "Test Task",
            "validated",
            status="completed",
            priority="medium",
            cost_usd=0.05,
            tokens=1000,
            data="{}",
        )
        conn.commit()
        conn.close()

        # Patch to COMPLETE
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_db:
            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_db.return_value = temp_db
                mock_cwd.return_value = temp_ledger_dir.parent.parent

                response = client.patch(
                    f"/api/entity/{task_id}",
                    json={"workflow": {"stage": "complete"}},
                )

        assert response.status_code == 200

        # Verify ledger workflow stage was cleared (set to dev_complete)
        reader = LedgerReader(temp_ledger_dir)
        updated_entry = reader.get_task(task_id)
        assert updated_entry is not None
        assert updated_entry.workflow.stage == "dev_complete"

    def test_ledger_optional_no_entry(self, temp_db, sample_entity_in_db):
        """Test that missing ledger entry doesn't block database update."""
        # This tests that updating workflow stage works even if there's no
        # corresponding ledger entry (e.g., for epics)
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_path.return_value = temp_db
                # Point to non-existent ledger
                mock_cwd.return_value = Path("/tmp/nonexistent")

                response = client.patch(
                    f"/api/entity/{entity_id}",
                    json={"workflow": {"stage": "validated"}},
                )

        # Should still succeed - database update is what matters
        assert response.status_code == 200


class TestDatabaseUpdatePersistence:
    """Tests that database updates persist correctly."""

    def test_workflow_stage_persisted_in_database(self, temp_db, sample_entity_in_db):
        """Test that workflow stage is persisted in database."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            # Update to validated
            response = client.patch(
                f"/api/entity/{entity_id}",
                json={"workflow": {"stage": "validated"}},
            )

        assert response.status_code == 200

        # Verify database was updated
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT stage FROM entities WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "validated"

    def test_multiple_sequential_updates(self, temp_db, sample_entity_in_db):
        """Test multiple workflow stage updates in sequence."""
        entity_id = sample_entity_in_db

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            stages = ["needs_review", "validated", "released"]

            for stage in stages:
                response = client.patch(
                    f"/api/entity/{entity_id}",
                    json={"workflow": {"stage": stage}},
                )
                assert response.status_code == 200

            # Verify final stage in database
            conn = sqlite3.connect(str(temp_db))
            cursor = conn.execute(
                "SELECT stage FROM entities WHERE id = ?", (entity_id,)
            )
            row = cursor.fetchone()
            conn.close()

            assert row is not None
            assert row[0] == "released"

    def test_update_does_not_affect_other_entities(self, temp_db):
        """Test that updating one entity doesn't affect others."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)
        create_schema(conn)

        # Create two entities
        insert_entity(
            conn, "entity-1", "task", "Task 1", "implementing", status="in_progress"
        )
        insert_entity(
            conn, "entity-2", "task", "Task 2", "implementing", status="in_progress"
        )
        conn.commit()
        conn.close()

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db

            # Update only entity-1
            response = client.patch(
                "/api/entity/entity-1",
                json={"workflow": {"stage": "validated"}},
            )

        assert response.status_code == 200

        # Verify entity-1 was updated
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT stage FROM entities WHERE id = ?", ("entity-1",))
        assert cursor.fetchone()[0] == "validated"

        # Verify entity-2 was not affected
        cursor = conn.execute("SELECT stage FROM entities WHERE id = ?", ("entity-2",))
        assert cursor.fetchone()[0] == "implementing"
        conn.close()
