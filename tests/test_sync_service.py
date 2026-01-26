"""
Tests for the SyncService git plumbing functionality.

Tests cover:
- Service initialization
- Git command execution
- Branch existence checking
- Sync branch initialization
- State management
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cub.core.sync import SyncService, SyncState
from cub.core.sync.service import GitError


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


class TestSyncServiceInit:
    """Tests for SyncService initialization."""

    def test_init_with_defaults(self, git_repo: Path) -> None:
        """SyncService initializes with sensible defaults."""
        sync = SyncService(project_dir=git_repo)

        assert sync.project_dir == git_repo
        assert sync.branch_name == "cub-sync"
        assert sync.tasks_file == ".cub/tasks.jsonl"

    def test_init_with_custom_branch(self, git_repo: Path) -> None:
        """SyncService accepts custom branch name."""
        sync = SyncService(
            project_dir=git_repo,
            branch_name="my-sync-branch",
        )

        assert sync.branch_name == "my-sync-branch"
        assert sync.branch_ref == "refs/heads/my-sync-branch"

    def test_init_with_custom_tasks_file(self, git_repo: Path) -> None:
        """SyncService accepts custom tasks file path."""
        sync = SyncService(
            project_dir=git_repo,
            tasks_file=".cub/custom-tasks.jsonl",
        )

        assert sync.tasks_file == ".cub/custom-tasks.jsonl"
        assert sync.tasks_file_path == git_repo / ".cub/custom-tasks.jsonl"

    def test_state_file_path(self, git_repo: Path) -> None:
        """State file path is correctly computed."""
        sync = SyncService(project_dir=git_repo)

        expected = git_repo / ".cub/.sync-state.json"
        assert sync.state_file_path == expected


class TestGitCommandExecution:
    """Tests for the _run_git helper method."""

    def test_run_git_success(self, git_repo: Path) -> None:
        """_run_git returns stdout on success."""
        sync = SyncService(project_dir=git_repo)

        # rev-parse --git-dir should return .git
        result = sync._run_git(["rev-parse", "--git-dir"])
        assert result == ".git"

    def test_run_git_failure_raises(self, git_repo: Path) -> None:
        """_run_git raises GitError on failure."""
        sync = SyncService(project_dir=git_repo)

        with pytest.raises(GitError) as exc_info:
            sync._run_git(["nonexistent-command"])

        assert "nonexistent-command" in str(exc_info.value)

    def test_run_git_no_check(self, git_repo: Path) -> None:
        """_run_git with check=False doesn't raise on failure."""
        sync = SyncService(project_dir=git_repo)

        # This should not raise
        result = sync._run_git(["rev-parse", "nonexistent-ref"], check=False)
        # Result may be empty or contain error message
        assert isinstance(result, str)


class TestIsInitialized:
    """Tests for the is_initialized method."""

    def test_not_initialized_initially(self, git_repo: Path) -> None:
        """is_initialized returns False for new repo."""
        sync = SyncService(project_dir=git_repo)

        assert sync.is_initialized() is False

    def test_not_initialized_not_git_repo(self, tmp_path: Path) -> None:
        """is_initialized returns False if not a git repo."""
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()

        sync = SyncService(project_dir=non_repo)

        assert sync.is_initialized() is False

    def test_initialized_after_create(self, git_repo_with_commit: Path) -> None:
        """is_initialized returns True after branch is created."""
        sync = SyncService(project_dir=git_repo_with_commit)

        # Manually create the branch
        subprocess.run(
            ["git", "branch", "cub-sync"],
            cwd=git_repo_with_commit,
            capture_output=True,
            check=True,
        )

        assert sync.is_initialized() is True


