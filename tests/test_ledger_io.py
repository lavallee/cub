"""Tests for ledger reader and writer."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cub.core.ledger.models import (
    LedgerEntry,
    PlanEntry,
    RunEntry,
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

    def test_create_entry(self, ledger_dir: Path, sample_entry: LedgerEntry) -> None:
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

    def test_entry_exists(self, ledger_dir: Path, sample_entry: LedgerEntry) -> None:
        """Test checking if entry exists."""
        writer = LedgerWriter(ledger_dir)

        # Should not exist initially
        assert not writer.entry_exists(sample_entry.id)

        # Create entry
        writer.create_entry(sample_entry)

        # Should exist now
        assert writer.entry_exists(sample_entry.id)
        assert not writer.entry_exists("nonexistent-id")

    def test_update_entry(self, ledger_dir: Path, sample_entry: LedgerEntry) -> None:
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
        """Test rebuild_index with no by-task directory."""
        writer = LedgerWriter(ledger_dir)
        # Should not raise even when by_task_dir doesn't exist
        writer.rebuild_index()

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

    def test_get_task(self, ledger_dir: Path, sample_entry: LedgerEntry) -> None:
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

    def test_search_tasks_no_match(self, ledger_dir: Path, sample_entry: LedgerEntry) -> None:
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

    def test_roundtrip_entry(self, ledger_dir: Path, sample_entry: LedgerEntry) -> None:
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


class TestLedgerPromptAndLogWriting:
    """Test prompt and log file writing for attempts."""

    def test_write_prompt_file_basic(self, ledger_dir: Path) -> None:
        """Test writing a basic prompt file with frontmatter."""
        writer = LedgerWriter(ledger_dir)
        task_id = "cub-abc"
        prompt_content = "# Task: Fix login\n\nFix the login bug..."

        prompt_path = writer.write_prompt_file(
            task_id,
            1,
            prompt_content,
            harness="claude",
            model="haiku",
            run_id="cub-20260124-123456",
        )

        # Verify file was created
        expected_path = ledger_dir / "by-task" / task_id / "attempts" / "001-prompt.md"
        assert prompt_path == expected_path
        assert prompt_path.exists()

        # Verify content
        content = prompt_path.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "attempt: 1" in content
        assert "harness: claude" in content
        assert "model: haiku" in content
        assert "run_id: cub-20260124-123456" in content
        assert "started_at:" in content
        assert "# Task: Fix login" in content

    def test_write_prompt_file_multiple_attempts(self, ledger_dir: Path) -> None:
        """Test writing multiple prompt files for different attempts."""
        writer = LedgerWriter(ledger_dir)
        task_id = "cub-xyz"

        # Write first attempt
        path1 = writer.write_prompt_file(task_id, 1, "Attempt 1", harness="claude", model="haiku")
        # Write second attempt
        path2 = writer.write_prompt_file(task_id, 2, "Attempt 2", harness="claude", model="sonnet")

        # Verify both files exist
        assert path1.exists()
        assert path2.exists()
        assert path1.name == "001-prompt.md"
        assert path2.name == "002-prompt.md"

        # Verify directory structure
        attempts_dir = ledger_dir / "by-task" / task_id / "attempts"
        assert attempts_dir.exists()
        assert len(list(attempts_dir.glob("*-prompt.md"))) == 2

    def test_write_prompt_file_with_custom_started_at(self, ledger_dir: Path) -> None:
        """Test writing prompt file with custom started_at timestamp."""
        writer = LedgerWriter(ledger_dir)
        task_id = "cub-test"
        custom_time = datetime(2026, 1, 24, 12, 35, 0, tzinfo=timezone.utc)

        prompt_path = writer.write_prompt_file(
            task_id,
            1,
            "Test prompt",
            harness="claude",
            model="haiku",
            run_id="test-run",
            started_at=custom_time,
        )

        content = prompt_path.read_text(encoding="utf-8")
        assert "started_at: '2026-01-24T12:35:00+00:00'" in content

    def test_write_prompt_file_zero_padding(self, ledger_dir: Path) -> None:
        """Test that attempt numbers are zero-padded to 3 digits."""
        writer = LedgerWriter(ledger_dir)
        task_id = "cub-pad"

        # Test various attempt numbers
        path1 = writer.write_prompt_file(task_id, 1, "Attempt 1")
        path5 = writer.write_prompt_file(task_id, 5, "Attempt 5")
        path99 = writer.write_prompt_file(task_id, 99, "Attempt 99")
        path123 = writer.write_prompt_file(task_id, 123, "Attempt 123")

        assert path1.name == "001-prompt.md"
        assert path5.name == "005-prompt.md"
        assert path99.name == "099-prompt.md"
        assert path123.name == "123-prompt.md"

    def test_write_harness_log_basic(self, ledger_dir: Path) -> None:
        """Test writing a basic harness log file."""
        writer = LedgerWriter(ledger_dir)
        task_id = "cub-log"
        log_content = "Harness output...\nSome logs here\n"

        log_path = writer.write_harness_log(task_id, 1, log_content)

        # Verify file was created
        expected_path = ledger_dir / "by-task" / task_id / "attempts" / "001-harness.log"
        assert log_path == expected_path
        assert log_path.exists()

        # Verify content
        content = log_path.read_text(encoding="utf-8")
        assert content == log_content

    def test_write_harness_log_multiple_attempts(self, ledger_dir: Path) -> None:
        """Test writing multiple harness logs for different attempts."""
        writer = LedgerWriter(ledger_dir)
        task_id = "cub-multi"

        # Write logs for multiple attempts
        path1 = writer.write_harness_log(task_id, 1, "Log for attempt 1")
        path2 = writer.write_harness_log(task_id, 2, "Log for attempt 2")
        path3 = writer.write_harness_log(task_id, 3, "Log for attempt 3")

        # Verify all files exist
        assert path1.exists()
        assert path2.exists()
        assert path3.exists()
        assert path1.name == "001-harness.log"
        assert path2.name == "002-harness.log"
        assert path3.name == "003-harness.log"

        # Verify directory structure
        attempts_dir = ledger_dir / "by-task" / task_id / "attempts"
        assert attempts_dir.exists()
        assert len(list(attempts_dir.glob("*-harness.log"))) == 3

    def test_write_prompt_and_log_together(self, ledger_dir: Path) -> None:
        """Test writing both prompt and log files for the same attempt."""
        writer = LedgerWriter(ledger_dir)
        task_id = "cub-both"

        # Write both prompt and log for attempt 1
        prompt_path = writer.write_prompt_file(
            task_id,
            1,
            "# Task prompt",
            harness="claude",
            model="haiku",
            run_id="test-run",
        )
        log_path = writer.write_harness_log(task_id, 1, "Harness output")

        # Verify both exist in the same directory
        attempts_dir = ledger_dir / "by-task" / task_id / "attempts"
        assert prompt_path.parent == attempts_dir
        assert log_path.parent == attempts_dir
        assert prompt_path.exists()
        assert log_path.exists()

        # Verify both have matching attempt numbers
        assert prompt_path.name == "001-prompt.md"
        assert log_path.name == "001-harness.log"

    def test_write_files_creates_directories(self, ledger_dir: Path) -> None:
        """Test that write methods create necessary directories."""
        writer = LedgerWriter(ledger_dir)
        task_id = "cub-newdirs"

        # Verify directories don't exist yet
        task_dir = ledger_dir / "by-task" / task_id
        attempts_dir = task_dir / "attempts"
        assert not task_dir.exists()
        assert not attempts_dir.exists()

        # Write a prompt file
        writer.write_prompt_file(task_id, 1, "Test prompt")

        # Verify directories were created
        assert task_dir.exists()
        assert attempts_dir.exists()
        assert task_dir.is_dir()
        assert attempts_dir.is_dir()


class TestLedgerPlanEntries:
    """Tests for plan entry read/write operations."""

    def test_create_plan_entry(self, ledger_dir: Path) -> None:
        """Test creating a plan ledger entry."""
        writer = LedgerWriter(ledger_dir)
        plan = PlanEntry(
            plan_id="cub-054A",
            spec_id="cub-054",
            title="Ledger Consolidation Plan A",
            epics=["cub-054A-0", "cub-054A-1"],
            status="in_progress",
            total_cost=1.23,
            total_tokens=150000,
            total_tasks=10,
            completed_tasks=5,
        )

        writer.create_plan_entry(plan)

        # Verify file structure
        plan_dir = ledger_dir / "by-plan" / "cub-054A"
        entry_file = plan_dir / "entry.json"
        assert plan_dir.exists()
        assert entry_file.exists()

        # Verify content
        with open(entry_file) as f:
            data = json.load(f)
        assert data["plan_id"] == "cub-054A"
        assert data["spec_id"] == "cub-054"
        assert data["title"] == "Ledger Consolidation Plan A"
        assert data["epics"] == ["cub-054A-0", "cub-054A-1"]
        assert data["status"] == "in_progress"
        assert data["total_cost"] == 1.23
        assert data["total_tokens"] == 150000
        assert data["total_tasks"] == 10
        assert data["completed_tasks"] == 5

    def test_get_plan_entry(self, ledger_dir: Path) -> None:
        """Test getting a plan entry."""
        writer = LedgerWriter(ledger_dir)
        plan = PlanEntry(
            plan_id="cub-055B",
            spec_id="cub-055",
            title="Test Plan B",
        )

        writer.create_plan_entry(plan)
        retrieved = writer.get_plan_entry("cub-055B")

        assert retrieved is not None
        assert retrieved.plan_id == "cub-055B"
        assert retrieved.spec_id == "cub-055"
        assert retrieved.title == "Test Plan B"

    def test_get_plan_entry_not_found(self, ledger_dir: Path) -> None:
        """Test getting nonexistent plan entry returns None."""
        writer = LedgerWriter(ledger_dir)
        retrieved = writer.get_plan_entry("nonexistent")
        assert retrieved is None

    def test_update_plan_entry(self, ledger_dir: Path) -> None:
        """Test updating an existing plan entry."""
        writer = LedgerWriter(ledger_dir)
        plan = PlanEntry(
            plan_id="cub-056C",
            spec_id="cub-056",
            title="Test Plan C",
            status="in_progress",
            total_tasks=10,
            completed_tasks=3,
        )

        writer.create_plan_entry(plan)

        # Update the plan
        writer.update_plan_entry(
            "cub-056C",
            {
                "status": "completed",
                "completed_tasks": 10,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Verify update
        updated = writer.get_plan_entry("cub-056C")
        assert updated is not None
        assert updated.status == "completed"
        assert updated.completed_tasks == 10
        assert updated.completed_at is not None

    def test_update_plan_entry_not_found(self, ledger_dir: Path) -> None:
        """Test updating nonexistent plan entry raises error."""
        writer = LedgerWriter(ledger_dir)

        with pytest.raises(FileNotFoundError, match="Plan entry .* not found"):
            writer.update_plan_entry("nonexistent", {"status": "completed"})

    def test_update_plan_entry_atomic_write(self, ledger_dir: Path) -> None:
        """Test that plan update uses atomic write pattern."""
        writer = LedgerWriter(ledger_dir)
        plan = PlanEntry(
            plan_id="cub-057D",
            spec_id="cub-057",
            title="Atomic Test Plan",
        )

        writer.create_plan_entry(plan)
        entry_file = ledger_dir / "by-plan" / "cub-057D" / "entry.json"
        temp_file = entry_file.with_suffix(".tmp")

        # Update should not leave temp file behind
        writer.update_plan_entry("cub-057D", {"total_tasks": 5})
        assert not temp_file.exists()
        assert entry_file.exists()


class TestLedgerRunEntries:
    """Tests for run entry read/write operations."""

    def test_create_run_entry(self, ledger_dir: Path) -> None:
        """Test creating a run session ledger entry."""
        writer = LedgerWriter(ledger_dir)
        run = RunEntry(
            run_id="cub-20260204-161800",
            status="running",
            config={"harness": "claude", "model": "sonnet"},
            tasks_attempted=["cub-054A-1.1", "cub-054A-1.2"],
            tasks_completed=["cub-054A-1.1"],
            total_cost=0.15,
            total_tokens=25000,
            iterations=1,
        )

        writer.create_run_entry(run)

        # Verify file structure
        entry_file = ledger_dir / "by-run" / "cub-20260204-161800.json"
        assert entry_file.exists()

        # Verify content
        with open(entry_file) as f:
            data = json.load(f)
        assert data["run_id"] == "cub-20260204-161800"
        assert data["status"] == "running"
        assert data["config"] == {"harness": "claude", "model": "sonnet"}
        assert data["tasks_attempted"] == ["cub-054A-1.1", "cub-054A-1.2"]
        assert data["tasks_completed"] == ["cub-054A-1.1"]
        assert data["total_cost"] == 0.15
        assert data["total_tokens"] == 25000
        assert data["iterations"] == 1

    def test_get_run_entry(self, ledger_dir: Path) -> None:
        """Test getting a run entry."""
        writer = LedgerWriter(ledger_dir)
        run = RunEntry(
            run_id="cub-20260204-120000",
            status="completed",
        )

        writer.create_run_entry(run)
        retrieved = writer.get_run_entry("cub-20260204-120000")

        assert retrieved is not None
        assert retrieved.run_id == "cub-20260204-120000"
        assert retrieved.status == "completed"

    def test_get_run_entry_not_found(self, ledger_dir: Path) -> None:
        """Test getting nonexistent run entry returns None."""
        writer = LedgerWriter(ledger_dir)
        retrieved = writer.get_run_entry("nonexistent")
        assert retrieved is None

    def test_update_run_entry(self, ledger_dir: Path) -> None:
        """Test updating an existing run entry."""
        writer = LedgerWriter(ledger_dir)
        run = RunEntry(
            run_id="cub-20260204-130000",
            status="running",
            tasks_attempted=["task-1"],
            tasks_completed=[],
        )

        writer.create_run_entry(run)

        # Update the run
        writer.update_run_entry(
            "cub-20260204-130000",
            {
                "status": "completed",
                "tasks_completed": ["task-1"],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Verify update
        updated = writer.get_run_entry("cub-20260204-130000")
        assert updated is not None
        assert updated.status == "completed"
        assert updated.tasks_completed == ["task-1"]
        assert updated.completed_at is not None

    def test_update_run_entry_not_found(self, ledger_dir: Path) -> None:
        """Test updating nonexistent run entry raises error."""
        writer = LedgerWriter(ledger_dir)

        with pytest.raises(FileNotFoundError, match="Run entry .* not found"):
            writer.update_run_entry("nonexistent", {"status": "completed"})

    def test_update_run_entry_atomic_write(self, ledger_dir: Path) -> None:
        """Test that run update uses atomic write pattern."""
        writer = LedgerWriter(ledger_dir)
        run = RunEntry(
            run_id="cub-20260204-140000",
            status="running",
        )

        writer.create_run_entry(run)
        entry_file = ledger_dir / "by-run" / "cub-20260204-140000.json"
        temp_file = entry_file.with_suffix(".tmp")

        # Update should not leave temp file behind
        writer.update_run_entry("cub-20260204-140000", {"status": "completed"})
        assert not temp_file.exists()
        assert entry_file.exists()

    def test_create_run_entry_creates_directory(self, ledger_dir: Path) -> None:
        """Test that creating run entry creates by-run directory."""
        writer = LedgerWriter(ledger_dir)
        run_dir = ledger_dir / "by-run"

        # Verify directory doesn't exist yet
        assert not run_dir.exists()

        # Create run entry
        run = RunEntry(run_id="cub-20260204-150000", status="running")
        writer.create_run_entry(run)

        # Verify directory was created
        assert run_dir.exists()
        assert run_dir.is_dir()


class TestLedgerReaderPlanQueries:
    """Tests for LedgerReader plan query methods."""

    def test_get_plan(self, ledger_dir: Path) -> None:
        """Test getting a plan entry."""
        writer = LedgerWriter(ledger_dir)
        plan = PlanEntry(
            plan_id="cub-054A",
            spec_id="cub-054",
            title="Ledger Consolidation",
            epics=["cub-054A-0", "cub-054A-1"],
            status="in_progress",
            total_cost=1.23,
            total_tokens=150000,
            total_tasks=10,
            completed_tasks=5,
        )

        writer.create_plan_entry(plan)

        reader = LedgerReader(ledger_dir)
        retrieved = reader.get_plan("cub-054A")

        assert retrieved is not None
        assert retrieved.plan_id == "cub-054A"
        assert retrieved.spec_id == "cub-054"
        assert retrieved.title == "Ledger Consolidation"
        assert retrieved.epics == ["cub-054A-0", "cub-054A-1"]
        assert retrieved.status == "in_progress"
        assert retrieved.total_cost == 1.23

    def test_get_plan_not_found(self, ledger_dir: Path) -> None:
        """Test getting nonexistent plan returns None."""
        reader = LedgerReader(ledger_dir)
        retrieved = reader.get_plan("nonexistent")
        assert retrieved is None

    def test_list_plans_empty(self, ledger_dir: Path) -> None:
        """Test listing plans from empty ledger."""
        reader = LedgerReader(ledger_dir)
        plans = reader.list_plans()
        assert plans == []

    def test_list_plans(self, ledger_dir: Path) -> None:
        """Test listing all plans."""
        writer = LedgerWriter(ledger_dir)

        plan1 = PlanEntry(
            plan_id="cub-054A",
            spec_id="cub-054",
            title="Plan A",
            status="in_progress",
        )
        plan2 = PlanEntry(
            plan_id="cub-055B",
            spec_id="cub-055",
            title="Plan B",
            status="completed",
        )

        writer.create_plan_entry(plan1)
        writer.create_plan_entry(plan2)

        reader = LedgerReader(ledger_dir)
        plans = reader.list_plans()

        assert len(plans) == 2
        plan_ids = {p.plan_id for p in plans}
        assert plan_ids == {"cub-054A", "cub-055B"}

    def test_list_plans_filter_by_status(self, ledger_dir: Path) -> None:
        """Test filtering plans by status."""
        from cub.core.ledger.models import PlanFilters

        writer = LedgerWriter(ledger_dir)

        plan1 = PlanEntry(
            plan_id="cub-054A",
            spec_id="cub-054",
            title="Plan A",
            status="in_progress",
        )
        plan2 = PlanEntry(
            plan_id="cub-055B",
            spec_id="cub-055",
            title="Plan B",
            status="completed",
        )

        writer.create_plan_entry(plan1)
        writer.create_plan_entry(plan2)

        reader = LedgerReader(ledger_dir)
        filters = PlanFilters(status="completed")
        plans = reader.list_plans(filters)

        assert len(plans) == 1
        assert plans[0].plan_id == "cub-055B"

    def test_list_plans_filter_by_spec_id(self, ledger_dir: Path) -> None:
        """Test filtering plans by spec_id."""
        from cub.core.ledger.models import PlanFilters

        writer = LedgerWriter(ledger_dir)

        plan1 = PlanEntry(
            plan_id="cub-054A",
            spec_id="cub-054",
            title="Plan A",
        )
        plan2 = PlanEntry(
            plan_id="cub-054B",
            spec_id="cub-054",
            title="Plan B",
        )
        plan3 = PlanEntry(
            plan_id="cub-055A",
            spec_id="cub-055",
            title="Plan C",
        )

        writer.create_plan_entry(plan1)
        writer.create_plan_entry(plan2)
        writer.create_plan_entry(plan3)

        reader = LedgerReader(ledger_dir)
        filters = PlanFilters(spec_id="cub-054")
        plans = reader.list_plans(filters)

        assert len(plans) == 2
        plan_ids = {p.plan_id for p in plans}
        assert plan_ids == {"cub-054A", "cub-054B"}

    def test_list_plans_filter_by_date_range(self, ledger_dir: Path) -> None:
        """Test filtering plans by date range."""
        from cub.core.ledger.models import PlanFilters

        writer = LedgerWriter(ledger_dir)

        plan1 = PlanEntry(
            plan_id="cub-054A",
            spec_id="cub-054",
            title="Plan A",
            started_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )
        plan2 = PlanEntry(
            plan_id="cub-055B",
            spec_id="cub-055",
            title="Plan B",
            started_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        writer.create_plan_entry(plan1)
        writer.create_plan_entry(plan2)

        reader = LedgerReader(ledger_dir)

        # Test since filter
        filters = PlanFilters(since="2026-01-20")
        plans = reader.list_plans(filters)
        assert len(plans) == 1
        assert plans[0].plan_id == "cub-055B"

        # Test until filter
        filters = PlanFilters(until="2026-01-20")
        plans = reader.list_plans(filters)
        assert len(plans) == 1
        assert plans[0].plan_id == "cub-054A"


class TestLedgerReaderRunQueries:
    """Tests for LedgerReader run query methods."""

    def test_get_run(self, ledger_dir: Path) -> None:
        """Test getting a run entry."""
        writer = LedgerWriter(ledger_dir)
        run = RunEntry(
            run_id="cub-20260204-161800",
            status="running",
            config={"harness": "claude", "model": "sonnet"},
            tasks_attempted=["task-1", "task-2"],
            tasks_completed=["task-1"],
            total_cost=0.15,
            total_tokens=25000,
        )

        writer.create_run_entry(run)

        reader = LedgerReader(ledger_dir)
        retrieved = reader.get_run("cub-20260204-161800")

        assert retrieved is not None
        assert retrieved.run_id == "cub-20260204-161800"
        assert retrieved.status == "running"
        assert retrieved.total_cost == 0.15
        assert retrieved.total_tokens == 25000

    def test_get_run_not_found(self, ledger_dir: Path) -> None:
        """Test getting nonexistent run returns None."""
        reader = LedgerReader(ledger_dir)
        retrieved = reader.get_run("nonexistent")
        assert retrieved is None

    def test_list_runs_empty(self, ledger_dir: Path) -> None:
        """Test listing runs from empty ledger."""
        reader = LedgerReader(ledger_dir)
        runs = reader.list_runs()
        assert runs == []

    def test_list_runs(self, ledger_dir: Path) -> None:
        """Test listing all runs."""
        writer = LedgerWriter(ledger_dir)

        run1 = RunEntry(
            run_id="cub-20260204-120000",
            status="completed",
        )
        run2 = RunEntry(
            run_id="cub-20260204-130000",
            status="running",
        )

        writer.create_run_entry(run1)
        writer.create_run_entry(run2)

        reader = LedgerReader(ledger_dir)
        runs = reader.list_runs()

        assert len(runs) == 2
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"cub-20260204-120000", "cub-20260204-130000"}

    def test_list_runs_filter_by_status(self, ledger_dir: Path) -> None:
        """Test filtering runs by status."""
        from cub.core.ledger.models import RunFilters

        writer = LedgerWriter(ledger_dir)

        run1 = RunEntry(
            run_id="cub-20260204-120000",
            status="completed",
        )
        run2 = RunEntry(
            run_id="cub-20260204-130000",
            status="running",
        )
        run3 = RunEntry(
            run_id="cub-20260204-140000",
            status="failed",
        )

        writer.create_run_entry(run1)
        writer.create_run_entry(run2)
        writer.create_run_entry(run3)

        reader = LedgerReader(ledger_dir)
        filters = RunFilters(status="completed")
        runs = reader.list_runs(filters)

        assert len(runs) == 1
        assert runs[0].run_id == "cub-20260204-120000"

    def test_list_runs_filter_by_date_range(self, ledger_dir: Path) -> None:
        """Test filtering runs by date range."""
        from cub.core.ledger.models import RunFilters

        writer = LedgerWriter(ledger_dir)

        run1 = RunEntry(
            run_id="cub-20260115-120000",
            status="completed",
            started_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )
        run2 = RunEntry(
            run_id="cub-20260201-120000",
            status="completed",
            started_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        writer.create_run_entry(run1)
        writer.create_run_entry(run2)

        reader = LedgerReader(ledger_dir)

        # Test since filter
        filters = RunFilters(since="2026-01-20")
        runs = reader.list_runs(filters)
        assert len(runs) == 1
        assert runs[0].run_id == "cub-20260201-120000"

        # Test until filter
        filters = RunFilters(until="2026-01-20")
        runs = reader.list_runs(filters)
        assert len(runs) == 1
        assert runs[0].run_id == "cub-20260115-120000"

    def test_list_runs_filter_by_cost(self, ledger_dir: Path) -> None:
        """Test filtering runs by cost range."""
        from cub.core.ledger.models import RunFilters

        writer = LedgerWriter(ledger_dir)

        run1 = RunEntry(
            run_id="cub-20260204-120000",
            status="completed",
            total_cost=0.10,
        )
        run2 = RunEntry(
            run_id="cub-20260204-130000",
            status="completed",
            total_cost=0.50,
        )
        run3 = RunEntry(
            run_id="cub-20260204-140000",
            status="completed",
            total_cost=1.00,
        )

        writer.create_run_entry(run1)
        writer.create_run_entry(run2)
        writer.create_run_entry(run3)

        reader = LedgerReader(ledger_dir)

        # Test min_cost filter
        filters = RunFilters(min_cost=0.40)
        runs = reader.list_runs(filters)
        assert len(runs) == 2
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"cub-20260204-130000", "cub-20260204-140000"}

        # Test max_cost filter
        filters = RunFilters(max_cost=0.60)
        runs = reader.list_runs(filters)
        assert len(runs) == 2
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"cub-20260204-120000", "cub-20260204-130000"}

        # Test both min and max
        filters = RunFilters(min_cost=0.20, max_cost=0.80)
        runs = reader.list_runs(filters)
        assert len(runs) == 1
        assert runs[0].run_id == "cub-20260204-130000"
