"""
Tests for ID parser and validator.

These tests verify that the parser correctly converts string IDs back into
typed models, validates formats, and extracts parent relationships.
"""

import pytest

from cub.core.ids import (
    EpicId,
    PlanId,
    SpecId,
    StandaloneTaskId,
    TaskId,
    get_id_type,
    get_parent_id,
    parse_id,
    validate_id,
)


class TestValidateId:
    """Tests for validate_id function."""

    def test_validate_spec_id(self) -> None:
        """Test that spec IDs are validated correctly."""
        assert validate_id("cub-054") is True
        assert validate_id("cub-001") is True
        assert validate_id("cub-999") is True
        assert validate_id("myproject-123") is True

    def test_validate_plan_id(self) -> None:
        """Test that plan IDs are validated correctly."""
        assert validate_id("cub-054A") is True
        assert validate_id("cub-054a") is True
        assert validate_id("cub-0540") is True
        assert validate_id("cub-054Z") is True

    def test_validate_epic_id(self) -> None:
        """Test that epic IDs are validated correctly."""
        assert validate_id("cub-054A-0") is True
        assert validate_id("cub-054A-9") is True
        assert validate_id("cub-054A-a") is True
        assert validate_id("cub-054A-Z") is True

    def test_validate_task_id(self) -> None:
        """Test that task IDs are validated correctly."""
        assert validate_id("cub-054A-0.1") is True
        assert validate_id("cub-054A-0.10") is True
        assert validate_id("cub-054A-0.100") is True

    def test_validate_standalone_task_id(self) -> None:
        """Test that standalone task IDs are validated correctly."""
        assert validate_id("cub-s017") is True
        assert validate_id("cub-s001") is True
        assert validate_id("cub-s999") is True
        assert validate_id("myproject-s123") is True

    def test_validate_legacy_random_id(self) -> None:
        """Test that legacy random IDs are validated (backward compatibility)."""
        assert validate_id("cub-k7m") is True
        assert validate_id("cub-abc") is True
        assert validate_id("cub-x1y2z3") is True  # Legacy IDs can mix letters and digits
        assert validate_id("cub-XYZ") is False  # Uppercase not allowed in legacy

    def test_validate_invalid_formats(self) -> None:
        """Test that invalid formats are rejected."""
        assert validate_id("invalid") is False
        assert validate_id("cub-") is False
        assert validate_id("cub-054-") is False
        assert validate_id("cub-054A-") is False
        assert validate_id("cub-054!") is False
        assert validate_id("CUB-054") is False  # Uppercase project
        assert validate_id("") is False

    def test_validate_partial_matches_rejected(self) -> None:
        """Test that partial matches are rejected (must match entire string)."""
        # Note: Patterns with hyphens can be ambiguous
        # "cub-054-extra" is NOT valid (not a hierarchical or legacy format)
        # "prefix-cub-054" IS valid (project="prefix-cub", number=54)
        assert validate_id("cub-054!") is False
        assert validate_id("cub-054 ") is False  # Trailing space
        assert validate_id(" cub-054") is False  # Leading space
        assert validate_id("CUB-054") is False  # Uppercase project
        assert validate_id("cub-054-") is False  # Trailing dash


class TestGetIdType:
    """Tests for get_id_type function."""

    def test_get_spec_type(self) -> None:
        """Test detecting spec ID type."""
        assert get_id_type("cub-054") == "spec"
        assert get_id_type("cub-001") == "spec"
        assert get_id_type("myproject-123") == "spec"

    def test_get_plan_type(self) -> None:
        """Test detecting plan ID type."""
        assert get_id_type("cub-054A") == "plan"
        assert get_id_type("cub-054a") == "plan"
        assert get_id_type("cub-0540") == "plan"

    def test_get_epic_type(self) -> None:
        """Test detecting epic ID type."""
        assert get_id_type("cub-054A-0") == "epic"
        assert get_id_type("cub-054A-9") == "epic"
        assert get_id_type("cub-054A-a") == "epic"

    def test_get_task_type(self) -> None:
        """Test detecting task ID type."""
        assert get_id_type("cub-054A-0.1") == "task"
        assert get_id_type("cub-054A-0.10") == "task"
        assert get_id_type("cub-054A-0.100") == "task"

    def test_get_standalone_type(self) -> None:
        """Test detecting standalone task ID type."""
        assert get_id_type("cub-s017") == "standalone"
        assert get_id_type("cub-s001") == "standalone"
        assert get_id_type("myproject-s123") == "standalone"

    def test_get_type_legacy_random_id(self) -> None:
        """Test that legacy random IDs return None."""
        assert get_id_type("cub-k7m") is None
        assert get_id_type("cub-abc") is None

    def test_get_type_invalid_format(self) -> None:
        """Test that invalid formats return None."""
        assert get_id_type("invalid") is None
        assert get_id_type("cub-") is None
        assert get_id_type("") is None


