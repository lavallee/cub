"""Tests for welcome message generation and formatting."""

from __future__ import annotations

from datetime import datetime, timezone

from cub.core.launch.welcome import (
    create_welcome_format,
    format_for_harness,
    format_for_inline,
    format_for_terminal,
    generate_welcome,
)
from cub.core.suggestions.engine import WelcomeMessage
from cub.core.suggestions.models import ProjectSnapshot, Suggestion, SuggestionCategory

# =============================================================================
# Fixtures
# =============================================================================


def _make_snapshot(
    *,
    total_tasks: int = 10,
    open_tasks: int = 5,
    in_progress_tasks: int = 2,
    ready_tasks: int = 3,
    closed_tasks: int = 0,
    blocked_tasks: int = 0,
) -> ProjectSnapshot:
    """Create a ProjectSnapshot for testing."""
    return ProjectSnapshot(
        total_tasks=total_tasks,
        open_tasks=open_tasks,
        in_progress_tasks=in_progress_tasks,
        closed_tasks=closed_tasks,
        ready_tasks=ready_tasks,
        blocked_tasks=blocked_tasks,
        snapshot_time=datetime.now(timezone.utc),
    )


def _make_welcome(
    *,
    total_tasks: int = 10,
    open_tasks: int = 5,
    in_progress_tasks: int = 2,
    ready_tasks: int = 3,
    suggestions: list[Suggestion] | None = None,
) -> WelcomeMessage:
    """Create a WelcomeMessage for testing."""
    if suggestions is None:
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Work on task cub-123",
                description="Implement the feature",
                rationale="This task is ready and unblocked",
                priority_score=0.85,
                action="bd update cub-123 --status in_progress",
                source="task",
            ),
            Suggestion(
                category=SuggestionCategory.GIT,
                title="Push uncommitted changes",
                description="You have uncommitted work",
                rationale="Avoid losing work",
                priority_score=0.7,
                action="git push",
                source="git",
            ),
        ]

    return WelcomeMessage(
        total_tasks=total_tasks,
        open_tasks=open_tasks,
        in_progress_tasks=in_progress_tasks,
        ready_tasks=ready_tasks,
        top_suggestions=suggestions,
        available_skills=[],
    )


# =============================================================================
# Test generate_welcome
# =============================================================================


class TestGenerateWelcome:
    """Tests for generate_welcome function."""

    def test_generate_welcome_from_snapshot(self) -> None:
        """Generate welcome message from project snapshot."""
        snapshot = _make_snapshot(
            total_tasks=10,
            open_tasks=5,
            in_progress_tasks=2,
            ready_tasks=3,
        )

        welcome = generate_welcome(snapshot)

        assert welcome.total_tasks == 10
        assert welcome.open_tasks == 5
        assert welcome.in_progress_tasks == 2
        assert welcome.ready_tasks == 3
        assert welcome.top_suggestions == []
        assert welcome.available_skills == []

    def test_generate_welcome_empty_project(self) -> None:
        """Generate welcome for empty project."""
        snapshot = _make_snapshot(
            total_tasks=0,
            open_tasks=0,
            in_progress_tasks=0,
            ready_tasks=0,
        )

        welcome = generate_welcome(snapshot)

        assert welcome.total_tasks == 0
        assert welcome.open_tasks == 0
        assert welcome.in_progress_tasks == 0
        assert welcome.ready_tasks == 0

    def test_generate_welcome_preserves_task_stats(self) -> None:
        """Ensure all task statistics are preserved."""
        snapshot = _make_snapshot(
            total_tasks=25,
            open_tasks=10,
            in_progress_tasks=5,
            ready_tasks=8,
        )

        welcome = generate_welcome(snapshot)

        # All stats should match
        assert welcome.total_tasks == snapshot.total_tasks
        assert welcome.open_tasks == snapshot.open_tasks
        assert welcome.in_progress_tasks == snapshot.in_progress_tasks
        assert welcome.ready_tasks == snapshot.ready_tasks


# =============================================================================
# Test format_for_terminal
# =============================================================================


