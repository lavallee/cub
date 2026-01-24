"""
Tests for GitHub client functionality.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.github.client import GitHubClient, GitHubClientError
from cub.core.github.models import GitHubIssue, RepoInfo


class TestGitHubClientError:
    """Tests for GitHubClientError exception class."""

    def test_instantiation(self):
        """Test basic instantiation."""
        error = GitHubClientError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_inherits_from_exception(self):
        """Test GitHubClientError inherits from Exception."""
        error = GitHubClientError("test")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test error can be raised and caught."""
        with pytest.raises(GitHubClientError) as exc_info:
            raise GitHubClientError("test error")
        assert "test error" in str(exc_info.value)


class TestRepoInfo:
    """Tests for RepoInfo model."""

    def test_from_ssh_url(self):
        """Test parsing SSH format URL."""
        url = "git@github.com:owner/repo.git"
        repo = RepoInfo.from_remote_url(url)

        assert repo is not None
        assert repo.owner == "owner"
        assert repo.repo == "repo"

    def test_from_ssh_url_no_git_suffix(self):
        """Test parsing SSH URL without .git suffix."""
        url = "git@github.com:owner/repo"
        repo = RepoInfo.from_remote_url(url)

        assert repo is not None
        assert repo.owner == "owner"
        assert repo.repo == "repo"

    def test_from_https_url(self):
        """Test parsing HTTPS format URL."""
        url = "https://github.com/owner/repo.git"
        repo = RepoInfo.from_remote_url(url)

        assert repo is not None
        assert repo.owner == "owner"
        assert repo.repo == "repo"

    def test_from_https_url_no_suffix(self):
        """Test parsing HTTPS URL without .git suffix."""
        url = "https://github.com/owner/repo"
        repo = RepoInfo.from_remote_url(url)

        assert repo is not None
        assert repo.owner == "owner"
        assert repo.repo == "repo"

    def test_from_https_url_trailing_slash(self):
        """Test parsing HTTPS URL with trailing slash."""
        url = "https://github.com/owner/repo/"
        repo = RepoInfo.from_remote_url(url)

        assert repo is not None
        assert repo.owner == "owner"
        assert repo.repo == "repo"

    def test_from_non_github_url(self):
        """Test non-GitHub URL returns None."""
        url = "git@gitlab.com:owner/repo.git"
        repo = RepoInfo.from_remote_url(url)

        assert repo is None

    def test_from_empty_url(self):
        """Test empty URL returns None."""
        assert RepoInfo.from_remote_url("") is None

    def test_full_name(self):
        """Test full_name computed property."""
        repo = RepoInfo(owner="user", repo="project")
        assert repo.full_name == "user/project"

    def test_url(self):
        """Test url computed property."""
        repo = RepoInfo(owner="user", repo="project")
        assert repo.url == "https://github.com/user/project"

    def test_issue_url(self):
        """Test issue_url method."""
        repo = RepoInfo(owner="user", repo="project")
        assert repo.issue_url(123) == "https://github.com/user/project/issues/123"


class TestGitHubIssue:
    """Tests for GitHubIssue model."""

    def test_from_gh_api_basic(self):
        """Test parsing basic issue data from gh api."""
        data = {
            "number": 123,
            "title": "Fix the bug",
            "body": "Description here",
            "state": "open",
            "html_url": "https://github.com/owner/repo/issues/123",
            "labels": [{"name": "bug"}, {"name": "priority-high"}],
            "assignees": [{"login": "user1"}, {"login": "user2"}],
        }

        issue = GitHubIssue.from_gh_api(data)

        assert issue.number == 123
        assert issue.title == "Fix the bug"
        assert issue.body == "Description here"
        assert issue.state == "open"
        assert issue.url == "https://github.com/owner/repo/issues/123"
        assert issue.labels == ["bug", "priority-high"]
        assert issue.assignees == ["user1", "user2"]

    def test_from_gh_api_minimal(self):
        """Test parsing minimal issue data."""
        data = {
            "number": 1,
            "title": "Simple",
        }

        issue = GitHubIssue.from_gh_api(data)

        assert issue.number == 1
        assert issue.title == "Simple"
        assert issue.body == ""
        assert issue.state == "open"
        assert issue.labels == []
        assert issue.assignees == []

    def test_from_gh_api_null_body(self):
        """Test parsing issue with null body."""
        data = {
            "number": 1,
            "title": "No body",
            "body": None,
        }

        issue = GitHubIssue.from_gh_api(data)

        assert issue.body == ""

    def test_is_open(self):
        """Test is_open computed property."""
        open_issue = GitHubIssue(number=1, title="Open", state="open")
        closed_issue = GitHubIssue(number=2, title="Closed", state="closed")

        assert open_issue.is_open is True
        assert closed_issue.is_open is False

    def test_labels_str_with_labels(self):
        """Test labels_str with labels."""
        issue = GitHubIssue(number=1, title="Test", labels=["bug", "urgent"])
        assert issue.labels_str == "bug, urgent"

    def test_labels_str_empty(self):
        """Test labels_str with no labels."""
        issue = GitHubIssue(number=1, title="Test", labels=[])
        assert issue.labels_str == "(none)"


