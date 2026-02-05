"""
Cub CLI - Release command.

Mark a plan as released, update CHANGELOG, create git tag, and move specs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from cub.core.release import ReleaseService, ReleaseServiceError

app = typer.Typer(
    name="release",
    help="Mark a plan as released",
    no_args_is_help=True,
)

console = Console()


@app.callback(invoke_without_command=True)
def release_command(
    ctx: typer.Context,
    plan_id: Annotated[
        str,
        typer.Argument(
            help="Plan ID to release (e.g., cub-048a)",
        ),
    ],
    version: Annotated[
        str,
        typer.Argument(
            help="Version tag (e.g., v0.30)",
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be done without making changes",
        ),
    ] = False,
    no_tag: Annotated[
        bool,
        typer.Option(
            "--no-tag",
            help="Skip git tag creation",
        ),
    ] = False,
) -> None:
    """
    Mark a plan as released.

    This command:
    1. Updates the plan status to "released" in the ledger
    2. Updates CHANGELOG.md with release notes
    3. Creates a git tag (unless --no-tag)
    4. Moves the spec file to specs/released/

    Examples:

        # Release a plan
        cub release cub-048a v0.30

        # Preview changes without applying them
        cub release cub-048a v0.30 --dry-run

        # Release without creating a git tag
        cub release cub-048a v0.30 --no-tag
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    project_dir = Path.cwd()

    try:
        service = ReleaseService(project_dir)

        console.print(f"[cyan]Releasing plan {plan_id} as {version}...[/cyan]")
        if dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
        console.print()

        result = service.release_plan(
            plan_id=plan_id,
            version=version,
            dry_run=dry_run,
            no_tag=no_tag,
        )

        # Display results
        console.print("[bold]Release Summary:[/bold]")
        console.print(f"  Plan ID: {result.plan_id}")
        console.print(f"  Version: {result.version}")
        console.print()

        if result.spec_file:
            if result.spec_moved:
                status = "[green]✓[/green]" if not dry_run else "[dim]○[/dim]"
                action = "Moved" if not dry_run else "Would move"
                console.print(f"  {status} {action} spec: {result.spec_file.name}")
            else:
                console.print(f"  [yellow]⚠[/yellow] Failed to move spec: {result.spec_file.name}")
        else:
            console.print("  [dim]○ No spec file found[/dim]")

        if result.changelog_updated:
            status = "[green]✓[/green]" if not dry_run else "[dim]○[/dim]"
            action = "Updated" if not dry_run else "Would update"
            console.print(f"  {status} {action} CHANGELOG.md")
        else:
            console.print("  [yellow]⚠[/yellow] Failed to update CHANGELOG.md")

        if no_tag:
            console.print("  [dim]○ Skipped git tag (--no-tag)[/dim]")
        elif result.tag_created:
            status = "[green]✓[/green]" if not dry_run else "[dim]○[/dim]"
            action = "Created" if not dry_run else "Would create"
            console.print(f"  {status} {action} git tag: {result.version}")
        else:
            console.print("  [yellow]⚠[/yellow] Failed to create git tag")

        if result.ledger_updated:
            status = "[green]✓[/green]" if not dry_run else "[dim]○[/dim]"
            action = "Updated" if not dry_run else "Would update"
            console.print(f"  {status} {action} ledger status to 'released'")
        else:
            console.print("  [yellow]⚠[/yellow] Failed to update ledger")

        console.print()

        if dry_run:
            console.print("[dim]Dry run complete - no changes made[/dim]")
        else:
            console.print(f"[green]✓ Released {plan_id} as {version}[/green]")

    except ReleaseServiceError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)
