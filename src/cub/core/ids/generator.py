"""
ID generator with counter integration.

This module provides the primary API for creating new hierarchical IDs.
It combines counter allocation from the sync branch with the typed ID models
to produce collision-free identifiers.

Generator functions:
    - generate_spec_id: Allocate counter and create spec ID
    - generate_plan_id: Create plan ID from spec (letter explicit)
    - generate_epic_id: Create epic ID from plan (char explicit)
    - generate_task_id: Create task ID from epic (number explicit)
    - generate_standalone_id: Allocate counter and create standalone task ID

Helper functions:
    - next_plan_letter: Auto-select next available plan letter
    - next_epic_char: Auto-select next available epic char

Example:
    >>> from cub.core.sync import SyncService
    >>> from cub.core.ids import generate_spec_id, generate_plan_id
    >>> sync = SyncService()
    >>> spec = generate_spec_id("cub", sync)
    >>> str(spec)
    'cub-054'
    >>> plan = generate_plan_id(spec, "A")
    >>> str(plan)
    'cub-054A'
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cub.core.ids.counters import allocate_spec_number, allocate_standalone_number
from cub.core.ids.models import EpicId, PlanId, SpecId, StandaloneTaskId, TaskId

if TYPE_CHECKING:
    from cub.core.sync.service import SyncService


def generate_spec_id(project: str, sync_service: SyncService) -> SpecId:
    """
    Generate a new spec ID by allocating a counter from the sync branch.

    This atomically reads the current counter, increments it, and commits
    the updated state to the sync branch, then constructs a SpecId.

    Args:
        project: The project name (e.g., "cub")
        sync_service: The SyncService instance for counter allocation

    Returns:
        A new SpecId with allocated number

    Raises:
        RuntimeError: If sync branch is not initialized
        CounterAllocationError: If allocation fails after retries

    Example:
        >>> sync = SyncService()
        >>> spec = generate_spec_id("cub", sync)
        >>> str(spec)
        'cub-054'
    """
    number = allocate_spec_number(sync_service)
    return SpecId(project=project, number=number)


def generate_plan_id(spec: SpecId, letter: str) -> PlanId:
    """
    Generate a plan ID from a spec ID with explicit letter.

    The letter distinguishes multiple plans for the same spec.
    Valid letters: A-Z, a-z, 0-9 (uppercase letters first in sequence).

    Args:
        spec: The parent SpecId
        letter: Single character A-Z, a-z, or 0-9

    Returns:
        A new PlanId

    Raises:
        ValueError: If letter is not a single character or not in valid range

    Example:
        >>> spec = SpecId(project="cub", number=54)
        >>> plan = generate_plan_id(spec, "A")
        >>> str(plan)
        'cub-054A'
    """
    return PlanId(spec=spec, letter=letter)


def generate_epic_id(plan: PlanId, char: str) -> EpicId:
    """
    Generate an epic ID from a plan ID with explicit char.

    The char distinguishes multiple epics within the same plan.
    Valid chars: 0-9, a-z, A-Z (numbers first in sequence).

    Args:
        plan: The parent PlanId
        char: Single character 0-9, a-z, or A-Z

    Returns:
        A new EpicId

    Raises:
        ValueError: If char is not a single character or not in valid range

    Example:
        >>> spec = SpecId(project="cub", number=54)
        >>> plan = PlanId(spec=spec, letter="A")
        >>> epic = generate_epic_id(plan, "0")
        >>> str(epic)
        'cub-054A-0'
    """
    return EpicId(plan=plan, char=char)


def generate_task_id(epic: EpicId, number: int) -> TaskId:
    """
    Generate a task ID from an epic ID with explicit number.

    The number is sequential within the epic (starts at 1).

    Args:
        epic: The parent EpicId
        number: Task number (must be >= 1)

    Returns:
        A new TaskId

    Raises:
        ValueError: If number is less than 1

    Example:
        >>> spec = SpecId(project="cub", number=54)
        >>> plan = PlanId(spec=spec, letter="A")
        >>> epic = EpicId(plan=plan, char="0")
        >>> task = generate_task_id(epic, 1)
        >>> str(task)
        'cub-054A-0.1'
    """
    return TaskId(epic=epic, number=number)


def generate_standalone_id(project: str, sync_service: SyncService) -> StandaloneTaskId:
    """
    Generate a new standalone task ID by allocating a counter from the sync branch.

    Standalone tasks are not part of the spec/plan/epic hierarchy.
    They use a separate counter to avoid collisions.

    Args:
        project: The project name (e.g., "cub")
        sync_service: The SyncService instance for counter allocation

    Returns:
        A new StandaloneTaskId with allocated number

    Raises:
        RuntimeError: If sync branch is not initialized
        CounterAllocationError: If allocation fails after retries

    Example:
        >>> sync = SyncService()
        >>> standalone = generate_standalone_id("cub", sync)
        >>> str(standalone)
        'cub-s017'
    """
    number = allocate_standalone_number(sync_service)
    return StandaloneTaskId(project=project, number=number)


# Sequence constants for auto-selection helpers
# Plan letters: A-Z, a-z, 0-9 (uppercase first)
_PLAN_LETTER_SEQUENCE = (
    list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    + list("abcdefghijklmnopqrstuvwxyz")
    + list("0123456789")
)

# Epic chars: 0-9, a-z, A-Z (numbers first)
_EPIC_CHAR_SEQUENCE = (
    list("0123456789")
    + list("abcdefghijklmnopqrstuvwxyz")
    + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
)


def next_plan_letter(existing: list[str]) -> str:
    """
    Auto-select the next available plan letter.

    Plan letter sequence: A-Z, a-z, 0-9 (62 total options).
    Returns the first letter in the sequence that's not in the existing list.

    Args:
        existing: List of already-used plan letters

    Returns:
        The next available letter in sequence

    Raises:
        ValueError: If all 62 letters are exhausted

    Example:
        >>> next_plan_letter([])
        'A'
        >>> next_plan_letter(["A", "B"])
        'C'
        >>> next_plan_letter(["A", "B", "C"])
        'D'
        >>> next_plan_letter(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        'a'
    """
    existing_set = set(existing)
    for letter in _PLAN_LETTER_SEQUENCE:
        if letter not in existing_set:
            return letter

    raise ValueError(
        "All plan letters exhausted (62 letters used). "
        "Cannot create more plans for this spec."
    )


def next_epic_char(existing: list[str]) -> str:
    """
    Auto-select the next available epic char.

    Epic char sequence: 0-9, a-z, A-Z (62 total options).
    Returns the first char in the sequence that's not in the existing list.

    Args:
        existing: List of already-used epic chars

    Returns:
        The next available char in sequence

    Raises:
        ValueError: If all 62 chars are exhausted

    Example:
        >>> next_epic_char([])
        '0'
        >>> next_epic_char(["0", "1"])
        '2'
        >>> next_epic_char(list("0123456789"))
        'a'
        >>> next_epic_char(list("0123456789abcdefghijklmnopqrstuvwxyz"))
        'A'
    """
    existing_set = set(existing)
    for char in _EPIC_CHAR_SEQUENCE:
        if char not in existing_set:
            return char

    raise ValueError(
        "All epic chars exhausted (62 chars used). "
        "Cannot create more epics for this plan."
    )