class TestFormatForTerminal:
    """Tests for Rich terminal formatting."""

    def test_format_terminal_with_tasks(self) -> None:
        """Format terminal output with tasks."""
        welcome = _make_welcome()
        output = format_for_terminal(welcome)

        # Should contain Rich markup
        assert "[bold cyan]Welcome to cub[/bold cyan]" in output
        assert "[bold]10[/bold] tasks" in output
        assert "[cyan]5 open[/cyan]" in output
        assert "[yellow]2 in progress[/yellow]" in output
        assert "[green]3 ready[/green]" in output

    def test_format_terminal_empty_tasks(self) -> None:
        """Format terminal output with no tasks."""
        welcome = _make_welcome(
            total_tasks=0,
            open_tasks=0,
            in_progress_tasks=0,
            ready_tasks=0,
            suggestions=[],
        )
        output = format_for_terminal(welcome)

        assert "No tasks found" in output

    def test_format_terminal_partial_stats(self) -> None:
        """Format terminal with only some task states."""
        welcome = _make_welcome(
            total_tasks=5,
            open_tasks=5,
            in_progress_tasks=0,
            ready_tasks=0,
        )
        output = format_for_terminal(welcome)

        assert "[bold]5[/bold] tasks" in output
        assert "[cyan]5 open[/cyan]" in output
        # Should not include zero stats
        assert "0 in progress" not in output
        assert "0 ready" not in output


# =============================================================================
# Test format_for_harness
# =============================================================================


class TestFormatForHarness:
    """Tests for plain text harness context formatting."""

    def test_format_harness_with_suggestions(self) -> None:
        """Format harness context with suggestions."""
        welcome = _make_welcome()
        output = format_for_harness(welcome)

        # Should contain plain text structure
        assert "PROJECT STATUS" in output
        assert "=" * 50 in output
        assert "Tasks: 10 total | 5 open | 2 in progress | 3 ready" in output

        # Should contain suggestions
        assert "TOP SUGGESTIONS" in output
        # First suggestion has priority 0.85 -> "urgent"
        assert "1. [URGENT] Work on task cub-123" in output
        assert "Rationale: This task is ready and unblocked" in output
        assert "Action: bd update cub-123 --status in_progress" in output

        # Second suggestion has priority 0.7 -> "high"
        assert "2. [HIGH] Push uncommitted changes" in output
        assert "Rationale: Avoid losing work" in output
        assert "Action: git push" in output

    def test_format_harness_no_suggestions(self) -> None:
        """Format harness context without suggestions."""
        welcome = _make_welcome(suggestions=[])
        output = format_for_harness(welcome)

        # Should still show task stats
        assert "PROJECT STATUS" in output
        assert "Tasks: 10 total | 5 open | 2 in progress | 3 ready" in output

        # Should not have suggestions section
        assert "TOP SUGGESTIONS" not in output

    def test_format_harness_empty_project(self) -> None:
        """Format harness context for empty project."""
        welcome = _make_welcome(
            total_tasks=0,
            open_tasks=0,
            in_progress_tasks=0,
            ready_tasks=0,
            suggestions=[],
        )
        output = format_for_harness(welcome)

        assert "No tasks found" in output

    def test_format_harness_suggestion_priority_levels(self) -> None:
        """Format harness context with different priority levels."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Urgent task",
                rationale="Critical blocker",
                priority_score=0.95,
                action="fix now",
                source="task",
            ),
            Suggestion(
                category=SuggestionCategory.GIT,
                title="Low priority task",
                rationale="Nice to have",
                priority_score=0.3,
                action="maybe later",
                source="git",
            ),
        ]
        welcome = _make_welcome(suggestions=suggestions)
        output = format_for_harness(welcome)

        # Should show correct priority labels
        assert "[URGENT] Urgent task" in output
        assert "[LOW] Low priority task" in output


# =============================================================================
# Test format_for_inline
# =============================================================================


class TestFormatForInline:
    """Tests for inline status formatting (nested context)."""

    def test_format_inline_with_tasks(self) -> None:
        """Format inline status with tasks."""
        welcome = _make_welcome()
        output = format_for_inline(welcome)

        assert "cub session active" in output
        assert "10 tasks | 5 open | 2 in progress | 3 ready" in output

        # Should show top 3 suggestions
        assert "Suggested next actions:" in output
        assert "1. Work on task cub-123" in output
        assert "> bd update cub-123 --status in_progress" in output
        assert "2. Push uncommitted changes" in output
        assert "> git push" in output

    def test_format_inline_no_tasks(self) -> None:
        """Format inline status with no tasks."""
        welcome = _make_welcome(
            total_tasks=0,
            open_tasks=0,
            in_progress_tasks=0,
            ready_tasks=0,
            suggestions=[],
        )
        output = format_for_inline(welcome)

        assert "cub session active" in output
        assert "No tasks found" in output

    def test_format_inline_limits_suggestions(self) -> None:
        """Format inline status limits to top 3 suggestions."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title=f"Task {i}",
                rationale="test",
                priority_score=0.9 - (i * 0.1),
                action=f"action {i}",
                source="task",
            )
            for i in range(5)
        ]
        welcome = _make_welcome(suggestions=suggestions)
        output = format_for_inline(welcome)

        # Should only show first 3
        assert "1. Task 0" in output
        assert "2. Task 1" in output
        assert "3. Task 2" in output
        assert "4. Task 3" not in output
        assert "5. Task 4" not in output


