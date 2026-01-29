"""
AgentFormatter — structured markdown output for LLM consumption.

Transforms service-layer data into structured markdown following the envelope
template: heading, summary line, data tables, truncation notice, analysis section.

The formatter returns plain strings — no Rich, no console. DependencyGraph is an
optional parameter; when None, analysis hints that require graph queries are omitted.

Design principles:
- Summary line first (Claude can echo directly)
- Tables for lists (compact, parseable)
- Truncation with explicit notices
- Analysis section with pre-computed hints
- Target: <500 tokens per output (~2000 chars)
"""

from __future__ import annotations

from cub.core.services.models import EpicProgress, ProjectStats
from cub.core.suggestions.models import Suggestion
from cub.core.tasks.graph import DependencyGraph
from cub.core.tasks.models import Task


class AgentFormatter:
    """Static methods that transform service-layer data into structured markdown.

    Each method follows the envelope template:
    1. Heading (# command name)
    2. Summary line (key numbers)
    3. Data tables (compact, scannable)
    4. Truncation notice (if applicable)
    5. Analysis section (pre-computed insights)

    Example:
        >>> tasks = backend.get_ready_tasks()
        >>> graph = DependencyGraph(backend.list_tasks())
        >>> output = AgentFormatter.format_ready(tasks, graph)
        >>> print(output)
    """

    # Default truncation limit for lists
    DEFAULT_LIMIT = 10

    # ============================================================================
    # Shared helpers
    # ============================================================================

    @staticmethod
    def _truncate_table(
        items: list[str], limit: int | None = None, total: int | None = None
    ) -> str:
        """Format a table with truncation notice if needed.

        Args:
            items: List of table rows (already formatted as markdown)
            limit: Maximum items to show (None = show all)
            total: Total items available (for truncation notice)

        Returns:
            Markdown string with table rows and optional truncation notice
        """
        if limit is None:
            limit = AgentFormatter.DEFAULT_LIMIT

        total = total or len(items)
        rows = items[:limit]
        result = "\n".join(rows)

        if total > limit:
            result += f"\n\nShowing {limit} of {total}. Use --all for complete list."

        return result

    @staticmethod
    def _format_blocks_count(count: int) -> str:
        """Format blocks count as human-readable string."""
        if count == 0:
            return "none"
        if count == 1:
            return "1 task"
        return f"{count} tasks"

    @staticmethod
    def _truncate_description(text: str, max_chars: int = 500) -> str:
        """Truncate description to max_chars, appending '...' if truncated."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "..."

    # ============================================================================
    # format_ready
    # ============================================================================

    @staticmethod
    def format_ready(tasks: list[Task], graph: DependencyGraph | None = None) -> str:
        """Format ready tasks as structured markdown.

        Args:
            tasks: List of ready tasks (open, no blockers)
            graph: Optional dependency graph for impact analysis

        Returns:
            Markdown string following envelope template

        Example output:
            # cub task ready

            3 tasks ready to work on. 18 blocked across 5 dependency chains.

            ## Ready Tasks

            | ID | Title | Pri | Blocks |
            |----|-------|-----|--------|
            | cub-r6s.1 | Define InstructionConfig model | P1 | 3 tasks |

            ## Analysis

            - **Highest impact**: cub-r6s.1 unblocks 3 downstream tasks
            - **Recommendation**: Start with cub-r6s.1 — unblocks the most work
        """
        count = len(tasks)

        # Build summary line
        summary = f"{count} task{'s' if count != 1 else ''} ready to work on"

        # Add blocked task count if we have a graph
        if graph:
            stats = graph.stats
            total_blocked = stats["node_count"] - count
            chains = len(graph.chains(limit=100))
            if total_blocked > 0:
                summary += f". {total_blocked} blocked across {chains} dependency chain"
                summary += "s" if chains != 1 else ""

        summary += "."

        output = f"# cub task ready\n\n{summary}\n\n"

        # Early return if no tasks
        if count == 0:
            return output.rstrip()

        # Build table
        output += "## Ready Tasks\n\n"
        output += "| ID | Title | Pri | Blocks |\n"
        output += "|----|-------|-----|--------|\n"

        rows = []
        for task in tasks:
            blocks_count = len(task.blocks)
            blocks_str = AgentFormatter._format_blocks_count(blocks_count)
            rows.append(f"| {task.id} | {task.title} | {task.priority.value} | {blocks_str} |")

        output += AgentFormatter._truncate_table(rows, total=count)

        # Add analysis section if we have a graph
        if graph:
            output += "\n\n## Analysis\n\n"

            # Find highest impact task (blocks most)
            max_blocks = 0
            max_task = None
            for task in tasks:
                unblocks = len(graph.transitive_unblocks(task.id))
                if unblocks > max_blocks:
                    max_blocks = unblocks
                    max_task = task

            if max_task and max_blocks > 0:
                direct = graph.direct_unblocks(max_task.id)
                output += f"- **Highest impact**: {max_task.id} unblocks {max_blocks} "
                output += f"downstream task{'s' if max_blocks != 1 else ''}"
                if direct:
                    direct_str = ", ".join(direct[:3])
                    if len(direct) > 3:
                        direct_str += f", +{len(direct) - 3} more"
                    output += f" ({direct_str})"
                output += "\n"

            # Find highest priority task
            highest_pri = min(tasks, key=lambda t: t.priority_numeric)
            if highest_pri.priority_numeric < 2:  # P0 or P1
                pri_val = highest_pri.priority.value
                output += f"- **Highest priority**: {highest_pri.id} is {pri_val}"
                if highest_pri != max_task:
                    unblocks = len(graph.transitive_unblocks(highest_pri.id))
                    if unblocks > 0:
                        output += f", unblocks {unblocks} task"
                        output += "s" if unblocks != 1 else ""
                output += "\n"

            # Recommendation
            if max_task:
                output += f"- **Recommendation**: Start with {max_task.id} — unblocks the most work"

        return output.rstrip()

    # ============================================================================
    # format_task_detail
    # ============================================================================

    @staticmethod
    def format_task_detail(
        task: Task,
        graph: DependencyGraph | None = None,
        epic_progress: EpicProgress | None = None,
    ) -> str:
        """Format task detail as structured markdown.

        Args:
            task: Task to format
            graph: Optional dependency graph for impact analysis
            epic_progress: Optional epic progress for context

        Returns:
            Markdown string following envelope template

        Example output:
            # cub task show cub-r6s.1

            ## Define InstructionConfig model

            - **Priority**: P1
            - **Status**: open
            - **Epic**: cub-r6s (Instruction Generation)
            - **Type**: task

            ## Description

            Define the Pydantic model for instruction configuration...

            ## Dependencies

            - **Blocks**: cub-r6s.2, cub-r6s.3, cub-r6s.6
            - **Blocked by**: none (ready to work)
            - **Epic progress**: 0/6 tasks complete

            ## Analysis

            - **Context**: Foundation task for instruction generation epic
            - **Recommendation**: Claim and start — nothing blocks this
        """
        output = f"# cub task show {task.id}\n\n"
        output += f"## {task.title}\n\n"

        # Metadata
        output += f"- **Priority**: {task.priority.value}\n"
        output += f"- **Status**: {task.status.value}\n"

        if task.parent:
            parent_title = ""
            if epic_progress:
                parent_title = f" ({epic_progress.epic_title})"
            output += f"- **Epic**: {task.parent}{parent_title}\n"

        output += f"- **Type**: {task.type.value}\n"

        if task.assignee:
            output += f"- **Assignee**: {task.assignee}\n"

        if task.labels:
            output += f"- **Labels**: {', '.join(task.labels)}\n"

        # Description
        if task.description:
            output += "\n## Description\n\n"
            output += AgentFormatter._truncate_description(task.description)
            output += "\n"

        # Dependencies
        has_deps = task.depends_on or task.blocks or epic_progress
        if has_deps:
            output += "\n## Dependencies\n\n"

            # Blocks
            if task.blocks:
                blocks_str = ", ".join(task.blocks)
                output += f"- **Blocks**: {blocks_str}\n"
            else:
                output += "- **Blocks**: none\n"

            # Blocked by
            if task.depends_on:
                deps_str = ", ".join(task.depends_on)
                output += f"- **Blocked by**: {deps_str}\n"
            else:
                output += "- **Blocked by**: none (ready to work)\n"

            # Epic progress
            if epic_progress:
                total = epic_progress.total_tasks
                closed = epic_progress.closed_tasks
                output += f"- **Epic progress**: {closed}/{total} tasks complete"
                if total > 0:
                    pct = epic_progress.completion_percentage
                    output += f" ({pct:.0f}%)"
                output += "\n"

        # Analysis
        if graph or epic_progress:
            output += "\n## Analysis\n\n"

            # Context from epic
            if epic_progress and task.parent:
                ready = epic_progress.ready_tasks
                blocked = epic_progress.total_tasks - epic_progress.closed_tasks - ready
                if task.is_ready and blocked > 0:
                    output += f"- **Context**: Foundation task that unblocks {blocked} other "
                    output += f"task{'s' if blocked != 1 else ''} in this epic\n"

            # Impact analysis from graph
            if graph:
                unblocks = len(graph.transitive_unblocks(task.id))
                if unblocks > 0:
                    output += f"- **Impact**: Unblocks {unblocks} downstream task"
                    output += "s" if unblocks != 1 else ""
                    output += "\n"

                # Recommendation
                if task.is_ready:
                    output += "- **Recommendation**: Claim and start — nothing blocks this"
                elif task.depends_on:
                    output += f"- **Recommendation**: Wait for {len(task.depends_on)} "
                    output += "dependency" if len(task.depends_on) == 1 else "dependencies"
                    output += " to close"

        return output.rstrip()

    # ============================================================================
    # format_status
    # ============================================================================

    @staticmethod
    def format_status(
        stats: ProjectStats, epic_progress: EpicProgress | None = None
    ) -> str:
        """Format project status as structured markdown.

        Args:
            stats: Project statistics
            epic_progress: Optional epic progress for focused view

        Returns:
            Markdown string following envelope template

        Example output:
            # cub status

            42 tasks: 24 closed (57%), 3 in progress, 15 open. 18 blocked, 3 ready.

            ## Breakdown

            | Status | Count | Pct |
            |--------|-------|-----|
            | Closed | 24 | 57% |

            ## Analysis

            - **Bottleneck**: 3 root blockers gate all 18 blocked tasks
        """
        total = stats.total_tasks
        closed = stats.closed_tasks
        in_prog = stats.in_progress_tasks
        open_count = stats.open_tasks
        blocked = stats.blocked_tasks
        ready = stats.ready_tasks
        pct = stats.completion_percentage

        # Summary line
        output = "# cub status\n\n"
        output += f"{total} tasks: {closed} closed ({pct:.0f}%), "
        output += f"{in_prog} in progress, {open_count} open. "
        output += f"{blocked} blocked, {ready} ready.\n\n"

        # Breakdown table
        output += "## Breakdown\n\n"
        output += "| Status | Count | Pct |\n"
        output += "|--------|-------|-----|\n"

        if total > 0:
            closed_pct = (closed / total) * 100
            in_prog_pct = (in_prog / total) * 100
            ready_pct = (ready / total) * 100
            blocked_pct = (blocked / total) * 100

            output += f"| Closed | {closed} | {closed_pct:.0f}% |\n"
            output += f"| In Progress | {in_prog} | {in_prog_pct:.0f}% |\n"
            output += f"| Ready | {ready} | {ready_pct:.0f}% |\n"
            output += f"| Blocked | {blocked} | {blocked_pct:.0f}% |\n"
        else:
            output += "| No tasks | 0 | 0% |\n"

        # Epic progress section (if provided)
        if epic_progress:
            output += "\n## Epic Progress\n\n"
            output += f"**{epic_progress.epic_id}**: {epic_progress.epic_title}\n\n"
            output += f"- **Progress**: {epic_progress.closed_tasks}/{epic_progress.total_tasks} "
            output += f"complete ({epic_progress.completion_percentage:.0f}%)\n"
            output += f"- **Ready**: {epic_progress.ready_tasks} tasks\n"

            in_prog_epic = epic_progress.in_progress_tasks
            blocked_epic = (
                epic_progress.total_tasks
                - epic_progress.closed_tasks
                - epic_progress.ready_tasks
                - in_prog_epic
            )

            if in_prog_epic > 0:
                output += f"- **In progress**: {in_prog_epic} tasks\n"
            if blocked_epic > 0:
                output += f"- **Blocked**: {blocked_epic} tasks\n"

            # Cost metrics
            if epic_progress.total_cost_usd > 0:
                output += f"- **Cost**: ${epic_progress.total_cost_usd:.2f} "
                output += f"({epic_progress.tasks_with_cost} tasks)\n"

        # Analysis section
        output += "\n## Analysis\n\n"

        if blocked > 0 and ready > 0:
            output += f"- **Bottleneck**: {blocked} tasks blocked, {ready} ready to unblock them\n"
        elif blocked > 0:
            output += f"- **Bottleneck**: {blocked} tasks blocked with no ready tasks to unblock\n"
        elif ready > 0:
            output += f"- **Ready**: {ready} tasks available to work on\n"

        if stats.has_uncommitted_changes:
            output += "- **Git**: Uncommitted changes present\n"

        if stats.commits_since_main > 0:
            output += f"- **Git**: {stats.commits_since_main} commits ahead of main\n"

        # Ledger insights
        if stats.tasks_in_ledger > 0:
            output += f"- **Ledger**: {stats.tasks_in_ledger} tasks tracked, "
            output += f"${stats.total_cost_usd:.2f} total cost\n"

        return output.rstrip()

    # ============================================================================
    # format_suggestions
    # ============================================================================

    @staticmethod
    def format_suggestions(suggestions: list[Suggestion]) -> str:
        """Format suggestions as structured markdown.

        Args:
            suggestions: List of ranked suggestions

        Returns:
            Markdown string following envelope template

        Example output:
            # cub suggest

            3 recommendations based on current project state.

            ## Suggestions

            | Priority | Action | Target | Rationale |
            |----------|--------|--------|-----------|
            | 1 | Unblock work | cub-r6s.1 | P1, unblocks 3 tasks |
        """
        count = len(suggestions)

        output = "# cub suggest\n\n"
        output += f"{count} recommendation{'s' if count != 1 else ''} "
        output += "based on current project state.\n\n"

        if count == 0:
            return output.rstrip()

        output += "## Suggestions\n\n"
        output += "| Priority | Category | Title | Rationale |\n"
        output += "|----------|----------|-------|----------|\n"

        rows = []
        for i, sug in enumerate(suggestions, 1):
            # Truncate long rationale
            rationale = sug.rationale
            if len(rationale) > 80:
                rationale = rationale[:77] + "..."

            rows.append(
                f"| {i} | {sug.category.value} | {sug.title} | {rationale} |"
            )

        output += AgentFormatter._truncate_table(rows, total=count)

        return output.rstrip()


__all__ = ["AgentFormatter"]
