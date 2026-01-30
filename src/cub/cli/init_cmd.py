"""
Init command implementation for cub project initialization.

This module provides the native Python ``cub init`` command, handling:
- Project type detection (python, node, react, nextjs, go, rust, generic)
- Task backend initialization (beads or jsonl)
- Template copying (PROMPT.md, .cub.json, commands/)
- .gitignore updating with cub patterns
- Global configuration setup (``cub init --global``)
- Instruction file generation (AGENTS.md, CLAUDE.md)
- Claude Code hook installation
- Statusline installation
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from cub.cli.map import generate_map
from cub.core.config.loader import load_config
from cub.core.constitution import ensure_constitution
from cub.core.hooks.installer import install_hooks
from cub.core.instructions import (
    UpsertAction,
    generate_agents_md,
    generate_claude_md,
    upsert_managed_section,
)

console = Console()

# Patterns to add to .gitignore for cub projects
GITIGNORE_PATTERNS = [
    "# cub",
    ".cub/ledger/forensics/",
    ".cub/dashboard.db",
    ".cub/map.md",
]


# ---------------------------------------------------------------------------
# Helper: project config I/O
# ---------------------------------------------------------------------------


def _load_project_config(project_dir: Path) -> dict[str, Any] | None:
    """Load project configuration from .cub/config.json."""
    config_file = project_dir / ".cub" / "config.json"
    if not config_file.exists():
        return None
    try:
        with open(config_file, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data
    except (json.JSONDecodeError, OSError):
        return None


def _save_project_config(project_dir: Path, config: dict[str, Any]) -> None:
    """Save project configuration to .cub/config.json."""
    config_dir = project_dir / ".cub"
    config_file = config_dir / "config.json"
    config_dir.mkdir(parents=True, exist_ok=True)
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
    except OSError as e:
        console.print(f"[yellow]Warning: Could not write config: {e}[/yellow]")


# ---------------------------------------------------------------------------
# Helper: dev mode detection
# ---------------------------------------------------------------------------


def _detect_dev_mode(project_dir: Path) -> bool:
    """Detect if this is a development install of cub."""
    pyproject_path = project_dir / "pyproject.toml"
    git_dir = project_dir / ".git"

    if not (pyproject_path.exists() and git_dir.exists()):
        return False

    try:
        import tomllib  # type: ignore[import-not-found]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            return False

    try:
        with open(pyproject_path, "rb") as f:
            pyproject: dict[str, Any] = tomllib.load(f)
            return bool(pyproject.get("project", {}).get("name") == "cub")
    except Exception:
        return False


def _ensure_dev_mode_config(project_dir: Path, dev_mode_override: bool | None = None) -> None:
    """Ensure dev_mode is set in .cub/config.json."""
    config = _load_project_config(project_dir) or {}

    if dev_mode_override is not None:
        dev_mode = dev_mode_override
    else:
        dev_mode = _detect_dev_mode(project_dir)

    current_dev_mode = config.get("dev_mode", False)
    if current_dev_mode != dev_mode:
        config["dev_mode"] = dev_mode
        _save_project_config(project_dir, config)

        if dev_mode:
            console.print(
                "[cyan]i[/cyan] Development mode enabled (hooks will use local uv installation)"
            )
        else:
            console.print(
                "[cyan]i[/cyan] Production mode (hooks will use installed cub-hooks command)"
            )


# ---------------------------------------------------------------------------
# Helper: templates directory
# ---------------------------------------------------------------------------


def _get_templates_dir() -> Path:
    """Locate the cub templates directory."""
    import cub

    cub_path = Path(cub.__file__).parent
    # Try src layout first (editable install)
    templates_dir = cub_path.parent.parent / "templates"
    if templates_dir.is_dir():
        return templates_dir
    # Try package layout (pip install)
    templates_dir = cub_path / "templates"
    if templates_dir.is_dir():
        return templates_dir
    raise FileNotFoundError("Could not locate cub templates directory")


def _ensure_runloop(project_dir: Path, force: bool = False) -> None:
    """Copy runloop.md template into .cub/ if missing or force=True."""
    cub_dir = project_dir / ".cub"
    cub_dir.mkdir(exist_ok=True)
    target_path = cub_dir / "runloop.md"

    templates_dir = _get_templates_dir()
    source_path = templates_dir / "runloop.md"
    if not source_path.exists():
        raise FileNotFoundError(f"Template not found: {source_path}")

    if not target_path.exists() or force:
        shutil.copy2(source_path, target_path)


# ---------------------------------------------------------------------------
# Project type detection
# ---------------------------------------------------------------------------


def detect_project_type(project_dir: Path) -> str:
    """
    Detect the project type by inspecting marker files.

    Returns one of: nextjs, react, node, python, go, rust, generic.
    """
    # Node-based projects
    pkg_json = project_dir / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json, encoding="utf-8") as f:
                pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                return "nextjs"
            if "react" in deps:
                return "react"
        except (json.JSONDecodeError, OSError):
            pass
        return "node"

    # Python
    if (project_dir / "pyproject.toml").exists() or (project_dir / "requirements.txt").exists():
        return "python"

    # Go
    if (project_dir / "go.mod").exists():
        return "go"

    # Rust
    if (project_dir / "Cargo.toml").exists():
        return "rust"

    return "generic"


# ---------------------------------------------------------------------------
# Backend detection / initialization
# ---------------------------------------------------------------------------


def detect_backend(explicit: str | None = None) -> str:
    """
    Determine which task backend to use.

    Priority: explicit arg > CUB_BACKEND env var > auto-detect (bd in PATH).
    """
    if explicit:
        return explicit

    env_backend = os.environ.get("CUB_BACKEND")
    if env_backend:
        return env_backend

    if shutil.which("bd"):
        return "beads"

    return "jsonl"


def _init_backend(project_dir: Path, backend: str) -> None:
    """Initialize the chosen task backend."""
    if backend == "beads":
        bd_path = shutil.which("bd")
        if bd_path:
            subprocess.run(
                [bd_path, "init", "--stealth"],
                cwd=project_dir,
                capture_output=True,
                check=False,
            )
            console.print("[green]v[/green] Initialized beads backend")
        else:
            console.print("[yellow]Warning: bd not found, skipping beads init[/yellow]")
    elif backend == "jsonl":
        tasks_file = project_dir / ".cub" / "tasks.jsonl"
        tasks_file.parent.mkdir(parents=True, exist_ok=True)
        if not tasks_file.exists():
            tasks_file.touch()
        console.print("[green]v[/green] Initialized JSONL backend")
    else:
        console.print(f"[yellow]Warning: Unknown backend '{backend}', skipping[/yellow]")


# ---------------------------------------------------------------------------
# Template / file setup helpers
# ---------------------------------------------------------------------------


def _ensure_prompt_md(project_dir: Path, backend: str, force: bool = False) -> None:
    """Copy and customize PROMPT.md template for the project."""
    target = project_dir / ".cub" / "prompt.md"
    if target.exists() and not force:
        return

    templates_dir = _get_templates_dir()
    source = templates_dir / "PROMPT.md"
    if not source.exists():
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text(encoding="utf-8")

    # Customize backend-specific closure instructions
    if backend == "beads":
        content = content.replace(
            "{{TASK_CLOSURE}}",
            'bd close <task-id> -r "reason"',
        )
    else:
        content = content.replace(
            "{{TASK_CLOSURE}}",
            'cub task close <task-id> -r "reason"',
        )

    target.write_text(content, encoding="utf-8")


def _install_claude_commands(project_dir: Path) -> int:
    """Copy command reference files from templates/commands/ to .claude/commands/."""
    templates_dir = _get_templates_dir()
    source_dir = templates_dir / "commands"
    if not source_dir.is_dir():
        return 0

    target_dir = project_dir / ".claude" / "commands"
    target_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for src_file in sorted(source_dir.glob("*.md")):
        dst = target_dir / src_file.name
        if not dst.exists():
            shutil.copy2(src_file, dst)
            count += 1

    return count


def _update_gitignore(project_dir: Path) -> None:
    """Append cub-specific patterns to .gitignore if not already present."""
    gitignore = project_dir / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""

    missing = [p for p in GITIGNORE_PATTERNS if p not in existing]
    if not missing:
        return

    with open(gitignore, "a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write("\n".join(missing) + "\n")


def _ensure_specs_dir(project_dir: Path) -> None:
    """Create specs/ directory if it doesn't exist."""
    specs_dir = project_dir / "specs"
    specs_dir.mkdir(exist_ok=True)


