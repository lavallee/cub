"""
Tests for WorktreeManager.

Tests git worktree operations including creation, listing, removal,
and cleanup of merged branches.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import GitCommandError, InvalidGitRepositoryError

from cub.core.worktree import (
    Worktree,
    WorktreeError,
    WorktreeLockError,
    WorktreeManager,
    WorktreeNotFoundError,
)


@pytest.fixture
def mock_repo(tmp_path):
    """Provide a mock git.Repo object."""
    repo = MagicMock()
    repo.working_dir = str(tmp_path / "repo")
    repo.git = MagicMock()
    return repo


@pytest.fixture
def worktree_manager(mock_repo, tmp_path):
    """Provide a WorktreeManager instance with mocked repo."""
    with patch("cub.core.worktree.manager.Repo") as mock_repo_class:
        mock_repo_class.return_value = mock_repo
        manager = WorktreeManager(tmp_path / "repo")
        return manager


class TestWorktreeManagerInit:
    """Test WorktreeManager initialization."""

    def test_init_with_valid_repo(self, tmp_path):
        """Test initialization with a valid git repository."""
        with patch("cub.core.worktree.manager.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.working_dir = str(tmp_path)
            mock_repo_class.return_value = mock_repo

            manager = WorktreeManager(tmp_path)

            assert manager.repo_path == tmp_path
            assert manager.repo == mock_repo
            assert manager.worktree_base == tmp_path / ".cub" / "worktrees"

    def test_init_with_invalid_repo(self, tmp_path):
        """Test initialization fails when not in a git repository."""
        with patch("cub.core.worktree.manager.Repo") as mock_repo_class:
            mock_repo_class.side_effect = InvalidGitRepositoryError()

            with pytest.raises(WorktreeError, match="Not a git repository"):
                WorktreeManager(tmp_path)

    def test_init_defaults_to_cwd(self):
        """Test initialization defaults to current working directory."""
        with patch("cub.core.worktree.manager.Repo") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.working_dir = "/current/dir"
            mock_repo_class.return_value = mock_repo

            with patch("cub.core.worktree.manager.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path("/current/dir")
                manager = WorktreeManager()

                assert manager.repo_path == Path("/current/dir")


class TestWorktreeCreate:
    """Test worktree creation."""

    def test_create_with_new_branch(self, worktree_manager, mock_repo, tmp_path):
        """Test creating a worktree with a new branch."""
        task_id = "cub-001"
        worktree_path = worktree_manager.worktree_base / task_id

        # Mock git worktree add
        mock_repo.git.execute = MagicMock()

        # Mock Repo for the new worktree
        with patch("cub.core.worktree.manager.Repo") as mock_worktree_repo_class:
            mock_worktree_repo = MagicMock()
            mock_worktree_repo.head.commit.hexsha = "abc123"
            mock_worktree_repo_class.return_value = mock_worktree_repo

            worktree = worktree_manager.create(task_id)

            # Verify git command (no HEAD needed with -b)
            mock_repo.git.execute.assert_called_once_with(
                ["worktree", "add", "-b", task_id, str(worktree_path)]
            )

            # Verify returned worktree
            assert worktree.path == worktree_path
            assert worktree.branch == task_id
            assert worktree.commit == "abc123"
            assert not worktree.is_bare
            assert not worktree.is_locked

    def test_create_with_existing_branch(self, worktree_manager, mock_repo):
        """Test creating a worktree with an existing branch."""
        task_id = "cub-002"
        branch = "feature/existing"
        worktree_path = worktree_manager.worktree_base / task_id

        mock_repo.git.execute = MagicMock()

        with patch("cub.core.worktree.manager.Repo") as mock_worktree_repo_class:
            mock_worktree_repo = MagicMock()
            mock_worktree_repo.head.commit.hexsha = "def456"
            mock_worktree_repo_class.return_value = mock_worktree_repo

            worktree = worktree_manager.create(task_id, branch=branch, create_branch=False)

            # Verify git command (no -b flag, no HEAD needed when branch is specified)
            mock_repo.git.execute.assert_called_once_with(
                ["worktree", "add", branch, str(worktree_path)]
            )

            assert worktree.branch == branch

    def test_create_without_branch(self, worktree_manager, mock_repo):
        """Test creating a detached HEAD worktree."""
        task_id = "cub-003"
        worktree_path = worktree_manager.worktree_base / task_id

        mock_repo.git.execute = MagicMock()

        with patch("cub.core.worktree.manager.Repo") as mock_worktree_repo_class:
            mock_worktree_repo = MagicMock()
            mock_worktree_repo.head.commit.hexsha = "ghi789"
            mock_worktree_repo_class.return_value = mock_worktree_repo

            worktree = worktree_manager.create(task_id, branch=None, create_branch=False)

            # Verify git command
            mock_repo.git.execute.assert_called_once_with(
                ["worktree", "add", str(worktree_path), "HEAD"]
            )

            assert worktree.branch is None

    def test_create_fails_if_exists(self, worktree_manager, tmp_path):
        """Test creation fails if worktree directory already exists."""
        task_id = "cub-004"
        worktree_path = worktree_manager.worktree_base / task_id
        worktree_path.mkdir(parents=True)

        with pytest.raises(WorktreeError, match="already exists"):
            worktree_manager.create(task_id)

    def test_create_git_command_error(self, worktree_manager, mock_repo):
        """Test creation handles git command errors."""
        task_id = "cub-005"

        mock_repo.git.execute = MagicMock(
            side_effect=GitCommandError("worktree add", stderr="fatal: invalid reference")
        )

        with pytest.raises(WorktreeError, match="Failed to create worktree"):
            worktree_manager.create(task_id)


class TestWorktreeList:
    """Test listing worktrees."""

    def test_list_multiple_worktrees(self, worktree_manager, mock_repo, tmp_path):
        """Test listing multiple worktrees."""
        # Mock git worktree list --porcelain output
        porcelain_output = """worktree /repo
