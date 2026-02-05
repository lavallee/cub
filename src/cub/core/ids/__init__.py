"""
ID system for hierarchical task identification.

This package provides type-safe ID models and utilities for the hierarchical
ID system: spec → plan → epic → task, plus standalone tasks.

Public API:
    Models:
        - SpecId: Spec ID model (cub-054)
        - PlanId: Plan ID model (cub-054A)
        - EpicId: Epic ID model (cub-054A-0)
        - TaskId: Task ID model (cub-054A-0.1)
        - StandaloneTaskId: Standalone task ID model (cub-s017)

    Parser functions:
        - parse_id: Parse string ID into typed model
        - validate_id: Check if string is valid ID format
        - get_id_type: Determine ID type without full parsing
        - get_parent_id: Extract parent ID from hierarchical ID

    Counter functions:
        - read_counters: Read current counter state from sync branch
        - allocate_spec_number: Allocate next spec number with optimistic locking
        - allocate_standalone_number: Allocate next standalone number
        - CounterAllocationError: Exception for allocation failures

    Generator functions:
        - generate_spec_id: Generate new spec ID with counter allocation
        - generate_plan_id: Generate new plan ID from spec
        - generate_epic_id: Generate new epic ID from plan
        - generate_task_id: Generate new task ID from epic
        - generate_standalone_id: Generate new standalone task ID with counter allocation
        - next_plan_letter: Auto-select next available plan letter
        - next_epic_char: Auto-select next available epic char

Example:
    >>> from cub.core.ids import SpecId, PlanId, EpicId, TaskId, parse_id
    >>> spec = SpecId(project="cub", number=54)
    >>> str(spec)
    'cub-054'
    >>> plan = PlanId(spec=spec, letter="A")
    >>> str(plan)
    'cub-054A'
    >>> epic = EpicId(plan=plan, char="0")
    >>> str(epic)
    'cub-054A-0'
    >>> task = TaskId(epic=epic, number=1)
    >>> str(task)
    'cub-054A-0.1'
    >>> parsed = parse_id("cub-054A-0.1")
    >>> str(parsed)
    'cub-054A-0.1'
"""

from cub.core.ids.counters import (
    CounterAllocationError,
    allocate_spec_number,
    allocate_standalone_number,
    read_counters,
)
from cub.core.ids.generator import (
    generate_epic_id,
    generate_plan_id,
    generate_spec_id,
    generate_standalone_id,
    generate_task_id,
    next_epic_char,
    next_plan_letter,
)
from cub.core.ids.models import EpicId, PlanId, SpecId, StandaloneTaskId, TaskId
from cub.core.ids.parser import get_id_type, get_parent_id, parse_id, validate_id

__all__ = [
    # Models
    "SpecId",
    "PlanId",
    "EpicId",
    "TaskId",
    "StandaloneTaskId",
    # Parser functions
    "parse_id",
    "validate_id",
    "get_id_type",
    "get_parent_id",
    # Counter functions
    "read_counters",
    "allocate_spec_number",
    "allocate_standalone_number",
    "CounterAllocationError",
    # Generator functions
    "generate_spec_id",
    "generate_plan_id",
    "generate_epic_id",
    "generate_task_id",
    "generate_standalone_id",
    "next_plan_letter",
    "next_epic_char",
]
