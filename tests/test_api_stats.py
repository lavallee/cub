"""
Tests for the dashboard API stats endpoint.

Tests validate:
- GET /api/stats endpoint
- Response model and serialization
- Empty database handling
- Statistics computation accuracy
- Error handling
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cub.core.dashboard.api.app import app
from cub.core.dashboard.db.connection import configure_connection, insert_entity
from cub.core.dashboard.db.schema import create_schema

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


class TestStatsEndpoint:
    """Tests for GET /api/stats endpoint."""

    def test_stats_empty_database(self):
        """Test stats endpoint with no database returns zero stats."""
        with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
            mock_path.return_value = Path("/tmp/nonexistent_db.db")
            response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate stats structure
        assert data["total"] == 0
        assert data["cost_total"] == 0.0
        assert data["tokens_total"] == 0
        assert data["duration_total_seconds"] == 0
        assert data["by_stage"] == {}
        assert data["by_type"] == {}

    def test_stats_with_single_entity(self, temp_db):
        """Test stats endpoint with a single entity."""
        # Add one entity
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        insert_entity(
            conn,
            "task-1",
            "task",
            "Test Task",
            "implementing",
            cost_usd=1.5,
            tokens=1000,
        )

        conn.commit()
        conn.close()

        # Get stats
        with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate single entity stats
        assert data["total"] == 1
        assert data["cost_total"] == 1.5
        assert data["tokens_total"] == 1000
        assert data["by_stage"]["IN_PROGRESS"] == 1
        assert data["by_type"]["task"] == 1

    def test_stats_with_multiple_entities(self, temp_db):
        """Test stats endpoint computes correct aggregates for multiple entities."""
        # Add test entities
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Tasks in different stages
        insert_entity(
            conn,
            "task-1",
            "task",
            "Task 1",
            "implementing",
            cost_usd=2.5,
            tokens=2000,
        )

        insert_entity(
            conn,
            "task-2",
            "task",
            "Task 2",
            "staged",
            cost_usd=1.5,
            tokens=1500,
        )

        insert_entity(
            conn,
            "task-3",
            "task",
            "Task 3",
            "implementing",
            cost_usd=1.0,
            tokens=800,
        )

        # Epic
        insert_entity(
            conn,
            "epic-1",
            "epic",
            "Epic 1",
            "staged",
            cost_usd=0.5,
            tokens=100,
        )

        # Spec
        insert_entity(
            conn,
            "spec-1",
            "spec",
            "Spec 1",
            "researching",
            cost_usd=0.0,
            tokens=0,
        )

        conn.commit()
        conn.close()

        # Get stats
        with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate aggregates
        assert data["total"] == 5
        assert data["cost_total"] == 5.5
        assert data["tokens_total"] == 4400

        # Validate by_stage (using uppercase Stage enum values)
        assert data["by_stage"]["READY"] == 2  # staged -> READY
        assert data["by_stage"]["IN_PROGRESS"] == 2  # implementing -> IN_PROGRESS
        assert data["by_stage"]["RESEARCHING"] == 1  # researching -> RESEARCHING

        # Validate by_type
        assert data["by_type"]["task"] == 3
        assert data["by_type"]["epic"] == 1
        assert data["by_type"]["spec"] == 1

    def test_stats_with_all_stages(self, temp_db):
        """Test stats endpoint with entities in all stages."""
        # Add entities in all possible stages
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        stages = [
            ("backlog", "CAPTURES"),
            ("researching", "RESEARCHING"),
            ("planned", "PLANNED"),
            ("staged", "READY"),
            ("implementing", "IN_PROGRESS"),
            ("verifying", "NEEDS_REVIEW"),
            ("completed", "COMPLETE"),
            ("released", "RELEASED"),
        ]

        for i, (db_stage, _) in enumerate(stages):
            insert_entity(
                conn,
                f"task-{i}",
                "task",
                f"Task {i}",
                db_stage,
                cost_usd=1.0,
                tokens=100,
            )

        conn.commit()
        conn.close()

        # Get stats
        with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate all stages are represented
        assert data["total"] == 8
        assert data["cost_total"] == 8.0
        assert data["tokens_total"] == 800
        assert len(data["by_stage"]) == 8

        # Each stage should have exactly 1 entity
        for _, model_stage in stages:
            assert data["by_stage"][model_stage] == 1

    def test_stats_with_different_types(self, temp_db):
        """Test stats endpoint with different entity types."""
        # Add entities of different types
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Valid entity types from schema: spec, plan, epic, task, ledger, release
        entity_types = ["spec", "plan", "epic", "task", "ledger", "release"]

        for entity_type in entity_types:
            insert_entity(
                conn,
                f"{entity_type}-1",
                entity_type,
                f"Test {entity_type}",
                "implementing",
                cost_usd=1.0,
                tokens=100,
            )

        conn.commit()
        conn.close()

        # Get stats
        with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate type counts
        assert data["total"] == len(entity_types)
        assert len(data["by_type"]) == len(entity_types)

        for entity_type in entity_types:
            assert data["by_type"][entity_type] == 1

    def test_stats_with_zero_costs(self, temp_db):
        """Test stats endpoint correctly handles entities with zero/null costs."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Entity with zero cost
        insert_entity(
            conn,
            "task-1",
            "task",
            "Free Task",
            "implementing",
            cost_usd=0.0,
            tokens=0,
        )

        # Entity with null cost (no cost field)
        insert_entity(
            conn,
            "task-2",
            "task",
            "No Cost Task",
            "implementing",
        )

        conn.commit()
        conn.close()

        # Get stats
        with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate that zero/null costs don't cause issues
        assert data["total"] == 2
        assert data["cost_total"] == 0.0
        assert data["tokens_total"] == 0

    def test_stats_response_schema(self, temp_db):
        """Test that stats response matches expected schema."""
        with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate required keys
        required_keys = {
            "total",
            "by_stage",
            "by_type",
            "cost_total",
            "tokens_total",
            "duration_total_seconds",
        }
        assert set(data.keys()) == required_keys

        # Validate types
        assert isinstance(data["total"], int)
        assert isinstance(data["by_stage"], dict)
        assert isinstance(data["by_type"], dict)
        assert isinstance(data["cost_total"], (int, float))
        assert isinstance(data["tokens_total"], int)
        assert isinstance(data["duration_total_seconds"], int)

        # Validate non-negative values
        assert data["total"] >= 0
        assert data["cost_total"] >= 0.0
        assert data["tokens_total"] >= 0
        assert data["duration_total_seconds"] >= 0


