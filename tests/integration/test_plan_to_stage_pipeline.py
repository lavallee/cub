"""
Integration tests for the full planning to staging pipeline.

Tests the end-to-end workflow from:
1. Orient phase (creates plan.json)
2. Architect phase (updates plan.json)
3. Itemize phase (updates plan.json)
4. Stage phase (reads plan.json and imports tasks)

Validates that:
- plan.json is properly created on first phase
- plan.json is properly updated by subsequent phases
- plan.json schema is consistent and readable by `cub stage`
- The full pipeline works when run in sequence
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cub.core.plan.architect import ArchitectStage
from cub.core.plan.context import PlanContext
from cub.core.plan.itemize import ItemizeStage
from cub.core.plan.models import Plan, PlanStage, PlanStatus, StageStatus
from cub.core.plan.orient import OrientStage
from cub.core.plan.pipeline import PipelineConfig, PlanPipeline
from cub.core.stage.stager import Stager, find_stageable_plans


# Patch Claude CLI to use template fallback
@pytest.fixture(autouse=True)
def _no_claude() -> object:
    """Prevent real Claude CLI invocations in tests."""
    from cub.core.plan.claude import ClaudeNotFoundError

    err = ClaudeNotFoundError("mocked: claude not installed")
    with (
        patch("cub.core.plan.orient.invoke_claude_command", side_effect=err),
        patch("cub.core.plan.architect.invoke_claude_command", side_effect=err),
        patch("cub.core.plan.itemize.invoke_claude_command", side_effect=err),
    ):
        yield


@pytest.fixture
def project_with_spec(tmp_path: Path) -> tuple[Path, Path]:
    """Create a project with a spec file in researching/."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Create pyproject.toml for project name detection
    pyproject = project_root / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test-project"')

    # Create spec directory and file
    specs_dir = project_root / "specs" / "researching"
    specs_dir.mkdir(parents=True)

    spec_file = specs_dir / "test-feature.md"
    spec_file.write_text(
        """---
status: draft
decisions_made:
  - "Use Python 3.11"
  - "Use mypy strict mode"
questions:
  - "What database to use?"
---
# Test Feature

## Overview

This feature adds user authentication to the application.
It enables secure login and session management for users.

## Goals

- **Secure login**: Allow users to log in securely with password
- **Session management**: Manage user sessions with tokens
- **Password reset**: Allow users to reset forgotten passwords

## Non-Goals

- Social login integration
- Biometric authentication
"""
    )

    return project_root, spec_file


