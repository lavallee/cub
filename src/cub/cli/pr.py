"""
Cub CLI - PR command.

Create and manage pull requests for epics or branches.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from cub.core.github.client import GitHubClientError
from cub.core.pr import PRService, PRServiceError

app = typer.Typer(
    name="pr",
    help="Create and manage pull requests",
    no_args_is_help=False,
    invoke_without_command=True,
)

console = Console()


def _run_claude_for_ci(prompt: str) -> None:
    """Run Claude to handle CI/review workflow."""
    console.print("[cyan]Invoking Claude to manage CI and reviews...[/cyan]")
    console.print()

    try:
        # Use subprocess to run claude with the prompt
        # --dangerously-skip-permissions allows Claude to handle GitHub CLI
        # operations (check CI, respond to reviews, merge) without prompts
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "--print", prompt],
            check=False,
        )
        if result.returncode != 0:
            console.print("[yellow]Claude exited with non-zero status[/yellow]")
    except FileNotFoundError:
        console.print("[red]Claude CLI not found. Install it or use --no-ci flag.[/red]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130)


@app.callback(invoke_without_command=True)
def pr_command(
    ctx: typer.Context,
    target: Annotated[
        str | None,
        typer.Argument(
            help="Epic ID, branch name, or omit for current branch",
        ),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option(
            "--title",
            "-t",
            help="PR title (default: from epic or branch name)",
        ),
    ] = None,
    base: Annotated[
        str | None,
        typer.Option(
            "--base",
            "-b",
            help="Target branch (default: from binding or main)",
        ),
    ] = None,
    draft: Annotated[
        bool,
        typer.Option(
            "--draft",
            help="Create as draft PR",
        ),
    ] = False,
    push: Annotated[
        bool,
        typer.Option(
            "--push",
            help="Push branch to remote before creating PR",
        ),
    ] = False,
    no_ci: Annotated[
        bool,
        typer.Option(
            "--no-ci",
            help="Just create PR, skip CI/review handling (old behavior)",
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
    Create a pull request for an epic or branch.

    By default, creates a PR and then invokes Claude to wait for CI,
    address review comments, and report when ready to merge.

    Use --no-ci to just create the PR and exit (old cub pr behavior).

    Examples:

        # Create PR for current branch, wait for CI
        cub pr

        # Create PR for an epic
        cub pr cub-vd6

        # Create draft PR with custom title
        cub pr --draft --title "WIP: New feature"

        # Just create PR, skip CI handling
        cub pr --no-ci

        # Push branch and create PR
        cub pr --push
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    project_dir = Path.cwd()

    try:
        service = PRService(project_dir)

        # Create PR
        result = service.create_pr(
            target=target,
            title=title,
            base=base,
            draft=draft,
            push=push,
            dry_run=dry_run,
        )

        if dry_run:
            console.print("[dim]Dry run - no changes made[/dim]")
            return

        # If --no-ci, we're done
        if no_ci:
            console.print()
            console.print(f"View PR: {result.url}")
            return

        # If PR already existed, also done
        if not result.created:
            console.print()
            console.print(f"View PR: {result.url}")
            return

        # Run Claude to handle CI/reviews
        console.print()
        resolved = service.resolve_input(target)
        branch = resolved.branch or target or "current"
        base_branch = base or (resolved.binding.base_branch if resolved.binding else "main")

        prompt = service.get_claude_ci_prompt(
            pr_number=result.number,
            branch=branch,
            base=base_branch,
        )

        _run_claude_for_ci(prompt)

    except PRServiceError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except GitHubClientError as e:
        console.print(f"[red]GitHub error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def status(
    target: Annotated[
        str | None,
        typer.Argument(
            help="Epic ID, branch name, PR number, or omit for current branch",
        ),
    ] = None,
) -> None:
    """
    Show PR status for an epic or branch.

    Displays PR info, CI check status, and review status.

    Examples:

        cub pr status           # Status for current branch
        cub pr status cub-vd6   # Status for epic
        cub pr status 123       # Status for PR #123
    """
    project_dir = Path.cwd()

    try:
        service = PRService(project_dir)
        resolved = service.resolve_input(target)

        # Get PR info
        pr_info = None
        pr_number: int | None = None

        if resolved.type == "pr":
            pr_number = resolved.pr_number
            pr_info = service.github_client.get_pr(pr_number or 0)
        elif resolved.binding and resolved.binding.pr_number:
            pr_number = resolved.binding.pr_number
            pr_info = service.github_client.get_pr(pr_number)
        elif resolved.branch:
            base = resolved.binding.base_branch if resolved.binding else "main"
            existing = service.github_client.get_pr_by_branch(resolved.branch, base)
            if existing:
                pr_number = int(existing.get("number") or 0)
                pr_info = service.github_client.get_pr(pr_number)

        if not pr_info:
            console.print(f"No PR found for {target or 'current branch'}")
            if resolved.branch:
                console.print(f"Create one with: cub pr {resolved.branch}")
            raise typer.Exit(1)

        # Display PR info
        console.print()
        console.print(f"[bold]PR #{pr_info.get('number')}[/bold]: {pr_info.get('title')}")
        console.print(f"  State: {pr_info.get('state')}")
        console.print(f"  {pr_info.get('head')} -> {pr_info.get('base')}")
        console.print(f"  URL: {pr_info.get('url')}")

        # Get checks
        if pr_number:
            checks = service.github_client.get_pr_checks(pr_number)
            if checks:
                console.print()
                console.print("[bold]CI Checks:[/bold]")
                for check in checks:
                    status_str = check.get("status", "unknown")
                    conclusion = check.get("conclusion")
                    if conclusion:
                        if conclusion == "success":
                            icon = "[green]✓[/green]"
                        elif conclusion in ("failure", "cancelled"):
                            icon = "[red]✗[/red]"
                        else:
                            icon = "[yellow]?[/yellow]"
                        console.print(f"  {icon} {check.get('name')}: {conclusion}")
                    else:
                        console.print(f"  [dim]⋯[/dim] {check.get('name')}: {status_str}")

    except PRServiceError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except GitHubClientError as e:
        console.print(f"[red]GitHub error:[/red] {e}")
        raise typer.Exit(1)
