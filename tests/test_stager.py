"""
Tests for the cub.core.stage.stager module.

Tests the Stager class that imports tasks from itemized-plan.md
into the task backend.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from cub.core.plan.context import PlanContext
from cub.core.plan.models import Plan, PlanStatus
from cub.core.stage.stager import (
    ItemizedPlanNotFoundError,
    PlanAlreadyStagedError,
    PlanNotCompleteError,
    Stager,
    StagingResult,
    TaskImportError,
    find_stageable_plans,
)
from cub.core.tasks.models import Task, TaskType


@pytest.fixture
def project_with_plans(tmp_path: Path) -> Path:
    """Create a project directory with a complete plan."""
    project = tmp_path / "project"
    project.mkdir()

    # Create plans directory
    plans_dir = project / "plans"
    plans_dir.mkdir()

    # Create a complete plan
    plan_dir = plans_dir / "my-feature"
    plan_dir.mkdir()

    # Create plan.json with complete status
    plan_data = {
        "slug": "my-feature",
        "project": "test",
        "status": "complete",
        "spec_file": "my-feature.md",
        "stages": {
            "orient": "complete",
            "architect": "complete",
            "itemize": "complete",
        },
        "created": "2026-01-20T10:00:00+00:00",
        "updated": "2026-01-20T14:00:00+00:00",
    }
    (plan_dir / "plan.json").write_text(json.dumps(plan_data, indent=2))

    # Create itemized-plan.md
    itemized_content = """# Itemized Plan: My Feature

> Source: [my-feature.md](specs/researching/my-feature.md)
> Generated: 2026-01-20

## Context Summary
This is a test plan.

**Mindset:** mvp | **Scale:** team

---

## Epic: test-abc - Test Epic
Priority: 0
Labels: core, backend

This epic implements the test feature.

### Task: test-abc.1 - Implement core module
Priority: 0
Labels: core

**Context**: Implement the core module with validation.

**Implementation Steps**:
1. Create the module file
2. Add validation logic
3. Write tests

**Acceptance Criteria**:
- [ ] Module created
- [ ] Validation works

**Files**: src/core/module.py, tests/test_module.py

---

### Task: test-abc.2 - Add documentation
Priority: 2
Labels: docs
Blocks: test-abc.1

**Context**: Add documentation for the module.

**Implementation Steps**:
1. Write docstrings
2. Update README

**Acceptance Criteria**:
- [ ] Docstrings complete

---

