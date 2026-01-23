"""
Cub CLI - Dashboard command.

Launch the project kanban dashboard web interface.
"""

import logging
import threading
import time
import webbrowser
from pathlib import Path

import typer
from rich.console import Console

from cub.utils.project import find_project_root

app = typer.Typer(
    name="dashboard",
    help="Launch project kanban dashboard",
    no_args_is_help=False,
)

console = Console()
logger = logging.getLogger(__name__)


def _get_project_paths() -> tuple[Path, Path, Path]:
    """
    Get project paths for dashboard.

    Returns:
        Tuple of (project_root, db_path, specs_root)

    Raises:
        typer.Exit: If not in a project directory
    """
    project_root = find_project_root()
    if project_root is None:
        console.print(
            "[red]Error:[/red] Not in a project directory. "
            "Could not find .beads/, .cub/, .cub.json, or .git/"
        )
        console.print("[dim]Run 'cub init' to initialize a project.[/dim]")
        raise typer.Exit(1)

    # Ensure .cub directory exists
    cub_dir = project_root / ".cub"
    cub_dir.mkdir(exist_ok=True)

    db_path = cub_dir / "dashboard.db"
    specs_root = project_root / "specs"

    return project_root, db_path, specs_root


@app.callback(invoke_without_command=True)
def dashboard(
    ctx: typer.Context,
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port to run the server on",
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Don't open browser automatically",
    ),
    no_sync: bool = typer.Option(
        False,
        "--no-sync",
        help="Skip initial data sync",
    ),
) -> None:
    """
    Launch the project kanban dashboard.

    This command:
    1. Syncs project data (specs, plans, tasks) to SQLite
    2. Starts the FastAPI server
    3. Opens the dashboard in your default browser

    The dashboard provides a visual kanban board showing all project
    entities across 8 lifecycle stages from "researching" to "released".

    Examples:
        cub dashboard                  # Launch on default port 8080
        cub dashboard --port 3000      # Launch on port 3000
        cub dashboard --no-browser     # Don't open browser
        cub dashboard --no-sync        # Skip initial sync
    """
    # If subcommand is provided, don't run main command
    if ctx.invoked_subcommand is not None:
        return

    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if debug:
        logging.basicConfig(level=logging.DEBUG)
        console.print("[dim]Debug mode enabled[/dim]")

    try:
        project_root, db_path, specs_root = _get_project_paths()

        if debug:
            console.print(f"[dim]Project root: {project_root}[/dim]")
            console.print(f"[dim]Database: {db_path}[/dim]")
            console.print(f"[dim]Specs root: {specs_root}[/dim]")

        # Import dashboard dependencies
        try:
            import uvicorn

            from cub.core.dashboard.api.app import app as fastapi_app
            from cub.core.dashboard.sync import SyncOrchestrator
        except ImportError as e:
            console.print(
                "[red]Error:[/red] Dashboard dependencies not installed. "
                f"Missing module: {e.name}"
            )
            console.print(
                "[dim]Install with: pip install fastapi uvicorn[/dim]"
            )
            raise typer.Exit(1)

        # Sync data unless --no-sync
        if not no_sync:
            console.print("[cyan]Syncing project data...[/cyan]")

            orchestrator = SyncOrchestrator(
                db_path=db_path,
                specs_root=specs_root,
            )

            result = orchestrator.sync()

            if result.success:
                console.print(
                    f"[green]✓[/green] Sync complete: "
                    f"{result.entities_added} entities added"
                )
                if result.warnings:
                    for warning in result.warnings:
                        console.print(f"[yellow]Warning:[/yellow] {warning}")
            else:
                console.print("[red]Sync failed:[/red]")
                for error in result.errors:
                    console.print(f"  • {error}")
                console.print("\n[yellow]Starting server with partial data...[/yellow]")

        # Store db_path in FastAPI app state for routes to use
        fastapi_app.state.db_path = db_path

        # Start server
        url = f"http://localhost:{port}"
        console.print("\n[bold cyan]Starting dashboard server...[/bold cyan]")
        console.print(f"[dim]API: {url}/api/board[/dim]")
        console.print(f"[dim]Docs: {url}/docs[/dim]")

        # Open browser after a short delay
        if not no_browser:
            def open_browser() -> None:
                time.sleep(1.5)  # Wait for server to start
                console.print(f"\n[green]Opening browser:[/green] {url}")
                webbrowser.open(url)

            threading.Thread(target=open_browser, daemon=True).start()

        console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

        # Run server (this blocks)
        uvicorn.run(
            fastapi_app,
            host="127.0.0.1",
            port=port,
            log_level="info" if debug else "warning",
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command()
def sync(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force full sync (ignore checksums)",
    ),
) -> None:
    """
    Sync project data to dashboard database.

    Parses specs, plans, tasks, and ledger entries and writes them
    to the SQLite database used by the dashboard.

    This command is useful for:
    - Updating the dashboard after making changes
    - Debugging sync issues
    - Pre-populating the database before starting the server

    Examples:
        cub dashboard sync             # Incremental sync
        cub dashboard sync --force     # Full sync
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if debug:
        logging.basicConfig(level=logging.DEBUG)
        console.print("[dim]Debug mode enabled[/dim]")

    try:
        project_root, db_path, specs_root = _get_project_paths()

        if debug:
            console.print(f"[dim]Project root: {project_root}[/dim]")
            console.print(f"[dim]Database: {db_path}[/dim]")
            console.print(f"[dim]Specs root: {specs_root}[/dim]")

        # Import dashboard sync dependency
        try:
            from cub.core.dashboard.sync import SyncOrchestrator
        except ImportError as e:
            console.print(
                "[red]Error:[/red] Dashboard dependencies not installed. "
                f"Missing module: {e.name}"
            )
            console.print(
                "[dim]Install with: pip install fastapi uvicorn[/dim]"
            )
            raise typer.Exit(1)

        console.print("[cyan]Syncing project data...[/cyan]")

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=specs_root,
        )

        result = orchestrator.sync(force_full_sync=force)

        if result.success:
            console.print("\n[bold green]✓ Sync successful[/bold green]")
            console.print(f"  Entities added: {result.entities_added}")
            console.print(f"  Entities updated: {result.entities_updated}")
            console.print(f"  Duration: {result.duration_seconds:.2f}s")

            if result.sources_synced:
                console.print(f"  Sources: {', '.join(result.sources_synced)}")

            if result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in result.warnings:
                    console.print(f"  • {warning}")

            # Show stats
            stats = orchestrator.get_stats()
            if stats["total"] > 0:
                console.print("\n[bold]Database statistics:[/bold]")
                console.print(f"  Total entities: {stats['total']}")
                if stats["by_type"]:
                    console.print("  By type:")
                    for entity_type, count in stats["by_type"].items():
                        console.print(f"    {entity_type}: {count}")
                if stats["by_stage"]:
                    console.print("  By stage:")
                    for stage, count in stats["by_stage"].items():
                        console.print(f"    {stage}: {count}")
        else:
            console.print("\n[bold red]✗ Sync failed[/bold red]")
            for error in result.errors:
                console.print(f"  • {error}")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


__all__ = ["app"]
