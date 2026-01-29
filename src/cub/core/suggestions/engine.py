"""
Suggestion engine for cub.

Composes data sources, applies ranking, and provides the public API
for getting smart suggestions about what to do next.
"""

from dataclasses import dataclass
from pathlib import Path

from cub.core.suggestions.models import Suggestion
from cub.core.suggestions.ranking import rank_suggestions
from cub.core.suggestions.sources import (
    GitSource,
    LedgerSource,
    MilestoneSource,
    SuggestionSource,
    TaskSource,
)


@dataclass
class WelcomeMessage:
    """Welcome message with project stats and suggestions.

    Provides a structured overview for the user when they launch cub,
    including key metrics and top suggestions.
    """

    # Project statistics
    total_tasks: int
    open_tasks: int
    in_progress_tasks: int
    ready_tasks: int

    # Suggestions
    top_suggestions: list[Suggestion]

    # Available skills/tools
    available_skills: list[str]


class SuggestionEngine:
    """Engine for generating and ranking suggestions.

    Composes multiple data sources (tasks, git, ledger, milestones),
    collects suggestions from each, and ranks them to provide
    actionable recommendations.
    """

    def __init__(self, project_dir: Path | None = None):
        """Initialize suggestion engine.

        Args:
            project_dir: Project directory path (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()

        # Initialize data sources
        self.sources: list[SuggestionSource] = [
            TaskSource(project_dir=self.project_dir),
            GitSource(project_dir=self.project_dir),
            LedgerSource(project_dir=self.project_dir),
            MilestoneSource(project_dir=self.project_dir),
        ]

    def get_suggestions(self, limit: int | None = None) -> list[Suggestion]:
        """Get ranked list of suggestions.

        Collects suggestions from all sources, ranks them, and returns
        the top N suggestions.

        Args:
            limit: Maximum number of suggestions to return (None = all)

        Returns:
            Ranked list of suggestions (highest priority first)
        """
        # Collect suggestions from all sources
        all_suggestions: list[Suggestion] = []
        for source in self.sources:
            try:
                source_suggestions = source.get_suggestions()
                all_suggestions.extend(source_suggestions)
            except Exception:
                # If a source fails, continue with others
                # This ensures we always provide some suggestions
                continue

        # Rank all suggestions
        ranked_suggestions = rank_suggestions(all_suggestions)

        # Apply limit if specified
        if limit is not None and limit > 0:
            ranked_suggestions = ranked_suggestions[:limit]

        return ranked_suggestions

    def get_next_action(self) -> Suggestion | None:
        """Get single best recommendation for what to do next.

        Returns:
            The highest-priority suggestion, or None if no suggestions available
        """
        suggestions = self.get_suggestions(limit=1)
        return suggestions[0] if suggestions else None

    def get_welcome(
        self, max_suggestions: int = 5, available_skills: list[str] | None = None
    ) -> WelcomeMessage:
        """Get welcome message with stats and top suggestions.

        Args:
            max_suggestions: Maximum number of suggestions to include
            available_skills: List of available skill names

        Returns:
            WelcomeMessage with project stats and top suggestions
        """
        # Get top suggestions
        top_suggestions = self.get_suggestions(limit=max_suggestions)

        # Gather task statistics from TaskSource
        task_stats = self._get_task_stats()

        return WelcomeMessage(
            total_tasks=task_stats["total_tasks"],
            open_tasks=task_stats["open_tasks"],
            in_progress_tasks=task_stats["in_progress_tasks"],
            ready_tasks=task_stats["ready_tasks"],
            top_suggestions=top_suggestions,
            available_skills=available_skills or [],
        )

    def _get_task_stats(self) -> dict[str, int]:
        """Get task statistics for welcome message.

        Returns:
            Dict with task counts
        """
        # Find TaskSource in sources by checking for backend attribute
        task_source = None
        for source in self.sources:
            # Check if source has backend attribute (duck typing for TaskSource)
            if hasattr(source, "backend"):
                task_source = source
                break

        if task_source is None:
            return {
                "total_tasks": 0,
                "open_tasks": 0,
                "in_progress_tasks": 0,
                "ready_tasks": 0,
            }

        try:
            from cub.core.tasks.models import TaskStatus

            backend = task_source.backend

            # Get task counts
            all_tasks = backend.list_tasks()
            total_tasks = len(all_tasks)
            open_tasks = len(backend.list_tasks(status=TaskStatus.OPEN))
            in_progress_tasks = len(backend.list_tasks(status=TaskStatus.IN_PROGRESS))
            ready_tasks = len(backend.get_ready_tasks())

            return {
                "total_tasks": total_tasks,
                "open_tasks": open_tasks,
                "in_progress_tasks": in_progress_tasks,
                "ready_tasks": ready_tasks,
            }
        except Exception:
            # If backend is unavailable, return zeros
            return {
                "total_tasks": 0,
                "open_tasks": 0,
                "in_progress_tasks": 0,
                "ready_tasks": 0,
            }
