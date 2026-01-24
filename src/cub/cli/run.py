"""
Cub CLI - Run command.

Execute autonomous task loop with specified harness.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cub.core.harness.async_backend import AsyncHarnessBackend

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cub.core.cleanup.service import CleanupService
from cub.core.config.loader import load_config
from cub.core.config.models import CubConfig
from cub.core.harness.async_backend import detect_async_harness, get_async_backend
from cub.core.harness.models import HarnessResult, TaskInput, TokenUsage
from cub.core.ledger.integration import LedgerIntegration
from cub.core.ledger.writer import LedgerWriter

# TODO: Restore when plan module is implemented
# from cub.core.plan.context import PlanContext
# from cub.core.plan.models import PlanStatus
from cub.core.sandbox.models import SandboxConfig, SandboxState
from cub.core.sandbox.provider import get_provider, is_provider_available
from cub.core.sandbox.state import clear_sandbox_state, save_sandbox_state
from cub.core.session import RunSessionManager, SessionBudget

# TODO: Restore when specs module is implemented
# from cub.core.specs.lifecycle import SpecLifecycleError, move_spec_to_implementing
from cub.core.status.models import (
    BudgetStatus,
    EventLevel,
    IterationInfo,
    RunArtifact,
    RunPhase,
    RunStatus,
    TaskArtifact,
)
from cub.core.status.writer import StatusWriter
from cub.core.tasks.backend import TaskBackend
from cub.core.tasks.backend import get_backend as get_task_backend
from cub.core.tasks.models import Task, TaskStatus
from cub.core.worktree.manager import WorktreeError, WorktreeManager
from cub.core.worktree.parallel import ParallelRunner
from cub.dashboard.tmux import get_dashboard_pane_size, launch_with_dashboard
from cub.utils.hooks import HookContext, run_hooks, run_hooks_async, wait_async_hooks


def _run_async(func: Any, *args: Any) -> Any:
    """
    Run an async function from a sync context.

    Uses asyncio.run() to execute async code from Typer's sync CLI context.
    This works with all async harness backends (both SDK and legacy shell-out).

    Args:
        func: An async function to call
        *args: Arguments to pass to the function

    Returns:
        The result of the async operation

    Example:
        # With no args
        result = _run_async(my_async_func)

        # With args
        result = _run_async(harness.run_task, task_input, debug)
    """
    import asyncio

    return asyncio.run(func(*args))


def _setup_harness(
    harness: str | None,
    priority_list: list[str] | None,
    debug: bool,
) -> tuple[str, AsyncHarnessBackend] | None:
    """
    Detect and validate harness backend.

    Centralizes harness setup logic used by main run loop, --direct, and --gh-issue.

    Args:
        harness: Explicit harness name or None for auto-detect
        priority_list: Priority list for auto-detection
        debug: Enable debug logging

    Returns:
        Tuple of (harness_name, backend) on success, or None on failure
        (error message already printed to console)
    """
    # Use module-level imports for detect_async_harness and get_async_backend
    # so that tests can mock them properly
    harness_name = harness or detect_async_harness(priority_list)
    if not harness_name:
        console.print(
            "[red]No harness available. Install claude, codex, or another supported harness.[/red]"
        )
        return None

    try:
        harness_backend: AsyncHarnessBackend = get_async_backend(harness_name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return None

    if not harness_backend.is_available():
        console.print(f"[red]Harness '{harness_name}' is not available. Is it installed?[/red]")
        return None

    if debug:
        console.print(f"[dim]Harness: {harness_name} (v{harness_backend.get_version()})[/dim]")

    return harness_name, harness_backend


def _invoke_harness(
    harness_backend: AsyncHarnessBackend,
    task_input: TaskInput,
    stream: bool,
    debug: bool,
    harness_log_path: Path | None = None,
) -> HarnessResult:
    """
    Invoke harness with unified streaming/blocking execution.

    Centralizes harness invocation logic used by main run loop, --direct, and --gh-issue.

    Args:
        harness_backend: The harness backend to use
        task_input: Task parameters (prompt, system_prompt, model, etc.)
        stream: Whether to stream output
        debug: Enable debug logging
        harness_log_path: Optional path to write raw harness output

    Returns:
        HarnessResult with output, usage, and timing
    """
    start_time = time.time()

    if stream and harness_backend.capabilities.streaming:
        # Stream execution with tee-like behavior (output to console AND file)
        sys.stdout.flush()

        async def _stream_and_collect() -> str:
            """Stream output and collect for result."""
            collected = ""
            # stream_task returns AsyncIterator[str] directly (async generator)
            stream_iter: AsyncIterator[str] = harness_backend.stream_task(task_input, debug=debug)  # type: ignore[assignment]
            async for chunk in stream_iter:
                _stream_callback(chunk)
                collected += chunk
            return collected

        result_output = _run_async(_stream_and_collect)
        sys.stdout.write("\n")
        sys.stdout.flush()

        # Write collected output to harness.log if path provided
        if harness_log_path is not None:
            try:
                harness_log_path.write_text(result_output, encoding="utf-8")
            except Exception as e:
                if debug:
                    console.print(f"[dim]Warning: Failed to write harness.log: {e}[/dim]")

        return HarnessResult(
            output=result_output,
            usage=TokenUsage(),  # Usage tracking TBD for streaming
            duration_seconds=time.time() - start_time,
            exit_code=0,
        )
    else:
        # Blocking execution with async backend
        task_result = _run_async(harness_backend.run_task, task_input, debug)

        # Write output to harness.log if path provided
        if harness_log_path is not None:
            try:
                harness_log_path.write_text(task_result.output, encoding="utf-8")
            except Exception as e:
                if debug:
                    console.print(f"[dim]Warning: Failed to write harness.log: {e}[/dim]")

        return HarnessResult(
            output=task_result.output,
            usage=task_result.usage,
            duration_seconds=task_result.duration_seconds,
            exit_code=task_result.exit_code,
            error=task_result.error,
            timestamp=task_result.timestamp,
        )


def _slugify(text: str, max_length: int = 40) -> str:
    """Convert text to a URL/branch-friendly slug."""
    import re

    # Convert to lowercase
    slug = text.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove non-alphanumeric characters (except hyphens)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate to max length (at word boundary if possible)
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug


def _create_branch_from_base(
    branch_name: str,
    base_branch: str,
    console: Console,
) -> bool:
    """
    Create a new git branch from a base branch.

    Args:
        branch_name: Name for the new branch
        base_branch: Branch to create from
        console: Rich console for output

    Returns:
        True if branch was created successfully
    """
    import subprocess

    from cub.core.branches.store import BranchStore

    # Check if branch already exists
    if BranchStore.git_branch_exists(branch_name):
        console.print(f"[yellow]Branch '{branch_name}' already exists[/yellow]")
        # Switch to it
        result = subprocess.run(
            ["git", "checkout", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            console.print(f"[red]Failed to switch to branch: {result.stderr}[/red]")
            return False
        console.print(f"[green]Switched to existing branch '{branch_name}'[/green]")
        return True

    # Verify base branch exists
    if not BranchStore.git_branch_exists(base_branch):
        # Try with origin/ prefix
        remote_base = f"origin/{base_branch}"
        if BranchStore.git_branch_exists(remote_base):
            base_branch = remote_base
        else:
            console.print(f"[red]Base branch '{base_branch}' does not exist[/red]")
            return False

    # Create and checkout new branch from base
    result = subprocess.run(
        ["git", "checkout", "-b", branch_name, base_branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        console.print(f"[red]Failed to create branch: {result.stderr}[/red]")
        return False

    console.print(f"[green]Created branch '{branch_name}' from '{base_branch}'[/green]")
    return True


def _get_gh_issue_title(issue_number: int) -> str | None:
    """Get the title of a GitHub issue."""
    import subprocess

    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "title", "-q", ".title"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (OSError, FileNotFoundError):
        return None


def _get_epic_title(epic_id: str) -> str | None:
    """Get the title of an epic from beads."""
    import json
    import subprocess

    try:
        result = subprocess.run(
            ["bd", "show", epic_id, "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # bd show returns a list with one element
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            if isinstance(data, dict):
                title = data.get("title")
                if isinstance(title, str):
                    return title
        return None
    except (OSError, FileNotFoundError, json.JSONDecodeError):
        return None


app = typer.Typer(
    name="run",
    help="Execute autonomous task loop",
    no_args_is_help=False,
)

console = Console()


def _stream_callback(text: str) -> None:
    """Write text to stdout with immediate flush for real-time streaming."""
    sys.stdout.write(text)
    sys.stdout.flush()


# Global flag for interrupt handling
_interrupted = False


def _signal_handler(signum: int, frame: object) -> None:
    """Handle SIGINT gracefully."""
    global _interrupted
    if _interrupted:
        # Second interrupt - force exit
        console.print("\n[bold red]Force exiting...[/bold red]")
        sys.exit(130)
    _interrupted = True
    console.print("\n[yellow]Interrupt received. Finishing current task...[/yellow]")


def _transition_staged_specs_to_implementing(
    project_dir: Path,
    debug: bool = False,
) -> list[Path]:
    """
    Transition specs from staged/ to implementing/ at run start.

    Finds all plans in STAGED status and moves their specs from
    specs/staged/ to specs/implementing/.

    Args:
        project_dir: Project root directory.
        debug: Show debug output.

    Returns:
        List of moved spec paths.

    Note:
        Currently stubbed - requires plan module implementation.
    """
    # TODO: Implement when plan module is ready
    # This function needs PlanContext and PlanStatus from cub.core.plan
    return []


def generate_system_prompt(project_dir: Path) -> str:
    """
    Generate the system prompt for the harness.

    Reads from PROMPT.md in the project directory or templates.
    """
    # Check for project-specific prompt
    prompt_files = [
        project_dir / "PROMPT.md",
        project_dir / "templates" / "PROMPT.md",
        Path(__file__).parent.parent.parent.parent / "templates" / "PROMPT.md",
    ]

    for prompt_file in prompt_files:
        if prompt_file.exists():
            return prompt_file.read_text()

    # Fallback minimal prompt
    return """# Autonomous Coding Session

