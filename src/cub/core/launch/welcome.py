"""
Welcome message generation for cub launch.

Generates welcome messages from project snapshots in both Rich (terminal)
and plain text (harness context) formats. The welcome message is the first
thing users see when launching cub, providing opinionated guidance and
immediate value.

Design principles:
- Concise: Essential information only, no clutter
- Opinionated: Clear recommendations, not just data
- Immediately useful: Actionable suggestions front and center
- Context-aware: Different formats for terminal vs harness
"""

from __future__ import annotations

from dataclasses import dataclass

from cub.core.suggestions.engine import WelcomeMessage
from cub.core.suggestions.models import ProjectSnapshot


@dataclass
class WelcomeFormat:
    """Welcome message in different output formats.

    Attributes:
        rich_content: Rich-formatted content for terminal display
        plain_content: Plain text content for harness context injection
        has_suggestions: Whether there are actionable suggestions
        priority_level: Highest priority level among suggestions (urgent/high/medium/low)
    """

    rich_content: str  # Rich markup for terminal rendering
    plain_content: str  # Plain text for system prompt injection
    has_suggestions: bool
    priority_level: str


def generate_welcome(snapshot: ProjectSnapshot) -> WelcomeMessage:
    """Generate welcome message from project snapshot.

    Converts a ProjectSnapshot (rich project state data) into a WelcomeMessage
    (focused on task stats and suggestions). This is the core transformation
    that extracts what users need to see when launching cub.

    Args:
        snapshot: Current project state snapshot

    Returns:
        WelcomeMessage with task stats and suggestions

    Example:
        >>> from cub.core.suggestions.models import ProjectSnapshot
        >>> snapshot = ProjectSnapshot(
        ...     total_tasks=10,
        ...     open_tasks=5,
        ...     in_progress_tasks=2,
        ...     ready_tasks=3,
        ... )
        >>> welcome = generate_welcome(snapshot)
        >>> print(f"Tasks: {welcome.total_tasks}, Ready: {welcome.ready_tasks}")
    """
    # Extract task statistics from snapshot
    return WelcomeMessage(
        total_tasks=snapshot.total_tasks,
        open_tasks=snapshot.open_tasks,
        in_progress_tasks=snapshot.in_progress_tasks,
        ready_tasks=snapshot.ready_tasks,
        top_suggestions=[],  # Suggestions are added separately by the engine
        available_skills=[],
    )


def format_for_terminal(welcome: WelcomeMessage) -> str:
    """Format welcome message for Rich terminal display.

    Generates Rich markup that will be rendered by cli/default.py.
    This is used when cub launches in a terminal context.

    Args:
        welcome: Welcome message with stats and suggestions

    Returns:
        Rich markup string for terminal rendering

    Note:
        The actual Rich rendering (Panel, Table) is handled by cli/default.py.
        This function just generates structured markup if needed for future use.
    """
    # Build stats summary
    stats_parts: list[str] = []
    if welcome.total_tasks > 0:
        stats_parts.append(f"[bold]{welcome.total_tasks}[/bold] tasks")
        if welcome.open_tasks > 0:
            stats_parts.append(f"[cyan]{welcome.open_tasks} open[/cyan]")
        if welcome.in_progress_tasks > 0:
            stats_parts.append(f"[yellow]{welcome.in_progress_tasks} in progress[/yellow]")
        if welcome.ready_tasks > 0:
            stats_parts.append(f"[green]{welcome.ready_tasks} ready[/green]")

    stats_line = " | ".join(stats_parts) if stats_parts else "No tasks found"

    # Build header
    content_lines = [
        "[bold cyan]Welcome to cub[/bold cyan]",
        "",
        stats_line,
    ]

    return "\n".join(content_lines)


