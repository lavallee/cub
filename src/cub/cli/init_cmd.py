"""
Init command implementation for cub project initialization.

This module provides the native Python ``cub init`` command, handling:
- Project type detection (python, node, react, nextjs, go, rust, generic)
- Task backend initialization (beads or jsonl)
- Template copying (runloop.md, prompt.md, .cub.json, commands/)
- .gitignore updating with cub patterns
- Global configuration setup (``cub init --global``)
- Instruction file generation (CLAUDE.md with AGENTS.md as symlink)
- Claude Code hook installation
- Statusline installation

System Prompt Architecture:
- runloop.md is the system-managed prompt template (immutable by features)
- prompt.md is user-customizable and preserved across re-init (unless --force)
- Plan-level context is injected at runtime, not persisted globally
- See prompt_builder.py for context composition logic

Note: CLAUDE.md is the canonical instruction file. AGENTS.md is created as a
symlink to CLAUDE.md to ensure consistency without duplication.
"""

import hashlib
import json
import logging
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
    create_agents_symlink,
    generate_claude_md,
    upsert_managed_section,
)

console = Console()
logger = logging.getLogger(__name__)

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


def _generate_project_id(project_dir: Path) -> str:
    """
    Generate a unique project_id from the project directory name.

    Uses the first 3 lowercase characters of the directory name.
    Falls back to "cub" if the name is too short.

    Args:
        project_dir: Project directory path

    Returns:
        A 3-character project_id prefix
    """
    name = project_dir.name.lower()
    # Strip common prefixes that might cause collisions
    if name.startswith("cub-"):
        # Use the part after "cub-" for better uniqueness
        name = name[4:]
    prefix = name[:3]
    return prefix if prefix else "cub"


def _ensure_project_id(project_dir: Path, project_id: str | None = None) -> str:
    """
    Ensure project_id is set in .cub/config.json.

    If project_id is not already set, generates one from the directory name
    or uses the provided value.

    Args:
        project_dir: Project directory path
        project_id: Optional explicit project_id to use

    Returns:
        The project_id that was set or already exists
    """
    config = _load_project_config(project_dir) or {}

    # If already set and no override provided, keep existing
    if config.get("project_id") and project_id is None:
        return str(config["project_id"])

    # Generate or use provided
    final_id = project_id if project_id else _generate_project_id(project_dir)
    config["project_id"] = final_id
    _save_project_config(project_dir, config)

    return final_id


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


