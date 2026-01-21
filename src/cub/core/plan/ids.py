"""
ID generation utilities for beads-compatible plan IDs.

Generates hierarchical IDs for epics, tasks, and subtasks that are compatible
with the beads issue tracking system.

ID Formats:
    - Epic: {project}-{random 3 chars} (e.g., cub-k7m)
    - Task: {epic_id}.{number} (e.g., cub-k7m.1)
    - Subtask: {task_id}.{number} (e.g., cub-k7m.1.1)

Example:
    >>> epic_id = generate_epic_id("cub")
    >>> epic_id  # Something like 'cub-k7m'
    >>> task_id = generate_task_id(epic_id, 1)
    >>> task_id  # 'cub-k7m.1'
    >>> subtask_id = generate_subtask_id(task_id, 1)
    >>> subtask_id  # 'cub-k7m.1.1'
"""

import re
import secrets
import string

# Characters for random ID suffix generation (lowercase alphanumeric)
ID_CHARS = string.ascii_lowercase + string.digits
EPIC_SUFFIX_LENGTH = 3
MAX_GENERATION_ATTEMPTS = 100

# Regex patterns for ID validation
EPIC_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*-[a-z0-9]{3}$")
TASK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*-[a-z0-9]{3}\.\d+$")
SUBTASK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*-[a-z0-9]{3}\.\d+\.\d+$")


def generate_epic_id(project: str, existing_ids: set[str] | None = None) -> str:
    """
    Generate a beads-compatible epic ID with random suffix.

    The format is: {project}-{random 3 chars}
    For example: cub-k7m, myapp-a2x, proj-9bz

    Args:
        project: Project identifier (e.g., 'cub'). Must be lowercase alphanumeric
            with optional hyphens, starting with a letter.
        existing_ids: Optional set of existing IDs to avoid collisions.
            If provided, will retry generation until a unique ID is found.

    Returns:
        A unique epic ID string.

    Raises:
        ValueError: If project is invalid (empty, wrong format).
        RuntimeError: If unable to generate unique ID after max attempts
            (only when existing_ids is provided and heavily populated).

    Example:
        >>> epic_id = generate_epic_id("cub")
        >>> epic_id.startswith("cub-")
        True
        >>> len(epic_id)
        7

        >>> existing = {"cub-abc", "cub-def"}
        >>> new_id = generate_epic_id("cub", existing)
        >>> new_id not in existing
        True
    """
    # Validate project
    if not project:
        raise ValueError("Project cannot be empty")

    project_pattern = re.compile(r"^[a-z][a-z0-9-]*$")
    if not project_pattern.match(project):
        raise ValueError(
            f"Invalid project identifier: {project!r}. "
            "Must be lowercase alphanumeric with optional hyphens, starting with a letter."
        )

    for _ in range(MAX_GENERATION_ATTEMPTS):
        suffix = "".join(secrets.choice(ID_CHARS) for _ in range(EPIC_SUFFIX_LENGTH))
        epic_id = f"{project}-{suffix}"

        if existing_ids is None or epic_id not in existing_ids:
            return epic_id

    raise RuntimeError(
        f"Failed to generate unique epic ID after {MAX_GENERATION_ATTEMPTS} attempts"
    )


def generate_task_id(epic_id: str, task_num: int) -> str:
    """
    Generate a task ID from an epic ID and task number.

    The format is: {epic_id}.{number}
    For example: cub-k7m.1, cub-k7m.2

    Args:
        epic_id: Parent epic ID (e.g., 'cub-k7m').
        task_num: Task number within the epic (1-based, positive integer).

    Returns:
        Task ID string.

    Raises:
        ValueError: If epic_id is invalid or task_num is not positive.

    Example:
        >>> generate_task_id("cub-k7m", 1)
        'cub-k7m.1'
        >>> generate_task_id("cub-k7m", 42)
        'cub-k7m.42'
    """
    if not epic_id:
        raise ValueError("Epic ID cannot be empty")

    if not is_valid_epic_id(epic_id):
        raise ValueError(f"Invalid epic ID format: {epic_id!r}")

    if task_num < 1:
        raise ValueError(f"Task number must be positive, got {task_num}")

    return f"{epic_id}.{task_num}"


def generate_subtask_id(task_id: str, subtask_num: int) -> str:
    """
    Generate a subtask ID from a task ID and subtask number.

    The format is: {task_id}.{number}
    For example: cub-k7m.1.1, cub-k7m.1.2

    Args:
        task_id: Parent task ID (e.g., 'cub-k7m.1').
        subtask_num: Subtask number within the task (1-based, positive integer).

    Returns:
        Subtask ID string.

    Raises:
        ValueError: If task_id is invalid or subtask_num is not positive.

    Example:
        >>> generate_subtask_id("cub-k7m.1", 1)
        'cub-k7m.1.1'
        >>> generate_subtask_id("cub-k7m.1", 3)
        'cub-k7m.1.3'
    """
    if not task_id:
        raise ValueError("Task ID cannot be empty")

    if not is_valid_task_id(task_id):
        raise ValueError(f"Invalid task ID format: {task_id!r}")

    if subtask_num < 1:
        raise ValueError(f"Subtask number must be positive, got {subtask_num}")

    return f"{task_id}.{subtask_num}"


