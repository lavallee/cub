"""cub new - Create a new cub project."""

import os
import subprocess
from pathlib import Path

import typer
from rich.console import Console

from cub.core.bash_delegate import find_bash_cub
from cub.utils.hooks import HookContext, run_hooks

console = Console()


def new(
    ctx: typer.Context,
    directory: str = typer.Argument(..., help="Directory to create for the new project"),
) -> None:
    """Create a new project directory ready for cub-based development."""
    project_dir = Path(directory).resolve()
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    # Case: directory exists with files
    if project_dir.exists() and any(project_dir.iterdir()):
        confirm = typer.confirm(
            f"Directory '{project_dir}' already has files. Run cub init there instead?"
        )
        if not confirm:
            raise typer.Exit(0)
    else:
        # Create directory if needed
        project_dir.mkdir(parents=True, exist_ok=True)

    # Git init if no .git directory
    if not (project_dir / ".git").exists():
        result = subprocess.run(
            ["git", "init"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            console.print(f"[red]git init failed:[/red] {result.stderr.strip()}")
            raise typer.Exit(1)
        console.print(f"[green]Initialized git repository in {project_dir}[/green]")

    # Run cub init (delegated to bash, same pattern as delegated.init)
    try:
        bash_cub = find_bash_cub()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    env = os.environ.copy()
    if debug:
        env["CUB_DEBUG"] = "true"

    init_result = subprocess.run(
        [str(bash_cub), "init"],
        cwd=project_dir,
        env=env,
        check=False,
    )

    if init_result.returncode != 0:
        console.print("[red]cub init failed[/red]")
        raise typer.Exit(init_result.returncode)

    # Fire post-init hook
    hook_ctx = HookContext(
        hook_name="post-init",
        project_dir=project_dir,
        init_type="project",
    )
    run_hooks("post-init", hook_ctx, project_dir)

    console.print(f"\n[green bold]Project ready at {project_dir}[/green bold]")
    raise typer.Exit(0)
