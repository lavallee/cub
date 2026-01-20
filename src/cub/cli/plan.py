"""
Cub CLI - Plan command.

The plan command provides a three-phase workflow for planning projects:
- orient: Research and understand the problem space
- architect: Design the solution architecture
- itemize: Break down into actionable tasks
"""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(
    name="plan",
    help="Plan projects with orient, architect, and itemize phases",
    no_args_is_help=True,
)

console = Console()


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
) -> None:
    """
    Research and understand the problem space.

    The orient phase gathers context about the project:
    - Analyzes captures and existing documentation
    - Identifies key concepts and constraints
    - Surfaces questions that need answers

    Examples:
        cub plan orient
        cub plan orient spec-abc123
        cub plan orient path/to/spec.md
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if verbose or debug:
        console.print(f"[dim]Debug mode: {debug}[/dim]")
        if spec:
            console.print(f"[dim]Spec: {spec}[/dim]")

    console.print("[yellow]orient command not yet implemented[/yellow]")
    raise typer.Exit(1)


@app.command()
def architect(
    ctx: typer.Context,
    spec: str | None = typer.Argument(
        None,
        help="Spec ID or path to architect from (default: active spec)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
) -> None:
    """
    Design the solution architecture.

    The architect phase designs the technical approach:
    - Proposes system structure and components
    - Identifies integration points
    - Documents design decisions and trade-offs

    Examples:
        cub plan architect
        cub plan architect spec-abc123
        cub plan architect path/to/spec.md
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if verbose or debug:
        console.print(f"[dim]Debug mode: {debug}[/dim]")
        if spec:
            console.print(f"[dim]Spec: {spec}[/dim]")

    console.print("[yellow]architect command not yet implemented[/yellow]")
    raise typer.Exit(1)


@app.command()
def itemize(
    ctx: typer.Context,
    spec: str | None = typer.Argument(
        None,
        help="Spec ID or path to itemize from (default: active spec)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
) -> None:
    """
    Break down the architecture into actionable tasks.

    The itemize phase creates the task breakdown:
    - Generates well-scoped tasks from the architecture
    - Orders tasks by dependencies
    - Assigns estimates and priorities

    Examples:
        cub plan itemize
        cub plan itemize spec-abc123
        cub plan itemize path/to/spec.md
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if verbose or debug:
        console.print(f"[dim]Debug mode: {debug}[/dim]")
        if spec:
            console.print(f"[dim]Spec: {spec}[/dim]")

    console.print("[yellow]itemize command not yet implemented[/yellow]")
    raise typer.Exit(1)
