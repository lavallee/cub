"""
Tests for ledger models.

Comprehensive tests for Pydantic models in cub.core.ledger, including
validation, serialization, deserialization, computed properties, and
edge cases.
"""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cub.core.ledger import (
    CommitRef,
    EpicSummary,
    LedgerEntry,
    LedgerIndex,
    LedgerStats,
    TokenUsage,
    VerificationStatus,
)


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Test all expected status values exist."""
        assert VerificationStatus.PASS
        assert VerificationStatus.FAIL
        assert VerificationStatus.WARN
        assert VerificationStatus.SKIP
        assert VerificationStatus.PENDING
        assert VerificationStatus.ERROR

    def test_is_successful(self) -> None:
        """Test is_successful property."""
        assert VerificationStatus.PASS.is_successful
        assert VerificationStatus.SKIP.is_successful
        assert not VerificationStatus.FAIL.is_successful
        assert not VerificationStatus.ERROR.is_successful
        assert not VerificationStatus.WARN.is_successful
        assert not VerificationStatus.PENDING.is_successful

    def test_requires_attention(self) -> None:
        """Test requires_attention property."""
        assert VerificationStatus.FAIL.requires_attention
        assert VerificationStatus.ERROR.requires_attention
        assert not VerificationStatus.PASS.requires_attention
        assert not VerificationStatus.SKIP.requires_attention
        assert not VerificationStatus.WARN.requires_attention
        assert not VerificationStatus.PENDING.requires_attention


class TestTokenUsage:
    """Tests for TokenUsage model."""

    def test_create_with_defaults(self) -> None:
        """Test creating TokenUsage with default values."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_creation_tokens == 0
        assert usage.total_tokens == 0

    def test_create_with_values(self) -> None:
        """Test creating TokenUsage with specific values."""
        usage = TokenUsage(
            input_tokens=1000, output_tokens=500, cache_read_tokens=200, cache_creation_tokens=100
        )
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.cache_read_tokens == 200
        assert usage.cache_creation_tokens == 100

    def test_total_tokens_calculation(self) -> None:
        """Test total_tokens computed property."""
        usage = TokenUsage(
            input_tokens=1000, output_tokens=500, cache_read_tokens=200, cache_creation_tokens=100
        )
        assert usage.total_tokens == 1800

    def test_negative_tokens_rejected(self) -> None:
        """Test that negative token values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TokenUsage(input_tokens=-100)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_serialization(self) -> None:
        """Test JSON serialization."""
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        data = usage.model_dump()
        assert data["input_tokens"] == 1000
        assert data["output_tokens"] == 500
        assert data["cache_read_tokens"] == 0
        assert data["cache_creation_tokens"] == 0

    def test_deserialization(self) -> None:
        """Test JSON deserialization."""
        data = {"input_tokens": 1000, "output_tokens": 500}
        usage = TokenUsage.model_validate(data)
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500


class TestCommitRef:
    """Tests for CommitRef model."""

    def test_create_minimal(self) -> None:
        """Test creating CommitRef with minimal required fields."""
        ref = CommitRef(hash="abc123f")
        assert ref.hash == "abc123f"
        assert ref.message == ""
        assert ref.author == ""
        assert isinstance(ref.timestamp, datetime)

    def test_create_full(self) -> None:
        """Test creating CommitRef with all fields."""
        ts = datetime(2026, 1, 18, 10, 45, tzinfo=timezone.utc)
        ref = CommitRef(
            hash="abc123f456def", message="feat: add auth", author="John Doe", timestamp=ts
        )
        assert ref.hash == "abc123f456def"
        assert ref.message == "feat: add auth"
        assert ref.author == "John Doe"
        assert ref.timestamp == ts

    def test_short_hash_property(self) -> None:
        """Test short_hash property returns first 7 chars."""
        ref = CommitRef(hash="abc123f456def789")
        assert ref.short_hash == "abc123f"

    def test_short_hash_with_short_input(self) -> None:
        """Test short_hash with hash already 7 chars."""
        ref = CommitRef(hash="abc123f")
        assert ref.short_hash == "abc123f"

    def test_hash_normalized_to_lowercase(self) -> None:
        """Test that hash is normalized to lowercase."""
        ref = CommitRef(hash="ABC123F")
        assert ref.hash == "abc123f"

    def test_invalid_hash_chars_rejected(self) -> None:
        """Test that non-hex characters in hash are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CommitRef(hash="xyz1234")  # 7 chars to pass length validation
        assert "hexadecimal" in str(exc_info.value).lower()

    def test_hash_too_short_rejected(self) -> None:
        """Test that hash shorter than 7 chars is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CommitRef(hash="abc12")
        assert "at least 7 characters" in str(exc_info.value)

    def test_hash_too_long_rejected(self) -> None:
        """Test that hash longer than 40 chars is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CommitRef(hash="a" * 41)
        assert "at most 40 characters" in str(exc_info.value)

    def test_serialization(self) -> None:
        """Test JSON serialization."""
        ts = datetime(2026, 1, 18, 10, 45, tzinfo=timezone.utc)
        ref = CommitRef(hash="abc123f", message="feat: add", author="John", timestamp=ts)
        data = ref.model_dump()
        assert data["hash"] == "abc123f"
        assert data["message"] == "feat: add"

    def test_deserialization(self) -> None:
        """Test JSON deserialization."""
        data = {
            "hash": "abc123f",
            "message": "feat: add",
            "author": "John",
            "timestamp": "2026-01-18T10:45:00Z",
        }
        ref = CommitRef.model_validate(data)
        assert ref.hash == "abc123f"
        assert ref.message == "feat: add"


