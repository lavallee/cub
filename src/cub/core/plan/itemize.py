"""
Itemize stage implementation for cub plan.

The itemize stage breaks the architecture into discrete tasks with beads IDs.
It reads orientation.md and architecture.md, and produces itemized-plan.md with:
- Epics with priority and labels
- Tasks with priority, labels, blocks, context, implementation steps, and acceptance criteria
- Beads-compatible IDs using random suffix format (e.g., cub-k7m.1)

Example:
    >>> from cub.core.plan.context import PlanContext
    >>> from cub.core.plan.itemize import ItemizeStage
    >>> ctx = PlanContext.load(Path("plans/my-feature"))
    >>> stage = ItemizeStage(ctx)
    >>> result = stage.run()
    >>> result.output_path.exists()
    True
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.plan.ids import generate_epic_id, generate_task_id
from cub.core.plan.models import PlanStage, StageStatus

if TYPE_CHECKING:
    from cub.core.plan.context import PlanContext


@dataclass
class Epic:
    """An epic in the itemized plan."""

    id: str
    title: str
    priority: int
    labels: list[str]
    description: str


@dataclass
class Task:
    """A task in the itemized plan."""

    id: str
    title: str
    priority: int
    labels: list[str]
    epic_id: str
    blocks: list[str] = field(default_factory=list)
    context: str = ""
    implementation_steps: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class ItemizeResult:
    """Result of running the itemize stage."""

    output_path: Path
    epics: list[Epic]
    tasks: list[Task]
    started_at: datetime
    completed_at: datetime

    @property
    def duration_seconds(self) -> float:
        """Get the duration of the itemize stage in seconds."""
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def total_tasks(self) -> int:
        """Get the total number of tasks across all epics."""
        return len(self.tasks)


class ItemizeStageError(Exception):
    """Base exception for itemize stage errors."""

    pass


class ItemizeInputError(ItemizeStageError):
    """Raised when itemize stage input is invalid or missing."""

    pass


class ItemizeStage:
    """
    Itemize stage of the planning pipeline.

    The itemize phase breaks architecture into discrete tasks:
    - Reviews orientation.md for requirements context
    - Reviews architecture.md for implementation phases
    - Produces itemized-plan.md with epics and tasks

    This stage produces itemized-plan.md with task breakdown,
    dependencies, implementation steps, and acceptance criteria.

    Attributes:
        ctx: The PlanContext for this planning session.
    """

    def __init__(
        self,
        ctx: PlanContext,
    ) -> None:
        """
        Initialize the itemize stage.

        Args:
            ctx: PlanContext for this planning session.
        """
        self.ctx = ctx

    def validate(self) -> None:
        """
        Validate that itemize stage can run.

        Raises:
            ItemizeInputError: If prerequisites are not met.
        """
        # Check that architect stage is complete
        if self.ctx.plan.stages[PlanStage.ARCHITECT] != StageStatus.COMPLETE:
            raise ItemizeInputError(
                "Itemize stage requires completed architecture. "
                "Run 'cub plan architect' first."
            )

        # Check that architecture.md exists
        if not self.ctx.architecture_path.exists():
            raise ItemizeInputError(
                f"Architecture file not found: {self.ctx.architecture_path}. "
                "Run 'cub plan architect' first."
            )

        # Check that orientation.md exists
        if not self.ctx.orientation_path.exists():
            raise ItemizeInputError(
                f"Orientation file not found: {self.ctx.orientation_path}. "
                "Run 'cub plan orient' first."
            )

    def _read_orientation(self) -> str:
        """
        Read the orientation.md content.

        Returns:
            Content of orientation.md.

        Raises:
            ItemizeInputError: If file cannot be read.
        """
        try:
            return self.ctx.orientation_path.read_text()
        except OSError as e:
            raise ItemizeInputError(f"Cannot read orientation.md: {e}") from e

    def _read_architecture(self) -> str:
        """
        Read the architecture.md content.

        Returns:
            Content of architecture.md.

        Raises:
            ItemizeInputError: If file cannot be read.
        """
        try:
            return self.ctx.architecture_path.read_text()
        except OSError as e:
            raise ItemizeInputError(f"Cannot read architecture.md: {e}") from e

    def _extract_from_orientation(self, orientation_content: str) -> dict[str, object]:
        """
        Extract information from the orientation.md content.

        Args:
            orientation_content: Content of orientation.md.

        Returns:
            Dictionary with extracted information.
        """
        extracted: dict[str, object] = {
            "title": None,
            "problem_statement": None,
            "requirements_p0": [],
            "requirements_p1": [],
            "constraints": [],
            "mvp_scope": [],
        }

        # Extract title from first heading
        title_match = re.search(
            r"^#\s+Orientation:\s*(.+)$", orientation_content, re.MULTILINE
        )
        if title_match:
            extracted["title"] = title_match.group(1).strip()

        # Extract problem statement
        problem_match = re.search(
            r"##\s+Problem Statement\s*\n([\s\S]*?)(?=\n##|\Z)",
            orientation_content,
            re.IGNORECASE,
        )
        if problem_match:
            extracted["problem_statement"] = problem_match.group(1).strip()

        # Extract P0 requirements
        p0_match = re.search(
            r"###\s+P0[^\n]*\n([\s\S]*?)(?=\n###|\n##|\Z)",
            orientation_content,
            re.IGNORECASE,
        )
        if p0_match:
            p0_content = p0_match.group(1)
            requirements = re.findall(
                r"^[-*]\s+\*?\*?([^*\n]+)", p0_content, re.MULTILINE
            )
            if requirements:
                extracted["requirements_p0"] = [r.strip() for r in requirements]

        # Extract P1 requirements
        p1_match = re.search(
            r"###\s+P1[^\n]*\n([\s\S]*?)(?=\n###|\n##|\Z)",
            orientation_content,
            re.IGNORECASE,
        )
        if p1_match:
            p1_content = p1_match.group(1)
            requirements = re.findall(r"^[-*]\s+(.+)$", p1_content, re.MULTILINE)
            if requirements:
                extracted["requirements_p1"] = [r.strip() for r in requirements]

        # Extract MVP scope
        mvp_match = re.search(
            r"##\s+MVP Boundary\s*\n([\s\S]*?)(?=\n##|\Z)",
            orientation_content,
            re.IGNORECASE,
        )
        if mvp_match:
            mvp_content = mvp_match.group(1)
            # Look for "In scope" items
            in_scope_match = re.search(
                r"\*\*In scope[^*]*\*\*:?\s*\n([\s\S]*?)(?=\n\*\*|\Z)",
                mvp_content,
                re.IGNORECASE,
            )
            if in_scope_match:
                scope_items = re.findall(
                    r"^[-*]\s+(.+)$", in_scope_match.group(1), re.MULTILINE
                )
                if scope_items:
                    extracted["mvp_scope"] = [s.strip() for s in scope_items]

        return extracted

    def _extract_from_architecture(
        self, architecture_content: str
    ) -> dict[str, object]:
        """
        Extract information from the architecture.md content.

        Args:
            architecture_content: Content of architecture.md.

        Returns:
            Dictionary with extracted information.
        """
        extracted: dict[str, object] = {
            "title": None,
            "mindset": None,
            "scale": None,
            "tech_stack": [],
            "components": [],
            "phases": [],
        }

        # Extract title from first heading
        title_match = re.search(
            r"^#\s+Architecture Design:\s*(.+)$", architecture_content, re.MULTILINE
        )
        if title_match:
            extracted["title"] = title_match.group(1).strip()

        # Extract mindset
        mindset_match = re.search(
            r"\*\*Mindset:\*\*\s*(\w+)", architecture_content, re.IGNORECASE
        )
        if mindset_match:
            extracted["mindset"] = mindset_match.group(1).strip()

        # Extract scale
        scale_match = re.search(
            r"\*\*Scale:\*\*\s*(\S+)", architecture_content, re.IGNORECASE
        )
        if scale_match:
            extracted["scale"] = scale_match.group(1).strip()

        # Extract components
        components_section_match = re.search(
            r"##\s+Components\s*\n([\s\S]*?)(?=\n##|\Z)",
            architecture_content,
            re.IGNORECASE,
        )
        if components_section_match:
            components_content = components_section_match.group(1)
            component_matches = re.findall(
                r"###\s+(.+?)\s*\n", components_content, re.MULTILINE
            )
            if component_matches:
                extracted["components"] = [c.strip() for c in component_matches]

        # Extract implementation phases
        # Note: Match until the next ## heading (not ###) or end of string
        phases_section_match = re.search(
            r"##\s+Implementation Phases\s*\n([\s\S]*?)(?=\n##[^#]|\Z)",
            architecture_content,
            re.IGNORECASE,
        )
        if phases_section_match:
            phases_content = phases_section_match.group(1)
            # Match phase headers and their content until next ### or end
            phase_matches = re.findall(
                r"###\s+Phase\s+\d+:\s*(.+?)\n([\s\S]*?)(?=\n###|$)",
                phases_content,
            )
            phases = []
            for phase_name, phase_body in phase_matches:
                # Extract tasks for this phase
                task_matches = re.findall(r"^[-*]\s+(.+)$", phase_body, re.MULTILINE)
                phases.append(
                    {
                        "name": phase_name.strip(),
                        "tasks": [t.strip() for t in task_matches],
                    }
                )
            extracted["phases"] = phases

        return extracted

    def _generate_epics_and_tasks(
        self,
        orientation_extracted: dict[str, object],
        architecture_extracted: dict[str, object],
    ) -> tuple[list[Epic], list[Task]]:
        """
        Generate epics and tasks from extracted information.

        Args:
            orientation_extracted: Information extracted from orientation.md.
            architecture_extracted: Information extracted from architecture.md.

        Returns:
            Tuple of (list of Epic, list of Task).
        """
        epics: list[Epic] = []
        tasks: list[Task] = []
        existing_ids: set[str] = set()

        project = self.ctx.project
        phases = architecture_extracted.get("phases", [])
        if not isinstance(phases, list):
            phases = []

        # If no phases found, create a single epic from requirements
        if not phases:
            requirements = orientation_extracted.get("requirements_p0", [])
            if not isinstance(requirements, list):
                requirements = []

            # Create a single Foundation epic
            epic_id = generate_epic_id(project, existing_ids)
            existing_ids.add(epic_id)

            # Generate plan label and description with plan reference
            plan_label = f"plan:{self.ctx.plan.slug}"
            spec_ref = self.ctx.plan.spec_file or "N/A"

            epic = Epic(
                id=epic_id,
                title=f"{self.ctx.plan.slug}: Foundation",
                priority=0,
                labels=[plan_label, "phase-1", "foundation"],
                description=(
                    f"Core implementation based on P0 requirements.\n\n"
                    f"Plan: plans/{self.ctx.plan.slug}/\n"
                    f"Spec: {spec_ref}"
                ),
            )
            epics.append(epic)

            # Create tasks from requirements
            task_num = 1
            for req in requirements:
                task_id = generate_task_id(epic_id, task_num)
                # Add complexity and model labels (default to medium/sonnet)
                task_labels = [plan_label, "foundation", "complexity:medium", "model:sonnet"]
                task = Task(
                    id=task_id,
                    title=str(req)[:100] if req else f"Task {task_num}",
                    priority=0,
                    labels=task_labels,
                    epic_id=epic_id,
                    context=(
                        f"Implements P0 requirement: {req}\n"
                        f"See: plans/{self.ctx.plan.slug}/"
                    ),
                    implementation_steps=["Implement the feature", "Add tests"],
                    acceptance_criteria=[f"Feature works as described: {req}"],
                )
                tasks.append(task)
                task_num += 1

            return epics, tasks

        # Generate epics from phases
        for phase_idx, phase in enumerate(phases):
            if not isinstance(phase, dict):
                continue

            phase_name = phase.get("name", f"Phase {phase_idx + 1}")
            phase_tasks = phase.get("tasks", [])
            if not isinstance(phase_tasks, list):
                phase_tasks = []

            # Generate epic ID
            epic_id = generate_epic_id(project, existing_ids)
            existing_ids.add(epic_id)

            # Determine priority based on phase number
            priority = phase_idx

            # Generate labels with plan reference
            plan_label = f"plan:{self.ctx.plan.slug}"
            labels = [plan_label, f"phase-{phase_idx + 1}", phase_name.lower().replace(" ", "-")]

            # Generate epic description with plan/spec reference
            spec_ref = self.ctx.plan.spec_file or "N/A"
            epic_description = (
                f"Implementation phase {phase_idx + 1}: {phase_name}\n\n"
                f"Plan: plans/{self.ctx.plan.slug}/\n"
                f"Spec: {spec_ref}"
            )

            epic = Epic(
                id=epic_id,
                title=f"{self.ctx.plan.slug}: {phase_name}",
                priority=priority,
                labels=labels,
                description=epic_description,
            )
            epics.append(epic)

            # Generate tasks from phase tasks
            task_num = 1
            for task_name in phase_tasks:
                task_id = generate_task_id(epic_id, task_num)
                task_title = str(task_name)[:100] if task_name else f"Task {task_num}"

                # Generate implementation steps
                impl_steps = [
                    f"Implement: {task_name}",
                    "Add unit tests",
                    "Update documentation if needed",
                ]

                # Generate acceptance criteria
                acceptance = [
                    f"{task_name} is implemented and working",
                    "Tests pass",
                    "mypy strict passes",
                ]

                # Add complexity and model labels (default to medium/sonnet)
                task_labels = labels + ["complexity:medium", "model:sonnet"]

                task = Task(
                    id=task_id,
                    title=task_title,
                    priority=priority,
                    labels=task_labels,
                    epic_id=epic_id,
                    context=f"Part of {phase_name} phase. See: plans/{self.ctx.plan.slug}/",
                    implementation_steps=impl_steps,
                    acceptance_criteria=acceptance,
                )
                tasks.append(task)
                task_num += 1

        return epics, tasks

    def _generate_itemized_plan(
        self,
        orientation_extracted: dict[str, object],
        architecture_extracted: dict[str, object],
        epics: list[Epic],
        tasks: list[Task],
    ) -> str:
        """
        Generate the itemized-plan.md content.

        Args:
            orientation_extracted: Information extracted from orientation.md.
            architecture_extracted: Information extracted from architecture.md.
            epics: List of generated epics.
            tasks: List of generated tasks.

        Returns:
            Generated itemized-plan.md content.
        """
        now = datetime.now(timezone.utc)
        title = orientation_extracted.get("title") or self.ctx.plan.slug
        mindset = architecture_extracted.get("mindset") or "mvp"
        scale = architecture_extracted.get("scale") or "team"

        # Get relative paths for links
        spec_link = self._relative_spec_path() or "N/A"

        orient_link = "[orientation.md](./orientation.md)"
        arch_link = "[architecture.md](./architecture.md)"
        lines = [
            f"# Itemized Plan: {title}",
            "",
            f"> Source: [{self.ctx.plan.spec_file or 'N/A'}]({spec_link})",
            f"> Orient: {orient_link} | Architect: {arch_link}",
            f"> Generated: {now.strftime('%Y-%m-%d')}",
            "",
            "## Context Summary",
            "",
        ]

        # Add problem statement as context
        problem = orientation_extracted.get("problem_statement")
        if problem and isinstance(problem, str):
            summary = problem.split("\n")[0][:300]
            if len(problem) > 300:
                summary += "..."
            lines.append(summary)
        else:
            lines.append("*Implementation plan for the feature.*")
        lines.extend(["", f"**Mindset:** {mindset} | **Scale:** {scale}", "", "---", ""])

        # Group tasks by epic
        tasks_by_epic: dict[str, list[Task]] = {}
        for task in tasks:
            if task.epic_id not in tasks_by_epic:
                tasks_by_epic[task.epic_id] = []
            tasks_by_epic[task.epic_id].append(task)

        # Generate epic sections
        for epic in epics:
            lines.extend(
                [
                    f"## Epic: {epic.id} - {epic.title}",
                    "",
                    f"Priority: {epic.priority}",
                    f"Labels: {', '.join(epic.labels)}",
                    "",
                    epic.description,
                    "",
                ]
            )

            # Generate tasks for this epic
            epic_tasks = tasks_by_epic.get(epic.id, [])
            for task in epic_tasks:
                lines.extend(
                    [
                        f"### Task: {task.id} - {task.title}",
                        "",
                        f"Priority: {task.priority}",
                        f"Labels: {', '.join(task.labels)}",
                    ]
                )

                if task.blocks:
                    lines.append(f"Blocks: {', '.join(task.blocks)}")

                lines.extend(["", f"**Context**: {task.context}", ""])

                if task.implementation_steps:
                    lines.append("**Implementation Steps**:")
                    for i, step in enumerate(task.implementation_steps, 1):
                        lines.append(f"{i}. {step}")
                    lines.append("")

                if task.acceptance_criteria:
                    lines.append("**Acceptance Criteria**:")
                    for criterion in task.acceptance_criteria:
                        lines.append(f"- [ ] {criterion}")
                    lines.append("")

                if task.files:
                    lines.append(f"**Files**: {', '.join(task.files)}")
                    lines.append("")

                lines.extend(["---", ""])

        # Add summary section
        lines.extend(
            [
                "## Summary",
                "",
                "| Epic | Tasks | Priority | Description |",
                "|------|-------|----------|-------------|",
            ]
        )

        for epic in epics:
            task_count = len(tasks_by_epic.get(epic.id, []))
            desc = epic.description
            desc_short = desc[:40] + "..." if len(desc) > 40 else desc
            lines.append(f"| {epic.id} | {task_count} | P{epic.priority} | {desc_short} |")

        lines.extend(
            [
                "",
                f"**Total**: {len(epics)} epics, {len(tasks)} tasks",
                "",
            ]
        )

        return "\n".join(lines)

    def _relative_spec_path(self) -> str | None:
        """Get the relative path from plan dir to spec file."""
        if not self.ctx.spec_path:
            return None

        try:
            # Calculate relative path from plan directory to spec
            spec_path = self.ctx.spec_path
            return str(Path("../..") / spec_path.relative_to(self.ctx.project_root))
        except ValueError:
            return str(self.ctx.spec_path)

    def run(self) -> ItemizeResult:
        """
        Run the itemize stage.

        This method:
        1. Validates prerequisites
        2. Reads orientation.md and architecture.md
        3. Extracts information from both documents
        4. Generates epics and tasks with beads IDs
        5. Produces itemized-plan.md
        6. Updates plan status

        Returns:
            ItemizeResult with output path and generated epics/tasks.

        Raises:
            ItemizeStageError: If stage fails to run.
        """
        started_at = datetime.now(timezone.utc)

        # Validate prerequisites
        self.validate()

        # Mark stage as in progress
        self.ctx.plan.start_stage(PlanStage.ITEMIZE)
        self.ctx.ensure_plan_dir()
        self.ctx.save_plan()

        # Read input documents
        orientation_content = self._read_orientation()
        architecture_content = self._read_architecture()

        # Extract information
        orientation_extracted = self._extract_from_orientation(orientation_content)
        architecture_extracted = self._extract_from_architecture(architecture_content)

        # Generate epics and tasks
        epics, tasks = self._generate_epics_and_tasks(
            orientation_extracted, architecture_extracted
        )

        # Generate itemized plan document
        itemized_plan_content = self._generate_itemized_plan(
            orientation_extracted, architecture_extracted, epics, tasks
        )

        # Write itemized-plan.md
        output_path = self.ctx.itemized_plan_path
        output_path.write_text(itemized_plan_content)

        # Mark stage as complete
        self.ctx.plan.complete_stage(PlanStage.ITEMIZE)
        self.ctx.save_plan()

        completed_at = datetime.now(timezone.utc)

        return ItemizeResult(
            output_path=output_path,
            epics=epics,
            tasks=tasks,
            started_at=started_at,
            completed_at=completed_at,
        )


def run_itemize(ctx: PlanContext) -> ItemizeResult:
    """
    Convenience function to run the itemize stage.

    Args:
        ctx: PlanContext for this planning session.

    Returns:
        ItemizeResult with output path and generated epics/tasks.
    """
    stage = ItemizeStage(ctx)
    return stage.run()
