"""
ID parser and validator for hierarchical task identification.

This module provides utilities to parse string IDs back into typed ID models
and validate ID formats. It handles the full hierarchy:
- Spec: cub-054
- Plan: cub-054A
- Epic: cub-054A-0
- Task: cub-054A-0.1
- Standalone: cub-s017

It also detects legacy random IDs (e.g., cub-k7m) for backward compatibility.

Public API:
    - parse_id: Parse string ID into typed model
    - validate_id: Check if string is valid ID format
    - get_id_type: Determine ID type without full parsing
    - get_parent_id: Extract parent ID from hierarchical ID
"""

import re
from typing import Literal

from cub.core.ids.models import EpicId, PlanId, SpecId, StandaloneTaskId, TaskId

# Type alias for ID type literals
IdType = Literal["spec", "plan", "epic", "task", "standalone"]

# Regex patterns for each ID type
# Pattern breakdown:
# - Spec: {project}-{number:03d} → cub-054
# - Plan: {spec_id}{letter} → cub-054A
# - Epic: {plan_id}-{char} → cub-054A-0
# - Task: {epic_id}.{number} → cub-054A-0.1
# - Standalone: {project}-s{number:03d} → cub-s017
# - Legacy: {project}-{random_chars} → cub-k7m (3+ lowercase letters)

# Component patterns
_PROJECT_PATTERN = r"[a-z][a-z0-9-]*"
# Spec number: at least 3 digits (zero-padded) or 4+ digits (large numbers)
_SPEC_NUMBER_PATTERN = r"(?:\d{3,})"
_PLAN_LETTER_PATTERN = r"[A-Za-z0-9]"
_EPIC_CHAR_PATTERN = r"[0-9a-zA-Z]"
_TASK_NUMBER_PATTERN = r"\d+"
# Standalone number: at least 3 digits (zero-padded) or 4+ digits (large numbers)
_STANDALONE_NUMBER_PATTERN = r"(?:\d{3,})"

# Full ID patterns (anchored with ^ and $ to match entire string)
# Note: Order matters when matching - check most specific patterns first
_SPEC_REGEX = re.compile(
    rf"^({_PROJECT_PATTERN})-({_SPEC_NUMBER_PATTERN})$"
)
_PLAN_REGEX = re.compile(
    rf"^({_PROJECT_PATTERN})-({_SPEC_NUMBER_PATTERN})({_PLAN_LETTER_PATTERN})$"
)
_EPIC_REGEX = re.compile(
    rf"^({_PROJECT_PATTERN})-({_SPEC_NUMBER_PATTERN})({_PLAN_LETTER_PATTERN})-({_EPIC_CHAR_PATTERN})$"
)
_TASK_REGEX = re.compile(
    rf"^({_PROJECT_PATTERN})-({_SPEC_NUMBER_PATTERN})({_PLAN_LETTER_PATTERN})-({_EPIC_CHAR_PATTERN})\.({_TASK_NUMBER_PATTERN})$"
)
_STANDALONE_REGEX = re.compile(
    rf"^({_PROJECT_PATTERN})-s({_STANDALONE_NUMBER_PATTERN})$"
)
# Legacy random ID: project-{3+ lowercase alphanumeric, NOT all digits, NOT s+digits}
# Legacy IDs were random lowercase strings like "k7m", "abc", "x1y2"
# Requirements:
#   - Project name must not end in a digit (to avoid matching hierarchical IDs)
#   - At least 3 chars after the dash
#   - Only lowercase letters and digits
#   - Contains at least one lowercase letter (not all digits)
#   - Does NOT match pattern s+digits (standalone format)
# Pattern: ([a-z](?:[a-z0-9-]*[a-z])?) matches project ending in letter or single letter
_LEGACY_REGEX = re.compile(
    r"^([a-z](?:[a-z0-9-]*[a-z])?)-(?!s\d+$)(?=.*[a-z])[a-z0-9]{3,}$"
)


