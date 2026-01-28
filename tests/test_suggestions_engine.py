"""
Tests for suggestion ranking and engine.

Tests the ranking algorithm and SuggestionEngine that composes
sources and provides the public API.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from cub.core.suggestions.engine import SuggestionEngine, WelcomeMessage
from cub.core.suggestions.models import Suggestion, SuggestionCategory
from cub.core.suggestions.ranking import (
    _calculate_final_score,
    _get_recency_decay,
    _get_urgency_multiplier,
    rank_suggestions,
)


class TestRankingScoringFunctions:
    """Test individual ranking functions."""

    def test_urgency_multiplier_review_highest(self):
        """Test REVIEW category gets highest multiplier."""
        assert _get_urgency_multiplier(SuggestionCategory.REVIEW) == 1.2

    def test_urgency_multiplier_git_high(self):
        """Test GIT category gets high multiplier."""
        assert _get_urgency_multiplier(SuggestionCategory.GIT) == 1.15

    def test_urgency_multiplier_task_above_baseline(self):
        """Test TASK category gets above-baseline multiplier."""
        assert _get_urgency_multiplier(SuggestionCategory.TASK) == 1.1

    def test_urgency_multiplier_milestone_slightly_above(self):
        """Test MILESTONE category gets slightly above baseline."""
        assert _get_urgency_multiplier(SuggestionCategory.MILESTONE) == 1.05

    def test_urgency_multiplier_plan_baseline(self):
        """Test PLAN category gets baseline multiplier."""
        assert _get_urgency_multiplier(SuggestionCategory.PLAN) == 1.0

    def test_urgency_multiplier_cleanup_below_baseline(self):
        """Test CLEANUP category gets below-baseline multiplier."""
        assert _get_urgency_multiplier(SuggestionCategory.CLEANUP) == 0.95

    def test_recency_decay_fresh_no_decay(self):
        """Test very fresh suggestions have no decay."""
        now = datetime.now(timezone.utc)
        # 30 minutes ago
        recent = now - timedelta(minutes=30)

        decay = _get_recency_decay(recent)
        assert decay == 1.0

    def test_recency_decay_one_hour_no_decay(self):
        """Test suggestions at exactly 1 hour have no decay."""
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        decay = _get_recency_decay(one_hour_ago)
        assert abs(decay - 1.0) < 0.01  # Allow small floating point error

    def test_recency_decay_within_24_hours_linear(self):
        """Test linear decay between 1-24 hours."""
        now = datetime.now(timezone.utc)

        # 12 hours ago (midpoint) should be around 0.975
        halfway = now - timedelta(hours=12)
        decay_halfway = _get_recency_decay(halfway)
        assert 0.97 < decay_halfway < 0.98

        # 23 hours ago should be close to 0.95
        near_end = now - timedelta(hours=23)
        decay_near_end = _get_recency_decay(near_end)
        assert 0.94 < decay_near_end < 0.96

    def test_recency_decay_old_minimum(self):
        """Test old suggestions get minimum decay."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=7)

        decay = _get_recency_decay(old)
        assert decay == 0.95

    def test_calculate_final_score_combines_factors(self):
        """Test final score combines all factors."""
        # Fresh, high-priority, review suggestion
        suggestion = Suggestion(
            category=SuggestionCategory.REVIEW,
            title="Fix critical bug",
            rationale="Test",
            priority_score=0.85,
            created_at=datetime.now(timezone.utc),
        )

        score = _calculate_final_score(suggestion)

        # Should be: 0.85 * 1.2 * 1.0 = 1.02
        assert abs(score - 1.02) < 0.01

    def test_calculate_final_score_low_priority_cleanup(self):
        """Test low priority cleanup gets lower score."""
        suggestion = Suggestion(
            category=SuggestionCategory.CLEANUP,
            title="Remove old files",
            rationale="Test",
            priority_score=0.3,
            created_at=datetime.now(timezone.utc),
        )

        score = _calculate_final_score(suggestion)

        # Should be: 0.3 * 0.95 * 1.0 = 0.285
        assert abs(score - 0.285) < 0.01