You are an autonomous coding agent working through a task backlog.

## Workflow
1. Understand the task
2. Search the codebase before implementing
3. Implement the solution fully
4. Run tests and type checks
5. Close the task when complete
"""


def _read_direct_input(direct: str) -> str:
    """
    Read task content from direct input.

    Supports:
    - Plain string: "Add a logout button"
    - File path with @: @task.txt
    - Stdin: -

    Args:
        direct: The --direct argument value

    Returns:
        Task content string

    Raises:
        typer.Exit: On error reading input
    """
    if direct == "-":
        # Read from stdin
        if sys.stdin.isatty():
            console.print("[red]--direct - requires piped input[/red]")
            console.print("[dim]Example: echo 'task' | cub run --direct -[/dim]")
            raise typer.Exit(1)
        return sys.stdin.read().strip()

    if direct.startswith("@"):
        # Read from file
        file_path = Path(direct[1:])
        if not file_path.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            raise typer.Exit(1)
        return file_path.read_text().strip()

    # Plain string
    return direct.strip()


def generate_direct_task_prompt(task_content: str) -> str:
    """
    Generate a task prompt for direct mode (no task backend).

    Args:
        task_content: Raw task description provided via --direct

    Returns:
        Task prompt string
    """
    prompt_parts = []

    prompt_parts.append("## CURRENT TASK\n")
    prompt_parts.append("Mode: Direct (no task backend)")
    prompt_parts.append("")
    prompt_parts.append("Description:")
    prompt_parts.append(task_content)
    prompt_parts.append("")
    prompt_parts.append("When complete:")
    prompt_parts.append("1. Run feedback loops (typecheck, test, lint) if code was changed")
    prompt_parts.append("2. Commit changes if appropriate")
    prompt_parts.append("")
    prompt_parts.append(
        "Note: This is a direct task without a task backend. "
        "No task ID to close. Just complete the work described above."
    )

    return "\n".join(prompt_parts)


def generate_task_prompt(task: Task, task_backend: TaskBackend) -> str:
    """
    Generate the task prompt for a specific task.

    Args:
        task: Task to generate prompt for
        task_backend: The task backend instance

    Returns:
        Task prompt string
    """
    # Build the task prompt
    prompt_parts = []

    # Add task header
    prompt_parts.append("## CURRENT TASK\n")
    prompt_parts.append(f"Task ID: {task.id}")
    prompt_parts.append(f"Type: {task.type.value if hasattr(task.type, 'value') else task.type}")
    prompt_parts.append(f"Title: {task.title}\n")

    # Add description
    prompt_parts.append("Description:")
    prompt_parts.append(task.description or "(No description provided)")
    prompt_parts.append("")

    # Add acceptance criteria if present
    if task.acceptance_criteria:
        prompt_parts.append("Acceptance Criteria:")
        for criterion in task.acceptance_criteria:
            prompt_parts.append(f"- {criterion}")
        prompt_parts.append("")

    # Add backend-specific task management instructions
    prompt_parts.append("## Task Management\n")
    prompt_parts.append(task_backend.get_agent_instructions(task.id))
    prompt_parts.append("")

    # Add completion workflow (backend-agnostic)
    task_type_str = task.type.value if hasattr(task.type, "value") else task.type
    prompt_parts.append("## When Complete\n")
    prompt_parts.append("1. Run feedback loops (typecheck, test, lint)")
    prompt_parts.append("2. Mark the task complete (see Task Management above)")
    prompt_parts.append(f"3. Commit: `{task_type_str}({task.id}): {task.title}`")
    prompt_parts.append("4. Append learnings to progress.txt")

    return "\n".join(prompt_parts)


def display_task_info(task: Task, iteration: int, max_iterations: int) -> None:
    """Display information about the current task being executed."""
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    priority_str = task.priority.value if hasattr(task.priority, "value") else task.priority
    type_str = task.type.value if hasattr(task.type, "value") else task.type
    table.add_row("Task", f"[bold]{task.id}[/bold]")
    table.add_row("Title", task.title)
    table.add_row("Priority", str(priority_str))
    table.add_row("Type", str(type_str))
    table.add_row("Iteration", f"{iteration}/{max_iterations}")

    console.print(Panel(table, title="[bold]Current Task[/bold]", border_style="blue"))


def create_run_artifact(status: RunStatus, config: dict[str, Any] | None = None) -> RunArtifact:
    """
    Create a RunArtifact from RunStatus for persistence to run.json.

    Args:
        status: Current RunStatus
        config: Optional config snapshot

    Returns:
        RunArtifact with budget totals and completion info
    """
    # Determine completion time
    completed_at = datetime.now() if status.phase in [RunPhase.COMPLETED, RunPhase.FAILED, RunPhase.STOPPED] else None

    # Map phase to status string
    status_str = status.phase.value if hasattr(status.phase, "value") else str(status.phase)

    return RunArtifact(
        run_id=status.run_id,
        session_name=status.session_name,
        started_at=status.started_at,
        completed_at=completed_at,
        status=status_str,
        config=config or {},
        tasks_completed=status.budget.tasks_completed,
        tasks_failed=0,  # TODO: Track failed tasks separately if needed
        budget=status.budget,
    )


def display_summary(status: RunStatus) -> None:
    """Display run summary at the end."""
    table = Table(title="Run Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Duration", f"{status.duration_seconds:.1f}s")
    table.add_row("Iterations", str(status.iteration.current))
    table.add_row("Tasks Completed", str(status.budget.tasks_completed))
    table.add_row("Tokens Used", f"{status.budget.tokens_used:,}")
    if status.budget.cost_usd:
        table.add_row("Cost", f"${status.budget.cost_usd:.4f}")
    table.add_row("Final Phase", status.phase.value)

    console.print(table)


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    harness: str | None = typer.Option(
        None,
        "--harness",
        "-h",
        help="AI harness to use (claude, claude-sdk, claude-cli, codex, gemini, opencode). 'claude' defaults to 'claude-sdk' (SDK with hooks). Use 'claude-cli' for shell-out.",
    ),
    once: bool = typer.Option(
        False,
        "--once",
        "-1",
        help="Run a single iteration then exit",
    ),
    task_id: str | None = typer.Option(
        None,
        "--task",
        "-t",
        help="Run specific task by ID",
    ),
    budget: float | None = typer.Option(
        None,
        "--budget",
        "-b",
        help="Maximum budget in USD",
    ),
    budget_tokens: int | None = typer.Option(
        None,
        "--budget-tokens",
        help="Maximum token budget",
    ),
    epic: str | None = typer.Option(
        None,
        "--epic",
        "-e",
        help="Only work on tasks in this epic",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Only work on tasks with this label",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (e.g., sonnet, opus, haiku)",
    ),
    session_name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Session name for tracking",
    ),
    ready: bool = typer.Option(
        False,
        "--ready",
        "-r",
        help="List ready tasks without running",
    ),
    stream: bool = typer.Option(
        False,
        "--stream",
        "-s",
        help="Stream harness output in real-time",
    ),
    monitor: bool = typer.Option(
        False,
        "--monitor",
        help="Launch with live dashboard in tmux split pane",
    ),
    worktree: bool = typer.Option(
        False,
        "--worktree",
        help="Run in isolated git worktree",
    ),
    worktree_keep: bool = typer.Option(
        False,
        "--worktree-keep",
        help="Keep worktree after run completes (only with --worktree)",
    ),
    parallel: int | None = typer.Option(
        None,
        "--parallel",
        "-p",
        help="Run N tasks in parallel, each in its own worktree",
        min=1,
        max=10,
    ),
    sandbox: bool = typer.Option(
        False,
        "--sandbox",
        help="Run in Docker sandbox for isolation",
    ),
    sandbox_keep: bool = typer.Option(
        False,
        "--sandbox-keep",
        help="Keep sandbox container after run completes (only with --sandbox)",
    ),
    no_network: bool = typer.Option(
        False,
        "--no-network",
        help="Disable network access (requires --sandbox)",
    ),
    direct: str | None = typer.Option(
        None,
        "--direct",
        "-d",
        help="Run directly with provided task (string, @file, or - for stdin)",
    ),
    gh_issue: int | None = typer.Option(
        None,
        "--gh-issue",
        help="Work on a specific GitHub issue by number",
    ),
    main_ok: bool = typer.Option(
        False,
        "--main-ok",
        help="Allow running on main/master branch (normally blocked)",
    ),
    use_current_branch: bool = typer.Option(
        False,
        "--use-current-branch",
        help="Run in the current branch instead of creating a new one",
    ),
    from_branch: str | None = typer.Option(
        None,
        "--from-branch",
        help="Base branch for new feature branch (default: origin/main). "
        "Ignored with --use-current-branch.",
    ),
) -> None:
    """
    Execute autonomous task loop.

    Runs the main cub loop, picking up tasks and executing them with the
    specified AI harness until stopped or budget is exhausted.

    Branch Protection:
        By default, cub run will not execute on main/master branch. When
        --label, --epic, or --gh-issue is specified, a feature branch is
        automatically created. Use --main-ok to explicitly allow main.

    Examples:
        cub run                      # Creates new branch from origin/main
        cub run --use-current-branch # Run in current branch
        cub run --harness claude     # Run with Claude
        cub run --once               # Run one iteration
        cub run --task cub-123       # Run specific task
        cub run --budget 5.0         # Set budget to $5
        cub run --epic backend-v2    # Work on epic
        cub run --label priority     # Work on labeled tasks
        cub run --gh-issue 123       # Work on GitHub issue
        cub run --from-branch develop  # Create branch from develop
        cub run --ready              # List ready tasks
        cub run --worktree           # Run in isolated worktree
        cub run --parallel 3         # Run 3 tasks in parallel
        cub run --sandbox            # Run in Docker sandbox
        cub run --direct "task"      # Direct task
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Validate flags
    if no_network and not sandbox:
        console.print("[red]--no-network requires --sandbox[/red]")
        raise typer.Exit(1)

    if sandbox_keep and not sandbox:
        console.print("[red]--sandbox-keep requires --sandbox[/red]")
        raise typer.Exit(1)

    if direct:
        # --direct is incompatible with task management flags
        if task_id:
            console.print("[red]--direct cannot be used with --task[/red]")
            raise typer.Exit(1)
        if epic:
            console.print("[red]--direct cannot be used with --epic[/red]")
            raise typer.Exit(1)
        if label:
            console.print("[red]--direct cannot be used with --label[/red]")
            raise typer.Exit(1)
        if ready:
            console.print("[red]--direct cannot be used with --ready[/red]")
            raise typer.Exit(1)
        if parallel:
            console.print("[red]--direct cannot be used with --parallel[/red]")
            raise typer.Exit(1)

    if gh_issue is not None:
        # --gh-issue is incompatible with task management flags
        if task_id:
            console.print("[red]--gh-issue cannot be used with --task[/red]")
            raise typer.Exit(1)
        if epic:
            console.print("[red]--gh-issue cannot be used with --epic[/red]")
            raise typer.Exit(1)
        if label:
            console.print("[red]--gh-issue cannot be used with --label[/red]")
            raise typer.Exit(1)
        if ready:
            console.print("[red]--gh-issue cannot be used with --ready[/red]")
            raise typer.Exit(1)
        if parallel:
            console.print("[red]--gh-issue cannot be used with --parallel[/red]")
            raise typer.Exit(1)
        if direct:
            console.print("[red]--gh-issue cannot be used with --direct[/red]")
            raise typer.Exit(1)

    # ==========================================================================
    # Branch protection and auto-branch creation
    # ==========================================================================

    from cub.core.branches.store import BranchStore

    current_branch = BranchStore.get_current_branch()
    # Use origin/main as default to avoid issues with stale local main
    base_branch = from_branch if from_branch else "origin/main"

    # Determine branch behavior based on --use-current-branch flag
    if use_current_branch:
        # --use-current-branch: work in current branch (explicit opt-in)
        # Still protect main/master unless --main-ok is set
        if current_branch in ("main", "master") and not main_ok:
            console.print(
                f"[red]Cannot run on '{current_branch}' branch without --main-ok[/red]"
            )
            console.print(
                "[dim]Remove --use-current-branch to auto-create a feature branch,[/dim]"
            )
            console.print("[dim]or add --main-ok to explicitly allow running on main.[/dim]")
            raise typer.Exit(1)
        elif current_branch in ("main", "master"):
            # --main-ok was set, warn but continue
            console.print(
                f"[yellow]Warning: Running on '{current_branch}' branch "
                "(--use-current-branch --main-ok)[/yellow]"
            )
        # else: on a feature branch with --use-current-branch, proceed normally
    else:
        # Default behavior: create a new branch from origin/main (or --from-branch)
        # Generate branch name based on context
        auto_branch_name: str | None = None

        if label:
            # --label foo → feature/foo
            auto_branch_name = f"feature/{_slugify(label)}"
        elif epic:
            # --epic cub-xyz → feature/[epic-slug]
            epic_title = _get_epic_title(epic)
            if epic_title:
                auto_branch_name = f"feature/{_slugify(epic_title)}"
            else:
                # Fallback to epic ID
                auto_branch_name = f"feature/{_slugify(epic)}"
        elif gh_issue is not None:
            # --gh-issue 47 → fix/[issue-slug]
            issue_title = _get_gh_issue_title(gh_issue)
            if issue_title:
                auto_branch_name = f"fix/{_slugify(issue_title)}"
            else:
                # Fallback to issue number
                auto_branch_name = f"fix/issue-{gh_issue}"
        elif task_id:
            # --task cub-123 → task/cub-123
            auto_branch_name = f"task/{_slugify(task_id)}"
        else:
            # No specific context - generate timestamp-based branch
            auto_branch_name = f"cub/run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Check if we're already on a feature branch (not main/master)
        if current_branch not in ("main", "master", None):
            # Already on a feature branch - check if we should create a new one anyway
            # For now, reuse existing feature branch to avoid branch sprawl
            if debug:
                console.print(
                    f"[dim]Already on feature branch '{current_branch}', continuing...[/dim]"
                )
        else:
            # On main/master or detached HEAD - create and switch to new branch
            console.print(
                f"[cyan]Creating branch '{auto_branch_name}' from '{base_branch}'[/cyan]"
            )
            if not _create_branch_from_base(auto_branch_name, base_branch, console):
                raise typer.Exit(1)

            # Bind branch to epic if --epic was specified
            if epic:
                try:
                    backend = get_task_backend(project_dir=project_dir)
                    if backend.bind_branch(epic, auto_branch_name, base_branch):
                        console.print(
                            f"[green]Bound branch '{auto_branch_name}' to epic '{epic}'[/green]"
                        )
                except Exception:
                    # Non-fatal: binding failed but branch was created
                    pass

            # Update current_branch for any subsequent checks
            current_branch = auto_branch_name

    # Handle --sandbox flag: run in Docker container
    if sandbox:
        # Check if Docker is available
        if not is_provider_available("docker"):
            console.print(
                "[red]Docker is not available. "
                "Please install Docker and ensure the daemon is running.[/red]"
            )
            console.print("[dim]Install: https://docs.docker.com/get-docker/[/dim]")
            raise typer.Exit(1)

        # Delegate to sandbox execution
        exit_code = _run_in_sandbox(
            project_dir=project_dir,
            harness=harness,
            once=once,
            task_id=task_id,
            budget=budget,
            budget_tokens=budget_tokens,
            epic=epic,
            label=label,
            model=model,
            session_name=session_name,
            stream=stream,
            no_network=no_network,
            sandbox_keep=sandbox_keep,
            debug=debug,
        )
        raise typer.Exit(exit_code)

    # Load configuration
    config = load_config(project_dir)

    # Initialize session manager
    session_manager = RunSessionManager(project_dir / ".cub")

    # Detect orphaned sessions from previous runs
    orphaned_sessions = session_manager.detect_orphans()
    if orphaned_sessions and debug:
        console.print(f"[dim]Detected {len(orphaned_sessions)} orphaned session(s)[/dim]")
        for orphan in orphaned_sessions:
            console.print(f"[dim]  - {orphan.run_id}: {orphan.orphaned_reason}[/dim]")

    # Handle --worktree flag: create and enter worktree
    worktree_path: Path | None = None
    original_cwd: Path | None = None

    if worktree:
        try:
            # Generate worktree name based on task or session
            if task_id:
                worktree_name = task_id
            else:
                worktree_name = f"cub-run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            manager = WorktreeManager(project_dir)

            # Create worktree (or get existing one)
            worktree_obj = manager.create(worktree_name, create_branch=False)
            worktree_path = worktree_obj.path

            console.print(f"[cyan]Created worktree: {worktree_path}[/cyan]")

            # Change to worktree directory
            original_cwd = Path.cwd()
            os.chdir(worktree_path)
            project_dir = worktree_path

            if debug:
                console.print(f"[dim]Working directory: {project_dir}[/dim]")

        except WorktreeError as e:
            console.print(f"[red]Failed to create worktree: {e}[/red]")
            raise typer.Exit(1)

    # Handle --monitor flag: launch tmux session with dashboard
    if monitor:
        # Generate session name (same logic as below)
        run_id = session_name or f"cub-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Get dashboard pane size from config
        pane_size = get_dashboard_pane_size(
            getattr(getattr(config, "dashboard", None), "pane_size", None)
        )

        # Reconstruct all CLI arguments (except --monitor)
        run_args = []
        if harness:
            run_args.extend(["--harness", harness])
        if once:
            run_args.append("--once")
        if task_id:
            run_args.extend(["--task", task_id])
        if budget:
            run_args.extend(["--budget", str(budget)])
        if budget_tokens:
            run_args.extend(["--budget-tokens", str(budget_tokens)])
        if epic:
            run_args.extend(["--epic", epic])
        if label:
            run_args.extend(["--label", label])
        if model:
            run_args.extend(["--model", model])
        if session_name:
            run_args.extend(["--name", session_name])
        if ready:
            run_args.append("--ready")
        if stream:
            run_args.append("--stream")
        if worktree:
            run_args.append("--worktree")
        if worktree_keep:
            run_args.append("--worktree-keep")
        if parallel:
            run_args.extend(["--parallel", str(parallel)])
        if sandbox:
            run_args.append("--sandbox")
        if sandbox_keep:
            run_args.append("--sandbox-keep")
        if no_network:
            run_args.append("--no-network")
        if debug:
            run_args.append("--debug")

        # Launch tmux session (this function does not return)
        launch_with_dashboard(
            run_args=run_args,
            session_name=run_id,
            pane_size=pane_size,
        )

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Project: {project_dir}[/dim]")

    # Handle --direct flag: run without task backend
    if direct:
        exit_code = _run_direct(
            direct=direct,
            project_dir=project_dir,
            config=config,
            harness=harness,
            model=model,
            stream=stream,
            budget=budget,
            budget_tokens=budget_tokens,
            session_name=session_name,
            debug=debug,
        )
        raise typer.Exit(exit_code)

    # Handle --gh-issue flag: run on a specific GitHub issue
    if gh_issue is not None:
        exit_code = _run_gh_issue(
            issue_number=gh_issue,
            project_dir=project_dir,
            config=config,
            harness=harness,
            model=model,
            stream=stream,
            budget=budget,
            budget_tokens=budget_tokens,
            session_name=session_name,
            debug=debug,
        )
        raise typer.Exit(exit_code)

    # Get task backend
    try:
        task_backend = get_task_backend(project_dir=project_dir)
        backend_name = task_backend.backend_name
    except Exception as e:
        console.print(f"[red]Failed to initialize task backend: {e}[/red]")
        raise typer.Exit(1)

    if debug:
        console.print(f"[dim]Task backend: {backend_name}[/dim]")

    # Handle --ready flag: just list ready tasks
    if ready:
        _show_ready_tasks(task_backend, epic, label)
        raise typer.Exit(0)

    # Handle --parallel flag: execute tasks in parallel
    if parallel is not None and parallel > 1:
        _run_parallel(
            task_backend=task_backend,
            backend_name=backend_name,
            project_dir=project_dir,
            parallel=parallel,
            harness=harness,
            model=model,
            epic=epic,
            label=label,
            debug=debug,
            stream=stream,
        )
        # _run_parallel handles its own exit
        raise typer.Exit(0)

    # Setup harness
    harness_result = _setup_harness(harness, config.harness.priority, debug)
    if harness_result is None:
        raise typer.Exit(1)
    harness_name, harness_backend = harness_result

    # Set up signal handler for graceful interrupts
    signal.signal(signal.SIGINT, _signal_handler)

    # Initialize run status
    run_id = session_name or f"cub-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    max_iterations = 1 if once else config.loop.max_iterations

    status = RunStatus(
        run_id=run_id,
        session_name=session_name or run_id,
        phase=RunPhase.INITIALIZING,
        epic=epic,
        label=label,
        branch=current_branch,
        iteration=IterationInfo(
            current=0,
            max=max_iterations,
            max_task_iteration=config.guardrails.max_task_iterations,
        ),
        budget=BudgetStatus(
            tokens_limit=budget_tokens or config.budget.max_tokens_per_task,
            cost_limit=budget or config.budget.max_total_cost,
            tasks_limit=config.budget.max_tasks_per_session,
        ),
    )

    # Initialize status writer
    status_writer = StatusWriter(project_dir, run_id)
    status_writer.write(status)

    if debug:
        console.print(f"[dim]Status file: {status_writer.status_path}[/dim]")

    # Initialize ledger writer
    ledger_dir = project_dir / ".cub" / "ledger"
    ledger_writer = LedgerWriter(ledger_dir)

    # Initialize ledger integration
    ledger_integration = LedgerIntegration(ledger_writer)

    # Update task counts
    counts = task_backend.get_task_counts()
    status.tasks_total = counts.total
    status.tasks_open = counts.open
    status.tasks_in_progress = counts.in_progress
    status.tasks_closed = counts.closed

    # Initialize task entries for Kanban display
    initial_tasks = task_backend.get_ready_tasks(parent=epic, label=label)
    status.set_task_entries([(t.id, t.title) for t in initial_tasks])

    console.print(f"[bold]Starting cub run: {run_id}[/bold]")
    console.print(
        f"Tasks: {counts.open} open, {counts.in_progress} in progress, {counts.closed} closed"
    )
    console.print(f"Max iterations: {max_iterations}")
    console.print()

    # Generate system prompt
    system_prompt = generate_system_prompt(project_dir)

    # Start run session tracking
    session_budget = SessionBudget(
        tokens_limit=status.budget.tokens_limit or 0,
        cost_limit=status.budget.cost_limit or 0.0,
    )
    run_session = session_manager.start_session(
        harness=harness_name,
        budget=session_budget,
        project_dir=project_dir,
    )
    if debug:
        console.print(f"[dim]Run session: {run_session.run_id}[/dim]")

    # Main loop
    status.phase = RunPhase.RUNNING
    status.add_event("Run started", EventLevel.INFO)
    status_writer.write(status)

    # Transition specs from staged/ to implementing/ at run start
    moved_specs = _transition_staged_specs_to_implementing(project_dir, debug)
    if moved_specs:
        console.print(f"[cyan]Moved {len(moved_specs)} spec(s) to implementing/[/cyan]")
        for spec_path in moved_specs:
            status.add_event(
                f"Spec moved to implementing: {spec_path.name}",
                EventLevel.INFO,
            )
        status_writer.write(status)

    # Run pre-loop hooks (sync - must complete before loop starts)
    pre_loop_context = HookContext(
        hook_name="pre-loop",
        project_dir=project_dir,
        harness=harness_name,
        session_id=run_id,
    )
    if not run_hooks("pre-loop", pre_loop_context, project_dir):
        if config.hooks.fail_fast:
            status.mark_failed("Pre-loop hook failed")
            console.print("[red]Pre-loop hook failed. Stopping.[/red]")
            raise typer.Exit(1)

    global _interrupted
    budget_warning_fired = False  # Track if budget warning hook has been fired

    try:
        while status.iteration.current < max_iterations:
            # Check for interrupt
            if _interrupted:
                console.print("[yellow]Stopping due to interrupt...[/yellow]")
                status.mark_stopped()
                break

            # Check budget
            if status.budget.is_over_budget:
                console.print("[yellow]Budget exhausted. Stopping.[/yellow]")
                status.add_event("Budget exhausted", EventLevel.WARNING)
                status.mark_completed()
                break

            # Increment iteration
            status.iteration.current += 1

            if debug:
                iter_info = f"{status.iteration.current}/{max_iterations}"
                console.print(f"[dim]=== Iteration {iter_info} ===[/dim]")

            # Get task to work on
            current_task: Task | None = None

            if task_id:
                # Specific task requested
                current_task = task_backend.get_task(task_id)
                if not current_task:
                    console.print(f"[red]Task {task_id} not found[/red]")
                    status.mark_failed(f"Task {task_id} not found")
                    break
                if current_task.status == TaskStatus.CLOSED:
                    console.print(f"[yellow]Task {task_id} is already closed[/yellow]")
                    status.mark_completed()
                    break
            else:
                # Get next ready task
                ready_tasks = task_backend.get_ready_tasks(parent=epic, label=label)

                if not ready_tasks:
                    # Check if all done or blocked
                    counts = task_backend.get_task_counts()
                    if counts.remaining == 0:
                        console.print("[green]All tasks complete![/green]")
                        # Fire on-all-tasks-complete hook (async)
                        complete_context = HookContext(
                            hook_name="on-all-tasks-complete",
                            project_dir=project_dir,
                            harness=harness_name,
                            session_id=run_id,
                        )
                        run_hooks_async("on-all-tasks-complete", complete_context, project_dir)
                        status.mark_completed()
                        break
                    else:
                        console.print(
                            f"[yellow]No ready tasks, but {counts.remaining} tasks "
                            "remaining. Check dependencies.[/yellow]"
                        )
                        status.mark_completed()
                        break

                current_task = ready_tasks[0]

            # Display task info
            display_task_info(current_task, status.iteration.current, max_iterations)

            # Update status
            status.current_task_id = current_task.id
            status.current_task_title = current_task.title
            status.start_task_entry(current_task.id)  # Mark task as DOING in Kanban
            status.add_event(
                f"Starting task: {current_task.title}", EventLevel.INFO, task_id=current_task.id
            )
            status_writer.write(status)

            # Run pre-task hooks (sync - must complete before task runs)
            pre_task_context = HookContext(
                hook_name="pre-task",
                project_dir=project_dir,
                task_id=current_task.id,
                task_title=current_task.title,
                harness=harness_name,
                session_id=run_id,
            )
            if not run_hooks("pre-task", pre_task_context, project_dir):
                if config.hooks.fail_fast:
                    status.mark_failed(f"Pre-task hook failed for {current_task.id}")
                    console.print("[red]Pre-task hook failed. Stopping.[/red]")
                    break

            # Claim task (mark as in_progress)
            try:
                task_backend.update_task(
                    current_task.id, status=TaskStatus.IN_PROGRESS, assignee=run_id
                )
            except Exception as e:
                if debug:
                    console.print(f"[dim]Failed to claim task: {e}[/dim]")

            # Create ledger entry for task start
            if config.ledger.enabled:
                try:
                    ledger_integration.on_task_start(
                        current_task,
                        run_id=run_id,
                        epic_id=epic,
                    )
                    if debug:
                        console.print(
                            f"[dim]Created ledger entry for task start: {current_task.id}[/dim]"
                        )
                except Exception as e:
                    if debug:
                        console.print(f"[dim]Warning: Failed to create ledger entry: {e}[/dim]")

            # Generate task prompt
            task_prompt = generate_task_prompt(current_task, task_backend)

            if debug:
                console.print(f"[dim]System prompt: {len(system_prompt)} chars[/dim]")
                console.print(f"[dim]Task prompt: {len(task_prompt)} chars[/dim]")

            # Get model from task label or CLI arg or config
            task_model = model or current_task.model_label or config.harness.model

            # Invoke harness
            console.print(f"[bold]Running {harness_name}...[/bold]")

            # Track attempt start time
            attempt_start_time = datetime.now()

            try:
                task_input = TaskInput(
                    prompt=task_prompt,
                    system_prompt=system_prompt,
                    model=task_model,
                    working_dir=str(project_dir),
                    auto_approve=True,  # Auto-approve for unattended execution
                )

                # Write prompt before harness invocation (audit trail, even if harness fails)
                try:
                    status_writer.write_prompt(current_task.id, system_prompt, task_prompt)
                except Exception as e:
                    if debug:
                        console.print(f"[dim]Warning: Failed to write prompt.md: {e}[/dim]")

                # Record attempt start in ledger
                if config.ledger.enabled:
                    try:
                        # Get attempt number (1-based)
                        attempt_number = ledger_integration.get_attempt_count(current_task.id) + 1

                        # Build combined prompt for ledger
                        combined_prompt = (
                            f"# System Prompt\n\n{system_prompt}\n\n"
                            f"# Task Prompt\n\n{task_prompt}"
                        )

                        ledger_integration.on_attempt_start(
                            current_task.id,
                            attempt_number,
                            combined_prompt,
                            run_id=run_id,
                            harness=harness_name,
                            model=task_model or "",
                        )
                        if debug:
                            console.print(
                                f"[dim]Recorded attempt {attempt_number} start in ledger[/dim]"
                            )
                    except Exception as e:
                        if debug:
                            console.print(
                                f"[dim]Warning: Failed to record attempt start: {e}[/dim]"
                            )

                # Get harness log path for this task
                harness_log_path = status_writer.get_harness_log_path(current_task.id)

                result = _invoke_harness(
                    harness_backend, task_input, stream, debug, harness_log_path
                )

                # Record attempt end in ledger
                if config.ledger.enabled:
                    try:
                        # Read harness log content
                        log_content = ""
                        if harness_log_path and harness_log_path.exists():
                            log_content = harness_log_path.read_text(encoding="utf-8")

                        # Convert TokenUsage to LedgerTokenUsage
                        from cub.core.ledger.models import TokenUsage as LedgerTokenUsage
                        ledger_tokens = LedgerTokenUsage(
                            input_tokens=result.usage.input_tokens,
                            output_tokens=result.usage.output_tokens,
                            cache_read_tokens=result.usage.cache_read_tokens,
                            cache_creation_tokens=result.usage.cache_creation_tokens,
                        )

                        ledger_integration.on_attempt_end(
                            current_task.id,
                            attempt_number,
                            log_content,
                            run_id=run_id,
                            success=result.success,
                            harness=harness_name,
                            model=task_model or "",
                            tokens=ledger_tokens,
                            cost_usd=result.usage.cost_usd or 0.0,
                            duration_seconds=int(result.duration_seconds),
                            started_at=attempt_start_time,
                        )
                        if debug:
                            console.print(
                                f"[dim]Recorded attempt {attempt_number} end in ledger[/dim]"
                            )
                    except Exception as e:
                        if debug:
                            console.print(
                                f"[dim]Warning: Failed to record attempt end: {e}[/dim]"
                            )

            except Exception as e:
                console.print(f"[red]Harness invocation failed: {e}[/red]")
                status.add_event(f"Harness failed: {e}", EventLevel.ERROR, task_id=current_task.id)

                # Record failed attempt in ledger
                if config.ledger.enabled:
                    try:
                        attempt_number = ledger_integration.get_attempt_count(current_task.id) + 1
                        ledger_integration.on_attempt_end(
                            current_task.id,
                            attempt_number,
                            log_content="",
                            run_id=run_id,
                            success=False,
                            harness=harness_name,
                            model=task_model or "",
                            error_category="harness_failure",
                            error_summary=str(e),
                            started_at=attempt_start_time,
                        )
                    except Exception as ledger_error:
                        if debug:
                            console.print(
                                f"[dim]Warning: Failed to record failed attempt: "
                                f"{ledger_error}[/dim]"
                            )

                if config.loop.on_task_failure == "stop":
                    status.mark_failed(str(e))
                    break
                continue

            duration = result.duration_seconds

            # Update budget tracking
            status.budget.tokens_used += result.usage.total_tokens
            if result.usage.cost_usd:
                status.budget.cost_usd += result.usage.cost_usd

            # Check for budget warning (fire once when crossing threshold)
            budget_pct = status.budget.tokens_percentage or status.budget.cost_percentage
            warning_threshold = config.guardrails.iteration_warning_threshold * 100
            if budget_pct and budget_pct >= warning_threshold and not budget_warning_fired:
                budget_warning_fired = True
                console.print(
                    f"[yellow]Budget warning: {budget_pct:.1f}% used "
                    f"(threshold: {warning_threshold:.0f}%)[/yellow]"
                )
                status.add_event(f"Budget warning: {budget_pct:.1f}% used", EventLevel.WARNING)
                # Fire on-budget-warning hook (async)
                budget_context = HookContext(
                    hook_name="on-budget-warning",
                    project_dir=project_dir,
                    harness=harness_name,
                    session_id=run_id,
                    budget_percentage=budget_pct,
                    budget_used=status.budget.tokens_used,
                    budget_limit=status.budget.tokens_limit,
                )
                run_hooks_async("on-budget-warning", budget_context, project_dir)

            # Log result
            if result.success:
                console.print(f"[green]Task completed in {duration:.1f}s[/green]")
                console.print(f"[dim]Tokens: {result.usage.total_tokens:,}[/dim]")
                status.budget.tasks_completed += 1
                status.complete_task_entry(current_task.id)  # Mark task as DONE in Kanban
                status.add_event(
                    f"Task completed: {current_task.title}",
                    EventLevel.INFO,
                    task_id=current_task.id,
                    duration=duration,
                    tokens=result.usage.total_tokens,
                )

                # Persist task artifact with token usage
                priority_str = (
                    current_task.priority.value
                    if hasattr(current_task.priority, "value")
                    else str(current_task.priority)
                )
                task_artifact = TaskArtifact(
                    task_id=current_task.id,
                    title=current_task.title,
                    priority=priority_str,
                    status="completed",
                    started_at=datetime.now(),  # TODO: Track actual start time
                    completed_at=datetime.now(),
                    iterations=1,  # TODO: Track actual iterations if task retries
                    exit_code=result.exit_code,
                    usage=result.usage,
                    duration_seconds=duration,
                )
                try:
                    status_writer.write_task_artifact(current_task.id, task_artifact)
                    if debug:
                        console.print("[dim]Persisted task artifact to task.json[/dim]")
                except Exception as e:
                    if debug:
                        console.print(f"[dim]Warning: Failed to write task artifact: {e}[/dim]")

                # Close the task in the backend so it won't be picked up again
                try:
                    task_backend.close_task(
                        current_task.id,
                        reason="Completed by autonomous execution",
                    )
                    if debug:
                        console.print(
                            f"[dim]Closed task {current_task.id} in backend[/dim]"
                        )
                except Exception as e:
                    # Log but don't fail - the work is done even if closure fails
                    console.print(
                        f"[yellow]Warning: Failed to close task in backend: {e}[/yellow]"
                    )
                    status.add_event(
                        f"Failed to close task in backend: {e}",
                        EventLevel.WARNING,
                        task_id=current_task.id,
                    )

                # Finalize ledger entry after successful task completion
                if config.ledger.enabled:
                    try:
                        # Get current task state for drift detection
                        current_task_state = task_backend.get_task(current_task.id)

                        ledger_integration.on_task_close(
                            current_task.id,
                            success=True,
                            partial=False,
                            final_model=task_model or "",
                            current_task=current_task_state,
                        )
                        if debug:
                            console.print(
                                f"[dim]Finalized ledger entry for {current_task.id}[/dim]"
                            )
                    except Exception as e:
                        # Log but don't fail - ledger is informational
                        if debug:
                            console.print(
                                f"[dim]Warning: Failed to finalize ledger entry: {e}[/dim]"
                            )
                        status.add_event(
                            f"Failed to finalize ledger entry: {e}",
                            EventLevel.WARNING,
                            task_id=current_task.id,
                        )

                # Run post-task hooks (async - fire and forget for notifications)
                post_task_context = HookContext(
                    hook_name="post-task",
                    project_dir=project_dir,
                    task_id=current_task.id,
                    task_title=current_task.title,
                    exit_code=0,
                    harness=harness_name,
                    session_id=run_id,
                )
                run_hooks_async("post-task", post_task_context, project_dir)
            else:
                console.print(f"[red]Task failed: {result.error or 'Unknown error'}[/red]")
                status.add_event(
                    f"Task failed: {result.error}",
                    EventLevel.ERROR,
                    task_id=current_task.id,
                    exit_code=result.exit_code,
                )

                # Persist task artifact with token usage even on failure
                priority_str = (
                    current_task.priority.value
                    if hasattr(current_task.priority, "value")
                    else str(current_task.priority)
                )
                task_artifact = TaskArtifact(
                    task_id=current_task.id,
                    title=current_task.title,
                    priority=priority_str,
                    status="failed",
                    started_at=datetime.now(),  # TODO: Track actual start time
                    completed_at=datetime.now(),
                    iterations=1,  # TODO: Track actual iterations if task retries
                    exit_code=result.exit_code,
                    usage=result.usage,
                    duration_seconds=duration,
                )
                try:
                    status_writer.write_task_artifact(current_task.id, task_artifact)
                    if debug:
                        console.print("[dim]Persisted task artifact to task.json[/dim]")
                except Exception as e:
                    if debug:
                        console.print(f"[dim]Warning: Failed to write task artifact: {e}[/dim]")

                # Finalize ledger entry after failed task
                if config.ledger.enabled:
                    try:
                        current_task_state = task_backend.get_task(current_task.id)
                        ledger_integration.on_task_close(
                            current_task.id,
                            success=False,
                            partial=True,
                            final_model=task_model or "",
                            current_task=current_task_state,
                        )
                        if debug:
                            console.print(
                                f"[dim]Finalized ledger entry for failed task "
                                f"{current_task.id}[/dim]"
                            )
                    except Exception as e:
                        if debug:
                            console.print(
                                f"[dim]Warning: Failed to finalize ledger entry: {e}[/dim]"
                            )

                # Run on-error hooks (async - fire and forget for error notifications)
                on_error_context = HookContext(
                    hook_name="on-error",
                    project_dir=project_dir,
                    task_id=current_task.id,
                    task_title=current_task.title,
                    exit_code=result.exit_code or 1,
                    harness=harness_name,
                    session_id=run_id,
                )
                run_hooks_async("on-error", on_error_context, project_dir)

                if config.loop.on_task_failure == "stop":
                    status.mark_failed(result.error or "Task execution failed")
                    break

            # Clear current task
            status.current_task_id = None
            status.current_task_title = None

            # Update task counts
            counts = task_backend.get_task_counts()
            status.tasks_open = counts.open
            status.tasks_in_progress = counts.in_progress
            status.tasks_closed = counts.closed

            # Write status
            status_writer.write(status)

            # Update run session with progress
            try:
                session_budget = SessionBudget(
                    tokens_used=status.budget.tokens_used,
                    tokens_limit=status.budget.tokens_limit or 0,
                    cost_usd=status.budget.cost_usd,
                    cost_limit=status.budget.cost_limit or 0.0,
                )
                session_manager.update_session(
                    run_session.run_id,
                    tasks_completed=status.budget.tasks_completed,
                    tasks_failed=status.tasks_closed - status.budget.tasks_completed,
                    current_task=None,  # Task just finished
                    budget=session_budget,
                )
            except Exception as e:
                if debug:
                    console.print(f"[dim]Warning: Failed to update run session: {e}[/dim]")

            # If running specific task, exit after one iteration
            if task_id:
                if result.success:
                    status.mark_completed()
                break

            # Brief pause between iterations
            if not once and status.iteration.current < max_iterations:
                time.sleep(2)

        else:
            # Loop completed all iterations
            console.print(f"[yellow]Reached max iterations ({max_iterations})[/yellow]")
            status.add_event("Reached max iterations", EventLevel.WARNING)
            status.mark_stopped()

    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        status.mark_failed(str(e))
        raise

    finally:
        # Run post-loop hooks (sync - must complete before session ends)
        post_loop_context = HookContext(
            hook_name="post-loop",
            project_dir=project_dir,
            harness=harness_name,
            session_id=run_id,
        )
        run_hooks("post-loop", post_loop_context, project_dir)

        # Wait for all async hooks to complete (post-task, on-error)
        wait_async_hooks()

        # End run session tracking
        try:
            session_manager.end_session(run_session.run_id)
            if debug:
                console.print(f"[dim]Ended run session: {run_session.run_id}[/dim]")
        except Exception as e:
            if debug:
                console.print(f"[dim]Warning: Failed to end run session: {e}[/dim]")

        # Auto-close epic if all tasks are complete
        if epic:
            try:
                closed, message = task_backend.try_close_epic(epic)
                if closed:
                    console.print(f"[green]{message}[/green]")
                    status.add_event(message, EventLevel.INFO)
                elif debug:
                    console.print(f"[dim]{message}[/dim]")
            except Exception as e:
                # Non-fatal: epic closure failed but run completed
                if debug:
                    console.print(f"[dim]Failed to check epic closure: {e}[/dim]")

        # Final status write
        status_writer.write(status)

        # Persist run artifact with budget totals
        config_dict = config.model_dump(mode="json") if isinstance(config, CubConfig) else {}
        run_artifact = create_run_artifact(status, config_dict)
        status_writer.write_run_artifact(run_artifact)

        # Display summary
        console.print()
        display_summary(status)

        if debug:
            console.print(f"[dim]Final status: {status_writer.status_path}[/dim]")
            console.print(f"[dim]Run artifact: {status_writer.run_artifact_path}[/dim]")

        # Clean up working directory (commit artifacts, remove temp files)
        if isinstance(config, CubConfig) and config.cleanup.enabled:
            try:
                cleanup_service = CleanupService(
                    config=config.cleanup,
                    project_dir=project_dir,
                    debug=debug,
                )

                if debug:
                    # Show preview of what will be cleaned
                    preview = cleanup_service.get_cleanup_preview()
                    if any(preview.values()):
                        console.print("\n[dim]Cleanup preview:[/dim]")
                        for category, files in preview.items():
                            if files:
                                console.print(f"[dim]  {category}: {len(files)} file(s)[/dim]")

                cleanup_result = cleanup_service.cleanup()

                # Display cleanup summary
                if cleanup_result.committed_files or cleanup_result.removed_files:
                    console.print(f"\n[cyan]{cleanup_result.summary()}[/cyan]")
                elif debug:
                    console.print(f"\n[dim]{cleanup_result.summary()}[/dim]")

                if cleanup_result.error:
                    console.print(f"[yellow]Cleanup warning: {cleanup_result.error}[/yellow]")

                if not cleanup_result.is_clean and cleanup_result.remaining_files:
                    if debug:
                        console.print("[dim]Remaining uncommitted files:[/dim]")
                        for f in cleanup_result.remaining_files[:10]:
                            console.print(f"[dim]  - {f}[/dim]")
                        if len(cleanup_result.remaining_files) > 10:
                            remaining = len(cleanup_result.remaining_files) - 10
                            console.print(f"[dim]  ... and {remaining} more[/dim]")

            except Exception as e:
                # Non-fatal: cleanup failed but run completed
                console.print(f"[yellow]Cleanup warning: {e}[/yellow]")
                if debug:
                    import traceback

                    console.print(f"[dim]{traceback.format_exc()}[/dim]")

        # Cleanup worktree if requested
        if worktree and worktree_path and not worktree_keep:
            try:
                # Return to original directory before cleanup
                if original_cwd:
                    os.chdir(original_cwd)

                manager = WorktreeManager()
                manager.remove(worktree_path, force=False)
                console.print(f"[cyan]Removed worktree: {worktree_path}[/cyan]")

            except WorktreeError as e:
                console.print(f"[yellow]Failed to cleanup worktree: {e}[/yellow]")
                console.print(f"[dim]Worktree preserved at: {worktree_path}[/dim]")

        elif worktree and worktree_path and worktree_keep:
            console.print(f"[cyan]Worktree preserved at: {worktree_path}[/cyan]")

    # Exit with appropriate code
    if status.phase == RunPhase.FAILED:
        raise typer.Exit(1)
    raise typer.Exit(0)


