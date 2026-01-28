"""
Init command implementation for generating instruction files.

This module provides functionality for generating AGENTS.md and CLAUDE.md
files at the project root during initialization. These files provide
workflow instructions for AI assistants running in direct harness mode.
"""

import shutil
from pathlib import Path

import typer
from rich.console import Console

from cub.cli.map import generate_map
from cub.core.config.loader import load_config
from cub.core.constitution import ensure_constitution
from cub.core.instructions import (
    generate_agents_md,
    generate_claude_md,
    upsert_managed_section,
)

console = Console()


def _ensure_runloop(project_dir: Path, force: bool = False) -> None:
    """
    Ensure runloop.md exists in .cub directory.

    Copies from templates if missing or if force=True.

    Args:
        project_dir: Path to the project root directory
        force: If True, overwrite existing file.
    """
    cub_dir = project_dir / ".cub"
    cub_dir.mkdir(exist_ok=True)

    target_path = cub_dir / "runloop.md"

    # Find templates directory
    import cub

    cub_path = Path(cub.__file__).parent
    # Try src layout first (editable install)
    templates_dir = cub_path.parent.parent / "templates"
    if not templates_dir.is_dir():
        # Try package layout (pip install)
        templates_dir = cub_path / "templates"
    if not templates_dir.is_dir():
        raise FileNotFoundError("Could not locate cub templates directory")

    source_path = templates_dir / "runloop.md"
    if not source_path.exists():
        raise FileNotFoundError(f"Template not found: {source_path}")

    if not target_path.exists() or force:
        shutil.copy2(source_path, target_path)


def generate_instruction_files(project_dir: Path, force: bool = False) -> None:
    """
    Generate AGENTS.md and CLAUDE.md instruction files at project root.

    Uses the managed section upsert engine to non-destructively update
    instruction files. Also ensures constitution and runloop are in place.

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

    # Ensure constitution exists
    try:
        ensure_constitution(project_dir, force=force)
        console.print("[green]✓[/green] Constitution ready")
    except Exception as e:
        console.print(f"[red]Error ensuring constitution: {e}[/red]")
        raise typer.Exit(1)

    # Copy runloop template
    try:
        _ensure_runloop(project_dir, force=force)
        console.print("[green]✓[/green] Runloop ready")
    except Exception as e:
        console.print(f"[red]Error ensuring runloop: {e}[/red]")
        raise typer.Exit(1)

    # Generate managed section content for AGENTS.md
    try:
        agents_content = generate_agents_md(project_dir, config)
        agents_path = project_dir / "AGENTS.md"
        result = upsert_managed_section(agents_path, agents_content, version=1)

        if result.action.value == "CREATED":
            console.print("[green]✓[/green] Created AGENTS.md")
        elif result.action.value == "APPENDED":
            console.print("[green]✓[/green] Added managed section to AGENTS.md")
        elif result.action.value == "REPLACED":
            console.print("[green]✓[/green] Updated managed section in AGENTS.md")

        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning: {warning}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error creating AGENTS.md: {e}[/red]")
        raise typer.Exit(1)

    # Generate managed section content for CLAUDE.md
    try:
        claude_content = generate_claude_md(project_dir, config)
        claude_path = project_dir / "CLAUDE.md"
        result = upsert_managed_section(claude_path, claude_content, version=1)

        if result.action.value == "CREATED":
            console.print("[green]✓[/green] Created CLAUDE.md")
        elif result.action.value == "APPENDED":
            console.print("[green]✓[/green] Added managed section to CLAUDE.md")
        elif result.action.value == "REPLACED":
            console.print("[green]✓[/green] Updated managed section in CLAUDE.md")

        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning: {warning}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error creating CLAUDE.md: {e}[/red]")
        raise typer.Exit(1)

    # Generate project map
    try:
        map_content = generate_map(project_dir, token_budget=4096, max_depth=4)
        map_path = project_dir / ".cub" / "map.md"
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(map_content, encoding="utf-8")
        console.print("[green]✓[/green] Generated project map at .cub/map.md")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not generate map: {e}[/yellow]")


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
