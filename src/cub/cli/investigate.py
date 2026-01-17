"""
Cub CLI - Investigate command.

Intelligent capture processing that categorizes ideas and moves them forward.
"""

import re
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cub.core.captures.models import Capture
from cub.core.captures.store import CaptureStore
from cub.core.tasks import get_task_service

console = Console()
app = typer.Typer(help="Investigate and process captures")

# Default output directory for investigation artifacts
INVESTIGATIONS_DIR = Path("specs/investigations")


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
    combined = content_lower + " " + title_lower

    # Quick fix/enhancement indicators - small, well-defined changes
    quick_indicators = [
        # Fixes
        "fix typo",
        "fix bug",
        "fix error",
        "fix issue",
        # Removals
        "remove ",
        "delete ",
        "drop ",
        # Renames/updates
        "rename ",
        "update copyright",
        "change ",
        "replace ",
        # Additions (small)
        "add missing",
        "add option",
        "add flag",
        "add argument",
        "add param",
        "add a ",
        "add an ",
        # Small enhancements
        "should take",
        "should accept",
        "should support",
        "should have a",
        "should have an",
        "should include",
        "should allow",
        "needs a ",
        "needs an ",
        "could use",
        "make it ",
        "make the ",
        # Specific targets (suggests well-scoped change)
        "the script",
        "the function",
        "the command",
        "the file",
        "in the ",
    ]

    # Strong quick indicators - don't need length check
    strong_quick = [
        "fix typo",
        "fix bug",
        "remove ",
        "delete ",
        "rename ",
        "add option",
        "add flag",
        "add argument",
        "should take",
        "should accept",
    ]

    if any(ind in combined for ind in strong_quick):
        return CaptureCategory.QUICK

    # Weaker quick indicators need shorter content
    if any(ind in combined for ind in quick_indicators):
        if len(content) < 300:  # Increased threshold
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

    # Default logic for unmatched captures
    # Short captures without clear indicators need clarification
    if len(content) < 50:
        return CaptureCategory.UNCLEAR

    # Medium-length captures that mention specific code artifacts are likely quick tasks
    code_artifacts = ["script", "function", "class", "file", "module", "command", "cli", "api"]
    if len(content) < 300 and any(artifact in combined for artifact in code_artifacts):
        return CaptureCategory.QUICK

    # Longer content without clear indicators defaults to unclear (needs human triage)
    # rather than assuming design, since misclassification wastes effort
    return CaptureCategory.UNCLEAR


def _ensure_investigations_dir() -> Path:
    """Ensure the investigations directory exists and return its path."""
    INVESTIGATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return INVESTIGATIONS_DIR


def _extract_body_content(content: str) -> str:
    """Extract the body content from a capture (after frontmatter)."""
    # Skip YAML frontmatter if present
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()


def process_quick_fix(
    capture: Capture,
    content: str,
    dry_run: bool = False,
    store: CaptureStore | None = None,
) -> str:
    """
    Process a quick fix capture.

    Creates a beads task for the fix, then archives the capture.
    """
    if dry_run:
        return f"Would create task for: {capture.title}"

    body = _extract_body_content(content)
    context = f"Quick fix from capture {capture.id}:\n\n{body}"

    service = get_task_service()
    task = service.create_quick_fix(
        title=capture.title,
        context=context,
        labels=capture.tags,
        source_capture_id=capture.id,
    )

    if task and store:
        store.archive_capture(capture.id)
        return f"Created task {task.id}, archived capture"
    elif task:
        return f"Created task {task.id}"
    else:
        return "Failed to create task"