class TestRankSuggestions:
    """Test the main ranking function."""

    def test_rank_empty_list(self):
        """Test ranking empty list returns empty list."""
        result = rank_suggestions([])
        assert result == []

    def test_rank_single_suggestion(self):
        """Test ranking single suggestion returns it."""
        suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Do something",
            rationale="Test",
            priority_score=0.5,
        )

        result = rank_suggestions([suggestion])
        assert len(result) == 1
        assert result[0] == suggestion

    def test_rank_by_priority_score(self):
        """Test suggestions ranked by base priority score."""
        low = Suggestion(
            category=SuggestionCategory.TASK,
            title="Low priority",
            rationale="Test",
            priority_score=0.3,
        )
        high = Suggestion(
            category=SuggestionCategory.TASK,
            title="High priority",
            rationale="Test",
            priority_score=0.8,
        )

        result = rank_suggestions([low, high])

        assert len(result) == 2
        assert result[0] == high
        assert result[1] == low

    def test_rank_by_category_urgency(self):
        """Test suggestions ranked by category urgency multiplier."""
        # Same base priority, different categories
        cleanup = Suggestion(
            category=SuggestionCategory.CLEANUP,
            title="Cleanup task",
            rationale="Test",
            priority_score=0.5,
        )
        review = Suggestion(
            category=SuggestionCategory.REVIEW,
            title="Review task",
            rationale="Test",
            priority_score=0.5,
        )

        result = rank_suggestions([cleanup, review])

        assert len(result) == 2
        # Review should come first due to higher urgency multiplier
        assert result[0] == review
        assert result[1] == cleanup

    def test_rank_by_recency(self):
        """Test suggestions ranked by recency."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=2)

        old_suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Old suggestion",
            rationale="Test",
            priority_score=0.5,
            created_at=old,
        )
        new_suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="New suggestion",
            rationale="Test",
            priority_score=0.5,
            created_at=now,
        )

        result = rank_suggestions([old_suggestion, new_suggestion])

        assert len(result) == 2
        # New should come first due to better recency decay
        assert result[0] == new_suggestion
        assert result[1] == old_suggestion

    def test_rank_complex_ordering(self):
        """Test complex ranking with multiple factors."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=1)

        suggestions = [
            # Low priority, cleanup, fresh
            Suggestion(
                category=SuggestionCategory.CLEANUP,
                title="Cleanup",
                rationale="Test",
                priority_score=0.3,
                created_at=now,
            ),
            # Medium priority, task, old
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Task",
                rationale="Test",
                priority_score=0.5,
                created_at=old,
            ),
            # High priority, review, fresh
            Suggestion(
                category=SuggestionCategory.REVIEW,
                title="Review",
                rationale="Test",
                priority_score=0.85,
                created_at=now,
            ),
            # Medium priority, git, fresh
            Suggestion(
                category=SuggestionCategory.GIT,
                title="Git",
                rationale="Test",
                priority_score=0.6,
                created_at=now,
            ),
        ]

        result = rank_suggestions(suggestions)

        assert len(result) == 4
        # Review should be first (0.85 * 1.2 * 1.0 = 1.02)
        assert result[0].title == "Review"
        # Git should be second (0.6 * 1.15 * 1.0 = 0.69)
        assert result[1].title == "Git"
        # Task should be third (0.5 * 1.1 * 0.95 ≈ 0.52)
        assert result[2].title == "Task"
        # Cleanup should be last (0.3 * 0.95 * 1.0 = 0.285)
        assert result[3].title == "Cleanup"

    def test_rank_stable_sort_by_title(self):
        """Test suggestions with same score are sorted by title."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Zebra task",
                rationale="Test",
                priority_score=0.5,
            ),
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Alpha task",
                rationale="Test",
                priority_score=0.5,
            ),
        ]

        result = rank_suggestions(suggestions)

        assert len(result) == 2
        assert result[0].title == "Alpha task"
        assert result[1].title == "Zebra task"


class TestSuggestionEngine:
    """Test SuggestionEngine public API."""

    @pytest.fixture
    def mock_sources(self):
        """Create mock suggestion sources."""
        task_source = Mock()
        git_source = Mock()
        ledger_source = Mock()
        milestone_source = Mock()

        # Default: no suggestions
        task_source.get_suggestions.return_value = []
        git_source.get_suggestions.return_value = []
        ledger_source.get_suggestions.return_value = []
        milestone_source.get_suggestions.return_value = []

        return {
            "task": task_source,
            "git": git_source,
            "ledger": ledger_source,
            "milestone": milestone_source,
        }

    @pytest.fixture
    def engine(self, tmp_path, mock_sources):
        """Create SuggestionEngine with mocked sources."""
        with (
            patch("cub.core.suggestions.engine.TaskSource", return_value=mock_sources["task"]),
            patch("cub.core.suggestions.engine.GitSource", return_value=mock_sources["git"]),
            patch("cub.core.suggestions.engine.LedgerSource", return_value=mock_sources["ledger"]),
            patch(
                "cub.core.suggestions.engine.MilestoneSource",
                return_value=mock_sources["milestone"],
            ),
        ):
            yield SuggestionEngine(project_dir=tmp_path)

    def test_engine_initialization(self, tmp_path):
        """Test engine initializes with default project dir."""
        engine = SuggestionEngine()
        assert engine.project_dir == Path.cwd()

        engine2 = SuggestionEngine(project_dir=tmp_path)
        assert engine2.project_dir == tmp_path

    def test_get_suggestions_empty(self, engine, mock_sources):
        """Test get_suggestions with no suggestions."""
        result = engine.get_suggestions()
        assert result == []

    def test_get_suggestions_from_multiple_sources(self, engine, mock_sources):
        """Test get_suggestions collects from all sources."""
        suggestion1 = Suggestion(
            category=SuggestionCategory.TASK,
            title="Task 1",
            rationale="Test",
            priority_score=0.5,
        )
        suggestion2 = Suggestion(
            category=SuggestionCategory.GIT,
            title="Git 1",
            rationale="Test",
            priority_score=0.6,
        )
        suggestion3 = Suggestion(
            category=SuggestionCategory.REVIEW,
            title="Review 1",
            rationale="Test",
            priority_score=0.8,
        )

        mock_sources["task"].get_suggestions.return_value = [suggestion1]
        mock_sources["git"].get_suggestions.return_value = [suggestion2]
        mock_sources["ledger"].get_suggestions.return_value = [suggestion3]

        result = engine.get_suggestions()

        assert len(result) == 3
        # Should be ranked: Review (highest), Git, Task
        assert result[0] == suggestion3
        assert result[1] == suggestion2
        assert result[2] == suggestion1

    def test_get_suggestions_with_limit(self, engine, mock_sources):
        """Test get_suggestions respects limit parameter."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title=f"Task {i}",
                rationale="Test",
                priority_score=0.5 + (i * 0.1),
            )
            for i in range(5)
        ]

        mock_sources["task"].get_suggestions.return_value = suggestions

        result = engine.get_suggestions(limit=3)

        assert len(result) == 3
        # Should get top 3 by score
        assert all(s in suggestions for s in result)

    def test_get_suggestions_handles_source_failure(self, engine, mock_sources):
        """Test get_suggestions continues if a source fails."""
        suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Working task",
            rationale="Test",
            priority_score=0.5,
        )

        mock_sources["task"].get_suggestions.return_value = [suggestion]
        mock_sources["git"].get_suggestions.side_effect = Exception("Git failed")
        mock_sources["ledger"].get_suggestions.return_value = []

        result = engine.get_suggestions()

        # Should still get the task suggestion despite git failure
        assert len(result) == 1
        assert result[0] == suggestion

    def test_get_next_action_returns_top_suggestion(self, engine, mock_sources):
        """Test get_next_action returns single best suggestion."""
        suggestion1 = Suggestion(
            category=SuggestionCategory.TASK,
            title="Lower priority",
            rationale="Test",
            priority_score=0.5,
        )
        suggestion2 = Suggestion(
            category=SuggestionCategory.REVIEW,
            title="Higher priority",
            rationale="Test",
            priority_score=0.9,
        )

        mock_sources["task"].get_suggestions.return_value = [suggestion1]
        mock_sources["ledger"].get_suggestions.return_value = [suggestion2]

        result = engine.get_next_action()

        assert result == suggestion2

    def test_get_next_action_returns_none_when_empty(self, engine, mock_sources):
        """Test get_next_action returns None when no suggestions."""
        result = engine.get_next_action()
        assert result is None

    def test_get_welcome_returns_message(self, engine, mock_sources):
        """Test get_welcome returns WelcomeMessage."""
        # Mock task backend
        mock_backend = MagicMock()
        mock_backend.list_tasks.return_value = []
        mock_backend.get_ready_tasks.return_value = []
        mock_sources["task"].backend = mock_backend

        suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Top suggestion",
            rationale="Test",
            priority_score=0.8,
        )
        mock_sources["task"].get_suggestions.return_value = [suggestion]

        result = engine.get_welcome(
            max_suggestions=5, available_skills=["commit", "review"]
        )

        assert isinstance(result, WelcomeMessage)
        assert result.total_tasks == 0
        assert result.open_tasks == 0
        assert result.in_progress_tasks == 0
        assert result.ready_tasks == 0
        assert len(result.top_suggestions) == 1
        assert result.top_suggestions[0] == suggestion
        assert result.available_skills == ["commit", "review"]

    def test_get_welcome_with_task_stats(self, engine, mock_sources):
        """Test get_welcome includes task statistics."""
        from cub.core.tasks.models import Task, TaskPriority, TaskStatus, TaskType

        # Create mock tasks
        tasks = [
            Task(
                id=f"task-{i}",
                title=f"Task {i}",
                status=TaskStatus.OPEN if i < 3 else TaskStatus.CLOSED,
                priority=TaskPriority.P2,
                type=TaskType.TASK,
            )
            for i in range(5)
        ]

        in_progress_task = Task(
            id="task-ip",
            title="In Progress",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.P1,
            type=TaskType.TASK,
        )

        ready_tasks = [tasks[0], tasks[1]]

        mock_backend = MagicMock()
        mock_backend.list_tasks.side_effect = lambda status=None: (
            tasks + [in_progress_task]
            if status is None
            else [t for t in tasks + [in_progress_task] if t.status == status]
        )
        mock_backend.get_ready_tasks.return_value = ready_tasks

        mock_sources["task"].backend = mock_backend
        mock_sources["task"].get_suggestions.return_value = []

        result = engine.get_welcome()

        assert result.total_tasks == 6
        assert result.open_tasks == 3
        assert result.in_progress_tasks == 1
        assert result.ready_tasks == 2

    def test_get_welcome_limits_suggestions(self, engine, mock_sources):
        """Test get_welcome respects max_suggestions parameter."""
        suggestions = [
            Suggestion(
                category=SuggestionCategory.TASK,
                title=f"Task {i}",
                rationale="Test",
                priority_score=0.5,
            )
            for i in range(10)
        ]

        mock_sources["task"].get_suggestions.return_value = suggestions
        mock_sources["task"].backend = MagicMock()
        mock_sources["task"].backend.list_tasks.return_value = []
        mock_sources["task"].backend.get_ready_tasks.return_value = []

        result = engine.get_welcome(max_suggestions=3)

        assert len(result.top_suggestions) == 3

    def test_get_welcome_handles_missing_backend(self, engine, mock_sources):
        """Test get_welcome handles missing task backend gracefully."""
        # Remove TaskSource from sources
        engine.sources = [mock_sources["git"], mock_sources["ledger"]]

        result = engine.get_welcome()

        # Should still return a message with zero stats
        assert result.total_tasks == 0
        assert result.open_tasks == 0
        assert result.in_progress_tasks == 0
        assert result.ready_tasks == 0


class TestWelcomeMessage:
    """Test WelcomeMessage dataclass."""

    def test_create_welcome_message(self):
        """Test creating WelcomeMessage."""
        suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Test",
            rationale="Test",
            priority_score=0.5,
        )

        message = WelcomeMessage(
            total_tasks=10,
            open_tasks=5,
            in_progress_tasks=2,
            ready_tasks=3,
            top_suggestions=[suggestion],
            available_skills=["commit", "review"],
        )

        assert message.total_tasks == 10
        assert message.open_tasks == 5
        assert message.in_progress_tasks == 2
        assert message.ready_tasks == 3
        assert len(message.top_suggestions) == 1
        assert message.top_suggestions[0] == suggestion
        assert message.available_skills == ["commit", "review"]
