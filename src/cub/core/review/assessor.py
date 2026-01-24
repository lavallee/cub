"""
Assessment logic for reviewing task implementation quality.

This module provides assessor classes that analyze ledger entries
to determine whether tasks, epics, and plans were fully implemented.
"""

from __future__ import annotations

from pathlib import Path

from cub.core.ledger.models import LedgerEntry
from cub.core.ledger.reader import LedgerReader
from cub.core.plans import get_epic_ids
from cub.core.review.models import (
    AssessmentGrade,
    EpicAssessment,
    IssueSeverity,
    IssueType,
    PlanAssessment,
    ReviewIssue,
    TaskAssessment,
)


class TaskAssessor:
    """Assess individual task implementations from ledger entries."""

    def __init__(self, ledger_reader: LedgerReader) -> None:
        """Initialize the task assessor.

        Args:
            ledger_reader: LedgerReader instance for accessing ledger data
        """
        self.ledger = ledger_reader

    def assess_task(self, task_id: str) -> TaskAssessment:
        """Assess a single task from its ledger entry.

        Args:
            task_id: Task ID to assess

        Returns:
            TaskAssessment with grade, issues, and summary
        """
        entry = self.ledger.get_task(task_id)
        if not entry:
            return TaskAssessment(
                task_id=task_id,
                title="Unknown",
                grade=AssessmentGrade.UNKNOWN,
                issues=[
                    ReviewIssue(
                        type=IssueType.NOT_IN_LEDGER,
                        severity=IssueSeverity.CRITICAL,
                        description=f"Task {task_id} not found in ledger",
                        recommendation="Ensure the task was completed and recorded in the ledger",
                    )
                ],
                summary="Task not found in ledger",
            )

        issues: list[ReviewIssue] = []
        issues.extend(self._check_verification(entry))
        issues.extend(self._check_drift(entry))
        issues.extend(self._check_outcome(entry))
        issues.extend(self._check_commits(entry))

        grade = self._determine_grade(issues)
        summary = self._build_summary(entry, grade, issues)

        # Extract metrics from entry
        total_attempts = 0
        escalated = False
        files_changed_count = 0
        has_commits = False

        if entry.outcome:
            total_attempts = entry.outcome.total_attempts
            escalated = entry.outcome.escalated
            files_changed_count = len(entry.outcome.files_changed)
            has_commits = len(entry.outcome.commits) > 0
        else:
            total_attempts = entry.iterations
            files_changed_count = len(entry.files_changed)
            has_commits = len(entry.commits) > 0

        return TaskAssessment(
            task_id=task_id,
            title=entry.title,
            grade=grade,
            issues=issues,
            summary=summary,
            verification_status=entry.verification.status,
            drift_severity=entry.drift.severity,
            total_attempts=total_attempts,
            escalated=escalated,
            files_changed_count=files_changed_count,
            has_commits=has_commits,
        )

    def _check_verification(self, entry: LedgerEntry) -> list[ReviewIssue]:
        """Check verification status for issues."""
        issues: list[ReviewIssue] = []

        if entry.verification.status == "fail":
            issues.append(
                ReviewIssue(
                    type=IssueType.VERIFICATION_FAILED,
                    severity=IssueSeverity.CRITICAL,
                    description="Verification checks failed",
                    recommendation="Run tests and fix failing checks: pytest tests/",
                )
            )
        elif entry.verification.status == "pending":
            issues.append(
                ReviewIssue(
                    type=IssueType.VERIFICATION_PENDING,
                    severity=IssueSeverity.WARNING,
                    description="Verification checks not yet run",
                    recommendation="Run verification: pytest tests/ && mypy src/",
                )
            )

        return issues

    def _check_drift(self, entry: LedgerEntry) -> list[ReviewIssue]:
        """Check for spec drift issues."""
        issues: list[ReviewIssue] = []

        if entry.drift.severity == "significant":
            issues.append(
                ReviewIssue(
                    type=IssueType.SPEC_DRIFT_SIGNIFICANT,
                    severity=IssueSeverity.CRITICAL,
                    description="Significant drift from specification",
                    recommendation="Review implementation against spec and address divergence",
                )
            )

        if entry.drift.omissions:
            omissions_str = ", ".join(entry.drift.omissions[:3])
            if len(entry.drift.omissions) > 3:
                omissions_str += f" (+{len(entry.drift.omissions) - 3} more)"

            issues.append(
                ReviewIssue(
                    type=IssueType.SPEC_DRIFT_OMISSION,
                    severity=IssueSeverity.WARNING,
                    description=f"Features omitted from spec: {omissions_str}",
                    recommendation="Evaluate if omissions are acceptable or need follow-up work",
                )
            )

        return issues

    def _check_outcome(self, entry: LedgerEntry) -> list[ReviewIssue]:
        """Check outcome for issues."""
        issues: list[ReviewIssue] = []

        if entry.outcome:
            if not entry.outcome.success:
                issues.append(
                    ReviewIssue(
                        type=IssueType.TASK_FAILED,
                        severity=IssueSeverity.CRITICAL,
                        description="Task did not complete successfully",
                        recommendation="Review task output and address failure cause",
                    )
                )
            elif entry.outcome.partial:
                issues.append(
                    ReviewIssue(
                        type=IssueType.INCOMPLETE_SCOPE,
                        severity=IssueSeverity.WARNING,
                        description="Task was only partially completed",
                        recommendation="Review remaining work and create follow-up tasks if needed",
                    )
                )

            if entry.outcome.escalated:
                escalation_desc = (
                    f"Task escalated: {' -> '.join(entry.outcome.escalation_path)}"
                )
                issues.append(
                    ReviewIssue(
                        type=IssueType.TASK_ESCALATED,
                        severity=IssueSeverity.INFO,
                        description=escalation_desc,
                        recommendation="Consider if task complexity matches expectations",
                    )
                )

        return issues

    def _check_commits(self, entry: LedgerEntry) -> list[ReviewIssue]:
        """Check for commit-related issues."""
        issues: list[ReviewIssue] = []

        has_commits = False
        if entry.outcome and entry.outcome.commits:
            has_commits = True
        elif entry.commits:
            has_commits = True

        if not has_commits:
            issues.append(
                ReviewIssue(
                    type=IssueType.MISSING_COMMITS,
                    severity=IssueSeverity.WARNING,
                    description="No commits recorded for this task",
                    recommendation="Verify changes are committed and associated with this task",
                )
            )

        return issues

    def _determine_grade(self, issues: list[ReviewIssue]) -> AssessmentGrade:
        """Determine overall grade based on issues found."""
        has_critical = any(i.severity == IssueSeverity.CRITICAL for i in issues)
        has_warning = any(i.severity == IssueSeverity.WARNING for i in issues)

        if has_critical:
            return AssessmentGrade.FAIL
        elif has_warning:
            return AssessmentGrade.PARTIAL
        else:
            return AssessmentGrade.PASS

    def _build_summary(
        self,
        entry: LedgerEntry,
        grade: AssessmentGrade,
        issues: list[ReviewIssue],
    ) -> str:
        """Build a human-readable summary of the assessment."""
        if grade == AssessmentGrade.PASS:
            return "Task completed successfully with no critical issues."
        elif grade == AssessmentGrade.PARTIAL:
            warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
            return f"Task completed with {warning_count} warning(s) requiring attention."
        else:
            critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
            return f"Task has {critical_count} critical issue(s) that need resolution."