def _run_direct(
    direct: str,
    project_dir: Path,
    config: object,
    harness: str | None,
    model: str | None,
    stream: bool,
    budget: float | None,
    budget_tokens: int | None,
    session_name: str | None,
    debug: bool,
) -> int:
    """
    Run a direct task without using a task backend.

    Args:
        direct: The --direct argument value (string, @file, or -)
        project_dir: Project directory
        config: Loaded configuration
        harness: AI harness to use
        model: Model to use
        stream: Stream output
        budget: Budget limit (USD)
        budget_tokens: Token budget limit
        session_name: Session name
        debug: Debug mode

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    from cub.core.config.models import CubConfig

    # Type narrow config
    if not isinstance(config, CubConfig):
        console.print("[red]Invalid configuration[/red]")
        return 1

    # Read direct input
    try:
        task_content = _read_direct_input(direct)
    except typer.Exit as e:
        return e.exit_code if e.exit_code is not None else 1

    if not task_content:
        console.print("[red]Empty task content[/red]")
        return 1

    if debug:
        console.print(f"[dim]Direct task: {task_content[:100]}...[/dim]")

    # Setup harness
    harness_result = _setup_harness(harness, config.harness.priority, debug)
    if harness_result is None:
        return 1
    harness_name, harness_backend = harness_result

    # Generate prompts
    system_prompt = generate_system_prompt(project_dir)
    task_prompt = generate_direct_task_prompt(task_content)

    if debug:
        console.print(f"[dim]System prompt: {len(system_prompt)} chars[/dim]")
        console.print(f"[dim]Task prompt: {len(task_prompt)} chars[/dim]")

    # Get model
    task_model = model or config.harness.model

    # Create a session ID for direct mode
    direct_session_id = session_name or f"direct-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Initialize status writer for log capture
    status_writer = StatusWriter(project_dir, direct_session_id)

    # Display task info
    console.print(
        Panel(
            f"[bold]{task_content[:200]}{'...' if len(task_content) > 200 else ''}[/bold]",
            title="[bold]Direct Task[/bold]",
            border_style="blue",
        )
    )

    # Invoke harness
    console.print(f"[bold]Running {harness_name}...[/bold]")

    try:
        task_input = TaskInput(
            prompt=task_prompt,
            system_prompt=system_prompt,
            model=task_model,
            working_dir=str(project_dir),
            auto_approve=True,
        )

        # Write prompt before harness invocation (audit trail, even if harness fails)
        try:
            status_writer.write_prompt("direct", system_prompt, task_prompt)
        except Exception as e:
            if debug:
                console.print(f"[dim]Warning: Failed to write prompt.md: {e}[/dim]")

        # Get harness log path for direct mode (use "direct" as task_id)
        harness_log_path = status_writer.get_harness_log_path("direct")

        result = _invoke_harness(harness_backend, task_input, stream, debug, harness_log_path)
    except Exception as e:
        console.print(f"[red]Harness invocation failed: {e}[/red]")
        return 1

    # Display result
    console.print()
    if result.success:
        console.print(f"[green]Completed in {result.duration_seconds:.1f}s[/green]")
        console.print(f"[dim]Tokens: {result.usage.total_tokens:,}[/dim]")
        if result.usage.cost_usd:
            console.print(f"[dim]Cost: ${result.usage.cost_usd:.4f}[/dim]")
        return 0
    else:
        console.print(f"[red]Failed: {result.error or 'Unknown error'}[/red]")
        return result.exit_code if result.exit_code else 1


def _run_gh_issue(
    issue_number: int,
    project_dir: Path,
    config: object,
    harness: str | None,
    model: str | None,
    stream: bool,
    budget: float | None,
    budget_tokens: int | None,
    session_name: str | None,
    debug: bool,
) -> int:
    """
    Run on a specific GitHub issue.

    Args:
        issue_number: GitHub issue number to work on
        project_dir: Project directory
        config: Loaded configuration
        harness: AI harness to use
        model: Model to use
        stream: Stream output
        budget: Budget limit (USD)
        budget_tokens: Token budget limit
        session_name: Session name
        debug: Debug mode

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    from cub.core.config.models import CubConfig
    from cub.core.github import GitHubClientError, GitHubIssueMode

    # Type narrow config
    if not isinstance(config, CubConfig):
        console.print("[red]Invalid configuration[/red]")
        return 1

    # Initialize GitHub issue mode
    try:
        issue_mode = GitHubIssueMode.from_project_dir(issue_number, project_dir)
    except GitHubClientError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    if debug:
        console.print(f"[dim]Repository: {issue_mode.repo.full_name}[/dim]")
        console.print(f"[dim]Issue: #{issue_mode.issue.number}[/dim]")

    # Setup harness
    harness_result = _setup_harness(harness, config.harness.priority, debug)
    if harness_result is None:
        return 1
    harness_name, harness_backend = harness_result

    # Display issue info
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value")

    table.add_row("Issue", f"[bold]#{issue_mode.issue.number}[/bold]")
    table.add_row("Title", issue_mode.issue.title)
    table.add_row("Repository", issue_mode.repo.full_name)
    table.add_row("Labels", issue_mode.issue.labels_str)
    table.add_row("URL", issue_mode.issue.url)

    console.print(Panel(table, title="[bold]GitHub Issue[/bold]", border_style="blue"))

    # Post start comment
    console.print("[dim]Posting start comment...[/dim]")
    issue_mode.post_start_comment()

    # Generate prompts
    system_prompt = generate_system_prompt(project_dir)
    task_prompt = issue_mode.generate_prompt()

    if debug:
        console.print(f"[dim]System prompt: {len(system_prompt)} chars[/dim]")
        console.print(f"[dim]Task prompt: {len(task_prompt)} chars[/dim]")

    # Get model
    task_model = model or config.harness.model

    # Create a session ID for gh-issue mode
    gh_session_id = session_name or f"gh-{issue_number}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Initialize status writer for log capture
    status_writer = StatusWriter(project_dir, gh_session_id)

    # Invoke harness
    console.print(f"[bold]Running {harness_name}...[/bold]")

    try:
        task_input = TaskInput(
            prompt=task_prompt,
            system_prompt=system_prompt,
            model=task_model,
            working_dir=str(project_dir),
            auto_approve=True,
        )

        # Write prompt before harness invocation (audit trail, even if harness fails)
        issue_task_id = f"issue-{issue_number}"
        try:
            status_writer.write_prompt(issue_task_id, system_prompt, task_prompt)
        except Exception as e:
            if debug:
                console.print(f"[dim]Warning: Failed to write prompt.md: {e}[/dim]")

        # Get harness log path for gh-issue mode (use issue number as task_id)
        harness_log_path = status_writer.get_harness_log_path(issue_task_id)

        result = _invoke_harness(harness_backend, task_input, stream, debug, harness_log_path)
    except Exception as e:
        console.print(f"[red]Harness invocation failed: {e}[/red]")
        return 1

    # Display result
    console.print()
    if result.success:
        console.print(f"[green]Completed in {result.duration_seconds:.1f}s[/green]")
        console.print(f"[dim]Tokens: {result.usage.total_tokens:,}[/dim]")
        if result.usage.cost_usd:
            console.print(f"[dim]Cost: ${result.usage.cost_usd:.4f}[/dim]")

        # Handle issue completion (post comment, maybe close)
        console.print()
        issue_mode.finish()

        if issue_mode.should_close_issue():
            console.print(f"[green]Issue #{issue_number} closed[/green]")
        else:
            branch = issue_mode.client.get_current_branch()
            console.print(
                f"[cyan]Changes on branch '{branch}'. Issue will close when merged to main.[/cyan]"
            )

        return 0
    else:
        console.print(f"[red]Failed: {result.error or 'Unknown error'}[/red]")
        return result.exit_code if result.exit_code else 1