def validate_id(id_str: str) -> bool:
    """
    Check if a string is a valid ID format.

    This is a fast check that only validates the format without constructing
    the full typed model. It returns True for any valid ID type including
    legacy random IDs.

    Args:
        id_str: The ID string to validate

    Returns:
        True if the string matches any valid ID format, False otherwise

    Examples:
        >>> validate_id("cub-054")
        True
        >>> validate_id("cub-054A-0.1")
        True
        >>> validate_id("cub-s017")
        True
        >>> validate_id("cub-k7m")  # Legacy random ID
        True
        >>> validate_id("invalid-id!")
        False
    """
    return (
        _SPEC_REGEX.match(id_str) is not None
        or _PLAN_REGEX.match(id_str) is not None
        or _EPIC_REGEX.match(id_str) is not None
        or _TASK_REGEX.match(id_str) is not None
        or _STANDALONE_REGEX.match(id_str) is not None
        or _LEGACY_REGEX.match(id_str) is not None
    )


def get_id_type(id_str: str) -> IdType | None:
    """
    Determine the type of an ID without full parsing.

    This is faster than parse_id when you only need to know the type.
    Returns None for legacy random IDs and invalid formats.

    Args:
        id_str: The ID string to check

    Returns:
        The ID type, or None if not a valid hierarchical ID

    Examples:
        >>> get_id_type("cub-054")
        'spec'
        >>> get_id_type("cub-054A")
        'plan'
        >>> get_id_type("cub-054A-0")
        'epic'
        >>> get_id_type("cub-054A-0.1")
        'task'
        >>> get_id_type("cub-s017")
        'standalone'
        >>> get_id_type("cub-k7m")  # Legacy random ID
        None
    """
    # Check in order from most specific to least specific
    # Match the logic in parse_id for consistency
    if _TASK_REGEX.match(id_str):
        return "task"
    elif _EPIC_REGEX.match(id_str):
        return "epic"
    elif _PLAN_REGEX.match(id_str):
        # Plan takes precedence over spec (even when both match)
        # This allows full range of plan letters including digits
        return "plan"
    elif _STANDALONE_REGEX.match(id_str):
        return "standalone"
    elif _SPEC_REGEX.match(id_str):
        return "spec"
    else:
        return None


def get_parent_id(id_str: str) -> str | None:
    """
    Extract the parent ID from a hierarchical ID.

    Returns the parent ID in the hierarchy, or None if the ID has no parent
    (spec, standalone, or invalid).

    Args:
        id_str: The ID string to extract parent from

    Returns:
        The parent ID string, or None if no parent exists

    Examples:
        >>> get_parent_id("cub-054A-0.1")
        'cub-054A-0'
        >>> get_parent_id("cub-054A-0")
        'cub-054A'
        >>> get_parent_id("cub-054A")
        'cub-054'
        >>> get_parent_id("cub-054")
        None
        >>> get_parent_id("cub-s017")
        None
    """
    id_type = get_id_type(id_str)

    if id_type == "task":
        # Parent is epic: remove .{number}
        match = _TASK_REGEX.match(id_str)
        if match:
            project, spec_num, plan_letter, epic_char, _ = match.groups()
            return f"{project}-{spec_num}{plan_letter}-{epic_char}"

    elif id_type == "epic":
        # Parent is plan: remove -{char}
        match = _EPIC_REGEX.match(id_str)
        if match:
            project, spec_num, plan_letter, _ = match.groups()
            return f"{project}-{spec_num}{plan_letter}"

    elif id_type == "plan":
        # Parent is spec: remove {letter}
        match = _PLAN_REGEX.match(id_str)
        if match:
            project, spec_num, _ = match.groups()
            return f"{project}-{spec_num}"

    # Spec and standalone have no parent
    return None


