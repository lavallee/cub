"""
Tests for ID models.

These tests verify the hierarchical ID models work correctly with proper
validation, string formatting, and immutability.
"""

import pytest
from pydantic import ValidationError

from cub.core.ids import EpicId, PlanId, SpecId, StandaloneTaskId, TaskId


class TestSpecId:
    """Tests for SpecId model."""

    def test_spec_id_format(self) -> None:
        """Test SpecId string format: {project}-{number:03d}"""
        spec = SpecId(project="cub", number=54)
        assert str(spec) == "cub-054"

    def test_spec_id_zero_padding(self) -> None:
        """Test that spec numbers are zero-padded to 3 digits."""
        spec1 = SpecId(project="cub", number=1)
        assert str(spec1) == "cub-001"

        spec2 = SpecId(project="cub", number=99)
        assert str(spec2) == "cub-099"

        spec3 = SpecId(project="cub", number=1000)
        assert str(spec3) == "cub-1000"

    def test_spec_id_negative_number_rejected(self) -> None:
        """Test that negative spec numbers are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SpecId(project="cub", number=-1)
        assert "Spec number must be non-negative" in str(exc_info.value)

    def test_spec_id_immutable(self) -> None:
        """Test that SpecId is immutable (frozen)."""
        spec = SpecId(project="cub", number=54)
        with pytest.raises(ValidationError):
            spec.number = 55  # type: ignore[misc]

    def test_spec_id_equality(self) -> None:
        """Test that SpecId equality works correctly."""
        spec1 = SpecId(project="cub", number=54)
        spec2 = SpecId(project="cub", number=54)
        spec3 = SpecId(project="cub", number=55)

        assert spec1 == spec2
        assert spec1 != spec3


class TestPlanId:
    """Tests for PlanId model."""

    def test_plan_id_format(self) -> None:
        """Test PlanId string format: {spec_id}{letter}"""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        assert str(plan) == "cub-054A"

    def test_plan_id_letter_sequences(self) -> None:
        """Test that all valid letter values work: A-Z, a-z, 0-9."""
        spec = SpecId(project="cub", number=54)

        # Test uppercase letters
        for i, char in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            plan = PlanId(spec=spec, letter=char)
            assert str(plan) == f"cub-054{char}"

        # Test lowercase letters
        for char in "abcdefghijklmnopqrstuvwxyz":
            plan = PlanId(spec=spec, letter=char)
            assert str(plan) == f"cub-054{char}"

        # Test digits
        for char in "0123456789":
            plan = PlanId(spec=spec, letter=char)
            assert str(plan) == f"cub-054{char}"

    def test_plan_id_invalid_letter_rejected(self) -> None:
        """Test that invalid letter values are rejected."""
        spec = SpecId(project="cub", number=54)

        # Test multi-character string
        with pytest.raises(ValidationError) as exc_info:
            PlanId(spec=spec, letter="AB")
        assert "single character" in str(exc_info.value)

        # Test special character
        with pytest.raises(ValidationError) as exc_info:
            PlanId(spec=spec, letter="-")
        assert "single character" in str(exc_info.value)

        # Test empty string
        with pytest.raises(ValidationError) as exc_info:
            PlanId(spec=spec, letter="")
        assert "single character" in str(exc_info.value)

    def test_plan_id_immutable(self) -> None:
        """Test that PlanId is immutable (frozen)."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        with pytest.raises(ValidationError):
            plan.letter = "B"  # type: ignore[misc]


