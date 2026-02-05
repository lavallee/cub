"""
Tests for ID collision prevention hooks.

Tests the pre-push hook verification logic that checks for counter
conflicts between local and remote sync branches.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.ids.hooks import (
    format_hook_message,
    verify_counters_before_push,
)
from cub.core.sync.models import CounterState


class TestVerifyCountersBeforePush:
    """Test suite for verify_counters_before_push()."""

    def test_no_sync_branch_allows_push(self, tmp_path: Path) -> None:
        """When sync branch isn't initialized, hook should allow push."""
        # Create a minimal git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create .cub directory
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()

        ok, message = verify_counters_before_push(project_dir=tmp_path)

        assert ok is True
        assert message == ""

    def test_no_remote_allows_push(self, tmp_path: Path, git_repo: Path) -> None:
        """When remote doesn't exist, hook should allow push."""
        with patch("cub.core.ids.hooks._fetch_remote_sync_branch") as mock_fetch:
            from cub.core.ids.hooks import GitError

            mock_fetch.side_effect = GitError("Remote not found")

            ok, message = verify_counters_before_push(project_dir=git_repo)

            assert ok is True
            assert message == ""

    def test_no_remote_counters_allows_push(self, tmp_path: Path) -> None:
        """When remote has no counters.json, hook should allow push."""
        # Mock sync service
        with patch("cub.core.ids.hooks.SyncService") as mock_sync_cls:
            mock_sync = MagicMock()
            mock_sync.is_initialized.return_value = True
            mock_sync_cls.return_value = mock_sync

            # Mock fetch succeeds
            with patch("cub.core.ids.hooks._fetch_remote_sync_branch"):
                # Mock remote counters returns None (no counters.json exists)
                with patch(
                    "cub.core.ids.hooks._read_remote_counters", return_value=None
                ):
                    # Even with high local IDs, push should be allowed
                    with patch(
                        "cub.core.ids.hooks._scan_local_task_ids",
                        return_value=(100, 50),
                    ):
                        ok, message = verify_counters_before_push(project_dir=tmp_path)

                        assert ok is True
                        assert message == ""

    def test_no_conflicts_allows_push(self, tmp_path: Path) -> None:
        """When no conflicts exist, hook should allow push."""
        # Mock sync service
        with patch("cub.core.ids.hooks.SyncService") as mock_sync_cls:
            mock_sync = MagicMock()
            mock_sync.is_initialized.return_value = True
            mock_sync_cls.return_value = mock_sync

            # Mock fetch succeeds
            with patch("cub.core.ids.hooks._fetch_remote_sync_branch"):
                # Mock remote counters at 10/5
                remote_counters = CounterState(spec_number=10, standalone_task_number=5)
                with patch(
                    "cub.core.ids.hooks._read_remote_counters", return_value=remote_counters
                ):
                    # Mock scan finds max 9/4 (no conflict)
                    with patch(
                        "cub.core.ids.hooks._scan_local_task_ids",
                        return_value=(9, 4),
                    ):
                        ok, message = verify_counters_before_push(project_dir=tmp_path)

                        assert ok is True
                        assert message == ""

    def test_spec_conflict_blocks_push(self, tmp_path: Path) -> None:
        """When spec number conflicts, hook should block push."""
        with patch("cub.core.ids.hooks.SyncService") as mock_sync_cls:
            mock_sync = MagicMock()
            mock_sync.is_initialized.return_value = True
            mock_sync_cls.return_value = mock_sync

            with patch("cub.core.ids.hooks._fetch_remote_sync_branch"):
                # Remote counters at 10/5
                remote_counters = CounterState(spec_number=10, standalone_task_number=5)
                with patch(
                    "cub.core.ids.hooks._read_remote_counters", return_value=remote_counters
                ):
                    # Local has used spec 10 (conflicts with remote next=10)
                    with patch(
                        "cub.core.ids.hooks._scan_local_task_ids",
                        return_value=(10, 4),
                    ):
                        ok, message = verify_counters_before_push(project_dir=tmp_path)

                        assert ok is False
                        assert "Local spec number 10" in message
                        assert "conflicts with" in message
                        assert "remote counter" in message

    def test_standalone_conflict_blocks_push(self, tmp_path: Path) -> None:
        """When standalone number conflicts, hook should block push."""
        with patch("cub.core.ids.hooks.SyncService") as mock_sync_cls:
            mock_sync = MagicMock()
            mock_sync.is_initialized.return_value = True
            mock_sync_cls.return_value = mock_sync

            with patch("cub.core.ids.hooks._fetch_remote_sync_branch"):
                # Remote counters at 10/5
                remote_counters = CounterState(spec_number=10, standalone_task_number=5)
                with patch(
                    "cub.core.ids.hooks._read_remote_counters", return_value=remote_counters
                ):
                    # Local has used standalone 5 (conflicts with remote next=5)
                    with patch(
                        "cub.core.ids.hooks._scan_local_task_ids",
                        return_value=(9, 5),
                    ):
                        ok, message = verify_counters_before_push(project_dir=tmp_path)

                        assert ok is False
                        assert "Local standalone task number 5" in message
                        assert "conflicts with" in message

    def test_both_conflicts_block_push(self, tmp_path: Path) -> None:
        """When both spec and standalone conflict, both should be reported."""
        with patch("cub.core.ids.hooks.SyncService") as mock_sync_cls:
            mock_sync = MagicMock()
            mock_sync.is_initialized.return_value = True
            mock_sync_cls.return_value = mock_sync

            with patch("cub.core.ids.hooks._fetch_remote_sync_branch"):
                remote_counters = CounterState(spec_number=10, standalone_task_number=5)
                with patch(
                    "cub.core.ids.hooks._read_remote_counters", return_value=remote_counters
                ):
                    # Local has used spec 11 and standalone 6
                    with patch(
                        "cub.core.ids.hooks._scan_local_task_ids",
                        return_value=(11, 6),
                    ):
                        ok, message = verify_counters_before_push(project_dir=tmp_path)

                        assert ok is False
                        assert "Local spec number 11" in message
                        assert "Local standalone task number 6" in message