class TestInitialize:
    """Tests for the initialize method."""

    def test_initialize_creates_branch_from_head(self, git_repo_with_commit: Path) -> None:
        """initialize creates branch from HEAD when commits exist."""
        sync = SyncService(project_dir=git_repo_with_commit)

        assert sync.is_initialized() is False

        sync.initialize()

        assert sync.is_initialized() is True

        # Verify branch points to HEAD
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        sync_sha = subprocess.run(
            ["git", "rev-parse", "cub-sync"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert head_sha == sync_sha

    def test_initialize_creates_branch_in_empty_repo(self, git_repo: Path) -> None:
        """initialize creates branch with empty tree if no commits."""
        sync = SyncService(project_dir=git_repo)

        sync.initialize()

        assert sync.is_initialized() is True

        # Verify branch exists
        result = subprocess.run(
            ["git", "show-ref", "--verify", "refs/heads/cub-sync"],
            cwd=git_repo,
            capture_output=True,
        )
        assert result.returncode == 0

    def test_initialize_idempotent(self, git_repo_with_commit: Path) -> None:
        """initialize is safe to call multiple times."""
        sync = SyncService(project_dir=git_repo_with_commit)

        sync.initialize()
        first_sha = subprocess.run(
            ["git", "rev-parse", "cub-sync"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Call again - should be a no-op
        sync.initialize()
        second_sha = subprocess.run(
            ["git", "rev-parse", "cub-sync"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert first_sha == second_sha

    def test_initialize_updates_state(self, git_repo_with_commit: Path) -> None:
        """initialize updates the sync state file."""
        sync = SyncService(project_dir=git_repo_with_commit)

        sync.initialize()

        state = sync.get_state()
        assert state.initialized is True
        assert state.branch_name == "cub-sync"

    def test_initialize_raises_if_not_git_repo(self, tmp_path: Path) -> None:
        """initialize raises if not in a git repository."""
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()

        sync = SyncService(project_dir=non_repo)

        with pytest.raises(RuntimeError, match="Not a git repository"):
            sync.initialize()


class TestSyncState:
    """Tests for SyncState model."""

    def test_state_default_values(self) -> None:
        """SyncState has sensible defaults."""
        state = SyncState()

        assert state.branch_name == "cub-sync"
        assert state.tasks_file == ".cub/tasks.jsonl"
        assert state.last_commit_sha is None
        assert state.initialized is False

    def test_state_has_unpushed_changes_no_commits(self) -> None:
        """has_unpushed_changes returns False when no commits."""
        state = SyncState()

        assert state.has_unpushed_changes() is False

    def test_state_has_unpushed_changes_when_ahead(self) -> None:
        """has_unpushed_changes returns True when local is ahead."""
        state = SyncState(
            last_commit_sha="abc123",
            last_push_sha=None,
        )

        assert state.has_unpushed_changes() is True

    def test_state_has_unpushed_changes_when_in_sync(self) -> None:
        """has_unpushed_changes returns False when local matches remote."""
        state = SyncState(
            last_commit_sha="abc123",
            last_push_sha="abc123",
        )

        assert state.has_unpushed_changes() is False

    def test_state_serialization(self, git_repo: Path) -> None:
        """SyncState can be serialized and deserialized."""
        original = SyncState(
            branch_name="my-branch",
            tasks_file=".cub/my-tasks.jsonl",
            last_commit_sha="abc123",
            initialized=True,
        )

        json_str = original.model_dump_json()
        restored = SyncState.model_validate_json(json_str)

        assert restored.branch_name == original.branch_name
        assert restored.tasks_file == original.tasks_file
        assert restored.last_commit_sha == original.last_commit_sha
        assert restored.initialized == original.initialized


class TestStateFilePersistence:
    """Tests for state file persistence."""

    def test_state_file_created_on_initialize(self, git_repo_with_commit: Path) -> None:
        """State file is created when initializing."""
        sync = SyncService(project_dir=git_repo_with_commit)

        assert not sync.state_file_path.exists()

        sync.initialize()

        assert sync.state_file_path.exists()

    def test_state_file_loaded_on_access(self, git_repo_with_commit: Path) -> None:
        """State is loaded from file when it exists."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create new service instance
        sync2 = SyncService(project_dir=git_repo_with_commit)
        state = sync2.get_state()

        assert state.initialized is True
        assert state.branch_name == "cub-sync"

    def test_state_file_handles_corruption(self, git_repo_with_commit: Path) -> None:
        """State loading handles corrupted files gracefully."""
        sync = SyncService(project_dir=git_repo_with_commit)

        # Create corrupted state file
        sync.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        sync.state_file_path.write_text("not valid json")

        # Should return default state, not crash
        state = sync.get_state()
        assert state.initialized is False