class TestGetParentId:
    """Tests for get_parent_id function."""

    def test_task_parent_is_epic(self) -> None:
        """Test that task ID's parent is the epic ID."""
        assert get_parent_id("cub-054A-0.1") == "cub-054A-0"
        assert get_parent_id("cub-054A-0.10") == "cub-054A-0"
        assert get_parent_id("cub-054B-9.99") == "cub-054B-9"

    def test_epic_parent_is_plan(self) -> None:
        """Test that epic ID's parent is the plan ID."""
        assert get_parent_id("cub-054A-0") == "cub-054A"
        assert get_parent_id("cub-054B-9") == "cub-054B"
        assert get_parent_id("cub-054a-z") == "cub-054a"

    def test_plan_parent_is_spec(self) -> None:
        """Test that plan ID's parent is the spec ID."""
        assert get_parent_id("cub-054A") == "cub-054"
        assert get_parent_id("cub-054B") == "cub-054"
        assert get_parent_id("cub-054a") == "cub-054"

    def test_spec_has_no_parent(self) -> None:
        """Test that spec ID has no parent."""
        assert get_parent_id("cub-054") is None
        assert get_parent_id("cub-001") is None

    def test_standalone_has_no_parent(self) -> None:
        """Test that standalone task ID has no parent."""
        assert get_parent_id("cub-s017") is None
        assert get_parent_id("cub-s001") is None

    def test_invalid_id_has_no_parent(self) -> None:
        """Test that invalid IDs return None."""
        assert get_parent_id("invalid") is None
        assert get_parent_id("cub-k7m") is None  # Legacy random ID

    def test_parent_chain_consistency(self) -> None:
        """Test that parent extraction maintains consistency through the chain."""
        task_id = "cub-048A-0.2"
        epic_id = get_parent_id(task_id)
        assert epic_id == "cub-048A-0"

        plan_id = get_parent_id(epic_id)
        assert plan_id == "cub-048A"

        spec_id = get_parent_id(plan_id)
        assert spec_id == "cub-048"

        assert get_parent_id(spec_id) is None


