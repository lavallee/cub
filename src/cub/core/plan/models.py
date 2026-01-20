"""
Plan data models for cub.

Defines the Plan model and related enums for managing the planning workflow.
Plans are stored as directories containing plan.json (metadata) and stage
output files (orientation.md, architecture.md, itemized-plan.md).

The plan workflow:
1. Orient - understand the problem space
2. Architect - design the technical approach
3. Itemize - break into discrete tasks

Example:
    >>> plan = Plan(slug="user-auth", project="cub")
    >>> plan.status
    <PlanStatus.PENDING: 'pending'>
    >>> plan.complete_stage(PlanStage.ORIENT)
    >>> plan.stages[PlanStage.ORIENT]
    <StageStatus.COMPLETE: 'complete'>
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from typing_extensions import Self


class PlanStatus(str, Enum):
    """Plan lifecycle status.

    Plans progress through these statuses as work proceeds:
    - PENDING: Created but no stages complete
    - IN_PROGRESS: At least one stage started
    - COMPLETE: All stages (orient, architect, itemize) complete
    - STAGED: Tasks imported to task backend
    - ARCHIVED: Plan no longer active (replaced, abandoned, etc.)
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    STAGED = "staged"
    ARCHIVED = "archived"


class PlanStage(str, Enum):
    """Plan interview stages.

    Each stage produces an output file:
    - ORIENT: orientation.md - problem understanding
    - ARCHITECT: architecture.md - technical design
    - ITEMIZE: itemized-plan.md - task breakdown

    Stages must be completed in order: orient -> architect -> itemize.
    """

    ORIENT = "orient"
    ARCHITECT = "architect"
    ITEMIZE = "itemize"

    @property
    def output_file(self) -> str:
        """Get the output filename for this stage."""
        return {
            PlanStage.ORIENT: "orientation.md",
            PlanStage.ARCHITECT: "architecture.md",
            PlanStage.ITEMIZE: "itemized-plan.md",
        }[self]

    @property
    def next_stage(self) -> "PlanStage | None":
        """Get the next stage in the workflow, or None if this is the last."""
        order = [PlanStage.ORIENT, PlanStage.ARCHITECT, PlanStage.ITEMIZE]
        idx = order.index(self)
        if idx < len(order) - 1:
            return order[idx + 1]
        return None

    @property
    def previous_stage(self) -> "PlanStage | None":
        """Get the previous stage in the workflow, or None if this is the first."""
        order = [PlanStage.ORIENT, PlanStage.ARCHITECT, PlanStage.ITEMIZE]
        idx = order.index(self)
        if idx > 0:
            return order[idx - 1]
        return None


