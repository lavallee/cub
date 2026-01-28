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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from cub.core.ledger.session_integration import SessionLedgerIntegration
from cub.core.ledger.writer import LedgerWriter

logger = logging.getLogger(__name__)


def _get_ledger_integration(cwd: str | None) -> SessionLedgerIntegration | None:
    """
    Create SessionLedgerIntegration from project directory.

    Args:
        cwd: Current working directory from hook payload

    Returns:
        SessionLedgerIntegration instance or None if cwd is invalid
    """
    if not cwd:
        return None

    project_dir = Path(cwd)
    ledger_dir = project_dir / ".cub" / "ledger"

    # Ensure ledger directory exists
    ledger_dir.mkdir(parents=True, exist_ok=True)

    writer = LedgerWriter(ledger_dir)
    return SessionLedgerIntegration(writer)


# ===== Forensics Event Models =====


class ForensicEvent(BaseModel):
    """Base class for all forensic events."""

    event_type: str = Field(description="Type of forensic event")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of event",
    )
    session_id: str | None = Field(default=None, description="Claude Code session ID")


class SessionStartEvent(ForensicEvent):
    """Forensic event for session start."""

    event_type: Literal["session_start"] = "session_start"
    cwd: str | None = Field(default=None, description="Current working directory")


class FileWriteEvent(ForensicEvent):
    """Forensic event for file writes."""

    event_type: Literal["file_write"] = "file_write"
    file_path: str = Field(description="Path to file that was written")
    tool_name: str = Field(description="Tool used (Write, Edit, NotebookEdit)")
    file_category: str | None = Field(
        default=None, description="Category of file (plan, spec, capture, source)"
    )


class TaskClaimEvent(ForensicEvent):
    """Forensic event for task claiming."""

    event_type: Literal["task_claim"] = "task_claim"
    task_id: str = Field(description="ID of claimed task")
    command: str | None = Field(default=None, description="Command that claimed the task")


class TaskCloseEvent(ForensicEvent):
    """Forensic event for task closure."""

    event_type: Literal["task_close"] = "task_close"
    task_id: str = Field(description="ID of closed task")
    command: str | None = Field(default=None, description="Command that closed the task")
    reason: str | None = Field(default=None, description="Closure reason if provided")


class GitCommitEvent(ForensicEvent):
    """Forensic event for git commits."""

    event_type: Literal["git_commit"] = "git_commit"
    command: str = Field(description="Git commit command that was run")
    message_preview: str | None = Field(default=None, description="First line of commit message")


class SessionEndEvent(ForensicEvent):
    """Forensic event for session end."""

    event_type: Literal["session_end"] = "session_end"
    transcript_path: str | None = Field(default=None, description="Path to session transcript")


class SessionCheckpointEvent(ForensicEvent):
    """Forensic event for session checkpoints (compaction)."""

    event_type: Literal["session_checkpoint"] = "session_checkpoint"
    reason: str | None = Field(default=None, description="Reason for checkpoint")


