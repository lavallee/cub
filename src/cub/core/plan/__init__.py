"""
Plan module for cub.

This module provides data models and utilities for managing plans - the
intermediate artifacts between specs and tasks. Plans go through three
stages (orient, architect, itemize) to produce a taskable itemized plan.

Directory structure:
    project/
    ├── plans/
    │   └── {slug}/
    │       ├── plan.json           # Plan metadata
    │       ├── orientation.md      # Stage 1 output
    │       ├── architecture.md     # Stage 2 output
    │       └── itemized-plan.md    # Stage 3 output
"""

from cub.core.plan.models import (
    Plan,
    PlanStage,
    PlanStatus,
    SpecStage,
    StageStatus,
)

__all__ = [
    "Plan",
    "PlanStage",
    "PlanStatus",
    "SpecStage",
    "StageStatus",
]
