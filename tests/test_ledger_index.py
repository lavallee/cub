"""Tests for ledger index functionality.

Tests validate:
- Index update when entries are created or modified
- Index rebuild from task files
- Index consistency (all tasks in files are indexed)
- Search uses index for fast lookups
- Index filtering by various criteria
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.ledger.models import (
    LedgerEntry,
    TokenUsage,
    VerificationStatus,
    WorkflowStage,
)
from cub.core.ledger.reader import LedgerReader
from cub.core.ledger.writer import LedgerWriter


@pytest.fixture
def ledger_dir(tmp_path: Path) -> Path:
    """Create a temporary ledger directory."""
    ledger = tmp_path / ".cub" / "ledger"
    ledger.mkdir(parents=True)
    return ledger


@pytest.fixture
def sample_entry() -> LedgerEntry:
    """Create a sample ledger entry for testing."""
    return LedgerEntry(
        id="cub-m4j.1",
        title="Implement ledger core",
        epic_id="cub-m4j",
        spec_file="specs/planned/ledger.md",
        files_changed=["src/ledger/models.py", "src/ledger/writer.py"],
        tokens=TokenUsage(input_tokens=800, output_tokens=200),
        cost_usd=0.05,
        harness_name="claude",
        completed_at=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        verification_status=VerificationStatus.PASS,
    )


@pytest.fixture
def sample_entry_2() -> LedgerEntry:
    """Create a second sample ledger entry."""
    return LedgerEntry(
        id="cub-m4j.2",
        title="Add ledger reader",
        epic_id="cub-m4j",
        spec_file="specs/planned/ledger.md",
        files_changed=["src/ledger/reader.py"],
        tokens=TokenUsage(input_tokens=600, output_tokens=150),
        cost_usd=0.03,
        harness_name="claude",
        completed_at=datetime(2024, 1, 20, 14, 0, tzinfo=timezone.utc),
        verification_status=VerificationStatus.PASS,
    )


@pytest.fixture
def sample_entry_3_with_workflow() -> LedgerEntry:
    """Create an entry with workflow stage set."""
    entry = LedgerEntry(
        id="cub-m4j.3",
        title="Add dashboard integration",
        epic_id="cub-m4j",
        spec_file="specs/planned/ledger.md",
        files_changed=["src/dashboard/sync/ledger.py"],
        tokens=TokenUsage(input_tokens=900, output_tokens=300),
        cost_usd=0.08,
        harness_name="claude",
        completed_at=datetime(2024, 1, 25, 11, 0, tzinfo=timezone.utc),
        verification_status=VerificationStatus.PASS,
    )
    entry.workflow_stage = WorkflowStage.VALIDATED
    return entry


@pytest.fixture
def sample_entry_failed() -> LedgerEntry:
    """Create a failed entry for testing."""
    return LedgerEntry(
        id="cub-x3s.1",
        title="Failed task",
        epic_id="cub-x3s",
        spec_file="specs/planned/failed.md",
        files_changed=["src/test.py"],
        tokens=TokenUsage(input_tokens=400, output_tokens=100),
        cost_usd=0.02,
        harness_name="claude",
        completed_at=datetime(2024, 1, 10, 9, 0, tzinfo=timezone.utc),
        verification_status=VerificationStatus.FAIL,
    )


class TestIndexUpdate:
    """Tests for index update when creating and modifying entries."""

    def test_index_created_on_first_entry(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test that index.jsonl is created when first entry is added."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        # Verify index file exists
        assert writer.index_file.exists()

        # Verify index contains entry
        with open(writer.index_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        index_data = json.loads(lines[0])
        assert index_data["id"] == sample_entry.id

    def test_index_appends_new_entry(
        self, ledger_dir: Path, sample_entry: LedgerEntry, sample_entry_2: LedgerEntry
    ) -> None:
        """Test that new entries are appended to index."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        # Verify index has both entries
        with open(writer.index_file) as f:
            lines = f.readlines()
        assert len(lines) == 2

        # Verify both IDs are in index
        ids = [json.loads(line)["id"] for line in lines]
        assert sample_entry.id in ids
        assert sample_entry_2.id in ids

    def test_index_updated_on_entry_modification(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test that modifying an entry updates the index."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        # Modify entry
        sample_entry.title = "Updated Title"
        sample_entry.cost_usd = 0.10
        writer.update_entry(sample_entry)

        # Verify index is updated (not appended)
        with open(writer.index_file) as f:
            lines = f.readlines()
        assert len(lines) == 1  # Still one entry

        # Verify updated values in index
        index_data = json.loads(lines[0])
        assert index_data["title"] == "Updated Title"
        assert index_data["cost_usd"] == 0.10

    def test_index_entry_schema(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test that index entries contain all expected fields."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        with open(writer.index_file) as f:
            index_data = json.loads(f.readline())

        # Verify required fields
        required_fields = [
            "id",
            "title",
            "completed",
            "cost_usd",
            "files",
            "verification",
            "tokens",
        ]
        for field in required_fields:
            assert field in index_data, f"Missing required field: {field}"

        # Verify field types
        assert isinstance(index_data["id"], str)
        assert isinstance(index_data["title"], str)
        assert isinstance(index_data["completed"], str)
        assert isinstance(index_data["cost_usd"], (int, float))
        assert isinstance(index_data["files"], list)
        assert isinstance(index_data["verification"], str)
        assert isinstance(index_data["tokens"], int)

    def test_index_preserves_optional_fields(
        self, ledger_dir: Path, sample_entry_3_with_workflow: LedgerEntry
    ) -> None:
        """Test that optional fields like workflow_stage are preserved in index."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry_3_with_workflow)

        with open(writer.index_file) as f:
            index_data = json.loads(f.readline())

        assert index_data["workflow_stage"] == "validated"
        assert index_data["epic"] == "cub-m4j"


class TestIndexRebuild:
    """Tests for rebuilding index from task files."""

    def test_rebuild_index_from_task_files(
        self, ledger_dir: Path, sample_entry: LedgerEntry, sample_entry_2: LedgerEntry
    ) -> None:
        """Test rebuilding index from all task files."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        # Delete index
        writer.index_file.unlink()
        assert not writer.index_file.exists()

        # Rebuild index
        writer.rebuild_index()

        # Verify index is recreated
        assert writer.index_file.exists()

        with open(writer.index_file) as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_rebuild_preserves_entry_order(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
        sample_entry_failed: LedgerEntry,
    ) -> None:
        """Test that rebuilding index preserves file order."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)
        writer.create_entry(sample_entry_failed)

        # Get original order
        with open(writer.index_file) as f:
            original_ids = [json.loads(line)["id"] for line in f.readlines()]

        # Rebuild
        writer.index_file.unlink()
        writer.rebuild_index()

        # Verify order is preserved
        with open(writer.index_file) as f:
            rebuilt_ids = [json.loads(line)["id"] for line in f.readlines()]

        assert original_ids == rebuilt_ids

    def test_rebuild_empty_directory(self, ledger_dir: Path) -> None:
        """Test rebuilding index when no task files exist."""
        writer = LedgerWriter(ledger_dir)
        writer.rebuild_index()

        # Index file should not be created if no tasks
        assert not writer.index_file.exists()

    def test_rebuild_handles_corrupted_task_file(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test rebuild handles corrupted task files gracefully."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        # Create a corrupted task file
        by_task_dir = ledger_dir / "by-task"
        corrupted_file = by_task_dir / "corrupted.json"
        corrupted_file.write_text("{ invalid json")

        # Rebuild should handle gracefully
        with pytest.raises(json.JSONDecodeError):
            writer.rebuild_index()


class TestIndexConsistency:
    """Tests for index consistency and validation."""

    def test_index_consistency_all_tasks_indexed(
        self, ledger_dir: Path, sample_entry: LedgerEntry, sample_entry_2: LedgerEntry
    ) -> None:
        """Test that all task files have corresponding index entries."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        reader = LedgerReader(ledger_dir)

        # Get all task files
        by_task_dir = ledger_dir / "by-task"
        task_files = set(f.stem for f in by_task_dir.glob("*.json"))

        # Get all indexed tasks
        indexed_tasks = set(e.id for e in reader._read_index())

        assert task_files == indexed_tasks

    def test_index_entries_match_task_files(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test that index entries match the actual task files."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        reader = LedgerReader(ledger_dir)

        # Get index entry
        index_entries = list(reader._read_index())
        assert len(index_entries) == 1
        index_entry = index_entries[0]

        # Get task file entry
        task_entry = reader.get_task(sample_entry.id)
        assert task_entry is not None

        # Verify key fields match
        assert index_entry.id == task_entry.id
        assert index_entry.title == task_entry.title
        assert index_entry.cost_usd == task_entry.cost_usd
        assert index_entry.tokens == task_entry.tokens.total_tokens

    def test_index_consistency_after_update(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test index remains consistent after entry update."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        # Update entry
        sample_entry.cost_usd = 0.25
        sample_entry.verification_status = VerificationStatus.WARN
        writer.update_entry(sample_entry)

        reader = LedgerReader(ledger_dir)

        # Verify index matches updated task
        index_entries = list(reader._read_index())
        assert len(index_entries) == 1
        assert index_entries[0].cost_usd == 0.25
        assert index_entries[0].verification == "warn"


class TestSearchUsesIndex:
    """Tests that search operations use the index effectively."""

    def test_search_by_title(
        self, ledger_dir: Path, sample_entry: LedgerEntry, sample_entry_2: LedgerEntry
    ) -> None:
        """Test searching tasks by title uses index."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        reader = LedgerReader(ledger_dir)
        results = reader.search_tasks("reader")

        assert len(results) == 1
        assert results[0].id == "cub-m4j.2"

    def test_search_case_insensitive(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test that search is case-insensitive."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        reader = LedgerReader(ledger_dir)

        # Search with different cases
        results1 = reader.search_tasks("implement")
        results2 = reader.search_tasks("IMPLEMENT")
        results3 = reader.search_tasks("ImPlEmEnT")

        assert len(results1) == len(results2) == len(results3) == 1
        assert results1[0].id == results2[0].id == results3[0].id

    def test_search_in_files(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test searching in changed files."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        reader = LedgerReader(ledger_dir)
        results = reader.search_tasks("models.py")

        assert len(results) == 1
        assert results[0].id == sample_entry.id

    def test_search_with_filters(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
        sample_entry_failed: LedgerEntry,
    ) -> None:
        """Test search with multiple filters."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)
        writer.create_entry(sample_entry_failed)

        reader = LedgerReader(ledger_dir)

        # Search with epic filter
        results = reader.search_tasks(
            "ledger", epic="cub-m4j", verification=VerificationStatus.PASS
        )

        assert len(results) == 2
        assert all(r.epic == "cub-m4j" for r in results)
        assert all(r.verification == "pass" for r in results)

    def test_list_by_verification(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_failed: LedgerEntry,
    ) -> None:
        """Test listing tasks by verification status."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_failed)

        reader = LedgerReader(ledger_dir)

        # List passed tasks
        passed = reader.list_tasks(verification=VerificationStatus.PASS)
        assert len(passed) == 1
        assert passed[0].verification == "pass"

        # List failed tasks
        failed = reader.list_tasks(verification=VerificationStatus.FAIL)
        assert len(failed) == 1
        assert failed[0].verification == "fail"

    def test_list_by_epic(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
        sample_entry_failed: LedgerEntry,
    ) -> None:
        """Test listing tasks by epic."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)
        writer.create_entry(sample_entry_failed)

        reader = LedgerReader(ledger_dir)

        # List cub-m4j tasks
        m4j_tasks = reader.list_tasks(epic="cub-m4j")
        assert len(m4j_tasks) == 2
        assert all(t.epic == "cub-m4j" for t in m4j_tasks)

        # List cub-x3s tasks
        x3s_tasks = reader.list_tasks(epic="cub-x3s")
        assert len(x3s_tasks) == 1
        assert x3s_tasks[0].epic == "cub-x3s"

    def test_search_multiple_fields(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test searching across multiple fields."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        reader = LedgerReader(ledger_dir)

        # Search for term in title
        results = reader.search_tasks("core", fields=["title"])
        assert len(results) == 1
        assert results[0].id == "cub-m4j.1"

        # Search in all fields
        results = reader.search_tasks("reader", fields=["title", "files"])
        assert len(results) == 1
        assert results[0].id == "cub-m4j.2"


class TestIndexDates:
    """Tests for date-based index queries."""

    def test_filter_by_since_date(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test filtering index entries by since date."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)  # 2024-01-15
        writer.create_entry(sample_entry_2)  # 2024-01-20

        reader = LedgerReader(ledger_dir)

        # Get tasks since 2024-01-18
        results = reader.list_tasks(since="2024-01-18")
        assert len(results) == 1
        assert results[0].id == "cub-m4j.2"

        # Get tasks since 2024-01-15
        results = reader.list_tasks(since="2024-01-15")
        assert len(results) == 2

    def test_cost_above_filter(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test filtering by cost threshold."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)  # $0.05
        writer.create_entry(sample_entry_2)  # $0.03

        reader = LedgerReader(ledger_dir)

        # Get expensive tasks
        results = reader._query_index(cost_above=0.04)
        assert len(results) == 1
        assert results[0].id == "cub-m4j.1"
