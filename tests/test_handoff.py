"""
Tests for the handoff utility module.

Tests the try_handoff_or_message function and related utilities
that help provide seamless workflow transitions using Claude Code
slash commands.
"""

from __future__ import annotations

import os
import subprocess
from unittest.mock import MagicMock, patch

from cub.utils.handoff import (
    SLASH_COMMAND_MAP,
    HandoffOutcome,
    HandoffResult,
    attempt_handoff,
    format_shell_command,
    format_slash_command,
    get_next_step_message,
    is_claude_code_environment,
    try_handoff_or_message,
)


class TestFormatSlashCommand:
    """Tests for format_slash_command function."""

    def test_format_without_args(self) -> None:
        """Test formatting a slash command without arguments."""
        result = format_slash_command("architect")
        assert result == "`/cub:architect`"

    def test_format_with_args(self) -> None:
        """Test formatting a slash command with arguments."""
        result = format_slash_command("architect", "my-plan")
        assert result == "`/cub:architect my-plan`"

    def test_format_itemize(self) -> None:
        """Test formatting itemize command."""
        result = format_slash_command("itemize", "test-slug")
        assert result == "`/cub:itemize test-slug`"

    def test_format_orient(self) -> None:
        """Test formatting orient command."""
        result = format_slash_command("orient")
        assert result == "`/cub:orient`"


class TestFormatShellCommand:
    """Tests for format_shell_command function."""

    def test_format_without_args(self) -> None:
        """Test formatting a shell command without arguments."""
        result = format_shell_command("stage")
        assert result == "`cub stage`"

    def test_format_with_args(self) -> None:
        """Test formatting a shell command with arguments."""
        result = format_shell_command("stage", "my-plan")
        assert result == "`cub stage my-plan`"

    def test_format_plan_subcommand(self) -> None:
        """Test formatting plan subcommand."""
        result = format_shell_command("plan architect", "my-plan")
        assert result == "`cub plan architect my-plan`"


class TestSlashCommandMap:
    """Tests for the SLASH_COMMAND_MAP."""

    def test_plan_architect_mapping(self) -> None:
        """Test plan architect has correct mapping."""
        assert SLASH_COMMAND_MAP["plan architect"] == "architect"

    def test_plan_itemize_mapping(self) -> None:
        """Test plan itemize has correct mapping."""
        assert SLASH_COMMAND_MAP["plan itemize"] == "itemize"

    def test_plan_orient_mapping(self) -> None:
        """Test plan orient has correct mapping."""
        assert SLASH_COMMAND_MAP["plan orient"] == "orient"

    def test_stage_not_in_map(self) -> None:
        """Test that stage command is not in the map (no slash equivalent)."""
        assert "stage" not in SLASH_COMMAND_MAP


class TestTryHandoffOrMessage:
    """Tests for try_handoff_or_message function."""

    def test_plan_architect_uses_slash_syntax(self) -> None:
        """Test plan architect returns slash command syntax."""
        success, message = try_handoff_or_message("plan architect", "my-plan")
        assert success is False
        assert "`/cub:architect my-plan`" in message
        assert "[bold]Next step:[/bold]" in message

    def test_plan_itemize_uses_slash_syntax(self) -> None:
        """Test plan itemize returns slash command syntax."""
        success, message = try_handoff_or_message("plan itemize", "my-plan")
        assert success is False
        assert "`/cub:itemize my-plan`" in message

    def test_plan_orient_uses_slash_syntax(self) -> None:
        """Test plan orient returns slash command syntax."""
        success, message = try_handoff_or_message("plan orient", "spec.md")
        assert success is False
        assert "`/cub:orient spec.md`" in message

    def test_stage_uses_shell_syntax(self) -> None:
        """Test stage command (no slash equivalent) uses shell syntax."""
        success, message = try_handoff_or_message("stage", "my-plan")
        assert success is False
        assert "`cub stage my-plan`" in message
        # Should NOT have /cub: prefix
        assert "/cub:" not in message

    def test_unknown_command_uses_shell_syntax(self) -> None:
        """Test unknown command uses shell syntax."""
        success, message = try_handoff_or_message("unknown-cmd", "args")
        assert success is False
        assert "`cub unknown-cmd args`" in message

    def test_command_without_args(self) -> None:
        """Test command without arguments."""
        success, message = try_handoff_or_message("plan architect")
        assert success is False
        assert "`/cub:architect`" in message
        # No trailing space
        assert "`/cub:architect `" not in message


