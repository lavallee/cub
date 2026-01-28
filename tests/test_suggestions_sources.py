"""
Tests for suggestion sources.

Tests the data source adapters that generate suggestions from
tasks, git, ledger, and milestones.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from cub.core.ledger.models import (
    LedgerEntry,
    LedgerIndex,
    Lineage,
    Outcome,
    Verification,
    VerificationStatus,
    WorkflowStage,
    WorkflowState,
)
from cub.core.suggestions.models import Suggestion, SuggestionCategory
from cub.core.suggestions.sources import (
    GitSource,
    LedgerSource,
    MilestoneSource,
    SuggestionSource,
    TaskSource,
)
from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType


class TestSuggestionSourceProtocol:
    """Test the SuggestionSource protocol."""

    def test_protocol_runtime_checkable(self):
        """Test that protocol is runtime checkable."""
        # Create a mock that implements the protocol
        mock_source = Mock(spec=SuggestionSource)
        mock_source.get_suggestions = Mock(return_value=[])

        assert isinstance(mock_source, SuggestionSource)

    def test_protocol_method_signature(self):
        """Test protocol requires get_suggestions method."""

        class ValidSource:
            def get_suggestions(self) -> list[Suggestion]:
                return []

        assert isinstance(ValidSource(), SuggestionSource)


class TestTaskSource:
    """Test TaskSource suggestion generator."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock task backend."""
        backend = MagicMock()
        backend.get_ready_tasks = MagicMock(return_value=[])
        backend.list_tasks = MagicMock(return_value=[])
        return backend

    @pytest.fixture
    def task_source(self, mock_backend, tmp_path):
        """Create TaskSource with mocked backend."""
        with patch("cub.core.suggestions.sources.get_backend", return_value=mock_backend):
            source = TaskSource(project_dir=tmp_path)
            yield source

    def test_no_suggestions_when_no_tasks(self, task_source, mock_backend):
        """Test empty suggestions when no tasks available."""
        mock_backend.get_ready_tasks.return_value = []
        mock_backend.list_tasks.return_value = []

        suggestions = task_source.get_suggestions()

        assert suggestions == []

    def test_suggests_ready_tasks(self, task_source, mock_backend):
        """Test suggestion generation for ready tasks."""
        ready_task = Task(
            id="cub-001",
            title="Implement feature X",
            status=TaskStatus.OPEN,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
            description="Add new feature",
            depends_on=[],
            blocks=[],
        )

        mock_backend.get_ready_tasks.return_value = [ready_task]
        mock_backend.list_tasks.return_value = []

        suggestions = task_source.get_suggestions()

        assert len(suggestions) >= 1
        task_suggestion = suggestions[0]
        assert task_suggestion.category == SuggestionCategory.TASK
        assert "cub-001" in task_suggestion.title
        assert task_suggestion.priority_score > 0.5  # P1 should boost priority
        assert task_suggestion.context["task_id"] == "cub-001"
        assert task_suggestion.context["is_ready"] is True

    def test_suggests_multiple_ready_tasks(self, task_source, mock_backend):
        """Test suggesting top 3 ready tasks."""
        ready_tasks = [
            Task(
                id=f"cub-{i:03d}",
                title=f"Task {i}",
                status=TaskStatus.OPEN,
                priority=TaskPriority.P2,
            )
            for i in range(5)
        ]

        mock_backend.get_ready_tasks.return_value = ready_tasks
        mock_backend.list_tasks.return_value = []

        suggestions = task_source.get_suggestions()

        # Should suggest top 3 ready tasks
        task_suggestions = [s for s in suggestions if s.category == SuggestionCategory.TASK]
        assert len(task_suggestions) <= 3

    def test_warns_about_in_progress_tasks(self, task_source, mock_backend):
        """Test warning suggestions for stale in-progress tasks."""
        in_progress_task = Task(
            id="cub-002",
            title="Abandoned work",
            status=TaskStatus.IN_PROGRESS,
        )

        mock_backend.get_ready_tasks.return_value = []
        mock_backend.list_tasks.side_effect = lambda status=None: (
            [in_progress_task] if status == TaskStatus.IN_PROGRESS else []
        )

        suggestions = task_source.get_suggestions()

        assert len(suggestions) == 1
        assert "abandon" in suggestions[0].title.lower()
        assert suggestions[0].priority_score == 0.7

    def test_suggests_resolving_dependencies(self, task_source, mock_backend):
        """Test suggestion when tasks are blocked by dependencies."""
        blocked_task = Task(
            id="cub-003",
            title="Blocked task",
            status=TaskStatus.OPEN,
            depends_on=["cub-001", "cub-002"],
        )

        mock_backend.get_ready_tasks.return_value = []
        mock_backend.list_tasks.side_effect = lambda status=None: (
            [blocked_task] if status == TaskStatus.OPEN else []
        )

        suggestions = task_source.get_suggestions()

        # Should suggest resolving dependencies
        plan_suggestions = [s for s in suggestions if s.category == SuggestionCategory.PLAN]
        assert len(plan_suggestions) == 1
        assert "dependencies" in plan_suggestions[0].title.lower()
        assert plan_suggestions[0].context["blocked_tasks"] == 1

    def test_priority_score_calculation(self, task_source, mock_backend):
        """Test that priority scores reflect task importance."""
        p0_task = Task(
            id="cub-p0",
            title="Critical",
            priority=TaskPriority.P0,
            status=TaskStatus.OPEN,
        )
        p4_task = Task(
            id="cub-p4",
            title="Low priority",
            priority=TaskPriority.P4,
            status=TaskStatus.OPEN,
        )

        mock_backend.get_ready_tasks.return_value = [p0_task, p4_task]
        mock_backend.list_tasks.return_value = []

        suggestions = task_source.get_suggestions()

        task_suggestions = [s for s in suggestions if s.category == SuggestionCategory.TASK]
        p0_score = next(s.priority_score for s in task_suggestions if "cub-p0" in s.title)
        p4_score = next(s.priority_score for s in task_suggestions if "cub-p4" in s.title)

        assert p0_score > p4_score

    def test_bug_tasks_get_priority_boost(self, task_source, mock_backend):
        """Test that bug tasks get priority boost."""
        bug_task = Task(
            id="cub-bug",
            title="Fix critical bug",
            type=TaskType.BUG,
            priority=TaskPriority.P2,
            status=TaskStatus.OPEN,
        )
        feature_task = Task(
            id="cub-feat",
            title="Add feature",
            type=TaskType.TASK,
            priority=TaskPriority.P2,
            status=TaskStatus.OPEN,
        )

        mock_backend.get_ready_tasks.return_value = [bug_task, feature_task]
        mock_backend.list_tasks.return_value = []

        suggestions = task_source.get_suggestions()

        task_suggestions = [s for s in suggestions if s.category == SuggestionCategory.TASK]
        bug_score = next(s.priority_score for s in task_suggestions if "cub-bug" in s.title)
        feat_score = next(s.priority_score for s in task_suggestions if "cub-feat" in s.title)

        assert bug_score > feat_score

    def test_blocking_tasks_get_priority_boost(self, task_source, mock_backend):
        """Test that tasks blocking others get priority boost."""
        blocking_task = Task(
            id="cub-block",
            title="Blocking task",
            priority=TaskPriority.P2,
            status=TaskStatus.OPEN,
            blocks=["cub-001", "cub-002"],
        )

        mock_backend.get_ready_tasks.return_value = [blocking_task]
        mock_backend.list_tasks.return_value = []

        suggestions = task_source.get_suggestions()

        task_suggestions = [s for s in suggestions if s.category == SuggestionCategory.TASK]
        assert task_suggestions[0].priority_score >= 0.65  # Base + boost

    def test_handles_backend_errors_gracefully(self, tmp_path):
        """Test graceful handling when backend is unavailable."""
        failing_backend = MagicMock()
        failing_backend.get_ready_tasks.side_effect = Exception("Backend error")

        with patch("cub.core.suggestions.sources.get_backend", return_value=failing_backend):
            source = TaskSource(project_dir=tmp_path)
            suggestions = source.get_suggestions()

            # Should return empty list, not crash
            assert suggestions == []