## Summary
| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| test-abc | 2 | 0 | Test Epic |
"""
    (plan_dir / "itemized-plan.md").write_text(itemized_content)

    # Create orientation.md (required for complete plan)
    (plan_dir / "orientation.md").write_text("# Orientation\nTest orientation.")

    # Create architecture.md (required for complete plan)
    (plan_dir / "architecture.md").write_text("# Architecture\nTest architecture.")

    return project


@pytest.fixture
def mock_backend() -> Mock:
    """Create a mock task backend."""
    backend = Mock()

    def mock_import(tasks: list[Task]) -> list[Task]:
        # Return the same tasks (simulating successful import)
        return tasks

    backend.import_tasks = Mock(side_effect=mock_import)
    backend.backend_name = "mock"
    return backend


class TestStager:
    """Tests for the Stager class."""

    def test_stage_complete_plan(
        self,
        project_with_plans: Path,
        mock_backend: Mock,
    ) -> None:
        """Test staging a complete plan successfully."""
        plan_dir = project_with_plans / "plans" / "my-feature"
        ctx = PlanContext.load(plan_dir, project_with_plans)

        stager = Stager(ctx, backend=mock_backend)
        result = stager.stage()

        # Check result
        assert result.plan_slug == "my-feature"
        assert len(result.epics_created) == 1
        assert len(result.tasks_created) == 2
        assert not result.dry_run
        assert result.duration_seconds > 0

        # Check epics
        epic = result.epics_created[0]
        assert epic.id == "test-abc"
        assert epic.title == "Test Epic"
        assert epic.type == TaskType.EPIC

        # Check tasks
        task_ids = [t.id for t in result.tasks_created]
        assert "test-abc.1" in task_ids
        assert "test-abc.2" in task_ids

        # Check backend was called
        assert mock_backend.import_tasks.call_count == 2  # Once for epics, once for tasks

        # Check plan status was updated
        updated_plan = Plan.load(plan_dir)
        assert updated_plan.status == PlanStatus.STAGED

    def test_stage_dry_run(
        self,
        project_with_plans: Path,
        mock_backend: Mock,
    ) -> None:
        """Test dry run doesn't import or update status."""
        plan_dir = project_with_plans / "plans" / "my-feature"
        ctx = PlanContext.load(plan_dir, project_with_plans)

        stager = Stager(ctx, backend=mock_backend)
        result = stager.stage(dry_run=True)

        # Check result
        assert result.dry_run
        assert len(result.epics_created) == 1
        assert len(result.tasks_created) == 2

        # Backend should NOT be called
        mock_backend.import_tasks.assert_not_called()

        # Plan status should NOT be updated
        unchanged_plan = Plan.load(plan_dir)
        assert unchanged_plan.status == PlanStatus.COMPLETE

    def test_stage_incomplete_plan_fails(
        self,
        project_with_plans: Path,
        mock_backend: Mock,
    ) -> None:
        """Test that staging an incomplete plan fails."""
        plan_dir = project_with_plans / "plans" / "my-feature"

        # Make the plan incomplete
        plan_data = {
            "slug": "my-feature",
            "project": "test",
            "status": "in_progress",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "pending",  # Not complete!
            },
            "created": "2026-01-20T10:00:00+00:00",
            "updated": "2026-01-20T14:00:00+00:00",
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_data, indent=2))

        ctx = PlanContext.load(plan_dir, project_with_plans)
        stager = Stager(ctx, backend=mock_backend)

        with pytest.raises(PlanNotCompleteError):
            stager.stage()

    def test_stage_already_staged_plan_fails(
        self,
        project_with_plans: Path,
        mock_backend: Mock,
    ) -> None:
        """Test that staging an already-staged plan fails."""
        plan_dir = project_with_plans / "plans" / "my-feature"

        # Make the plan already staged
        plan_data = {
            "slug": "my-feature",
            "project": "test",
            "status": "staged",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "complete",
            },
            "created": "2026-01-20T10:00:00+00:00",
            "updated": "2026-01-20T14:00:00+00:00",
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_data, indent=2))

        ctx = PlanContext.load(plan_dir, project_with_plans)
        stager = Stager(ctx, backend=mock_backend)

        with pytest.raises(PlanAlreadyStagedError):
            stager.stage()

    def test_stage_missing_itemized_plan_fails(
        self,
        project_with_plans: Path,
        mock_backend: Mock,
    ) -> None:
        """Test that staging fails when itemized-plan.md is missing."""
        plan_dir = project_with_plans / "plans" / "my-feature"

        # Remove itemized-plan.md
        (plan_dir / "itemized-plan.md").unlink()

        ctx = PlanContext.load(plan_dir, project_with_plans)
        stager = Stager(ctx, backend=mock_backend)

        with pytest.raises(ItemizedPlanNotFoundError):
            stager.stage()

    def test_stage_backend_import_fails(
        self,
        project_with_plans: Path,
    ) -> None:
        """Test that staging fails gracefully when backend import fails."""
        plan_dir = project_with_plans / "plans" / "my-feature"
        ctx = PlanContext.load(plan_dir, project_with_plans)

        # Create a backend that fails on import
        failing_backend = Mock()
        failing_backend.import_tasks = Mock(
            side_effect=ValueError("Import failed!")
        )

        stager = Stager(ctx, backend=failing_backend)

        with pytest.raises(TaskImportError, match="Import failed"):
            stager.stage()

    def test_parse_plan(
        self,
        project_with_plans: Path,
    ) -> None:
        """Test parsing itemized-plan.md separately."""
        plan_dir = project_with_plans / "plans" / "my-feature"
        ctx = PlanContext.load(plan_dir, project_with_plans)

        stager = Stager(ctx)
        parsed = stager.parse_plan()

        # Check metadata
        assert parsed.metadata.title == "My Feature"
        assert parsed.metadata.mindset == "mvp"
        assert parsed.metadata.scale == "team"

        # Check epics
        assert len(parsed.epics) == 1
        assert parsed.epics[0].id == "test-abc"
        assert parsed.epics[0].title == "Test Epic"
        assert "core" in parsed.epics[0].labels
        assert "backend" in parsed.epics[0].labels

        # Check tasks
        assert len(parsed.tasks) == 2
        task_ids = [t.id for t in parsed.tasks]
        assert "test-abc.1" in task_ids
        assert "test-abc.2" in task_ids

        # Check task details
        task1 = next(t for t in parsed.tasks if t.id == "test-abc.1")
        assert task1.priority == 0
        assert "core" in task1.labels
        assert len(task1.implementation_steps) == 3
        assert len(task1.acceptance_criteria) == 2
        assert "src/core/module.py" in task1.files

        task2 = next(t for t in parsed.tasks if t.id == "test-abc.2")
        assert task2.blocks == ["test-abc.1"]


