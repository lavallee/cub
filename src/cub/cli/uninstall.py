"""
Cub CLI - Uninstall command.

Uninstall cub and optionally clean up configuration files.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from cub import __version__

app = typer.Typer(
    name="uninstall",
    help="Uninstall cub from your system",
    no_args_is_help=False,
)

console = Console()


def detect_install_method() -> str:
    """
    Detect how cub was installed.

    Returns:
        String indicating install method: "pipx", "pip", "editable", or "unknown"
    """
    # Check if pipx is available and has cub installed
    if shutil.which("pipx"):
        try:
            result = subprocess.run(
                ["pipx", "list", "--short"],
                capture_output=True,
                text=True,
                check=False,
            )
            if "cub" in result.stdout:
                return "pipx"
        except Exception:
            pass

    # Check if installed in editable mode
    try:
        import cub

        cub_path = Path(cub.__file__).resolve()
        # Editable installs typically have the source in a non-site-packages location
        if "site-packages" not in str(cub_path):
            return "editable"
    except Exception:
        pass

    # Default to pip if we can import cub
    try:
        import cub  # noqa: F811

        return "pip"
    except ImportError:
        pass

    return "unknown"


def get_config_paths() -> list[Path]:
    """
    Get paths to cub configuration directories.

    Returns:
        List of paths that may contain cub configuration
    """
    paths = []

    # XDG config
    xdg_config = Path.home() / ".config" / "cub"
    if xdg_config.exists():
        paths.append(xdg_config)

    # XDG data
    xdg_data = Path.home() / ".local" / "share" / "cub"
    if xdg_data.exists():
        paths.append(xdg_data)

    # Legacy paths
    legacy_config = Path.home() / ".cub"
    if legacy_config.exists():
        paths.append(legacy_config)

    return paths


def run_pipx_uninstall() -> bool:
    """
    Uninstall cub using pipx.

    Returns:
        True if uninstall succeeded
    """
    console.print("[dim]Uninstalling with pipx...[/dim]")

    try:
        result = subprocess.run(
            ["pipx", "uninstall", "cub"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return True

        console.print(f"[red]pipx uninstall failed:[/red]")
        if result.stderr:
            console.print(f"[dim]{result.stderr}[/dim]")
        return False

    except Exception as e:
        console.print(f"[red]Error running pipx: {e}[/red]")
        return False


def run_pip_uninstall() -> bool:
    """
    Uninstall cub using pip.

    Returns:
        True if uninstall succeeded
    """
    console.print("[dim]Uninstalling with pip...[/dim]")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "cub", "-y"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return True

        console.print(f"[red]pip uninstall failed:[/red]")
        if result.stderr:
            console.print(f"[dim]{result.stderr}[/dim]")
        return False

    except Exception as e:
        console.print(f"[red]Error running pip: {e}[/red]")
        return False


@app.callback(invoke_without_command=True)
def uninstall(
    ctx: typer.Context,
    clean: bool = typer.Option(
        False,
        "--clean",
        "-c",
        help="Also remove configuration files (~/.config/cub, ~/.local/share/cub)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompts",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without making changes",
    ),
) -> None:
    """
    Uninstall cub from your system.

    By default, only removes the cub package. Use --clean to also remove
    configuration files and data directories.

    Examples:
        cub uninstall              # Uninstall cub package
        cub uninstall --clean      # Also remove config files
        cub uninstall --dry-run    # Show what would be done
    """
    install_method = detect_install_method()

    console.print(f"[bold]cub[/bold] v{__version__}")
    console.print(f"[dim]Installed via: {install_method}[/dim]")
    console.print()

    if install_method == "unknown":
        console.print("[red]Error: Could not detect cub installation[/red]")
        console.print("[dim]cub may not be installed, or was installed in an unknown way[/dim]")
        raise typer.Exit(1)

    if install_method == "editable":
        console.print("[yellow]Editable install detected[/yellow]")
        console.print("[dim]For editable installs, simply remove the source directory[/dim]")
        console.print("[dim]or run: pip uninstall cub[/dim]")
        if not force:
            raise typer.Exit(0)

    # Show what will be done
    config_paths = get_config_paths()

    console.print("[bold]Actions to perform:[/bold]")
    if install_method == "pipx":
        console.print("  - Run: pipx uninstall cub")
    else:
        console.print("  - Run: pip uninstall cub")

    if clean and config_paths:
        console.print("  - Remove configuration directories:")
        for path in config_paths:
            console.print(f"    - {path}")
    elif clean:
        console.print("  - [dim]No configuration directories found[/dim]")

    console.print()

    if dry_run:
        console.print("[yellow]Dry run - no changes made[/yellow]")
        raise typer.Exit(0)

    # Confirm unless --force
    if not force:
        confirm = typer.confirm("Proceed with uninstall?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    console.print()

    # Uninstall package
    if install_method == "pipx":
        success = run_pipx_uninstall()
    else:
        success = run_pip_uninstall()

    if not success:
        console.print("[red]Package uninstall failed[/red]")
        raise typer.Exit(1)

    console.print("[green]Package uninstalled successfully[/green]")

    # Clean config if requested
    if clean and config_paths:
        console.print()
        console.print("[dim]Removing configuration directories...[/dim]")
        for path in config_paths:
            try:
                shutil.rmtree(path)
                console.print(f"  [green]Removed:[/green] {path}")
            except Exception as e:
                console.print(f"  [red]Failed to remove {path}:[/red] {e}")

    console.print()
    console.print("[green]Uninstall complete![/green]")
    raise typer.Exit(0)


__all__ = ["app"]
