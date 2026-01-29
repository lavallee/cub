"""
Reusable hydration engine for expanding unstructured text into structured output.

This package provides the core hydration logic used by punchlists, issue triage,
CLI input expansion, and other features that need to transform brief text into
structured titles, context, implementation steps, and acceptance criteria.
"""

from cub.core.hydrate.engine import hydrate, hydrate_batch
from cub.core.hydrate.formatter import generate_itemized_plan
from cub.core.hydrate.models import HydrationResult, HydrationStatus

__all__ = [
    "HydrationResult",
    "HydrationStatus",
    "generate_itemized_plan",
    "hydrate",
    "hydrate_batch",
]