def parse_id(
    id_str: str,
) -> SpecId | PlanId | EpicId | TaskId | StandaloneTaskId:
    """
    Parse a string ID into its typed model.

    This function converts string IDs back into the appropriate Pydantic model
    with full parent chain composition. It raises ValueError for invalid formats
    and legacy random IDs.

    Args:
        id_str: The ID string to parse

    Returns:
        The typed ID model with full parent chain

    Raises:
        ValueError: If the ID format is invalid or is a legacy random ID

    Examples:
        >>> id_obj = parse_id("cub-054")
        >>> isinstance(id_obj, SpecId)
        True
        >>> str(id_obj)
        'cub-054'

        >>> task_id = parse_id("cub-054A-0.1")
        >>> isinstance(task_id, TaskId)
        True
        >>> str(task_id)
        'cub-054A-0.1'
        >>> str(task_id.epic.plan.spec)
        'cub-054'

        >>> parse_id("invalid-id!")
        Traceback (most recent call last):
            ...
        ValueError: Invalid ID format: invalid-id!

        >>> parse_id("cub-k7m")  # Legacy random ID
        Traceback (most recent call last):
            ...
        ValueError: Legacy random ID format detected: cub-k7m. Cannot parse into typed model.
    """
    # Try to match each ID type from most specific to least specific
    # Order matters for ambiguous cases:
    # - task/epic/plan have more structure, so check them before spec
    # - standalone has unique prefix (s), check before spec
    # - spec is most general (just digits), check last among hierarchical

    # Task ID: cub-054A-0.1
    match = _TASK_REGEX.match(id_str)
    if match:
        project, spec_num, plan_letter, epic_char, task_num = match.groups()
        spec = SpecId(project=project, number=int(spec_num))
        plan = PlanId(spec=spec, letter=plan_letter)
        epic = EpicId(plan=plan, char=epic_char)
        task = TaskId(epic=epic, number=int(task_num))
        return task

    # Epic ID: cub-054A-0
    match = _EPIC_REGEX.match(id_str)
    if match:
        project, spec_num, plan_letter, epic_char = match.groups()
        spec = SpecId(project=project, number=int(spec_num))
        plan = PlanId(spec=spec, letter=plan_letter)
        epic = EpicId(plan=plan, char=epic_char)
        return epic

    # Plan ID: cub-054A  OR  Spec ID: cub-054
    # These patterns can both match IDs ending in digits (e.g., cub-1000)
    # Resolution strategy: prefer plan if it results in a properly formatted spec number
    plan_match = _PLAN_REGEX.match(id_str)
    spec_match = _SPEC_REGEX.match(id_str)

    if plan_match and spec_match:
        # Both match - this happens when ID ends in digits
        # E.g., cub-1000 could be spec(1000) or plan(100, '0')
        # E.g., cub-0549 could be spec(549) or plan(054, '9')
        #
        # Prefer plan interpretation to allow full range of plan letters (0-9)
        # This means cub-0549 → plan(054, 9) instead of spec(549)
        # If user wants spec(549), they should write cub-549 not cub-0549
        project, spec_num, plan_letter = plan_match.groups()
        spec = SpecId(project=project, number=int(spec_num))
        plan = PlanId(spec=spec, letter=plan_letter)
        return plan
    elif plan_match:
        # Only plan matches (e.g., cub-054A where A is a letter)
        project, spec_num, plan_letter = plan_match.groups()
        spec = SpecId(project=project, number=int(spec_num))
        plan = PlanId(spec=spec, letter=plan_letter)
        return plan
    elif spec_match:
        # Only spec matches
        project, spec_num = spec_match.groups()
        spec = SpecId(project=project, number=int(spec_num))
        return spec

    # Standalone Task ID: cub-s017
    match = _STANDALONE_REGEX.match(id_str)
    if match:
        project, standalone_num = match.groups()
        standalone = StandaloneTaskId(project=project, number=int(standalone_num))
        return standalone

    # Check for legacy random ID after all hierarchical patterns
    if _LEGACY_REGEX.match(id_str):
        raise ValueError(
            f"Legacy random ID format detected: {id_str}. "
            "Cannot parse into typed model."
        )

    # No match found
    raise ValueError(f"Invalid ID format: {id_str}")