def is_valid_epic_id(epic_id: str) -> bool:
    """
    Check if a string is a valid epic ID.

    Valid format: {project}-{3 alphanumeric chars}
    Examples: cub-k7m, myapp-a2x, proj-9bz

    Args:
        epic_id: String to validate.

    Returns:
        True if valid epic ID format, False otherwise.

    Example:
        >>> is_valid_epic_id("cub-k7m")
        True
        >>> is_valid_epic_id("cub-k7m.1")
        False
        >>> is_valid_epic_id("invalid")
        False
    """
    if not epic_id:
        return False
    return bool(EPIC_ID_PATTERN.match(epic_id))


def is_valid_task_id(task_id: str) -> bool:
    """
    Check if a string is a valid task ID.

    Valid format: {epic_id}.{number}
    Examples: cub-k7m.1, myapp-a2x.42

    Args:
        task_id: String to validate.

    Returns:
        True if valid task ID format, False otherwise.

    Example:
        >>> is_valid_task_id("cub-k7m.1")
        True
        >>> is_valid_task_id("cub-k7m.1.1")
        False
        >>> is_valid_task_id("cub-k7m")
        False
    """
    if not task_id:
        return False
    return bool(TASK_ID_PATTERN.match(task_id))


def is_valid_subtask_id(subtask_id: str) -> bool:
    """
    Check if a string is a valid subtask ID.

    Valid format: {task_id}.{number}
    Examples: cub-k7m.1.1, myapp-a2x.42.3

    Args:
        subtask_id: String to validate.

    Returns:
        True if valid subtask ID format, False otherwise.

    Example:
        >>> is_valid_subtask_id("cub-k7m.1.1")
        True
        >>> is_valid_subtask_id("cub-k7m.1")
        False
        >>> is_valid_subtask_id("cub-k7m")
        False
    """
    if not subtask_id:
        return False
    return bool(SUBTASK_ID_PATTERN.match(subtask_id))


def parse_id(id_str: str) -> tuple[str, list[int]]:
    """
    Parse an ID into its epic component and numeric parts.

    Args:
        id_str: ID string to parse (epic, task, or subtask).

    Returns:
        Tuple of (epic_id, list of numeric parts).
        For epic: ("cub-k7m", [])
        For task: ("cub-k7m", [1])
        For subtask: ("cub-k7m", [1, 1])

    Raises:
        ValueError: If ID format is invalid.

    Example:
        >>> parse_id("cub-k7m")
        ('cub-k7m', [])
        >>> parse_id("cub-k7m.1")
        ('cub-k7m', [1])
        >>> parse_id("cub-k7m.1.3")
        ('cub-k7m', [1, 3])
    """
    if not id_str:
        raise ValueError("ID cannot be empty")

    parts = id_str.split(".")

    # First part should be the epic ID
    epic_id = parts[0]
    if not is_valid_epic_id(epic_id):
        raise ValueError(f"Invalid epic ID component: {epic_id!r}")

    # Remaining parts should be positive integers
    numbers: list[int] = []
    for part in parts[1:]:
        try:
            num = int(part)
            if num < 1:
                raise ValueError(f"ID numbers must be positive, got {num}")
            numbers.append(num)
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid ID component: {part!r}") from e
            raise

    # Validate based on number of parts
    if len(numbers) > 2:
        raise ValueError(f"ID has too many levels: {id_str!r}")

    return epic_id, numbers


def get_parent_id(id_str: str) -> str | None:
    """
    Get the parent ID of a given ID.

    Args:
        id_str: ID string (epic, task, or subtask).

    Returns:
        Parent ID string, or None if id_str is an epic (has no parent).

    Raises:
        ValueError: If ID format is invalid.

    Example:
        >>> get_parent_id("cub-k7m.1.1")
        'cub-k7m.1'
        >>> get_parent_id("cub-k7m.1")
        'cub-k7m'
        >>> get_parent_id("cub-k7m")
        None
    """
    epic_id, numbers = parse_id(id_str)

    if not numbers:
        # Epic has no parent
        return None
    elif len(numbers) == 1:
        # Task's parent is the epic
        return epic_id
    else:
        # Subtask's parent is the task
        return f"{epic_id}.{numbers[0]}"
