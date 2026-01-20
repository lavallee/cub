"""
Spec data models for cub.

Defines the Stage enum and Spec model representing specification files
stored as Markdown files with YAML frontmatter. Specs are organized in
stage directories (researching, planned, completed) under the specs/ folder.
"""

from datetime import date
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Stage(str, Enum):
    """Spec lifecycle stages.

    Specs move through these stages as planning and implementation proceeds:
    - RESEARCHING: Initial exploration phase, many unknowns (-ing = active)
    - PLANNED: Plan exists, ready to stage (past = at rest)
    - STAGED: Tasks in backend, ready to build (past = at rest)
    - IMPLEMENTING: Active work happening (-ing = active)
    - RELEASED: Shipped, available for drift audit (past = at rest)

    The word forms (-ing vs past tense) indicate whether the spec is
    actively being worked on or is at rest awaiting the next action.

    Stage directories:
    - specs/researching/
    - specs/planned/
    - specs/staged/
    - specs/implementing/
    - specs/released/

    Note: COMPLETED is kept as an alias for RELEASED for backwards compatibility.
    """

    RESEARCHING = "researching"
    PLANNED = "planned"
    STAGED = "staged"
    IMPLEMENTING = "implementing"
    RELEASED = "released"
    # Backwards compatibility alias
    COMPLETED = "released"

    @classmethod
    def from_directory(cls, directory_name: str) -> "Stage":
        """Get stage from directory name.

        Args:
            directory_name: Name of the stage directory (e.g., 'researching')

        Returns:
            Corresponding Stage enum value

        Raises:
            ValueError: If directory name doesn't match any stage
        """
        # Handle 'completed' as alias for 'released'
        if directory_name == "completed":
            return cls.RELEASED

        for stage in cls:
            if stage.value == directory_name:
                return stage
        raise ValueError(f"Unknown stage directory: {directory_name}")

    @property
    def is_active(self) -> bool:
        """Check if this stage represents active work (-ing form)."""
        return self in (Stage.RESEARCHING, Stage.IMPLEMENTING)


class SpecStatus(str, Enum):
    """Spec status values from frontmatter.

    These match the status values used in SPEC-TEMPLATE.md.
    """

    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in-progress"
    PARTIAL = "partial"
    COMPLETE = "complete"
    ARCHIVED = "archived"
    # Stage-derived statuses (for backwards compatibility)
    RESEARCHING = "researching"
    PLANNED = "planned"


class SpecPriority(str, Enum):
    """Spec priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SpecComplexity(str, Enum):
    """Spec complexity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Readiness(BaseModel):
    """Readiness scoring for a spec.

    Readiness score guide:
    - 0-3: Many unknowns, major questions unanswered
    - 4-6: Core concept solid, some implementation details unclear
    - 7-8: Most questions answered, minor details remain
    - 9-10: Ready to implement, all decisions made
    """

    score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Readiness score 0-10",
    )
    blockers: list[str] = Field(
        default_factory=list,
        description="What's stopping this from being 'ready'",
    )
    questions: list[str] = Field(
        default_factory=list,
        description="Open questions that need answers",
    )
    decisions_needed: list[str] = Field(
        default_factory=list,
        description="Key decisions that need to be made",
    )
    tools_needed: list[str] = Field(
        default_factory=list,
        description="Tools we wish we had to answer questions",
    )


