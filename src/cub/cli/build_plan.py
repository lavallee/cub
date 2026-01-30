"""
Cub CLI - build-plan command.

Executes a staged plan by running cub for each epic in order,
with retry logic, branch management, and auto-commit of progress.
"""

import os
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def _find_build_plan_script() -> Path | None:
    """Locate the build-plan.sh script.

    Search order:
    1. Project-local: .cub/scripts/build-plan.sh
    2. Package templates (editable install): cub/../../../templates/scripts/
    3. Package templates (pip install): cub/templates/scripts/
    """
    # 1. Project-local copy
    local = Path.cwd() / ".cub" / "scripts" / "build-plan.sh"
    if local.exists():
        return local

    # 2/3. Package templates
    import cub

    cub_path = Path(cub.__file__).parent
    for candidate in (
        cub_path.parent.parent / "templates" / "scripts" / "build-plan.sh",
        cub_path / "templates" / "scripts" / "build-plan.sh",
    ):
        if candidate.exists():
            return candidate

    return None


def main(
    ctx: typer.Context,
    plan_slug: str = typer.Argument(
        ...,
        help="Plan slug (directory name under plans/)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without executing",
    ),
    start_epic: str | None = typer.Option(
        None,
        "--start-epic",
        help="Start from this epic (skip earlier ones)",
    ),
    only_epic: str | None = typer.Option(
        None,
        "--only-epic",
        help="Only run this specific epic",
    ),
    no_branch: bool = typer.Option(
        False,
        "--no-branch",
        help="Don't create a feature branch, use current branch",
    ),
    max_retries: int = typer.Option(
        3,
        "--max-retries",
        help="Max retry attempts per epic",
    ),
    retry_delay: int = typer.Option(
        10,
        "--retry-delay",
        help="Seconds between retries",
    ),
    main_ok: bool = typer.Option(
        False,
        "--main-ok",
        help="Allow running on main/master branch",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Stream harness output in real-time (default: on)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (e.g., sonnet, opus, haiku)",
    ),
) -> None:
    """
    Execute a staged plan by running cub for each epic.

    Takes a plan slug, creates a feature branch, and runs cub run --epic
    for each epic in order. Stops on failure and auto-commits progress.

    Examples:
        cub build-plan my-feature
        cub build-plan my-feature --dry-run
        cub build-plan my-feature --start-epic cub-d2v
        cub build-plan my-feature --only-epic cub-k8d
        cub build-plan my-feature --no-branch
        cub build-plan my-feature --no-branch --main-ok
    """
    script = _find_build_plan_script()
    if script is None:
        console.print("[red]Error: build-plan.sh script not found[/red]")
        console.print("[dim]Run 'cub init' or 'cub update' to install project scripts[/dim]")
        raise typer.Exit(1)

    # Build args
    cmd = ["bash", str(script), plan_slug]
    if dry_run:
        cmd.append("--dry-run")
    if start_epic:
        cmd.extend(["--start-epic", start_epic])
    if only_epic:
        cmd.extend(["--only-epic", only_epic])
    if no_branch:
        cmd.append("--no-branch")
    cmd.extend(["--max-retries", str(max_retries)])
    cmd.extend(["--retry-delay", str(retry_delay)])
    if main_ok:
        cmd.append("--main-ok")
    if not stream:
        cmd.append("--no-stream")
    if model:
        cmd.extend(["--model", model])

    # Pass through environment
    env = os.environ.copy()

    try:
        result = subprocess.run(cmd, env=env, check=False)
        raise typer.Exit(result.returncode)
    except KeyboardInterrupt:
        raise typer.Exit(130)
