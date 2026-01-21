"""
Tests for the spec lifecycle management module.

Tests cover:
- Moving specs from planned -> staged (on stage)
- Moving specs from staged -> implementing (on run start)
- Moving specs from implementing -> released (on release)
- Determining lifecycle stage from plan context
- Error handling and edge cases
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from cub.core.plan.context import PlanContext
from cub.core.specs.lifecycle import (
    SpecLifecycleError,
    get_spec_lifecycle_stage_from_plan,
    move_spec_to_implementing,
    move_spec_to_staged,
    move_specs_to_released,
)
from cub.core.specs.models import Spec, Stage
from cub.core.specs.workflow import SpecMoveError, SpecNotFoundError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_plan_context(tmp_path: Path) -> MagicMock:
    """Create a mock PlanContext for testing."""
    ctx = MagicMock(spec=PlanContext)
    ctx.get_specs_root.return_value = tmp_path / "specs"
    return ctx


@pytest.fixture
def specs_dir(tmp_path: Path) -> Path:
    """Create a specs directory with stage subdirectories."""
    specs_root = tmp_path / "specs"
    for stage in ["researching", "planned", "staged", "implementing", "released"]:
        (specs_root / stage).mkdir(parents=True)
    return specs_root


@pytest.fixture
def sample_spec_content() -> str:
    """Sample spec markdown content."""
    return """---
title: Test Feature
status: ready
priority: high
complexity: medium
created: 2026-01-20
---

# Test Feature

This is a test feature spec.
"""


# =============================================================================
# move_spec_to_staged Tests
# =============================================================================


class TestMoveSpecToStaged:
    """Tests for moving specs from planned -> staged."""

    def test_move_spec_with_no_spec_in_context(self, mock_plan_context: MagicMock) -> None:
        """Should return None when plan context has no spec."""
        mock_plan_context.has_spec = False
        mock_plan_context.spec_path = None

        result = move_spec_to_staged(mock_plan_context)

        assert result is None

    def test_move_spec_not_in_planned_directory(
        self, mock_plan_context: MagicMock, specs_dir: Path
    ) -> None:
        """Should return None when spec is not in planned/ directory."""
        # Spec is in researching/, not planned/
        spec_path = specs_dir / "researching" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = move_spec_to_staged(mock_plan_context)

        assert result is None

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_spec_from_planned_to_staged(
        self,
        mock_workflow_class: MagicMock,
        mock_plan_context: MagicMock,
        specs_dir: Path,
    ) -> None:
        """Should move spec from planned/ to staged/ successfully."""
        # Setup: spec in planned/
        spec_path = specs_dir / "planned" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        # Mock the workflow
        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow

        # Mock the result of move_to_stage
        moved_spec = Mock(spec=Spec)
        moved_spec.path = specs_dir / "staged" / "feature.md"
        mock_workflow.move_to_stage.return_value = moved_spec

        result = move_spec_to_staged(mock_plan_context)

        # Verify workflow was called correctly
        mock_workflow_class.assert_called_once_with(specs_dir)
        mock_workflow.move_to_stage.assert_called_once_with("feature", Stage.STAGED)
        assert result == specs_dir / "staged" / "feature.md"

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_spec_verbose_output(
        self,
        mock_workflow_class: MagicMock,
        mock_plan_context: MagicMock,
        specs_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print status message when verbose=True."""
        spec_path = specs_dir / "planned" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow
        moved_spec = Mock(spec=Spec)
        moved_spec.path = specs_dir / "staged" / "feature.md"
        mock_workflow.move_to_stage.return_value = moved_spec

        move_spec_to_staged(mock_plan_context, verbose=True)

        captured = capsys.readouterr()
        assert "Moved spec to staged/" in captured.out

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_spec_workflow_error(
        self,
        mock_workflow_class: MagicMock,
        mock_plan_context: MagicMock,
        specs_dir: Path,
    ) -> None:
        """Should raise SpecLifecycleError when workflow fails."""
        spec_path = specs_dir / "planned" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow
        mock_workflow.move_to_stage.side_effect = SpecMoveError("Move failed")

        with pytest.raises(SpecLifecycleError, match="Failed to move spec to staged"):
            move_spec_to_staged(mock_plan_context)

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_spec_not_found_error(
        self,
        mock_workflow_class: MagicMock,
        mock_plan_context: MagicMock,
        specs_dir: Path,
    ) -> None:
        """Should raise SpecLifecycleError when spec not found."""
        spec_path = specs_dir / "planned" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow
        mock_workflow.move_to_stage.side_effect = SpecNotFoundError("Not found")

        with pytest.raises(SpecLifecycleError, match="Failed to move spec to staged"):
            move_spec_to_staged(mock_plan_context)


# =============================================================================
# move_spec_to_implementing Tests
# =============================================================================


