"""Utility modules for cub."""

from .handoff import (
    HandoffOutcome,
    HandoffResult,
    attempt_handoff,
    format_shell_command,
    format_slash_command,
    try_handoff_or_message,
)
from .hooks import HookContext, run_hooks
from .logging import CubLogger, EventType, LogEntry
from .project import find_project_root, get_project_root

__all__ = [
    "attempt_handoff",
    "find_project_root",
    "format_shell_command",
    "format_slash_command",
    "get_project_root",
    "CubLogger",
    "EventType",
    "HandoffOutcome",
    "HandoffResult",
    "HookContext",
    "LogEntry",
    "run_hooks",
    "try_handoff_or_message",
]