class EpicAssessor:
    """Assess epic implementations by aggregating task assessments."""

    def __init__(self, ledger_reader: LedgerReader) -> None:
        """Initialize the epic assessor.

        Args:
            ledger_reader: LedgerReader instance for accessing ledger data
        """
        self.ledger = ledger_reader
        self.task_assessor = TaskAssessor(ledger_reader)

    def assess_epic(self, epic_id: str) -> EpicAssessment:
        """Assess all tasks in an epic.

        Args:
            epic_id: Epic ID to assess

        Returns:
            EpicAssessment with task assessments and aggregate metrics
        """
        # Get all tasks in this epic from ledger
        index_entries = self.ledger.list_tasks(epic=epic_id)

        if not index_entries:
            return EpicAssessment(
                epic_id=epic_id,
                title="Unknown",
                grade=AssessmentGrade.UNKNOWN,
                summary=f"No tasks found in ledger for epic {epic_id}",
            )

        # Assess each task
        task_assessments = [
            self.task_assessor.assess_task(entry.id) for entry in index_entries
        ]

        # Get epic title from first task's parent info or use ID
        epic_title = epic_id  # Default to ID
        for entry in index_entries:
            full_entry = self.ledger.get_task(entry.id)
            if full_entry and full_entry.lineage.epic_id == epic_id:
                epic_title = f"Epic {epic_id}"
                break

        # Aggregate counts
        tasks_total = len(task_assessments)
        tasks_passed = sum(1 for t in task_assessments if t.grade == AssessmentGrade.PASS)
        tasks_partial = sum(1 for t in task_assessments if t.grade == AssessmentGrade.PARTIAL)
        tasks_failed = sum(1 for t in task_assessments if t.grade == AssessmentGrade.FAIL)

        # Determine epic grade
        aggregate_issues: list[ReviewIssue] = []

        if tasks_failed > 0:
            grade = AssessmentGrade.FAIL
            aggregate_issues.append(
                ReviewIssue(
                    type=IssueType.TASK_FAILED,
                    severity=IssueSeverity.CRITICAL,
                    description=f"{tasks_failed} task(s) failed in this epic",
                    recommendation="Address failed tasks before marking epic complete",
                )
            )
        elif tasks_partial > 0:
            grade = AssessmentGrade.PARTIAL
            aggregate_issues.append(
                ReviewIssue(
                    type=IssueType.INCOMPLETE_SCOPE,
                    severity=IssueSeverity.WARNING,
                    description=f"{tasks_partial} task(s) partially completed",
                    recommendation="Review partial completions for follow-up work",
                )
            )
        else:
            grade = AssessmentGrade.PASS

        # Build summary
        if grade == AssessmentGrade.PASS:
            summary = f"All {tasks_total} tasks completed successfully."
        elif grade == AssessmentGrade.PARTIAL:
            summary = f"{tasks_passed}/{tasks_total} tasks passed, {tasks_partial} partial."
        else:
            summary = f"{tasks_passed}/{tasks_total} tasks passed, {tasks_failed} failed."

        return EpicAssessment(
            epic_id=epic_id,
            title=epic_title,
            grade=grade,
            task_assessments=task_assessments,
            aggregate_issues=aggregate_issues,
            summary=summary,
            tasks_total=tasks_total,
            tasks_passed=tasks_passed,
            tasks_partial=tasks_partial,
            tasks_failed=tasks_failed,
        )


