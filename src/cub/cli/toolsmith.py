"""
Cub CLI - Toolsmith command.

Discover and catalog tools for use in Cub workflows.
Toolsmith manages tool definitions, metadata, and integration points.
"""

import time
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from cub.core.toolsmith.service import ToolsmithService
from cub.core.toolsmith.sources import get_all_sources
from cub.core.toolsmith.store import ToolsmithStore

console = Console()
app = typer.Typer(
    name="toolsmith",
    help="Discover and catalog tools",
)


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
) -> None:
    """
    Sync tools from external sources into the tool catalog.

    Discover tools from specified sources and update the local catalog.
    Without --source, syncs from all configured sources.

    Examples:
        cub toolsmith sync
        cub toolsmith sync --source smithery
        cub toolsmith sync --source glama
    """
    service = _get_service()

    # Determine which sources we're syncing
    source_names = [source] if source else None
    source_desc = f"source '{source}'" if source else "all sources"

    # Show progress while syncing
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Syncing from {source_desc}...", total=None)
        start_time = time.time()
        result = service.sync(source_names=source_names)
        elapsed = time.time() - start_time

    # Display results
    console.print()
    console.print(f"[bold green]✓[/bold green] Sync complete in {elapsed:.2f}s")
    console.print()

    # Show sync statistics
    console.print(f"Tools added: [green]{result.tools_added}[/green]")
    console.print(f"Tools updated: [blue]{result.tools_updated}[/blue]")
    console.print(f"Total changes: [bold]{result.tools_added + result.tools_updated}[/bold]")

    # Show errors if any
    if result.errors:
        console.print()
        console.print("[yellow]Errors encountered:[/yellow]")
        for error in result.errors:
            console.print(f"  [red]•[/red] {error}")
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
) -> None:
    """
    Search for tools by name, description, or capability.

    Search the local tool catalog or live sources for tools matching
    the query. Supports filtering by source.

    Examples:
        cub toolsmith search "database"
        cub toolsmith search "http" --live
        cub toolsmith search "api" --source smithery
    """
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
        console.print(f"[yellow]No tools found matching '[/yellow]{query}[yellow]'[/yellow]")
        if source:
            console.print(f"[dim]Filtered by source: {source}[/dim]")
        return

    # Create results table
    table = Table(title=f"Search Results: '{query}'" + (f" (source: {source})" if source else ""))
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Source", style="blue")
    table.add_column("Description", style="white")

    for tool in results:
        table.add_row(
            tool.name,
            tool.tool_type.value.replace("_", " ").title(),
            tool.source,
            tool.description[:80] + "..." if len(tool.description) > 80 else tool.description,
        )

    console.print()
    console.print(table)
    console.print()
    console.print(f"[dim]Found {len(results)} tool(s)[/dim]")


@app.command()
def stats() -> None:
    """
    Show statistics about the tool catalog.

    Display metrics including total tools, sources, capabilities,
    and catalog health.

    Examples:
        cub toolsmith stats
    """
    service = _get_service()
    catalog_stats = service.stats()

    # Display overview
    console.print()
    console.print("[bold]Tool Catalog Statistics[/bold]")
    console.print()
    console.print(f"Total tools: [bold cyan]{catalog_stats.total_tools}[/bold cyan]")

    if catalog_stats.last_sync:
        last_sync_str = catalog_stats.last_sync.strftime("%Y-%m-%d %H:%M:%S UTC")
        console.print(f"Last sync: [dim]{last_sync_str}[/dim]")
    else:
        console.print("Last sync: [yellow]Never[/yellow]")

    console.print()

    # Tools by source table
    if catalog_stats.by_source:
        source_table = Table(title="Tools by Source")
        source_table.add_column("Source", style="cyan")
        source_table.add_column("Count", justify="right", style="green")

        sorted_sources = sorted(
            catalog_stats.by_source.items(), key=lambda x: x[1], reverse=True
        )
        for source, count in sorted_sources:
            source_table.add_row(source, str(count))

        console.print(source_table)
        console.print()

    # Tools by type table
    if catalog_stats.by_type:
        type_table = Table(title="Tools by Type")
        type_table.add_column("Type", style="magenta")
        type_table.add_column("Count", justify="right", style="green")

        sorted_types = sorted(
            catalog_stats.by_type.items(), key=lambda x: x[1], reverse=True
        )
        for tool_type, count in sorted_types:
            type_table.add_row(tool_type.replace("_", " ").title(), str(count))

        console.print(type_table)
        console.print()

    # Sources synced
    if catalog_stats.sources_synced:
        console.print("[bold]Synced Sources:[/bold]")
        for source in sorted(catalog_stats.sources_synced):
            console.print(f"  [blue]•[/blue] {source}")
    else:
        console.print("[yellow]No sources have been synced yet[/yellow]")
        console.print("[dim]Run 'cub toolsmith sync' to sync tools from all sources[/dim]")


__all__ = ["app"]
