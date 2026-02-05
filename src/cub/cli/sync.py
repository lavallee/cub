"""
Cub CLI - Sync command for git-based task synchronization.

Provides CLI interface to the SyncService for syncing task state
to a git branch without affecting the working tree.
"""

import typer
from rich.console import Console
from rich.table import Table

from cub.cli.errors import ExitCode, print_sync_not_initialized_error
from cub.core.ids.counters import ensure_counters
from cub.core.sync import SyncService, SyncStatus
from cub.core.sync.service import GitError

console = Console()
app = typer.Typer(
    name="sync",
    help="Sync task state to git branch",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def sync(
    ctx: typer.Context,
    pull: bool = typer.Option(
        False,
        "--pull",
        help="Pull and merge remote changes before syncing",
    ),
    push: bool = typer.Option(
        False,
        "--push",
        help="Push local changes to remote after syncing",
    ),
    message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Custom commit message",
    ),
) -> None:
    """
    Sync task state to the cub-sync branch.

    By default, commits current task state locally. Use --pull to fetch
    and merge remote changes first, or --push to push local changes after.

    Examples:
        cub sync                    # Commit task state locally
        cub sync --pull             # Pull remote changes first, then commit
        cub sync --push             # Commit and push to remote
        cub sync --pull --push      # Full sync: pull, commit, push
        cub sync -m "Custom msg"    # Use custom commit message
    """
    # If a subcommand was invoked, don't run the default action
    if ctx.invoked_subcommand is not None:
        return

    try:
        sync_service = SyncService()

        # Check if initialized
        if not sync_service.is_initialized():
            print_sync_not_initialized_error()
            raise typer.Exit(ExitCode.USER_ERROR)

        # Pull if requested
        if pull:
            console.print("[blue]Pulling remote changes...[/blue]")
            result = sync_service.pull()

            if not result.success:
                console.print(f"[red]Pull failed:[/red] {result.message}")
                raise typer.Exit(1)

            if result.tasks_updated > 0:
                console.print(
                    f"[green]✓[/green] Merged {result.tasks_updated} tasks from remote"
                )
                if result.conflicts:
                    console.print(
                        f"[yellow]⚠[/yellow]  Resolved {len(result.conflicts)} conflicts"
                    )
            else:
                console.print("[green]✓[/green] Already up to date with remote")

        # Commit current state
        try:
            commit_sha = sync_service.commit(message)
            console.print(f"[green]✓[/green] Committed: {commit_sha[:8]}")
        except RuntimeError as e:
            error_msg = str(e)
            if "No changes to commit" in error_msg:
                console.print("[blue]No changes to commit[/blue]")
            else:
                console.print(f"[red]Commit failed:[/red] {error_msg}")
                raise typer.Exit(1)

        # Push if requested
        if push:
            console.print("[blue]Pushing to remote...[/blue]")
            success = sync_service.push()

            if success:
                console.print("[green]✓[/green] Pushed to remote")
            else:
                console.print("[red]Push failed[/red]")
                raise typer.Exit(1)

    except GitError as e:
        console.print(f"[red]Git error:[/red] {e.stderr or str(e)}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def status(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed status information",
    ),
) -> None:
    """
    Show sync status.

    Displays the current state of the sync branch, including whether
    it's up-to-date, ahead, or behind the remote.

    Examples:
        cub sync status           # Show basic sync status
        cub sync status -v        # Show detailed status with timestamps
    """
    try:
        sync_service = SyncService()
        sync_status = sync_service.get_status()
        state = sync_service.get_state()

        # Status icon and message
        status_icons = {
            SyncStatus.UP_TO_DATE: ("✓", "green", "Up to date with remote"),
            SyncStatus.AHEAD: ("↑", "yellow", "Local changes not pushed"),
            SyncStatus.BEHIND: ("↓", "yellow", "Remote changes available"),
            SyncStatus.DIVERGED: ("⚠", "red", "Local and remote have diverged"),
            SyncStatus.NO_REMOTE: ("○", "blue", "No remote branch"),
            SyncStatus.UNINITIALIZED: ("✗", "red", "Not initialized"),
        }

        icon, color, message = status_icons[sync_status]
        console.print(f"[{color}]{icon}[/{color}] {message}")

        if sync_status == SyncStatus.UNINITIALIZED:
            console.print("\nRun [bold]cub sync init[/bold] to initialize.")
            raise typer.Exit(1)

        # Show verbose details
        if verbose:
            table = Table(title="Sync Details", show_header=False)
            table.add_column("Field", style="cyan")
            table.add_column("Value")

            table.add_row("Branch", state.branch_name)
            table.add_row("Tasks file", state.tasks_file)

            if state.last_commit_sha:
                table.add_row("Last commit", state.last_commit_sha[:8])

            if state.last_sync_at:
                table.add_row("Last synced", state.last_sync_at.strftime("%Y-%m-%d %H:%M:%S"))

            if state.last_push_at:
                table.add_row("Last pushed", state.last_push_at.strftime("%Y-%m-%d %H:%M:%S"))
            elif state.last_commit_sha:
                table.add_row("Last pushed", "[dim]Never[/dim]")

            table.add_row("Remote", state.remote_name)

            console.print()
            console.print(table)

        # Show actionable recommendations
        if sync_status == SyncStatus.AHEAD:
            console.print("\n[dim]→ Run [bold]cub sync --push[/bold] to push your changes[/dim]")
        elif sync_status == SyncStatus.BEHIND:
            console.print("\n[dim]→ Run [bold]cub sync --pull[/bold] to pull remote changes[/dim]")
        elif sync_status == SyncStatus.DIVERGED:
            console.print(
                "\n[dim]→ Run [bold]cub sync --pull[/bold] to merge (last-write-wins)[/dim]"
            )
        elif sync_status == SyncStatus.NO_REMOTE:
            console.print("\n[dim]→ Run [bold]cub sync --push[/bold] to create remote branch[/dim]")

    except GitError as e:
        console.print(f"[red]Git error:[/red] {e.stderr or str(e)}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def init(
    branch_name: str = typer.Option(
        "cub-sync",
        "--branch",
        "-b",
        help="Name of the sync branch",
    ),
) -> None:
    """
    Initialize the sync branch.

    Creates a new branch for syncing task state. This branch will be
    managed by cub and should not be checked out manually.

    Examples:
        cub sync init                    # Initialize with default branch name
        cub sync init --branch my-sync   # Use custom branch name
    """
    try:
        sync_service = SyncService(branch_name=branch_name)

        if sync_service.is_initialized():
            console.print(f"[yellow]Sync branch '{branch_name}' already exists[/yellow]")
            raise typer.Exit(1)

        console.print(f"[blue]Initializing sync branch: {branch_name}[/blue]")
        sync_service.initialize()

        # Initialize counters (scans existing tasks to avoid ID collisions)
        counters = ensure_counters(sync_service)
        if counters.spec_number > 0 or counters.standalone_task_number > 0:
            console.print(
                f"[dim]Initialized counters from existing tasks: "
                f"spec={counters.spec_number}, standalone={counters.standalone_task_number}[/dim]"
            )

        console.print(f"[green]✓[/green] Initialized sync branch: {branch_name}")
        console.print(
            "\n[dim]Task state will be synced to this branch automatically.[/dim]"
        )
        console.print("[dim]Run [bold]cub sync[/bold] to commit your first sync.[/dim]")

    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except GitError as e:
        console.print(f"[red]Git error:[/red] {e.stderr or str(e)}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def agent(
    push: bool = typer.Option(
        False,
        "--push",
        help="Push local managed sections to sync branch",
    ),
    pull: bool = typer.Option(
        False,
        "--pull",
        help="Pull managed sections from sync branch",
    ),
) -> None:
    """
    Sync managed sections in agent.md across worktrees and branches.

    Managed sections are marked with special comments and contain content
    that should be synchronized across different worktrees (e.g., task
    workflow instructions, project-specific conventions).

    By default (no flags), pulls managed sections from sync branch.

    Examples:
        cub sync agent              # Pull managed sections from sync branch
        cub sync agent --pull       # Explicitly pull from sync branch
        cub sync agent --push       # Push local sections to sync branch
    """
    try:
        sync_service = SyncService()

        # Check if initialized
        if not sync_service.is_initialized():
            print_sync_not_initialized_error()
            raise typer.Exit(ExitCode.USER_ERROR)

        # Default to pull if no direction specified
        if not push and not pull:
            pull = True

        # Handle push
        if push:
            console.print("[blue]Pushing managed sections to sync branch...[/blue]")
            result = sync_service.sync_agent_push()

            if not result.success:
                console.print(f"[red]Push failed:[/red] {result.message}")
                if result.conflicts:
                    console.print("[yellow]Conflicts:[/yellow]")
                    for conflict in result.conflicts:
                        console.print(f"  - {conflict.task_id}")
                raise typer.Exit(1)

            if result.tasks_updated > 0:
                console.print(
                    f"[green]✓[/green] {result.message} (commit: {result.commit_sha[:8] if result.commit_sha else 'N/A'})"  # noqa: E501
                )
            else:
                console.print(f"[blue]{result.message}[/blue]")

        # Handle pull
        if pull:
            console.print("[blue]Pulling managed sections from sync branch...[/blue]")
            result = sync_service.sync_agent_pull()

            if not result.success:
                console.print(f"[red]Pull failed:[/red] {result.message}")
                if result.conflicts:
                    console.print("[yellow]Conflicts detected:[/yellow]")
                    for conflict in result.conflicts:
                        console.print(f"  - {conflict.task_id}")
                    console.print(
                        "\n[dim]Resolve conflicts manually and try again.[/dim]"
                    )
                raise typer.Exit(1)

            if result.tasks_updated > 0:
                console.print(f"[green]✓[/green] {result.message}")
            else:
                console.print(f"[blue]{result.message}[/blue]")

    except GitError as e:
        console.print(f"[red]Git error:[/red] {e.stderr or str(e)}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


__all__ = ["app"]
