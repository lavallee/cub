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
]
