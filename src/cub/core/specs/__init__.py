"""
Cub specs module.

Provides data models and workflow management for specification files.
Specs are Markdown files with YAML frontmatter organized in stage
directories under the specs/ folder.

Spec lifecycle stages:
- RESEARCHING: Initial exploration phase (-ing = active)
- PLANNED: Plan exists, ready to stage (past = at rest)
- STAGED: Tasks in backend, ready to build (past = at rest)
- IMPLEMENTING: Active work happening (-ing = active)
- RELEASED: Shipped, available for drift audit (past = at rest)

Stage directories:
- specs/researching/
- specs/planned/
- specs/staged/
- specs/implementing/
- specs/released/
"""

from cub.core.specs.lifecycle import (
    SpecLifecycleError,
    get_spec_lifecycle_stage_from_plan,
    move_spec_to_implementing,
    move_spec_to_staged,
    move_specs_to_released,
)
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
    # Lifecycle
    "SpecLifecycleError",
    "get_spec_lifecycle_stage_from_plan",
    "move_spec_to_implementing",
    "move_spec_to_staged",
    "move_specs_to_released",
]