class TestEpicId:
    """Tests for EpicId model."""

    def test_epic_id_format(self) -> None:
        """Test EpicId string format: {plan_id}-{char}"""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        assert str(epic) == "cub-054A-0"

    def test_epic_id_char_sequences(self) -> None:
        """Test that all valid char values work: 0-9, a-z, A-Z."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")

        # Test digits (preferred first)
        for char in "0123456789":
            epic = EpicId(plan=plan, char=char)
            assert str(epic) == f"cub-054A-{char}"

        # Test lowercase letters
        for char in "abcdefghijklmnopqrstuvwxyz":
            epic = EpicId(plan=plan, char=char)
            assert str(epic) == f"cub-054A-{char}"

        # Test uppercase letters
        for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            epic = EpicId(plan=plan, char=char)
            assert str(epic) == f"cub-054A-{char}"

    def test_epic_id_invalid_char_rejected(self) -> None:
        """Test that invalid char values are rejected."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")

        # Test multi-character string
        with pytest.raises(ValidationError) as exc_info:
            EpicId(plan=plan, char="00")
        assert "single character" in str(exc_info.value)

        # Test special character
        with pytest.raises(ValidationError) as exc_info:
            EpicId(plan=plan, char="-")
        assert "single character" in str(exc_info.value)

        # Test empty string
        with pytest.raises(ValidationError) as exc_info:
            EpicId(plan=plan, char="")
        assert "single character" in str(exc_info.value)

    def test_epic_id_immutable(self) -> None:
        """Test that EpicId is immutable (frozen)."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        with pytest.raises(ValidationError):
            epic.char = "1"  # type: ignore[misc]


class TestTaskId:
    """Tests for TaskId model."""

    def test_task_id_format(self) -> None:
        """Test TaskId string format: {epic_id}.{number}"""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        task = TaskId(epic=epic, number=1)
        assert str(task) == "cub-054A-0.1"

    def test_task_id_multiple_digits(self) -> None:
        """Test that task numbers work with multiple digits."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")

        task1 = TaskId(epic=epic, number=1)
        assert str(task1) == "cub-054A-0.1"

        task10 = TaskId(epic=epic, number=10)
        assert str(task10) == "cub-054A-0.10"

        task100 = TaskId(epic=epic, number=100)
        assert str(task100) == "cub-054A-0.100"

    def test_task_id_zero_rejected(self) -> None:
        """Test that task number 0 is rejected (must start at 1)."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")

        with pytest.raises(ValidationError) as exc_info:
            TaskId(epic=epic, number=0)
        assert "must be positive" in str(exc_info.value)

    def test_task_id_negative_number_rejected(self) -> None:
        """Test that negative task numbers are rejected."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")

        with pytest.raises(ValidationError) as exc_info:
            TaskId(epic=epic, number=-1)
        assert "must be positive" in str(exc_info.value)

    def test_task_id_immutable(self) -> None:
        """Test that TaskId is immutable (frozen)."""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        task = TaskId(epic=epic, number=1)
        with pytest.raises(ValidationError):
            task.number = 2  # type: ignore[misc]


