"""
Tests for suggestion models.

Tests the Pydantic models for suggestions, including Suggestion,
SuggestionCategory, and ProjectSnapshot.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cub.core.suggestions.models import (
    ProjectSnapshot,
    Suggestion,
    SuggestionCategory,
)


class TestSuggestionCategory:
    """Test SuggestionCategory enum."""

    def test_all_categories_exist(self):
        """Test all expected category values exist."""
        assert SuggestionCategory.TASK == "task"
        assert SuggestionCategory.REVIEW == "review"
        assert SuggestionCategory.MILESTONE == "milestone"
        assert SuggestionCategory.GIT == "git"
        assert SuggestionCategory.CLEANUP == "cleanup"
        assert SuggestionCategory.PLAN == "plan"

    def test_category_from_string(self):
        """Test creating category from string."""
        assert SuggestionCategory("task") == SuggestionCategory.TASK
        assert SuggestionCategory("review") == SuggestionCategory.REVIEW
        assert SuggestionCategory("git") == SuggestionCategory.GIT

    def test_emoji_property(self):
        """Test that each category has an emoji."""
        assert SuggestionCategory.TASK.emoji == "📋"
        assert SuggestionCategory.REVIEW.emoji == "🔍"
        assert SuggestionCategory.MILESTONE.emoji == "🎯"
        assert SuggestionCategory.GIT.emoji == "🌿"
        assert SuggestionCategory.CLEANUP.emoji == "🧹"
        assert SuggestionCategory.PLAN.emoji == "📐"


class TestSuggestion:
    """Test Suggestion model."""

    def test_create_minimal_suggestion(self):
        """Test creating suggestion with minimal required fields."""
        suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Work on task",
            rationale="This task is ready",
            priority_score=0.5,
        )

        assert suggestion.category == SuggestionCategory.TASK
        assert suggestion.title == "Work on task"
        assert suggestion.rationale == "This task is ready"
        assert suggestion.priority_score == 0.5
        assert suggestion.description == ""
        assert suggestion.action is None
        assert suggestion.source == "unknown"
        assert suggestion.context == {}
        assert isinstance(suggestion.created_at, datetime)

    def test_create_full_suggestion(self):
        """Test creating suggestion with all fields."""
        created_at = datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc)
        suggestion = Suggestion(
            category=SuggestionCategory.GIT,
            title="Push commits",
            description="You have 3 commits to push",
            rationale="Backing up your work is important",
            priority_score=0.65,
            action="git push",
            source="git",
            context={"commits_ahead": 3, "branch": "feature-x"},
            created_at=created_at,
        )

        assert suggestion.category == SuggestionCategory.GIT
        assert suggestion.title == "Push commits"
        assert suggestion.description == "You have 3 commits to push"
        assert suggestion.rationale == "Backing up your work is important"
        assert suggestion.priority_score == 0.65
        assert suggestion.action == "git push"
        assert suggestion.source == "git"
        assert suggestion.context["commits_ahead"] == 3
        assert suggestion.context["branch"] == "feature-x"
        assert suggestion.created_at == created_at

    def test_priority_score_validation_min(self):
        """Test priority score must be >= 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Invalid",
                rationale="Test",
                priority_score=-0.1,
            )
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_priority_score_validation_max(self):
        """Test priority score must be <= 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Invalid",
                rationale="Test",
                priority_score=1.1,
            )
        assert "less than or equal to 1" in str(exc_info.value)

    def test_priority_score_validation_exact_bounds(self):
        """Test priority score accepts exact boundary values."""
        min_suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Min score",
            rationale="Test",
            priority_score=0.0,
        )
        assert min_suggestion.priority_score == 0.0

        max_suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Max score",
            rationale="Test",
            priority_score=1.0,
        )
        assert max_suggestion.priority_score == 1.0

    def test_title_required(self):
        """Test title is required and cannot be empty."""
        with pytest.raises(ValidationError):
            Suggestion(
                category=SuggestionCategory.TASK,
                title="",
                rationale="Test",
                priority_score=0.5,
            )

    def test_rationale_required(self):
        """Test rationale is required and cannot be empty."""
        with pytest.raises(ValidationError):
            Suggestion(
                category=SuggestionCategory.TASK,
                title="Test",
                rationale="",
                priority_score=0.5,
            )

    def test_formatted_title_property(self):
        """Test formatted_title includes category emoji."""
        suggestion = Suggestion(
            category=SuggestionCategory.MILESTONE,
            title="Complete epic",
            rationale="All tasks done",
            priority_score=0.7,
        )

        assert suggestion.formatted_title == "🎯 Complete epic"

    def test_urgency_level_property(self):
        """Test urgency_level computed from priority_score."""
        urgent = Suggestion(
            category=SuggestionCategory.TASK,
            title="Urgent",
            rationale="Test",
            priority_score=0.85,
        )
        assert urgent.urgency_level == "urgent"

        high = Suggestion(
            category=SuggestionCategory.TASK,
            title="High",
            rationale="Test",
            priority_score=0.7,
        )
        assert high.urgency_level == "high"

        medium = Suggestion(
            category=SuggestionCategory.TASK,
            title="Medium",
            rationale="Test",
            priority_score=0.5,
        )
        assert medium.urgency_level == "medium"

        low = Suggestion(
            category=SuggestionCategory.TASK,
            title="Low",
            rationale="Test",
            priority_score=0.3,
        )
        assert low.urgency_level == "low"

    def test_urgency_level_boundaries(self):
        """Test urgency level at boundary values."""
        # Test boundaries for each level
        assert Suggestion(
            category=SuggestionCategory.TASK,
            title="T",
            rationale="R",
            priority_score=0.8,
        ).urgency_level == "urgent"

        assert Suggestion(
            category=SuggestionCategory.TASK,
            title="T",
            rationale="R",
            priority_score=0.79,
        ).urgency_level == "high"

        assert Suggestion(
            category=SuggestionCategory.TASK,
            title="T",
            rationale="R",
            priority_score=0.6,
        ).urgency_level == "high"

        assert Suggestion(
            category=SuggestionCategory.TASK,
            title="T",
            rationale="R",
            priority_score=0.59,
        ).urgency_level == "medium"

        assert Suggestion(
            category=SuggestionCategory.TASK,
            title="T",
            rationale="R",
            priority_score=0.4,
        ).urgency_level == "medium"

        assert Suggestion(
            category=SuggestionCategory.TASK,
            title="T",
            rationale="R",
            priority_score=0.39,
        ).urgency_level == "low"

    def test_context_accepts_various_types(self):
        """Test context dict accepts strings, ints, floats, bools, None."""
        suggestion = Suggestion(
            category=SuggestionCategory.TASK,
            title="Test",
            rationale="Test",
            priority_score=0.5,
            context={
                "str_val": "text",
                "int_val": 42,
                "float_val": 3.14,
                "bool_val": True,
                "none_val": None,
            },
        )

        assert suggestion.context["str_val"] == "text"
        assert suggestion.context["int_val"] == 42
        assert suggestion.context["float_val"] == 3.14
        assert suggestion.context["bool_val"] is True
        assert suggestion.context["none_val"] is None

    def test_serialization(self):
        """Test JSON serialization."""
        suggestion = Suggestion(
            category=SuggestionCategory.REVIEW,
            title="Review task",
            description="Check completed work",
            rationale="Quality assurance",
            priority_score=0.75,
            action="cub ledger show task-1",
            source="ledger",
            context={"task_id": "task-1"},
        )

        data = suggestion.model_dump()

        assert data["category"] == "review"
        assert data["title"] == "Review task"
        assert data["description"] == "Check completed work"
        assert data["rationale"] == "Quality assurance"
        assert data["priority_score"] == 0.75
        assert data["action"] == "cub ledger show task-1"
        assert data["source"] == "ledger"
        assert data["context"]["task_id"] == "task-1"
        assert "created_at" in data

    def test_deserialization(self):
        """Test JSON deserialization."""
        data = {
            "category": "git",
            "title": "Commit changes",
            "rationale": "Save your work",
            "priority_score": 0.8,
            "source": "git",
        }

        suggestion = Suggestion.model_validate(data)

        assert suggestion.category == SuggestionCategory.GIT
        assert suggestion.title == "Commit changes"
        assert suggestion.rationale == "Save your work"
        assert suggestion.priority_score == 0.8
        assert suggestion.source == "git"


class TestProjectSnapshot:
    """Test ProjectSnapshot model."""

    def test_create_with_defaults(self):
        """Test creating ProjectSnapshot with default values."""
        snapshot = ProjectSnapshot()

        # Task state
        assert snapshot.total_tasks == 0
        assert snapshot.open_tasks == 0
        assert snapshot.in_progress_tasks == 0
        assert snapshot.closed_tasks == 0
        assert snapshot.ready_tasks == 0
        assert snapshot.blocked_tasks == 0

        # Git state
        assert snapshot.current_branch is None
        assert snapshot.has_uncommitted_changes is False
        assert snapshot.commits_since_main == 0
        assert snapshot.recent_commits == 0

        # Ledger state
        assert snapshot.tasks_in_ledger == 0
        assert snapshot.unreviewed_tasks == 0
        assert snapshot.failed_verifications == 0
        assert snapshot.total_cost_usd == 0.0

        # Milestone state
        assert snapshot.total_milestones == 0
        assert snapshot.active_milestones == 0
        assert snapshot.completed_milestones == 0
        assert snapshot.milestone_progress == 0.0

        # Temporal
        assert isinstance(snapshot.snapshot_time, datetime)

    def test_create_with_full_data(self):
        """Test creating ProjectSnapshot with complete data."""
        snapshot_time = datetime(2026, 1, 28, 15, 30, tzinfo=timezone.utc)
        snapshot = ProjectSnapshot(
            total_tasks=50,
            open_tasks=20,
            in_progress_tasks=5,
            closed_tasks=25,
            ready_tasks=10,
            blocked_tasks=5,
            current_branch="feature-x",
            has_uncommitted_changes=True,
            commits_since_main=3,
            recent_commits=5,
            tasks_in_ledger=25,
            unreviewed_tasks=3,
            failed_verifications=1,
            total_cost_usd=12.50,
            total_milestones=5,
            active_milestones=2,
            completed_milestones=3,
            milestone_progress=60.0,
            snapshot_time=snapshot_time,
        )

        assert snapshot.total_tasks == 50
        assert snapshot.open_tasks == 20
        assert snapshot.in_progress_tasks == 5
        assert snapshot.closed_tasks == 25
        assert snapshot.ready_tasks == 10
        assert snapshot.blocked_tasks == 5
        assert snapshot.current_branch == "feature-x"
        assert snapshot.has_uncommitted_changes is True
        assert snapshot.commits_since_main == 3
        assert snapshot.recent_commits == 5
        assert snapshot.tasks_in_ledger == 25
        assert snapshot.unreviewed_tasks == 3
        assert snapshot.failed_verifications == 1
        assert snapshot.total_cost_usd == 12.50
        assert snapshot.total_milestones == 5
        assert snapshot.active_milestones == 2
        assert snapshot.completed_milestones == 3
        assert snapshot.milestone_progress == 60.0
        assert snapshot.snapshot_time == snapshot_time

    def test_completion_percentage_property(self):
        """Test completion_percentage computed property."""
        snapshot = ProjectSnapshot(
            total_tasks=100,
            closed_tasks=40,
        )

        assert snapshot.completion_percentage == 40.0

    def test_completion_percentage_with_no_tasks(self):
        """Test completion_percentage when total_tasks is 0."""
        snapshot = ProjectSnapshot(
            total_tasks=0,
            closed_tasks=0,
        )

        assert snapshot.completion_percentage == 0.0

    def test_work_in_progress_property(self):
        """Test work_in_progress computed property."""
        # With in-progress tasks
        snapshot1 = ProjectSnapshot(in_progress_tasks=3)
        assert snapshot1.work_in_progress is True

        # With uncommitted changes
        snapshot2 = ProjectSnapshot(has_uncommitted_changes=True)
        assert snapshot2.work_in_progress is True

        # With both
        snapshot3 = ProjectSnapshot(
            in_progress_tasks=2,
            has_uncommitted_changes=True,
        )
        assert snapshot3.work_in_progress is True

        # With neither
        snapshot4 = ProjectSnapshot()
        assert snapshot4.work_in_progress is False

    def test_needs_attention_property(self):
        """Test needs_attention computed property."""
        # With failed verifications
        snapshot1 = ProjectSnapshot(failed_verifications=1)
        assert snapshot1.needs_attention is True

        # With unreviewed tasks
        snapshot2 = ProjectSnapshot(unreviewed_tasks=5)
        assert snapshot2.needs_attention is True

        # With blocked tasks
        snapshot3 = ProjectSnapshot(blocked_tasks=3)
        assert snapshot3.needs_attention is True

        # With multiple issues
        snapshot4 = ProjectSnapshot(
            failed_verifications=1,
            unreviewed_tasks=2,
            blocked_tasks=1,
        )
        assert snapshot4.needs_attention is True

        # With no issues
        snapshot5 = ProjectSnapshot()
        assert snapshot5.needs_attention is False

    def test_negative_values_rejected(self):
        """Test that negative values are rejected for count fields."""
        with pytest.raises(ValidationError):
            ProjectSnapshot(total_tasks=-1)

        with pytest.raises(ValidationError):
            ProjectSnapshot(commits_since_main=-1)

        with pytest.raises(ValidationError):
            ProjectSnapshot(total_cost_usd=-1.0)

    def test_milestone_progress_validation(self):
        """Test milestone_progress must be between 0 and 100."""
        # Valid values
        ProjectSnapshot(milestone_progress=0.0)
        ProjectSnapshot(milestone_progress=50.0)
        ProjectSnapshot(milestone_progress=100.0)

        # Invalid values
        with pytest.raises(ValidationError):
            ProjectSnapshot(milestone_progress=-0.1)

        with pytest.raises(ValidationError):
            ProjectSnapshot(milestone_progress=100.1)

    def test_serialization(self):
        """Test JSON serialization."""
        snapshot = ProjectSnapshot(
            total_tasks=10,
            closed_tasks=5,
            current_branch="main",
            total_cost_usd=7.25,
        )

        data = snapshot.model_dump()

        assert data["total_tasks"] == 10
        assert data["closed_tasks"] == 5
        assert data["current_branch"] == "main"
        assert data["total_cost_usd"] == 7.25
        assert "snapshot_time" in data

    def test_deserialization(self):
        """Test JSON deserialization."""
        data = {
            "total_tasks": 20,
            "open_tasks": 10,
            "closed_tasks": 10,
            "current_branch": "develop",
            "has_uncommitted_changes": True,
        }

        snapshot = ProjectSnapshot.model_validate(data)

        assert snapshot.total_tasks == 20
        assert snapshot.open_tasks == 10
        assert snapshot.closed_tasks == 10
        assert snapshot.current_branch == "develop"
        assert snapshot.has_uncommitted_changes is True
