"""
Cub CLI - Plan command.

The plan command provides a three-phase workflow for planning projects:
- orient: Research and understand the problem space
- architect: Design the solution architecture
- itemize: Break down into actionable tasks
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.plan.architect import ArchitectStage, ArchitectStageError
from cub.core.plan.context import (
    OrientDepth,
    PlanContext,
    PlanContextError,
    PlanExistsError,
    SpecNotFoundError,
)
from cub.core.plan.itemize import ItemizeStage, ItemizeStageError
from cub.core.plan.models import PlanStage
from cub.core.plan.orient import OrientStage, OrientStageError
from cub.core.plan.pipeline import (
    PipelineConfig,
    PipelineConfigError,
    PipelineError,
    PipelineStepSummary,
    PlanPipeline,
    StepDetectionStatus,
    detect_pipeline_steps,
)
from cub.core.plan.template_sync import ensure_fresh_templates
from cub.utils.handoff import try_handoff_or_message

app = typer.Typer(
    name="plan",
    help="Plan projects with orient, architect, and itemize phases",
    no_args_is_help=True,
)

console = Console()


def _ensure_plan_json_exists(plan_dir: Path, project_root: Path) -> None:
    """
    Ensure plan.json exists in a plan directory.

    If plan.json is missing but artifacts exist, auto-creates it
    by detecting completed stages from artifact files.

    Args:
        plan_dir: Path to the plan directory.
        project_root: Project root directory.
    """
    if (plan_dir / "plan.json").exists():
        return

    from cub.core.plan.models import Plan, PlanStage, StageStatus

    # Check which artifacts exist
    stages: dict[PlanStage, StageStatus] = {}
    artifact_map = {
        PlanStage.ORIENT: "orientation.md",
        PlanStage.ARCHITECT: "architecture.md",
        PlanStage.ITEMIZE: "itemized-plan.md",
    }
    for stage_enum, filename in artifact_map.items():
        path = plan_dir / filename
        if path.exists() and path.stat().st_size >= 100:
            stages[stage_enum] = StageStatus.COMPLETE
        else:
            stages[stage_enum] = StageStatus.PENDING

    project = _get_project_identifier(project_root)
    plan = Plan(
        slug=plan_dir.name,
        project=project,
        stages=stages,
    )
    plan.save(project_root)
    console.print(f"[dim]Auto-created plan.json for {plan_dir.name}[/dim]")


def _find_vision_document(project_root: Path) -> Path | None:
    """
    Find a vision document in the project.

    Searches common locations for vision/requirements documents:
    - VISION.md
    - docs/PRD.md
    - docs/VISION.md
    - README.md (last resort)

    Args:
        project_root: Project root directory.

    Returns:
        Path to vision document, or None if not found.
    """
    candidates = [
        project_root / "VISION.md",
        project_root / "docs" / "PRD.md",
        project_root / "docs" / "VISION.md",
        project_root / "docs" / "vision.md",
        project_root / "PRD.md",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    # README.md is last resort - only if it has meaningful content
    readme = project_root / "README.md"
    if readme.exists():
        content = readme.read_text()
        # Only use README if it's substantial (>500 chars, not just a stub)
        if len(content) > 500 and "## " in content:
            return readme.resolve()

    return None


def _resolve_spec_path(spec: str | None, project_root: Path) -> Path | None:
    """
    Resolve the spec argument to a full path.

    Args:
        spec: Spec ID, path, or None.
        project_root: Project root directory.

    Returns:
        Resolved Path to the spec file, or None if not provided.

    Raises:
        typer.BadParameter: If spec cannot be found.
    """
    if spec is None:
        return None

    spec_path = Path(spec)

    # If it's already an absolute path or relative path that exists
    if spec_path.exists():
        return spec_path.resolve()

    # Try as relative to project root
    rel_path = project_root / spec
    if rel_path.exists():
        return rel_path.resolve()

    # Search in specs directories
    specs_root = project_root / "specs"
    if specs_root.exists():
        for stage_dir in ["researching", "planned", "staged", "implementing", "released"]:
            stage_path = specs_root / stage_dir
            if stage_path.exists():
                # Try exact filename
                spec_file = stage_path / spec
                if spec_file.exists():
                    return spec_file.resolve()
                # Try with .md extension
                spec_file = stage_path / f"{spec}.md"
                if spec_file.exists():
                    return spec_file.resolve()

    raise typer.BadParameter(
        f"Spec not found: {spec}. "
        f"Provide a path or spec name (e.g., 'my-feature' or 'specs/researching/my-feature.md')"
    )


def _get_project_identifier(project_root: Path) -> str:
    """
    Get the project identifier from the project root.

    Tries multiple strategies:
    1. Directory name (most common)
    2. pyproject.toml name
    3. package.json name

    Args:
        project_root: Project root directory.

    Returns:
        Project identifier string.
    """
    import re

    # Try pyproject.toml
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            return match.group(1).lower().replace("_", "-")

    # Try package.json
    package_json = project_root / "package.json"
    if package_json.exists():
        import json

        try:
            data = json.loads(package_json.read_text())
            if "name" in data:
                return str(data["name"]).lower().replace("_", "-")
        except (json.JSONDecodeError, KeyError):
            pass

    # Fall back to directory name
    return project_root.name.lower().replace("_", "-")


@app.command()
def orient(
    ctx: typer.Context,
    spec: str | None = typer.Argument(
        None,
        help="Spec ID or path to orient from (default: active spec)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    depth: str = typer.Option(
        OrientDepth.STANDARD,
        "--depth",
        "-d",
        help="Orient depth: light, standard, or deep",
    ),
    slug: str | None = typer.Option(
        None,
        "--slug",
        "-s",
        help="Explicit plan slug (default: derived from spec name)",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Research and understand the problem space.

    The orient phase gathers context about the project:
    - Analyzes captures and existing documentation
    - Identifies key concepts and constraints
    - Surfaces questions that need answers

    Creates orientation.md in the plan directory with:
    - Problem statement (refined)
    - Requirements (P0/P1/P2)
    - Constraints
    - Open questions
    - Risks with mitigations

    Examples:
        cub plan orient spec-abc123
        cub plan orient path/to/spec.md
        cub plan orient spec.md --depth deep
        cub plan orient spec.md --slug my-plan
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_root = project_root.resolve()

    # Ensure planning templates are fresh
    for warning in ensure_fresh_templates(project_root):
        console.print(f"[yellow]Template: {warning}[/yellow]")

    if verbose or debug:
        console.print(f"[dim]Project root: {project_root}[/dim]")
        if spec:
            console.print(f"[dim]Spec argument: {spec}[/dim]")

    # Resolve spec path
    try:
        spec_path = _resolve_spec_path(spec, project_root)
    except typer.BadParameter as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if spec_path is None:
        console.print(
            "[yellow]No spec provided. Interactive mode not yet implemented.[/yellow]"
        )
        console.print(
            "[dim]Usage: cub plan orient <spec-path-or-name>[/dim]"
        )
        raise typer.Exit(1)

    if verbose or debug:
        console.print(f"[dim]Resolved spec: {spec_path}[/dim]")

    # Get project identifier
    project = _get_project_identifier(project_root)
    if verbose or debug:
        console.print(f"[dim]Project identifier: {project}[/dim]")

    # Validate depth
    valid_depths = [OrientDepth.LIGHT, OrientDepth.STANDARD, OrientDepth.DEEP]
    if depth.lower() not in valid_depths:
        console.print(
            f"[red]Invalid depth: {depth}. Valid options: {', '.join(valid_depths)}[/red]"
        )
        raise typer.Exit(1)

    # Create plan context
    try:
        plan_ctx = PlanContext.create(
            project_root=project_root,
            project=project,
            spec_path=spec_path,
            slug=slug,
            depth=depth.lower(),
            verbose=verbose,
        )
    except PlanExistsError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except PlanContextError as e:
        console.print(f"[red]Error creating plan context: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Orienting:[/bold] {plan_ctx.plan.slug}")
    if spec_path:
        console.print(f"[dim]Source: {spec_path.relative_to(project_root)}[/dim]")

    # Run orient stage
    try:
        stage = OrientStage(plan_ctx)
        result = stage.run()
    except OrientStageError as e:
        console.print(f"[red]Orient stage failed: {e}[/red]")
        raise typer.Exit(1)
    except SpecNotFoundError as e:
        console.print(f"[red]Spec not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)

    # Report success
    console.print()
    console.print("[green]Orient complete![/green]")
    console.print(
        f"[dim]Output: {result.output_path.relative_to(project_root)}[/dim]"
    )
    console.print(
        f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]"
    )

    if verbose:
        console.print()
        console.print("[bold]Summary:[/bold]")
        if result.problem_statement:
            ps = result.problem_statement[:100]
            if len(result.problem_statement) > 100:
                ps += "..."
            console.print(f"  Problem: {ps}")
        if result.requirements_p0:
            console.print(f"  P0 requirements: {len(result.requirements_p0)}")
        if result.open_questions:
            console.print(f"  Open questions: {len(result.open_questions)}")

    # Show pipeline step summary and next actions
    summary = detect_pipeline_steps(plan_ctx.plan_dir, project_root)
    _display_step_summary(summary)
    _prompt_next_action(summary, project_root)


@app.command()
def architect(
    ctx: typer.Context,
    plan_slug: str | None = typer.Argument(
        None,
        help="Plan slug to continue architecturing (default: infer from spec)",
    ),
    spec: str | None = typer.Option(
        None,
        "--spec",
        "-s",
        help="Spec ID or path to find existing plan",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    mindset: str = typer.Option(
        "mvp",
        "--mindset",
        "-m",
        help="Technical mindset: prototype, mvp, production, or enterprise",
    ),
    scale: str = typer.Option(
        "team",
        "--scale",
        help="Expected scale: personal, team, product, or internet-scale",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Design the solution architecture.

    The architect phase designs the technical approach:
    - Proposes system structure and components
    - Identifies integration points
    - Documents design decisions and trade-offs

    Requires orient phase to be complete first.

    Examples:
        cub plan architect                     # Use most recent plan
        cub plan architect my-feature          # Specific plan by slug
        cub plan architect --spec my-feature   # Find plan by spec name
        cub plan architect --mindset production
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_root = project_root.resolve()

    # Ensure planning templates are fresh
    for warning in ensure_fresh_templates(project_root):
        console.print(f"[yellow]Template: {warning}[/yellow]")

    if verbose or debug:
        console.print(f"[dim]Project root: {project_root}[/dim]")
        if plan_slug:
            console.print(f"[dim]Plan slug: {plan_slug}[/dim]")
        if spec:
            console.print(f"[dim]Spec: {spec}[/dim]")

    # Validate mindset
    valid_mindsets = ["prototype", "mvp", "production", "enterprise"]
    if mindset.lower() not in valid_mindsets:
        console.print(
            f"[red]Invalid mindset: {mindset}. Valid options: {', '.join(valid_mindsets)}[/red]"
        )
        raise typer.Exit(1)

    # Validate scale
    valid_scales = ["personal", "team", "product", "internet-scale"]
    if scale.lower() not in valid_scales:
        console.print(
            f"[red]Invalid scale: {scale}. Valid options: {', '.join(valid_scales)}[/red]"
        )
        raise typer.Exit(1)

    # Find the plan to continue
    plan_dir: Path | None = None

    if plan_slug:
        # Direct slug provided
        plan_dir = project_root / "plans" / plan_slug
        if not plan_dir.exists():
            console.print(f"[red]Plan not found: {plan_slug}[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)
    elif spec:
        # Find plan by spec name
        spec_name = Path(spec).stem
        plan_dir = project_root / "plans" / spec_name
        if not plan_dir.exists():
            # Try finding by searching plans directory
            plans_root = project_root / "plans"
            if plans_root.exists():
                for candidate in plans_root.iterdir():
                    if candidate.is_dir() and spec_name in candidate.name:
                        plan_dir = candidate
                        break
        if not plan_dir or not plan_dir.exists():
            console.print(f"[red]No plan found for spec: {spec}[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)
    else:
        # Find most recent plan (with or without plan.json)
        plans_root = project_root / "plans"
        if not plans_root.exists():
            console.print("[red]No plans found.[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)

        plan_dirs = [d for d in plans_root.iterdir() if d.is_dir()]
        if not plan_dirs:
            console.print("[red]No plans found.[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)

        # Sort by modification time, most recent first
        plan_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        plan_dir = plan_dirs[0]

    # Ensure plan.json exists (auto-create from artifacts if needed)
    _ensure_plan_json_exists(plan_dir, project_root)

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

    console.print(f"[bold]Architecting:[/bold] {plan_ctx.plan.slug}")
    console.print(f"[dim]Mindset: {mindset} | Scale: {scale}[/dim]")

    # Run architect stage
    try:
        stage = ArchitectStage(plan_ctx, mindset=mindset.lower(), scale=scale.lower())
        result = stage.run()
    except ArchitectStageError as e:
        console.print(f"[red]Architect stage failed: {e}[/red]")
        raise typer.Exit(1)
    except SpecNotFoundError as e:
        console.print(f"[red]Spec not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)

    # Report success
    console.print()
    console.print("[green]Architect complete![/green]")
    console.print(
        f"[dim]Output: {result.output_path.relative_to(project_root)}[/dim]"
    )
    console.print(
        f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]"
    )

    if verbose:
        console.print()
        console.print("[bold]Summary:[/bold]")
        console.print(f"  Mindset: {result.mindset}")
        console.print(f"  Scale: {result.scale}")
        if result.tech_stack:
            console.print(f"  Tech stack choices: {len(result.tech_stack)}")
        if result.components:
            console.print(f"  Components: {len(result.components)}")
        if result.implementation_phases:
            console.print(f"  Implementation phases: {len(result.implementation_phases)}")

    # Show pipeline step summary and next actions
    summary = detect_pipeline_steps(plan_ctx.plan_dir, project_root)
    _display_step_summary(summary)
    _prompt_next_action(summary, project_root)


@app.command()
def itemize(
    ctx: typer.Context,
    plan_slug: str | None = typer.Argument(
        None,
        help="Plan slug to itemize (default: most recent plan with architect complete)",
    ),
    spec: str | None = typer.Option(
        None,
        "--spec",
        "-s",
        help="Spec ID or path to find existing plan",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Break down the architecture into actionable tasks.

    The itemize phase creates the task breakdown:
    - Generates well-scoped tasks from the architecture
    - Orders tasks by dependencies
    - Assigns estimates and priorities
    - Creates beads-compatible IDs

    Requires architect phase to be complete first.

    Examples:
        cub plan itemize                     # Use most recent plan
        cub plan itemize my-feature          # Specific plan by slug
        cub plan itemize --spec my-feature   # Find plan by spec name
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_root = project_root.resolve()

    # Ensure planning templates are fresh
    for warning in ensure_fresh_templates(project_root):
        console.print(f"[yellow]Template: {warning}[/yellow]")

    if verbose or debug:
        console.print(f"[dim]Project root: {project_root}[/dim]")
        if plan_slug:
            console.print(f"[dim]Plan slug: {plan_slug}[/dim]")
        if spec:
            console.print(f"[dim]Spec: {spec}[/dim]")

    # Find the plan to continue
    plan_dir: Path | None = None

    if plan_slug:
        # Direct slug provided
        plan_dir = project_root / "plans" / plan_slug
        if not plan_dir.exists():
            console.print(f"[red]Plan not found: {plan_slug}[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)
    elif spec:
        # Find plan by spec name
        spec_name = Path(spec).stem
        plan_dir = project_root / "plans" / spec_name
        if not plan_dir.exists():
            # Try finding by searching plans directory
            plans_root = project_root / "plans"
            if plans_root.exists():
                for candidate in plans_root.iterdir():
                    if candidate.is_dir() and spec_name in candidate.name:
                        plan_dir = candidate
                        break
        if not plan_dir or not plan_dir.exists():
            console.print(f"[red]No plan found for spec: {spec}[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)
    else:
        # Find most recent plan (with or without plan.json)
        plans_root = project_root / "plans"
        if not plans_root.exists():
            console.print("[red]No plans found.[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)

        plan_dirs = [d for d in plans_root.iterdir() if d.is_dir()]
        if not plan_dirs:
            console.print("[red]No plans found.[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)

        # Sort by modification time, most recent first
        plan_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        plan_dir = plan_dirs[0]

    # Ensure plan.json exists (auto-create from artifacts if needed)
    _ensure_plan_json_exists(plan_dir, project_root)

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

    console.print(f"[bold]Itemizing:[/bold] {plan_ctx.plan.slug}")

    # Run itemize stage
    try:
        stage = ItemizeStage(plan_ctx)
        result = stage.run()
    except ItemizeStageError as e:
        console.print(f"[red]Itemize stage failed: {e}[/red]")
        raise typer.Exit(1)
    except SpecNotFoundError as e:
        console.print(f"[red]Spec not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)

    # Report success
    console.print()
    console.print("[green]Itemize complete![/green]")
    console.print(
        f"[dim]Output: {result.output_path.relative_to(project_root)}[/dim]"
    )
    console.print(
        f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]"
    )

    if verbose:
        console.print()
        console.print("[bold]Summary:[/bold]")
        console.print(f"  Epics: {len(result.epics)}")
        console.print(f"  Tasks: {result.total_tasks}")
        if result.epics:
            console.print("  Epic IDs:")
            for epic in result.epics:
                task_count = len([t for t in result.tasks if t.epic_id == epic.id])
                console.print(f"    - {epic.id}: {epic.title} ({task_count} tasks)")

    # Show pipeline step summary and next actions
    summary = detect_pipeline_steps(plan_ctx.plan_dir, project_root)
    _display_step_summary(summary)
    _prompt_next_action(summary, project_root)


@app.command("run")
def run_pipeline(
    ctx: typer.Context,
    spec: str | None = typer.Argument(
        None,
        help="Spec ID or path to plan from",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    depth: str = typer.Option(
        OrientDepth.STANDARD,
        "--depth",
        "-d",
        help="Orient depth: light, standard, or deep",
    ),
    mindset: str = typer.Option(
        "mvp",
        "--mindset",
        "-m",
        help="Technical mindset: prototype, mvp, production, or enterprise",
    ),
    scale: str = typer.Option(
        "team",
        "--scale",
        help="Expected scale: personal, team, product, or internet-scale",
    ),
    slug: str | None = typer.Option(
        None,
        "--slug",
        "-s",
        help="Explicit plan slug (default: derived from spec name)",
    ),
    continue_from: str | None = typer.Option(
        None,
        "--continue",
        "-c",
        help="Continue from existing plan slug or path",
    ),
    no_move_spec: bool = typer.Option(
        False,
        "--no-move-spec",
        help="Don't move spec to planned/ on completion",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--auto",
        help="Run without user interaction (for CI/automation)",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Run the full planning pipeline (orient -> architect -> itemize).

    This command runs all three planning phases in sequence:
    1. Orient: Research and understand the problem space
    2. Architect: Design the solution architecture
    3. Itemize: Break down into actionable tasks

    On completion, the spec is moved from researching/ to planned/.

    Examples:
        cub plan run specs/researching/my-feature.md
        cub plan run my-feature
        cub plan run spec.md --depth deep --mindset production
        cub plan run --continue my-feature  # Resume incomplete plan
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_root = project_root.resolve()

    # Ensure planning templates are fresh
    for warning in ensure_fresh_templates(project_root):
        console.print(f"[yellow]Template: {warning}[/yellow]")

    if verbose or debug:
        console.print(f"[dim]Project root: {project_root}[/dim]")
        if spec:
            console.print(f"[dim]Spec argument: {spec}[/dim]")
        if continue_from:
            console.print(f"[dim]Continuing from: {continue_from}[/dim]")

    # Resolve continue_from to a path
    continue_path: Path | None = None
    if continue_from:
        # Try as plan slug first
        plan_dir = project_root / "plans" / continue_from
        if plan_dir.exists() and (plan_dir / "plan.json").exists():
            continue_path = plan_dir
        else:
            # Try as direct path
            direct_path = Path(continue_from)
            if direct_path.exists() and (direct_path / "plan.json").exists():
                continue_path = direct_path.resolve()
            else:
                console.print(f"[red]Plan not found: {continue_from}[/red]")
                console.print(
                    "[dim]Provide a plan slug or path to an existing plan directory.[/dim]"
                )
                raise typer.Exit(1)

    # Resolve spec path if provided
    spec_path: Path | None = None
    if spec and not continue_path:
        try:
            spec_path = _resolve_spec_path(spec, project_root)
        except typer.BadParameter as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    # Must have either spec or continue_from
    if spec_path is None and continue_path is None:
        # Try to find a vision document automatically
        vision_doc = _find_vision_document(project_root)
        if vision_doc:
            spec_path = vision_doc
            console.print(f"[dim]Auto-discovered: {vision_doc.relative_to(project_root)}[/dim]")
        else:
            console.print(
                "[yellow]No spec provided and no vision document found.[/yellow]"
            )
            console.print("[dim]Usage: cub plan run <spec-path-or-name>[/dim]")
            console.print("[dim]       cub plan run --continue <plan-slug>[/dim]")
            console.print(
                "[dim]Or create VISION.md, docs/PRD.md, or similar in your project root.[/dim]"
            )
            raise typer.Exit(1)

    # Create pipeline configuration
    try:
        config = PipelineConfig(
            spec_path=spec_path,
            slug=slug,
            depth=depth.lower(),
            mindset=mindset.lower(),
            scale=scale.lower(),
            verbose=verbose,
            move_spec=not no_move_spec,
            continue_from=continue_path,
            non_interactive=non_interactive,
        )
    except PipelineConfigError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(1)

    # Progress callback for Rich output
    def on_progress(stage: PlanStage, status: str, message: str) -> None:
        if status == "starting":
            console.print(f"[bold blue]{stage.value.title()}:[/bold blue] {message}")
        elif status == "complete":
            console.print(f"[green]{message}[/green]")
        elif status == "error":
            console.print(f"[red]Error: {message}[/red]")

    # Run the pipeline
    console.print("[bold]Running planning pipeline...[/bold]")
    if non_interactive:
        console.print("[dim]Mode: non-interactive (CI/automation)[/dim]")
    if spec_path:
        try:
            relative_spec = spec_path.relative_to(project_root)
        except ValueError:
            relative_spec = spec_path
        console.print(f"[dim]Source: {relative_spec}[/dim]")
    elif continue_path:
        console.print(f"[dim]Continuing: {continue_path.name}[/dim]")
    console.print(f"[dim]Depth: {depth} | Mindset: {mindset} | Scale: {scale}[/dim]")
    console.print()

    try:
        pipeline = PlanPipeline(project_root, config, on_progress)
        result = pipeline.run()
    except PipelineError as e:
        console.print(f"[red]Pipeline error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)

    # Report results
    console.print()
    if result.success:
        console.print("[bold green]Pipeline complete![/bold green]")
        console.print(f"[dim]Plan: {result.plan_dir.name}[/dim]")
        console.print(f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]")

        if verbose:
            console.print()
            console.print("[bold]Stages completed:[/bold]")
            for stage_result in result.stage_results:
                status = "[green]\u2713[/green]" if stage_result.success else "[red]\u2717[/red]"
                console.print(
                    f"  {status} {stage_result.stage.value}: {stage_result.duration_seconds:.1f}s"
                )

            if result.itemize_result:
                console.print()
                console.print("[bold]Summary:[/bold]")
                console.print(f"  Epics: {len(result.itemize_result.epics)}")
                console.print(f"  Tasks: {result.itemize_result.total_tasks}")

        if result.spec_moved and result.spec_new_path:
            console.print()
            try:
                relative_new = result.spec_new_path.relative_to(project_root)
            except ValueError:
                relative_new = result.spec_new_path
            console.print(f"[dim]Spec moved to: {relative_new}[/dim]")

        # Show step summary and next actions
        summary = detect_pipeline_steps(result.plan_dir, project_root)
        _display_step_summary(summary)
        _prompt_next_action(summary, project_root)
    else:
        console.print("[bold red]Pipeline failed![/bold red]")
        if result.error:
            console.print(f"[red]{result.error}[/red]")

        # Detect steps and show detailed summary instead of basic stage list
        if result.plan.slug != "error" and result.plan_dir.exists():
            summary = detect_pipeline_steps(result.plan_dir, project_root)
            _display_step_summary(summary)
            _prompt_next_action(summary, project_root)

            console.print()
            console.print(
                f"[dim]Resume with: cub plan run --continue {result.plan.slug}[/dim]"
            )
        else:
            # Show basic stage results as fallback
            if result.stage_results:
                console.print()
                console.print("[bold]Stage results:[/bold]")
                for stage_result in result.stage_results:
                    icon = "[green]✓[/green]" if stage_result.success else "[red]✗[/red]"
                    console.print(f"  {icon} {stage_result.stage.value}")

        raise typer.Exit(1)


@app.command("ensure")
def ensure(
    ctx: typer.Context,
    slug: str = typer.Argument(
        ...,
        help="Plan slug (directory name under plans/)",
    ),
    spec: str | None = typer.Option(
        None,
        "--spec",
        "-s",
        help="Spec ID or path to link to this plan",
    ),
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly format",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Ensure a plan.json exists for a given slug.

    Idempotent: if plan.json already exists, prints status and exits.
    If missing, creates it via PlanContext.create() with proper defaults.

    This is the key command that skill templates call to ensure
    plan.json exists before writing artifacts.

    Examples:
        cub plan ensure my-feature
        cub plan ensure my-feature --spec specs/researching/my-feature.md
    """
    project_root = project_root.resolve()
    plan_dir = project_root / "plans" / slug

    # If plan.json already exists, load and report status
    if (plan_dir / "plan.json").exists():
        try:
            from cub.core.plan.models import Plan

            plan = Plan.load(plan_dir)
            if agent:
                console.print(f"plan_dir={plan_dir}")
                console.print(f"status={plan.status.value}")
                for stage_name, stage_status in plan.stages.items():
                    console.print(f"stage.{stage_name.value}={stage_status.value}")
            else:
                console.print(f"[dim]Plan already exists:[/dim] {slug}")
                console.print(f"[dim]Status:[/dim] {plan.status.value}")
                for stage_name, stage_status in plan.stages.items():
                    indicator = _stage_indicator(stage_status)
                    console.print(f"  {stage_name.value}: {indicator}")
            return
        except (ValueError, OSError) as e:
            console.print(f"[yellow]Warning: existing plan.json is corrupt: {e}[/yellow]")
            console.print("[dim]Recreating plan.json...[/dim]")

    # Resolve spec path if provided
    spec_path: Path | None = None
    if spec:
        try:
            spec_path = _resolve_spec_path(spec, project_root)
        except typer.BadParameter as e:
            console.print(f"[yellow]Warning: {e}[/yellow]")

    # Get project identifier
    project = _get_project_identifier(project_root)

    # Create plan context (which creates plan.json)
    try:
        plan_ctx = PlanContext.create(
            project_root=project_root,
            project=project,
            spec_path=spec_path,
            slug=slug,
        )
        plan_ctx.save_plan()
    except PlanExistsError:
        # Race condition: plan was created between our check and create
        # Just load and report
        from cub.core.plan.models import Plan

        plan = Plan.load(plan_dir)
        if agent:
            console.print(f"plan_dir={plan_dir}")
            console.print(f"status={plan.status.value}")
        else:
            console.print(f"[dim]Plan already exists:[/dim] {slug}")
        return
    except PlanContextError as e:
        console.print(f"[red]Error creating plan: {e}[/red]")
        raise typer.Exit(1)

    if agent:
        console.print(f"plan_dir={plan_ctx.plan_dir}")
        console.print(f"status={plan_ctx.plan.status.value}")
    else:
        console.print(f"[green]Plan created:[/green] {slug}")
        console.print(f"[dim]Directory:[/dim] {plan_ctx.plan_dir}")


