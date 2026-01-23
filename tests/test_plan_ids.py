"""
Unit tests for plan ID generation utilities.

Tests the beads-compatible ID generation for epics, tasks, and subtasks.
"""

import pytest

from cub.core.plan.ids import (
    EPIC_SUFFIX_LENGTH,
    ID_CHARS,
    generate_epic_id,
    generate_subtask_id,
    generate_task_id,
    get_parent_id,
    is_valid_epic_id,
    is_valid_subtask_id,
    is_valid_task_id,
    parse_id,
)

# ==============================================================================
# generate_epic_id Tests
# ==============================================================================


class TestGenerateEpicId:
    """Test epic ID generation."""

    def test_generates_valid_format(self):
        """Test that generated epic IDs have correct format."""
        epic_id = generate_epic_id("cub")
        assert epic_id.startswith("cub-")
        assert len(epic_id) == 3 + 1 + EPIC_SUFFIX_LENGTH  # "cub" + "-" + suffix
        assert is_valid_epic_id(epic_id)

    def test_suffix_is_alphanumeric(self):
        """Test that suffix contains only valid characters."""
        for _ in range(10):
            epic_id = generate_epic_id("proj")
            suffix = epic_id.split("-")[-1]
            assert len(suffix) == EPIC_SUFFIX_LENGTH
            assert all(c in ID_CHARS for c in suffix)

    def test_different_projects(self):
        """Test ID generation with different project names."""
        epic1 = generate_epic_id("myapp")
        epic2 = generate_epic_id("another-project")

        assert epic1.startswith("myapp-")
        assert epic2.startswith("another-project-")

    def test_generates_unique_ids(self):
        """Test that multiple calls generate different IDs (probabilistic)."""
        ids = {generate_epic_id("cub") for _ in range(100)}
        # With 36^3 = 46656 possibilities, 100 calls should rarely collide
        assert len(ids) >= 95  # Allow for rare collisions

    def test_avoids_existing_ids(self):
        """Test collision avoidance with existing_ids."""
        existing = {"cub-abc", "cub-def", "cub-xyz"}
        new_id = generate_epic_id("cub", existing)
        assert new_id not in existing
        assert is_valid_epic_id(new_id)

    def test_empty_existing_ids_works(self):
        """Test that empty existing_ids set works."""
        new_id = generate_epic_id("cub", set())
        assert is_valid_epic_id(new_id)

    def test_none_existing_ids_works(self):
        """Test that None existing_ids works."""
        new_id = generate_epic_id("cub", None)
        assert is_valid_epic_id(new_id)

    def test_empty_project_raises(self):
        """Test that empty project raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            generate_epic_id("")

    def test_invalid_project_format_raises(self):
        """Test that invalid project format raises ValueError."""
        # Must start with letter
        with pytest.raises(ValueError, match="Invalid project identifier"):
            generate_epic_id("123abc")

        # No uppercase
        with pytest.raises(ValueError, match="Invalid project identifier"):
            generate_epic_id("MyApp")

        # No special characters (except hyphen)
        with pytest.raises(ValueError, match="Invalid project identifier"):
            generate_epic_id("my_app")

    def test_project_with_hyphen_valid(self):
        """Test that project with hyphen is valid."""
        epic_id = generate_epic_id("my-app")
        assert epic_id.startswith("my-app-")
        assert is_valid_epic_id(epic_id)

    def test_project_with_numbers_valid(self):
        """Test that project with numbers is valid."""
        epic_id = generate_epic_id("app2")
        assert epic_id.startswith("app2-")
        assert is_valid_epic_id(epic_id)


class TestGenerateEpicIdCollisionExhaustion:
    """Test epic ID generation collision exhaustion."""

    def test_raises_on_exhaustion(self):
        """Test RuntimeError when all IDs are taken."""
        # Create a set with all possible 3-char suffixes for a project
        # This is 36^3 = 46656 IDs, which is too many to test directly
        # Instead, we mock by testing with a heavily populated set

        # Create a mock scenario where we force exhaustion
        # by making all generated IDs collide

        # In practice, we can't test true exhaustion without mocking
        # This test verifies the mechanism exists
        # The actual exhaustion would require 46656+ attempts
        with pytest.raises(RuntimeError, match="Failed to generate unique epic ID"):
            # Create a set that rejects everything
            class AlwaysRejects:
                def __contains__(self, item: str) -> bool:
                    return True

            generate_epic_id("cub", AlwaysRejects())  # type: ignore[arg-type]


# ==============================================================================
# generate_task_id Tests
# ==============================================================================


class TestGenerateTaskId:
    """Test task ID generation."""

    def test_basic_task_id(self):
        """Test basic task ID generation."""
        task_id = generate_task_id("cub-k7m", 1)
        assert task_id == "cub-k7m.1"

    def test_various_task_numbers(self):
        """Test task ID with various numbers."""
        assert generate_task_id("cub-abc", 1) == "cub-abc.1"
        assert generate_task_id("cub-abc", 42) == "cub-abc.42"
        assert generate_task_id("cub-abc", 999) == "cub-abc.999"

    def test_different_epic_ids(self):
        """Test task ID with different epic IDs."""
        assert generate_task_id("myapp-xyz", 1) == "myapp-xyz.1"
        assert generate_task_id("another-proj-a2b", 5) == "another-proj-a2b.5"

    def test_empty_epic_id_raises(self):
        """Test that empty epic ID raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            generate_task_id("", 1)

    def test_invalid_epic_id_raises(self):
        """Test that invalid epic ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid epic ID"):
            generate_task_id("invalid", 1)

        with pytest.raises(ValueError, match="Invalid epic ID"):
            generate_task_id("cub-k7m.1", 1)  # task ID, not epic ID

    def test_zero_task_number_raises(self):
        """Test that zero task number raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            generate_task_id("cub-k7m", 0)

    def test_negative_task_number_raises(self):
        """Test that negative task number raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            generate_task_id("cub-k7m", -1)


# ==============================================================================
# generate_subtask_id Tests
# ==============================================================================


class TestGenerateSubtaskId:
    """Test subtask ID generation."""

    def test_basic_subtask_id(self):
        """Test basic subtask ID generation."""
        subtask_id = generate_subtask_id("cub-k7m.1", 1)
        assert subtask_id == "cub-k7m.1.1"

    def test_various_subtask_numbers(self):
        """Test subtask ID with various numbers."""
        assert generate_subtask_id("cub-abc.5", 1) == "cub-abc.5.1"
        assert generate_subtask_id("cub-abc.5", 3) == "cub-abc.5.3"
        assert generate_subtask_id("cub-abc.5", 99) == "cub-abc.5.99"

    def test_different_task_ids(self):
        """Test subtask ID with different task IDs."""
        assert generate_subtask_id("myapp-xyz.10", 2) == "myapp-xyz.10.2"
        assert generate_subtask_id("proj-a2b.1", 1) == "proj-a2b.1.1"

    def test_empty_task_id_raises(self):
        """Test that empty task ID raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            generate_subtask_id("", 1)

    def test_invalid_task_id_raises(self):
        """Test that invalid task ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid task ID"):
            generate_subtask_id("cub-k7m", 1)  # epic ID, not task ID

        with pytest.raises(ValueError, match="Invalid task ID"):
            generate_subtask_id("cub-k7m.1.1", 1)  # subtask ID, not task ID

    def test_zero_subtask_number_raises(self):
        """Test that zero subtask number raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            generate_subtask_id("cub-k7m.1", 0)

    def test_negative_subtask_number_raises(self):
        """Test that negative subtask number raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            generate_subtask_id("cub-k7m.1", -1)


# ==============================================================================
# is_valid_* Validation Tests
# ==============================================================================


class TestIsValidEpicId:
    """Test epic ID validation."""

    def test_valid_epic_ids(self):
        """Test valid epic ID formats."""
        assert is_valid_epic_id("cub-k7m") is True
        assert is_valid_epic_id("myapp-abc") is True
        assert is_valid_epic_id("proj-123") is True
        assert is_valid_epic_id("a-xyz") is True
        assert is_valid_epic_id("my-long-project-a2b") is True

    def test_invalid_epic_ids(self):
        """Test invalid epic ID formats."""
        assert is_valid_epic_id("") is False
        assert is_valid_epic_id("cub") is False  # No suffix
        assert is_valid_epic_id("cub-") is False  # Empty suffix
        assert is_valid_epic_id("cub-ab") is False  # Too short
        assert is_valid_epic_id("cub-abcd") is False  # Too long
        assert is_valid_epic_id("cub-k7m.1") is False  # Task ID
        assert is_valid_epic_id("CUB-k7m") is False  # Uppercase
        assert is_valid_epic_id("123-abc") is False  # Starts with number


class TestIsValidTaskId:
    """Test task ID validation."""

    def test_valid_task_ids(self):
        """Test valid task ID formats."""
        assert is_valid_task_id("cub-k7m.1") is True
        assert is_valid_task_id("myapp-abc.42") is True
        assert is_valid_task_id("proj-123.999") is True

    def test_invalid_task_ids(self):
        """Test invalid task ID formats."""
        assert is_valid_task_id("") is False
        assert is_valid_task_id("cub-k7m") is False  # Epic ID
        assert is_valid_task_id("cub-k7m.1.1") is False  # Subtask ID
        assert is_valid_task_id("cub-k7m.") is False  # Missing number
        assert is_valid_task_id("cub-k7m.abc") is False  # Non-numeric
        assert is_valid_task_id("cub-k7m.0") is True  # Zero is syntactically valid


class TestIsValidSubtaskId:
    """Test subtask ID validation."""

    def test_valid_subtask_ids(self):
        """Test valid subtask ID formats."""
        assert is_valid_subtask_id("cub-k7m.1.1") is True
        assert is_valid_subtask_id("myapp-abc.42.3") is True
        assert is_valid_subtask_id("proj-123.999.99") is True

    def test_invalid_subtask_ids(self):
        """Test invalid subtask ID formats."""
        assert is_valid_subtask_id("") is False
        assert is_valid_subtask_id("cub-k7m") is False  # Epic ID
        assert is_valid_subtask_id("cub-k7m.1") is False  # Task ID
        assert is_valid_subtask_id("cub-k7m.1.1.1") is False  # Too deep
        assert is_valid_subtask_id("cub-k7m.1.") is False  # Missing number


# ==============================================================================
# parse_id Tests
# ==============================================================================


class TestParseId:
    """Test ID parsing."""

    def test_parse_epic_id(self):
        """Test parsing epic ID."""
        epic, numbers = parse_id("cub-k7m")
        assert epic == "cub-k7m"
        assert numbers == []

    def test_parse_task_id(self):
        """Test parsing task ID."""
        epic, numbers = parse_id("cub-k7m.1")
        assert epic == "cub-k7m"
        assert numbers == [1]

        epic, numbers = parse_id("myapp-abc.42")
        assert epic == "myapp-abc"
        assert numbers == [42]

    def test_parse_subtask_id(self):
        """Test parsing subtask ID."""
        epic, numbers = parse_id("cub-k7m.1.3")
        assert epic == "cub-k7m"
        assert numbers == [1, 3]

        epic, numbers = parse_id("proj-xyz.10.99")
        assert epic == "proj-xyz"
        assert numbers == [10, 99]

    def test_empty_id_raises(self):
        """Test that empty ID raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_id("")

    def test_invalid_epic_component_raises(self):
        """Test that invalid epic component raises ValueError."""
        with pytest.raises(ValueError, match="Invalid epic ID"):
            parse_id("invalid")

        with pytest.raises(ValueError, match="Invalid epic ID"):
            parse_id("123-abc")

    def test_invalid_number_component_raises(self):
        """Test that invalid number component raises ValueError."""
        with pytest.raises(ValueError, match="Invalid ID component"):
            parse_id("cub-k7m.abc")

    def test_negative_number_raises(self):
        """Test that negative number raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_id("cub-k7m.-1")

    def test_zero_number_raises(self):
        """Test that zero number raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_id("cub-k7m.0")

    def test_too_many_levels_raises(self):
        """Test that too many levels raises ValueError."""
        with pytest.raises(ValueError, match="too many levels"):
            parse_id("cub-k7m.1.1.1")