class TestGetRemoteUrl:
    """Tests for GitHubClient._get_remote_url static method."""

    def test_get_remote_url_success(self, tmp_path):
        """Test getting remote URL successfully."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="git@github.com:owner/repo.git\n",
            )

            url = GitHubClient._get_remote_url(tmp_path)

            assert url == "git@github.com:owner/repo.git"
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == ["git", "remote", "get-url", "origin"]
            assert call_args[1]["cwd"] == tmp_path

    def test_get_remote_url_no_remote(self, tmp_path):
        """Test getting remote URL when no origin remote exists."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=128,
                stdout="",
                stderr="fatal: No such remote 'origin'",
            )

            url = GitHubClient._get_remote_url(tmp_path)

            assert url is None

    def test_get_remote_url_os_error(self, tmp_path):
        """Test getting remote URL when git command fails with OSError."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")

            url = GitHubClient._get_remote_url(tmp_path)

            assert url is None

    def test_get_remote_url_file_not_found(self, tmp_path):
        """Test getting remote URL when git not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git")

            url = GitHubClient._get_remote_url(tmp_path)

            assert url is None


class TestFromProjectDir:
    """Tests for GitHubClient.from_project_dir class method."""

    def test_from_project_dir_success(self, tmp_path):
        """Test creating client from project directory successfully."""
        with patch.object(GitHubClient, "is_gh_available", return_value=True):
            with patch.object(
                GitHubClient,
                "_get_remote_url",
                return_value="git@github.com:owner/repo.git",
            ):
                client = GitHubClient.from_project_dir(tmp_path)

                assert client.repo.owner == "owner"
                assert client.repo.repo == "repo"

    def test_from_project_dir_gh_not_available(self, tmp_path):
        """Test error when gh CLI not available."""
        with patch.object(GitHubClient, "is_gh_available", return_value=False):
            with pytest.raises(GitHubClientError) as exc_info:
                GitHubClient.from_project_dir(tmp_path)

            error_msg = str(exc_info.value)
            assert "GitHub CLI (gh) is not installed" in error_msg
            assert "gh auth login" in error_msg

    def test_from_project_dir_no_remote(self, tmp_path):
        """Test error when no git remote exists."""
        with patch.object(GitHubClient, "is_gh_available", return_value=True):
            with patch.object(GitHubClient, "_get_remote_url", return_value=None):
                with pytest.raises(GitHubClientError) as exc_info:
                    GitHubClient.from_project_dir(tmp_path)

                assert "No git remote 'origin' found" in str(exc_info.value)

    def test_from_project_dir_not_github_url(self, tmp_path):
        """Test error when remote is not a GitHub URL."""
        with patch.object(GitHubClient, "is_gh_available", return_value=True):
            with patch.object(
                GitHubClient,
                "_get_remote_url",
                return_value="git@gitlab.com:owner/repo.git",
            ):
                with pytest.raises(GitHubClientError) as exc_info:
                    GitHubClient.from_project_dir(tmp_path)

                error_msg = str(exc_info.value)
                assert "not a GitHub repository" in error_msg
                assert "gitlab.com" in error_msg

    def test_from_project_dir_defaults_to_cwd(self):
        """Test defaults to current working directory when not specified."""
        with patch.object(GitHubClient, "is_gh_available", return_value=True):
            with patch.object(
                GitHubClient,
                "_get_remote_url",
                return_value="git@github.com:owner/repo.git",
            ):
                with patch("cub.core.github.client.Path") as mock_path:
                    mock_path.cwd.return_value = Path("/fake/cwd")

                    GitHubClient.from_project_dir(None)

                    mock_path.cwd.assert_called_once()


