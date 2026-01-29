"""
Cub CLI - Doctor command.

Diagnose and optionally fix common cub issues.
"""

import subprocess
from pathlib import Path

import typer
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

from cub.core.hooks.installer import validate_hooks
from cub.core.tasks.backend import get_backend
from cub.core.tasks.models import TaskStatus, TaskType
from cub.utils.project import get_project_root

app = typer.Typer(
    name="doctor",
    help="Diagnose and fix configuration issues",
    no_args_is_help=False,
)

console = Console()


class DiagnosticResult(BaseModel):
    """Represents a diagnostic check result."""

    category: str = Field(description="Check category (e.g., 'Environment', 'Hooks')")
    name: str = Field(description="Check name")
    status: str = Field(description="Status: pass, warn, fail, info")
    message: str = Field(description="Human-readable message")
    details: list[str] = Field(default_factory=list, description="Additional details")
    fix_command: str | None = Field(default=None, description="Suggested fix command")


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


def collect_environment_checks() -> list[DiagnosticResult]:
    """
    Collect environment diagnostic checks.

    Returns:
        List of DiagnosticResult objects for environment checks
    """
    results = []

    # Check git
    if _check_command("git"):
        version = _get_command_version("git", ["--version"])
        results.append(
            DiagnosticResult(
                category="Environment",
                name="git",
                status="pass",
                message=f"git {version}",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                category="Environment",
                name="git",
                status="fail",
                message="git not installed (required)",
                fix_command="Install from https://git-scm.com/downloads",
            )
        )

    # Check for at least one harness
    harnesses = ["claude", "codex", "gemini", "opencode"]
    harness_found = False
    harness_details = []

    for harness in harnesses:
        if _check_command(harness):
            version = _get_command_version(harness, ["--version"])
            harness_details.append(f"{harness} {version}")
            harness_found = True

    if harness_found:
        results.append(
            DiagnosticResult(
                category="Environment",
                name="AI Harness",
                status="pass",
                message="AI harness found",
                details=harness_details,
            )
        )
    else:
        results.append(
            DiagnosticResult(
                category="Environment",
                name="AI Harness",
                status="fail",
                message="No AI harness found (need claude, codex, gemini, or opencode)",
                fix_command="pip install anthropic-claude",
            )
        )

    # Check beads (optional)
    if _check_command("bd"):
        version = _get_command_version("bd", ["--version"])
        results.append(
            DiagnosticResult(
                category="Environment",
                name="beads (bd)",
                status="info",
                message=f"beads (bd) {version}",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                category="Environment",
                name="beads (bd)",
                status="info",
                message="beads (bd) not installed (optional)",
            )
        )

    return results


def collect_hooks_check(project_dir: Path, fix: bool = False) -> list[DiagnosticResult]:
    """
    Collect hooks diagnostic checks.

    Args:
        project_dir: Project directory path
        fix: If True, auto-fix hook issues

    Returns:
        List of DiagnosticResult objects for hook checks
    """
    results = []

    # Check if .claude directory exists
    claude_dir = project_dir / ".claude"
    if not claude_dir.exists():
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Hooks Installed",
                status="fail",
                message=".claude/ directory not found",
                fix_command="cub hooks install",
            )
        )
        return results

    # Check if settings.json exists
    settings_file = claude_dir / "settings.json"
    if not settings_file.exists():
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Hooks Installed",
                status="fail",
                message="settings.json not found in .claude/",
                fix_command="cub hooks install",
            )
        )
        return results

    # Hooks are installed
    results.append(
        DiagnosticResult(
            category="Hooks",
            name="Hooks Installed",
            status="pass",
            message="Hooks installed",
        )
    )

    # Validate hooks
    issues = validate_hooks(project_dir)

    if not issues:
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Shell Script",
                status="pass",
                message="Shell script present and executable",
            )
        )
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Python Module",
                status="pass",
                message="Python module importable",
            )
        )
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Hook Events",
                status="pass",
                message="All hook events configured",
            )
        )
        return results

    # Categorize issues
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    # Check shell script
    hook_script = project_dir / ".cub" / "scripts" / "hooks" / "cub-hook.sh"
    if any(hook_script.name in i.message for i in errors if "script" in i.message.lower()):
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Shell Script",
                status="fail",
                message="Shell script missing or not executable",
                fix_command="cub hooks install --force",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Shell Script",
                status="pass",
                message="Shell script present and executable",
            )
        )

    # Check Python module
    if any("handler" in i.message.lower() for i in errors):
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Python Module",
                status="fail",
                message="Python module not importable",
                fix_command="pip install -e .[dev]",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Python Module",
                status="pass",
                message="Python module importable",
            )
        )

    # Check hook events
    if any("event" in i.message.lower() or "not configured" in i.message.lower() for i in infos):
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Hook Events",
                status="warn",
                message="Some hook events not configured",
                fix_command="cub hooks install --force",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                category="Hooks",
                name="Hook Events",
                status="pass",
                message="All hook events configured",
            )
        )

    # Add specific errors/warnings as details
    if errors or warnings:
        issue_details = []
        for issue in errors:
            issue_details.append(f"ERROR: {issue.message}")
        for issue in warnings:
            issue_details.append(f"WARNING: {issue.message}")

        # Auto-fix if requested and there are errors/warnings
        if fix:
            from cub.core.hooks.installer import install_hooks

            result = install_hooks(project_dir, force=True)
            if result.success:
                results.append(
                    DiagnosticResult(
                        category="Hooks",
                        name="Auto-fix",
                        status="pass",
                        message=f"Auto-fixed hook issues: {result.message}",
                    )
                )
            else:
                results.append(
                    DiagnosticResult(
                        category="Hooks",
                        name="Auto-fix",
                        status="fail",
                        message=f"Auto-fix failed: {result.message}",
                    )
                )

    return results