class TestStandaloneTaskId:
    """Tests for StandaloneTaskId model."""

    def test_standalone_task_id_format(self) -> None:
        """Test StandaloneTaskId string format: {project}-s{number:03d}"""
        task = StandaloneTaskId(project="cub", number=17)
        assert str(task) == "cub-s017"

    def test_standalone_task_id_zero_padding(self) -> None:
        """Test that standalone task numbers are zero-padded to 3 digits."""
        task1 = StandaloneTaskId(project="cub", number=1)
        assert str(task1) == "cub-s001"

        task2 = StandaloneTaskId(project="cub", number=99)
        assert str(task2) == "cub-s099"

        task3 = StandaloneTaskId(project="cub", number=1000)
        assert str(task3) == "cub-s1000"

    def test_standalone_task_id_negative_number_rejected(self) -> None:
        """Test that negative standalone task numbers are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            StandaloneTaskId(project="cub", number=-1)
        assert "must be non-negative" in str(exc_info.value)

    def test_standalone_task_id_immutable(self) -> None:
        """Test that StandaloneTaskId is immutable (frozen)."""
        task = StandaloneTaskId(project="cub", number=17)
        with pytest.raises(ValidationError):
            task.number = 18  # type: ignore[misc]


class TestHierarchicalComposition:
    """Tests for hierarchical composition of ID models."""

    def test_full_hierarchy(self) -> None:
        """Test that IDs compose correctly through the full hierarchy."""
        # Build the full hierarchy
        spec = SpecId(project="cub", number=48)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        task = TaskId(epic=epic, number=1)

        # Verify each level
        assert str(spec) == "cub-048"
        assert str(plan) == "cub-048A"
        assert str(epic) == "cub-048A-0"
        assert str(task) == "cub-048A-0.1"

        # Verify we can access nested components
        assert str(task.epic) == "cub-048A-0"
        assert str(task.epic.plan) == "cub-048A"
        assert str(task.epic.plan.spec) == "cub-048"
        assert task.epic.plan.spec.project == "cub"
        assert task.epic.plan.spec.number == 48

    def test_multiple_plans_same_spec(self) -> None:
        """Test that multiple plans can exist for the same spec."""
        spec = SpecId(project="cub", number=48)
        plan_a = PlanId(spec=spec, letter="A")
        plan_b = PlanId(spec=spec, letter="B")

        assert str(plan_a) == "cub-048A"
        assert str(plan_b) == "cub-048B"

    def test_multiple_epics_same_plan(self) -> None:
        """Test that multiple epics can exist for the same plan."""
        spec = SpecId(project="cub", number=48)
        plan = PlanId(spec=spec, letter="A")
        epic_0 = EpicId(plan=plan, char="0")
        epic_1 = EpicId(plan=plan, char="1")

        assert str(epic_0) == "cub-048A-0"
        assert str(epic_1) == "cub-048A-1"

    def test_multiple_tasks_same_epic(self) -> None:
        """Test that multiple tasks can exist for the same epic."""
        spec = SpecId(project="cub", number=48)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        task_1 = TaskId(epic=epic, number=1)
        task_2 = TaskId(epic=epic, number=2)

        assert str(task_1) == "cub-048A-0.1"
        assert str(task_2) == "cub-048A-0.2"


class TestAcceptanceCriteria:
    """Tests for specific acceptance criteria from the task description."""

    def test_spec_id_acceptance_criteria(self) -> None:
        """Test: str(SpecId(project="cub", number=54)) returns "cub-054" """
        spec = SpecId(project="cub", number=54)
        assert str(spec) == "cub-054"

    def test_task_id_acceptance_criteria(self) -> None:
        """Test: str(TaskId(...)) returns "cub-054A-0.1" format"""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        task = TaskId(epic=epic, number=1)
        assert str(task) == "cub-054A-0.1"

    def test_validation_errors_acceptance_criteria(self) -> None:
        """Test: Invalid letter/char values raise ValidationError"""
        spec = SpecId(project="cub", number=54)

        # Invalid plan letter
        with pytest.raises(ValidationError):
            PlanId(spec=spec, letter="!")

        # Invalid epic char
        plan = PlanId(spec=spec, letter="A")
        with pytest.raises(ValidationError):
            EpicId(plan=plan, char="@")

    def test_immutability_acceptance_criteria(self) -> None:
        """Test: Models are immutable (frozen=True)"""
        spec = SpecId(project="cub", number=54)
        plan = PlanId(spec=spec, letter="A")
        epic = EpicId(plan=plan, char="0")
        task = TaskId(epic=epic, number=1)
        standalone = StandaloneTaskId(project="cub", number=17)

        # All models should raise ValidationError on mutation
        with pytest.raises(ValidationError):
            spec.number = 55  # type: ignore[misc]

        with pytest.raises(ValidationError):
            plan.letter = "B"  # type: ignore[misc]

        with pytest.raises(ValidationError):
            epic.char = "1"  # type: ignore[misc]

        with pytest.raises(ValidationError):
            task.number = 2  # type: ignore[misc]

        with pytest.raises(ValidationError):
            standalone.number = 18  # type: ignore[misc]