def process_audit(
    capture: Capture,
    content: str,
    dry_run: bool = False,
    store: CaptureStore | None = None,
) -> str:
    """
    Process a code audit capture.

    Extracts search patterns from the capture, runs code analysis,
    and produces a report in specs/investigations/.
    """
    if dry_run:
        return f"Would run code audit for: {capture.title}"

    body = _extract_body_content(content)

    # Try to extract search patterns from the content
    # Look for quoted strings, code references, or key terms
    patterns: list[str] = []

    # Extract quoted strings
    quoted = re.findall(r'"([^"]+)"', body) + re.findall(r"'([^']+)'", body)
    patterns.extend(quoted)

    # Extract potential code patterns (camelCase, snake_case, etc.)
    code_patterns = re.findall(r"\b[a-z]+(?:_[a-z]+)+\b", body)  # snake_case
    code_patterns += re.findall(r"\b[a-z]+(?:[A-Z][a-z]+)+\b", body)  # camelCase
    patterns.extend(code_patterns)

    # If no patterns found, use key nouns from the title
    if not patterns:
        # Simple extraction of potential search terms
        words = capture.title.lower().split()
        skip_words = {
            "the",
            "a",
            "an",
            "all",
            "find",
            "track",
            "audit",
            "where",
            "how",
            "many",
            "list",
            "search",
            "for",
            "in",
            "of",
            "to",
            "and",
            "or",
        }
        patterns = [w for w in words if w not in skip_words and len(w) > 2]

    # Run grep for each pattern and collect results
    findings: dict[str, list[str]] = {}

    for pattern in patterns[:5]:  # Limit to 5 patterns
        try:
            result = subprocess.run(
                ["rg", "-l", "--type-add", "code:*.py", "-t", "code", pattern],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )
            if result.stdout.strip():
                files = result.stdout.strip().split("\n")
                findings[pattern] = files[:20]  # Limit files per pattern
        except FileNotFoundError:
            # Fall back to grep if rg not available
            try:
                result = subprocess.run(
                    ["grep", "-rl", pattern, "--include=*.py", "."],
                    capture_output=True,
                    text=True,
                    cwd=Path.cwd(),
                )
                if result.stdout.strip():
                    files = result.stdout.strip().split("\n")
                    findings[pattern] = files[:20]
            except FileNotFoundError:
                pass

    # Generate report
    report_dir = _ensure_investigations_dir()
    report_file = report_dir / f"{capture.id}-audit.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    report_content = f"""# Audit Report: {capture.title}

**Capture ID:** {capture.id}
**Generated:** {timestamp}
**Category:** audit

## Original Capture

{body}

## Search Patterns

The following patterns were extracted and searched:

{chr(10).join(f'- `{p}`' for p in patterns[:5])}

## Findings

"""

    if findings:
        for pattern, files in findings.items():
            report_content += f"### Pattern: `{pattern}`\n\n"
            report_content += f"Found in {len(files)} file(s):\n\n"
            for f in files:
                report_content += f"- `{f}`\n"
            report_content += "\n"
    else:
        report_content += "*No matches found for the extracted patterns.*\n\n"

    report_content += """## Next Steps

- [ ] Review the findings above
- [ ] Identify patterns that need changes
- [ ] Create tasks for necessary modifications

## Notes

*Add your analysis notes here.*
"""

    report_file.write_text(report_content)

    # Update capture with link to report
    if store:
        store.update_capture(
            capture.id,
            append_content=f"\n---\n**Audit completed:** {timestamp}\n**Report:** {report_file}",
        )

    return f"Report generated: {report_file}"


def process_research(
    capture: Capture,
    content: str,
    dry_run: bool = False,
    store: CaptureStore | None = None,
) -> str:
    """
    Process a research capture.

    Creates a research template with the capture context,
    ready for web search and summarization.
    """
    if dry_run:
        return f"Would research: {capture.title}"

    body = _extract_body_content(content)

    # Generate research template
    report_dir = _ensure_investigations_dir()
    report_file = report_dir / f"{capture.id}-research.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Extract potential search queries from the content
    queries = [capture.title]
    # Look for questions in the content
    questions = re.findall(r"[^.!?]*\?", body)
    queries.extend([q.strip() for q in questions[:3]])

    report_content = f"""# Research: {capture.title}

