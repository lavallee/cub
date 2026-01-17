"""
Cub CLI - Merge command.

Merge pull requests with CI verification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from cub.core.github.client import GitHubClientError
from cub.core.pr import PRService, PRServiceError

app = typer.Typer(
    name="merge",
    help="Merge pull requests",
    no_args_is_help=False,
    invoke_without_command=True,
)

console = Console()


@app.callback(invoke_without_command=True)
def merge_command(
    ctx: typer.Context,
    target: Annotated[
        str,
        typer.Argument(
            help="Epic ID, branch name, or PR number",
        ),
    ],
    method: Annotated[
        str,
        typer.Option(
            "--method",
            "-m",
            help="Merge method: squash, merge, or rebase",
        ),
    ] = "squash",
    no_delete: Annotated[
        bool,
        typer.Option(
            "--no-delete",
            help="Don't delete branch after merge",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Merge even if checks are failing",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be done without making changes",
        ),
    ] = False,
) -> None:
    """
    Merge a pull request.

    Verifies CI status before merging and updates the binding status
    to 'merged' after successful merge.

    Examples:

        # Merge PR for an epic
        cub merge cub-vd6

        # Merge by PR number
        cub merge 123

        # Merge by branch name
        cub merge feature/my-branch

        # Use merge commit instead of squash
        cub merge cub-vd6 --method merge

        # Keep branch after merge
        cub merge cub-vd6 --no-delete

        # Dry run
        cub merge cub-vd6 --dry-run
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    # Validate method
    valid_methods = ("squash", "merge", "rebase")
    if method not in valid_methods:
        console.print(f"[red]Invalid merge method:[/red] {method}")
        console.print(f"Valid methods: {', '.join(valid_methods)}")
        raise typer.Exit(1)

    project_dir = Path.cwd()

    try:
        service = PRService(project_dir)

        # Check CI status first (unless --force)
        if not force and not dry_run:
            resolved = service.resolve_input(target)

            # Get PR number
            pr_number: int | None = None
            if resolved.type == "pr":
                pr_number = resolved.pr_number
            elif resolved.binding and resolved.binding.pr_number:
                pr_number = resolved.binding.pr_number
            elif resolved.branch:
                base = resolved.binding.base_branch if resolved.binding else "main"
                existing = service.github_client.get_pr_by_branch(resolved.branch, base)
                if existing:
                    pr_number = int(existing.get("number") or 0)

            if pr_number:
                checks = service.github_client.get_pr_checks(pr_number)
                failed = [c for c in checks if c.get("conclusion") in ("failure", "cancelled")]
                pending = [c for c in checks if c.get("status") != "completed"]

                if failed:
                    console.print("[red]CI checks failed:[/red]")
                    for check in failed:
                        console.print(f"  - {check.get('name')}: {check.get('conclusion')}")
                    console.print()
                    console.print("Use --force to merge anyway")
                    raise typer.Exit(1)

                if pending:
                    console.print("[yellow]CI checks still running:[/yellow]")
                    for check in pending:
                        console.print(f"  - {check.get('name')}: {check.get('status')}")
                    console.print()
                    console.print("Wait for checks to complete or use --force to merge anyway")
                    raise typer.Exit(1)

        # Merge
        result = service.merge_pr(
            target=target,
            method=method,
            delete_branch=not no_delete,
            dry_run=dry_run,
        )

        if dry_run:
            console.print("[dim]Dry run - no changes made[/dim]")
            return

        console.print()
        if result.branch_deleted:
            console.print(f"PR #{result.pr_number} merged and branch deleted")
        else:
            console.print(f"PR #{result.pr_number} merged (branch kept)")

    except PRServiceError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except GitHubClientError as e:
        console.print(f"[red]GitHub error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def wait(
    target: Annotated[
        str,
        typer.Argument(
            help="Epic ID, branch name, or PR number",
        ),
    ],
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Timeout in seconds (default: 600)",
        ),
    ] = 600,
) -> None:
    """
    Wait for CI checks to complete.

    Blocks until all CI checks pass or fail.

    Examples:

        cub merge wait cub-vd6
        cub merge wait 123 --timeout 1200
    """
    project_dir = Path.cwd()

    try:
        service = PRService(project_dir)
        resolved = service.resolve_input(target)

        # Get PR number
        pr_number: int | None = None
        if resolved.type == "pr":
            pr_number = resolved.pr_number
        elif resolved.binding and resolved.binding.pr_number:
            pr_number = resolved.binding.pr_number
        elif resolved.branch:
            base = resolved.binding.base_branch if resolved.binding else "main"
            existing = service.github_client.get_pr_by_branch(resolved.branch, base)
            if existing:
                pr_number = int(existing.get("number") or 0)

        if not pr_number:
            console.print(f"[red]No PR found for {target}[/red]")
            raise typer.Exit(1)

        console.print(f"Waiting for CI checks on PR #{pr_number}...")
        console.print("[dim]Press Ctrl+C to cancel[/dim]")

        try:
            success = service.github_client.wait_for_checks(pr_number, timeout=timeout)
            if success:
                console.print("[green]All checks passed![/green]")
            else:
                console.print("[red]Some checks failed[/red]")
                raise typer.Exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled[/yellow]")
            raise typer.Exit(130)

    except PRServiceError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except GitHubClientError as e:
        console.print(f"[red]GitHub error:[/red] {e}")
        raise typer.Exit(1)