class PlanAssessor:
    """Assess plan implementations by finding and assessing all epics."""

    def __init__(self, ledger_reader: LedgerReader, plans_root: Path) -> None:
        """Initialize the plan assessor.

        Args:
            ledger_reader: LedgerReader instance for accessing ledger data
            plans_root: Path to plans directory (e.g., ./plans)
        """
        self.ledger = ledger_reader
        self.plans_root = plans_root
        self.epic_assessor = EpicAssessor(ledger_reader)

    def assess_plan(self, plan_slug: str) -> PlanAssessment:
        """Assess a plan by finding its epics and tasks.

        Args:
            plan_slug: Plan slug (e.g., 'unified-tracking-model')

        Returns:
            PlanAssessment with epic assessments and overall metrics
        """
        plan_dir = self.plans_root / plan_slug

        if not plan_dir.exists():
            return PlanAssessment(
                plan_slug=plan_slug,
                grade=AssessmentGrade.UNKNOWN,
                summary=f"Plan directory not found: {plan_dir}",
            )

        # Get epic IDs from plan directory (reads itemized-plan.md or cached plan.json)
        epic_ids = get_epic_ids(plan_dir)

        # Also search ledger for tasks with this plan in lineage (fallback)
        all_entries = self.ledger.list_tasks()
        for entry in all_entries:
            full_entry = self.ledger.get_task(entry.id)
            if full_entry and full_entry.lineage.plan_file:
                if plan_slug in full_entry.lineage.plan_file:
                    if full_entry.lineage.epic_id and full_entry.lineage.epic_id not in epic_ids:
                        epic_ids.append(full_entry.lineage.epic_id)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_epic_ids: list[str] = []
        for eid in epic_ids:
            if eid not in seen:
                seen.add(eid)
                unique_epic_ids.append(eid)
        epic_ids = unique_epic_ids

        if not epic_ids:
            return PlanAssessment(
                plan_slug=plan_slug,
                grade=AssessmentGrade.UNKNOWN,
                summary=f"No epics found for plan {plan_slug}",
            )

        # Assess each epic
        epic_assessments = [self.epic_assessor.assess_epic(eid) for eid in epic_ids]

        # Aggregate counts
        epics_total = len(epic_assessments)
        epics_passed = sum(1 for e in epic_assessments if e.grade == AssessmentGrade.PASS)
        tasks_total = sum(e.tasks_total for e in epic_assessments)
        tasks_passed = sum(e.tasks_passed for e in epic_assessments)

        # Determine overall grade
        overall_issues: list[ReviewIssue] = []
        epics_failed = sum(1 for e in epic_assessments if e.grade == AssessmentGrade.FAIL)
        epics_partial = sum(1 for e in epic_assessments if e.grade == AssessmentGrade.PARTIAL)

        if epics_failed > 0:
            grade = AssessmentGrade.FAIL
            overall_issues.append(
                ReviewIssue(
                    type=IssueType.TASK_FAILED,
                    severity=IssueSeverity.CRITICAL,
                    description=f"{epics_failed} epic(s) have failing tasks",
                    recommendation="Address failed epics before marking plan complete",
                )
            )
        elif epics_partial > 0:
            grade = AssessmentGrade.PARTIAL
            overall_issues.append(
                ReviewIssue(
                    type=IssueType.INCOMPLETE_SCOPE,
                    severity=IssueSeverity.WARNING,
                    description=f"{epics_partial} epic(s) have partial completions",
                    recommendation="Review partial completions for follow-up work",
                )
            )
        else:
            grade = AssessmentGrade.PASS

        # Build summary
        if grade == AssessmentGrade.PASS:
            summary = (
                f"Plan completed: {epics_passed}/{epics_total} epics passed, "
                f"{tasks_passed}/{tasks_total} tasks."
            )
        elif grade == AssessmentGrade.PARTIAL:
            summary = f"Plan partially complete: {epics_passed}/{epics_total} epics passed."
        else:
            summary = f"Plan incomplete: {epics_failed}/{epics_total} epics failed."

        return PlanAssessment(
            plan_slug=plan_slug,
            grade=grade,
            epic_assessments=epic_assessments,
            overall_issues=overall_issues,
            summary=summary,
            epics_total=epics_total,
            epics_passed=epics_passed,
            tasks_total=tasks_total,
            tasks_passed=tasks_passed,
        )
