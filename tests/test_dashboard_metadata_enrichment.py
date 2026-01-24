"""
Tests for dashboard metadata enrichment during sync.

Tests cover:
- Spec parser extracts readiness score and notes count
- Task/Epic parser extracts description excerpt
- Plan parser extracts description excerpt
- Resolver computes task counts for epics
- Resolver computes task and epic counts for plans
- Graceful handling of missing metadata (None values)
- Database read/write cycle preserves metadata
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from cub.core.dashboard.db.models import DashboardEntity, EntityType, Stage
from cub.core.dashboard.sync.parsers.plans import PlanParser
from cub.core.dashboard.sync.parsers.specs import SpecParser
from cub.core.dashboard.sync.resolver import RelationshipResolver
from cub.core.specs import Spec
from cub.core.specs import Stage as SpecStage
from cub.core.specs.models import Readiness, SpecComplexity, SpecPriority


class TestSpecMetadataExtraction:
    """Tests for spec metadata extraction."""

    def test_extract_readiness_score_with_complete_data(self, tmp_path: Path) -> None:
        """Test extracting readiness score from spec with complete data."""
        # Create a spec file with readiness data
        spec_file = tmp_path / "test-spec.md"
        spec_file.write_text(
            """---
readiness:
  score: 8
  blockers:
    - Need API key
  questions:
    - Which database to use?
notes: This is a test spec
---

# Test Spec

Content here.
"""
        )

        # Parse the spec
        parser = SpecParser(tmp_path)
        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is not None
        assert entity.readiness_score == 0.8  # 8/10 normalized to 0-1
        assert entity.notes_count == 3  # 1 blocker + 1 question + 1 notes field
        assert entity.description_excerpt == "This is a test spec"

    def test_extract_readiness_score_with_minimal_data(self, tmp_path: Path) -> None:
        """Test extracting readiness with minimal data (graceful degradation)."""
        spec_file = tmp_path / "minimal-spec.md"
        spec_file.write_text(
            """---
title: Minimal Spec
---

# Minimal Spec

No readiness data here.
"""
        )

        parser = SpecParser(tmp_path)
        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is not None
        # Default readiness score is 0
        assert entity.readiness_score == 0.0
        assert entity.notes_count == 0
        assert entity.description_excerpt is None

    def test_extract_long_description_excerpt(self, tmp_path: Path) -> None:
        """Test that long descriptions are truncated to 100 chars."""
        long_notes = "A" * 150
        spec_file = tmp_path / "long-spec.md"
        spec_file.write_text(
            f"""---
notes: {long_notes}
---

