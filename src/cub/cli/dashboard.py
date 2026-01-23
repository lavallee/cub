"""
Cub CLI - Dashboard command.

Launch the project kanban dashboard web interface.
"""

import logging
import shutil
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
err_console = Console(stderr=True)
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

            # Detect project paths for sync sources
            plans_root = project_root / ".cub" / "sessions"
            ledger_path = project_root / ".cub" / "ledger"
            changelog_path = project_root / "CHANGELOG.md"

            orchestrator = SyncOrchestrator(
                db_path=db_path,
                specs_root=specs_root,
                plans_root=plans_root if plans_root.exists() else None,
                tasks_backend="beads",  # Use beads task backend
                ledger_path=ledger_path if ledger_path.exists() else None,
                changelog_path=changelog_path if changelog_path.exists() else None,
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

        # Detect project paths for sync sources
        plans_root = project_root / ".cub" / "sessions"
        ledger_path = project_root / ".cub" / "ledger"
        changelog_path = project_root / "CHANGELOG.md"

        orchestrator = SyncOrchestrator(
            db_path=db_path,
            specs_root=specs_root,
            plans_root=plans_root if plans_root.exists() else None,
            tasks_backend="beads",  # Use beads task backend
            ledger_path=ledger_path if ledger_path.exists() else None,
            changelog_path=changelog_path if changelog_path.exists() else None,
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


@app.command()
def export(
    ctx: typer.Context,
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    ),
    pretty: bool = typer.Option(
        True,
        "--pretty/--compact",
        help="Pretty-print JSON with indentation",
    ),
) -> None:
    """
    Export board data as JSON.

    Exports the current dashboard state including all entities, columns,
    and statistics. Useful for:

    - Scripting and automation
    - Backup and restore
    - Integration with external tools
    - Data analysis with jq

    Examples:
        cub dashboard export                    # Print to stdout
        cub dashboard export -o board.json      # Save to file
        cub dashboard export --compact          # Minified JSON
        cub dashboard export | jq '.stats'      # Pipe to jq
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if debug:
        logging.basicConfig(level=logging.DEBUG)
        err_console.print("[dim]Debug mode enabled[/dim]")

    try:
        project_root, db_path, specs_root = _get_project_paths()

        if debug:
            err_console.print(f"[dim]Database: {db_path}[/dim]")

        # Check if database exists
        if not db_path.exists():
            err_console.print("[red]Error:[/red] Dashboard database not found.")
            err_console.print(
                "[dim]Run 'cub dashboard sync' first to create the database.[/dim]"
            )
            raise typer.Exit(1)

        # Import dashboard dependencies
        try:
            from cub.core.dashboard.db.connection import get_connection
            from cub.core.dashboard.db.queries import get_board_data
        except ImportError as e:
            err_console.print(
                "[red]Error:[/red] Dashboard dependencies not installed. "
                f"Missing module: {e.name}"
            )
            raise typer.Exit(1)

        # Fetch board data
        with get_connection(db_path) as conn:
            board = get_board_data(conn)

        # Serialize to JSON
        indent = 2 if pretty else None
        json_output = board.model_dump_json(indent=indent, exclude_none=True)

        # Output
        if output:
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json_output)
                err_console.print(f"[green]✓[/green] Exported to {output}")
            except PermissionError:
                err_console.print(
                    f"[red]Error:[/red] Permission denied writing to {output}"
                )
                raise typer.Exit(1)
            except OSError as e:
                err_console.print(f"[red]Error:[/red] Failed to write file: {e}")
                raise typer.Exit(1)
        else:
            # Print to stdout (use print, not console, to avoid Rich formatting)
            print(json_output)

    except typer.Exit:
        raise
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        if debug:
            import traceback
            err_console.print(traceback.format_exc())
        raise typer.Exit(1)


# Example files to copy during init
EXAMPLE_VIEW_FILES = [
    "default-view.yaml",
    "sprint-view.yaml",
    "ideas-view.yaml",
]


def _get_examples_dir() -> Path:
    """Get the path to the examples directory bundled with the package."""
    # The examples are in src/cub/dashboard/examples/ relative to this file
    # This file is at src/cub/cli/dashboard.py
    # So we need to go up to src/cub, then into dashboard/examples
    return Path(__file__).parent.parent / "dashboard" / "examples"


@app.command()
def views(
    ctx: typer.Context,
) -> None:
    """
    List available dashboard views.

    Displays all available views (both built-in and custom) without starting
    the server. Each view represents a different way to organize and visualize
    your project entities on the kanban board.

    Built-in views:
    - default: Full 8-column workflow (Captures → Released)
    - sprint: Active work focused (Ready → In Progress → Review → Complete)
    - ideas: Idea development focused (Captures → Specs → Planned)

    Custom views can be created by:
    1. Running 'cub dashboard init' to copy example view configurations
    2. Editing the YAML files in .cub/views/
    3. Views are automatically loaded - just refresh to see changes

    Examples:
        cub dashboard views              # List all available views
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if debug:
        logging.basicConfig(level=logging.DEBUG)
        console.print("[dim]Debug mode enabled[/dim]")

    try:
        # Import dashboard views dependencies
        try:
            from cub.core.dashboard.views import list_views
        except ImportError as e:
            console.print(
                "[red]Error:[/red] Dashboard dependencies not installed. "
                f"Missing module: {e.name}"
            )
            console.print(
                "[dim]Install with: pip install pyyaml[/dim]"
            )
            raise typer.Exit(1)

        # Get all available views
        view_summaries = list_views(use_cache=False)

        if not view_summaries:
            console.print("[yellow]No views found[/yellow]")
            raise typer.Exit(1)

        # Display views in a formatted list
        console.print("\n[bold cyan]Available Dashboard Views[/bold cyan]\n")

        for view in view_summaries:
            # Highlight default view
            prefix = "[green]●[/green]" if view.is_default else "○"
            default_indicator = " [dim](default)[/dim]" if view.is_default else ""

            console.print(f"{prefix} [bold]{view.name}[/bold]{default_indicator}")
            console.print(f"  [dim]ID:[/dim] {view.id}")
            if view.description:
                console.print(f"  [dim]{view.description}[/dim]")
            console.print()

        # Show summary
        console.print(f"[bold]Summary:[/bold] {len(view_summaries)} view(s) available")

        # Check if .cub/views directory exists
        project_root = None
        try:
            from cub.utils.project import find_project_root
            project_root = find_project_root()
        except Exception:
            pass

        if project_root:
            views_dir = project_root / ".cub" / "views"
            if views_dir.exists():
                custom_files = list(views_dir.glob("*.yaml")) + list(views_dir.glob("*.yml"))
                if custom_files:
                    console.print(
                        f"[dim]Custom views stored in:[/dim] {views_dir}"
                    )

        console.print(
            "\n[dim]Use 'cub dashboard init' to create custom view configurations.[/dim]"
        )

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command()
def init(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing view files",
    ),
) -> None:
    """
    Initialize dashboard with example view configurations.

    Copies example YAML files to .cub/views/ so you can customize them.
    Run this to get started with custom view configurations.

    Examples:
        cub dashboard init              # Copy example views
        cub dashboard init --force      # Overwrite existing files
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if debug:
        logging.basicConfig(level=logging.DEBUG)
        console.print("[dim]Debug mode enabled[/dim]")

    try:
        project_root, db_path, specs_root = _get_project_paths()

        # Create .cub/views/ directory if it doesn't exist
        views_dir = project_root / ".cub" / "views"
        views_dir.mkdir(parents=True, exist_ok=True)

        if debug:
            console.print(f"[dim]Views directory: {views_dir}[/dim]")

        # Get examples directory
        examples_dir = _get_examples_dir()
        if not examples_dir.exists():
            console.print(
                "[red]Error:[/red] Examples directory not found. "
                "This may indicate a broken installation."
            )
            raise typer.Exit(1)

        if debug:
            console.print(f"[dim]Examples directory: {examples_dir}[/dim]")

        # Copy each example file
        copied = []
        skipped = []

        for filename in EXAMPLE_VIEW_FILES:
            source = examples_dir / filename
            target = views_dir / filename

            if not source.exists():
                console.print(f"[yellow]Warning:[/yellow] Example file not found: {filename}")
                continue

            if target.exists() and not force:
                skipped.append(filename)
                continue

            shutil.copy(source, target)
            copied.append(filename)

        # Print summary
        if copied:
            console.print(f"\n[green]✓[/green] Copied {len(copied)} view configuration(s):")
            for filename in copied:
                console.print(f"  • {views_dir / filename}")

        if skipped:
            console.print(f"\n[yellow]Skipped {len(skipped)} existing file(s):[/yellow]")
            for filename in skipped:
                console.print(f"  • {filename}")
            console.print("[dim]Use --force to overwrite[/dim]")

        if not copied and not skipped:
            console.print("[yellow]No example files found to copy[/yellow]")
            raise typer.Exit(1)

        # Print helpful message
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Edit the YAML files in .cub/views/ to customize your views")
        console.print("  2. Run 'cub dashboard' to see your custom views")
        console.print("  3. Views are loaded automatically - just refresh to see changes")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


__all__ = ["app"]
