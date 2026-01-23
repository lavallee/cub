"""
Spec lifecycle management for cub.

Provides functions to automatically move specs through lifecycle stages:
- staged -> implementing (on cub run)
- implementing -> released (on release)

These functions are designed to be called from CLI commands and scripts.
"""

from __future__ import annotations

from pathlib import Path

from cub.core.plan.context import PlanContext
from cub.core.specs.models import Stage
from cub.core.specs.workflow import (
    SpecMoveError,
    SpecNotFoundError,
    SpecWorkflow,
)


class SpecLifecycleError(Exception):
    """Base exception for spec lifecycle errors."""

    pass


def move_spec_to_staged(
    plan_ctx: PlanContext,
    verbose: bool = False,
) -> Path | None:
    """
    Move a spec from planned/ to staged/ when a plan is staged.

    This should be called after tasks are successfully imported to the
    task backend during the staging process.

    Args:
        plan_ctx: The plan context containing spec path info.
        verbose: If True, print status messages.

    Returns:
        New path of the spec file, or None if no move occurred.

    Raises:
        SpecLifecycleError: If the move fails.
    """
    if not plan_ctx.has_spec or plan_ctx.spec_path is None:
        return None

    spec_path = plan_ctx.spec_path
    specs_root = plan_ctx.get_specs_root()

    # Check if spec is in planned/
    planned_dir = specs_root / Stage.PLANNED.value
    try:
        spec_path.relative_to(planned_dir)
    except ValueError:
        # Spec is not in planned/, don't move
        if verbose:
            print(f"Spec not in planned/: {spec_path}")
        return None

    # Move to staged/
    workflow = SpecWorkflow(specs_root)
    try:
        spec_name = spec_path.stem
        updated_spec = workflow.move_to_stage(spec_name, Stage.STAGED)
        if verbose:
            print(f"Moved spec to staged/: {updated_spec.path}")
        return updated_spec.path
    except (SpecNotFoundError, SpecMoveError) as e:
        raise SpecLifecycleError(f"Failed to move spec to staged: {e}") from e


def move_spec_to_implementing(
    plan_ctx: PlanContext,
    verbose: bool = False,
) -> Path | None:
    """
    Move a spec from staged/ to implementing/ when cub run starts.

    This should be called at the beginning of a run when working on
    tasks from a staged plan.

    Args:
        plan_ctx: The plan context containing spec path info.
        verbose: If True, print status messages.

    Returns:
        New path of the spec file, or None if no move occurred.

    Raises:
        SpecLifecycleError: If the move fails.
    """
    if not plan_ctx.has_spec or plan_ctx.spec_path is None:
        return None

    spec_path = plan_ctx.spec_path
    specs_root = plan_ctx.get_specs_root()

    # Check if spec is in staged/
    staged_dir = specs_root / Stage.STAGED.value
    try:
        spec_path.relative_to(staged_dir)
    except ValueError:
        # Spec is not in staged/, don't move
        if verbose:
            print(f"Spec not in staged/: {spec_path}")
        return None

    # Move to implementing/
    workflow = SpecWorkflow(specs_root)
    try:
        spec_name = spec_path.stem
        updated_spec = workflow.move_to_stage(spec_name, Stage.IMPLEMENTING)
        if verbose:
            print(f"Moved spec to implementing/: {updated_spec.path}")
        return updated_spec.path
    except (SpecNotFoundError, SpecMoveError) as e:
        raise SpecLifecycleError(f"Failed to move spec to implementing: {e}") from e


def move_specs_to_released(
    specs_root: Path,
    verbose: bool = False,
) -> list[Path]:
    """
    Move all specs from implementing/ to released/ during a release.

    This should be called from the release script after all checks pass.

    Args:
        specs_root: Path to the specs/ directory.
        verbose: If True, print status messages.

    Returns:
        List of new paths for moved specs.

    Raises:
        SpecLifecycleError: If moving any spec fails.
    """
    workflow = SpecWorkflow(specs_root)
    moved_paths: list[Path] = []

    # Get all specs in implementing/
    try:
        implementing_specs = workflow.list_specs(Stage.IMPLEMENTING)
    except FileNotFoundError:
        # No specs directory, nothing to move
        return []

    for spec in implementing_specs:
        try:
            updated_spec = workflow.move_to_stage(spec, Stage.RELEASED)
            moved_paths.append(updated_spec.path)
            if verbose:
                print(f"Moved spec to released/: {updated_spec.path}")
        except (SpecNotFoundError, SpecMoveError) as e:
            raise SpecLifecycleError(
                f"Failed to move spec '{spec.name}' to released: {e}"
            ) from e

    return moved_paths


def get_spec_lifecycle_stage_from_plan(
    plan_ctx: PlanContext,
) -> Stage | None:
    """
    Determine the current lifecycle stage of a spec from its plan context.

    Args:
        plan_ctx: The plan context.

    Returns:
        The spec's current Stage, or None if no spec is associated.
    """
    if not plan_ctx.has_spec or plan_ctx.spec_path is None:
        return None

    spec_path = plan_ctx.spec_path
    specs_root = plan_ctx.get_specs_root()

    # Determine stage from directory
    for stage in [s for s in Stage if s != Stage.COMPLETED]:
        stage_dir = specs_root / stage.value
        try:
            spec_path.relative_to(stage_dir)
            return stage
        except ValueError:
            continue

    return None