def _show_ready_tasks(
    task_backend: object,
    epic: str | None,
    label: str | None,
) -> None:
    """Display ready tasks in a table."""
    # Type narrowing for mypy
    from cub.core.tasks.backend import TaskBackend

    if not isinstance(task_backend, TaskBackend):
        console.print("[red]Invalid task backend[/red]")
        return

    ready_tasks = task_backend.get_ready_tasks(parent=epic, label=label)

    if not ready_tasks:
        console.print("[yellow]No ready tasks found.[/yellow]")
        counts = task_backend.get_task_counts()
        if counts.remaining > 0:
            console.print(
                f"[dim]{counts.remaining} tasks remaining but blocked by dependencies.[/dim]"
            )
        return

    table = Table(title="Ready Tasks", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Priority", style="yellow")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Labels", style="dim")

    for task in ready_tasks:
        priority = task.priority.value if hasattr(task.priority, "value") else str(task.priority)
        task_type = task.type.value if hasattr(task.type, "value") else str(task.type)
        labels = ", ".join(task.labels[:3]) if task.labels else ""
        if len(task.labels) > 3:
            labels += "..."

        table.add_row(
            task.id,
            priority,
            task_type,
            task.title[:60] + "..." if len(task.title) > 60 else task.title,
            labels,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(ready_tasks)} ready tasks[/dim]")


