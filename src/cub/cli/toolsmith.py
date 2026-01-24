"""
Cub CLI - Toolsmith command.

Discover and catalog tools for use in Cub workflows.
Toolsmith manages tool definitions, metadata, and integration points.
"""

import logging
import sys
import time
import traceback
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from cub.core.toolsmith.adoption import AdoptionStore
from cub.core.toolsmith.exceptions import ToolsmithError
from cub.core.toolsmith.service import ToolsmithService
from cub.core.toolsmith.sources import get_all_sources
from cub.core.toolsmith.store import ToolsmithStore

console = Console()
app = typer.Typer(
    name="toolsmith",
    help="Discover and catalog tools",
)

# Global debug flag
_debug_mode = False


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for toolsmith commands.

    Args:
        debug: If True, enable DEBUG level logging and full tracebacks
    """
    global _debug_mode
    _debug_mode = debug

    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )


def handle_error(error: Exception, command_name: str) -> None:
    """
    Handle and display errors with appropriate user-friendly messages.

    Args:
        error: The exception that was raised
        command_name: Name of the command that failed
    """
    if isinstance(error, ToolsmithError):
        # User-friendly error message for toolsmith-specific errors
        error_text = Text()
        error_text.append("Error: ", style="bold red")
        error_text.append(str(error))

        # Add context if available
        if hasattr(error, "context") and error.context:
            error_text.append("\n\nContext:\n", style="dim")
            for key, value in error.context.items():
                error_text.append(f"  {key}: ", style="cyan")
                error_text.append(f"{value}\n", style="white")

        console.print()
        console.print(
            Panel(
                error_text,
                title="[bold red]Error[/bold red]",
                border_style="red",
                expand=False,
            )
        )

        if _debug_mode:
            console.print("\n[dim]Full traceback:[/dim]")
            console.print(traceback.format_exc())
    else:
        # Generic error handling for unexpected exceptions
        error_text = Text()
        error_text.append("Unexpected error in ", style="bold red")
        error_text.append(command_name, style="bold yellow")
        error_text.append(": ", style="bold red")
        error_text.append(str(error))

        console.print()
        console.print(
            Panel(
                error_text,
                title="[bold red]Unexpected Error[/bold red]",
                border_style="red",
                expand=False,
            )
        )

        if _debug_mode:
            console.print("\n[dim]Full traceback:[/dim]")
            console.print(traceback.format_exc())

    console.print()
    if not _debug_mode:
        console.print("[dim]Run with --debug for full traceback[/dim]")
        console.print()


def _get_service() -> ToolsmithService:
    """Get ToolsmithService instance with default store and all sources."""
    store = ToolsmithStore.default()
    sources = get_all_sources()
    return ToolsmithService(store, sources)


@app.command()
def sync(
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            "-s",
            help="Tool source to sync from (e.g., 'smithery', 'glama')",
        ),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug mode with full tracebacks and verbose logging",
        ),
    ] = False,
) -> None:
    """
    Sync tools from external sources into the tool catalog.

    Discover tools from specified sources and update the local catalog.
    Without --source, syncs from all configured sources.

    Examples:
        cub toolsmith sync
        cub toolsmith sync --source smithery
        cub toolsmith sync --source glama
        cub toolsmith sync --debug
    """
    setup_logging(debug)

    try:
        service = _get_service()

        # Determine which sources we're syncing
        source_names = [source] if source else None
        source_desc = f"source '{source}'" if source else "all sources"

        # Show progress while syncing with spinner
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Syncing from {source_desc}...", total=None)
            start_time = time.time()
            result = service.sync(source_names=source_names)
            elapsed = time.time() - start_time

        # Display results with formatted panel
        console.print()

        # Create summary text with status indicator
        status_indicator = Text("✓", style="bold green")
        summary_text = Text.from_markup(f"Sync complete in {elapsed:.2f}s")
        console.print(
            Panel(
                summary_text, title=status_indicator, border_style="green", expand=False
            )
        )
        console.print()

        # Create statistics table
        stats_table = Table(title="Sync Statistics", show_header=False, box=None)
        stats_table.add_column("Metric", style="cyan", no_wrap=True, width=20)
        stats_table.add_column("Count", justify="right", style="bold")

        stats_table.add_row("Tools added", Text(str(result.tools_added), style="green"))
        stats_table.add_row("Tools updated", Text(str(result.tools_updated), style="blue"))
        total_changes = result.tools_added + result.tools_updated
        stats_table.add_row(
            "Total changes",
            Text(str(total_changes), style="bold cyan"),
        )

        console.print(stats_table)
        console.print()

        # Show errors if any
        if result.errors:
            console.print()
            error_panel_content = Text()
            for i, error in enumerate(result.errors):
                if i > 0:
                    error_panel_content.append("\n")
                error_panel_content.append(f"• {error}")
            console.print(
                Panel(
                    error_panel_content,
                    title="[bold yellow]Warnings[/bold yellow]",
                    border_style="yellow",
                    expand=False,
                )
            )
            console.print()
            # Don't exit with error code if we still successfully synced some sources
            if result.tools_added == 0 and result.tools_updated == 0:
                raise typer.Exit(1)

    except Exception as e:
        handle_error(e, "sync")
        raise typer.Exit(1)


@app.command()
def search(
    query: Annotated[str, typer.Argument(..., help="Search query for tools")],
    live: Annotated[
        bool,
        typer.Option(
            "--live",
            "-l",
            help="Force live search instead of local catalog",
        ),
    ] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            "-s",
            help="Filter results by source (e.g., 'smithery', 'glama')",
        ),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug mode with full tracebacks and verbose logging",
        ),
    ] = False,
) -> None:
    """
    Search for tools by name, description, or capability.

    Search the local tool catalog or live sources for tools matching
    the query. Supports filtering by source.

    Examples:
        cub toolsmith search "database"
        cub toolsmith search "http" --live
        cub toolsmith search "api" --source smithery
        cub toolsmith search "database" --debug
    """
    setup_logging(debug)

    try:
        service = _get_service()

        # Perform search
        # Note: --live forces live_fallback=True, otherwise defaults to True
        # If we want --live to ONLY search live (skip local), we'd need to modify
        # the service API. For now, --live forces live_fallback behavior.
        results = service.search(query, live_fallback=True if live else True)

        # Filter by source if specified
        if source:
            results = [tool for tool in results if tool.source == source]

        # Display results
        if not results:
            console.print()
            no_results_text = Text.from_markup(
                f"[yellow]No tools found matching '[bold]{query}[/bold]'[/yellow]"
            )
            if source:
                no_results_text.append(
                    Text(f"\nFiltered by source: {source}", style="dim")
                )
            console.print(Panel(no_results_text, border_style="yellow", expand=False))
            console.print()
            return

        # Create results table with improved formatting
        title_text = f"Search Results: '{query}'"
        if source:
            title_text += f" (source: {source})"

        table = Table(title=title_text, border_style="cyan")
        table.add_column("ID", style="dim", no_wrap=True, width=28)
        table.add_column("Name", style="cyan", no_wrap=True, width=20)
        table.add_column("Type", style="magenta", width=15)
        table.add_column("Source", style="blue", width=15)
        table.add_column("Description", style="white")

        for tool in results:
            # Truncate long descriptions with ellipsis
            description = tool.description
            max_desc_length = 60
            if len(description) > max_desc_length:
                description = description[: max_desc_length - 3] + "..."

            table.add_row(
                tool.id,
                tool.name,
                tool.tool_type.value.replace("_", " ").title(),
                tool.source,
                description,
            )

        console.print()
        console.print(table)
        console.print()

        # Display results summary
        result_summary = Text()
        result_summary.append("Found ", style="dim")
        result_summary.append(str(len(results)), style="bold green")
        result_summary.append(f" tool{'s' if len(results) != 1 else ''}", style="dim")
        console.print(result_summary)

    except Exception as e:
        handle_error(e, "search")
        raise typer.Exit(1)


@app.command()
def adopt(
    tool_id: Annotated[str, typer.Argument(..., help="Tool ID to adopt (see 'cub toolsmith search')")],
    note: Annotated[
        str | None,
        typer.Option("--note", help="Optional note about why/how we are adopting this tool"),
    ] = None,
) -> None:
    """Adopt a tool for this project.

    Records intent to use a tool (and optional note) in .cub/toolsmith/adopted.json.

    This is a lightweight workflow step: discovery → adoption → (future) install/execute.
    """
    try:
        store = AdoptionStore.default()
        record = store.adopt(tool_id=tool_id, note=note)
        console.print()
        console.print(
            Panel(
                Text.from_markup(
                    f"[bold green]Adopted[/bold green] [cyan]{record.tool_id}[/cyan]\n"
                    f"[dim]adopted_at:[/dim] {record.adopted_at.isoformat()}"
                ),
                border_style="green",
                expand=False,
            )
        )
        console.print()
    except Exception as e:
        handle_error(e, "adopt")
        raise typer.Exit(1)


@app.command()
def adopted() -> None:
    """List adopted tools for this project."""
    try:
        store = AdoptionStore.default()
        adopted_tools = store.list()
        if not adopted_tools:
            console.print()
            console.print(Panel(Text("No adopted tools yet."), border_style="yellow", expand=False))
            console.print()
            return

        table = Table(title="Adopted Tools", border_style="green")
        table.add_column("Tool ID", style="cyan")
        table.add_column("Adopted At", style="dim", no_wrap=True)
        table.add_column("Note", style="white")
        for a in adopted_tools:
            table.add_row(a.tool_id, a.adopted_at.isoformat(), a.note or "")

        console.print()
        console.print(table)
        console.print()
    except Exception as e:
        handle_error(e, "adopted")
        raise typer.Exit(1)


@app.command()
def stats(
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug mode with full tracebacks and verbose logging",
        ),
    ] = False,
) -> None:
    """
    Show statistics about the tool catalog.

    Display metrics including total tools, sources, capabilities,
    and catalog health.

    Examples:
        cub toolsmith stats
        cub toolsmith stats --debug
    """
    setup_logging(debug)

    try:
        service = _get_service()
        catalog_stats = service.stats()

        # Display overview with panel
        console.print()
        overview_table = Table(show_header=False, box=None)
        overview_table.add_column("Metric", style="cyan", no_wrap=True, width=15)
        overview_table.add_column("Value", style="bold")

        overview_table.add_row(
            "Total tools", Text(str(catalog_stats.total_tools), style="bold cyan")
        )

        if catalog_stats.last_sync:
            last_sync_str = catalog_stats.last_sync.strftime("%Y-%m-%d %H:%M:%S UTC")
            overview_table.add_row("Last sync", Text(last_sync_str, style="dim"))
        else:
            overview_table.add_row("Last sync", Text("Never", style="yellow"))

        console.print(
            Panel(
                overview_table,
                title="[bold]Tool Catalog Overview[/bold]",
                border_style="blue",
                expand=False,
            )
        )
        console.print()

        # Tools by source table
        if catalog_stats.by_source:
            source_table = Table(title="Tools by Source", border_style="cyan")
            source_table.add_column("Source", style="cyan", width=20)
            source_table.add_column("Count", justify="right", style="green", width=10)

            sorted_sources = sorted(
                catalog_stats.by_source.items(), key=lambda x: x[1], reverse=True
            )
            for source, count in sorted_sources:
                source_table.add_row(source, str(count))

            console.print(source_table)
            console.print()
        else:
            console.print("[yellow]No sources have been synced yet[/yellow]")
            console.print()

        # Tools by type table
        if catalog_stats.by_type:
            type_table = Table(title="Tools by Type", border_style="magenta")
            type_table.add_column("Type", style="magenta", width=20)
            type_table.add_column("Count", justify="right", style="green", width=10)

            sorted_types = sorted(
                catalog_stats.by_type.items(), key=lambda x: x[1], reverse=True
            )
            for tool_type, count in sorted_types:
                type_table.add_row(tool_type.replace("_", " ").title(), str(count))

            console.print(type_table)
            console.print()
        else:
            console.print("[yellow]No tools available yet[/yellow]")
            console.print()

        # Sources synced
        if catalog_stats.sources_synced:
            synced_text = Text()
            synced_text.append("Synced Sources:\n", style="bold")
            for source in sorted(catalog_stats.sources_synced):
                synced_text.append(f"  • {source}\n", style="blue")
            synced_text.rstrip()
            console.print(Panel(synced_text, border_style="green", expand=False))
        else:
            help_text = Text()
            help_text.append("No sources have been synced yet\n", style="yellow")
            help_text.append("Run ", style="dim")
            help_text.append("cub toolsmith sync", style="bold cyan")
            help_text.append(" to sync tools from all sources", style="dim")
            console.print(Panel(help_text, border_style="yellow", expand=False))

    except Exception as e:
        handle_error(e, "stats")
        raise typer.Exit(1)


__all__ = ["app"]
