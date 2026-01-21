"""
Tests for PR service functionality.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from cub.core.github.client import GitHubClient
from cub.core.github.models import RepoInfo
from cub.core.pr.service import (
    PRService,
    StreamConfig,
    _delete_local_branch,
    _find_worktree_for_branch,
    _prune_remote_tracking,
    _switch_to_branch,
    _update_worktree,
)


class TestPRServiceGeneratePRBody:
    """Tests for PRService.generate_pr_body."""

    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        repo = RepoInfo(owner="user", repo="project")
        return GitHubClient(repo)

    @pytest.fixture
    def pr_service(self, tmp_path, mock_github_client):
        """Create a PR service with mocked GitHub client."""
        service = PRService(tmp_path)
        service._github_client = mock_github_client
        return service

    def test_generate_pr_body_with_commits_and_files(self, pr_service):
        """Test PR body generation with commits and file changes."""
        with (
            patch.object(pr_service.github_client, "get_commits_between") as mock_commits,
            patch.object(pr_service.github_client, "get_files_changed") as mock_files,
            patch.object(pr_service.github_client, "get_diff_stat") as mock_stat,
        ):
            mock_commits.return_value = [
                {"sha": "abc1234", "subject": "Add new feature", "body": ""},
                {"sha": "def5678", "subject": "Fix bug in feature", "body": ""},
            ]
            mock_files.return_value = {
                "added": ["src/new_file.py"],
                "modified": ["src/existing.py"],
                "deleted": [],
            }
            mock_stat.return_value = {
                "files": 2,
                "insertions": 50,
                "deletions": 10,
            }

            body = pr_service.generate_pr_body(None, "feature", "main")

            # Check that commits are included
            assert "### Commits (2)" in body
            assert "`abc1234` Add new feature" in body
            assert "`def5678` Fix bug in feature" in body

            # Check that files are included
            assert "### Files Changed" in body
            assert "`src/new_file.py`" in body
            assert "`src/existing.py`" in body

            # Check that stats are included
            assert "2 file(s) changed" in body
            assert "+50" in body
            assert "-10" in body

    def test_generate_pr_body_no_commits(self, pr_service):
        """Test PR body generation with no commits."""
        with (
            patch.object(pr_service.github_client, "get_commits_between") as mock_commits,
            patch.object(pr_service.github_client, "get_files_changed") as mock_files,
            patch.object(pr_service.github_client, "get_diff_stat") as mock_stat,
        ):
            mock_commits.return_value = []
            mock_files.return_value = {"added": [], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 0, "insertions": 0, "deletions": 0}

            body = pr_service.generate_pr_body(None, "feature", "main")

            # Should not have commits section
            assert "### Commits" not in body
            # Should still have summary and test plan
            assert "## Summary" in body
            assert "## Test Plan" in body

    def test_generate_pr_body_with_epic(self, pr_service):
        """Test PR body generation with epic from beads."""

        def mock_subprocess_run(cmd, **kwargs):
            """Mock subprocess.run to return different values for different commands."""
            if cmd[0] == "bd" and cmd[1] == "show":
                return MagicMock(
                    returncode=0,
                    stdout='{"title": "Epic Title", "description": "Epic description here"}',
                )
            elif cmd[0] == "bd" and cmd[1] == "list":
                # Return empty list for child tasks
                return MagicMock(
                    returncode=0,
                    stdout="[]",
                )
            return MagicMock(returncode=1)

        with (
            patch("subprocess.run", side_effect=mock_subprocess_run),
            patch.object(pr_service.github_client, "get_commits_between") as mock_commits,
            patch.object(pr_service.github_client, "get_files_changed") as mock_files,
            patch.object(pr_service.github_client, "get_diff_stat") as mock_stat,
        ):
            mock_commits.return_value = []
            mock_files.return_value = {"added": [], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 0, "insertions": 0, "deletions": 0}

            body = pr_service.generate_pr_body("epic-123", "feature", "main")

            # Should include epic description
            assert "Epic description here" in body

    def test_generate_pr_body_many_files_truncated(self, pr_service):
        """Test that many files are truncated with '... and N more'."""
        with (
            patch.object(pr_service.github_client, "get_commits_between") as mock_commits,
            patch.object(pr_service.github_client, "get_files_changed") as mock_files,
            patch.object(pr_service.github_client, "get_diff_stat") as mock_stat,
        ):
            mock_commits.return_value = []
            # Create 15 added files
            mock_files.return_value = {
                "added": [f"src/file{i}.py" for i in range(15)],
                "modified": [],
                "deleted": [],
            }
            mock_stat.return_value = {"files": 15, "insertions": 100, "deletions": 0}

            body = pr_service.generate_pr_body(None, "feature", "main")

            # Should show truncation message
            assert "... and 5 more" in body

    def test_format_file_list_under_max(self, pr_service):
        """Test file list formatting with few files."""
        files = ["a.py", "b.py", "c.py"]
        result = pr_service._format_file_list(files)

        assert result == ["`a.py`", "`b.py`", "`c.py`"]

    def test_format_file_list_over_max(self, pr_service):
        """Test file list formatting with many files."""
        files = [f"file{i}.py" for i in range(15)]
        result = pr_service._format_file_list(files)

        assert len(result) == 11  # 10 files + "... and 5 more"
        assert result[-1] == "... and 5 more"

    def test_generate_pr_body_with_deleted_files(self, pr_service):
        """Test PR body includes deleted files."""
        with (
            patch.object(pr_service.github_client, "get_commits_between") as mock_commits,
            patch.object(pr_service.github_client, "get_files_changed") as mock_files,
            patch.object(pr_service.github_client, "get_diff_stat") as mock_stat,
        ):
            mock_commits.return_value = []
            mock_files.return_value = {
                "added": [],
                "modified": [],
                "deleted": ["old_file.py"],
            }
            mock_stat.return_value = {"files": 1, "insertions": 0, "deletions": 50}

            body = pr_service.generate_pr_body(None, "feature", "main")

            assert "**Deleted (1):**" in body
            assert "`old_file.py`" in body

    def test_generate_pr_body_insertions_only(self, pr_service):
        """Test PR body stats with only insertions."""
        with (
            patch.object(pr_service.github_client, "get_commits_between") as mock_commits,
            patch.object(pr_service.github_client, "get_files_changed") as mock_files,
            patch.object(pr_service.github_client, "get_diff_stat") as mock_stat,
        ):
            mock_commits.return_value = []
            mock_files.return_value = {"added": ["new.py"], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 1, "insertions": 100, "deletions": 0}

            body = pr_service.generate_pr_body(None, "feature", "main")

            assert "+100" in body
            assert "-0" not in body  # Should not show zero deletions


class TestWorktreeHelpers:
    """Tests for worktree helper functions."""

    def test_find_worktree_for_branch_found(self, tmp_path):
        """Test finding worktree for an existing branch."""
        worktree_output = """worktree /path/to/repo
