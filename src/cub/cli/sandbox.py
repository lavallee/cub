"""
Cub CLI - Sandbox commands.

Manage Docker sandboxes for isolated task execution.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from cub.core.sandbox.provider import get_provider
from cub.core.sandbox.state import clear_sandbox_state, load_sandbox_state

app = typer.Typer(
    name="sandbox",
    help="Manage Docker sandboxes",
    no_args_is_help=True,
)

console = Console()


def _get_sandbox_id(
    project_dir: Path,
    sandbox_id: str | None,
) -> tuple[str, str]:
    """
    Get sandbox ID and provider from args or state file.

    Args:
        project_dir: Project directory
        sandbox_id: Explicit sandbox ID (optional)

    Returns:
        Tuple of (sandbox_id, provider_name)

    Raises:
        typer.Exit: If no sandbox found
    """
    if sandbox_id:
        # Explicit ID provided - assume docker for now
        return sandbox_id, "docker"

    # Load from state file
    state = load_sandbox_state(project_dir)
    if state is None:
        console.print(
            "[red]No active sandbox found[/red]\n"
            "Start a sandbox with:\n"
            "  cub run --sandbox --sandbox-keep"
        )
        raise typer.Exit(1)

    return state.sandbox_id, state.provider


@app.command()
def logs(
    ctx: typer.Context,
    sandbox_id: str | None = typer.Argument(
        None,
        help="Sandbox ID (auto-detects from state if not specified)",
    ),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Stream logs in real-time",
    ),
) -> None:
    """
    Show logs from sandbox container.

    Examples:
        cub sandbox logs                 # Show logs from active sandbox
        cub sandbox logs cub-sandbox-123 # Show logs from specific sandbox
        cub sandbox logs -f              # Follow logs in real-time
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Get sandbox ID
    sandbox_id_resolved, provider_name = _get_sandbox_id(project_dir, sandbox_id)

    if debug:
        console.print(f"[dim]Sandbox ID: {sandbox_id_resolved}[/dim]")
        console.print(f"[dim]Provider: {provider_name}[/dim]")

    # Get provider
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        console.print(f"[red]Failed to get provider: {e}[/red]")
        raise typer.Exit(1)

    # Stream or fetch logs
    try:
        if follow:
            console.print(f"[bold]Streaming logs from {sandbox_id_resolved}[/bold]")
            console.print("[dim]Press Ctrl+C to stop[/dim]\n")

            def log_callback(line: str) -> None:
                """Print log line."""
                print(line, end="")

            try:
                provider.logs(sandbox_id_resolved, follow=True, callback=log_callback)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped streaming logs[/yellow]")
                raise typer.Exit(0)
        else:
            logs_output = provider.logs(sandbox_id_resolved, follow=False)
            console.print(logs_output)

    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to get logs: {e}[/red]")
        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command()