HEAD abc123
branch refs/heads/main

worktree /repo/.cub/worktrees/cub-001
HEAD def456
branch refs/heads/cub-001

worktree /repo/.cub/worktrees/cub-002
HEAD ghi789
"""

        mock_repo.git.worktree = MagicMock(return_value=porcelain_output)

        worktrees = worktree_manager.list()

        assert len(worktrees) == 3

        # Main worktree
        assert worktrees[0].path == Path("/repo")
        assert worktrees[0].branch == "refs/heads/main"
        assert worktrees[0].commit == "abc123"
        assert not worktrees[0].is_bare
        assert not worktrees[0].is_locked

        # Task worktree with branch
        assert worktrees[1].path == Path("/repo/.cub/worktrees/cub-001")
        assert worktrees[1].branch == "refs/heads/cub-001"
        assert worktrees[1].commit == "def456"

        # Task worktree without branch (detached HEAD)
        assert worktrees[2].path == Path("/repo/.cub/worktrees/cub-002")
        assert worktrees[2].branch is None
        assert worktrees[2].commit == "ghi789"

    def test_list_with_locked_worktree(self, worktree_manager, mock_repo):
        """Test listing includes locked worktrees."""
        porcelain_output = """worktree /repo
HEAD abc123
branch refs/heads/main

worktree /repo/.cub/worktrees/cub-001
HEAD def456
branch refs/heads/cub-001
locked

"""

        mock_repo.git.worktree = MagicMock(return_value=porcelain_output)

        worktrees = worktree_manager.list()

        assert len(worktrees) == 2
        assert worktrees[1].is_locked

    def test_list_with_bare_repo(self, worktree_manager, mock_repo):
        """Test listing includes bare repository."""
        porcelain_output = """worktree /repo
bare

