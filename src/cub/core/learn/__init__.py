"""
Learn service for extracting patterns and lessons from ledger data.

Provides high-level operations for:
- Analyzing ledger entries for patterns
- Identifying repeated failures, cost outliers, and lessons learned
- Suggesting updates to guardrails and agent instructions
"""

from cub.core.learn.service import (
    LearnResult,
    LearnService,
    LearnServiceError,
    Pattern,
    PatternCategory,
    Suggestion,
    SuggestionTarget,
)

__all__ = [
    "LearnService",
    "LearnServiceError",
    "Pattern",
    "PatternCategory",
    "Suggestion",
    "SuggestionTarget",
    "LearnResult",
]
