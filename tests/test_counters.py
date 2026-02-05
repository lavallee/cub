"""
Tests for counter management on the sync branch.

Tests cover:
- CounterState model
- Reading counters from sync branch
- Allocating spec numbers
- Allocating standalone numbers
- Handling missing counters.json
- Retry logic for concurrent allocation
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from cub.core.ids.counters import (
    COUNTERS_FILE,
    CounterAllocationError,
    allocate_spec_number,
    allocate_standalone_number,
    read_counters,
)
from cub.core.sync import CounterState, SyncService


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)

    # Configure git user (required for commits)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    return repo


@pytest.fixture
def git_repo_with_commit(git_repo: Path) -> Path:
    """Create a git repo with an initial commit."""
    # Create a file and commit
    (git_repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    return git_repo


@pytest.fixture
def initialized_sync(git_repo_with_commit: Path) -> SyncService:
    """Create an initialized SyncService."""
    sync = SyncService(project_dir=git_repo_with_commit)
    sync.initialize()
    return sync


class TestCounterStateModel:
    """Tests for the CounterState Pydantic model."""

    def test_default_values(self) -> None:
        """CounterState has sensible defaults."""
        state = CounterState()

        assert state.spec_number == 0
        assert state.standalone_task_number == 0
        assert state.updated_at is not None

    def test_custom_values(self) -> None:
        """CounterState accepts custom values."""
        now = datetime.now(timezone.utc)
        state = CounterState(
            spec_number=54,
            standalone_task_number=17,
            updated_at=now,
        )

        assert state.spec_number == 54
        assert state.standalone_task_number == 17
        assert state.updated_at == now

    def test_increment_spec_number(self) -> None:
        """increment_spec_number returns current and increments."""
        state = CounterState(spec_number=10)
        old_updated_at = state.updated_at

        allocated = state.increment_spec_number()

        assert allocated == 10
        assert state.spec_number == 11
        assert state.updated_at >= old_updated_at

    def test_increment_standalone_number(self) -> None:
        """increment_standalone_number returns current and increments."""
        state = CounterState(standalone_task_number=5)
        old_updated_at = state.updated_at

        allocated = state.increment_standalone_number()

        assert allocated == 5
        assert state.standalone_task_number == 6
        assert state.updated_at >= old_updated_at

    def test_serialization_roundtrip(self) -> None:
        """CounterState can be serialized and deserialized."""
        original = CounterState(
            spec_number=100,
            standalone_task_number=50,
        )

        json_str = original.model_dump_json()
        restored = CounterState.model_validate_json(json_str)

        assert restored.spec_number == original.spec_number
        assert restored.standalone_task_number == original.standalone_task_number

    def test_validation_rejects_negative_numbers(self) -> None:
        """CounterState rejects negative counter values."""
        with pytest.raises(ValueError):
            CounterState(spec_number=-1)

        with pytest.raises(ValueError):
            CounterState(standalone_task_number=-1)


class TestReadCounters:
    """Tests for reading counters from the sync branch."""

    def test_read_counters_requires_initialization(self, git_repo_with_commit: Path) -> None:
        """read_counters raises if sync branch not initialized."""
        sync = SyncService(project_dir=git_repo_with_commit)

        with pytest.raises(RuntimeError, match="not initialized"):
            read_counters(sync)

    def test_read_counters_returns_defaults_when_no_file(
        self, initialized_sync: SyncService
    ) -> None:
        """read_counters returns defaults when counters.json doesn't exist."""
        state = read_counters(initialized_sync)

        assert state.spec_number == 0
        assert state.standalone_task_number == 0

    def test_read_counters_returns_stored_values(
        self, initialized_sync: SyncService
    ) -> None:
        """read_counters returns values from counters.json on sync branch."""
        # Allocate some numbers first to create counters.json
        allocate_spec_number(initialized_sync)
        allocate_spec_number(initialized_sync)
        allocate_standalone_number(initialized_sync)

        state = read_counters(initialized_sync)

        assert state.spec_number == 2
        assert state.standalone_task_number == 1

    def test_read_counters_handles_corrupted_file(
        self, initialized_sync: SyncService
    ) -> None:
        """read_counters handles corrupted counters.json gracefully."""
        # Create corrupted counters.json on sync branch
        # We'll do this by committing invalid JSON directly
        blob_sha = initialized_sync._run_git(
            ["hash-object", "-w", "--stdin"],
            input_data="not valid json",
        )

        # Create tree with this blob
        tree_entry = f"100644 blob {blob_sha}\tcounters.json\n"
        cub_tree = initialized_sync._run_git(["mktree"], input_data=tree_entry)

        # Create root tree with .cub
        root_entry = f"040000 tree {cub_tree}\t.cub\n"
        root_tree = initialized_sync._run_git(["mktree"], input_data=root_entry)

        # Commit
        parent_sha = initialized_sync._get_branch_sha(initialized_sync.branch_ref)
        commit_sha = initialized_sync._run_git(
            ["commit-tree", root_tree, "-p", parent_sha, "-m", "Corrupt counters"],
        )
        initialized_sync._run_git(
            ["update-ref", initialized_sync.branch_ref, commit_sha]
        )

        # Should return defaults instead of crashing
        state = read_counters(initialized_sync)

        assert state.spec_number == 0
        assert state.standalone_task_number == 0


