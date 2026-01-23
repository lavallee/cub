"""
Unit tests for architect stage implementation.

Tests the ArchitectStage class functionality including validation,
context gathering, tech stack inference, and architecture.md generation.
"""

import json
from pathlib import Path

import pytest

from cub.core.plan.architect import (
    ArchitectInputError,
    ArchitectQuestion,
    ArchitectResult,
    ArchitectStage,
    Component,
    ImplementationPhase,
    TechnicalRisk,
    TechStackChoice,
    run_architect,
)
from cub.core.plan.context import PlanContext
from cub.core.plan.models import PlanStage, PlanStatus, StageStatus

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def plan_with_orient(tmp_path: Path) -> tuple[Path, PlanContext]:
    """Create a plan with completed orient stage."""
    # Create plan directory
    plan_dir = tmp_path / "plans" / "my-feature"
    plan_dir.mkdir(parents=True)

    # Create plan.json with orient complete
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
    (plan_dir / "plan.json").write_text(json.dumps(plan_json))

    # Create orientation.md
    orientation_content = """# Orientation: My Feature

> Source: [my-feature.md](../../specs/researching/my-feature.md)
> Generated: 2026-01-20
> Depth: Standard

## Problem Statement

This feature solves the problem of users needing better task management.
It enables efficient workflow automation.

## Requirements

### P0 (Must Have)

- **Task tracking**: Track tasks in a structured way
- **Progress reporting**: Show progress to users
- **CLI interface**: Command-line access

### P1 (Should Have)

- Integration with external systems

### P2 (Nice to Have)

- Web dashboard

## Constraints

| Constraint | Detail |
|------------|--------|
| Python version | 3.10+ |
| Type checking | mypy strict mode |

## Open Questions

1. How should we handle task dependencies?

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Scope creep | High | Medium | Strict MVP boundary |

## MVP Boundary

**In scope for MVP:**
- Task tracking
- Progress reporting
- CLI interface

**Explicitly deferred:**
- Web dashboard
- Advanced analytics

---

**Status**: Ready for Architect phase
"""
    (plan_dir / "orientation.md").write_text(orientation_content)

    # Create spec file
    specs_dir = tmp_path / "specs" / "researching"
    specs_dir.mkdir(parents=True)
    (specs_dir / "my-feature.md").write_text("# My Feature\n\n## Overview\n\nFeature overview.")

    # Load context
    ctx = PlanContext.load(plan_dir, tmp_path)
    return tmp_path, ctx


@pytest.fixture
def plan_without_orient(tmp_path: Path) -> tuple[Path, PlanContext]:
    """Create a plan without completed orient stage."""
    # Create plan directory
    plan_dir = tmp_path / "plans" / "incomplete-plan"
    plan_dir.mkdir(parents=True)

    # Create plan.json with orient pending
    plan_json = {
        "slug": "incomplete-plan",
        "project": "test",
        "status": "pending",
        "stages": {
            "orient": "pending",
            "architect": "pending",
            "itemize": "pending",
        },
    }
    (plan_dir / "plan.json").write_text(json.dumps(plan_json))

    # Load context
    ctx = PlanContext.load(plan_dir, tmp_path)
    return tmp_path, ctx


# ==============================================================================
# ArchitectStage Validation Tests
# ==============================================================================


