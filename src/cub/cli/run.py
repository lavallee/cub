"""
Cub CLI - Run command.

Execute autonomous task loop with specified harness.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cub.core.harness.async_backend import AsyncHarnessBackend

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cub.cli.errors import (
    ExitCode,
    print_harness_not_found_error,
    print_harness_not_installed_error,
    print_incompatible_flags_error,
    print_main_branch_error,
    print_missing_dependency_error,
)
from cub.core.circuit_breaker import CircuitBreaker
from cub.core.cleanup.service import CleanupService
from cub.core.config.loader import load_config
from cub.core.config.models import CubConfig
from cub.core.harness.async_backend import detect_async_harness, get_async_backend
from cub.core.harness.models import HarnessResult, TaskInput, TokenUsage
from cub.core.ledger.integration import LedgerIntegration
from cub.core.ledger.writer import LedgerWriter
from cub.core.run.git_ops import create_run_branch, get_epic_context, get_issue_context, slugify
from cub.core.run.interrupt import InterruptHandler
from cub.core.run.models import RunEvent, RunEventType

# TODO: Restore when plan module is implemented
# from cub.core.plan.context import PlanContext
# from cub.core.plan.models import PlanStatus
from cub.core.sandbox.models import SandboxConfig, SandboxState
from cub.core.sandbox.provider import get_provider, is_provider_available
from cub.core.sandbox.state import clear_sandbox_state, save_sandbox_state
from cub.core.services.run import RunService
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
from cub.core.sync.service import SyncService
from cub.core.tasks.backend import TaskBackend
from cub.core.tasks.backend import get_backend as get_task_backend
from cub.core.tasks.models import Task
from cub.core.worktree.manager import WorktreeError, WorktreeManager
from cub.core.worktree.parallel import ParallelRunner
from cub.dashboard.tmux import get_dashboard_pane_size, launch_with_dashboard
from cub.utils.hooks import HookContext, run_hooks_async, wait_async_hooks


class RichParallelCallback:
    """Rich Console-based implementation of ParallelRunnerCallback."""

    def __init__(self, console: Console) -> None:
        """
        Initialize callback.

        Args:
            console: Rich console for output
        """
        self.console = console

    def on_start(self, num_tasks: int, num_workers: int) -> None:
        """Display start message."""
        self.console.print(
            f"[bold cyan]Starting parallel execution: {num_tasks} tasks, "
            f"{num_workers} workers[/bold cyan]"
        )

    def on_task_complete(
        self, task_id: str, task_title: str, success: bool, error: str | None = None
    ) -> None:
        """Display task completion status."""
        if success:
            self.console.print(f"[green]✓ {task_id}: {task_title}[/green]")
        else:
            error_msg = error or "Unknown error"
            self.console.print(f"[red]✗ {task_id}: {error_msg}[/red]")

    def on_task_exception(self, task_id: str, exception: str) -> None:
        """Display task exception."""
        self.console.print(f"[red]✗ {task_id}: Exception: {exception}[/red]")

    def on_debug(self, message: str) -> None:
        """Display debug message."""
        self.console.print(f"[dim]{message}[/dim]")


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
        print_harness_not_found_error()
        return None

    try:
        harness_backend: AsyncHarnessBackend = get_async_backend(harness_name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return None

    if not harness_backend.is_available():
        print_harness_not_installed_error(harness_name)
        return None

    if debug:
        console.print(f"[dim]Harness: {harness_name} (v{harness_backend.get_version()})[/dim]")

    return harness_name, harness_backend


async def _invoke_harness_async(
    harness_backend: AsyncHarnessBackend,
    task_input: TaskInput,
    stream: bool,
    debug: bool,
    harness_log_path: Path | None = None,
) -> HarnessResult:
    """
    Async harness invocation (used for circuit breaker wrapping).

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

        collected = ""
        usage = TokenUsage()
        message_count = 0
        # stream_task yields str chunks and optionally a final TokenUsage sentinel
        stream_it = harness_backend.stream_task(task_input, debug=debug)
        async for chunk in stream_it:  # type: ignore[attr-defined]
            if isinstance(chunk, TokenUsage):
                usage = chunk
            else:
                if message_count > 0:
                    _stream_callback("\n")
                _stream_callback(chunk)
                collected += chunk
                message_count += 1

        sys.stdout.write("\n")
        sys.stdout.flush()

        # Write collected output to harness.log if path provided
        if harness_log_path is not None:
            try:
                harness_log_path.write_text(collected, encoding="utf-8")
            except Exception as e:
                if debug:
                    console.print(f"[dim]Warning: Failed to write harness.log: {e}[/dim]")

        return HarnessResult(
            output=collected,
            usage=usage,
            duration_seconds=time.time() - start_time,
            exit_code=0,
        )
    else:
        # Blocking execution with async backend
        task_result = await harness_backend.run_task(task_input, debug)

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


