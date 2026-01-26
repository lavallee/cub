"""
Tests for the SyncService git plumbing functionality.

Tests cover:
- Service initialization
- Git command execution
- Branch existence checking
- Sync branch initialization
- State management
- Pull with conflict detection
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from cub.core.sync import SyncConflict, SyncResult, SyncService, SyncState, SyncStatus
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


class TestPull:
    """Tests for the pull method with conflict detection."""

    @pytest.fixture
    def git_repo_with_remote(self, tmp_path: Path) -> tuple[Path, Path]:
        """
        Create a git repo with a remote for testing pull operations.

        Returns:
            Tuple of (local_repo_path, remote_repo_path).
        """
        # Create "remote" bare repo
        remote_repo = tmp_path / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote_repo)], capture_output=True, check=True)

        # Create local repo
        local_repo = tmp_path / "local"
        local_repo.mkdir()
        subprocess.run(["git", "init"], cwd=local_repo, capture_output=True, check=True)

        # Configure git user
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Add remote
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote_repo)],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Create initial commit on local
        (local_repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=local_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        return local_repo, remote_repo

    def test_pull_fails_when_not_initialized(self, git_repo_with_remote: tuple[Path, Path]) -> None:
        """pull returns failure when sync branch not initialized."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)

        result = sync.pull()

        assert result.success is False
        assert result.operation == "pull"
        assert "not initialized" in result.message.lower()

    def test_pull_succeeds_when_no_remote_branch(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """pull succeeds with nothing to do when remote branch doesn't exist."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        result = sync.pull()

        assert result.success is True
        assert result.operation == "pull"
        assert result.tasks_updated == 0
        assert "no remote" in result.message.lower() or "nothing to pull" in result.message.lower()

    def test_pull_adds_remote_only_tasks(self, git_repo_with_remote: tuple[Path, Path]) -> None:
        """pull adds tasks that exist only on remote."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create local tasks file
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001", "title": "Local task"}\n')
        sync.commit("Initial local tasks")

        # Push sync branch to remote
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Simulate remote changes by cloning, modifying, and pushing
        second_clone = local_repo.parent / "second_clone"
        subprocess.run(
            ["git", "clone", str(remote_repo), str(second_clone)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        # Checkout sync branch and add a new task
        subprocess.run(
            ["git", "checkout", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        tasks_in_clone = second_clone / ".cub" / "tasks.jsonl"
        tasks_in_clone.write_text(
            '{"id": "task-001", "title": "Local task"}\n'
            '{"id": "task-002", "title": "Remote task"}\n'
        )
        subprocess.run(["git", "add", "."], cwd=second_clone, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add remote task"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        # Now pull from the original local repo
        result = sync.pull()

        assert result.success is True
        assert result.tasks_updated == 1
        assert len(result.conflicts) == 0

        # Verify task was added locally
        local_content = tasks_path.read_text()
        assert "task-002" in local_content
        assert "Remote task" in local_content

    def test_pull_detects_conflict_uses_last_write_wins(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """pull detects conflicts and uses last-write-wins based on updated_at."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create local task with older timestamp
        old_time = (datetime.now() - timedelta(hours=1)).isoformat()
        local_task = {"id": "task-001", "title": "Local version", "updated_at": old_time}
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text(json.dumps(local_task) + "\n")
        sync.commit("Local task")

        # Push to remote
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Create "remote" changes with newer timestamp
        second_clone = local_repo.parent / "second_clone"
        subprocess.run(
            ["git", "clone", str(remote_repo), str(second_clone)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        subprocess.run(
            ["git", "checkout", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        new_time = datetime.now().isoformat()
        remote_task = {"id": "task-001", "title": "Remote version", "updated_at": new_time}
        tasks_in_clone = second_clone / ".cub" / "tasks.jsonl"
        tasks_in_clone.write_text(json.dumps(remote_task) + "\n")
        subprocess.run(["git", "add", "."], cwd=second_clone, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Update task remotely"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        # Pull from local - should use remote (newer) version
        result = sync.pull()

        assert result.success is True
        assert result.tasks_updated == 1
        assert len(result.conflicts) == 1

        conflict = result.conflicts[0]
        assert conflict.task_id == "task-001"
        assert conflict.winner == "remote"
        assert conflict.resolution == "last_write_wins"

        # Verify remote version was used
        local_content = tasks_path.read_text()
        assert "Remote version" in local_content
        assert "Local version" not in local_content

    def test_pull_keeps_local_when_newer(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """pull keeps local version when it has a newer updated_at timestamp."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # First push an old version to remote
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        old_task = {"id": "task-001", "title": "Old version", "updated_at": old_time}
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text(json.dumps(old_task) + "\n")
        sync.commit("Old task")

        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Now update local with newer timestamp
        new_time = datetime.now().isoformat()
        new_task = {"id": "task-001", "title": "New local version", "updated_at": new_time}
        tasks_path.write_text(json.dumps(new_task) + "\n")
        sync.commit("Updated local task")

        # Pull should keep local (newer) version
        result = sync.pull()

        assert result.success is True
        # tasks_updated should be 0 since local is kept
        assert result.tasks_updated == 0
        assert len(result.conflicts) == 1

        conflict = result.conflicts[0]
        assert conflict.task_id == "task-001"
        assert conflict.winner == "local"

        # Verify local version was kept
        local_content = tasks_path.read_text()
        assert "New local version" in local_content

    def test_pull_prefers_remote_when_no_timestamps(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """pull prefers remote version when neither has updated_at timestamps."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create local task without timestamp
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001", "title": "Local version"}\n')
        sync.commit("Local task")

        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Create different remote version without timestamp
        second_clone = local_repo.parent / "second_clone"
        subprocess.run(
            ["git", "clone", str(remote_repo), str(second_clone)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        subprocess.run(
            ["git", "checkout", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        tasks_in_clone = second_clone / ".cub" / "tasks.jsonl"
        tasks_in_clone.write_text('{"id": "task-001", "title": "Remote version"}\n')
        subprocess.run(["git", "add", "."], cwd=second_clone, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Update task remotely"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        # Pull - should prefer remote when no timestamps
        result = sync.pull()

        assert result.success is True
        assert result.tasks_updated == 1
        assert len(result.conflicts) == 1
        assert result.conflicts[0].winner == "remote"

        # Verify remote version was used
        local_content = tasks_path.read_text()
        assert "Remote version" in local_content

    def test_pull_no_changes_when_identical(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """pull reports no changes when local and remote are identical."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create local tasks
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001", "title": "Same task"}\n')
        sync.commit("Local task")

        # Push to remote
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Pull should find no changes
        result = sync.pull()

        assert result.success is True
        assert result.tasks_updated == 0
        assert len(result.conflicts) == 0
        assert "up to date" in result.message.lower()

    def test_pull_creates_commit_when_changes_merged(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """pull creates a commit after successfully merging changes."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create local task
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001", "title": "Local"}\n')
        sync.commit("Local task")

        # Get commit SHA before pull
        before_sha = subprocess.run(
            ["git", "rev-parse", "cub-sync"],
            cwd=local_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Push and add remote task
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        second_clone = local_repo.parent / "second_clone"
        subprocess.run(
            ["git", "clone", str(remote_repo), str(second_clone)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        subprocess.run(
            ["git", "checkout", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        tasks_in_clone = second_clone / ".cub" / "tasks.jsonl"
        tasks_in_clone.write_text(
            '{"id": "task-001", "title": "Local"}\n'
            '{"id": "task-002", "title": "Remote"}\n'
        )
        subprocess.run(["git", "add", "."], cwd=second_clone, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add remote task"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        # Pull
        result = sync.pull()

        assert result.success is True
        assert result.commit_sha is not None
        assert len(result.commit_sha) == 40

        # Verify commit was created
        after_sha = subprocess.run(
            ["git", "rev-parse", "cub-sync"],
            cwd=local_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        assert after_sha != before_sha
        assert after_sha == result.commit_sha

    def test_pull_returns_sync_result(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """pull returns a SyncResult with all expected fields."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        result = sync.pull()

        assert isinstance(result, SyncResult)
        assert result.operation == "pull"
        assert isinstance(result.success, bool)
        assert isinstance(result.tasks_updated, int)
        assert isinstance(result.conflicts, list)
        assert result.started_at is not None
        assert result.completed_at is not None


class TestSyncConflictModel:
    """Tests for the SyncConflict model."""

    def test_conflict_creation(self) -> None:
        """SyncConflict can be created with all fields."""
        now = datetime.now()
        earlier = now - timedelta(hours=1)

        conflict = SyncConflict(
            task_id="task-001",
            local_updated_at=earlier,
            remote_updated_at=now,
            resolution="last_write_wins",
            winner="remote",
        )

        assert conflict.task_id == "task-001"
        assert conflict.local_updated_at == earlier
        assert conflict.remote_updated_at == now
        assert conflict.resolution == "last_write_wins"
        assert conflict.winner == "remote"

    def test_conflict_default_values(self) -> None:
        """SyncConflict has sensible defaults."""
        conflict = SyncConflict(task_id="task-001")

        assert conflict.task_id == "task-001"
        assert conflict.local_updated_at is None
        assert conflict.remote_updated_at is None
        assert conflict.resolution == "last_write_wins"
        assert conflict.winner == ""


class TestSyncResultModel:
    """Tests for the SyncResult model."""

    def test_result_creation(self) -> None:
        """SyncResult can be created with all fields."""
        now = datetime.now()
        conflict = SyncConflict(task_id="task-001", winner="remote")

        result = SyncResult(
            success=True,
            operation="pull",
            commit_sha="abc123def456",
            message="Merged 5 tasks",
            tasks_updated=5,
            conflicts=[conflict],
            started_at=now - timedelta(seconds=2),
            completed_at=now,
        )

        assert result.success is True
        assert result.operation == "pull"
        assert result.commit_sha == "abc123def456"
        assert result.tasks_updated == 5
        assert len(result.conflicts) == 1
        assert result.duration_seconds is not None
        assert result.duration_seconds >= 2

    def test_result_summary(self) -> None:
        """SyncResult.summary() returns human-readable text."""
        result = SyncResult(
            success=True,
            operation="pull",
            commit_sha="abc123def456",
            tasks_updated=3,
            conflicts=[SyncConflict(task_id="t1"), SyncConflict(task_id="t2")],
        )

        summary = result.summary()

        assert "pull" in summary
        assert "succeeded" in summary
        assert "abc123de" in summary  # Short SHA
        assert "3 tasks updated" in summary
        assert "2 conflicts resolved" in summary

    def test_result_summary_failure(self) -> None:
        """SyncResult.summary() handles failure case."""
        result = SyncResult(
            success=False,
            operation="pull",
            message="Remote not found",
        )

        summary = result.summary()

        assert "pull" in summary
        assert "failed" in summary
        assert "Remote not found" in summary


class TestMergeTasks:
    """Tests for the _merge_tasks helper method."""

    def test_merge_adds_remote_only_tasks(self, git_repo_with_commit: Path) -> None:
        """_merge_tasks adds tasks that only exist remotely."""
        sync = SyncService(project_dir=git_repo_with_commit)

        local = {"task-001": {"id": "task-001", "title": "Local"}}
        remote = {
            "task-001": {"id": "task-001", "title": "Local"},
            "task-002": {"id": "task-002", "title": "Remote"},
        }

        merged, conflicts, updated = sync._merge_tasks(local, remote)

        assert "task-001" in merged
        assert "task-002" in merged
        assert len(conflicts) == 0
        assert updated == 1

    def test_merge_keeps_local_only_tasks(self, git_repo_with_commit: Path) -> None:
        """_merge_tasks keeps tasks that only exist locally."""
        sync = SyncService(project_dir=git_repo_with_commit)

        local = {
            "task-001": {"id": "task-001", "title": "Local"},
            "task-002": {"id": "task-002", "title": "Local only"},
        }
        remote = {"task-001": {"id": "task-001", "title": "Local"}}

        merged, conflicts, updated = sync._merge_tasks(local, remote)

        assert "task-001" in merged
        assert "task-002" in merged
        assert merged["task-002"]["title"] == "Local only"
        assert len(conflicts) == 0
        assert updated == 0

    def test_merge_detects_conflict(self, git_repo_with_commit: Path) -> None:
        """_merge_tasks detects conflicts when tasks differ."""
        sync = SyncService(project_dir=git_repo_with_commit)

        old_time = (datetime.now() - timedelta(hours=1)).isoformat()
        new_time = datetime.now().isoformat()

        local = {"task-001": {"id": "task-001", "title": "Local", "updated_at": old_time}}
        remote = {"task-001": {"id": "task-001", "title": "Remote", "updated_at": new_time}}

        merged, conflicts, updated = sync._merge_tasks(local, remote)

        assert len(conflicts) == 1
        assert conflicts[0].task_id == "task-001"
        assert conflicts[0].winner == "remote"
        assert merged["task-001"]["title"] == "Remote"
        assert updated == 1

    def test_merge_no_conflict_when_identical(self, git_repo_with_commit: Path) -> None:
        """_merge_tasks doesn't report conflict when tasks are identical."""
        sync = SyncService(project_dir=git_repo_with_commit)

        task = {"id": "task-001", "title": "Same", "status": "open"}
        local = {"task-001": task}
        remote = {"task-001": task.copy()}

        merged, conflicts, updated = sync._merge_tasks(local, remote)

        assert len(conflicts) == 0
        assert updated == 0


class TestParseTasksFromJsonl:
    """Tests for the _parse_tasks_from_jsonl helper method."""

    def test_parse_valid_jsonl(self, git_repo_with_commit: Path) -> None:
        """_parse_tasks_from_jsonl parses valid JSONL content."""
        sync = SyncService(project_dir=git_repo_with_commit)

        content = '{"id": "task-001", "title": "First"}\n{"id": "task-002", "title": "Second"}\n'

        tasks = sync._parse_tasks_from_jsonl(content)

        assert len(tasks) == 2
        assert "task-001" in tasks
        assert "task-002" in tasks
        assert tasks["task-001"]["title"] == "First"

    def test_parse_skips_empty_lines(self, git_repo_with_commit: Path) -> None:
        """_parse_tasks_from_jsonl skips empty lines."""
        sync = SyncService(project_dir=git_repo_with_commit)

        content = '{"id": "task-001", "title": "First"}\n\n{"id": "task-002", "title": "Second"}\n'

        tasks = sync._parse_tasks_from_jsonl(content)

        assert len(tasks) == 2

    def test_parse_skips_invalid_json(self, git_repo_with_commit: Path) -> None:
        """_parse_tasks_from_jsonl skips invalid JSON lines."""
        sync = SyncService(project_dir=git_repo_with_commit)

        content = '{"id": "task-001", "title": "Valid"}\nnot valid json\n{"id": "task-002"}\n'

        tasks = sync._parse_tasks_from_jsonl(content)

        assert len(tasks) == 2
        assert "task-001" in tasks
        assert "task-002" in tasks

    def test_parse_skips_tasks_without_id(self, git_repo_with_commit: Path) -> None:
        """_parse_tasks_from_jsonl skips tasks without an id field."""
        sync = SyncService(project_dir=git_repo_with_commit)

        content = '{"id": "task-001", "title": "Has ID"}\n{"title": "No ID"}\n'

        tasks = sync._parse_tasks_from_jsonl(content)

        assert len(tasks) == 1
        assert "task-001" in tasks


class TestSerializeTasksToJsonl:
    """Tests for the _serialize_tasks_to_jsonl helper method."""

    def test_serialize_produces_valid_jsonl(self, git_repo_with_commit: Path) -> None:
        """_serialize_tasks_to_jsonl produces valid JSONL output."""
        sync = SyncService(project_dir=git_repo_with_commit)

        tasks = {
            "task-001": {"id": "task-001", "title": "First"},
            "task-002": {"id": "task-002", "title": "Second"},
        }

        content = sync._serialize_tasks_to_jsonl(tasks)

        # Verify it can be parsed back
        parsed = sync._parse_tasks_from_jsonl(content)
        assert len(parsed) == 2

    def test_serialize_empty_dict(self, git_repo_with_commit: Path) -> None:
        """_serialize_tasks_to_jsonl handles empty dict."""
        sync = SyncService(project_dir=git_repo_with_commit)

        content = sync._serialize_tasks_to_jsonl({})

        assert content == ""


class TestGetTaskUpdatedAt:
    """Tests for the _get_task_updated_at helper method."""

    def test_parse_iso_timestamp(self, git_repo_with_commit: Path) -> None:
        """_get_task_updated_at parses ISO format timestamps."""
        sync = SyncService(project_dir=git_repo_with_commit)

        task = {"updated_at": "2024-01-15T10:30:00"}
        result = sync._get_task_updated_at(task)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_iso_with_z_suffix(self, git_repo_with_commit: Path) -> None:
        """_get_task_updated_at handles ISO timestamps with Z suffix."""
        sync = SyncService(project_dir=git_repo_with_commit)

        task = {"updated_at": "2024-01-15T10:30:00Z"}
        result = sync._get_task_updated_at(task)

        assert result is not None
        assert result.year == 2024

    def test_returns_none_when_missing(self, git_repo_with_commit: Path) -> None:
        """_get_task_updated_at returns None when field is missing."""
        sync = SyncService(project_dir=git_repo_with_commit)

        task = {"id": "task-001"}
        result = sync._get_task_updated_at(task)

        assert result is None

    def test_returns_none_for_invalid_format(self, git_repo_with_commit: Path) -> None:
        """_get_task_updated_at returns None for unparseable timestamps."""
        sync = SyncService(project_dir=git_repo_with_commit)

        task = {"updated_at": "not a date"}
        result = sync._get_task_updated_at(task)

        assert result is None


class TestPush:
    """Tests for the push method."""

    @pytest.fixture
    def git_repo_with_remote(self, tmp_path: Path) -> tuple[Path, Path]:
        """
        Create a git repo with a remote for testing push operations.

        Returns:
            Tuple of (local_repo_path, remote_repo_path).
        """
        # Create "remote" bare repo
        remote_repo = tmp_path / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote_repo)], capture_output=True, check=True)

        # Create local repo
        local_repo = tmp_path / "local"
        local_repo.mkdir()
        subprocess.run(["git", "init"], cwd=local_repo, capture_output=True, check=True)

        # Configure git user
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Add remote
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote_repo)],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Create initial commit on local
        (local_repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=local_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        return local_repo, remote_repo

    def test_push_requires_initialization(self, git_repo_with_remote: tuple[Path, Path]) -> None:
        """push raises if sync branch not initialized."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)

        with pytest.raises(RuntimeError, match="not initialized"):
            sync.push()

    def test_push_succeeds_when_remote_branch_doesnt_exist(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """push creates remote branch if it doesn't exist."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create tasks file and commit
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001", "title": "Test task"}\n')
        sync.commit("Initial sync")

        # Push should succeed and create remote branch
        result = sync.push()

        assert result is True

        # Verify remote branch exists
        remote_branches = subprocess.run(
            ["git", "branch", "-r"],
            cwd=local_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        assert "origin/cub-sync" in remote_branches

    def test_push_updates_state(self, git_repo_with_remote: tuple[Path, Path]) -> None:
        """push updates sync state with push SHA and timestamp."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create tasks file and commit
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001"}\n')
        commit_sha = sync.commit("Test sync")

        # Push
        result = sync.push()

        assert result is True

        # Verify state was updated
        state = sync.get_state()
        assert state.last_push_sha == commit_sha
        assert state.last_push_at is not None

    def test_push_handles_failure_gracefully(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """push returns False when push fails."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Remove the remote to cause push to fail
        subprocess.run(
            ["git", "remote", "remove", "origin"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Push should fail but not raise
        result = sync.push()

        assert result is False

    def test_push_updates_existing_remote_branch(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """push updates remote branch when it already exists."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create and push first commit
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001"}\n')
        sync.commit("First sync")
        sync.push()

        # Get remote SHA
        first_remote_sha = subprocess.run(
            ["git", "rev-parse", "origin/cub-sync"],
            cwd=local_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Create and push second commit
        tasks_path.write_text('{"id": "task-001"}\n{"id": "task-002"}\n')
        sync.commit("Second sync")
        sync.push()

        # Get new remote SHA
        second_remote_sha = subprocess.run(
            ["git", "rev-parse", "origin/cub-sync"],
            cwd=local_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Should be different
        assert second_remote_sha != first_remote_sha

    def test_push_does_not_affect_working_tree(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """push doesn't modify files in the working tree."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create tasks file and commit
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001"}\n')
        sync.commit("Test sync")

        # Record initial git status
        initial_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=local_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        # Push
        sync.push()

        # Verify git status is unchanged
        final_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=local_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        assert final_status == initial_status


class TestGetStatus:
    """Tests for the get_status method."""

    @pytest.fixture
    def git_repo_with_remote(self, tmp_path: Path) -> tuple[Path, Path]:
        """
        Create a git repo with a remote for testing status operations.

        Returns:
            Tuple of (local_repo_path, remote_repo_path).
        """
        # Create "remote" bare repo
        remote_repo = tmp_path / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote_repo)], capture_output=True, check=True)

        # Create local repo
        local_repo = tmp_path / "local"
        local_repo.mkdir()
        subprocess.run(["git", "init"], cwd=local_repo, capture_output=True, check=True)

        # Configure git user
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Add remote
        subprocess.run(
            ["git", "remote", "add", "origin", str(remote_repo)],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Create initial commit on local
        (local_repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=local_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        return local_repo, remote_repo

    def test_status_returns_uninitialized_when_not_initialized(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """get_status returns UNINITIALIZED when sync branch doesn't exist."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)

        status = sync.get_status()

        assert status == SyncStatus.UNINITIALIZED

    def test_status_returns_no_remote_when_remote_branch_doesnt_exist(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """get_status returns NO_REMOTE when remote branch doesn't exist."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        status = sync.get_status()

        assert status == SyncStatus.NO_REMOTE

    def test_status_returns_up_to_date_when_branches_match(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """get_status returns UP_TO_DATE when local and remote are identical."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create tasks and push
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001"}\n')
        sync.commit("Initial sync")
        sync.push()

        # Status should be up to date
        status = sync.get_status()

        assert status == SyncStatus.UP_TO_DATE

    def test_status_returns_ahead_when_local_has_new_commits(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """get_status returns AHEAD when local has commits not pushed."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create tasks and push
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001"}\n')
        sync.commit("Initial sync")
        sync.push()

        # Add another commit locally
        tasks_path.write_text('{"id": "task-001"}\n{"id": "task-002"}\n')
        sync.commit("Second sync")

        # Status should be ahead
        status = sync.get_status()

        assert status == SyncStatus.AHEAD

    def test_status_returns_behind_when_remote_has_new_commits(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """get_status returns BEHIND when remote has commits not pulled."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create tasks and push
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001"}\n')
        sync.commit("Initial sync")
        sync.push()

        # Simulate remote changes by cloning, modifying, and pushing
        second_clone = local_repo.parent / "second_clone"
        subprocess.run(
            ["git", "clone", str(remote_repo), str(second_clone)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        subprocess.run(
            ["git", "checkout", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        tasks_in_clone = second_clone / ".cub" / "tasks.jsonl"
        tasks_in_clone.write_text(
            '{"id": "task-001"}\n'
            '{"id": "task-002"}\n'
        )
        subprocess.run(["git", "add", "."], cwd=second_clone, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add remote task"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        # Status should be behind
        status = sync.get_status()

        assert status == SyncStatus.BEHIND

    def test_status_returns_diverged_when_branches_diverged(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """get_status returns DIVERGED when local and remote have diverged."""
        local_repo, remote_repo = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Create initial tasks and push
        tasks_path = local_repo / ".cub" / "tasks.jsonl"
        tasks_path.parent.mkdir(parents=True, exist_ok=True)
        tasks_path.write_text('{"id": "task-001"}\n')
        sync.commit("Initial sync")
        sync.push()

        # Create local change
        tasks_path.write_text('{"id": "task-001"}\n{"id": "task-002"}\n')
        sync.commit("Local change")

        # Create different remote change
        second_clone = local_repo.parent / "second_clone"
        subprocess.run(
            ["git", "clone", str(remote_repo), str(second_clone)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        subprocess.run(
            ["git", "checkout", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        tasks_in_clone = second_clone / ".cub" / "tasks.jsonl"
        tasks_in_clone.write_text(
            '{"id": "task-001"}\n'
            '{"id": "task-003"}\n'
        )
        subprocess.run(["git", "add", "."], cwd=second_clone, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Remote change"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "cub-sync"],
            cwd=second_clone,
            capture_output=True,
            check=True,
        )

        # Status should be diverged
        status = sync.get_status()

        assert status == SyncStatus.DIVERGED

    def test_status_handles_fetch_failure_gracefully(
        self, git_repo_with_remote: tuple[Path, Path]
    ) -> None:
        """get_status handles fetch failures gracefully."""
        local_repo, _ = git_repo_with_remote
        sync = SyncService(project_dir=local_repo)
        sync.initialize()

        # Remove remote to cause fetch to fail
        subprocess.run(
            ["git", "remote", "remove", "origin"],
            cwd=local_repo,
            capture_output=True,
            check=True,
        )

        # Should handle gracefully
        status = sync.get_status()

        assert status == SyncStatus.NO_REMOTE
