"""
Cub CLI - Investigate command.

Intelligent capture processing that categorizes ideas and moves them forward.
"""

from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from cub.core.captures.models import Capture
from cub.core.captures.store import CaptureStore

console = Console()
app = typer.Typer(help="Investigate and process captures")


class CaptureCategory(str, Enum):
    """Categories for capture processing."""

    QUICK = "quick"  # Small, immediate fixes
    AUDIT = "audit"  # Code exploration needed
    RESEARCH = "research"  # External investigation needed
    DESIGN = "design"  # Planning and feedback needed
    SPIKE = "spike"  # Exploratory work on a branch
    UNCLEAR = "unclear"  # Needs clarification


def categorize_capture(capture: Capture, content: str) -> CaptureCategory:
    """
    Analyze a capture and determine its category.

    Uses heuristics and optionally AI to categorize.

    Args:
        capture: The capture metadata
        content: The full capture content

    Returns:
        The determined category
    """
    content_lower = content.lower()
    title_lower = capture.title.lower()

    # Quick fix indicators
    quick_indicators = [
        "fix typo",
        "remove ",
        "delete ",
        "rename ",
        "update copyright",
        "change ",
        "add missing",
    ]
    if any(ind in content_lower or ind in title_lower for ind in quick_indicators):
        if len(content) < 200:  # Short = likely quick fix
            return CaptureCategory.QUICK

    # Audit indicators
    audit_indicators = [
        "track all",
        "find all",
        "audit",
        "where do we",
        "how many",
        "list all",
        "search for",
    ]
    if any(ind in content_lower for ind in audit_indicators):
        return CaptureCategory.AUDIT

    # Research indicators
    research_indicators = [
        "check out",
        "look at",
        "research",
        "investigate",
        "compare",
        "inspiration",
        "best practice",
        "how does",
        "what is",
    ]
    if any(ind in content_lower for ind in research_indicators):
        return CaptureCategory.RESEARCH

    # Spike indicators (exploratory coding)
    spike_indicators = [
        "try ",
        "test whether",
        "experiment",
        "prototype",
        "spike",
        "proof of concept",
        "poc",
        "explore approach",
        "try out",
        "see if",
    ]
    if any(ind in content_lower for ind in spike_indicators):
        return CaptureCategory.SPIKE

    # Design indicators
    design_indicators = [
        "think through",
        "design",
        "architect",
        "plan",
        "how should",
        "what if",
        "consider",
        "explore option",
    ]
    if any(ind in content_lower for ind in design_indicators):
        return CaptureCategory.DESIGN

    # Default to unclear if can't categorize
    if len(content) < 50:
        return CaptureCategory.UNCLEAR

    # Longer content without clear indicators → likely design
    return CaptureCategory.DESIGN


def process_quick_fix(capture: Capture, content: str, dry_run: bool = False) -> str:
    """
    Process a quick fix capture.

    Creates a beads task for the fix.
    """
    if dry_run:
        return f"Would create task for: {capture.title}"

    # TODO: Create beads task
    # bd create --title "{capture.title}" --type task
    return f"Created task for: {capture.title}"


def process_audit(capture: Capture, content: str, dry_run: bool = False) -> str:
    """
    Process a code audit capture.

    Runs code analysis and produces a report.
    """
    if dry_run:
        return f"Would run code audit for: {capture.title}"

    # TODO: Run grep/glob analysis
    # TODO: Generate report in specs/investigations/
    return f"Audit report generated for: {capture.title}"


def process_research(capture: Capture, content: str, dry_run: bool = False) -> str:
    """
    Process a research capture.

    Runs web search and summarizes findings.
    """
    if dry_run:
        return f"Would research: {capture.title}"

    # TODO: Run web search
    # TODO: Summarize findings
    return f"Research summary generated for: {capture.title}"


def process_design(capture: Capture, content: str, dry_run: bool = False) -> str:
    """
    Process a design capture.

    Creates a design document for review.
    """
    if dry_run:
        return f"Would create design doc for: {capture.title}"

    # TODO: Generate design document template
    # TODO: Pre-fill with context
    return f"Design doc created for: {capture.title}"


def process_spike(capture: Capture, content: str, dry_run: bool = False) -> str:
    """
    Process a spike capture.

    Creates a beads task for exploratory work on a branch.
    """
    if dry_run:
        return f"Would create spike task for: {capture.title}"

    # TODO: Create beads task with spike type
    # TODO: Include branch naming convention
    return f"Spike task created for: {capture.title}"


def process_unclear(capture: Capture, content: str, dry_run: bool = False) -> str:
    """
    Process an unclear capture.

    Asks clarifying questions.
    """
    if dry_run:
        return f"Would ask clarifying questions for: {capture.title}"

    # TODO: Generate clarifying questions
    return f"Clarification needed for: {capture.title}"


