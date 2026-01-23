"""
Planning context for cub.

Provides the PlanContext class that holds shared state and resources
for planning pipeline stages (orient, architect, itemize). This enables
the stages to share information about the project, spec being planned,
and accumulated outputs.

Example:
    >>> ctx = PlanContext.create(
    ...     project_root=Path("."),
    ...     spec_path=Path("specs/researching/my-feature.md"),
    ...     project="cub",
    ... )
    >>> ctx.plan.slug
    'my-feature'
    >>> ctx.spec.name
    'my-feature'
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, computed_field

from cub.core.plan.models import Plan, PlanStage, PlanStatus

if TYPE_CHECKING:
    pass


class OrientDepth(str):
    """Depth level for orient phase.

    - LIGHT: Quick coherence check, minimal questions
    - STANDARD: Full review with all standard questions
    - DEEP: Extended review with market analysis and edge cases
    """

    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"


class PlanContextError(Exception):
    """Base exception for plan context errors."""

    pass


class SpecNotFoundError(PlanContextError):
    """Raised when a spec file cannot be found."""

    pass


class PlanExistsError(PlanContextError):
    """Raised when trying to create a plan that already exists."""

    pass


class PlanContext(BaseModel):
    """
    Shared context for planning pipeline stages.

    PlanContext holds all the information needed by orient, architect, and
    itemize stages:
    - Project configuration (root path, project identifier)
    - Current plan being worked on
    - Source spec (if planning from a spec file)
    - Stage-specific configuration (depth, mindset, etc.)

    The context is created at the start of a planning session and passed
    through each stage. It accumulates outputs as stages complete.

    Example:
        >>> ctx = PlanContext.create(
        ...     project_root=Path("."),
        ...     spec_path=Path("specs/researching/my-feature.md"),
        ...     project="cub",
        ... )
        >>> # Run orient stage
        >>> orient_result = await run_orient(ctx)
        >>> # Context now has orientation data
        >>> ctx.plan.stages[PlanStage.ORIENT]
        <StageStatus.COMPLETE: 'complete'>
    """

    # Project configuration
    project_root: Path = Field(
        ...,
        description="Root directory of the project",
    )
    project: str = Field(
        ...,
        min_length=1,
        description="Project identifier (e.g., 'cub')",
    )

    # Plan being worked on
    plan: Plan = Field(
        ...,
        description="The plan being created or updated",
    )

    # Source spec (optional - plans can exist without specs)
    spec_path: Path | None = Field(
        default=None,
        description="Path to the source spec file",
    )

    # Stage-specific configuration
    depth: str = Field(
        default=OrientDepth.STANDARD,
        description="Depth level for orient phase (light/standard/deep)",
    )
    verbose: bool = Field(
        default=False,
        description="Whether to show verbose output",
    )

    # Timestamps
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this planning session started",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # Allow Path type
    )

    @computed_field
    @property
    def plan_dir(self) -> Path:
        """Get the directory where plan artifacts are stored."""
        return self.plan.get_plan_dir(self.project_root)

    @computed_field
    @property
    def has_spec(self) -> bool:
        """Check if this planning session has a source spec."""
        return self.spec_path is not None

    @computed_field
    @property
    def orientation_path(self) -> Path:
        """Path to the orientation.md output file."""
        return self.plan.get_stage_output_path(PlanStage.ORIENT, self.project_root)

    @computed_field
    @property
    def architecture_path(self) -> Path:
        """Path to the architecture.md output file."""
        return self.plan.get_stage_output_path(PlanStage.ARCHITECT, self.project_root)

    @computed_field
    @property
    def itemized_plan_path(self) -> Path:
        """Path to the itemized-plan.md output file."""
        return self.plan.get_stage_output_path(PlanStage.ITEMIZE, self.project_root)

    def get_specs_root(self) -> Path:
        """Get the specs root directory."""
        return self.project_root / "specs"

    def get_system_plan_path(self) -> Path:
        """Get the path to .cub/SYSTEM-PLAN.md constitutional memory."""
        return self.project_root / ".cub" / "SYSTEM-PLAN.md"

    def get_agent_instructions_path(self) -> Path:
        """Get the path to CLAUDE.md / AGENT.md instructions."""
        # Try several common names
        for name in ["CLAUDE.md", "AGENT.md", "AGENTS.md"]:
            path = self.project_root / name
            if path.exists():
                return path
        # Default to CLAUDE.md even if it doesn't exist
        return self.project_root / "CLAUDE.md"

    def read_spec_content(self) -> str:
        """
        Read the content of the source spec file.

        Returns:
            Spec file content as a string.

        Raises:
            SpecNotFoundError: If no spec is associated or file doesn't exist or cannot be read.
        """
        if self.spec_path is None:
            raise SpecNotFoundError("No spec associated with this plan")

        if not self.spec_path.exists():
            raise SpecNotFoundError(f"Spec file not found: {self.spec_path}")

        try:
            content = self.spec_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise SpecNotFoundError(
                f"Spec file has invalid UTF-8 encoding: {self.spec_path}: {e}"
            ) from e
        except OSError as e:
            raise SpecNotFoundError(
                f"Cannot read spec file: {self.spec_path}: {e}"
            ) from e

        if not content.strip():
            raise SpecNotFoundError(f"Spec file is empty: {self.spec_path}")

        return content

    def read_system_plan(self) -> str | None:
        """
        Read the SYSTEM-PLAN.md constitutional memory if it exists.

        Returns:
            Content of SYSTEM-PLAN.md, or None if file doesn't exist or cannot be read.
        """
        path = self.get_system_plan_path()
        if not path.exists():
            return None

        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Silently fail for non-critical file reads
            return None

    def read_agent_instructions(self) -> str | None:
        """
        Read the CLAUDE.md / AGENT.md instructions if they exist.

        Returns:
            Content of agent instructions, or None if file doesn't exist or cannot be read.
        """
        path = self.get_agent_instructions_path()
        if not path.exists():
            return None

        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Silently fail for non-critical file reads
            return None

    def ensure_plan_dir(self) -> Path:
        """
        Ensure the plan directory exists.

        Returns:
            Path to the plan directory.

        Raises:
            OSError: If directory cannot be created.
        """
        try:
            self.plan_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise OSError(f"Cannot create plan directory {self.plan_dir}: {e}") from e
        return self.plan_dir

    def save_plan(self) -> Path:
        """
        Save the plan metadata to plan.json.

        Returns:
            Path to the saved plan.json file.
        """
        return self.plan.save(self.project_root)

    @classmethod
    def create(
        cls,
        project_root: Path,
        project: str,
        spec_path: Path | None = None,
        slug: str | None = None,
        depth: str = OrientDepth.STANDARD,
        verbose: bool = False,
    ) -> PlanContext:
        """
        Create a new PlanContext for a planning session.

        This factory method handles:
        - Slug generation from spec path if not provided
        - Slug collision detection (appending _alt_[a-z] suffix)
        - Plan initialization with proper defaults

        Args:
            project_root: Root directory of the project.
            project: Project identifier (e.g., 'cub').
            spec_path: Optional path to the source spec file.
            slug: Optional explicit plan slug. If not provided, derived from
                spec filename or timestamp.
            depth: Orient phase depth level.
            verbose: Whether to show verbose output.

        Returns:
            New PlanContext ready for planning.

        Raises:
            PlanExistsError: If a plan with the slug already exists and all
                alternative suffixes are exhausted.
        """
        # Derive slug from spec path if not provided
        if slug is None:
            if spec_path is not None:
                # Use spec filename without extension
                slug = spec_path.stem
            else:
                # Use timestamp-based slug
                slug = f"plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Check for collision and find available slug
        plans_dir = project_root / "plans"
        final_slug = _find_available_slug(plans_dir, slug)

        # Create the plan
        plan = Plan(
            slug=final_slug,
            project=project,
            status=PlanStatus.PENDING,
            spec_file=spec_path.name if spec_path else None,
        )

        return cls(
            project_root=project_root,
            project=project,
            plan=plan,
            spec_path=spec_path,
            depth=depth,
            verbose=verbose,
        )

    @classmethod
    def load(
        cls,
        plan_dir: Path,
        project_root: Path | None = None,
    ) -> PlanContext:
        """
        Load an existing plan into a PlanContext.

        Args:
            plan_dir: Path to the plan directory containing plan.json.
            project_root: Project root (inferred from plan_dir if not provided).

        Returns:
            PlanContext loaded from the existing plan.

        Raises:
            FileNotFoundError: If plan.json doesn't exist.
        """
        # Infer project root if not provided (plan_dir is usually at plans/{slug})
        if project_root is None:
            # Go up two levels: plans/{slug} -> plans -> project_root
            project_root = plan_dir.parent.parent

        # Load the plan
        plan = Plan.load(plan_dir)

        # Find the spec file if one is linked
        spec_path: Path | None = None
        if plan.spec_file:
            specs_root = project_root / "specs"
            spec_path = _find_spec_by_name(specs_root, plan.spec_file)

        return cls(
            project_root=project_root,
            project=plan.project,
            plan=plan,
            spec_path=spec_path,
        )


def _find_available_slug(plans_dir: Path, base_slug: str) -> str:
    """
    Find an available slug, appending _alt_[a-z] if base exists.

    Args:
        plans_dir: Directory containing plans.
        base_slug: The desired base slug.

    Returns:
        An available slug (either base_slug or base_slug_alt_X).

    Raises:
        PlanExistsError: If all alternatives exhausted (a-z all taken).
    """
    # If plans directory doesn't exist yet, base slug is available
    if not plans_dir.exists():
        return base_slug

    # If base slug is available, use it
    if not (plans_dir / base_slug).exists():
        return base_slug

    # Try _alt_a through _alt_z
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        alt_slug = f"{base_slug}_alt_{suffix}"
        if not (plans_dir / alt_slug).exists():
            return alt_slug

    raise PlanExistsError(
        f"Plan '{base_slug}' exists and all alternatives (_alt_a through _alt_z) "
        "are taken. Please use --slug to specify a different name."
    )


def _find_spec_by_name(specs_root: Path, spec_file: str) -> Path | None:
    """
    Find a spec file by searching all stage directories.

    Args:
        specs_root: Root specs directory.
        spec_file: Spec filename to find.

    Returns:
        Path to the spec file, or None if not found.
    """
    if not specs_root.exists():
        return None

    # Search each stage directory
    stage_dirs = ["researching", "planned", "staged", "implementing", "released"]
    for stage_dir in stage_dirs:
        spec_path = specs_root / stage_dir / spec_file
        if spec_path.exists():
            return spec_path

    return None
