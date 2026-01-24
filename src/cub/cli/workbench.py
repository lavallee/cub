"""Cub CLI - Workbench command.

MVP implementation for the PM Workbench concept:
- Create a session artifact under specs/workbench/sessions/
- Seed unknowns from a spec frontmatter
- Prefer adopted tools (Toolsmith) for next moves

This is intentionally minimal to support early experiments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from cub.core.workbench.session import create_pm_workbench_session

console = Console()
app = typer.Typer(name="workbench", help="PM Workbench: unknowns ledger + next move (MVP)")


@app.command("start")
def start(
    spec: Annotated[
        Path,
        typer.Option(
            "--spec",
            "-s",
            help="Spec file to seed the workbench session from",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = Path("specs/researching/pm-workbench.md"),
    session_id: Annotated[
        str | None,
        typer.Option("--id", help="Optional explicit session id"),
    ] = None,
) -> None:
    """Start a PM Workbench session from a spec."""
    out_dir = Path("specs") / "workbench" / "sessions"
    paths = create_pm_workbench_session(spec_path=spec, out_dir=out_dir, session_id=session_id)

    console.print()
    console.print(
        Panel(
            Text.from_markup(
                f"[bold green]Created workbench session[/bold green]\n"
                f"[dim]path:[/dim] {paths.session_path}"
            ),
            border_style="green",
            expand=False,
        )
    )
    console.print()