PROCESSORS = {
    CaptureCategory.QUICK: process_quick_fix,
    CaptureCategory.AUDIT: process_audit,
    CaptureCategory.RESEARCH: process_research,
    CaptureCategory.DESIGN: process_design,
    CaptureCategory.SPIKE: process_spike,
    CaptureCategory.UNCLEAR: process_unclear,
}


@app.callback(invoke_without_command=True)
def investigate(
    ctx: typer.Context,
    capture_id: str | None = typer.Argument(
        None,
        help="Capture ID to investigate (e.g., cap-abc123)",
    ),
    all_captures: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Investigate all active captures",
    ),
    mode: CaptureCategory | None = typer.Option(
        None,
        "--mode",
        "-m",
        help="Override auto-categorization",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without doing it",
    ),
    batch_quick: bool = typer.Option(
        False,
        "--batch-quick-fixes",
        help="Batch quick fixes into a single task",
    ),
) -> None:
    """
    Investigate captures and move them forward.

    Analyzes each capture to determine what action it needs:
    - quick: Small fixes → create task
    - audit: Code exploration → run analysis
    - research: External investigation → web search
    - design: Planning needed → create design doc
    - unclear: Needs clarification → ask questions

    Examples:
        cub investigate cap-abc123
        cub investigate --all
        cub investigate --all --dry-run
        cub investigate cap-abc123 --mode=research
    """
    if ctx.invoked_subcommand is not None:
        return

    if not capture_id and not all_captures:
        console.print("[red]Error:[/red] Provide a capture ID or use --all")
        raise typer.Exit(1)

    # Collect captures to process
    captures_to_process: list[tuple[Capture, CaptureStore, str]] = []

    if capture_id:
        # Find single capture
        try:
            store = CaptureStore.global_store()
            capture = store.get_capture(capture_id)
            capture_file = store.get_capture_file_path(capture_id)
            content = capture_file.read_text()
            captures_to_process.append((capture, store, content))
        except FileNotFoundError:
            try:
                store = CaptureStore.project()
                capture = store.get_capture(capture_id)
                capture_file = store.get_capture_file_path(capture_id)
                content = capture_file.read_text()
                captures_to_process.append((capture, store, content))
            except FileNotFoundError:
                console.print(f"[red]Error:[/red] Capture not found: {capture_id}")
                raise typer.Exit(1)
    else:
        # Get all active captures from both global and project stores
        stores_to_check: list[CaptureStore] = []
        try:
            stores_to_check.append(CaptureStore.global_store())
        except FileNotFoundError:
            pass
        try:
            stores_to_check.append(CaptureStore.project())
        except FileNotFoundError:
            pass

        for store in stores_to_check:
            try:
                for capture in store.list_captures():
                    capture_file = store.get_capture_file_path(capture.id)
                    content = capture_file.read_text()
                    captures_to_process.append((capture, store, content))
            except FileNotFoundError:
                continue

    if not captures_to_process:
        console.print("[yellow]No captures to investigate.[/yellow]")
        raise typer.Exit(0)

    console.print(f"\nAnalyzing {len(captures_to_process)} capture(s)...\n")

    # Process each capture
    results: list[tuple[str, CaptureCategory, str]] = []
    quick_fixes: list[tuple[Capture, str]] = []

    for capture, store, content in captures_to_process:
        # Determine category
        category = mode if mode else categorize_capture(capture, content)

        console.print(f"[bold]{capture.id}[/bold]: {capture.title[:50]}...")
        console.print(f"  Category: [cyan]{category.value}[/cyan]")

        # Batch quick fixes if requested
        if batch_quick and category == CaptureCategory.QUICK:
            quick_fixes.append((capture, content))
            console.print("  Action: [dim]Batched for later[/dim]")
            results.append((capture.id, category, "Batched"))
            continue

        # Process based on category
        processor = PROCESSORS[category]
        result = processor(capture, content, dry_run=dry_run)
        console.print(f"  Action: {result}")
        results.append((capture.id, category, result))
        console.print()

    # Process batched quick fixes
    if quick_fixes:
        console.print(f"\n[bold]Processing {len(quick_fixes)} batched quick fixes...[/bold]")
        if dry_run:
            console.print("  [dim]Would create single task with all quick fixes[/dim]")
        else:
            # TODO: Create single task with all quick fixes
            console.print("  Created batched task")

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Category")
    table.add_column("Count")

    category_counts: dict[CaptureCategory, int] = {}
    for _, category, _ in results:
        category_counts[category] = category_counts.get(category, 0) + 1

    for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        table.add_row(category.value, str(count))

    console.print(table)
