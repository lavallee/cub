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
    PlanPipeline,
)

app = typer.Typer(
    name="plan",
    help="Plan projects with orient, architect, and itemize phases",
    no_args_is_help=True,
)

console = Console()


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

    console.print()
    console.print("[bold]Next step:[/bold] cub plan architect")


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
        # Find most recent plan
        plans_root = project_root / "plans"
        if not plans_root.exists():
            console.print("[red]No plans found.[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)

        # Find most recently modified plan directory
        plan_dirs = [d for d in plans_root.iterdir() if d.is_dir() and (d / "plan.json").exists()]
        if not plan_dirs:
            console.print("[red]No plans found.[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)

        # Sort by modification time, most recent first
        plan_dirs.sort(key=lambda p: (p / "plan.json").stat().st_mtime, reverse=True)
        plan_dir = plan_dirs[0]

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

    console.print()
    console.print("[bold]Next step:[/bold] cub plan itemize")


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
        # Find most recent plan
        plans_root = project_root / "plans"
        if not plans_root.exists():
            console.print("[red]No plans found.[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)

        # Find most recently modified plan directory
        plan_dirs = [d for d in plans_root.iterdir() if d.is_dir() and (d / "plan.json").exists()]
        if not plan_dirs:
            console.print("[red]No plans found.[/red]")
            console.print("[dim]Run 'cub plan orient <spec>' first to create a plan.[/dim]")
            raise typer.Exit(1)

        # Sort by modification time, most recent first
        plan_dirs.sort(key=lambda p: (p / "plan.json").stat().st_mtime, reverse=True)
        plan_dir = plan_dirs[0]

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

    console.print()
    console.print("[bold]Next step:[/bold] cub stage")


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

        console.print()
        console.print("[bold]Next step:[/bold] cub stage")
    else:
        console.print("[bold red]Pipeline failed![/bold red]")
        if result.error:
            console.print(f"[red]{result.error}[/red]")

        # Show which stages completed
        if result.stage_results:
            console.print()
            console.print("[bold]Stage results:[/bold]")
            for stage_result in result.stage_results:
                status = "[green]\u2713[/green]" if stage_result.success else "[red]\u2717[/red]"
                console.print(f"  {status} {stage_result.stage.value}")

        # Suggest how to resume
        if result.plan.slug != "error":
            console.print()
            console.print(
                f"[dim]Resume with: cub plan run --continue {result.plan.slug}[/dim]"
            )

        raise typer.Exit(1)


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
