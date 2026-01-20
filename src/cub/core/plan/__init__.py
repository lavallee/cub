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

ID Formats (beads-compatible):
    - Epic: {project}-{random 3 chars} (e.g., cub-k7m)
    - Task: {epic_id}.{number} (e.g., cub-k7m.1)
    - Subtask: {task_id}.{number} (e.g., cub-k7m.1.1)
"""

from cub.core.plan.context import (
    OrientDepth,
    PlanContext,
    PlanContextError,
    PlanExistsError,
    SpecNotFoundError,
)
from cub.core.plan.ids import (
    generate_epic_id,
    generate_subtask_id,
    generate_task_id,
    get_parent_id,
    is_valid_epic_id,
    is_valid_subtask_id,
    is_valid_task_id,
    parse_id,
)
from cub.core.plan.models import (
    Plan,
    PlanStage,
    PlanStatus,
    SpecStage,
    StageStatus,
)
from cub.core.plan.architect import (
    ArchitectInputError,
    ArchitectQuestion,
    ArchitectResult,
    ArchitectStage,
    ArchitectStageError,
    Component,
    ImplementationPhase,
    TechStackChoice,
    TechnicalRisk,
    run_architect,
)
from cub.core.plan.orient import (
    OrientInputError,
    OrientQuestion,
    OrientResult,
    OrientStage,
    OrientStageError,
    run_orient,
)

__all__ = [
    # Models
    "Plan",
    "PlanStage",
    "PlanStatus",
    "SpecStage",
    "StageStatus",
    # Context
    "PlanContext",
    "PlanContextError",
    "PlanExistsError",
    "SpecNotFoundError",
    "OrientDepth",
    # Orient Stage
    "OrientStage",
    "OrientResult",
    "OrientQuestion",
    "OrientStageError",
    "OrientInputError",
    "run_orient",
    # Architect Stage
    "ArchitectStage",
    "ArchitectResult",
    "ArchitectQuestion",
    "ArchitectStageError",
    "ArchitectInputError",
    "TechStackChoice",
    "Component",
    "ImplementationPhase",
    "TechnicalRisk",
    "run_architect",
    # ID utilities
    "generate_epic_id",
    "generate_task_id",
    "generate_subtask_id",
    "is_valid_epic_id",
    "is_valid_task_id",
    "is_valid_subtask_id",
    "parse_id",
    "get_parent_id",
]
