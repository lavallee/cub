"""
Tests for ID generator with counter integration.

This module tests the generator functions that create new IDs by combining
counter allocation with the ID models.
"""

from unittest.mock import Mock

import pytest

from cub.core.ids import (
    EpicId,
    PlanId,
    SpecId,
    StandaloneTaskId,
    TaskId,
    generate_epic_id,
    generate_plan_id,
    generate_spec_id,
    generate_standalone_id,
    generate_task_id,
    next_epic_char,
    next_plan_letter,
)


class TestGenerateSpecId:
    """Tests for generate_spec_id function."""

    def test_generate_spec_id_allocates_counter(self, monkeypatch):
        """Should allocate counter and return SpecId."""
        # Mock allocate_spec_number to return 54
        mock_allocate = Mock(return_value=54)
        monkeypatch.setattr(
            "cub.core.ids.generator.allocate_spec_number", mock_allocate
        )

        sync_service = Mock()
        result = generate_spec_id("cub", sync_service)

        assert isinstance(result, SpecId)
        assert result.project == "cub"
        assert result.number == 54
        assert str(result) == "cub-054"
        mock_allocate.assert_called_once_with(sync_service)

    def test_generate_spec_id_different_project(self, monkeypatch):
        """Should work with different project names."""
        mock_allocate = Mock(return_value=123)
        monkeypatch.setattr(
            "cub.core.ids.generator.allocate_spec_number", mock_allocate
        )

        sync_service = Mock()
        result = generate_spec_id("myproject", sync_service)

        assert result.project == "myproject"
        assert result.number == 123
        assert str(result) == "myproject-123"


class TestGeneratePlanId:
    """Tests for generate_plan_id function."""

    def test_generate_plan_id_uppercase_letter(self):
        """Should create plan ID with uppercase letter."""
        spec = SpecId(project="cub", number=54)
        result = generate_plan_id(spec, "A")

        assert isinstance(result, PlanId)
        assert result.spec == spec
        assert result.letter == "A"
        assert str(result) == "cub-054A"

    def test_generate_plan_id_lowercase_letter(self):
        """Should create plan ID with lowercase letter."""
        spec = SpecId(project="cub", number=54)
        result = generate_plan_id(spec, "a")

        assert result.letter == "a"
        assert str(result) == "cub-054a"

    def test_generate_plan_id_digit_letter(self):
        """Should create plan ID with digit letter."""
        spec = SpecId(project="cub", number=54)
        result = generate_plan_id(spec, "5")

        assert result.letter == "5"
        assert str(result) == "cub-0545"

    def test_generate_plan_id_invalid_letter(self):
        """Should reject invalid letter."""
        spec = SpecId(project="cub", number=54)
        with pytest.raises(ValueError, match="Plan letter must be a single character"):
            generate_plan_id(spec, "-")


class TestGenerateEpicId:
    """Tests for generate_epic_id function."""

    def test_generate_epic_id_digit_char(self):
        """Should create epic ID with digit char."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        result = generate_epic_id(plan, "0")

        assert isinstance(result, EpicId)
        assert result.plan == plan
        assert result.char == "0"
        assert str(result) == "cub-054A-0"

    def test_generate_epic_id_lowercase_char(self):
        """Should create epic ID with lowercase char."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        result = generate_epic_id(plan, "a")

        assert result.char == "a"
        assert str(result) == "cub-054A-a"

    def test_generate_epic_id_uppercase_char(self):
        """Should create epic ID with uppercase char."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        result = generate_epic_id(plan, "Z")

        assert result.char == "Z"
        assert str(result) == "cub-054A-Z"

    def test_generate_epic_id_invalid_char(self):
        """Should reject invalid char."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        with pytest.raises(ValueError, match="Epic char must be a single character"):
            generate_epic_id(plan, "-")