class TestLedgerEntry:
    """Tests for LedgerEntry model."""

    def test_create_minimal(self) -> None:
        """Test creating LedgerEntry with minimal required fields."""
        entry = LedgerEntry(id="beads-abc", title="Test task")
        assert entry.id == "beads-abc"
        assert entry.title == "Test task"
        assert isinstance(entry.completed_at, datetime)
        assert entry.tokens.total_tokens == 0
        assert entry.cost_usd == 0.0
        assert entry.duration_seconds == 0
        assert entry.iterations == 1

    def test_create_full(self) -> None:
        """Test creating LedgerEntry with all fields populated."""
        started = datetime(2026, 1, 18, 10, 0, tzinfo=timezone.utc)
        completed = datetime(2026, 1, 18, 10, 45, tzinfo=timezone.utc)

        entry = LedgerEntry(
            id="beads-abc123",
            title="Implement user authentication",
            started_at=started,
            completed_at=completed,
            tokens=TokenUsage(input_tokens=45000, output_tokens=12000),
            cost_usd=0.09,
            duration_seconds=2700,
            iterations=3,
            approach="Used JWT with bcrypt",
            decisions=["JWT over session cookies", "24h token expiry"],
            lessons_learned=["bcrypt.compare is async"],
            files_changed=["src/auth/middleware.ts", "src/auth/jwt.ts"],
            commits=[CommitRef(hash="abc123f", message="feat: implement auth")],
            spec_file="specs/planned/auth.md",
            run_log_path=".cub/ledger/by-run/session-123/tasks/beads-abc",
            epic_id="auth-epic",
            verification_status=VerificationStatus.PASS,
            verification_notes=["Tests pass", "Build succeeds"],
            harness_name="claude",
            harness_model="sonnet",
        )

        assert entry.id == "beads-abc123"
        assert entry.title == "Implement user authentication"
        assert entry.started_at == started
        assert entry.completed_at == completed
        assert entry.tokens.input_tokens == 45000
        assert entry.cost_usd == 0.09
        assert entry.duration_seconds == 2700
        assert entry.iterations == 3
        assert entry.approach == "Used JWT with bcrypt"
        assert len(entry.decisions) == 2
        assert len(entry.lessons_learned) == 1
        assert len(entry.files_changed) == 2
        assert len(entry.commits) == 1
        assert entry.spec_file == "specs/planned/auth.md"
        assert entry.epic_id == "auth-epic"
        assert entry.verification_status == VerificationStatus.PASS
        assert entry.harness_name == "claude"

    def test_duration_minutes_property(self) -> None:
        """Test duration_minutes computed property."""
        entry = LedgerEntry(id="test", title="Test", duration_seconds=2700)
        assert entry.duration_minutes == 45.0

    def test_primary_commit_property_with_commits(self) -> None:
        """Test primary_commit returns first commit."""
        commits = [
            CommitRef(hash="abc123f", message="first"),
            CommitRef(hash="def456a", message="second"),
        ]
        entry = LedgerEntry(id="test", title="Test", commits=commits)
        assert entry.primary_commit == commits[0]
        assert entry.primary_commit.hash == "abc123f"

    def test_primary_commit_property_no_commits(self) -> None:
        """Test primary_commit returns None when no commits."""
        entry = LedgerEntry(id="test", title="Test")
        assert entry.primary_commit is None

    def test_cost_per_token_property(self) -> None:
        """Test cost_per_token computed property."""
        entry = LedgerEntry(
            id="test",
            title="Test",
            cost_usd=0.09,
            tokens=TokenUsage(input_tokens=45000, output_tokens=12000),
        )
        # 0.09 / 57000 ≈ 0.00000157894...
        assert entry.cost_per_token == pytest.approx(0.09 / 57000, rel=1e-9)

    def test_cost_per_token_zero_tokens(self) -> None:
        """Test cost_per_token returns 0 when no tokens."""
        entry = LedgerEntry(id="test", title="Test", cost_usd=0.09)
        assert entry.cost_per_token == 0.0

    def test_empty_title_rejected(self) -> None:
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LedgerEntry(id="test", title="")
        assert "at least 1 character" in str(exc_info.value)

    def test_negative_cost_rejected(self) -> None:
        """Test that negative cost is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LedgerEntry(id="test", title="Test", cost_usd=-1.0)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_negative_duration_rejected(self) -> None:
        """Test that negative duration is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LedgerEntry(id="test", title="Test", duration_seconds=-100)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_zero_iterations_rejected(self) -> None:
        """Test that zero iterations is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LedgerEntry(id="test", title="Test", iterations=0)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_serialization_roundtrip(self) -> None:
        """Test serialization and deserialization roundtrip."""
        original = LedgerEntry(
            id="beads-abc",
            title="Test task",
            cost_usd=0.05,
            tokens=TokenUsage(input_tokens=1000, output_tokens=500),
            files_changed=["file1.py", "file2.py"],
            commits=[CommitRef(hash="abc123f", message="test commit")],
        )

        # Serialize
        data = json.loads(original.model_dump_json())

        # Deserialize
        restored = LedgerEntry.model_validate(data)

        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.cost_usd == original.cost_usd
        assert restored.tokens.input_tokens == original.tokens.input_tokens
        assert restored.files_changed == original.files_changed
        assert len(restored.commits) == len(original.commits)


class TestLedgerIndex:
    """Tests for LedgerIndex model."""

    def test_create_minimal(self) -> None:
        """Test creating LedgerIndex with minimal fields."""
        index = LedgerIndex(id="beads-abc", title="Test task", completed="2026-01-18")
        assert index.id == "beads-abc"
        assert index.title == "Test task"
        assert index.completed == "2026-01-18"
        assert index.cost_usd == 0.0
        assert index.files == []
        assert index.commit == ""
        assert index.spec is None
        assert index.epic is None
        assert index.verification == "pending"
        assert index.tokens == 0

    def test_create_full(self) -> None:
        """Test creating LedgerIndex with all fields."""
        index = LedgerIndex(
            id="beads-abc",
            title="Implement auth",
            completed="2026-01-18",
            cost_usd=0.09,
            files=["src/auth/"],
            commit="abc123f",
            spec="specs/planned/auth.md",
            epic="auth-epic",
            verification="pass",
            tokens=57000,
        )
        assert index.id == "beads-abc"
        assert index.title == "Implement auth"
        assert index.cost_usd == 0.09
        assert index.files == ["src/auth/"]
        assert index.commit == "abc123f"
        assert index.spec == "specs/planned/auth.md"
        assert index.epic == "auth-epic"
        assert index.verification == "pass"
        assert index.tokens == 57000

    def test_invalid_date_format_rejected(self) -> None:
        """Test that invalid date format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LedgerIndex(id="test", title="Test", completed="01/18/2026")
        assert "YYYY-MM-DD" in str(exc_info.value)

    def test_valid_date_formats(self) -> None:
        """Test that valid date format is accepted."""
        index = LedgerIndex(id="test", title="Test", completed="2026-01-18")
        assert index.completed == "2026-01-18"

    def test_from_ledger_entry(self) -> None:
        """Test creating index from full ledger entry."""
        entry = LedgerEntry(
            id="beads-abc",
            title="Implement auth",
            completed_at=datetime(2026, 1, 18, 10, 45, tzinfo=timezone.utc),
            cost_usd=0.09,
            tokens=TokenUsage(input_tokens=45000, output_tokens=12000),
            files_changed=["src/auth/middleware.ts", "src/auth/jwt.ts"],
            commits=[CommitRef(hash="abc123f456", message="feat: auth")],
            spec_file="specs/planned/auth.md",
            epic_id="auth-epic",
            verification_status=VerificationStatus.PASS,
        )

        index = LedgerIndex.from_ledger_entry(entry)

        assert index.id == "beads-abc"
        assert index.title == "Implement auth"
        assert index.completed == "2026-01-18"
        assert index.cost_usd == 0.09
        assert index.files == ["src/auth/middleware.ts", "src/auth/jwt.ts"]
        assert index.commit == "abc123f"  # short hash
        assert index.spec == "specs/planned/auth.md"
        assert index.epic == "auth-epic"
        assert index.verification == "pass"
        assert index.tokens == 57000

    def test_from_ledger_entry_no_commits(self) -> None:
        """Test creating index from entry with no commits."""
        entry = LedgerEntry(id="test", title="Test")
        index = LedgerIndex.from_ledger_entry(entry)
        assert index.commit == ""

    def test_serialization_for_jsonl(self) -> None:
        """Test serialization produces compact JSONL-friendly output."""
        index = LedgerIndex(
            id="beads-abc",
            title="Test",
            completed="2026-01-18",
            cost_usd=0.05,
            files=["file1.py"],
            commit="abc123f",
        )
        json_str = index.model_dump_json()
        data = json.loads(json_str)

        # Verify all expected keys present
        assert "id" in data
        assert "title" in data
        assert "completed" in data
        assert "cost_usd" in data
        assert "files" in data
        assert "commit" in data


