"""
Tests for LedgerParser.

Tests the ledger parser's ability to convert ledger entries
into DashboardEntity objects with proper stage computation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.dashboard.db.models import EntityType, Stage
from cub.core.dashboard.sync.parsers.ledger import LedgerParser
from cub.core.ledger.models import (
    Attempt,
    DriftRecord,
    LedgerEntry,
    LedgerIndex,
    Lineage,
    Outcome,
    TaskSnapshot,
    TokenUsage,
    Verification,
    WorkflowState,
)


@pytest.fixture
def tmp_ledger_dir(tmp_path: Path) -> Path:
    """Create temporary ledger directory structure."""
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    (ledger_dir / "by-task").mkdir()
    return ledger_dir


@pytest.fixture
def sample_ledger_entry() -> LedgerEntry:
    """Create a sample ledger entry for testing."""
    return LedgerEntry(
        version=1,
        id="cub-001",
        title="Implement user authentication",
        lineage=Lineage(
            spec_file="specs/planned/auth.md",
            plan_file=".cub/sessions/session-123/plan.jsonl",
            epic_id="cub-epic-1",
        ),
        task=TaskSnapshot(
            title="Implement user authentication",
            description="Add JWT-based authentication to the API",
            type="task",
            priority=0,
            labels=["backend", "security"],
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            captured_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        ),
        task_changed=None,
        attempts=[
            Attempt(
                attempt_number=1,
                run_id="run-123",
                started_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
                completed_at=datetime(2024, 1, 1, 11, 30, 0, tzinfo=timezone.utc),
                harness="claude",
                model="sonnet",
                success=True,
                tokens=TokenUsage(input_tokens=5000, output_tokens=2000),
                cost_usd=0.15,
                duration_seconds=1800,
            )
        ],
        outcome=Outcome(
            success=True,
            partial=False,
            completed_at=datetime(2024, 1, 1, 11, 30, 0, tzinfo=timezone.utc),
            total_cost_usd=0.15,
            total_attempts=1,
            total_duration_seconds=1800,
            final_model="sonnet",
            escalated=False,
            escalation_path=[],
            files_changed=["src/auth/middleware.ts", "src/auth/jwt.ts"],
            commits=[],
            approach="Used JWT for stateless authentication",
            decisions=["Chose bcrypt for password hashing"],
            lessons_learned=["JWT expiration should be configurable"],
        ),
        drift=DriftRecord(
            additions=[],
            omissions=[],
            severity="none",
        ),
        verification=Verification(
            status="pass",
            checked_at=datetime(2024, 1, 1, 11, 35, 0, tzinfo=timezone.utc),
            tests_passed=True,
            typecheck_passed=True,
            lint_passed=True,
            notes=["All tests passed"],
        ),
        workflow=WorkflowState(
            stage="dev_complete",
            stage_updated_at=datetime(2024, 1, 1, 11, 30, 0, tzinfo=timezone.utc),
        ),
        state_history=[],
        started_at=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2024, 1, 1, 11, 30, 0, tzinfo=timezone.utc),
        tokens=TokenUsage(input_tokens=5000, output_tokens=2000),
        cost_usd=0.15,
        duration_seconds=1800,
        iterations=1,
        approach="",
        decisions=[],
        lessons_learned=[],
        files_changed=[],
        commits=[],
        spec_file=None,
        run_log_path=None,
        epic_id="cub-epic-1",
        verification_status="pass",
        verification_notes=[],
        harness_name="claude",
        harness_model="sonnet",
        workflow_stage=None,
        workflow_stage_updated_at=None,
    )


@pytest.fixture
def sample_index_entry() -> LedgerIndex:
    """Create a sample ledger index entry."""
    return LedgerIndex(
        id="cub-001",
        title="Implement user authentication",
        completed="2024-01-01",
        cost_usd=0.15,
        files=["src/auth/middleware.ts", "src/auth/jwt.ts"],
        commit="abc123f",
        spec="specs/planned/auth.md",
        epic="cub-epic-1",
        verification="pass",
        tokens=7000,
        workflow_stage=None,
    )


def write_ledger_files(
    ledger_dir: Path,
    index_entries: list[LedgerIndex],
    full_entries: dict[str, LedgerEntry],
) -> None:
    """Write ledger files to disk."""
    # Write index.jsonl
    index_file = ledger_dir / "index.jsonl"
    with open(index_file, "w", encoding="utf-8") as f:
        for entry in index_entries:
            f.write(entry.model_dump_json() + "\n")

    # Write full entries
    by_task_dir = ledger_dir / "by-task"
    for task_id, entry in full_entries.items():
        task_file = by_task_dir / f"{task_id}.json"
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(entry.model_dump(mode="json"), f, indent=2)


@pytest.fixture
def parser_with_data(
    tmp_ledger_dir: Path,
    sample_index_entry: LedgerIndex,
    sample_ledger_entry: LedgerEntry,
) -> LedgerParser:
    """Create parser with sample data written to disk."""
    write_ledger_files(
        tmp_ledger_dir,
        index_entries=[sample_index_entry],
        full_entries={"cub-001": sample_ledger_entry},
    )
    return LedgerParser(ledger_dir=tmp_ledger_dir)


class TestLedgerParser:
    """Test suite for LedgerParser."""

    def test_parse_empty_ledger(self, tmp_ledger_dir: Path) -> None:
        """Test parsing empty ledger directory."""
        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        assert len(entities) == 0

    def test_parse_nonexistent_ledger(self, tmp_path: Path) -> None:
        """Test parsing nonexistent ledger directory."""
        nonexistent = tmp_path / "nonexistent"
        parser = LedgerParser(ledger_dir=nonexistent)
        entities = parser.parse()

        assert len(entities) == 0

    def test_parse_single_entry(self, parser_with_data: LedgerParser) -> None:
        """Test parsing a single ledger entry."""
        entities = parser_with_data.parse()

        assert len(entities) == 1
        entity = entities[0]

        assert entity.id == "cub-001"
        assert entity.title == "Implement user authentication"
        assert entity.type == EntityType.LEDGER
        assert entity.stage == Stage.COMPLETE  # dev_complete -> COMPLETE

    def test_stage_computation_dev_complete(self, tmp_ledger_dir: Path) -> None:
        """Test stage computation for dev_complete workflow stage."""
        entry = LedgerEntry(
            id="task-1",
            title="Test Task",
            workflow=WorkflowState(stage="dev_complete"),
            completed_at=datetime.now(timezone.utc),
        )
        write_ledger_files(
            tmp_ledger_dir,
            index_entries=[LedgerIndex(id="task-1", title="Test Task", completed="2024-01-01")],
            full_entries={"task-1": entry},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        assert len(entities) == 1
        assert entities[0].stage == Stage.COMPLETE

    def test_stage_computation_needs_review(self, tmp_ledger_dir: Path) -> None:
        """Test stage computation for needs_review workflow stage."""
        entry = LedgerEntry(
            id="task-1",
            title="Test Task",
            workflow=WorkflowState(stage="needs_review"),
            completed_at=datetime.now(timezone.utc),
        )
        write_ledger_files(
            tmp_ledger_dir,
            index_entries=[
                LedgerIndex(
                    id="task-1",
                    title="Test Task",
                    completed="2024-01-01",
                    workflow_stage="needs_review",
                )
            ],
            full_entries={"task-1": entry},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        assert len(entities) == 1
        assert entities[0].stage == Stage.NEEDS_REVIEW

    def test_stage_computation_validated(self, tmp_ledger_dir: Path) -> None:
        """Test stage computation for validated workflow stage."""
        entry = LedgerEntry(
            id="task-1",
            title="Test Task",
            workflow=WorkflowState(stage="validated"),
            completed_at=datetime.now(timezone.utc),
        )
        write_ledger_files(
            tmp_ledger_dir,
            index_entries=[
                LedgerIndex(
                    id="task-1",
                    title="Test Task",
                    completed="2024-01-01",
                    workflow_stage="validated",
                )
            ],
            full_entries={"task-1": entry},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        assert len(entities) == 1
        assert entities[0].stage == Stage.VALIDATED

    def test_stage_computation_released(self, tmp_ledger_dir: Path) -> None:
        """Test stage computation for released workflow stage."""
        entry = LedgerEntry(
            id="task-1",
            title="Test Task",
            workflow=WorkflowState(stage="released"),
            completed_at=datetime.now(timezone.utc),
        )
        write_ledger_files(
            tmp_ledger_dir,
            index_entries=[
                LedgerIndex(
                    id="task-1",
                    title="Test Task",
                    completed="2024-01-01",
                    workflow_stage="released",
                )
            ],
            full_entries={"task-1": entry},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        assert len(entities) == 1
        assert entities[0].stage == Stage.RELEASED

    def test_entity_metadata_from_outcome(self, parser_with_data: LedgerParser) -> None:
        """Test entity metadata extraction from outcome."""
        entities = parser_with_data.parse()
        entity = entities[0]

        # Should use outcome metrics
        assert entity.cost_usd == 0.15
        assert entity.tokens == 7000
        assert entity.duration_seconds == 1800
        assert entity.verification_status == "pass"

    def test_entity_metadata_epic_lineage(self, parser_with_data: LedgerParser) -> None:
        """Test epic_id extraction from lineage."""
        entities = parser_with_data.parse()
        entity = entities[0]

        assert entity.epic_id == "cub-epic-1"

    def test_entity_metadata_spec_plan_lineage(self, parser_with_data: LedgerParser) -> None:
        """Test spec_id and plan_id extraction from lineage."""
        entities = parser_with_data.parse()
        entity = entities[0]

        assert entity.spec_id == "specs/planned/auth.md"
        assert entity.plan_id == ".cub/sessions/session-123/plan.jsonl"

    def test_checksum_computation(self, tmp_ledger_dir: Path) -> None:
        """Test checksum computation for change detection."""
        entry1 = LedgerEntry(
            id="task-1",
            title="Test Task",
            completed_at=datetime.now(timezone.utc),
        )
        entry2 = LedgerEntry(
            id="task-1",
            title="Test Task",
            completed_at=datetime.now(timezone.utc),
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        checksum1 = parser._compute_checksum(entry1)
        checksum2 = parser._compute_checksum(entry2)

        # Different timestamps should produce different checksums
        # (but same content structure)
        assert isinstance(checksum1, str)
        assert isinstance(checksum2, str)
        assert len(checksum1) == 32  # MD5 hex digest

    def test_parse_multiple_entries(self, tmp_ledger_dir: Path) -> None:
        """Test parsing multiple ledger entries."""
        entries = [
            LedgerEntry(
                id="task-1",
                title="Task 1",
                workflow=WorkflowState(stage="dev_complete"),
                completed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            ),
            LedgerEntry(
                id="task-2",
                title="Task 2",
                workflow=WorkflowState(stage="needs_review"),
                completed_at=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            ),
            LedgerEntry(
                id="task-3",
                title="Task 3",
                workflow=WorkflowState(stage="validated"),
                completed_at=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        index_entries = [
            LedgerIndex(id="task-1", title="Task 1", completed="2024-01-01"),
            LedgerIndex(id="task-2", title="Task 2", completed="2024-01-02"),
            LedgerIndex(id="task-3", title="Task 3", completed="2024-01-03"),
        ]

        write_ledger_files(
            tmp_ledger_dir,
            index_entries=index_entries,
            full_entries={e.id: e for e in entries},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        assert len(entities) == 3
        # Should be sorted by completion date (newest first)
        assert entities[0].id == "task-3"
        assert entities[1].id == "task-2"
        assert entities[2].id == "task-1"

    def test_parse_by_epic(self, tmp_ledger_dir: Path) -> None:
        """Test parsing ledger entries by epic."""
        entries = [
            LedgerEntry(
                id="task-1",
                title="Task 1",
                lineage=Lineage(epic_id="epic-1"),
                completed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            ),
            LedgerEntry(
                id="task-2",
                title="Task 2",
                lineage=Lineage(epic_id="epic-1"),
                completed_at=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            ),
            LedgerEntry(
                id="task-3",
                title="Task 3",
                lineage=Lineage(epic_id="epic-2"),
                completed_at=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        index_entries = [
            LedgerIndex(id="task-1", title="Task 1", completed="2024-01-01", epic="epic-1"),
            LedgerIndex(id="task-2", title="Task 2", completed="2024-01-02", epic="epic-1"),
            LedgerIndex(id="task-3", title="Task 3", completed="2024-01-03", epic="epic-2"),
        ]

        write_ledger_files(
            tmp_ledger_dir,
            index_entries=index_entries,
            full_entries={e.id: e for e in entries},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        epic1_entities = parser.parse_by_epic("epic-1")

        assert len(epic1_entities) == 2
        assert all(e.epic_id == "epic-1" for e in epic1_entities)

    def test_parse_by_stage(self, tmp_ledger_dir: Path) -> None:
        """Test parsing ledger entries by stage."""
        entries = [
            LedgerEntry(
                id="task-1",
                title="Task 1",
                workflow=WorkflowState(stage="dev_complete"),
                completed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            ),
            LedgerEntry(
                id="task-2",
                title="Task 2",
                workflow=WorkflowState(stage="needs_review"),
                completed_at=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            ),
            LedgerEntry(
                id="task-3",
                title="Task 3",
                workflow=WorkflowState(stage="needs_review"),
                completed_at=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        index_entries = [
            LedgerIndex(id="task-1", title="Task 1", completed="2024-01-01"),
            LedgerIndex(id="task-2", title="Task 2", completed="2024-01-02"),
            LedgerIndex(id="task-3", title="Task 3", completed="2024-01-03"),
        ]

        write_ledger_files(
            tmp_ledger_dir,
            index_entries=index_entries,
            full_entries={e.id: e for e in entries},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        review_entities = parser.parse_by_stage(Stage.NEEDS_REVIEW)

        assert len(review_entities) == 2
        assert all(e.stage == Stage.NEEDS_REVIEW for e in review_entities)

    def test_missing_full_entry_file(self, tmp_ledger_dir: Path) -> None:
        """Test handling of missing full entry file."""
        # Write index but no full entry
        index_file = tmp_ledger_dir / "index.jsonl"
        with open(index_file, "w", encoding="utf-8") as f:
            f.write('{"id": "task-1", "title": "Task 1", "completed": "2024-01-01"}\n')

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        # Should handle gracefully and skip the entry
        assert len(entities) == 0

    def test_legacy_epic_id_fallback(self, tmp_ledger_dir: Path) -> None:
        """Test fallback to legacy epic_id field."""
        entry = LedgerEntry(
            id="task-1",
            title="Task 1",
            lineage=Lineage(epic_id=None),  # No epic in lineage
            epic_id="epic-legacy",  # Use legacy field
            completed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        )

        write_ledger_files(
            tmp_ledger_dir,
            index_entries=[LedgerIndex(id="task-1", title="Task 1", completed="2024-01-01")],
            full_entries={"task-1": entry},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        assert len(entities) == 1
        assert entities[0].epic_id == "epic-legacy"

    def test_description_excerpt_truncation(self, tmp_ledger_dir: Path) -> None:
        """Test description excerpt truncation."""
        long_description = "A" * 150
        entry = LedgerEntry(
            id="task-1",
            title="Task 1",
            task=TaskSnapshot(
                title="Task 1",
                description=long_description,
                captured_at=datetime.now(timezone.utc),
            ),
            completed_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        )

        write_ledger_files(
            tmp_ledger_dir,
            index_entries=[LedgerIndex(id="task-1", title="Task 1", completed="2024-01-01")],
            full_entries={"task-1": entry},
        )

        parser = LedgerParser(ledger_dir=tmp_ledger_dir)
        entities = parser.parse()

        assert len(entities) == 1
        assert entities[0].description_excerpt is not None
        assert len(entities[0].description_excerpt) <= 100
        assert entities[0].description_excerpt.endswith("...")
