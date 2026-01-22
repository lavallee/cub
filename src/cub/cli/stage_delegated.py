"""
Cub CLI - Stage command (delegated to bash).

The stage command imports tasks from completed plans into the task backend.
This is the final step of the planning pipeline.

This module delegates to the bash implementation for reliability.
"""

from __future__ import annotations

import typer

from cub.core.bash_delegate import delegate_to_bash

app = typer.Typer(
    name="stage",
    help="Import tasks from completed plans into the task backend",
)


def _get_debug(ctx: typer.Context) -> bool:
    """Extract debug flag from context."""
    if ctx.obj:
        return ctx.obj.get("debug", False)
    return False


@app.callback(invoke_without_command=True)
def stage(
    ctx: typer.Context,
    plan_slug: str | None = typer.Argument(
        None,
        help="Plan slug to stage (default: most recent plan with itemize complete)",
    ),
    prefix: str | None = typer.Option(
        None,
        "--prefix",
        help="Beads prefix for issue IDs",
    ),
    skip_prompt: bool = typer.Option(
        False,
        "--skip-prompt",
        help="Don't generate PROMPT.md and AGENT.md",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview actions without executing",
    ),
) -> None:
    """
    Import tasks from completed plans into the task backend.

    Stage initializes beads (if needed) and imports the generated plan:
    1. Run pre-flight checks (git, tools)
    2. Initialize beads (if needed)
    3. Import itemized-plan.jsonl
    4. Generate PROMPT.md and AGENT.md
    5. Create git commit

    Requires itemize phase to be complete first.

    Examples:
        cub stage                        # Stage most recent plan
        cub stage my-feature             # Stage specific plan
        cub stage --dry-run              # Preview staging actions
        cub stage --prefix myproj        # Use custom prefix
    """
    args = []
    if plan_slug:
        args.append(plan_slug)
    if prefix:
        args.extend(["--prefix", prefix])
    if skip_prompt:
        args.append("--skip-prompt")
    if dry_run:
        args.append("--dry-run")

    delegate_to_bash("stage", args, debug=_get_debug(ctx))
