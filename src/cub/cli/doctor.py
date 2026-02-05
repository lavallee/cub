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
from cub.core.tasks.jsonl import JsonlBackend
from cub.core.tasks.models import TaskStatus, TaskType
from cub.core.verify import IssueSeverity, VerifyService
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


def collect_tasks_file_check(project_dir: Path, fix: bool = False) -> DiagnosticResult:
    """
    Check if the tasks.jsonl file is valid and attempt repair if corrupted.

    Args:
        project_dir: Project directory path
        fix: If True, attempt to repair corrupted file

    Returns:
        DiagnosticResult with tasks file status
    """
    tasks_file = project_dir / ".cub" / "tasks.jsonl"

    # Check if file exists
    if not tasks_file.exists():
        return DiagnosticResult(
            category="Task State",
            name="Tasks File",
            status="info",
            message="No tasks file found (will be created on first use)",
        )

    # Try to validate the file
    backend = JsonlBackend(project_dir=project_dir)
    is_valid, error_msg = backend.validate_file()

    if is_valid:
        return DiagnosticResult(
            category="Task State",
            name="Tasks File",
            status="pass",
            message="Tasks file is valid",
        )

    # File is corrupted
    if not fix:
        return DiagnosticResult(
            category="Task State",
            name="Tasks File",
            status="fail",
            message=f"Tasks file is corrupted: {error_msg}",
            details=[
                "Common causes: editor auto-formatting, copy-paste with newlines",
                "The file has JSON objects split across multiple lines",
            ],
            fix_command="cub doctor --fix",
        )

    # Attempt repair
    success, repair_msg, tasks_recovered = backend.repair_corrupted_file()

    if success:
        return DiagnosticResult(
            category="Task State",
            name="Tasks File",
            status="pass",
            message=f"Tasks file repaired: {repair_msg}",
            details=[f"Recovered {tasks_recovered} task(s)"],
        )
    else:
        return DiagnosticResult(
            category="Task State",
            name="Tasks File",
            status="fail",
            message=f"Failed to repair tasks file: {repair_msg}",
            details=[
                "Manual repair may be required",
                "Check .cub/tasks.jsonl.bak for the original file",
            ],
        )


def check_tasks_file(project_dir: Path, fix: bool = False) -> int:
    """
    Check if the tasks.jsonl file is valid (legacy Rich output version).

    Args:
        project_dir: Project directory path
        fix: If True, attempt to repair corrupted file

    Returns:
        Number of issues found
    """
    tasks_file = project_dir / ".cub" / "tasks.jsonl"

    if not tasks_file.exists():
        console.print("[dim]ℹ[/dim] No tasks file found (will be created on first use)")
        return 0

    # Try to validate the file
    backend = JsonlBackend(project_dir=project_dir)
    is_valid, error_msg = backend.validate_file()

    if is_valid:
        console.print("[green]✓[/green] Tasks file is valid")
        return 0

    # File is corrupted
    console.print(f"[red]✗[/red] Tasks file is corrupted: {error_msg}")
    console.print("[dim]  Common causes: editor auto-formatting, copy-paste with newlines[/dim]")

    if not fix:
        console.print("[dim]  → Run 'cub doctor --fix' to attempt automatic repair[/dim]")
        return 1

    # Attempt repair
    console.print("\n[blue]Attempting to repair tasks file...[/blue]")
    success, repair_msg, tasks_recovered = backend.repair_corrupted_file()

    if success:
        console.print(f"[green]✓[/green] {repair_msg}")
        return 0
    else:
        console.print(f"[red]✗[/red] Repair failed: {repair_msg}")
        console.print("[dim]  Manual repair may be required[/dim]")
        console.print("[dim]  Check .cub/tasks.jsonl.bak for the original file[/dim]")
        return 1


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


def collect_ledger_health_check(project_dir: Path, fix: bool = False) -> list[DiagnosticResult]:
    """
    Collect ledger health diagnostic checks.

    Args:
        project_dir: Project directory path
        fix: If True, auto-fix simple issues

    Returns:
        List of DiagnosticResult objects for ledger health checks
    """
    results = []

    try:
        service = VerifyService(project_dir)
        result = service.verify(fix=fix, check_ledger=True, check_ids=False, check_counters=False)

        # Convert issues to diagnostic results
        for issue in result.issues:
            # Map severity
            if issue.severity == IssueSeverity.ERROR:
                status = "fail"
            elif issue.severity == IssueSeverity.WARNING:
                status = "warn"
            else:
                status = "info"

            results.append(
                DiagnosticResult(
                    category="Ledger Health",
                    name=issue.category.title(),
                    status=status,
                    message=issue.message,
                    details=[issue.location] if issue.location else [],
                    fix_command=issue.fix_suggestion,
                )
            )

        # If no issues found, add a passing result
        if not result.issues:
            results.append(
                DiagnosticResult(
                    category="Ledger Health",
                    name="Ledger Consistency",
                    status="pass",
                    message="Ledger is consistent and healthy",
                )
            )

    except Exception as e:
        results.append(
            DiagnosticResult(
                category="Ledger Health",
                name="Ledger Check",
                status="fail",
                message=f"Failed to check ledger health: {e}",
            )
        )

    return results