class TestEpicSummary:
    """Tests for EpicSummary model."""

    def test_create_minimal(self) -> None:
        """Test creating EpicSummary with minimal fields."""
        summary = EpicSummary(epic_id="epic-001", title="Auth System")
        assert summary.epic_id == "epic-001"
        assert summary.title == "Auth System"
        assert summary.status == "in_progress"
        assert summary.task_ids == []
        assert summary.tasks_total == 0
        assert summary.tasks_completed == 0
        assert summary.total_cost_usd == 0.0

    def test_create_full(self) -> None:
        """Test creating EpicSummary with all fields."""
        started = datetime(2026, 1, 18, 8, 0, tzinfo=timezone.utc)
        completed = datetime(2026, 1, 18, 12, 0, tzinfo=timezone.utc)

        summary = EpicSummary(
            epic_id="epic-001",
            title="Auth System",
            status="completed",
            task_ids=["beads-abc", "beads-def"],
            tasks_total=2,
            tasks_completed=2,
            total_cost_usd=0.21,
            total_duration_seconds=14400,
            total_tokens=100000,
            started_at=started,
            completed_at=completed,
            first_commit="abc123f",
            last_commit="def456a",
            spec_file="specs/planned/auth.md",
            drift_notes=["Token expiry changed from 1h to 24h"],
        )

        assert summary.epic_id == "epic-001"
        assert summary.status == "completed"
        assert len(summary.task_ids) == 2
        assert summary.tasks_total == 2
        assert summary.tasks_completed == 2
        assert summary.total_cost_usd == 0.21
        assert summary.total_tokens == 100000
        assert len(summary.drift_notes) == 1

    def test_completion_percentage(self) -> None:
        """Test completion_percentage computed property."""
        summary = EpicSummary(epic_id="test", title="Test", tasks_total=5, tasks_completed=3)
        assert summary.completion_percentage == 60.0

    def test_completion_percentage_zero_total(self) -> None:
        """Test completion_percentage returns 0 when no tasks."""
        summary = EpicSummary(epic_id="test", title="Test")
        assert summary.completion_percentage == 0.0

    def test_average_cost_per_task(self) -> None:
        """Test average_cost_per_task computed property."""
        summary = EpicSummary(epic_id="test", title="Test", tasks_completed=4, total_cost_usd=0.40)
        assert summary.average_cost_per_task == 0.10

    def test_average_cost_per_task_zero_completed(self) -> None:
        """Test average_cost_per_task returns 0 when no completed tasks."""
        summary = EpicSummary(epic_id="test", title="Test", total_cost_usd=0.40)
        assert summary.average_cost_per_task == 0.0

    def test_is_complete_true(self) -> None:
        """Test is_complete property when epic is done."""
        summary = EpicSummary(epic_id="test", title="Test", tasks_total=5, tasks_completed=5)
        assert summary.is_complete is True

    def test_is_complete_false_partial(self) -> None:
        """Test is_complete property when epic is partial."""
        summary = EpicSummary(epic_id="test", title="Test", tasks_total=5, tasks_completed=3)
        assert summary.is_complete is False

    def test_is_complete_false_no_tasks(self) -> None:
        """Test is_complete property when no tasks."""
        summary = EpicSummary(epic_id="test", title="Test")
        assert summary.is_complete is False

    def test_serialization_roundtrip(self) -> None:
        """Test serialization and deserialization roundtrip."""
        original = EpicSummary(
            epic_id="epic-001",
            title="Auth System",
            task_ids=["beads-abc", "beads-def"],
            tasks_total=2,
            tasks_completed=2,
            total_cost_usd=0.21,
        )

        data = json.loads(original.model_dump_json())
        restored = EpicSummary.model_validate(data)

        assert restored.epic_id == original.epic_id
        assert restored.title == original.title
        assert restored.task_ids == original.task_ids
        assert restored.tasks_total == original.tasks_total
        assert restored.total_cost_usd == original.total_cost_usd


