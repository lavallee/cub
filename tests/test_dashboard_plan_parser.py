"""
Tests for the plan parser in the dashboard sync layer.

Tests cover:
- Parsing valid session directories with session.json and plan.jsonl
- Handling missing session.json (uses defaults)
- Handling missing plan.jsonl (returns empty list)
- Handling invalid JSON (logs warning, continues)
- Handling empty files (returns empty list)
- Epic vs task filtering (only epics become plan entities)
- Priority mapping
- Label extraction
- Checksum computation for incremental sync
- Parsing all sessions
- Parsing sessions with epic_id in metadata
"""

import json
from pathlib import Path

import pytest

from cub.core.dashboard.db.models import EntityType, Stage
from cub.core.dashboard.sync.parsers.plans import PlanParser


@pytest.fixture
def tmp_sessions_root(tmp_path: Path) -> Path:
    """Create temporary sessions directory structure."""
    sessions_root = tmp_path / ".cub" / "sessions"
    sessions_root.mkdir(parents=True)
    return sessions_root


@pytest.fixture
def parser(tmp_sessions_root: Path) -> PlanParser:
    """Create PlanParser instance with temp directory."""
    return PlanParser(tmp_sessions_root)


class TestPlanParser:
    """Tests for the PlanParser class."""

    def test_parse_valid_session_with_epic(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test parsing a valid session with an epic task."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        # Create session.json
        session_data = {
            "id": "test-20260123-120000",
            "created": "2026-01-23T12:00:00Z",
            "updated": "2026-01-23T13:00:00Z",
            "status": "created",
            "stages": {
                "triage": "complete",
                "architect": None,
                "plan": None,
                "bootstrap": None,
            },
        }
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Create plan.jsonl with an epic
        epic_task = {
            "id": "test-E01",
            "title": "Test Epic",
            "description": "A test epic for parsing",
            "status": "open",
            "priority": 0,
            "issue_type": "epic",
            "labels": ["phase-1", "foundation"],
            "dependencies": [],
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.id == "test-E01"
        assert entity.type == EntityType.PLAN
        assert entity.title == "Test Epic"
        assert entity.description == "A test epic for parsing"
        assert entity.stage == Stage.PLANNED
        assert entity.status == "open"
        assert entity.priority == 0
        assert "phase-1" in entity.labels
        assert "foundation" in entity.labels
        # Note: datetimes are timezone-aware (UTC)
        assert entity.created_at is not None
        assert entity.created_at.year == 2026
        assert entity.created_at.month == 1
        assert entity.created_at.day == 23
        assert entity.updated_at is not None
        assert entity.plan_id == "test-20260123-120000"
        assert entity.source_type == "plan"
        assert entity.source_checksum is not None
        assert entity.frontmatter == epic_task

    def test_parse_session_filters_out_regular_tasks(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test that regular tasks are not converted to plan entities."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Create plan.jsonl with mix of epic and regular tasks
        tasks = [
            {
                "id": "test-E01",
                "title": "Epic",
                "issue_type": "epic",
                "status": "open",
                "priority": 0,
            },
            {
                "id": "test-001",
                "title": "Regular Task",
                "issue_type": "task",
                "status": "open",
                "priority": 0,
            },
            {
                "id": "test-002",
                "title": "Another Task",
                "issue_type": "task",
                "status": "open",
                "priority": 1,
            },
        ]
        plan_content = "\n".join(json.dumps(task) for task in tasks)
        (session_dir / "plan.jsonl").write_text(plan_content + "\n")

        entities = parser.parse_session(session_dir)

        # Only the epic should be converted
        assert len(entities) == 1
        assert entities[0].id == "test-E01"
        assert entities[0].type == EntityType.PLAN

    def test_parse_session_missing_session_json(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing session with missing session.json."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        # Only create plan.jsonl
        epic_task = {
            "id": "test-E01",
            "title": "Epic without session.json",
            "issue_type": "epic",
            "status": "open",
            "priority": 1,
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.id == "test-E01"
        # Should use directory name as fallback plan_id
        assert entity.plan_id == "test-20260123-120000"
        # Debug logs may not appear depending on logging level
        # Just check the fallback behavior works

    def test_parse_session_missing_plan_jsonl(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing session with missing plan.jsonl."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        # Only create session.json
        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        entities = parser.parse_session(session_dir)

        assert len(entities) == 0
        # Debug logs may not appear depending on logging level
        # Just check that no entities are returned

    def test_parse_session_invalid_session_json(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing session with invalid JSON in session.json."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        # Create invalid JSON
        (session_dir / "session.json").write_text("{ invalid json }")

        # Create valid plan.jsonl
        epic_task = {
            "id": "test-E01",
            "title": "Epic",
            "issue_type": "epic",
            "status": "open",
            "priority": 0,
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        # Should still parse the plan with fallback metadata
        assert len(entities) == 1
        assert "Invalid JSON" in caplog.text

    def test_parse_session_invalid_plan_jsonl_line(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing plan.jsonl with some invalid JSON lines."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Create plan.jsonl with mix of valid and invalid lines
        plan_content = [
            json.dumps({"id": "test-E01", "title": "Epic 1", "issue_type": "epic", "priority": 0}),
            "{ invalid json line }",
            json.dumps({"id": "test-E02", "title": "Epic 2", "issue_type": "epic", "priority": 1}),
        ]
        (session_dir / "plan.jsonl").write_text("\n".join(plan_content) + "\n")

        entities = parser.parse_session(session_dir)

        # Should parse valid lines and skip invalid
        assert len(entities) == 2
        assert {e.id for e in entities} == {"test-E01", "test-E02"}
        assert "Invalid JSON" in caplog.text

    def test_parse_session_empty_plan_jsonl(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test parsing session with empty plan.jsonl."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))
        (session_dir / "plan.jsonl").write_text("")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 0

    def test_priority_mapping(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test that task priorities map correctly to dashboard priorities."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Create epics with different priorities
        tasks = [
            {"id": "test-E01", "title": "P0", "issue_type": "epic", "priority": 0},
            {"id": "test-E02", "title": "P1", "issue_type": "epic", "priority": 1},
            {"id": "test-E03", "title": "P2", "issue_type": "epic", "priority": 2},
            {"id": "test-E04", "title": "P3", "issue_type": "epic", "priority": 3},
            {"id": "test-E05", "title": "P4", "issue_type": "epic", "priority": 4},
        ]
        plan_content = "\n".join(json.dumps(task) for task in tasks)
        (session_dir / "plan.jsonl").write_text(plan_content + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 5
        priorities = {e.id: e.priority for e in entities}
        assert priorities == {
            "test-E01": 0,
            "test-E02": 1,
            "test-E03": 2,
            "test-E04": 3,
            "test-E05": 4,
        }

    def test_label_extraction(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test extraction of labels from task metadata."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        epic_task = {
            "id": "test-E01",
            "title": "Epic with labels",
            "issue_type": "epic",
            "priority": 0,
            "labels": ["phase-1", "model:sonnet", "complexity:high", "foundation"],
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert "phase-1" in entity.labels
        assert "model:sonnet" in entity.labels
        assert "complexity:high" in entity.labels
        assert "foundation" in entity.labels

    def test_checksum_computation(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test that checksum is computed and changes when content changes."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        epic_task = {
            "id": "test-E01",
            "title": "Epic v1",
            "issue_type": "epic",
            "priority": 0,
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities1 = parser.parse_session(session_dir)
        assert len(entities1) == 1
        checksum1 = entities1[0].source_checksum

        # Modify the plan
        epic_task["title"] = "Epic v2"
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities2 = parser.parse_session(session_dir)
        assert len(entities2) == 1
        checksum2 = entities2[0].source_checksum

        assert checksum1 != checksum2, "Checksum should change when content changes"

    def test_parse_all_sessions(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test parsing all sessions."""
        # Create multiple session directories
        sessions = [
            ("session-1", "test-E01", "Epic 1"),
            ("session-2", "test-E02", "Epic 2"),
            ("session-3", "test-E03", "Epic 3"),
        ]

        for session_name, epic_id, epic_title in sessions:
            session_dir = tmp_sessions_root / session_name
            session_dir.mkdir()

            session_data = {"id": session_name}
            (session_dir / "session.json").write_text(json.dumps(session_data))

            epic_task = {
                "id": epic_id,
                "title": epic_title,
                "issue_type": "epic",
                "priority": 0,
            }
            (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_all()

        assert len(entities) == 3
        assert all(e.type == EntityType.PLAN for e in entities)
        assert {e.id for e in entities} == {"test-E01", "test-E02", "test-E03"}

        # Check that entities are sorted by ID
        entity_ids = [e.id for e in entities]
        assert entity_ids == sorted(entity_ids)

    def test_parse_nonexistent_sessions_root(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing when sessions root doesn't exist."""
        sessions_root = tmp_path / "nonexistent"
        parser = PlanParser(sessions_root)

        entities = parser.parse_all()

        assert len(entities) == 0
        assert "Sessions root not found" in caplog.text

    def test_parse_session_with_epic_id_in_metadata(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test parsing session with epic_id in session metadata."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {
            "id": "test-20260123-120000",
            "epic_id": "parent-epic-123",
            "created": "2026-01-23T12:00:00Z",
        }
        (session_dir / "session.json").write_text(json.dumps(session_data))

        epic_task = {
            "id": "test-E01",
            "title": "Child Epic",
            "issue_type": "epic",
            "priority": 0,
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.epic_id == "parent-epic-123"

    def test_parse_session_with_spec_id_in_task(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test parsing task with spec_id reference."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        epic_task = {
            "id": "test-E01",
            "title": "Epic linked to spec",
            "issue_type": "epic",
            "priority": 0,
            "spec_id": "auth-system",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.spec_id == "auth-system"

    def test_parse_session_task_missing_id(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handling task without id field."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Epic without id
        epic_task = {
            "title": "Epic without ID",
            "issue_type": "epic",
            "priority": 0,
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 0
        assert "Task missing id" in caplog.text

    def test_parse_session_not_a_directory(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test handling when session path is not a directory."""
        # Create a file instead of directory
        not_a_dir = tmp_sessions_root / "not-a-dir"
        not_a_dir.write_text("not a directory")

        entities = parser.parse_session(not_a_dir)

        assert len(entities) == 0

    def test_parse_all_ignores_files(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test that parse_all ignores files in sessions root."""
        # Create a valid session
        session_dir = tmp_sessions_root / "valid-session"
        session_dir.mkdir()
        session_data = {"id": "valid-session"}
        (session_dir / "session.json").write_text(json.dumps(session_data))
        epic_task = {"id": "test-E01", "title": "Epic", "issue_type": "epic", "priority": 0}
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        # Create a file (should be ignored)
        (tmp_sessions_root / "not-a-session.txt").write_text("ignore me")

        entities = parser.parse_all()

        # Should only get the valid session
        assert len(entities) == 1
        assert entities[0].id == "test-E01"

    def test_parse_session_with_dependencies(
        self, tmp_sessions_root: Path, parser: PlanParser
    ) -> None:
        """Test that dependencies are preserved in frontmatter."""
        session_dir = tmp_sessions_root / "test-20260123-120000"
        session_dir.mkdir()

        session_data = {"id": "test-20260123-120000"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        epic_task = {
            "id": "test-E01",
            "title": "Epic with deps",
            "issue_type": "epic",
            "priority": 0,
            "dependencies": [
                {"depends_on_id": "other-epic", "type": "blocks"},
            ],
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        entity = entities[0]
        assert entity.frontmatter is not None
        assert "dependencies" in entity.frontmatter
        assert len(entity.frontmatter["dependencies"]) == 1

    def test_parse_session_with_null_session_json(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a session with null content in session.json."""
        session_dir = tmp_sessions_root / "test-null"
        session_dir.mkdir()

        # Write null JSON
        (session_dir / "session.json").write_text("null")

        epic_task = {
            "id": "test-E01",
            "title": "Epic task",
            "issue_type": "epic",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        # Should handle gracefully - null becomes empty dict
        assert len(entities) == 1
        assert "Null content" in caplog.text

    def test_parse_session_with_empty_session_json(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a session with empty session.json."""
        session_dir = tmp_sessions_root / "test-empty"
        session_dir.mkdir()

        # Write empty file
        (session_dir / "session.json").write_text("")

        epic_task = {
            "id": "test-E01",
            "title": "Epic task",
            "issue_type": "epic",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        # Should skip session due to empty file
        # But should use directory name as fallback
        assert len(entities) == 1
        assert "Empty session.json" in caplog.text

    def test_parse_session_with_non_dict_session_json(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a session with non-dict content in session.json."""
        session_dir = tmp_sessions_root / "test-non-dict"
        session_dir.mkdir()

        # Write array instead of dict
        (session_dir / "session.json").write_text('["item1", "item2"]')

        epic_task = {
            "id": "test-E01",
            "title": "Epic task",
            "issue_type": "epic",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        # Should still create entities using directory name as fallback session ID
        # This is graceful degradation - we don't lose the tasks
        assert len(entities) == 1
        assert "not a dict" in caplog.text
        # plan_id should be directory name since session.json was invalid
        assert entities[0].plan_id == "test-non-dict"

    def test_parse_session_with_invalid_json_in_session_file(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a session with invalid JSON in session.json."""
        session_dir = tmp_sessions_root / "test-invalid-json"
        session_dir.mkdir()

        # Write invalid JSON
        (session_dir / "session.json").write_text('{"id": invalid json}')

        epic_task = {
            "id": "test-E01",
            "title": "Epic task",
            "issue_type": "epic",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        # Should use directory name as fallback
        assert len(entities) == 1
        assert "Invalid JSON" in caplog.text

    def test_parse_plan_with_empty_jsonl(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a session with empty plan.jsonl."""
        session_dir = tmp_sessions_root / "test-empty-plan"
        session_dir.mkdir()

        session_data = {"id": "test-empty-plan"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Write empty file
        (session_dir / "plan.jsonl").write_text("")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 0
        assert "Empty plan.jsonl" in caplog.text

    def test_parse_plan_with_null_tasks(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a plan.jsonl with null task lines."""
        session_dir = tmp_sessions_root / "test-null-tasks"
        session_dir.mkdir()

        session_data = {"id": "test-null-tasks"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Write null and valid tasks
        content = "null\n"
        content += json.dumps({"id": "test-E01", "title": "Valid Epic", "issue_type": "epic"}) + "\n"
        (session_dir / "plan.jsonl").write_text(content)

        entities = parser.parse_session(session_dir)

        # Should get 1 valid entity
        assert len(entities) == 1
        assert "Null task" in caplog.text

    def test_parse_plan_with_non_dict_tasks(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a plan.jsonl with non-dict task lines."""
        session_dir = tmp_sessions_root / "test-non-dict-tasks"
        session_dir.mkdir()

        session_data = {"id": "test-non-dict-tasks"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Write array and valid task
        content = '["not", "a", "dict"]\n'
        content += json.dumps({"id": "test-E01", "title": "Valid Epic", "issue_type": "epic"}) + "\n"
        (session_dir / "plan.jsonl").write_text(content)

        entities = parser.parse_session(session_dir)

        # Should get 1 valid entity
        assert len(entities) == 1
        assert "not a dict" in caplog.text

    def test_parse_plan_with_mixed_valid_invalid_lines(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing plan.jsonl with mix of valid and invalid lines."""
        session_dir = tmp_sessions_root / "test-mixed"
        session_dir.mkdir()

        session_data = {"id": "test-mixed"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Write mix of valid, invalid JSON, null, and non-dict
        content = json.dumps({"id": "test-E01", "title": "Epic 1", "issue_type": "epic"}) + "\n"
        content += "{invalid json}\n"
        content += "null\n"
        content += json.dumps({"id": "test-E02", "title": "Epic 2", "issue_type": "epic"}) + "\n"
        content += '["array"]\n'
        content += json.dumps({"id": "test-E03", "title": "Epic 3", "issue_type": "epic"}) + "\n"
        (session_dir / "plan.jsonl").write_text(content)

        entities = parser.parse_session(session_dir)

        # Should get 3 valid entities
        assert len(entities) == 3
        entity_ids = [e.id for e in entities]
        assert "test-E01" in entity_ids
        assert "test-E02" in entity_ids
        assert "test-E03" in entity_ids
        assert "Parsed 3 tasks" in caplog.text and "3 errors" in caplog.text

    def test_parse_task_with_missing_id(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a task without an id field."""
        session_dir = tmp_sessions_root / "test-no-id"
        session_dir.mkdir()

        session_data = {"id": "test-no-id"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Epic without id
        epic_task = {
            "title": "Epic without ID",
            "issue_type": "epic",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 0
        assert "missing id" in caplog.text

    def test_parse_task_with_non_string_id(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a task with non-string id (should convert)."""
        session_dir = tmp_sessions_root / "test-numeric-id"
        session_dir.mkdir()

        session_data = {"id": "test-numeric-id"}
        (session_dir / "session.json").write_text(json.dumps(session_data))

        # Epic with numeric id
        epic_task = {
            "id": 12345,  # numeric instead of string
            "title": "Epic with numeric ID",
            "issue_type": "epic",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        assert entities[0].id == "12345"  # Converted to string
        assert "not a string" in caplog.text

    def test_parse_task_with_invalid_timestamps(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing a task with invalid timestamp formats."""
        import logging
        caplog.set_level(logging.DEBUG)  # Enable DEBUG level to see timestamp warnings

        session_dir = tmp_sessions_root / "test-invalid-timestamps"
        session_dir.mkdir()

        # Session with invalid timestamps
        session_data = {
            "id": "test-invalid-timestamps",
            "created": "not-a-timestamp",
            "updated": "also-invalid",
        }
        (session_dir / "session.json").write_text(json.dumps(session_data))

        epic_task = {
            "id": "test-E01",
            "title": "Epic task",
            "issue_type": "epic",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        assert len(entities) == 1
        # Timestamps should be None due to invalid format
        assert entities[0].created_at is None
        assert entities[0].updated_at is None
        # Check that debug message was logged
        assert "Invalid" in caplog.text and "timestamp" in caplog.text

    def test_parse_session_with_unicode_error(
        self, tmp_sessions_root: Path, parser: PlanParser, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test parsing session.json with invalid UTF-8 encoding."""
        session_dir = tmp_sessions_root / "test-unicode"
        session_dir.mkdir()

        # Write invalid UTF-8 bytes
        (session_dir / "session.json").write_bytes(b"\xff\xfe\x00\x00Invalid UTF-8")

        epic_task = {
            "id": "test-E01",
            "title": "Epic task",
            "issue_type": "epic",
        }
        (session_dir / "plan.jsonl").write_text(json.dumps(epic_task) + "\n")

        entities = parser.parse_session(session_dir)

        # Should use directory name as fallback
        assert len(entities) == 1
        assert "Unable to read" in caplog.text or "UTF-8" in caplog.text
