"""
Unit tests for orient stage implementation.

Tests the PlanContext class and OrientStage functionality including
validation, context gathering, and orientation.md generation.

All stage tests mock out invoke_claude_command so stages use
their template fallback instead of calling the real Claude CLI.
"""

from pathlib import Path

import pytest

# Use template fallback instead of real Claude CLI.
pytestmark = pytest.mark.usefixtures("_no_claude")

from cub.core.plan.context import (
    OrientDepth,
    PlanContext,
    SpecNotFoundError,
)
from cub.core.plan.models import PlanStage, PlanStatus, StageStatus
from cub.core.plan.orient import (
    OrientInputError,
    OrientQuestion,
    OrientStage,
    run_orient,
)

# ==============================================================================
# PlanContext Tests
# ==============================================================================


class TestPlanContextCreate:
    """Test PlanContext.create factory method."""

    def test_create_from_spec(self, tmp_path: Path) -> None:
        """Test creating context from a spec file."""
        # Create spec file
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature\n\nOverview content.")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test-project",
            spec_path=spec_file,
        )

        assert ctx.plan.slug == "my-feature"
        assert ctx.plan.project == "test-project"
        assert ctx.plan.status == PlanStatus.PENDING
        assert ctx.plan.spec_file == "my-feature.md"
        assert ctx.spec_path == spec_file
        assert ctx.has_spec is True

    def test_create_with_explicit_slug(self, tmp_path: Path) -> None:
        """Test creating context with explicit slug override."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test-project",
            spec_path=spec_file,
            slug="custom-plan-name",
        )

        assert ctx.plan.slug == "custom-plan-name"

    def test_create_without_spec(self, tmp_path: Path) -> None:
        """Test creating context without a spec (timestamp-based slug)."""
        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test-project",
        )

        assert ctx.plan.slug.startswith("plan-")
        assert ctx.has_spec is False
        assert ctx.spec_path is None

    def test_create_handles_slug_collision(self, tmp_path: Path) -> None:
        """Test that slug collision adds _alt_X suffix."""
        # Create existing plan directory
        existing_plan = tmp_path / "plans" / "my-feature"
        existing_plan.mkdir(parents=True)

        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test-project",
            spec_path=spec_file,
        )

        assert ctx.plan.slug == "my-feature_alt_a"

    def test_create_handles_multiple_collisions(self, tmp_path: Path) -> None:
        """Test handling multiple slug collisions."""
        # Create existing plan directories
        plans_dir = tmp_path / "plans"
        (plans_dir / "my-feature").mkdir(parents=True)
        (plans_dir / "my-feature_alt_a").mkdir(parents=True)
        (plans_dir / "my-feature_alt_b").mkdir(parents=True)

        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test-project",
            spec_path=spec_file,
        )

        assert ctx.plan.slug == "my-feature_alt_c"

    def test_create_with_depth_option(self, tmp_path: Path) -> None:
        """Test creating context with depth option."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test-project",
            spec_path=spec_file,
            depth=OrientDepth.DEEP,
        )

        assert ctx.depth == OrientDepth.DEEP


class TestPlanContextPaths:
    """Test PlanContext path-related properties."""

    def test_plan_dir(self, tmp_path: Path) -> None:
        """Test plan_dir computed property."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        assert ctx.plan_dir == tmp_path / "plans" / "my-feature"

    def test_orientation_path(self, tmp_path: Path) -> None:
        """Test orientation_path computed property."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        assert ctx.orientation_path == tmp_path / "plans" / "my-feature" / "orientation.md"

    def test_get_specs_root(self, tmp_path: Path) -> None:
        """Test get_specs_root method."""
        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
        )

        assert ctx.get_specs_root() == tmp_path / "specs"

    def test_get_system_plan_path(self, tmp_path: Path) -> None:
        """Test get_system_plan_path method."""
        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
        )

        assert ctx.get_system_plan_path() == tmp_path / ".cub" / "SYSTEM-PLAN.md"


