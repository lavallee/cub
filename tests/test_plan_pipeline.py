"""
Unit tests for pipeline orchestration.

Tests the PlanPipeline class that runs orient -> architect -> itemize
in sequence with spec lifecycle management.

All stages fall back to template-based generation (no real LLM calls).
"""

import json
from pathlib import Path

import pytest

from cub.core.plan.models import PlanStage, StageStatus
from cub.core.plan.pipeline import (
    PipelineConfig,
    PipelineConfigError,
    PipelineResult,
    PipelineStepSummary,
    PlanPipeline,
    StageResult,
    StepDetectionStatus,
    StepInfo,
    continue_pipeline,
    detect_pipeline_steps,
    run_pipeline,
)

# All pipeline tests mock out invoke_claude_command so stages use
# their template fallback instead of calling the real Claude CLI.
pytestmark = pytest.mark.usefixtures("_no_claude")


# ==============================================================================
# Test Fixtures
# ==============================================================================


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

    spec_file = specs_dir / "my-feature.md"
    spec_file.write_text(
        """---
status: draft
---
# My Feature

## Overview

This feature adds user authentication to the application.

## Goals

- **Secure login**: Allow users to log in securely
- **Session management**: Manage user sessions
"""
    )

    return project_root, spec_file


@pytest.fixture
def project_with_partial_plan(tmp_path: Path) -> tuple[Path, Path]:
    """Create a project with a plan that has orient complete."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Create pyproject.toml
    pyproject = project_root / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test-project"')

    # Create spec file
    specs_dir = project_root / "specs" / "researching"
    specs_dir.mkdir(parents=True)
    spec_file = specs_dir / "my-feature.md"
    spec_file.write_text("# My Feature\n\n## Overview\n\nContent.")

    # Create partial plan
    plan_dir = project_root / "plans" / "my-feature"
    plan_dir.mkdir(parents=True)

    plan_json = {
        "slug": "my-feature",
        "project": "test-project",
        "status": "in_progress",
        "spec_file": "my-feature.md",
        "stages": {
            "orient": "complete",
            "architect": "pending",
            "itemize": "pending",
        },
    }
    (plan_dir / "plan.json").write_text(json.dumps(plan_json))

    # Create orientation.md
    (plan_dir / "orientation.md").write_text(
        """# Orientation: My Feature

> Source: [my-feature.md](../../specs/researching/my-feature.md)
> Generated: 2026-01-20
> Depth: Standard

## Problem Statement

This feature adds user authentication to the application.

## Requirements

### P0 (Must Have)

- **Secure login**
- **Session management**

### P1 (Should Have)

- *To be determined during interview.*

### P2 (Nice to Have)

- *To be determined during interview.*

## Constraints

| Constraint | Detail |
|------------|--------|
| *Constraints* | *To be determined* |

## Open Questions

1. *Questions to be surfaced during interview.*

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| *Risks* | *TBD* | *TBD* | *To be determined during interview* |

## MVP Boundary

**In scope for MVP:**
- Secure login
- Session management

**Explicitly deferred:**
- *To be determined during interview.*

---

**Status**: Ready for Architect phase
"""
    )

    return project_root, plan_dir


# ==============================================================================
# PipelineConfig Tests
# ==============================================================================


class TestPipelineConfig:
    """Test PipelineConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = PipelineConfig()
        assert config.spec_path is None
        assert config.slug is None
        assert config.depth == "standard"
        assert config.mindset == "mvp"
        assert config.scale == "team"
        assert config.verbose is False
        assert config.move_spec is True
        assert config.continue_from is None

    def test_custom_values(self, tmp_path: Path) -> None:
        """Test custom configuration values."""
        spec_path = tmp_path / "spec.md"
        spec_path.write_text("# Spec")

        config = PipelineConfig(
            spec_path=spec_path,
            slug="custom-slug",
            depth="deep",
            mindset="production",
            scale="product",
            verbose=True,
            move_spec=False,
        )

        assert config.spec_path == spec_path
        assert config.slug == "custom-slug"
        assert config.depth == "deep"
        assert config.mindset == "production"
        assert config.scale == "product"
        assert config.verbose is True
        assert config.move_spec is False


