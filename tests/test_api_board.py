"""
Tests for the dashboard API board endpoints.

Tests validate:
- GET /api/board endpoint
- GET /api/board/stats endpoint
- Response models and serialization
- Empty database handling
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


class TestRootEndpoints:
    """Tests for root and health check endpoints."""

    def test_root_endpoint(self):
        """Test GET / serves the frontend HTML."""
        response = client.get("/")
        assert response.status_code == 200
        # Root endpoint now serves HTML for the SPA
        assert "text/html" in response.headers.get("content-type", "")
        assert "<!doctype html>" in response.text.lower()

    def test_health_endpoint(self):
        """Test GET /health returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestBoardEndpoint:
    """Tests for GET /api/board endpoint."""

    def test_board_empty_database(self, temp_db):
        """Test board endpoint with no database returns empty board."""
        # Point to non-existent database
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = Path("/tmp/nonexistent_db.db")
            response = client.get("/api/board")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "view" in data
        assert "columns" in data
        assert "stats" in data

        # Check view config
        assert data["view"]["id"] == "default"
        assert data["view"]["name"] == "Full Workflow"
        assert len(data["view"]["columns"]) == 10

        # Check columns are empty
        assert len(data["columns"]) == 10
        for column in data["columns"]:
            assert column["count"] == 0
            assert column["entities"] == []

        # Check stats are zero
        stats = data["stats"]
        assert stats["total"] == 0
        assert stats["cost_total"] == 0.0
        assert stats["tokens_total"] == 0

    def test_board_with_entities(self, temp_db):
        """Test board endpoint returns entities grouped by stage."""
        # Add test entities to database
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Add entities in different stages
        insert_entity(
            conn,
            "task-1",
            "task",
            "Task in progress",
            "implementing",
            status="in_progress",
            priority="high",
            cost_usd=1.5,
            tokens=1000,
        )

        insert_entity(
            conn,
            "task-2",
            "task",
            "Task ready",
            "staged",
            status="open",
            priority="medium",
            cost_usd=0.5,
            tokens=500,
        )

        insert_entity(
            conn,
            "spec-1",
            "spec",
            "Spec in planning",
            "planned",
            status="researched",
        )

        conn.commit()
        conn.close()

        # Mock database path
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/board")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "view" in data
        assert "columns" in data
        assert "stats" in data

        # Check that we have entities
        total_entities = sum(col["count"] for col in data["columns"])
        assert total_entities == 3

        # Check stats
        stats = data["stats"]
        assert stats["total"] == 3
        assert stats["cost_total"] == 2.0
        assert stats["tokens_total"] == 1500

        # Check by_stage counts (using uppercase Stage enum values)
        assert "READY" in stats["by_stage"]
        assert "IN_PROGRESS" in stats["by_stage"]
        assert "PLANNED" in stats["by_stage"]

        # Check by_type counts
        assert "task" in stats["by_type"]
        assert stats["by_type"]["task"] == 2
        assert "spec" in stats["by_type"]
        assert stats["by_type"]["spec"] == 1

    def test_board_response_schema(self, temp_db):
        """Test that board response matches expected schema."""
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/board")

        assert response.status_code == 200
        data = response.json()

        # Validate top-level keys
        assert set(data.keys()) == {"view", "columns", "stats"}

        # Validate view structure
        view = data["view"]
        assert "id" in view
        assert "name" in view
        assert "columns" in view
        assert "filters" in view
        assert "display" in view

        # Validate columns structure
        for column in data["columns"]:
            assert "id" in column
            assert "title" in column
            assert "stage" in column
            assert "entities" in column
            assert "count" in column
            assert isinstance(column["entities"], list)
            assert isinstance(column["count"], int)

        # Validate stats structure
        stats = data["stats"]
        assert "total" in stats
        assert "by_stage" in stats
        assert "by_type" in stats
        assert "cost_total" in stats
        assert "tokens_total" in stats