class TestPlanJsonGenerationAtEachPhase:
    """Test that plan.json is properly generated and updated at each phase."""

    def test_orient_creates_plan_json(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that orient stage creates plan.json with correct initial state."""
        project_root, spec_file = project_with_spec

        # Create plan context
        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            spec_path=spec_file,
        )

        # Run orient stage
        stage = OrientStage(ctx)
        result = stage.run()

        # Verify plan.json exists
        plan_dir = project_root / "plans" / "test-feature"
        plan_json_path = plan_dir / "plan.json"
        assert plan_json_path.exists(), "plan.json should be created by orient stage"

        # Verify plan.json content
        with open(plan_json_path) as f:
            plan_data = json.load(f)

        assert plan_data["slug"] == "test-feature"
        assert plan_data["project"] == "test-project"
        assert plan_data["spec_file"] == "test-feature.md"
        assert plan_data["stages"]["orient"] == "complete"
        assert plan_data["stages"]["architect"] == "pending"
        assert plan_data["stages"]["itemize"] == "pending"
        assert plan_data["status"] == "in_progress"

        # Verify orientation.md exists
        assert (plan_dir / "orientation.md").exists()
        assert result.output_path == plan_dir / "orientation.md"

    def test_architect_updates_plan_json_preserving_orient(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that architect stage updates plan.json without losing orient data."""
        project_root, spec_file = project_with_spec

        # First run orient stage
        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            spec_path=spec_file,
        )
        orient_stage = OrientStage(ctx)
        orient_stage.run()

        # Capture plan.json after orient
        plan_dir = project_root / "plans" / "test-feature"
        with open(plan_dir / "plan.json") as f:
            orient_data = json.load(f)

        # Load context and run architect stage
        ctx = PlanContext.load(plan_dir, project_root)
        architect_stage = ArchitectStage(ctx, mindset="mvp", scale="team")
        result = architect_stage.run()

        # Verify plan.json was updated
        with open(plan_dir / "plan.json") as f:
            architect_data = json.load(f)

        # Original data preserved
        assert architect_data["slug"] == orient_data["slug"]
        assert architect_data["project"] == orient_data["project"]
        assert architect_data["spec_file"] == orient_data["spec_file"]
        assert architect_data["stages"]["orient"] == "complete"  # Still complete

        # Architect stage updated
        assert architect_data["stages"]["architect"] == "complete"
        assert architect_data["stages"]["itemize"] == "pending"
        assert architect_data["status"] == "in_progress"

        # Verify architecture.md exists
        assert (plan_dir / "architecture.md").exists()
        assert result.output_path == plan_dir / "architecture.md"

    def test_itemize_updates_plan_json_preserving_all_phases(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that itemize stage updates plan.json without losing previous phase data."""
        project_root, spec_file = project_with_spec

        # Run full pipeline first
        config = PipelineConfig(spec_path=spec_file, move_spec=False)
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()

        assert result.success

        # Verify plan.json final state
        plan_dir = project_root / "plans" / "test-feature"
        with open(plan_dir / "plan.json") as f:
            final_data = json.load(f)

        # All stages complete
        assert final_data["stages"]["orient"] == "complete"
        assert final_data["stages"]["architect"] == "complete"
        assert final_data["stages"]["itemize"] == "complete"
        assert final_data["status"] == "complete"

        # All output files exist
        assert (plan_dir / "orientation.md").exists()
        assert (plan_dir / "architecture.md").exists()
        assert (plan_dir / "itemized-plan.md").exists()


class TestPlanJsonSchemaConsistency:
    """Test that plan.json schema is consistent and readable."""

    def test_plan_load_after_each_stage(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that Plan.load() works after each stage completes."""
        project_root, spec_file = project_with_spec

        # Create and run orient
        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            spec_path=spec_file,
        )
        OrientStage(ctx).run()

        # Load and verify plan after orient
        plan_dir = project_root / "plans" / "test-feature"
        plan = Plan.load(plan_dir)
        assert plan.slug == "test-feature"
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.PENDING
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.PENDING

        # Run architect
        ctx = PlanContext.load(plan_dir, project_root)
        ArchitectStage(ctx).run()

        # Load and verify plan after architect
        plan = Plan.load(plan_dir)
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.PENDING

        # Run itemize
        ctx = PlanContext.load(plan_dir, project_root)
        ItemizeStage(ctx).run()

        # Load and verify plan after itemize
        plan = Plan.load(plan_dir)
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.COMPLETE
        assert plan.is_complete

    def test_plan_context_load_after_each_stage(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that PlanContext.load() works after each stage completes."""
        project_root, spec_file = project_with_spec

        # Run full pipeline
        config = PipelineConfig(spec_path=spec_file, move_spec=False)
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()
        assert result.success

        # Load context and verify
        plan_dir = project_root / "plans" / "test-feature"
        ctx = PlanContext.load(plan_dir, project_root)

        assert ctx.plan.slug == "test-feature"
        assert ctx.plan.project == "test-project"
        assert ctx.plan.is_complete
        assert ctx.plan_dir == plan_dir
        assert ctx.orientation_path.exists()
        assert ctx.architecture_path.exists()
        assert ctx.itemized_plan_path.exists()


class TestStageCanReadCompletePlan:
    """Test that cub stage can read and process completed plans."""

    def test_stager_validates_complete_plan(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that Stager validates a complete plan successfully."""
        project_root, spec_file = project_with_spec

        # Run full pipeline
        config = PipelineConfig(spec_path=spec_file, move_spec=False)
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()
        assert result.success

        # Load context for stager
        plan_dir = project_root / "plans" / "test-feature"
        ctx = PlanContext.load(plan_dir, project_root)

        # Create mock backend for staging
        mock_backend = Mock()
        mock_backend.import_tasks = Mock(side_effect=lambda tasks: tasks)

        # Create stager and validate
        stager = Stager(ctx, backend=mock_backend)
        stager.validate()  # Should not raise

    def test_find_stageable_plans_finds_complete_plan(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that find_stageable_plans() finds complete plans."""
        project_root, spec_file = project_with_spec

        # Run full pipeline
        config = PipelineConfig(spec_path=spec_file, move_spec=False)
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()
        assert result.success

        # Find stageable plans
        stageable = find_stageable_plans(project_root)

        assert len(stageable) == 1
        assert stageable[0].name == "test-feature"

    def test_stager_stages_complete_plan(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that Stager can stage a complete plan."""
        project_root, spec_file = project_with_spec

        # Run full pipeline
        config = PipelineConfig(spec_path=spec_file, move_spec=False)
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()
        assert result.success

        # Load context for stager
        plan_dir = project_root / "plans" / "test-feature"
        ctx = PlanContext.load(plan_dir, project_root)

        # Create mock backend
        mock_backend = Mock()
        mock_backend.import_tasks = Mock(side_effect=lambda tasks: tasks)

        # Stage
        stager = Stager(ctx, backend=mock_backend)
        staging_result = stager.stage()

        # Verify staging result
        assert staging_result.plan_slug == "test-feature"
        assert len(staging_result.epics_created) > 0 or len(staging_result.tasks_created) > 0
        assert not staging_result.dry_run

        # Verify plan was marked as staged
        updated_plan = Plan.load(plan_dir)
        assert updated_plan.status == PlanStatus.STAGED


class TestFullPipelineToStageIntegration:
    """End-to-end integration test for orient → architect → itemize → stage."""

    def test_full_pipeline_to_stage_flow(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test complete flow from orient to stage."""
        project_root, spec_file = project_with_spec

        # Phase 1: Run orient separately
        ctx = PlanContext.create(
            project_root=project_root,
            project="test-project",
            spec_path=spec_file,
        )
        OrientStage(ctx).run()

        # Verify state after orient
        plan_dir = project_root / "plans" / "test-feature"
        plan = Plan.load(plan_dir)
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert (plan_dir / "orientation.md").exists()

        # Phase 2: Run architect
        ctx = PlanContext.load(plan_dir, project_root)
        ArchitectStage(ctx).run()

        # Verify state after architect
        plan = Plan.load(plan_dir)
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.COMPLETE
        assert (plan_dir / "architecture.md").exists()

        # Phase 3: Run itemize
        ctx = PlanContext.load(plan_dir, project_root)
        ItemizeStage(ctx).run()

        # Verify state after itemize
        plan = Plan.load(plan_dir)
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.COMPLETE
        assert plan.is_complete
        assert (plan_dir / "itemized-plan.md").exists()

        # Phase 4: Stage
        ctx = PlanContext.load(plan_dir, project_root)
        mock_backend = Mock()
        mock_backend.import_tasks = Mock(side_effect=lambda tasks: tasks)

        stager = Stager(ctx, backend=mock_backend)
        staging_result = stager.stage()

        # Verify final state
        assert staging_result.plan_slug == "test-feature"
        final_plan = Plan.load(plan_dir)
        assert final_plan.status == PlanStatus.STAGED

    def test_pipeline_run_then_stage(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test using PlanPipeline.run() followed by Stager."""
        project_root, spec_file = project_with_spec

        # Run pipeline
        config = PipelineConfig(spec_path=spec_file, move_spec=False)
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()

        assert result.success
        assert result.plan.is_complete

        # Now stage
        ctx = PlanContext.load(result.plan_dir, project_root)
        mock_backend = Mock()
        mock_backend.import_tasks = Mock(side_effect=lambda tasks: tasks)

        stager = Stager(ctx, backend=mock_backend)
        staging_result = stager.stage()

        assert staging_result.plan_slug == result.plan.slug
        assert mock_backend.import_tasks.call_count == 2  # epics + tasks


class TestPlanJsonFieldsAfterPipeline:
    """Test specific plan.json fields are correctly populated."""

    def test_timestamps_are_valid_iso(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that timestamps are valid ISO format."""
        project_root, spec_file = project_with_spec

        # Run pipeline
        config = PipelineConfig(spec_path=spec_file, move_spec=False)
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()
        assert result.success

        # Check timestamps
        plan_dir = project_root / "plans" / "test-feature"
        with open(plan_dir / "plan.json") as f:
            plan_data = json.load(f)

        from datetime import datetime

        # These should not raise
        created = datetime.fromisoformat(plan_data["created"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(plan_data["updated"].replace("Z", "+00:00"))

        assert created is not None
        assert updated is not None
        assert updated >= created

    def test_all_required_fields_present(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that all required fields are present in plan.json."""
        project_root, spec_file = project_with_spec

        # Run pipeline
        config = PipelineConfig(spec_path=spec_file, move_spec=False)
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()
        assert result.success

        plan_dir = project_root / "plans" / "test-feature"
        with open(plan_dir / "plan.json") as f:
            plan_data = json.load(f)

        # Required fields
        required_fields = ["slug", "project", "status", "stages", "created", "updated"]
        for field in required_fields:
            assert field in plan_data, f"Missing required field: {field}"

        # Stages must have all three
        stages = plan_data["stages"]
        assert "orient" in stages
        assert "architect" in stages
        assert "itemize" in stages
