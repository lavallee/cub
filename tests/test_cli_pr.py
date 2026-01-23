"""
Tests for the PR CLI command.

Tests the _run_claude_for_ci function and related error handling
for graceful degradation when Claude Code integration fails.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from cub.cli.pr import (
    CLAUDE_CI_TIMEOUT_SECONDS,
    ClaudeCIOutcome,
    ClaudeCIResult,
    _run_claude_for_ci,
)


class TestClaudeCIResult:
    """Tests for ClaudeCIResult enum."""

    def test_all_values_exist(self) -> None:
        """Test all expected enum values exist."""
        assert ClaudeCIResult.SUCCESS.value == "success"
        assert ClaudeCIResult.CLAUDE_NOT_FOUND.value == "claude_not_found"
        assert ClaudeCIResult.EXECUTION_FAILED.value == "execution_failed"
        assert ClaudeCIResult.TIMEOUT.value == "timeout"
        assert ClaudeCIResult.INTERRUPTED.value == "interrupted"


class TestClaudeCIOutcome:
    """Tests for ClaudeCIOutcome dataclass."""

    def test_outcome_with_all_fields(self) -> None:
        """Test creating outcome with all fields."""
        outcome = ClaudeCIOutcome(
            result=ClaudeCIResult.SUCCESS,
            message="Test message",
            exit_code=0,
            stderr=None,
        )
        assert outcome.result == ClaudeCIResult.SUCCESS
        assert outcome.message == "Test message"
        assert outcome.exit_code == 0
        assert outcome.stderr is None

    def test_outcome_with_optional_fields(self) -> None:
        """Test creating outcome without optional fields."""
        outcome = ClaudeCIOutcome(
            result=ClaudeCIResult.CLAUDE_NOT_FOUND,
            message="CLI not found",
        )
        assert outcome.exit_code is None
        assert outcome.stderr is None

    def test_outcome_with_stderr(self) -> None:
        """Test creating outcome with stderr captured."""
        outcome = ClaudeCIOutcome(
            result=ClaudeCIResult.EXECUTION_FAILED,
            message="Claude exited with code 1",
            exit_code=1,
            stderr="Error: No messages returned",
        )
        assert outcome.stderr == "Error: No messages returned"


class TestRunClaudeForCI:
    """Tests for _run_claude_for_ci function."""

    def test_success_returns_success_result(self) -> None:
        """Test successful Claude invocation returns SUCCESS result."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.SUCCESS
        assert "completed successfully" in outcome.message
        assert outcome.exit_code == 0

    def test_nonzero_exit_returns_execution_failed(self) -> None:
        """Test non-zero exit code returns EXECUTION_FAILED result."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Some error"

        with patch("subprocess.run", return_value=mock_result):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.EXECUTION_FAILED
        assert "exited with code 1" in outcome.message
        assert outcome.exit_code == 1
        assert outcome.stderr == "Some error"

    def test_no_messages_error_detected(self) -> None:
        """Test that 'No messages returned' error is detected and noted."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: No messages returned"

        with patch("subprocess.run", return_value=mock_result):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.EXECUTION_FAILED
        assert "Claude returned no response" in outcome.message
        assert outcome.stderr == "Error: No messages returned"

    def test_connection_error_detected(self) -> None:
        """Test that connection errors are detected and noted."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Connection refused"

        with patch("subprocess.run", return_value=mock_result):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.EXECUTION_FAILED
        assert "connection issue" in outcome.message

    def test_file_not_found_returns_claude_not_found(self) -> None:
        """Test FileNotFoundError returns CLAUDE_NOT_FOUND result."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.CLAUDE_NOT_FOUND
        assert "Claude CLI not found" in outcome.message
        assert outcome.exit_code is None

    def test_timeout_returns_timeout_result(self) -> None:
        """Test subprocess.TimeoutExpired returns TIMEOUT result."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 600)):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.TIMEOUT
        assert "timed out" in outcome.message
        assert str(CLAUDE_CI_TIMEOUT_SECONDS) in outcome.message

    def test_keyboard_interrupt_returns_interrupted(self) -> None:
        """Test KeyboardInterrupt returns INTERRUPTED result."""
        with patch("subprocess.run", side_effect=KeyboardInterrupt):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.INTERRUPTED
        assert "Interrupted" in outcome.message

    def test_generic_exception_returns_execution_failed(self) -> None:
        """Test generic exception returns EXECUTION_FAILED result."""
        with patch("subprocess.run", side_effect=OSError("Unexpected error")):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.EXECUTION_FAILED
        assert "Unexpected error" in outcome.message

    def test_subprocess_called_with_correct_args(self) -> None:
        """Test subprocess.run is called with correct arguments."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            _run_claude_for_ci("test prompt")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == [
            "claude",
            "--dangerously-skip-permissions",
            "--print",
            "test prompt",
        ]
        assert call_args[1]["check"] is False
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True
        assert call_args[1]["timeout"] == CLAUDE_CI_TIMEOUT_SECONDS

    def test_empty_stderr_handled(self) -> None:
        """Test empty stderr is handled gracefully."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.EXECUTION_FAILED
        assert outcome.stderr is None  # Empty string converted to None via strip

    def test_none_stderr_handled(self) -> None:
        """Test None stderr is handled gracefully."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = None

        with patch("subprocess.run", return_value=mock_result):
            outcome = _run_claude_for_ci("test prompt")

        assert outcome.result == ClaudeCIResult.EXECUTION_FAILED
        assert outcome.stderr is None


class TestClaudeCITimeoutConstant:
    """Tests for the timeout constant."""

    def test_timeout_is_reasonable(self) -> None:
        """Test timeout is a reasonable value (10 minutes)."""
        assert CLAUDE_CI_TIMEOUT_SECONDS == 600

    def test_timeout_is_positive(self) -> None:
        """Test timeout is a positive value."""
        assert CLAUDE_CI_TIMEOUT_SECONDS > 0
