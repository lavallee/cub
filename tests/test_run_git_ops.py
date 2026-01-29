"""Tests for cub.core.run.git_ops module."""

import json
from unittest.mock import MagicMock, patch

from cub.core.run.git_ops import (
    BranchCreationResult,
    EpicContext,
    IssueContext,
    create_run_branch,
    get_epic_context,
    get_issue_context,
    slugify,
)


class TestSlugify:
    """Tests for slugify function."""

    def test_basic_slugification(self):
        """Test basic text to slug conversion."""
        assert slugify("Add User Authentication") == "add-user-authentication"

    def test_spaces_and_underscores(self):
        """Test that spaces and underscores become hyphens."""
        assert slugify("test_with_underscores") == "test-with-underscores"
        assert slugify("test with spaces") == "test-with-spaces"
        assert slugify("test_and spaces") == "test-and-spaces"

    def test_special_characters_removed(self):
        """Test that special characters are removed."""
        assert slugify("Fix Bug #123 - API Error") == "fix-bug-123-api-error"
        assert slugify("Feature: New UI!") == "feature-new-ui"
        assert slugify("test@example.com") == "testexamplecom"

    def test_multiple_hyphens_collapsed(self):
        """Test that multiple hyphens are collapsed to one."""
        assert slugify("test---multiple---hyphens") == "test-multiple-hyphens"
        assert slugify("test  multiple  spaces") == "test-multiple-spaces"

    def test_leading_trailing_hyphens_stripped(self):
        """Test that leading/trailing hyphens are removed."""
        assert slugify("-leading-hyphen") == "leading-hyphen"
        assert slugify("trailing-hyphen-") == "trailing-hyphen"
        assert slugify("-both-") == "both"

    def test_max_length_truncation(self):
        """Test that slugs are truncated to max length at word boundaries."""
        long_text = "Very Long Feature Name That Exceeds Maximum Length Limit"
        result = slugify(long_text, max_length=40)
        assert len(result) <= 40
        assert result == "very-long-feature-name-that-exceeds"

    def test_custom_max_length(self):
        """Test custom max length parameter."""
        result = slugify("Short text", max_length=5)
        assert len(result) <= 5
        assert result == "short"

    def test_empty_string(self):
        """Test empty string input."""
        assert slugify("") == ""

    def test_only_special_characters(self):
        """Test string with only special characters."""
        assert slugify("!@#$%^&*()") == ""

    def test_unicode_characters(self):
        """Test that unicode characters are removed."""
        assert slugify("café résumé") == "caf-rsum"

    def test_numbers_preserved(self):
        """Test that numbers are preserved in slugs."""
        assert slugify("API v2.0 Release") == "api-v20-release"
        assert slugify("Issue-123-fix") == "issue-123-fix"


class TestGetEpicContext:
    """Tests for get_epic_context function."""

    @patch("cub.core.run.git_ops._get_epic_title")
    def test_with_title(self, mock_get_title):
        """Test getting epic context when title is available."""
        mock_get_title.return_value = "Core/interface refactor"
        context = get_epic_context("cub-b1a")
        assert isinstance(context, EpicContext)
        assert context.epic_id == "cub-b1a"
        assert context.title == "Core/interface refactor"
        mock_get_title.assert_called_once_with("cub-b1a")

    @patch("cub.core.run.git_ops._get_epic_title")
    def test_without_title(self, mock_get_title):
        """Test getting epic context when title is not available."""
        mock_get_title.return_value = None
        context = get_epic_context("cub-123")
        assert isinstance(context, EpicContext)
        assert context.epic_id == "cub-123"
        assert context.title is None
        mock_get_title.assert_called_once_with("cub-123")


