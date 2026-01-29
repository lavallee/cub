"""
Cub CLI - Default command handler.

Implements the bare `cub` command behavior:
- In terminal: show welcome message with suggestions, then launch default harness
- In harness/nested: show inline status with suggestions (no nesting)

This module handles:
1. Environment detection (terminal vs harness vs nested)
2. Welcome message generation with project stats and smart suggestions
3. Harness launch with --resume and --continue passthrough
4. Nesting prevention via CUB_SESSION_ACTIVE environment variable
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cub.core.services.launch import HarnessNotFoundError, LaunchService, LaunchServiceError
from cub.core.services.suggestions import SuggestionService
from cub.core.suggestions.engine import WelcomeMessage

console = Console()


def render_welcome(welcome: WelcomeMessage, *, nested: bool = False) -> None:
    """Render a welcome message with project stats and suggestions.

    Args:
        welcome: Welcome message data from SuggestionService.
        nested: If True, show compact inline status instead of full welcome.
    """
    # Header with project stats
    if nested:
        _render_inline_status(welcome)
    else:
        _render_full_welcome(welcome)


def _render_inline_status(welcome: WelcomeMessage) -> None:
    """Render compact inline status for nested/harness contexts."""
    # Build status line
    parts: list[str] = []
    if welcome.total_tasks > 0:
        parts.append(f"[bold]{welcome.total_tasks}[/bold] tasks")
        if welcome.open_tasks > 0:
            parts.append(f"[cyan]{welcome.open_tasks}[/cyan] open")
        if welcome.in_progress_tasks > 0:
            parts.append(f"[yellow]{welcome.in_progress_tasks}[/yellow] in progress")
        if welcome.ready_tasks > 0:
            parts.append(f"[green]{welcome.ready_tasks}[/green] ready")

    status_line = " | ".join(parts) if parts else "No tasks found"

    console.print()
    console.print(
        Panel(
            f"[bold cyan]cub[/bold cyan] [dim]session active[/dim]\n\n{status_line}",
            border_style="cyan",
            title="[bold]Project Status[/bold]",
            title_align="left",
        )
    )

    # Show top suggestions inline
    if welcome.top_suggestions:
        console.print()
        console.print("[bold]Suggested next actions:[/bold]")
        for idx, suggestion in enumerate(welcome.top_suggestions[:3], start=1):
            action_str = ""
            if suggestion.action:
                action_str = f"  [green]> {suggestion.action}[/green]"
            console.print(f"  {idx}. {suggestion.formatted_title}{action_str}")

    console.print()


def _render_full_welcome(welcome: WelcomeMessage) -> None:
    """Render full welcome message for terminal launch."""
    # Title panel
    stats_parts: list[str] = []
    if welcome.total_tasks > 0:
        stats_parts.append(f"[bold]{welcome.total_tasks}[/bold] tasks")
        if welcome.open_tasks > 0:
            stats_parts.append(f"[cyan]{welcome.open_tasks} open[/cyan]")
        if welcome.in_progress_tasks > 0:
            stats_parts.append(f"[yellow]{welcome.in_progress_tasks} in progress[/yellow]")
        if welcome.ready_tasks > 0:
            stats_parts.append(f"[green]{welcome.ready_tasks} ready[/green]")

    stats_line = " | ".join(stats_parts) if stats_parts else "No tasks found"

    console.print()
    console.print(
        Panel(
            f"[bold cyan]Welcome to cub[/bold cyan]\n\n{stats_line}",
            border_style="cyan",
            title="[bold]Project Overview[/bold]",
            title_align="left",
        )
    )

    # Suggestions table
    if welcome.top_suggestions:
        console.print()

        table = Table(
            show_header=True,
            show_lines=True,
            expand=True,
            title="Smart Suggestions",
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Suggestion", style="bold")
        table.add_column("Priority", justify="center", width=10)

        for idx, suggestion in enumerate(welcome.top_suggestions, start=1):
            # Format priority with color
            urgency = suggestion.urgency_level
            if urgency == "urgent":
                priority_str = f"[red bold]{urgency.upper()}[/red bold]"
            elif urgency == "high":
                priority_str = f"[yellow]{urgency.capitalize()}[/yellow]"
            elif urgency == "medium":
                priority_str = f"[cyan]{urgency.capitalize()}[/cyan]"
            else:
                priority_str = f"[dim]{urgency.capitalize()}[/dim]"

            # Build suggestion content
            content_lines = [suggestion.formatted_title]
            if suggestion.rationale:
                content_lines.append(f"[dim]{suggestion.rationale}[/dim]")
            if suggestion.action:
                content_lines.append(f"[green]> {suggestion.action}[/green]")

            table.add_row(str(idx), "\n".join(content_lines), priority_str)

        console.print(table)

    console.print()


def _get_welcome_message(debug: bool = False) -> WelcomeMessage:
    """Get welcome message, handling errors gracefully.

    Args:
        debug: Whether to show debug output on error.

    Returns:
        WelcomeMessage with project stats and suggestions.
    """
    try:
        service = SuggestionService.from_project_dir()
        return service.get_welcome(max_suggestions=5)
    except Exception as e:
        if debug:
            console.print(f"[dim]Warning: Could not load suggestions: {e}[/dim]")
        # Return empty welcome message on failure
        return WelcomeMessage(
            total_tasks=0,
            open_tasks=0,
            in_progress_tasks=0,
            ready_tasks=0,
            top_suggestions=[],
            available_skills=[],
        )


def default_command(
    *,
    resume: bool = False,
    continue_session: bool = False,
    debug: bool = False,
) -> None:
    """Execute the bare `cub` default command.

    Detects the environment and either:
    - Shows inline status (if nested in an existing harness session)
    - Generates welcome + launches default harness (if in a terminal)

    Args:
        resume: Pass --resume flag to harness for session resumption.
        continue_session: Pass --continue flag to harness for session continuation.
        debug: Enable debug output.
    """
    # Step 1: Detect environment
    try:
        launch_service = LaunchService.from_config()
    except Exception as e:
        if debug:
            console.print(f"[dim]Config load error: {e}[/dim]")
        # Fall back with default config if config loading fails
        # (e.g., no cub project initialized yet)
        _handle_no_project(resume=resume, continue_session=continue_session, debug=debug)
        return

    env_info = launch_service.detect()

    if debug:
        console.print(f"[dim]Environment: {env_info.context.value}[/dim]")
        if env_info.session_id:
            console.print(f"[dim]Session ID: {env_info.session_id}[/dim]")

    # Step 2: Handle based on environment
    if env_info.in_harness:
        # Nested or harness context: show inline status, don't nest
        welcome = _get_welcome_message(debug=debug)
        render_welcome(welcome, nested=True)
        return

    # Terminal context: show welcome and launch harness
    welcome = _get_welcome_message(debug=debug)
    render_welcome(welcome, nested=False)

    # Step 3: Launch harness
    console.print("[dim]Launching harness...[/dim]")
    console.print()

    try:
        launch_service.launch(
            resume=resume,
            continue_session=continue_session,
            debug=debug,
        )
        # launch() calls os.execve() and does not return on success
    except HarnessNotFoundError as e:
        console.print(
            Panel(
                f"[red bold]Harness not found[/red bold]\n\n"
                f"Could not find '{e.harness_name}' in PATH.\n\n"
                f"[dim]Install the harness or configure a different one in .cub/config.json\n"
                f"Available harnesses: claude-code, codex, gemini[/dim]",
                border_style="red",
                title="Error",
            )
        )
        raise typer.Exit(1) from e
    except LaunchServiceError as e:
        console.print(f"[red]Error launching harness: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1) from e


def _handle_no_project(
    *,
    resume: bool = False,
    continue_session: bool = False,
    debug: bool = False,
) -> None:
    """Handle the case where no cub project is initialized.

    Still tries to launch the harness (useful for first-time users),
    but with a helpful message about initializing.
    """
    console.print()
    console.print(
        Panel(
            "[bold cyan]Welcome to cub[/bold cyan]\n\n"
            "[yellow]No cub project detected in this directory.[/yellow]\n\n"
            "[dim]Run [bold]cub init[/bold] to set up task management, "
            "hooks, and project tracking.\n"
            "Or just start working - cub will launch your default harness.[/dim]",
            border_style="yellow",
            title="[bold]Getting Started[/bold]",
            title_align="left",
        )
    )
    console.print()

    # Try to launch harness anyway — the user may just want an interactive session
    try:
        from cub.core.config.loader import load_config

        config = load_config()
        launch_service = LaunchService(config, project_dir=__import__("pathlib").Path.cwd())
        launch_service.launch(
            resume=resume,
            continue_session=continue_session,
            debug=debug,
        )
    except HarnessNotFoundError as e:
        console.print(
            Panel(
                f"[red bold]No harness found[/red bold]\n\n"
                f"Could not find '{e.harness_name}' in PATH.\n\n"
                "[dim]Install Claude Code: npm install -g @anthropic/claude-code\n"
                "Or specify a harness: cub run --harness codex[/dim]",
                border_style="red",
                title="Error",
            )
        )
        raise typer.Exit(1) from e
    except Exception:
        # If we can't launch, show help instead
        console.print(
            "[dim]Could not launch harness. "
            "Run [bold]cub --help[/bold] for available commands.[/dim]"
        )
        raise typer.Exit(1)


__all__ = ["default_command", "render_welcome"]