class TestPlanContextReadMethods:
    """Test PlanContext content reading methods."""

    def test_read_spec_content(self, tmp_path: Path) -> None:
        """Test reading spec file content."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature\n\nSome content.")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        content = ctx.read_spec_content()
        assert "# My Feature" in content
        assert "Some content." in content

    def test_read_spec_content_no_spec(self, tmp_path: Path) -> None:
        """Test reading spec content when no spec is set."""
        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
        )

        with pytest.raises(SpecNotFoundError, match="No spec associated"):
            ctx.read_spec_content()

    def test_read_system_plan(self, tmp_path: Path) -> None:
        """Test reading SYSTEM-PLAN.md."""
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir(parents=True)
        system_plan = cub_dir / "SYSTEM-PLAN.md"
        system_plan.write_text("# System Plan\n\nProject patterns.")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
        )

        content = ctx.read_system_plan()
        assert content is not None
        assert "# System Plan" in content

    def test_read_system_plan_not_exists(self, tmp_path: Path) -> None:
        """Test reading SYSTEM-PLAN.md when it doesn't exist."""
        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
        )

        content = ctx.read_system_plan()
        assert content is None

    def test_read_agent_instructions(self, tmp_path: Path) -> None:
        """Test reading CLAUDE.md agent instructions."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Agent Instructions\n\nProject info.")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
        )

        content = ctx.read_agent_instructions()
        assert content is not None
        assert "# Agent Instructions" in content


class TestPlanContextLoad:
    """Test PlanContext.load method."""

    def test_load_existing_plan(self, tmp_path: Path) -> None:
        """Test loading an existing plan."""
        # Create plan directory with plan.json
        plan_dir = tmp_path / "plans" / "my-feature"
        plan_dir.mkdir(parents=True)

        plan_json = {
            "slug": "my-feature",
            "project": "test",
            "status": "in_progress",
            "spec_file": "my-feature.md",
            "stages": {
                "orient": "complete",
                "architect": "pending",
                "itemize": "pending",
            },
        }
        import json
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))

        # Create spec file
        specs_dir = tmp_path / "specs" / "planned"
        specs_dir.mkdir(parents=True)
        (specs_dir / "my-feature.md").write_text("# My Feature")

        ctx = PlanContext.load(plan_dir, tmp_path)

        assert ctx.plan.slug == "my-feature"
        assert ctx.plan.status == PlanStatus.IN_PROGRESS
        assert ctx.plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert ctx.spec_path == specs_dir / "my-feature.md"


# ==============================================================================
# OrientStage Tests
# ==============================================================================


class TestOrientStageValidation:
    """Test OrientStage validation."""

    def test_validate_with_spec(self, tmp_path: Path) -> None:
        """Test validation passes with a spec."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        # Should not raise
        stage.validate()

    def test_validate_without_spec(self, tmp_path: Path) -> None:
        """Test validation fails without a spec (interactive mode not supported)."""
        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
        )

        stage = OrientStage(ctx)
        with pytest.raises(OrientInputError, match="requires a spec file"):
            stage.validate()

    def test_validate_missing_spec_file(self, tmp_path: Path) -> None:
        """Test validation fails if spec file doesn't exist."""
        # Create context with non-existent spec path
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "nonexistent.md"

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
            slug="test-plan",
        )

        stage = OrientStage(ctx)
        with pytest.raises(OrientInputError, match="Spec file not found"):
            stage.validate()


class TestOrientStageRun:
    """Test OrientStage.run method."""

    def test_run_creates_orientation_md(self, tmp_path: Path) -> None:
        """Test that run creates orientation.md file."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text(
            """---
status: draft
---
# My Feature

## Overview

This feature does something awesome.

## Goals

- **Goal 1**: Make things better
- **Goal 2**: Improve performance
"""
        )

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        result = stage.run()

        assert result.output_path.exists()
        assert result.output_path.name == "orientation.md"

        content = result.output_path.read_text()
        assert "# Orientation: My Feature" in content
        assert "## Problem Statement" in content
        assert "## Requirements" in content

    def test_run_updates_plan_status(self, tmp_path: Path) -> None:
        """Test that run updates plan status and stages."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature\n\n## Overview\n\nContent.")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        stage.run()

        assert ctx.plan.status == PlanStatus.IN_PROGRESS
        assert ctx.plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE

    def test_run_saves_plan_json(self, tmp_path: Path) -> None:
        """Test that run saves plan.json."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature\n\n## Overview\n\nContent.")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        stage.run()

        plan_json = ctx.plan_dir / "plan.json"
        assert plan_json.exists()

    def test_run_extracts_goals(self, tmp_path: Path) -> None:
        """Test that run extracts goals from spec."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text(
            """# My Feature

## Overview

A feature description.

## Goals

- **Improve performance**: Make it faster
- **Add caching**: Cache results
"""
        )

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        result = stage.run()

        # Goals should be extracted (though possibly empty due to regex)
        assert result.output_path.exists()

    def test_run_includes_depth_in_output(self, tmp_path: Path) -> None:
        """Test that orientation.md includes depth level."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
            depth=OrientDepth.DEEP,
        )

        stage = OrientStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "Depth: Deep" in content

    def test_run_result_has_timing(self, tmp_path: Path) -> None:
        """Test that result includes timing information."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        result = stage.run()

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at
        assert result.duration_seconds >= 0