# ==============================================================================
# get_parent_id Tests
# ==============================================================================


class TestGetParentId:
    """Test parent ID retrieval."""

    def test_epic_has_no_parent(self):
        """Test that epic ID has no parent."""
        assert get_parent_id("cub-k7m") is None

    def test_task_parent_is_epic(self):
        """Test that task's parent is the epic."""
        assert get_parent_id("cub-k7m.1") == "cub-k7m"
        assert get_parent_id("myapp-abc.42") == "myapp-abc"

    def test_subtask_parent_is_task(self):
        """Test that subtask's parent is the task."""
        assert get_parent_id("cub-k7m.1.1") == "cub-k7m.1"
        assert get_parent_id("proj-xyz.10.5") == "proj-xyz.10"

    def test_invalid_id_raises(self):
        """Test that invalid ID raises ValueError."""
        with pytest.raises(ValueError):
            get_parent_id("")

        with pytest.raises(ValueError):
            get_parent_id("invalid")


# ==============================================================================
# Integration / Round-Trip Tests
# ==============================================================================


class TestIdHierarchy:
    """Test ID generation hierarchy integration."""

    def test_full_hierarchy(self):
        """Test generating a full epic -> task -> subtask hierarchy."""
        # Generate epic
        epic_id = generate_epic_id("cub")
        assert is_valid_epic_id(epic_id)

        # Generate tasks
        task1 = generate_task_id(epic_id, 1)
        task2 = generate_task_id(epic_id, 2)
        assert is_valid_task_id(task1)
        assert is_valid_task_id(task2)
        assert get_parent_id(task1) == epic_id
        assert get_parent_id(task2) == epic_id

        # Generate subtasks
        subtask1_1 = generate_subtask_id(task1, 1)
        subtask1_2 = generate_subtask_id(task1, 2)
        subtask2_1 = generate_subtask_id(task2, 1)
        assert is_valid_subtask_id(subtask1_1)
        assert is_valid_subtask_id(subtask1_2)
        assert is_valid_subtask_id(subtask2_1)
        assert get_parent_id(subtask1_1) == task1
        assert get_parent_id(subtask1_2) == task1
        assert get_parent_id(subtask2_1) == task2

    def test_parse_round_trip(self):
        """Test that parse_id correctly parses all levels."""
        epic_id = generate_epic_id("myproject")
        task_id = generate_task_id(epic_id, 5)
        subtask_id = generate_subtask_id(task_id, 3)

        # Parse and verify
        parsed_epic, nums = parse_id(epic_id)
        assert parsed_epic == epic_id
        assert nums == []

        parsed_epic, nums = parse_id(task_id)
        assert parsed_epic == epic_id
        assert nums == [5]

        parsed_epic, nums = parse_id(subtask_id)
        assert parsed_epic == epic_id
        assert nums == [5, 3]

    def test_id_uniqueness_across_epics(self):
        """Test that multiple epics can have same-numbered tasks."""
        epic1 = generate_epic_id("proj", set())
        epic2 = generate_epic_id("proj", {epic1})

        # Both epics can have task 1
        task1_1 = generate_task_id(epic1, 1)
        task2_1 = generate_task_id(epic2, 1)

        assert task1_1 != task2_1
        assert is_valid_task_id(task1_1)
        assert is_valid_task_id(task2_1)