class Spec(BaseModel):
    """
    A specification file in the cub system.

    Specs are stored as Markdown files with YAML frontmatter in the specs/
    directory, organized by stage (researching/, planned/, completed/).

    Example:
        >>> spec = Spec(
        ...     name="my-feature",
        ...     path=Path("specs/planned/my-feature.md"),
        ...     stage=Stage.PLANNED,
        ...     status=SpecStatus.READY,
        ...     priority=SpecPriority.HIGH,
        ... )
        >>> spec.name
        'my-feature'
        >>> spec.stage
        <Stage.PLANNED: 'planned'>
    """

    # Derived from file location
    name: str = Field(..., description="Spec name (filename without .md extension)")
    path: Path = Field(..., description="Path to the spec file")
    stage: Stage = Field(..., description="Current lifecycle stage (from directory)")

    # From frontmatter
    status: SpecStatus | None = Field(
        default=None,
        description="Spec status from frontmatter",
    )
    priority: SpecPriority = Field(
        default=SpecPriority.MEDIUM,
        description="Priority level",
    )
    complexity: SpecComplexity = Field(
        default=SpecComplexity.MEDIUM,
        description="Complexity level",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of specs or systems this depends on",
    )
    blocks: list[str] = Field(
        default_factory=list,
        description="List of specs this blocks",
    )
    created: date | None = Field(
        default=None,
        description="Creation date",
    )
    updated: date | None = Field(
        default=None,
        description="Last update date",
    )
    readiness: Readiness = Field(
        default_factory=Readiness,
        description="Readiness scoring",
    )
    notes: str | None = Field(
        default=None,
        description="Additional notes from frontmatter",
    )

    # Optional title (extracted from markdown heading if present)
    title: str | None = Field(
        default=None,
        description="Spec title (from # heading in markdown)",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allow Path type
    )

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, v: Path | str) -> Path:
        """Convert string path to Path object."""
        if isinstance(v, str):
            return Path(v)
        return v

    @property
    def filename(self) -> str:
        """Get the filename (with extension)."""
        return self.path.name

    @property
    def is_ready_for_implementation(self) -> bool:
        """Check if spec is ready to be implemented.

        A spec is ready if:
        - Stage is PLANNED or STAGED
        - Readiness score is >= 7
        - Has no blockers

        Returns:
            True if spec can be implemented
        """
        return (
            self.stage in (Stage.PLANNED, Stage.STAGED)
            and self.readiness.score >= 7
            and len(self.readiness.blockers) == 0
        )

    def to_frontmatter_dict(self) -> dict[str, object]:
        """
        Convert spec metadata to frontmatter dictionary for serialization.

        Returns:
            Dictionary suitable for YAML frontmatter representation
        """
        frontmatter: dict[str, object] = {}

        if self.status:
            frontmatter["status"] = self.status.value
        frontmatter["priority"] = self.priority.value
        frontmatter["complexity"] = self.complexity.value

        if self.dependencies:
            frontmatter["dependencies"] = self.dependencies
        else:
            frontmatter["dependencies"] = []

        if self.blocks:
            frontmatter["blocks"] = self.blocks

        if self.created:
            frontmatter["created"] = self.created.isoformat()
        if self.updated:
            frontmatter["updated"] = self.updated.isoformat()

        # Include readiness if it has content
        readiness_dict: dict[str, object] = {"score": self.readiness.score}
        if self.readiness.blockers:
            readiness_dict["blockers"] = self.readiness.blockers
        if self.readiness.questions:
            readiness_dict["questions"] = self.readiness.questions
        if self.readiness.decisions_needed:
            readiness_dict["decisions_needed"] = self.readiness.decisions_needed
        if self.readiness.tools_needed:
            readiness_dict["tools_needed"] = self.readiness.tools_needed
        frontmatter["readiness"] = readiness_dict

        if self.notes:
            frontmatter["notes"] = self.notes

        return frontmatter

    @classmethod
    def from_frontmatter_dict(
        cls,
        data: dict[str, object],
        name: str,
        path: Path,
        stage: Stage,
        title: str | None = None,
    ) -> "Spec":
        """
        Create a Spec instance from frontmatter dictionary.

        Args:
            data: Dictionary parsed from YAML frontmatter
            name: Spec name (filename without extension)
            path: Path to the spec file
            stage: Stage derived from directory location
            title: Optional title from markdown heading

        Returns:
            Spec instance
        """
        # Parse status
        status: SpecStatus | None = None
        status_raw = data.get("status")
        if isinstance(status_raw, str):
            try:
                status = SpecStatus(status_raw)
            except ValueError:
                # Unknown status, leave as None
                pass

        # Parse priority
        priority = SpecPriority.MEDIUM
        priority_raw = data.get("priority")
        if isinstance(priority_raw, str):
            try:
                priority = SpecPriority(priority_raw)
            except ValueError:
                pass

        # Parse complexity
        complexity = SpecComplexity.MEDIUM
        complexity_raw = data.get("complexity")
        if isinstance(complexity_raw, str):
            try:
                complexity = SpecComplexity(complexity_raw)
            except ValueError:
                pass

        # Parse dependencies
        dependencies: list[str] = []
        deps_raw = data.get("dependencies", [])
        if isinstance(deps_raw, list):
            dependencies = [str(d) for d in deps_raw]

        # Parse blocks
        blocks: list[str] = []
        blocks_raw = data.get("blocks", [])
        if isinstance(blocks_raw, list):
            blocks = [str(b) for b in blocks_raw]

        # Parse dates
        created: date | None = None
        created_raw = data.get("created")
        if isinstance(created_raw, str):
            try:
                created = date.fromisoformat(created_raw)
            except ValueError:
                pass
        elif isinstance(created_raw, date):
            created = created_raw

        updated: date | None = None
        updated_raw = data.get("updated")
        if isinstance(updated_raw, str):
            try:
                updated = date.fromisoformat(updated_raw)
            except ValueError:
                pass
        elif isinstance(updated_raw, date):
            updated = updated_raw

        # Parse readiness
        readiness = Readiness()
        readiness_raw = data.get("readiness", {})
        if isinstance(readiness_raw, dict):
            readiness = Readiness(
                score=int(readiness_raw.get("score", 0)),
                blockers=list(readiness_raw.get("blockers", [])),
                questions=list(readiness_raw.get("questions", [])),
                decisions_needed=list(readiness_raw.get("decisions_needed", [])),
                tools_needed=list(readiness_raw.get("tools_needed", [])),
            )

        # Parse notes
        notes: str | None = None
        notes_raw = data.get("notes")
        if isinstance(notes_raw, str):
            notes = notes_raw

        return cls(
            name=name,
            path=path,
            stage=stage,
            status=status,
            priority=priority,
            complexity=complexity,
            dependencies=dependencies,
            blocks=blocks,
            created=created,
            updated=updated,
            readiness=readiness,
            notes=notes,
            title=title,
        )
