"""
Cub CLI - Tools command.

Manage and execute tools via the unified tool execution runtime.
Provides commands for listing adapters, checking tool readiness,
and executing tools with various adapter types (HTTP, CLI, MCP).
"""

import asyncio
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cub.core.tools import (
    ExecutionService,
    list_adapters,
)
from cub.core.tools.metrics import MetricsStore

console = Console()
app = typer.Typer(
    name="tools",
    help="Manage and execute tools via the unified tool runtime",
)

# Global debug flag
_debug_mode = False


def setup_logging(debug: bool = False) -> None:
    """
    Configure logging for tools commands.

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
    error_text = Text()
    error_text.append("Error in ", style="bold red")
    error_text.append(command_name, style="bold yellow")
    error_text.append(": ", style="bold red")
    error_text.append(str(error))

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

    console.print()
    if not _debug_mode:
        console.print("[dim]Run with --debug for full traceback[/dim]")
        console.print()


@app.command()
def list(
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug mode with full tracebacks and verbose logging",
        ),
    ] = False,
) -> None:
    """
    List available tool adapters.

    Shows all registered adapters (HTTP, CLI, MCP) that can be used
    to execute tools.

    Examples:
        cub tools list
        cub tools list --debug
    """
    setup_logging(debug)

    try:
        adapters = list_adapters()

        if not adapters:
            console.print()
            console.print(
                Panel(
                    Text("No adapters registered.", style="yellow"),
                    border_style="yellow",
                    expand=False,
                )
            )
            console.print()
            return

        # Create table
        table = Table(title="Registered Tool Adapters", border_style="cyan")
        table.add_column("Adapter Type", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")

        # Map adapter types to descriptions
        descriptions = {
            "http": "Execute HTTP/REST API tools",
            "cli": "Execute command-line interface tools",
            "mcp_stdio": "Execute Model Context Protocol servers via stdio",
        }

        for adapter_type in sorted(adapters):
            description = descriptions.get(adapter_type, "No description available")
            table.add_row(adapter_type, description)

        console.print()
        console.print(table)
        console.print()

        # Summary
        summary = Text()
        summary.append("Total adapters: ", style="dim")
        summary.append(str(len(adapters)), style="bold green")
        console.print(summary)

    except Exception as e:
        handle_error(e, "list")
        raise typer.Exit(1)


@app.command()
def check(
    tool_id: Annotated[str, typer.Argument(..., help="Tool ID to check")],
    adapter: Annotated[
        str,
        typer.Option(
            "--adapter",
            "-a",
            help="Adapter type (http, cli, mcp_stdio)",
        ),
    ] = "http",
    auth_env: Annotated[
        str | None,
        typer.Option(
            "--auth-env",
            help="Environment variable containing auth credentials",
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
    Check if a tool is ready to execute.

    Verifies that the tool can be executed with the specified adapter,
    checking for required dependencies, credentials, and adapter health.

    Examples:
        cub tools check brave-search --adapter http --auth-env BRAVE_API_KEY
        cub tools check gh --adapter cli
        cub tools check my-tool --adapter mcp_stdio --debug
    """
    setup_logging(debug)

    try:
        service = ExecutionService()

        # Build config
        config: dict[str, Any] = {}
        if auth_env:
            config["auth_env_var"] = auth_env

        # Check readiness
        async def _check() -> None:
            readiness = await service.check_readiness(
                tool_id=tool_id,
                adapter_type=adapter,
                config=config if config else None,
            )

            console.print()

            if readiness.ready:
                # Success panel
                success_text = Text()
                success_text.append("Tool ", style="dim")
                success_text.append(tool_id, style="bold cyan")
                success_text.append(" is ready to execute", style="dim")

                console.print(
                    Panel(
                        success_text,
                        title="[bold green]✓ Ready[/bold green]",
                        border_style="green",
                        expand=False,
                    )
                )
            else:
                # Missing dependencies panel
                error_text = Text()
                error_text.append("Tool ", style="dim")
                error_text.append(tool_id, style="bold cyan")
                error_text.append(" is not ready\n\n", style="dim")
                error_text.append("Missing dependencies:\n", style="bold red")
                for dep in readiness.missing:
                    error_text.append(f"  • {dep}\n", style="yellow")

                console.print(
                    Panel(
                        error_text,
                        title="[bold red]✗ Not Ready[/bold red]",
                        border_style="red",
                        expand=False,
                    )
                )

            console.print()

        asyncio.run(_check())

    except Exception as e:
        handle_error(e, "check")
        raise typer.Exit(1)


