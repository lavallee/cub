"""
PR management module.

Provides functionality for creating, managing, and merging
pull requests with optional CI/review handling.
"""

from cub.core.pr.service import (
    MergeResult,
    PRResult,
    PRService,
    PRServiceError,
    StreamConfig,
)

__all__ = [
    "MergeResult",
    "PRResult",
    "PRService",
    "PRServiceError",
    "StreamConfig",
]
