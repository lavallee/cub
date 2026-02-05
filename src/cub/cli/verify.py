"""
Cub CLI - Verify command.

Check ledger consistency, ID integrity, and counter sync status.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from cub.core.verify import IssueSeverity, VerifyService

app = typer.Typer(
    name="verify",
    help="Verify cub data integrity",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def verify_command(
    ctx: typer.Context,
    fix: Annotated[
        bool,
        typer.Option(
            "--fix",
            help="Attempt to auto-fix simple issues",
        ),
    ] = False,
    ledger: Annotated[
        bool,
        typer.Option(
            "--ledger/--no-ledger",
            help="Check ledger consistency (default: enabled)",
        ),
    ] = True,
    ids: Annotated[
        bool,
        typer.Option(
            "--ids/--no-ids",
            help="Check ID integrity (default: enabled)",
        ),
    ] = True,
    counters: Annotated[
        bool,
        typer.Option(
            "--counters/--no-counters",
            help="Check counter sync status (default: enabled)",
        ),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed information including info-level issues",
        ),
    ] = False,
) -> None:
    """
    Verify cub data integrity.

    This command checks:
    - Ledger consistency (file structure, JSON validity, entry integrity)
    - ID integrity (format validation, duplicate detection, cross-references)
    - Counter sync status (counters match actual usage)

    Examples:

        # Run all checks
        cub verify

        # Run checks and auto-fix simple issues
        cub verify --fix

        # Check only ledger consistency
        cub verify --no-ids --no-counters

        # Check only counters
        cub verify --no-ledger --no-ids

        # Show all issues including informational ones
        cub verify --verbose
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    project_dir = Path.cwd()

    try:
        service = VerifyService(project_dir)

        console.print("[cyan]Verifying cub data integrity...[/cyan]")
        if fix:
            console.print("[yellow]Auto-fix mode enabled[/yellow]")
        console.print()

        # Build list of checks to run
        checks_enabled = []
        if ledger:
            checks_enabled.append("ledger")
        if ids:
            checks_enabled.append("IDs")
        if counters:
            checks_enabled.append("counters")

        if checks_enabled:
            console.print(f"[dim]Checking: {', '.join(checks_enabled)}[/dim]")
            console.print()

        result = service.verify(
            fix=fix,
            check_ledger=ledger,
            check_ids=ids,
            check_counters=counters,
        )

        # Display summary
        console.print("[bold]Verification Summary:[/bold]")
        console.print(f"  Checks run: {result.checks_run}")
        console.print(f"  Files checked: {result.files_checked}")
        console.print()

        # Display issues
        if result.issues:
            # Filter issues by severity if not verbose
            issues_to_show = result.issues
            if not verbose:
                issues_to_show = [
                    i for i in result.issues
                    if i.severity != IssueSeverity.INFO
                ]

            if issues_to_show:
                # Create table
                table = Table(title="Issues Found", show_header=True)
                table.add_column("Severity", style="bold")
                table.add_column("Category", style="cyan")
                table.add_column("Message")
                table.add_column("Location", style="dim")

                for issue in issues_to_show:
                    # Color severity based on level
                    if issue.severity == IssueSeverity.ERROR:
                        severity_str = f"[red]{issue.severity.value.upper()}[/red]"
                    elif issue.severity == IssueSeverity.WARNING:
                        severity_str = f"[yellow]{issue.severity.value.upper()}[/yellow]"
                    else:
                        severity_str = f"[blue]{issue.severity.value.upper()}[/blue]"

                    table.add_row(
                        severity_str,
                        issue.category,
                        issue.message,
                        issue.location or "",
                    )

                console.print(table)
                console.print()

                # Show fix suggestions for fixable issues
                fixable_issues = [i for i in issues_to_show if i.fix_suggestion]
                if fixable_issues and not fix:
                    console.print("[bold]Fix Suggestions:[/bold]")
                    for issue in fixable_issues:
                        auto_fix_tag = (
                            " [green](auto-fixable)[/green]" if issue.auto_fixable else ""
                        )
                        console.print(f"  • {issue.fix_suggestion}{auto_fix_tag}")
                    console.print()
                    console.print("[dim]Run with --fix to automatically fix simple issues[/dim]")
                    console.print()

        # Show auto-fix results
        if fix and result.auto_fixed > 0:
            console.print(f"[green]✓ Auto-fixed {result.auto_fixed} issue(s)[/green]")
            console.print()

        # Final status
        if result.has_errors:
            console.print(f"[red]✗ Found {result.error_count} error(s)[/red]")
            if result.has_warnings:
                console.print(f"[yellow]⚠ Found {result.warning_count} warning(s)[/yellow]")
            raise typer.Exit(1)
        elif result.has_warnings:
            console.print(f"[yellow]⚠ Found {result.warning_count} warning(s)[/yellow]")
            if verbose and result.info_count > 0:
                console.print(f"[blue]ℹ Found {result.info_count} info message(s)[/blue]")
        elif verbose and result.info_count > 0:
            console.print(f"[blue]ℹ Found {result.info_count} info message(s)[/blue]")
        else:
            console.print("[green]✓ No issues found - data integrity verified[/green]")

    except typer.Exit:
        # Re-raise typer.Exit to preserve exit code
        raise
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)
