"""
Stager for importing plan tasks into task backend.

The Stager bridges the planning phase and execution phase by:
1. Parsing the itemized-plan.md file
2. Converting parsed tasks to Task models
3. Importing tasks via the task backend's import_tasks() method
4. Updating the plan status to STAGED

Example:
    >>> from cub.core.stage import Stager
    >>> from cub.core.plan.context import PlanContext
    >>> ctx = PlanContext.load(Path("plans/my-feature"), Path("."))
    >>> stager = Stager(ctx)
    >>> result = stager.stage()
    >>> print(f"Staged {len(result.tasks_created)} tasks")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from cub.core.plan.context import PlanContext
from cub.core.plan.models import PlanStatus
from cub.core.plan.parser import (
    ParsedEpic,
    ParsedPlan,
    ParsedTask,
    PlanFileNotFoundError,
    PlanFormatError,
    parse_itemized_plan,
)
from cub.core.tasks.backend import TaskBackend, get_backend
from cub.core.tasks.models import Task, TaskPriority, TaskType

if TYPE_CHECKING:
    pass


class StagerError(Exception):
    """Base exception for staging errors."""

    pass


class PlanNotCompleteError(StagerError):
    """Raised when trying to stage a plan that isn't complete."""

    pass


class PlanAlreadyStagedError(StagerError):
    """Raised when trying to stage a plan that's already staged."""

    pass


class ItemizedPlanNotFoundError(StagerError):
    """Raised when itemized-plan.md is missing."""

    pass


class TaskImportError(StagerError):
    """Raised when task import fails."""

    pass


@dataclass
class StagingResult:
    """Result of staging a plan."""

    plan_slug: str
    epics_created: list[Task] = field(default_factory=list)
    tasks_created: list[Task] = field(default_factory=list)
    duration_seconds: float = 0.0
    dry_run: bool = False

    @property
    def total_created(self) -> int:
        """Total number of items created (epics + tasks)."""
        return len(self.epics_created) + len(self.tasks_created)


