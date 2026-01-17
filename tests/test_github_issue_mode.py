"""
Tests for GitHub Issue Mode functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from cub.core.github.client import GitHubClient, GitHubClientError
from cub.core.github.issue_mode import GitHubIssueMode
from cub.core.github.models import GitHubIssue, RepoInfo


class TestGitHubIssueModePromptGeneration:
    """Tests for prompt generation."""

    def test_generate_prompt_basic(self):
        """Test basic prompt generation."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(
            number=123,
            title="Fix the login bug",
            body="Users cannot log in with special characters.",
            state="open",
            labels=["bug", "priority-high"],
            url="https://github.com/user/project/issues/123",
        )

        mode = GitHubIssueMode(client=client, issue=issue)
        prompt = mode.generate_prompt()

        assert "## CURRENT TASK" in prompt
        assert "GitHub Issue: #123" in prompt
        assert "Repository: user/project" in prompt
        assert "Fix the login bug" in prompt
        assert "Users cannot log in with special characters" in prompt
        assert "bug, priority-high" in prompt
        assert "fixes #123" in prompt

    def test_generate_prompt_no_body(self):
        """Test prompt generation with no issue body."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(
            number=1,
            title="Simple issue",
            body="",
            state="open",
        )

        mode = GitHubIssueMode(client=client, issue=issue)
        prompt = mode.generate_prompt()

        assert "(No description provided)" in prompt

    def test_generate_prompt_no_labels(self):
        """Test prompt generation with no labels."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(
            number=1,
            title="Simple issue",
            body="Description",
            state="open",
            labels=[],
        )

        mode = GitHubIssueMode(client=client, issue=issue)
        prompt = mode.generate_prompt()

        # Labels line should not be present when empty
        assert "Labels:" not in prompt

    def test_generate_prompt_mentions_no_beads(self):
        """Test prompt mentions no beads commands needed."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(
            number=1,
            title="Test",
            body="Test",
            state="open",
        )

        mode = GitHubIssueMode(client=client, issue=issue)
        prompt = mode.generate_prompt()

        assert "No bd/beads commands needed" in prompt


class TestGitHubIssueModeClosureDetection:
    """Tests for issue closure detection."""

    def test_should_close_on_main_with_new_commits(self):
        """Test closure detection when on main with new commits."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=1, title="Test", state="open")

        with patch.object(client, "get_current_branch", return_value="main"):
            with patch.object(client, "get_head_commit", return_value="new-commit"):
                mode = GitHubIssueMode(
                    client=client,
                    issue=issue,
                    initial_commit="old-commit",
                )

                assert mode.should_close_issue() is True

    def test_should_close_on_master_with_new_commits(self):
        """Test closure detection when on master with new commits."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=1, title="Test", state="open")

        with patch.object(client, "get_current_branch", return_value="master"):
            with patch.object(client, "get_head_commit", return_value="new-commit"):
                mode = GitHubIssueMode(
                    client=client,
                    issue=issue,
                    initial_commit="old-commit",
                )

                assert mode.should_close_issue() is True

    def test_should_not_close_on_feature_branch(self):
        """Test no closure on feature branch."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=1, title="Test", state="open")

        with patch.object(client, "get_current_branch", return_value="feature/my-feature"):
            with patch.object(client, "get_head_commit", return_value="new-commit"):
                mode = GitHubIssueMode(
                    client=client,
                    issue=issue,
                    initial_commit="old-commit",
                )

                assert mode.should_close_issue() is False

    def test_should_not_close_without_new_commits(self):
        """Test no closure when no new commits."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=1, title="Test", state="open")

        with patch.object(client, "get_current_branch", return_value="main"):
            with patch.object(client, "get_head_commit", return_value="same-commit"):
                mode = GitHubIssueMode(
                    client=client,
                    issue=issue,
                    initial_commit="same-commit",
                )

                assert mode.should_close_issue() is False


class TestGitHubIssueModeComments:
    """Tests for comment posting."""

    def test_post_start_comment(self):
        """Test posting start comment."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=42, title="Test", state="open")

        mode = GitHubIssueMode(client=client, issue=issue)

        with patch.object(client, "get_current_branch", return_value="feature/test"):
            with patch.object(client, "add_comment") as mock_add:
                mode.post_start_comment()

                mock_add.assert_called_once()
                call_args = mock_add.call_args
                assert call_args[0][0] == 42  # issue number
                assert "Cub" in call_args[0][1]
                assert "starting work" in call_args[0][1]
                assert "feature/test" in call_args[0][1]

    def test_post_completion_comment_on_main(self):
        """Test posting completion comment when on main."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=42, title="Test", state="open")

        mode = GitHubIssueMode(client=client, issue=issue)

        with patch.object(client, "add_comment") as mock_add:
            mode.post_completion_comment(on_main=True)

            mock_add.assert_called_once()
            call_args = mock_add.call_args
            assert "Completed" in call_args[0][1] or "completed" in call_args[0][1]
            assert "main" in call_args[0][1].lower()

    def test_post_completion_comment_on_branch(self):
        """Test posting completion comment when on feature branch."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=42, title="Test", state="open")

        mode = GitHubIssueMode(client=client, issue=issue)

        with patch.object(client, "get_current_branch", return_value="feature/fix"):
            with patch.object(client, "add_comment") as mock_add:
                mode.post_completion_comment(on_main=False)

                mock_add.assert_called_once()
                call_args = mock_add.call_args
                assert "feature/fix" in call_args[0][1]
                assert "merged" in call_args[0][1].lower()

    def test_comment_failure_does_not_raise(self):
        """Test comment failure is swallowed (non-critical)."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=42, title="Test", state="open")

        mode = GitHubIssueMode(client=client, issue=issue)

        with patch.object(client, "get_current_branch", return_value="main"):
            with patch.object(client, "add_comment", side_effect=GitHubClientError("Failed")):
                # Should not raise
                mode.post_start_comment()


class TestGitHubIssueModeFromProjectDir:
    """Tests for from_project_dir factory."""

    def test_from_project_dir_success(self, tmp_path):
        """Test successful initialization from project dir."""
        import json

        issue_data = {
            "number": 123,
            "title": "Test issue",
            "body": "Description",
            "state": "open",
            "html_url": "https://github.com/user/repo/issues/123",
            "labels": [],
            "assignees": [],
        }

        with patch.object(GitHubClient, "is_gh_available", return_value=True):
            with patch.object(
                GitHubClient, "_get_remote_url", return_value="git@github.com:user/repo.git"
            ):
                with patch("subprocess.run") as mock_run:
                    # Mock for get_issue
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout=json.dumps(issue_data),
                    )

                    mode = GitHubIssueMode.from_project_dir(123, tmp_path)

                    assert mode.issue.number == 123
                    assert mode.repo.owner == "user"
                    assert mode.repo.repo == "repo"

    def test_from_project_dir_closed_issue(self, tmp_path):
        """Test error when issue is already closed."""
        import json

        closed_issue = {
            "number": 123,
            "title": "Closed",
            "body": "",
            "state": "closed",
            "html_url": "",
            "labels": [],
            "assignees": [],
        }

        with patch.object(GitHubClient, "is_gh_available", return_value=True):
            with patch.object(
                GitHubClient, "_get_remote_url", return_value="git@github.com:user/repo.git"
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout=json.dumps(closed_issue),
                    )

                    with pytest.raises(GitHubClientError) as exc_info:
                        GitHubIssueMode.from_project_dir(123, tmp_path)

                    assert "already closed" in str(exc_info.value)

    def test_from_project_dir_gh_not_available(self, tmp_path):
        """Test error when gh is not available."""
        with patch.object(GitHubClient, "is_gh_available", return_value=False):
            with pytest.raises(GitHubClientError) as exc_info:
                GitHubIssueMode.from_project_dir(123, tmp_path)

            assert "not installed" in str(exc_info.value) or "not authenticated" in str(
                exc_info.value
            )


class TestGitHubIssueModeFinish:
    """Tests for finish() method."""

    def test_finish_closes_on_main(self):
        """Test finish closes issue when on main with new commits."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=42, title="Test", state="open")

        mode = GitHubIssueMode(client=client, issue=issue, initial_commit="old")

        with patch.object(client, "get_current_branch", return_value="main"):
            with patch.object(client, "get_head_commit", return_value="new"):
                with patch.object(client, "add_comment"):
                    with patch.object(client, "close_issue") as mock_close:
                        mode.finish()

                        mock_close.assert_called_once_with(42)

    def test_finish_does_not_close_on_branch(self):
        """Test finish does not close when on feature branch."""
        repo = RepoInfo(owner="user", repo="project")
        client = GitHubClient(repo)
        issue = GitHubIssue(number=42, title="Test", state="open")

        mode = GitHubIssueMode(client=client, issue=issue, initial_commit="old")

        with patch.object(client, "get_current_branch", return_value="feature/test"):
            with patch.object(client, "get_head_commit", return_value="new"):
                with patch.object(client, "add_comment"):
                    with patch.object(client, "close_issue") as mock_close:
                        mode.finish()

                        mock_close.assert_not_called()