@app.command("complete-stage")
def complete_stage(
    ctx: typer.Context,
    slug: str = typer.Argument(
        ...,
        help="Plan slug",
    ),
    stage_name: str = typer.Argument(
        ...,
        help="Stage to mark complete (orient, architect, or itemize)",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Mark a plan stage as complete.

    Loads plan.json (creating it first if needed), marks the specified
    stage as complete, and saves. This is the key command that skill
    templates call after writing artifacts.

    Examples:
        cub plan complete-stage my-feature orient
        cub plan complete-stage my-feature architect
        cub plan complete-stage my-feature itemize
    """
    project_root = project_root.resolve()

    # Validate stage name
    try:
        stage_enum = PlanStage(stage_name.lower())
    except ValueError:
        valid = ", ".join(s.value for s in PlanStage)
        console.print(f"[red]Invalid stage: {stage_name}. Valid stages: {valid}[/red]")
        raise typer.Exit(1)

    plan_dir = project_root / "plans" / slug

    # If plan.json doesn't exist, ensure it first
    if not (plan_dir / "plan.json").exists():
        # Auto-create plan.json (ensure internally)
        project = _get_project_identifier(project_root)
        try:
            plan_ctx = PlanContext.create(
                project_root=project_root,
                project=project,
                slug=slug,
            )
            plan_ctx.save_plan()
            console.print(f"[dim]Created plan.json for {slug}[/dim]")
        except (PlanExistsError, PlanContextError) as e:
            console.print(f"[red]Error creating plan: {e}[/red]")
            raise typer.Exit(1)

    # Load plan and complete the stage
    try:
        from cub.core.plan.models import Plan

        plan = Plan.load(plan_dir)
        plan.complete_stage(stage_enum)
        plan.save(project_root)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except (ValueError, OSError) as e:
        console.print(f"[red]Error updating plan: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Stage {stage_name} marked complete[/green] for {slug}")

    if plan.is_complete:
        console.print("[green]All stages complete![/green] Ready for staging.")


@app.command("status")
def plan_status(
    ctx: typer.Context,
    slug: str | None = typer.Argument(
        None,
        help="Plan slug (default: most recent plan)",
    ),
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly markdown format",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Show the status of a plan's pipeline stages.

    Uses artifact detection and plan.json to show which stages are
    complete, in-progress, or incomplete, along with recommended
    next action.

    Examples:
        cub plan status                  # Most recent plan
        cub plan status my-feature       # Specific plan
        cub plan status --agent          # LLM-friendly output
    """
    project_root = project_root.resolve()

    # Find plan directory
    plan_dir: Path | None = None

    if slug:
        plan_dir = project_root / "plans" / slug
        if not plan_dir.exists():
            console.print(f"[red]Plan not found: {slug}[/red]")
            raise typer.Exit(1)
    else:
        # Find most recent plan directory (with or without plan.json)
        plans_root = project_root / "plans"
        if not plans_root.exists():
            console.print("[red]No plans found.[/red]")
            raise typer.Exit(1)

        plan_dirs = [d for d in plans_root.iterdir() if d.is_dir()]
        if not plan_dirs:
            console.print("[red]No plans found.[/red]")
            raise typer.Exit(1)

        # Sort by most recent modification
        plan_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        plan_dir = plan_dirs[0]

    # Detect pipeline status
    summary = detect_pipeline_steps(plan_dir, project_root)

    if agent:
        # Agent-friendly output
        console.print(f"# Plan Status: {summary.plan_slug}")
        console.print(f"plan_dir={summary.plan_dir}")
        console.print(f"plan_json={'yes' if summary.plan_exists else 'no'}")
        console.print(f"staged={'yes' if summary.is_staged else 'no'}")
        console.print(f"all_complete={'yes' if summary.all_complete else 'no'}")
        console.print()
        for step in summary.steps:
            console.print(f"- {step.stage.value}: {step.status.value} ({step.detail})")
        if summary.next_step:
            console.print(f"\nnext_action={summary.next_step.value}")
    else:
        _display_step_summary(summary)
        _prompt_next_action(summary, project_root)


@app.command("list")
def list_plans(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output including stage status",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    List all plans in the project.

    Shows existing plans with their status, spec source, and completion state.
    Replaces the old 'cub sessions' command.

    Examples:
        cub plan list              # List all plans
        cub plan list --verbose    # Show detailed stage status
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_root = project_root.resolve()

    plans_root = project_root / "plans"
    if not plans_root.exists():
        console.print("[yellow]No plans found.[/yellow]")
        console.print("[dim]Run 'cub plan run <spec>' to create a plan.[/dim]")
        return

    # Find all plan directories
    plan_dirs = [
        d for d in plans_root.iterdir()
        if d.is_dir() and (d / "plan.json").exists()
    ]

    if not plan_dirs:
        console.print("[yellow]No plans found.[/yellow]")
        console.print("[dim]Run 'cub plan run <spec>' to create a plan.[/dim]")
        return

    # Sort by modification time, most recent first
    plan_dirs.sort(key=lambda p: (p / "plan.json").stat().st_mtime, reverse=True)

    console.print(f"[bold]Plans ({len(plan_dirs)}):[/bold]")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Slug")
    table.add_column("Status")
    table.add_column("Spec")
    if verbose:
        table.add_column("Orient")
        table.add_column("Architect")
        table.add_column("Itemize")

    for plan_dir in plan_dirs:
        try:
            plan_ctx = PlanContext.load(plan_dir, project_root)
            plan = plan_ctx.plan
            spec_name = plan.spec_file or "-"

            # Status color
            if plan.is_complete:
                status_str = "[green]complete[/green]"
            elif plan.status.value == "in_progress":
                status_str = "[yellow]in progress[/yellow]"
            else:
                status_str = f"[dim]{plan.status.value}[/dim]"

            if verbose:
                # Stage status
                orient = _stage_indicator(plan.stages.get(PlanStage.ORIENT))
                architect = _stage_indicator(plan.stages.get(PlanStage.ARCHITECT))
                itemize = _stage_indicator(plan.stages.get(PlanStage.ITEMIZE))
                table.add_row(plan.slug, status_str, spec_name, orient, architect, itemize)
            else:
                table.add_row(plan.slug, status_str, spec_name)
        except Exception as e:
            if debug:
                console.print(f"[red]Error loading {plan_dir.name}: {e}[/red]")
            if verbose:
                table.add_row(plan_dir.name, "[red]error[/red]", "-", "-", "-", "-")
            else:
                table.add_row(plan_dir.name, "[red]error[/red]", "-")

    console.print(table)

    if verbose:
        console.print()
        console.print("[dim]Legend: \u2713 complete, \u2717 not started, \u25cb in progress[/dim]")


def _step_status_indicator(status: StepDetectionStatus) -> str:
    """Get a visual indicator for step detection status."""
    if status == StepDetectionStatus.COMPLETE:
        return "[green]✓ complete[/green]"
    elif status == StepDetectionStatus.IN_PROGRESS:
        return "[yellow]◐ in-progress[/yellow]"
    elif status == StepDetectionStatus.CORRUPTED:
        return "[red]⚠ corrupted[/red]"
    else:
        return "[dim]○ incomplete[/dim]"


def _display_step_summary(summary: PipelineStepSummary) -> None:
    """
    Display a summary table of pipeline step completion status.

    Args:
        summary: The pipeline step summary to display.
    """
    console.print()
    console.print(f"[bold]Pipeline status for:[/bold] {summary.plan_slug}")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Step", style="bold")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for step in summary.steps:
        status_str = _step_status_indicator(step.status)
        table.add_row(step.stage.value.title(), status_str, step.detail)

    console.print(table)

    if summary.is_staged:
        console.print("[dim]This plan has already been staged to the task backend.[/dim]")
    elif summary.all_complete:
        console.print("[green]All steps complete.[/green] Ready for staging.")
    elif summary.has_corruption:
        console.print(
            "[yellow]Warning:[/yellow] Some steps have corrupted artifacts. "
            "Consider re-running those steps."
        )

    if summary.next_step and not summary.is_staged:
        console.print()
        console.print(
            f"[bold]Suggested next step:[/bold] {summary.next_step.value}"
        )


def _prompt_next_action(
    summary: PipelineStepSummary,
    project_root: Path,
) -> None:
    """
    Prompt the user with options for what to do next after viewing the step summary.

    Shows options to continue to the next incomplete step, re-run a specific step,
    or exit. Routes the selected action to the appropriate subcommand message.

    Args:
        summary: The pipeline step summary.
        project_root: Project root directory.
    """
    if summary.is_staged:
        console.print()
        console.print("[dim]Plan is already staged. No further pipeline steps needed.[/dim]")
        return

    if summary.all_complete:
        _success, next_msg = try_handoff_or_message("stage", summary.plan_slug)
        console.print(next_msg)
        return

    # Build the list of actionable options
    options: list[tuple[str, str, str]] = []

    if summary.next_step:
        step_name = summary.next_step.value
        # Map stage to command
        cmd_map = {
            "orient": "plan orient",
            "architect": "plan architect",
            "itemize": "plan itemize",
        }
        cmd = cmd_map.get(step_name, f"plan {step_name}")
        options.append((
            f"Continue → {step_name}",
            cmd,
            summary.plan_slug,
        ))

    # Add re-run options for completed or corrupted steps
    for step in summary.steps:
        if step.status in (StepDetectionStatus.COMPLETE, StepDetectionStatus.CORRUPTED):
            step_name = step.stage.value
            cmd_map = {
                "orient": "plan orient",
                "architect": "plan architect",
                "itemize": "plan itemize",
            }
            cmd = cmd_map.get(step_name, f"plan {step_name}")
            label = "Re-run" if step.status == StepDetectionStatus.COMPLETE else "Fix"
            options.append((
                f"{label} → {step_name}",
                cmd,
                summary.plan_slug,
            ))

    if not options:
        return

    console.print()
    console.print("[bold]Available actions:[/bold]")
    for i, (label, cmd, args) in enumerate(options, 1):
        _success, msg = try_handoff_or_message(cmd, args)
        console.print(f"  {i}. {label}: {msg}")

    console.print(f"  {len(options) + 1}. Exit")


def _stage_indicator(status: object) -> str:
    """Get a visual indicator for stage status."""
    from cub.core.plan.models import StageStatus

    if status is None:
        return "[dim]\u2717[/dim]"
    elif status == StageStatus.COMPLETE:
        return "[green]\u2713[/green]"
    elif status == StageStatus.IN_PROGRESS:
        return "[yellow]\u25cb[/yellow]"
    else:
        return "[dim]\u2717[/dim]"
