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


class TestPRServiceError:
    """Tests for PRServiceError exception class."""

    def test_pr_service_error_message(self):
        """Test PRServiceError can be raised with a message."""
        from cub.core.pr.service import PRServiceError

        with pytest.raises(PRServiceError) as exc_info:
            raise PRServiceError("Something went wrong")
        assert str(exc_info.value) == "Something went wrong"

    def test_pr_service_error_inheritance(self):
        """Test PRServiceError inherits from Exception."""
        from cub.core.pr.service import PRServiceError

        assert issubclass(PRServiceError, Exception)


class TestPRResult:
    """Tests for PRResult dataclass."""

    def test_pr_result_creation(self):
        """Test PRResult can be created with all fields."""
        from cub.core.pr.service import PRResult

        result = PRResult(
            url="https://github.com/user/repo/pull/42",
            number=42,
            title="My PR",
            created=True,
        )
        assert result.url == "https://github.com/user/repo/pull/42"
        assert result.number == 42
        assert result.title == "My PR"
        assert result.created is True

    def test_pr_result_existing_pr(self):
        """Test PRResult for an existing PR."""
        from cub.core.pr.service import PRResult

        result = PRResult(
            url="https://github.com/user/repo/pull/1",
            number=1,
            title="Old PR",
            created=False,
        )
        assert result.created is False


class TestMergeResult:
    """Tests for MergeResult dataclass."""

    def test_merge_result_success(self):
        """Test MergeResult for successful merge."""
        from cub.core.pr.service import MergeResult

        result = MergeResult(
            success=True,
            pr_number=42,
            method="squash",
            branch_deleted=True,
        )
        assert result.success is True
        assert result.pr_number == 42
        assert result.method == "squash"
        assert result.branch_deleted is True

    def test_merge_result_no_branch_deletion(self):
        """Test MergeResult when branch is not deleted."""
        from cub.core.pr.service import MergeResult

        result = MergeResult(
            success=True,
            pr_number=10,
            method="merge",
            branch_deleted=False,
        )
        assert result.branch_deleted is False


class TestPRServiceInitialization:
    """Tests for PRService initialization."""

    def test_default_initialization(self):
        """Test PRService can be initialized with defaults."""
        service = PRService()
        assert service.project_dir == Path.cwd()
        assert service._stream_config is not None
        assert service._branch_store is None
        assert service._github_client is None

    def test_initialization_with_project_dir(self, tmp_path):
        """Test PRService can be initialized with project directory."""
        service = PRService(project_dir=tmp_path)
        assert service.project_dir == tmp_path

    def test_initialization_with_stream_config(self, tmp_path):
        """Test PRService can be initialized with stream config."""
        config = StreamConfig(enabled=True, debug=True)
        service = PRService(project_dir=tmp_path, stream_config=config)
        assert service._stream_config.enabled is True
        assert service._stream_config.debug is True

    def test_branch_store_lazy_init(self, tmp_path):
        """Test branch_store property initializes BranchStore lazily."""
        service = PRService(project_dir=tmp_path)
        assert service._branch_store is None
        # Access property to trigger initialization
        store = service.branch_store
        assert store is not None
        assert service._branch_store is not None

    def test_github_client_lazy_init(self, tmp_path):
        """Test github_client property initializes lazily with mocked from_project_dir."""
        from cub.core.github.models import RepoInfo

        service = PRService(project_dir=tmp_path)
        assert service._github_client is None

        # Mock from_project_dir to avoid needing real git repo
        mock_client = GitHubClient(RepoInfo(owner="test", repo="repo"))
        with patch.object(GitHubClient, "from_project_dir", return_value=mock_client):
            client = service.github_client
            assert client is not None
            assert service._github_client is not None


