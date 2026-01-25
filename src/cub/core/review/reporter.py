"""
Reporter for rendering review assessments with Rich formatting.

This module provides the ReviewReporter class for displaying
task, epic, and plan assessments in the terminal.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cub.core.review.models import (
    AssessmentGrade,
    EpicAssessment,
    IssueSeverity,
    PlanAssessment,
    ReviewIssue,
    TaskAssessment,
)


def _grade_style(grade: AssessmentGrade) -> str:
    """Get Rich style for a grade."""
    if grade == AssessmentGrade.PASS:
        return "bold green"
    elif grade == AssessmentGrade.PARTIAL:
        return "bold yellow"
    elif grade == AssessmentGrade.FAIL:
        return "bold red"
    else:
        return "dim"


def _grade_badge(grade: AssessmentGrade) -> Text:
    """Create a colored badge for a grade."""
    style = _grade_style(grade)
    return Text(f"[{grade.value.upper()}]", style=style)


def _severity_style(severity: IssueSeverity) -> str:
    """Get Rich style for a severity level."""
    if severity == IssueSeverity.CRITICAL:
        return "bold red"
    elif severity == IssueSeverity.WARNING:
        return "yellow"
    else:
        return "dim"


class ReviewReporter:
    """Reporter for rendering review assessments with Rich formatting."""

    def __init__(self, console: Console | None = None, verbose: bool = False) -> None:
        """Initialize the reporter.

        Args:
            console: Rich console for output (creates default if None)
            verbose: Whether to show detailed output
        """
        self.console = console or Console()
        self.verbose = verbose

    def render_task_assessment(self, assessment: TaskAssessment) -> None:
        """Render a task assessment with Rich formatting.

        Args:
            assessment: TaskAssessment to render
        """
        # Build title with grade badge
        title = Text()
        title.append("Task: ", style="bold")
        title.append(f"{assessment.task_id} - {assessment.title}\n")
        title.append("Grade: ")
        title.append_text(_grade_badge(assessment.grade))

        self.console.print()
        self.console.print(Panel(title, expand=False))

        # Metrics section
        metrics = Table(show_header=False, box=None, padding=(0, 2))
        metrics.add_column("Label", style="dim")
        metrics.add_column("Value")

        metrics.add_row("Verification:", assessment.verification_status or "unknown")
        metrics.add_row("Drift:", assessment.drift_severity or "none")
        attempts_str = f"{assessment.total_attempts}"
        if assessment.escalated:
            attempts_str += " (escalated)"
        metrics.add_row("Attempts:", attempts_str)
        metrics.add_row("Files:", str(assessment.files_changed_count))
        metrics.add_row("Commits:", "yes" if assessment.has_commits else "no")

        self.console.print(metrics)
        self.console.print()

        # Issues section
        if assessment.issues:
            self._render_issues(assessment.issues)

        # Summary
        self.console.print(f"  [dim]Summary:[/dim] {assessment.summary}")
        self.console.print()

    def render_epic_assessment(self, assessment: EpicAssessment) -> None:
        """Render an epic assessment with Rich formatting.

        Args:
            assessment: EpicAssessment to render
        """
        # Build title with grade badge
        title = Text()
        title.append("Epic: ", style="bold")
        title.append(f"{assessment.epic_id} - {assessment.title}")
        title.append(f" ({assessment.tasks_total} tasks)\n")
        title.append("Grade: ")
        title.append_text(_grade_badge(assessment.grade))

        self.console.print()
        self.console.print(Panel(title, expand=False))

        # Task counts
        task_summary = (
            f"  Tasks: {assessment.tasks_passed}/{assessment.tasks_total} passed"
        )
        if assessment.tasks_partial > 0:
            task_summary += f", {assessment.tasks_partial} partial"
        if assessment.tasks_failed > 0:
            task_summary += f", {assessment.tasks_failed} failed"
        self.console.print(task_summary)
        self.console.print()

        # Aggregate issues
        if assessment.aggregate_issues:
            self._render_issues(assessment.aggregate_issues)

        # Task table
        if assessment.task_assessments:
            self.console.print("  [bold]Tasks:[/bold]")
            for task in assessment.task_assessments:
                badge = _grade_badge(task.grade)
                self.console.print("    ", end="")
                self.console.print(badge, end="")
                self.console.print(f" {task.task_id} - {task.title}")

                # In verbose mode, show per-task issues
                if self.verbose and task.issues:
                    for issue in task.issues:
                        style = _severity_style(issue.severity)
                        self.console.print(
                            f"        [{style}]└ {issue.description}[/{style}]"
                        )

        self.console.print()

        # Recommendations
        if self.verbose and assessment.aggregate_issues:
            self._render_recommendations(assessment.aggregate_issues)

        # Summary
        self.console.print(f"  [dim]Summary:[/dim] {assessment.summary}")
        self.console.print()

    def render_plan_assessment(self, assessment: PlanAssessment) -> None:
        """Render a plan assessment with Rich formatting.

        Args:
            assessment: PlanAssessment to render
        """
        # Build title with grade badge
        title = Text()
        title.append("Plan: ", style="bold")
        title.append(f"{assessment.plan_slug}\n")
        title.append("Grade: ")
        title.append_text(_grade_badge(assessment.grade))

        self.console.print()
        self.console.print(Panel(title, expand=False))

        # Overall counts
        self.console.print(
            f"  Epics: {assessment.epics_passed}/{assessment.epics_total} passed"
        )
        self.console.print(
            f"  Tasks: {assessment.tasks_passed}/{assessment.tasks_total} passed"
        )
        completion_pct = assessment.completion_rate * 100
        self.console.print(f"  Completion: {completion_pct:.0f}%")
        self.console.print()

        # Overall issues
        if assessment.overall_issues:
            self._render_issues(assessment.overall_issues)

        # Epic summaries
        if assessment.epic_assessments:
            self.console.print("  [bold]Epics:[/bold]")
            for epic in assessment.epic_assessments:
                badge = _grade_badge(epic.grade)
                task_info = f"({epic.tasks_passed}/{epic.tasks_total} tasks)"
                self.console.print("    ", end="")
                self.console.print(badge, end="")
                self.console.print(f" {epic.epic_id} - {epic.title} {task_info}")

                # In verbose mode, show per-task details within each epic
                if self.verbose and epic.task_assessments:
                    for task in epic.task_assessments:
                        task_badge = _grade_badge(task.grade)
                        self.console.print("      ", end="")
                        self.console.print(task_badge, end="")
                        self.console.print(f" {task.task_id}")
                        for issue in task.issues:
                            style = _severity_style(issue.severity)
                            self.console.print(
                                f"          [{style}]└ {issue.description}[/{style}]"
                            )

        self.console.print()

        # Recommendations
        if self.verbose and assessment.overall_issues:
            self._render_recommendations(assessment.overall_issues)

        # Summary
        self.console.print(f"  [dim]Summary:[/dim] {assessment.summary}")
        self.console.print()

    def _render_issues(self, issues: list[ReviewIssue]) -> None:
        """Render a list of issues."""
        self.console.print("  [bold]Issues:[/bold]")
        for issue in issues:
            style = _severity_style(issue.severity)
            marker = "!" if issue.severity == IssueSeverity.CRITICAL else "-"
            sev = issue.severity.value
            self.console.print(
                f"  [{style}]{marker}[/{style}] [{style}][{sev}][/{style}] "
                f"{issue.description}"
            )
        self.console.print()

    def _render_recommendations(self, issues: list[ReviewIssue]) -> None:
        """Render recommendations from issues."""
        recommendations = [i.recommendation for i in issues if i.recommendation]
        if recommendations:
            self.console.print("  [bold]Recommendations:[/bold]")
            for rec in recommendations:
                self.console.print(f"  - {rec}")
            self.console.print()

    def to_json(self, assessment: TaskAssessment | EpicAssessment | PlanAssessment) -> str:
        """Serialize assessment to JSON.

        Args:
            assessment: Assessment model to serialize

        Returns:
            JSON string representation
        """
        return assessment.model_dump_json(indent=2)
