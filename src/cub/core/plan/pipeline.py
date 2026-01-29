"""
Pipeline orchestration for cub plan.

Provides the PlanPipeline class that runs the full planning pipeline:
orient -> architect -> itemize in sequence with spec lifecycle management.

The pipeline:
1. Creates a new plan from a spec file (or loads an existing plan)
2. Runs each stage in sequence, stopping if a stage fails
3. Manages spec lifecycle transitions (researching -> planned)
4. Provides progress callbacks for UI integration

Example:
    >>> from cub.core.plan.pipeline import PlanPipeline, PipelineConfig
    >>> from pathlib import Path
    >>>
    >>> config = PipelineConfig(
    ...     spec_path=Path("specs/researching/my-feature.md"),
    ...     mindset="mvp",
    ...     scale="team",
    ... )
    >>> pipeline = PlanPipeline(Path("."), config)
    >>> result = pipeline.run()
    >>> result.success
    True
    >>> result.plan.is_complete
    True
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from cub.core.plan.architect import ArchitectResult, ArchitectStage, ArchitectStageError
from cub.core.plan.context import (
    OrientDepth,
    PlanContext,
    PlanContextError,
    PlanExistsError,
)
from cub.core.plan.itemize import ItemizeResult, ItemizeStage, ItemizeStageError
from cub.core.plan.models import Plan, PlanStage, SpecStage, StageStatus
from cub.core.plan.orient import OrientResult, OrientStage, OrientStageError

if TYPE_CHECKING:
    pass


class ProgressCallback(Protocol):
    """Protocol for pipeline progress callbacks."""

    def __call__(
        self,
        stage: PlanStage,
        status: str,
        message: str,
    ) -> None:
        """
        Called when pipeline progress is made.

        Args:
            stage: The current stage (ORIENT, ARCHITECT, ITEMIZE).
            status: Status string ('starting', 'complete', 'error').
            message: Human-readable message about the progress.
        """
        ...


def _default_progress_callback(
    stage: PlanStage,
    status: str,
    message: str,
) -> None:
    """Default no-op progress callback."""
    pass


@dataclass
class PipelineConfig:
    """Configuration for the planning pipeline.

    Attributes:
        spec_path: Path to the source spec file.
        slug: Optional explicit plan slug. If not provided, derived from spec.
        depth: Orient phase depth level.
        mindset: Architect phase mindset (prototype/mvp/production/enterprise).
        scale: Architect phase scale (personal/team/product/internet-scale).
        verbose: Whether to show verbose output.
        move_spec: Whether to move spec on plan completion.
        continue_from: Optional plan directory to continue from.
        non_interactive: Whether to run without user interaction (for CI/automation).
    """

    spec_path: Path | None = None
    slug: str | None = None
    depth: str = OrientDepth.STANDARD
    mindset: str = "mvp"
    scale: str = "team"
    verbose: bool = False
    move_spec: bool = True
    continue_from: Path | None = None
    non_interactive: bool = False


@dataclass
class StageResult:
    """Result of a single stage execution."""

    stage: PlanStage
    success: bool
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass
class PipelineResult:
    """Result of running the full planning pipeline.

    Attributes:
        success: Whether the pipeline completed successfully.
        plan: The Plan object (may be incomplete if pipeline failed).
        plan_dir: Path to the plan directory.
        stage_results: Results for each stage attempted.
        orient_result: Result from orient stage (if completed).
        architect_result: Result from architect stage (if completed).
        itemize_result: Result from itemize stage (if completed).
        spec_moved: Whether the spec was moved to a new location.
        error: Error message if pipeline failed.
        started_at: When the pipeline started.
        completed_at: When the pipeline completed.
    """

    success: bool
    plan: Plan
    plan_dir: Path
    stage_results: list[StageResult] = field(default_factory=list)
    orient_result: OrientResult | None = None
    architect_result: ArchitectResult | None = None
    itemize_result: ItemizeResult | None = None
    spec_moved: bool = False
    spec_new_path: Path | None = None
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def duration_seconds(self) -> float:
        """Get the total duration of the pipeline in seconds."""
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def stages_completed(self) -> list[PlanStage]:
        """Get list of successfully completed stages."""
        return [r.stage for r in self.stage_results if r.success]


class PipelineError(Exception):
    """Base exception for pipeline errors."""

    pass


class PipelineConfigError(PipelineError):
    """Raised when pipeline configuration is invalid."""

    pass


class PipelineStageError(PipelineError):
    """Raised when a pipeline stage fails."""

    def __init__(self, stage: PlanStage, message: str) -> None:
        self.stage = stage
        super().__init__(f"{stage.value} stage failed: {message}")


class PlanPipeline:
    """
    Orchestrates the full planning pipeline.

    The pipeline runs orient -> architect -> itemize in sequence,
    managing plan state and spec lifecycle transitions.

    Example:
        >>> config = PipelineConfig(
        ...     spec_path=Path("specs/researching/my-feature.md"),
        ... )
        >>> pipeline = PlanPipeline(Path("."), config)
        >>> result = pipeline.run()
        >>> if result.success:
        ...     print(f"Plan complete: {result.plan_dir}")
        ... else:
        ...     print(f"Pipeline failed: {result.error}")

    Attributes:
        project_root: Root directory of the project.
        config: Pipeline configuration.
        on_progress: Callback for progress updates.
    """

    def __init__(
        self,
        project_root: Path,
        config: PipelineConfig,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """
        Initialize the planning pipeline.

        Args:
            project_root: Root directory of the project.
            config: Pipeline configuration.
            on_progress: Optional callback for progress updates.

        Raises:
            PipelineConfigError: If configuration is invalid.
        """
        self.project_root = project_root.resolve()
        self.config = config
        self.on_progress: Callable[[PlanStage, str, str], None] = (
            on_progress or _default_progress_callback
        )

        # Validate configuration
        self._validate_config()

    def _validate_config(self) -> None:
        """
        Validate pipeline configuration.

        Raises:
            PipelineConfigError: If configuration is invalid.
        """
        # Must have either spec_path or continue_from
        if self.config.spec_path is None and self.config.continue_from is None:
            raise PipelineConfigError(
                "Pipeline requires either spec_path or continue_from"
            )

        # If continuing, plan must exist
        if self.config.continue_from is not None:
            plan_json = self.config.continue_from / "plan.json"
            if not plan_json.exists():
                raise PipelineConfigError(
                    f"Cannot continue: plan.json not found in {self.config.continue_from}"
                )

        # Validate depth
        valid_depths = [OrientDepth.LIGHT, OrientDepth.STANDARD, OrientDepth.DEEP]
        if self.config.depth.lower() not in valid_depths:
            raise PipelineConfigError(
                f"Invalid depth: {self.config.depth}. "
                f"Valid options: {', '.join(valid_depths)}"
            )

        # Validate mindset
        valid_mindsets = ["prototype", "mvp", "production", "enterprise"]
        if self.config.mindset.lower() not in valid_mindsets:
            raise PipelineConfigError(
                f"Invalid mindset: {self.config.mindset}. "
                f"Valid options: {', '.join(valid_mindsets)}"
            )

        # Validate scale
        valid_scales = ["personal", "team", "product", "internet-scale"]
        if self.config.scale.lower() not in valid_scales:
            raise PipelineConfigError(
                f"Invalid scale: {self.config.scale}. "
                f"Valid options: {', '.join(valid_scales)}"
            )

    def _get_project_identifier(self) -> str:
        """
        Get the project identifier from the project root.

        Returns:
            Project identifier string.
        """
        import re

        # Try pyproject.toml
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                return match.group(1).lower().replace("_", "-")

        # Try package.json
        package_json = self.project_root / "package.json"
        if package_json.exists():
            import json

            try:
                data = json.loads(package_json.read_text())
                if "name" in data:
                    return str(data["name"]).lower().replace("_", "-")
            except (json.JSONDecodeError, KeyError):
                pass

        # Fall back to directory name
        return self.project_root.name.lower().replace("_", "-")

    def _create_or_load_context(self) -> PlanContext:
        """
        Create a new plan context or load an existing one.

        Returns:
            PlanContext for the pipeline.

        Raises:
            PipelineError: If context cannot be created or loaded.
        """
        try:
            if self.config.continue_from is not None:
                # Load existing plan
                return PlanContext.load(
                    self.config.continue_from,
                    self.project_root,
                )
            else:
                # Create new plan
                project = self._get_project_identifier()
                return PlanContext.create(
                    project_root=self.project_root,
                    project=project,
                    spec_path=self.config.spec_path,
                    slug=self.config.slug,
                    depth=self.config.depth.lower(),
                    verbose=self.config.verbose,
                )
        except PlanExistsError as e:
            raise PipelineError(str(e)) from e
        except PlanContextError as e:
            raise PipelineError(f"Failed to create plan context: {e}") from e
        except FileNotFoundError as e:
            raise PipelineError(f"Failed to load plan: {e}") from e

    def _should_run_stage(self, ctx: PlanContext, stage: PlanStage) -> bool:
        """
        Check if a stage should be run.

        Args:
            ctx: The plan context.
            stage: The stage to check.

        Returns:
            True if the stage should be run.
        """
        return ctx.plan.stages[stage] != StageStatus.COMPLETE

    def _run_orient(self, ctx: PlanContext) -> OrientResult:
        """
        Run the orient stage.

        Args:
            ctx: The plan context.

        Returns:
            OrientResult from the stage.

        Raises:
            PipelineStageError: If the stage fails.
        """
        self.on_progress(PlanStage.ORIENT, "starting", "Starting orient phase...")

        try:
            stage = OrientStage(ctx)
            result = stage.run(non_interactive=self.config.non_interactive)
            self.on_progress(
                PlanStage.ORIENT,
                "complete",
                f"Orient complete: {result.output_path.name}",
            )
            return result
        except OrientStageError as e:
            self.on_progress(PlanStage.ORIENT, "error", str(e))
            raise PipelineStageError(PlanStage.ORIENT, str(e)) from e

    def _run_architect(self, ctx: PlanContext) -> ArchitectResult:
        """
        Run the architect stage.

        Args:
            ctx: The plan context.

        Returns:
            ArchitectResult from the stage.

        Raises:
            PipelineStageError: If the stage fails.
        """
        self.on_progress(PlanStage.ARCHITECT, "starting", "Starting architect phase...")

        try:
            stage = ArchitectStage(
                ctx,
                mindset=self.config.mindset.lower(),
                scale=self.config.scale.lower(),
            )
            result = stage.run(non_interactive=self.config.non_interactive)
            self.on_progress(
                PlanStage.ARCHITECT,
                "complete",
                f"Architect complete: {result.output_path.name}",
            )
            return result
        except ArchitectStageError as e:
            self.on_progress(PlanStage.ARCHITECT, "error", str(e))
            raise PipelineStageError(PlanStage.ARCHITECT, str(e)) from e

    def _run_itemize(self, ctx: PlanContext) -> ItemizeResult:
        """
        Run the itemize stage.

        Args:
            ctx: The plan context.

        Returns:
            ItemizeResult from the stage.

        Raises:
            PipelineStageError: If the stage fails.
        """
        self.on_progress(PlanStage.ITEMIZE, "starting", "Starting itemize phase...")

        try:
            stage = ItemizeStage(ctx)
            result = stage.run(non_interactive=self.config.non_interactive)
            self.on_progress(
                PlanStage.ITEMIZE,
                "complete",
                f"Itemize complete: {result.output_path.name}",
            )
            return result
        except ItemizeStageError as e:
            self.on_progress(PlanStage.ITEMIZE, "error", str(e))
            raise PipelineStageError(PlanStage.ITEMIZE, str(e)) from e

    def _move_spec_to_planned(self, ctx: PlanContext) -> Path | None:
        """
        Move the spec from researching/ to planned/.

        This is called when the full pipeline completes successfully.

        Args:
            ctx: The plan context.

        Returns:
            New path of the spec, or None if not moved.
        """
        if not ctx.has_spec or ctx.spec_path is None:
            return None

        spec_path = ctx.spec_path

        # Check if spec is in researching/
        specs_root = ctx.get_specs_root()
        researching_dir = specs_root / "researching"

        try:
            relative = spec_path.relative_to(researching_dir)
        except ValueError:
            # Spec is not in researching/, don't move
            return None

        # Move to planned/
        planned_dir = specs_root / SpecStage.PLANNED.value
        planned_dir.mkdir(parents=True, exist_ok=True)
        new_path = planned_dir / relative

        # Ensure parent directories exist
        new_path.parent.mkdir(parents=True, exist_ok=True)

        # Move the file
        shutil.move(str(spec_path), str(new_path))

        return new_path

    def run(self) -> PipelineResult:
        """
        Run the full planning pipeline.

        Executes orient -> architect -> itemize in sequence.
        Stages that are already complete are skipped.
        If a stage fails, the pipeline stops and returns partial results.

        Returns:
            PipelineResult with success status and stage results.
        """
        started_at = datetime.now(timezone.utc)
        stage_results: list[StageResult] = []
        orient_result: OrientResult | None = None
        architect_result: ArchitectResult | None = None
        itemize_result: ItemizeResult | None = None
        error: str | None = None
        spec_moved = False
        spec_new_path: Path | None = None

        # Create or load context
        try:
            ctx = self._create_or_load_context()
        except PipelineError as e:
            return PipelineResult(
                success=False,
                plan=Plan(slug="error", project="unknown"),
                plan_dir=self.project_root / "plans" / "error",
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        # Persist plan.json immediately so a checkpoint exists before any stage runs
        ctx.save_plan()

        # Run orient stage
        if self._should_run_stage(ctx, PlanStage.ORIENT):
            stage_started = datetime.now(timezone.utc)
            try:
                orient_result = self._run_orient(ctx)
                duration = (datetime.now(timezone.utc) - stage_started).total_seconds()
                stage_results.append(
                    StageResult(
                        stage=PlanStage.ORIENT,
                        success=True,
                        duration_seconds=duration,
                    )
                )
            except PipelineStageError as e:
                duration = (datetime.now(timezone.utc) - stage_started).total_seconds()
                stage_results.append(
                    StageResult(
                        stage=PlanStage.ORIENT,
                        success=False,
                        error=str(e),
                        duration_seconds=duration,
                    )
                )
                return PipelineResult(
                    success=False,
                    plan=ctx.plan,
                    plan_dir=ctx.plan_dir,
                    stage_results=stage_results,
                    error=str(e),
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )

        # Run architect stage
        if self._should_run_stage(ctx, PlanStage.ARCHITECT):
            stage_started = datetime.now(timezone.utc)
            try:
                architect_result = self._run_architect(ctx)
                duration = (datetime.now(timezone.utc) - stage_started).total_seconds()
                stage_results.append(
                    StageResult(
                        stage=PlanStage.ARCHITECT,
                        success=True,
                        duration_seconds=duration,
                    )
                )
            except PipelineStageError as e:
                duration = (datetime.now(timezone.utc) - stage_started).total_seconds()
                stage_results.append(
                    StageResult(
                        stage=PlanStage.ARCHITECT,
                        success=False,
                        error=str(e),
                        duration_seconds=duration,
                    )
                )
                return PipelineResult(
                    success=False,
                    plan=ctx.plan,
                    plan_dir=ctx.plan_dir,
                    stage_results=stage_results,
                    orient_result=orient_result,
                    error=str(e),
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )

        # Run itemize stage
        if self._should_run_stage(ctx, PlanStage.ITEMIZE):
            stage_started = datetime.now(timezone.utc)
            try:
                itemize_result = self._run_itemize(ctx)
                duration = (datetime.now(timezone.utc) - stage_started).total_seconds()
                stage_results.append(
                    StageResult(
                        stage=PlanStage.ITEMIZE,
                        success=True,
                        duration_seconds=duration,
                    )
                )
            except PipelineStageError as e:
                duration = (datetime.now(timezone.utc) - stage_started).total_seconds()
                stage_results.append(
                    StageResult(
                        stage=PlanStage.ITEMIZE,
                        success=False,
                        error=str(e),
                        duration_seconds=duration,
                    )
                )
                return PipelineResult(
                    success=False,
                    plan=ctx.plan,
                    plan_dir=ctx.plan_dir,
                    stage_results=stage_results,
                    orient_result=orient_result,
                    architect_result=architect_result,
                    error=str(e),
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )

        # Move spec to planned/ if configured
        if self.config.move_spec and ctx.plan.is_complete:
            try:
                spec_new_path = self._move_spec_to_planned(ctx)
                if spec_new_path is not None:
                    spec_moved = True
            except OSError as e:
                # Non-fatal, just report in result
                error = f"Warning: Failed to move spec: {e}"

        completed_at = datetime.now(timezone.utc)

        return PipelineResult(
            success=True,
            plan=ctx.plan,
            plan_dir=ctx.plan_dir,
            stage_results=stage_results,
            orient_result=orient_result,
            architect_result=architect_result,
            itemize_result=itemize_result,
            spec_moved=spec_moved,
            spec_new_path=spec_new_path,
            error=error,
            started_at=started_at,
            completed_at=completed_at,
        )

    def run_single_stage(self, stage: PlanStage) -> PipelineResult:
        """
        Run a single stage of the pipeline.

        This is useful for resuming failed pipelines or re-running
        a specific stage.

        Args:
            stage: The stage to run.

        Returns:
            PipelineResult with the stage result.
        """
        started_at = datetime.now(timezone.utc)
        stage_results: list[StageResult] = []

        # Create or load context
        try:
            ctx = self._create_or_load_context()
        except PipelineError as e:
            return PipelineResult(
                success=False,
                plan=Plan(slug="error", project="unknown"),
                plan_dir=self.project_root / "plans" / "error",
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        # Persist plan.json immediately so a checkpoint exists before any stage runs
        ctx.save_plan()

        # Run the requested stage
        stage_started = datetime.now(timezone.utc)
        orient_result: OrientResult | None = None
        architect_result: ArchitectResult | None = None
        itemize_result: ItemizeResult | None = None

        try:
            if stage == PlanStage.ORIENT:
                orient_result = self._run_orient(ctx)
            elif stage == PlanStage.ARCHITECT:
                architect_result = self._run_architect(ctx)
            elif stage == PlanStage.ITEMIZE:
                itemize_result = self._run_itemize(ctx)

            duration = (datetime.now(timezone.utc) - stage_started).total_seconds()
            stage_results.append(
                StageResult(
                    stage=stage,
                    success=True,
                    duration_seconds=duration,
                )
            )

            return PipelineResult(
                success=True,
                plan=ctx.plan,
                plan_dir=ctx.plan_dir,
                stage_results=stage_results,
                orient_result=orient_result,
                architect_result=architect_result,
                itemize_result=itemize_result,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        except PipelineStageError as e:
            duration = (datetime.now(timezone.utc) - stage_started).total_seconds()
            stage_results.append(
                StageResult(
                    stage=stage,
                    success=False,
                    error=str(e),
                    duration_seconds=duration,
                )
            )
            return PipelineResult(
                success=False,
                plan=ctx.plan,
                plan_dir=ctx.plan_dir,
                stage_results=stage_results,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )


def run_pipeline(
    project_root: Path,
    spec_path: Path,
    slug: str | None = None,
    depth: str = OrientDepth.STANDARD,
    mindset: str = "mvp",
    scale: str = "team",
    verbose: bool = False,
    move_spec: bool = True,
    non_interactive: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """
    Convenience function to run the full planning pipeline.

    Args:
        project_root: Root directory of the project.
        spec_path: Path to the source spec file.
        slug: Optional explicit plan slug.
        depth: Orient phase depth level.
        mindset: Architect phase mindset.
        scale: Architect phase scale.
        verbose: Whether to show verbose output.
        move_spec: Whether to move spec on plan completion.
        non_interactive: Whether to run without user interaction.
        on_progress: Optional callback for progress updates.

    Returns:
        PipelineResult with success status and stage results.
    """
    config = PipelineConfig(
        spec_path=spec_path,
        slug=slug,
        depth=depth,
        mindset=mindset,
        scale=scale,
        verbose=verbose,
        move_spec=move_spec,
        non_interactive=non_interactive,
    )
    pipeline = PlanPipeline(project_root, config, on_progress)
    return pipeline.run()


def continue_pipeline(
    project_root: Path,
    plan_dir: Path,
    mindset: str = "mvp",
    scale: str = "team",
    verbose: bool = False,
    move_spec: bool = True,
    non_interactive: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """
    Convenience function to continue an existing pipeline.

    Args:
        project_root: Root directory of the project.
        plan_dir: Path to the existing plan directory.
        mindset: Architect phase mindset.
        scale: Architect phase scale.
        verbose: Whether to show verbose output.
        move_spec: Whether to move spec on plan completion.
        non_interactive: Whether to run without user interaction.
        on_progress: Optional callback for progress updates.

    Returns:
        PipelineResult with success status and stage results.
    """
    config = PipelineConfig(
        continue_from=plan_dir,
        mindset=mindset,
        scale=scale,
        verbose=verbose,
        move_spec=move_spec,
        non_interactive=non_interactive,
    )
    pipeline = PlanPipeline(project_root, config, on_progress)
    return pipeline.run()


# ==============================================================================
# Step Detection
# ==============================================================================


class StepDetectionStatus(str, Enum):
    """Status of a detected pipeline step."""

    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    INCOMPLETE = "incomplete"
    CORRUPTED = "corrupted"


@dataclass
class StepInfo:
    """Information about a single pipeline step's completion state.

    Attributes:
        stage: The plan stage this info is about.
        status: Detected status of the step.
        artifact_path: Path to the expected output artifact.
        artifact_exists: Whether the artifact file exists on disk.
        artifact_size: Size of the artifact in bytes, or 0 if missing.
        plan_status: Status recorded in plan.json for this stage, if any.
        detail: Human-readable detail about the step's state.
    """

    stage: PlanStage
    status: StepDetectionStatus
    artifact_path: Path
    artifact_exists: bool
    artifact_size: int = 0
    plan_status: StageStatus | None = None
    detail: str = ""


@dataclass
class PipelineStepSummary:
    """Summary of all pipeline steps for a plan.

    Attributes:
        plan_slug: The plan slug being inspected.
        plan_dir: Path to the plan directory.
        steps: Ordered list of step information (orient, architect, itemize).
        plan_exists: Whether a plan.json was found.
        next_step: The next step that should be run, or None if all complete.
        is_staged: Whether the plan has already been staged to a task backend.
    """

    plan_slug: str
    plan_dir: Path
    steps: list[StepInfo]
    plan_exists: bool
    next_step: PlanStage | None
    is_staged: bool = False

    @property
    def all_complete(self) -> bool:
        """Check if all steps are complete."""
        return all(s.status == StepDetectionStatus.COMPLETE for s in self.steps)

    @property
    def completed_steps(self) -> list[StepInfo]:
        """Get list of completed steps."""
        return [s for s in self.steps if s.status == StepDetectionStatus.COMPLETE]

    @property
    def has_corruption(self) -> bool:
        """Check if any step has corrupted artifacts."""
        return any(s.status == StepDetectionStatus.CORRUPTED for s in self.steps)


# Minimum artifact sizes (bytes) to consider a file as having real content
# vs. being a stub or corrupted output.
_MIN_ARTIFACT_SIZES: dict[PlanStage, int] = {
    PlanStage.ORIENT: 100,
    PlanStage.ARCHITECT: 100,
    PlanStage.ITEMIZE: 100,
}


def detect_pipeline_steps(
    plan_dir: Path,
    project_root: Path | None = None,
) -> PipelineStepSummary:
    """
    Detect the completion state of pipeline steps for a plan.

    Examines both plan.json metadata and artifact files on disk to determine
    which steps are complete, in-progress, incomplete, or corrupted. Handles
    edge cases like:
    - plan.json says complete but artifact file is missing
    - Artifact file exists but plan.json says pending (partial completion)
    - Artifact file exists but is suspiciously small (corrupted)
    - Missing plan.json entirely

    Args:
        plan_dir: Path to the plan directory (containing plan.json).
        project_root: Project root, inferred from plan_dir if not provided.

    Returns:
        PipelineStepSummary with detailed step information.
    """
    if project_root is None:
        project_root = plan_dir.parent.parent

    plan_slug = plan_dir.name
    plan_exists = (plan_dir / "plan.json").exists()
    is_staged = False

    # Try to load plan.json for metadata
    plan: Plan | None = None
    if plan_exists:
        try:
            plan = Plan.load(plan_dir)
            is_staged = plan.status.value == "staged"
        except (ValueError, OSError):
            # Corrupted plan.json - continue with file-based detection
            plan = None

    # Check each stage
    stage_order = [PlanStage.ORIENT, PlanStage.ARCHITECT, PlanStage.ITEMIZE]
    steps: list[StepInfo] = []

    for stage in stage_order:
        artifact_path = plan_dir / stage.output_file
        artifact_exists = artifact_path.exists()
        artifact_size = artifact_path.stat().st_size if artifact_exists else 0
        plan_status = plan.stages.get(stage) if plan else None
        min_size = _MIN_ARTIFACT_SIZES[stage]

        status, detail = _determine_step_status(
            stage=stage,
            plan_status=plan_status,
            artifact_exists=artifact_exists,
            artifact_size=artifact_size,
            min_size=min_size,
        )

        steps.append(
            StepInfo(
                stage=stage,
                status=status,
                artifact_path=artifact_path,
                artifact_exists=artifact_exists,
                artifact_size=artifact_size,
                plan_status=plan_status,
                detail=detail,
            )
        )

    # Determine next step
    next_step = _determine_next_step(steps)

    return PipelineStepSummary(
        plan_slug=plan_slug,
        plan_dir=plan_dir,
        steps=steps,
        plan_exists=plan_exists,
        next_step=next_step,
        is_staged=is_staged,
    )


def _determine_step_status(
    *,
    stage: PlanStage,
    plan_status: StageStatus | None,
    artifact_exists: bool,
    artifact_size: int,
    min_size: int,
) -> tuple[StepDetectionStatus, str]:
    """
    Determine the status of a single step from metadata and file state.

    Returns:
        Tuple of (status, human-readable detail).
    """
    if plan_status == StageStatus.COMPLETE and artifact_exists and artifact_size >= min_size:
        return StepDetectionStatus.COMPLETE, f"{stage.output_file} ({artifact_size:,} bytes)"

    if plan_status == StageStatus.COMPLETE and not artifact_exists:
        return StepDetectionStatus.CORRUPTED, (
            f"plan.json says complete but {stage.output_file} is missing"
        )

    if plan_status == StageStatus.COMPLETE and artifact_exists and artifact_size < min_size:
        return StepDetectionStatus.CORRUPTED, (
            f"{stage.output_file} exists but is suspiciously small ({artifact_size} bytes)"
        )

    if plan_status == StageStatus.IN_PROGRESS:
        if artifact_exists and artifact_size >= min_size:
            return StepDetectionStatus.IN_PROGRESS, (
                f"{stage.output_file} exists ({artifact_size:,} bytes) but marked in-progress"
            )
        return StepDetectionStatus.IN_PROGRESS, "started but not yet finished"

    if artifact_exists and artifact_size >= min_size and plan_status == StageStatus.PENDING:
        # File exists but plan.json doesn't reflect it - partial completion
        return StepDetectionStatus.IN_PROGRESS, (
            f"{stage.output_file} exists ({artifact_size:,} bytes) but plan.json says pending"
        )

    return StepDetectionStatus.INCOMPLETE, "not started"


def _determine_next_step(steps: list[StepInfo]) -> PlanStage | None:
    """
    Determine the next step that should be run.

    Prioritizes:
    1. In-progress steps (resume)
    2. First incomplete step after the last complete step
    3. Corrupted steps that need re-running

    Returns:
        The next PlanStage to run, or None if all complete.
    """
    # If everything is complete, nothing to do
    if all(s.status == StepDetectionStatus.COMPLETE for s in steps):
        return None

    # Check for in-progress steps first (resume those)
    for step in steps:
        if step.status == StepDetectionStatus.IN_PROGRESS:
            return step.stage

    # Check for corrupted steps (need re-run)
    for step in steps:
        if step.status == StepDetectionStatus.CORRUPTED:
            return step.stage

    # Find first incomplete step
    for step in steps:
        if step.status == StepDetectionStatus.INCOMPLETE:
            return step.stage

    return None