def _invoke_harness(
    harness_backend: AsyncHarnessBackend,
    task_input: TaskInput,
    stream: bool,
    debug: bool,
    harness_log_path: Path | None = None,
    circuit_breaker: CircuitBreaker | None = None,
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
        circuit_breaker: Optional circuit breaker for timeout protection

    Returns:
        HarnessResult with output, usage, and timing

    Raises:
        CircuitBreakerTrippedError: If circuit breaker timeout is exceeded
    """
    # Create async invocation coroutine
    coro = _invoke_harness_async(harness_backend, task_input, stream, debug, harness_log_path)

    # Wrap with circuit breaker if provided
    if circuit_breaker is not None:
        coro = circuit_breaker.execute(coro)

    # Execute the coroutine
    return _run_async(lambda: coro)




app = typer.Typer(
    name="run",
    help="Execute autonomous task loop with AI harness",
    no_args_is_help=False,
)

console = Console()


def _stream_callback(text: str) -> None:
    """Write text to stdout with immediate flush for real-time streaming."""
    sys.stdout.write(text)
    sys.stdout.flush()


# Global flag for interrupt handling (DEPRECATED - use InterruptHandler instead)
# Kept for backward compatibility during migration
_interrupted = False


def _signal_handler(signum: int, frame: object) -> None:
    """
    Handle SIGINT gracefully (DEPRECATED).

    This function is deprecated and will be removed once all code paths
    use InterruptHandler. It's kept for backward compatibility.
    """
    global _interrupted
    if _interrupted:
        # Second interrupt - force exit with exception to allow finally blocks to run
        # Using raise SystemExit instead of sys.exit() ensures finally blocks execute (E4)
        console.print("\n[bold red]Force exiting...[/bold red]")
        raise SystemExit(130)
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


# --- Prompt builder functions (delegated to core/run/prompt_builder) ---
# Re-exported here for backwards compatibility with existing imports.
from cub.core.run.prompt_builder import (  # noqa: E402, F401
    generate_direct_task_prompt,
    generate_epic_context,
    generate_retry_context,
    generate_system_prompt,
    generate_task_prompt,
)


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


def display_task_info(
    task: Task,
    iteration: int,
    max_iterations: int,
    *,
    harness_name: str | None = None,
    model: str | None = None,
) -> None:
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
    if harness_name:
        table.add_row("Harness", harness_name)
    if model:
        table.add_row("Model", model)

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
    completed_at = (
        datetime.now()
        if status.phase in [RunPhase.COMPLETED, RunPhase.FAILED, RunPhase.STOPPED]
        else None
    )

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

    # Circuit breaker status
    if status.circuit_breaker_enabled:
        table.add_row("Circuit Breaker", f"Enabled ({status.circuit_breaker_timeout}min timeout)")
    else:
        table.add_row("Circuit Breaker", "Disabled")

    console.print(table)


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    harness: str | None = typer.Option(
        None,
        "--harness",
        "-H",
        help=(
            "AI harness to use (claude, claude-sdk, claude-cli, codex, gemini, "
            "opencode). 'claude' defaults to 'claude-sdk'. Use 'claude-cli' for "
            "shell-out."
        ),
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
    plan: str | None = typer.Option(
        None,
        "--plan",
        help="Execute a staged plan by iterating through all its epics",
    ),
    start_epic: str | None = typer.Option(
        None,
        "--start-epic",
        help="Start plan execution from this epic (skip earlier ones, requires --plan)",
    ),
    only_epic: str | None = typer.Option(
        None,
        "--only-epic",
        help="Only execute this specific epic within the plan (requires --plan)",
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
    no_sync: bool = typer.Option(
        False,
        "--no-sync",
        help="Disable auto-sync for this run (overrides config)",
    ),
    no_circuit_breaker: bool = typer.Option(
        False,
        "--no-circuit-breaker",
        help="Disable circuit breaker timeout protection (overrides config)",
    ),
) -> None:
    """
    Execute autonomous task loop with AI harness.

    Picks up tasks from your task backend and executes them using the specified
    AI harness (Claude, Codex, Gemini, etc) until stopped, budget exhausted, or
    no more tasks. By default creates a feature branch from origin/main and
    auto-syncs task state to the cub-sync branch.

    Task Selection:
        By default, picks unblocked tasks with highest priority.
        Use --task, --epic, or --label to narrow scope.
        Use --ready to list tasks without executing.

    Budget Control:
        Set limits with --budget (USD) or --budget-tokens (token count).
        Useful for testing before running large sessions.

    Isolation Modes:
        --worktree    Run in isolated git worktree (default)
        --parallel N  Run N tasks in parallel in separate worktrees
        --sandbox     Run in Docker container for maximum isolation
        --direct      Run a single task without task backend

    Branch Management:
        By default creates feature branch from origin/main (main/master protected).
        --use-current-branch  Stay in current branch (must not be main/master)
        --from-branch <name>  Use different base branch
        --main-ok             Explicitly allow running on main/master (risky)

    Monitoring:
        --monitor     Live dashboard in tmux (requires tmux)
        --stream      Stream harness output in real-time
        --debug       Show detailed logging

    Examples:
        # Basic execution
        cub run                      # Run ready tasks (creates feature branch)
        cub run --once               # Single iteration and exit

        # Select specific work
        cub run --task cub-123       # Work on specific task
        cub run --epic backend-v2    # Work on epic
        cub run --label priority     # Work on labeled tasks
        cub run --gh-issue 47        # Work on GitHub issue

        # Isolation
        cub run --parallel 3         # Run 3 tasks in parallel
        cub run --sandbox            # Run in Docker sandbox
        cub run --worktree           # Use isolated worktree

        # Advanced
        cub run --direct "Add logout button"  # Direct task
        cub run --budget 5.0         # Limit to $5 spend
        cub run --from-branch develop  # Branch from develop
        cub run --use-current-branch # Stay in current branch
        cub run --harness claude     # Specific harness
        cub run --model opus         # Specific model

        # Monitoring
        cub run --monitor            # Live dashboard
        cub run --stream             # Stream output
        cub run --ready              # List ready tasks
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Validate flags
    if no_network and not sandbox:
        print_incompatible_flags_error(
            "--no-network",
            "--sandbox",
            reason="Network isolation is only available in sandbox mode",
        )
        raise typer.Exit(ExitCode.USER_ERROR)

    if sandbox_keep and not sandbox:
        print_incompatible_flags_error(
            "--sandbox-keep",
            "--sandbox",
            reason="Can only preserve sandboxes when sandbox mode is enabled",
        )
        raise typer.Exit(ExitCode.USER_ERROR)

    if direct:
        # --direct is incompatible with task management flags
        if task_id:
            print_incompatible_flags_error(
                "--direct", "--task", reason="Direct mode runs without task management"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if epic:
            print_incompatible_flags_error(
                "--direct", "--epic", reason="Direct mode runs without task management"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if label:
            print_incompatible_flags_error(
                "--direct", "--label", reason="Direct mode runs without task management"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if ready:
            print_incompatible_flags_error(
                "--direct", "--ready", reason="Direct mode runs without task management"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if parallel:
            print_incompatible_flags_error(
                "--direct", "--parallel", reason="Direct mode runs without task management"
            )
            raise typer.Exit(ExitCode.USER_ERROR)

    if gh_issue is not None:
        # --gh-issue is incompatible with task management flags
        if task_id:
            print_incompatible_flags_error(
                "--gh-issue", "--task", reason="GitHub issue mode uses issues for input, not tasks"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if epic:
            print_incompatible_flags_error(
                "--gh-issue", "--epic", reason="GitHub issue mode uses issues for input, not epics"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if label:
            print_incompatible_flags_error(
                "--gh-issue", "--label", reason="GitHub issue mode uses issues for input"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if ready:
            print_incompatible_flags_error(
                "--gh-issue", "--ready", reason="GitHub issue mode uses issues for input"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if parallel:
            print_incompatible_flags_error(
                "--gh-issue", "--parallel", reason="GitHub issue mode processes one issue at a time"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if direct:
            print_incompatible_flags_error(
                "--gh-issue",
                "--direct",
                reason="Choose either GitHub issue mode or direct mode, not both",
            )
            raise typer.Exit(ExitCode.USER_ERROR)

    # --plan flag validation
    if plan:
        # --plan is incompatible with other execution mode flags
        if task_id:
            print_incompatible_flags_error(
                "--plan", "--task", reason="Plan mode executes full epics, not individual tasks"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if epic:
            print_incompatible_flags_error(
                "--plan", "--epic", reason="Use --only-epic with --plan to run a specific epic"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if label:
            print_incompatible_flags_error(
                "--plan", "--label", reason="Plan mode executes all tasks in each epic"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if direct:
            print_incompatible_flags_error(
                "--plan", "--direct", reason="Plan mode uses staged plan tasks"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if gh_issue is not None:
            print_incompatible_flags_error(
                "--plan", "--gh-issue", reason="Plan mode uses staged plan tasks"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if ready:
            print_incompatible_flags_error(
                "--plan", "--ready", reason="Plan mode doesn't support ready listing"
            )
            raise typer.Exit(ExitCode.USER_ERROR)
        if parallel:
            print_incompatible_flags_error(
                "--plan", "--parallel", reason="Plan mode runs epics sequentially"
            )
            raise typer.Exit(ExitCode.USER_ERROR)

    # --start-epic and --only-epic require --plan
    if start_epic and not plan:
        console.print("[red]Error: --start-epic requires --plan[/red]")
        raise typer.Exit(ExitCode.USER_ERROR)
    if only_epic and not plan:
        console.print("[red]Error: --only-epic requires --plan[/red]")
        raise typer.Exit(ExitCode.USER_ERROR)
    if start_epic and only_epic:
        print_incompatible_flags_error(
            "--start-epic", "--only-epic", reason="Use one or the other, not both"
        )
        raise typer.Exit(ExitCode.USER_ERROR)

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
            print_main_branch_error(current_branch)
            raise typer.Exit(ExitCode.USER_ERROR)
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
            auto_branch_name = f"feature/{slugify(label)}"
        elif epic:
            # --epic cub-xyz → feature/[epic-slug]
            epic_context = get_epic_context(epic)
            if epic_context.title:
                auto_branch_name = f"feature/{slugify(epic_context.title)}"
            else:
                # Fallback to epic ID
                auto_branch_name = f"feature/{slugify(epic)}"
        elif gh_issue is not None:
            # --gh-issue 47 → fix/[issue-slug]
            issue_context = get_issue_context(gh_issue)
            if issue_context.title:
                auto_branch_name = f"fix/{slugify(issue_context.title)}"
            else:
                # Fallback to issue number
                auto_branch_name = f"fix/issue-{gh_issue}"
        elif task_id:
            # --task cub-123 → task/cub-123
            auto_branch_name = f"task/{slugify(task_id)}"
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
            console.print(f"[cyan]Creating branch '{auto_branch_name}' from '{base_branch}'[/cyan]")
            result = create_run_branch(auto_branch_name, base_branch)
            if not result.success:
                console.print(f"[red]{result.error}[/red]")
                raise typer.Exit(1)
            # Print user-friendly messages
            if result.created:
                console.print(
                    f"[green]Created branch '{result.branch_name}' from '{base_branch}'[/green]"
                )
            else:
                console.print(f"[yellow]Branch '{result.branch_name}' already exists[/yellow]")
                console.print(f"[green]Switched to existing branch '{result.branch_name}'[/green]")

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
            print_missing_dependency_error(
                "docker",
                install_url="https://docs.docker.com/get-docker/",
                install_cmd="Follow platform-specific instructions at the docs link",
            )
            raise typer.Exit(ExitCode.USER_ERROR)

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
        if plan:
            run_args.extend(["--plan", plan])
        if start_epic:
            run_args.extend(["--start-epic", start_epic])
        if only_epic:
            run_args.extend(["--only-epic", only_epic])
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
        if no_sync:
            run_args.append("--no-sync")
        if no_circuit_breaker:
            run_args.append("--no-circuit-breaker")
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

    # Handle --plan flag: execute a staged plan
    if plan:
        exit_code = _run_plan(
            plan_slug=plan,
            project_dir=project_dir,
            config=config,
            harness=harness,
            model=model,
            stream=stream,
            budget=budget,
            budget_tokens=budget_tokens,
            session_name=session_name,
            start_epic=start_epic,
            only_epic=only_epic,
            main_ok=main_ok,
            use_current_branch=use_current_branch,
            from_branch=from_branch,
            no_sync=no_sync,
            no_circuit_breaker=no_circuit_breaker,
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

    # Initialize sync service (if enabled and backend supports it)
    # Only initialize for backends that use .cub/tasks.jsonl (jsonl or both mode)
    sync_service: SyncService | None = None
    should_auto_sync = (
        not no_sync
        and config.sync.enabled
        and config.sync.auto_sync in ("run", "always")
        and ("jsonl" in backend_name or "both" in backend_name)
    )
    if should_auto_sync:
        sync_service = SyncService(project_dir=project_dir)
        # Initialize sync branch if not already initialized
        if not sync_service.is_initialized():
            try:
                sync_service.initialize()
                if debug:
                    console.print("[dim]Initialized cub-sync branch[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to initialize sync branch: {e}[/yellow]")
                sync_service = None  # Disable auto-sync for this run

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

    # Initialize circuit breaker for stagnation detection
    circuit_breaker_enabled = config.circuit_breaker.enabled and not no_circuit_breaker
    if debug and circuit_breaker_enabled:
        timeout = config.circuit_breaker.timeout_minutes
        console.print(f"[dim]Circuit breaker enabled: {timeout} minute timeout[/dim]")
    elif debug:
        console.print("[dim]Circuit breaker disabled[/dim]")

    # Set up interrupt handler for graceful interrupts
    interrupt_handler = InterruptHandler()

    # Add callback for Rich console output on interrupt
    def _on_interrupt_callback() -> None:
        """Display interrupt message using Rich console."""
        console.print("\n[yellow]Interrupt received. Finishing current task...[/yellow]")

    interrupt_handler.on_interrupt(_on_interrupt_callback)

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
        circuit_breaker_enabled=circuit_breaker_enabled,
        circuit_breaker_timeout=config.circuit_breaker.timeout_minutes,
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
    ledger_integration = LedgerIntegration(ledger_writer, task_backend)

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

    # Build RunService with pre-wired dependencies
    run_service = RunService(
        config=config,
        project_dir=project_dir,
        task_backend=task_backend,
        harness_name=harness_name,
        harness_backend=harness_backend,
        ledger_integration=ledger_integration,
        sync_service=sync_service,
        status_writer=status_writer,
        interrupt_handler=interrupt_handler,
    )

    # Build RunConfig from CLI args and loaded config
    run_config = run_service.build_run_config(
        once=once,
        task_id=task_id,
        epic=epic,
        label=label,
        model=model,
        session_name=session_name,
        stream=stream,
        debug=debug,
        max_iterations=max_iterations,
        budget_tokens=budget_tokens,
        budget_cost=budget,
        no_circuit_breaker=no_circuit_breaker,
        no_sync=no_sync,
    )

    try:
        # Execute the loop via RunService and render events
        for event in run_service.execute(run_config, run_id=run_id):
            # No need to forward interrupt flag - RunLoop checks interrupt_handler directly

            # Render event based on type
            _render_run_event(
                event,
                status=status,
                status_writer=status_writer,
                task_backend=task_backend,
                session_manager=session_manager,
                run_session=run_session,
                config=config,
                harness_name=harness_name,
                model=run_config.model,
                run_id=run_id,
                project_dir=project_dir,
                debug=debug,
            )

    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        status.mark_failed(str(e))
        raise

    finally:
        # Note: pre/post-loop hooks and async hook waiting are now handled
        # inside RunLoop.execute(). We only handle session/cleanup here.

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

        # Unregister interrupt handler
        try:
            interrupt_handler.unregister()
        except Exception:
            pass  # Non-fatal

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


def _render_run_event(
    event: RunEvent,
    *,
    status: RunStatus,
    status_writer: StatusWriter,
    task_backend: TaskBackend,
    session_manager: RunSessionManager,
    run_session: object,
    config: CubConfig,
    harness_name: str,
    model: str | None = None,
    run_id: str,
    project_dir: Path,
    debug: bool,
) -> None:
    """
    Render a RunEvent from the core loop into Rich CLI output and status updates.

    This is the bridge between the pure RunLoop state machine and the CLI
    rendering layer. It handles:
    - Rich console output (colors, panels, tables)
    - RunStatus updates for the status file
    - Session manager updates
    - Task artifact persistence

    Args:
        event: The RunEvent to render.
        status: Mutable RunStatus to update.
        status_writer: For persisting status and artifacts.
        task_backend: For task count queries.
        session_manager: For session progress updates.
        run_session: Current session object.
        config: Loaded CubConfig.
        harness_name: Harness name for display.
        model: Model override from CLI/config (e.g., "sonnet", "opus").
        run_id: Run ID for session tracking.
        project_dir: Project directory.
        debug: Debug mode flag.
    """
    et = event.event_type

    if et == RunEventType.RUN_STARTED:
        # Already displayed by the setup code above
        pass

    elif et == RunEventType.ITERATION_STARTED:
        if debug:
            console.print(
                f"[dim]=== Iteration {event.iteration}/{event.max_iterations} ===[/dim]"
            )

    elif et == RunEventType.TASK_SELECTED:
        # Display task info panel
        if event.task_id:
            task = task_backend.get_task(event.task_id)
            if task:
                # Resolve effective model: CLI/config override > task label
                effective_model = model or task.model_label
                display_task_info(
                    task,
                    event.iteration,
                    event.max_iterations,
                    harness_name=harness_name,
                    model=effective_model,
                )

            # Update status
            status.current_task_id = event.task_id
            status.current_task_title = event.task_title
            status.iteration.current = event.iteration
            status.start_task_entry(event.task_id)
            status.add_event(
                f"Starting task: {event.task_title}",
                EventLevel.INFO,
                task_id=event.task_id,
            )
            status_writer.write(status)

    elif et == RunEventType.TASK_STARTED:
        console.print(f"[bold]Running {harness_name}...[/bold]")

    elif et == RunEventType.TASK_COMPLETED:
        console.print(f"[green]Task completed in {event.duration_seconds:.1f}s[/green]")
        console.print(f"[dim]Tokens: {event.tokens_used:,}[/dim]")

        status.budget.tasks_completed += 1
        if event.task_id:
            status.complete_task_entry(event.task_id)
        status.add_event(
            f"Task completed: {event.task_title}",
            EventLevel.INFO,
            task_id=event.task_id,
            duration=event.duration_seconds,
            tokens=event.tokens_used,
        )

        # Persist task artifact
        if event.task_id:
            task = task_backend.get_task(event.task_id)
            if task:
                priority_str = (
                    task.priority.value if hasattr(task.priority, "value") else str(task.priority)
                )
                task_artifact = TaskArtifact(
                    task_id=event.task_id,
                    title=event.task_title or "",
                    priority=priority_str,
                    status="completed",
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    iterations=1,
                    exit_code=event.exit_code,
                    duration_seconds=event.duration_seconds,
                )
                try:
                    status_writer.write_task_artifact(event.task_id, task_artifact)
                except Exception:
                    pass

        # Clear current task and update counts
        _update_status_after_task(
            status, status_writer, task_backend, session_manager, run_session, debug
        )

    elif et == RunEventType.TASK_FAILED:
        console.print(f"[red]Task failed: {event.error or 'Unknown error'}[/red]")
        status.add_event(
            f"Task failed: {event.error}",
            EventLevel.ERROR,
            task_id=event.task_id,
            exit_code=event.exit_code,
        )

        # Persist task artifact for failed task
        if event.task_id:
            task = task_backend.get_task(event.task_id)
            if task:
                priority_str = (
                    task.priority.value if hasattr(task.priority, "value") else str(task.priority)
                )
                task_artifact = TaskArtifact(
                    task_id=event.task_id,
                    title=event.task_title or "",
                    priority=priority_str,
                    status="failed",
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    iterations=1,
                    exit_code=event.exit_code,
                    duration_seconds=event.duration_seconds,
                )
                try:
                    status_writer.write_task_artifact(event.task_id, task_artifact)
                except Exception:
                    pass

        # Update status
        _update_status_after_task(
            status, status_writer, task_backend, session_manager, run_session, debug
        )

        if config.loop.on_task_failure == "stop":
            status.mark_failed(event.error or "Task execution failed")

    elif et == RunEventType.BUDGET_UPDATED:
        # Update budget in status
        status.budget.tokens_used = event.total_tokens_used
        status.budget.cost_usd = event.total_cost_usd

    elif et == RunEventType.BUDGET_WARNING:
        pct = event.budget_percentage or 0.0
        threshold = config.guardrails.iteration_warning_threshold * 100
        console.print(
            f"[yellow]Budget warning: {pct:.1f}% used "
            f"(threshold: {threshold:.0f}%)[/yellow]"
        )
        status.add_event(f"Budget warning: {pct:.1f}% used", EventLevel.WARNING)

        # Fire on-budget-warning hook (async)
        budget_context = HookContext(
            hook_name="on-budget-warning",
            project_dir=project_dir,
            harness=harness_name,
            session_id=run_id,
            budget_percentage=pct,
            budget_used=status.budget.tokens_used,
            budget_limit=status.budget.tokens_limit,
        )
        run_hooks_async("on-budget-warning", budget_context, project_dir)

    elif et == RunEventType.BUDGET_EXHAUSTED:
        console.print("[yellow]Budget exhausted. Stopping.[/yellow]")
        status.add_event("Budget exhausted", EventLevel.WARNING)
        status.mark_completed()

    elif et == RunEventType.EPIC_CLOSED:
        console.print(f"[green]{event.message}[/green]")
        status.add_event(event.message, EventLevel.INFO, task_id=event.task_id)

    elif et == RunEventType.ALL_TASKS_COMPLETE:
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

    elif et == RunEventType.NO_TASKS_AVAILABLE:
        from cub.cli.errors import print_error

        remaining = event.data.get("remaining", 0) if event.data else 0
        print_error(
            "No ready tasks available",
            reason=f"{remaining} tasks remaining but all have unmet dependencies",
            solution="cub task list --status blocked  # to see blocked tasks\n"
            "       [cyan]→ Or:[/cyan] Check task dependencies with 'cub task show <task-id>'",
        )
        status.mark_completed()

    elif et == RunEventType.MAX_ITERATIONS_REACHED:
        console.print(f"[yellow]Reached max iterations ({event.max_iterations})[/yellow]")
        status.add_event("Reached max iterations", EventLevel.WARNING)
        status.mark_stopped()

    elif et == RunEventType.CIRCUIT_BREAKER_TRIPPED:
        console.print(f"[red]Circuit breaker tripped: {event.error}[/red]")
        status.add_event(
            f"Circuit breaker tripped: {event.error}",
            EventLevel.ERROR,
            task_id=event.task_id,
        )
        status.mark_failed(event.error or "Circuit breaker tripped")
        status_writer.write(status)

    elif et == RunEventType.HARNESS_ERROR:
        console.print(f"[red]Harness invocation failed: {event.error}[/red]")
        status.add_event(
            f"Harness failed: {event.error}",
            EventLevel.ERROR,
            task_id=event.task_id,
        )

    elif et == RunEventType.HOOK_FAILED:
        console.print(f"[red]{event.message}[/red]")
        status.mark_failed(event.error or "Hook failed")

    elif et == RunEventType.INTERRUPT_RECEIVED:
        console.print("[yellow]Stopping due to interrupt...[/yellow]")
        status.mark_stopped()

    elif et == RunEventType.RUN_COMPLETED:
        if not status.is_finished:
            status.mark_completed()

    elif et == RunEventType.RUN_FAILED:
        if not status.is_finished:
            status.mark_failed(event.error or "Run failed")

    elif et == RunEventType.RUN_STOPPED:
        if not status.is_finished:
            status.mark_stopped()

    elif et == RunEventType.DEBUG_INFO:
        if debug:
            console.print(f"[dim]{event.message}[/dim]")


def _update_status_after_task(
    status: RunStatus,
    status_writer: StatusWriter,
    task_backend: TaskBackend,
    session_manager: RunSessionManager,
    run_session: object,
    debug: bool,
) -> None:
    """Update status, task counts, and session after task completion/failure."""
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
            run_session.run_id,  # type: ignore[attr-defined]
            tasks_completed=status.budget.tasks_completed,
            tasks_failed=max(0, status.tasks_closed - status.budget.tasks_completed),
            current_task=None,
            budget=session_budget,
        )
    except Exception as e:
        if debug:
            console.print(f"[dim]Warning: Failed to update run session: {e}[/dim]")


def _run_plan(
    plan_slug: str,
    project_dir: Path,
    config: object,
    harness: str | None,
    model: str | None,
    stream: bool,
    budget: float | None,
    budget_tokens: int | None,
    session_name: str | None,
    start_epic: str | None,
    only_epic: str | None,
    main_ok: bool,
    use_current_branch: bool,
    from_branch: str | None,
    no_sync: bool,
    no_circuit_breaker: bool,
    debug: bool,
) -> int:
    """
    Execute a staged plan by iterating through its epics.

    This implements the functionality of the build-plan command as an integrated
    part of cub run. It iterates through all epics in a plan, running `cub run --epic`
    for each one, and creates appropriate ledger entries.

    Args:
        plan_slug: The plan slug (directory name under plans/)
        project_dir: Project directory
        config: Loaded configuration
        harness: AI harness to use
        model: Model to use
        stream: Stream output
        budget: Budget limit (USD)
        budget_tokens: Token budget limit
        session_name: Session name
        start_epic: Start from this epic (skip earlier ones)
        only_epic: Only run this specific epic
        main_ok: Allow running on main/master branch
        use_current_branch: Use current branch instead of creating new one
        from_branch: Base branch for new feature branch
        no_sync: Disable auto-sync
        no_circuit_breaker: Disable circuit breaker
        debug: Debug mode

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    from cub.core.config.models import CubConfig
    from cub.core.ledger.models import EpicEntry, PlanEntry
    from cub.core.plan.models import Plan, PlanStatus
    from cub.core.prep.plan_markdown import parse_plan_markdown

    # Type narrow config
    if not isinstance(config, CubConfig):
        console.print("[red]Invalid configuration[/red]")
        return 1

    # Validate plan exists
    plan_dir = project_dir / "plans" / plan_slug
    itemized_plan_path = plan_dir / "itemized-plan.md"
    plan_json_path = plan_dir / "plan.json"

    if not plan_dir.exists():
        console.print(f"[red]Plan directory not found: {plan_dir}[/red]")
        return 1

    if not itemized_plan_path.exists():
        console.print(f"[red]Itemized plan not found: {itemized_plan_path}[/red]")
        console.print("[dim]Run 'cub plan itemize' first[/dim]")
        return 1

    if not plan_json_path.exists():
        console.print(f"[red]Plan metadata not found: {plan_json_path}[/red]")
        console.print("[dim]Run 'cub stage' first[/dim]")
        return 1

    # Load plan
    try:
        plan = Plan.load(plan_dir)
    except Exception as e:
        console.print(f"[red]Failed to load plan: {e}[/red]")
        return 1

    if plan.status not in (PlanStatus.STAGED, PlanStatus.COMPLETE):
        console.print(
            f"[yellow]Warning: Plan status is '{plan.status.value}', expected 'staged'[/yellow]"
        )

    # Parse epics from itemized plan
    itemized_content = itemized_plan_path.read_text(encoding="utf-8")
    epics = parse_plan_markdown(itemized_content)

    if not epics:
        console.print("[red]No epics found in itemized plan[/red]")
        return 1

    epic_ids = [epic.epic_id for epic in epics]
    console.print(f"[bold]Plan: {plan_slug}[/bold]")
    console.print(f"Epics: {len(epic_ids)}")

    if debug:
        for i, epic in enumerate(epics, 1):
            console.print(f"[dim]  {i}. {epic.epic_id}: {epic.title}[/dim]")

    # Setup harness
    harness_result = _setup_harness(harness, config.harness.priority, debug)
    if harness_result is None:
        return 1
    harness_name, harness_backend = harness_result

    # Initialize task backend
    try:
        task_backend = get_task_backend(project_dir=project_dir)
    except Exception as e:
        console.print(f"[red]Failed to initialize task backend: {e}[/red]")
        return 1

    # Initialize ledger
    ledger_dir = project_dir / ".cub" / "ledger"
    ledger_writer = LedgerWriter(ledger_dir)
    ledger_integration = LedgerIntegration(ledger_writer, task_backend)

    # Generate session/plan ID
    plan_session_id = session_name or f"plan-{plan_slug}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    start_time = datetime.now()

    # Create/update PlanEntry in ledger
    plan_entry = PlanEntry(
        plan_id=plan_session_id,
        spec_id=plan.spec_file or plan_slug,
        title=plan_slug,
        epics=epic_ids,
        status="in_progress",
        started_at=start_time,
    )
    try:
        ledger_writer.create_plan_entry(plan_entry)
        if debug:
            console.print(f"[dim]Created plan entry: {plan_session_id}[/dim]")
    except Exception as e:
        if debug:
            console.print(f"[dim]Warning: Failed to write plan entry: {e}[/dim]")

    # Track overall progress
    processed_epics = 0
    failed_epic: str | None = None
    total_tasks_completed = 0
    total_cost = 0.0
    total_tokens = 0

    # Determine which epics to process
    epic_started = start_epic is None  # If no start_epic, start from beginning

    console.print()
    for i, epic in enumerate(epics, 1):
        epic_id = epic.epic_id

        # Handle --only-epic
        if only_epic and epic_id != only_epic:
            continue

        # Handle --start-epic
        if start_epic:
            if epic_id == start_epic:
                epic_started = True
            if not epic_started:
                console.print(f"[dim]Skipping {epic_id} (before start epic)[/dim]")
                continue

        # Check if epic is already complete (all tasks closed)
        epic_tasks = task_backend.list_tasks(parent=epic_id)
        open_tasks = [t for t in epic_tasks if t.status.value != "closed"]

        if not open_tasks and epic_tasks:
            console.print(f"[green]✓ Skipping {epic_id} (already complete)[/green]")
            processed_epics += 1
            continue

        console.print()
        console.print(f"[bold cyan]═══ Epic {i}/{len(epics)}: {epic_id} ═══[/bold cyan]")
        console.print(f"[bold]{epic.title}[/bold]")
        console.print(f"Tasks: {len(open_tasks)} open / {len(epic_tasks)} total")
        console.print()

        # Run cub for this epic using RunService
        try:
            # Initialize sync service
            sync_service: SyncService | None = None
            backend_name = task_backend.backend_name
            should_auto_sync = (
                not no_sync
                and config.sync.enabled
                and config.sync.auto_sync in ("run", "always")
                and ("jsonl" in backend_name or "both" in backend_name)
            )
            if should_auto_sync:
                sync_service = SyncService(project_dir=project_dir)
                if not sync_service.is_initialized():
                    try:
                        sync_service.initialize()
                    except Exception:
                        sync_service = None

            # Initialize status writer
            epic_run_id = f"{plan_session_id}-{epic_id}"
            status_writer = StatusWriter(project_dir, epic_run_id)

            # Initialize interrupt handler
            interrupt_handler = InterruptHandler()

            # Build RunService
            run_service = RunService(
                config=config,
                project_dir=project_dir,
                task_backend=task_backend,
                harness_name=harness_name,
                harness_backend=harness_backend,
                ledger_integration=ledger_integration,
                sync_service=sync_service,
                status_writer=status_writer,
                interrupt_handler=interrupt_handler,
            )

            # Build RunConfig for this epic
            run_config = run_service.build_run_config(
                epic=epic_id,
                model=model,
                stream=stream,
                debug=debug,
                budget_tokens=budget_tokens,
                budget_cost=budget,
                no_circuit_breaker=no_circuit_breaker,
                no_sync=no_sync,
            )

            # Execute the epic
            epic_start_time = datetime.now()
            epic_success = True
            epic_tasks_completed = 0
            epic_cost = 0.0
            epic_tokens = 0

            for event in run_service.execute(run_config, run_id=epic_run_id):
                # Track metrics from events
                if event.event_type == RunEventType.TASK_COMPLETED:
                    epic_tasks_completed += 1
                    total_tasks_completed += 1
                    if event.cost_usd:
                        epic_cost += event.cost_usd
                        total_cost += event.cost_usd
                    if event.tokens_used:
                        epic_tokens += event.tokens_used
                        total_tokens += event.tokens_used
                    console.print(f"[green]✓ {event.task_id}: {event.task_title}[/green]")
                elif event.event_type == RunEventType.TASK_FAILED:
                    epic_success = False
                    console.print(f"[red]✗ {event.task_id}: {event.error or 'Failed'}[/red]")
                elif event.event_type == RunEventType.BUDGET_EXHAUSTED:
                    console.print("[yellow]Budget exhausted[/yellow]")
                    break
                elif event.event_type == RunEventType.INTERRUPT_RECEIVED:
                    console.print("[yellow]Interrupted[/yellow]")
                    break
                elif event.event_type == RunEventType.ALL_TASKS_COMPLETE:
                    console.print(f"[green]All tasks in epic {epic_id} complete[/green]")
                elif event.event_type == RunEventType.NO_TASKS_AVAILABLE:
                    if debug:
                        console.print(f"[dim]No more ready tasks in {epic_id}[/dim]")
                elif event.event_type == RunEventType.RUN_FAILED:
                    epic_success = False
                    console.print(f"[red]Epic run failed: {event.error}[/red]")
                elif debug and event.event_type == RunEventType.BUDGET_UPDATED:
                    tokens = event.tokens_used or 0
                    cost = event.cost_usd or 0.0
                    console.print(f"[dim]Tokens: {tokens:,}, Cost: ${cost:.4f}[/dim]")

            result = run_service.get_result()

            # Create EpicEntry in ledger
            try:
                from cub.core.ledger.models import EpicAggregates, Lineage

                epic_aggregates = EpicAggregates(
                    total_tasks=len(epic_tasks),
                    tasks_completed=epic_tasks_completed,
                    tasks_successful=epic_tasks_completed if epic_success else 0,
                    total_cost_usd=epic_cost,
                    total_tokens=epic_tokens,
                )
                is_complete = epic_success and result.tasks_failed == 0
                epic_entry = EpicEntry(
                    id=epic_id,
                    title=epic.title,
                    lineage=Lineage(plan_file=plan_slug),
                    aggregates=epic_aggregates,
                    started_at=epic_start_time,
                    completed_at=datetime.now() if is_complete else None,
                )
                ledger_writer.create_epic_entry(epic_entry)
            except Exception as e:
                if debug:
                    console.print(f"[dim]Warning: Failed to write epic entry: {e}[/dim]")

            # Check if epic completed
            if not epic_success or result.tasks_failed > 0:
                failed_epic = epic_id
                console.print(f"[red]Epic {epic_id} failed[/red]")
                break

            # Try to close epic in task backend
            closed, message = task_backend.try_close_epic(epic_id)
            if closed:
                console.print(f"[green]{message}[/green]")

            processed_epics += 1
            console.print(f"[green]✓ Epic {epic_id} complete[/green]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
            failed_epic = epic_id
            break
        except Exception as e:
            console.print(f"[red]Error running epic {epic_id}: {e}[/red]")
            if debug:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
            failed_epic = epic_id
            break

    # Update PlanEntry with final status
    plan_completed = failed_epic is None
    try:
        plan_entry.status = "completed" if plan_completed else "in_progress"
        plan_entry.completed_at = datetime.now() if plan_completed else None
        plan_entry.total_cost = total_cost
        plan_entry.total_tokens = total_tokens
        plan_entry.completed_tasks = total_tasks_completed
        plan_entry.total_tasks = sum(
            len(task_backend.list_tasks(parent=e.epic_id)) for e in epics
        )
        ledger_writer.create_plan_entry(plan_entry)
    except Exception as e:
        if debug:
            console.print(f"[dim]Warning: Failed to update plan entry: {e}[/dim]")

    # Run end-of-plan lifecycle hook if plan completed
    if plan_completed and config.hooks.enabled:
        try:
            from cub.core.hooks.lifecycle import invoke_end_of_plan_hook
            from cub.core.run.models import RunConfig

            # Build a minimal RunConfig for the hook
            run_config = RunConfig(
                project_dir=str(project_dir),
                hooks_enabled=config.hooks.enabled,
                hooks_fail_fast=config.hooks.fail_fast,
                harness_name=harness_name,
            )

            invoke_end_of_plan_hook(
                run_config,
                task_backend,
                plan_slug,
                plan_session_id,
            )
        except Exception as e:
            if debug:
                console.print(f"[dim]Warning: Failed to invoke end-of-plan hook: {e}[/dim]")

    # Summary
    console.print()
    console.print("─" * 60)
    if failed_epic:
        console.print(f"[red]Plan execution stopped at epic: {failed_epic}[/red]")
        console.print(
            f"[dim]To resume: cub run --plan {plan_slug} --start-epic {failed_epic}[/dim]"
        )
        return 1
    else:
        console.print(f"[green]Plan '{plan_slug}' completed successfully![/green]")
        console.print(f"Epics processed: {processed_epics}")
        console.print(f"Tasks completed: {total_tasks_completed}")
        if total_cost > 0:
            console.print(f"Total cost: ${total_cost:.4f}")
        if total_tokens > 0:
            console.print(f"Total tokens: {total_tokens:,}")
        return 0


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
    start_time = datetime.now()

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

    # Track execution state for artifact creation
    result = None
    exit_code = 1

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

        # Display result
        console.print()
        if result.success:
            console.print(f"[green]Completed in {result.duration_seconds:.1f}s[/green]")
            console.print(f"[dim]Tokens: {result.usage.total_tokens:,}[/dim]")
            if result.usage.cost_usd:
                console.print(f"[dim]Cost: ${result.usage.cost_usd:.4f}[/dim]")
            exit_code = 0
        else:
            console.print(f"[red]Failed: {result.error or 'Unknown error'}[/red]")
            exit_code = result.exit_code if result.exit_code else 1

    except Exception as e:
        console.print(f"[red]Harness invocation failed: {e}[/red]")
        exit_code = 1
    finally:
        # Always create run artifact on exit (E4 requirement)
        try:
            from cub.core.status.models import BudgetStatus, RunArtifact

            completed_at = datetime.now()

            # Build budget status from result if available
            budget_status = BudgetStatus()
            if result and result.usage:
                budget_status.tokens_used = result.usage.total_tokens
                budget_status.cost_usd = result.usage.cost_usd or 0.0
                # Apply limits if provided
                if budget_tokens:
                    budget_status.tokens_limit = budget_tokens
                if budget:
                    budget_status.cost_limit = budget

            # Create run artifact
            run_artifact = RunArtifact(
                run_id=direct_session_id,
                session_name=session_name or "direct",
                started_at=start_time,
                completed_at=completed_at,
                status="completed" if exit_code == 0 else "failed",
                config={
                    "harness": harness_name,
                    "model": task_model,
                    "mode": "direct",
                },
                tasks_completed=1 if exit_code == 0 else 0,
                tasks_failed=0 if exit_code == 0 else 1,
                budget=budget_status,
            )

            status_writer.write_run_artifact(run_artifact)

            if debug:
                artifact_path = status_writer.run_artifact_path
                console.print(f"[dim]Run artifact written to {artifact_path}[/dim]")
        except Exception as e:
            # Don't let artifact write failure crash the program
            console.print(f"[yellow]Warning: Failed to write run artifact: {e}[/yellow]")

    return exit_code


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
    start_time = datetime.now()

    # Initialize status writer for log capture
    status_writer = StatusWriter(project_dir, gh_session_id)

    # Invoke harness
    console.print(f"[bold]Running {harness_name}...[/bold]")

    # Track execution state for artifact creation
    result = None
    exit_code = 1

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
                    f"[cyan]Changes on branch '{branch}'. "
                    f"Issue will close when merged to main.[/cyan]"
                )

            exit_code = 0
        else:
            console.print(f"[red]Failed: {result.error or 'Unknown error'}[/red]")
            exit_code = result.exit_code if result.exit_code else 1

    except Exception as e:
        console.print(f"[red]Harness invocation failed: {e}[/red]")
        exit_code = 1
    finally:
        # Always create run artifact on exit (E4 requirement)
        try:
            from cub.core.status.models import BudgetStatus, RunArtifact

            completed_at = datetime.now()

            # Build budget status from result if available
            budget_status = BudgetStatus()
            if result and result.usage:
                budget_status.tokens_used = result.usage.total_tokens
                budget_status.cost_usd = result.usage.cost_usd or 0.0
                # Apply limits if provided
                if budget_tokens:
                    budget_status.tokens_limit = budget_tokens
                if budget:
                    budget_status.cost_limit = budget

            # Create run artifact
            run_artifact = RunArtifact(
                run_id=gh_session_id,
                session_name=session_name or f"gh-{issue_number}",
                started_at=start_time,
                completed_at=completed_at,
                status="completed" if exit_code == 0 else "failed",
                config={
                    "harness": harness_name,
                    "model": task_model,
                    "mode": "gh-issue",
                    "issue_number": issue_number,
                },
                tasks_completed=1 if exit_code == 0 else 0,
                tasks_failed=0 if exit_code == 0 else 1,
                budget=budget_status,
            )

            status_writer.write_run_artifact(run_artifact)

            if debug:
                artifact_path = status_writer.run_artifact_path
                console.print(f"[dim]Run artifact written to {artifact_path}[/dim]")
        except Exception as e:
            # Don't let artifact write failure crash the program
            console.print(f"[yellow]Warning: Failed to write run artifact: {e}[/yellow]")

    return exit_code


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

    # Create session tracking for unified artifact
    parallel_session_id = f"parallel-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    start_time = datetime.now()
    status_writer = StatusWriter(project_dir, parallel_session_id)
    exit_code = 1

    try:
        # Create callback for Rich output
        callback = RichParallelCallback(console=console)

        # Create parallel runner
        runner = ParallelRunner(
            project_dir=project_dir,
            harness=harness,
            model=model,
            debug=debug,
            stream=stream,
            callback=callback,
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
            exit_code = 0
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
            priority = (
                task.priority.value if hasattr(task.priority, "value") else str(task.priority)
            )
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
            exit_code = 1
            raise typer.Exit(1)

        exit_code = 0
        raise typer.Exit(0)

    finally:
        # Always create unified run artifact (E4 requirement)
        # Workers create their own artifacts in worktrees, but we need unified host tracking
        try:
            from cub.core.status.models import BudgetStatus, RunArtifact

            completed_at = datetime.now()

            # Aggregate budget from worker results if available
            budget_status = BudgetStatus()
            if "result" in locals():
                total_tokens = sum(
                    worker.tokens_used for worker in result.workers if worker.tokens_used
                )
                budget_status.tokens_used = total_tokens

            # Create unified run artifact
            run_artifact = RunArtifact(
                run_id=parallel_session_id,
                session_name="parallel",
                started_at=start_time,
                completed_at=completed_at,
                status="completed" if exit_code == 0 else "failed",
                config={
                    "mode": "parallel",
                    "harness": harness,
                    "model": model,
                    "workers": parallel,
                    "epic": epic,
                    "label": label,
                },
                tasks_completed=result.tasks_completed if "result" in locals() else 0,
                tasks_failed=result.tasks_failed if "result" in locals() else 0,
                budget=budget_status,
            )

            status_writer.write_run_artifact(run_artifact)

            if debug:
                artifact_path = status_writer.run_artifact_path
                console.print(f"[dim]Unified artifact written to {artifact_path}[/dim]")
        except Exception as e:
            # Don't let artifact write failure crash cleanup
            console.print(f"[yellow]Warning: Failed to write unified artifact: {e}[/yellow]")


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

    # Create host-side session tracking for artifact creation
    sandbox_session_id = session_name or f"sandbox-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    start_time = datetime.now()
    status_writer = StatusWriter(project_dir, sandbox_session_id)

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
    exit_code = 1  # Track exit code for artifact creation
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

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        if sandbox_id:
            console.print("[cyan]Stopping sandbox...[/cyan]")
            try:
                provider.stop(sandbox_id)
            except Exception as e:
                if debug:
                    console.print(f"[dim]Failed to stop sandbox: {e}[/dim]")
        exit_code = 130

    except Exception as e:
        console.print(f"[red]Sandbox execution failed: {e}[/red]")
        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        exit_code = 1

    finally:
        # Always create host-side run artifact (E4 requirement)
        # Sandbox creates its own artifacts inside container, but host needs record too
        try:
            from cub.core.status.models import BudgetStatus, RunArtifact

            completed_at = datetime.now()

            # Create run artifact for host-side tracking
            run_artifact = RunArtifact(
                run_id=sandbox_session_id,
                session_name=session_name or "sandbox",
                started_at=start_time,
                completed_at=completed_at,
                status="completed" if exit_code == 0 else "failed",
                config={
                    "mode": "sandbox",
                    "harness": harness,
                    "model": model,
                    "sandbox_id": sandbox_id,
                    "network": not no_network,
                },
                tasks_completed=0,  # Sandbox tracks internally
                tasks_failed=0,
                budget=BudgetStatus(
                    tokens_limit=budget_tokens,
                    cost_limit=budget,
                ),
            )

            status_writer.write_run_artifact(run_artifact)

            if debug:
                artifact_path = status_writer.run_artifact_path
                console.print(f"[dim]Host artifact written to {artifact_path}[/dim]")
        except Exception as e:
            # Don't let artifact write failure crash cleanup
            console.print(f"[yellow]Warning: Failed to write host artifact: {e}[/yellow]")

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

    return exit_code


__all__ = ["app"]
