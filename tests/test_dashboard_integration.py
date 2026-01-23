"""
Integration test for the complete dashboard flow.

Tests the full workflow from `cub dashboard sync` to API response:
1. Create project with specs, plans, tasks
2. Run sync orchestrator
3. Query board API endpoint
4. Validate response structure and data
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cub.core.dashboard.api.app import app
from cub.core.dashboard.db import get_connection
from cub.core.dashboard.db.queries import get_all_entities
from cub.core.dashboard.sync.orchestrator import SyncOrchestrator
from cub.core.specs import Stage as SpecStage


@pytest.fixture
def integration_project(tmp_path: Path) -> Path:
    """
    Create a complete project structure with specs, plans, and tasks.

    This fixture sets up a realistic project environment for testing
    the full dashboard sync and API workflow.
    """
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Create specs directory structure
    specs_root = project_root / "specs"
    for stage in SpecStage:
        (specs_root / stage.value).mkdir(parents=True)

    # Create a spec in planned stage
    spec_content = """---
id: test-spec-1
title: Test Feature Spec
stage: planned
priority: 2
---

# Test Feature

This is a test specification for integration testing.

## Requirements

- Requirement 1
- Requirement 2
"""
    spec_path = specs_root / "planned" / "test-spec-1.md"
    spec_path.write_text(spec_content)

    # Create .cub directory structure
    cub_dir = project_root / ".cub"
    cub_dir.mkdir()

    # Create sessions directory with a plan
    sessions_dir = cub_dir / "sessions"
    test_session = sessions_dir / "test-session-001"
    test_session.mkdir(parents=True)

    # Create session.json
    session_data = {
        "session_id": "test-session-001",
        "status": "completed",
        "spec_id": "test-spec-1",
        "created_at": "2026-01-23T10:00:00Z",
    }
    (test_session / "session.json").write_text(json.dumps(session_data))

    # Create plan.jsonl
    plan_entries = [
        {"type": "plan_metadata", "plan_id": "test-plan-1", "session_id": "test-session-001"},
        {"type": "task", "task_id": "test-task-1", "title": "Implement feature", "status": "open"},
        {"type": "task", "task_id": "test-task-2", "title": "Write tests", "status": "open"},
    ]
    plan_lines = "\n".join(json.dumps(entry) for entry in plan_entries)
    (test_session / "plan.jsonl").write_text(plan_lines)

    # Create CHANGELOG.md
    changelog_content = """# Changelog

## [Unreleased]

### Added
- Initial setup

## [0.1.0] - 2026-01-20

### Added
- Feature X (#test-task-1)
"""
    (project_root / "CHANGELOG.md").write_text(changelog_content)

    # Create ledger directory
    ledger_dir = cub_dir / "ledger"
    ledger_dir.mkdir()

    return project_root


class TestDashboardIntegration:
    """Integration tests for complete dashboard workflow."""

    def test_full_sync_to_api_flow(self, integration_project: Path):
        """
        Test the complete flow from sync to API response.

        This test validates:
        1. Sync orchestrator successfully processes all data sources
        2. Database is populated with entities and relationships
        3. Board API returns valid response with data
        4. Response structure matches schema
        """
        db_path = integration_project / ".cub" / "dashboard.db"

        # Step 1: Run sync orchestrator
        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=integration_project / "specs",
            plans_root=integration_project / ".cub" / "sessions",
            changelog_path=integration_project / "CHANGELOG.md",
            ledger_path=integration_project / ".cub" / "ledger",
        )
        result = orchestrator.sync()

        # Validate sync completed successfully
        assert result.success is True
        assert result.entities_added > 0, "Expected at least one entity to be synced"

        # Step 2: Verify database has data
        with get_connection(db_path) as conn:
            entities = get_all_entities(conn)
            assert len(entities) > 0, "Expected entities in database after sync"

            # Check that we have a spec entity
            spec_entities = [e for e in entities if e.type.value == "spec"]
            assert len(spec_entities) > 0, "Expected at least one spec entity"
            assert spec_entities[0].id == "test-spec-1"
            assert spec_entities[0].title == "Test Feature"

        # Step 3: Call board API endpoint
        # Mock the get_db_path to return our test database
        from unittest.mock import patch

        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_get_db:
            mock_get_db.return_value = db_path

            client = TestClient(app)
            response = client.get("/api/board")

            # Step 4: Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

            data = response.json()

            # Validate response structure
            assert "view" in data
            assert "columns" in data
            assert "stats" in data

            # Validate view configuration
            assert data["view"]["id"] is not None
            assert len(data["view"]["columns"]) > 0

            # Validate columns
            assert isinstance(data["columns"], list)
            assert len(data["columns"]) > 0

            # Find column with our spec
            spec_found = False
            for column in data["columns"]:
                assert "id" in column
                assert "title" in column
                assert "stage" in column
                assert "entities" in column
                assert "count" in column

                # Check if our spec is in this column
                for entity in column["entities"]:
                    if entity["id"] == "test-spec-1":
                        spec_found = True
                        assert entity["title"] == "Test Feature"
                        assert entity["type"] == "spec"
                        break

            assert spec_found, "Expected to find test-spec-1 in board response"

            # Validate stats
            assert "total" in data["stats"]
            assert data["stats"]["total"] > 0
            assert "by_stage" in data["stats"]
            assert "by_type" in data["stats"]

    def test_sync_and_query_entity_endpoint(self, integration_project: Path):
        """
        Test sync followed by entity detail API call.

        Validates that synced entities can be retrieved via the entity endpoint.
        """
        db_path = integration_project / ".cub" / "dashboard.db"

        # Run sync
        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=integration_project / "specs",
            plans_root=integration_project / ".cub" / "sessions",
            changelog_path=integration_project / "CHANGELOG.md",
            ledger_path=integration_project / ".cub" / "ledger",
        )
        result = orchestrator.sync()
        assert result.success is True

        # Query entity endpoint
        from unittest.mock import patch

        with patch("cub.core.dashboard.api.routes.entity.get_db_path") as mock_get_db:
            mock_get_db.return_value = db_path

            client = TestClient(app)
            response = client.get("/api/entity/test-spec-1")

            assert response.status_code == 200
            data = response.json()

            # Validate entity data (EntityDetail wraps the entity)
            assert "entity" in data
            entity = data["entity"]
            assert entity["id"] == "test-spec-1"
            assert entity["title"] == "Test Feature"
            assert entity["type"] == "spec"
            assert "stage" in entity
            assert "priority" in entity

    def test_empty_project_returns_empty_board(self, tmp_path: Path):
        """
        Test that an empty project (no sync) returns a valid empty board.

        This validates graceful handling when the database doesn't exist yet.
        """
        empty_project = tmp_path / "empty_project"
        empty_project.mkdir()

        db_path = empty_project / ".cub" / "dashboard.db"

        from unittest.mock import patch

        with patch("cub.core.dashboard.api.routes.board.get_db_path") as mock_get_db:
            mock_get_db.return_value = db_path

            client = TestClient(app)
            response = client.get("/api/board")

            assert response.status_code == 200
            data = response.json()

            # Should return empty board structure
            assert "view" in data
            assert "columns" in data
            assert "stats" in data

            # All columns should be empty
            for column in data["columns"]:
                assert column["count"] == 0
                assert len(column["entities"]) == 0

            # Stats should be zero
            assert data["stats"]["total"] == 0
