"""
Cub CLI - Upgrade command.

Upgrade cub to a new version or reinstall from local source.
"""

import os
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console

from cub import __version__

app = typer.Typer(
    name="upgrade",
    help="Upgrade cub to a newer version",
    no_args_is_help=False,
)

console = Console()


class InstallMethod(Enum):
    """How cub was installed."""

    PIPX = "pipx"
    PIP = "pip"
    EDITABLE = "editable"
    UNKNOWN = "unknown"


def detect_install_method() -> InstallMethod:
    """
    Detect how cub was installed.

    Returns:
        InstallMethod indicating how cub was installed
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
                return InstallMethod.PIPX
        except Exception:
            pass

    # Check if installed in editable mode
    try:
        import cub

        cub_path = Path(cub.__file__).resolve()
        # Editable installs typically have the source in a non-site-packages location
        if "site-packages" not in str(cub_path):
            return InstallMethod.EDITABLE
    except Exception:
        pass

    # Default to pip if we can import cub
    try:
        import cub  # noqa: F811

        return InstallMethod.PIP
    except ImportError:
        pass

    return InstallMethod.UNKNOWN


def is_cub_repo(path: Path) -> bool:
    """
    Check if the given path is a cub repository.

    Args:
        path: Directory path to check

    Returns:
        True if path looks like a cub repository
    """
    # Check for pyproject.toml with cub project
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        if 'name = "cub"' in content:
            return True

    # Check for src/cub directory structure
    src_cub = path / "src" / "cub"
    if src_cub.is_dir() and (src_cub / "__init__.py").exists():
        return True

    return False


def get_local_version(path: Path) -> str | None:
    """
    Get the version from a local cub repository.

    Args:
        path: Path to cub repository

    Returns:
        Version string or None if not found
    """
    # Try pyproject.toml first
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        for line in content.splitlines():
            if line.strip().startswith("version"):
                # Parse version = "X.Y.Z"
                parts = line.split("=", 1)
                if len(parts) == 2:
                    version = parts[1].strip().strip('"').strip("'")
                    return version

    # Try __init__.py
    init_file = path / "src" / "cub" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text()
        for line in content.splitlines():
            if "__version__" in line:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    version = parts[1].strip().strip('"').strip("'")
                    return version

    return None


def run_pipx_install_local(path: Path, force: bool = False) -> bool:
    """
    Install cub from local path using pipx.

    Args:
        path: Path to cub repository
        force: Force reinstall even if same version

    Returns:
        True if installation succeeded
    """
    console.print(f"[dim]Installing from {path}...[/dim]")

    # Use pipx install with --force to reinstall
    cmd = ["pipx", "install", str(path)]
    if force:
        cmd.append("--force")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return True

        # If failed without --force, try with --force
        if not force and "already installed" in result.stderr.lower():
            console.print("[dim]Already installed, using --force...[/dim]")
            cmd.append("--force")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return True

        console.print(f"[red]pipx install failed:[/red]")
        if result.stderr:
            console.print(f"[dim]{result.stderr}[/dim]")
        return False

    except Exception as e:
        console.print(f"[red]Error running pipx: {e}[/red]")
        return False


def run_pip_install_local(path: Path, force: bool = False) -> bool:
    """
    Install cub from local path using pip.

    Args:
        path: Path to cub repository
        force: Force reinstall even if same version

    Returns:
        True if installation succeeded
    """
    console.print(f"[dim]Installing from {path}...[/dim]")

    cmd = [sys.executable, "-m", "pip", "install", str(path)]
    if force:
        cmd.append("--force-reinstall")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return True

        console.print(f"[red]pip install failed:[/red]")
        if result.stderr:
            console.print(f"[dim]{result.stderr}[/dim]")
        return False

    except Exception as e:
        console.print(f"[red]Error running pip: {e}[/red]")
        return False


def run_pip_install_editable(path: Path) -> bool:
    """
    Install cub from local path in editable mode using pip.

    Args:
        path: Path to cub repository

    Returns:
        True if installation succeeded
    """
    console.print(f"[dim]Installing in editable mode from {path}...[/dim]")

    cmd = [sys.executable, "-m", "pip", "install", "-e", str(path)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return True

        console.print(f"[red]pip install -e failed:[/red]")
        if result.stderr:
            console.print(f"[dim]{result.stderr}[/dim]")
        return False

    except Exception as e:
        console.print(f"[red]Error running pip: {e}[/red]")
        return False


@app.callback(invoke_without_command=True)
def upgrade(
    ctx: typer.Context,
    local: bool = typer.Option(
        False,
        "--local",
        "-l",
        help="Install from current directory (must be a cub repository)",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        "-c",
        help="Check for updates without installing",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force reinstall even if same version",
    ),
    version: str | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Install specific version (e.g., 0.23.3)",
    ),
    editable: bool = typer.Option(
        False,
        "--editable",
        "-e",
        help="Install in editable/development mode (implies --local)",
    ),
) -> None:
    """
    Upgrade cub to a newer version.

    By default, upgrades to the latest release. Use --local to install
    from the current directory (for development).

    Examples:
        cub upgrade                  # Upgrade to latest release
        cub upgrade --check          # Check for available updates
        cub upgrade --local          # Install from current directory
        cub upgrade --local --force  # Force reinstall from local
        cub upgrade --editable       # Install in development mode
        cub upgrade --version 0.23.3 # Install specific version
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    # Detect how cub was installed
    install_method = detect_install_method()

    if debug:
        console.print(f"[dim]Current version: {__version__}[/dim]")
        console.print(f"[dim]Install method: {install_method.value}[/dim]")

    console.print(f"[bold]cub[/bold] v{__version__}")
    console.print(f"[dim]Installed via: {install_method.value}[/dim]")
    console.print()

    # Handle --editable (implies --local)
    if editable:
        local = True

    # Handle --local mode
    if local:
        cwd = Path.cwd()

        if not is_cub_repo(cwd):
            console.print("[red]Error: Current directory is not a cub repository[/red]")
            console.print("[dim]Run this from a cloned cub repository, or omit --local[/dim]")
            raise typer.Exit(1)

        local_version = get_local_version(cwd)
        if local_version:
            console.print(f"Local version: v{local_version}")
        else:
            console.print("[yellow]Warning: Could not determine local version[/yellow]")
            local_version = "unknown"

        if check:
            if local_version == __version__:
                console.print("[green]Local version matches installed version[/green]")
            else:
                console.print(
                    f"[yellow]Local version ({local_version}) differs from "
                    f"installed ({__version__})[/yellow]"
                )
            raise typer.Exit(0)

        if local_version == __version__ and not force:
            console.print(f"[green]Already at version v{__version__}[/green]")
            console.print("[dim]Use --force to reinstall[/dim]")
            raise typer.Exit(0)

        # Perform installation
        console.print()

        if editable:
            # Editable mode always uses pip
            success = run_pip_install_editable(cwd)
        elif install_method == InstallMethod.PIPX:
            success = run_pipx_install_local(cwd, force=force)
        else:
            success = run_pip_install_local(cwd, force=force)

        if success:
            console.print()
            console.print(f"[green]Successfully installed cub v{local_version} from local[/green]")
            if editable:
                console.print("[dim]Installed in editable mode - changes take effect immediately[/dim]")
            raise typer.Exit(0)
        else:
            console.print("[red]Installation failed[/red]")
            raise typer.Exit(1)

    # Handle --version flag (install specific version)
    if version:
        console.print(f"Installing version v{version}...")

        if install_method == InstallMethod.PIPX:
            cmd = ["pipx", "install", f"cub=={version}", "--force"]
        else:
            cmd = [sys.executable, "-m", "pip", "install", f"cub=={version}", "--force-reinstall"]

        if debug:
            console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                console.print(f"[green]Successfully installed cub v{version}[/green]")
                raise typer.Exit(0)
            else:
                console.print(f"[red]Failed to install version {version}[/red]")
                if result.stderr:
                    console.print(f"[dim]{result.stderr}[/dim]")
                raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    # Default: upgrade to latest
    if check:
        console.print("[yellow]Checking for updates requires network access...[/yellow]")
        console.print("[dim]This feature is not yet implemented for PyPI releases[/dim]")
        console.print("[dim]Use: pip index versions cub  # to check available versions[/dim]")
        raise typer.Exit(0)

    console.print("Upgrading to latest version...")

    if install_method == InstallMethod.PIPX:
        cmd = ["pipx", "upgrade", "cub"]
        if force:
            cmd = ["pipx", "install", "cub", "--force"]
    elif install_method == InstallMethod.EDITABLE:
        console.print("[yellow]Editable install detected - use --local to update[/yellow]")
        console.print("[dim]Or pull latest changes: git pull[/dim]")
        raise typer.Exit(0)
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "cub"]
        if force:
            cmd.append("--force-reinstall")

    if debug:
        console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            console.print("[green]Upgrade complete![/green]")
            # Show new version
            result2 = subprocess.run(
                [sys.executable, "-c", "from cub import __version__; print(__version__)"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result2.returncode == 0:
                new_version = result2.stdout.strip()
                if new_version != __version__:
                    console.print(f"[green]Updated: v{__version__} -> v{new_version}[/green]")
                else:
                    console.print(f"[dim]Already at latest version (v{__version__})[/dim]")
            raise typer.Exit(0)
        else:
            console.print("[red]Upgrade failed[/red]")
            if result.stderr:
                console.print(f"[dim]{result.stderr}[/dim]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


__all__ = ["app"]
