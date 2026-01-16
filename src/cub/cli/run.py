"""
Cub CLI - Run command.

Execute autonomous task loop with specified harness.
"""

import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cub.core.config.loader import load_config
from cub.core.harness.backend import detect_harness
from cub.core.harness.backend import get_backend as get_harness_backend
from cub.core.harness.models import HarnessResult
from cub.core.status.models import (
    BudgetStatus,
    EventLevel,
    IterationInfo,
    RunPhase,
    RunStatus,
)
from cub.core.status.writer import StatusWriter
from cub.core.tasks.backend import get_backend as get_task_backend
from cub.core.tasks.models import Task, TaskStatus
from cub.core.worktree.manager import WorktreeError, WorktreeManager
from cub.dashboard.tmux import get_dashboard_pane_size, launch_with_dashboard

app = typer.Typer(
    name="run",
    help="Execute autonomous task loop",
    no_args_is_help=False,
)

console = Console()


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


def generate_task_prompt(task: Task, backend_name: str) -> str:
    """
    Generate the task prompt for a specific task.

    Args:
        task: Task to generate prompt for
        backend_name: Name of the task backend (beads, json)

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

    # Add completion instructions based on backend
    prompt_parts.append("When complete:")
    prompt_parts.append("1. Run feedback loops (typecheck, test, lint)")

    task_type_str = task.type.value if hasattr(task.type, "value") else task.type
    if backend_name == "beads":
        prompt_parts.append(f"2. Mark task complete: bd close {task.id}")
        prompt_parts.append(f"3. Commit: {task_type_str}({task.id}): {task.title}")
    else:
        prompt_parts.append(f'2. Update prd.json: set status to "closed" for {task.id}')
        prompt_parts.append(f"3. Commit: {task_type_str}({task.id}): {task.title}")

    prompt_parts.append("4. Append learnings to progress.txt")

    # Add backend-specific notes
    if backend_name == "beads":
        prompt_parts.append("")
        prompt_parts.append(
            "Note: This project uses the beads task backend. Use 'bd' commands for task management:"
        )
        prompt_parts.append(f"- bd close {task.id}  - Mark this task complete")
        prompt_parts.append(f"- bd show {task.id}   - Check task status")
        prompt_parts.append("- bd list              - See all tasks")

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
        help="AI harness to use (claude, codex, gemini, opencode)",
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
) -> None:
    """
    Execute autonomous task loop.

    Runs the main cub loop, picking up tasks and executing them with the
    specified AI harness until stopped or budget is exhausted.

    Examples:
        cub run                         # Run with default harness
        cub run --harness claude        # Run with Claude
        cub run --once                  # Run one iteration
        cub run --task cub-123          # Run specific task
        cub run --budget 5.0            # Set budget to $5
        cub run --epic backend-v2       # Work on epic only
        cub run --label priority        # Work on labeled tasks
        cub run --ready                 # List ready tasks
        cub run --worktree              # Run in isolated worktree
        cub run --worktree --worktree-keep  # Keep worktree after run
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_dir = Path.cwd()

    # Load configuration
    config = load_config(project_dir)

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

    # Get task backend
    try:
        task_backend = get_task_backend(project_dir=project_dir)
        backend_name = "beads" if hasattr(task_backend, "_run_bd") else "json"
    except Exception as e:
        console.print(f"[red]Failed to initialize task backend: {e}[/red]")
        raise typer.Exit(1)

    if debug:
        console.print(f"[dim]Task backend: {backend_name}[/dim]")

    # Handle --ready flag: just list ready tasks
    if ready:
        _show_ready_tasks(task_backend, epic, label)
        raise typer.Exit(0)

    # Detect or validate harness
    harness_name = harness or detect_harness(config.harness.priority)
    if not harness_name:
        console.print(
            "[red]No harness available. Install claude, codex, or another supported harness.[/red]"
        )
        raise typer.Exit(1)

    try:
        harness_backend = get_harness_backend(harness_name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if not harness_backend.is_available():
        console.print(f"[red]Harness '{harness_name}' is not available. Is it installed?[/red]")
        raise typer.Exit(1)

    if debug:
        console.print(f"[dim]Harness: {harness_name} (v{harness_backend.get_version()})[/dim]")

    # Set up signal handler for graceful interrupts
    signal.signal(signal.SIGINT, _signal_handler)

    # Initialize run status
    run_id = session_name or f"cub-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    max_iterations = 1 if once else config.loop.max_iterations

    status = RunStatus(
        run_id=run_id,
        session_name=session_name or run_id,
        phase=RunPhase.INITIALIZING,
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

    # Update task counts
    counts = task_backend.get_task_counts()
    status.tasks_total = counts.total
    status.tasks_open = counts.open
    status.tasks_in_progress = counts.in_progress
    status.tasks_closed = counts.closed

    console.print(f"[bold]Starting cub run: {run_id}[/bold]")
    console.print(
        f"Tasks: {counts.open} open, {counts.in_progress} in progress, {counts.closed} closed"
    )
    console.print(f"Max iterations: {max_iterations}")
    console.print()

    # Generate system prompt
    system_prompt = generate_system_prompt(project_dir)

    # Main loop
    status.phase = RunPhase.RUNNING
    status.add_event("Run started", EventLevel.INFO)
    status_writer.write(status)

    global _interrupted

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
            status.add_event(
                f"Starting task: {current_task.title}", EventLevel.INFO, task_id=current_task.id
            )
            status_writer.write(status)

            # Claim task (mark as in_progress)
            try:
                task_backend.update_task(
                    current_task.id, status=TaskStatus.IN_PROGRESS, assignee=run_id
                )
            except Exception as e:
                if debug:
                    console.print(f"[dim]Failed to claim task: {e}[/dim]")

            # Generate task prompt
            task_prompt = generate_task_prompt(current_task, backend_name)

            if debug:
                console.print(f"[dim]System prompt: {len(system_prompt)} chars[/dim]")
                console.print(f"[dim]Task prompt: {len(task_prompt)} chars[/dim]")

            # Get model from task label or CLI arg or config
            task_model = model or current_task.model_label or config.harness.model

            # Invoke harness
            console.print(f"[bold]Running {harness_name}...[/bold]")
            start_time = time.time()

            try:
                if stream and harness_backend.capabilities.streaming:
                    result: HarnessResult = harness_backend.invoke_streaming(
                        system_prompt=system_prompt,
                        task_prompt=task_prompt,
                        model=task_model,
                        debug=debug,
                        callback=lambda text: print(text, end="", flush=True),
                    )
                    print()  # Newline after streaming output
                else:
                    result = harness_backend.invoke(
                        system_prompt=system_prompt,
                        task_prompt=task_prompt,
                        model=task_model,
                        debug=debug,
                    )
            except Exception as e:
                console.print(f"[red]Harness invocation failed: {e}[/red]")
                status.add_event(f"Harness failed: {e}", EventLevel.ERROR, task_id=current_task.id)
                if config.loop.on_task_failure == "stop":
                    status.mark_failed(str(e))
                    break
                continue

            duration = time.time() - start_time

            # Update budget tracking
            status.budget.tokens_used += result.usage.total_tokens
            if result.usage.cost_usd:
                status.budget.cost_usd += result.usage.cost_usd

            # Log result
            if result.success:
                console.print(f"[green]Task completed in {duration:.1f}s[/green]")
                console.print(f"[dim]Tokens: {result.usage.total_tokens:,}[/dim]")
                status.budget.tasks_completed += 1
                status.add_event(
                    f"Task completed: {current_task.title}",
                    EventLevel.INFO,
                    task_id=current_task.id,
                    duration=duration,
                    tokens=result.usage.total_tokens,
                )
            else:
                console.print(f"[red]Task failed: {result.error or 'Unknown error'}[/red]")
                status.add_event(
                    f"Task failed: {result.error}",
                    EventLevel.ERROR,
                    task_id=current_task.id,
                    exit_code=result.exit_code,
                )

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
        # Final status write
        status_writer.write(status)

        # Display summary
        console.print()
        display_summary(status)

        if debug:
            console.print(f"[dim]Final status: {status_writer.status_path}[/dim]")

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


__all__ = ["app"]