class TaskMentionEvent(ForensicEvent):
    """Forensic event for task mentions in user prompts."""

    event_type: Literal["task_mention"] = "task_mention"
    task_id: str = Field(description="ID of mentioned task")
    prompt_preview: str | None = Field(
        default=None, description="Preview of prompt containing mention"
    )


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

    Detects writes to tracked directories (plans/, specs/, captures/, src/)
    and logs them as forensic events. Also detects task operations and git commits
    in Bash tool usage.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue
    """
    try:
        # Detect file writes (Write, Edit, NotebookEdit)
        if payload.tool_name in ("Write", "Edit", "NotebookEdit"):
            file_path = _extract_file_path(payload.tool_input)
            if file_path:
                category = _categorize_file(file_path)
                if category:
                    event = FileWriteEvent(
                        session_id=payload.session_id,
                        file_path=file_path,
                        tool_name=payload.tool_name,
                        file_category=category,
                    )
                    await _write_forensic_event(event, payload.cwd)
                    logger.debug(
                        f"File write: {file_path} ({category})",
                        extra={"file_path": file_path, "category": category},
                    )

        # Detect task operations and git commits (Bash tool)
        elif payload.tool_name == "Bash":
            command = payload.tool_input.get("command", "") if payload.tool_input else ""
            if command:
                # Detect task claim/update
                # Task ID pattern: cub-w3f.2 (alphanumeric with optional dots)
                # New format: cub task claim <task-id>
                # Legacy format: bd update <task-id> --status in_progress
                if match := re.search(r"cub\s+task\s+claim\s+([\w.-]+)", command):
                    task_id = match.group(1)
                    claim_event = TaskClaimEvent(
                        session_id=payload.session_id, task_id=task_id, command=command
                    )
                    await _write_forensic_event(claim_event, payload.cwd)
                    logger.info(f"Task claimed: {task_id}", extra={"task_id": task_id})
                elif match := re.search(
                    r"bd\s+update\s+([\w.-]+)\s+--status\s+in_progress", command
                ):
                    # Legacy fallback for bd commands
                    task_id = match.group(1)
                    claim_event = TaskClaimEvent(
                        session_id=payload.session_id, task_id=task_id, command=command
                    )
                    await _write_forensic_event(claim_event, payload.cwd)
                    logger.info(f"Task claimed (legacy): {task_id}", extra={"task_id": task_id})

                # Detect task close
                # New format: cub task close <task-id> --reason "..."
                # Legacy format: bd close <task-id> -r "..."
                elif match := re.search(
                    r"cub\s+task\s+close\s+([\w.-]+)(?:\s+--reason\s+['\"]([^'\"]+)['\"])?", command
                ):
                    task_id = match.group(1)
                    reason = match.group(2)
                    close_event = TaskCloseEvent(
                        session_id=payload.session_id,
                        task_id=task_id,
                        command=command,
                        reason=reason,
                    )
                    await _write_forensic_event(close_event, payload.cwd)
                    logger.info(f"Task closed: {task_id}", extra={"task_id": task_id})
                elif match := re.search(
                    r"bd\s+close\s+([\w.-]+)(?:\s+-r\s+['\"]([^'\"]+)['\"])?", command
                ):
                    # Legacy fallback for bd commands
                    task_id = match.group(1)
                    reason = match.group(2)
                    close_event = TaskCloseEvent(
                        session_id=payload.session_id,
                        task_id=task_id,
                        command=command,
                        reason=reason,
                    )
                    await _write_forensic_event(close_event, payload.cwd)
                    logger.info(f"Task closed (legacy): {task_id}", extra={"task_id": task_id})

                # Detect git commit
                elif "git commit" in command and not command.strip().startswith("#"):
                    message_preview = _extract_commit_message(command)
                    commit_event = GitCommitEvent(
                        session_id=payload.session_id,
                        command=command,
                        message_preview=message_preview,
                    )
                    await _write_forensic_event(commit_event, payload.cwd)
                    logger.info(f"Git commit: {message_preview or '(no message)'}")

    except Exception as e:
        # Defensive: don't crash on unexpected tool input structures
        logger.debug(f"Failed to process tool use in hook: {e}")

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
    for the session and capture final artifacts. Writes a session_end event
    with transcript path, then synthesizes ledger entry from forensics.

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
        event = SessionEndEvent(
            session_id=payload.session_id, transcript_path=payload.transcript_path
        )
        await _write_forensic_event(event, payload.cwd)

        # Synthesize ledger entry from forensics
        integration = _get_ledger_integration(payload.cwd)
        if integration and payload.session_id and payload.cwd:
            forensics_path = (
                Path(payload.cwd) / ".cub" / "ledger" / "forensics" / f"{payload.session_id}.jsonl"
            )

            try:
                # Let SessionLedgerIntegration reconstruct state and create entry
                # Note: Task object not available here, ledger entry uses task_id only
                entry = integration.on_session_end(
                    payload.session_id,
                    forensics_path,
                    task=None,  # TODO: Could load task from backend if task_id is in forensics
                )

                if entry:
                    logger.info(
                        f"Ledger entry created for session {payload.session_id}: {entry.id}",
                        extra={"session_id": payload.session_id, "task_id": entry.id},
                    )

                    # Enrich with transcript data (best-effort)
                    if payload.transcript_path:
                        try:
                            enriched_entry = integration.enrich_from_transcript(
                                entry.id,
                                Path(payload.transcript_path),
                            )
                            if enriched_entry:
                                logger.debug(
                                    f"Enriched ledger entry {entry.id} with transcript data: "
                                    f"{enriched_entry.tokens.total_tokens} tokens, "
                                    f"${enriched_entry.cost_usd:.4f} cost",
                                    extra={
                                        "session_id": payload.session_id,
                                        "task_id": entry.id,
                                        "tokens": enriched_entry.tokens.total_tokens,
                                        "cost_usd": enriched_entry.cost_usd,
                                    },
                                )
                        except Exception as e:
                            logger.debug(
                                f"Failed to enrich ledger entry from transcript: {e}",
                                extra={"session_id": payload.session_id, "task_id": entry.id},
                            )
                else:
                    logger.debug(
                        f"No ledger entry created for session {payload.session_id} "
                        "(no task associated)",
                        extra={"session_id": payload.session_id},
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to synthesize ledger entry from forensics: {e}",
                    extra={"session_id": payload.session_id},
                )

        logger.info(
            f"Session stopped: {payload.session_id}",
            extra={"session_id": payload.session_id, "transcript_path": payload.transcript_path},
        )
    except Exception as e:
        # Defensive: don't crash the hook, just log the error
        logger.warning(f"Failed to finalize session in stop hook: {e}")

    return HookEventResult(
        continue_execution=True,
        hook_specific={"hookEventName": "Stop"},
    )


def _build_project_context(project_dir: Path) -> str | None:
    """
    Build project context string with tasks and metadata.

    Loads available tasks from the project's task backend and formats
    a concise context summary for injection into Claude Code session.

    Args:
        project_dir: Path to project directory

    Returns:
        Context string (under 500 tokens) or None if unavailable
    """
    try:
        from cub.core.tasks.backend import get_backend
        from cub.core.tasks.models import TaskStatus

        # Load task backend from project config
        backend = get_backend(project_dir=project_dir)

        # Query ready tasks (top 10 by priority)
        ready_tasks = backend.get_ready_tasks()[:10]

        # Query in-progress tasks for resumed session awareness
        in_progress_tasks = backend.list_tasks(status=TaskStatus.IN_PROGRESS)

        # Get project name from directory
        project_name = project_dir.name

        # Build concise context string
        context_parts = [f"**Project:** {project_name}"]

        # Add ready tasks section
        if ready_tasks:
            context_parts.append("\n**Ready Tasks:**")
            for task in ready_tasks:
                priority_str = f"[{task.priority.value}]" if task.priority else ""
                context_parts.append(f"- {task.id}: {task.title} {priority_str}")
        else:
            context_parts.append("\n**Ready Tasks:** None")

        # Add in-progress tasks section
        if in_progress_tasks:
            context_parts.append("\n**In Progress:**")
            for task in in_progress_tasks:
                context_parts.append(f"- {task.id}: {task.title}")

        # Join all parts
        context = "\n".join(context_parts)

        # Ensure we're under 500 tokens (rough estimate: 1 token ≈ 4 chars)
        max_chars = 500 * 4
        if len(context) > max_chars:
            context = context[:max_chars] + "..."

        logger.debug(
            f"Built project context: {len(ready_tasks)} ready, {len(in_progress_tasks)} in progress"
        )

        return context

    except Exception as e:
        # Don't fail session start if context building fails
        logger.debug(f"Failed to build project context: {e}")
        return None


async def handle_session_start(payload: HookEventPayload) -> HookEventResult:
    """
    Handle SessionStart events to initialize session tracking.

    Creates initial ledger entry for the session if it doesn't exist.
    Writes a session_start forensic event with cwd and timestamp.
    Injects available tasks and project context as additionalContext.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue with injected context
    """
    additional_context = None

    try:
        # Create and write session_start event
        event = SessionStartEvent(session_id=payload.session_id, cwd=payload.cwd)
        await _write_forensic_event(event, payload.cwd)

        # Initialize SessionLedgerIntegration (stateless, just ensures setup)
        integration = _get_ledger_integration(payload.cwd)
        if integration:
            logger.debug(
                f"SessionLedgerIntegration initialized for session: {payload.session_id}",
                extra={"session_id": payload.session_id},
            )

        # Load task backend and inject project context
        if payload.cwd:
            project_dir = Path(payload.cwd)
            additional_context = _build_project_context(project_dir)

        logger.info(
            f"Session started: {payload.session_id}",
            extra={"session_id": payload.session_id, "cwd": payload.cwd},
        )
    except Exception as e:
        logger.warning(f"Failed to initialize session in start hook: {e}")

    # Return result with additional context if available
    hook_specific = {"hookEventName": "SessionStart"}
    if additional_context:
        hook_specific["additionalContext"] = additional_context

    return HookEventResult(
        continue_execution=True,
        hook_specific=hook_specific,
    )


async def handle_session_end(payload: HookEventPayload) -> HookEventResult:
    """
    Handle SessionEnd events to finalize session.

    Ensures all artifacts are captured and ledger entries are closed.
    Writes a session_end event with transcript path, then synthesizes
    ledger entry from forensics.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue
    """
    try:
        event = SessionEndEvent(
            session_id=payload.session_id, transcript_path=payload.transcript_path
        )
        await _write_forensic_event(event, payload.cwd)

        # Synthesize ledger entry from forensics
        integration = _get_ledger_integration(payload.cwd)
        if integration and payload.session_id and payload.cwd:
            forensics_path = (
                Path(payload.cwd) / ".cub" / "ledger" / "forensics" / f"{payload.session_id}.jsonl"
            )

            try:
                # Let SessionLedgerIntegration reconstruct state and create entry
                entry = integration.on_session_end(
                    payload.session_id,
                    forensics_path,
                    task=None,  # TODO: Could load task from backend if task_id is in forensics
                )

                if entry:
                    logger.info(
                        f"Ledger entry created for session {payload.session_id}: {entry.id}",
                        extra={"session_id": payload.session_id, "task_id": entry.id},
                    )
                else:
                    logger.debug(
                        f"No ledger entry created for session {payload.session_id} "
                        "(no task associated)",
                        extra={"session_id": payload.session_id},
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to synthesize ledger entry from forensics: {e}",
                    extra={"session_id": payload.session_id},
                )

        logger.info(
            f"Session ended: {payload.session_id}",
            extra={"session_id": payload.session_id, "transcript_path": payload.transcript_path},
        )
    except Exception as e:
        logger.warning(f"Failed to finalize session in end hook: {e}")

    return HookEventResult(
        continue_execution=True,
        hook_specific={"hookEventName": "SessionEnd"},
    )


async def handle_pre_compact(payload: HookEventPayload) -> HookEventResult:
    """
    Handle PreCompact events to checkpoint session state.

    Compaction means Claude Code is about to compact the transcript and start a new
    session. We write a session_checkpoint event and start a new forensics file.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue
    """
    try:
        event = SessionCheckpointEvent(
            session_id=payload.session_id, reason="transcript_compaction"
        )
        await _write_forensic_event(event, payload.cwd)

        logger.info(
            f"Session checkpoint: {payload.session_id} (compaction)",
            extra={"session_id": payload.session_id},
        )
    except Exception as e:
        logger.warning(f"Failed to checkpoint session in pre_compact hook: {e}")

    return HookEventResult(
        continue_execution=True,
        hook_specific={"hookEventName": "PreCompact"},
    )


def _format_task_context(task: Any) -> str:
    """
    Format task details for injection as additional context.

    Args:
        task: Task object from backend

    Returns:
        Formatted task context string (markdown)
    """
    from cub.core.tasks.models import Task

    if not isinstance(task, Task):
        return ""

    # Build context with task details
    context_parts = [f"## Task: {task.id}"]
    context_parts.append(f"**Title:** {task.title}")

    if task.status:
        context_parts.append(f"**Status:** {task.status.value}")

    if task.priority:
        context_parts.append(f"**Priority:** {task.priority.value}")

    if task.description:
        context_parts.append(f"**Description:**\n{task.description}")

    if task.acceptance_criteria:
        criteria_text = "\n".join(f"- {c}" for c in task.acceptance_criteria)
        context_parts.append(f"**Acceptance Criteria:**\n{criteria_text}")

    return "\n\n".join(context_parts)


async def handle_user_prompt_submit(payload: HookEventPayload) -> HookEventResult:
    """
    Handle UserPromptSubmit events to detect task mentions and inject task details.

    Detects task ID patterns (e.g., cub-w3f.2) in user prompts, queries the task
    backend for task details, and injects them as additionalContext for the AI.

    Args:
        payload: Parsed hook event payload

    Returns:
        Hook result allowing execution to continue, with task details in additionalContext
    """
    additional_context = None
    hook_specific = {"hookEventName": "UserPromptSubmit"}

    try:
        # Extract user prompt from payload
        user_prompt = payload.tool_input.get("prompt", "") if payload.tool_input else ""

        if not user_prompt or not payload.cwd:
            return HookEventResult(
                continue_execution=True,
                hook_specific=hook_specific,
            )

        # Load config to get task ID pattern
        try:
            from cub.core.config import load_config

            config = load_config(project_dir=Path(payload.cwd))
            task_pattern = config.task.id_pattern
            inject_context = config.task.inject_context
        except Exception:
            # Fall back to default pattern if config loading fails
            task_pattern = r"cub-[\w.-]+"
            inject_context = True

        # Skip context injection if disabled in config
        if not inject_context:
            return HookEventResult(
                continue_execution=True,
                hook_specific=hook_specific,
            )

        # Wrap pattern in word boundaries and capturing group if needed
        if not task_pattern.startswith("("):
            # Add word boundaries and capturing group
            task_pattern = r"\b(" + task_pattern + r")\b"

        # Detect task ID patterns in the prompt
        matches = re.finditer(task_pattern, user_prompt, re.IGNORECASE)

        # Collect task details for all matched task IDs
        task_details: list[str] = []

        for match in matches:
            task_id = match.group(1)
            prompt_preview = user_prompt[:100]  # First 100 chars

            # Write forensic event for this task mention
            event = TaskMentionEvent(
                session_id=payload.session_id, task_id=task_id, prompt_preview=prompt_preview
            )
            await _write_forensic_event(event, payload.cwd)

            logger.info(f"Task mentioned: {task_id}", extra={"task_id": task_id})

            # Query task backend for task details
            try:
                from cub.core.tasks.backend import get_backend
                from cub.core.tasks.models import TaskStatus

                backend = get_backend(project_dir=Path(payload.cwd))
                task = backend.get_task(task_id)

                if task:
                    # Skip if task is already in progress (avoid context duplication)
                    if task.status == TaskStatus.IN_PROGRESS:
                        logger.debug(
                            f"Task {task_id} already in progress, skipping context injection",
                            extra={"task_id": task_id},
                        )
                        continue

                    # Format task details for injection
                    task_context = _format_task_context(task)
                    task_details.append(task_context)
                    logger.debug(
                        f"Task context injected: {task_id}",
                        extra={"task_id": task_id},
                    )
                else:
                    logger.debug(
                        f"Task not found in backend: {task_id}",
                        extra={"task_id": task_id},
                    )
            except Exception as e:
                logger.debug(
                    f"Failed to fetch task details for {task_id}: {e}",
                    extra={"task_id": task_id},
                )
                continue

        # Build additional context if any tasks were found
        if task_details:
            additional_context = "\n\n".join(task_details)
            hook_specific["additionalContext"] = additional_context

    except Exception as e:
        logger.debug(f"Failed to handle user prompt submit event: {e}")

    return HookEventResult(
        continue_execution=True,
        hook_specific=hook_specific,
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
        "PreCompact": handle_pre_compact,
        "UserPromptSubmit": handle_user_prompt_submit,
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


def _categorize_file(file_path: str) -> str | None:
    """
    Categorize file based on path.

    Args:
        file_path: File path to categorize

    Returns:
        Category string ("plan", "spec", "capture", "source") or None if not tracked
    """
    path = Path(file_path)
    parts = path.parts

    if "plans" in parts:
        return "plan"
    elif "specs" in parts:
        return "spec"
    elif "captures" in parts:
        return "capture"
    elif any(p in parts for p in ("src", "lib", "app", "tests")):
        return "source"
    return None


def _extract_commit_message(command: str) -> str | None:
    """
    Extract commit message from git commit command.

    Args:
        command: Git commit command string

    Returns:
        First line of commit message or None
    """
    # Try to extract from -m flag
    if match := re.search(r'-m\s+["\']([^"\']+)["\']', command):
        message = match.group(1)
        # Return first line only
        return message.split("\n")[0]

    # Try to extract from heredoc
    if match := re.search(r"cat\s+<<['\"]?EOF['\"]?\n([^\n]+)", command):
        return match.group(1)

    return None


async def _write_forensic_event(event: ForensicEvent, cwd: str | None) -> None:
    """
    Write forensic event to JSONL log.

    Creates .cub/ledger/forensics/{session_id}.jsonl and appends structured event.

    Args:
        event: Forensic event to write
        cwd: Current working directory
    """
    if not cwd or not event.session_id:
        logger.debug("Skipping forensic event write: missing cwd or session_id")
        return

    forensics_dir = Path(cwd) / ".cub" / "ledger" / "forensics"
    forensics_dir.mkdir(parents=True, exist_ok=True)

    forensics_file = forensics_dir / f"{event.session_id}.jsonl"
    with forensics_file.open("a", encoding="utf-8") as f:
        # Write event as JSONL (one JSON object per line)
        json.dump(event.model_dump(exclude_none=True), f)
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


def cli_main() -> None:
    """
    Entry point for cub-hooks console script.

    This is the function registered in pyproject.toml as the cub-hooks command.
    It's a lightweight wrapper around main() that handles asyncio event loop setup.
    """
    import asyncio

    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    cli_main()
