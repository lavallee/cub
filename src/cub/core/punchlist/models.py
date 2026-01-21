"""
Data models for punchlist processing.

Defines the core dataclasses used throughout the punchlist pipeline:
parsing, hydration, and task creation.
"""

from dataclasses import dataclass, field
from pathlib import Path

from cub.core.tasks.models import Task


@dataclass
class PunchlistItem:
    """
    A raw item parsed from a punchlist file.

    Represents the unprocessed text content of a single item
    separated by em-dash delimiters.
    """

    raw_text: str
    """The raw text content of the item."""

    index: int
    """Zero-based index of the item in the punchlist."""


@dataclass
class HydratedItem:
    """
    A punchlist item after hydration with Claude.

    Contains the AI-generated title and description that will be
    used to create the actual task.
    """

    title: str
    """Concise task title (50 chars max, imperative mood)."""

    description: str
    """Detailed description with context and acceptance criteria."""

    raw_item: PunchlistItem
    """Reference to the original raw item."""


@dataclass
class PunchlistResult:
    """
    Result of processing a punchlist file.

    Contains the created epic and all child tasks, along with
    metadata about the processing.
    """

    epic: Task
    """The created epic task."""

    tasks: list[Task] = field(default_factory=list)
    """List of child tasks created under the epic."""

    source_file: Path | None = None
    """Path to the original punchlist file."""

    @property
    def task_count(self) -> int:
        """Number of tasks created."""
        return len(self.tasks)