def collect_stale_epics_check(project_dir: Path, fix: bool = False) -> DiagnosticResult:
    """
    Collect diagnostic result for stale epics check.

    Args:
        project_dir: Project directory path
        fix: If True, auto-close stale epics

    Returns:
        DiagnosticResult with stale epic information
    """
    try:
        backend = get_backend(project_dir=project_dir)
    except Exception as e:
        return DiagnosticResult(
            category="Task State",
            name="Stale Epics",
            status="warn",
            message=f"Could not load task backend: {e}",
        )

    # Get all tasks
    try:
        all_tasks = backend.list_tasks()
    except Exception as e:
        return DiagnosticResult(
            category="Task State",
            name="Stale Epics",
            status="warn",
            message=f"Could not list tasks: {e}",
        )

    # Find open epics
    open_epics = [
        task
        for task in all_tasks
        if task.type == TaskType.EPIC and task.status != TaskStatus.CLOSED
    ]

    if not open_epics:
        return DiagnosticResult(
            category="Task State",
            name="Stale Epics",
            status="pass",
            message="No open epics to check",
        )

    stale_epics = []
    stale_details = []

    for epic in open_epics:
        # Find subtasks
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
        return DiagnosticResult(
            category="Task State",
            name="Stale Epics",
            status="pass",
            message="No stale epics found",
        )

    # Fix if requested
    fixed_epics = []
    if fix:
        for epic_id in stale_epics:
            try:
                backend.close_task(epic_id, reason="Auto-closed: all subtasks complete")
                fixed_epics.append(epic_id)
            except Exception:
                pass

    if fixed_epics:
        return DiagnosticResult(
            category="Task State",
            name="Stale Epics",
            status="pass",
            message=f"Auto-closed {len(fixed_epics)} stale epic(s)",
            details=stale_details,
        )

    return DiagnosticResult(
        category="Task State",
        name="Stale Epics",
        status="warn",
        message=f"Found {len(stale_epics)} stale epic(s) with all subtasks complete",
        details=stale_details,
        fix_command="cub doctor --fix",
    )


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


