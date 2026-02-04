"""
Retro service for generating retrospective reports.

Provides high-level operations for:
- Generating retrospective reports from ledger data
- Analyzing completed tasks, epics, and plans
- Summarizing metrics, outcomes, and lessons learned
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class RetroServiceError(Exception):
    """Error from retro service operations."""

    pass


@dataclass
class RetroReport:
    """
    Retrospective report for a completed plan or epic.

    Contains summary, metrics, issues encountered, and lessons learned.
    """

    # Identification
    id: str
    title: str
    report_type: str  # "epic" or "plan"
    generated_at: datetime

    # Summary
    description: str
    status: str
    total_tasks: int
    tasks_completed: int
    tasks_successful: int
    tasks_failed: int

    # Metrics
    total_cost_usd: float
    avg_cost_per_task: float
    total_duration_seconds: int
    avg_duration_seconds: int
    total_tokens: int
    avg_tokens_per_task: int
    total_escalations: int
    escalation_rate: float

    # Timeline
    started_at: datetime | None
    completed_at: datetime | None

    # Commits
    first_commit: dict[str, str] | None
    last_commit: dict[str, str] | None
    total_commits: int

    # Analysis
    task_list: list[dict[str, str | float | int | bool]] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    issues_encountered: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """
        Generate markdown representation of the report.

        Returns:
            Formatted markdown string
        """
        lines: list[str] = []

        # Header
        lines.append(f"# Retrospective: {self.title}")
        lines.append("")
        lines.append(f"**ID:** {self.id}  ")
        lines.append(f"**Type:** {self.report_type.title()}  ")
        lines.append(f"**Status:** {self.status}  ")
        lines.append(
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  "
        )
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        if self.description:
            lines.append(self.description)
            lines.append("")

        # Timeline
        if self.started_at or self.completed_at:
            lines.append("### Timeline")
            lines.append("")
            if self.started_at:
                lines.append(
                    f"- **Started:** {self.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
            if self.completed_at:
                lines.append(
                    f"- **Completed:** {self.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
            if self.started_at and self.completed_at:
                duration = self.completed_at - self.started_at
                days = duration.days
                hours = duration.seconds // 3600
                minutes = (duration.seconds % 3600) // 60
                lines.append(
                    f"- **Duration:** {days}d {hours}h {minutes}m"
                )
            lines.append("")

        # Metrics
        lines.append("## Metrics")
        lines.append("")
        lines.append(f"- **Total Tasks:** {self.total_tasks}")
        if self.total_tasks > 0:
            completion_rate = self.tasks_completed / self.total_tasks * 100
            lines.append(
                f"- **Completed:** {self.tasks_completed} "
                f"({completion_rate:.1f}% completion rate)"
            )
        else:
            lines.append("- **Completed:** 0")

        if self.tasks_completed > 0:
            success_rate = self.tasks_successful / self.tasks_completed * 100
            lines.append(
                f"- **Successful:** {self.tasks_successful} "
                f"({success_rate:.1f}% success rate)"
            )
        else:
            lines.append("- **Successful:** 0")
        if self.tasks_failed > 0:
            lines.append(f"- **Failed:** {self.tasks_failed}")
        lines.append("")

        lines.append("### Cost & Resources")
        lines.append("")
        lines.append(f"- **Total Cost:** ${self.total_cost_usd:.2f}")
        lines.append(f"- **Average Cost per Task:** ${self.avg_cost_per_task:.2f}")
        lines.append(f"- **Total Tokens:** {self.total_tokens:,}")
        lines.append(f"- **Average Tokens per Task:** {self.avg_tokens_per_task:,}")
        lines.append("")

        lines.append("### Time")
        lines.append("")
        hours = self.total_duration_seconds // 3600
        minutes = (self.total_duration_seconds % 3600) // 60
        lines.append(f"- **Total Duration:** {hours}h {minutes}m")
        avg_hours = self.avg_duration_seconds // 3600
        avg_minutes = (self.avg_duration_seconds % 3600) // 60
        lines.append(f"- **Average Duration per Task:** {avg_hours}h {avg_minutes}m")
        lines.append("")

        if self.total_escalations > 0:
            lines.append("### Escalations")
            lines.append("")
            lines.append(f"- **Total Escalations:** {self.total_escalations}")
            lines.append(f"- **Escalation Rate:** {self.escalation_rate*100:.1f}%")
            lines.append("")

        # Commits
        if self.total_commits > 0:
            lines.append("## Commits")
            lines.append("")
            lines.append(f"**Total Commits:** {self.total_commits}")
            lines.append("")
            if self.first_commit:
                lines.append("**First Commit:**")
                hash_short = self.first_commit.get("hash", "N/A")[:7]
                message = self.first_commit.get("message", "N/A")
                lines.append(f"- `{hash_short}` - {message}")
                lines.append("")
            if self.last_commit:
                lines.append("**Last Commit:**")
                hash_short = self.last_commit.get("hash", "N/A")[:7]
                message = self.last_commit.get("message", "N/A")
                lines.append(f"- `{hash_short}` - {message}")
                lines.append("")

        # Task List
        if self.task_list:
            lines.append("## Tasks")
            lines.append("")
            for task_info in self.task_list:
                task_id = task_info.get("id", "unknown")
                task_title = task_info.get("title", "Untitled")
                success = task_info.get("success", False)
                cost = task_info.get("cost_usd", 0.0)
                attempts = task_info.get("attempts", 1)
                status_icon = "✓" if success else "✗"

                lines.append(
                    f"- [{status_icon}] **{task_id}**: {task_title} "
                    f"(${cost:.2f}, {attempts} attempt{'s' if attempts != 1 else ''})"
                )
            lines.append("")

        # Decisions
        if self.decisions:
            lines.append("## Key Decisions")
            lines.append("")
            for decision in self.decisions:
                lines.append(f"- {decision}")
            lines.append("")

        # Lessons Learned
        if self.lessons_learned:
            lines.append("## Lessons Learned")
            lines.append("")
            for lesson in self.lessons_learned:
                lines.append(f"- {lesson}")
            lines.append("")

        # Issues
        if self.issues_encountered:
            lines.append("## Issues Encountered")
            lines.append("")
            for issue in self.issues_encountered:
                lines.append(f"- {issue}")
            lines.append("")

        return "\n".join(lines)


class RetroService:
    """
    Service for generating retrospective reports.

    Provides high-level operations for:
    - Generating retro reports for completed epics
    - Analyzing task outcomes and metrics
    - Extracting lessons learned and key decisions

    Example:
        >>> service = RetroService(Path.cwd())
        >>> report = service.generate_retro("cub-048a-4")
        >>> print(report.to_markdown())
    """

    def __init__(self, project_dir: Path | None = None) -> None:
        """
        Initialize RetroService.

        Args:
            project_dir: Project directory (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self.ledger_dir = self.project_dir / ".cub" / "ledger"

    def generate_retro(self, id: str, *, epic: bool = False) -> RetroReport:
        """
        Generate a retrospective report.

        Args:
            id: Epic or plan ID
            epic: If True, treat as epic ID (default: auto-detect)

        Returns:
            RetroReport containing analysis and metrics

        Raises:
            RetroServiceError: If report generation fails
        """
        logger.info(f"Generating retrospective for {id}")

        # Determine if this is an epic or plan
        # For now, we'll treat everything as an epic since the ledger
        # structure uses by-epic and by-task
        entry_path = self.ledger_dir / "by-epic" / id / "entry.json"

        if not entry_path.exists():
            raise RetroServiceError(
                f"Epic {id} not found in ledger. "
                f"Expected: {entry_path}"
            )

        # Load epic entry
        try:
            with entry_path.open("r") as f:
                epic_data = json.load(f)
        except Exception as e:
            raise RetroServiceError(f"Failed to load epic data: {e}")

        # Extract basic info
        epic_info = epic_data.get("epic", {})
        aggregates = epic_data.get("aggregates", {})

        # Parse timestamps
        started_at = None
        completed_at = None
        if epic_data.get("started_at"):
            try:
                started_at = datetime.fromisoformat(
                    epic_data["started_at"].replace("Z", "+00:00")
                )
            except Exception:
                pass
        if epic_data.get("completed_at"):
            try:
                completed_at = datetime.fromisoformat(
                    epic_data["completed_at"].replace("Z", "+00:00")
                )
            except Exception:
                pass

        # Parse commits
        first_commit = epic_data.get("first_commit")
        last_commit = epic_data.get("last_commit")

        # Count commits by collecting from all tasks
        task_ids = epic_data.get("task_ids", [])
        total_commits = 0
        task_list: list[dict[str, str | float | int | bool]] = []
        all_decisions: list[str] = []
        all_lessons: list[str] = []

        # Load task details
        for task_id in task_ids:
            task_path = self.ledger_dir / "by-task" / f"{task_id}.json"
            if not task_path.exists():
                continue

            try:
                with task_path.open("r") as f:
                    task_data = json.load(f)

                # Count commits
                commits = task_data.get("commits", [])
                total_commits += len(commits)

                # Extract task info
                outcome = task_data.get("outcome", {})
                task_list.append({
                    "id": task_id,
                    "title": task_data.get("task", {}).get("title", "Untitled"),
                    "success": outcome.get("success", False),
                    "cost_usd": outcome.get("total_cost_usd", 0.0),
                    "attempts": outcome.get("total_attempts", 1),
                })

                # Collect decisions and lessons
                decisions = task_data.get("decisions", [])
                if decisions:
                    all_decisions.extend(decisions)

                lessons = task_data.get("lessons_learned", [])
                if lessons:
                    all_lessons.extend(lessons)

            except Exception as e:
                logger.warning(f"Failed to load task {task_id}: {e}")
                continue

        # Create report
        report = RetroReport(
            id=id,
            title=epic_info.get("title", id),
            report_type="epic",
            generated_at=datetime.utcnow(),
            description=epic_info.get("description", ""),
            status=epic_info.get("status", "unknown"),
            total_tasks=aggregates.get("total_tasks", 0),
            tasks_completed=aggregates.get("tasks_completed", 0),
            tasks_successful=aggregates.get("tasks_successful", 0),
            tasks_failed=aggregates.get("tasks_failed", 0),
            total_cost_usd=aggregates.get("total_cost_usd", 0.0),
            avg_cost_per_task=aggregates.get("avg_cost_per_task", 0.0),
            total_duration_seconds=aggregates.get("total_duration_seconds", 0),
            avg_duration_seconds=aggregates.get("avg_duration_seconds", 0),
            total_tokens=aggregates.get("total_tokens", 0),
            avg_tokens_per_task=aggregates.get("avg_tokens_per_task", 0),
            total_escalations=aggregates.get("total_escalations", 0),
            escalation_rate=aggregates.get("escalation_rate", 0.0),
            started_at=started_at,
            completed_at=completed_at,
            first_commit=first_commit,
            last_commit=last_commit,
            total_commits=total_commits,
            task_list=task_list,
            decisions=all_decisions,
            lessons_learned=all_lessons,
            issues_encountered=[],  # Could extract from error summaries in the future
        )

        return report