class TestStatsErrorHandling:
    """Tests for error handling in stats endpoint."""

    def test_stats_with_corrupted_database(self):
        """Test stats endpoint handles database errors gracefully."""
        # Create a file that's not a valid SQLite database
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_db = Path(tmpdir) / "bad.db"
            bad_db.write_text("not a database")

            with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
                mock_path.return_value = bad_db
                response = client.get("/api/stats")

        # Should return 500 error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to compute stats" in data["detail"]

    def test_stats_with_missing_permissions(self):
        """Test stats endpoint handles permission errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            configure_connection(conn)
            create_schema(conn)
            conn.commit()
            conn.close()

            # Make database unreadable (Unix only)
            import os
            import stat

            try:
                os.chmod(db_path, 0o000)

                with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
                    mock_path.return_value = db_path
                    response = client.get("/api/stats")

                # Should return 500 error
                assert response.status_code == 500
                data = response.json()
                assert "detail" in data

            finally:
                # Restore permissions for cleanup
                os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)


class TestStatsComparison:
    """Tests to ensure /api/stats matches /api/board/stats behavior."""

    def test_stats_matches_board_stats(self, temp_db):
        """Test that /api/stats returns same data as /api/board/stats."""
        # Add test entities
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        insert_entity(
            conn,
            "task-1",
            "task",
            "Task 1",
            "implementing",
            cost_usd=2.5,
            tokens=2000,
        )

        insert_entity(
            conn,
            "task-2",
            "task",
            "Task 2",
            "staged",
            cost_usd=1.5,
            tokens=1500,
        )

        conn.commit()
        conn.close()

        # Get stats from both endpoints
        with patch("cub.core.dashboard.api.routes.stats.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            stats_response = client.get("/api/stats")

        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            board_stats_response = client.get("/api/board/stats")

        # Both should succeed
        assert stats_response.status_code == 200
        assert board_stats_response.status_code == 200

        # Data should match
        stats_data = stats_response.json()
        board_stats_data = board_stats_response.json()

        assert stats_data["total"] == board_stats_data["total"]
        assert stats_data["cost_total"] == board_stats_data["cost_total"]
        assert stats_data["tokens_total"] == board_stats_data["tokens_total"]
        assert stats_data["by_stage"] == board_stats_data["by_stage"]
        assert stats_data["by_type"] == board_stats_data["by_type"]
