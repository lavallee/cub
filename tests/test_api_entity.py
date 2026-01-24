"""
Tests for the dashboard API entity endpoint.

Tests validate:
- GET /api/entity/{id} endpoint
- Entity detail response model
- Relationship organization
- Empty database handling
- Error handling (404, 500)
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


class TestEntityEndpoint:
    """Tests for GET /api/entity/{id} endpoint."""

    def test_entity_not_found_no_database(self):
        """Test entity endpoint returns 404 when database doesn't exist."""
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = Path("/tmp/nonexistent_db.db")
            response = client.get("/api/entity/task-1")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Entity not found" in data["detail"]
        assert "task-1" in data["detail"]

    def test_entity_not_found_empty_database(self, temp_db):
        """Test entity endpoint returns 404 when entity doesn't exist."""
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/nonexistent-id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Entity not found" in data["detail"]
        assert "nonexistent-id" in data["detail"]

    def test_entity_basic_fetch(self, temp_db):
        """Test fetching a basic entity without relationships."""
        # Add a test entity
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        insert_entity(
            conn,
            "task-1",
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

        # Fetch entity
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/task-1")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "entity" in data
        assert "relationships" in data
        assert "content" in data

        # Validate entity data
        entity = data["entity"]
        assert entity["id"] == "task-1"
        assert entity["type"] == "task"
        assert entity["title"] == "Test Task"
        assert entity["stage"] == "IN_PROGRESS"  # Converted from implementing
        assert entity["status"] == "in_progress"
        assert entity["cost_usd"] == 1.5
        assert entity["tokens"] == 1000
        assert "test" in entity["labels"]

        # Validate relationships are present (even if empty)
        relationships = data["relationships"]
        assert "parent" in relationships
        assert "children" in relationships
        assert "blocks" in relationships
        assert "blocked_by" in relationships
        assert "spec" in relationships
        assert "plan" in relationships
        assert "epic" in relationships

        # All should be empty or None for a standalone entity
        assert relationships["parent"] is None
        assert relationships["children"] == []

    def test_entity_with_relationships(self, temp_db):
        """Test fetching an entity with parent-child relationships."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Create epic
        insert_entity(
            conn,
            "epic-1",
            "epic",
            "Test Epic",
            "staged",
            status="open",
        )

        # Create task that belongs to epic
        insert_entity(
            conn,
            "task-1",
            "task",
            "Test Task",
            "implementing",
            status="in_progress",
            data='{"epic_id": "epic-1"}',
        )

        # Create relationship
        conn.execute(
            """
            INSERT INTO relationships (from_id, to_id, type)
            VALUES (?, ?, ?)
            """,
            ("epic-1", "task-1", "epic_to_task"),
        )

        conn.commit()
        conn.close()

        # Fetch task entity
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/task-1")

        assert response.status_code == 200
        data = response.json()

        # Validate entity
        entity = data["entity"]
        assert entity["id"] == "task-1"

        # Validate epic relationship
        relationships = data["relationships"]
        assert relationships["epic"] is not None
        epic = relationships["epic"]
        assert epic["id"] == "epic-1"
        assert epic["title"] == "Test Epic"

        # Now fetch epic and check it has the task as a child
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/epic-1")

        assert response.status_code == 200
        data = response.json()

        # Validate epic has task in tasks list
        relationships = data["relationships"]
        assert "tasks" in relationships
        assert len(relationships["tasks"]) == 1
        task = relationships["tasks"][0]
        assert task["id"] == "task-1"

    def test_entity_with_dependencies(self, temp_db):
        """Test fetching an entity with dependency relationships."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Create two tasks with dependency
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
            "staged",
            status="open",
        )

        # Task 2 depends on Task 1
        conn.execute(
            """
            INSERT INTO relationships (from_id, to_id, type)
            VALUES (?, ?, ?)
            """,
            ("task-2", "task-1", "depends_on"),
        )

        conn.commit()
        conn.close()

        # Fetch task-2 (depends on task-1)
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/task-2")

        assert response.status_code == 200
        data = response.json()

        # Validate dependencies
        relationships = data["relationships"]
        assert "depends_on" in relationships
        assert len(relationships["depends_on"]) == 1
        dep = relationships["depends_on"][0]
        assert dep["id"] == "task-1"

    def test_entity_with_blocking_relationships(self, temp_db):
        """Test fetching an entity with blocks/blocked_by relationships."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Create two tasks where one blocks another
        insert_entity(
            conn,
            "task-1",
            "task",
            "Blocking Task",
            "implementing",
            status="in_progress",
        )

        insert_entity(
            conn,
            "task-2",
            "task",
            "Blocked Task",
            "staged",
            status="open",
        )

        # Task 1 blocks Task 2
        conn.execute(
            """
            INSERT INTO relationships (from_id, to_id, type)
            VALUES (?, ?, ?)
            """,
            ("task-1", "task-2", "blocks"),
        )

        conn.commit()
        conn.close()

        # Fetch task-1 (blocks task-2)
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/task-1")

        assert response.status_code == 200
        data = response.json()

        relationships = data["relationships"]
        assert "blocks" in relationships
        assert len(relationships["blocks"]) == 1
        assert relationships["blocks"][0]["id"] == "task-2"

        # Fetch task-2 (blocked by task-1)
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/task-2")

        assert response.status_code == 200
        data = response.json()

        relationships = data["relationships"]
        assert "blocked_by" in relationships
        assert len(relationships["blocked_by"]) == 1
        assert relationships["blocked_by"][0]["id"] == "task-1"

    def test_entity_response_schema(self, temp_db):
        """Test that entity response matches expected schema."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        insert_entity(
            conn,
            "task-1",
            "task",
            "Test Task",
            "implementing",
            status="in_progress",
        )

        conn.commit()
        conn.close()

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/task-1")

        assert response.status_code == 200
        data = response.json()

        # Validate top-level keys
        assert set(data.keys()) == {"entity", "relationships", "content"}

        # Validate entity structure (subset of key fields)
        entity = data["entity"]
        required_entity_keys = {
            "id",
            "type",
            "title",
            "stage",
            "status",
            "source_type",
            "source_path",
        }
        assert required_entity_keys.issubset(set(entity.keys()))

        # Validate relationships structure
        relationships = data["relationships"]
        assert isinstance(relationships, dict)

        # Content can be None or string
        assert data["content"] is None or isinstance(data["content"], str)

    def test_entity_with_content(self, temp_db):
        """Test that entity content is returned correctly."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        content_text = "Test task with content"

        insert_entity(
            conn,
            "task-1",
            "task",
            "Test Task",
            "implementing",
            status="in_progress",
            data='{"content": "' + content_text + '"}',
        )

        conn.commit()
        conn.close()

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/task-1")

        assert response.status_code == 200
        data = response.json()

        # Validate content is returned
        assert data["content"] is not None
        assert data["content"] == content_text


class TestErrorHandling:
    """Tests for error handling in entity endpoint."""

    def test_entity_with_corrupted_database(self):
        """Test entity endpoint handles database errors gracefully."""
        # Create a file that's not a valid SQLite database
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_db = Path(tmpdir) / "bad.db"
            bad_db.write_text("not a database")

            with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
                mock_path.return_value = bad_db
                response = client.get("/api/entity/task-1")

        # Should return 500 error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to fetch entity details" in data["detail"]

    def test_entity_with_special_characters_in_id(self, temp_db):
        """Test entity endpoint handles special characters in entity ID."""
        # Note: This tests URL encoding behavior
        entity_id = "task-with-special-chars-123"

        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        insert_entity(
            conn,
            entity_id,
            "task",
            "Test Task",
            "implementing",
            status="in_progress",
        )

        conn.commit()
        conn.close()

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get(f"/api/entity/{entity_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["entity"]["id"] == entity_id


class TestRelationshipIntegrity:
    """Tests for relationship data integrity."""

    def test_bidirectional_relationships(self, temp_db):
        """Test that bidirectional relationships are properly resolved."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Create parent-child relationship using epic_to_task
        insert_entity(
            conn,
            "parent-1",
            "epic",
            "Parent Epic",
            "staged",
        )

        insert_entity(
            conn,
            "child-1",
            "task",
            "Child Task",
            "implementing",
        )

        # Epic contains task
        conn.execute(
            """
            INSERT INTO relationships (from_id, to_id, type)
            VALUES (?, ?, ?)
            """,
            ("parent-1", "child-1", "epic_to_task"),
        )

        conn.commit()
        conn.close()

        # Fetch parent epic - should show task in tasks list
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/parent-1")

        assert response.status_code == 200
        parent_data = response.json()
        assert len(parent_data["relationships"]["tasks"]) == 1
        assert parent_data["relationships"]["tasks"][0]["id"] == "child-1"

        # Fetch child task - should show epic
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/child-1")

        assert response.status_code == 200
        child_data = response.json()
        assert child_data["relationships"]["epic"] is not None
        assert child_data["relationships"]["epic"]["id"] == "parent-1"

    def test_multiple_relationships(self, temp_db):
        """Test entity with multiple different relationship types."""
        conn = sqlite3.connect(str(temp_db))
        configure_connection(conn)

        # Create a complex scenario
        insert_entity(conn, "spec-1", "spec", "Spec", "planned")
        insert_entity(conn, "plan-1", "plan", "Plan", "planned")
        insert_entity(conn, "epic-1", "epic", "Epic", "staged")
        insert_entity(conn, "task-1", "task", "Task 1", "implementing")
        insert_entity(conn, "task-2", "task", "Task 2", "staged")

        # Spec -> Plan
        conn.execute(
            "INSERT INTO relationships (from_id, to_id, type) VALUES (?, ?, ?)",
            ("spec-1", "plan-1", "spec_to_plan"),
        )

        # Plan -> Epic
        conn.execute(
            "INSERT INTO relationships (from_id, to_id, type) VALUES (?, ?, ?)",
            ("plan-1", "epic-1", "plan_to_epic"),
        )

        # Epic -> Task 1
        conn.execute(
            "INSERT INTO relationships (from_id, to_id, type) VALUES (?, ?, ?)",
            ("epic-1", "task-1", "epic_to_task"),
        )

        # Epic -> Task 2
        conn.execute(
            "INSERT INTO relationships (from_id, to_id, type) VALUES (?, ?, ?)",
            ("epic-1", "task-2", "epic_to_task"),
        )

        # Task 2 depends on Task 1
        conn.execute(
            "INSERT INTO relationships (from_id, to_id, type) VALUES (?, ?, ?)",
            ("task-2", "task-1", "depends_on"),
        )

        conn.commit()
        conn.close()

        # Fetch task-2 - should have epic and dependency (direct relationships only)
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/task-2")

        assert response.status_code == 200
        data = response.json()

        relationships = data["relationships"]

        # Should have epic (direct relationship)
        assert relationships["epic"] is not None
        assert relationships["epic"]["id"] == "epic-1"

        # Should NOT have plan or spec (indirect relationships - would need traversal)
        # In this implementation, we only show direct relationships
        assert relationships["plan"] is None
        assert relationships["spec"] is None

        # Should depend on task-1 (direct dependency)
        assert len(relationships["depends_on"]) == 1
        assert relationships["depends_on"][0]["id"] == "task-1"

        # Fetch epic-1 - should have both tasks and plan
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/epic-1")

        assert response.status_code == 200
        data = response.json()

        relationships = data["relationships"]

        # Epic should have both tasks
        assert len(relationships["tasks"]) == 2
        task_ids = {t["id"] for t in relationships["tasks"]}
        assert task_ids == {"task-1", "task-2"}

        # Epic should have plan
        assert relationships["plan"] is not None
        assert relationships["plan"]["id"] == "plan-1"

        # Fetch plan-1 - should have spec and epics
        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_path:
            mock_path.return_value = temp_db
            response = client.get("/api/entity/plan-1")

        assert response.status_code == 200
        data = response.json()

        relationships = data["relationships"]

        # Plan should have spec
        assert relationships["spec"] is not None
        assert relationships["spec"]["id"] == "spec-1"

        # Plan should have epic in epics list
        assert "epics" in relationships
        assert len(relationships["epics"]) == 1
        assert relationships["epics"][0]["id"] == "epic-1"