def check_hooks(project_dir: Path, fix: bool = False) -> int:
    """
    Check Claude Code hooks configuration.

    Reports on hook installation status:
    - Hooks installed (yes/no)
    - Shell script present and executable
    - Python module importable
    - All required hook events configured

    Args:
        project_dir: Project directory path
        fix: If True, auto-install hooks when issues are found

    Returns:
        Number of issues found
    """
    console.print("\n[bold]Claude Code Hooks:[/bold]")

    # Check if .claude directory exists
    claude_dir = project_dir / ".claude"
    if not claude_dir.exists():
        console.print("[red]✗[/red] Hooks installed: No")
        console.print("[dim]  .claude/ directory not found[/dim]")
        console.print(
            "[dim]→ Run 'cub hooks install' to install Claude Code hooks[/dim]"
        )
        return 0

    # Hooks are "installed" if settings.json exists
    settings_file = claude_dir / "settings.json"
    hooks_installed = settings_file.exists()

    if hooks_installed:
        console.print("[green]✓[/green] Hooks installed: Yes")
    else:
        console.print("[red]✗[/red] Hooks installed: No")
        console.print("[dim]  settings.json not found in .claude/[/dim]")
        console.print(
            "[dim]→ Run 'cub hooks install' to install Claude Code hooks[/dim]"
        )
        return 0

    # Validate hooks
    issues = validate_hooks(project_dir)

    if not issues:
        console.print("[green]✓[/green] Shell script present and executable")
        console.print("[green]✓[/green] Python module importable")
        console.print("[green]✓[/green] All hook events configured")
        return 0

    # Categorize issues by severity
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    # Check specific validation statuses
    hook_script = project_dir / ".cub" / "scripts" / "hooks" / "cub-hook.sh"
    if any(hook_script.name in i.message for i in errors if "script" in i.message.lower()):
        console.print("[red]✗[/red] Shell script present and executable: No")
    else:
        console.print("[green]✓[/green] Shell script present and executable")

    if any("handler" in i.message.lower() for i in errors):
        console.print("[red]✗[/red] Python module importable: No")
    else:
        console.print("[green]✓[/green] Python module importable")

    if any("event" in i.message.lower() or "not configured" in i.message.lower() for i in infos):
        console.print("[yellow]![/yellow] All hook events configured: Partially")
    else:
        console.print("[green]✓[/green] All hook events configured")

    console.print()

    # Report errors with specific fix suggestions
    if errors:
        console.print("[bold]Errors:[/bold]")
        for issue in errors:
            console.print(f"  [red]✗[/red] {issue.message}")
            if issue.file_path:
                console.print(f"    [dim]File: {issue.file_path}[/dim]")
            # Provide specific fix command
            if "script" in issue.message.lower():
                console.print(
                    "[dim]    → Run 'cub hooks install --force' to reinstall script[/dim]"
                )
            elif "handler" in issue.message.lower():
                console.print(
                    "[dim]    → Ensure cub is properly installed: pip install -e .[dev][/dim]"
                )

    # Report warnings with suggestions
    if warnings:
        console.print("[bold]Warnings:[/bold]")
        for issue in warnings:
            console.print(f"  [yellow]![/yellow] {issue.message}")
            if issue.file_path:
                console.print(f"    [dim]File: {issue.file_path}[/dim]")
            console.print(
                "[dim]    → Run 'cub hooks install --force' to fix[/dim]"
            )

    # Report infos (unconfigured events)
    if infos:
        console.print("[bold]Info:[/bold]")
        for issue in infos:
            console.print(f"  [dim]ℹ[/dim] {issue.message}")
        console.print(
            "[dim]  → Run 'cub hooks install --force' to configure all events[/dim]"
        )

    # Overall fix suggestion or auto-fix
    if errors or warnings:
        if fix:
            from cub.core.hooks.installer import install_hooks

            console.print("\n[blue]Attempting to auto-fix hook issues...[/blue]")
            result = install_hooks(project_dir, force=True)

            if result.success:
                console.print(f"[green]✓[/green] {result.message}")
                if result.hooks_installed:
                    console.print(f"  Installed hooks: {', '.join(result.hooks_installed)}")
                return 0  # Fixed successfully, no issues remaining
            else:
                console.print(f"[red]✗[/red] Auto-fix failed: {result.message}")
                for issue in result.issues:
                    if issue.severity == "error":
                        console.print(f"  [red]Error:[/red] {issue.message}")
                return len(errors) + len(warnings)
        else:
            console.print(
                "\n[dim]→ Run 'cub hooks install --force' to reinstall hooks[/dim]"
            )

    return len(errors) + len(warnings)


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
    agent: bool = typer.Option(
        False,
        "--agent",
        help="Output structured markdown for LLM consumption",
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
        cub doctor --agent      # Output structured markdown
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        console.print(f"[dim]Fix mode: {fix}[/dim]")
        console.print(f"[dim]Verbose: {verbose}[/dim]")
        console.print(f"[dim]Agent mode: {agent}[/dim]")

    try:
        # Get project root
        project_dir = get_project_root()

        # If agent mode, use collector functions and AgentFormatter
        if agent:
            # Collect diagnostic results
            checks: list[DiagnosticResult] = []

            # Environment checks
            checks.extend(collect_environment_checks())

            # Hooks checks
            checks.extend(collect_hooks_check(project_dir, fix=fix))

            # Stale epics check
            checks.append(collect_stale_epics_check(project_dir, fix=fix))

            # Format and print
            from cub.core.services.agent_format import AgentFormatter

            output = AgentFormatter.format_doctor(checks)
            print(output)

            # Exit with appropriate code based on failures
            failures = [c for c in checks if c.status == "fail"]
            raise typer.Exit(0 if not failures else 1)

        # Otherwise, use Rich console rendering with legacy check functions
        console.print(Panel("[bold]Cub Doctor[/bold] - Diagnostic Tool", expand=False))

        # Run checks (legacy rendering)
        total_issues = 0

        # Check environment
        total_issues += check_environment()

        # Check hooks
        total_issues += check_hooks(project_dir, fix=fix)

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