**Capture ID:** {capture.id}
**Generated:** {timestamp}
**Category:** research
**Status:** needs_research

## Original Capture

{body}

## Suggested Search Queries

{chr(10).join(f'- [ ] "{q}"' for q in queries)}

## Research Findings

*This section should be filled in with research results.*

### Key Sources

1. *Source 1*
2. *Source 2*
3. *Source 3*

### Summary

*Summarize the key findings here.*

### Relevant Code/Tools

*List any relevant tools, libraries, or code examples found.*

## Recommendations

*Based on the research, what actions should be taken?*

- [ ] Recommendation 1
- [ ] Recommendation 2

## Next Steps

- [ ] Complete web searches for suggested queries
- [ ] Summarize findings
- [ ] Create actionable tasks from recommendations
"""

    report_file.write_text(report_content)

    # Mark capture for human review since research needs manual/AI work
    if store:
        store.update_capture(
            capture.id,
            needs_human_review=True,
            append_content=f"\n---\n**Research template created:** {timestamp}\n"
            f"**Template:** {report_file}",
        )

    return f"Research template: {report_file} (needs completion)"


def process_design(
    capture: Capture,
    content: str,
    dry_run: bool = False,
    store: CaptureStore | None = None,
) -> str:
    """
    Process a design capture.

    Creates a design document template for review.
    """
    if dry_run:
        return f"Would create design doc for: {capture.title}"

    body = _extract_body_content(content)

    # Generate design document
    report_dir = _ensure_investigations_dir()
    report_file = report_dir / f"{capture.id}-design.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    report_content = f"""# Design: {capture.title}

**Capture ID:** {capture.id}
**Generated:** {timestamp}
**Category:** design
**Status:** draft

## Problem Statement

{body}

## Goals

*What are we trying to achieve?*

- [ ] Goal 1
- [ ] Goal 2

## Non-Goals

*What is explicitly out of scope?*

-

## Background & Context

*What context is needed to understand this design?*

## Proposed Solution

### Overview

*High-level description of the proposed approach.*

### Detailed Design

*Detailed explanation of the solution.*

### Alternatives Considered

*What other approaches were considered and why were they rejected?*

1. **Alternative 1:** *description*
   - Pros:
   - Cons:

## Implementation Plan

*How will this be implemented?*

### Phase 1

- [ ] Task 1
- [ ] Task 2

### Phase 2

- [ ] Task 3
- [ ] Task 4

## Open Questions

*What questions need to be answered?*

- [ ] Question 1
- [ ] Question 2

## Feedback Requested

*What specific feedback is needed?*

---

## Feedback Log

*Record feedback received here.*

