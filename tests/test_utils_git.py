"""Tests for cub.utils.git module."""

import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from cub.utils.git import (
    get_commits_between,
    get_commits_since,
    get_current_commit,
    parse_commit_timestamp,
)


class TestParseCommitTimestamp:
    """Tests for parse_commit_timestamp function."""

    def test_iso_format_with_offset(self) -> None:
        result = parse_commit_timestamp("2026-01-24T15:30:00-05:00")
        assert result.tzinfo == timezone.utc
        assert result.hour == 20  # 15:30 EST = 20:30 UTC
        assert result.minute == 30

    def test_iso_format_utc(self) -> None:
        result = parse_commit_timestamp("2026-01-24T12:00:00+00:00")
        assert result.hour == 12
        assert result.minute == 0

    def test_iso_format_positive_offset(self) -> None:
        result = parse_commit_timestamp("2026-01-24T22:00:00+09:00")
        assert result.hour == 13  # 22:00 JST = 13:00 UTC


class TestGetCurrentCommit:
    """Tests for get_current_commit function."""

    @patch("cub.utils.git.subprocess.run")
    def test_returns_commit_hash(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="abc123def456789\n", returncode=0)
        result = get_current_commit()
        assert result == "abc123def456789"
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("cub.utils.git.subprocess.run")
    def test_returns_none_on_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = get_current_commit()
        assert result is None

    @patch("cub.utils.git.subprocess.run")
    def test_returns_none_when_git_not_installed(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("git not found")
        result = get_current_commit()
        assert result is None


class TestGetCommitsSince:
    """Tests for get_commits_since function."""

    @patch("cub.utils.git.subprocess.run")
    def test_with_datetime_input(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout=(
                "abc123|Fix bug|2026-01-24T10:00:00+00:00\n"
                "def456|Add feature|2026-01-24T11:00:00+00:00\n"
            ),
            returncode=0,
        )
        since = datetime(2026, 1, 24, 9, 0, 0, tzinfo=timezone.utc)
        result = get_commits_since(since)

        assert len(result) == 2
        assert result[0]["hash"] == "abc123"
        assert result[0]["message"] == "Fix bug"
        assert result[1]["hash"] == "def456"

    @patch("cub.utils.git.subprocess.run")
    def test_with_string_input(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="abc123|Fix bug|2026-01-24T10:00:00+00:00\n",
            returncode=0,
        )
        result = get_commits_since("2026-01-24T09:00:00")

        assert len(result) == 1
        # Verify the string was passed through directly
        args = mock_run.call_args[0][0]
        assert "--since=2026-01-24T09:00:00" in args

    @patch("cub.utils.git.subprocess.run")
    def test_empty_output(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        result = get_commits_since("2026-01-24T09:00:00")
        assert result == []

    @patch("cub.utils.git.subprocess.run")
    def test_called_process_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = get_commits_since("2026-01-24T09:00:00")
        assert result == []

    @patch("cub.utils.git.subprocess.run")
    def test_git_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()
        result = get_commits_since("2026-01-24T09:00:00")
        assert result == []

    @patch("cub.utils.git.subprocess.run")
    def test_malformed_line_skipped(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout=(
                "abc123|Fix bug|2026-01-24T10:00:00+00:00\n"
                "badline\n"
                "def456|Add feature|2026-01-24T11:00:00+00:00\n"
            ),
            returncode=0,
        )
        result = get_commits_since("2026-01-24T09:00:00")
        assert len(result) == 2


class TestGetCommitsBetween:
    """Tests for get_commits_between function."""

    @patch("cub.utils.git.subprocess.run")
    def test_returns_commits(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout=(
                "abc123|Commit 1|2026-01-24T10:00:00+00:00\n"
                "def456|Commit 2|2026-01-24T11:00:00+00:00\n"
            ),
            returncode=0,
        )
        result = get_commits_between("aaa111", "bbb222")

        assert len(result) == 2
        args = mock_run.call_args[0][0]
        assert "aaa111..bbb222" in args

    @patch("cub.utils.git.subprocess.run")
    def test_default_to_commit_is_head(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        get_commits_between("aaa111")

        args = mock_run.call_args[0][0]
        assert "aaa111..HEAD" in args

    @patch("cub.utils.git.subprocess.run")
    def test_called_process_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = get_commits_between("aaa", "bbb")
        assert result == []

    @patch("cub.utils.git.subprocess.run")
    def test_git_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()
        result = get_commits_between("aaa", "bbb")
        assert result == []