def format_for_harness(welcome: WelcomeMessage) -> str:
    """Format welcome message for harness context injection.

    Generates plain text suitable for injecting into system prompts or
    harness context. This is used when cub passes project context to
    the launched harness.

    The format is optimized for LLM consumption: structured, concise,
    and focused on actionable information.

    Args:
        welcome: Welcome message with stats and suggestions

    Returns:
        Plain text string for system prompt injection

    Example output:
        PROJECT STATUS
        ==============
        Tasks: 10 total | 5 open | 2 in progress | 3 ready

        TOP SUGGESTIONS
        ===============
        1. [HIGH] Work on task cub-123: Implement feature X
           Rationale: This task is ready and unblocked
           Action: cub task claim cub-123

        2. [MEDIUM] Push uncommitted changes
           Rationale: Avoid losing work
           Action: git push
    """
    lines: list[str] = []

    # Project status section
    lines.append("PROJECT STATUS")
    lines.append("=" * 50)

    # Task statistics
    if welcome.total_tasks > 0:
        task_parts = [f"{welcome.total_tasks} total"]
        if welcome.open_tasks > 0:
            task_parts.append(f"{welcome.open_tasks} open")
        if welcome.in_progress_tasks > 0:
            task_parts.append(f"{welcome.in_progress_tasks} in progress")
        if welcome.ready_tasks > 0:
            task_parts.append(f"{welcome.ready_tasks} ready")

        lines.append(f"Tasks: {' | '.join(task_parts)}")
    else:
        lines.append("No tasks found")

    lines.append("")

    # Suggestions section
    if welcome.top_suggestions:
        lines.append("TOP SUGGESTIONS")
        lines.append("=" * 50)

        for idx, suggestion in enumerate(welcome.top_suggestions, start=1):
            # Priority label
            urgency = suggestion.urgency_level.upper()

            # Title with priority
            lines.append(f"{idx}. [{urgency}] {suggestion.title}")

            # Rationale
            if suggestion.rationale:
                lines.append(f"   Rationale: {suggestion.rationale}")

            # Action command
            if suggestion.action:
                lines.append(f"   Action: {suggestion.action}")

            # Blank line between suggestions
            if idx < len(welcome.top_suggestions):
                lines.append("")

    return "\n".join(lines)


def format_for_inline(welcome: WelcomeMessage) -> str:
    """Format welcome message for inline status (nested harness context).

    Generates compact plain text for displaying when cub is run inside
    an existing harness session. This is the "you're already in a session"
    message that prevents nesting.

    Args:
        welcome: Welcome message with stats and suggestions

    Returns:
        Compact plain text status message

    Example output:
        cub session active

        10 tasks | 5 open | 2 in progress | 3 ready

        Suggested next actions:
        1. Work on task cub-123
        2. Push uncommitted changes
        3. Review completed work
    """
    lines: list[str] = []

    # Header
    lines.append("cub session active")
    lines.append("")

    # Task stats
    if welcome.total_tasks > 0:
        parts = [f"{welcome.total_tasks} tasks"]
        if welcome.open_tasks > 0:
            parts.append(f"{welcome.open_tasks} open")
        if welcome.in_progress_tasks > 0:
            parts.append(f"{welcome.in_progress_tasks} in progress")
        if welcome.ready_tasks > 0:
            parts.append(f"{welcome.ready_tasks} ready")

        lines.append(" | ".join(parts))
    else:
        lines.append("No tasks found")

    lines.append("")

    # Top suggestions (compact format)
    if welcome.top_suggestions:
        lines.append("Suggested next actions:")
        for idx, suggestion in enumerate(welcome.top_suggestions[:3], start=1):
            lines.append(f"{idx}. {suggestion.title}")
            if suggestion.action:
                lines.append(f"   > {suggestion.action}")

    return "\n".join(lines)


def create_welcome_format(welcome: WelcomeMessage, *, nested: bool = False) -> WelcomeFormat:
    """Create complete welcome format with all variants.

    Generates all output formats (Rich, plain text, inline) from a single
    WelcomeMessage. This is the main entry point for welcome formatting.

    Args:
        welcome: Welcome message with stats and suggestions
        nested: If True, generate inline format instead of full welcome

    Returns:
        WelcomeFormat with all output variants

    Example:
        >>> welcome = WelcomeMessage(...)
        >>> fmt = create_welcome_format(welcome)
        >>> print(fmt.plain_content)  # For system prompt
        >>> print(fmt.rich_content)   # For terminal display
    """
    # Determine priority level
    priority_level = "low"
    if welcome.top_suggestions:
        highest_priority = max(
            s.priority_score for s in welcome.top_suggestions
        )
        if highest_priority >= 0.9:
            priority_level = "urgent"
        elif highest_priority >= 0.7:
            priority_level = "high"
        elif highest_priority >= 0.5:
            priority_level = "medium"

    # Generate formats
    if nested:
        rich_content = format_for_inline(welcome)
        plain_content = format_for_inline(welcome)
    else:
        rich_content = format_for_terminal(welcome)
        plain_content = format_for_harness(welcome)

    return WelcomeFormat(
        rich_content=rich_content,
        plain_content=plain_content,
        has_suggestions=len(welcome.top_suggestions) > 0,
        priority_level=priority_level,
    )


__all__ = [
    "generate_welcome",
    "format_for_terminal",
    "format_for_harness",
    "format_for_inline",
    "create_welcome_format",
    "WelcomeFormat",
]