class TestGenerateTaskId:
    """Tests for generate_task_id function."""

    def test_generate_task_id_first_task(self):
        """Should create task ID with number 1."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        result = generate_task_id(epic, 1)

        assert isinstance(result, TaskId)
        assert result.epic == epic
        assert result.number == 1
        assert str(result) == "cub-054A-0.1"

    def test_generate_task_id_multi_digit_number(self):
        """Should create task ID with multi-digit number."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        result = generate_task_id(epic, 42)

        assert result.number == 42
        assert str(result) == "cub-054A-0.42"

    def test_generate_task_id_zero_rejected(self):
        """Should reject task number 0."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        with pytest.raises(ValueError, match="Task number must be positive"):
            generate_task_id(epic, 0)

    def test_generate_task_id_negative_rejected(self):
        """Should reject negative task number."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        with pytest.raises(ValueError, match="Task number must be positive"):
            generate_task_id(epic, -1)


class TestGenerateStandaloneId:
    """Tests for generate_standalone_id function."""

    def test_generate_standalone_id_allocates_counter(self, monkeypatch):
        """Should allocate counter and return StandaloneTaskId."""
        # Mock allocate_standalone_number to return 17
        mock_allocate = Mock(return_value=17)
        monkeypatch.setattr(
            "cub.core.ids.generator.allocate_standalone_number", mock_allocate
        )

        sync_service = Mock()
        result = generate_standalone_id("cub", sync_service)

        assert isinstance(result, StandaloneTaskId)
        assert result.project == "cub"
        assert result.number == 17
        assert str(result) == "cub-s017"
        mock_allocate.assert_called_once_with(sync_service)

    def test_generate_standalone_id_different_project(self, monkeypatch):
        """Should work with different project names."""
        mock_allocate = Mock(return_value=5)
        monkeypatch.setattr(
            "cub.core.ids.generator.allocate_standalone_number", mock_allocate
        )

        sync_service = Mock()
        result = generate_standalone_id("myproject", sync_service)

        assert result.project == "myproject"
        assert result.number == 5
        assert str(result) == "myproject-s005"


class TestNextPlanLetter:
    """Tests for next_plan_letter helper."""

    def test_next_plan_letter_empty_list(self):
        """Should return 'A' when no letters exist."""
        result = next_plan_letter([])
        assert result == "A"

    def test_next_plan_letter_first_few(self):
        """Should return next uppercase letter in sequence."""
        assert next_plan_letter(["A"]) == "B"
        assert next_plan_letter(["A", "B"]) == "C"
        assert next_plan_letter(["A", "B", "C"]) == "D"

    def test_next_plan_letter_after_uppercase(self):
        """Should return first lowercase after all uppercase."""
        uppercase = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        result = next_plan_letter(uppercase)
        assert result == "a"

    def test_next_plan_letter_after_lowercase(self):
        """Should return first digit after all letters."""
        all_letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
        result = next_plan_letter(all_letters)
        assert result == "0"

    def test_next_plan_letter_skips_used(self):
        """Should skip used letters even if out of order."""
        result = next_plan_letter(["A", "C", "B"])
        assert result == "D"

    def test_next_plan_letter_mixed_sequence(self):
        """Should work with mixed case existing letters."""
        result = next_plan_letter(["A", "a", "0"])
        assert result == "B"

    def test_next_plan_letter_exhausted(self):
        """Should raise ValueError when all 62 letters are used."""
        # All plan letters: A-Z (26), a-z (26), 0-9 (10) = 62 total
        all_letters = (
            list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            + list("abcdefghijklmnopqrstuvwxyz")
            + list("0123456789")
        )
        with pytest.raises(ValueError, match="All plan letters exhausted"):
            next_plan_letter(all_letters)


