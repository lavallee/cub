"""
Cub CLI - Learn command.

Analyze ledger entries to extract patterns and lessons, updating guardrails
and CLAUDE.md with discovered knowledge.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from cub.core.learn import LearnService, LearnServiceError, PatternCategory

app = typer.Typer(
    name="learn",
    help="Extract patterns and lessons from ledger data",
    no_args_is_help=True,
)

console = Console()


@app.command(name="extract")
def extract_command(
    since: Annotated[
        int | None,
        typer.Option(
            "--since",
            "-s",
            help="Only analyze entries from the last N days",
        ),
    ] = None,
    since_date: Annotated[
        str | None,
        typer.Option(
            "--since-date",
            help="Only analyze entries since this date (YYYY-MM-DD)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show suggestions without modifying files (default)",
        ),
    ] = True,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Apply suggestions to files (overrides --dry-run)",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed pattern information",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write markdown report to file",
        ),
    ] = None,
) -> None:
    """
    Extract patterns and lessons from ledger entries.

    Analyzes completed tasks to identify:
    - Repeated failure patterns
    - Cost and duration outliers
    - Escalation patterns
    - Recurring lessons learned

    Generates suggestions for updating guardrails.md and CLAUDE.md
    based on discovered patterns.

    Examples:

        # Analyze all entries (dry run, default)
        cub learn extract

        # Analyze last 30 days
        cub learn extract --since 30

        # Apply suggestions to files
        cub learn extract --apply

        # Write report to file
        cub learn extract --output learn-report.md

        # Analyze entries since a specific date
        cub learn extract --since-date 2026-01-01
    """
    project_dir = Path.cwd()

    try:
        service = LearnService(project_dir)

        # Parse since_date if provided
        parsed_since_date: datetime | None = None
        if since_date:
            try:
                parsed_since_date = datetime.strptime(since_date, "%Y-%m-%d")
            except ValueError:
                console.print(
                    f"[red]Error:[/red] Invalid date format '{since_date}'. Use YYYY-MM-DD."
                )
                raise typer.Exit(1)

        # Determine effective dry_run setting
        effective_dry_run = not apply

        # Show header
        console.print("[cyan]Analyzing ledger entries...[/cyan]")
        if since:
            console.print(f"[dim]Time window: last {since} days[/dim]")
        elif since_date:
            console.print(f"[dim]Since: {since_date}[/dim]")
        if effective_dry_run:
            console.print("[yellow]DRY RUN - No files will be modified[/yellow]")
        console.print()

        # Run extraction
        result = service.extract(
            since_days=since,
            since_date=parsed_since_date,
            dry_run=effective_dry_run,
        )

        # Display summary
        console.print("[bold]Analysis Summary:[/bold]")
        console.print(f"  Entries analyzed: {result.entries_analyzed}")
        console.print(f"  Time range: {result.time_range_days} days")
        console.print(f"  Patterns detected: {len(result.patterns)}")
        console.print(f"  Suggestions generated: {len(result.suggestions)}")
        console.print()

        # Display patterns
        if result.patterns:
            console.print("[bold]Detected Patterns:[/bold]")
            console.print()

            # Create table
            table = Table(show_header=True)
            table.add_column("Category", style="cyan")
            table.add_column("Description")
            table.add_column("Frequency", justify="right")
            table.add_column("Confidence", justify="right")

            for pattern in result.patterns:
                # Format category
                category_str = pattern.category.value.replace("_", " ").title()

                # Color based on category
                if pattern.category == PatternCategory.REPEATED_FAILURE:
                    category_display = f"[red]{category_str}[/red]"
                elif pattern.category == PatternCategory.COST_OUTLIER:
                    category_display = f"[yellow]{category_str}[/yellow]"
                elif pattern.category == PatternCategory.DURATION_OUTLIER:
                    category_display = f"[yellow]{category_str}[/yellow]"
                elif pattern.category == PatternCategory.ESCALATION_PATTERN:
                    category_display = f"[magenta]{category_str}[/magenta]"
                else:
                    category_display = f"[green]{category_str}[/green]"

                # Truncate long descriptions
                description = pattern.description
                if len(description) > 60:
                    description = description[:57] + "..."

                table.add_row(
                    category_display,
                    description,
                    str(pattern.frequency),
                    f"{pattern.confidence:.0%}",
                )

            console.print(table)
            console.print()

            # Show evidence in verbose mode
            if verbose:
                console.print("[bold]Pattern Details:[/bold]")
                console.print()
                for pattern in result.patterns:
                    console.print(f"  [cyan]{pattern.category.value}:[/cyan]")
                    console.print(f"    {pattern.description}")
                    if pattern.evidence:
                        evidence_str = ", ".join(pattern.evidence[:10])
                        if len(pattern.evidence) > 10:
                            evidence_str += f" (+{len(pattern.evidence) - 10} more)"
                        console.print(f"    Evidence: {evidence_str}")
                    console.print()

        else:
            console.print("[dim]No significant patterns detected.[/dim]")
            console.print()

        # Display suggestions
        if result.suggestions:
            console.print("[bold]Suggested Updates:[/bold]")
            console.print()

            for i, suggestion in enumerate(result.suggestions, 1):
                # Priority indicator
                priority_colors = {1: "red", 2: "yellow", 3: "blue"}
                priority_labels = {1: "HIGH", 2: "MED", 3: "LOW"}
                color = priority_colors.get(suggestion.priority, "white")
                label = priority_labels.get(suggestion.priority, "???")

                console.print(
                    f"  [{color}][{label}][/{color}] "
                    f"[bold]{suggestion.target.value}[/bold] "
                    f"[dim]({suggestion.section})[/dim]"
                )
                console.print(f"    {suggestion.content}")
                if verbose:
                    console.print(f"    [dim]Rationale: {suggestion.rationale}[/dim]")
                console.print()

        else:
            console.print("[dim]No suggestions at this time.[/dim]")
            console.print()

        # Show applied changes
        if result.changes_applied > 0:
            console.print(f"[green]Applied {result.changes_applied} changes:[/green]")
            for file_path in result.files_modified:
                console.print(f"  - {file_path}")
            console.print()
        elif not effective_dry_run and result.suggestions:
            console.print("[yellow]No changes applied (suggestions may already exist).[/yellow]")
            console.print()

        # Write report to file if requested
        if output:
            markdown = result.to_markdown()
            output.write_text(markdown)
            console.print(f"[green]Report written to {output}[/green]")
            console.print()

        # Final guidance
        if effective_dry_run and result.suggestions:
            console.print("[dim]Run with --apply to apply suggestions to files.[/dim]")

    except LearnServiceError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)
