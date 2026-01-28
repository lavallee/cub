"""
Ranking algorithm for suggestions.

Implements scoring and ordering of suggestions based on multiple factors:
- Base priority score from the suggestion
- Urgency multiplier based on category
- Recency decay based on creation time
"""

from datetime import datetime, timezone

from cub.core.suggestions.models import Suggestion, SuggestionCategory


def rank_suggestions(suggestions: list[Suggestion]) -> list[Suggestion]:
    """Rank suggestions by computed score and return ordered list.

    Scoring formula: base_priority × urgency_multiplier × recency_decay

    Args:
        suggestions: List of suggestions to rank

    Returns:
        Sorted list of suggestions (highest score first)
    """
    if not suggestions:
        return []

    # Calculate final scores for each suggestion
    scored_suggestions = [
        (suggestion, _calculate_final_score(suggestion)) for suggestion in suggestions
    ]

    # Sort by score (descending), then by priority_score (descending), then by title
    scored_suggestions.sort(
        key=lambda x: (-x[1], -x[0].priority_score, x[0].title)
    )

    return [suggestion for suggestion, _ in scored_suggestions]


def _calculate_final_score(suggestion: Suggestion) -> float:
    """Calculate final ranking score for a suggestion.

    Args:
        suggestion: Suggestion to score

    Returns:
        Final score (higher is better)
    """
    base_priority = suggestion.priority_score
    urgency_multiplier = _get_urgency_multiplier(suggestion.category)
    recency_decay = _get_recency_decay(suggestion.created_at)

    final_score = base_priority * urgency_multiplier * recency_decay

    return final_score


def _get_urgency_multiplier(category: SuggestionCategory) -> float:
    """Get urgency multiplier based on suggestion category.

    Different categories have different urgency levels:
    - REVIEW: 1.2 (reviews are important for quality)
    - GIT: 1.15 (git operations prevent work loss)
    - TASK: 1.1 (tasks are core workflow)
    - MILESTONE: 1.05 (milestones provide structure)
    - PLAN: 1.0 (planning is valuable but not urgent)
    - CLEANUP: 0.95 (cleanup is nice but lower priority)

    Args:
        category: Suggestion category

    Returns:
        Multiplier value (typically 0.95 to 1.2)
    """
    multipliers = {
        SuggestionCategory.REVIEW: 1.2,
        SuggestionCategory.GIT: 1.15,
        SuggestionCategory.TASK: 1.1,
        SuggestionCategory.MILESTONE: 1.05,
        SuggestionCategory.PLAN: 1.0,
        SuggestionCategory.CLEANUP: 0.95,
    }

    return multipliers.get(category, 1.0)


def _get_recency_decay(created_at: datetime) -> float:
    """Calculate recency decay factor.

    Older suggestions get slightly lower scores to prefer fresh information.
    Decay is gentle to avoid overly penalizing older suggestions.

    Decay formula:
    - 0-1 hour old: 1.0 (no decay)
    - 1-24 hours: linear decay from 1.0 to 0.95
    - 24+ hours: 0.95 (minimum decay factor)

    Args:
        created_at: When suggestion was created

    Returns:
        Decay factor (0.95 to 1.0)
    """
    now = datetime.now(timezone.utc)
    age_hours = (now - created_at).total_seconds() / 3600

    if age_hours <= 1.0:
        # No decay for very fresh suggestions
        return 1.0
    elif age_hours < 24.0:
        # Linear decay from 1.0 to 0.95 over 23 hours
        decay_per_hour = 0.05 / 23.0
        decay = 1.0 - ((age_hours - 1.0) * decay_per_hour)
        return max(0.95, decay)
    else:
        # Minimum decay for old suggestions
        return 0.95