class TestGetIssueContext:
    """Tests for get_issue_context function."""

    @patch("cub.core.run.git_ops._get_gh_issue_title")
    def test_with_title(self, mock_get_title):
        """Test getting issue context when title is available."""
        mock_get_title.return_value = "Fix authentication bug"
        context = get_issue_context(123)
        assert isinstance(context, IssueContext)
        assert context.issue_number == 123
        assert context.title == "Fix authentication bug"
        mock_get_title.assert_called_once_with(123)

    @patch("cub.core.run.git_ops._get_gh_issue_title")
    def test_without_title(self, mock_get_title):
        """Test getting issue context when title is not available."""
        mock_get_title.return_value = None
        context = get_issue_context(456)
        assert isinstance(context, IssueContext)
        assert context.issue_number == 456
        assert context.title is None
        mock_get_title.assert_called_once_with(456)


class TestCreateRunBranch:
    """Tests for create_run_branch function."""

    @patch("subprocess.run")
    @patch("cub.core.branches.store.BranchStore.git_branch_exists")
    def test_create_new_branch_success(self, mock_exists, mock_run):
        """Test successfully creating a new branch."""
        # Branch doesn't exist, base branch exists
        mock_exists.side_effect = [False, True]  # branch doesn't exist, base exists
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = create_run_branch("feature/new-feature", "origin/main")

        assert isinstance(result, BranchCreationResult)
        assert result.success is True
        assert result.created is True
        assert result.branch_name == "feature/new-feature"
        assert result.error is None

        # Verify git checkout -b was called
        mock_run.assert_called_once_with(
            ["git", "checkout", "-b", "feature/new-feature", "origin/main"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    @patch("cub.core.branches.store.BranchStore.git_branch_exists")
    def test_switch_to_existing_branch(self, mock_exists, mock_run):
        """Test switching to an existing branch."""
        # Branch already exists
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = create_run_branch("feature/existing", "main")

        assert result.success is True
        assert result.created is False
        assert result.branch_name == "feature/existing"
        assert result.error is None

        # Verify git checkout was called (not checkout -b)
        mock_run.assert_called_once_with(
            ["git", "checkout", "feature/existing"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    @patch("cub.core.branches.store.BranchStore.git_branch_exists")
    def test_switch_to_existing_branch_fails(self, mock_exists, mock_run):
        """Test failure when switching to existing branch fails."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="error: pathspec 'feature/existing' did not match any file(s) known to git",
        )

        result = create_run_branch("feature/existing", "main")

        assert result.success is False
        assert result.created is False
        assert result.branch_name == "feature/existing"
        assert "Failed to switch to branch" in result.error

    @patch("cub.core.branches.store.BranchStore.git_branch_exists")
    def test_base_branch_not_found(self, mock_exists):
        """Test failure when base branch doesn't exist."""
        # Branch doesn't exist, base doesn't exist (both local and remote)
        mock_exists.side_effect = [False, False, False]

        result = create_run_branch("feature/new", "nonexistent")

        assert result.success is False
        assert result.created is False
        assert result.branch_name == "feature/new"
        assert "Base branch 'nonexistent' does not exist" in result.error

    @patch("cub.core.branches.store.BranchStore.git_branch_exists")
    def test_tries_remote_base_branch(self, mock_exists):
        """Test that it tries origin/ prefix if local base doesn't exist."""
        # Branch doesn't exist, local base doesn't exist, remote base exists
        mock_exists.side_effect = [False, False, True]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = create_run_branch("feature/new", "main")

            assert result.success is True
            assert result.created is True

            # Verify it used origin/main as the base
            mock_run.assert_called_once_with(
                ["git", "checkout", "-b", "feature/new", "origin/main"],
                capture_output=True,
                text=True,
                check=False,
            )

    @patch("subprocess.run")
    @patch("cub.core.branches.store.BranchStore.git_branch_exists")
    def test_create_branch_fails(self, mock_exists, mock_run):
        """Test failure when git checkout -b fails."""
        mock_exists.side_effect = [False, True]
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="fatal: A branch named 'feature/new' already exists.",
        )

        result = create_run_branch("feature/new", "main")

        assert result.success is False
        assert result.created is False
        assert "Failed to create branch" in result.error


class TestGetGhIssueTitle:
    """Tests for _get_gh_issue_title internal function."""

    @patch("subprocess.run")
    def test_successful_retrieval(self, mock_run):
        """Test successfully retrieving issue title."""
        from cub.core.run.git_ops import _get_gh_issue_title

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Fix authentication bug\n",
        )

        title = _get_gh_issue_title(123)

        assert title == "Fix authentication bug"
        mock_run.assert_called_once_with(
            ["gh", "issue", "view", "123", "--json", "title", "-q", ".title"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_gh_command_fails(self, mock_run):
        """Test when gh command fails."""
        from cub.core.run.git_ops import _get_gh_issue_title

        mock_run.return_value = MagicMock(returncode=1, stdout="")

        title = _get_gh_issue_title(999)

        assert title is None

    @patch("subprocess.run")
    def test_gh_not_installed(self, mock_run):
        """Test when gh CLI is not installed."""
        from cub.core.run.git_ops import _get_gh_issue_title

        mock_run.side_effect = FileNotFoundError()

        title = _get_gh_issue_title(123)

        assert title is None

    @patch("subprocess.run")
    def test_os_error(self, mock_run):
        """Test when OSError occurs."""
        from cub.core.run.git_ops import _get_gh_issue_title

        mock_run.side_effect = OSError("Permission denied")

        title = _get_gh_issue_title(123)

        assert title is None


class TestGetEpicTitle:
    """Tests for _get_epic_title internal function."""

    @patch("subprocess.run")
    def test_successful_retrieval(self, mock_run):
        """Test successfully retrieving epic title."""
        from cub.core.run.git_ops import _get_epic_title

        epic_data = [{"id": "cub-b1a", "title": "Core/interface refactor"}]
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(epic_data),
        )

        title = _get_epic_title("cub-b1a")

        assert title == "Core/interface refactor"
        mock_run.assert_called_once_with(
            ["bd", "show", "cub-b1a", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_dict_format(self, mock_run):
        """Test handling dict format (not wrapped in list)."""
        from cub.core.run.git_ops import _get_epic_title

        epic_data = {"id": "cub-123", "title": "New Feature"}
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(epic_data),
        )

        title = _get_epic_title("cub-123")

        assert title == "New Feature"

    @patch("subprocess.run")
    def test_bd_command_fails(self, mock_run):
        """Test when bd command fails."""
        from cub.core.run.git_ops import _get_epic_title

        mock_run.return_value = MagicMock(returncode=1, stdout="")

        title = _get_epic_title("cub-999")

        assert title is None

    @patch("subprocess.run")
    def test_bd_not_installed(self, mock_run):
        """Test when bd CLI is not installed."""
        from cub.core.run.git_ops import _get_epic_title

        mock_run.side_effect = FileNotFoundError()

        title = _get_epic_title("cub-123")

        assert title is None

    @patch("subprocess.run")
    def test_invalid_json(self, mock_run):
        """Test when bd returns invalid JSON."""
        from cub.core.run.git_ops import _get_epic_title

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json",
        )

        title = _get_epic_title("cub-123")

        assert title is None

    @patch("subprocess.run")
    def test_missing_title_field(self, mock_run):
        """Test when epic data doesn't have title field."""
        from cub.core.run.git_ops import _get_epic_title

        epic_data = [{"id": "cub-123"}]  # No title field
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(epic_data),
        )

        title = _get_epic_title("cub-123")

        assert title is None

    @patch("subprocess.run")
    def test_empty_list(self, mock_run):
        """Test when bd returns empty list."""
        from cub.core.run.git_ops import _get_epic_title

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([]),
        )

        title = _get_epic_title("cub-999")

        assert title is None

    @patch("subprocess.run")
    def test_title_not_string(self, mock_run):
        """Test when title field is not a string."""
        from cub.core.run.git_ops import _get_epic_title

        epic_data = [{"id": "cub-123", "title": 12345}]  # Title is int
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(epic_data),
        )

        title = _get_epic_title("cub-123")

        assert title is None

    @patch("subprocess.run")
    def test_os_error(self, mock_run):
        """Test when OSError occurs."""
        from cub.core.run.git_ops import _get_epic_title

        mock_run.side_effect = OSError("Permission denied")

        title = _get_epic_title("cub-123")

        assert title is None