class TestNextEpicChar:
    """Tests for next_epic_char helper."""

    def test_next_epic_char_empty_list(self):
        """Should return '0' when no chars exist."""
        result = next_epic_char([])
        assert result == "0"

    def test_next_epic_char_first_few(self):
        """Should return next digit in sequence."""
        assert next_epic_char(["0"]) == "1"
        assert next_epic_char(["0", "1"]) == "2"
        assert next_epic_char(["0", "1", "2"]) == "3"

    def test_next_epic_char_after_digits(self):
        """Should return first lowercase after all digits."""
        digits = list("0123456789")
        result = next_epic_char(digits)
        assert result == "a"

    def test_next_epic_char_after_lowercase(self):
        """Should return first uppercase after all lowercase."""
        digits_and_lowercase = list("0123456789abcdefghijklmnopqrstuvwxyz")
        result = next_epic_char(digits_and_lowercase)
        assert result == "A"

    def test_next_epic_char_skips_used(self):
        """Should skip used chars even if out of order."""
        result = next_epic_char(["0", "2", "1"])
        assert result == "3"

    def test_next_epic_char_mixed_sequence(self):
        """Should work with mixed case existing chars."""
        result = next_epic_char(["0", "a", "A"])
        assert result == "1"

    def test_next_epic_char_exhausted(self):
        """Should raise ValueError when all 62 chars are used."""
        # All epic chars: 0-9 (10), a-z (26), A-Z (26) = 62 total
        all_chars = (
            list("0123456789")
            + list("abcdefghijklmnopqrstuvwxyz")
            + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        )
        with pytest.raises(ValueError, match="All epic chars exhausted"):
            next_epic_char(all_chars)


class TestAcceptanceCriteria:
    """Verify acceptance criteria from task description."""

    def test_generate_spec_id_acceptance(self, monkeypatch):
        """AC: generate_spec_id("cub", sync) allocates counter and returns SpecId."""
        mock_allocate = Mock(return_value=54)
        monkeypatch.setattr(
            "cub.core.ids.generator.allocate_spec_number", mock_allocate
        )

        sync_service = Mock()
        result = generate_spec_id("cub", sync_service)

        assert isinstance(result, SpecId)
        assert str(result) == "cub-054"
        mock_allocate.assert_called_once()

    def test_letter_char_helpers_follow_sequence_rules(self):
        """AC: Letter/char helpers follow sequence rules (A-Z, a-z, 0-9 for plans)."""
        # Plan letters: A-Z first
        assert next_plan_letter([]) == "A"
        uppercase = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        assert next_plan_letter(uppercase) == "a"

        # Then a-z
        all_letters = uppercase + list("abcdefghijklmnopqrstuvwxyz")
        assert next_plan_letter(all_letters) == "0"

        # Epic chars: 0-9 first
        assert next_epic_char([]) == "0"
        digits = list("0123456789")
        assert next_epic_char(digits) == "a"

        # Then a-z
        digits_lowercase = digits + list("abcdefghijklmnopqrstuvwxyz")
        assert next_epic_char(digits_lowercase) == "A"

    def test_generator_validates_inputs(self):
        """AC: Generator validates inputs (e.g., letter must be single char)."""
        spec = SpecId(project="cub", number=54)

        # Invalid plan letter
        with pytest.raises(ValueError):
            generate_plan_id(spec, "AB")  # Too long

        with pytest.raises(ValueError):
            generate_plan_id(spec, "-")  # Invalid character

        # Invalid epic char
        plan = PlanId(spec=spec, letter="A")
        with pytest.raises(ValueError):
            generate_epic_id(plan, "01")  # Too long

        # Invalid task number
        epic = EpicId(plan=plan, char="0")
        with pytest.raises(ValueError):
            generate_task_id(epic, 0)  # Must be >= 1

    def test_all_generators_return_typed_models(self, monkeypatch):
        """AC: All generators return properly typed ID models."""
        # Mock counter allocation
        monkeypatch.setattr(
            "cub.core.ids.generator.allocate_spec_number", Mock(return_value=54)
        )
        monkeypatch.setattr(
            "cub.core.ids.generator.allocate_standalone_number", Mock(return_value=17)
        )

        sync_service = Mock()

        # Test each generator returns correct type
        spec = generate_spec_id("cub", sync_service)
        assert isinstance(spec, SpecId)

        plan = generate_plan_id(spec, "A")
        assert isinstance(plan, PlanId)

        epic = generate_epic_id(plan, "0")
        assert isinstance(epic, EpicId)

        task = generate_task_id(epic, 1)
        assert isinstance(task, TaskId)

        standalone = generate_standalone_id("cub", sync_service)
        assert isinstance(standalone, StandaloneTaskId)