def _ensure_cub_json(project_dir: Path, force: bool = False) -> None:
    """Copy .cub.json template if not already present."""
    target = project_dir / ".cub.json"
    if target.exists() and not force:
        return

    templates_dir = _get_templates_dir()
    source = templates_dir / ".cub.json"
    if source.exists():
        shutil.copy2(source, target)


# ---------------------------------------------------------------------------
# Global init
# ---------------------------------------------------------------------------


def _init_global(force: bool = False) -> None:
    """Set up global cub configuration in XDG config directory."""
    xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    global_dir = xdg_config / "cub"
    global_config = global_dir / "config.json"

    global_dir.mkdir(parents=True, exist_ok=True)

    if not global_config.exists() or force:
        default_config: dict[str, Any] = {
            "harness": "auto",
            "budget": {
                "max_tokens_per_task": 500000,
            },
            "state": {
                "require_clean": True,
                "run_tests": True,
            },
            "loop": {
                "max_iterations": 100,
                "on_task_failure": "stop",
            },
        }
        with open(global_config, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
            f.write("\n")
        console.print(f"[green]v[/green] Created global config at {global_config}")
    else:
        console.print(f"[green]v[/green] Global config already exists at {global_config}")

    # Ensure hooks directory
    hooks_dir = global_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    console.print("[green]v[/green] Global cub setup complete")


# ---------------------------------------------------------------------------
# generate_instruction_files (existing, preserved)
# ---------------------------------------------------------------------------


def generate_instruction_files(
    project_dir: Path,
    force: bool = False,
    install_hooks_flag: bool = False,
    dev_mode_override: bool | None = None,
) -> None:
    """
    Generate AGENTS.md and CLAUDE.md instruction files at project root.

    Uses the managed section upsert engine to non-destructively update
    instruction files. Also ensures constitution and runloop are in place.
    """
    # Ensure dev_mode is configured
    _ensure_dev_mode_config(project_dir, dev_mode_override)

    try:
        config = load_config(project_dir)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        console.print("[yellow]Using default configuration[/yellow]")
        from cub.core.config.models import (
            CircuitBreakerConfig,
            CubConfig,
            HarnessConfig,
        )

        config = CubConfig(
            harness=HarnessConfig(name="auto", priority=["claude", "codex"]),
            circuit_breaker=CircuitBreakerConfig(timeout_minutes=30, enabled=True),
        )

    # Ensure constitution exists
    try:
        ensure_constitution(project_dir, force=force)
        console.print("[green]v[/green] Constitution ready")
    except Exception as e:
        console.print(f"[red]Error ensuring constitution: {e}[/red]")

    # Copy runloop template
    try:
        _ensure_runloop(project_dir, force=force)
        console.print("[green]v[/green] Runloop ready")
    except Exception as e:
        console.print(f"[red]Error ensuring runloop: {e}[/red]")

    # Generate managed section content for AGENTS.md
    try:
        agents_content = generate_agents_md(project_dir, config)
        agents_path = project_dir / "AGENTS.md"
        result = upsert_managed_section(agents_path, agents_content, version=1)

        if result.action == UpsertAction.CREATED:
            console.print("[green]v[/green] Created AGENTS.md")
        elif result.action == UpsertAction.APPENDED:
            console.print("[green]v[/green] Added managed section to AGENTS.md")
        elif result.action == UpsertAction.REPLACED:
            console.print("[green]v[/green] Updated managed section in AGENTS.md")

        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning: {warning}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error creating AGENTS.md: {e}[/red]")

    # Generate managed section content for CLAUDE.md
    try:
        claude_content = generate_claude_md(project_dir, config)
        claude_path = project_dir / "CLAUDE.md"
        result = upsert_managed_section(claude_path, claude_content, version=1)

        if result.action == UpsertAction.CREATED:
            console.print("[green]v[/green] Created CLAUDE.md")
        elif result.action == UpsertAction.APPENDED:
            console.print("[green]v[/green] Added managed section to CLAUDE.md")
        elif result.action == UpsertAction.REPLACED:
            console.print("[green]v[/green] Updated managed section in CLAUDE.md")

        if result.warnings:
            for warning in result.warnings:
                console.print(f"[yellow]Warning: {warning}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error creating CLAUDE.md: {e}[/red]")

    # Generate project map
    try:
        map_content = generate_map(project_dir, token_budget=4096, max_depth=4)
        map_path = project_dir / ".cub" / "map.md"
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(map_content, encoding="utf-8")
        console.print("[green]v[/green] Generated project map at .cub/map.md")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not generate map: {e}[/yellow]")

    # Install hooks if requested
    if install_hooks_flag:
        try:
            hook_result = install_hooks(project_dir, force=force)
            if hook_result.success:
                if hook_result.hooks_installed:
                    console.print(
                        f"[green]v[/green] Installed Claude Code hooks: "
                        f"{', '.join(hook_result.hooks_installed)}"
                    )
                else:
                    console.print("[green]v[/green] Claude Code hooks already installed")
                if hook_result.issues:
                    for issue in hook_result.issues:
                        if issue.severity == "warning":
                            console.print(f"[yellow]Warning: {issue.message}[/yellow]")
            else:
                console.print(f"[red]x[/red] Failed to install hooks: {hook_result.message}")
                if hook_result.issues:
                    for issue in hook_result.issues:
                        console.print(f"  [red]o[/red] {issue.message}")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not install hooks: {e}[/yellow]")


# ---------------------------------------------------------------------------
# Project init orchestrator
# ---------------------------------------------------------------------------


def init_project(
    project_dir: Path,
    force: bool = False,
    project_type: str | None = None,
    backend: str | None = None,
    interactive: bool = False,
    install_hooks_flag: bool = True,
    dev_mode_override: bool | None = None,
    quiet: bool = False,
) -> None:
    """
    Full project initialization sequence.

    This is the main entry point for ``cub init`` (project-level).
    It orchestrates all initialization steps in order.
    """
    project_dir = project_dir.resolve()

    if not project_dir.exists():
        console.print(f"[red]Error: Directory does not exist: {project_dir}[/red]")
        raise typer.Exit(1)

    if not project_dir.is_dir():
        console.print(f"[red]Error: Not a directory: {project_dir}[/red]")
        raise typer.Exit(1)

    project_name = project_dir.name
    console.print(f"[bold]Initializing cub in {project_name}[/bold]\n")

    # 1. Detect project type
    detected_type = project_type or detect_project_type(project_dir)
    console.print(f"[green]v[/green] Detected project type: {detected_type}")

    # 2. Detect and initialize backend
    chosen_backend = detect_backend(backend)
    _init_backend(project_dir, chosen_backend)

    # 3. Create specs/ directory
    _ensure_specs_dir(project_dir)

    # 4. Copy .cub.json template
    _ensure_cub_json(project_dir, force=force)

    # 5. Copy PROMPT.md template
    _ensure_prompt_md(project_dir, chosen_backend, force=force)

    # 6. Install Claude Code commands/skills
    cmd_count = _install_claude_commands(project_dir)
    if cmd_count > 0:
        console.print(f"[green]v[/green] Installed {cmd_count} Claude Code commands")

    # 7. Update .gitignore
    _update_gitignore(project_dir)

    # 8. Generate instruction files (constitution, runloop, AGENTS.md, CLAUDE.md,
    #    map, hooks)
    generate_instruction_files(
        project_dir,
        force=force,
        install_hooks_flag=install_hooks_flag,
        dev_mode_override=dev_mode_override,
    )

    # 9. Install statusline
    try:
        from cub.cli.statusline import install_statusline

        if install_statusline(project_dir, force=force):
            console.print("[green]v[/green] Installed Claude Code statusline")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not install statusline: {e}[/yellow]")

    # 10. Fire post-init hooks
    try:
        from cub.utils.hooks import HookContext, run_hooks

        context = HookContext(
            hook_name="post-init",
            project_dir=project_dir,
            init_type="project",
        )
        run_hooks("post-init", context, project_dir)
    except Exception:
        pass  # Non-critical

    console.print(f"\n[green bold]cub initialized in {project_name}[/green bold]")

    if not quiet:
        from cub.cli.guidance import render_guidance
        from cub.core.guidance import CommandType

        render_guidance(console, CommandType.INIT)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(
    project_dir: str = typer.Argument(
        ".",
        help="Project directory to initialize (default: current directory)",
    ),
    global_: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Set up global cub configuration",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files",
    ),
    hooks: bool = typer.Option(
        True,
        "--hooks/--no-hooks",
        help="Install Claude Code hooks (default: on)",
    ),
    dev_mode: bool | None = typer.Option(
        None,
        "--dev-mode/--no-dev-mode",
        help="Enable/disable dev mode (auto-detected if not specified)",
    ),
    project_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Project type (python, node, react, nextjs, go, rust, generic)",
    ),
    backend: str | None = typer.Option(
        None,
        "--backend",
        "-b",
        help="Task backend (beads, jsonl)",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Interactive mode with prompts",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress post-command guidance messages",
    ),
) -> None:
    """
    Initialize cub in a project or globally.

    Sets up project configuration, task backend, instruction files,
    Claude Code hooks, and statusline. Run this once in a new project
    to get started with cub.

    Use --global to set up user-level configuration (~/.config/cub/).

    Examples:
        cub init                    # Initialize current directory
        cub init /path/to/project   # Initialize a specific directory
        cub init --global           # Set up global configuration
        cub init --no-hooks         # Skip hook installation
        cub init --backend beads    # Force beads backend
        cub init --type python      # Force Python project type
    """
    if global_:
        _init_global(force=force)
        return

    project_path = Path(project_dir).resolve()

    init_project(
        project_path,
        force=force,
        project_type=project_type,
        backend=backend,
        interactive=interactive,
        install_hooks_flag=hooks,
        dev_mode_override=dev_mode,
        quiet=quiet,
    )


if __name__ == "__main__":
    typer.run(main)