# ==============================================================================
# PlanPipeline Validation Tests
# ==============================================================================


class TestPlanPipelineValidation:
    """Test PlanPipeline configuration validation."""

    def test_requires_spec_or_continue(self, tmp_path: Path) -> None:
        """Test that pipeline requires either spec_path or continue_from."""
        config = PipelineConfig()  # Neither provided

        with pytest.raises(PipelineConfigError, match="requires either"):
            PlanPipeline(tmp_path, config)

    def test_validates_continue_from_exists(self, tmp_path: Path) -> None:
        """Test that continue_from must point to existing plan."""
        plan_dir = tmp_path / "plans" / "nonexistent"
        plan_dir.mkdir(parents=True)
        # No plan.json

        config = PipelineConfig(continue_from=plan_dir)

        with pytest.raises(PipelineConfigError, match="plan.json not found"):
            PlanPipeline(tmp_path, config)

    def test_validates_depth(self, tmp_path: Path) -> None:
        """Test that depth is validated."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec")

        config = PipelineConfig(spec_path=spec_file, depth="invalid")

        with pytest.raises(PipelineConfigError, match="Invalid depth"):
            PlanPipeline(tmp_path, config)

    def test_validates_mindset(self, tmp_path: Path) -> None:
        """Test that mindset is validated."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec")

        config = PipelineConfig(spec_path=spec_file, mindset="invalid")

        with pytest.raises(PipelineConfigError, match="Invalid mindset"):
            PlanPipeline(tmp_path, config)

    def test_validates_scale(self, tmp_path: Path) -> None:
        """Test that scale is validated."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec")

        config = PipelineConfig(spec_path=spec_file, scale="invalid")

        with pytest.raises(PipelineConfigError, match="Invalid scale"):
            PlanPipeline(tmp_path, config)


# ==============================================================================
# PlanPipeline.run() Tests
# ==============================================================================


class TestPlanPipelineRun:
    """Test PlanPipeline.run() method."""

    def test_run_full_pipeline(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test running the full pipeline from spec to itemized plan."""
        project_root, spec_file = project_with_spec

        config = PipelineConfig(
            spec_path=spec_file,
            move_spec=False,  # Don't move spec in test
        )
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()

        assert result.success is True
        assert result.plan.is_complete is True
        assert result.plan.slug == "my-feature"
        assert len(result.stage_results) == 3

        # Check all stages completed
        stages_completed = [r.stage for r in result.stage_results if r.success]
        assert PlanStage.ORIENT in stages_completed
        assert PlanStage.ARCHITECT in stages_completed
        assert PlanStage.ITEMIZE in stages_completed

        # Check output files exist
        plan_dir = result.plan_dir
        assert (plan_dir / "plan.json").exists()
        assert (plan_dir / "orientation.md").exists()
        assert (plan_dir / "architecture.md").exists()
        assert (plan_dir / "itemized-plan.md").exists()

        # Check results are populated
        assert result.orient_result is not None
        assert result.architect_result is not None
        assert result.itemize_result is not None

    def test_run_moves_spec(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that pipeline moves spec from researching/ to planned/."""
        project_root, spec_file = project_with_spec

        config = PipelineConfig(
            spec_path=spec_file,
            move_spec=True,
        )
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()

        assert result.success is True
        assert result.spec_moved is True
        assert result.spec_new_path is not None

        # Original location should be gone
        assert not spec_file.exists()

        # New location should exist
        planned_dir = project_root / "specs" / "planned"
        assert (planned_dir / "my-feature.md").exists()
        assert result.spec_new_path == planned_dir / "my-feature.md"

    def test_run_no_move_spec(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that pipeline can skip moving spec."""
        project_root, spec_file = project_with_spec

        config = PipelineConfig(
            spec_path=spec_file,
            move_spec=False,
        )
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()

        assert result.success is True
        assert result.spec_moved is False

        # Original location should still exist
        assert spec_file.exists()

    def test_run_continues_partial_plan(
        self, project_with_partial_plan: tuple[Path, Path]
    ) -> None:
        """Test continuing from a partially complete plan."""
        project_root, plan_dir = project_with_partial_plan

        config = PipelineConfig(
            continue_from=plan_dir,
            move_spec=False,
        )
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()

        assert result.success is True
        assert result.plan.is_complete is True

        # Should have only run architect and itemize (orient was already complete)
        assert len(result.stage_results) == 2
        stages_run = [r.stage for r in result.stage_results]
        assert PlanStage.ORIENT not in stages_run
        assert PlanStage.ARCHITECT in stages_run
        assert PlanStage.ITEMIZE in stages_run

    def test_run_with_progress_callback(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that progress callback is called during run."""
        project_root, spec_file = project_with_spec

        progress_events: list[tuple[PlanStage, str, str]] = []

        def on_progress(stage: PlanStage, status: str, message: str) -> None:
            progress_events.append((stage, status, message))

        config = PipelineConfig(
            spec_path=spec_file,
            move_spec=False,
        )
        pipeline = PlanPipeline(project_root, config, on_progress)
        result = pipeline.run()

        assert result.success is True

        # Should have starting and complete events for each stage
        starting_events = [(s, st) for s, st, _ in progress_events if st == "starting"]
        complete_events = [(s, st) for s, st, _ in progress_events if st == "complete"]

        assert len(starting_events) == 3
        assert len(complete_events) == 3

    def test_run_with_custom_slug(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test running pipeline with custom slug."""
        project_root, spec_file = project_with_spec

        config = PipelineConfig(
            spec_path=spec_file,
            slug="custom-plan-name",
            move_spec=False,
        )
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run()

        assert result.success is True
        assert result.plan.slug == "custom-plan-name"
        assert result.plan_dir.name == "custom-plan-name"


class TestPlanPipelineRunSingleStage:
    """Test PlanPipeline.run_single_stage() method."""

    def test_run_single_orient(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test running only orient stage."""
        project_root, spec_file = project_with_spec

        config = PipelineConfig(
            spec_path=spec_file,
            move_spec=False,
        )
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run_single_stage(PlanStage.ORIENT)

        assert result.success is True
        assert len(result.stage_results) == 1
        assert result.stage_results[0].stage == PlanStage.ORIENT
        assert result.orient_result is not None
        assert result.architect_result is None
        assert result.itemize_result is None

    def test_run_single_architect(
        self, project_with_partial_plan: tuple[Path, Path]
    ) -> None:
        """Test running only architect stage."""
        project_root, plan_dir = project_with_partial_plan

        config = PipelineConfig(
            continue_from=plan_dir,
            move_spec=False,
        )
        pipeline = PlanPipeline(project_root, config)
        result = pipeline.run_single_stage(PlanStage.ARCHITECT)

        assert result.success is True
        assert len(result.stage_results) == 1
        assert result.stage_results[0].stage == PlanStage.ARCHITECT
        assert result.architect_result is not None


# ==============================================================================
# StageResult and PipelineResult Tests
# ==============================================================================


class TestStageResult:
    """Test StageResult dataclass."""

    def test_stage_result_success(self) -> None:
        """Test successful stage result."""
        result = StageResult(
            stage=PlanStage.ORIENT,
            success=True,
            duration_seconds=1.5,
        )

        assert result.stage == PlanStage.ORIENT
        assert result.success is True
        assert result.error is None
        assert result.duration_seconds == 1.5

    def test_stage_result_failure(self) -> None:
        """Test failed stage result."""
        result = StageResult(
            stage=PlanStage.ARCHITECT,
            success=False,
            error="Something went wrong",
            duration_seconds=0.5,
        )

        assert result.stage == PlanStage.ARCHITECT
        assert result.success is False
        assert result.error == "Something went wrong"


class TestPipelineResult:
    """Test PipelineResult dataclass."""

    def test_duration_seconds(self, tmp_path: Path) -> None:
        """Test duration calculation."""
        from datetime import datetime, timedelta, timezone

        started = datetime.now(timezone.utc)
        completed = started + timedelta(seconds=5.5)

        result = PipelineResult(
            success=True,
            plan=None,  # type: ignore
            plan_dir=tmp_path,
            started_at=started,
            completed_at=completed,
        )

        assert abs(result.duration_seconds - 5.5) < 0.001

    def test_stages_completed(self, tmp_path: Path) -> None:
        """Test stages_completed property."""
        result = PipelineResult(
            success=True,
            plan=None,  # type: ignore
            plan_dir=tmp_path,
            stage_results=[
                StageResult(PlanStage.ORIENT, success=True),
                StageResult(PlanStage.ARCHITECT, success=True),
                StageResult(PlanStage.ITEMIZE, success=False, error="Failed"),
            ],
        )

        completed = result.stages_completed
        assert PlanStage.ORIENT in completed
        assert PlanStage.ARCHITECT in completed
        assert PlanStage.ITEMIZE not in completed


# ==============================================================================
# Convenience Function Tests
# ==============================================================================


class TestConvenienceFunctions:
    """Test run_pipeline and continue_pipeline convenience functions."""

    def test_run_pipeline_function(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test run_pipeline convenience function."""
        project_root, spec_file = project_with_spec

        result = run_pipeline(
            project_root=project_root,
            spec_path=spec_file,
            move_spec=False,
        )

        assert result.success is True
        assert result.plan.is_complete is True

    def test_continue_pipeline_function(
        self, project_with_partial_plan: tuple[Path, Path]
    ) -> None:
        """Test continue_pipeline convenience function."""
        project_root, plan_dir = project_with_partial_plan

        result = continue_pipeline(
            project_root=project_root,
            plan_dir=plan_dir,
            move_spec=False,
        )

        assert result.success is True
        assert result.plan.is_complete is True


# ==============================================================================
# CLI Integration Tests
# ==============================================================================


class TestPlanRunCLI:
    """Test 'cub plan run' CLI command."""

    def test_run_command_help(self) -> None:
        """Test that run command shows help."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["plan", "run", "--help"])

        assert result.exit_code == 0
        assert "orient" in result.output.lower()
        assert "architect" in result.output.lower()
        assert "itemize" in result.output.lower()

    def test_run_command_requires_spec(self) -> None:
        """Test that run command requires spec or continue."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(app, ["plan", "run"])
            assert result.exit_code == 1
            assert "no spec provided" in result.output.lower()

    def test_run_command_with_spec(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test run command with a spec file."""
        from typer.testing import CliRunner

        from cub.cli import app

        project_root, spec_file = project_with_spec
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "plan", "run",
                str(spec_file),
                "-p", str(project_root),
                "--no-move-spec",
            ],
        )

        assert result.exit_code == 0
        assert "pipeline complete" in result.output.lower()

        # Check outputs were created
        plan_dir = project_root / "plans" / "my-feature"
        assert (plan_dir / "orientation.md").exists()
        assert (plan_dir / "architecture.md").exists()
        assert (plan_dir / "itemized-plan.md").exists()

    def test_run_command_with_continue(
        self, project_with_partial_plan: tuple[Path, Path]
    ) -> None:
        """Test run command with --continue flag."""
        from typer.testing import CliRunner

        from cub.cli import app

        project_root, plan_dir = project_with_partial_plan
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "plan", "run",
                "--continue", "my-feature",
                "-p", str(project_root),
                "--no-move-spec",
            ],
        )

        assert result.exit_code == 0
        assert "pipeline complete" in result.output.lower()

    def test_run_command_verbose(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test run command with verbose flag."""
        from typer.testing import CliRunner

        from cub.cli import app

        project_root, spec_file = project_with_spec
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "plan", "run",
                str(spec_file),
                "-p", str(project_root),
                "--no-move-spec",
                "-v",
            ],
        )

        assert result.exit_code == 0
        # Verbose output includes stages and summary
        assert "stages completed" in result.output.lower() or "epics" in result.output.lower()

    def test_run_command_nonexistent_spec(self, tmp_path: Path) -> None:
        """Test run command with nonexistent spec."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "plan", "run",
                "nonexistent.md",
                "-p", str(tmp_path),
            ],
        )

        assert result.exit_code == 1
        assert "spec not found" in result.output.lower()

    def test_run_command_nonexistent_continue(self, tmp_path: Path) -> None:
        """Test run command with nonexistent continue target."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "plan", "run",
                "--continue", "nonexistent-plan",
                "-p", str(tmp_path),
            ],
        )

        assert result.exit_code == 1
        assert "plan not found" in result.output.lower()


