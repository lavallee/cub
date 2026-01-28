"""
Cub CLI - Update command.

Update project templates and skills to the latest versions from cub.
This updates project files, not cub itself. For upgrading cub, use `cub system-upgrade`.
"""

import hashlib
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

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
            for script_file in scripts_source.glob("*.py"):
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
                if target_path.suffix == ".py" and "scripts" in target_path.parts:
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