class TestArchitectStageValidation:
    """Test ArchitectStage validation."""

    def test_validate_with_completed_orient(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test validation passes when orient is complete."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        # Should not raise
        stage.validate()

    def test_validate_without_orient(
        self, plan_without_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test validation fails when orient is not complete."""
        _, ctx = plan_without_orient
        stage = ArchitectStage(ctx)
        with pytest.raises(ArchitectInputError, match="requires completed orientation"):
            stage.validate()

    def test_validate_missing_orientation_file(self, tmp_path: Path) -> None:
        """Test validation fails if orientation.md is missing."""
        # Create plan with complete orient but no file
        plan_dir = tmp_path / "plans" / "missing-file"
        plan_dir.mkdir(parents=True)

        plan_json = {
            "slug": "missing-file",
            "project": "test",
            "status": "in_progress",
            "stages": {
                "orient": "complete",
                "architect": "pending",
                "itemize": "pending",
            },
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))

        ctx = PlanContext.load(plan_dir, tmp_path)
        stage = ArchitectStage(ctx)

        with pytest.raises(ArchitectInputError, match="Orientation file not found"):
            stage.validate()


# ==============================================================================
# ArchitectStage Run Tests
# ==============================================================================


class TestArchitectStageRun:
    """Test ArchitectStage.run method."""

    def test_run_creates_architecture_md(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that run creates architecture.md file."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        result = stage.run()

        assert result.output_path.exists()
        assert result.output_path.name == "architecture.md"

        content = result.output_path.read_text()
        assert "# Architecture Design:" in content
        assert "## Technical Summary" in content
        assert "## Technology Stack" in content
        assert "## Components" in content

    def test_run_updates_plan_status(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that run updates plan status and stages."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        stage.run()

        assert ctx.plan.status == PlanStatus.IN_PROGRESS
        assert ctx.plan.stages[PlanStage.ARCHITECT] == StageStatus.COMPLETE

    def test_run_saves_plan_json(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that run saves plan.json."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        stage.run()

        plan_json = ctx.plan_dir / "plan.json"
        assert plan_json.exists()

        # Verify stage status is persisted
        data = json.loads(plan_json.read_text())
        assert data["stages"]["architect"] == "complete"

    def test_run_includes_mindset_and_scale(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that architecture.md includes mindset and scale."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx, mindset="production", scale="product")
        result = stage.run()

        content = result.output_path.read_text()
        assert "**Mindset:** production" in content
        assert "**Scale:** product" in content

    def test_run_result_has_timing(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that result includes timing information."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        result = stage.run()

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at
        assert result.duration_seconds >= 0

    def test_run_extracts_problem_statement(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that run extracts problem statement from orientation."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        result = stage.run()

        assert "task management" in result.technical_summary.lower()


# ==============================================================================
# Tech Stack Inference Tests
# ==============================================================================


class TestTechStackInference:
    """Test technology stack inference."""

    def test_infer_from_agent_instructions(self, tmp_path: Path) -> None:
        """Test inferring tech stack from CLAUDE.md."""
        # Create CLAUDE.md with tech hints
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
# Agent Instructions

- Python 3.10+
- Using Typer for CLI
- Pydantic v2 for models
- pytest for testing
- mypy strict mode
""")

        # Create plan with orient complete
        plan_dir = tmp_path / "plans" / "tech-test"
        plan_dir.mkdir(parents=True)

        plan_json = {
            "slug": "tech-test",
            "project": "test",
            "status": "in_progress",
            "stages": {"orient": "complete", "architect": "pending", "itemize": "pending"},
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))
        (plan_dir / "orientation.md").write_text(
            "# Orientation: Test\n\n## Problem Statement\n\nTest problem."
        )

        ctx = PlanContext.load(plan_dir, tmp_path)
        stage = ArchitectStage(ctx)
        result = stage.run()

        # Check that tech stack was inferred
        assert any("Python" in t.choice for t in result.tech_stack)

    def test_mindset_affects_tech_stack(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that mindset affects default tech stack."""
        _, ctx = plan_with_orient

        # Run with prototype mindset
        stage = ArchitectStage(ctx, mindset="prototype")
        result = stage.run()
        content = result.output_path.read_text()

        # Prototype should mention simpler tech
        assert "prototype" in content.lower()


# ==============================================================================
# Component Generation Tests
# ==============================================================================


class TestComponentGeneration:
    """Test component generation."""

    def test_prototype_has_minimal_components(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that prototype mindset generates minimal components."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx, mindset="prototype")
        result = stage.run()

        # Prototype should have fewer components
        assert len(result.components) <= 2

    def test_production_has_more_components(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that production mindset generates more components."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx, mindset="production")
        result = stage.run()

        # Production should have more components including data layer
        assert len(result.components) >= 2
        content = result.output_path.read_text()
        assert "Data Layer" in content


# ==============================================================================
# Implementation Phase Tests
# ==============================================================================


class TestImplementationPhases:
    """Test implementation phase generation."""

    def test_phases_include_foundation(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that phases always include foundation."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        result = stage.run()

        phase_names = [p.name for p in result.implementation_phases]
        assert "Foundation" in phase_names

    def test_phases_include_core_features(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that phases include core features."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        result = stage.run()

        phase_names = [p.name for p in result.implementation_phases]
        assert "Core Features" in phase_names

    def test_production_has_polish_phase(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that production mindset has polish phase."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx, mindset="production")
        result = stage.run()

        phase_names = [p.name for p in result.implementation_phases]
        assert "Polish" in phase_names


# ==============================================================================
# Technical Risk Tests
# ==============================================================================


class TestTechnicalRisks:
    """Test technical risk generation."""

    def test_risks_included_in_output(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that risks are included in output."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "## Technical Risks" in content
        assert "| Risk |" in content

    def test_enterprise_has_security_risks(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test that enterprise mindset includes security risks."""
        _, ctx = plan_with_orient
        stage = ArchitectStage(ctx, mindset="enterprise")
        result = stage.run()

        content = result.output_path.read_text()
        assert "Security" in content or "security" in content


# ==============================================================================
# ArchitectQuestion Tests
# ==============================================================================


class TestArchitectQuestions:
    """Test architect questions functionality."""

    def test_default_questions_exist(self) -> None:
        """Test that default questions are defined."""
        from cub.core.plan.architect import DEFAULT_ARCHITECT_QUESTIONS

        assert len(DEFAULT_ARCHITECT_QUESTIONS) > 0
        assert any(q.id == "mindset" for q in DEFAULT_ARCHITECT_QUESTIONS)
        assert any(q.id == "scale" for q in DEFAULT_ARCHITECT_QUESTIONS)

    def test_custom_questions(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test providing custom questions."""
        _, ctx = plan_with_orient

        custom_questions = [
            ArchitectQuestion(
                id="custom",
                question="Custom architecture question?",
                category="Custom",
            ),
        ]

        stage = ArchitectStage(ctx, questions=custom_questions)
        assert len(stage.questions) == 1
        assert stage.questions[0].id == "custom"


# ==============================================================================
# run_architect Convenience Function Tests
# ==============================================================================


class TestRunArchitectConvenienceFunction:
    """Test the run_architect convenience function."""

    def test_run_architect_function(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test run_architect convenience function."""
        _, ctx = plan_with_orient

        result = run_architect(ctx)

        assert result.output_path.exists()
        assert ctx.plan.stages[PlanStage.ARCHITECT] == StageStatus.COMPLETE

    def test_run_architect_with_options(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test run_architect with mindset and scale options."""
        _, ctx = plan_with_orient

        result = run_architect(ctx, mindset="enterprise", scale="internet-scale")

        assert result.mindset == "enterprise"
        assert result.scale == "internet-scale"


# ==============================================================================
# Data Class Tests
# ==============================================================================


class TestDataClasses:
    """Test data class functionality."""

    def test_tech_stack_choice(self) -> None:
        """Test TechStackChoice dataclass."""
        choice = TechStackChoice(
            layer="Language",
            choice="Python 3.11",
            rationale="Modern, fast",
        )
        assert choice.layer == "Language"
        assert choice.choice == "Python 3.11"

    def test_component(self) -> None:
        """Test Component dataclass."""
        comp = Component(
            name="Core",
            purpose="Business logic",
            responsibilities=["Data processing", "Validation"],
            dependencies=["Database"],
            interface="Internal API",
        )
        assert comp.name == "Core"
        assert len(comp.responsibilities) == 2

    def test_implementation_phase(self) -> None:
        """Test ImplementationPhase dataclass."""
        phase = ImplementationPhase(
            number=1,
            name="Foundation",
            goal="Setup infrastructure",
            tasks=["Create project", "Setup CI"],
        )
        assert phase.number == 1
        assert len(phase.tasks) == 2

    def test_technical_risk(self) -> None:
        """Test TechnicalRisk dataclass."""
        risk = TechnicalRisk(
            risk="Scope creep",
            impact="High",
            likelihood="Medium",
            mitigation="Strict boundaries",
        )
        assert risk.impact == "High"

    def test_architect_result_duration(self) -> None:
        """Test ArchitectResult.duration_seconds property."""
        from datetime import datetime, timezone

        start = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 20, 10, 0, 30, tzinfo=timezone.utc)

        result = ArchitectResult(
            output_path=Path("/tmp/test.md"),
            technical_summary="Test",
            tech_stack=[],
            components=[],
            implementation_phases=[],
            technical_risks=[],
            mindset="mvp",
            scale="team",
            started_at=start,
            completed_at=end,
        )
        assert result.duration_seconds == 30.0


# ==============================================================================
# CLI Integration Tests
# ==============================================================================


class TestPlanArchitectCLI:
    """Test architect CLI command integration."""

    def test_architect_command_with_plan(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test architect command with a plan slug."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_with_orient

        result = runner.invoke(
            app,
            ["plan", "architect", "my-feature", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "Architect complete!" in result.output

        # Check architecture.md was created
        architecture_file = tmp_path / "plans" / "my-feature" / "architecture.md"
        assert architecture_file.exists()

    def test_architect_command_no_plan(self, tmp_path: Path) -> None:
        """Test architect command without any plans shows error."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        result = runner.invoke(
            app, ["plan", "architect", "-p", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "No plans found" in result.output

    def test_architect_command_plan_not_found(self, tmp_path: Path) -> None:
        """Test architect command with non-existent plan."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        # Create empty plans directory
        (tmp_path / "plans").mkdir(parents=True)

        result = runner.invoke(
            app,
            ["plan", "architect", "nonexistent", "-p", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert "Plan not found" in result.output

    def test_architect_command_verbose(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test architect command with verbose flag."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_with_orient

        result = runner.invoke(
            app,
            ["plan", "architect", "my-feature", "-p", str(tmp_path), "-v"],
        )

        assert result.exit_code == 0
        assert "Summary:" in result.output or "Architect complete!" in result.output

    def test_architect_command_with_mindset(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test architect command with mindset option."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_with_orient

        result = runner.invoke(
            app,
            [
                "plan",
                "architect",
                "my-feature",
                "-p",
                str(tmp_path),
                "--mindset",
                "production",
            ],
        )

        assert result.exit_code == 0

        # Check mindset was used
        architecture_file = tmp_path / "plans" / "my-feature" / "architecture.md"
        content = architecture_file.read_text()
        assert "production" in content.lower()

    def test_architect_command_invalid_mindset(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test architect command with invalid mindset."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_with_orient

        result = runner.invoke(
            app,
            [
                "plan",
                "architect",
                "my-feature",
                "-p",
                str(tmp_path),
                "--mindset",
                "invalid",
            ],
        )

        assert result.exit_code == 1
        assert "Invalid mindset" in result.output

    def test_architect_command_finds_recent_plan(
        self, plan_with_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test architect command finds most recent plan when no slug given."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_with_orient

        result = runner.invoke(
            app,
            ["plan", "architect", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "Architect complete!" in result.output

    def test_architect_command_orient_not_complete(
        self, plan_without_orient: tuple[Path, PlanContext]
    ) -> None:
        """Test architect command fails if orient not complete."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_without_orient

        result = runner.invoke(
            app,
            ["plan", "architect", "incomplete-plan", "-p", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert (
            "requires completed orientation" in result.output
            or "failed" in result.output.lower()
        )