class TestResolveInput:
    """Tests for PRService.resolve_input method."""

    @pytest.fixture
    def pr_service(self, tmp_path):
        """Create a PR service for testing."""
        return PRService(project_dir=tmp_path)

    def test_resolve_input_none_uses_current_branch(self, pr_service):
        """Test resolve_input with None uses current branch."""
        with (
            patch(
                "cub.core.pr.service.BranchStore.get_current_branch"
            ) as mock_current,
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_current.return_value = "feature/my-feature"
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_exists.return_value = True

            result = pr_service.resolve_input(None)

            assert result.type == "branch"
            assert result.branch == "feature/my-feature"

    def test_resolve_input_none_no_current_branch_raises(self, pr_service):
        """Test resolve_input with None raises when no current branch."""
        from cub.core.pr.service import PRServiceError

        with patch(
            "cub.core.pr.service.BranchStore.get_current_branch"
        ) as mock_current:
            mock_current.return_value = None

            with pytest.raises(PRServiceError) as exc_info:
                pr_service.resolve_input(None)
            assert "Could not determine current branch" in str(exc_info.value)

    def test_resolve_input_pr_number(self, pr_service):
        """Test resolve_input with PR number format."""
        result = pr_service.resolve_input("42")
        assert result.type == "pr"
        assert result.pr_number == 42

    def test_resolve_input_pr_number_with_hash(self, pr_service):
        """Test resolve_input with #PR format."""
        result = pr_service.resolve_input("#123")
        assert result.type == "pr"
        assert result.pr_number == 123

    def test_resolve_input_epic_id_with_binding(self, pr_service):
        """Test resolve_input with epic ID that has a binding."""
        from cub.core.branches.models import BranchBinding

        binding = BranchBinding(
            epic_id="cub-vd6",
            branch_name="feature/vd6",
            base_branch="main",
        )
        with patch.object(
            pr_service.branch_store, "get_binding"
        ) as mock_get_binding:
            mock_get_binding.return_value = binding

            result = pr_service.resolve_input("cub-vd6")

            assert result.type == "epic"
            assert result.epic_id == "cub-vd6"
            assert result.branch == "feature/vd6"
            assert result.binding == binding

    def test_resolve_input_branch_with_binding(self, pr_service):
        """Test resolve_input with branch name that has a binding."""
        from cub.core.branches.models import BranchBinding

        binding = BranchBinding(
            epic_id="cub-123",
            branch_name="feature/my-branch",
            base_branch="develop",
        )
        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
        ):
            mock_get_binding.return_value = None  # No epic match
            mock_get_binding_by_branch.return_value = binding

            result = pr_service.resolve_input("feature/my-branch")

            assert result.type == "branch"
            assert result.branch == "feature/my-branch"
            assert result.epic_id == "cub-123"
            assert result.binding == binding

    def test_resolve_input_valid_git_branch(self, pr_service):
        """Test resolve_input with valid git branch (no binding)."""
        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_exists.return_value = True

            result = pr_service.resolve_input("feature/unbound")

            assert result.type == "branch"
            assert result.branch == "feature/unbound"
            assert result.binding is None

    def test_resolve_input_unbound_epic(self, pr_service):
        """Test resolve_input with unbound epic ID (assumed)."""
        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_exists.return_value = False  # Not a valid branch

            result = pr_service.resolve_input("cub-unknown")

            assert result.type == "epic"
            assert result.epic_id == "cub-unknown"
            assert result.binding is None


