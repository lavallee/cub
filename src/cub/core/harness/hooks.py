"""
Hook handlers for artifact capture during direct harness sessions.

This module provides handlers that process Claude Code hook events to automatically
capture artifacts (plans, outputs, ledger entries) when users run harnesses directly
(Claude Code, Codex, OpenCode) instead of via `cub run`.

The handlers are designed to be called from hook scripts installed in .cub/hooks/
or .claude/hooks/. They parse hook event JSON payloads defensively and integrate
with the ledger system to maintain roughly equivalent records to `cub run`.

Usage:
    From hook script:
        #!/bin/bash
        python -m cub.core.harness.hooks "$HOOK_EVENT_NAME"

    Or programmatically:
        from cub.core.harness.hooks import handle_hook_event
        result = await handle_hook_event("PostToolUse", payload)
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class HookEventPayload:
    """
    Parsed hook event payload from Claude Code.

    Provides safe access to hook event fields with defensive parsing.
    Malformed payloads result in None values rather than exceptions.
    """

    def __init__(self, raw_data: dict[str, Any]) -> None:
        """Initialize from raw JSON payload.

        Args:
            raw_data: Dictionary parsed from hook stdin JSON
        """
        self.raw = raw_data
        self.event_name = raw_data.get("hook_event_name", "")
        self.session_id = raw_data.get("session_id")
        self.transcript_path = raw_data.get("transcript_path")
        self.cwd = raw_data.get("cwd")
        self.tool_name = raw_data.get("tool_name")
        self.tool_input = raw_data.get("tool_input", {})
        self.tool_response = raw_data.get("tool_response")
        self.tool_use_id = raw_data.get("tool_use_id")

    @classmethod
    def from_stdin(cls) -> "HookEventPayload | None":
        """Parse hook payload from stdin.

        Returns:
            Parsed payload or None if stdin is invalid JSON
        """
        try:
            data = json.load(sys.stdin)
            return cls(data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse hook payload from stdin: {e}")
            return None

    def is_valid(self) -> bool:
        """Check if payload has minimum required fields."""
        return bool(self.event_name and self.session_id)


class HookEventResult:
    """
    Result returned from hook handler.

    Encapsulates the response that should be sent back to Claude Code
    via stdout and exit code.
    """

    def __init__(
        self,
        continue_execution: bool = True,
        stop_reason: str | None = None,
        suppress_output: bool = False,
        system_message: str | None = None,
        hook_specific: dict[str, Any] | None = None,
    ) -> None:
        """Initialize hook result.

        Args:
            continue_execution: Whether Claude should continue (default: True)
            stop_reason: Message when continue=False (shown to user)
            suppress_output: Hide stdout from transcript
            system_message: Message shown to user
            hook_specific: Hook-specific output fields
        """
        self.continue_execution = continue_execution
        self.stop_reason = stop_reason
        self.suppress_output = suppress_output
        self.system_message = system_message
        self.hook_specific = hook_specific or {}

    def to_json(self) -> dict[str, Any]:
        """Convert to JSON for stdout output.

        Returns:
            Dictionary suitable for JSON serialization
        """
        result: dict[str, Any] = {
            "continue": self.continue_execution,
        }
        if self.stop_reason:
            result["stopReason"] = self.stop_reason
        if self.suppress_output:
            result["suppressOutput"] = True
        if self.system_message:
            result["systemMessage"] = self.system_message
        if self.hook_specific:
            result["hookSpecificOutput"] = self.hook_specific

        return result

    def exit_code(self) -> int:
        """Get appropriate exit code.

        Returns:
            0 for success, 2 for blocking error
        """
        return 0 if self.continue_execution else 2


async def handle_post_tool_use(payload: HookEventPayload) -> HookEventResult:
    """
    Handle PostToolUse events to capture file writes and plan updates.

    Detects writes to plans/ directory and logs them to the ledger for
    forensic tracking. This enables reconstruction of work done in direct
    harness sessions.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue
    """
    # Detect writes to plans/ directory
    if payload.tool_name in ("Write", "Edit", "NotebookEdit"):
        try:
            file_path = _extract_file_path(payload.tool_input)
            if file_path and _is_plan_file(file_path):
                await _log_plan_write(payload.session_id, file_path, payload.cwd)
        except Exception as e:
            # Defensive: don't crash on unexpected tool input structures
            logger.debug(f"Failed to process tool write in hook: {e}")

    # Always allow execution to continue
    return HookEventResult(
        continue_execution=True,
        hook_specific={
            "hookEventName": "PostToolUse",
        },
    )


async def handle_stop(payload: HookEventPayload) -> HookEventResult:
    """
    Handle Stop events to capture session end and finalize ledger entries.

    When Claude finishes responding, we finalize any open ledger entries
    for the session and capture final artifacts.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue
    """
    # Prevent infinite loops if already in stop hook
    if payload.raw.get("stop_hook_active"):
        return HookEventResult(
            continue_execution=True,
            hook_specific={"hookEventName": "Stop"},
        )

    try:
        await _finalize_session(payload.session_id, payload.transcript_path, payload.cwd)
    except Exception as e:
        # Defensive: don't crash the hook, just log the error
        logger.warning(f"Failed to finalize session in stop hook: {e}")

    return HookEventResult(
        continue_execution=True,
        hook_specific={"hookEventName": "Stop"},
    )


async def handle_session_start(payload: HookEventPayload) -> HookEventResult:
    """
    Handle SessionStart events to initialize session tracking.

    Creates initial ledger entry for the session if it doesn't exist.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue
    """
    try:
        await _initialize_session(payload.session_id, payload.cwd)
    except Exception as e:
        logger.warning(f"Failed to initialize session in start hook: {e}")

    return HookEventResult(
        continue_execution=True,
        hook_specific={"hookEventName": "SessionStart"},
    )


async def handle_session_end(payload: HookEventPayload) -> HookEventResult:
    """
    Handle SessionEnd events to finalize session.

    Ensures all artifacts are captured and ledger entries are closed.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue
    """
    try:
        await _finalize_session(payload.session_id, payload.transcript_path, payload.cwd)
    except Exception as e:
        logger.warning(f"Failed to finalize session in end hook: {e}")

    return HookEventResult(
        continue_execution=True,
        hook_specific={"hookEventName": "SessionEnd"},
    )


async def handle_hook_event(event_type: str, payload: HookEventPayload) -> HookEventResult:
    """
    Dispatcher for hook events.

    Routes hook events to appropriate handlers based on event type.

    Args:
        event_type: Hook event name (e.g., "PostToolUse", "Stop")
        payload: Parsed hook event payload

    Returns:
        Hook result with appropriate response

    Raises:
        ValueError: If event_type is unknown
    """
    handlers = {
        "PostToolUse": handle_post_tool_use,
        "Stop": handle_stop,
        "SessionStart": handle_session_start,
        "SessionEnd": handle_session_end,
    }

    handler = handlers.get(event_type)
    if not handler:
        logger.warning(f"No handler for hook event: {event_type}")
        # Return safe default: allow execution to continue
        return HookEventResult(
            continue_execution=True,
            hook_specific={"hookEventName": event_type},
        )

    return await handler(payload)


def _extract_file_path(tool_input: dict[str, Any]) -> str | None:
    """
    Extract file path from tool input.

    Args:
        tool_input: Tool input parameters

    Returns:
        File path string or None if not found
    """
    # Write and Edit tools use file_path parameter
    # NotebookEdit uses notebook_path
    return tool_input.get("file_path") or tool_input.get("notebook_path")


def _is_plan_file(file_path: str) -> bool:
    """
    Check if file path is in plans/ directory.

    Args:
        file_path: File path to check

    Returns:
        True if file is in plans/ directory
    """
    path = Path(file_path)
    return "plans" in path.parts


async def _log_plan_write(session_id: str | None, file_path: str, cwd: str | None) -> None:
    """
    Log plan file write to ledger.

    Creates a forensic record of the plan file write for later analysis.

    Args:
        session_id: Claude Code session ID
        file_path: Path to plan file that was written
        cwd: Current working directory
    """
    # TODO: Integrate with ledger writer to create forensic entry
    # For now, just log the event
    logger.info(
        f"Plan file write detected: {file_path} (session: {session_id}, cwd: {cwd})",
        extra={
            "session_id": session_id,
            "file_path": file_path,
            "cwd": cwd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Write to .cub/ledger/forensics/{session_id}.jsonl for later processing
    if cwd:
        forensics_dir = Path(cwd) / ".cub" / "ledger" / "forensics"
        forensics_dir.mkdir(parents=True, exist_ok=True)

        forensics_file = forensics_dir / f"{session_id}.jsonl"
        with forensics_file.open("a", encoding="utf-8") as f:
            json.dump(
                {
                    "event": "plan_write",
                    "file_path": file_path,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                f,
            )
            f.write("\n")


async def _finalize_session(
    session_id: str | None, transcript_path: str | None, cwd: str | None
) -> None:
    """
    Finalize session and capture artifacts.

    Closes any open ledger entries and captures final session state.

    Args:
        session_id: Claude Code session ID
        transcript_path: Path to session transcript
        cwd: Current working directory
    """
    # TODO: Integrate with ledger to finalize entries
    logger.info(
        f"Finalizing session: {session_id} (transcript: {transcript_path})",
        extra={
            "session_id": session_id,
            "transcript_path": transcript_path,
            "cwd": cwd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Write finalization marker to forensics log
    if cwd and session_id:
        forensics_dir = Path(cwd) / ".cub" / "ledger" / "forensics"
        forensics_dir.mkdir(parents=True, exist_ok=True)

        forensics_file = forensics_dir / f"{session_id}.jsonl"
        with forensics_file.open("a", encoding="utf-8") as f:
            json.dump(
                {
                    "event": "session_finalize",
                    "transcript_path": transcript_path,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                f,
            )
            f.write("\n")


async def _initialize_session(session_id: str | None, cwd: str | None) -> None:
    """
    Initialize session tracking.

    Creates initial forensic entry for the session.

    Args:
        session_id: Claude Code session ID
        cwd: Current working directory
    """
    logger.info(
        f"Initializing session: {session_id}",
        extra={
            "session_id": session_id,
            "cwd": cwd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Write initialization marker to forensics log
    if cwd and session_id:
        forensics_dir = Path(cwd) / ".cub" / "ledger" / "forensics"
        forensics_dir.mkdir(parents=True, exist_ok=True)

        forensics_file = forensics_dir / f"{session_id}.jsonl"
        with forensics_file.open("a", encoding="utf-8") as f:
            json.dump(
                {
                    "event": "session_start",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                f,
            )
            f.write("\n")


async def main() -> int:
    """
    Main entry point for hook script execution.

    Reads hook payload from stdin, dispatches to handler, and outputs result.

    Returns:
        Exit code (0 for success, 2 for blocking)
    """
    # Set up basic logging to stderr (won't interfere with stdout JSON)
    logging.basicConfig(
        level=logging.INFO,
        format="[cub-hook] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    # Get event type from command line arg or default to payload
    event_type = sys.argv[1] if len(sys.argv) > 1 else None

    # Parse payload from stdin
    payload = HookEventPayload.from_stdin()
    if not payload or not payload.is_valid():
        logger.error("Invalid hook payload from stdin")
        # Don't block on malformed input
        return 0

    # Use event type from payload if not specified on command line
    if not event_type:
        event_type = payload.event_name

    try:
        # Handle the hook event
        result = await handle_hook_event(event_type, payload)

        # Output JSON response to stdout
        print(json.dumps(result.to_json(), indent=2))

        return result.exit_code()

    except Exception as e:
        logger.exception(f"Unexpected error in hook handler: {e}")
        # Don't block on unexpected errors
        return 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
