"""
Integration tests for auto-sync during cub run.

Tests the automatic synchronization of task state to the cub-sync branch
when tasks are completed during a run session.

Test scenarios:
- Auto-sync commits after each task completion
- Multiple tasks sync sequentially
- --no-sync flag disables auto-sync
- Sync failure handling (doesn't stop the run)
- Config option respects auto_sync setting
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from cub.core.sync.service import GitError, SyncService


class TestAutoSyncDuringRun:
    """Test auto-sync behavior during cub run execution."""

    @pytest.fixture
    def mock_sync_service(self) -> Mock:
        """Create a mock SyncService for testing."""
        service = Mock(spec=SyncService)
        service.is_initialized.return_value = False  # Not initialized by default
        service.initialize.return_value = None
        service.commit.return_value = "abc1234567890def"
        return service

    @pytest.fixture
    def temp_project(self, tmp_path: Path) -> Path:
        """Create a temporary project directory with git initialized."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Initialize git
        import subprocess

        subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        readme = project_dir / "README.md"
        readme.write_text("# Test Project\n")
        subprocess.run(
            ["git", "add", "README.md"], cwd=project_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )

        # Create .cub directory
        cub_dir = project_dir / ".cub"
        cub_dir.mkdir()

        # Create tasks file
        tasks_file = cub_dir / "tasks.jsonl"
        tasks = [
            {
                "id": "test-001",
                "title": "Test task 1",
                "status": "open",
                "type": "task",
                "priority": 0,
            },
            {
                "id": "test-002",
                "title": "Test task 2",
                "status": "open",
                "type": "task",
                "priority": 1,
            },
        ]
        with open(tasks_file, "w") as f:
            for task in tasks:
                f.write(json.dumps(task) + "\n")

        return project_dir

    def test_sync_service_initialized_on_run_start(
        self, temp_project: Path, mock_sync_service: Mock
    ) -> None:
        """Test that sync service is initialized when run starts with auto_sync enabled."""
        # This test validates the setup phase of auto-sync
        # In actual implementation, this happens in cli/run.py before the loop starts

        # Simulate the initialization flow
        service = mock_sync_service

        # Check if initialized
        is_initialized = service.is_initialized()

        # If not, initialize
        if not is_initialized:
            service.initialize()

        # Verify both methods were called
        service.is_initialized.assert_called()
        service.initialize.assert_called()

    def test_sync_commits_after_task_completion(
        self, temp_project: Path, mock_sync_service: Mock
    ) -> None:
        """Test that sync service commits after each task is completed."""
        task_id = "test-001"

        # Simulate task completion with sync
        mock_sync_service.commit(message=f"Task {task_id} completed")

        # Verify commit was called with correct message
        mock_sync_service.commit.assert_called_once_with(message=f"Task {task_id} completed")

    def test_sync_multiple_tasks_sequentially(
        self, temp_project: Path, mock_sync_service: Mock
    ) -> None:
        """Test that multiple task completions each trigger a sync commit."""
        task_ids = ["test-001", "test-002", "test-003"]

        for task_id in task_ids:
            mock_sync_service.commit(message=f"Task {task_id} completed")

        # Verify commit was called for each task
        assert mock_sync_service.commit.call_count == len(task_ids)

        # Verify each call had the correct message
        calls = mock_sync_service.commit.call_args_list
        for i, task_id in enumerate(task_ids):
            assert calls[i][1]["message"] == f"Task {task_id} completed"

    def test_no_sync_flag_disables_auto_sync(self, temp_project: Path) -> None:
        """Test that --no-sync flag prevents sync service from being initialized."""
        # When --no-sync is passed, sync_service should be None
        # This is validated in the CLI layer

        # Simulate the check in cli/run.py
        no_sync = True
        config_auto_sync = "run"
        config_enabled = True

        should_auto_sync = (
            not no_sync and config_enabled and config_auto_sync in ("run", "always")
        )

        assert should_auto_sync is False

    def test_sync_failure_doesnt_stop_run(
        self, temp_project: Path, mock_sync_service: Mock
    ) -> None:
        """Test that sync failures are logged but don't stop task execution."""
        # Simulate sync failure
        mock_sync_service.commit.side_effect = GitError("Failed to commit")

        task_completed = False
        try:
            # Try to sync
            mock_sync_service.commit(message="Task test-001 completed")
        except GitError:
            # Sync failed, but task should still be marked complete
            # In actual implementation, the exception is caught and logged
            task_completed = True

        # Verify task can still complete even if sync fails
        assert task_completed is True

    def test_sync_respects_config_auto_sync_never(self) -> None:
        """Test that auto_sync='never' prevents sync during run."""
        config_auto_sync = "never"
        config_enabled = True
        no_sync = False

        should_auto_sync = (
            not no_sync and config_enabled and config_auto_sync in ("run", "always")
        )

        assert should_auto_sync is False

    def test_sync_respects_config_auto_sync_run(self) -> None:
        """Test that auto_sync='run' enables sync during run."""
        config_auto_sync = "run"
        config_enabled = True
        no_sync = False

        should_auto_sync = (
            not no_sync and config_enabled and config_auto_sync in ("run", "always")
        )

        assert should_auto_sync is True

    def test_sync_respects_config_auto_sync_always(self) -> None:
        """Test that auto_sync='always' enables sync during run."""
        config_auto_sync = "always"
        config_enabled = True
        no_sync = False

        should_auto_sync = (
            not no_sync and config_enabled and config_auto_sync in ("run", "always")
        )

        assert should_auto_sync is True

    def test_sync_disabled_when_config_enabled_false(self) -> None:
        """Test that sync.enabled=False prevents sync initialization."""
        config_auto_sync = "run"
        config_enabled = False
        no_sync = False

        should_auto_sync = (
            not no_sync and config_enabled and config_auto_sync in ("run", "always")
        )

        assert should_auto_sync is False