class TestCreatePR:
    """Tests for PRService.create_pr method."""

    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        from cub.core.github.models import RepoInfo

        repo = RepoInfo(owner="user", repo="project")
        return GitHubClient(repo)

    @pytest.fixture
    def pr_service(self, tmp_path, mock_github_client):
        """Create a PR service with mocked GitHub client."""
        service = PRService(tmp_path)
        service._github_client = mock_github_client
        return service

    def test_create_pr_existing_pr(self, pr_service):
        """Test create_pr when PR already exists."""
        from cub.core.branches.models import BranchBinding

        binding = BranchBinding(
            epic_id="cub-123",
            branch_name="feature/test",
            base_branch="main",
            pr_number=None,
        )

        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.github_client, "get_pr_by_branch"
            ) as mock_existing,
            patch.object(
                pr_service.branch_store, "update_pr"
            ) as mock_update_pr,
        ):
            mock_get_binding.return_value = binding
            mock_existing.return_value = {
                "number": 99,
                "url": "https://github.com/user/repo/pull/99",
                "title": "Existing PR",
            }

            result = pr_service.create_pr(target="cub-123")

            assert result.created is False
            assert result.number == 99
            assert result.url == "https://github.com/user/repo/pull/99"
            mock_update_pr.assert_called_once_with("cub-123", 99)

    def test_create_pr_dry_run(self, pr_service):
        """Test create_pr in dry_run mode."""
        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch.object(
                pr_service.github_client, "get_pr_by_branch"
            ) as mock_existing,
            patch.object(
                pr_service.github_client, "needs_push"
            ) as mock_needs_push,
            patch.object(
                pr_service.github_client, "get_commits_between"
            ) as mock_commits,
            patch.object(
                pr_service.github_client, "get_files_changed"
            ) as mock_files,
            patch.object(
                pr_service.github_client, "get_diff_stat"
            ) as mock_stat,
            patch(
                "cub.core.pr.service.BranchStore.get_current_branch"
            ) as mock_current,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_existing.return_value = None
            mock_needs_push.return_value = False
            mock_current.return_value = "feature/dry-run"
            mock_exists.return_value = True
            mock_commits.return_value = []
            mock_files.return_value = {"added": [], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 0, "insertions": 0, "deletions": 0}

            result = pr_service.create_pr(target="feature/dry-run", dry_run=True)

            assert result.created is True
            assert result.url == "(dry-run)"
            assert result.number == 0

    def test_create_pr_needs_push(self, pr_service):
        """Test create_pr when branch needs push."""
        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch.object(
                pr_service.github_client, "get_pr_by_branch"
            ) as mock_existing,
            patch.object(
                pr_service.github_client, "needs_push"
            ) as mock_needs_push,
            patch.object(
                pr_service.github_client, "push_branch"
            ) as mock_push,
            patch.object(
                pr_service.github_client, "branch_exists_on_remote"
            ) as mock_remote,
            patch.object(
                pr_service.github_client, "create_pr"
            ) as mock_create,
            patch.object(
                pr_service.github_client, "get_commits_between"
            ) as mock_commits,
            patch.object(
                pr_service.github_client, "get_files_changed"
            ) as mock_files,
            patch.object(
                pr_service.github_client, "get_diff_stat"
            ) as mock_stat,
            patch(
                "cub.core.pr.service.BranchStore.get_current_branch"
            ) as mock_current,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_existing.return_value = None
            mock_needs_push.return_value = True
            mock_current.return_value = "feature/push"
            mock_exists.return_value = True
            mock_remote.return_value = True
            mock_commits.return_value = []
            mock_files.return_value = {"added": [], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 0, "insertions": 0, "deletions": 0}
            mock_create.return_value = {
                "url": "https://github.com/user/repo/pull/55",
                "number": 55,
            }

            result = pr_service.create_pr(target="feature/push")

            mock_push.assert_called_once_with("feature/push")
            assert result.number == 55

    def test_create_pr_wrong_branch_raises(self, pr_service):
        """Test create_pr raises when not on expected branch."""
        from cub.core.pr.service import PRServiceError

        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch.object(
                pr_service.github_client, "get_pr_by_branch"
            ) as mock_existing,
            patch(
                "cub.core.pr.service.BranchStore.get_current_branch"
            ) as mock_current,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_existing.return_value = None
            mock_current.return_value = "main"  # Wrong branch
            mock_exists.return_value = True

            with pytest.raises(PRServiceError) as exc_info:
                pr_service.create_pr(target="feature/expected")

            assert "Not on expected branch" in str(exc_info.value)
            assert "main" in str(exc_info.value)
            assert "feature/expected" in str(exc_info.value)

    def test_create_pr_no_branch_raises(self, pr_service):
        """Test create_pr raises when no branch can be determined."""
        from cub.core.pr.service import PRServiceError

        with patch.object(
            pr_service.branch_store, "get_binding"
        ) as mock_get_binding:
            mock_get_binding.return_value = None

            with pytest.raises(PRServiceError) as exc_info:
                # Unbound epic with no branch
                mock_resolved = MagicMock(
                    type="epic",
                    branch=None,
                    binding=None,
                    epic_id="cub-unbound",
                    pr_number=None,
                )
                pr_service.resolve_input = MagicMock(return_value=mock_resolved)
                pr_service.create_pr(target="cub-unbound")

            assert "No branch found" in str(exc_info.value)

    def test_create_pr_github_error(self, pr_service):
        """Test create_pr handles GitHub API errors."""
        from cub.core.github.client import GitHubClientError
        from cub.core.pr.service import PRServiceError

        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch.object(
                pr_service.github_client, "get_pr_by_branch"
            ) as mock_existing,
            patch.object(
                pr_service.github_client, "needs_push"
            ) as mock_needs_push,
            patch.object(
                pr_service.github_client, "branch_exists_on_remote"
            ) as mock_remote,
            patch.object(
                pr_service.github_client, "create_pr"
            ) as mock_create,
            patch.object(
                pr_service.github_client, "get_commits_between"
            ) as mock_commits,
            patch.object(
                pr_service.github_client, "get_files_changed"
            ) as mock_files,
            patch.object(
                pr_service.github_client, "get_diff_stat"
            ) as mock_stat,
            patch(
                "cub.core.pr.service.BranchStore.get_current_branch"
            ) as mock_current,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_existing.return_value = None
            mock_needs_push.return_value = False
            mock_current.return_value = "feature/error"
            mock_exists.return_value = True
            mock_remote.return_value = True
            mock_commits.return_value = []
            mock_files.return_value = {"added": [], "modified": [], "deleted": []}
            mock_stat.return_value = {"files": 0, "insertions": 0, "deletions": 0}
            mock_create.side_effect = GitHubClientError("API rate limit exceeded")

            with pytest.raises(PRServiceError) as exc_info:
                pr_service.create_pr(target="feature/error")

            assert "API rate limit exceeded" in str(exc_info.value)

    def test_create_pr_with_pr_target_returns_existing(self, pr_service):
        """Test create_pr with PR number target returns existing PR info."""
        with patch.object(
            pr_service.github_client, "get_pr"
        ) as mock_get_pr:
            mock_get_pr.return_value = {
                "number": 42,
                "url": "https://github.com/user/repo/pull/42",
                "title": "Existing PR",
            }

            result = pr_service.create_pr(target="42")

            assert result.created is False
            assert result.number == 42