class TestGitSource:
    """Test GitSource suggestion generator."""

    @pytest.fixture
    def git_source(self, tmp_path):
        """Create GitSource with temp directory."""
        return GitSource(project_dir=tmp_path)

    def test_suggests_commit_when_changes_exist(self, git_source):
        """Test suggestion to commit when there are uncommitted changes."""
        with patch.object(git_source, "_has_uncommitted_changes", return_value=True):
            suggestions = git_source.get_suggestions()

            commit_suggestions = [
                s for s in suggestions if s.category == SuggestionCategory.GIT
            ]
            assert len(commit_suggestions) >= 1
            assert "commit" in commit_suggestions[0].title.lower()
            assert commit_suggestions[0].priority_score == 0.75

    def test_suggests_push_when_commits_ahead(self, git_source):
        """Test suggestion to push when local commits exist."""
        with patch.object(git_source, "_has_uncommitted_changes", return_value=False):
            with patch.object(git_source, "_get_commits_ahead", return_value=3):
                suggestions = git_source.get_suggestions()

                push_suggestions = [
                    s for s in suggestions if "push" in s.title.lower()
                ]
                assert len(push_suggestions) == 1
                assert push_suggestions[0].priority_score == 0.65
                assert push_suggestions[0].context["commits_ahead"] == 3

    def test_suggests_pr_with_multiple_recent_commits(self, git_source):
        """Test PR suggestion when branch has multiple recent commits."""
        recent_commits = [
            {"hash": f"abc{i}", "message": f"commit {i}", "timestamp": "2026-01-28T10:00:00Z"}
            for i in range(5)
        ]

        with patch.object(git_source, "_has_uncommitted_changes", return_value=False):
            with patch.object(git_source, "_get_commits_ahead", return_value=0):
                with patch.object(
                    git_source, "_get_recent_commits", return_value=recent_commits
                ):
                    with patch.object(git_source, "_get_current_branch", return_value="feature-x"):
                        suggestions = git_source.get_suggestions()

                        pr_suggestions = [
                            s for s in suggestions if "pull request" in s.title.lower()
                        ]
                        assert len(pr_suggestions) == 1
                        assert pr_suggestions[0].context["branch"] == "feature-x"
                        assert pr_suggestions[0].context["recent_commits"] == 5

    def test_no_pr_suggestion_on_main_branch(self, git_source):
        """Test no PR suggestion when on main branch."""
        recent_commits = [
            {"hash": "abc", "message": "commit", "timestamp": "2026-01-28T10:00:00Z"}
        ] * 5

        with patch.object(git_source, "_has_uncommitted_changes", return_value=False):
            with patch.object(git_source, "_get_commits_ahead", return_value=0):
                with patch.object(
                    git_source, "_get_recent_commits", return_value=recent_commits
                ):
                    with patch.object(git_source, "_get_current_branch", return_value="main"):
                        suggestions = git_source.get_suggestions()

                        pr_suggestions = [
                            s for s in suggestions if "pull request" in s.title.lower()
                        ]
                        assert len(pr_suggestions) == 0

    def test_no_suggestions_when_clean_repo(self, git_source):
        """Test no suggestions when repo is clean and synced."""
        with patch.object(git_source, "_has_uncommitted_changes", return_value=False):
            with patch.object(git_source, "_get_commits_ahead", return_value=0):
                with patch.object(git_source, "_get_recent_commits", return_value=[]):
                    suggestions = git_source.get_suggestions()

                    assert suggestions == []

    def test_has_uncommitted_changes_detection(self, git_source, tmp_path):
        """Test detection of uncommitted changes via git status."""
        # Mock subprocess to simulate git status output
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=" M file.txt\n",
            )

            assert git_source._has_uncommitted_changes() is True

    def test_get_commits_ahead_parsing(self, git_source):
        """Test parsing of commits ahead count."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="5\n",
            )

            assert git_source._get_commits_ahead() == 5

    def test_handles_git_not_available(self, git_source):
        """Test graceful handling when git is not available."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            suggestions = git_source.get_suggestions()

            # Should return empty list, not crash
            assert suggestions == []


