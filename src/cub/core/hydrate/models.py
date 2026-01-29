"""
Data models for the hydration engine.

Defines context-neutral models for hydration input, output, and status.
"""

from dataclasses import dataclass, field
from enum import Enum


class HydrationStatus(str, Enum):
    """Status of a hydration result."""

    SUCCESS = "success"
    FALLBACK = "fallback"


@dataclass
class HydrationResult:
    """
    Result of hydrating a single text item.

    Contains the structured output from Claude or fallback extraction.
    """

    title: str
    """Concise task title (imperative mood)."""

    description: str
    """One-line description or context paragraph."""

    context: str
    """Detailed context paragraph."""

    implementation_steps: list[str] = field(default_factory=list)
    """Ordered implementation steps."""

    acceptance_criteria: list[str] = field(default_factory=list)
    """Acceptance criteria checklist items."""

    status: HydrationStatus = HydrationStatus.SUCCESS
    """Whether hydration used AI or fell back to simple extraction."""

    source_text: str = ""
    """The original unstructured text that was hydrated."""