"""

        mock_repo.git.worktree = MagicMock(return_value=porcelain_output)

        worktrees = worktree_manager.list()

        assert len(worktrees) == 1
        assert worktrees[0].is_bare

    def test_list_empty(self, worktree_manager, mock_repo):
        """Test listing when no worktrees exist."""
        mock_repo.git.worktree = MagicMock(return_value="")

        worktrees = worktree_manager.list()

        assert len(worktrees) == 0

    def test_list_git_command_error(self, worktree_manager, mock_repo):
        """Test listing handles git command errors."""
        mock_repo.git.worktree = MagicMock(
            side_effect=GitCommandError("worktree list", stderr="fatal: not a git repository")
        )

        with pytest.raises(WorktreeError, match="Failed to list worktrees"):
            worktree_manager.list()


class TestWorktreeRemove:
    """Test worktree removal."""

    def test_remove_existing_worktree(self, worktree_manager, mock_repo, tmp_path):
        """Test removing an existing worktree."""
        worktree_path = tmp_path / ".cub" / "worktrees" / "cub-001"
        worktree_path.mkdir(parents=True)

        # Mock list() to return the worktree
        with patch.object(worktree_manager, "list") as mock_list:
            mock_list.return_value = [
                Worktree(
                    path=worktree_path,
                    branch="refs/heads/cub-001",
                    commit="abc123",
                    is_bare=False,
                    is_locked=False,
                )
            ]

            mock_repo.git.execute = MagicMock()

            worktree_manager.remove(worktree_path)

            mock_repo.git.execute.assert_called_once_with(
                ["worktree", "remove", str(worktree_path)]
            )

    def test_remove_with_force(self, worktree_manager, mock_repo, tmp_path):
        """Test removing a worktree with force flag."""
        worktree_path = tmp_path / ".cub" / "worktrees" / "cub-002"
        worktree_path.mkdir(parents=True)

        with patch.object(worktree_manager, "list") as mock_list:
            mock_list.return_value = [
                Worktree(
                    path=worktree_path,
                    branch="refs/heads/cub-002",
                    commit="def456",
                    is_bare=False,
                    is_locked=True,
                )
            ]

            mock_repo.git.execute = MagicMock()

            worktree_manager.remove(worktree_path, force=True)

            mock_repo.git.execute.assert_called_once_with(
                ["worktree", "remove", "--force", str(worktree_path)]
            )

    def test_remove_nonexistent_path(self, worktree_manager):
        """Test removing a path that doesn't exist."""
        nonexistent_path = Path("/nonexistent/path")

        with pytest.raises(WorktreeNotFoundError, match="not found"):
            worktree_manager.remove(nonexistent_path)

    def test_remove_not_a_worktree(self, worktree_manager, tmp_path):
        """Test removing a path that's not a worktree."""
        not_worktree_path = tmp_path / "not_worktree"
        not_worktree_path.mkdir()

        with patch.object(worktree_manager, "list") as mock_list:
            mock_list.return_value = []

            with pytest.raises(WorktreeNotFoundError, match="Not a worktree"):
                worktree_manager.remove(not_worktree_path)

    def test_remove_bare_repo(self, worktree_manager, tmp_path):
        """Test removing bare repository worktree is prevented."""
        bare_path = tmp_path / "repo"
        bare_path.mkdir()

        with patch.object(worktree_manager, "list") as mock_list:
            mock_list.return_value = [
                Worktree(path=bare_path, branch=None, commit="abc123", is_bare=True)
            ]

            with pytest.raises(WorktreeError, match="Cannot remove bare repository"):
                worktree_manager.remove(bare_path)

    def test_remove_locked_without_force(self, worktree_manager, tmp_path):
        """Test removing locked worktree without force fails."""
        locked_path = tmp_path / ".cub" / "worktrees" / "cub-003"
        locked_path.mkdir(parents=True)

        with patch.object(worktree_manager, "list") as mock_list:
            mock_list.return_value = [
                Worktree(
                    path=locked_path,
                    branch="refs/heads/cub-003",
                    commit="ghi789",
                    is_bare=False,
                    is_locked=True,
                )
            ]

            with pytest.raises(WorktreeLockError, match="locked"):
                worktree_manager.remove(locked_path, force=False)

    def test_remove_git_command_error(self, worktree_manager, mock_repo, tmp_path):
        """Test removal handles git command errors."""
        worktree_path = tmp_path / ".cub" / "worktrees" / "cub-004"
        worktree_path.mkdir(parents=True)

        with patch.object(worktree_manager, "list") as mock_list:
            mock_list.return_value = [
                Worktree(
                    path=worktree_path,
                    branch="refs/heads/cub-004",
                    commit="jkl012",
                    is_bare=False,
                    is_locked=False,
                )
            ]

            mock_repo.git.execute = MagicMock(
                side_effect=GitCommandError("worktree remove", stderr="fatal: error")
            )

            with pytest.raises(WorktreeError, match="Failed to remove worktree"):
                worktree_manager.remove(worktree_path)


