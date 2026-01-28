"""cub new - Create a new cub project."""

import subprocess
from pathlib import Path

import typer
from rich.console import Console

from cub.cli.init_cmd import init_project

console = Console()


def new(
    ctx: typer.Context,
    directory: str = typer.Argument(..., help="Directory to create for the new project"),
) -> None:
    """Create a new project directory ready for cub-based development."""
    project_dir = Path(directory).resolve()

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

    # Run cub init (native Python)
    init_project(project_dir, force=False, install_hooks_flag=True)

    console.print(f"\n[green bold]Project ready at {project_dir}[/green bold]")
    raise typer.Exit(0)