def collect_id_integrity_check(project_dir: Path, fix: bool = False) -> list[DiagnosticResult]:
    """
    Collect ID integrity diagnostic checks.

    Args:
        project_dir: Project directory path
        fix: If True, auto-fix simple issues

    Returns:
        List of DiagnosticResult objects for ID integrity checks
    """
    results = []

    try:
        service = VerifyService(project_dir)
        result = service.verify(fix=fix, check_ledger=False, check_ids=True, check_counters=False)

        # Convert issues to diagnostic results
        for issue in result.issues:
            # Map severity
            if issue.severity == IssueSeverity.ERROR:
                status = "fail"
            elif issue.severity == IssueSeverity.WARNING:
                status = "warn"
            else:
                status = "info"

            results.append(
                DiagnosticResult(
                    category="ID System",
                    name=issue.category.upper(),
                    status=status,
                    message=issue.message,
                    details=[issue.location] if issue.location else [],
                    fix_command=issue.fix_suggestion,
                )
            )

        # If no issues found, add a passing result
        if not result.issues:
            results.append(
                DiagnosticResult(
                    category="ID System",
                    name="ID Integrity",
                    status="pass",
                    message="All task IDs are valid and consistent",
                )
            )

    except Exception as e:
        results.append(
            DiagnosticResult(
                category="ID System",
                name="ID Check",
                status="fail",
                message=f"Failed to check ID integrity: {e}",
            )
        )

    return results


def collect_counter_sync_check(project_dir: Path, fix: bool = False) -> list[DiagnosticResult]:
    """
    Collect counter sync diagnostic checks.

    Args:
        project_dir: Project directory path
        fix: If True, auto-fix simple issues

    Returns:
        List of DiagnosticResult objects for counter sync checks
    """
    results = []

    try:
        service = VerifyService(project_dir)
        result = service.verify(fix=fix, check_ledger=False, check_ids=False, check_counters=True)

        # Convert issues to diagnostic results
        for issue in result.issues:
            # Map severity
            if issue.severity == IssueSeverity.ERROR:
                status = "fail"
            elif issue.severity == IssueSeverity.WARNING:
                status = "warn"
            else:
                status = "info"

            results.append(
                DiagnosticResult(
                    category="Counter Sync",
                    name=issue.category.title(),
                    status=status,
                    message=issue.message,
                    details=[issue.location] if issue.location else [],
                    fix_command=issue.fix_suggestion,
                )
            )

        # If no issues found, add a passing result
        if not result.issues:
            results.append(
                DiagnosticResult(
                    category="Counter Sync",
                    name="Counter Sync",
                    status="pass",
                    message="Counters are in sync with actual usage",
                )
            )

    except Exception as e:
        results.append(
            DiagnosticResult(
                category="Counter Sync",
                name="Counter Check",
                status="fail",
                message=f"Failed to check counter sync: {e}",
            )
        )

    return results


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


def check_ledger_health(project_dir: Path, fix: bool = False) -> int:
    """
    Check ledger health (legacy Rich output version).

    Args:
        project_dir: Project directory path
        fix: If True, attempt to auto-fix simple issues

    Returns:
        Number of issues found
    """
    try:
        service = VerifyService(project_dir)
        result = service.verify(fix=fix, check_ledger=True, check_ids=False, check_counters=False)

        if not result.issues:
            console.print("[green]✓[/green] Ledger is consistent and healthy")
            return 0

        # Report issues
        errors = [i for i in result.issues if i.severity == IssueSeverity.ERROR]
        warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
        infos = [i for i in result.issues if i.severity == IssueSeverity.INFO]

        for issue in errors:
            console.print(f"[red]✗[/red] {issue.message}")
            if issue.location:
                console.print(f"[dim]  Location: {issue.location}[/dim]")
            if issue.fix_suggestion:
                console.print(f"[dim]  → {issue.fix_suggestion}[/dim]")

        for issue in warnings:
            console.print(f"[yellow]![/yellow] {issue.message}")
            if issue.location:
                console.print(f"[dim]  Location: {issue.location}[/dim]")
            if issue.fix_suggestion:
                console.print(f"[dim]  → {issue.fix_suggestion}[/dim]")

        if not errors and not warnings and infos:
            console.print(f"[blue]ℹ[/blue] {len(infos)} informational message(s)")

        return len(errors) + len(warnings)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to check ledger health: {e}")
        return 1


