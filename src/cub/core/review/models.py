"""
Review models for task implementation assessment.

This module defines Pydantic models for assessing whether completed tasks,
epics, and plans were fully and correctly implemented.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AssessmentGrade(str, Enum):
    """Grade assigned to a task, epic, or plan assessment."""

    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"
    UNKNOWN = "unknown"


class IssueType(str, Enum):
    """Types of issues that can be detected during review."""

    # Ledger-based issues
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_PENDING = "verification_pending"
    SPEC_DRIFT_OMISSION = "spec_drift_omission"
    SPEC_DRIFT_SIGNIFICANT = "spec_drift_significant"
    MISSING_COMMITS = "missing_commits"
    INCOMPLETE_SCOPE = "incomplete_scope"
    TASK_FAILED = "task_failed"
    TASK_ESCALATED = "task_escalated"
    NOT_IN_LEDGER = "not_in_ledger"

    # Structural check issues
    MISSING_FILE = "missing_file"
    MISSING_TEST = "missing_test"
    UNCHECKED_CRITERIA = "unchecked_criteria"
    TESTS_FAILING = "tests_failing"
    TYPE_CHECK_FAILING = "type_check_failing"

    # Deep analysis issues
    IMPLEMENTATION_GAP = "implementation_gap"
    SPEC_MISMATCH = "spec_mismatch"
    DEEP_ANALYSIS_FINDING = "deep_analysis_finding"  # General LLM-identified issue


class IssueSeverity(str, Enum):
    """Severity levels for review issues."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ReviewIssue(BaseModel):
    """A single issue detected during review."""

    type: IssueType
    severity: IssueSeverity
    description: str
    recommendation: str = ""

    def __str__(self) -> str:
        return f"[{self.severity.value}] {self.description}"


class AcceptanceCriterion(BaseModel):
    """A single acceptance criterion from task description."""

    text: str
    checked: bool = False


class TaskAssessment(BaseModel):
    """Assessment of a single task's implementation."""

    task_id: str
    title: str
    grade: AssessmentGrade
    issues: list[ReviewIssue] = Field(default_factory=list)
    summary: str

    # Metrics from ledger
    verification_status: str | None = None
    drift_severity: str | None = None
    total_attempts: int = 0
    escalated: bool = False
    files_changed_count: int = 0
    has_commits: bool = False

    # Structural check results
    specified_files: list[str] = Field(default_factory=list)
    missing_files: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    unchecked_criteria: list[str] = Field(default_factory=list)
    missing_tests: list[str] = Field(default_factory=list)

    # Deep analysis results (populated with --deep)
    deep_analysis: str | None = None

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warning issues."""
        return any(i.severity == IssueSeverity.WARNING for i in self.issues)


class EpicAssessment(BaseModel):
    """Assessment of an epic and all its tasks."""

    epic_id: str
    title: str
    grade: AssessmentGrade
    task_assessments: list[TaskAssessment] = Field(default_factory=list)
    aggregate_issues: list[ReviewIssue] = Field(default_factory=list)
    summary: str

    # Aggregates
    tasks_total: int = 0
    tasks_passed: int = 0
    tasks_partial: int = 0
    tasks_failed: int = 0

    @property
    def completion_rate(self) -> float:
        """Calculate the completion rate (passed / total)."""
        if self.tasks_total == 0:
            return 0.0
        return self.tasks_passed / self.tasks_total


class PlanAssessment(BaseModel):
    """Assessment of an entire plan and its epics."""

    plan_slug: str
    grade: AssessmentGrade
    epic_assessments: list[EpicAssessment] = Field(default_factory=list)
    overall_issues: list[ReviewIssue] = Field(default_factory=list)
    summary: str

    # Aggregates
    epics_total: int = 0
    epics_passed: int = 0
    tasks_total: int = 0
    tasks_passed: int = 0

    @property
    def completion_rate(self) -> float:
        """Calculate the overall task completion rate."""
        if self.tasks_total == 0:
            return 0.0
        return self.tasks_passed / self.tasks_total
