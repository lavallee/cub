"""
Data source adapters for the suggestion system.

Provides protocol definition and implementations for gathering suggestion data
from different sources: tasks, git, ledger, and milestones.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from cub.core.ledger.models import VerificationStatus, WorkflowStage
from cub.core.ledger.reader import LedgerReader
from cub.core.suggestions.models import Suggestion, SuggestionCategory
from cub.core.tasks.backend import TaskBackend, get_backend
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType
from cub.utils.git import get_commits_since


@runtime_checkable
class SuggestionSource(Protocol):
    """Protocol for suggestion data sources.

    Each source analyzes a specific aspect of project state
    (tasks, git, ledger, milestones) and generates relevant suggestions.
    """

    def get_suggestions(self) -> list[Suggestion]:
        """Generate suggestions from this data source.

        Returns:
            List of suggestions with priority scores and rationale
        """
        ...


class TaskSource:
    """Generates suggestions from task backend state.

    Analyzes open, ready, blocked, and in-progress tasks to suggest
    what to work on next.
    """

    def __init__(self, project_dir: Path | None = None):
        """Initialize task source.

        Args:
            project_dir: Project directory path (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self.backend: TaskBackend = get_backend(project_dir=self.project_dir)

    def get_suggestions(self) -> list[Suggestion]:
        """Generate task-related suggestions.

        Returns:
            List of suggestions for tasks to work on
        """
        suggestions: list[Suggestion] = []

        # Get tasks in different states
        try:
            ready_tasks = self.backend.get_ready_tasks()
            in_progress_tasks = self.backend.list_tasks(status=TaskStatus.IN_PROGRESS)
            open_tasks = self.backend.list_tasks(status=TaskStatus.OPEN)
        except Exception:
            # Backend might not be available, return empty suggestions
            return suggestions

        # Suggest ready tasks (no dependencies blocking them)
        for task in ready_tasks[:3]:  # Top 3 ready tasks
            priority_score = self._calculate_task_priority(task, ready_tasks)

            suggestions.append(
                Suggestion(
                    category=SuggestionCategory.TASK,
                    title=f"Work on {task.id}: {task.title}",
                    description=task.description or "No description available",
                    rationale=self._generate_task_rationale(task, is_ready=True),
                    priority_score=priority_score,
                    action=f"bd update {task.id} --status in_progress && cub run {task.id}",
                    source="task_backend",
                    context={
                        "task_id": task.id,
                        "task_type": task.type.value,
                        "task_priority": task.priority.value,
                        "is_ready": True,
                    },
                )
            )

        # Warn about abandoned in-progress tasks
        for task in in_progress_tasks:
            # In-progress tasks should be finished or moved back to open
            suggestions.append(
                Suggestion(
                    category=SuggestionCategory.TASK,
                    title=f"Complete or abandon {task.id}",
                    description=f"Task '{task.title}' is marked in-progress but may be stale",
                    rationale=(
                        "This task is marked as in-progress. Consider completing it, "
                        "or moving it back to open status if work hasn't started."
                    ),
                    priority_score=0.7,
                    action=f"bd show {task.id}",
                    source="task_backend",
                    context={
                        "task_id": task.id,
                        "task_status": task.status.value,
                    },
                )
            )

        # Suggest planning if no ready tasks but many open ones
        if len(ready_tasks) == 0 and len(open_tasks) > 0:
            blocked_count = len([t for t in open_tasks if len(t.depends_on) > 0])
            if blocked_count > 0:
                suggestions.append(
                    Suggestion(
                        category=SuggestionCategory.PLAN,
                        title="Resolve task dependencies",
                        description=f"{blocked_count} tasks are blocked by dependencies",
                        rationale=(
                            f"There are {blocked_count} tasks blocked by dependencies. "
                            "Consider completing blocking tasks or breaking down dependencies."
                        ),
                        priority_score=0.65,
                        action="bd list --status open",
                        source="task_backend",
                        context={
                            "blocked_tasks": blocked_count,
                            "open_tasks": len(open_tasks),
                        },
                    )
                )

        return suggestions

    def _calculate_task_priority(self, task: Task, all_ready_tasks: list[Task]) -> float:
        """Calculate priority score for a task.

        Args:
            task: Task to score
            all_ready_tasks: All ready tasks for context

        Returns:
            Priority score from 0.0 to 1.0
        """
        base_score = 0.5

        # Priority boost (P0 = +0.3, P1 = +0.2, P2 = +0.1, P3/P4 = +0.0)
        priority_boost = {
            TaskPriority.P0: 0.3,
            TaskPriority.P1: 0.2,
            TaskPriority.P2: 0.1,
            TaskPriority.P3: 0.0,
            TaskPriority.P4: 0.0,
        }.get(task.priority, 0.0)

        # Type boost (bugs are slightly higher priority)
        type_boost = 0.1 if task.type in (TaskType.BUG, TaskType.BUGFIX) else 0.0

        # If this task blocks others, higher priority
        blocks_boost = 0.15 if len(task.blocks) > 0 else 0.0

        total_score = min(1.0, base_score + priority_boost + type_boost + blocks_boost)
        return total_score

    def _generate_task_rationale(self, task: Task, is_ready: bool = False) -> str:
        """Generate rationale for working on a task.

        Args:
            task: Task to generate rationale for
            is_ready: Whether task is ready (no blockers)

        Returns:
            Human-readable rationale string
        """
        parts = []

        if is_ready:
            parts.append("This task is ready to work on (no blockers)")

        if task.priority in (TaskPriority.P0, TaskPriority.P1):
            parts.append(f"High priority ({task.priority.value})")

        if task.type in (TaskType.BUG, TaskType.BUGFIX):
            parts.append("Bug fix needed")

        if len(task.blocks) > 0:
            parts.append(f"Blocks {len(task.blocks)} other task(s)")

        if task.parent:
            parts.append(f"Part of epic {task.parent}")

        if not parts:
            parts.append("Next available task")

        return ". ".join(parts) + "."


class GitSource:
    """Generates suggestions from git repository state.

    Analyzes branch state, uncommitted changes, and recent commit
    activity to suggest git operations.
    """

    def __init__(self, project_dir: Path | None = None):
        """Initialize git source.

        Args:
            project_dir: Project directory path (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()

    def get_suggestions(self) -> list[Suggestion]:
        """Generate git-related suggestions.

        Returns:
            List of suggestions for git operations
        """
        suggestions: list[Suggestion] = []

        # Check for uncommitted changes
        if self._has_uncommitted_changes():
            suggestions.append(
                Suggestion(
                    category=SuggestionCategory.GIT,
                    title="Commit uncommitted changes",
                    description="You have uncommitted changes in your working directory",
                    rationale=(
                        "Committing changes regularly helps track progress and "
                        "prevents loss of work."
                    ),
                    priority_score=0.75,
                    action="git status",
                    source="git",
                    context={"has_changes": True},
                )
            )

        # Check for commits that haven't been pushed
        commits_ahead = self._get_commits_ahead()
        if commits_ahead > 0:
            suggestions.append(
                Suggestion(
                    category=SuggestionCategory.GIT,
                    title=f"Push {commits_ahead} local commit(s)",
                    description=f"Your branch has {commits_ahead} commit(s) not pushed to remote",
                    rationale=(
                        "Pushing commits backs up your work and makes it visible "
                        "to collaborators."
                    ),
                    priority_score=0.65,
                    action="git push",
                    source="git",
                    context={"commits_ahead": commits_ahead},
                )
            )

        # Check for recent commit activity (might want to create PR)
        recent_commits = self._get_recent_commits(hours=24)
        current_branch = self._get_current_branch()
        if (
            len(recent_commits) >= 3
            and current_branch
            and current_branch not in ("main", "master")
        ):
            suggestions.append(
                Suggestion(
                    category=SuggestionCategory.GIT,
                    title="Consider creating a pull request",
                    description=(
                        f"Branch '{current_branch}' has "
                        f"{len(recent_commits)} commits in the last 24h"
                    ),
                    rationale=(
                        "Multiple commits suggest a feature or fix is ready for review. "
                        "Creating a PR enables code review and discussion."
                    ),
                    priority_score=0.55,
                    action="gh pr create",
                    source="git",
                    context={
                        "branch": current_branch,
                        "recent_commits": len(recent_commits),
                    },
                )
            )

        return suggestions

    def _has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            True if there are uncommitted or staged changes
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return bool(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _get_commits_ahead(self) -> int:
        """Get number of commits ahead of remote tracking branch.

        Returns:
            Number of commits ahead, or 0 if not tracked
        """
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "@{u}..HEAD"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=False,  # Might fail if no upstream
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
            return 0
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            return 0

    def _get_current_branch(self) -> str | None:
        """Get current branch name.

        Returns:
            Branch name or None if not on a branch
        """
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() or None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _get_recent_commits(self, hours: int = 24) -> list[dict[str, str]]:
        """Get commits from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of commit dictionaries
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return get_commits_since(since)


class LedgerSource:
    """Generates suggestions from ledger (completed work) state.

    Analyzes verification status, workflow stages, and completion
    patterns to suggest review and cleanup actions.
    """

    def __init__(self, project_dir: Path | None = None):
        """Initialize ledger source.

        Args:
            project_dir: Project directory path (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self.ledger: LedgerReader | None
        try:
            self.ledger = LedgerReader(self.project_dir / ".cub" / "ledger")
        except Exception:
            self.ledger = None

    def get_suggestions(self) -> list[Suggestion]:
        """Generate ledger-related suggestions.

        Returns:
            List of suggestions for reviews and workflow actions
        """
        suggestions: list[Suggestion] = []

        if self.ledger is None:
            # No ledger available
            return suggestions

        # Check for failed verifications
        try:
            failed_tasks = self.ledger.list_tasks(verification=VerificationStatus.FAIL)
            if len(failed_tasks) > 0:
                task_ids = ", ".join([t.id for t in failed_tasks[:3]])
                suggestions.append(
                    Suggestion(
                        category=SuggestionCategory.REVIEW,
                        title=f"Fix {len(failed_tasks)} task(s) with failed verification",
                        description=f"Tasks with failed tests or checks: {task_ids}",
                        rationale=(
                            "Failed verifications indicate issues that should be addressed "
                            "before proceeding with new work."
                        ),
                        priority_score=0.85,
                        action=f"cub ledger show {failed_tasks[0].id}",
                        source="ledger",
                        context={
                            "failed_count": len(failed_tasks),
                            "task_ids": [t.id for t in failed_tasks[:5]],
                        },
                    )
                )
        except Exception:
            pass

        # Check for tasks needing review
        try:
            # Tasks that are completed but not yet in validation workflow
            all_tasks = self.ledger.list_tasks()
            needs_review = []
            for task in all_tasks:
                # Read full entry to check workflow stage
                try:
                    entry = self.ledger.get_task(task.id)
                    if (
                        entry
                        and entry.workflow.stage == WorkflowStage.NEEDS_REVIEW
                    ):
                        needs_review.append(task)
                except Exception:
                    continue

            if len(needs_review) > 0:
                suggestions.append(
                    Suggestion(
                        category=SuggestionCategory.REVIEW,
                        title=f"Review {len(needs_review)} completed task(s)",
                        description="Tasks awaiting validation",
                        rationale=(
                            "Completed tasks should be reviewed and validated before "
                            "moving to release stage."
                        ),
                        priority_score=0.6,
                        action="cub ledger list --stage needs_review",
                        source="ledger",
                        context={"needs_review_count": len(needs_review)},
                    )
                )
        except Exception:
            pass

        # Check for high costs (> $5 for a single task)
        try:
            all_tasks = self.ledger.list_tasks()
            expensive_tasks = [t for t in all_tasks if t.cost_usd and t.cost_usd > 5.0]
            if len(expensive_tasks) > 0:
                suggestions.append(
                    Suggestion(
                        category=SuggestionCategory.REVIEW,
                        title=f"Review {len(expensive_tasks)} expensive task(s)",
                        description="Some tasks had unusually high costs",
                        rationale=(
                            "High-cost tasks may indicate inefficiencies or complex work "
                            "that could benefit from review or process improvement."
                        ),
                        priority_score=0.5,
                        action="cub ledger stats",
                        source="ledger",
                        context={
                            "expensive_count": len(expensive_tasks),
                            "max_cost": max(t.cost_usd for t in expensive_tasks if t.cost_usd),
                        },
                    )
                )
        except Exception:
            pass

        return suggestions


class MilestoneSource:
    """Generates suggestions from milestone/epic state.

    Analyzes epic progress and completion to suggest milestone-focused work.
    """

    def __init__(self, project_dir: Path | None = None):
        """Initialize milestone source.

        Args:
            project_dir: Project directory path (defaults to cwd)
        """
        self.project_dir = project_dir or Path.cwd()
        self.backend: TaskBackend = get_backend(project_dir=self.project_dir)

    def get_suggestions(self) -> list[Suggestion]:
        """Generate milestone-related suggestions.

        Returns:
            List of suggestions for milestone/epic work
        """
        suggestions: list[Suggestion] = []

        # Get epic tasks
        try:
            all_tasks = self.backend.list_tasks()
            epics = [t for t in all_tasks if t.type == TaskType.EPIC]
            open_epics = [e for e in epics if e.status != TaskStatus.CLOSED]
        except Exception:
            return suggestions

        # Suggest working on epic if it has ready child tasks
        for epic in open_epics[:2]:  # Top 2 open epics
            try:
                # Get tasks that belong to this epic
                epic_tasks = self.backend.list_tasks(parent=epic.id)
                ready_epic_tasks = [
                    t
                    for t in epic_tasks
                    if t.status == TaskStatus.OPEN and len(t.depends_on) == 0
                ]

                if len(ready_epic_tasks) > 0:
                    total_epic_tasks = len(epic_tasks)
                    closed_epic_tasks = len(
                        [t for t in epic_tasks if t.status == TaskStatus.CLOSED]
                    )
                    completion = (
                        (closed_epic_tasks / total_epic_tasks * 100)
                        if total_epic_tasks > 0
                        else 0.0
                    )

                    suggestions.append(
                        Suggestion(
                            category=SuggestionCategory.MILESTONE,
                            title=f"Continue epic {epic.id}: {epic.title}",
                            description=(
                                f"{completion:.0f}% complete "
                                f"({closed_epic_tasks}/{total_epic_tasks} tasks)"
                            ),
                            rationale=(
                                f"This epic has {len(ready_epic_tasks)} ready task(s). "
                                "Continuing focused work on an epic helps build momentum."
                            ),
                            priority_score=0.7,
                            action=f"bd list --parent {epic.id}",
                            source="milestone",
                            context={
                                "epic_id": epic.id,
                                "total_tasks": total_epic_tasks,
                                "ready_tasks": len(ready_epic_tasks),
                                "completion_percentage": completion,
                            },
                        )
                    )
            except Exception:
                continue

        # Suggest closing epic if all tasks are done
        for epic in open_epics:
            try:
                epic_tasks = self.backend.list_tasks(parent=epic.id)
                if len(epic_tasks) > 0:
                    all_closed = all(t.status == TaskStatus.CLOSED for t in epic_tasks)
                    if all_closed:
                        suggestions.append(
                            Suggestion(
                                category=SuggestionCategory.MILESTONE,
                                title=f"Close completed epic {epic.id}",
                                description=f"All tasks in '{epic.title}' are complete",
                                rationale=(
                                    "All child tasks are closed. Consider closing the epic "
                                    "to mark this milestone as complete."
                                ),
                                priority_score=0.65,
                                action=f"bd close {epic.id} -r 'All tasks complete'",
                                source="milestone",
                                context={
                                    "epic_id": epic.id,
                                    "total_tasks": len(epic_tasks),
                                },
                            )
                        )
            except Exception:
                continue

        return suggestions