@app.command()
def run(
    tool_id: Annotated[str, typer.Argument(..., help="Tool ID to run")],
    action: Annotated[str, typer.Argument(..., help="Action to invoke")],
    adapter: Annotated[
        str,
        typer.Option(
            "--adapter",
            "-a",
            help="Adapter type (http, cli, mcp_stdio)",
        ),
    ] = "http",
    params: Annotated[
        str | None,
        typer.Option(
            "--params",
            "-p",
            help="JSON-encoded parameters for the action",
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            "-t",
            help="Execution timeout in seconds",
        ),
    ] = 30.0,
    no_save: Annotated[
        bool,
        typer.Option(
            "--no-save",
            help="Don't save execution artifact to disk",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug mode with full tracebacks and verbose logging",
        ),
    ] = False,
) -> None:
    """
    Execute a tool with the specified adapter.

    Runs a tool action and displays the results. Artifacts are saved to
    .cub/toolsmith/runs/ unless --no-save is specified.

    Examples:
        cub tools run brave-search search --params '{"query": "python"}'
        cub tools run gh pr --adapter cli --params '{"action": "list"}'
        cub tools run my-tool action --adapter mcp_stdio --timeout 60
    """
    setup_logging(debug)

    try:
        service = ExecutionService()

        # Parse params
        params_dict: dict[str, Any] = {}
        if params:
            try:
                params_dict = json.loads(params)
            except json.JSONDecodeError as e:
                console.print()
                console.print(
                    Panel(
                        Text(f"Invalid JSON in --params: {e}", style="red"),
                        title="[bold red]Error[/bold red]",
                        border_style="red",
                        expand=False,
                    )
                )
                console.print()
                raise typer.Exit(1)

        # Execute tool
        async def _run() -> None:
            result = await service.execute(
                tool_id=tool_id,
                action=action,
                adapter_type=adapter,
                params=params_dict,
                timeout=timeout,
                save_artifact=not no_save,
            )

            console.print()

            if result.success:
                # Success panel
                success_text = Text()
                success_text.append("Tool ", style="dim")
                success_text.append(result.tool_id, style="bold cyan")
                success_text.append(" executed successfully\n\n", style="dim")

                # Add output summary if available
                if result.output_markdown:
                    success_text.append("Summary:\n", style="bold green")
                    success_text.append(f"{result.output_markdown}\n\n", style="white")

                # Add execution info
                success_text.append("Duration: ", style="dim")
                success_text.append(f"{result.duration_ms}ms\n", style="cyan")

                if result.artifact_path:
                    success_text.append("Artifact: ", style="dim")
                    success_text.append(f"{result.artifact_path}\n", style="blue")

                console.print(
                    Panel(
                        success_text,
                        title="[bold green]✓ Success[/bold green]",
                        border_style="green",
                        expand=False,
                    )
                )

                # Print full output if available and not markdown
                if result.output and not result.output_markdown:
                    console.print()
                    console.print("[dim]Full Output:[/dim]")
                    console.print(json.dumps(result.output, indent=2))

            else:
                # Error panel
                error_text = Text()
                error_text.append("Tool ", style="dim")
                error_text.append(result.tool_id, style="bold cyan")
                error_text.append(" failed\n\n", style="dim")

                error_text.append("Error: ", style="bold red")
                error_text.append(f"{result.error}\n", style="yellow")

                if result.error_type:
                    error_text.append("Type: ", style="dim")
                    error_text.append(f"{result.error_type}\n", style="magenta")

                error_text.append("Duration: ", style="dim")
                error_text.append(f"{result.duration_ms}ms\n", style="cyan")

                if result.artifact_path:
                    error_text.append("Artifact: ", style="dim")
                    error_text.append(f"{result.artifact_path}\n", style="blue")

                console.print(
                    Panel(
                        error_text,
                        title="[bold red]✗ Failed[/bold red]",
                        border_style="red",
                        expand=False,
                    )
                )

            console.print()

        asyncio.run(_run())

    except Exception as e:
        handle_error(e, "run")
        raise typer.Exit(1)


