"""
Session tracking module for cub.

This module provides models and utilities for tracking active `cub run`
executions. It supports the unified tracking system that captures task
execution history, costs, and progress.
"""

from cub.core.session.manager import RunSessionError, RunSessionManager
from cub.core.session.models import (
    RunSession,
    SessionBudget,
    SessionStatus,
    generate_run_id,
)

__all__ = [
    "RunSession",
    "SessionBudget",
    "SessionStatus",
    "generate_run_id",
    "RunSessionManager",
    "RunSessionError",
]
