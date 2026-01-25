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

from cub.core.workbench.note import write_research_note_from_session
from cub.core.workbench.run import run_next_move
from cub.core.workbench.session import create_pm_workbench_session

console = Console()
app = typer.Typer(name="workbench", help="PM Workbench: unknowns ledger + next move (MVP)")


def _latest_session_path() -> Path | None:
    sessions_dir = Path("specs") / "workbench" / "sessions"
    if not sessions_dir.exists():
        return None
    sessions = sorted(sessions_dir.glob("wb-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions[0] if sessions else None


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


@app.command("run-next")
def run_next(
    session: Annotated[
        Path | None,
        typer.Option(
            "--session",
            "-f",
            help="Workbench session file to run (defaults to most recent)",
        ),
    ] = None,
    write_note: Annotated[
        bool,
        typer.Option(
            "--write-note/--no-write-note",
            help="Write/append a markdown note from tool run artifacts",
        ),
    ] = False,
) -> None:
    """Run the current session's Next Move.

    Executes the tool specified in the session frontmatter (if any) and
    appends run artifact links back into the session file.
    """
    session_path = session
    if session_path is None:
        session_path = _latest_session_path()

    if session_path is None:
        raise typer.BadParameter("No sessions found. Create one with: cub workbench start")

    if not session_path.exists():
        raise typer.BadParameter(f"Session file not found: {session_path}")

    result = run_next_move(session_path=session_path)

    note_path: Path | None = None
    if write_note:
        # Prefer the path declared in the session next_move.artifact_plan.path.
        try:
            import frontmatter

            post = frontmatter.load(result.session_path)
            meta = post.metadata if isinstance(post.metadata, dict) else {}
            nm_raw = meta.get("next_move")
            nm = nm_raw if isinstance(nm_raw, dict) else {}
            ap_raw = nm.get("artifact_plan")
            ap = ap_raw if isinstance(ap_raw, dict) else {}
            np = ap.get("path")
            if isinstance(np, str) and np.strip():
                note_path = Path(np)
        except Exception:
            note_path = None

        if note_path is None:
            note_path = Path("specs") / "investigations" / "research" / "workbench-research.md"

        write_research_note_from_session(session_path=result.session_path, note_path=note_path)

    console.print()
    console.print(
        Panel(
            Text.from_markup(
                f"[bold green]Ran next move[/bold green]\n"
                f"[dim]session:[/dim] {result.session_path}\n"
                f"[dim]tool:[/dim] {result.tool_id}\n"
                f"[dim]artifacts:[/dim] {len(result.artifact_paths)}"
                + (f"\n[dim]note:[/dim] {note_path}" if note_path else "")
            ),
            border_style="green",
            expand=False,
        )
    )
    console.print()
