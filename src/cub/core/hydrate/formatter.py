"""
Markdown formatter for hydration results.

Generates itemized-plan.md format from hydration results,
compatible with `cub stage` for importing into the task backend.
"""

from datetime import datetime, timezone
from pathlib import Path

from cub.core.hydrate.models import HydrationResult
from cub.core.plan.ids import generate_epic_id, generate_task_id


def generate_itemized_plan(
    results: list[HydrationResult],
    epic_title: str,
    source_path: Path | None = None,
    labels: list[str] | None = None,
    project_id: str = "cub",
) -> str:
    """
    Generate itemized-plan.md content from hydration results.

    The output is compatible with the plan parser and `cub stage`.

    Args:
        results: List of hydrated items to include as tasks.
        epic_title: Title for the epic.
        source_path: Path to the source file (for metadata).
        labels: Additional labels for the epic.
        project_id: Project identifier for ID generation.

    Returns:
        Markdown string in itemized-plan.md format.
    """
    epic_id = generate_epic_id(project_id)
    filename = source_path.name if source_path else "punchlist"
    stem = source_path.stem if source_path else "punchlist"
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    epic_labels = ["punchlist", f"punchlist:{stem}"]
    if labels:
        epic_labels.extend(labels)

    lines: list[str] = []

    # Header
    lines.append(f"# Itemized Plan: {epic_title}")
    lines.append("")
    if source_path:
        lines.append(f"> Source: [{filename}]({source_path})")
    lines.append(f"> Generated: {now}")
    lines.append("")

    # Context summary
    lines.append("## Context Summary")
    lines.append(f"Tasks generated from punchlist: {filename}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Epic section
    lines.append(f"## Epic: {epic_id} - {epic_title}")
    lines.append("Priority: 2")
    lines.append(f"Labels: {', '.join(epic_labels)}")
    lines.append("")
    lines.append(f"Punchlist tasks from: {filename}")
    lines.append("")

    # Tasks
    for i, result in enumerate(results, 1):
        task_id = generate_task_id(epic_id, i)

        lines.append(f"### Task: {task_id} - {result.title}")
        lines.append("Priority: 2")
        lines.append("Labels: punchlist")
        lines.append("")

        if result.context:
            lines.append(f"**Context**: {result.context}")
            lines.append("")

        if result.implementation_steps:
            lines.append("**Implementation Steps**:")
            for step_num, step in enumerate(result.implementation_steps, 1):
                lines.append(f"{step_num}. {step}")
            lines.append("")

        if result.acceptance_criteria:
            lines.append("**Acceptance Criteria**:")
            for criterion in result.acceptance_criteria:
                lines.append(f"- [ ] {criterion}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