class TestLedgerSource:
    """Test LedgerSource suggestion generator."""

    @pytest.fixture
    def mock_ledger(self):
        """Create a mock ledger reader."""
        ledger = MagicMock()
        ledger.list_tasks = MagicMock(return_value=[])
        ledger.get_task = MagicMock(return_value=None)
        return ledger

    @pytest.fixture
    def ledger_source(self, mock_ledger, tmp_path):
        """Create LedgerSource with mocked ledger."""
        source = LedgerSource(project_dir=tmp_path)
        source.ledger = mock_ledger
        return source

    def test_no_suggestions_when_no_ledger(self, tmp_path):
        """Test no suggestions when ledger is unavailable."""
        source = LedgerSource(project_dir=tmp_path)
        source.ledger = None

        suggestions = source.get_suggestions()

        assert suggestions == []

    def test_suggests_fixing_failed_verifications(self, ledger_source, mock_ledger):
        """Test suggestion to fix tasks with failed verification."""
        failed_tasks = [
            LedgerIndex(
                id="cub-001",
                title="Task 1",
                completed="2026-01-28",
                verification="fail",
            ),
            LedgerIndex(
                id="cub-002",
                title="Task 2",
                completed="2026-01-28",
                verification="fail",
            ),
        ]

        # Mock list_tasks for returning failed tasks (verification=FAIL)
        # Return empty list for other calls (reviewing completed, expensive tasks)
        def mock_list_tasks_impl(verification=None):
            if verification == VerificationStatus.FAIL:
                return failed_tasks
            return []

        mock_ledger.list_tasks.side_effect = mock_list_tasks_impl

        suggestions = ledger_source.get_suggestions()

        fix_suggestions = [
            s for s in suggestions if "failed verification" in s.title.lower()
        ]
        assert len(fix_suggestions) == 1
        assert fix_suggestions[0].priority_score == 0.85
        assert fix_suggestions[0].category == SuggestionCategory.REVIEW
        assert fix_suggestions[0].context["failed_count"] == 2

    def test_suggests_reviewing_completed_tasks(self, ledger_source, mock_ledger):
        """Test suggestion to review tasks needing validation."""
        completed_task = LedgerEntry(
            id="cub-003",
            title="Completed task",
            completed=datetime.now(timezone.utc),
            lineage=Lineage(),
            outcome=Outcome(),
            verification=Verification(),
            workflow=WorkflowState(stage=WorkflowStage.NEEDS_REVIEW),
        )

        mock_ledger.list_tasks.return_value = [
            LedgerIndex(
                id="cub-003",
                title="Completed task",
                completed="2026-01-28",
            )
        ]
        mock_ledger.get_task.return_value = completed_task

        suggestions = ledger_source.get_suggestions()

        review_suggestions = [
            s for s in suggestions if "review" in s.title.lower()
        ]
        assert len(review_suggestions) >= 1
        assert review_suggestions[0].priority_score == 0.6

    def test_suggests_reviewing_expensive_tasks(self, ledger_source, mock_ledger):
        """Test suggestion to review high-cost tasks."""
        expensive_tasks = [
            LedgerIndex(
                id="cub-expensive",
                title="Expensive task",
                completed="2026-01-28",
                cost_usd=7.50,
            )
        ]

        mock_ledger.list_tasks.return_value = expensive_tasks

        suggestions = ledger_source.get_suggestions()

        cost_suggestions = [
            s for s in suggestions if "expensive" in s.title.lower()
        ]
        assert len(cost_suggestions) == 1
        assert cost_suggestions[0].context["max_cost"] == 7.50

    def test_handles_ledger_errors_gracefully(self, ledger_source, mock_ledger):
        """Test graceful handling of ledger read errors."""
        mock_ledger.list_tasks.side_effect = Exception("Ledger error")

        suggestions = ledger_source.get_suggestions()

        # Should not crash, may return partial suggestions
        assert isinstance(suggestions, list)


