"""
Cub CLI - Doctor command.

Diagnose and optionally fix common cub issues.
"""

import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from cub.core.tasks.backend import get_backend
from cub.core.tasks.models import TaskStatus, TaskType
from cub.utils.project import get_project_root

app = typer.Typer(
    name="doctor",
    help="Diagnose and fix configuration issues",
    no_args_is_help=False,
)

console = Console()


def check_stale_epics(project_dir: Path, fix: bool = False) -> tuple[int, list[str]]:
    """
    Check for stale epics (epics where all subtasks are complete).

    Args:
        project_dir: Project directory path
        fix: If True, auto-close stale epics

    Returns:
        Tuple of (issue_count, fixed_epic_ids)
    """
    try:
        backend = get_backend(project_dir=project_dir)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load task backend: {e}[/yellow]")
        return 0, []

    # Get all tasks
    try:
        all_tasks = backend.list_tasks()
    except Exception as e:
        console.print(f"[yellow]Warning: Could not list tasks: {e}[/yellow]")
        return 0, []

    # Find open epics
    open_epics = [
        task
        for task in all_tasks
        if task.type == TaskType.EPIC and task.status != TaskStatus.CLOSED
    ]

    if not open_epics:
        console.print("[green]✓[/green] No open epics to check")
        return 0, []

    stale_epics = []
    stale_details = []

    for epic in open_epics:
        # Find subtasks: tasks with parent == epic_id OR tasks with ID prefix matching epic_id
        # (beads convention: epic-id.1, epic-id.2, etc.)
        subtasks_by_parent = [t for t in all_tasks if t.parent == epic.id and t.id != epic.id]
        subtasks_by_prefix = [
            t for t in all_tasks if t.id.startswith(f"{epic.id}.") and t.id != epic.id
        ]

        # Combine and deduplicate
        seen_ids: set[str] = set()
        subtasks = []
        for task in subtasks_by_parent + subtasks_by_prefix:
            if task.id not in seen_ids:
                seen_ids.add(task.id)
                subtasks.append(task)

        # Skip epics with no subtasks (they may be parent containers)
        if not subtasks:
            continue

        # Count subtask statuses
        open_count = sum(1 for t in subtasks if t.status == TaskStatus.OPEN)
        in_progress_count = sum(1 for t in subtasks if t.status == TaskStatus.IN_PROGRESS)
        closed_count = sum(1 for t in subtasks if t.status == TaskStatus.CLOSED)

        # Check if all subtasks are closed
        if open_count == 0 and in_progress_count == 0 and closed_count > 0:
            stale_epics.append(epic.id)
            stale_details.append(f"{epic.id} ({epic.title}) - {closed_count} subtasks complete")

    if not stale_epics:
        console.print("[green]✓[/green] No stale epics found")
        return 0, []

    # Report stale epics
    console.print(
        f"[yellow]![/yellow] Found {len(stale_epics)} stale epic(s) with all subtasks complete"
    )
    for detail in stale_details:
        console.print(f"  • {detail}")

    # Fix if requested
    fixed_epics = []
    if fix:
        console.print("\n[bold]Auto-closing stale epics:[/bold]")
        for epic_id in stale_epics:
            try:
                backend.close_task(epic_id, reason="Auto-closed: all subtasks complete")
                console.print(f"  [green]✓[/green] Closed: {epic_id}")
                fixed_epics.append(epic_id)
            except Exception as e:
                console.print(f"  [red]✗[/red] Failed to close {epic_id}: {e}")

        if fixed_epics:
            console.print(f"\n[green]✓[/green] Auto-closed {len(fixed_epics)} stale epic(s)")

    return len(stale_epics), fixed_epics


def check_environment() -> int:
    """
    Check for required tools and environment.

    Returns:
        Number of issues found
    """
    issues = 0

    console.print("\n[bold]System Requirements:[/bold]")

    # Check git
    if _check_command("git"):
        version = _get_command_version("git", ["--version"])
        console.print(f"[green]✓[/green] git {version}")
    else:
        console.print("[red]✗[/red] git not installed (required)")
        console.print("[dim]→ Install: https://git-scm.com/downloads[/dim]")
        issues += 1

    # Check for at least one harness
    console.print("\n[bold]AI Harnesses:[/bold]")
    harness_found = False
    harnesses = ["claude", "codex", "gemini", "opencode"]

    for harness in harnesses:
        if _check_command(harness):
            version = _get_command_version(harness, ["--version"])
            console.print(f"[green]✓[/green] {harness} {version}")
            harness_found = True

    if not harness_found:
        console.print(
            "[red]✗[/red] No AI harness found (need claude, codex, gemini, or opencode)"
        )
        console.print("[dim]→ Install: pip install anthropic-claude  # or another harness[/dim]")
        console.print("[dim]  Docs: https://docs.anthropic.com/claude-code[/dim]")
        issues += 1

    # Check beads (optional)
    console.print("\n[bold]Optional Tools:[/bold]")
    if _check_command("bd"):
        version = _get_command_version("bd", ["--version"])
        console.print(f"[green]✓[/green] beads (bd) {version}")
    else:
        console.print("[dim]ℹ[/dim] beads (bd) not installed (optional)")

    return issues


def _check_command(cmd: str) -> bool:
    """Check if a command is available in PATH."""
    try:
        subprocess.run(
            [cmd, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _get_command_version(cmd: str, args: list[str]) -> str:
    """Get version string from a command."""
    try:
        result = subprocess.run(
            [cmd] + args,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            # Clean up version output
            version = result.stdout.strip().split("\n")[0]
            # Remove common prefixes
            for prefix in ["git version ", "jq-", "tmux ", "docker version "]:
                if version.startswith(prefix):
                    version = version[len(prefix) :]
            return version
        return "unknown"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


@app.callback(invoke_without_command=True)
def doctor(
    ctx: typer.Context,
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Automatically fix detected issues",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed diagnostic info",
    ),
) -> None:
    """
    Diagnose and optionally fix common cub issues.

    Checks:
    - Environment: git, harness availability
    - Task state: stale epics (epics where all subtasks are complete)

    Fix Actions:
    --fix will:
    - Auto-close stale epics with "Auto-closed: all subtasks complete"

    Examples:
        cub doctor              # Run diagnostics
        cub doctor --fix        # Auto-fix detected issues
        cub doctor --verbose    # Show detailed diagnostic info
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Fix mode: {fix}[/dim]")
        console.print(f"[dim]Verbose: {verbose}[/dim]")

    console.print(Panel("[bold]Cub Doctor[/bold] - Diagnostic Tool", expand=False))

    try:
        # Get project root
        project_dir = get_project_root()

        # Run checks
        total_issues = 0

        # Check environment
        total_issues += check_environment()

        # Check stale epics
        console.print("\n[bold]Stale Epics:[/bold]")
        stale_count, fixed_epics = check_stale_epics(project_dir, fix=fix)
        total_issues += stale_count

        # Summary
        console.print("\n" + "=" * 60)
        if total_issues == 0:
            console.print("[green]✓[/green] No issues found")
        else:
            console.print(f"[yellow]![/yellow] Found {total_issues} issue(s)")
            if not fix:
                console.print("\n[dim]Run 'cub doctor --fix' to auto-fix some issues[/dim]")

        # Exit with appropriate code
        if total_issues > 0 and not fix:
            raise typer.Exit(1)
        else:
            raise typer.Exit(0)

    except typer.Exit:
        # Re-raise typer.Exit without catching it
        raise
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if debug:
            import traceback

            console.print("[dim]" + traceback.format_exc() + "[/dim]")
        raise typer.Exit(1)
