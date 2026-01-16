"""
Cub CLI - Worktree command.

Manage git worktrees for parallel task execution.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.worktree.manager import WorktreeError, WorktreeManager

app = typer.Typer(
    name="worktree",
    help="Manage git worktrees for parallel task execution",
    no_args_is_help=False,
)

console = Console()


@app.callback(invoke_without_command=True)
def worktree_main(ctx: typer.Context) -> None:
    """
    Manage git worktrees for parallel task execution.

    Worktrees allow running multiple tasks simultaneously in isolated
    git working directories. Each task gets its own worktree under .cub/worktrees/.

    Examples:
        cub worktree list              # Show all worktrees
        cub worktree create <branch>   # Create a new worktree
        cub worktree clean             # Remove merged worktrees
        cub worktree remove <path>     # Remove a specific worktree
    """
    if ctx.invoked_subcommand is None:
        # Show worktree list when no subcommand specified
        _worktree_list()


@app.command()
def list(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show additional details",
    ),
) -> None:
    """
    Show all worktrees in the repository.

    Displays path, branch, and commit information for each worktree.
    Includes task association if the worktree is under .cub/worktrees/.

    Examples:
        cub worktree list              # Show all worktrees
        cub worktree list --verbose    # Show detailed information
    """
    _worktree_list(verbose=verbose)


def _worktree_list(verbose: bool = False) -> None:
    """Internal implementation of worktree list."""
    try:
        manager = WorktreeManager()
        worktrees = manager.list()

        if not worktrees:
            console.print("[yellow]No worktrees found[/yellow]")
            return

        # Create table
        table = Table(title="Git Worktrees")
        table.add_column("Path", style="cyan")
        table.add_column("Branch", style="green")
        table.add_column("Commit", style="blue")
        if verbose:
            table.add_column("Locked", style="red")
            table.add_column("Task", style="magenta")

        for wt in worktrees:
            # Skip bare repository
            if wt.is_bare:
                continue

            # Extract task ID if worktree is under .cub/worktrees/
            task_id = None
            if ".cub/worktrees/" in str(wt.path):
                try:
                    task_id = wt.path.parent.name if wt.path.parent.name != "worktrees" else None
                except Exception:
                    pass

            # Format branch name
            branch = wt.branch or "[dim]detached[/dim]"
            if wt.branch and wt.branch.startswith("refs/heads/"):
                branch = wt.branch[len("refs/heads/") :]

            # Format commit (short form)
            commit = wt.commit[:7] if wt.commit else "unknown"

            if verbose:
                locked_status = "[red]locked[/red]" if wt.is_locked else ""
                task_col = task_id or ""
                table.add_row(str(wt.path), branch, commit, locked_status, task_col)
            else:
                table.add_row(str(wt.path), branch, commit)

        console.print(table)

    except WorktreeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def create(
    branch: str = typer.Argument(..., help="Branch name or task ID"),
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        "-t",
        help="Task ID for organizing worktrees (defaults to branch name)",
    ),
) -> None:
    """
    Create a new worktree.

    Creates a git worktree with an optional new branch. If no task-id is
    specified, the branch name is used as the task identifier.

    Examples:
        cub worktree create feature/new-feature
        cub worktree create cub-042 --task-id cub-042
        cub worktree create my-branch -t cub-043
    """
    try:
        manager = WorktreeManager()
        actual_task_id = task_id or branch
        worktree = manager.create(actual_task_id, branch=branch, create_branch=True)

        console.print(f"[green]✓[/green] Created worktree at: {worktree.path}")
        console.print(f"  Branch: [cyan]{worktree.branch}[/cyan]")
        console.print(f"  Commit: [blue]{worktree.commit[:7]}[/blue]")
        console.print(f"  Task ID: [magenta]{actual_task_id}[/magenta]")

    except WorktreeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def remove(
    path: str = typer.Argument(..., help="Path to the worktree"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force removal even if worktree has uncommitted changes",
    ),
) -> None:
    """
    Remove a worktree.

    Removes a worktree and its associated administrative data. By default,
    refuses to remove worktrees with uncommitted changes. Use --force to override.

    Examples:
        cub worktree remove .cub/worktrees/cub-042
        cub worktree remove .cub/worktrees/cub-042 --force
    """
    try:
        manager = WorktreeManager()
        worktree_path = Path(path)
        manager.remove(worktree_path, force=force)

        console.print(f"[green]✓[/green] Removed worktree: {worktree_path}")

    except WorktreeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def clean(
    base_branch: str = typer.Option(
        "main",
        "--base",
        "-b",
        help="Base branch to check for merged branches",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show removed worktrees",
    ),
) -> None:
    """
    Remove worktrees for merged branches.

    Automatically removes worktrees whose branches have been merged into
    the base branch. This helps clean up after completing tasks.

    By default, checks against 'main' branch. Use --base to specify a
    different base branch (e.g., 'develop').

    Examples:
        cub worktree clean              # Clean up merged worktrees
        cub worktree clean --base develop
        cub worktree clean -v           # Show removed worktrees
    """
    try:
        manager = WorktreeManager()
        removed = manager.cleanup_merged(base_branch=base_branch)

        if not removed:
            console.print("[yellow]No merged worktrees to clean[/yellow]")
            return

        console.print(f"[green]✓[/green] Cleaned up {len(removed)} merged worktree(s)")

        if verbose:
            console.print("\nRemoved:")
            for path in removed:
                console.print(f"  - {path}")

    except WorktreeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)


__all__ = ["app"]
