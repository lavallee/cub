"""
Punchlist processing for cub.

This module provides functionality to parse punchlist markdown files
containing small bugs/features separated by em-dash delimiters,
hydrate them with Claude to generate structured titles and descriptions,
and create an epic with child tasks.
"""

from cub.core.punchlist.models import HydratedItem, PunchlistItem, PunchlistResult
from cub.core.punchlist.parser import parse_punchlist
from cub.core.punchlist.processor import process_punchlist

__all__ = [
    "HydratedItem",
    "PunchlistItem",
    "PunchlistResult",
    "parse_punchlist",
    "process_punchlist",
]
