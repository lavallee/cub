"""Tests for ledger reader and writer."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.ledger.models import (
    LedgerEntry,
    LedgerIndex,
    TokenUsage,
    VerificationStatus,
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
        id="beads-abc",
        title="Implement feature X",
        epic_id="epic-123",
        spec_file="specs/planned/feature-x.md",
        files_changed=["src/feature.py", "tests/test_feature.py"],
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
        id="beads-def",
        title="Fix bug in module Y",
        epic_id="epic-456",
        spec_file="specs/planned/bug-fix.md",
        files_changed=["src/module_y.py"],
        tokens=TokenUsage(input_tokens=400, output_tokens=100),
        cost_usd=0.025,
        harness_name="codex",
        completed_at=datetime(2024, 1, 20, 14, 0, tzinfo=timezone.utc),
        verification_status=VerificationStatus.FAIL,
    )


class TestLedgerWriter:
    """Tests for LedgerWriter."""

    def test_init(self, ledger_dir: Path) -> None:
        """Test writer initialization."""
        writer = LedgerWriter(ledger_dir)
        assert writer.ledger_dir == ledger_dir
        assert writer.index_file == ledger_dir / "index.jsonl"
        assert writer.by_task_dir == ledger_dir / "by-task"

    def test_create_entry(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test creating a ledger entry."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        # Verify by-task file was created
        task_file = ledger_dir / "by-task" / f"{sample_entry.id}.json"
        assert task_file.exists()

        # Verify content
        with open(task_file) as f:
            data = json.load(f)
        assert data["id"] == sample_entry.id
        assert data["title"] == sample_entry.title
        assert data["epic_id"] == sample_entry.epic_id

        # Verify index was updated
        assert writer.index_file.exists()
        with open(writer.index_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        index_data = json.loads(lines[0])
        assert index_data["id"] == sample_entry.id

    def test_create_multiple_entries(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test creating multiple entries appends to index."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        # Verify both task files exist
        assert (ledger_dir / "by-task" / f"{sample_entry.id}.json").exists()
        assert (ledger_dir / "by-task" / f"{sample_entry_2.id}.json").exists()

        # Verify index has both entries
        with open(writer.index_file) as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_entry_exists(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test checking if entry exists."""
        writer = LedgerWriter(ledger_dir)

        # Should not exist initially
        assert not writer.entry_exists(sample_entry.id)

        # Create entry
        writer.create_entry(sample_entry)

        # Should exist now
        assert writer.entry_exists(sample_entry.id)
        assert not writer.entry_exists("nonexistent-id")

    def test_update_entry(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test updating an existing entry."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        # Update the entry
        updated_entry = LedgerEntry(
            id=sample_entry.id,
            title="Updated title",
            epic_id=sample_entry.epic_id,
            spec_file=sample_entry.spec_file,
            files_changed=sample_entry.files_changed,
            tokens=TokenUsage(input_tokens=1500, output_tokens=500),  # Changed
            cost_usd=0.10,  # Changed
            harness_name=sample_entry.harness_name,
            completed_at=sample_entry.completed_at,
            verification_status=VerificationStatus.PASS,
        )
        writer.update_entry(updated_entry)

        # Verify file was updated
        task_file = ledger_dir / "by-task" / f"{sample_entry.id}.json"
        with open(task_file) as f:
            data = json.load(f)
        assert data["title"] == "Updated title"
        assert data["tokens"]["input_tokens"] == 1500
        assert data["cost_usd"] == 0.10

    def test_update_nonexistent_entry_raises(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test updating nonexistent entry raises FileNotFoundError."""
        writer = LedgerWriter(ledger_dir)

        with pytest.raises(FileNotFoundError, match="not found"):
            writer.update_entry(sample_entry)

    def test_rebuild_index_empty_by_task_dir(self, ledger_dir: Path) -> None:
        """Test _rebuild_index with no by-task directory."""
        writer = LedgerWriter(ledger_dir)
        # Should not raise even when by_task_dir doesn't exist
        writer._rebuild_index()

    def test_update_entry_rebuilds_index(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test that update_entry properly rebuilds the index."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        # Update the first entry
        updated_entry = LedgerEntry(
            id=sample_entry.id,
            title="Updated title",
            epic_id=sample_entry.epic_id,
            completed_at=sample_entry.completed_at,
        )
        writer.update_entry(updated_entry)

        # Verify index was rebuilt with updated entry
        reader = LedgerReader(ledger_dir)
        tasks = reader.list_tasks()
        assert len(tasks) == 2
        # Find the updated entry
        updated = next(t for t in tasks if t.id == sample_entry.id)
        assert updated.title == "Updated title"


class TestLedgerReader:
    """Tests for LedgerReader."""

    def test_init(self, ledger_dir: Path) -> None:
        """Test reader initialization."""
        reader = LedgerReader(ledger_dir)
        assert reader.ledger_dir == ledger_dir
        assert reader.index_file == ledger_dir / "index.jsonl"
        assert reader.by_task_dir == ledger_dir / "by-task"

    def test_exists(self, ledger_dir: Path, tmp_path: Path) -> None:
        """Test checking if ledger exists."""
        reader = LedgerReader(ledger_dir)
        assert reader.exists()

        nonexistent = LedgerReader(tmp_path / "nonexistent")
        assert not nonexistent.exists()

    def test_list_tasks_empty(self, ledger_dir: Path) -> None:
        """Test listing tasks from empty ledger."""
        reader = LedgerReader(ledger_dir)
        tasks = reader.list_tasks()
        assert tasks == []

    def test_list_tasks(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test listing tasks from ledger."""
        # Write entries first
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        # Read back
        reader = LedgerReader(ledger_dir)
        tasks = reader.list_tasks()
        assert len(tasks) == 2
        assert tasks[0].id == sample_entry.id
        assert tasks[1].id == sample_entry_2.id

    def test_list_tasks_filter_by_since(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test filtering tasks by date."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)  # 2024-01-15
        writer.create_entry(sample_entry_2)  # 2024-01-20

        reader = LedgerReader(ledger_dir)
        tasks = reader.list_tasks(since="2024-01-18")
        assert len(tasks) == 1
        assert tasks[0].id == sample_entry_2.id

    def test_list_tasks_filter_by_epic(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test filtering tasks by epic."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)  # epic-123
        writer.create_entry(sample_entry_2)  # epic-456

        reader = LedgerReader(ledger_dir)
        tasks = reader.list_tasks(epic="epic-123")
        assert len(tasks) == 1
        assert tasks[0].id == sample_entry.id

    def test_list_tasks_filter_by_verification(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test filtering tasks by verification status."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)  # PASS
        writer.create_entry(sample_entry_2)  # FAIL

        reader = LedgerReader(ledger_dir)
        tasks = reader.list_tasks(verification=VerificationStatus.PASS)
        assert len(tasks) == 1
        assert tasks[0].id == sample_entry.id

    def test_get_task(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test getting full task entry."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        reader = LedgerReader(ledger_dir)
        entry = reader.get_task(sample_entry.id)
        assert entry is not None
        assert entry.id == sample_entry.id
        assert entry.title == sample_entry.title
        assert entry.spec_file == sample_entry.spec_file
        assert entry.files_changed == sample_entry.files_changed

    def test_get_task_not_found(self, ledger_dir: Path) -> None:
        """Test getting nonexistent task returns None."""
        reader = LedgerReader(ledger_dir)
        entry = reader.get_task("nonexistent")
        assert entry is None

    def test_search_tasks_by_title(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test searching tasks by title."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)  # "Implement feature X"
        writer.create_entry(sample_entry_2)  # "Fix bug in module Y"

        reader = LedgerReader(ledger_dir)
        results = reader.search_tasks("feature")
        assert len(results) == 1
        assert results[0].id == sample_entry.id

    def test_search_tasks_by_files(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test searching tasks by file names."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)  # has "feature.py"
        writer.create_entry(sample_entry_2)  # has "module_y.py"

        reader = LedgerReader(ledger_dir)
        results = reader.search_tasks("module_y")
        assert len(results) == 1
        assert results[0].id == sample_entry_2.id

    def test_search_tasks_case_insensitive(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test search is case insensitive."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        reader = LedgerReader(ledger_dir)
        results = reader.search_tasks("FEATURE")
        assert len(results) == 1

    def test_search_tasks_no_match(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test search with no matches."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        reader = LedgerReader(ledger_dir)
        results = reader.search_tasks("nonexistent")
        assert len(results) == 0

    def test_get_stats_empty(self, ledger_dir: Path) -> None:
        """Test getting stats from empty ledger."""
        reader = LedgerReader(ledger_dir)
        stats = reader.get_stats()
        assert stats.total_tasks == 0
        assert stats.total_cost_usd == 0.0

    def test_get_stats(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test getting aggregate stats."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)  # 1000 tokens, $0.05, PASS
        writer.create_entry(sample_entry_2)  # 500 tokens, $0.025, FAIL

        reader = LedgerReader(ledger_dir)
        stats = reader.get_stats()

        assert stats.total_tasks == 2
        assert stats.total_epics == 2
        assert stats.total_tokens == 1500
        assert abs(stats.total_cost_usd - 0.075) < 0.0001
        assert abs(stats.average_cost_per_task - 0.0375) < 0.0001
        assert stats.min_cost_usd == 0.025
        assert stats.max_cost_usd == 0.05
        assert stats.tasks_verified == 1  # Only PASS counts
        assert stats.tasks_failed == 1  # FAIL counts

    def test_get_stats_with_filters(
        self,
        ledger_dir: Path,
        sample_entry: LedgerEntry,
        sample_entry_2: LedgerEntry,
    ) -> None:
        """Test getting stats with filters."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)
        writer.create_entry(sample_entry_2)

        reader = LedgerReader(ledger_dir)

        # Filter by epic
        stats = reader.get_stats(epic="epic-123")
        assert stats.total_tasks == 1
        assert stats.total_cost_usd == 0.05

        # Filter by date
        stats = reader.get_stats(since="2024-01-18")
        assert stats.total_tasks == 1
        assert stats.total_cost_usd == 0.025


class TestLedgerReaderEdgeCases:
    """Test edge cases for LedgerReader."""

    def test_read_index_with_empty_lines(self, ledger_dir: Path) -> None:
        """Test reading index file with empty lines."""
        # Create index with empty lines
        (ledger_dir / "index.jsonl").write_text(
            '{"id": "task-1", "title": "Task 1", "completed": "2024-01-15", "cost_usd": 0.01, "files": [], "commit": "", "verification": "pass", "tokens": 100}\n'
            "\n"  # Empty line
            '{"id": "task-2", "title": "Task 2", "completed": "2024-01-16", "cost_usd": 0.02, "files": [], "commit": "", "verification": "pass", "tokens": 200}\n'
        )

        reader = LedgerReader(ledger_dir)
        tasks = reader.list_tasks()
        assert len(tasks) == 2

    def test_search_tasks_spec_field(self, ledger_dir: Path) -> None:
        """Test searching in spec field."""
        # Create index with spec field
        (ledger_dir / "index.jsonl").write_text(
            '{"id": "task-1", "title": "Task 1", "completed": "2024-01-15", "cost_usd": 0.01, "files": [], "commit": "", "verification": "pass", "tokens": 100, "spec": "authentication flow"}\n'
        )

        reader = LedgerReader(ledger_dir)
        results = reader.search_tasks("authentication")
        assert len(results) == 1

    def test_search_tasks_no_spec_field(self, ledger_dir: Path) -> None:
        """Test searching when spec field is None."""
        # Create index without spec field
        (ledger_dir / "index.jsonl").write_text(
            '{"id": "task-1", "title": "Task 1", "completed": "2024-01-15", "cost_usd": 0.01, "files": [], "commit": "", "verification": "pass", "tokens": 100}\n'
        )

        reader = LedgerReader(ledger_dir)
        # Search for something not in title
        results = reader.search_tasks("xyz_not_found")
        assert len(results) == 0


class TestLedgerRoundTrip:
    """Test read/write round trips."""

    def test_roundtrip_entry(
        self, ledger_dir: Path, sample_entry: LedgerEntry
    ) -> None:
        """Test writing and reading back an entry."""
        writer = LedgerWriter(ledger_dir)
        writer.create_entry(sample_entry)

        reader = LedgerReader(ledger_dir)
        entry = reader.get_task(sample_entry.id)

        assert entry is not None
        assert entry.id == sample_entry.id
        assert entry.title == sample_entry.title
        assert entry.epic_id == sample_entry.epic_id
        assert entry.spec_file == sample_entry.spec_file
        assert entry.files_changed == sample_entry.files_changed
        assert entry.tokens.total_tokens == sample_entry.tokens.total_tokens
        assert entry.cost_usd == sample_entry.cost_usd
        assert entry.harness_name == sample_entry.harness_name