# =============================================================================
# Test create_welcome_format
# =============================================================================


class TestCreateWelcomeFormat:
    """Tests for complete welcome format creation."""

    def test_create_format_terminal(self) -> None:
        """Create welcome format for terminal."""
        welcome = _make_welcome()
        fmt = create_welcome_format(welcome, nested=False)

        assert fmt.has_suggestions is True
        assert fmt.priority_level == "high"  # Priority score 0.85
        assert "[bold cyan]Welcome to cub[/bold cyan]" in fmt.rich_content
        assert "PROJECT STATUS" in fmt.plain_content

    def test_create_format_nested(self) -> None:
        """Create welcome format for nested context."""
        welcome = _make_welcome()
        fmt = create_welcome_format(welcome, nested=True)

        assert fmt.has_suggestions is True
        assert "cub session active" in fmt.rich_content
        assert "cub session active" in fmt.plain_content

    def test_create_format_priority_urgent(self) -> None:
        """Create format with urgent priority."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Critical task",
                rationale="Blocker",
                priority_score=0.95,
                action="do now",
                source="task",
            )
        ]
        welcome = _make_welcome(suggestions=suggestions)
        fmt = create_welcome_format(welcome)

        assert fmt.priority_level == "urgent"

    def test_create_format_priority_medium(self) -> None:
        """Create format with medium priority."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Medium task",
                rationale="Normal",
                priority_score=0.6,
                action="do soon",
                source="task",
            )
        ]
        welcome = _make_welcome(suggestions=suggestions)
        fmt = create_welcome_format(welcome)

        assert fmt.priority_level == "medium"

    def test_create_format_priority_low(self) -> None:
        """Create format with low priority."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Low task",
                rationale="Optional",
                priority_score=0.3,
                action="maybe later",
                source="task",
            )
        ]
        welcome = _make_welcome(suggestions=suggestions)
        fmt = create_welcome_format(welcome)

        assert fmt.priority_level == "low"

    def test_create_format_no_suggestions(self) -> None:
        """Create format with no suggestions."""
        welcome = _make_welcome(suggestions=[])
        fmt = create_welcome_format(welcome)

        assert fmt.has_suggestions is False
        assert fmt.priority_level == "low"


# =============================================================================
# Integration tests
# =============================================================================


class TestWelcomeIntegration:
    """Integration tests for welcome message flow."""

    def test_snapshot_to_welcome_to_format(self) -> None:
        """Test full flow: snapshot -> welcome -> format."""
        # Create snapshot
        snapshot = _make_snapshot(
            total_tasks=15,
            open_tasks=8,
            in_progress_tasks=3,
            ready_tasks=5,
        )

        # Generate welcome
        welcome = generate_welcome(snapshot)

        # Create format
        fmt = create_welcome_format(welcome)

        # Verify stats propagated
        assert "15" in fmt.plain_content or "[bold]15[/bold]" in fmt.rich_content
        assert "8 open" in fmt.plain_content or "[cyan]8 open[/cyan]" in fmt.rich_content

    def test_welcome_with_suggestions_integration(self) -> None:
        """Test welcome with suggestions added after generation."""
        snapshot = _make_snapshot()
        welcome = generate_welcome(snapshot)

        # Add suggestions (simulating what the engine does)
        welcome = WelcomeMessage(
            total_tasks=welcome.total_tasks,
            open_tasks=welcome.open_tasks,
            in_progress_tasks=welcome.in_progress_tasks,
            ready_tasks=welcome.ready_tasks,
            top_suggestions=[
                Suggestion(
                    category=SuggestionCategory.TASK,
                    title="Next task",
                    rationale="Ready to work",
                    priority_score=0.8,
                    action="bd update task-1 --status in_progress",
                    source="task",
                )
            ],
            available_skills=["commit", "review"],
        )

        # Format for harness
        output = format_for_harness(welcome)

        assert "Next task" in output
        assert "bd update task-1 --status in_progress" in output