HEAD abc1234567890
branch refs/heads/feature

worktree /path/to/repo/.git/beads-worktrees/main
HEAD def5678901234
branch refs/heads/main
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=worktree_output)
            result = _find_worktree_for_branch(tmp_path, "main")

        assert result == Path("/path/to/repo/.git/beads-worktrees/main")

    def test_find_worktree_for_branch_not_found(self, tmp_path):
        """Test finding worktree for non-existent branch."""
        worktree_output = """worktree /path/to/repo
HEAD abc1234567890
branch refs/heads/feature
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=worktree_output)
            result = _find_worktree_for_branch(tmp_path, "main")

        assert result is None

    def test_find_worktree_for_branch_git_error(self, tmp_path):
        """Test finding worktree when git command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = _find_worktree_for_branch(tmp_path, "main")

        assert result is None

    def test_update_worktree_success(self, tmp_path):
        """Test updating worktree successfully."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _update_worktree(tmp_path)

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "pull", "--ff-only"]
        assert call_args[1]["cwd"] == tmp_path

    def test_update_worktree_failure(self, tmp_path):
        """Test updating worktree when pull fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = _update_worktree(tmp_path)

        assert result is False

    def test_delete_local_branch_success(self, tmp_path):
        """Test deleting local branch successfully."""
        with patch("subprocess.run") as mock_run:
            # First call: get current branch
            # Second call: delete branch
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="main\n"),  # current branch
                MagicMock(returncode=0),  # delete success
            ]
            result = _delete_local_branch(tmp_path, "feature")

        assert result is True

    def test_delete_local_branch_is_current(self, tmp_path):
        """Test cannot delete current branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="feature\n")
            result = _delete_local_branch(tmp_path, "feature")

        assert result is False

    def test_delete_local_branch_not_found(self, tmp_path):
        """Test deleting non-existent branch returns True."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="main\n"),
                MagicMock(returncode=1, stderr="error: branch 'feature' not found."),
            ]
            result = _delete_local_branch(tmp_path, "feature")

        assert result is True  # Not found is considered success

    def test_prune_remote_tracking_success(self, tmp_path):
        """Test pruning remote tracking branches."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _prune_remote_tracking(tmp_path)

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "fetch", "--prune"]

    def test_prune_remote_tracking_failure(self, tmp_path):
        """Test pruning when fetch fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = _prune_remote_tracking(tmp_path)

        assert result is False

    def test_switch_to_branch_success(self, tmp_path):
        """Test switching to branch successfully."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            success, error_msg = _switch_to_branch(tmp_path, "main")

        assert success is True
        assert error_msg == ""
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "switch", "main"]
        assert call_args[1]["cwd"] == tmp_path

    def test_switch_to_branch_failure(self, tmp_path):
        """Test switching to branch when it fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="error: Your local changes would be overwritten",
            )
            success, error_msg = _switch_to_branch(tmp_path, "main")

        assert success is False
        assert "local changes would be overwritten" in error_msg

    def test_switch_to_branch_failure_with_stdout(self, tmp_path):
        """Test switching to branch when it fails with stdout message."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="fatal: cannot switch to main",
                stderr="",
            )
            success, error_msg = _switch_to_branch(tmp_path, "main")

        assert success is False
        assert "cannot switch to main" in error_msg

    def test_switch_to_branch_oserror(self, tmp_path):
        """Test switching to branch when git not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")
            success, error_msg = _switch_to_branch(tmp_path, "main")

        assert success is False
        assert "git not found" in error_msg