class StageStatus(str, Enum):
    """Status of an individual plan stage.

    - PENDING: Not started
    - IN_PROGRESS: Currently being worked on
    - COMPLETE: Successfully finished
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class SpecStage(str, Enum):
    """Spec lifecycle stages.

    Specs move through these stages as planning and implementation proceeds:
    - RESEARCHING: Initial exploration, many unknowns (-ing = active)
    - PLANNED: Plan exists, ready to stage (past = at rest)
    - STAGED: Tasks in backend, ready to build (past = at rest)
    - IMPLEMENTING: Active work happening (-ing = active)
    - RELEASED: Shipped, available for drift audit (past = at rest)

    The word forms (-ing vs past tense) indicate whether the spec is
    actively being worked on or is at rest awaiting the next action.
    """

    RESEARCHING = "researching"
    PLANNED = "planned"
    STAGED = "staged"
    IMPLEMENTING = "implementing"
    RELEASED = "released"

    @classmethod
    def from_directory(cls, directory_name: str) -> "SpecStage":
        """Get stage from directory name.

        Args:
            directory_name: Name of the stage directory (e.g., 'researching')

        Returns:
            Corresponding SpecStage enum value

        Raises:
            ValueError: If directory name doesn't match any stage
        """
        for stage in cls:
            if stage.value == directory_name:
                return stage
        raise ValueError(f"Unknown spec stage directory: {directory_name}")

    @property
    def is_active(self) -> bool:
        """Check if this stage represents active work (-ing form)."""
        return self in (SpecStage.RESEARCHING, SpecStage.IMPLEMENTING)


class Plan(BaseModel):
    """
    A plan in the cub system.

    Plans are stored as directories in the project's plans/ folder:
        plans/{slug}/
            plan.json           # This model serialized
            orientation.md      # Orient stage output
            architecture.md     # Architect stage output
            itemized-plan.md    # Itemize stage output

    Example:
        >>> plan = Plan(slug="user-auth", project="cub", spec_file="user-auth.md")
        >>> plan.complete_stage(PlanStage.ORIENT)
        >>> plan.status
        <PlanStatus.IN_PROGRESS: 'in_progress'>
        >>> plan.stages[PlanStage.ORIENT]
        <StageStatus.COMPLETE: 'complete'>
    """

    # Required fields
    slug: str = Field(
        ...,
        min_length=1,
        description="Plan slug (directory name, e.g., 'user-auth')",
    )
    project: str = Field(
        ...,
        min_length=1,
        description="Project identifier (e.g., 'cub')",
    )

    # Plan state
    status: PlanStatus = Field(
        default=PlanStatus.PENDING,
        description="Overall plan status",
    )
    stages: dict[PlanStage, StageStatus] = Field(
        default_factory=lambda: {
            PlanStage.ORIENT: StageStatus.PENDING,
            PlanStage.ARCHITECT: StageStatus.PENDING,
            PlanStage.ITEMIZE: StageStatus.PENDING,
        },
        description="Status of each plan stage",
    )

    # Spec linkage (optional - plans can exist without specs)
    spec_file: str | None = Field(
        default=None,
        description="Linked spec filename (not full path, e.g., 'user-auth.md')",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the plan was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the plan was last modified",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,  # Keep enums as enums for validation
    )

    @field_validator("stages", mode="before")
    @classmethod
    def validate_stages(
        cls, v: dict[str, str] | dict[PlanStage, StageStatus]
    ) -> dict[PlanStage, StageStatus]:
        """Convert string keys/values to enums when loading from JSON."""
        if not v:
            return {
                PlanStage.ORIENT: StageStatus.PENDING,
                PlanStage.ARCHITECT: StageStatus.PENDING,
                PlanStage.ITEMIZE: StageStatus.PENDING,
            }

        result: dict[PlanStage, StageStatus] = {}
        for key, value in v.items():
            # Convert key
            if isinstance(key, str):
                stage = PlanStage(key)
            else:
                stage = key
            # Convert value
            if isinstance(value, str):
                status = StageStatus(value)
            else:
                status = value
            result[stage] = status

        # Ensure all stages present
        for stage in PlanStage:
            if stage not in result:
                result[stage] = StageStatus.PENDING

        return result

    @computed_field
    @property
    def is_complete(self) -> bool:
        """Check if all stages are complete."""
        return all(status == StageStatus.COMPLETE for status in self.stages.values())

    @computed_field
    @property
    def current_stage(self) -> PlanStage | None:
        """Get the current active stage (in_progress), or None."""
        for stage in PlanStage:
            if self.stages[stage] == StageStatus.IN_PROGRESS:
                return stage
        return None

    @computed_field
    @property
    def next_pending_stage(self) -> PlanStage | None:
        """Get the next stage that hasn't been started yet."""
        for stage in [PlanStage.ORIENT, PlanStage.ARCHITECT, PlanStage.ITEMIZE]:
            if self.stages[stage] == StageStatus.PENDING:
                return stage
        return None

    @computed_field
    @property
    def completed_stages(self) -> list[PlanStage]:
        """Get list of completed stages in order."""
        return [
            stage
            for stage in [PlanStage.ORIENT, PlanStage.ARCHITECT, PlanStage.ITEMIZE]
            if self.stages[stage] == StageStatus.COMPLETE
        ]

    def start_stage(self, stage: PlanStage) -> None:
        """
        Mark a stage as in progress.

        Args:
            stage: The stage to start

        Raises:
            ValueError: If prerequisites aren't met (previous stages not complete)
        """
        # Check prerequisites
        prev = stage.previous_stage
        if prev is not None and self.stages[prev] != StageStatus.COMPLETE:
            raise ValueError(
                f"Cannot start {stage.value}: previous stage {prev.value} not complete"
            )

        self.stages[stage] = StageStatus.IN_PROGRESS
        self._update_status()
        self.updated_at = datetime.now(timezone.utc)

    def complete_stage(self, stage: PlanStage) -> None:
        """
        Mark a stage as complete.

        Args:
            stage: The stage to complete
        """
        self.stages[stage] = StageStatus.COMPLETE
        self._update_status()
        self.updated_at = datetime.now(timezone.utc)

    def _update_status(self) -> None:
        """Update overall plan status based on stage statuses."""
        if self.status in (PlanStatus.STAGED, PlanStatus.ARCHIVED):
            # Don't change status once staged or archived
            return

        if all(s == StageStatus.COMPLETE for s in self.stages.values()):
            self.status = PlanStatus.COMPLETE
        elif any(s != StageStatus.PENDING for s in self.stages.values()):
            self.status = PlanStatus.IN_PROGRESS
        else:
            self.status = PlanStatus.PENDING

    def mark_staged(self) -> None:
        """Mark plan as staged (tasks imported to backend)."""
        if not self.is_complete:
            raise ValueError("Cannot stage incomplete plan")
        self.status = PlanStatus.STAGED
        self.updated_at = datetime.now(timezone.utc)

    def archive(self) -> None:
        """Archive the plan."""
        self.status = PlanStatus.ARCHIVED
        self.updated_at = datetime.now(timezone.utc)

    def get_plan_dir(self, project_root: Path) -> Path:
        """
        Get the plan directory path.

        Args:
            project_root: Root directory of the project

        Returns:
            Path to plans/{slug}/
        """
        return project_root / "plans" / self.slug

    def get_stage_output_path(self, stage: PlanStage, project_root: Path) -> Path:
        """
        Get the output file path for a stage.

        Args:
            stage: The plan stage
            project_root: Root directory of the project

        Returns:
            Path to the stage output file (e.g., plans/user-auth/orientation.md)
        """
        return self.get_plan_dir(project_root) / stage.output_file

    def to_json_dict(self) -> dict[str, object]:
        """
        Convert to dictionary for JSON serialization.

        This produces the plan.json structure:
        {
            "slug": "user-auth",
            "project": "cub",
            "status": "in_progress",
            "spec_file": "user-auth.md",
            "stages": {
                "orient": "complete",
                "architect": "in_progress",
                "itemize": "pending"
            },
            "created": "2026-01-20T10:30:00Z",
            "updated": "2026-01-20T14:45:00Z"
        }
        """
        return {
            "slug": self.slug,
            "project": self.project,
            "status": self.status.value,
            "spec_file": self.spec_file,
            "stages": {stage.value: status.value for stage, status in self.stages.items()},
            "created": self.created_at.isoformat(),
            "updated": self.updated_at.isoformat(),
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> Self:
        """
        Create a Plan from a JSON dictionary (plan.json content).

        Args:
            data: Dictionary from JSON

        Returns:
            Plan instance
        """
        # Parse timestamps
        created_at = datetime.now(timezone.utc)
        created_raw = data.get("created")
        if isinstance(created_raw, str):
            created_at = datetime.fromisoformat(created_raw)

        updated_at = datetime.now(timezone.utc)
        updated_raw = data.get("updated")
        if isinstance(updated_raw, str):
            updated_at = datetime.fromisoformat(updated_raw)

        # Parse status
        status = PlanStatus.PENDING
        status_raw = data.get("status")
        if isinstance(status_raw, str):
            status = PlanStatus(status_raw)

        # Parse stages
        stages_raw = data.get("stages", {})
        stages: dict[PlanStage, StageStatus] = {}
        if isinstance(stages_raw, dict):
            for key, value in stages_raw.items():
                if isinstance(key, str) and isinstance(value, str):
                    stages[PlanStage(key)] = StageStatus(value)

        # Fill in missing stages
        for stage in PlanStage:
            if stage not in stages:
                stages[stage] = StageStatus.PENDING

        # Get slug and project
        slug = data.get("slug")
        if not isinstance(slug, str):
            raise ValueError("Plan must have a slug")

        project = data.get("project")
        if not isinstance(project, str):
            raise ValueError("Plan must have a project")

        # Get optional spec_file
        spec_file: str | None = None
        spec_file_raw = data.get("spec_file")
        if isinstance(spec_file_raw, str):
            spec_file = spec_file_raw

        return cls(
            slug=slug,
            project=project,
            status=status,
            spec_file=spec_file,
            stages=stages,
            created_at=created_at,
            updated_at=updated_at,
        )

    def save(self, project_root: Path) -> Path:
        """
        Save the plan to plan.json in its directory.

        Creates the plan directory if it doesn't exist.

        Args:
            project_root: Root directory of the project

        Returns:
            Path to the saved plan.json file
        """
        import json

        plan_dir = self.get_plan_dir(project_root)
        plan_dir.mkdir(parents=True, exist_ok=True)

        plan_file = plan_dir / "plan.json"
        with plan_file.open("w") as f:
            json.dump(self.to_json_dict(), f, indent=2)
            f.write("\n")

        return plan_file

    @classmethod
    def load(cls, plan_dir: Path) -> Self:
        """
        Load a plan from its directory.

        Args:
            plan_dir: Path to the plan directory (containing plan.json)

        Returns:
            Plan instance

        Raises:
            FileNotFoundError: If plan.json doesn't exist
            ValueError: If plan.json is invalid
        """
        import json

        plan_file = plan_dir / "plan.json"
        if not plan_file.exists():
            raise FileNotFoundError(f"No plan.json found in {plan_dir}")

        with plan_file.open() as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid plan.json: expected dict, got {type(data)}")

        return cls.from_json_dict(data)