class TestStagingResult:
    """Tests for the StagingResult dataclass."""

    def test_total_created(self) -> None:
        """Test total_created property."""
        result = StagingResult(
            plan_slug="test",
            epics_created=[
                Task(id="e1", title="Epic 1"),
            ],
            tasks_created=[
                Task(id="t1", title="Task 1"),
                Task(id="t2", title="Task 2"),
            ],
        )
        assert result.total_created == 3

    def test_empty_result(self) -> None:
        """Test result with no items."""
        result = StagingResult(plan_slug="test")
        assert result.total_created == 0
        assert result.epics_created == []
        assert result.tasks_created == []


class TestFindStageablePlans:
    """Tests for the find_stageable_plans function."""

    def test_find_complete_plan(self, project_with_plans: Path) -> None:
        """Test finding a complete plan."""
        stageable = find_stageable_plans(project_with_plans)
        assert len(stageable) == 1
        assert stageable[0].name == "my-feature"

    def test_excludes_staged_plans(self, project_with_plans: Path) -> None:
        """Test that staged plans are excluded."""
        plan_dir = project_with_plans / "plans" / "my-feature"
        plan_data = {
            "slug": "my-feature",
            "project": "test",
            "status": "staged",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "complete",
            },
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_data))

        stageable = find_stageable_plans(project_with_plans)
        assert len(stageable) == 0

    def test_excludes_incomplete_plans(self, project_with_plans: Path) -> None:
        """Test that incomplete plans are excluded."""
        plan_dir = project_with_plans / "plans" / "my-feature"
        plan_data = {
            "slug": "my-feature",
            "project": "test",
            "status": "in_progress",
            "stages": {
                "orient": "complete",
                "architect": "in_progress",
                "itemize": "pending",
            },
        }
        (plan_dir / "plan.json").write_text(json.dumps(plan_data))

        stageable = find_stageable_plans(project_with_plans)
        assert len(stageable) == 0

    def test_no_plans_directory(self, tmp_path: Path) -> None:
        """Test when plans directory doesn't exist."""
        project = tmp_path / "empty"
        project.mkdir()

        stageable = find_stageable_plans(project)
        assert stageable == []

    def test_empty_plans_directory(self, tmp_path: Path) -> None:
        """Test when plans directory is empty."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "plans").mkdir()

        stageable = find_stageable_plans(project)
        assert stageable == []

    def test_multiple_stageable_plans(self, project_with_plans: Path) -> None:
        """Test finding multiple stageable plans."""
        # Create a second complete plan
        plan2_dir = project_with_plans / "plans" / "another-feature"
        plan2_dir.mkdir()
        plan2_data = {
            "slug": "another-feature",
            "project": "test",
            "status": "complete",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "complete",
            },
        }
        (plan2_dir / "plan.json").write_text(json.dumps(plan2_data))
        (plan2_dir / "itemized-plan.md").write_text("# Itemized Plan: Another")
        (plan2_dir / "orientation.md").write_text("# Orient")
        (plan2_dir / "architecture.md").write_text("# Arch")

        stageable = find_stageable_plans(project_with_plans)
        assert len(stageable) == 2
        slugs = [p.name for p in stageable]
        assert "my-feature" in slugs
        assert "another-feature" in slugs
