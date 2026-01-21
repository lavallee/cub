"""
Cub CLI - Spec command.

Create feature specifications through an interactive interview process.
"""

import subprocess
from pathlib import Path

import typer
from rich.console import Console

console = Console()


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
        help="List specs in researching stage",
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
        cub spec --list                    # List researching specs
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    # Handle --list flag
    if list_specs:
        _list_researching_specs(debug)
        return

    # Ensure specs/researching directory exists
    specs_dir = Path("specs/researching")
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

        # Exit with the same code as Claude
        raise typer.Exit(result.returncode)
    except FileNotFoundError:
        console.print(
            "[red]Error:[/red] Claude CLI not found. "
            "Please install Claude Code from https://claude.ai/download"
        )
        raise typer.Exit(1)


def _list_researching_specs(debug: bool) -> None:
    """List specs in the researching stage."""
    specs_dir = Path("specs/researching")

    if not specs_dir.exists():
        console.print("[yellow]No specs/researching directory found.[/yellow]")
        console.print("[dim]Run 'cub spec' to create your first spec.[/dim]")
        return

    spec_files = sorted(specs_dir.glob("*.md"))

    if not spec_files:
        console.print("[yellow]No specs in researching stage.[/yellow]")
        console.print("[dim]Run 'cub spec' to create your first spec.[/dim]")
        return

    console.print(f"[bold]Specs in researching ({len(spec_files)}):[/bold]")
    console.print()

    for spec_file in spec_files:
        # Try to extract title from frontmatter or first heading
        title = _extract_spec_title(spec_file)
        readiness = _extract_readiness(spec_file)

        readiness_str = f"[{readiness}/10]" if readiness is not None else ""
        console.print(f"  [cyan]{spec_file.stem}[/cyan] {readiness_str}")
        if title and title != spec_file.stem:
            console.print(f"    [dim]{title}[/dim]")

    console.print()
    console.print("[dim]View a spec: cat specs/researching/<name>.md[/dim]")
    console.print("[dim]Plan a spec: cub plan run specs/researching/<name>.md[/dim]")


def _extract_spec_title(spec_file: Path) -> str | None:
    """Extract title from spec file (first heading or frontmatter)."""
    try:
        content = spec_file.read_text()
        lines = content.split("\n")

        # Skip frontmatter
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter:
                continue
            # First non-frontmatter line that's a heading
            if line.startswith("# "):
                return line[2:].strip()

        return None
    except OSError:
        return None


def _extract_readiness(spec_file: Path) -> int | None:
    """Extract readiness score from spec frontmatter."""
    try:
        content = spec_file.read_text()
        lines = content.split("\n")

        in_frontmatter = False
        in_readiness = False

        for line in lines:
            if line.strip() == "---":
                if in_frontmatter:
                    break  # End of frontmatter
                in_frontmatter = True
                continue

            if not in_frontmatter:
                continue

            if line.startswith("readiness:"):
                in_readiness = True
                continue

            if in_readiness and "score:" in line:
                # Extract score value
                parts = line.split(":")
                if len(parts) >= 2:
                    try:
                        return int(parts[-1].strip())
                    except ValueError:
                        pass

            # Reset if we hit another top-level key
            if in_readiness and line and not line.startswith(" ") and not line.startswith("\t"):
                in_readiness = False

        return None
    except OSError:
        return None
