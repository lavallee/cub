"""
Cub CLI - Stage command.

The stage command imports tasks from a completed plan's itemized-plan.md
into the task backend (beads or JSON), bridging planning and execution.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.plan.context import PlanContext, PlanContextError
from cub.core.specs.lifecycle import SpecLifecycleError, move_spec_to_staged
from cub.core.stage.stager import (
    ItemizedPlanNotFoundError,
    PlanAlreadyStagedError,
    PlanNotCompleteError,
    Stager,
    StagerError,
    StagingResult,
    TaskImportError,
    find_stageable_plans,
)

app = typer.Typer(
    name="stage",
    help="Import tasks from a completed plan into the task backend",
    no_args_is_help=False,
)

console = Console()


def _generate_prompt_md(
    plan_ctx: PlanContext,
    project_root: Path,
    verbose: bool = False,
) -> Path | None:
    """
    Generate PROMPT.md by combining Ralph Loop template with plan artifacts.

    Preserves the Ralph Loop workflow template (Context Files, Workflow steps,
    Critical Rules, COMPLETE promise) while inserting project-specific context
    from orientation.md and architecture.md.

    Args:
        plan_ctx: The plan context.
        project_root: Project root directory.
        verbose: Show detailed output.

    Returns:
        Path to generated prompt.md, or None if not generated.
    """
    import re

    cub_dir = project_root / ".cub"
    cub_dir.mkdir(parents=True, exist_ok=True)
    output_path = cub_dir / "prompt.md"

    # Read orientation.md
    orientation_content = ""
    orientation_path = plan_ctx.orientation_path
    if orientation_path.exists():
        orientation_content = orientation_path.read_text()

    # Read architecture.md
    architecture_content = ""
    architecture_path = plan_ctx.architecture_path
    if architecture_path.exists():
        architecture_content = architecture_path.read_text()

    # Extract sections
    def extract_section(content: str, heading: str, max_lines: int = 10) -> str:
        """Extract a section from markdown content."""
        pattern = rf"##\s+{re.escape(heading)}\s*\n([\s\S]*?)(?=\n##|\Z)"
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            lines = match.group(1).strip().split("\n")
            return "\n".join(lines[:max_lines])
        return ""

    # Build project context section
    project_context_lines: list[str] = []

    # Overview from orientation
    overview = extract_section(orientation_content, "Problem Statement", 5)
    if overview:
        project_context_lines.extend([
            "## Project Context",
            "",
            overview,
            "",
        ])

    # Requirements from orientation
    reqs = extract_section(orientation_content, "Requirements", 10)
    if reqs:
        project_context_lines.extend([
            "### Requirements",
            "",
            reqs,
            "",
        ])

    # Technical approach from architecture
    approach = extract_section(architecture_content, "Approach", 10)
    if not approach:
        approach = extract_section(architecture_content, "Technical Approach", 10)
    if approach:
        project_context_lines.extend([
            "### Technical Approach",
            "",
            approach,
            "",
        ])

    # Components from architecture
    components = extract_section(architecture_content, "Components", 15)
    if components:
        project_context_lines.extend([
            "### Components",
            "",
            components,
            "",
        ])

    # Constraints from orientation
    constraints = extract_section(orientation_content, "Constraints", 5)
    if constraints:
        project_context_lines.extend([
            "### Constraints",
            "",
            constraints,
            "",
        ])

    project_context = "\n".join(project_context_lines)

    # Load the Ralph Loop template from templates/PROMPT.md
    # This template contains the workflow, critical rules, and COMPLETE promise
    template_path = project_root / "templates" / "PROMPT.md"
    if not template_path.exists():
        # Fall back to bundled template
        template_path = Path(__file__).parent.parent.parent.parent / "templates" / "PROMPT.md"

    if not template_path.exists():
        # Last resort: use minimal fallback
        if not project_context:
            return None
        output_path.write_text(project_context)
        return output_path

    # Read the template (skip the HTML comment header)
    template_content = template_path.read_text()

    # Find where the actual content starts (after the HTML comment)
    # The template has a <!-- ... --> comment at the top with instructions
    comment_end = template_content.find("-->")
    if comment_end != -1:
        # Skip past the comment and any whitespace
        template_content = template_content[comment_end + 3:].lstrip()

    # Insert project context after "## Context Files" section
    # This ensures the Ralph Loop workflow stays at the top
    if project_context:
        # Find the "## Your Workflow" section to insert before it
        workflow_marker = "## Your Workflow"
        if workflow_marker in template_content:
            insert_point = template_content.find(workflow_marker)
            template_content = (
                template_content[:insert_point]
                + project_context
                + "\n"
                + template_content[insert_point:]
            )
        else:
            # Append at the end if we can't find the marker
            template_content = template_content + "\n" + project_context

    # Add generation footer
    footer = f"\n\n---\n\nGenerated by cub stage from plan: {plan_ctx.plan.slug}\n"
    template_content = template_content.rstrip() + footer

    output_path.write_text(template_content)

    if verbose:
        console.print(f"[dim]  Generated: {output_path.relative_to(project_root)}[/dim]")

    return output_path


def _generate_agent_md(
    project_root: Path,
    verbose: bool = False,
) -> Path | None:
    """
    Generate AGENT.md template if it doesn't exist.

    Creates a starter template for agent instructions. Does not overwrite
    existing files.

    Args:
        project_root: Project root directory.
        verbose: Show detailed output.

    Returns:
        Path to generated agent.md, or None if already exists or not generated.
    """
    cub_dir = project_root / ".cub"
    cub_dir.mkdir(parents=True, exist_ok=True)
    output_path = cub_dir / "agent.md"

    # Don't overwrite existing file
    if output_path.exists():
        if verbose:
            rel_path = output_path.relative_to(project_root)
            console.print(f"[dim]  Skipped: {rel_path} (already exists)[/dim]")
        return None

    template = """\
