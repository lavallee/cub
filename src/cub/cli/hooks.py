"""
Hook management commands for Claude Code integration.

Provides commands to install, uninstall, and validate Claude Code hooks
that enable the symbiotic workflow (artifact tracking in direct sessions).
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.hooks.installer import install_hooks, uninstall_hooks, validate_hooks

app = typer.Typer(
    name="hooks",
    help="Manage Claude Code hooks for symbiotic workflow",
    no_args_is_help=True,
)

console = Console()


@app.command(name="install")
def install(
    project_dir: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project directory (default: current directory)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing hook configuration",
    ),
) -> None:
    """
    Install Claude Code hooks for symbiotic workflow.

    This command installs hooks in .claude/settings.json that enable
    cub to track file writes, task claims, and git commits when you
    work directly in Claude Code (outside of 'cub run').

    The hooks capture session events and write them to forensics logs
    in .cub/ledger/forensics/, enabling full context recovery across
    sessions.

    Examples:
        cub hooks install              # Install in current project
        cub hooks install --force      # Reinstall/overwrite existing
        cub hooks install -p ../other  # Install in different project
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    if not project_path.is_dir():
        console.print(f"[red]Error: Not a directory: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Installing hooks in:[/blue] {project_path}")

    result = install_hooks(project_path, force=force)

    if result.success:
        console.print(f"[green]✓[/green] {result.message}")
        if result.hooks_installed:
            console.print(f"  Installed hooks: {', '.join(result.hooks_installed)}")
        if result.settings_file:
            console.print(f"  Settings file: {result.settings_file}")

        # Show warnings if any
        for issue in result.issues:
            if issue.severity == "warning":
                console.print(f"[yellow]⚠[/yellow] {issue.message}")
            elif issue.severity == "info":
                console.print(f"[blue]ℹ[/blue] {issue.message}")

        raise typer.Exit(0)
    else:
        console.print(f"[red]✗[/red] {result.message}")

        # Show all issues
        for issue in result.issues:
            if issue.severity == "error":
                console.print(f"[red]Error:[/red] {issue.message}")
            elif issue.severity == "warning":
                console.print(f"[yellow]Warning:[/yellow] {issue.message}")
            else:
                console.print(f"[blue]Info:[/blue] {issue.message}")

        raise typer.Exit(1)


@app.command(name="uninstall")
def uninstall(
    project_dir: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project directory (default: current directory)",
    ),
) -> None:
    """
    Remove Claude Code hooks configuration.

    This command removes cub hooks from .claude/settings.json while
    preserving other settings and non-cub hooks.

    Note: This does not delete the hook script from .cub/scripts/hooks/,
    only removes the configuration from settings.json.

    Examples:
        cub hooks uninstall         # Remove hooks from current project
        cub hooks uninstall -p ..   # Remove from parent directory
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Removing hooks from:[/blue] {project_path}")

    uninstall_hooks(project_path)

    console.print("[green]✓[/green] Hooks removed from .claude/settings.json")


@app.command(name="check")
def check(
    project_dir: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project directory (default: current directory)",
    ),
) -> None:
    """
    Validate hook installation.

    Checks that:
    - .claude/settings.json exists and is valid JSON
    - Hook script exists and is executable
    - All expected hooks are configured
    - Python handler module is importable

    This is a subset of 'cub doctor' focused on hooks only.

    Examples:
        cub hooks check           # Check current project
        cub hooks check -p ..     # Check parent directory
    """
    project_path = Path(project_dir).resolve()

    if not project_path.exists():
        console.print(f"[red]Error: Directory does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Checking hooks in:[/blue] {project_path}\n")

    issues = validate_hooks(project_path)

    if not issues:
        console.print("[green]✓[/green] All hooks validated successfully")
        raise typer.Exit(0)

    # Group issues by severity
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    # Display issues in a table
    table = Table(title="Hook Validation Issues", show_header=True, header_style="bold")
    table.add_column("Severity", style="white", width=10)
    table.add_column("Issue", style="white")
    table.add_column("Hook/File", style="dim")

    for issue in errors:
        table.add_row(
            "[red]ERROR[/red]",
            issue.message,
            issue.hook_name or issue.file_path or "",
        )

    for issue in warnings:
        table.add_row(
            "[yellow]WARNING[/yellow]",
            issue.message,
            issue.hook_name or issue.file_path or "",
        )

    for issue in infos:
        table.add_row(
            "[blue]INFO[/blue]",
            issue.message,
            issue.hook_name or issue.file_path or "",
        )

    console.print(table)
    console.print()

    # Summary
    if errors:
        console.print(f"[red]✗[/red] Found {len(errors)} error(s)")
        console.print("  Run 'cub hooks install --force' to fix")
        raise typer.Exit(1)
    elif warnings:
        console.print(f"[yellow]⚠[/yellow] Found {len(warnings)} warning(s)")
        raise typer.Exit(0)
    else:
        console.print(f"[blue]ℹ[/blue] Found {len(infos)} info message(s)")
        raise typer.Exit(0)
