"""
Cub CLI - Update command.

Update project templates and skills to the latest versions from cub.
This updates project files, not cub itself. For upgrading cub, use `cub system-upgrade`.
"""

import hashlib
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.cli.map import generate_map
from cub.core.config.loader import load_config
from cub.core.constitution import ensure_constitution
from cub.core.instructions import (
    detect_managed_section,
    generate_agents_md,
    generate_claude_md,
    upsert_managed_section,
)

app = typer.Typer(
    name="update",
    help="Update project templates and skills",
    no_args_is_help=False,
)

console = Console()


def get_templates_dir() -> Path:
    """Get the templates directory from the cub package."""
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
    # Fall back to looking relative to bash script location
    bash_dir = cub_path / "bash"
    if bash_dir.is_dir():
        templates_dir = bash_dir.parent.parent / "templates"
        if templates_dir.is_dir():
            return templates_dir
    raise FileNotFoundError("Could not locate cub templates directory")


def file_hash(path: Path) -> str:
    """Calculate MD5 hash of a file."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def files_differ(source: Path, target: Path) -> bool:
    """Check if two files have different content."""
    if not target.exists():
        return True
    return file_hash(source) != file_hash(target)


def get_layout_root() -> Path:
    """Get the layout root directory (.cub or similar)."""
    # Check for .cub directory (standard layout)
    if Path(".cub").is_dir():
        return Path(".cub")
    # Check for .claude directory (alternate layout)
    if Path(".claude").is_dir():
        # Create .cub if it doesn't exist
        Path(".cub").mkdir(exist_ok=True)
        return Path(".cub")
    # Default to .cub
    return Path(".cub")


def _refresh_managed_sections(
    project_dir: Path, force: bool = False, debug: bool = False
) -> list[str]:
    """
    Refresh managed sections in AGENTS.md and CLAUDE.md.

    Args:
        project_dir: Path to the project root directory
        force: If True, update even if content hasn't changed
        debug: Show debug output

    Returns:
        List of status messages for updated files
    """
    from cub.core.config.models import (
        CircuitBreakerConfig,
        CubConfig,
        HarnessConfig,
    )

    messages = []

    # Load config or use defaults
    try:
        config = load_config(project_dir)
    except Exception:
        config = CubConfig(
            harness=HarnessConfig(name="auto", priority=["claude", "codex"]),
            circuit_breaker=CircuitBreakerConfig(timeout_minutes=30, enabled=True),
        )

    # Update AGENTS.md
    agents_path = project_dir / "AGENTS.md"
    if agents_path.exists():
        try:
            # Detect current section
            section_info = detect_managed_section(agents_path)

            if section_info.found:
                # Generate new content
                new_content = generate_agents_md(project_dir, config)

                # Check if update needed
                if force or section_info.content_modified:
                    result = upsert_managed_section(agents_path, new_content, version=1)
                    messages.append("[green]✓[/green] Updated AGENTS.md managed section")
                    if result.warnings:
                        for warning in result.warnings:
                            messages.append(f"[yellow]  Warning: {warning}[/yellow]")
                elif debug:
                    messages.append("[dim]AGENTS.md managed section unchanged[/dim]")
            elif debug:
                messages.append("[dim]AGENTS.md has no managed section[/dim]")
        except Exception as e:
            messages.append(f"[red]Error updating AGENTS.md: {e}[/red]")

    # Update CLAUDE.md
    claude_path = project_dir / "CLAUDE.md"
    if claude_path.exists():
        try:
            # Detect current section
            section_info = detect_managed_section(claude_path)

            if section_info.found:
                # Generate new content
                new_content = generate_claude_md(project_dir, config)

                # Check if update needed
                if force or section_info.content_modified:
                    result = upsert_managed_section(claude_path, new_content, version=1)
                    messages.append("[green]✓[/green] Updated CLAUDE.md managed section")
                    if result.warnings:
                        for warning in result.warnings:
                            messages.append(f"[yellow]  Warning: {warning}[/yellow]")
                elif debug:
                    messages.append("[dim]CLAUDE.md managed section unchanged[/dim]")
            elif debug:
                messages.append("[dim]CLAUDE.md has no managed section[/dim]")
        except Exception as e:
            messages.append(f"[red]Error updating CLAUDE.md: {e}[/red]")

    return messages


def _ensure_runloop(project_dir: Path, templates_dir: Path, force: bool = False) -> str | None:
    """
    Ensure runloop.md exists in .cub directory.

    Copies from templates if missing. Warns if modified from template.

    Args:
        project_dir: Path to the project root directory
        templates_dir: Path to templates directory
        force: If True, overwrite existing file

    Returns:
        Status message or None if no action taken
    """
    cub_dir = project_dir / ".cub"
    cub_dir.mkdir(exist_ok=True)

    target_path = cub_dir / "runloop.md"
    source_path = templates_dir / "runloop.md"

    if not source_path.exists():
        return f"[yellow]Warning: Template not found: {source_path}[/yellow]"

    if not target_path.exists():
        shutil.copy2(source_path, target_path)
        return "[green]✓[/green] Created .cub/runloop.md"
    elif force:
        shutil.copy2(source_path, target_path)
        return "[green]✓[/green] Updated .cub/runloop.md"
    else:
        # Check if modified from template
        source_hash = hashlib.md5(source_path.read_bytes()).hexdigest()
        target_hash = hashlib.md5(target_path.read_bytes()).hexdigest()
        if source_hash != target_hash:
            return (
                "[yellow]Warning: .cub/runloop.md modified from template "
                "(use --force to overwrite)[/yellow]"
            )

    return None


@app.callback(invoke_without_command=True)
def update(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be updated without making changes",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite modified files (by default, only unmodified files are updated)",
    ),
    skills_only: bool = typer.Option(
        False,
        "--skills-only",
        "-s",
        help="Only update Claude Code skills, not .cub templates",
    ),
    templates_only: bool = typer.Option(
        False,
        "--templates-only",
        "-t",
        help="Only update .cub templates, not skills",
    ),
) -> None:
    """
    Update project templates and skills to the latest versions.

    This updates the .cub/ directory files and .claude/commands/ skills
    from the installed cub package. By default, only files that haven't
    been modified are updated.

    Use --force to overwrite all files, including modified ones.
    Use --dry-run to see what would be updated without making changes.

    Examples:
        cub update                  # Update unmodified files
        cub update --dry-run        # Show what would be updated
        cub update --force          # Update all files, including modified
        cub update --skills-only    # Only update Claude Code skills
        cub update --templates-only # Only update .cub templates
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False

    # Validate options
    if skills_only and templates_only:
        console.print("[red]Error: Cannot use --skills-only and --templates-only together[/red]")
        raise typer.Exit(1)

    # Find templates directory
    try:
        templates_dir = get_templates_dir()
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if debug:
        console.print(f"[dim]Templates directory: {templates_dir}[/dim]")

    # Get project directory
    project_dir = Path.cwd()

    # Ensure constitution exists (don't overwrite unless force=True)
    if not skills_only:
        try:
            ensure_constitution(project_dir, force=force)
            if not dry_run:
                console.print("[green]✓[/green] Constitution ready")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not ensure constitution: {e}[/yellow]")

    # Refresh runloop
    if not skills_only:
        runloop_msg = _ensure_runloop(project_dir, templates_dir, force=force)
        if runloop_msg and not dry_run:
            console.print(runloop_msg)

    # Refresh managed sections in AGENTS.md and CLAUDE.md
    if not skills_only:
        managed_messages = _refresh_managed_sections(project_dir, force=force, debug=debug)
        if managed_messages and not dry_run:
            for msg in managed_messages:
                console.print(msg)

    # Regenerate project map
    if not skills_only:
        map_path = project_dir / ".cub" / "map.md"
        try:
            if not dry_run:
                map_content = generate_map(project_dir, token_budget=4096, max_depth=4)
                map_path.parent.mkdir(parents=True, exist_ok=True)
                map_path.write_text(map_content, encoding="utf-8")
                console.print("[green]✓[/green] Regenerated project map at .cub/map.md")
            else:
                console.print("[dim]Would regenerate project map at .cub/map.md[/dim]")
        except Exception as e:
            if not dry_run:
                console.print(f"[yellow]Warning: Could not regenerate map: {e}[/yellow]")
            elif debug:
                console.print(f"[dim]Map generation would fail: {e}[/dim]")

    # Refresh hooks (script + settings.json)
    if not skills_only:
        try:
            from cub.core.hooks.installer import install_hooks

            if not dry_run:
                hook_result = install_hooks(project_dir, force=force)
                if hook_result.success:
                    if hook_result.hooks_installed:
                        console.print(
                            f"[green]✓[/green] Updated hooks: "
                            f"{', '.join(hook_result.hooks_installed)}"
                        )
                    elif debug:
                        console.print("[dim]Hooks already up to date[/dim]")
                    for issue in hook_result.issues:
                        if issue.severity == "warning":
                            console.print(f"[yellow]Warning: {issue.message}[/yellow]")
                else:
                    console.print(
                        f"[yellow]Warning: Hook update issue: {hook_result.message}[/yellow]"
                    )
            else:
                console.print("[dim]Would refresh hooks[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not update hooks: {e}[/yellow]")

    # Track updates
    updates: list[tuple[str, str, str]] = []  # (source, target, status)
    skipped: list[tuple[str, str]] = []  # (target, reason)

    # Update .cub templates
    if not skills_only:
        layout_root = get_layout_root()
        layout_root.mkdir(exist_ok=True)

        # Map of template files to their targets
        template_files = {
            "PROMPT.md": layout_root / "prompt.md",
            "README.md": layout_root / "README.md",
        }

        for template_name, target_path in template_files.items():
            source_path = templates_dir / template_name
            if not source_path.exists():
                if debug:
                    console.print(f"[dim]Template not found: {source_path}[/dim]")
                continue

            if not target_path.exists():
                # New file - always add
                updates.append((str(source_path), str(target_path), "new"))
            elif files_differ(source_path, target_path):
                if force:
                    updates.append((str(source_path), str(target_path), "update"))
                else:
                    skipped.append((str(target_path), "modified"))
            else:
                skipped.append((str(target_path), "unchanged"))

    # Update scripts
    if not skills_only:
        scripts_source = templates_dir / "scripts"
        scripts_target = Path(".cub") / "scripts"
        if scripts_source.is_dir():
            scripts_target.mkdir(parents=True, exist_ok=True)
            for script_file in sorted(scripts_source.glob("*.*")):
                target_path = scripts_target / script_file.name
                if not target_path.exists():
                    updates.append((str(script_file), str(target_path), "new"))
                elif files_differ(script_file, target_path):
                    if force:
                        updates.append((str(script_file), str(target_path), "update"))
                    else:
                        skipped.append((str(target_path), "modified"))
                else:
                    skipped.append((str(target_path), "unchanged"))

    # Update Claude Code skills
    if not templates_only:
        skills_source = templates_dir / "commands"
        skills_target = Path(".claude/commands")

        if skills_source.is_dir():
            skills_target.mkdir(parents=True, exist_ok=True)

            for skill_file in skills_source.glob("*.md"):
                target_path = skills_target / skill_file.name

                if not target_path.exists():
                    # New skill - always add
                    updates.append((str(skill_file), str(target_path), "new"))
                elif files_differ(skill_file, target_path):
                    if force:
                        updates.append((str(skill_file), str(target_path), "update"))
                    else:
                        skipped.append((str(target_path), "modified"))
                else:
                    skipped.append((str(target_path), "unchanged"))

    # Display results
    if updates:
        table = Table(title="Files to Update" if dry_run else "Updated Files")
        table.add_column("File", style="cyan")
        table.add_column("Status", style="green")

        for source, target, status in updates:
            status_display = "[green]new[/green]" if status == "new" else "[yellow]update[/yellow]"
            table.add_row(target, status_display)

        console.print(table)

        if not dry_run:
            # Perform updates
            for source, target, status in updates:
                source_path = Path(source)
                target_path = Path(target)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(source_path.read_bytes())
                # Set executable for scripts
                if target_path.suffix in (".py", ".sh") and "scripts" in target_path.parts:
                    target_path.chmod(0o755)

            console.print()
            console.print(f"[green]Updated {len(updates)} file(s)[/green]")
        else:
            console.print()
            console.print("[dim]Run without --dry-run to apply changes[/dim]")
    else:
        console.print("[green]All files are up to date[/green]")

    # Show skipped files if any were modified
    modified_skipped = [(t, r) for t, r in skipped if r == "modified"]
    if modified_skipped and not force:
        console.print()
        console.print(f"[yellow]Skipped {len(modified_skipped)} modified file(s):[/yellow]")
        for target, _ in modified_skipped:
            console.print(f"  [dim]{target}[/dim]")
        console.print()
        console.print("[dim]Use --force to overwrite modified files[/dim]")

    if debug:
        unchanged = [(t, r) for t, r in skipped if r == "unchanged"]
        if unchanged:
            console.print()
            console.print(f"[dim]Unchanged: {len(unchanged)} file(s)[/dim]")


__all__ = ["app"]