class TestWorktreeGetForTask:
    """Test getting worktree for a task."""

    def test_get_existing_worktree(self, worktree_manager, tmp_path):
        """Test getting a worktree that already exists."""
        task_id = "cub-001"
        worktree_path = worktree_manager.worktree_base / task_id
        worktree_path.mkdir(parents=True)

        result_path = worktree_manager.get_for_task(task_id)

        assert result_path == worktree_path

    def test_get_creates_worktree_if_missing(self, worktree_manager, mock_repo):
        """Test getting a worktree creates it if missing."""
        task_id = "cub-002"
        worktree_path = worktree_manager.worktree_base / task_id

        with patch.object(worktree_manager, "create") as mock_create:
            mock_create.return_value = Worktree(
                path=worktree_path,
                branch=task_id,
                commit="abc123",
            )

            result_path = worktree_manager.get_for_task(task_id)

            mock_create.assert_called_once_with(task_id)
            assert result_path == worktree_path

    def test_get_without_create(self, worktree_manager):
        """Test getting a worktree with create_if_missing=False."""
        task_id = "cub-003"

        with pytest.raises(WorktreeNotFoundError, match="not found for task"):
            worktree_manager.get_for_task(task_id, create_if_missing=False)


class TestWorktreeCleanupMerged:
    """Test cleanup of merged branches."""

    def test_cleanup_removes_merged_worktrees(self, worktree_manager, mock_repo, tmp_path):
        """Test cleanup removes worktrees for merged branches."""
        # Mock git branch --merged
        mock_repo.git.branch = MagicMock(return_value="  feature-1\n  feature-2\n* main")

        # Mock list() to return worktrees
        worktree1_path = tmp_path / ".cub" / "worktrees" / "cub-001"
        worktree2_path = tmp_path / ".cub" / "worktrees" / "cub-002"
        worktree3_path = tmp_path / ".cub" / "worktrees" / "cub-003"

        with patch.object(worktree_manager, "list") as mock_list:
            mock_list.return_value = [
                Worktree(
                    path=tmp_path / "repo",
                    branch="refs/heads/main",
                    commit="abc123",
                    is_bare=False,
                ),
                Worktree(
                    path=worktree1_path,
                    branch="refs/heads/feature-1",
                    commit="def456",
                    is_bare=False,
                ),
                Worktree(
                    path=worktree2_path,
                    branch="refs/heads/feature-2",
                    commit="ghi789",
                    is_bare=False,
                ),
                Worktree(
                    path=worktree3_path,
                    branch="refs/heads/feature-3",
                    commit="jkl012",
                    is_bare=False,
                ),
            ]

            with patch.object(worktree_manager, "remove"):
                removed = worktree_manager.cleanup_merged()

                # Should remove feature-1 and feature-2 (merged)
                assert len(removed) == 2
                assert worktree1_path in removed
                assert worktree2_path in removed

    def test_cleanup_skips_locked_worktrees(self, worktree_manager, mock_repo, tmp_path):
        """Test cleanup skips locked worktrees."""
        mock_repo.git.branch = MagicMock(return_value="  feature-1")

        worktree_path = tmp_path / ".cub" / "worktrees" / "cub-001"

        with patch.object(worktree_manager, "list") as mock_list:
            mock_list.return_value = [
                Worktree(
                    path=worktree_path,
                    branch="refs/heads/feature-1",
                    commit="abc123",
                    is_bare=False,
                    is_locked=True,
                )
            ]

            with patch.object(worktree_manager, "remove") as mock_remove:
                mock_remove.side_effect = WorktreeLockError("locked")

                removed = worktree_manager.cleanup_merged()

                # Should skip locked worktree
                assert len(removed) == 0

    def test_cleanup_with_custom_base_branch(self, worktree_manager, mock_repo):
        """Test cleanup with custom base branch."""
        worktree_manager.cleanup_merged(base_branch="develop")

        mock_repo.git.branch.assert_called_once_with("--merged", "develop")

    def test_cleanup_git_command_error(self, worktree_manager, mock_repo):
        """Test cleanup handles git command errors."""
        mock_repo.git.branch = MagicMock(
            side_effect=GitCommandError("branch --merged", stderr="fatal: error")
        )

        with pytest.raises(WorktreeError, match="Failed to cleanup merged worktrees"):
            worktree_manager.cleanup_merged()


class TestWorktreePrune:
    """Test worktree pruning."""

    def test_prune_success(self, worktree_manager, mock_repo):
        """Test successful prune operation."""
        mock_repo.git.worktree = MagicMock()

        worktree_manager.prune()

        mock_repo.git.worktree.assert_called_once_with("prune")

    def test_prune_git_command_error(self, worktree_manager, mock_repo):
        """Test prune handles git command errors."""
        mock_repo.git.worktree = MagicMock(
            side_effect=GitCommandError("worktree prune", stderr="fatal: error")
        )

        with pytest.raises(WorktreeError, match="Failed to prune worktrees"):
            worktree_manager.prune()