class TestGitHubClient:
    """Tests for GitHubClient."""

    def test_is_gh_available_success(self):
        """Test gh availability check when installed and authenticated."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            assert GitHubClient.is_gh_available() is True

            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["gh", "auth", "status"]

    def test_is_gh_available_not_authenticated(self):
        """Test gh availability check when not authenticated."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            assert GitHubClient.is_gh_available() is False

    def test_is_gh_available_not_installed(self):
        """Test gh availability check when not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            assert GitHubClient.is_gh_available() is False

    def test_get_issue_success(self):
        """Test fetching issue successfully."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        issue_data = {
            "number": 42,
            "title": "Test issue",
            "body": "Description",
            "state": "open",
            "html_url": "https://github.com/user/project/issues/42",
            "labels": [],
            "assignees": [],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(issue_data),
            )

            issue = client.get_issue(42)

            assert issue.number == 42
            assert issue.title == "Test issue"

    def test_get_issue_not_found(self):
        """Test fetching nonexistent issue."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="404 Not Found",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.get_issue(99999)

            assert "not found" in str(exc_info.value).lower()

    def test_add_comment_success(self):
        """Test adding comment successfully."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Should not raise
            client.add_comment(42, "Test comment")

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "repos/user/project/issues/42/comments" in call_args

    def test_add_comment_failure(self):
        """Test adding comment failure."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Permission denied",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.add_comment(42, "Test comment")

            assert "Failed to add comment" in str(exc_info.value)

    def test_close_issue_success(self):
        """Test closing issue successfully."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Should not raise
            client.close_issue(42)

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "repos/user/project/issues/42" in call_args
            assert "state=closed" in call_args

    def test_get_current_branch(self):
        """Test getting current branch."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="feature/my-branch\n",
            )

            branch = client.get_current_branch()
            assert branch == "feature/my-branch"

    def test_get_head_commit(self):
        """Test getting HEAD commit."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="abc123def456\n",
            )

            commit = client.get_head_commit()
            assert commit == "abc123def456"

    def test_get_commits_between_success(self):
        """Test getting commits between branches."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        # Simulate git log output with null separator
        git_output = "abc1234|Add feature X|This is the body\x00def5678|Fix bug Y|\x00"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            commits = client.get_commits_between("main", "feature")

            assert len(commits) == 2
            assert commits[0]["sha"] == "abc1234"
            assert commits[0]["subject"] == "Add feature X"
            assert commits[0]["body"] == "This is the body"
            assert commits[1]["sha"] == "def5678"
            assert commits[1]["subject"] == "Fix bug Y"
            assert commits[1]["body"] == ""

    def test_get_commits_between_empty(self):
        """Test getting commits when there are none."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
            )

            commits = client.get_commits_between("main", "main")

            assert commits == []

    def test_get_commits_between_failure(self):
        """Test getting commits when git command fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            commits = client.get_commits_between("main", "nonexistent")

            assert commits == []

    def test_get_files_changed_success(self):
        """Test getting files changed between branches."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        git_output = "A\tsrc/new_file.py\nM\tsrc/modified.py\nD\tsrc/deleted.py\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            files = client.get_files_changed("main", "feature")

            assert files["added"] == ["src/new_file.py"]
            assert files["modified"] == ["src/modified.py"]
            assert files["deleted"] == ["src/deleted.py"]

    def test_get_files_changed_renamed(self):
        """Test getting files changed with renames."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        git_output = "R100\told_name.py\tnew_name.py\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            files = client.get_files_changed("main", "feature")

            # Renames use the new name (renamed-to file)
            assert files["modified"] == ["new_name.py"]

    def test_get_files_changed_empty(self):
        """Test getting files changed when there are none."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
            )

            files = client.get_files_changed("main", "main")

            assert files == {"added": [], "modified": [], "deleted": []}

    def test_get_diff_stat_success(self):
        """Test getting diff statistics."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        git_output = " 3 files changed, 50 insertions(+), 10 deletions(-)\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            stats = client.get_diff_stat("main", "feature")

            assert stats["files"] == 3
            assert stats["insertions"] == 50
            assert stats["deletions"] == 10

    def test_get_diff_stat_insertions_only(self):
        """Test getting diff statistics with only insertions."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        git_output = " 1 file changed, 25 insertions(+)\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            stats = client.get_diff_stat("main", "feature")

            assert stats["files"] == 1
            assert stats["insertions"] == 25
            assert stats["deletions"] == 0

    def test_get_diff_stat_empty(self):
        """Test getting diff statistics when there are no changes."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
            )

            stats = client.get_diff_stat("main", "main")

            assert stats == {"files": 0, "insertions": 0, "deletions": 0}

    def test_get_diff_stat_deletions_only(self):
        """Test getting diff statistics with only deletions."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        git_output = " 2 files changed, 30 deletions(-)\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            stats = client.get_diff_stat("main", "feature")

            assert stats["files"] == 2
            assert stats["insertions"] == 0
            assert stats["deletions"] == 30

    def test_get_diff_stat_failure(self):
        """Test getting diff statistics when git command fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            stats = client.get_diff_stat("main", "nonexistent")

            assert stats == {"files": 0, "insertions": 0, "deletions": 0}

    def test_get_diff_stat_os_error(self):
        """Test getting diff statistics when git is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")

            stats = client.get_diff_stat("main", "feature")

            assert stats == {"files": 0, "insertions": 0, "deletions": 0}

    def test_is_gh_available_os_error(self):
        """Test gh availability check when OSError occurs."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Process error")

            assert GitHubClient.is_gh_available() is False

    def test_get_issue_api_error(self):
        """Test fetching issue with API error (not 404)."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="403 Forbidden",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.get_issue(42)

            assert "Failed to fetch issue" in str(exc_info.value)
            assert "403 Forbidden" in str(exc_info.value)

    def test_get_issue_json_parse_error(self):
        """Test fetching issue when JSON response is malformed."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.get_issue(42)

            assert "Failed to parse GitHub API response" in str(exc_info.value)

    def test_get_issue_os_error(self):
        """Test fetching issue when subprocess fails with OSError."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("gh not found")

            with pytest.raises(GitHubClientError) as exc_info:
                client.get_issue(42)

            assert "Failed to run gh command" in str(exc_info.value)

    def test_get_issue_unknown_error(self):
        """Test fetching issue with unknown error (empty stderr)."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.get_issue(42)

            assert "Unknown error" in str(exc_info.value)

    def test_add_comment_os_error(self):
        """Test adding comment when subprocess fails with OSError."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh")

            with pytest.raises(GitHubClientError) as exc_info:
                client.add_comment(42, "Test comment")

            assert "Failed to run gh command" in str(exc_info.value)

    def test_close_issue_failure(self):
        """Test closing issue when API fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Resource not accessible",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.close_issue(42)

            assert "Failed to close issue" in str(exc_info.value)

    def test_close_issue_os_error(self):
        """Test closing issue when subprocess fails with OSError."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("gh not found")

            with pytest.raises(GitHubClientError) as exc_info:
                client.close_issue(42)

            assert "Failed to run gh command" in str(exc_info.value)

    def test_get_current_branch_failure(self):
        """Test getting current branch when git command fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            branch = client.get_current_branch()
            assert branch is None

    def test_get_current_branch_os_error(self):
        """Test getting current branch when git is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")

            branch = client.get_current_branch()
            assert branch is None

    def test_get_head_commit_failure(self):
        """Test getting HEAD commit when git command fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128)

            commit = client.get_head_commit()
            assert commit is None

    def test_get_head_commit_os_error(self):
        """Test getting HEAD commit when git is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git")

            commit = client.get_head_commit()
            assert commit is None

    def test_create_pr_success(self):
        """Test creating PR successfully."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/user/project/pull/123\n",
            )

            result = client.create_pr(
                head="feature-branch",
                base="main",
                title="Add feature",
                body="This PR adds a feature",
            )

            assert result["url"] == "https://github.com/user/project/pull/123"
            assert result["number"] == 123

            # Verify command structure
            call_args = mock_run.call_args[0][0]
            assert "gh" in call_args
            assert "pr" in call_args
            assert "create" in call_args
            assert "--head" in call_args
            assert "feature-branch" in call_args
            assert "--base" in call_args
            assert "main" in call_args

    def test_create_pr_with_draft(self):
        """Test creating draft PR."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/user/project/pull/456\n",
            )

            result = client.create_pr(
                head="feature-branch",
                base="main",
                title="WIP: Add feature",
                body="Work in progress",
                draft=True,
            )

            assert result["number"] == 456

            # Verify --draft flag is included
            call_args = mock_run.call_args[0][0]
            assert "--draft" in call_args

    def test_create_pr_failure(self):
        """Test PR creation failure."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Branch not pushed to remote",
                stdout="",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.create_pr(
                    head="feature-branch",
                    base="main",
                    title="Add feature",
                    body="Body",
                )

            assert "Failed to create PR" in str(exc_info.value)
            assert "Branch not pushed" in str(exc_info.value)

    def test_create_pr_failure_stdout_error(self):
        """Test PR creation failure with error in stdout."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="",
                stdout="Pull request already exists",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.create_pr(
                    head="feature-branch",
                    base="main",
                    title="Add feature",
                    body="Body",
                )

            assert "Pull request already exists" in str(exc_info.value)

    def test_create_pr_os_error(self):
        """Test PR creation when gh is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh")

            with pytest.raises(GitHubClientError) as exc_info:
                client.create_pr(
                    head="feature-branch",
                    base="main",
                    title="Add feature",
                    body="Body",
                )

            assert "Failed to run gh command" in str(exc_info.value)

    def test_create_pr_url_parsing_error(self):
        """Test PR creation with malformed URL response."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="some-unexpected-output\n",
            )

            result = client.create_pr(
                head="feature-branch",
                base="main",
                title="Add feature",
                body="Body",
            )

            # Should return 0 when URL can't be parsed
            assert result["url"] == "some-unexpected-output"
            assert result["number"] == 0

    def test_get_pr_by_branch_existing(self):
        """Test getting existing PR by branch."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        pr_data = {
            "number": 42,
            "url": "https://github.com/user/project/pull/42",
            "title": "Feature PR",
            "state": "OPEN",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(pr_data),
            )

            result = client.get_pr_by_branch("feature-branch", "main")

            assert result is not None
            assert result["number"] == 42
            assert result["title"] == "Feature PR"
            assert result["state"] == "OPEN"

    def test_get_pr_by_branch_no_pr(self):
        """Test getting PR by branch when none exists."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="null",
            )

            result = client.get_pr_by_branch("feature-branch", "main")

            assert result is None

    def test_get_pr_by_branch_empty_output(self):
        """Test getting PR by branch with empty output."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
            )

            result = client.get_pr_by_branch("feature-branch", "main")

            assert result is None

    def test_get_pr_by_branch_error(self):
        """Test getting PR by branch when command fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = client.get_pr_by_branch("feature-branch", "main")

            assert result is None

    def test_get_pr_by_branch_json_error(self):
        """Test getting PR by branch with malformed JSON."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not json",
            )

            result = client.get_pr_by_branch("feature-branch", "main")

            assert result is None

    def test_get_pr_by_branch_os_error(self):
        """Test getting PR by branch when gh not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("gh not found")

            result = client.get_pr_by_branch("feature-branch", "main")

            assert result is None

    def test_get_pr_success(self):
        """Test getting PR details successfully."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        pr_data = {
            "number": 42,
            "url": "https://github.com/user/project/pull/42",
            "title": "Feature PR",
            "state": "OPEN",
            "headRefName": "feature-branch",
            "baseRefName": "main",
            "mergeable": "MERGEABLE",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(pr_data),
            )

            result = client.get_pr(42)

            assert result is not None
            assert result["number"] == 42
            assert result["head"] == "feature-branch"
            assert result["base"] == "main"
            assert result["mergeable"] == "MERGEABLE"

    def test_get_pr_by_branch_name(self):
        """Test getting PR details by branch name."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        pr_data = {
            "number": 42,
            "url": "https://github.com/user/project/pull/42",
            "title": "Feature PR",
            "state": "OPEN",
            "headRefName": "feature-branch",
            "baseRefName": "main",
            "mergeable": "MERGEABLE",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(pr_data),
            )

            result = client.get_pr("feature-branch")

            assert result is not None
            # Verify branch name was passed to command
            call_args = mock_run.call_args[0][0]
            assert "feature-branch" in call_args

    def test_get_pr_not_found(self):
        """Test getting PR that doesn't exist."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = client.get_pr(99999)

            assert result is None

    def test_get_pr_json_error(self):
        """Test getting PR with malformed JSON response."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not json",
            )

            result = client.get_pr(42)

            assert result is None

    def test_get_pr_os_error(self):
        """Test getting PR when gh not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh")

            result = client.get_pr(42)

            assert result is None

    def test_get_pr_checks_success(self):
        """Test getting PR checks successfully."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        checks_data = [
            {"name": "tests", "status": "completed", "conclusion": "success"},
            {"name": "lint", "status": "completed", "conclusion": "success"},
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(checks_data),
            )

            checks = client.get_pr_checks(42)

            assert len(checks) == 2
            assert checks[0]["name"] == "tests"
            assert checks[0]["conclusion"] == "success"

    def test_get_pr_checks_empty(self):
        """Test getting PR checks when none exist."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="[]",
            )

            checks = client.get_pr_checks(42)

            assert checks == []

    def test_get_pr_checks_failure(self):
        """Test getting PR checks when command fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            checks = client.get_pr_checks(42)

            assert checks == []

    def test_get_pr_checks_json_error(self):
        """Test getting PR checks with malformed JSON."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not json",
            )

            checks = client.get_pr_checks(42)

            assert checks == []

    def test_get_pr_checks_os_error(self):
        """Test getting PR checks when gh not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("gh not found")

            checks = client.get_pr_checks(42)

            assert checks == []

    def test_wait_for_checks_success(self):
        """Test waiting for checks successfully."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = client.wait_for_checks(42)

            assert result is True
            # Verify --watch flag
            call_args = mock_run.call_args[0][0]
            assert "--watch" in call_args

    def test_wait_for_checks_failure(self):
        """Test waiting for checks when checks fail."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = client.wait_for_checks(42)

            assert result is False

    def test_wait_for_checks_timeout(self):
        """Test waiting for checks with timeout."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=600)

            result = client.wait_for_checks(42, timeout=600)

            assert result is False

    def test_wait_for_checks_os_error(self):
        """Test waiting for checks when gh not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh")

            result = client.wait_for_checks(42)

            assert result is False

    def test_merge_pr_success_squash(self):
        """Test merging PR successfully with squash."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = client.merge_pr(42, method="squash")

            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "--squash" in call_args
            assert "--delete-branch" in call_args

    def test_merge_pr_success_merge(self):
        """Test merging PR with merge method."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = client.merge_pr(42, method="merge")

            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "--merge" in call_args

    def test_merge_pr_success_rebase(self):
        """Test merging PR with rebase method."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = client.merge_pr(42, method="rebase")

            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "--rebase" in call_args

    def test_merge_pr_no_delete_branch(self):
        """Test merging PR without deleting branch."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = client.merge_pr(42, delete_branch=False)

            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "--no-delete-branch" in call_args

    def test_merge_pr_failure(self):
        """Test merging PR when merge fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Merge conflicts",
                stdout="",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.merge_pr(42)

            assert "Failed to merge PR" in str(exc_info.value)
            assert "Merge conflicts" in str(exc_info.value)

    def test_merge_pr_os_error(self):
        """Test merging PR when gh not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("gh not found")

            with pytest.raises(GitHubClientError) as exc_info:
                client.merge_pr(42)

            assert "Failed to run gh command" in str(exc_info.value)

    def test_needs_push_no_upstream(self):
        """Test needs_push when no upstream exists."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = client.needs_push("feature-branch")

            assert result is True

    def test_needs_push_ahead_of_remote(self):
        """Test needs_push when branch is ahead of remote."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            # First call returns upstream, second call returns ahead count
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="origin/feature-branch\n"),
                MagicMock(returncode=0, stdout="3\n"),
            ]

            result = client.needs_push("feature-branch")

            assert result is True

    def test_needs_push_up_to_date(self):
        """Test needs_push when branch is up to date."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="origin/feature-branch\n"),
                MagicMock(returncode=0, stdout="0\n"),
            ]

            result = client.needs_push("feature-branch")

            assert result is False

    def test_needs_push_rev_list_fails(self):
        """Test needs_push when rev-list command fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="origin/feature-branch\n"),
                MagicMock(returncode=1),
            ]

            result = client.needs_push("feature-branch")

            assert result is True

    def test_needs_push_os_error(self):
        """Test needs_push when git is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")

            result = client.needs_push("feature-branch")

            assert result is True

    def test_needs_push_value_error(self):
        """Test needs_push when ahead count is not a number."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="origin/feature-branch\n"),
                MagicMock(returncode=0, stdout="not a number\n"),
            ]

            result = client.needs_push("feature-branch")

            assert result is True

    def test_push_branch_success(self):
        """Test pushing branch successfully."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Should not raise
            client.push_branch("feature-branch")

            call_args = mock_run.call_args[0][0]
            assert "git" in call_args
            assert "push" in call_args
            assert "-u" in call_args
            assert "origin" in call_args
            assert "feature-branch" in call_args

    def test_push_branch_failure(self):
        """Test pushing branch when push fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Permission denied (publickey)",
            )

            with pytest.raises(GitHubClientError) as exc_info:
                client.push_branch("feature-branch")

            assert "Failed to push branch" in str(exc_info.value)
            assert "Permission denied" in str(exc_info.value)

    def test_push_branch_os_error(self):
        """Test pushing branch when git is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git")

            with pytest.raises(GitHubClientError) as exc_info:
                client.push_branch("feature-branch")

            assert "Failed to run git command" in str(exc_info.value)

    def test_branch_exists_on_remote_true(self):
        """Test checking branch exists on remote when it does."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="abc123def456\trefs/heads/feature-branch\n",
            )

            result = client.branch_exists_on_remote("feature-branch")

            assert result is True

    def test_branch_exists_on_remote_false(self):
        """Test checking branch exists on remote when it doesn't."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
            )

            result = client.branch_exists_on_remote("nonexistent-branch")

            assert result is False

    def test_branch_exists_on_remote_os_error(self):
        """Test checking branch on remote when git is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")

            result = client.branch_exists_on_remote("feature-branch")

            assert result is False

    def test_get_commits_between_os_error(self):
        """Test getting commits when git is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git")

            commits = client.get_commits_between("main", "feature")

            assert commits == []

    def test_get_commits_between_partial_parse(self):
        """Test getting commits with partial data."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        # Only has sha and subject, no body
        git_output = "abc1234|Add feature X\x00"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            commits = client.get_commits_between("main", "feature")

            assert len(commits) == 1
            assert commits[0]["sha"] == "abc1234"
            assert commits[0]["subject"] == "Add feature X"
            assert commits[0]["body"] == ""

    def test_get_files_changed_failure(self):
        """Test getting files changed when git command fails."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            files = client.get_files_changed("main", "nonexistent")

            assert files == {"added": [], "modified": [], "deleted": []}

    def test_get_files_changed_os_error(self):
        """Test getting files changed when git is not available."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")

            files = client.get_files_changed("main", "feature")

            assert files == {"added": [], "modified": [], "deleted": []}

    def test_get_files_changed_rename_short_format(self):
        """Test getting files changed with rename in short format (2 fields)."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        # Some rename formats only have 2 fields
        git_output = "R100\tnew_name.py\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            files = client.get_files_changed("main", "feature")

            # Should fall back to parts[1]
            assert files["modified"] == ["new_name.py"]

    def test_get_files_changed_skips_invalid_lines(self):
        """Test getting files changed skips lines with too few parts."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)

        git_output = "M\tsrc/file.py\nX\ninvalid\nA\tsrc/new.py\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=git_output,
            )

            files = client.get_files_changed("main", "feature")

            assert files["modified"] == ["src/file.py"]
            assert files["added"] == ["src/new.py"]
            assert files["deleted"] == []
