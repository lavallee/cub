"""
Formatter for review assessments.

This module provides data formatting functions for review assessments,
including JSON serialization.
"""

from __future__ import annotations

from cub.core.review.models import EpicAssessment, PlanAssessment, TaskAssessment


def to_json(assessment: TaskAssessment | EpicAssessment | PlanAssessment) -> str:
    """Serialize assessment to JSON.

    Args:
        assessment: Assessment model to serialize

    Returns:
        JSON string representation
    """
    return assessment.model_dump_json(indent=2)