| Date | From | Feedback | Resolution |
|------|------|----------|------------|
| | | | |
"""

    report_file.write_text(report_content)

    # Mark for human review
    if store:
        store.update_capture(
            capture.id,
            needs_human_review=True,
            append_content=f"\n---\n**Design doc created:** {timestamp}\n"
            f"**Document:** {report_file}",
        )

    return f"Design doc: {report_file} (needs review)"


def process_spike(
    capture: Capture,
    content: str,
    dry_run: bool = False,
    store: CaptureStore | None = None,
) -> str:
    """
    Process a spike capture.

    Creates a beads task for exploratory work on a branch.
    """
    if dry_run:
        return f"Would create spike task for: {capture.title}"

    body = _extract_body_content(content)

    # Extract exploration goals from the body if possible
    exploration_goals = [body] if body else ["Validate approach", "Document findings"]

    service = get_task_service()
    task = service.create_spike(
        title=capture.title,
        context=f"Spike from capture {capture.id}",
        exploration_goals=exploration_goals,
        labels=capture.tags,
        source_capture_id=capture.id,
    )

    if task and store:
        store.archive_capture(capture.id)
        return f"Created spike task {task.id}, archived capture"
    elif task:
        return f"Created spike task {task.id}"
    else:
        return "Failed to create spike task"


def process_unclear(
    capture: Capture,
    content: str,
    dry_run: bool = False,
    store: CaptureStore | None = None,
) -> str:
    """
    Process an unclear capture.

    Marks for human review with clarifying questions.
    """
    if dry_run:
        return f"Would ask clarifying questions for: {capture.title}"

    body = _extract_body_content(content)

    # Generate clarifying questions based on what's missing
    questions = []

    if len(body) < 20:
        questions.append("Can you provide more context about what you're trying to accomplish?")

    if "?" not in body:
        questions.append("What specific question are you trying to answer?")

    # Check for missing context
    if not any(word in body.lower() for word in ["because", "since", "so that", "in order"]):
        questions.append("What is the motivation or goal behind this idea?")

    if not any(
        word in body.lower() for word in ["file", "function", "class", "module", "component"]
    ):
        questions.append("Which part of the codebase does this relate to?")

    # Default questions if we couldn't generate specific ones
    if not questions:
        questions = [
            "What specific outcome are you hoping for?",
            "What have you already tried or considered?",
            "Are there any constraints or requirements to be aware of?",
        ]

    # Update capture with questions and mark for review
    questions_text = "\n".join(f"- {q}" for q in questions)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if store:
        store.update_capture(
            capture.id,
            needs_human_review=True,
            append_content=f"""
---

**Clarification needed** ({timestamp})

This capture needs more detail before it can be processed. Please answer the following questions:

{questions_text}

Once clarified, run `cub investigate {capture.id}` again.
""",
        )
        return f"Marked for review with {len(questions)} questions"

    return f"Needs clarification ({len(questions)} questions)"


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
    - spike: Exploratory work → create spike task
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
                    # Skip captures already marked for review or archived
                    if capture.needs_human_review:
                        continue
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
    quick_fixes: list[tuple[Capture, CaptureStore, str]] = []

    for capture, store, content in captures_to_process:
        # Determine category
        category = mode if mode else categorize_capture(capture, content)

        console.print(f"[bold]{capture.id}[/bold]: {capture.title[:50]}...")
        console.print(f"  Category: [cyan]{category.value}[/cyan]")

        # Batch quick fixes if requested
        if batch_quick and category == CaptureCategory.QUICK:
            quick_fixes.append((capture, store, content))
            console.print("  Action: [dim]Batched for later[/dim]")
            results.append((capture.id, category, "Batched"))
            continue

        # Process based on category
        processor = PROCESSORS[category]
        result = processor(capture, content, dry_run=dry_run, store=store)
        console.print(f"  Action: {result}")
        results.append((capture.id, category, result))
        console.print()

    # Process batched quick fixes
    if quick_fixes:
        console.print(f"\n[bold]Processing {len(quick_fixes)} batched quick fixes...[/bold]")
        if dry_run:
            console.print("  [dim]Would create single task with all quick fixes[/dim]")
        else:
            # Create a single task with all quick fixes
            all_tags: set[str] = set()
            for c, _, _ in quick_fixes:
                all_tags.update(c.tags)

            # Build items list for batched task
            items: list[tuple[str, str]] = []
            for capture, _, content in quick_fixes:
                body = _extract_body_content(content)
                items.append((f"{capture.id}: {capture.title}", body))

            service = get_task_service()
            task = service.create_batched_task(
                title=f"Quick fixes batch ({len(quick_fixes)} items)",
                items=items,
                labels=["quick-fix"] + list(all_tags),
            )

            if task:
                console.print(f"  Created batched task: {task.id}")
                # Archive all the captures
                for capture, qf_store, _ in quick_fixes:
                    try:
                        qf_store.archive_capture(capture.id)
                    except Exception as e:
                        console.print(
                            f"  [yellow]Warning:[/yellow] Could not archive {capture.id}: {e}"
                        )
            else:
                console.print("  [red]Failed to create batched task[/red]")

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
