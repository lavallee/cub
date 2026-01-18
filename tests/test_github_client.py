"""
Tests for GitHub client functionality.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from cub.core.github.client import GitHubClient, GitHubClientError
from cub.core.github.models import GitHubIssue, RepoInfo


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
