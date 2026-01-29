"""
Cub CLI - PR command.

Create and manage pull requests for epics or branches.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
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


class RichPRCallback:
    """Rich Console-based implementation of PREventCallback."""

    def __init__(self, console: Console, stream: bool = False) -> None:
        """
        Initialize callback.

        Args:
            console: Rich console for output
            stream: Whether to show streaming progress messages
        """
        self.console = console
        self.stream = stream

    def on_progress(self, message: str) -> None:
        """Display progress message if streaming is enabled."""
        if self.stream:
            self.console.print(f"[cyan]→[/cyan] {message}")

    def on_status(self, message: str, level: str = "info") -> None:
        """Display status message with appropriate styling."""
        if level == "success":
            self.console.print(f"[green]{message}[/green]")
        elif level == "warning":
            self.console.print(f"[yellow]{message}[/yellow]")
        elif level == "error":
            self.console.print(f"[red]{message}[/red]")
        else:
            self.console.print(message)

    def on_info(self, message: str) -> None:
        """Display informational message."""
        self.console.print(message)


# Timeout for Claude CI invocation (10 minutes max)
CLAUDE_CI_TIMEOUT_SECONDS = 600


class ClaudeCIResult(Enum):
    """Result of Claude CI invocation."""

    SUCCESS = "success"
    CLAUDE_NOT_FOUND = "claude_not_found"
    EXECUTION_FAILED = "execution_failed"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"


@dataclass
class ClaudeCIOutcome:
    """Outcome of Claude CI invocation."""

    result: ClaudeCIResult
    message: str
    exit_code: int | None = None
    stderr: str | None = None


def _run_claude_for_ci(prompt: str) -> ClaudeCIOutcome:
    """
    Run Claude to handle CI/review workflow.

    Returns an outcome with status and message rather than raising exceptions,
    allowing the caller to handle graceful degradation.

    Args:
        prompt: The prompt to send to Claude for CI management.

    Returns:
        ClaudeCIOutcome with result status, message, and optional details.
    """
    console.print("[cyan]Invoking Claude to manage CI and reviews...[/cyan]")
    console.print()

    try:
        # Use subprocess to run claude with the prompt
        # --dangerously-skip-permissions allows Claude to handle GitHub CLI
        # operations (check CI, respond to reviews, merge) without prompts
        # Capture output to get error details if something goes wrong
        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "--print", prompt],
            check=False,
            capture_output=True,
            text=True,
            timeout=CLAUDE_CI_TIMEOUT_SECONDS,
        )

        if result.returncode == 0:
            return ClaudeCIOutcome(
                result=ClaudeCIResult.SUCCESS,
                message="Claude CI management completed successfully",
                exit_code=0,
            )
        else:
            # Extract useful error info from stderr
            stderr = result.stderr.strip() if result.stderr else None
            # Common error pattern from Claude CLI
            error_hint = ""
            if stderr:
                if "No messages returned" in stderr:
                    error_hint = " (Claude returned no response - may be a connection issue)"
                elif "connection" in stderr.lower():
                    error_hint = " (connection issue)"

            return ClaudeCIOutcome(
                result=ClaudeCIResult.EXECUTION_FAILED,
                message=f"Claude exited with code {result.returncode}{error_hint}",
                exit_code=result.returncode,
                stderr=stderr,
            )

    except FileNotFoundError:
        return ClaudeCIOutcome(
            result=ClaudeCIResult.CLAUDE_NOT_FOUND,
            message="Claude CLI not found. Install Claude Code or use --no-ci flag.",
        )
    except subprocess.TimeoutExpired:
        return ClaudeCIOutcome(
            result=ClaudeCIResult.TIMEOUT,
            message=f"Claude CI invocation timed out after {CLAUDE_CI_TIMEOUT_SECONDS}s",
        )
    except KeyboardInterrupt:
        return ClaudeCIOutcome(
            result=ClaudeCIResult.INTERRUPTED,
            message="Interrupted by user",
        )
    except Exception as e:
        # Catch-all for unexpected errors (e.g., OSError, permission issues)
        return ClaudeCIOutcome(
            result=ClaudeCIResult.EXECUTION_FAILED,
            message=f"Unexpected error invoking Claude: {e}",
        )


def _pr_needs_work(pr_number: int) -> tuple[bool, str]:
    """
    Check if a PR has unresolved work (failing CI, pending reviews, etc.).

    Returns:
        Tuple of (needs_work: bool, reason: str)
    """
    import json

    try:
        # Get PR status including checks and review decision
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--json",
                "reviewDecision,statusCheckRollup,state",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return False, "Could not check PR status"

        data = json.loads(result.stdout)

        # Check if PR is already merged or closed
        state = data.get("state", "").upper()
        if state == "MERGED":
            return False, "PR is already merged"
        if state == "CLOSED":
            return False, "PR is closed"

        reasons: list[str] = []

        # Check CI status
        checks = data.get("statusCheckRollup", []) or []
        failing_checks = []
        pending_checks = []
        for check in checks:
            conclusion = check.get("conclusion", "").upper()
            status = check.get("status", "").upper()
            name = check.get("name", "unknown")

            if conclusion in ("FAILURE", "CANCELLED", "TIMED_OUT"):
                failing_checks.append(name)
            elif status in ("QUEUED", "IN_PROGRESS", "PENDING") or (
                status == "COMPLETED" and not conclusion
            ):
                pending_checks.append(name)

        if failing_checks:
            reasons.append(f"failing CI: {', '.join(failing_checks[:3])}")
        if pending_checks:
            reasons.append(f"pending CI: {', '.join(pending_checks[:3])}")

        # Check review decision
        review_decision = data.get("reviewDecision", "").upper()
        if review_decision == "CHANGES_REQUESTED":
            reasons.append("changes requested")
        elif review_decision == "REVIEW_REQUIRED":
            reasons.append("review required")

        if reasons:
            return True, "; ".join(reasons)

        return False, "all checks passing, no changes requested"

    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return False, "Could not check PR status"


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
    stream: Annotated[
        bool,
        typer.Option(
            "--stream",
            "-s",
            help="Show real-time output from PR creation process",
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

        # Show real-time progress
        cub pr --stream

        # Show progress with debug details
        cub pr --stream --debug
    """
    # Skip if a subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    project_dir = Path.cwd()

    # Create callback for Rich output
    callback = RichPRCallback(console=console, stream=stream)

    try:
        service = PRService(project_dir, callback=callback)

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

        # If PR already existed, check if there's unresolved work
        if not result.created:
            needs_work, reason = _pr_needs_work(result.number)
            if not needs_work:
                console.print()
                console.print(f"[green]PR #{result.number}:[/green] {reason}")
                console.print(f"View PR: {result.url}")
                return
            # There's work to do - continue to Claude CI handling
            console.print()
            console.print(f"[yellow]PR #{result.number} needs attention:[/yellow] {reason}")

        # Always show the PR URL first (graceful degradation - PR exists even if CI fails)
        console.print()
        console.print(f"[green]View PR:[/green] {result.url}")
        console.print()

        # Run Claude to handle CI/reviews
        resolved = service.resolve_input(target)
        branch = resolved.branch or target or "current"
        base_branch = base or (resolved.binding.base_branch if resolved.binding else "main")

        prompt = service.get_claude_ci_prompt(
            pr_number=result.number,
            branch=branch,
            base=base_branch,
        )

        outcome = _run_claude_for_ci(prompt)

        # Handle the outcome with graceful degradation
        if outcome.result == ClaudeCIResult.SUCCESS:
            console.print()
            console.print("[green]Claude CI management completed.[/green]")
        elif outcome.result == ClaudeCIResult.INTERRUPTED:
            # User interrupted - just note it, PR is already created
            console.print()
            console.print("[yellow]Claude CI handling interrupted.[/yellow]")
            console.print(f"[dim]You can check CI manually: gh pr checks {branch} --watch[/dim]")
        elif outcome.result == ClaudeCIResult.CLAUDE_NOT_FOUND:
            console.print()
            console.print(f"[yellow]Warning:[/yellow] {outcome.message}")
            console.print(f"[dim]You can check CI manually: gh pr checks {branch} --watch[/dim]")
        else:
            # EXECUTION_FAILED or TIMEOUT - PR still created, provide context
            console.print()
            console.print(f"[yellow]Warning:[/yellow] {outcome.message}")
            if outcome.stderr:
                # Show first line of stderr for context
                first_line = outcome.stderr.split("\n")[0][:200]
                if first_line:
                    console.print(f"[dim]Details: {first_line}[/dim]")
            console.print(f"[dim]You can check CI manually: gh pr checks {branch} --watch[/dim]")

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