class TestMilestoneSource:
    """Test MilestoneSource suggestion generator."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock task backend."""
        backend = MagicMock()
        backend.list_tasks = MagicMock(return_value=[])
        return backend

    @pytest.fixture
    def milestone_source(self, mock_backend, tmp_path):
        """Create MilestoneSource with mocked backend."""
        with patch("cub.core.suggestions.sources.get_backend", return_value=mock_backend):
            source = MilestoneSource(project_dir=tmp_path)
            yield source

    def test_no_suggestions_when_no_epics(self, milestone_source, mock_backend):
        """Test no suggestions when no epics exist."""
        mock_backend.list_tasks.return_value = []

        suggestions = milestone_source.get_suggestions()

        assert suggestions == []

    def test_suggests_continuing_epic_with_ready_tasks(self, milestone_source, mock_backend):
        """Test suggestion to continue epic with ready tasks."""
        epic = Task(
            id="epic-001",
            title="Big Feature",
            type=TaskType.EPIC,
            status=TaskStatus.OPEN,
        )
        epic_task_1 = Task(
            id="cub-001",
            title="Subtask 1",
            status=TaskStatus.OPEN,
            parent="epic-001",
            depends_on=[],
        )
        epic_task_2 = Task(
            id="cub-002",
            title="Subtask 2",
            status=TaskStatus.CLOSED,
            parent="epic-001",
        )

        def list_tasks_side_effect(parent=None):
            if parent == "epic-001":
                return [epic_task_1, epic_task_2]
            return [epic]

        mock_backend.list_tasks.side_effect = list_tasks_side_effect

        suggestions = milestone_source.get_suggestions()

        epic_suggestions = [
            s for s in suggestions if s.category == SuggestionCategory.MILESTONE
        ]
        assert len(epic_suggestions) >= 1
        assert "continue" in epic_suggestions[0].title.lower()
        assert "epic-001" in epic_suggestions[0].title
        assert epic_suggestions[0].context["ready_tasks"] == 1

    def test_suggests_closing_completed_epic(self, milestone_source, mock_backend):
        """Test suggestion to close epic when all tasks done."""
        epic = Task(
            id="epic-002",
            title="Completed Feature",
            type=TaskType.EPIC,
            status=TaskStatus.OPEN,
        )
        closed_tasks = [
            Task(
                id=f"cub-{i:03d}",
                title=f"Task {i}",
                status=TaskStatus.CLOSED,
                parent="epic-002",
            )
            for i in range(3)
        ]

        def list_tasks_side_effect(parent=None):
            if parent == "epic-002":
                return closed_tasks
            return [epic]

        mock_backend.list_tasks.side_effect = list_tasks_side_effect

        suggestions = milestone_source.get_suggestions()

        close_suggestions = [
            s for s in suggestions if "close" in s.title.lower()
        ]
        assert len(close_suggestions) >= 1
        assert "epic-002" in close_suggestions[0].title
        assert close_suggestions[0].context["total_tasks"] == 3

    def test_calculates_epic_completion_percentage(self, milestone_source, mock_backend):
        """Test epic completion percentage calculation."""
        epic = Task(
            id="epic-003",
            title="Half-Done Feature",
            type=TaskType.EPIC,
            status=TaskStatus.OPEN,
        )
        epic_tasks = [
            Task(id="cub-001", title="Task 1", status=TaskStatus.CLOSED, parent="epic-003"),
            Task(id="cub-002", title="Task 2", status=TaskStatus.OPEN, parent="epic-003"),
        ]

        def list_tasks_side_effect(parent=None):
            if parent == "epic-003":
                return epic_tasks
            return [epic]

        mock_backend.list_tasks.side_effect = list_tasks_side_effect

        suggestions = milestone_source.get_suggestions()

        epic_suggestions = [
            s for s in suggestions if s.category == SuggestionCategory.MILESTONE
        ]
        if epic_suggestions:
            assert epic_suggestions[0].context["completion_percentage"] == 50.0

    def test_handles_backend_errors_gracefully(self, tmp_path):
        """Test graceful handling when backend errors occur."""
        failing_backend = MagicMock()
        failing_backend.list_tasks.side_effect = Exception("Backend error")

        with patch("cub.core.suggestions.sources.get_backend", return_value=failing_backend):
            source = MilestoneSource(project_dir=tmp_path)
            suggestions = source.get_suggestions()

            # Should return empty list, not crash
            assert suggestions == []
