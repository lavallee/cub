"""
Tests for plan ensure, complete-stage, status commands and related fixes.

Tests:
- cub plan ensure creates plan.json when missing
- cub plan ensure is idempotent
- cub plan complete-stage updates correct stage status
- Three complete-stages → plan.is_complete is True
- detect_pipeline_steps with artifacts but no plan.json → COMPLETE
- cub stage self-heals from missing plan.json
"""

from pathlib import Path

import pytest

from cub.core.plan.context import PlanContext
from cub.core.plan.models import Plan, PlanStage, PlanStatus, StageStatus
from cub.core.plan.pipeline import (
    StepDetectionStatus,
    detect_pipeline_steps,
)

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a minimal project directory."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "test-project"')
    (project / "plans").mkdir()
    return project


@pytest.fixture
def plan_dir_with_artifacts(project_root: Path) -> Path:
    """Create a plan directory with all three artifacts but no plan.json."""
    plan_dir = project_root / "plans" / "my-feature"
    plan_dir.mkdir(parents=True)

    (plan_dir / "orientation.md").write_text(
        "# Orient Report: My Feature\n\n"
        "## Problem Statement\n\n"
        "Users need authentication.\n\n"
        "## Requirements\n\n"
        "### P0 - Must Have\n- Login\n"
    )

    (plan_dir / "architecture.md").write_text(
        "# Architecture Design: My Feature\n\n"
        "## Technical Summary\n\n"
        "JWT-based auth with PostgreSQL.\n\n"
        "## Components\n\n"
        "### Auth Service\n- Login endpoint\n"
    )

    (plan_dir / "itemized-plan.md").write_text(
        "# Itemized Plan: My Feature\n\n"
        "## Epic: test-abc - my-feature #1: Foundation\n\n"
        "### Task: test-abc.1 - Setup auth\n\n"
        "Priority: 0\nLabels: phase-1\n\n"
        "**Context**: Setup authentication\n\n"
        "**Implementation Steps**:\n1. Create auth module\n\n"
        "**Acceptance Criteria**:\n- [ ] Auth works\n"
    )

    return plan_dir


# ==============================================================================
# Tests: cub plan ensure (model-level)
# ==============================================================================


class TestPlanEnsure:
    """Tests for plan ensure functionality."""

    def test_ensure_creates_plan_json_when_missing(
        self, project_root: Path
    ) -> None:
        """ensure creates plan.json when it doesn't exist."""
        slug = "new-feature"
        plan_dir = project_root / "plans" / slug

        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            slug=slug,
        )
        ctx.save_plan()

        plan_json = plan_dir / "plan.json"
        assert plan_json.exists()

        plan = Plan.load(plan_dir)
        assert plan.slug == slug
        assert plan.project == "test-project"
        assert plan.status == PlanStatus.PENDING

    def test_ensure_is_idempotent(self, project_root: Path) -> None:
        """ensure doesn't modify existing plan.json."""
        slug = "existing-feature"
        plan_dir = project_root / "plans" / slug

        # Create initial plan
        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            slug=slug,
        )
        ctx.save_plan()

        # Complete a stage
        plan = Plan.load(plan_dir)
        plan.complete_stage(PlanStage.ORIENT)
        plan.save(project_root)

        # Load again — orient should still be complete
        plan2 = Plan.load(plan_dir)
        assert plan2.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan2.status == PlanStatus.IN_PROGRESS

    def test_ensure_with_spec(self, project_root: Path) -> None:
        """ensure links spec file when provided."""
        # Create spec
        specs_dir = project_root / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature\n\nA feature spec.")

        slug = "my-feature"
        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            spec_path=spec_file,
            slug=slug,
        )
        ctx.save_plan()

        plan = Plan.load(project_root / "plans" / slug)
        assert plan.spec_file == "my-feature.md"


# ==============================================================================
# Tests: cub plan complete-stage (model-level)
# ==============================================================================


class TestCompleteStage:
    """Tests for plan complete-stage functionality."""

    def test_complete_stage_updates_status(self, project_root: Path) -> None:
        """complete-stage marks the correct stage as complete."""
        slug = "test-plan"
        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            slug=slug,
        )
        ctx.save_plan()

        plan_dir = project_root / "plans" / slug
        plan = Plan.load(plan_dir)
        plan.complete_stage(PlanStage.ORIENT)
        plan.save(project_root)

        plan = Plan.load(plan_dir)
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.PENDING
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.PENDING
        assert plan.status == PlanStatus.IN_PROGRESS

    def test_three_complete_stages_makes_plan_complete(
        self, project_root: Path
    ) -> None:
        """Completing all three stages marks plan as complete."""
        slug = "test-plan"
        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            slug=slug,
        )
        ctx.save_plan()

        plan_dir = project_root / "plans" / slug
        plan = Plan.load(plan_dir)

        plan.complete_stage(PlanStage.ORIENT)
        plan.complete_stage(PlanStage.ARCHITECT)
        plan.complete_stage(PlanStage.ITEMIZE)
        plan.save(project_root)

        plan = Plan.load(plan_dir)
        assert plan.is_complete
        assert plan.status == PlanStatus.COMPLETE

    def test_complete_stage_creates_plan_if_missing(
        self, project_root: Path
    ) -> None:
        """complete-stage can work even when plan.json must be created first."""
        slug = "no-plan-yet"
        plan_dir = project_root / "plans" / slug
        plan_dir.mkdir(parents=True)

        # Create plan manually (simulating what the CLI does internally)
        plan = Plan(slug=slug, project="test-project")
        plan.complete_stage(PlanStage.ORIENT)
        plan.save(project_root)

        loaded = Plan.load(plan_dir)
        assert loaded.stages[PlanStage.ORIENT] == StageStatus.COMPLETE