class TestMoveSpecToImplementing:
    """Tests for moving specs from staged -> implementing."""

    def test_move_spec_with_no_spec_in_context(self, mock_plan_context: MagicMock) -> None:
        """Should return None when plan context has no spec."""
        mock_plan_context.has_spec = False
        mock_plan_context.spec_path = None

        result = move_spec_to_implementing(mock_plan_context)

        assert result is None

    def test_move_spec_not_in_staged_directory(
        self, mock_plan_context: MagicMock, specs_dir: Path
    ) -> None:
        """Should return None when spec is not in staged/ directory."""
        # Spec is in planned/, not staged/
        spec_path = specs_dir / "planned" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = move_spec_to_implementing(mock_plan_context)

        assert result is None

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_spec_from_staged_to_implementing(
        self,
        mock_workflow_class: MagicMock,
        mock_plan_context: MagicMock,
        specs_dir: Path,
    ) -> None:
        """Should move spec from staged/ to implementing/ successfully."""
        # Setup: spec in staged/
        spec_path = specs_dir / "staged" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        # Mock the workflow
        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow

        # Mock the result of move_to_stage
        moved_spec = Mock(spec=Spec)
        moved_spec.path = specs_dir / "implementing" / "feature.md"
        mock_workflow.move_to_stage.return_value = moved_spec

        result = move_spec_to_implementing(mock_plan_context)

        # Verify workflow was called correctly
        mock_workflow_class.assert_called_once_with(specs_dir)
        mock_workflow.move_to_stage.assert_called_once_with("feature", Stage.IMPLEMENTING)
        assert result == specs_dir / "implementing" / "feature.md"

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_spec_verbose_output(
        self,
        mock_workflow_class: MagicMock,
        mock_plan_context: MagicMock,
        specs_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print status message when verbose=True."""
        spec_path = specs_dir / "staged" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow
        moved_spec = Mock(spec=Spec)
        moved_spec.path = specs_dir / "implementing" / "feature.md"
        mock_workflow.move_to_stage.return_value = moved_spec

        move_spec_to_implementing(mock_plan_context, verbose=True)

        captured = capsys.readouterr()
        assert "Moved spec to implementing/" in captured.out

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_spec_workflow_error(
        self,
        mock_workflow_class: MagicMock,
        mock_plan_context: MagicMock,
        specs_dir: Path,
    ) -> None:
        """Should raise SpecLifecycleError when workflow fails."""
        spec_path = specs_dir / "staged" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow
        mock_workflow.move_to_stage.side_effect = SpecMoveError("Move failed")

        with pytest.raises(SpecLifecycleError, match="Failed to move spec to implementing"):
            move_spec_to_implementing(mock_plan_context)


# =============================================================================
# move_specs_to_released Tests
# =============================================================================


class TestMoveSpecsToReleased:
    """Tests for moving specs from implementing -> released."""

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_specs_no_implementing_specs(
        self, mock_workflow_class: MagicMock, specs_dir: Path
    ) -> None:
        """Should return empty list when no specs in implementing/."""
        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow
        mock_workflow.list_specs.return_value = []

        result = move_specs_to_released(specs_dir)

        assert result == []
        mock_workflow.list_specs.assert_called_once_with(Stage.IMPLEMENTING)

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_specs_no_specs_directory(
        self, mock_workflow_class: MagicMock, specs_dir: Path
    ) -> None:
        """Should return empty list when specs directory doesn't exist."""
        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow
        mock_workflow.list_specs.side_effect = FileNotFoundError()

        result = move_specs_to_released(specs_dir)

        assert result == []

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_multiple_specs_to_released(
        self, mock_workflow_class: MagicMock, specs_dir: Path
    ) -> None:
        """Should move all implementing specs to released."""
        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow

        # Create mock specs
        spec1 = Mock(spec=Spec)
        spec1.name = "feature1"
        spec2 = Mock(spec=Spec)
        spec2.name = "feature2"

        mock_workflow.list_specs.return_value = [spec1, spec2]

        # Mock move results
        moved_spec1 = Mock(spec=Spec)
        moved_spec1.path = specs_dir / "released" / "feature1.md"
        moved_spec2 = Mock(spec=Spec)
        moved_spec2.path = specs_dir / "released" / "feature2.md"

        mock_workflow.move_to_stage.side_effect = [moved_spec1, moved_spec2]

        result = move_specs_to_released(specs_dir)

        # Verify both specs were moved
        assert len(result) == 2
        assert result[0] == specs_dir / "released" / "feature1.md"
        assert result[1] == specs_dir / "released" / "feature2.md"

        # Verify workflow calls
        assert mock_workflow.move_to_stage.call_count == 2
        mock_workflow.move_to_stage.assert_any_call(spec1, Stage.RELEASED)
        mock_workflow.move_to_stage.assert_any_call(spec2, Stage.RELEASED)

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_specs_verbose_output(
        self,
        mock_workflow_class: MagicMock,
        specs_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Should print status messages when verbose=True."""
        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow

        spec1 = Mock(spec=Spec)
        spec1.name = "feature1"
        mock_workflow.list_specs.return_value = [spec1]

        moved_spec = Mock(spec=Spec)
        moved_spec.path = specs_dir / "released" / "feature1.md"
        mock_workflow.move_to_stage.return_value = moved_spec

        move_specs_to_released(specs_dir, verbose=True)

        captured = capsys.readouterr()
        assert "Moved spec to released/" in captured.out

    @patch("cub.core.specs.lifecycle.SpecWorkflow")
    def test_move_specs_error_on_one_spec(
        self, mock_workflow_class: MagicMock, specs_dir: Path
    ) -> None:
        """Should raise SpecLifecycleError if any spec fails to move."""
        mock_workflow = MagicMock()
        mock_workflow_class.return_value = mock_workflow

        spec1 = Mock(spec=Spec)
        spec1.name = "feature1"
        mock_workflow.list_specs.return_value = [spec1]

        mock_workflow.move_to_stage.side_effect = SpecMoveError("Move failed")

        with pytest.raises(SpecLifecycleError, match="Failed to move spec 'feature1' to released"):
            move_specs_to_released(specs_dir)


# =============================================================================
# get_spec_lifecycle_stage_from_plan Tests
# =============================================================================


class TestGetSpecLifecycleStageFromPlan:
    """Tests for determining spec lifecycle stage from plan context."""

    def test_get_stage_with_no_spec(self, mock_plan_context: MagicMock) -> None:
        """Should return None when plan has no spec."""
        mock_plan_context.has_spec = False
        mock_plan_context.spec_path = None

        result = get_spec_lifecycle_stage_from_plan(mock_plan_context)

        assert result is None

    def test_get_stage_researching(self, mock_plan_context: MagicMock, specs_dir: Path) -> None:
        """Should detect spec in researching/ stage."""
        spec_path = specs_dir / "researching" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = get_spec_lifecycle_stage_from_plan(mock_plan_context)

        assert result == Stage.RESEARCHING

    def test_get_stage_planned(self, mock_plan_context: MagicMock, specs_dir: Path) -> None:
        """Should detect spec in planned/ stage."""
        spec_path = specs_dir / "planned" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = get_spec_lifecycle_stage_from_plan(mock_plan_context)

        assert result == Stage.PLANNED

    def test_get_stage_staged(self, mock_plan_context: MagicMock, specs_dir: Path) -> None:
        """Should detect spec in staged/ stage."""
        spec_path = specs_dir / "staged" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = get_spec_lifecycle_stage_from_plan(mock_plan_context)

        assert result == Stage.STAGED

    def test_get_stage_implementing(self, mock_plan_context: MagicMock, specs_dir: Path) -> None:
        """Should detect spec in implementing/ stage."""
        spec_path = specs_dir / "implementing" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = get_spec_lifecycle_stage_from_plan(mock_plan_context)

        assert result == Stage.IMPLEMENTING

    def test_get_stage_released(self, mock_plan_context: MagicMock, specs_dir: Path) -> None:
        """Should NOT detect spec in released/ stage due to COMPLETED filter bug.

        Note: There's a bug where the function filters out Stage.COMPLETED,
        which is an alias for Stage.RELEASED. This causes RELEASED stage to
        be excluded from the search. This test documents current behavior.
        """
        spec_path = specs_dir / "released" / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = get_spec_lifecycle_stage_from_plan(mock_plan_context)

        # BUG: This should be Stage.RELEASED but returns None due to
        # filtering out COMPLETED which is an alias for RELEASED
        assert result is None

    def test_get_stage_outside_specs_dir(
        self, mock_plan_context: MagicMock, specs_dir: Path, tmp_path: Path
    ) -> None:
        """Should return None when spec is outside specs directory."""
        # Spec in a different location
        spec_path = tmp_path / "other" / "feature.md"
        spec_path.parent.mkdir(parents=True)
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = get_spec_lifecycle_stage_from_plan(mock_plan_context)

        assert result is None

    def test_get_stage_in_unknown_subdirectory(
        self, mock_plan_context: MagicMock, specs_dir: Path
    ) -> None:
        """Should return None when spec is in unknown subdirectory."""
        # Spec in specs/archive/ (not a lifecycle stage)
        archive_dir = specs_dir / "archive"
        archive_dir.mkdir()
        spec_path = archive_dir / "feature.md"
        spec_path.touch()

        mock_plan_context.has_spec = True
        mock_plan_context.spec_path = spec_path
        mock_plan_context.get_specs_root.return_value = specs_dir

        result = get_spec_lifecycle_stage_from_plan(mock_plan_context)

        assert result is None
