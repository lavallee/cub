"""
ID models for hierarchical task identification.

These Pydantic models provide type-safe representations of the hierarchical
ID system: spec → plan → epic → task, plus standalone tasks.

ID Format Examples:
    - Spec:       cub-054
    - Plan:       cub-054A
    - Epic:       cub-054A-0
    - Task:       cub-054A-0.1
    - Standalone: cub-s017

The hierarchy enables full traceability from any task back to its originating
spec while preventing collisions via counter-based allocation on the sync branch.
"""

import re

from pydantic import BaseModel, ConfigDict, field_validator


class SpecId(BaseModel):
    """
    Spec ID: {project}-{number:03d} → cub-054

    Represents a specification document. The number is allocated from
    a global counter on the sync branch.
    """

    project: str
    number: int

    model_config = ConfigDict(frozen=True)

    @field_validator("number")
    @classmethod
    def validate_number(cls, v: int) -> int:
        """Validate that number is non-negative."""
        if v < 0:
            raise ValueError("Spec number must be non-negative")
        return v

    def __str__(self) -> str:
        """Format as {project}-{number:03d}"""
        return f"{self.project}-{self.number:03d}"


class PlanId(BaseModel):
    """
    Plan ID: {spec_id}{letter} → cub-054A

    Represents an implementation plan for a spec. The letter distinguishes
    multiple plans for the same spec.

    Letter Sequence: A-Z, a-z, 0-9 (uppercase first, 62 options total)
    """

    spec: SpecId
    letter: str

    model_config = ConfigDict(frozen=True)

    @field_validator("letter")
    @classmethod
    def validate_letter(cls, v: str) -> str:
        """Validate letter is A-Z, a-z, or 0-9."""
        if not re.match(r"^[A-Za-z0-9]$", v):
            raise ValueError(
                "Plan letter must be a single character: A-Z, a-z, or 0-9"
            )
        return v

    def __str__(self) -> str:
        """Format as {spec_id}{letter}"""
        return f"{self.spec}{self.letter}"


class EpicId(BaseModel):
    """
    Epic ID: {plan_id}-{char} → cub-054A-0

    Represents an epic (group of related tasks) within a plan.
    The char distinguishes multiple epics in the same plan.

    Char Sequence: 0-9, a-z, A-Z (numbers first, 62 options total)
    """

    plan: PlanId
    char: str

    model_config = ConfigDict(frozen=True)

    @field_validator("char")
    @classmethod
    def validate_char(cls, v: str) -> str:
        """Validate char is 0-9, a-z, or A-Z."""
        if not re.match(r"^[0-9a-zA-Z]$", v):
            raise ValueError(
                "Epic char must be a single character: 0-9, a-z, or A-Z"
            )
        return v

    def __str__(self) -> str:
        """Format as {plan_id}-{char}"""
        return f"{self.plan}-{self.char}"


class TaskId(BaseModel):
    """
    Task ID: {epic_id}.{number} → cub-054A-0.1

    Represents a specific task within an epic. The number is sequential
    within the epic.
    """

    epic: EpicId
    number: int

    model_config = ConfigDict(frozen=True)

    @field_validator("number")
    @classmethod
    def validate_number(cls, v: int) -> int:
        """Validate that number is positive."""
        if v < 1:
            raise ValueError("Task number must be positive (starts at 1)")
        return v

    def __str__(self) -> str:
        """Format as {epic_id}.{number}"""
        return f"{self.epic}.{self.number}"


class StandaloneTaskId(BaseModel):
    """
    Standalone task ID: {project}-s{number:03d} → cub-s017

    Represents a task that is not part of a spec/plan/epic hierarchy.
    Used for ad-hoc work that doesn't fit the structured planning process.

    The number is allocated from a separate global counter on the sync branch.
    """

    project: str
    number: int

    model_config = ConfigDict(frozen=True)

    @field_validator("number")
    @classmethod
    def validate_number(cls, v: int) -> int:
        """Validate that number is non-negative."""
        if v < 0:
            raise ValueError("Standalone task number must be non-negative")
        return v

    def __str__(self) -> str:
        """Format as {project}-s{number:03d}"""
        return f"{self.project}-s{self.number:03d}"
