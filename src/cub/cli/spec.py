"""
Cub CLI - Spec command.

Create feature specifications through an interactive interview process.
"""

import subprocess
from pathlib import Path

import typer
from rich.console import Console

from cub.core.specs import Spec, SpecWorkflow, Stage
from cub.utils.project import find_project_root

console = Console()

# Stage colors for display
STAGE_COLORS: dict[Stage, str] = {
    Stage.RESEARCHING: "yellow",
    Stage.PLANNED: "blue",
    Stage.STAGED: "magenta",
    Stage.IMPLEMENTING: "cyan",
    Stage.RELEASED: "green",
}


def spec(
    ctx: typer.Context,
    topic: str | None = typer.Argument(
        None,
        help="Feature name or brief description to start the interview",
    ),
    list_specs: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List specs in all lifecycle stages",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress post-command guidance messages",
    ),
) -> None:
    """
    Create a feature specification through an interactive interview.

    This launches an AI-guided interview session that helps you articulate
    a feature idea and produces a structured spec file in specs/researching/.

    The interview covers:
    - Problem space exploration
    - Goals and non-goals
    - Dependencies and constraints
    - Open questions and readiness assessment

    Examples:
        cub spec                           # Start interview with no topic
        cub spec "user authentication"    # Start with a topic
        cub spec --list                    # List all specs
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    # Handle --list flag
    if list_specs:
        _list_all_specs(debug)
        return

    # Ensure specs/researching directory exists (relative to project root or cwd)
    project_root = find_project_root() or Path.cwd()
    specs_dir = project_root / "specs" / "researching"
    specs_dir.mkdir(parents=True, exist_ok=True)

    # Build the skill invocation
    skill_prompt = "/cub:spec"
    if topic:
        skill_prompt += f" {topic}"
        console.print(f"[bold]Starting spec interview for:[/bold] {topic}")
    else:
        console.print("[bold]Starting spec interview...[/bold]")

    console.print(
        "[dim]This will guide you through creating a feature specification.[/dim]"
    )
    console.print()

    # Launch Claude with the spec skill
    try:
        result = subprocess.run(
            ["claude", skill_prompt],
            check=False,  # Don't raise on non-zero exit
        )

        # Show guidance on successful completion
        if result.returncode == 0 and not quiet:
            from cub.cli.guidance import render_guidance
            from cub.core.guidance import CommandType

            render_guidance(console, CommandType.SPEC)

        # Exit with the same code as Claude
        raise typer.Exit(result.returncode)
    except FileNotFoundError:
        console.print(
            "[red]Error:[/red] Claude CLI not found. "
            "Please install Claude Code from https://claude.ai/download"
        )
        raise typer.Exit(1)


def _list_all_specs(debug: bool) -> None:
    """List specs in all lifecycle stages."""
    # Find project root from current directory
    project_root = find_project_root()
    if project_root is None:
        console.print(
            "[yellow]Not in a project directory.[/yellow] "
            "Could not find .beads/, .cub/, .cub.json, or .git/"
        )
        console.print("[dim]Run 'cub init' to initialize a project.[/dim]")
        return

    specs_dir = project_root / "specs"

    if not specs_dir.exists():
        console.print("[yellow]No specs/ directory found.[/yellow]")
        console.print("[dim]Run 'cub spec' to create your first spec.[/dim]")
        return

    # Use SpecWorkflow to list all specs
    try:
        workflow = SpecWorkflow(specs_dir)
        all_specs = workflow.list_specs()
    except FileNotFoundError:
        console.print("[yellow]No specs/ directory found.[/yellow]")
        console.print("[dim]Run 'cub spec' to create your first spec.[/dim]")
        return

    if not all_specs:
        console.print("[yellow]No specs found in any stage.[/yellow]")
        console.print("[dim]Run 'cub spec' to create your first spec.[/dim]")
        return

    # Group specs by stage for display
    specs_by_stage: dict[Stage, list[Spec]] = {}
    for s in all_specs:
        if s.stage not in specs_by_stage:
            specs_by_stage[s.stage] = []
        specs_by_stage[s.stage].append(s)

    # Display total count
    console.print(f"[bold]Specs ({len(all_specs)} total):[/bold]")
    console.print()

    # Display specs grouped by stage in lifecycle order
    stage_order = [
        Stage.RESEARCHING,
        Stage.PLANNED,
        Stage.STAGED,
        Stage.IMPLEMENTING,
        Stage.RELEASED,
    ]

    for stage in stage_order:
        if stage not in specs_by_stage:
            continue

        stage_specs = specs_by_stage[stage]
        color = STAGE_COLORS.get(stage, "white")
        console.print(f"[bold {color}]{stage.value}[/bold {color}] ({len(stage_specs)}):")

        for spec in stage_specs:
            readiness_str = (
                f"[{spec.readiness.score}/10]" if spec.readiness.score > 0 else ""
            )
            console.print(f"  [cyan]{spec.name}[/cyan] {readiness_str}")
            if spec.title and spec.title != spec.name:
                console.print(f"    [dim]{spec.title}[/dim]")

        console.print()

    # Show helpful commands
    console.print("[dim]View a spec: cat specs/<stage>/<name>.md[/dim]")
    if Stage.RESEARCHING in specs_by_stage:
        console.print(
            "[dim]Plan a spec: cub plan run specs/researching/<name>.md[/dim]"
        )