# ==============================================================================
# Tests: detect_pipeline_steps with artifacts but no plan.json
# ==============================================================================


class TestArtifactOnlyDetection:
    """Tests for pipeline step detection when plan.json is missing."""

    def test_artifacts_without_plan_json_detected_as_complete(
        self, plan_dir_with_artifacts: Path
    ) -> None:
        """Artifacts without plan.json should be detected as COMPLETE."""
        summary = detect_pipeline_steps(plan_dir_with_artifacts)

        assert not summary.plan_exists

        for step in summary.steps:
            assert step.status == StepDetectionStatus.COMPLETE, (
                f"{step.stage.value} should be COMPLETE but was {step.status.value}"
            )

        assert summary.all_complete

    def test_partial_artifacts_without_plan_json(
        self, project_root: Path
    ) -> None:
        """Only some artifacts present → mixed status."""
        plan_dir = project_root / "plans" / "partial"
        plan_dir.mkdir(parents=True)

        # Only orientation.md
        (plan_dir / "orientation.md").write_text(
            "# Orient Report\n\n" + "x" * 200
        )

        summary = detect_pipeline_steps(plan_dir)

        assert summary.steps[0].status == StepDetectionStatus.COMPLETE  # orient
        assert summary.steps[1].status == StepDetectionStatus.INCOMPLETE  # architect
        assert summary.steps[2].status == StepDetectionStatus.INCOMPLETE  # itemize
        assert not summary.all_complete

    def test_small_artifact_not_detected_as_complete(
        self, project_root: Path
    ) -> None:
        """Artifacts below minimum size should not be detected as complete."""
        plan_dir = project_root / "plans" / "stub"
        plan_dir.mkdir(parents=True)

        # Too small — stub file
        (plan_dir / "orientation.md").write_text("# Stub")

        summary = detect_pipeline_steps(plan_dir)
        assert summary.steps[0].status == StepDetectionStatus.INCOMPLETE

    def test_next_step_correct_without_plan_json(
        self, project_root: Path
    ) -> None:
        """Next step detection works without plan.json."""
        plan_dir = project_root / "plans" / "partial"
        plan_dir.mkdir(parents=True)

        (plan_dir / "orientation.md").write_text("# Orient\n\n" + "x" * 200)

        summary = detect_pipeline_steps(plan_dir)
        assert summary.next_step == PlanStage.ARCHITECT


# ==============================================================================
# Tests: Self-healing in cub stage
# ==============================================================================


class TestSelfHealingPlanJson:
    """Tests for plan.json reconstruction from artifacts."""

    def test_self_heal_creates_plan_json(
        self, plan_dir_with_artifacts: Path, project_root: Path
    ) -> None:
        """Self-healing creates plan.json from artifacts."""
        from cub.cli.stage import _self_heal_plan_json

        assert not (plan_dir_with_artifacts / "plan.json").exists()

        result = _self_heal_plan_json(plan_dir_with_artifacts, project_root)
        assert result is True
        assert (plan_dir_with_artifacts / "plan.json").exists()

        plan = Plan.load(plan_dir_with_artifacts)
        assert plan.is_complete
        assert plan.status == PlanStatus.COMPLETE
        assert plan.slug == "my-feature"

    def test_self_heal_skips_if_plan_json_exists(
        self, project_root: Path
    ) -> None:
        """Self-healing doesn't overwrite existing plan.json."""
        from cub.cli.stage import _self_heal_plan_json

        plan_dir = project_root / "plans" / "existing"
        plan_dir.mkdir(parents=True)

        plan = Plan(slug="existing", project="test-project")
        plan.save(project_root)

        result = _self_heal_plan_json(plan_dir, project_root)
        assert result is False

    def test_self_heal_skips_if_artifacts_incomplete(
        self, project_root: Path
    ) -> None:
        """Self-healing doesn't create plan.json if artifacts are incomplete."""
        from cub.cli.stage import _self_heal_plan_json

        plan_dir = project_root / "plans" / "partial"
        plan_dir.mkdir(parents=True)

        # Only one artifact
        (plan_dir / "orientation.md").write_text("# Orient\n\n" + "x" * 200)

        result = _self_heal_plan_json(plan_dir, project_root)
        assert result is False
        assert not (plan_dir / "plan.json").exists()