# Long Spec
"""
        )

        parser = SpecParser(tmp_path)
        entity = parser.parse_file(spec_file, SpecStage.PLANNED)

        assert entity is not None
        assert entity.description_excerpt is not None
        assert len(entity.description_excerpt) == 100
        assert entity.description_excerpt.endswith("...")
        assert entity.description_excerpt == "A" * 97 + "..."


class TestTaskMetadataExtraction:
    """Tests for task/epic metadata extraction."""

    def test_extract_description_excerpt_from_plan(self, tmp_path: Path) -> None:
        """Test extracting description excerpt from plan task."""
        session_dir = tmp_path / "test-session"
        session_dir.mkdir()

        # Create session.json
        session_data = {
            "id": "test-session",
            "created": "2026-01-23T12:00:00Z",
            "updated": "2026-01-23T13:00:00Z",
        }
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Create plan.jsonl with epic
        epic = {
            "id": "test-epic",
            "title": "Test Epic",
            "description": "This is a short description for the epic",
            "issue_type": "epic",
            "status": "open",
            "priority": 0,
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic) + "\n")

        parser = PlanParser(tmp_path)
        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.description_excerpt == "This is a short description for the epic"

    def test_extract_truncated_description_excerpt(self, tmp_path: Path) -> None:
        """Test that long descriptions are truncated."""
        session_dir = tmp_path / "test-session"
        session_dir.mkdir()

        session_data = {"id": "test-session"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        long_desc = "B" * 150
        epic = {
            "id": "test-epic",
            "title": "Test Epic",
            "description": long_desc,
            "issue_type": "epic",
            "status": "open",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic) + "\n")

        parser = PlanParser(tmp_path)
        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.description_excerpt is not None
        assert len(entity.description_excerpt) == 100
        assert entity.description_excerpt == "B" * 97 + "..."

    def test_missing_description_returns_none(self, tmp_path: Path) -> None:
        """Test that missing description returns None (graceful degradation)."""
        session_dir = tmp_path / "test-session"
        session_dir.mkdir()

        session_data = {"id": "test-session"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        epic = {
            "id": "test-epic",
            "title": "Test Epic",
            "issue_type": "epic",
            "status": "open",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic) + "\n")

        parser = PlanParser(tmp_path)
        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.description_excerpt is None


class TestTaskCountComputation:
    """Tests for task count computation during resolution."""

    def test_compute_epic_task_count(self) -> None:
        """Test computing task count for an epic."""
        # Create test entities
        epic = DashboardEntity(
            id="epic-1",
            type=EntityType.EPIC,
            title="Test Epic",
            stage=Stage.PLANNED,
            status="open",
            source_type="test",
            source_path="test",
        )

        task1 = DashboardEntity(
            id="task-1",
            type=EntityType.TASK,
            title="Task 1",
            stage=Stage.READY,
            status="open",
            epic_id="epic-1",
            source_type="test",
            source_path="test",
        )

        task2 = DashboardEntity(
            id="task-2",
            type=EntityType.TASK,
            title="Task 2",
            stage=Stage.IN_PROGRESS,
            status="in_progress",
            parent_id="epic-1",
            source_type="test",
            source_path="test",
        )

        entities = [epic, task1, task2]
        resolver = RelationshipResolver()
        resolved_entities, _ = resolver.resolve(entities)

        # Find the resolved epic
        resolved_epic = next(e for e in resolved_entities if e.id == "epic-1")
        assert resolved_epic.task_count == 2

    def test_compute_plan_task_and_epic_counts(self) -> None:
        """Test computing task and epic counts for a plan."""
        # Create test entities
        plan = DashboardEntity(
            id="plan-1",
            type=EntityType.PLAN,
            title="Test Plan",
            stage=Stage.PLANNED,
            status="open",
            source_type="test",
            source_path="test",
        )

        epic1 = DashboardEntity(
            id="epic-1",
            type=EntityType.EPIC,
            title="Epic 1",
            stage=Stage.PLANNED,
            status="open",
            plan_id="plan-1",
            source_type="test",
            source_path="test",
        )

        epic2 = DashboardEntity(
            id="epic-2",
            type=EntityType.EPIC,
            title="Epic 2",
            stage=Stage.PLANNED,
            status="open",
            plan_id="plan-1",
            source_type="test",
            source_path="test",
        )

        task1 = DashboardEntity(
            id="task-1",
            type=EntityType.TASK,
            title="Task 1",
            stage=Stage.READY,
            status="open",
            epic_id="epic-1",
            source_type="test",
            source_path="test",
        )

        task2 = DashboardEntity(
            id="task-2",
            type=EntityType.TASK,
            title="Task 2",
            stage=Stage.READY,
            status="open",
            epic_id="epic-2",
            source_type="test",
            source_path="test",
        )

        entities = [plan, epic1, epic2, task1, task2]
        resolver = RelationshipResolver()
        resolved_entities, _ = resolver.resolve(entities)

        # Find the resolved plan
        resolved_plan = next(e for e in resolved_entities if e.id == "plan-1")
        assert resolved_plan.epic_count == 2
        assert resolved_plan.task_count == 2

    def test_graceful_handling_no_tasks(self) -> None:
        """Test that epics/plans with no tasks have None or 0 task_count."""
        epic = DashboardEntity(
            id="epic-empty",
            type=EntityType.EPIC,
            title="Empty Epic",
            stage=Stage.PLANNED,
            status="open",
            source_type="test",
            source_path="test",
        )

        entities = [epic]
        resolver = RelationshipResolver()
        resolved_entities, _ = resolver.resolve(entities)

        resolved_epic = next(e for e in resolved_entities if e.id == "epic-empty")
        # Should be 0, not None (we computed it but it's 0)
        assert resolved_epic.task_count == 0


class TestMetadataPersistence:
    """Tests for metadata persistence through database cycle."""

    def test_metadata_survives_database_roundtrip(self) -> None:
        """Test that metadata is preserved through write/read cycle."""
        from cub.core.dashboard.db.connection import get_connection
        from cub.core.dashboard.db.queries import get_all_entities
        from cub.core.dashboard.db.schema import create_schema
        from cub.core.dashboard.sync.writer import EntityWriter

        # Create entity with metadata
        entity = DashboardEntity(
            id="test-spec",
            type=EntityType.SPEC,
            title="Test Spec",
            stage=Stage.RESEARCHING,
            status="researching",
            source_type="file",
            source_path="specs/researching/test.md",
            source_checksum="abc123",
            readiness_score=0.75,
            notes_count=5,
            description_excerpt="Short description here",
        )

        # Write to database
        with get_connection(":memory:") as conn:
            create_schema(conn)
            writer = EntityWriter(conn)
            writer.write_entity(entity)
            conn.commit()

            # Read back from database
            entities = get_all_entities(conn)

        assert len(entities) == 1
        retrieved = entities[0]

        # Verify metadata was preserved
        assert retrieved.id == "test-spec"
        assert retrieved.readiness_score == 0.75
        assert retrieved.notes_count == 5
        assert retrieved.description_excerpt == "Short description here"

    def test_missing_metadata_fields_are_none(self) -> None:
        """Test that entities without metadata have None values."""
        from cub.core.dashboard.db.connection import get_connection
        from cub.core.dashboard.db.queries import get_all_entities
        from cub.core.dashboard.db.schema import create_schema
        from cub.core.dashboard.sync.writer import EntityWriter

        # Create entity without metadata
        entity = DashboardEntity(
            id="test-task",
            type=EntityType.TASK,
            title="Test Task",
            stage=Stage.READY,
            status="open",
            source_type="beads",
            source_path="beads:test-task",
        )

        with get_connection(":memory:") as conn:
            create_schema(conn)
            writer = EntityWriter(conn)
            writer.write_entity(entity)
            conn.commit()

            entities = get_all_entities(conn)

        assert len(entities) == 1
        retrieved = entities[0]

        # Metadata fields should be None
        assert retrieved.readiness_score is None
        assert retrieved.task_count is None
        assert retrieved.epic_count is None
        assert retrieved.notes_count is None
        assert retrieved.description_excerpt is None
