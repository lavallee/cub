"""
Task service for consistent task creation across cub.

Provides a unified interface for creating tasks with proper structure,
acceptance criteria, and routing through the appropriate backend.
"""

from dataclasses import dataclass, field
from enum import Enum

from cub.core.tasks.backend import get_backend
from cub.core.tasks.models import Task


class TaskComplexity(str, Enum):
    """Task complexity levels for model selection."""

    LOW = "low"  # Boilerplate, simple changes -> haiku
    MEDIUM = "medium"  # Standard feature work -> sonnet
    HIGH = "high"  # Complex/novel problems -> opus


class TaskDomain(str, Enum):
    """Task domain categories."""

    SETUP = "setup"
    MODEL = "model"
    API = "api"
    UI = "ui"
    LOGIC = "logic"
    TEST = "test"
    DOCS = "docs"
    REFACTOR = "refactor"
    FIX = "fix"


@dataclass
class TaskCreationRequest:
    """
    Structured request for creating a task with all relevant details.

    This ensures tasks are created with consistent structure and proper
    acceptance criteria, regardless of the source (investigate, bootstrap, etc).
    """

    # Required fields
    title: str

    # Content fields
    context: str = ""  # Why this task exists, how it fits the bigger picture
    implementation_steps: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)

    # Metadata
    task_type: str = "task"  # task, feature, bug, epic
    priority: int = 2  # 0-4 (P0-P4)
    labels: list[str] = field(default_factory=list)
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    domain: TaskDomain | None = None

    # Relationships
    depends_on: list[str] = field(default_factory=list)
    parent: str | None = None

    # Additional context
    files_involved: list[str] = field(default_factory=list)
    estimated_duration: str | None = None  # e.g., "15m", "30m", "1h"
    notes: str = ""

    # Source tracking
    source_capture_id: str | None = None  # If created from a capture

    def get_recommended_model(self) -> str:
        """Get recommended AI model based on complexity."""
        return {
            TaskComplexity.LOW: "haiku",
            TaskComplexity.MEDIUM: "sonnet",
            TaskComplexity.HIGH: "opus",
        }[self.complexity]

    def build_description(self) -> str:
        """
        Build a well-structured task description.

        Follows the template from cub:plan for consistency.
        """
        parts: list[str] = []

        # Context section
        if self.context:
            parts.append("## Context\n")
            parts.append(f"{self.context}\n")

        # Implementation hints
        hints: list[str] = []
        hints.append(f"**Recommended Model:** {self.get_recommended_model()}")
        if self.estimated_duration:
            hints.append(f"**Estimated Duration:** {self.estimated_duration}")
        if self.complexity:
            hints.append(f"**Complexity:** {self.complexity.value}")

        if hints:
            parts.append("## Implementation Hints\n")
            parts.append("\n".join(hints))
            parts.append("\n")

        # Implementation steps
        if self.implementation_steps:
            parts.append("## Implementation Steps\n")
            for i, step in enumerate(self.implementation_steps, 1):
                parts.append(f"{i}. {step}")
            parts.append("\n")

        # Acceptance criteria (critical for task completion)
        if self.acceptance_criteria:
            parts.append("## Acceptance Criteria\n")
            for criterion in self.acceptance_criteria:
                parts.append(f"- [ ] {criterion}")
            parts.append("\n")

        # Files involved
        if self.files_involved:
            parts.append("## Files Likely Involved\n")
            for file_path in self.files_involved:
                parts.append(f"- `{file_path}`")
            parts.append("\n")

        # Notes
        if self.notes:
            parts.append("## Notes\n")
            parts.append(f"{self.notes}\n")

        # Source tracking
        if self.source_capture_id:
            parts.append("---\n")
            parts.append(f"*Created from capture: {self.source_capture_id}*\n")

        return "\n".join(parts)

    def build_labels(self) -> list[str]:
        """Build complete label list including derived labels."""
        labels = list(self.labels)

        # Add complexity label
        labels.append(f"complexity:{self.complexity.value}")

        # Add model recommendation label
        labels.append(f"model:{self.get_recommended_model()}")

        # Add domain label if specified
        if self.domain:
            labels.append(self.domain.value)

        return labels