class TestGetClaudeCIPrompt:
    """Tests for PRService.get_claude_ci_prompt method."""

    def test_get_claude_ci_prompt_format(self, tmp_path):
        """Test get_claude_ci_prompt returns properly formatted prompt."""
        service = PRService(project_dir=tmp_path)

        prompt = service.get_claude_ci_prompt(
            pr_number=42,
            branch="feature/ci-test",
            base="main",
        )

        assert "PR #42" in prompt
        assert "feature/ci-test" in prompt
        assert "main" in prompt
        assert "gh pr checks" in prompt
        assert "gh pr view" in prompt
        assert "ready to merge" in prompt

    def test_get_claude_ci_prompt_different_base(self, tmp_path):
        """Test get_claude_ci_prompt with different base branch."""
        service = PRService(project_dir=tmp_path)

        prompt = service.get_claude_ci_prompt(
            pr_number=100,
            branch="hotfix/urgent",
            base="develop",
        )

        assert "PR #100" in prompt
        assert "hotfix/urgent" in prompt
        assert "develop" in prompt


class TestMergePR:
    """Tests for PRService.merge_pr method."""

    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        from cub.core.github.models import RepoInfo

        repo = RepoInfo(owner="user", repo="project")
        return GitHubClient(repo)

    @pytest.fixture
    def pr_service(self, tmp_path, mock_github_client):
        """Create a PR service with mocked GitHub client."""
        service = PRService(tmp_path)
        service._github_client = mock_github_client
        return service

    def test_merge_pr_success(self, pr_service):
        """Test merge_pr successful merge."""
        from cub.core.branches.models import BranchBinding

        binding = BranchBinding(
            epic_id="cub-merge",
            branch_name="feature/to-merge",
            base_branch="main",
            pr_number=77,
        )

        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.github_client, "get_pr"
            ) as mock_get_pr,
            patch.object(
                pr_service.github_client, "get_pr_checks"
            ) as mock_checks,
            patch.object(
                pr_service.github_client, "merge_pr"
            ) as mock_merge,
            patch.object(
                pr_service.branch_store, "update_status"
            ) as mock_update_status,
            patch("cub.core.pr.service._find_worktree_for_branch") as mock_find_wt,
            patch("cub.core.pr.service._prune_remote_tracking") as mock_prune,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_get_binding.return_value = binding
            mock_get_pr.return_value = {
                "number": 77,
                "state": "OPEN",
                "mergeable": True,
            }
            mock_checks.return_value = [
                {"name": "tests", "status": "completed", "conclusion": "success"}
            ]
            mock_find_wt.return_value = None
            mock_prune.return_value = True
            mock_subprocess.return_value = MagicMock(
                returncode=0, stdout="main\n", stderr=""
            )

            result = pr_service.merge_pr(target="cub-merge")

            assert result.success is True
            assert result.pr_number == 77
            assert result.method == "squash"
            mock_merge.assert_called_once()
            mock_update_status.assert_called_once_with("cub-merge", "merged")

    def test_merge_pr_already_merged(self, pr_service):
        """Test merge_pr when PR is already merged."""
        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch.object(
                pr_service.github_client, "get_pr"
            ) as mock_get_pr,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_exists.return_value = False
            mock_get_pr.return_value = {
                "number": 50,
                "state": "MERGED",
            }

            result = pr_service.merge_pr(target="50")

            assert result.success is True
            assert result.pr_number == 50
            assert result.branch_deleted is True  # Assumed deleted when merged

    def test_merge_pr_closed_raises(self, pr_service):
        """Test merge_pr raises when PR is closed (not merged)."""
        from cub.core.pr.service import PRServiceError

        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch.object(
                pr_service.github_client, "get_pr"
            ) as mock_get_pr,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_exists.return_value = False
            mock_get_pr.return_value = {
                "number": 60,
                "state": "CLOSED",
            }

            with pytest.raises(PRServiceError) as exc_info:
                pr_service.merge_pr(target="60")

            assert "PR #60 is closed" in str(exc_info.value)

    def test_merge_pr_dry_run(self, pr_service):
        """Test merge_pr in dry_run mode."""
        from cub.core.branches.models import BranchBinding

        binding = BranchBinding(
            epic_id="cub-dry",
            branch_name="feature/dry",
            base_branch="main",
            pr_number=88,
        )

        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.github_client, "get_pr"
            ) as mock_get_pr,
            patch.object(
                pr_service.github_client, "get_pr_checks"
            ) as mock_checks,
            patch.object(
                pr_service.github_client, "merge_pr"
            ) as mock_merge,
        ):
            mock_get_binding.return_value = binding
            mock_get_pr.return_value = {
                "number": 88,
                "state": "OPEN",
                "mergeable": True,
            }
            mock_checks.return_value = []

            result = pr_service.merge_pr(target="cub-dry", dry_run=True)

            assert result.success is True
            assert result.pr_number == 88
            mock_merge.assert_not_called()  # Should not actually merge

    def test_merge_pr_no_pr_found_raises(self, pr_service):
        """Test merge_pr raises when no PR found."""
        from cub.core.pr.service import PRServiceError

        with (
            patch.object(
                pr_service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                pr_service.branch_store, "get_binding_by_branch"
            ) as mock_get_binding_by_branch,
            patch.object(
                pr_service.github_client, "get_pr_by_branch"
            ) as mock_get_pr_by_branch,
            patch(
                "cub.core.pr.service.BranchStore.git_branch_exists"
            ) as mock_exists,
        ):
            mock_get_binding.return_value = None
            mock_get_binding_by_branch.return_value = None
            mock_exists.return_value = True
            mock_get_pr_by_branch.return_value = None

            with pytest.raises(PRServiceError) as exc_info:
                pr_service.merge_pr(target="feature/no-pr")

            assert "No PR found" in str(exc_info.value)

    def test_merge_pr_with_failed_checks_warns(self, pr_service):
        """Test merge_pr warns about failed checks but proceeds."""
        from io import StringIO

        from rich.console import Console

        from cub.core.branches.models import BranchBinding

        output = StringIO()
        console = Console(file=output, force_terminal=True)
        service = PRService(
            project_dir=pr_service.project_dir,
            stream_config=StreamConfig(console=console),
        )
        service._github_client = pr_service._github_client

        binding = BranchBinding(
            epic_id="cub-warn",
            branch_name="feature/warn",
            base_branch="main",
            pr_number=99,
        )

        with (
            patch.object(
                service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                service.github_client, "get_pr"
            ) as mock_get_pr,
            patch.object(
                service.github_client, "get_pr_checks"
            ) as mock_checks,
            patch.object(service.github_client, "merge_pr"),
            patch.object(service.branch_store, "update_status"),
            patch("cub.core.pr.service._find_worktree_for_branch") as mock_find_wt,
            patch("cub.core.pr.service._prune_remote_tracking") as mock_prune,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_get_binding.return_value = binding
            mock_get_pr.return_value = {
                "number": 99,
                "state": "OPEN",
                "mergeable": True,
            }
            mock_checks.return_value = [
                {"name": "tests", "status": "completed", "conclusion": "failure"},
                {"name": "lint", "status": "completed", "conclusion": "success"},
            ]
            mock_find_wt.return_value = None
            mock_prune.return_value = True
            mock_subprocess.return_value = MagicMock(
                returncode=0, stdout="main\n", stderr=""
            )

            service.merge_pr(target="cub-warn")

            output.seek(0)
            content = output.read()
            assert "Warning" in content or "failed" in content.lower()

    def test_merge_pr_with_pending_checks_warns(self, pr_service):
        """Test merge_pr warns about pending checks."""
        from io import StringIO

        from rich.console import Console

        from cub.core.branches.models import BranchBinding

        output = StringIO()
        console = Console(file=output, force_terminal=True)
        service = PRService(
            project_dir=pr_service.project_dir,
            stream_config=StreamConfig(console=console),
        )
        service._github_client = pr_service._github_client

        binding = BranchBinding(
            epic_id="cub-pending",
            branch_name="feature/pending",
            base_branch="main",
            pr_number=101,
        )

        with (
            patch.object(
                service.branch_store, "get_binding"
            ) as mock_get_binding,
            patch.object(
                service.github_client, "get_pr"
            ) as mock_get_pr,
            patch.object(
                service.github_client, "get_pr_checks"
            ) as mock_checks,
            patch.object(service.github_client, "merge_pr"),
            patch.object(service.branch_store, "update_status"),
            patch("cub.core.pr.service._find_worktree_for_branch") as mock_find_wt,
            patch("cub.core.pr.service._prune_remote_tracking") as mock_prune,
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_get_binding.return_value = binding
            mock_get_pr.return_value = {
                "number": 101,
                "state": "OPEN",
                "mergeable": True,
            }
            mock_checks.return_value = [
                {"name": "tests", "status": "in_progress", "conclusion": None},
            ]
            mock_find_wt.return_value = None
            mock_prune.return_value = True
            mock_subprocess.return_value = MagicMock(
                returncode=0, stdout="main\n", stderr=""
            )

            service.merge_pr(target="cub-pending")

            output.seek(0)
            content = output.read()
            assert "pending" in content.lower() or "Warning" in content


class TestWorktreeHelperExceptions:
    """Additional tests for worktree helper edge cases."""

    def test_find_worktree_oserror(self, tmp_path):
        """Test _find_worktree_for_branch handles OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not available")
            result = _find_worktree_for_branch(tmp_path, "main")
        assert result is None

    def test_update_worktree_oserror(self, tmp_path):
        """Test _update_worktree handles OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = _update_worktree(tmp_path)
        assert result is False

    def test_delete_local_branch_oserror(self, tmp_path):
        """Test _delete_local_branch handles OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not available")
            result = _delete_local_branch(tmp_path, "feature")
        assert result is False

    def test_prune_remote_tracking_oserror(self, tmp_path):
        """Test _prune_remote_tracking handles OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = _prune_remote_tracking(tmp_path)
        assert result is False


class TestGeneratePRBodyEdgeCases:
    """Additional tests for generate_pr_body edge cases."""

    @pytest.fixture
    def mock_github_client(self):
        """Create a mock GitHub client."""
        from cub.core.github.models import RepoInfo

        repo = RepoInfo(owner="user", repo="project")
        return GitHubClient(repo)

    @pytest.fixture
    def pr_service(self, tmp_path, mock_github_client):
        """Create a PR service with mocked GitHub client."""
        service = PRService(tmp_path)
        service._github_client = mock_github_client
        return service

    def test_generate_pr_body_with_completed_tasks(self, pr_service):
        """Test PR body includes completed tasks from beads."""

        def mock_subprocess_run(cmd, **kwargs):
            if cmd[0] == "bd" and cmd[1] == "show":
                return MagicMock(
                    returncode=0,
                    stdout='{"title": "Epic", "description": ""}',
                )
            elif cmd[0] == "bd" and cmd[1] == "list":
                tasks = '[{"id": "task-1", "title": "Task 1"}, '
                tasks += '{"id": "task-2", "title": "Task 2"}]'
                return MagicMock(returncode=0, stdout=tasks)
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

            assert "### Completed Tasks" in body
            assert "task-1" in body
            assert "Task 1" in body
            assert "task-2" in body

    def test_generate_pr_body_bd_json_error(self, pr_service):
        """Test PR body handles bd JSON parse errors gracefully."""

        def mock_subprocess_run(cmd, **kwargs):
            if cmd[0] == "bd":
                return MagicMock(
                    returncode=0,
                    stdout="invalid json",
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

            # Should not raise, should handle gracefully
            body = pr_service.generate_pr_body("epic-123", "feature", "main")

            assert "## Summary" in body

    def test_format_file_list_custom_max(self, pr_service):
        """Test _format_file_list with custom max_files."""
        files = [f"file{i}.py" for i in range(10)]
        result = pr_service._format_file_list(files, max_files=5)

        assert len(result) == 6  # 5 files + "... and 5 more"
        assert result[-1] == "... and 5 more"

    def test_format_file_list_exact_max(self, pr_service):
        """Test _format_file_list with exactly max_files files."""
        files = [f"file{i}.py" for i in range(10)]
        result = pr_service._format_file_list(files, max_files=10)

        assert len(result) == 10
        assert "more" not in result[-1]
