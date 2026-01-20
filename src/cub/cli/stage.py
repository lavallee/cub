"""
Cub CLI - Stage command.

The stage command imports tasks from a completed plan's itemized-plan.md
into the task backend (beads or JSON), bridging planning and execution.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.plan.context import PlanContext, PlanContextError
from cub.core.specs.lifecycle import SpecLifecycleError, move_spec_to_staged
from cub.core.stage.stager import (
    ItemizedPlanNotFoundError,
    PlanAlreadyStagedError,
    PlanNotCompleteError,
    Stager,
    StagerError,
    StagingResult,
    TaskImportError,
    find_stageable_plans,
)

app = typer.Typer(
    name="stage",
    help="Import tasks from a completed plan into the task backend",
    no_args_is_help=False,
)

console = Console()


def _find_plan_dir(
    plan_slug: str | None,
    project_root: Path,
) -> Path | None:
    """
    Find a plan directory by slug or find the most recent stageable plan.

    Args:
        plan_slug: Explicit plan slug, or None to find most recent.
        project_root: Project root directory.

    Returns:
        Path to plan directory, or None if not found.
    """
    if plan_slug:
        # Direct slug provided
        plan_dir = project_root / "plans" / plan_slug
        if plan_dir.exists() and (plan_dir / "plan.json").exists():
            return plan_dir
        return None

    # Find most recent stageable plan
    stageable = find_stageable_plans(project_root)
    if stageable:
        # Sort by modification time, most recent first
        stageable.sort(
            key=lambda p: (p / "plan.json").stat().st_mtime,
            reverse=True,
        )
        return stageable[0]

    return None


@app.callback(invoke_without_command=True)
def stage(
    ctx: typer.Context,
    plan_slug: str | None = typer.Argument(
        None,
        help="Plan slug to stage (default: most recent complete plan)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be imported without actually importing",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    list_plans: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List all stageable plans",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Import tasks from a completed plan into the task backend.

    The stage command bridges planning and execution by importing the
    tasks from itemized-plan.md into the task backend (beads or JSON).

    After staging:
    - Tasks are created in the task backend
    - The plan status is updated to STAGED
    - Tasks are ready for 'cub run' execution

    Examples:
        cub stage                     # Stage most recent complete plan
        cub stage my-feature          # Stage specific plan by slug
        cub stage --dry-run           # Preview without importing
        cub stage --list              # List all stageable plans
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_root = project_root.resolve()

    if verbose or debug:
        console.print(f"[dim]Project root: {project_root}[/dim]")
        if plan_slug:
            console.print(f"[dim]Plan slug: {plan_slug}[/dim]")

    # Handle --list flag
    if list_plans:
        _list_stageable_plans(project_root, verbose)
        return

    # Find the plan to stage
    plan_dir = _find_plan_dir(plan_slug, project_root)

    if plan_dir is None:
        if plan_slug:
            console.print(f"[red]Plan not found: {plan_slug}[/red]")
            console.print(
                "[dim]Run 'cub plan run <spec>' first to create a plan.[/dim]"
            )
        else:
            console.print("[red]No stageable plans found.[/red]")
            console.print(
                "[dim]Run 'cub plan run <spec>' first to create a complete plan.[/dim]"
            )
            console.print(
                "[dim]Or use 'cub stage --list' to see available plans.[/dim]"
            )
        raise typer.Exit(1)

    if verbose or debug:
        console.print(f"[dim]Using plan: {plan_dir.name}[/dim]")

    # Load plan context
    try:
        plan_ctx = PlanContext.load(plan_dir, project_root)
    except FileNotFoundError as e:
        console.print(f"[red]Error loading plan: {e}[/red]")
        raise typer.Exit(1)
    except PlanContextError as e:
        console.print(f"[red]Error loading plan context: {e}[/red]")
        raise typer.Exit(1)

    # Create stager and run
    stager = Stager(plan_ctx)

    if dry_run:
        console.print(f"[bold]Dry run:[/bold] {plan_ctx.plan.slug}")
    else:
        console.print(f"[bold]Staging:[/bold] {plan_ctx.plan.slug}")

    try:
        result = stager.stage(dry_run=dry_run)
    except PlanNotCompleteError as e:
        console.print(f"[red]Plan not ready: {e}[/red]")
        console.print(
            "[dim]Complete all planning stages first with 'cub plan run'.[/dim]"
        )
        raise typer.Exit(1)
    except PlanAlreadyStagedError as e:
        console.print(f"[yellow]Already staged: {e}[/yellow]")
        raise typer.Exit(0)
    except ItemizedPlanNotFoundError as e:
        console.print(f"[red]Missing itemized plan: {e}[/red]")
        console.print("[dim]Run 'cub plan itemize' first.[/dim]")
        raise typer.Exit(1)
    except TaskImportError as e:
        console.print(f"[red]Import failed: {e}[/red]")
        raise typer.Exit(1)
    except StagerError as e:
        console.print(f"[red]Staging error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)

    # Move spec from planned/ to staged/ (only on successful, non-dry-run staging)
    spec_moved = False
    spec_new_path = None
    if not dry_run:
        try:
            spec_new_path = move_spec_to_staged(plan_ctx, verbose=verbose or debug)
            if spec_new_path is not None:
                spec_moved = True
        except SpecLifecycleError as e:
            # Non-fatal: warn but don't fail staging
            console.print(f"[yellow]Warning: Could not move spec: {e}[/yellow]")

    # Report results
    console.print()
    if dry_run:
        console.print("[yellow]Dry run complete - no tasks imported[/yellow]")
    else:
        console.print("[green]Staging complete![/green]")

    console.print(f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]")

    # Summary
    console.print()
    console.print(f"[bold]Created:[/bold] {len(result.epics_created)} epics, "
                  f"{len(result.tasks_created)} tasks")

    # Report spec move
    if spec_moved and spec_new_path is not None:
        console.print(f"[cyan]Spec moved to:[/cyan] {spec_new_path.relative_to(project_root)}")

    if verbose:
        _print_detailed_results(result, project_root)

    # Next steps
    if not dry_run:
        console.print()
        console.print("[bold]Next step:[/bold] cub run")


def _list_stageable_plans(project_root: Path, verbose: bool) -> None:
    """List all plans that are ready to be staged."""
    stageable = find_stageable_plans(project_root)

    if not stageable:
        console.print("[yellow]No stageable plans found.[/yellow]")
        console.print(
            "[dim]Plans must be complete (orient, architect, itemize done) "
            "to be staged.[/dim]"
        )
        return

    # Sort by modification time
    stageable.sort(
        key=lambda p: (p / "plan.json").stat().st_mtime,
        reverse=True,
    )

    console.print(f"[bold]Stageable plans ({len(stageable)}):[/bold]")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Plan Slug")
    table.add_column("Status")
    table.add_column("Spec")

    for plan_dir in stageable:
        try:
            ctx = PlanContext.load(plan_dir, project_root)
            plan = ctx.plan
            spec_name = plan.spec_file or "-"
            table.add_row(
                plan.slug,
                plan.status.value,
                spec_name,
            )
        except Exception:
            # Skip plans that can't be loaded
            table.add_row(
                plan_dir.name,
                "[red]error[/red]",
                "-",
            )

    console.print(table)

    if verbose:
        console.print()
        console.print("[dim]Use 'cub stage <slug>' to stage a specific plan.[/dim]")


def _print_detailed_results(
    result: StagingResult,
    project_root: Path,
) -> None:
    """Print detailed staging results."""
    if result.epics_created:
        console.print()
        console.print("[bold]Epics:[/bold]")
        for epic in result.epics_created:
            task_count = len([t for t in result.tasks_created if t.parent == epic.id])
            console.print(f"  - {epic.id}: {epic.title} ({task_count} tasks)")

    if result.tasks_created:
        console.print()
        console.print("[bold]Tasks:[/bold]")
        for task in result.tasks_created:
            priority_str = f"P{task.priority_numeric}"
            console.print(f"  - {task.id} [{priority_str}]: {task.title}")
