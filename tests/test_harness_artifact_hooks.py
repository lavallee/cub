"""
Tests for harness artifact capture hooks.

Tests the hook handlers in src/cub/core/harness/hooks.py that process
Claude Code hook events to auto-capture artifacts during direct sessions.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cub.core.harness.hooks import (
    HookEventPayload,
    HookEventResult,
    handle_hook_event,
    handle_post_tool_use,
    handle_session_end,
    handle_session_start,
    handle_stop,
)


class TestHookEventPayload:
    """Test HookEventPayload parsing and validation."""

    def test_parse_minimal_payload(self):
        """Test parsing minimal valid payload."""
        data = {
            "hook_event_name": "PostToolUse",
            "session_id": "test-123",
        }
        payload = HookEventPayload(data)

        assert payload.event_name == "PostToolUse"
        assert payload.session_id == "test-123"
        assert payload.is_valid()

    def test_parse_full_payload(self):
        """Test parsing complete payload with all fields."""
        data = {
            "hook_event_name": "PostToolUse",
            "session_id": "test-123",
            "transcript_path": "/path/to/transcript.jsonl",
            "cwd": "/path/to/project",
            "tool_name": "Write",
            "tool_input": {"file_path": "plans/plan.md"},
            "tool_response": "File written",
            "tool_use_id": "toolu_123",
        }
        payload = HookEventPayload(data)

        assert payload.event_name == "PostToolUse"
        assert payload.session_id == "test-123"
        assert payload.transcript_path == "/path/to/transcript.jsonl"
        assert payload.cwd == "/path/to/project"
        assert payload.tool_name == "Write"
        assert payload.tool_input == {"file_path": "plans/plan.md"}
        assert payload.tool_response == "File written"
        assert payload.tool_use_id == "toolu_123"

    def test_invalid_payload_missing_fields(self):
        """Test that payload without required fields is invalid."""
        data = {"hook_event_name": "PostToolUse"}  # Missing session_id
        payload = HookEventPayload(data)

        assert not payload.is_valid()

    def test_parse_malformed_json(self):
        """Test that from_stdin handles malformed JSON gracefully."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "not json"
            payload = HookEventPayload.from_stdin()

            assert payload is None


class TestHookEventResult:
    """Test HookEventResult creation and serialization."""

    def test_default_result(self):
        """Test default result allows execution."""
        result = HookEventResult()

        assert result.continue_execution is True
        assert result.exit_code() == 0

    def test_blocking_result(self):
        """Test blocking result stops execution."""
        result = HookEventResult(
            continue_execution=False,
            stop_reason="Test block",
        )

        assert result.continue_execution is False
        assert result.exit_code() == 2
        assert result.stop_reason == "Test block"

    def test_to_json_minimal(self):
        """Test JSON serialization with minimal fields."""
        result = HookEventResult()
        data = result.to_json()

        assert data == {"continue": True}

    def test_to_json_full(self):
        """Test JSON serialization with all fields."""
        result = HookEventResult(
            continue_execution=False,
            stop_reason="Test reason",
            suppress_output=True,
            system_message="System message",
            hook_specific={"hookEventName": "PostToolUse"},
        )
        data = result.to_json()

        assert data == {
            "continue": False,
            "stopReason": "Test reason",
            "suppressOutput": True,
            "systemMessage": "System message",
            "hookSpecificOutput": {"hookEventName": "PostToolUse"},
        }


class TestHandlePostToolUse:
    """Test PostToolUse hook handler."""

    @pytest.mark.asyncio
    async def test_ignores_non_write_tools(self):
        """Test that non-write tools are ignored."""
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "test-123",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True
        assert result.hook_specific["hookEventName"] == "PostToolUse"

    @pytest.mark.asyncio
    async def test_captures_plan_write(self, tmp_path):
        """Test that writes to plans/ directory are captured."""
        cwd = str(tmp_path)
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "test-123",
                "tool_name": "Write",
                "tool_input": {"file_path": "plans/plan.md"},
                "cwd": cwd,
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        # Check forensic log was created
        forensics_file = tmp_path / ".cub" / "ledger" / "forensics" / "test-123.jsonl"
        assert forensics_file.exists()

        # Verify log content
        with forensics_file.open() as f:
            log_entry = json.loads(f.readline())
            assert log_entry["event"] == "plan_write"
            assert log_entry["file_path"] == "plans/plan.md"

    @pytest.mark.asyncio
    async def test_ignores_non_plan_writes(self, tmp_path):
        """Test that writes outside plans/ are not captured."""
        cwd = str(tmp_path)
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "test-123",
                "tool_name": "Write",
                "tool_input": {"file_path": "src/main.py"},
                "cwd": cwd,
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        # Forensic log should not exist
        forensics_file = tmp_path / ".cub" / "ledger" / "forensics" / "test-123.jsonl"
        assert not forensics_file.exists()

    @pytest.mark.asyncio
    async def test_handles_edit_tool(self, tmp_path):
        """Test that Edit tool writes are captured."""
        cwd = str(tmp_path)
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "test-123",
                "tool_name": "Edit",
                "tool_input": {"file_path": "plans/implementation.md"},
                "cwd": cwd,
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        forensics_file = tmp_path / ".cub" / "ledger" / "forensics" / "test-123.jsonl"
        assert forensics_file.exists()

    @pytest.mark.asyncio
    async def test_handles_notebook_edit_tool(self, tmp_path):
        """Test that NotebookEdit tool writes are captured."""
        cwd = str(tmp_path)
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "test-123",
                "tool_name": "NotebookEdit",
                "tool_input": {"notebook_path": "plans/analysis.ipynb"},
                "cwd": cwd,
            }
        )

        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True

        forensics_file = tmp_path / ".cub" / "ledger" / "forensics" / "test-123.jsonl"
        assert forensics_file.exists()

    @pytest.mark.asyncio
    async def test_defensive_against_malformed_input(self):
        """Test that malformed tool input doesn't crash."""
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "test-123",
                "tool_name": "Write",
                "tool_input": "not a dict",  # Malformed
            }
        )

        # Should not raise exception
        result = await handle_post_tool_use(payload)

        assert result.continue_execution is True