class TestStreamConfig:
    """Tests for StreamConfig class."""

    def test_stream_config_defaults(self):
        """Test StreamConfig default values."""
        config = StreamConfig()
        assert config.enabled is False
        assert config.debug is False
        assert config.console is not None

    def test_stream_config_with_values(self):
        """Test StreamConfig with explicit values."""
        console = Console()
        config = StreamConfig(enabled=True, debug=True, console=console)
        assert config.enabled is True
        assert config.debug is True
        assert config.console is console

    def test_stream_outputs_when_enabled(self):
        """Test that stream() outputs when enabled."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        config = StreamConfig(enabled=True, console=console)

        config.stream("Test message")

        output.seek(0)
        content = output.read()
        assert "Test message" in content

    def test_stream_silent_when_disabled(self):
        """Test that stream() is silent when disabled."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        config = StreamConfig(enabled=False, console=console)

        config.stream("Test message")

        output.seek(0)
        content = output.read()
        assert content == ""

    def test_debug_log_outputs_when_enabled(self):
        """Test that debug_log() outputs when debug enabled."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        config = StreamConfig(debug=True, console=console)

        config.debug_log("Debug message")

        output.seek(0)
        content = output.read()
        assert "DEBUG" in content
        assert "Debug message" in content

    def test_debug_log_silent_when_disabled(self):
        """Test that debug_log() is silent when debug disabled."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        config = StreamConfig(debug=False, console=console)

        config.debug_log("Debug message")

        output.seek(0)
        content = output.read()
        assert content == ""

    def test_debug_value_outputs_when_enabled(self):
        """Test that debug_value() outputs when debug enabled."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        config = StreamConfig(debug=True, console=console)

        config.debug_value("my_var", "my_value")

        output.seek(0)
        content = output.read()
        assert "DEBUG" in content
        assert "my_var" in content
        assert "my_value" in content

    def test_debug_value_silent_when_disabled(self):
        """Test that debug_value() is silent when debug disabled."""
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        config = StreamConfig(debug=False, console=console)

        config.debug_value("my_var", "my_value")

        output.seek(0)
        content = output.read()
        assert content == ""


class TestPRServiceWithStreaming:
    """Tests for PRService with streaming configuration."""

    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        repo = RepoInfo(owner="user", repo="project")
        return GitHubClient(repo)

    @pytest.fixture
    def stream_output(self):
        """Create a StringIO for capturing output."""
        return StringIO()

    @pytest.fixture
    def stream_console(self, stream_output):
        """Create a console that writes to StringIO."""
        return Console(file=stream_output, force_terminal=True)

    @pytest.fixture
    def pr_service_with_streaming(self, tmp_path, mock_github_client, stream_console):
        """Create a PR service with streaming enabled."""
        config = StreamConfig(enabled=True, debug=False, console=stream_console)
        service = PRService(tmp_path, stream_config=config)
        service._github_client = mock_github_client
        return service

    @pytest.fixture
    def pr_service_with_debug(self, tmp_path, mock_github_client, stream_console):
        """Create a PR service with debug enabled."""
        config = StreamConfig(enabled=True, debug=True, console=stream_console)
        service = PRService(tmp_path, stream_config=config)
        service._github_client = mock_github_client
        return service

    def test_service_uses_stream_config_console(
        self, tmp_path, mock_github_client, stream_console
    ):
        """Test that service uses the console from stream config."""
        config = StreamConfig(enabled=True, console=stream_console)
        service = PRService(tmp_path, stream_config=config)
        assert service._console is stream_console

    def test_create_pr_with_streaming_shows_progress(
        self, pr_service_with_streaming, stream_output
    ):
        """Test that create_pr shows streaming output when enabled."""
        with (
            patch.object(
                pr_service_with_streaming.github_client, "get_pr_by_branch"
            ) as mock_existing,
            patch.object(
                pr_service_with_streaming.github_client, "needs_push"
            ) as mock_needs_push,
            patch.object(
                pr_service_with_streaming.github_client, "branch_exists_on_remote"
            ) as mock_remote,
            patch.object(
                pr_service_with_streaming.github_client, "create_pr"
            ) as mock_create,
            patch.object(
                pr_service_with_streaming.github_client, "get_commits_between"
            ) as mock_commits,
            patch.object(
                pr_service_with_streaming.github_client, "get_files_changed"
            ) as mock_files,
            patch.object(
                pr_service_with_streaming.github_client, "get_diff_stat"
            ) as mock_stat,
            patch(
                "cub.core.pr.service.BranchStore.get_current_branch"
            ) as mock_current,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_branch_exists,
            patch.object(
                pr_service_with_streaming.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service_with_streaming.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
        ):
            mock_existing.return_value = None
            mock_needs_push.return_value = False
            mock_remote.return_value = True
            mock_current.return_value = "feature-branch"
            mock_branch_exists.return_value = True
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_commits.return_value = []
            mock_files.return_value = {"added": [], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 0, "insertions": 0, "deletions": 0}
            mock_create.return_value = {
                "url": "https://github.com/user/repo/pull/42",
                "number": 42,
            }

            pr_service_with_streaming.create_pr(target="feature-branch")

        stream_output.seek(0)
        content = stream_output.read()
        # Check for streaming messages
        assert "Resolving target" in content
        assert "Checking for existing PR" in content
        assert "Validating current branch" in content
        assert "Generating PR body" in content
        assert "Creating PR via GitHub API" in content

    def test_create_pr_with_debug_shows_variable_values(
        self, pr_service_with_debug, stream_output
    ):
        """Test that create_pr shows debug info when debug enabled."""
        with (
            patch.object(
                pr_service_with_debug.github_client, "get_pr_by_branch"
            ) as mock_existing,
            patch.object(
                pr_service_with_debug.github_client, "needs_push"
            ) as mock_needs_push,
            patch.object(
                pr_service_with_debug.github_client, "branch_exists_on_remote"
            ) as mock_remote,
            patch.object(
                pr_service_with_debug.github_client, "create_pr"
            ) as mock_create,
            patch.object(
                pr_service_with_debug.github_client, "get_commits_between"
            ) as mock_commits,
            patch.object(
                pr_service_with_debug.github_client, "get_files_changed"
            ) as mock_files,
            patch.object(
                pr_service_with_debug.github_client, "get_diff_stat"
            ) as mock_stat,
            patch(
                "cub.core.pr.service.BranchStore.get_current_branch"
            ) as mock_current,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_branch_exists,
            patch.object(
                pr_service_with_debug.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service_with_debug.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
        ):
            mock_existing.return_value = None
            mock_needs_push.return_value = False
            mock_remote.return_value = True
            mock_current.return_value = "feature-branch"
            mock_branch_exists.return_value = True
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_commits.return_value = []
            mock_files.return_value = {"added": [], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 0, "insertions": 0, "deletions": 0}
            mock_create.return_value = {
                "url": "https://github.com/user/repo/pull/42",
                "number": 42,
            }

            pr_service_with_debug.create_pr(target="feature-branch")

        stream_output.seek(0)
        content = stream_output.read()
        # Check for debug output (note: Rich may add escape codes between words)
        assert "DEBUG" in content
        # Check for target variable (Rich may format as "target=" or "target" separately)
        assert "target" in content
        assert "feature-branch" in content
        assert "resolved" in content
        assert "type" in content
        assert "needs_push" in content

    def test_create_pr_without_streaming_is_quiet(
        self, tmp_path, mock_github_client, stream_output, stream_console
    ):
        """Test that create_pr is quiet when streaming disabled."""
        config = StreamConfig(enabled=False, debug=False, console=stream_console)
        service = PRService(tmp_path, stream_config=config)
        service._github_client = mock_github_client

        with (
            patch.object(
                service.github_client, "get_pr_by_branch"
            ) as mock_existing,
            patch.object(service.github_client, "needs_push") as mock_needs_push,
            patch.object(
                service.github_client, "branch_exists_on_remote"
            ) as mock_remote,
            patch.object(service.github_client, "create_pr") as mock_create,
            patch.object(
                service.github_client, "get_commits_between"
            ) as mock_commits,
            patch.object(service.github_client, "get_files_changed") as mock_files,
            patch.object(service.github_client, "get_diff_stat") as mock_stat,
            patch(
                "cub.core.pr.service.BranchStore.get_current_branch"
            ) as mock_current,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_branch_exists,
            patch.object(service.branch_store, "get_binding") as mock_get_binding,
            patch.object(
                service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
        ):
            mock_existing.return_value = None
            mock_needs_push.return_value = False
            mock_remote.return_value = True
            mock_current.return_value = "feature-branch"
            mock_branch_exists.return_value = True
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_commits.return_value = []
            mock_files.return_value = {"added": [], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 0, "insertions": 0, "deletions": 0}
            mock_create.return_value = {
                "url": "https://github.com/user/repo/pull/42",
                "number": 42,
            }

            service.create_pr(target="feature-branch")

        stream_output.seek(0)
        content = stream_output.read()
        # Stream messages should not be present
        assert "Resolving target" not in content
        assert "DEBUG" not in content
        # But normal output (PR created) should still be there
        assert "Creating PR" in content
