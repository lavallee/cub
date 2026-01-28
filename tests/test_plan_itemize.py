"""
Unit tests for itemize stage implementation.

Tests the ItemizeStage class functionality including validation,
context extraction, task generation, and itemized-plan.md generation.

All stage tests mock out invoke_claude_command so stages use
their template fallback instead of calling the real Claude CLI.
"""

import json
from pathlib import Path

import pytest

# Use template fallback instead of real Claude CLI.
pytestmark = pytest.mark.usefixtures("_no_claude")

from cub.core.plan.context import PlanContext
from cub.core.plan.itemize import (
    Epic,
    ItemizeInputError,
    ItemizeResult,
    ItemizeStage,
    Task,
    run_itemize,
)
from cub.core.plan.models import PlanStage, PlanStatus, StageStatus

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def plan_with_architect(tmp_path: Path) -> tuple[Path, PlanContext]:
    """Create a plan with completed architect stage."""
    # Create plan directory
    plan_dir = tmp_path / "plans" / "my-feature"
    plan_dir.mkdir(parents=True)

    # Create plan.json with architect complete
    plan_json = {
        "slug": "my-feature",
        "project": "test",
        "status": "in_progress",
        "spec_file": "my-feature.md",
        "stages": {
            "orient": "complete",
            "architect": "complete",
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

    # Create architecture.md
    architecture_content = """# Architecture Design: My Feature

**Date:** 2026-01-20
**Mindset:** mvp
**Scale:** team
**Status:** Ready for Review

---

## Technical Summary

This architecture implements efficient task management with workflow automation.

This architecture follows a **mvp** mindset targeting **team** scale usage.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Project requirement from AGENT.md |
| CLI Framework | Typer | Type-safe CLI framework, project standard |
| Data Models | Pydantic v2 | Validation and serialization, project standard |
| Testing | pytest | Standard Python testing framework |
| Type Checking | mypy (strict) | Static type checking, project requirement |

## System Architecture

```
+---------------------------+
|     Interface Layer       |
|      (CLI / API)          |
+-----------+---------------+
            |
            v
+---------------------------+
|      Core Logic           |
|   (Business Operations)   |
+---------------------------+
```

## Components

### Core Logic
- **Purpose:** Business logic and domain operations
- **Responsibilities:**
  - Domain models
  - Business rules
  - Data validation
- **Dependencies:** Data layer
- **Interface:** Internal Python module

### Interface Layer
- **Purpose:** User-facing interface (CLI/API)
- **Responsibilities:**
  - Command/request handling
  - Input validation
  - Output formatting
- **Dependencies:** Core Logic
- **Interface:** CLI commands or REST API

## Data Model

*Data model entities to be defined based on requirements:*

Based on P0 requirements, key entities may include:

- **Task**: *To be specified*
- **Progress**: *To be specified*
- **CLI**: *To be specified*

## APIs / Interfaces

### CLI Commands
- **Type:** Command-line interface
- **Purpose:** User interaction
- **Key Commands:** *To be defined based on requirements*

## Implementation Phases

### Phase 1: Foundation
**Goal:** Basic infrastructure and project setup

- Project setup and configuration
- Basic project structure
- Test infrastructure setup
- CI/CD pipeline (if applicable)

### Phase 2: Core Features
**Goal:** Implement MVP functionality

- Task tracking
- Progress reporting
- CLI interface

### Phase 3: Polish
**Goal:** Production readiness

- Error handling improvements
- Documentation

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Scope creep | H | M | Strict MVP boundary enforcement |
| Technical debt | M | M | Schedule refactoring time |

## Dependencies

### External

- *External dependencies to be identified*

### Internal

- orientation.md requirements

## Future Considerations

- *Features deferred from MVP*
- *Scalability improvements*
- *Additional integrations*

---

**Status**: Ready for Itemize phase
"""
    (plan_dir / "architecture.md").write_text(architecture_content)

    # Create spec file
    specs_dir = tmp_path / "specs" / "researching"
    specs_dir.mkdir(parents=True)
    (specs_dir / "my-feature.md").write_text("# My Feature\n\n## Overview\n\nFeature overview.")

    # Load context
    ctx = PlanContext.load(plan_dir, tmp_path)
    return tmp_path, ctx


@pytest.fixture
def plan_without_architect(tmp_path: Path) -> tuple[Path, PlanContext]:
    """Create a plan without completed architect stage."""
    # Create plan directory
    plan_dir = tmp_path / "plans" / "incomplete-plan"
    plan_dir.mkdir(parents=True)

    # Create plan.json with architect pending
    plan_json = {
        "slug": "incomplete-plan",
        "project": "test",
        "status": "in_progress",
        "spec_file": "incomplete.md",
        "stages": {
            "orient": "complete",
            "architect": "pending",
            "itemize": "pending",
        },
    }
    (plan_dir / "plan.json").write_text(json.dumps(plan_json))

    # Create orientation.md (required for validation)
    orientation = "# Orientation: Incomplete\n\n## Problem Statement\n\nTest"
    (plan_dir / "orientation.md").write_text(orientation)

    # Load context
    ctx = PlanContext.load(plan_dir, tmp_path)
    return tmp_path, ctx


# ==============================================================================
# ItemizeStage Validation Tests
# ==============================================================================


class TestItemizeStageValidation:
    """Test ItemizeStage validation."""

    def test_validate_with_completed_architect(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test validation passes when architect is complete."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        # Should not raise
        stage.validate()

    def test_validate_without_architect(
        self, plan_without_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test validation fails when architect is not complete."""
        _, ctx = plan_without_architect
        stage = ItemizeStage(ctx)
        with pytest.raises(ItemizeInputError, match="requires completed architecture"):
            stage.validate()

    def test_validate_missing_architecture_file(self, tmp_path: Path) -> None:
        """Test validation fails if architecture.md is missing."""
        # Create plan with complete architect but no file
        plan_dir = tmp_path / "plans" / "missing-file"
        plan_dir.mkdir(parents=True)

        plan_json = {
            "slug": "missing-file",
            "project": "test",
            "status": "in_progress",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "pending",
            },
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))
        (plan_dir / "orientation.md").write_text("# Orientation\n\n## Problem Statement\n\nTest")

        ctx = PlanContext.load(plan_dir, tmp_path)
        stage = ItemizeStage(ctx)

        with pytest.raises(ItemizeInputError, match="Architecture file not found"):
            stage.validate()

    def test_validate_missing_orientation_file(self, tmp_path: Path) -> None:
        """Test validation fails if orientation.md is missing."""
        # Create plan with complete architect but no orientation file
        plan_dir = tmp_path / "plans" / "missing-orient"
        plan_dir.mkdir(parents=True)

        plan_json = {
            "slug": "missing-orient",
            "project": "test",
            "status": "in_progress",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "pending",
            },
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))
        (plan_dir / "architecture.md").write_text("# Architecture\n\n## Technical Summary\n\nTest")

        ctx = PlanContext.load(plan_dir, tmp_path)
        stage = ItemizeStage(ctx)

        with pytest.raises(ItemizeInputError, match="Orientation file not found"):
            stage.validate()


# ==============================================================================
# ItemizeStage Run Tests
# ==============================================================================


class TestItemizeStageRun:
    """Test ItemizeStage.run method."""

    def test_run_creates_itemized_plan_md(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that run creates itemized-plan.md file."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        assert result.output_path.exists()
        assert result.output_path.name == "itemized-plan.md"

        content = result.output_path.read_text()
        assert "# Itemized Plan:" in content
        assert "## Epic:" in content
        assert "### Task:" in content

    def test_run_updates_plan_status(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that run updates plan status and stages."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        stage.run()

        assert ctx.plan.status == PlanStatus.COMPLETE
        assert ctx.plan.stages[PlanStage.ITEMIZE] == StageStatus.COMPLETE

    def test_run_saves_plan_json(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that run saves plan.json."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        stage.run()

        plan_json = ctx.plan_dir / "plan.json"
        assert plan_json.exists()

        # Verify stage status is persisted
        data = json.loads(plan_json.read_text())
        assert data["stages"]["itemize"] == "complete"

    def test_run_result_has_timing(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that result includes timing information."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at
        assert result.duration_seconds >= 0

    def test_run_generates_epics(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that run generates epics from phases."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        assert len(result.epics) >= 1
        # Check epic structure
        for epic in result.epics:
            assert epic.id.startswith("test-")
            assert len(epic.title) > 0
            assert epic.priority >= 0
            assert len(epic.labels) > 0

    def test_run_generates_tasks(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that run generates tasks from phases."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        assert result.total_tasks >= 1
        # Check task structure
        for task in result.tasks:
            assert "." in task.id  # Should have epic.task format
            assert len(task.title) > 0
            assert task.epic_id in [e.id for e in result.epics]

    def test_run_uses_beads_compatible_ids(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that generated IDs follow beads format."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        from cub.core.plan.ids import is_valid_epic_id, is_valid_task_id

        for epic in result.epics:
            assert is_valid_epic_id(epic.id), f"Invalid epic ID: {epic.id}"

        for task in result.tasks:
            assert is_valid_task_id(task.id), f"Invalid task ID: {task.id}"


# ==============================================================================
# Content Extraction Tests
# ==============================================================================


class TestContentExtraction:
    """Test content extraction from orientation and architecture."""

    def test_extracts_phases_from_architecture(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that phases are extracted from architecture.md."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        # Should have epics for each phase (titles now include plan slug)
        epic_titles = [e.title for e in result.epics]
        assert any("Foundation" in title for title in epic_titles)
        assert any("Core Features" in title for title in epic_titles)

    def test_extracts_tasks_from_phases(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that tasks are extracted from phase tasks."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        task_titles = [t.title for t in result.tasks]
        # Should have tasks from phases
        assert any("Project setup" in title for title in task_titles)

    def test_includes_mindset_in_output(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that mindset is included in the output."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "mvp" in content.lower()


# ==============================================================================
# Task Generation Tests
# ==============================================================================


class TestTaskGeneration:
    """Test task generation logic."""

    def test_tasks_have_implementation_steps(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that generated tasks have implementation steps."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        for task in result.tasks:
            assert len(task.implementation_steps) > 0

    def test_tasks_have_acceptance_criteria(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that generated tasks have acceptance criteria."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        for task in result.tasks:
            assert len(task.acceptance_criteria) > 0

    def test_tasks_have_correct_epic_reference(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that tasks reference valid epics."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        epic_ids = {e.id for e in result.epics}
        for task in result.tasks:
            assert task.epic_id in epic_ids

    def test_task_ids_are_unique(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that all task IDs are unique."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        task_ids = [t.id for t in result.tasks]
        assert len(task_ids) == len(set(task_ids))


# ==============================================================================
# Output Format Tests
# ==============================================================================


class TestOutputFormat:
    """Test the format of itemized-plan.md output."""

    def test_output_has_header(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that output has proper header."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "# Itemized Plan:" in content
        assert "> Source:" in content
        assert "> Orient:" in content
        assert "> Generated:" in content

    def test_output_has_context_summary(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that output has context summary section."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "## Context Summary" in content

    def test_output_has_epic_sections(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that output has epic sections."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        for epic in result.epics:
            assert f"## Epic: {epic.id}" in content

    def test_output_has_task_sections(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that output has task sections."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        for task in result.tasks:
            assert f"### Task: {task.id}" in content

    def test_output_has_summary_table(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that output has summary table."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "## Summary" in content
        assert "| Epic | Tasks | Priority |" in content
        assert f"**Total**: {len(result.epics)} epics, {result.total_tasks} tasks" in content


# ==============================================================================
# run_itemize Convenience Function Tests
# ==============================================================================


class TestRunItemizeConvenienceFunction:
    """Test the run_itemize convenience function."""

    def test_run_itemize_function(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test run_itemize convenience function."""
        _, ctx = plan_with_architect

        result = run_itemize(ctx)

        assert result.output_path.exists()
        assert ctx.plan.stages[PlanStage.ITEMIZE] == StageStatus.COMPLETE


# ==============================================================================
# Data Class Tests
# ==============================================================================


class TestDataClasses:
    """Test data class functionality."""

    def test_epic_dataclass(self) -> None:
        """Test Epic dataclass."""
        epic = Epic(
            id="test-abc",
            title="Foundation",
            priority=0,
            labels=["phase-1", "foundation"],
            description="Core implementation",
        )
        assert epic.id == "test-abc"
        assert epic.title == "Foundation"
        assert epic.priority == 0
        assert len(epic.labels) == 2

    def test_task_dataclass(self) -> None:
        """Test Task dataclass."""
        task = Task(
            id="test-abc.1",
            title="Setup project",
            priority=0,
            labels=["foundation"],
            epic_id="test-abc",
            blocks=["test-abc.2"],
            context="Initial setup",
            implementation_steps=["Step 1", "Step 2"],
            acceptance_criteria=["Criteria 1"],
            files=["src/main.py"],
        )
        assert task.id == "test-abc.1"
        assert task.epic_id == "test-abc"
        assert len(task.blocks) == 1
        assert len(task.implementation_steps) == 2

    def test_itemize_result_duration(self) -> None:
        """Test ItemizeResult.duration_seconds property."""
        from datetime import datetime, timezone

        start = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 20, 10, 0, 45, tzinfo=timezone.utc)

        result = ItemizeResult(
            output_path=Path("/tmp/test.md"),
            epics=[],
            tasks=[],
            started_at=start,
            completed_at=end,
        )
        assert result.duration_seconds == 45.0
        assert result.total_tasks == 0


# ==============================================================================
# CLI Integration Tests
# ==============================================================================


class TestPlanItemizeCLI:
    """Test itemize CLI command integration."""

    def test_itemize_command_with_plan(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test itemize command with a plan slug."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_with_architect

        result = runner.invoke(
            app,
            ["plan", "itemize", "my-feature", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "Itemize complete!" in result.output

        # Check itemized-plan.md was created
        itemized_file = tmp_path / "plans" / "my-feature" / "itemized-plan.md"
        assert itemized_file.exists()

    def test_itemize_command_no_plan(self, tmp_path: Path) -> None:
        """Test itemize command without any plans shows error."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        result = runner.invoke(
            app, ["plan", "itemize", "-p", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "No plans found" in result.output

    def test_itemize_command_plan_not_found(self, tmp_path: Path) -> None:
        """Test itemize command with non-existent plan."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()

        # Create empty plans directory
        (tmp_path / "plans").mkdir(parents=True)

        result = runner.invoke(
            app,
            ["plan", "itemize", "nonexistent", "-p", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert "Plan not found" in result.output

    def test_itemize_command_verbose(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test itemize command with verbose flag."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_with_architect

        result = runner.invoke(
            app,
            ["plan", "itemize", "my-feature", "-p", str(tmp_path), "-v"],
        )

        assert result.exit_code == 0
        assert "Summary:" in result.output
        assert "Epics:" in result.output
        assert "Tasks:" in result.output

    def test_itemize_command_finds_recent_plan(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test itemize command finds most recent plan when no slug given."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_with_architect

        result = runner.invoke(
            app,
            ["plan", "itemize", "-p", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "Itemize complete!" in result.output

    def test_itemize_command_architect_not_complete(
        self, plan_without_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test itemize command fails if architect not complete."""
        from typer.testing import CliRunner

        from cub.cli import app

        runner = CliRunner()
        tmp_path, _ = plan_without_architect

        result = runner.invoke(
            app,
            ["plan", "itemize", "incomplete-plan", "-p", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert (
            "requires completed architecture" in result.output
            or "failed" in result.output.lower()
        )


# ==============================================================================
# Edge Case Tests
# ==============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_empty_phases(self, tmp_path: Path) -> None:
        """Test handling of architecture with no phases."""
        # Create plan with minimal architecture
        plan_dir = tmp_path / "plans" / "no-phases"
        plan_dir.mkdir(parents=True)

        plan_json = {
            "slug": "no-phases",
            "project": "test",
            "status": "in_progress",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "pending",
            },
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))

        # Minimal orientation with P0 requirements
        (plan_dir / "orientation.md").write_text(
            """# Orientation: Test

## Problem Statement

Test problem.

## Requirements

### P0 (Must Have)

- First requirement
- Second requirement

## MVP Boundary

**In scope for MVP:**
- First requirement
"""
        )

        # Minimal architecture with no phases
        (plan_dir / "architecture.md").write_text(
            """# Architecture Design: Test

**Mindset:** prototype
**Scale:** personal

## Technical Summary

Simple test architecture.
"""
        )

        ctx = PlanContext.load(plan_dir, tmp_path)
        stage = ItemizeStage(ctx)
        result = stage.run()

        # Should still generate something from requirements
        assert len(result.epics) >= 1
        assert result.total_tasks >= 1

    def test_handles_special_characters_in_title(self, tmp_path: Path) -> None:
        """Test handling of special characters in titles."""
        plan_dir = tmp_path / "plans" / "special-chars"
        plan_dir.mkdir(parents=True)

        plan_json = {
            "slug": "special-chars",
            "project": "test",
            "status": "in_progress",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "pending",
            },
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))

        (plan_dir / "orientation.md").write_text(
            """# Orientation: Feature with "Quotes" & <Special> chars

## Problem Statement

Test with special characters.

## Requirements

### P0 (Must Have)

- Feature: "quoted requirement"
"""
        )

        (plan_dir / "architecture.md").write_text(
            """# Architecture Design: Feature with "Quotes"

**Mindset:** mvp
**Scale:** team

## Implementation Phases

### Phase 1: Setup & Config
**Goal:** Initial setup

- Configure "special" settings
"""
        )

        ctx = PlanContext.load(plan_dir, tmp_path)
        stage = ItemizeStage(ctx)
        result = stage.run()

        # Should complete without error
        assert result.output_path.exists()
        content = result.output_path.read_text()
        assert "# Itemized Plan:" in content


# ==============================================================================
# Plan Label Tests
# ==============================================================================


class TestPlanLabels:
    """Test plan:<slug> label generation for task visibility."""

    def test_epics_have_plan_label(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that epics include the plan:<slug> label."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        for epic in result.epics:
            plan_labels = [lbl for lbl in epic.labels if lbl.startswith("plan:")]
            assert len(plan_labels) == 1, f"Epic {epic.id} should have exactly one plan label"
            assert plan_labels[0] == "plan:my-feature"

    def test_tasks_have_plan_label(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that tasks include the plan:<slug> label."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        for task in result.tasks:
            plan_labels = [lbl for lbl in task.labels if lbl.startswith("plan:")]
            assert len(plan_labels) == 1, f"Task {task.id} should have exactly one plan label"
            assert plan_labels[0] == "plan:my-feature"

    def test_epic_description_includes_plan_reference(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that epic descriptions include plan directory reference."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        for epic in result.epics:
            assert "Plan: plans/my-feature/" in epic.description
            assert "Spec:" in epic.description

    def test_task_context_includes_plan_reference(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that task context includes plan directory reference."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        for task in result.tasks:
            assert "plans/my-feature/" in task.context

    def test_plan_label_in_output_md(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that plan label appears in the generated markdown."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        content = result.output_path.read_text()
        assert "plan:my-feature" in content

    def test_epic_titles_include_plan_slug(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that epic titles include the plan slug for self-documentation.

        Epic title format: "{plan_slug} #{sequence}: {phase_name}"
        Example: "auth-flow #1: Foundation"

        This ensures epics are distinguishable across multiple plans and
        shows sequence even if work doesn't have to be strictly sequential.
        """
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        for epic in result.epics:
            assert epic.title.startswith("my-feature "), (
                f"Epic title '{epic.title}' should start with plan slug"
            )
            # Title should be in format "plan-slug #N: Phase Name"
            assert " #" in epic.title
            assert ": " in epic.title

    def test_tasks_have_complexity_and_model_labels(
        self, plan_with_architect: tuple[Path, PlanContext]
    ) -> None:
        """Test that tasks include complexity and model labels for harness selection."""
        _, ctx = plan_with_architect
        stage = ItemizeStage(ctx)
        result = stage.run()

        for task in result.tasks:
            complexity_labels = [lbl for lbl in task.labels if lbl.startswith("complexity:")]
            model_labels = [lbl for lbl in task.labels if lbl.startswith("model:")]
            assert len(complexity_labels) == 1, f"Task {task.id} should have one complexity label"
            assert len(model_labels) == 1, f"Task {task.id} should have one model label"
            # Default should be medium/sonnet
            assert complexity_labels[0] == "complexity:medium"
            assert model_labels[0] == "model:sonnet"

    def test_plan_label_with_no_phases(self, tmp_path: Path) -> None:
        """Test that plan label is added even when no phases are found."""
        plan_dir = tmp_path / "plans" / "simple-plan"
        plan_dir.mkdir(parents=True)

        plan_json = {
            "slug": "simple-plan",
            "project": "test",
            "status": "in_progress",
            "spec_file": "simple.md",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "pending",
            },
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_json))

        (plan_dir / "orientation.md").write_text(
            """# Orientation: Simple Plan

## Problem Statement

Test problem.

## Requirements

### P0 (Must Have)

- Requirement one
"""
        )

        (plan_dir / "architecture.md").write_text(
            """# Architecture Design: Simple Plan

**Mindset:** prototype
**Scale:** personal

## Technical Summary

Simple test.
"""
        )

        ctx = PlanContext.load(plan_dir, tmp_path)
        stage = ItemizeStage(ctx)
        result = stage.run()

        # Check epics have plan label
        for epic in result.epics:
            assert "plan:simple-plan" in epic.labels
            assert "Plan: plans/simple-plan/" in epic.description

        # Check tasks have plan label
        for task in result.tasks:
            assert "plan:simple-plan" in task.labels
            assert "plans/simple-plan/" in task.context