def _run_parallel(
    task_backend: object,
    backend_name: str,
    project_dir: Path,
    parallel: int,
    harness: str | None,
    model: str | None,
    epic: str | None,
    label: str | None,
    debug: bool,
    stream: bool,
) -> None:
    """
    Execute tasks in parallel using git worktrees.

    Args:
        task_backend: Task backend instance
        backend_name: Name of task backend (for display)
        project_dir: Project directory
        parallel: Number of tasks to run in parallel
        harness: AI harness to use
        model: Model to use
        epic: Filter by epic
        label: Filter by label
        debug: Enable debug output
        stream: Stream output (per-worker)
    """
    from cub.core.tasks.backend import TaskBackend

    # Type check task backend
    if not isinstance(task_backend, TaskBackend):
        console.print("[red]Invalid task backend[/red]")
        raise typer.Exit(1)

    # Create parallel runner
    runner = ParallelRunner(
        project_dir=project_dir,
        harness=harness,
        model=model,
        debug=debug,
        stream=stream,
    )

    # Find independent tasks
    console.print(f"[bold]Finding {parallel} independent tasks...[/bold]")
    tasks = runner.find_independent_tasks(
        task_backend=task_backend,
        count=parallel,
        epic=epic,
        label=label,
    )

    if not tasks:
        console.print("[yellow]No ready tasks found for parallel execution.[/yellow]")
        counts = task_backend.get_task_counts()
        if counts.remaining > 0:
            console.print(
                f"[dim]{counts.remaining} tasks remaining but blocked by dependencies.[/dim]"
            )
        raise typer.Exit(0)

    if len(tasks) < parallel:
        console.print(
            f"[yellow]Found only {len(tasks)} independent tasks (requested {parallel})[/yellow]"
        )

    # Display tasks to be executed
    console.print()
    table = Table(title="Tasks for Parallel Execution", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Priority", style="yellow")
    table.add_column("Title")

    for task in tasks:
        priority = task.priority.value if hasattr(task.priority, "value") else str(task.priority)
        table.add_row(
            task.id,
            priority,
            task.title[:60] + "..." if len(task.title) > 60 else task.title,
        )

    console.print(table)
    console.print()

    # Execute in parallel
    result = runner.run(tasks, max_workers=len(tasks))

    # Display summary
    _display_parallel_summary(result)

    # Exit with failure if any tasks failed
    if result.tasks_failed > 0:
        raise typer.Exit(1)

    raise typer.Exit(0)


def _display_parallel_summary(result: object) -> None:
    """Display summary of parallel execution."""
    from cub.core.worktree.parallel import ParallelRunResult

    if not isinstance(result, ParallelRunResult):
        return

    console.print()
    table = Table(title="Parallel Run Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Duration", f"{result.total_duration:.1f}s")
    table.add_row("Tasks Completed", str(result.tasks_completed))
    table.add_row("Tasks Failed", str(result.tasks_failed))
    table.add_row("Total Tokens", f"{result.total_tokens:,}")
    if result.total_cost > 0:
        table.add_row("Total Cost", f"${result.total_cost:.4f}")

    console.print(table)

    # Show individual task results
    if result.workers:
        console.print()
        worker_table = Table(title="Task Results", show_header=True)
        worker_table.add_column("Task", style="cyan")
        worker_table.add_column("Status")
        worker_table.add_column("Duration")
        worker_table.add_column("Tokens")

        for worker in result.workers:
            status = "[green]✓[/green]" if worker.success else "[red]✗[/red]"
            if not worker.success and worker.error:
                status = f"[red]✗ {worker.error[:30]}...[/red]"

            worker_table.add_row(
                worker.task_id,
                status,
                f"{worker.duration_seconds:.1f}s",
                f"{worker.tokens_used:,}" if worker.tokens_used else "-",
            )

        console.print(worker_table)


def _run_in_sandbox(
    project_dir: Path,
    harness: str | None,
    once: bool,
    task_id: str | None,
    budget: float | None,
    budget_tokens: int | None,
    epic: str | None,
    label: str | None,
    model: str | None,
    session_name: str | None,
    stream: bool,
    no_network: bool,
    sandbox_keep: bool,
    debug: bool,
) -> int:
    """
    Run cub in a Docker sandbox.

    Args:
        project_dir: Project directory to sandbox
        harness: AI harness to use
        once: Run one iteration
        task_id: Specific task to run
        budget: Budget limit (USD)
        budget_tokens: Token budget limit
        epic: Epic filter
        label: Label filter
        model: Model to use
        session_name: Session name
        stream: Stream output
        no_network: Disable network
        sandbox_keep: Keep container after run
        debug: Debug mode

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    console.print("[bold]Starting cub in Docker sandbox...[/bold]")

    # Build cub run arguments
    cub_args = []
    if harness:
        cub_args.extend(["--harness", harness])
    if once:
        cub_args.append("--once")
    if task_id:
        cub_args.extend(["--task", task_id])
    if budget:
        cub_args.extend(["--budget", str(budget)])
    if budget_tokens:
        cub_args.extend(["--budget-tokens", str(budget_tokens)])
    if epic:
        cub_args.extend(["--epic", epic])
    if label:
        cub_args.extend(["--label", label])
    if model:
        cub_args.extend(["--model", model])
    if session_name:
        cub_args.extend(["--name", session_name])
    if stream:
        cub_args.append("--stream")
    if debug:
        cub_args.append("--debug")

    # Create sandbox configuration
    sandbox_config = SandboxConfig(
        network=not no_network,
        cub_args=cub_args,
    )

    # Get Docker provider
    try:
        provider = get_provider("docker")
    except ValueError as e:
        console.print(f"[red]Failed to get Docker provider: {e}[/red]")
        return 1

    if debug:
        console.print(f"[dim]Provider: {provider.name} (v{provider.get_version()})[/dim]")
        console.print(f"[dim]Network: {'enabled' if not no_network else 'disabled'}[/dim]")

    # Start sandbox
    sandbox_id = None
    try:
        console.print("[cyan]Creating sandbox...[/cyan]")
        sandbox_id = provider.start(project_dir, sandbox_config)
        console.print(f"[cyan]Sandbox started: {sandbox_id}[/cyan]")

        # Save sandbox state if keeping
        if sandbox_keep:
            save_sandbox_state(project_dir, sandbox_id, provider.name)
            if debug:
                console.print("[dim]Saved sandbox state to .cub/sandbox.json[/dim]")

        if debug:
            console.print(f"[dim]Container ID: {sandbox_id}[/dim]")

        # Stream logs to terminal
        console.print()
        console.print("[bold]Sandbox Output:[/bold]")
        console.print("─" * 80)

        def log_callback(line: str) -> None:
            """Print log line to console."""
            print(line, end="")

        # Follow logs until container stops
        provider.logs(sandbox_id, follow=True, callback=log_callback)

        console.print("─" * 80)
        console.print()

        # Get final status
        status = provider.status(sandbox_id)

        if debug:
            console.print(f"[dim]Final state: {status.state.value}[/dim]")
            console.print(f"[dim]Exit code: {status.exit_code}[/dim]")

        # Show diff summary
        console.print("[bold]Changes:[/bold]")
        diff_output = provider.diff(sandbox_id)

        if diff_output:
            # Count lines changed
            diff_lines = diff_output.splitlines()
            added = sum(
                1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
            )
            removed = sum(
                1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
            )

            console.print(f"[green]+{added} lines added[/green]")
            console.print(f"[red]-{removed} lines removed[/red]")
            console.print()
            console.print("[dim]Diff:[/dim]")
            console.print(diff_output[:2000])  # Truncate for display
            if len(diff_output) > 2000:
                console.print(f"[dim]... ({len(diff_output) - 2000} more characters)[/dim]")
        else:
            console.print("[dim]No changes detected[/dim]")

        console.print()

        # Determine exit code
        if status.state == SandboxState.FAILED:
            console.print(f"[red]Sandbox failed: {status.error or 'Unknown error'}[/red]")
            exit_code = status.exit_code or 1
        elif status.exit_code == 0:
            console.print("[green]Sandbox completed successfully[/green]")
            exit_code = 0
        else:
            console.print(f"[yellow]Sandbox exited with code {status.exit_code}[/yellow]")
            exit_code = status.exit_code or 1

        return exit_code

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        if sandbox_id:
            console.print("[cyan]Stopping sandbox...[/cyan]")
            try:
                provider.stop(sandbox_id)
            except Exception as e:
                if debug:
                    console.print(f"[dim]Failed to stop sandbox: {e}[/dim]")
        return 130

    except Exception as e:
        console.print(f"[red]Sandbox execution failed: {e}[/red]")
        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return 1

    finally:
        # Cleanup sandbox unless --sandbox-keep
        if sandbox_id and not sandbox_keep:
            try:
                console.print("[cyan]Cleaning up sandbox...[/cyan]")
                provider.cleanup(sandbox_id)
                console.print("[cyan]Sandbox removed[/cyan]")
                # Clear state file
                clear_sandbox_state(project_dir)
            except Exception as e:
                console.print(f"[yellow]Failed to cleanup sandbox: {e}[/yellow]")
                console.print(f"[dim]Sandbox preserved: {sandbox_id}[/dim]")
        elif sandbox_id and sandbox_keep:
            console.print(f"[cyan]Sandbox preserved: {sandbox_id}[/cyan]")


__all__ = ["app"]