def status(
    ctx: typer.Context,
    sandbox_id: str | None = typer.Argument(
        None,
        help="Sandbox ID (auto-detects from state if not specified)",
    ),
) -> None:
    """
    Show sandbox status and resource usage.

    Examples:
        cub sandbox status                 # Show status of active sandbox
        cub sandbox status cub-sandbox-123 # Show status of specific sandbox
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Get sandbox ID
    sandbox_id_resolved, provider_name = _get_sandbox_id(project_dir, sandbox_id)

    if debug:
        console.print(f"[dim]Sandbox ID: {sandbox_id_resolved}[/dim]")
        console.print(f"[dim]Provider: {provider_name}[/dim]")

    # Get provider
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        console.print(f"[red]Failed to get provider: {e}[/red]")
        raise typer.Exit(1)

    # Get status
    try:
        sandbox_status = provider.status(sandbox_id_resolved)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to get status: {e}[/red]")
        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # Display status in a table
    table = Table(title=f"Sandbox Status: {sandbox_id_resolved}", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Provider", sandbox_status.provider)
    table.add_row("State", _format_state(sandbox_status.state.value))

    if sandbox_status.started_at:
        table.add_row("Started", sandbox_status.started_at.strftime("%Y-%m-%d %H:%M:%S"))

    if sandbox_status.stopped_at:
        table.add_row("Stopped", sandbox_status.stopped_at.strftime("%Y-%m-%d %H:%M:%S"))

    if sandbox_status.exit_code is not None:
        exit_style = "green" if sandbox_status.exit_code == 0 else "red"
        table.add_row("Exit Code", f"[{exit_style}]{sandbox_status.exit_code}[/{exit_style}]")

    if sandbox_status.error:
        table.add_row("Error", f"[red]{sandbox_status.error}[/red]")

    # Resource usage
    if sandbox_status.resources:
        res = sandbox_status.resources
        if res.memory_used and res.memory_limit:
            table.add_row("Memory", f"{res.memory_used} / {res.memory_limit}")
        if res.cpu_percent is not None:
            table.add_row("CPU", f"{res.cpu_percent:.1f}%")

    console.print(table)


def _format_state(state: str) -> str:
    """Format state with color."""
    colors = {
        "running": "green",
        "stopped": "yellow",
        "failed": "red",
        "starting": "cyan",
        "cleaning_up": "magenta",
    }
    color = colors.get(state, "white")
    return f"[{color}]{state}[/{color}]"


@app.command()
def diff(
    ctx: typer.Context,
    sandbox_id: str | None = typer.Argument(
        None,
        help="Sandbox ID (auto-detects from state if not specified)",
    ),
) -> None:
    """
    Show changes made in sandbox.

    Displays a git-style unified diff of all file changes.

    Examples:
        cub sandbox diff                 # Show diff from active sandbox
        cub sandbox diff cub-sandbox-123 # Show diff from specific sandbox
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Get sandbox ID
    sandbox_id_resolved, provider_name = _get_sandbox_id(project_dir, sandbox_id)

    if debug:
        console.print(f"[dim]Sandbox ID: {sandbox_id_resolved}[/dim]")
        console.print(f"[dim]Provider: {provider_name}[/dim]")

    # Get provider
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        console.print(f"[red]Failed to get provider: {e}[/red]")
        raise typer.Exit(1)

    # Get diff
    try:
        diff_output = provider.diff(sandbox_id_resolved)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to get diff: {e}[/red]")
        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    if not diff_output:
        console.print("[yellow]No changes detected[/yellow]")
        raise typer.Exit(0)

    # Display diff with syntax highlighting
    syntax = Syntax(diff_output, "diff", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="Sandbox Changes", border_style="cyan"))