class Stager:
    """
    Stages plans by importing tasks into the task backend.

    The Stager reads itemized-plan.md, converts parsed tasks to
    Task model objects, and uses the task backend's import_tasks()
    method to create them in the backend (beads, JSON, etc.).

    Example:
        >>> ctx = PlanContext.load(plan_dir, project_root)
        >>> stager = Stager(ctx)
        >>> result = stager.stage()
        >>> print(f"Created {result.total_created} items")
    """

    def __init__(
        self,
        plan_ctx: PlanContext,
        backend: TaskBackend | None = None,
    ) -> None:
        """
        Initialize the Stager.

        Args:
            plan_ctx: The plan context containing plan metadata and paths.
            backend: Optional task backend to use. If not provided,
                auto-detects the backend from the project directory.
        """
        self.plan_ctx = plan_ctx
        self._backend = backend

    @property
    def backend(self) -> TaskBackend:
        """
        Get the task backend, auto-detecting if not set.

        Raises:
            StagerError: If backend cannot be detected or initialized.
        """
        if self._backend is None:
            try:
                self._backend = get_backend(project_dir=self.plan_ctx.project_root)
            except ValueError as e:
                raise StagerError(
                    f"Cannot detect task backend: {e}. "
                    "Ensure you have beads configured or .tasks.json present."
                ) from e
        return self._backend

    def validate(self) -> None:
        """
        Validate that the plan can be staged.

        Raises:
            PlanNotCompleteError: If plan is not complete (all stages done).
            PlanAlreadyStagedError: If plan is already staged.
            ItemizedPlanNotFoundError: If itemized-plan.md doesn't exist.
        """
        plan = self.plan_ctx.plan

        # Check plan status
        if plan.status == PlanStatus.STAGED:
            raise PlanAlreadyStagedError(
                f"Plan '{plan.slug}' is already staged. "
                "Cannot stage a plan twice."
            )

        if plan.status == PlanStatus.ARCHIVED:
            raise PlanNotCompleteError(
                f"Plan '{plan.slug}' is archived. "
                "Cannot stage an archived plan."
            )

        if not plan.is_complete:
            raise PlanNotCompleteError(
                f"Plan '{plan.slug}' is not complete. "
                f"Status: {plan.status.value}. "
                "Run all stages (orient, architect, itemize) before staging."
            )

        # Check for itemized-plan.md
        itemized_path = self.plan_ctx.itemized_plan_path
        if not itemized_path.exists():
            raise ItemizedPlanNotFoundError(
                f"No itemized-plan.md found at {itemized_path}. "
                "Run 'cub plan itemize' first."
            )

    def parse_plan(self) -> ParsedPlan:
        """
        Parse the itemized-plan.md file.

        Returns:
            ParsedPlan containing metadata, epics, and tasks.

        Raises:
            ItemizedPlanNotFoundError: If file doesn't exist.
            StagerError: If file has invalid format.
        """
        itemized_path = self.plan_ctx.itemized_plan_path

        try:
            return parse_itemized_plan(itemized_path)
        except PlanFileNotFoundError as e:
            raise ItemizedPlanNotFoundError(str(e)) from e
        except PlanFormatError as e:
            raise StagerError(f"Invalid itemized-plan.md format: {e}") from e

    def _convert_epic_to_task(self, epic: ParsedEpic) -> Task:
        """
        Convert a ParsedEpic to a Task model (epic type).

        Args:
            epic: The parsed epic from itemized-plan.md.

        Returns:
            Task model with type=EPIC.
        """
        return Task(
            id=epic.id,
            title=epic.title,
            priority=TaskPriority(f"P{epic.priority}"),
            labels=epic.labels,
            type=TaskType.EPIC,
            description=epic.description,
        )

    def _convert_parsed_task_to_task(self, parsed_task: ParsedTask) -> Task:
        """
        Convert a ParsedTask to a Task model.

        Args:
            parsed_task: The parsed task from itemized-plan.md.

        Returns:
            Task model ready for import.
        """
        # Build description from context, steps, and files
        description_parts: list[str] = []

        if parsed_task.context:
            description_parts.append(parsed_task.context)

        if parsed_task.implementation_steps:
            description_parts.append("\n**Implementation Steps:**")
            for i, step in enumerate(parsed_task.implementation_steps, 1):
                description_parts.append(f"{i}. {step}")

        if parsed_task.files:
            description_parts.append(f"\n**Files:** {', '.join(parsed_task.files)}")

        description = "\n".join(description_parts) if description_parts else ""

        return Task(
            id=parsed_task.id,
            title=parsed_task.title,
            priority=TaskPriority(f"P{parsed_task.priority}"),
            labels=parsed_task.labels,
            parent=parsed_task.epic_id,
            blocks=parsed_task.blocks,  # In our model this stores what we block
            acceptance_criteria=parsed_task.acceptance_criteria,
            description=description,
            type=TaskType.TASK,
        )

    def stage(self, dry_run: bool = False) -> StagingResult:
        """
        Stage the plan by importing tasks to the backend.

        This is the main entry point for staging. It:
        1. Validates the plan is ready to stage
        2. Parses itemized-plan.md
        3. Converts parsed items to Task models
        4. Imports via backend.import_tasks()
        5. Updates plan status to STAGED

        Args:
            dry_run: If True, parse and validate but don't import.

        Returns:
            StagingResult with created epics and tasks.

        Raises:
            StagerError: If staging fails at any step.
        """
        start_time = time.time()

        # Validate
        self.validate()

        # Parse
        parsed_plan = self.parse_plan()

        # Convert epics to Task models
        epic_tasks = [self._convert_epic_to_task(e) for e in parsed_plan.epics]

        # Convert tasks to Task models
        tasks = [self._convert_parsed_task_to_task(t) for t in parsed_plan.tasks]

        # Validate that we have something to stage
        if not epic_tasks and not tasks:
            raise StagerError(
                "Parsed plan contains no epics or tasks. "
                "Cannot stage an empty plan."
            )

        # Validate task relationships
        epic_ids = {e.id for e in epic_tasks}
        for task in tasks:
            if task.parent and task.parent not in epic_ids:
                raise StagerError(
                    f"Task '{task.id}' references non-existent epic '{task.parent}'. "
                    "Fix the itemized-plan.md before staging."
                )

        if dry_run:
            # Return what would be created without actually creating
            return StagingResult(
                plan_slug=self.plan_ctx.plan.slug,
                epics_created=epic_tasks,
                tasks_created=tasks,
                duration_seconds=time.time() - start_time,
                dry_run=True,
            )

        # Import to backend
        try:
            # Import epics first (they may be parents of tasks)
            created_epics = self.backend.import_tasks(epic_tasks)
        except ValueError as e:
            raise TaskImportError(
                f"Failed to import epics to task backend: {e}. "
                "No changes have been made to the plan status."
            ) from e

        # Import tasks (if epics succeeded)
        try:
            created_tasks = self.backend.import_tasks(tasks)
        except ValueError as e:
            raise TaskImportError(
                f"Failed to import tasks to task backend: {e}. "
                f"Note: {len(created_epics)} epics were already imported. "
                "You may need to clean up the backend manually."
            ) from e

        # Validate import results
        if len(created_epics) != len(epic_tasks):
            raise TaskImportError(
                f"Backend import mismatch: expected {len(epic_tasks)} epics, "
                f"got {len(created_epics)}. Import may be incomplete."
            )
        if len(created_tasks) != len(tasks):
            raise TaskImportError(
                f"Backend import mismatch: expected {len(tasks)} tasks, "
                f"got {len(created_tasks)}. Import may be incomplete."
            )

        # Update plan status
        try:
            self.plan_ctx.plan.mark_staged()
        except ValueError as e:
            raise StagerError(
                f"Cannot mark plan as staged: {e}. "
                f"Tasks were imported successfully but plan status not updated."
            ) from e

        try:
            self.plan_ctx.save_plan()
        except (OSError, ValueError) as e:
            raise StagerError(
                f"Cannot save plan after staging: {e}. "
                f"Tasks were imported successfully but plan.json not updated. "
                f"Plan status is now STAGED in memory but not persisted."
            ) from e

        return StagingResult(
            plan_slug=self.plan_ctx.plan.slug,
            epics_created=created_epics,
            tasks_created=created_tasks,
            duration_seconds=time.time() - start_time,
            dry_run=False,
        )


