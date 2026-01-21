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

from cub.core.plan.architect import (
    ArchitectInputError,
    ArchitectQuestion,
    ArchitectResult,
    ArchitectStage,
    ArchitectStageError,
    Component,
    ImplementationPhase,
    TechnicalRisk,
    TechStackChoice,
    run_architect,
)
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
from cub.core.plan.itemize import (
    Epic,
    ItemizeInputError,
    ItemizeResult,
    ItemizeStage,
    ItemizeStageError,
    Task,
    run_itemize,
)
from cub.core.plan.models import (
    Plan,
    PlanStage,
    PlanStatus,
    SpecStage,
    StageStatus,
)
from cub.core.plan.orient import (
    OrientInputError,
    OrientQuestion,
    OrientResult,
    OrientStage,
    OrientStageError,
    run_orient,
)
from cub.core.plan.parser import (
    ParsedEpic,
    ParsedPlan,
    ParsedTask,
    PlanFileNotFoundError,
    PlanFormatError,
    PlanMetadata,
    PlanParseError,
    convert_to_task_models,
    parse_itemized_plan,
    parse_itemized_plan_content,
)
from cub.core.plan.pipeline import (
    PipelineConfig,
    PipelineConfigError,
    PipelineError,
    PipelineResult,
    PipelineStageError,
    PlanPipeline,
    ProgressCallback,
    StageResult,
    continue_pipeline,
    run_pipeline,
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
    # Itemize Stage
    "ItemizeStage",
    "ItemizeResult",
    "ItemizeStageError",
    "ItemizeInputError",
    "Epic",
    "Task",
    "run_itemize",
    # Pipeline
    "PlanPipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineError",
    "PipelineConfigError",
    "PipelineStageError",
    "StageResult",
    "ProgressCallback",
    "run_pipeline",
    "continue_pipeline",
    # ID utilities
    "generate_epic_id",
    "generate_task_id",
    "generate_subtask_id",
    "is_valid_epic_id",
    "is_valid_task_id",
    "is_valid_subtask_id",
    "parse_id",
    "get_parent_id",
    # Parser
    "ParsedEpic",
    "ParsedTask",
    "ParsedPlan",
    "PlanMetadata",
    "PlanParseError",
    "PlanFileNotFoundError",
    "PlanFormatError",
    "parse_itemized_plan",
    "parse_itemized_plan_content",
    "convert_to_task_models",
]
