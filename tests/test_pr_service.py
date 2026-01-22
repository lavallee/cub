"""
Tests for PR service functionality.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.github.client import GitHubClient
from cub.core.github.models import RepoInfo
from cub.core.pr.service import (
    PRService,
    _delete_local_branch,
    _find_worktree_for_branch,
    _prune_remote_tracking,
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
