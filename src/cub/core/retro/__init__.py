"""
Retro service for generating retrospective reports.

Provides high-level operations for:
- Generating retrospective reports for completed plans and epics
- Analyzing what went well and what didn't
- Extracting lessons learned from task execution
"""

from cub.core.retro.service import RetroReport, RetroService, RetroServiceError

__all__ = [
    "RetroService",
    "RetroServiceError",
    "RetroReport",
]