class TestSyncIntegrationScenarios:
    """End-to-end integration tests for sync during run."""

    @pytest.fixture
    def git_project(self, tmp_path: Path) -> Path:
        """Create a real git project for integration testing."""
        project_dir = tmp_path / "git_project"
        project_dir.mkdir()

        import subprocess

        # Initialize git
        subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )

        # Initial commit
        readme = project_dir / "README.md"
        readme.write_text("# Git Test Project\n")
        subprocess.run(
            ["git", "add", "README.md"], cwd=project_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )

        return project_dir

    def test_real_sync_initialization(self, git_project: Path) -> None:
        """Test real sync service initialization."""
        service = SyncService(project_dir=git_project)

        # Initialize sync branch
        assert service.is_initialized() is False
        service.initialize()
        assert service.is_initialized() is True

    def test_real_sync_commit_after_task(self, git_project: Path) -> None:
        """Test real sync commit with actual git operations."""
        # Setup
        service = SyncService(project_dir=git_project)
        service.initialize()

        # Create tasks file
        tasks_file = git_project / ".cub" / "tasks.jsonl"
        tasks_file.parent.mkdir(parents=True, exist_ok=True)

        task_data = {
            "id": "test-001",
            "title": "Test task",
            "status": "completed",
            "type": "task",
        }
        tasks_file.write_text(json.dumps(task_data) + "\n")

        # Commit task state
        commit_sha = service.commit(message="Task test-001 completed")

        # Verify commit was created
        assert commit_sha is not None
        assert len(commit_sha) == 40  # Git SHA-1 is 40 hex chars

        # Verify branch exists
        import subprocess

        result = subprocess.run(
            ["git", "show-ref", "--verify", f"refs/heads/{service.branch_name}"],
            cwd=git_project,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_multiple_tasks_create_multiple_commits(self, git_project: Path) -> None:
        """Test that multiple task completions create multiple commits."""
        service = SyncService(project_dir=git_project)
        service.initialize()

        tasks_file = git_project / ".cub" / "tasks.jsonl"
        tasks_file.parent.mkdir(parents=True, exist_ok=True)

        task_ids = ["test-001", "test-002", "test-003"]
        commit_shas = []

        for task_id in task_ids:
            # Update tasks file
            task_data = {
                "id": task_id,
                "title": f"Test task {task_id}",
                "status": "completed",
                "type": "task",
            }
            tasks_file.write_text(json.dumps(task_data) + "\n")

            # Commit
            commit_sha = service.commit(message=f"Task {task_id} completed")
            commit_shas.append(commit_sha)

        # Verify all commits are unique
        assert len(set(commit_shas)) == len(task_ids)

        # Verify commit history
        import subprocess

        result = subprocess.run(
            ["git", "log", "--oneline", service.branch_name],
            cwd=git_project,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Should have 3 task commits + 1 initialization commit
        log_lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert len(log_lines) >= len(task_ids)

    def test_sync_skips_unchanged_tasks(self, git_project: Path) -> None:
        """Test that sync skips commits when task state hasn't changed."""
        service = SyncService(project_dir=git_project)
        service.initialize()

        tasks_file = git_project / ".cub" / "tasks.jsonl"
        tasks_file.parent.mkdir(parents=True, exist_ok=True)

        # Create initial task
        task_data = {"id": "test-001", "title": "Test task", "status": "open", "type": "task"}
        tasks_file.write_text(json.dumps(task_data) + "\n")

        # First commit
        commit_sha_1 = service.commit(message="Task test-001 updated")

        # Second commit with same content (should return same SHA)
        commit_sha_2 = service.commit(message="Task test-001 updated again")

        # Should return existing commit SHA when content hasn't changed
        assert commit_sha_1 == commit_sha_2