class TestAllocateSpecNumber:
    """Tests for allocating spec numbers."""

    def test_allocate_spec_number_requires_initialization(
        self, git_repo_with_commit: Path
    ) -> None:
        """allocate_spec_number raises if sync branch not initialized."""
        sync = SyncService(project_dir=git_repo_with_commit)

        with pytest.raises(RuntimeError, match="not initialized"):
            allocate_spec_number(sync)

    def test_allocate_spec_number_returns_sequential_numbers(
        self, initialized_sync: SyncService
    ) -> None:
        """allocate_spec_number returns sequential numbers starting from 0."""
        first = allocate_spec_number(initialized_sync)
        second = allocate_spec_number(initialized_sync)
        third = allocate_spec_number(initialized_sync)

        assert first == 0
        assert second == 1
        assert third == 2

    def test_allocate_spec_number_persists_to_sync_branch(
        self, initialized_sync: SyncService
    ) -> None:
        """allocate_spec_number commits the updated counter to sync branch."""
        allocate_spec_number(initialized_sync)

        # Read back from sync branch
        state = read_counters(initialized_sync)
        assert state.spec_number == 1

    def test_allocate_spec_number_creates_commit(
        self, initialized_sync: SyncService, git_repo_with_commit: Path
    ) -> None:
        """allocate_spec_number creates a commit on sync branch."""
        # Get initial commit count
        initial_log = subprocess.run(
            ["git", "log", "--oneline", "cub-sync"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        )
        initial_count = len(initial_log.stdout.strip().split("\n"))

        allocate_spec_number(initialized_sync)

        # Check commit count increased
        final_log = subprocess.run(
            ["git", "log", "--oneline", "cub-sync"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        )
        final_count = len(final_log.stdout.strip().split("\n"))

        assert final_count == initial_count + 1

    def test_allocate_spec_number_does_not_affect_working_tree(
        self, initialized_sync: SyncService, git_repo_with_commit: Path
    ) -> None:
        """allocate_spec_number doesn't modify files in working directory."""
        # Record initial status
        initial_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        allocate_spec_number(initialized_sync)
        allocate_spec_number(initialized_sync)

        # Status should be unchanged
        final_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        assert final_status == initial_status

    def test_allocate_spec_number_preserves_current_branch(
        self, initialized_sync: SyncService, git_repo_with_commit: Path
    ) -> None:
        """allocate_spec_number doesn't change the current branch."""
        # Record current branch
        initial_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        allocate_spec_number(initialized_sync)

        # Current branch should be unchanged
        final_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert final_branch == initial_branch


class TestAllocateStandaloneNumber:
    """Tests for allocating standalone task numbers."""

    def test_allocate_standalone_number_requires_initialization(
        self, git_repo_with_commit: Path
    ) -> None:
        """allocate_standalone_number raises if sync branch not initialized."""
        sync = SyncService(project_dir=git_repo_with_commit)

        with pytest.raises(RuntimeError, match="not initialized"):
            allocate_standalone_number(sync)

    def test_allocate_standalone_number_returns_sequential_numbers(
        self, initialized_sync: SyncService
    ) -> None:
        """allocate_standalone_number returns sequential numbers starting from 0."""
        first = allocate_standalone_number(initialized_sync)
        second = allocate_standalone_number(initialized_sync)
        third = allocate_standalone_number(initialized_sync)

        assert first == 0
        assert second == 1
        assert third == 2

    def test_allocate_standalone_number_persists_to_sync_branch(
        self, initialized_sync: SyncService
    ) -> None:
        """allocate_standalone_number commits the updated counter to sync branch."""
        allocate_standalone_number(initialized_sync)

        # Read back from sync branch
        state = read_counters(initialized_sync)
        assert state.standalone_task_number == 1

    def test_spec_and_standalone_counters_are_independent(
        self, initialized_sync: SyncService
    ) -> None:
        """Spec and standalone counters are tracked independently."""
        # Allocate some of each
        spec1 = allocate_spec_number(initialized_sync)
        standalone1 = allocate_standalone_number(initialized_sync)
        spec2 = allocate_spec_number(initialized_sync)
        standalone2 = allocate_standalone_number(initialized_sync)

        # They should be independent sequences
        assert spec1 == 0
        assert spec2 == 1
        assert standalone1 == 0
        assert standalone2 == 1

        # Verify state
        state = read_counters(initialized_sync)
        assert state.spec_number == 2
        assert state.standalone_task_number == 2


class TestCounterAllocationRetry:
    """Tests for retry logic in counter allocation."""

    def test_allocation_raises_after_max_retries(
        self, initialized_sync: SyncService
    ) -> None:
        """Allocation raises CounterAllocationError after exhausting retries."""
        # Mock _commit_counters to always fail
        with patch(
            "cub.core.ids.counters._commit_counters",
            side_effect=Exception("Simulated failure"),
        ):
            with pytest.raises(CounterAllocationError) as exc_info:
                allocate_spec_number(initialized_sync, max_retries=2)

            assert exc_info.value.retries == 3  # 0, 1, 2 = 3 attempts

    def test_allocation_retries_attribute(self) -> None:
        """CounterAllocationError has correct retries attribute."""
        error = CounterAllocationError("Test error", retries=5)

        assert error.retries == 5
        assert "Test error" in str(error)


class TestCountersPersistence:
    """Tests for counter state persistence on sync branch."""

    def test_counters_survive_service_recreation(
        self, git_repo_with_commit: Path
    ) -> None:
        """Counter state persists across SyncService instances."""
        # First service instance
        sync1 = SyncService(project_dir=git_repo_with_commit)
        sync1.initialize()
        allocate_spec_number(sync1)
        allocate_spec_number(sync1)

        # New service instance
        sync2 = SyncService(project_dir=git_repo_with_commit)
        state = read_counters(sync2)

        assert state.spec_number == 2

        # Should continue from 2
        third = allocate_spec_number(sync2)
        assert third == 2

    def test_counters_stored_as_valid_json(
        self, initialized_sync: SyncService
    ) -> None:
        """Counters are stored as valid JSON on the sync branch."""
        allocate_spec_number(initialized_sync)

        # Read raw content from sync branch
        content = initialized_sync._get_file_from_ref(
            initialized_sync.branch_name, COUNTERS_FILE
        )

        assert content is not None

        # Should be valid JSON
        data = json.loads(content)
        assert "spec_number" in data
        assert "standalone_task_number" in data
        assert "updated_at" in data

    def test_counters_updated_at_reflects_last_change(
        self, initialized_sync: SyncService
    ) -> None:
        """CounterState.updated_at reflects the time of last allocation."""
        before_alloc = datetime.now(timezone.utc)
        allocate_spec_number(initialized_sync)
        after_alloc = datetime.now(timezone.utc)

        state = read_counters(initialized_sync)

        # Allow for some timing variance
        assert state.updated_at >= before_alloc - timedelta(seconds=1)
        assert state.updated_at <= after_alloc + timedelta(seconds=1)


class TestCountersPreserveOtherFiles:
    """Tests that counter commits preserve other files on sync branch."""

    def test_allocate_preserves_tasks_file(
        self, initialized_sync: SyncService
    ) -> None:
        """Counter allocation preserves existing tasks.jsonl on sync branch."""
        # Create tasks file and commit to sync branch
        tasks_path = initialized_sync.tasks_file_path
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001", "title": "Test task"}\n')
        initialized_sync.commit("Initial tasks")

        # Allocate a counter
        allocate_spec_number(initialized_sync)

        # Verify tasks file is still on sync branch
        content = initialized_sync._get_file_from_ref(
            initialized_sync.branch_name, ".cub/tasks.jsonl"
        )
        assert content is not None
        assert "test-001" in content

    def test_multiple_allocations_preserve_files(
        self, initialized_sync: SyncService
    ) -> None:
        """Multiple allocations preserve all files on sync branch."""
        # Create tasks file
        tasks_path = initialized_sync.tasks_file_path
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001"}\n')
        initialized_sync.commit("Initial tasks")

        # Multiple allocations
        allocate_spec_number(initialized_sync)
        allocate_standalone_number(initialized_sync)
        allocate_spec_number(initialized_sync)

        # Both counters and tasks should exist
        counters = initialized_sync._get_file_from_ref(
            initialized_sync.branch_name, COUNTERS_FILE
        )
        tasks = initialized_sync._get_file_from_ref(
            initialized_sync.branch_name, ".cub/tasks.jsonl"
        )

        assert counters is not None
        assert tasks is not None
        assert "test-001" in tasks
