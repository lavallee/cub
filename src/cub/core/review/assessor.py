"""
Assessment logic for reviewing task implementation quality.

This module provides assessor classes that analyze ledger entries
to determine whether tasks, epics, and plans were fully implemented.

Supports two levels of analysis:
- Structural checks (default): File existence, acceptance criteria, tests
- Deep analysis (--deep): LLM-based code review against spec
"""

from __future__ import annotations

import re
from pathlib import Path

from cub.core.ledger.models import LedgerEntry
from cub.core.ledger.reader import LedgerReader
from cub.core.plans import get_epic_ids
from cub.core.review.models import (
    AcceptanceCriterion,
    AssessmentGrade,
    EpicAssessment,
    IssueSeverity,
    IssueType,
    PlanAssessment,
    ReviewIssue,
    TaskAssessment,
)
from cub.utils.project import get_project_root


class TaskAssessor:
    """Assess individual task implementations from ledger entries.

    Performs structural checks by default:
    - Verifies specified files exist
    - Checks acceptance criteria are marked complete
    - Verifies test files exist for source files

    With deep=True, also performs LLM-based analysis of implementation.
    """

    def __init__(
        self,
        ledger_reader: LedgerReader,
        project_root: Path | None = None,
    ) -> None:
        """Initialize the task assessor.

        Args:
            ledger_reader: LedgerReader instance for accessing ledger data
            project_root: Project root directory (auto-detected if None)
        """
        self.ledger = ledger_reader
        self.project_root = project_root or get_project_root()

    def assess_task(self, task_id: str, *, deep: bool = False) -> TaskAssessment:
        """Assess a single task from its ledger entry.

        Args:
            task_id: Task ID to assess
            deep: If True, perform LLM-based deep analysis

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

        # Ledger-based checks
        issues.extend(self._check_verification(entry))
        issues.extend(self._check_drift(entry))
        issues.extend(self._check_outcome(entry))
        issues.extend(self._check_commits(entry))

        # Structural checks - parse task description from ledger snapshot
        description = entry.task.description if entry.task else ""
        specified_files = self._parse_specified_files(description)
        acceptance_criteria = self._parse_acceptance_criteria(description)
        missing_files = self._check_files_exist(specified_files)
        unchecked_criteria = [c.text for c in acceptance_criteria if not c.checked]
        missing_tests = self._check_tests_exist(specified_files)

        # Add structural issues
        issues.extend(self._check_structural(
            missing_files, unchecked_criteria, missing_tests
        ))

        # Deep analysis with LLM (if requested)
        deep_analysis = None
        if deep:
            deep_analysis, deep_issues = self._run_deep_analysis(entry, specified_files)
            issues.extend(deep_issues)

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
            specified_files=specified_files,
            missing_files=missing_files,
            acceptance_criteria=acceptance_criteria,
            unchecked_criteria=unchecked_criteria,
            missing_tests=missing_tests,
            deep_analysis=deep_analysis,
        )

    def _check_verification(self, entry: LedgerEntry) -> list[ReviewIssue]:
        """Check verification status for issues.

        Note: verification_pending is NOT a warning - that's what this review
        tool helps humans do. Only actual failures are issues.
        """
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
        # Note: "pending" is not an issue - review tool assists with verification

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

    def _parse_specified_files(self, description: str) -> list[str]:
        """Extract file paths mentioned in task description.

        Looks for patterns like:
        - Files: path/to/file.py, other/file.py
        - **Files:** `path/to/file.py` (markdown bold)
        - `path/to/file.py`
        - Create/modify/update <file path>
        """
        files: list[str] = []

        def clean_path(p: str) -> str:
            """Clean a path string by removing markdown formatting."""
            # Remove markdown formatting - loop until stable
            prev = ""
            while prev != p:
                prev = p
                p = p.strip().strip("`").strip("*").strip()
            return p

        # Pattern 1: "Files:" line with comma-separated paths (handles **Files:**)
        # Must be at start of line or after newline, with explicit colon
        files_line = re.search(
            r"(?:^|\n)\s*\*{0,2}Files?\*{0,2}:\s*(.+?)(?:\n|$)",
            description,
            re.IGNORECASE,
        )
        if files_line:
            # Split on commas and clean up
            for f in files_line.group(1).split(","):
                f = clean_path(f)
                if f and "/" in f:  # Looks like a path
                    files.append(f)

        # Pattern 2: Backtick-wrapped paths that look like files
        backtick_paths = re.findall(r"`([^`]+\.[a-z]+)`", description)
        for path in backtick_paths:
            path = clean_path(path)
            if "/" in path and path not in files:
                files.append(path)

        # Pattern 3: Create/modify/update followed by path
        action_paths = re.findall(
            r"(?:create|modify|update|add|implement)\s+`?([^\s`]+\.[a-z]+)`?",
            description,
            re.IGNORECASE,
        )
        for path in action_paths:
            path = clean_path(path)
            if "/" in path and path not in files:
                files.append(path)

        return files

    def _parse_acceptance_criteria(self, description: str) -> list[AcceptanceCriterion]:
        """Extract acceptance criteria from markdown checkboxes.

        Looks for:
        - [ ] unchecked criterion
        - [x] checked criterion
        - [X] checked criterion
        """
        criteria: list[AcceptanceCriterion] = []

        # Match markdown checkboxes
        checkbox_pattern = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.+)$", re.MULTILINE)
        for match in checkbox_pattern.finditer(description):
            checked = match.group(1).lower() == "x"
            text = match.group(2).strip()
            criteria.append(AcceptanceCriterion(text=text, checked=checked))

        return criteria

    def _check_files_exist(self, specified_files: list[str]) -> list[str]:
        """Check which specified files don't exist.

        Tries multiple prefixes and skips template paths with {placeholders}.

        Returns list of missing file paths.
        """
        missing: list[str] = []
        prefixes_to_try = ["", "src/cub/", "src/"]

        for file_path in specified_files:
            # Skip template paths with placeholders like {epic-id}
            if "{" in file_path and "}" in file_path:
                continue

            # Skip directory patterns
            if file_path.endswith("/"):
                continue

            # Try with different prefixes
            found = False
            for prefix in prefixes_to_try:
                full_path = self.project_root / (prefix + file_path)
                if full_path.exists():
                    found = True
                    break

            if not found:
                missing.append(file_path)

        return missing

    def _check_tests_exist(self, specified_files: list[str]) -> list[str]:
        """Check if test files exist for source files.

        For files in src/, looks for corresponding test_*.py in tests/.
        Returns list of source files missing tests.
        """
        missing_tests: list[str] = []

        for file_path in specified_files:
            # Only check Python source files
            if not file_path.endswith(".py"):
                continue
            # Only check src/ files
            if not file_path.startswith("src/"):
                continue
            # Skip __init__.py and test files
            if file_path.endswith("__init__.py") or "test_" in file_path:
                continue

            # Convert src/cub/foo/bar.py -> tests/test_bar.py or tests/foo/test_bar.py
            path = Path(file_path)
            filename = path.name
            test_filename = f"test_{filename}"

            # Check common test locations
            test_paths = [
                self.project_root / "tests" / test_filename,
                self.project_root / "tests" / path.parent.name / test_filename,
            ]

            found = any(tp.exists() for tp in test_paths)
            if not found:
                missing_tests.append(file_path)

        return missing_tests

    def _check_structural(
        self,
        missing_files: list[str],
        unchecked_criteria: list[str],
        missing_tests: list[str],
    ) -> list[ReviewIssue]:
        """Generate issues for structural problems found."""
        issues: list[ReviewIssue] = []

        # Missing files
        for file_path in missing_files:
            issues.append(
                ReviewIssue(
                    type=IssueType.MISSING_FILE,
                    severity=IssueSeverity.CRITICAL,
                    description=f"Specified file not found: {file_path}",
                    recommendation=f"Create the file or update task description",
                )
            )

        # Unchecked acceptance criteria
        if unchecked_criteria:
            criteria_str = "; ".join(unchecked_criteria[:3])
            if len(unchecked_criteria) > 3:
                criteria_str += f" (+{len(unchecked_criteria) - 3} more)"
            issues.append(
                ReviewIssue(
                    type=IssueType.UNCHECKED_CRITERIA,
                    severity=IssueSeverity.WARNING,
                    description=f"Unchecked acceptance criteria: {criteria_str}",
                    recommendation="Verify criteria are met and update task description",
                )
            )

        # Missing tests
        if missing_tests:
            tests_str = ", ".join(missing_tests[:3])
            if len(missing_tests) > 3:
                tests_str += f" (+{len(missing_tests) - 3} more)"
            issues.append(
                ReviewIssue(
                    type=IssueType.MISSING_TEST,
                    severity=IssueSeverity.WARNING,
                    description=f"No tests found for: {tests_str}",
                    recommendation="Add test coverage for these files",
                )
            )

        return issues

    def _run_deep_analysis(
        self,
        entry: LedgerEntry,
        specified_files: list[str],
    ) -> tuple[str | None, list[ReviewIssue]]:
        """Run LLM-based deep analysis of implementation.

        This is a placeholder - actual LLM integration would go here.
        For now, returns None and empty issues.

        Args:
            entry: The ledger entry to analyze
            specified_files: Files mentioned in the task

        Returns:
            Tuple of (analysis_text, issues_found)
        """
        # TODO: Implement LLM-based analysis
        # This would:
        # 1. Read the spec file if available
        # 2. Read the implemented files
        # 3. Use an LLM to compare implementation vs spec
        # 4. Return analysis text and any issues found
        return None, []


class EpicAssessor:
    """Assess epic implementations by aggregating task assessments."""

    def __init__(self, ledger_reader: LedgerReader) -> None:
        """Initialize the epic assessor.

        Args:
            ledger_reader: LedgerReader instance for accessing ledger data
        """
        self.ledger = ledger_reader
        self.task_assessor = TaskAssessor(ledger_reader)

    def assess_epic(self, epic_id: str, *, deep: bool = False) -> EpicAssessment:
        """Assess all tasks in an epic.

        Args:
            epic_id: Epic ID to assess
            deep: If True, run LLM-based deep analysis on each task

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
            self.task_assessor.assess_task(entry.id, deep=deep) for entry in index_entries
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

    def assess_plan(self, plan_slug: str, *, deep: bool = False) -> PlanAssessment:
        """Assess a plan by finding its epics and tasks.

        Args:
            plan_slug: Plan slug (e.g., 'unified-tracking-model')
            deep: If True, run LLM-based deep analysis on each task

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
        epic_assessments = [self.epic_assessor.assess_epic(eid, deep=deep) for eid in epic_ids]

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