@app.command()
def export(
    ctx: typer.Context,
    dest: Path = typer.Argument(
        ...,
        help="Destination directory for exported files",
    ),
    sandbox_id: str | None = typer.Option(
        None,
        "--sandbox",
        "-s",
        help="Sandbox ID (auto-detects from state if not specified)",
    ),
    all_files: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Export all files (not just changed files)",
    ),
) -> None:
    """
    Export files from sandbox to local directory.

    By default, only exports changed files. Use --all to export everything.

    Examples:
        cub sandbox export /tmp/sandbox-export
        cub sandbox export ./output --all
        cub sandbox export /tmp/out --sandbox cub-sandbox-123
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Get sandbox ID
    sandbox_id_resolved, provider_name = _get_sandbox_id(project_dir, sandbox_id)

    if debug:
        console.print(f"[dim]Sandbox ID: {sandbox_id_resolved}[/dim]")
        console.print(f"[dim]Provider: {provider_name}[/dim]")
        console.print(f"[dim]Destination: {dest}[/dim]")
        console.print(f"[dim]Changed only: {not all_files}[/dim]")

    # Get provider
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        console.print(f"[red]Failed to get provider: {e}[/red]")
        raise typer.Exit(1)

    # Export files
    console.print(f"[cyan]Exporting files to {dest}...[/cyan]")
    try:
        provider.export(sandbox_id_resolved, dest, changed_only=not all_files)
        console.print(f"[green]Files exported successfully to {dest}[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to export files: {e}[/red]")
        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command()
def apply(
    ctx: typer.Context,
    sandbox_id: str | None = typer.Argument(
        None,
        help="Sandbox ID (auto-detects from state if not specified)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Apply sandbox changes to the project.

    Copies changed files from the sandbox back to the project directory.
    This will overwrite local files!

    Examples:
        cub sandbox apply           # Apply changes with confirmation
        cub sandbox apply -y        # Apply changes without confirmation
        cub sandbox apply cub-sandbox-123 -y
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Get sandbox ID
    sandbox_id_resolved, provider_name = _get_sandbox_id(project_dir, sandbox_id)

    if debug:
        console.print(f"[dim]Sandbox ID: {sandbox_id_resolved}[/dim]")
        console.print(f"[dim]Provider: {provider_name}[/dim]")
        console.print(f"[dim]Project dir: {project_dir}[/dim]")

    # Get provider
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        console.print(f"[red]Failed to get provider: {e}[/red]")
        raise typer.Exit(1)

    # Show diff first
    try:
        diff_output = provider.diff(sandbox_id_resolved)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to get diff: {e}[/red]")
        raise typer.Exit(1)

    if not diff_output:
        console.print("[yellow]No changes to apply[/yellow]")
        raise typer.Exit(0)

    # Display diff
    console.print("[bold]Changes to apply:[/bold]\n")
    syntax = Syntax(diff_output, "diff", theme="monokai", line_numbers=False)
    console.print(syntax)
    console.print()

    # Confirmation prompt
    if not yes:
        confirm = typer.confirm(
            "Apply these changes to the project? This will overwrite local files."
        )
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    # Apply changes
    console.print("[cyan]Applying changes...[/cyan]")
    try:
        provider.export(sandbox_id_resolved, project_dir, changed_only=True)
        console.print("[green]Changes applied successfully[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to apply changes: {e}[/red]")
        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command()
def clean(
    ctx: typer.Context,
    sandbox_id: str | None = typer.Argument(
        None,
        help="Sandbox ID (auto-detects from state if not specified)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """
    Remove sandbox and clean up resources.

    Stops the sandbox (if running) and removes all associated resources
    (containers, volumes, etc.).

    Examples:
        cub sandbox clean           # Clean active sandbox with confirmation
        cub sandbox clean -y        # Clean without confirmation
        cub sandbox clean cub-sandbox-123 -y
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Get sandbox ID
    sandbox_id_resolved, provider_name = _get_sandbox_id(project_dir, sandbox_id)

    if debug:
        console.print(f"[dim]Sandbox ID: {sandbox_id_resolved}[/dim]")
        console.print(f"[dim]Provider: {provider_name}[/dim]")

    # Confirmation prompt
    if not yes:
        confirm = typer.confirm(
            f"Remove sandbox {sandbox_id_resolved} and all its data? This cannot be undone."
        )
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    # Get provider
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        console.print(f"[red]Failed to get provider: {e}[/red]")
        raise typer.Exit(1)

    # Cleanup
    console.print(f"[cyan]Removing sandbox {sandbox_id_resolved}...[/cyan]")
    try:
        provider.cleanup(sandbox_id_resolved)
        console.print("[green]Sandbox removed successfully[/green]")

        # Clear state file if this was the active sandbox
        state = load_sandbox_state(project_dir)
        if state and state.sandbox_id == sandbox_id_resolved:
            clear_sandbox_state(project_dir)
            if debug:
                console.print("[dim]Cleared sandbox state[/dim]")

    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Failed to clean sandbox: {e}[/red]")
        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


__all__ = ["app"]
