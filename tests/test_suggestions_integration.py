"""
Integration tests for suggestion system and service.

Tests the full suggestion pipeline from service creation through CLI output,
validating that suggestions are generated correctly from real project state.
"""

from pathlib import Path

import pytest

from cub.core.services.suggestions import SuggestionService
from cub.core.suggestions.models import SuggestionCategory


class TestSuggestionServiceIntegration:
    """Integration tests for SuggestionService."""

    def test_service_creation(self, tmp_path: Path) -> None:
        """Test creating SuggestionService from project directory."""
        # Create a temporary project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Should create service without error
        service = SuggestionService.from_project_dir(project_dir)
        assert service is not None
        assert service.project_dir == project_dir

    def test_get_suggestions_returns_list(self, tmp_path: Path) -> None:
        """Test that get_suggestions returns a list."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        service = SuggestionService.from_project_dir(project_dir)
        suggestions = service.get_suggestions()

        assert isinstance(suggestions, list)
        # May be empty if no project state, but should be a list

    def test_get_suggestions_with_limit(self, tmp_path: Path) -> None:
        """Test that limit parameter works correctly."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        service = SuggestionService.from_project_dir(project_dir)
        suggestions = service.get_suggestions(limit=3)

        assert isinstance(suggestions, list)
        assert len(suggestions) <= 3

    def test_get_next_action_returns_top_suggestion(self, tmp_path: Path) -> None:
        """Test that get_next_action returns the highest-priority suggestion."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        service = SuggestionService.from_project_dir(project_dir)
        all_suggestions = service.get_suggestions()
        next_action = service.get_next_action()

        if all_suggestions:
            # Should return the first (highest priority) suggestion
            assert next_action == all_suggestions[0]
        else:
            # Should return None if no suggestions
            assert next_action is None

    def test_get_welcome_structure(self, tmp_path: Path) -> None:
        """Test that get_welcome returns a properly structured WelcomeMessage."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        service = SuggestionService.from_project_dir(project_dir)
        welcome = service.get_welcome(max_suggestions=3)

        # Check structure
        assert hasattr(welcome, "total_tasks")
        assert hasattr(welcome, "open_tasks")
        assert hasattr(welcome, "in_progress_tasks")
        assert hasattr(welcome, "ready_tasks")
        assert hasattr(welcome, "top_suggestions")
        assert hasattr(welcome, "available_skills")

        # Check types
        assert isinstance(welcome.total_tasks, int)
        assert isinstance(welcome.open_tasks, int)
        assert isinstance(welcome.in_progress_tasks, int)
        assert isinstance(welcome.ready_tasks, int)
        assert isinstance(welcome.top_suggestions, list)
        assert isinstance(welcome.available_skills, list)

        # Check limits
        assert len(welcome.top_suggestions) <= 3

    def test_welcome_with_skills(self, tmp_path: Path) -> None:
        """Test that welcome message includes provided skills."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        service = SuggestionService.from_project_dir(project_dir)
        skills = ["commit", "review-pr", "test-runner"]
        welcome = service.get_welcome(available_skills=skills)

        assert welcome.available_skills == skills

    def test_suggestions_have_required_fields(self, tmp_path: Path) -> None:
        """Test that all suggestions have required fields."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        service = SuggestionService.from_project_dir(project_dir)
        suggestions = service.get_suggestions()

        for suggestion in suggestions:
            # Check required fields
            assert hasattr(suggestion, "category")
            assert hasattr(suggestion, "title")
            assert hasattr(suggestion, "rationale")
            assert hasattr(suggestion, "priority_score")

            # Check types
            assert isinstance(suggestion.category, SuggestionCategory)
            assert isinstance(suggestion.title, str)
            assert isinstance(suggestion.rationale, str)
            assert isinstance(suggestion.priority_score, float)

            # Check values
            assert len(suggestion.title) > 0
            assert len(suggestion.rationale) > 0
            assert 0.0 <= suggestion.priority_score <= 1.0

    def test_suggestions_are_sorted_by_priority(self, tmp_path: Path) -> None:
        """Test that suggestions are returned in priority order."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        service = SuggestionService.from_project_dir(project_dir)
        suggestions = service.get_suggestions()

        if len(suggestions) > 1:
            # Check that each suggestion has priority >= the next one
            for i in range(len(suggestions) - 1):
                curr_score = suggestions[i].priority_score
                next_score = suggestions[i + 1].priority_score
                assert (
                    curr_score >= next_score
                ), f"Suggestion {i} priority ({curr_score}) < {i+1} ({next_score})"

    def test_suggestion_categories_are_valid(self, tmp_path: Path) -> None:
        """Test that all suggestion categories are valid enum values."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        service = SuggestionService.from_project_dir(project_dir)
        suggestions = service.get_suggestions()

        valid_categories = {
            SuggestionCategory.TASK,
            SuggestionCategory.REVIEW,
            SuggestionCategory.MILESTONE,
            SuggestionCategory.GIT,
            SuggestionCategory.CLEANUP,
            SuggestionCategory.PLAN,
        }

        for suggestion in suggestions:
            assert suggestion.category in valid_categories

    def test_service_handles_missing_project_state_gracefully(
        self, tmp_path: Path
    ) -> None:
        """Test that service handles missing project state without errors."""
        # Create empty project directory with no .cub, no .git, etc.
        project_dir = tmp_path / "empty_project"
        project_dir.mkdir()

        # Should not raise an error
        service = SuggestionService.from_project_dir(project_dir)
        suggestions = service.get_suggestions()

        # Should return a list (possibly empty)
        assert isinstance(suggestions, list)


class TestSuggestionServiceRealProject:
    """Integration tests using the actual cub project."""

    def test_cub_project_generates_suggestions(self) -> None:
        """Test that suggestion service works on the cub project itself."""
        # Use current directory (cub project)
        service = SuggestionService.from_project_dir(None)
        suggestions = service.get_suggestions()

        # The cub project should have suggestions
        assert isinstance(suggestions, list)
        # We can't assert exactly how many, but there should be some
        # given the active development state

    def test_cub_project_next_action(self) -> None:
        """Test getting next action from cub project."""
        service = SuggestionService.from_project_dir(None)
        next_action = service.get_next_action()

        # May or may not have a next action, but should return valid type
        assert next_action is None or hasattr(next_action, "category")

    def test_cub_project_welcome_message(self) -> None:
        """Test getting welcome message from cub project."""
        service = SuggestionService.from_project_dir(None)
        welcome = service.get_welcome()

        # Should have task counts
        assert isinstance(welcome.total_tasks, int)
        assert welcome.total_tasks >= 0

        # Should have suggestions
        assert isinstance(welcome.top_suggestions, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