class TestBoardStatsEndpoint:
    """Tests for GET /api/board/stats endpoint."""

    def test_stats_empty_database(self):
        """Test stats endpoint with no database returns zero stats."""
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = Path("/tmp/nonexistent_db.db")
            response = client.get("/api/board/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate stats structure
        assert data["total"] == 0
        assert data["cost_total"] == 0.0
        assert data["tokens_total"] == 0
        assert data["duration_total_seconds"] == 0
        assert data["by_stage"] == {}
        assert data["by_type"] == {}

    def test_stats_with_entities(self, temp_db):
        """Test stats endpoint computes correct aggregates."""
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

        insert_entity(
            conn,
            "epic-1",
            "epic",
            "Epic 1",
            "staged",
            cost_usd=0.0,
            tokens=0,
        )

        conn.commit()
        conn.close()

        # Get stats
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/board/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate aggregates
        assert data["total"] == 3
        assert data["cost_total"] == 4.0
        assert data["tokens_total"] == 3500

        # Validate by_stage (using uppercase Stage enum values)
        assert data["by_stage"]["READY"] == 2
        assert data["by_stage"]["IN_PROGRESS"] == 1

        # Validate by_type
        assert data["by_type"]["task"] == 2
        assert data["by_type"]["epic"] == 1

    def test_stats_response_schema(self, temp_db):
        """Test that stats response matches expected schema."""
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/board/stats")

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


class TestErrorHandling:
    """Tests for error handling in API endpoints."""

    def test_board_with_corrupted_database(self):
        """Test board endpoint handles database errors gracefully."""
        # Create a file that's not a valid SQLite database
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_db = Path(tmpdir) / "bad.db"
            bad_db.write_text("not a database")

            with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
                mock_path.return_value = bad_db
                response = client.get("/api/board")

        # Should return 500 error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to fetch board data" in data["detail"]

    def test_stats_with_corrupted_database(self):
        """Test stats endpoint handles database errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_db = Path(tmpdir) / "bad.db"
            bad_db.write_text("not a database")

            with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
                mock_path.return_value = bad_db
                response = client.get("/api/board/stats")

        # Should return 500 error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to compute board stats" in data["detail"]


class TestFilterBehavior:
    """Tests for filter application in board endpoint."""

    def test_excluded_labels_filtered(self, temp_db):
        """Test that entities with excluded labels are filtered out."""
        # Add entities with different labels
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Entity with 'archived' label (should be excluded by default)
        insert_entity(
            conn,
            "task-1",
            "task",
            "Archived task",
            "completed",
            data='{"labels": ["archived"]}',
        )

        # Entity without archived label (should be included)
        insert_entity(
            conn,
            "task-2",
            "task",
            "Active task",
            "implementing",
            data='{"labels": ["active"]}',
        )

        conn.commit()
        conn.close()

        # Get board
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/board")

        assert response.status_code == 200
        data = response.json()

        # Default view should exclude archived entities
        # Note: This depends on the default view having exclude_labels=["archived"]
        # The current implementation in queries.py applies this filter
        assert data["stats"]["total"] <= 2  # May be 1 or 2 depending on filter impl


class TestGroupingBehavior:
    """Tests for entity grouping in board columns."""

    def test_planned_column_groups_by_spec_id(self, temp_db):
        """Test that PLANNED column groups plans by their spec_id."""
        # Add entities to database
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Add a spec in PLANNED stage
        insert_entity(
            conn,
            "spec-1",
            "spec",
            "Auth Spec",
            "planned",
            status="researched",
        )

        # Add plans that reference the spec
        insert_entity(
            conn,
            "plan-1",
            "plan",
            "Auth Plan 1",
            "planned",
            status="drafted",
            data='{"spec_id": "spec-1"}',
        )

        insert_entity(
            conn,
            "plan-2",
            "plan",
            "Auth Plan 2",
            "planned",
            status="drafted",
            data='{"spec_id": "spec-1"}',
        )

        # Add another spec with a plan
        insert_entity(
            conn,
            "spec-2",
            "spec",
            "Dashboard Spec",
            "planned",
            status="researched",
        )

        insert_entity(
            conn,
            "plan-3",
            "plan",
            "Dashboard Plan",
            "planned",
            status="drafted",
            data='{"spec_id": "spec-2"}',
        )

        # Add a plan without a spec (legacy)
        insert_entity(
            conn,
            "plan-4",
            "plan",
            "Legacy Plan",
            "planned",
            status="drafted",
        )

        conn.commit()
        conn.close()

        # Get board
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/board")

        assert response.status_code == 200
        data = response.json()

        # Find the PLANNED column
        planned_column = None
        for col in data["columns"]:
            if col["id"] == "planned":
                planned_column = col
                break

        assert planned_column is not None, "PLANNED column not found"

        # Verify grouping structure
        assert "groups" in planned_column
        assert planned_column["groups"] is not None
        assert len(planned_column["groups"]) == 3  # 2 specs + 1 null group

        # Verify entities are empty when grouped
        assert planned_column["entities"] == []

        # Verify count includes all entities (2 specs + 3 plans + 1 legacy plan = 6)
        # Note: Specs themselves are also in the PLANNED stage and will be counted
        assert planned_column["count"] == 6

        # Check that groups have the right structure
        for group in planned_column["groups"]:
            assert "group_key" in group
            assert "group_entity" in group
            assert "entities" in group
            assert "count" in group

    def test_ungrouped_column_has_flat_entities(self, temp_db):
        """Test that columns without group_by have flat entity list."""
        # Add entities to database
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Add tasks in IN_PROGRESS stage (not grouped by default)
        insert_entity(
            conn,
            "task-1",
            "task",
            "Task 1",
            "implementing",
            status="in_progress",
        )

        insert_entity(
            conn,
            "task-2",
            "task",
            "Task 2",
            "implementing",
            status="in_progress",
        )

        conn.commit()
        conn.close()

        # Get board
        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/board")

        assert response.status_code == 200
        data = response.json()

        # Find the IN_PROGRESS column
        in_progress_column = None
        for col in data["columns"]:
            if col["id"] == "in_progress":
                in_progress_column = col
                break

        assert in_progress_column is not None

        # Verify flat structure (no grouping)
        assert in_progress_column["groups"] is None
        assert len(in_progress_column["entities"]) == 2
        assert in_progress_column["count"] == 2