def check_id_integrity(project_dir: Path, fix: bool = False) -> int:
    """
    Check ID integrity (legacy Rich output version).

    Args:
        project_dir: Project directory path
        fix: If True, attempt to auto-fix simple issues

    Returns:
        Number of issues found
    """
    try:
        service = VerifyService(project_dir)
        result = service.verify(fix=fix, check_ledger=False, check_ids=True, check_counters=False)

        if not result.issues:
            console.print("[green]✓[/green] All task IDs are valid and consistent")
            return 0

        # Report issues
        errors = [i for i in result.issues if i.severity == IssueSeverity.ERROR]
        warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
        infos = [i for i in result.issues if i.severity == IssueSeverity.INFO]

        for issue in errors:
            console.print(f"[red]✗[/red] {issue.message}")
            if issue.location:
                console.print(f"[dim]  Location: {issue.location}[/dim]")
            if issue.fix_suggestion:
                console.print(f"[dim]  → {issue.fix_suggestion}[/dim]")

        for issue in warnings:
            console.print(f"[yellow]![/yellow] {issue.message}")
            if issue.location:
                console.print(f"[dim]  Location: {issue.location}[/dim]")
            if issue.fix_suggestion:
                console.print(f"[dim]  → {issue.fix_suggestion}[/dim]")

        if not errors and not warnings and infos:
            console.print(f"[blue]ℹ[/blue] {len(infos)} informational message(s)")

        return len(errors) + len(warnings)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to check ID integrity: {e}")
        return 1


def check_counter_sync(project_dir: Path, fix: bool = False) -> int:
    """
    Check counter sync status (legacy Rich output version).

    Args:
        project_dir: Project directory path
        fix: If True, attempt to auto-fix simple issues

    Returns:
        Number of issues found
    """
    try:
        service = VerifyService(project_dir)
        result = service.verify(fix=fix, check_ledger=False, check_ids=False, check_counters=True)

        if not result.issues:
            console.print("[green]✓[/green] Counters are in sync with actual usage")
            return 0

        # Report issues
        errors = [i for i in result.issues if i.severity == IssueSeverity.ERROR]
        warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
        infos = [i for i in result.issues if i.severity == IssueSeverity.INFO]

        for issue in errors:
            console.print(f"[red]✗[/red] {issue.message}")
            if issue.location:
                console.print(f"[dim]  Location: {issue.location}[/dim]")
            if issue.fix_suggestion:
                console.print(f"[dim]  → {issue.fix_suggestion}[/dim]")

        for issue in warnings:
            console.print(f"[yellow]![/yellow] {issue.message}")
            if issue.location:
                console.print(f"[dim]  Location: {issue.location}[/dim]")
            if issue.fix_suggestion:
                console.print(f"[dim]  → {issue.fix_suggestion}[/dim]")

        if not errors and not warnings and infos:
            console.print(f"[blue]ℹ[/blue] {len(infos)} informational message(s)")

        return len(errors) + len(warnings)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to check counter sync: {e}")
        return 1


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
    - Task state: corrupted tasks file, stale epics
    - Ledger health: consistency, file structure, entry integrity
    - ID system: format validation, duplicates, cross-references
    - Counter sync: counter values match actual usage

    Fix Actions:
    --fix will:
    - Repair corrupted tasks.jsonl file (rejoins split JSON lines)
    - Auto-close stale epics with "Auto-closed: all subtasks complete"
    - Auto-fix simple ledger, ID, and counter issues

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

            # Tasks file check (run before stale epics since stale epics needs valid file)
            checks.append(collect_tasks_file_check(project_dir, fix=fix))

            # Stale epics check (only if tasks file is valid)
            tasks_file_ok = all(
                c.status != "fail"
                for c in checks
                if c.name == "Tasks File"
            )
            if tasks_file_ok:
                checks.append(collect_stale_epics_check(project_dir, fix=fix))
            else:
                checks.append(
                    DiagnosticResult(
                        category="Task State",
                        name="Stale Epics",
                        status="info",
                        message="Skipped (tasks file is corrupted)",
                    )
                )

            # Ledger health checks
            checks.extend(collect_ledger_health_check(project_dir, fix=fix))

            # ID integrity checks
            checks.extend(collect_id_integrity_check(project_dir, fix=fix))

            # Counter sync checks
            checks.extend(collect_counter_sync_check(project_dir, fix=fix))

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

        # Check tasks file
        console.print("\n[bold]Tasks File:[/bold]")
        tasks_file_issues = check_tasks_file(project_dir, fix=fix)
        total_issues += tasks_file_issues

        # Check stale epics (only if tasks file is valid)
        console.print("\n[bold]Stale Epics:[/bold]")
        if tasks_file_issues == 0:
            stale_count, fixed_epics = check_stale_epics(project_dir, fix=fix)
            total_issues += stale_count
        else:
            console.print("[dim]ℹ[/dim] Skipped (tasks file is corrupted)")

        # Check ledger health
        console.print("\n[bold]Ledger Health:[/bold]")
        total_issues += check_ledger_health(project_dir, fix=fix)

        # Check ID integrity
        console.print("\n[bold]ID System:[/bold]")
        total_issues += check_id_integrity(project_dir, fix=fix)

        # Check counter sync
        console.print("\n[bold]Counter Sync:[/bold]")
        total_issues += check_counter_sync(project_dir, fix=fix)

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
