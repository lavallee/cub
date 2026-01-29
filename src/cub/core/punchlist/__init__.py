"""
Punchlist processing for cub.

This module provides functionality to parse punchlist markdown files
containing small bugs/features separated by em-dash delimiters,
hydrate them with Claude to generate structured output,
and produce itemized-plan.md files for staging.
"""

from cub.core.hydrate.models import HydrationResult
from cub.core.punchlist.models import HydratedItem, PunchlistItem, PunchlistResult
from cub.core.punchlist.parser import parse_punchlist
from cub.core.punchlist.processor import process_punchlist

__all__ = [
    "HydratedItem",
    "HydrationResult",
    "PunchlistItem",
    "PunchlistResult",
    "parse_punchlist",
    "process_punchlist",
]