def stage_file(
    plan_path: Path,
    project_root: Path | None = None,
    dry_run: bool = False,
) -> StagingResult:
    """
    Stage a standalone itemized-plan.md file directly.

    Unlike the Stager class which requires a PlanContext with plan.json,
    this function accepts any itemized-plan.md file and imports its
    tasks into the backend. Used for punchlist-generated plans and
    other one-off plan files.

    Args:
        plan_path: Path to the itemized-plan.md file.
        project_root: Project root for backend detection. Defaults to cwd.
        dry_run: If True, parse but don't import.

    Returns:
        StagingResult with created epics and tasks.

    Raises:
        ItemizedPlanNotFoundError: If the file doesn't exist.
        StagerError: If the file has invalid format.
        TaskImportError: If backend import fails.
    """
    start_time = time.time()

    if not plan_path.exists():
        raise ItemizedPlanNotFoundError(f"File not found: {plan_path}")

    # Parse the plan file
    try:
        parsed_plan = parse_itemized_plan(plan_path)
    except PlanFileNotFoundError as e:
        raise ItemizedPlanNotFoundError(str(e)) from e
    except PlanFormatError as e:
        raise StagerError(f"Invalid plan format: {e}") from e

    # Reuse the same conversion helpers as Stager
    # (they're static-compatible, just need a temporary instance-free approach)
    epic_tasks = [
        Task(
            id=epic.id,
            title=epic.title,
            priority=TaskPriority(f"P{epic.priority}"),
            labels=epic.labels,
            type=TaskType.EPIC,
            description=epic.description,
        )
        for epic in parsed_plan.epics
    ]

    tasks: list[Task] = []
    for parsed_task in parsed_plan.tasks:
        description_parts: list[str] = []
        if parsed_task.context:
            description_parts.append(parsed_task.context)
        if parsed_task.implementation_steps:
            description_parts.append("\n**Implementation Steps:**")
            for i, step in enumerate(parsed_task.implementation_steps, 1):
                description_parts.append(f"{i}. {step}")
        if parsed_task.files:
            description_parts.append(
                f"\n**Files:** {', '.join(parsed_task.files)}"
            )
        description = "\n".join(description_parts) if description_parts else ""

        tasks.append(
            Task(
                id=parsed_task.id,
                title=parsed_task.title,
                priority=TaskPriority(f"P{parsed_task.priority}"),
                labels=parsed_task.labels,
                parent=parsed_task.epic_id,
                blocks=parsed_task.blocks,
                acceptance_criteria=parsed_task.acceptance_criteria,
                description=description,
                type=TaskType.TASK,
            )
        )

    if not epic_tasks and not tasks:
        raise StagerError("Plan file contains no epics or tasks.")

    # Validate relationships
    epic_ids = {e.id for e in epic_tasks}
    for task in tasks:
        if task.parent and task.parent not in epic_ids:
            raise StagerError(
                f"Task '{task.id}' references non-existent epic '{task.parent}'."
            )

    slug = plan_path.stem

    if dry_run:
        return StagingResult(
            plan_slug=slug,
            epics_created=epic_tasks,
            tasks_created=tasks,
            duration_seconds=time.time() - start_time,
            dry_run=True,
        )

    # Import to backend
    if project_root is None:
        project_root = Path.cwd()

    try:
        backend = get_backend(project_dir=project_root)
    except ValueError as e:
        raise StagerError(
            f"Cannot detect task backend: {e}. "
            "Ensure you have beads configured or .tasks.json present."
        ) from e

    try:
        created_epics = backend.import_tasks(epic_tasks)
    except ValueError as e:
        raise TaskImportError(f"Failed to import epics: {e}") from e

    try:
        created_tasks = backend.import_tasks(tasks)
    except ValueError as e:
        raise TaskImportError(
            f"Failed to import tasks: {e}. "
            f"Note: {len(created_epics)} epics were already imported."
        ) from e

    return StagingResult(
        plan_slug=slug,
        epics_created=created_epics,
        tasks_created=created_tasks,
        duration_seconds=time.time() - start_time,
        dry_run=False,
    )


def find_stageable_plans(project_root: Path) -> list[Path]:
    """
    Find all plans that are ready to be staged.

    A plan is stageable if:
    - Status is COMPLETE (all stages done)
    - Status is not STAGED or ARCHIVED

    Args:
        project_root: Root directory of the project.

    Returns:
        List of paths to plan directories that can be staged.
    """
    plans_dir = project_root / "plans"
    if not plans_dir.exists():
        return []

    stageable: list[Path] = []
    for plan_dir in plans_dir.iterdir():
        if not plan_dir.is_dir():
            continue

        plan_json = plan_dir / "plan.json"
        if not plan_json.exists():
            continue

        # Load and check status
        try:
            ctx = PlanContext.load(plan_dir, project_root)
            plan = ctx.plan
            if plan.is_complete and plan.status not in (
                PlanStatus.STAGED,
                PlanStatus.ARCHIVED,
            ):
                stageable.append(plan_dir)
        except Exception:
            # Skip plans that can't be loaded
            continue

    return stageable
