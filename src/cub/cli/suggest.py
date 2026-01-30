"""
Cub CLI - Suggest command.

Show smart suggestions for what to do next based on project state.
"""

import json as json_module

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cub.core.services.suggestions import SuggestionService
from cub.core.suggestions.models import SuggestionCategory
from cub.utils.project import get_project_root

app = typer.Typer(
    name="suggest",
    help="Get smart suggestions for next actions",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def suggest(
    ctx: typer.Context,
    limit: int = typer.Option(
        5,
        "--limit",
        "-n",
        help="Maximum number of suggestions to show",
    ),
    category: str | None = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category (task, review, milestone, git, cleanup, plan)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output suggestions as JSON",
    ),
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output in agent-friendly markdown format",
    ),
    show_action: bool = typer.Option(
        True,
        "--show-action/--no-action",
        help="Show executable action commands",
    ),
) -> None:
    """
    Get smart suggestions for what to do next.

    Analyzes your project state (tasks, git, ledger, milestones) and provides
    intelligent recommendations with rationale.

    Examples:
        cub suggest                     # Show top 5 suggestions
        cub suggest -n 10               # Show top 10 suggestions
        cub suggest -c task             # Only show task suggestions
        cub suggest --json              # JSON output for automation
        cub suggest --agent             # Agent-friendly markdown output
        cub suggest --no-action         # Hide action commands
    """
    debug = ctx.obj.get("debug", False)

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Limit: {limit}[/dim]")
        console.print(f"[dim]Category filter: {category or 'all'}[/dim]")
        console.print(f"[dim]JSON output: {json_output}[/dim]")

    try:
        # Get project root
        project_dir = get_project_root()

        # Create suggestion service
        service = SuggestionService.from_project_dir(project_dir)

        # Get suggestions
        suggestions = service.get_suggestions(limit=None)  # Get all, filter later

        # Filter by category if specified
        if category:
            try:
                category_enum = SuggestionCategory(category.lower())
                suggestions = [s for s in suggestions if s.category == category_enum]
            except ValueError:
                valid_categories = ", ".join([c.value for c in SuggestionCategory])
                console.print(
                    f"[red]Error: Invalid category '{category}'. "
                    f"Valid categories: {valid_categories}[/red]"
                )
                raise typer.Exit(1)

        # Apply limit after filtering
        suggestions = suggestions[:limit]

        if not suggestions:
            # --agent wins over --json
            if agent:
                console.print("# cub suggest\n")
                console.print("0 recommendations based on current project state.")
            elif category:
                console.print(
                    f"[yellow]No suggestions found for category '{category}'[/yellow]"
                )
            else:
                console.print(
                    "[yellow]No suggestions available. Your project is in great shape![/yellow]"
                )
            raise typer.Exit(0)

        # --agent wins over --json
        if agent:
            try:
                from cub.core.services.agent_format import AgentFormatter

                output = AgentFormatter.format_suggestions(suggestions)
                console.print(output)
            except ImportError:
                # Fallback to simple markdown if AgentFormatter not available
                count = len(suggestions)
                console.print("# cub suggest\n")
                plural = 's' if count != 1 else ''
                console.print(
                    f"{count} recommendation{plural} based on current project state.\n"
                )
                console.print("## Suggestions\n")
                console.print("| Priority | Category | Title | Rationale |")
                console.print("|----------|----------|-------|-----------|")
                for i, sug in enumerate(suggestions, 1):
                    rationale = sug.rationale
                    if len(rationale) > 80:
                        rationale = rationale[:77] + "..."
                    console.print(f"| {i} | {sug.category.value} | {sug.title} | {rationale} |")
            raise typer.Exit(0)

        if json_output:
            # Output machine-readable JSON
            json_output_dict = {
                "total_suggestions": len(suggestions),
                "suggestions": [
                    {
                        "category": s.category.value,
                        "title": s.title,
                        "description": s.description,
                        "rationale": s.rationale,
                        "priority_score": s.priority_score,
                        "urgency_level": s.urgency_level,
                        "action": s.action,
                        "source": s.source,
                        "context": s.context,
                        "created_at": s.created_at.isoformat(),
                    }
                    for s in suggestions
                ],
            }
            console.print(json_module.dumps(json_output_dict, indent=2))
            raise typer.Exit(0)

        # Display human-readable suggestions
        console.print()
        console.print(
            Panel(
                f"[bold cyan]Smart Suggestions[/bold cyan]\n"
                f"Found {len(suggestions)} recommendation{'s' if len(suggestions) != 1 else ''}",
                border_style="cyan",
            )
        )
        console.print()

        # Create suggestions table
        table = Table(show_header=True, show_lines=True, expand=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Suggestion", style="bold")
        table.add_column("Priority", justify="center", width=10)

        for idx, suggestion in enumerate(suggestions, start=1):
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
            content_lines = [
                f"{suggestion.formatted_title}",
                "",
                f"[dim]{suggestion.rationale}[/dim]",
            ]

            if suggestion.description:
                content_lines.extend(["", f"[dim italic]{suggestion.description}[/dim italic]"])

            if show_action and suggestion.action:
                content_lines.extend(
                    ["", f"[green]→ {suggestion.action}[/green]"]
                )

            content = "\n".join(content_lines)

            table.add_row(str(idx), content, priority_str)

        console.print(table)

        # Show next action tip
        if suggestions:
            next_action = suggestions[0]
            if next_action.action:
                console.print()
                console.print(
                    Panel(
                        f"[bold]Recommended next action:[/bold]\n\n"
                        f"[green]{next_action.action}[/green]",
                        border_style="green",
                        title="Quick Start",
                    )
                )

        raise typer.Exit(0)

    except typer.Exit:
        # Re-raise exit signals without modification
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)


__all__ = ["app"]