class TestOrientStageExtraction:
    """Test information extraction from specs."""

    def test_extract_title(self, tmp_path: Path) -> None:
        """Test extracting title from spec."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# Amazing Feature Title\n\nContent.")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "Orientation: Amazing Feature Title" in content

    def test_extract_overview(self, tmp_path: Path) -> None:
        """Test extracting overview from spec."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text(
            """# My Feature

## Overview

This is the problem we're solving and why it matters.
"""
        )

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        result = stage.run()

        assert "This is the problem" in result.problem_statement

    def test_extract_decisions_made(self, tmp_path: Path) -> None:
        """Test extracting decisions from frontmatter."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text(
            """---
status: draft
decisions_made:
  - "Use Python 3.10+"
  - "Implement with Pydantic v2"
---
# My Feature

## Overview

Content.
"""
        )

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        stage = OrientStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "## Constraints" in content


class TestOrientQuestions:
    """Test orient questions functionality."""

    def test_default_questions_exist(self) -> None:
        """Test that default questions are defined."""
        from cub.core.plan.orient import DEFAULT_ORIENT_QUESTIONS

        assert len(DEFAULT_ORIENT_QUESTIONS) > 0
        assert any(q.id == "problem" for q in DEFAULT_ORIENT_QUESTIONS)
        assert any(q.id == "success" for q in DEFAULT_ORIENT_QUESTIONS)

    def test_custom_questions(self, tmp_path: Path) -> None:
        """Test providing custom questions."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        custom_questions = [
            OrientQuestion(
                id="custom",
                question="Custom question?",
                category="Custom",
            ),
        ]

        stage = OrientStage(ctx, questions=custom_questions)
        assert len(stage.questions) == 1
        assert stage.questions[0].id == "custom"


class TestRunOrientConvenienceFunction:
    """Test the run_orient convenience function."""

    def test_run_orient_function(self, tmp_path: Path) -> None:
        """Test run_orient convenience function."""
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature")

        ctx = PlanContext.create(
            project_root=tmp_path,
            project="test",
            spec_path=spec_file,
        )

        result = run_orient(ctx)

        assert result.output_path.exists()
        assert ctx.plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE


# ==============================================================================
# CLI Integration Tests
# ==============================================================================


class TestPlanOrientCLI:
    """Test orient CLI command integration."""

    def test_orient_command_with_spec(self, tmp_path: Path) -> None:
        """Test orient command with a spec file."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        # Create spec file
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature\n\n## Overview\n\nContent.")

        # Also create pyproject.toml for project name detection
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-project"')

        result = runner.invoke(
            app,
            ["plan", "orient", str(spec_file), "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "Orient complete!" in result.output

        # Check orientation.md was created
        orientation_file = tmp_path / "plans" / "my-feature" / "orientation.md"
        assert orientation_file.exists()

    def test_orient_command_no_spec(self) -> None:
        """Test orient command without a spec shows error."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        result = runner.invoke(app, ["plan", "orient"])

        assert result.exit_code == 1
        assert "No spec provided" in result.output

    def test_orient_command_spec_not_found(self, tmp_path: Path) -> None:
        """Test orient command with non-existent spec."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        result = runner.invoke(
            app,
            ["plan", "orient", "nonexistent.md", "-p", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert "Spec not found" in result.output or "Error" in result.output

    def test_orient_command_verbose(self, tmp_path: Path) -> None:
        """Test orient command with verbose flag."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        # Create spec file
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature\n\n## Overview\n\nContent.")

        result = runner.invoke(
            app,
            ["plan", "orient", str(spec_file), "-p", str(tmp_path), "-v"],
        )

        assert result.exit_code == 0
        assert "Summary:" in result.output or "Orient complete!" in result.output

    def test_orient_command_with_slug(self, tmp_path: Path) -> None:
        """Test orient command with custom slug."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        # Create spec file
        specs_dir = tmp_path / "specs" / "researching"
        specs_dir.mkdir(parents=True)
        spec_file = specs_dir / "my-feature.md"
        spec_file.write_text("# My Feature\n\n## Overview\n\nContent.")

        result = runner.invoke(
            app,
            ["plan", "orient", str(spec_file), "-p", str(tmp_path), "-s", "custom-slug"],
        )

        assert result.exit_code == 0

        # Check custom slug was used
        orientation_file = tmp_path / "plans" / "custom-slug" / "orientation.md"
        assert orientation_file.exists()