def _file_hash(path: Path) -> str:
    """Calculate MD5 hash of a file for content comparison."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def _ensure_prompt_md(project_dir: Path, force: bool = False) -> str:
    """
    Ensure prompt.md exists in .cub/ directory, preserving user modifications.

    This function handles the user-customizable prompt.md file with careful
    preservation of user modifications:

    1. If prompt.md doesn't exist: Create from template
    2. If prompt.md exists and matches template: No action needed
    3. If prompt.md exists and differs from template:
       - Without --force: Skip with warning (preserve user modifications)
       - With --force: Overwrite with template

    The PROMPT.md symlink in project root is also maintained.

    Args:
        project_dir: Project directory path
        force: If True, overwrite even if user has modified the file

    Returns:
        Status message indicating what action was taken:
        - "created": New file was created from template
        - "skipped_modified": User-modified file was preserved
        - "skipped_unchanged": File already matches template
        - "overwritten": User-modified file was overwritten (force=True)
    """
    cub_dir = project_dir / ".cub"
    cub_dir.mkdir(exist_ok=True)
    target_path = cub_dir / "prompt.md"

    templates_dir = _get_templates_dir()
    source_path = templates_dir / "PROMPT.md"
    if not source_path.exists():
        raise FileNotFoundError(f"Template not found: {source_path}")

    # Determine action based on file state
    if not target_path.exists():
        # New file - create from template
        shutil.copy2(source_path, target_path)
        _ensure_prompt_symlink(project_dir)
        return "created"

    # File exists - check if it matches template
    source_hash = _file_hash(source_path)
    target_hash = _file_hash(target_path)

    if source_hash == target_hash:
        # File matches template - no action needed
        _ensure_prompt_symlink(project_dir)
        return "skipped_unchanged"

    # File differs from template
    if force:
        # Force flag - overwrite user modifications
        shutil.copy2(source_path, target_path)
        _ensure_prompt_symlink(project_dir)
        return "overwritten"
    else:
        # Preserve user modifications
        _ensure_prompt_symlink(project_dir)
        return "skipped_modified"


def _ensure_prompt_symlink(project_dir: Path) -> None:
    """
    Ensure PROMPT.md symlink exists in project root pointing to .cub/prompt.md.

    Creates the symlink if it doesn't exist. If a regular file exists at
    PROMPT.md, it is NOT converted to a symlink (user may have intentionally
    created a separate file).
    """
    symlink_path = project_dir / "PROMPT.md"
    target = Path(".cub/prompt.md")

    if symlink_path.is_symlink():
        # Already a symlink - verify it points to correct location
        try:
            current_target = symlink_path.readlink()
            if current_target != target:
                symlink_path.unlink()
                symlink_path.symlink_to(target)
        except OSError:
            pass  # Symlink issues are non-fatal
    elif not symlink_path.exists():
        # No file exists - create symlink
        try:
            symlink_path.symlink_to(target)
        except OSError:
            # Symlink creation failed (e.g., Windows without admin)
            pass
    # If a regular file exists, leave it alone (user's choice)


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


# NOTE: _ensure_prompt_md() is defined above and handles user-customizable
# prompt.md with modification detection. runloop.md is the system-managed
# template, while prompt.md is intended for user customization.
# Plan-level context is injected at runtime via prompt_builder.py.


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


def _ensure_hook_directories(project_dir: Path) -> None:
    """
    Create hook directories for each lifecycle hook point.

    Creates .cub/hooks/ and subdirectories for:
    - pre-session
    - end-of-task
    - end-of-epic
    - end-of-plan

    These directories help users understand where to place their hook scripts.
    """
    hooks_base = project_dir / ".cub" / "hooks"
    hooks_base.mkdir(parents=True, exist_ok=True)

    # Create subdirectories for each hook point
    hook_points = [
        "pre-session",
        "end-of-task",
        "end-of-epic",
        "end-of-plan",
    ]

    for hook_point in hook_points:
        hook_dir = hooks_base / hook_point
        hook_dir.mkdir(exist_ok=True)

    # Copy README.md into hooks directory
    templates_dir = _get_templates_dir()
    readme_template = templates_dir / "hooks" / "README.md"

    if readme_template.exists():
        target_readme = hooks_base / "README.md"
        shutil.copy2(readme_template, target_readme)


def _install_pre_push_hook(project_dir: Path, force: bool = False) -> bool:
    """
    Install pre-push hook for counter verification.

    Creates .git/hooks/pre-push that checks for ID collisions before pushing.

    Args:
        project_dir: Project directory
        force: If True, overwrite existing pre-push hook

    Returns:
        True if hook was installed, False if skipped
    """
    git_hooks_dir = project_dir / ".git" / "hooks"
    pre_push_hook = git_hooks_dir / "pre-push"

    # Check if .git directory exists
    if not git_hooks_dir.exists():
        logger.warning("No .git/hooks directory found, skipping pre-push hook installation")
        return False

    # Check if hook already exists
    if pre_push_hook.exists() and not force:
        # Check if it's our hook
        try:
            content = pre_push_hook.read_text(encoding="utf-8")
            if "verify_counters_before_push" in content:
                # Our hook is already installed
                logger.debug("Pre-push hook already installed")
                return False
            else:
                # Another pre-push hook exists
                console.print(
                    "[yellow]i[/yellow] Pre-push hook already exists (not installed by cub)"
                )
                console.print(
                    "[yellow]i[/yellow] Use --force to overwrite, or manually merge the hooks"
                )
                return False
        except OSError:
            pass

    # Copy hook template
    templates_dir = _get_templates_dir()
    hook_template = templates_dir / "hooks" / "pre-push"

    if not hook_template.exists():
        logger.warning(f"Pre-push hook template not found at {hook_template}")
        return False

    try:
        shutil.copy2(hook_template, pre_push_hook)
        # Make executable
        pre_push_hook.chmod(0o755)
        logger.info(f"Installed pre-push hook to {pre_push_hook}")
        return True
    except OSError as e:
        console.print(f"[yellow]Warning: Could not install pre-push hook: {e}[/yellow]")
        return False


def _ensure_project_config(
    project_dir: Path, force: bool = False, backend: str | None = None
) -> bool:
    """
    Ensure project configuration exists in .cub/config.json.

    This is the consolidated project configuration file that contains both
    user-facing settings (harness, budget, state, loop, hooks, interview)
    and internal state (project_id, dev_mode, backend).

    If a legacy .cub.json exists, migrates its settings to .cub/config.json.

    Args:
        project_dir: Project directory
        force: If True, overwrite existing config with defaults
        backend: Optional backend mode to set

    Returns:
        True if migration from legacy config occurred
    """
    config_dir = project_dir / ".cub"
    config_file = config_dir / "config.json"
    legacy_file = project_dir / ".cub.json"

    config_dir.mkdir(parents=True, exist_ok=True)

    # Check if we need to migrate from legacy config
    migrated = False
    existing_config: dict[str, Any] = {}
    legacy_config: dict[str, Any] = {}

    # Load existing .cub/config.json if present
    if config_file.exists() and not force:
        try:
            with open(config_file, encoding="utf-8") as f:
                existing_config = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing_config = {}

    # Load legacy .cub.json if present (for migration)
    if legacy_file.exists():
        try:
            with open(legacy_file, encoding="utf-8") as f:
                legacy_config = json.load(f)
            # Filter out comment block (<!-- key)
            legacy_config = {k: v for k, v in legacy_config.items() if not k.startswith("<!--")}
            migrated = True
        except (json.JSONDecodeError, OSError):
            legacy_config = {}

    # If config exists and not forcing, check if we need to update backend
    if config_file.exists() and not force and not migrated:
        # Still need to set backend if specified and not already set
        if backend and existing_config.get("backend", {}).get("mode") != backend:
            existing_config.setdefault("backend", {})["mode"] = backend
            try:
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(existing_config, f, indent=2)
                    f.write("\n")
            except OSError as e:
                console.print(f"[yellow]Warning: Could not update backend in config: {e}[/yellow]")
        return False

    # Build the default config template (without JSON comments)
    default_config: dict[str, Any] = {
        "harness": "claude",
        "budget": {
            "max_tokens_per_task": 500000,
            "max_tasks_per_session": None,
            "max_total_cost": None,
        },
        "state": {
            "require_clean": True,
            "run_tests": True,
            "run_typecheck": False,
            "run_lint": False,
        },
        "loop": {
            "max_iterations": 100,
            "on_task_failure": "stop",
        },
        "hooks": {
            "enabled": True,
            "fail_fast": False,
        },
        "interview": {
            "custom_questions": [],
        },
    }

    # Merge in order: default -> legacy -> existing -> backend override
    merged: dict[str, Any] = default_config.copy()

    # Deep merge legacy config (migrating from .cub.json)
    if legacy_config:
        for key, value in legacy_config.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key].update(value)
            else:
                merged[key] = value

    # Deep merge existing .cub/config.json (preserves internal state like project_id, dev_mode)
    for key, value in existing_config.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key].update(value)
        else:
            merged[key] = value

    # Set backend if specified
    if backend:
        if "backend" not in merged:
            merged["backend"] = {}
        merged["backend"]["mode"] = backend

    # Write the consolidated config
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
            f.write("\n")
    except OSError as e:
        console.print(f"[yellow]Warning: Could not write config: {e}[/yellow]")

    return migrated


def _migrate_legacy_config(project_dir: Path) -> bool:
    """
    Migrate settings from legacy .cub.json to .cub/config.json.

    This is called during init to consolidate config files. The legacy
    .cub.json file is NOT deleted to allow users to verify the migration.

    Args:
        project_dir: Project directory

    Returns:
        True if migration occurred
    """
    legacy_file = project_dir / ".cub.json"
    if not legacy_file.exists():
        return False

    migrated = _ensure_project_config(project_dir, force=False)

    if migrated:
        console.print(
            "[yellow]i[/yellow] Migrated settings from .cub.json to .cub/config.json"
        )
        console.print(
            "[yellow]i[/yellow] You can safely delete .cub.json after verifying the migration"
        )

    return migrated


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
    Generate CLAUDE.md instruction file and AGENTS.md symlink at project root.

    CLAUDE.md is the canonical instruction file. AGENTS.md is created as a
    symlink to CLAUDE.md to ensure consistency without duplication.

    Uses the managed section upsert engine to non-destructively update
    CLAUDE.md. Also ensures constitution and runloop are in place.
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

    # Ensure prompt.md exists (user-customizable, preserve modifications)
    try:
        prompt_status = _ensure_prompt_md(project_dir, force=force)
        if prompt_status == "created":
            console.print("[green]v[/green] Created .cub/prompt.md")
        elif prompt_status == "skipped_modified":
            console.print(
                "[yellow]i[/yellow] Preserved user-modified .cub/prompt.md "
                "(use --force to overwrite)"
            )
        elif prompt_status == "overwritten":
            console.print("[green]v[/green] Overwrote .cub/prompt.md with template")
        # skipped_unchanged: no message needed
    except Exception as e:
        console.print(f"[yellow]Warning: Could not ensure prompt.md: {e}[/yellow]")

    # Ensure .cub/agent.md exists (from template, don't overwrite)
    try:
        agent_path = project_dir / ".cub" / "agent.md"
        if not agent_path.exists():
            from cub.cli.update import get_templates_dir

            templates_dir = get_templates_dir()
            template_path = templates_dir / "agent.md"
            if template_path.exists():
                agent_path.parent.mkdir(parents=True, exist_ok=True)
                agent_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
                console.print("[green]v[/green] Created .cub/agent.md")
            else:
                console.print("[yellow]Warning: agent.md template not found[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not create agent.md: {e}[/yellow]")

    # Generate managed section content for CLAUDE.md (canonical instruction file)
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

    # Create AGENTS.md as symlink to CLAUDE.md (single source of truth)
    try:
        agents_path = project_dir / "AGENTS.md"
        if agents_path.is_symlink():
            # Already a symlink, update if needed
            if create_agents_symlink(project_dir, force=True):
                console.print("[green]v[/green] AGENTS.md symlink ready")
        elif agents_path.exists():
            # Existing file - convert to symlink with backup
            import shutil as shutil_backup

            backup_path = project_dir / "AGENTS.md.backup"
            shutil_backup.move(str(agents_path), str(backup_path))
            console.print("[yellow]i[/yellow] Backed up existing AGENTS.md to AGENTS.md.backup")
            if create_agents_symlink(project_dir, force=True):
                console.print("[green]v[/green] Created AGENTS.md symlink (-> CLAUDE.md)")
        else:
            # No existing file, create symlink
            if create_agents_symlink(project_dir, force=False):
                console.print("[green]v[/green] Created AGENTS.md symlink (-> CLAUDE.md)")
    except OSError as e:
        # Symlink creation failed (e.g., Windows without admin)
        console.print(f"[yellow]Warning: Could not create AGENTS.md symlink: {e}[/yellow]")
        console.print(
            "[yellow]i[/yellow] On Windows, symlinks require Developer Mode or admin rights"
        )

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
    project_id: str | None = None,
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

    # 2.5. Ensure project_id is set for task ID prefixes
    final_project_id = _ensure_project_id(project_dir, project_id)
    console.print(f"[green]v[/green] Project ID set to: {final_project_id}")

    # 3. Create specs/ directory
    _ensure_specs_dir(project_dir)

    # 3.5. Create hook directories
    _ensure_hook_directories(project_dir)
    console.print("[green]v[/green] Created hook directories")

    # 4. Ensure consolidated project config in .cub/config.json
    # This also migrates settings from legacy .cub.json if present
    migrated = _ensure_project_config(project_dir, force=force, backend=chosen_backend)
    if migrated:
        console.print(
            "[yellow]i[/yellow] Migrated settings from .cub.json to .cub/config.json"
        )
    else:
        console.print("[green]v[/green] Project config ready at .cub/config.json")

    # 5. prompt.md is now handled in generate_instruction_files()
    # It preserves user modifications unless --force is used

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

    # 9.5. Install pre-push hook
    if _install_pre_push_hook(project_dir, force=force):
        console.print("[green]v[/green] Installed pre-push hook for counter verification")

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
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        "-p",
        help="Project ID prefix for task IDs (auto-generated if not specified)",
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
        cub init --project-id myp   # Set explicit project ID prefix
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
        project_id=project_id,
    )


if __name__ == "__main__":
    typer.run(main)
