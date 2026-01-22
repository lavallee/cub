"""
Cub CLI - Plan command (delegated to bash).

The plan command provides a three-phase workflow for planning projects:
- orient: Research and understand the problem space
- architect: Design the solution architecture
- itemize: Break down into actionable tasks

This module delegates all commands to the bash implementation for reliability.
"""

from __future__ import annotations

import typer

from cub.core.bash_delegate import delegate_to_bash

app = typer.Typer(
    name="plan",
    help="Plan projects with orient, architect, and itemize phases",
    no_args_is_help=True,
)


def _get_debug(ctx: typer.Context) -> bool:
    """Extract debug flag from context."""
    if ctx.obj:
        return ctx.obj.get("debug", False)
    return False


@app.command()
def orient(
    ctx: typer.Context,
    spec: str | None = typer.Argument(
        None,
        help="Spec ID or path to orient from",
    ),
    plan: str | None = typer.Option(
        None,
        "--plan",
        help="Resume an existing plan by slug",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--auto",
        help="Run without user interaction (for CI/automation)",
    ),
) -> None:
    """
    Research and understand the problem space.

    The orient phase gathers context about the project:
    - Analyzes specs and existing documentation
    - Identifies key concepts and constraints
    - Surfaces questions that need answers

    Creates orientation.md in the plan directory.

    Examples:
        cub plan orient spec-abc123
        cub plan orient path/to/spec.md
        cub plan orient --plan my-feature
    """
    args = []
    if spec:
        args.extend(["--spec", spec])
    if plan:
        args.extend(["--plan", plan])
    if non_interactive:
        args.append("--non-interactive")

    delegate_to_bash("plan", ["orient"] + args, debug=_get_debug(ctx))


@app.command()
def architect(
    ctx: typer.Context,
    plan_slug: str | None = typer.Argument(
        None,
        help="Plan slug to continue (default: most recent plan with orient complete)",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--auto",
        help="Run without user interaction (for CI/automation)",
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
    """
    args = []
    if plan_slug:
        args.append(plan_slug)
    if non_interactive:
        args.append("--non-interactive")

    delegate_to_bash("plan", ["architect"] + args, debug=_get_debug(ctx))


@app.command()
def itemize(
    ctx: typer.Context,
    plan_slug: str | None = typer.Argument(
        None,
        help="Plan slug to itemize (default: most recent plan with architect complete)",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--auto",
        help="Run without user interaction (for CI/automation)",
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
    """
    args = []
    if plan_slug:
        args.append(plan_slug)
    if non_interactive:
        args.append("--non-interactive")

    delegate_to_bash("plan", ["itemize"] + args, debug=_get_debug(ctx))


@app.command("run")
def run_pipeline(
    ctx: typer.Context,
    spec: str | None = typer.Argument(
        None,
        help="Spec ID or path to plan from",
    ),
    plan: str | None = typer.Option(
        None,
        "--plan",
        help="Resume a specific plan by slug",
    ),
    continue_last: bool = typer.Option(
        False,
        "--continue",
        help="Continue the most recent plan",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--auto",
        help="Run without user interaction (for CI/automation)",
    ),
) -> None:
    """
    Run the full planning pipeline (orient -> architect -> itemize).

    This command runs all three planning phases in sequence:
    1. Orient: Research and understand the problem space
    2. Architect: Design the solution architecture
    3. Itemize: Break down into actionable tasks

    On completion, tasks are ready to be staged with 'cub stage'.

    Examples:
        cub plan run specs/researching/my-feature.md
        cub plan run my-feature
        cub plan run --continue  # Resume most recent plan
    """
    args = []
    if spec:
        args.extend(["--spec", spec])
    if plan:
        args.extend(["--plan", plan])
    if continue_last:
        args.append("--continue")
    if non_interactive:
        args.append("--non-interactive")

    delegate_to_bash("plan", ["run"] + args, debug=_get_debug(ctx))


@app.command("list")
def list_plans(
    ctx: typer.Context,
    show: str | None = typer.Argument(
        None,
        help="Show details of a specific plan",
    ),
) -> None:
    """
    List all plans in the project.

    Shows existing plans with their status and completion state.

    Examples:
        cub plan list              # List all plans
        cub plan list show         # Show most recent plan details
        cub plan list show slug    # Show specific plan details
    """
    args = []
    if show:
        args.extend(["show", show])

    delegate_to_bash("plan", ["list"] + args, debug=_get_debug(ctx))