# ==============================================================================
# Step Detection Tests
# ==============================================================================


class TestDetectPipelineSteps:
    """Test detect_pipeline_steps function."""

    def _make_plan_dir(
        self,
        tmp_path: Path,
        *,
        stages: dict[str, str] | None = None,
        artifacts: dict[str, str] | None = None,
        status: str = "in_progress",
    ) -> Path:
        """Helper to create a plan directory with specified state."""
        plan_dir = tmp_path / "plans" / "test-plan"
        plan_dir.mkdir(parents=True)

        if stages is None:
            stages = {
                "orient": "pending",
                "architect": "pending",
                "itemize": "pending",
            }

        plan_json = {
            "slug": "test-plan",
            "project": "test",
            "status": status,
            "stages": stages,
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))

        if artifacts:
            for filename, content in artifacts.items():
                (plan_dir / filename).write_text(content)

        return plan_dir

    def test_all_incomplete(self, tmp_path: Path) -> None:
        """Test detection when no steps are done."""
        plan_dir = self._make_plan_dir(tmp_path, status="pending")
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.plan_slug == "test-plan"
        assert summary.plan_exists is True
        assert summary.all_complete is False
        assert summary.next_step == PlanStage.ORIENT
        assert len(summary.steps) == 3
        assert all(
            s.status == StepDetectionStatus.INCOMPLETE for s in summary.steps
        )

    def test_orient_complete(self, tmp_path: Path) -> None:
        """Test detection when only orient is complete."""
        plan_dir = self._make_plan_dir(
            tmp_path,
            stages={"orient": "complete", "architect": "pending", "itemize": "pending"},
            artifacts={"orientation.md": "# Orientation\n" + "x" * 200},
        )
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.steps[0].status == StepDetectionStatus.COMPLETE
        assert summary.steps[1].status == StepDetectionStatus.INCOMPLETE
        assert summary.steps[2].status == StepDetectionStatus.INCOMPLETE
        assert summary.next_step == PlanStage.ARCHITECT
        assert summary.all_complete is False

    def test_all_complete(self, tmp_path: Path) -> None:
        """Test detection when all steps are complete."""
        plan_dir = self._make_plan_dir(
            tmp_path,
            stages={"orient": "complete", "architect": "complete", "itemize": "complete"},
            artifacts={
                "orientation.md": "# Orientation\n" + "x" * 200,
                "architecture.md": "# Architecture\n" + "x" * 200,
                "itemized-plan.md": "# Tasks\n" + "x" * 200,
            },
            status="complete",
        )
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.all_complete is True
        assert summary.next_step is None
        assert all(
            s.status == StepDetectionStatus.COMPLETE for s in summary.steps
        )

    def test_corrupted_missing_artifact(self, tmp_path: Path) -> None:
        """Test detection when plan.json says complete but artifact is missing."""
        plan_dir = self._make_plan_dir(
            tmp_path,
            stages={"orient": "complete", "architect": "pending", "itemize": "pending"},
            # No orientation.md artifact!
        )
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.steps[0].status == StepDetectionStatus.CORRUPTED
        assert "missing" in summary.steps[0].detail
        assert summary.has_corruption is True
        assert summary.next_step == PlanStage.ORIENT

    def test_corrupted_tiny_artifact(self, tmp_path: Path) -> None:
        """Test detection when artifact file is suspiciously small."""
        plan_dir = self._make_plan_dir(
            tmp_path,
            stages={"orient": "complete", "architect": "pending", "itemize": "pending"},
            artifacts={"orientation.md": "x"},  # Too small
        )
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.steps[0].status == StepDetectionStatus.CORRUPTED
        assert "small" in summary.steps[0].detail

    def test_in_progress_stage(self, tmp_path: Path) -> None:
        """Test detection of in-progress stages."""
        plan_dir = self._make_plan_dir(
            tmp_path,
            stages={
                "orient": "complete",
                "architect": "in_progress",
                "itemize": "pending",
            },
            artifacts={"orientation.md": "# Orientation\n" + "x" * 200},
        )
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.steps[0].status == StepDetectionStatus.COMPLETE
        assert summary.steps[1].status == StepDetectionStatus.IN_PROGRESS
        assert summary.next_step == PlanStage.ARCHITECT

    def test_artifact_exists_but_plan_says_pending(self, tmp_path: Path) -> None:
        """Test detection when artifact exists but plan.json hasn't been updated."""
        plan_dir = self._make_plan_dir(
            tmp_path,
            stages={"orient": "pending", "architect": "pending", "itemize": "pending"},
            artifacts={"orientation.md": "# Orientation\n" + "x" * 200},
        )
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        # Should detect as in-progress (partial completion)
        assert summary.steps[0].status == StepDetectionStatus.IN_PROGRESS
        assert "pending" in summary.steps[0].detail

    def test_missing_plan_json(self, tmp_path: Path) -> None:
        """Test detection when plan.json doesn't exist but artifact does."""
        plan_dir = tmp_path / "plans" / "orphan-plan"
        plan_dir.mkdir(parents=True)

        # Create an artifact without plan.json
        (plan_dir / "orientation.md").write_text("# Orientation\n" + "x" * 200)

        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.plan_exists is False
        # Without plan.json, artifact with sufficient size → COMPLETE
        assert summary.steps[0].status == StepDetectionStatus.COMPLETE
        assert "no plan.json" in summary.steps[0].detail

    def test_corrupted_plan_json(self, tmp_path: Path) -> None:
        """Test detection when plan.json is corrupted."""
        plan_dir = tmp_path / "plans" / "bad-plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan.json").write_text("{not valid json")
        (plan_dir / "orientation.md").write_text("# Orientation\n" + "x" * 200)

        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.plan_exists is True  # File exists, just can't parse
        # Should still detect artifacts
        assert summary.plan_slug == "bad-plan"

    def test_staged_plan(self, tmp_path: Path) -> None:
        """Test detection of a staged plan."""
        plan_dir = self._make_plan_dir(
            tmp_path,
            stages={"orient": "complete", "architect": "complete", "itemize": "complete"},
            artifacts={
                "orientation.md": "# Orientation\n" + "x" * 200,
                "architecture.md": "# Architecture\n" + "x" * 200,
                "itemized-plan.md": "# Tasks\n" + "x" * 200,
            },
            status="staged",
        )
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        assert summary.is_staged is True
        assert summary.all_complete is True

    def test_inferred_project_root(self, tmp_path: Path) -> None:
        """Test that project root is inferred from plan_dir when not provided."""
        plan_dir = self._make_plan_dir(tmp_path)
        summary = detect_pipeline_steps(plan_dir)

        assert summary.plan_slug == "test-plan"
        assert summary.plan_exists is True

    def test_completed_steps_property(self, tmp_path: Path) -> None:
        """Test the completed_steps property."""
        plan_dir = self._make_plan_dir(
            tmp_path,
            stages={"orient": "complete", "architect": "complete", "itemize": "pending"},
            artifacts={
                "orientation.md": "# Orientation\n" + "x" * 200,
                "architecture.md": "# Architecture\n" + "x" * 200,
            },
        )
        summary = detect_pipeline_steps(plan_dir, tmp_path)

        completed = summary.completed_steps
        assert len(completed) == 2
        assert completed[0].stage == PlanStage.ORIENT
        assert completed[1].stage == PlanStage.ARCHITECT