# Agent Instructions

This file contains instructions for AI agents working on this project.
Update this file as you learn new things about the codebase.

## Project Overview

<!-- Brief description of the project -->

## Tech Stack

- **Language**:
- **Framework**:
- **Database**:

## Development Setup

```bash
# Setup commands
```

## Running the Project

```bash
# Run commands
```

## Feedback Loops

Run these before committing:

```bash
# Tests
# Type checking
# Linting
```

## Common Commands

```bash
# Frequently used commands
```

---

Generated by cub stage. Customize based on your project.
"""

    output_path.write_text(template)

    if verbose:
        console.print(f"[dim]  Generated: {output_path.relative_to(project_root)}[/dim]")

    return output_path


def _run_preflight_checks(
    project_root: Path,
    verbose: bool = False,
    skip_git_check: bool = False,
) -> list[str]:
    """
    Run pre-flight checks before staging.

    Checks:
    1. Git repository exists
    2. Git working directory status (warn if dirty)
    3. Required tools (bd) are available
    4. Beads already initialized (info message)

    Args:
        project_root: Project root directory.
        verbose: Show detailed output.
        skip_git_check: Skip git-related checks.

    Returns:
        List of warning messages (empty if all checks pass).
    """
    warnings: list[str] = []

    # Check 1: Git repository
    if not skip_git_check:
        git_dir = project_root / ".git"
        if not git_dir.exists():
            warnings.append("Not a git repository. Consider initializing with 'git init'.")
        else:
            if verbose:
                console.print("[dim]  \u2713 Git repository found[/dim]")

            # Check 2: Clean working directory
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    # Count changes
                    changes = len(result.stdout.strip().split("\n"))
                    warnings.append(
                        f"Uncommitted changes detected ({changes} files). "
                        "Consider committing or stashing before staging."
                    )
                elif verbose:
                    console.print("[dim]  \u2713 Working directory clean[/dim]")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass  # Git not available or timed out

    # Check 3: Required tools
    if shutil.which("bd") is None:
        warnings.append(
            "Beads CLI (bd) not found. Install from: https://github.com/anthropics/beads"
        )
    elif verbose:
        console.print("[dim]  \u2713 Beads CLI (bd) found[/dim]")

    # Check 4: Beads already initialized
    beads_dir = project_root / ".beads"
    if beads_dir.exists():
        issues_file = beads_dir / "issues.jsonl"
        if issues_file.exists():
            # Count existing issues
            try:
                with open(issues_file) as f:
                    issue_count = sum(1 for line in f if line.strip())
                if issue_count > 0:
                    console.print(
                        f"[dim]  \u2139 Beads already initialized with {issue_count} issues. "
                        "Import will add to existing issues.[/dim]"
                    )
            except OSError:
                pass
    elif verbose:
        console.print("[dim]  \u2139 Beads not yet initialized (will initialize on staging)[/dim]")

    return warnings


def _find_plan_dir(
    plan_slug: str | None,
    project_root: Path,
) -> Path | None:
    """
    Find a plan directory by slug or find the most recent stageable plan.

    Args:
        plan_slug: Explicit plan slug, or None to find most recent.
        project_root: Project root directory.

    Returns:
        Path to plan directory, or None if not found.
    """
    if plan_slug:
        # Direct slug provided
        plan_dir = project_root / "plans" / plan_slug
        if plan_dir.exists() and (plan_dir / "plan.json").exists():
            return plan_dir
        return None

    # Find most recent stageable plan
    stageable = find_stageable_plans(project_root)
    if stageable:
        # Sort by modification time, most recent first
        stageable.sort(
            key=lambda p: (p / "plan.json").stat().st_mtime,
            reverse=True,
        )
        return stageable[0]

    return None


@app.callback(invoke_without_command=True)
def stage(
    ctx: typer.Context,
    plan_slug: str | None = typer.Argument(
        None,
        help="Plan slug to stage (default: most recent complete plan)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be imported without actually importing",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
    list_plans: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List all stageable plans",
    ),
    skip_checks: bool = typer.Option(
        False,
        "--skip-checks",
        help="Skip pre-flight checks (git, tools)",
    ),
    skip_prompt: bool = typer.Option(
        False,
        "--skip-prompt",
        help="Don't generate prompt.md and agent.md",
    ),
    project_root: Path = typer.Option(
        Path("."),
        "--project-root",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Import tasks from a completed plan into the task backend.

    The stage command bridges planning and execution by importing the
    tasks from itemized-plan.md into the task backend (beads or JSON).

    After staging:
    - Tasks are created in the task backend
    - The plan status is updated to STAGED
    - Tasks are ready for 'cub run' execution

    Examples:
        cub stage                     # Stage most recent complete plan
        cub stage my-feature          # Stage specific plan by slug
        cub stage --dry-run           # Preview without importing
        cub stage --list              # List all stageable plans
    """
    debug = ctx.obj.get("debug", False) if ctx.obj else False
    project_root = project_root.resolve()

    if verbose or debug:
        console.print(f"[dim]Project root: {project_root}[/dim]")
        if plan_slug:
            console.print(f"[dim]Plan slug: {plan_slug}[/dim]")

    # Handle --list flag
    if list_plans:
        _list_stageable_plans(project_root, verbose)
        return

    # Find the plan to stage
    plan_dir = _find_plan_dir(plan_slug, project_root)

    if plan_dir is None:
        if plan_slug:
            console.print(f"[red]Plan not found: {plan_slug}[/red]")
            console.print(
                "[dim]Run 'cub plan run <spec>' first to create a plan.[/dim]"
            )
        else:
            console.print("[red]No stageable plans found.[/red]")
            console.print(
                "[dim]Run 'cub plan run <spec>' first to create a complete plan.[/dim]"
            )
            console.print(
                "[dim]Or use 'cub stage --list' to see available plans.[/dim]"
            )
        raise typer.Exit(1)

    if verbose or debug:
        console.print(f"[dim]Using plan: {plan_dir.name}[/dim]")

    # Load plan context
    try:
        plan_ctx = PlanContext.load(plan_dir, project_root)
    except FileNotFoundError as e:
        console.print(f"[red]Error loading plan: {e}[/red]")
        raise typer.Exit(1)
    except PlanContextError as e:
        console.print(f"[red]Error loading plan context: {e}[/red]")
        raise typer.Exit(1)

    # Run pre-flight checks (unless skipped or dry-run)
    if not skip_checks and not dry_run:
        if verbose:
            console.print("[dim]Running pre-flight checks...[/dim]")
        preflight_warnings = _run_preflight_checks(project_root, verbose=verbose)
        for warning in preflight_warnings:
            console.print(f"[yellow]Warning: {warning}[/yellow]")

    # Create stager and run
    stager = Stager(plan_ctx)

    if dry_run:
        console.print(f"[bold]Dry run:[/bold] {plan_ctx.plan.slug}")
    else:
        console.print(f"[bold]Staging:[/bold] {plan_ctx.plan.slug}")

    try:
        result = stager.stage(dry_run=dry_run)
    except PlanNotCompleteError as e:
        console.print(f"[red]Plan not ready: {e}[/red]")
        console.print(
            "[dim]Complete all planning stages first with 'cub plan run'.[/dim]"
        )
        raise typer.Exit(1)
    except PlanAlreadyStagedError as e:
        console.print(f"[yellow]Already staged: {e}[/yellow]")
        raise typer.Exit(0)
    except ItemizedPlanNotFoundError as e:
        console.print(f"[red]Missing itemized plan: {e}[/red]")
        console.print("[dim]Run 'cub plan itemize' first.[/dim]")
        raise typer.Exit(1)
    except TaskImportError as e:
        console.print(f"[red]Import failed: {e}[/red]")
        raise typer.Exit(1)
    except StagerError as e:
        console.print(f"[red]Staging error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        if debug:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1)

    # Move spec from planned/ to staged/ (only on successful, non-dry-run staging)
    spec_moved = False
    spec_new_path = None
    if not dry_run:
        try:
            spec_new_path = move_spec_to_staged(plan_ctx, verbose=verbose or debug)
            if spec_new_path is not None:
                spec_moved = True
        except SpecLifecycleError as e:
            # Non-fatal: warn but don't fail staging
            console.print(f"[yellow]Warning: Could not move spec: {e}[/yellow]")

    # Generate prompt.md and agent.md (unless skipped or dry-run)
    prompt_generated = False
    agent_generated = False
    if not dry_run and not skip_prompt:
        if verbose:
            console.print("[dim]Generating prompt files...[/dim]")
        prompt_path = _generate_prompt_md(plan_ctx, project_root, verbose=verbose)
        if prompt_path:
            prompt_generated = True
        agent_path = _generate_agent_md(project_root, verbose=verbose)
        if agent_path:
            agent_generated = True

    # Report results
    console.print()
    if dry_run:
        console.print("[yellow]Dry run complete - no tasks imported[/yellow]")
    else:
        console.print("[green]Staging complete![/green]")

    console.print(f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]")

    # Summary
    console.print()
    console.print(f"[bold]Created:[/bold] {len(result.epics_created)} epics, "
                  f"{len(result.tasks_created)} tasks")

    # Report spec move
    if spec_moved and spec_new_path is not None:
        console.print(f"[cyan]Spec moved to:[/cyan] {spec_new_path.relative_to(project_root)}")

    # Report generated files
    if prompt_generated or agent_generated:
        generated_files = []
        if prompt_generated:
            generated_files.append(".cub/prompt.md")
        if agent_generated:
            generated_files.append(".cub/agent.md")
        console.print(f"[cyan]Generated:[/cyan] {', '.join(generated_files)}")

    if verbose:
        _print_detailed_results(result, project_root)

    # Next steps
    if not dry_run:
        console.print()
        console.print("[bold]Next step:[/bold] cub run")


def _list_stageable_plans(project_root: Path, verbose: bool) -> None:
    """List all plans that are ready to be staged."""
    stageable = find_stageable_plans(project_root)

    if not stageable:
        console.print("[yellow]No stageable plans found.[/yellow]")
        console.print(
            "[dim]Plans must be complete (orient, architect, itemize done) "
            "to be staged.[/dim]"
        )
        return

    # Sort by modification time
    stageable.sort(
        key=lambda p: (p / "plan.json").stat().st_mtime,
        reverse=True,
    )

    console.print(f"[bold]Stageable plans ({len(stageable)}):[/bold]")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Plan Slug")
    table.add_column("Status")
    table.add_column("Spec")

    for plan_dir in stageable:
        try:
            ctx = PlanContext.load(plan_dir, project_root)
            plan = ctx.plan
            spec_name = plan.spec_file or "-"
            table.add_row(
                plan.slug,
                plan.status.value,
                spec_name,
            )
        except Exception:
            # Skip plans that can't be loaded
            table.add_row(
                plan_dir.name,
                "[red]error[/red]",
                "-",
            )

    console.print(table)

    if verbose:
        console.print()
        console.print("[dim]Use 'cub stage <slug>' to stage a specific plan.[/dim]")


def _print_detailed_results(
    result: StagingResult,
    project_root: Path,
) -> None:
    """Print detailed staging results."""
    if result.epics_created:
        console.print()
        console.print("[bold]Epics:[/bold]")
        for epic in result.epics_created:
            task_count = len([t for t in result.tasks_created if t.parent == epic.id])
            console.print(f"  - {epic.id}: {epic.title} ({task_count} tasks)")

    if result.tasks_created:
        console.print()
        console.print("[bold]Tasks:[/bold]")
        for task in result.tasks_created:
            priority_str = f"P{task.priority_numeric}"
            console.print(f"  - {task.id} [{priority_str}]: {task.title}")
