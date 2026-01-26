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


class TestCommit:
    """Tests for the commit method."""

    def test_commit_requires_initialization(self, git_repo_with_commit: Path) -> None:
        """commit raises if sync branch not initialized."""
        sync = SyncService(project_dir=git_repo_with_commit)

        # Create tasks file but don't initialize
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001", "title": "Test task"}\n')

        with pytest.raises(RuntimeError, match="not initialized"):
            sync.commit("Test commit")

    def test_commit_requires_tasks_file(self, git_repo_with_commit: Path) -> None:
        """commit raises if tasks file doesn't exist."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Don't create tasks file
        with pytest.raises(RuntimeError, match="Tasks file not found"):
            sync.commit("Test commit")

    def test_commit_creates_commit_on_sync_branch(self, git_repo_with_commit: Path) -> None:
        """commit creates a git commit on the sync branch."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001", "title": "Test task"}\n')

        # Commit
        commit_sha = sync.commit("Initial sync")

        # Verify commit exists
        assert len(commit_sha) == 40  # SHA-1 hash length
        assert commit_sha.isalnum()

        # Verify sync branch points to new commit
        branch_sha = subprocess.run(
            ["git", "rev-parse", "cub-sync"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert branch_sha == commit_sha

    def test_commit_stores_tasks_content(self, git_repo_with_commit: Path) -> None:
        """commit stores the tasks file content in the commit."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file with specific content
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_content = '{"id": "test-001", "title": "My test task"}\n'
        tasks_path.write_text(tasks_content)

        # Commit
        commit_sha = sync.commit("Sync tasks")

        # Verify content is in the commit
        # Use git show to get the file content from the commit
        result = subprocess.run(
            ["git", "show", f"{commit_sha}:.cub/tasks.jsonl"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout == tasks_content

    def test_commit_uses_default_message(self, git_repo_with_commit: Path) -> None:
        """commit uses 'Update tasks' as default message."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001"}\n')

        # Commit without message
        commit_sha = sync.commit()

        # Verify commit message
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", commit_sha],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == "Update tasks"

    def test_commit_uses_custom_message(self, git_repo_with_commit: Path) -> None:
        """commit uses provided message."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001"}\n')

        # Commit with custom message
        commit_sha = sync.commit("Custom sync message")

        # Verify commit message
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", commit_sha],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == "Custom sync message"

    def test_commit_updates_state(self, git_repo_with_commit: Path) -> None:
        """commit updates sync state with commit SHA and hash."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001"}\n')

        # Commit
        commit_sha = sync.commit("Test sync")

        # Verify state was updated
        state = sync.get_state()
        assert state.last_commit_sha == commit_sha
        assert state.last_tasks_hash is not None
        assert state.last_sync_at is not None

    def test_commit_detects_no_changes(self, git_repo_with_commit: Path) -> None:
        """commit returns existing SHA when content hasn't changed."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001"}\n')

        # First commit
        first_sha = sync.commit("First sync")

        # Second commit with same content
        second_sha = sync.commit("Second sync")

        # Should return same SHA (no new commit)
        assert second_sha == first_sha

    def test_commit_creates_new_commit_on_content_change(self, git_repo_with_commit: Path) -> None:
        """commit creates new commit when content changes."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001"}\n')

        # First commit
        first_sha = sync.commit("First sync")

        # Change content
        tasks_path.write_text('{"id": "test-001"}\n{"id": "test-002"}\n')

        # Second commit
        second_sha = sync.commit("Second sync")

        # Should be different commits
        assert second_sha != first_sha

        # Verify parent relationship
        result = subprocess.run(
            ["git", "rev-parse", f"{second_sha}^"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == first_sha

    def test_commit_does_not_affect_working_tree(self, git_repo_with_commit: Path) -> None:
        """commit doesn't modify files in the working tree."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001"}\n')

        # Record initial git status
        initial_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        # Commit to sync branch
        sync.commit("Sync")

        # Verify git status is unchanged (working tree unaffected)
        final_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        assert final_status == initial_status

    def test_commit_preserves_working_branch(self, git_repo_with_commit: Path) -> None:
        """commit doesn't change the current branch."""
        sync = SyncService(project_dir=git_repo_with_commit)
        sync.initialize()

        # Create tasks file
        tasks_path = git_repo_with_commit / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "test-001"}\n')

        # Record current branch
        initial_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Commit to sync branch
        sync.commit("Sync")

        # Verify current branch is unchanged
        final_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo_with_commit,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert final_branch == initial_branch
