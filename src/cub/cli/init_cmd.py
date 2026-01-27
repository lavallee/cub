"""
Init command implementation for generating instruction files.

This module provides functionality for generating AGENTS.md and CLAUDE.md
files at the project root during initialization. These files provide
workflow instructions for AI assistants running in direct harness mode.
"""

from pathlib import Path

import typer
from rich.console import Console

from cub.core.config.loader import load_config
from cub.core.instructions import generate_agents_md, generate_claude_md

console = Console()


def generate_instruction_files(project_dir: Path, force: bool = False) -> None:
    """
    Generate AGENTS.md and CLAUDE.md instruction files at project root.

    Args:
        project_dir: Path to the project root directory
        force: If True, overwrite existing files. If False, skip if files exist.

    Raises:
        typer.Exit: If configuration cannot be loaded
    """
    try:
        config = load_config(project_dir)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        console.print("[yellow]Using default configuration[/yellow]")
        # Create a minimal default config
        from cub.core.config.models import (
            CircuitBreakerConfig,
            CubConfig,
            HarnessConfig,
        )

        config = CubConfig(
            harness=HarnessConfig(name="auto", priority=["claude", "codex"]),
            circuit_breaker=CircuitBreakerConfig(timeout_minutes=30, enabled=True),
        )

    # Generate AGENTS.md
    agents_path = project_dir / "AGENTS.md"
    if agents_path.exists() and not force:
        console.print("[yellow]AGENTS.md already exists, skipping[/yellow]")
    else:
        try:
            agents_content = generate_agents_md(project_dir, config)
            agents_path.write_text(agents_content)
            console.print("[green]✓[/green] Created AGENTS.md")
        except Exception as e:
            console.print(f"[red]Error creating AGENTS.md: {e}[/red]")
            raise typer.Exit(1)

    # Generate CLAUDE.md
    claude_path = project_dir / "CLAUDE.md"
    if claude_path.exists() and not force:
        console.print("[yellow]CLAUDE.md already exists, skipping[/yellow]")
    else:
        try:
            claude_content = generate_claude_md(project_dir, config)
            claude_path.write_text(claude_content)
            console.print("[green]✓[/green] Created CLAUDE.md")
        except Exception as e:
            console.print(f"[red]Error creating CLAUDE.md: {e}[/red]")
            raise typer.Exit(1)


def main(
    project_dir: str = typer.Argument(
        ".",
        help="Project directory to initialize (default: current directory)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing instruction files",
    ),
) -> None:
    """
    Generate AGENTS.md and CLAUDE.md instruction files.

    This command is typically called automatically by 'cub init' but can
    be run standalone to regenerate instruction files.
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    if not project_path.is_dir():
        console.print(f"[red]Error: Not a directory: {project_path}[/red]")
        raise typer.Exit(1)

    generate_instruction_files(project_path, force=force)


if __name__ == "__main__":
    typer.run(main)