class TestLedgerStats:
    """Tests for LedgerStats model."""

    def test_create_with_defaults(self) -> None:
        """Test creating LedgerStats with default values."""
        stats = LedgerStats()
        assert stats.total_tasks == 0
        assert stats.total_epics == 0
        assert stats.total_cost_usd == 0.0
        assert stats.total_tokens == 0
        assert stats.verification_rate == 0.0

    def test_create_with_values(self) -> None:
        """Test creating LedgerStats with specific values."""
        stats = LedgerStats(
            total_tasks=50,
            total_epics=5,
            total_cost_usd=5.23,
            average_cost_per_task=0.10,
            min_cost_usd=0.02,
            max_cost_usd=0.45,
            total_tokens=523000,
            average_tokens_per_task=10460,
            total_duration_seconds=18000,
            average_duration_seconds=360,
            tasks_verified=45,
            tasks_failed=3,
            verification_rate=0.9,
            total_files_changed=250,
            unique_files_changed=120,
        )

        assert stats.total_tasks == 50
        assert stats.total_cost_usd == 5.23
        assert stats.average_cost_per_task == 0.10
        assert stats.total_tokens == 523000
        assert stats.tasks_verified == 45
        assert stats.tasks_failed == 3
        assert stats.verification_rate == 0.9

    def test_total_duration_hours_property(self) -> None:
        """Test total_duration_hours computed property."""
        stats = LedgerStats(total_duration_seconds=7200)  # 2 hours
        assert stats.total_duration_hours == 2.0

    def test_average_duration_minutes_property(self) -> None:
        """Test average_duration_minutes computed property."""
        stats = LedgerStats(average_duration_seconds=300)  # 5 minutes
        assert stats.average_duration_minutes == 5.0

    def test_negative_values_rejected(self) -> None:
        """Test that negative values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LedgerStats(total_tasks=-1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_verification_rate_out_of_range_rejected(self) -> None:
        """Test that verification_rate outside 0-1 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LedgerStats(verification_rate=1.5)
        assert "less than or equal to 1" in str(exc_info.value)

    def test_serialization(self) -> None:
        """Test JSON serialization."""
        stats = LedgerStats(total_tasks=10, total_cost_usd=1.0, total_tokens=10000)
        data = stats.model_dump()
        assert data["total_tasks"] == 10
        assert data["total_cost_usd"] == 1.0
        assert data["total_tokens"] == 10000

    def test_deserialization(self) -> None:
        """Test JSON deserialization."""
        data = {"total_tasks": 10, "total_cost_usd": 1.0, "total_tokens": 10000}
        stats = LedgerStats.model_validate(data)
        assert stats.total_tasks == 10
        assert stats.total_cost_usd == 1.0
        assert stats.total_tokens == 10000