class TaskService:
    """
    Service for creating and managing tasks with consistent structure.

    Routes through the appropriate backend (beads, json) and ensures
    tasks have proper acceptance criteria and structure.
    """

    def __init__(self, backend: str | None = None):
        """
        Initialize the task service.

        Args:
            backend: Backend type ("beads" or "json"). Auto-detects if None.
        """
        self._backend = get_backend(backend)

    def create_task(self, request: TaskCreationRequest) -> Task | None:
        """
        Create a task from a structured request.

        Args:
            request: TaskCreationRequest with all task details

        Returns:
            Created Task object, or None if creation failed
        """
        description = request.build_description()
        labels = request.build_labels()

        try:
            task = self._backend.create_task(
                title=request.title,
                description=description,
                task_type=request.task_type,
                priority=request.priority,
                labels=labels,
                depends_on=request.depends_on if request.depends_on else None,
                parent=request.parent,
            )
            return task
        except Exception as e:
            # Log error but don't crash - task creation failures shouldn't be fatal
            print(f"Warning: Failed to create task '{request.title}': {e}")
            return None

    def create_quick_fix(
        self,
        title: str,
        context: str,
        acceptance_criteria: list[str] | None = None,
        labels: list[str] | None = None,
        source_capture_id: str | None = None,
    ) -> Task | None:
        """
        Create a quick fix task with sensible defaults.

        Quick fixes are low complexity, short duration tasks.
        """
        request = TaskCreationRequest(
            title=title,
            context=context,
            acceptance_criteria=acceptance_criteria or [f"Change is complete: {title}"],
            task_type="task",
            priority=2,
            labels=["quick-fix"] + (labels or []),
            complexity=TaskComplexity.LOW,
            estimated_duration="15m",
            source_capture_id=source_capture_id,
        )
        return self.create_task(request)

    def create_spike(
        self,
        title: str,
        context: str,
        exploration_goals: list[str],
        success_criteria: list[str] | None = None,
        labels: list[str] | None = None,
        source_capture_id: str | None = None,
    ) -> Task | None:
        """
        Create a spike/exploration task.

        Spikes are time-boxed explorations with specific goals.
        """
        # Generate branch name suggestion
        import re

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:30]
        branch_name = f"spike/{slug}"

        implementation_steps = [
            f"Create branch: `git checkout -b {branch_name}`",
            "Time-box exploration (suggested: 2-4 hours)",
            "Document findings in code comments or a SPIKE.md file",
            "Summarize learnings and decide next steps",
        ]

        default_criteria = [
            "Approach validated or invalidated",
            "Key learnings documented",
            "Recommendation for next steps provided",
        ]

        request = TaskCreationRequest(
            title=f"[Spike] {title}",
            context=context,
            implementation_steps=implementation_steps,
            acceptance_criteria=success_criteria or default_criteria,
            task_type="task",
            priority=2,
            labels=["spike"] + (labels or []),
            complexity=TaskComplexity.MEDIUM,
            estimated_duration="2-4h",
            notes="Exploration goals:\n"
            + "\n".join(f"- {goal}" for goal in exploration_goals),
            source_capture_id=source_capture_id,
        )
        return self.create_task(request)

    def create_batched_task(
        self,
        title: str,
        items: list[tuple[str, str]],  # List of (item_title, item_description)
        labels: list[str] | None = None,
    ) -> Task | None:
        """
        Create a batched task combining multiple items.

        Used for batching quick fixes or similar small tasks.
        """
        context = f"This task batches {len(items)} related items for efficiency."

        steps = [f"Complete: {item_title}" for item_title, _ in items]
        criteria = [f"{item_title} is done" for item_title, _ in items]

        notes_parts = ["## Batched Items\n"]
        for item_title, item_desc in items:
            notes_parts.append(f"### {item_title}\n")
            notes_parts.append(f"{item_desc}\n")
            notes_parts.append("---\n")

        request = TaskCreationRequest(
            title=title,
            context=context,
            implementation_steps=steps,
            acceptance_criteria=criteria,
            task_type="task",
            priority=2,
            labels=["batch"] + (labels or []),
            complexity=TaskComplexity.LOW,
            notes="\n".join(notes_parts),
        )
        return self.create_task(request)


# Convenience function for getting default service
_default_service: TaskService | None = None


def get_task_service() -> TaskService:
    """Get the default task service instance."""
    global _default_service
    if _default_service is None:
        _default_service = TaskService()
    return _default_service
