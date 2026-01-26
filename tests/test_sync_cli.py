"""
Tests for the sync CLI command.

Tests cover:
- Basic sync (commit)
- Pull from remote
- Push to remote
- Status command
- Init command
- Error handling
- Offline scenarios
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cub.cli.sync import app
from cub.core.sync import SyncResult, SyncState, SyncStatus
from cub.core.sync.service import GitError

runner = CliRunner()


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

    # Create initial commit
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    return repo


@pytest.fixture
def initialized_sync_repo(git_repo: Path) -> Path:
    """Create a git repo with sync branch initialized and tasks file."""
    # Create tasks file
    tasks_file = git_repo / ".cub" / "tasks.jsonl"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    tasks_file.write_text('{"id": "cub-001", "title": "Test task"}\n')

    # Initialize sync using subprocess to avoid mocking
    from cub.core.sync import SyncService

    sync = SyncService(project_dir=git_repo)
    sync.initialize()
    sync.commit("Initial tasks")

    return git_repo


class TestSyncInit:
    """Tests for 'cub sync --init' command."""

    def test_init_creates_sync_branch(self, git_repo: Path, monkeypatch) -> None:
        """Init command creates the sync branch."""
        monkeypatch.chdir(git_repo)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "Initialized sync branch: cub-sync" in result.stdout

        # Verify branch exists
        check = subprocess.run(
            ["git", "show-ref", "--verify", "refs/heads/cub-sync"],
            cwd=git_repo,
            capture_output=True,
        )
        assert check.returncode == 0

    def test_init_with_custom_branch_name(self, git_repo: Path, monkeypatch) -> None:
        """Init command accepts custom branch name."""
        monkeypatch.chdir(git_repo)

        result = runner.invoke(app, ["init", "--branch", "my-sync"])

        assert result.exit_code == 0
        assert "Initialized sync branch: my-sync" in result.stdout

        # Verify custom branch exists
        check = subprocess.run(
            ["git", "show-ref", "--verify", "refs/heads/my-sync"],
            cwd=git_repo,
            capture_output=True,
        )
        assert check.returncode == 0

    def test_init_already_initialized(self, initialized_sync_repo: Path, monkeypatch) -> None:
        """Init command handles already initialized case gracefully."""
        monkeypatch.chdir(initialized_sync_repo)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 1
        assert "already exists" in result.stdout

    def test_init_not_in_git_repo(self, tmp_path: Path, monkeypatch) -> None:
        """Init command fails gracefully when not in git repo."""
        not_a_repo = tmp_path / "not-git"
        not_a_repo.mkdir()
        monkeypatch.chdir(not_a_repo)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 1
        assert "Not a git repository" in result.stdout or "Error" in result.stdout


class TestSyncDefault:
    """Tests for 'cub sync' command (default commit behavior)."""

    def test_sync_commits_task_state(self, initialized_sync_repo: Path, monkeypatch) -> None:
        """Sync command commits task state."""
        monkeypatch.chdir(initialized_sync_repo)

        # Modify tasks file
        tasks_file = initialized_sync_repo / ".cub" / "tasks.jsonl"
        tasks_file.write_text('{"id": "cub-002", "title": "New task"}\n')

        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "Committed:" in result.stdout

    def test_sync_not_initialized(self, git_repo: Path, monkeypatch) -> None:
        """Sync command fails if not initialized."""
        monkeypatch.chdir(git_repo)

        # Create tasks file but don't initialize
        tasks_file = git_repo / ".cub" / "tasks.jsonl"
        tasks_file.parent.mkdir(parents=True, exist_ok=True)
        tasks_file.write_text('{"id": "cub-001", "title": "Test"}\n')

        result = runner.invoke(app, [])

        assert result.exit_code == 1
        assert "not initialized" in result.stdout

    def test_sync_with_custom_message(self, initialized_sync_repo: Path, monkeypatch) -> None:
        """Sync command accepts custom commit message."""
        monkeypatch.chdir(initialized_sync_repo)

        # Modify tasks file
        tasks_file = initialized_sync_repo / ".cub" / "tasks.jsonl"
        tasks_file.write_text('{"id": "cub-003", "title": "Another task"}\n')

        result = runner.invoke(app, ["--message", "Custom commit message"])

        assert result.exit_code == 0
        assert "Committed:" in result.stdout

        # Verify commit message (check git log)
        log_result = subprocess.run(
            ["git", "log", "-1", "--pretty=%s", "cub-sync"],
            cwd=initialized_sync_repo,
            capture_output=True,
            text=True,
        )
        assert "Custom commit message" in log_result.stdout

    def test_sync_no_changes(self, initialized_sync_repo: Path, monkeypatch) -> None:
        """Sync command handles no changes gracefully."""
        monkeypatch.chdir(initialized_sync_repo)

        # Run sync without modifying tasks
        result = runner.invoke(app, [])

        # Should succeed with "no changes" message
        assert result.exit_code == 0 or "No changes" in result.stdout


class TestSyncPull:
    """Tests for 'cub sync --pull' command."""

    def test_pull_without_remote(self, initialized_sync_repo: Path, monkeypatch) -> None:
        """Pull command handles missing remote gracefully."""
        monkeypatch.chdir(initialized_sync_repo)

        result = runner.invoke(app, ["--pull"])

        # When there's no valid remote, git fetch will fail
        # This is expected - the command should handle it and show an error
        assert "Pull failed" in result.stdout or "No remote" in result.stdout
        # Error is expected when remote doesn't exist
        assert result.exit_code == 1

    def test_pull_when_up_to_date(self, initialized_sync_repo: Path, monkeypatch) -> None:
        """Pull command handles up-to-date case."""
        monkeypatch.chdir(initialized_sync_repo)

        # Add a fake remote (local repo)
        subprocess.run(
            ["git", "remote", "add", "origin", str(initialized_sync_repo)],
            cwd=initialized_sync_repo,
            capture_output=True,
        )

        result = runner.invoke(app, ["--pull"])

        assert result.exit_code == 0
        # Should indicate up to date or no remote branch
        assert any(
            x in result.stdout.lower()
            for x in ["up to date", "no remote", "nothing to pull"]
        )

    @patch("cub.cli.sync.SyncService")
    def test_pull_merges_remote_changes(
        self, mock_service_class, tmp_path: Path, monkeypatch
    ) -> None:
        """Pull command merges remote changes."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.is_initialized.return_value = True

        # Simulate successful pull with updates
        mock_service.pull.return_value = SyncResult(
            success=True,
            operation="pull",
            message="Merged changes",
            tasks_updated=3,
            conflicts=[],
        )

        mock_service.commit.return_value = "abc123456"

        result = runner.invoke(app, ["--pull"])

        assert result.exit_code == 0
        assert "Merged 3 tasks" in result.stdout
        mock_service.pull.assert_called_once()

    @patch("cub.cli.sync.SyncService")
    def test_pull_with_conflicts(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Pull command handles conflicts."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.is_initialized.return_value = True

        # Simulate pull with conflicts
        from cub.core.sync import SyncConflict

        conflicts = [
            SyncConflict(
                task_id="cub-001",
                resolution="last_write_wins",
                winner="remote",
            )
        ]

        mock_service.pull.return_value = SyncResult(
            success=True,
            operation="pull",
            message="Merged with conflicts",
            tasks_updated=2,
            conflicts=conflicts,
        )

        mock_service.commit.return_value = "def456789"

        result = runner.invoke(app, ["--pull"])

        assert result.exit_code == 0
        assert "Merged 2 tasks" in result.stdout
        assert "Resolved 1 conflict" in result.stdout

    @patch("cub.cli.sync.SyncService")
    def test_pull_fails(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Pull command handles pull failure."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.is_initialized.return_value = True

        # Simulate pull failure
        mock_service.pull.return_value = SyncResult(
            success=False,
            operation="pull",
            message="Network error",
        )

        result = runner.invoke(app, ["--pull"])

        assert result.exit_code == 1
        assert "Pull failed" in result.stdout


class TestSyncPush:
    """Tests for 'cub sync --push' command."""

    @patch("cub.cli.sync.SyncService")
    def test_push_succeeds(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Push command pushes to remote."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.is_initialized.return_value = True
        mock_service.commit.return_value = "abc123456"
        mock_service.push.return_value = True

        result = runner.invoke(app, ["--push"])

        assert result.exit_code == 0
        assert "Pushed to remote" in result.stdout
        mock_service.push.assert_called_once()

    @patch("cub.cli.sync.SyncService")
    def test_push_fails(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Push command handles push failure."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.is_initialized.return_value = True
        mock_service.commit.return_value = "abc123456"
        mock_service.push.return_value = False

        result = runner.invoke(app, ["--push"])

        assert result.exit_code == 1
        assert "Push failed" in result.stdout

    @patch("cub.cli.sync.SyncService")
    def test_pull_and_push(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Sync command can pull and push in one operation."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.is_initialized.return_value = True

        mock_service.pull.return_value = SyncResult(
            success=True,
            operation="pull",
            message="Up to date",
            tasks_updated=0,
        )
        mock_service.commit.return_value = "abc123456"
        mock_service.push.return_value = True

        result = runner.invoke(app, ["--pull", "--push"])

        assert result.exit_code == 0
        assert "Pulled" in result.stdout or "up to date" in result.stdout.lower()
        assert "Pushed to remote" in result.stdout
        mock_service.pull.assert_called_once()
        mock_service.push.assert_called_once()


class TestSyncStatus:
    """Tests for 'cub sync status' command."""

    @patch("cub.cli.sync.SyncService")
    def test_status_up_to_date(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Status command shows up-to-date status."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_status.return_value = SyncStatus.UP_TO_DATE
        mock_service.get_state.return_value = SyncState(
            branch_name="cub-sync",
            tasks_file=".cub/tasks.jsonl",
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Up to date" in result.stdout

    @patch("cub.cli.sync.SyncService")
    def test_status_ahead(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Status command shows ahead status with actionable message."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_status.return_value = SyncStatus.AHEAD
        mock_service.get_state.return_value = SyncState(
            branch_name="cub-sync",
            tasks_file=".cub/tasks.jsonl",
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "ahead" in result.stdout.lower() or "not pushed" in result.stdout.lower()
        assert "--push" in result.stdout  # Should suggest pushing

    @patch("cub.cli.sync.SyncService")
    def test_status_behind(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Status command shows behind status with actionable message."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_status.return_value = SyncStatus.BEHIND
        mock_service.get_state.return_value = SyncState(
            branch_name="cub-sync",
            tasks_file=".cub/tasks.jsonl",
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "behind" in result.stdout.lower() or "remote changes" in result.stdout.lower()
        assert "--pull" in result.stdout  # Should suggest pulling

    @patch("cub.cli.sync.SyncService")
    def test_status_diverged(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Status command shows diverged status."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_status.return_value = SyncStatus.DIVERGED
        mock_service.get_state.return_value = SyncState(
            branch_name="cub-sync",
            tasks_file=".cub/tasks.jsonl",
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "diverged" in result.stdout.lower()
        assert "--pull" in result.stdout  # Should suggest pulling to merge

    @patch("cub.cli.sync.SyncService")
    def test_status_no_remote(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Status command shows no remote status."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_status.return_value = SyncStatus.NO_REMOTE
        mock_service.get_state.return_value = SyncState(
            branch_name="cub-sync",
            tasks_file=".cub/tasks.jsonl",
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "No remote" in result.stdout
        assert "--push" in result.stdout  # Should suggest pushing to create remote

    @patch("cub.cli.sync.SyncService")
    def test_status_uninitialized(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Status command shows uninitialized status."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_status.return_value = SyncStatus.UNINITIALIZED
        mock_service.get_state.return_value = SyncState(
            branch_name="cub-sync",
            tasks_file=".cub/tasks.jsonl",
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 1
        assert "Not initialized" in result.stdout
        assert "init" in result.stdout  # Should suggest initialization (either "init" or "--init")

    @patch("cub.cli.sync.SyncService")
    def test_status_verbose(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Status command shows detailed info with --verbose."""
        monkeypatch.chdir(tmp_path)

        # Setup mock
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.get_status.return_value = SyncStatus.UP_TO_DATE

        from datetime import datetime

        mock_service.get_state.return_value = SyncState(
            branch_name="cub-sync",
            tasks_file=".cub/tasks.jsonl",
            last_commit_sha="abc123456",
            last_sync_at=datetime(2024, 1, 15, 10, 30, 0),
            last_push_at=datetime(2024, 1, 15, 10, 35, 0),
        )

        result = runner.invoke(app, ["status", "--verbose"])

        assert result.exit_code == 0
        assert "abc12345" in result.stdout  # Truncated SHA
        assert "2024-01-15" in result.stdout  # Date


class TestSyncErrorHandling:
    """Tests for error handling in sync commands."""

    @patch("cub.cli.sync.SyncService")
    def test_git_error_handling(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Sync command handles git errors gracefully."""
        monkeypatch.chdir(tmp_path)

        # Setup mock to raise GitError
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.is_initialized.return_value = True
        mock_service.commit.side_effect = GitError(
            "Git command failed",
            command=["git", "commit"],
            stderr="fatal: something went wrong",
        )

        result = runner.invoke(app, [])

        assert result.exit_code == 1
        assert "Git error" in result.stdout

    @patch("cub.cli.sync.SyncService")
    def test_runtime_error_handling(self, mock_service_class, tmp_path: Path, monkeypatch) -> None:
        """Sync command handles runtime errors."""
        monkeypatch.chdir(tmp_path)

        # Setup mock to raise RuntimeError
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.is_initialized.return_value = True
        mock_service.commit.side_effect = RuntimeError("Tasks file not found")

        result = runner.invoke(app, [])

        assert result.exit_code == 1
        assert "Error" in result.stdout or "failed" in result.stdout.lower()


class TestSyncOfflineScenarios:
    """Tests for offline scenarios (no network, no remote)."""

    def test_offline_sync_works(self, initialized_sync_repo: Path, monkeypatch) -> None:
        """Sync works offline (no remote configured)."""
        monkeypatch.chdir(initialized_sync_repo)

        # Modify tasks file
        tasks_file = initialized_sync_repo / ".cub" / "tasks.jsonl"
        tasks_file.write_text('{"id": "cub-offline", "title": "Offline task"}\n')

        # Sync without remote should work
        result = runner.invoke(app, [])

        assert result.exit_code == 0
        assert "Committed:" in result.stdout

    def test_offline_status_works(self, initialized_sync_repo: Path, monkeypatch) -> None:
        """Status works offline."""
        monkeypatch.chdir(initialized_sync_repo)

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        # Should show status even without remote
        assert any(x in result.stdout for x in ["No remote", "Up to date"])

    def test_push_without_remote_fails_gracefully(
        self, initialized_sync_repo: Path, monkeypatch
    ) -> None:
        """Push without remote configured fails with clear message."""
        monkeypatch.chdir(initialized_sync_repo)

        # Modify tasks and try to push
        tasks_file = initialized_sync_repo / ".cub" / "tasks.jsonl"
        tasks_file.write_text('{"id": "cub-push", "title": "Push task"}\n')

        result = runner.invoke(app, ["--push"])

        assert result.exit_code == 1
        assert "failed" in result.stdout.lower() or "error" in result.stdout.lower()
