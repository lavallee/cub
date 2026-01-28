"""
Prompt builder for cub run sessions.

Builds system prompts and task-specific prompts for harness sessions.
This module is independent of CLI concerns (no Rich, no sys.exit, no typer).

Key functions:
    generate_system_prompt: Builds the system prompt from project context files
    generate_task_prompt: Builds the full task prompt with context
    generate_direct_task_prompt: Builds a task prompt for direct mode
    generate_epic_context: Builds epic context for tasks in an epic
    generate_retry_context: Builds retry context for previously-failed tasks

Data models:
    PromptConfig: Configuration inputs for system prompt generation
    TaskPrompt: Structured output from task prompt generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cub.core.ledger.integration import LedgerIntegration
    from cub.core.tasks.backend import TaskBackend
    from cub.core.tasks.models import Task


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptConfig:
    """Configuration inputs for system prompt generation.

    Attributes:
        project_dir: Path to the project root directory.
        package_root: Path to the cub package root (used to locate bundled
            templates). Defaults to the ``src/`` tree relative to this file.
    """

    project_dir: Path
    package_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)

    @property
    def prompt_search_paths(self) -> list[Path]:
        """Ordered list of candidate prompt file locations.

        Lookup order:
        1. ``.cub/runloop.md`` – project-specific runloop instructions
        2. ``PROMPT.md`` – legacy project-specific prompt
        3. ``templates/PROMPT.md`` – project templates directory
        4. ``<package>/templates/runloop.md`` – package-bundled runloop
        5. ``<package>/templates/PROMPT.md`` – package-bundled legacy
        """
        return [
            self.project_dir / ".cub" / "runloop.md",
            self.project_dir / "PROMPT.md",
            self.project_dir / "templates" / "PROMPT.md",
            self.package_root / "templates" / "runloop.md",
            self.package_root / "templates" / "PROMPT.md",
        ]


@dataclass(frozen=True)
class TaskPrompt:
    """Structured output from task prompt generation.

    Carries the rendered prompt text along with metadata about what context
    was included (useful for logging and debugging).

    Attributes:
        text: The full rendered prompt string.
        has_epic_context: Whether epic context was included.
        has_retry_context: Whether retry context was included.
    """

    text: str
    has_epic_context: bool = False
    has_retry_context: bool = False


# ---------------------------------------------------------------------------
# Fallback prompt
# ---------------------------------------------------------------------------

_FALLBACK_SYSTEM_PROMPT = """\
# Autonomous Coding Session

You are an autonomous coding agent working through a task backlog.