class TestGetNextStepMessage:
    """Tests for get_next_step_message function."""

    def test_prefer_slash_with_mapped_command(self) -> None:
        """Test preferring slash command when available."""
        message = get_next_step_message("plan architect", "my-plan", prefer_slash=True)
        assert "`/cub:architect my-plan`" in message

    def test_prefer_slash_with_unmapped_command(self) -> None:
        """Test shell command used when no slash equivalent exists."""
        message = get_next_step_message("stage", "my-plan", prefer_slash=True)
        assert "`cub stage my-plan`" in message

    def test_disable_prefer_slash(self) -> None:
        """Test disabling slash preference uses shell syntax."""
        message = get_next_step_message("plan architect", "my-plan", prefer_slash=False)
        assert "`cub plan architect my-plan`" in message
        assert "/cub:" not in message


class TestIsClaudeCodeEnvironment:
    """Tests for is_claude_code_environment function."""

    def test_returns_true_when_env_set(self) -> None:
        """Test returns True when CLAUDE_CODE=1."""
        with patch.dict(os.environ, {"CLAUDE_CODE": "1"}):
            assert is_claude_code_environment() is True

    def test_returns_false_when_env_not_set(self) -> None:
        """Test returns False when CLAUDE_CODE not set."""
        env = dict(os.environ)
        env.pop("CLAUDE_CODE", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_claude_code_environment() is False

    def test_returns_false_when_env_different_value(self) -> None:
        """Test returns False when CLAUDE_CODE has different value."""
        with patch.dict(os.environ, {"CLAUDE_CODE": "0"}):
            assert is_claude_code_environment() is False


class TestAttemptHandoff:
    """Tests for attempt_handoff function."""

    def test_success_with_zero_exit_code(self) -> None:
        """Test successful handoff returns SUCCESS result."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            outcome = attempt_handoff("architect", "my-plan")

        assert outcome.result == HandoffResult.SUCCESS
        assert "Handoff to `/cub:architect` initiated" in outcome.message
        assert outcome.exit_code == 0

    def test_failure_with_nonzero_exit_code(self) -> None:
        """Test failed handoff returns EXECUTION_FAILED result."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            outcome = attempt_handoff("architect", "my-plan")

        assert outcome.result == HandoffResult.EXECUTION_FAILED
        assert "exit code 1" in outcome.message
        assert outcome.exit_code == 1

    def test_claude_not_found(self) -> None:
        """Test CLAUDE_NOT_FOUND when claude CLI is missing."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            outcome = attempt_handoff("architect", "my-plan")

        assert outcome.result == HandoffResult.CLAUDE_NOT_FOUND
        assert "Claude CLI not found" in outcome.message
        assert outcome.exit_code is None

    def test_timeout_treated_as_success(self) -> None:
        """Test timeout is treated as success (non-blocking call)."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            outcome = attempt_handoff("architect", "my-plan")

        assert outcome.result == HandoffResult.SUCCESS
        assert "Handoff to `/cub:architect` initiated" in outcome.message
        assert outcome.exit_code == 0

    def test_generic_exception_returns_failed(self) -> None:
        """Test generic exception returns EXECUTION_FAILED."""
        with patch("subprocess.run", side_effect=OSError("Unknown error")):
            outcome = attempt_handoff("architect", "my-plan")

        assert outcome.result == HandoffResult.EXECUTION_FAILED
        assert "Handoff failed" in outcome.message

    def test_builds_correct_command_with_args(self) -> None:
        """Test that correct command is built with args."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            attempt_handoff("architect", "my-plan")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["claude", "/cub:architect my-plan"]

    def test_builds_correct_command_without_args(self) -> None:
        """Test that correct command is built without args."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            attempt_handoff("itemize")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["claude", "/cub:itemize"]


class TestHandoffOutcome:
    """Tests for HandoffOutcome dataclass."""

    def test_outcome_with_all_fields(self) -> None:
        """Test creating outcome with all fields."""
        outcome = HandoffOutcome(
            result=HandoffResult.SUCCESS,
            message="Test message",
            exit_code=0,
        )
        assert outcome.result == HandoffResult.SUCCESS
        assert outcome.message == "Test message"
        assert outcome.exit_code == 0

    def test_outcome_with_optional_exit_code(self) -> None:
        """Test creating outcome without exit code."""
        outcome = HandoffOutcome(
            result=HandoffResult.CLAUDE_NOT_FOUND,
            message="CLI not found",
        )
        assert outcome.exit_code is None


class TestHandoffResult:
    """Tests for HandoffResult enum."""

    def test_all_values_exist(self) -> None:
        """Test all expected enum values exist."""
        assert HandoffResult.SUCCESS.value == "success"
        assert HandoffResult.CLAUDE_NOT_FOUND.value == "claude_not_found"
        assert HandoffResult.EXECUTION_FAILED.value == "execution_failed"
        assert HandoffResult.NOT_IN_CLAUDE_CODE.value == "not_in_claude_code"
