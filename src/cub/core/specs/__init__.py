"""
Cub specs module.

Provides data models and workflow management for specification files.
Specs are Markdown files with YAML frontmatter organized in stage
directories under the specs/ folder.

Spec lifecycle stages:
- RESEARCHING: Initial exploration phase
- PLANNED: Ready to implement
- COMPLETED: Implementation finished

Stage directories:
- specs/researching/
- specs/planned/
- specs/completed/
"""

from cub.core.specs.models import (
    Readiness,
    Spec,
    SpecComplexity,
    SpecPriority,
    SpecStatus,
    Stage,
)
from cub.core.specs.workflow import (
    InvalidStageTransitionError,
    SpecMoveError,
    SpecNotFoundError,
    SpecWorkflow,
    SpecWorkflowError,
)

__all__ = [
    # Models
    "Readiness",
    "Spec",
    "SpecComplexity",
    "SpecPriority",
    "SpecStatus",
    "Stage",
    # Workflow
    "InvalidStageTransitionError",
    "SpecMoveError",
    "SpecNotFoundError",
    "SpecWorkflow",
    "SpecWorkflowError",
]
