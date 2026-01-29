"""
Suggestion system for cub.

Provides smart suggestions for next actions based on project state,
analyzing tasks, git history, ledger entries, and milestones to recommend
specific actions with rationale.
"""

from cub.core.suggestions.engine import SuggestionEngine, WelcomeMessage
from cub.core.suggestions.models import (
    ProjectSnapshot,
    Suggestion,
    SuggestionCategory,
)
from cub.core.suggestions.ranking import rank_suggestions
from cub.core.suggestions.sources import (
    GitSource,
    LedgerSource,
    MilestoneSource,
    SuggestionSource,
    TaskSource,
)

__all__ = [
    # Models
    "Suggestion",
    "SuggestionCategory",
    "ProjectSnapshot",
    # Sources
    "SuggestionSource",
    "TaskSource",
    "GitSource",
    "LedgerSource",
    "MilestoneSource",
    # Ranking
    "rank_suggestions",
    # Engine
    "SuggestionEngine",
    "WelcomeMessage",
]