## Workflow
1. Understand the task
2. Search the codebase before implementing
3. Implement the solution fully
4. Run tests and type checks
5. Close the task when complete
"""


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def generate_system_prompt(project_dir: Path) -> str:
    """Generate the system prompt for the harness.

    Searches for prompt files in priority order and returns the first found.
    Falls back to a minimal hardcoded prompt if nothing is found.

    Args:
        project_dir: Path to the project root directory.

    Returns:
        System prompt content.
    """
    config = PromptConfig(project_dir=project_dir)

    for prompt_file in config.prompt_search_paths:
        if prompt_file.exists():
            return prompt_file.read_text()

    return _FALLBACK_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Direct-mode prompt
# ---------------------------------------------------------------------------


def generate_direct_task_prompt(task_content: str) -> str:
    """Generate a task prompt for direct mode (no task backend).

    Args:
        task_content: Raw task description provided via ``--direct``.

    Returns:
        Rendered task prompt string.
    """
    prompt_parts: list[str] = []

    prompt_parts.append("## CURRENT TASK\n")
    prompt_parts.append("Mode: Direct (no task backend)")
    prompt_parts.append("")
    prompt_parts.append("Description:")
    prompt_parts.append(task_content)
    prompt_parts.append("")
    prompt_parts.append("When complete:")
    prompt_parts.append("1. Run feedback loops (typecheck, test, lint) if code was changed")
    prompt_parts.append("2. Commit changes if appropriate")
    prompt_parts.append("")
    prompt_parts.append(
        "Note: This is a direct task without a task backend. "
        "No task ID to close. Just complete the work described above."
    )

    return "\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# Epic context
# ---------------------------------------------------------------------------


def generate_epic_context(task: Task, task_backend: TaskBackend) -> str | None:
    """Generate epic context for a task that belongs to an epic.

    When a task belongs to an epic, this provides context about the epic's
    purpose and what sibling tasks have been completed or remain. This helps
    prevent repeated work and gives the agent awareness of the bigger picture.

    Args:
        task: Task to generate epic context for.
        task_backend: The task backend instance.

    Returns:
        Epic context string, or ``None`` if task has no parent epic.
    """
    from cub.core.tasks.models import TaskStatus

    # Skip if task has no parent
    if not task.parent:
        return None

    # Fetch the parent epic
    epic = task_backend.get_task(task.parent)
    if not epic:
        return None

    # Build epic context
    context_parts: list[str] = []
    context_parts.append("## Epic Context\n")
    context_parts.append(f"This task belongs to epic: **{epic.id}** - {epic.title}\n")

    # Add truncated epic description (~200 words)
    if epic.description:
        words = epic.description.split()
        if len(words) > 200:
            truncated = " ".join(words[:200]) + "..."
        else:
            truncated = epic.description
        context_parts.append("Epic Purpose:")
        context_parts.append(truncated)
        context_parts.append("")

    # Fetch sibling tasks (all tasks with same parent)
    sibling_tasks = task_backend.list_tasks(parent=task.parent)

    if sibling_tasks:
        # Separate into completed and remaining
        completed = [t for t in sibling_tasks if t.status == TaskStatus.CLOSED]
        remaining = [t for t in sibling_tasks if t.status != TaskStatus.CLOSED and t.id != task.id]

        if completed:
            context_parts.append("Completed Sibling Tasks:")
            for t in completed:
                context_parts.append(f"- ✓ {t.id}: {t.title}")
            context_parts.append("")

        if remaining:
            context_parts.append("Remaining Sibling Tasks:")
            for t in remaining:
                status_icon = "◐" if t.status == TaskStatus.IN_PROGRESS else "○"
                context_parts.append(f"- {status_icon} {t.id}: {t.title}")
            context_parts.append("")

    return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# Retry context
# ---------------------------------------------------------------------------


def generate_retry_context(
    task: Task, ledger_integration: LedgerIntegration, log_tail_lines: int = 50
) -> str | None:
    """Generate retry context for a task with previous failed attempts.

    When a task is retried after failure, this provides context about what
    went wrong in previous attempts. This helps the agent avoid repeating
    the same mistakes and understand the failure patterns.

    Args:
        task: Task to generate retry context for.
        ledger_integration: The ledger integration instance.
        log_tail_lines: Number of lines to extract from the end of the last log.

    Returns:
        Retry context string, or ``None`` if task has no previous attempts.
    """
    # Get the ledger entry for this task
    entry = ledger_integration.writer.get_entry(task.id)
    if not entry or not entry.attempts:
        return None

    # Filter to failed attempts only
    failed_attempts = [a for a in entry.attempts if not a.success]
    if not failed_attempts:
        return None

    # Build retry context
    context_parts: list[str] = []
    context_parts.append("## Retry Context\n")
    context_parts.append(
        f"This task has been attempted {len(entry.attempts)} time(s) before with "
        f"{len(failed_attempts)} failure(s).\n"
    )

    # Add summary of all failed attempts
    context_parts.append("Previous Failed Attempts:")
    for attempt in failed_attempts:
        duration_str = f"{attempt.duration_seconds}s"
        if attempt.duration_seconds >= 60:
            duration_str = f"{attempt.duration_minutes:.1f}m"

        parts = [f"- Attempt #{attempt.attempt_number}:"]
        parts.append(f"Model: {attempt.model or 'unknown'}")
        parts.append(f"Duration: {duration_str}")

        if attempt.error_category:
            parts.append(f"Error: {attempt.error_category}")
        if attempt.error_summary:
            parts.append(f"Summary: {attempt.error_summary}")

        context_parts.append(" | ".join(parts))

    context_parts.append("")

    # Add log tail from the most recent failed attempt
    last_failed = failed_attempts[-1]
    log_path = (
        ledger_integration.writer.by_task_dir
        / task.id
        / "attempts"
        / f"{last_failed.attempt_number:03d}-harness.log"
    )

    if log_path.exists():
        try:
            log_content = log_path.read_text(encoding="utf-8")
            lines = log_content.splitlines()

            if lines:
                # Get the tail of the log
                tail_lines = lines[-log_tail_lines:] if len(lines) > log_tail_lines else lines
                context_parts.append(
                    f"Last {len(tail_lines)} lines from most recent failure "
                    f"(attempt #{last_failed.attempt_number}):"
                )
                context_parts.append("```")
                context_parts.extend(tail_lines)
                context_parts.append("```")
                context_parts.append("")
        except (OSError, UnicodeDecodeError) as e:
            # Log file exists but couldn't be read - gracefully skip
            error_msg = (
                f"(Log file for attempt #{last_failed.attempt_number} "
                f"exists but could not be read: {e})"
            )
            context_parts.append(error_msg)
            context_parts.append("")

    return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# Task prompt (orchestrator)
# ---------------------------------------------------------------------------


def generate_task_prompt(
    task: Task,
    task_backend: TaskBackend,
    ledger_integration: LedgerIntegration | None = None,
) -> str:
    """Generate the full task prompt for a specific task.

    Combines task details, acceptance criteria, epic context, retry context,
    and backend-specific management instructions into a single prompt.

    Args:
        task: Task to generate prompt for.
        task_backend: The task backend instance.
        ledger_integration: Optional ledger integration for retry context.

    Returns:
        Rendered task prompt string.
    """
    # Build the task prompt
    prompt_parts: list[str] = []

    # Add task header
    prompt_parts.append("## CURRENT TASK\n")
    prompt_parts.append(f"Task ID: {task.id}")
    prompt_parts.append(f"Type: {task.type.value if hasattr(task.type, 'value') else task.type}")
    prompt_parts.append(f"Title: {task.title}\n")

    # Add description
    prompt_parts.append("Description:")
    prompt_parts.append(task.description or "(No description provided)")
    prompt_parts.append("")

    # Add acceptance criteria if present
    if task.acceptance_criteria:
        prompt_parts.append("Acceptance Criteria:")
        for criterion in task.acceptance_criteria:
            prompt_parts.append(f"- {criterion}")
        prompt_parts.append("")

    # Add epic context if available
    epic_ctx = generate_epic_context(task, task_backend)
    if epic_ctx:
        prompt_parts.append(epic_ctx)

    # Add retry context if available
    retry_ctx: str | None = None
    if ledger_integration:
        retry_ctx = generate_retry_context(task, ledger_integration)
        if retry_ctx:
            prompt_parts.append(retry_ctx)

    # Add backend-specific task management instructions
    prompt_parts.append("## Task Management\n")
    prompt_parts.append(task_backend.get_agent_instructions(task.id))
    prompt_parts.append("")

    # Add completion workflow (backend-agnostic)
    task_type_str = task.type.value if hasattr(task.type, "value") else task.type
    prompt_parts.append("## When Complete\n")
    prompt_parts.append("1. Run feedback loops (typecheck, test, lint)")
    prompt_parts.append("2. Mark the task complete (see Task Management above)")
    prompt_parts.append(f"3. Commit: `{task_type_str}({task.id}): {task.title}`")

    return "\n".join(prompt_parts)