class TestParseId:
    """Tests for parse_id function."""

    def test_parse_spec_id(self) -> None:
        """Test parsing spec ID."""
        result = parse_id("cub-054")
        assert isinstance(result, SpecId)
        assert result.project == "cub"
        assert result.number == 54
        assert str(result) == "cub-054"

    def test_parse_spec_id_different_padding(self) -> None:
        """Test parsing spec IDs with different number padding."""
        result1 = parse_id("cub-001")
        assert isinstance(result1, SpecId)
        assert result1.number == 1
        assert str(result1) == "cub-001"

        result2 = parse_id("cub-099")
        assert isinstance(result2, SpecId)
        assert result2.number == 99
        assert str(result2) == "cub-099"

        # Note: IDs ending in multiple digits are ambiguous
        # (could be spec or plan with digit letter)
        # The parser prefers plan interpretation
        result3 = parse_id("cub-1000")
        assert isinstance(result3, PlanId)
        assert result3.spec.number == 100
        assert result3.letter == "0"

    def test_parse_plan_id(self) -> None:
        """Test parsing plan ID with full parent chain."""
        result = parse_id("cub-054A")
        assert isinstance(result, PlanId)
        assert result.letter == "A"
        assert str(result) == "cub-054A"

        # Verify parent chain
        assert isinstance(result.spec, SpecId)
        assert result.spec.project == "cub"
        assert result.spec.number == 54
        assert str(result.spec) == "cub-054"

    def test_parse_epic_id(self) -> None:
        """Test parsing epic ID with full parent chain."""
        result = parse_id("cub-054A-0")
        assert isinstance(result, EpicId)
        assert result.char == "0"
        assert str(result) == "cub-054A-0"

        # Verify parent chain
        assert isinstance(result.plan, PlanId)
        assert str(result.plan) == "cub-054A"
        assert isinstance(result.plan.spec, SpecId)
        assert str(result.plan.spec) == "cub-054"

    def test_parse_task_id(self) -> None:
        """Test parsing task ID with full parent chain."""
        result = parse_id("cub-054A-0.1")
        assert isinstance(result, TaskId)
        assert result.number == 1
        assert str(result) == "cub-054A-0.1"

        # Verify full parent chain
        assert isinstance(result.epic, EpicId)
        assert str(result.epic) == "cub-054A-0"
        assert isinstance(result.epic.plan, PlanId)
        assert str(result.epic.plan) == "cub-054A"
        assert isinstance(result.epic.plan.spec, SpecId)
        assert str(result.epic.plan.spec) == "cub-054"

    def test_parse_task_id_multi_digit(self) -> None:
        """Test parsing task IDs with multi-digit numbers."""
        result10 = parse_id("cub-054A-0.10")
        assert isinstance(result10, TaskId)
        assert result10.number == 10

        result100 = parse_id("cub-054A-0.100")
        assert isinstance(result100, TaskId)
        assert result100.number == 100

    def test_parse_standalone_task_id(self) -> None:
        """Test parsing standalone task ID."""
        result = parse_id("cub-s017")
        assert isinstance(result, StandaloneTaskId)
        assert result.project == "cub"
        assert result.number == 17
        assert str(result) == "cub-s017"

    def test_parse_different_projects(self) -> None:
        """Test parsing IDs with different project names."""
        result1 = parse_id("myproject-054")
        assert isinstance(result1, SpecId)
        assert result1.project == "myproject"

        result2 = parse_id("my-proj-123A")
        assert isinstance(result2, PlanId)
        assert result2.spec.project == "my-proj"

    def test_parse_all_plan_letter_types(self) -> None:
        """Test parsing plan IDs with all valid letter types."""
        # Uppercase
        result_upper = parse_id("cub-054Z")
        assert isinstance(result_upper, PlanId)
        assert result_upper.letter == "Z"

        # Lowercase
        result_lower = parse_id("cub-054z")
        assert isinstance(result_lower, PlanId)
        assert result_lower.letter == "z"

        # Digit
        result_digit = parse_id("cub-0549")
        assert isinstance(result_digit, PlanId)
        assert result_digit.letter == "9"

    def test_parse_all_epic_char_types(self) -> None:
        """Test parsing epic IDs with all valid char types."""
        # Digit
        result_digit = parse_id("cub-054A-9")
        assert isinstance(result_digit, EpicId)
        assert result_digit.char == "9"

        # Lowercase
        result_lower = parse_id("cub-054A-z")
        assert isinstance(result_lower, EpicId)
        assert result_lower.char == "z"

        # Uppercase
        result_upper = parse_id("cub-054A-Z")
        assert isinstance(result_upper, EpicId)
        assert result_upper.char == "Z"

    def test_parse_legacy_random_id_raises(self) -> None:
        """Test that parsing legacy random IDs raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_id("cub-k7m")
        assert "Legacy random ID format detected" in str(exc_info.value)
        assert "cub-k7m" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            parse_id("cub-abc")
        assert "Legacy random ID format detected" in str(exc_info.value)

    def test_parse_invalid_format_raises(self) -> None:
        """Test that parsing invalid formats raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_id("invalid")
        assert "Invalid ID format" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            parse_id("cub-")
        assert "Invalid ID format" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            parse_id("")
        assert "Invalid ID format" in str(exc_info.value)

    def test_parse_round_trip_consistency(self) -> None:
        """Test that parsing and stringifying produces the same ID."""
        test_ids = [
            "cub-054",
            "cub-054A",
            "cub-054A-0",
            "cub-054A-0.1",
            "cub-s017",
            "myproject-123",
            "myproject-123B-9.99",
        ]

        for id_str in test_ids:
            parsed = parse_id(id_str)
            assert str(parsed) == id_str


