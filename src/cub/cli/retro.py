"""
Cub CLI - Retro command.

Generate retrospective reports for completed plans and epics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from cub.core.retro import RetroService, RetroServiceError

app = typer.Typer(
    name="retro",
    help="Generate retrospective reports",
    no_args_is_help=True,
)

console = Console()


@app.callback(invoke_without_command=True)
def retro_command(
    ctx: typer.Context,
    id: Annotated[
        str,
        typer.Argument(
            help="Epic or plan ID to generate retro for (e.g., cub-048a-4)",
        ),
    ],
    epic: Annotated[
        bool,
        typer.Option(
            "--epic",
            "-e",
            help="Treat as epic ID",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write report to file instead of stdout",
        ),
    ] = None,
) -> None:
    """
    Generate a retrospective report.

    This command generates a markdown retrospective report that includes:
    - Summary and timeline
    - Metrics (costs, tokens, duration)
    - Task list with outcomes
    - Key decisions made
    - Lessons learned
    - Issues encountered

    Examples:

        # Generate retro for an epic (to stdout)
        cub retro cub-048a-4

        # Generate retro with --epic flag
        cub retro cub-048a-4 --epic

        # Write retro to file
        cub retro cub-048a-4 --output retro.md

        # Write retro to file with explicit epic flag
        cub retro cub-048a-4 --epic --output retro.md
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    project_dir = Path.cwd()

    try:
        service = RetroService(project_dir)

        console.print(f"[cyan]Generating retrospective for {id}...[/cyan]")
        console.print()

        report = service.generate_retro(id, epic=epic)

        # Generate markdown
        markdown = report.to_markdown()

        # Output to file or stdout
        if output:
            output.write_text(markdown)
            console.print(f"[green]✓ Retrospective written to {output}[/green]")
        else:
            console.print(markdown)

    except RetroServiceError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)