class TestHandleStop:
    """Test Stop hook handler."""

    @pytest.mark.asyncio
    async def test_finalizes_session(self, tmp_path):
        """Test that session is finalized on stop."""
        cwd = str(tmp_path)
        payload = HookEventPayload(
            {
                "hook_event_name": "Stop",
                "session_id": "test-123",
                "transcript_path": "/path/to/transcript.jsonl",
                "cwd": cwd,
            }
        )

        result = await handle_stop(payload)

        assert result.continue_execution is True

        # Check forensic log
        forensics_file = tmp_path / ".cub" / "ledger" / "forensics" / "test-123.jsonl"
        assert forensics_file.exists()

        with forensics_file.open() as f:
            log_entry = json.loads(f.readline())
            assert log_entry["event"] == "session_finalize"
            assert log_entry["transcript_path"] == "/path/to/transcript.jsonl"

    @pytest.mark.asyncio
    async def test_prevents_infinite_loop(self, tmp_path):
        """Test that stop hook doesn't recurse if already active."""
        cwd = str(tmp_path)
        payload = HookEventPayload(
            {
                "hook_event_name": "Stop",
                "session_id": "test-123",
                "stop_hook_active": True,  # Already in stop hook
                "cwd": cwd,
            }
        )

        result = await handle_stop(payload)

        assert result.continue_execution is True

        # Should not write to forensics
        forensics_file = tmp_path / ".cub" / "ledger" / "forensics" / "test-123.jsonl"
        assert not forensics_file.exists()


class TestHandleSessionStart:
    """Test SessionStart hook handler."""

    @pytest.mark.asyncio
    async def test_initializes_session(self, tmp_path):
        """Test that session is initialized on start."""
        cwd = str(tmp_path)
        payload = HookEventPayload(
            {
                "hook_event_name": "SessionStart",
                "session_id": "test-123",
                "cwd": cwd,
            }
        )

        result = await handle_session_start(payload)

        assert result.continue_execution is True

        # Check forensic log
        forensics_file = tmp_path / ".cub" / "ledger" / "forensics" / "test-123.jsonl"
        assert forensics_file.exists()

        with forensics_file.open() as f:
            log_entry = json.loads(f.readline())
            assert log_entry["event"] == "session_start"


class TestHandleSessionEnd:
    """Test SessionEnd hook handler."""

    @pytest.mark.asyncio
    async def test_finalizes_on_end(self, tmp_path):
        """Test that session is finalized on end."""
        cwd = str(tmp_path)
        payload = HookEventPayload(
            {
                "hook_event_name": "SessionEnd",
                "session_id": "test-123",
                "transcript_path": "/path/to/transcript.jsonl",
                "cwd": cwd,
            }
        )

        result = await handle_session_end(payload)

        assert result.continue_execution is True

        forensics_file = tmp_path / ".cub" / "ledger" / "forensics" / "test-123.jsonl"
        assert forensics_file.exists()


class TestHandleHookEvent:
    """Test hook event dispatcher."""

    @pytest.mark.asyncio
    async def test_dispatches_to_correct_handler(self):
        """Test that events are dispatched to correct handlers."""
        payload = HookEventPayload(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "test-123",
            }
        )

        result = await handle_hook_event("PostToolUse", payload)

        assert result.hook_specific["hookEventName"] == "PostToolUse"

    @pytest.mark.asyncio
    async def test_handles_unknown_event(self):
        """Test that unknown events don't crash."""
        payload = HookEventPayload(
            {
                "hook_event_name": "UnknownEvent",
                "session_id": "test-123",
            }
        )

        result = await handle_hook_event("UnknownEvent", payload)

        # Should allow execution to continue
        assert result.continue_execution is True
        assert result.hook_specific["hookEventName"] == "UnknownEvent"