class TestAcceptanceCriteria:
    """Tests for specific acceptance criteria from task description."""

    def test_parse_spec_id_acceptance(self) -> None:
        """AC: parse_id("cub-054") returns SpecId(project="cub", number=54)"""
        result = parse_id("cub-054")
        assert isinstance(result, SpecId)
        assert result.project == "cub"
        assert result.number == 54

    def test_parse_task_id_with_parent_chain_acceptance(self) -> None:
        """AC: parse_id("cub-054A-0.1") returns fully nested TaskId with parent chain"""
        result = parse_id("cub-054A-0.1")
        assert isinstance(result, TaskId)
        assert result.number == 1

        # Verify full parent chain exists
        assert isinstance(result.epic, EpicId)
        assert result.epic.char == "0"

        assert isinstance(result.epic.plan, PlanId)
        assert result.epic.plan.letter == "A"

        assert isinstance(result.epic.plan.spec, SpecId)
        assert result.epic.plan.spec.project == "cub"
        assert result.epic.plan.spec.number == 54

    def test_get_parent_id_acceptance(self) -> None:
        """AC: get_parent_id("cub-054A-0.1") returns "cub-054A-0" """
        result = get_parent_id("cub-054A-0.1")
        assert result == "cub-054A-0"

    def test_legacy_random_id_detection_acceptance(self) -> None:
        """AC: Old random IDs like cub-k7m are detected but not parsed"""
        # validate_id should return True (detected as valid format)
        assert validate_id("cub-k7m") is True

        # get_id_type should return None (not a hierarchical type)
        assert get_id_type("cub-k7m") is None

        # parse_id should raise ValueError (cannot parse)
        with pytest.raises(ValueError) as exc_info:
            parse_id("cub-k7m")
        assert "Legacy random ID" in str(exc_info.value)

    def test_invalid_format_error_message_acceptance(self) -> None:
        """AC: Invalid formats raise ValueError with descriptive message"""
        with pytest.raises(ValueError) as exc_info:
            parse_id("invalid-format!")
        assert "Invalid ID format" in str(exc_info.value)
        assert "invalid-format!" in str(exc_info.value)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_padded_numbers_parsed_correctly(self) -> None:
        """Test that zero-padded numbers are parsed to correct integer values."""
        spec = parse_id("cub-001")
        assert isinstance(spec, SpecId)
        assert spec.number == 1  # Not "001"

        standalone = parse_id("cub-s007")
        assert isinstance(standalone, StandaloneTaskId)
        assert standalone.number == 7  # Not "007"

    def test_project_names_with_hyphens(self) -> None:
        """Test that project names with hyphens work correctly."""
        result = parse_id("my-project-name-054")
        assert isinstance(result, SpecId)
        assert result.project == "my-project-name"
        assert result.number == 54

    def test_case_sensitivity(self) -> None:
        """Test that plan letters and epic chars are case-sensitive."""
        plan_upper = parse_id("cub-054A")
        plan_lower = parse_id("cub-054a")

        assert isinstance(plan_upper, PlanId)
        assert isinstance(plan_lower, PlanId)
        assert plan_upper.letter == "A"
        assert plan_lower.letter == "a"
        assert plan_upper.letter != plan_lower.letter

    def test_large_numbers(self) -> None:
        """Test that large numbers work correctly."""
        # Note: IDs ending in digits are ambiguous due to plan letters allowing 0-9
        # Parser prefers plan interpretation: cub-9999 → plan(999, '9')
        plan = parse_id("cub-9999")
        assert isinstance(plan, PlanId)
        assert plan.spec.number == 999
        assert plan.letter == "9"

        # Task numbers can be large without ambiguity
        task = parse_id("cub-054A-0.9999")
        assert isinstance(task, TaskId)
        assert task.number == 9999

    def test_whitespace_not_allowed(self) -> None:
        """Test that IDs with whitespace are invalid."""
        assert validate_id("cub-054 ") is False
        assert validate_id(" cub-054") is False
        assert validate_id("cub -054") is False
        assert validate_id("cub- 054") is False

        with pytest.raises(ValueError):
            parse_id("cub-054 ")
