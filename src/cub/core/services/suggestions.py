"""
Suggestion service — clean API for smart project suggestions.

Wraps core/suggestions/ into a service that any interface (CLI, API, skills) can call.
The service is a stateless orchestrator that provides typed methods for getting
intelligent recommendations about what to do next.

Usage:
    >>> from cub.core.services.suggestions import SuggestionService
    >>> service = SuggestionService.from_project_dir(project_dir)
    >>> suggestions = service.get_suggestions(limit=5)
    >>> next_action = service.get_next_action()
    >>> welcome = service.get_welcome()
"""

from __future__ import annotations

from pathlib import Path

from cub.core.suggestions.engine import SuggestionEngine, WelcomeMessage
from cub.core.suggestions.models import Suggestion
from cub.utils.project import get_project_root

# ============================================================================
# Typed exceptions
# ============================================================================


class SuggestionServiceError(Exception):
    """Base exception for SuggestionService errors."""


# ============================================================================
# SuggestionService
# ============================================================================


class SuggestionService:
    """
    Service for generating smart project suggestions.

    Analyzes project state from multiple sources (tasks, git, ledger, milestones)
    and provides intelligent recommendations for what to do next.

    Example:
        >>> service = SuggestionService.from_project_dir(Path.cwd())
        >>> suggestions = service.get_suggestions(limit=3)
        >>> for suggestion in suggestions:
        ...     print(f"{suggestion.formatted_title}: {suggestion.rationale}")
    """

    def __init__(self, project_dir: Path) -> None:
        """
        Initialize service with project directory.

        Args:
            project_dir: Project root directory
        """
        self.project_dir = project_dir
        self._engine = SuggestionEngine(project_dir=project_dir)

    @classmethod
    def from_project_dir(cls, project_dir: Path | None = None) -> SuggestionService:
        """
        Create service from project directory.

        Args:
            project_dir: Project root directory (auto-detected if None)

        Returns:
            Configured SuggestionService instance
        """
        if project_dir is None:
            project_dir = get_project_root()

        return cls(project_dir)

    # ============================================================================
    # Suggestion methods
    # ============================================================================

    def get_suggestions(self, limit: int | None = None) -> list[Suggestion]:
        """
        Get ranked list of suggestions.

        Collects suggestions from all sources (tasks, git, ledger, milestones),
        ranks them by priority, and returns the top N.

        Args:
            limit: Maximum number of suggestions to return (None = all)

        Returns:
            Ranked list of suggestions (highest priority first)

        Example:
            >>> suggestions = service.get_suggestions(limit=5)
            >>> for s in suggestions:
            ...     print(f"{s.urgency_level}: {s.title}")
        """
        return self._engine.get_suggestions(limit=limit)

    def get_next_action(self) -> Suggestion | None:
        """
        Get single best recommendation for what to do next.

        Useful for automated decision-making when you want the highest-priority
        action without displaying multiple options.

        Returns:
            The highest-priority suggestion, or None if no suggestions available

        Example:
            >>> next_action = service.get_next_action()
            >>> if next_action:
            ...     print(f"Recommended: {next_action.action}")
        """
        return self._engine.get_next_action()

    def get_welcome(
        self, max_suggestions: int = 5, available_skills: list[str] | None = None
    ) -> WelcomeMessage:
        """
        Get welcome message with stats and top suggestions.

        Provides a structured overview suitable for displaying when launching
        the project or starting a new session.

        Args:
            max_suggestions: Maximum number of suggestions to include
            available_skills: List of available skill names (e.g., from harness)

        Returns:
            WelcomeMessage with project stats and top suggestions

        Example:
            >>> welcome = service.get_welcome(max_suggestions=3)
            >>> print(f"Tasks: {welcome.open_tasks} open, {welcome.ready_tasks} ready")
            >>> for suggestion in welcome.top_suggestions:
            ...     print(f"- {suggestion.formatted_title}")
        """
        return self._engine.get_welcome(
            max_suggestions=max_suggestions, available_skills=available_skills
        )


__all__ = [
    "SuggestionService",
    "SuggestionServiceError",
]