@app.command()
def artifacts(
    tool_id: Annotated[
        str | None,
        typer.Option(
            "--tool-id",
            "-i",
            help="Filter by tool ID",
        ),
    ] = None,
    action: Annotated[
        str | None,
        typer.Option(
            "--action",
            "-a",
            help="Filter by action",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Limit number of results",
        ),
    ] = 10,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Enable debug mode with full tracebacks and verbose logging",
        ),
    ] = False,
) -> None:
    """
    List execution artifacts.

    Shows recent tool execution artifacts stored in .cub/toolsmith/runs/.
    Results are sorted by modification time (most recent first).

    Examples:
        cub tools artifacts
        cub tools artifacts --tool-id brave-search
        cub tools artifacts --action search --limit 20
    """
    setup_logging(debug)

    try:
        service = ExecutionService()

        # List artifacts
        artifact_paths = service.list_artifacts(
            tool_id=tool_id,
            action=action,
        )

        if not artifact_paths:
            console.print()
            no_results = Text("No artifacts found", style="yellow")
            if tool_id or action:
                no_results.append("\n\n", style="dim")
                no_results.append("Filters:\n", style="dim")
                if tool_id:
                    no_results.append(f"  Tool ID: {tool_id}\n", style="cyan")
                if action:
                    no_results.append(f"  Action: {action}\n", style="cyan")

            console.print(
                Panel(
                    no_results,
                    border_style="yellow",
                    expand=False,
                )
            )
            console.print()
            return

        # Apply limit
        limited_paths = artifact_paths[:limit]

        # Create table
        title = "Execution Artifacts"
        if tool_id or action:
            filters = []
            if tool_id:
                filters.append(f"tool_id={tool_id}")
            if action:
                filters.append(f"action={action}")
            title += f" ({', '.join(filters)})"

        table = Table(title=title, border_style="cyan")
        table.add_column("Timestamp", style="dim", no_wrap=True, width=20)
        table.add_column("Tool ID", style="cyan", no_wrap=True, width=20)
        table.add_column("Action", style="magenta", width=15)
        table.add_column("Success", style="green", width=10)
        table.add_column("Path", style="blue")

        for artifact_path in limited_paths:
            # Read artifact to get details
            result = service.read_artifact(artifact_path)
            if result:
                timestamp = result.started_at.strftime("%Y-%m-%d %H:%M:%S")
                success_icon = "✓" if result.success else "✗"
                success_style = "green" if result.success else "red"

                table.add_row(
                    timestamp,
                    result.tool_id,
                    result.action,
                    Text(success_icon, style=success_style),
                    str(artifact_path.relative_to(Path.cwd()))
                    if artifact_path.is_relative_to(Path.cwd())
                    else str(artifact_path),
                )

        console.print()
        console.print(table)
        console.print()

        # Summary
        summary = Text()
        summary.append("Showing ", style="dim")
        summary.append(str(len(limited_paths)), style="bold green")
        summary.append(" of ", style="dim")
        summary.append(str(len(artifact_paths)), style="bold cyan")
        summary.append(" total artifacts", style="dim")

        if len(artifact_paths) > limit:
            summary.append("\n", style="dim")
            summary.append(
                f"Use --limit to see more (currently limited to {limit})",
                style="yellow",
            )

        console.print(summary)
        console.print()

    except Exception as e:
        handle_error(e, "artifacts")
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
    View tool effectiveness metrics.

    Shows execution statistics for all tools, including invocation counts,
    success rates, timing information, and error tracking. Metrics are
    color-coded based on success rate for quick assessment.

    Success rate color coding:
        Green: >80% - Highly reliable
        Yellow: 50-80% - Moderately reliable
        Red: <50% - Low reliability

    Examples:
        cub tools stats
        cub tools stats --debug
    """
    setup_logging(debug)

    try:
        store = MetricsStore.project()
        all_metrics = store.list_all()

        if not all_metrics:
            console.print()
            console.print(
                Panel(
                    Text("No metrics yet", style="yellow"),
                    title="[bold yellow]No Data[/bold yellow]",
                    border_style="yellow",
                    expand=False,
                )
            )
            console.print()
            console.print(
                "[dim]Metrics will appear here after executing tools with 'cub tools run'[/dim]"
            )
            console.print()
            return

        # Sort by invocations (most used first)
        all_metrics.sort(key=lambda m: m.invocations, reverse=True)

        # Create table
        table = Table(title="Tool Effectiveness Metrics", border_style="cyan")
        table.add_column("Tool ID", style="cyan", no_wrap=True)
        table.add_column("Invocations", style="white", justify="right")
        table.add_column("Success Rate", style="white", justify="right")
        table.add_column("Avg Duration", style="white", justify="right")
        table.add_column("Errors", style="white", justify="right")
        table.add_column("Last Used", style="dim")

        for metrics in all_metrics:
            # Calculate success rate
            success_rate = metrics.success_rate()

            # Color-code success rate
            if success_rate > 80.0:
                success_style = "bold green"
            elif success_rate >= 50.0:
                success_style = "bold yellow"
            else:
                success_style = "bold red"

            # Format success rate with color
            success_text = Text(f"{success_rate:.1f}%", style=success_style)

            # Format average duration
            avg_duration = (
                f"{metrics.avg_duration_ms:.0f}ms"
                if metrics.avg_duration_ms
                else "N/A"
            )

            # Count total errors
            total_errors = sum(metrics.error_types.values())
            errors_text = str(total_errors) if total_errors > 0 else "-"

            # Format last used timestamp
            if metrics.last_used_at:
                # Show relative time or date depending on recency
                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                time_diff = now - metrics.last_used_at
                total_seconds = time_diff.total_seconds()

                if total_seconds < 60:
                    last_used = "just now"
                elif total_seconds < 3600:
                    minutes = int(total_seconds // 60)
                    last_used = f"{minutes}m ago"
                elif total_seconds < 86400:
                    hours = int(total_seconds // 3600)
                    last_used = f"{hours}h ago"
                elif time_diff.days == 1:
                    last_used = "yesterday"
                elif time_diff.days < 7:
                    last_used = f"{time_diff.days}d ago"
                else:
                    last_used = metrics.last_used_at.strftime("%Y-%m-%d")
            else:
                last_used = "N/A"

            table.add_row(
                metrics.tool_id,
                str(metrics.invocations),
                success_text,
                avg_duration,
                errors_text,
                last_used,
            )

        console.print()
        console.print(table)
        console.print()

        # Summary statistics
        summary = Text()
        summary.append("Total tools: ", style="dim")
        summary.append(str(len(all_metrics)), style="bold cyan")
        summary.append("  •  Total invocations: ", style="dim")
        total_invocations = sum(m.invocations for m in all_metrics)
        summary.append(str(total_invocations), style="bold green")

        # Calculate overall success rate
        total_successes = sum(m.successes for m in all_metrics)
        overall_success_rate = (
            (total_successes / total_invocations) * 100 if total_invocations > 0 else 0.0
        )
        summary.append("  •  Overall success rate: ", style="dim")

        # Color-code overall rate
        if overall_success_rate > 80.0:
            rate_style = "bold green"
        elif overall_success_rate >= 50.0:
            rate_style = "bold yellow"
        else:
            rate_style = "bold red"

        summary.append(f"{overall_success_rate:.1f}%", style=rate_style)

        console.print(summary)
        console.print()

    except Exception as e:
        handle_error(e, "stats")
        raise typer.Exit(1)


__all__ = ["app"]