class TestFormatHookMessage:
    """Test suite for format_hook_message()."""

    def test_formats_conflict_message(self) -> None:
        """Should format a readable error message."""
        conflicts = ["Local spec number 10 conflicts with remote counter (next: 10)"]
        message = format_hook_message(
            conflicts=conflicts,
            local_spec=10,
            local_standalone=4,
            remote_spec=10,
            remote_standalone=5,
        )

        assert "ERROR: ID collision detected!" in message
        assert "Local spec number 10" in message
        assert "Resolution:" in message
        assert "cub sync pull" in message
        assert "--no-verify" in message

    def test_includes_current_state(self) -> None:
        """Should include current counter state."""
        conflicts = ["test conflict"]
        message = format_hook_message(
            conflicts=conflicts,
            local_spec=15,
            local_standalone=8,
            remote_spec=10,
            remote_standalone=5,
        )

        assert "Local max spec:        15" in message
        assert "Remote next spec:      10" in message
        assert "Local max standalone:  8" in message
        assert "Remote next standalone: 5" in message

    def test_handles_none_values(self) -> None:
        """Should handle None for local max values."""
        conflicts = ["test conflict"]
        message = format_hook_message(
            conflicts=conflicts,
            local_spec=None,
            local_standalone=None,
            remote_spec=10,
            remote_standalone=5,
        )

        assert "Local max spec:        none" in message
        assert "Local max standalone:  none" in message


class TestScanLocalTaskIds:
    """Test suite for _scan_local_task_ids()."""

    def test_no_tasks_file_returns_none(self, tmp_path: Path) -> None:
        """When tasks file doesn't exist, should return (None, None)."""
        from cub.core.ids.hooks import _scan_local_task_ids

        max_spec, max_standalone = _scan_local_task_ids(tmp_path)

        assert max_spec is None
        assert max_standalone is None

    def test_empty_tasks_file_returns_none(self, tmp_path: Path) -> None:
        """When tasks file is empty, should return (None, None)."""
        from cub.core.ids.hooks import _scan_local_task_ids

        # Create empty tasks file
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"
        tasks_file.touch()

        max_spec, max_standalone = _scan_local_task_ids(tmp_path)

        assert max_spec is None
        assert max_standalone is None

    def test_scans_spec_based_ids(self, tmp_path: Path) -> None:
        """Should find maximum spec number from epic and task IDs."""
        from cub.core.ids.hooks import _scan_local_task_ids

        # Create tasks file with spec-based IDs
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        tasks = [
            {"id": "cub-048a-0", "title": "Epic 048a-0"},
            {"id": "cub-048a-0.1", "title": "Task 048a-0.1"},
            {"id": "cub-052b-1", "title": "Epic 052b-1"},
            {"id": "cub-052b-1.2", "title": "Task 052b-1.2"},
        ]

        with tasks_file.open("w") as f:
            for task in tasks:
                f.write(json.dumps(task) + "\n")

        max_spec, max_standalone = _scan_local_task_ids(tmp_path)

        assert max_spec == 52  # From cub-052b-1
        assert max_standalone is None

    def test_scans_standalone_ids(self, tmp_path: Path) -> None:
        """Should find maximum standalone number."""
        from cub.core.ids.hooks import _scan_local_task_ids

        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        tasks = [
            {"id": "cub-s003", "title": "Standalone 3"},
            {"id": "cub-s015", "title": "Standalone 15"},
            {"id": "cub-s007", "title": "Standalone 7"},
        ]

        with tasks_file.open("w") as f:
            for task in tasks:
                f.write(json.dumps(task) + "\n")

        max_spec, max_standalone = _scan_local_task_ids(tmp_path)

        assert max_spec is None
        assert max_standalone == 15

    def test_scans_mixed_ids(self, tmp_path: Path) -> None:
        """Should handle both spec and standalone IDs."""
        from cub.core.ids.hooks import _scan_local_task_ids

        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        tasks = [
            {"id": "cub-048a-0", "title": "Epic"},
            {"id": "cub-048a-0.1", "title": "Task"},
            {"id": "cub-s003", "title": "Standalone"},
            {"id": "cub-052b-1.2", "title": "Task"},
            {"id": "cub-s015", "title": "Standalone"},
        ]

        with tasks_file.open("w") as f:
            for task in tasks:
                f.write(json.dumps(task) + "\n")

        max_spec, max_standalone = _scan_local_task_ids(tmp_path)

        assert max_spec == 52
        assert max_standalone == 15

    def test_handles_invalid_lines(self, tmp_path: Path) -> None:
        """Should skip invalid JSON lines gracefully."""
        from cub.core.ids.hooks import _scan_local_task_ids

        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        tasks_file = cub_dir / "tasks.jsonl"

        with tasks_file.open("w") as f:
            f.write('{"id": "cub-048a-0", "title": "Valid"}\n')
            f.write('invalid json line\n')
            f.write('{"id": "cub-052b-1", "title": "Valid"}\n')
            f.write('\n')  # Empty line

        max_spec, max_standalone = _scan_local_task_ids(tmp_path)

        assert max_spec == 52
        assert max_standalone is None


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for testing."""
    import subprocess

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Configure git user for testing
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    return tmp_path
