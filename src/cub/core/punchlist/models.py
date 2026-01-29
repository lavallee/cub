"""
Data models for punchlist processing.

Defines the core dataclasses used throughout the punchlist pipeline:
parsing, hydration, and plan generation.
"""

from dataclasses import dataclass, field
from pathlib import Path

from cub.core.hydrate.models import HydrationResult


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


# Keep HydratedItem as a thin alias for backwards compatibility
HydratedItem = HydrationResult


@dataclass
class PunchlistResult:
    """
    Result of processing a punchlist file.

    Contains the hydration results and output file path.
    """

    epic_title: str
    """Title of the generated epic."""

    items: list[HydrationResult] = field(default_factory=list)
    """List of hydrated items."""

    source_file: Path | None = None
    """Path to the original punchlist file."""

    output_file: Path | None = None
    """Path to the generated itemized-plan.md file."""

    @property
    def task_count(self) -> int:
        """Number of tasks generated."""
        return len(self.items)