class TestStepDetectionStatus:
    """Test StepDetectionStatus enum values."""

    def test_enum_values(self) -> None:
        """Test that all expected status values exist."""
        assert StepDetectionStatus.COMPLETE == "complete"
        assert StepDetectionStatus.IN_PROGRESS == "in_progress"
        assert StepDetectionStatus.INCOMPLETE == "incomplete"
        assert StepDetectionStatus.CORRUPTED == "corrupted"


class TestPipelineStepSummary:
    """Test PipelineStepSummary dataclass properties."""

    def test_all_complete_property(self, tmp_path: Path) -> None:
        """Test all_complete property with mixed steps."""
        steps = [
            StepInfo(
                stage=PlanStage.ORIENT,
                status=StepDetectionStatus.COMPLETE,
                artifact_path=tmp_path / "orientation.md",
                artifact_exists=True,
            ),
            StepInfo(
                stage=PlanStage.ARCHITECT,
                status=StepDetectionStatus.INCOMPLETE,
                artifact_path=tmp_path / "architecture.md",
                artifact_exists=False,
            ),
            StepInfo(
                stage=PlanStage.ITEMIZE,
                status=StepDetectionStatus.INCOMPLETE,
                artifact_path=tmp_path / "itemized-plan.md",
                artifact_exists=False,
            ),
        ]
        summary = PipelineStepSummary(
            plan_slug="test",
            plan_dir=tmp_path,
            steps=steps,
            plan_exists=True,
            next_step=PlanStage.ARCHITECT,
        )
        assert summary.all_complete is False

    def test_has_corruption_property(self, tmp_path: Path) -> None:
        """Test has_corruption property."""
        steps = [
            StepInfo(
                stage=PlanStage.ORIENT,
                status=StepDetectionStatus.CORRUPTED,
                artifact_path=tmp_path / "orientation.md",
                artifact_exists=False,
            ),
            StepInfo(
                stage=PlanStage.ARCHITECT,
                status=StepDetectionStatus.INCOMPLETE,
                artifact_path=tmp_path / "architecture.md",
                artifact_exists=False,
            ),
            StepInfo(
                stage=PlanStage.ITEMIZE,
                status=StepDetectionStatus.INCOMPLETE,
                artifact_path=tmp_path / "itemized-plan.md",
                artifact_exists=False,
            ),
        ]
        summary = PipelineStepSummary(
            plan_slug="test",
            plan_dir=tmp_path,
            steps=steps,
            plan_exists=True,
            next_step=PlanStage.ORIENT,
        )
        assert summary.has_corruption is True


class TestPlanRunCLIStepSummary:
    """Test that plan run CLI shows step summary."""

    def test_run_shows_step_summary_on_success(
        self, project_with_spec: tuple[Path, Path]
    ) -> None:
        """Test that successful run shows pipeline status summary."""
        from typer.testing import CliRunner

        from cub.cli import app

        project_root, spec_file = project_with_spec
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "plan", "run",
                str(spec_file),
                "-p", str(project_root),
                "--no-move-spec",
            ],
        )

        assert result.exit_code == 0
        assert "pipeline status" in result.output.lower()
        assert "complete" in result.output.lower()

    def test_continue_shows_step_summary(
        self, project_with_partial_plan: tuple[Path, Path]
    ) -> None:
        """Test that --continue run shows step summary."""
        from typer.testing import CliRunner

        from cub.cli import app

        project_root, plan_dir = project_with_partial_plan
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "plan", "run",
                "--continue", "my-feature",
                "-p", str(project_root),
                "--no-move-spec",
            ],
        )

        assert result.exit_code == 0
        assert "pipeline status" in result.output.lower()
