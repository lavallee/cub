"""
Integration tests for hierarchical ID format through the full pipeline.

Verifies that hierarchical IDs (cub-054A-0, cub-054A-0.1) flow correctly
through: template format → parser → stager → task backend.

Also verifies backward compatibility with legacy random IDs (cub-k7m, cub-k7m.1).
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from cub.core.plan.context import PlanContext
from cub.core.plan.models import Plan, PlanStage, PlanStatus
from cub.core.plan.parser import parse_itemized_plan, parse_itemized_plan_content
from cub.core.stage.stager import Stager

# ==============================================================================
# Test data: itemized plans in both ID formats
# ==============================================================================

HIERARCHICAL_PLAN = """\
# Itemized Plan: Ledger Consolidation

> Source: [cub-048-ledger-consolidation.md](../../specs/staged/cub-048-ledger-consolidation.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-02-11

## Context Summary

Consolidate the ledger system with hierarchical IDs.

**Mindset:** production | **Scale:** team

---

## Epic: cub-048A-0 - cub-048 #1: Foundation

Priority: 0
Labels: phase-1, foundation, model:opus

Core ID system and models.

### Task: cub-048A-0.1 - Implement SpecId model

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium
Blocks: cub-048A-0.2

**Context**: Create the SpecId Pydantic model as the root of the ID hierarchy.

**Implementation Steps**:
1. Create SpecId model with project and number fields
2. Add validation for non-negative numbers
3. Add __str__ method for formatting

**Acceptance Criteria**:
- [ ] SpecId model validates correctly
- [ ] str(SpecId(project="cub", number=54)) == "cub-054"
- [ ] Model is used by plan parser when staging

**Files**: src/cub/core/ids/models.py

---

### Task: cub-048A-0.2 - Wire ID generation into itemize

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium

**Context**: Connect the new ID system to the itemize stage so it generates hierarchical IDs.

**Implementation Steps**:
1. Update itemize.py to use new generators
2. Update parser regex to accept uppercase
3. Add integration test

**Acceptance Criteria**:
- [ ] Itemize generates hierarchical IDs when spec context available
- [ ] Parser accepts cub-054A-0 format
- [ ] Full pipeline test passes

**Files**: src/cub/core/plan/itemize.py, src/cub/core/plan/parser.py

---

## Epic: cub-048A-1 - cub-048 #2: Integration

Priority: 1
Labels: phase-2, integration, model:sonnet

Wire the ID system into existing consumers.

### Task: cub-048A-1.1 - Update plan commands to use hierarchical IDs

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium

**Context**: Ensure plan commands generate and accept hierarchical IDs.

**Implementation Steps**:
1. Update plan ensure to pass spec_id through
2. Verify stage command handles hierarchical IDs

**Acceptance Criteria**:
- [ ] cub plan ensure generates hierarchical slug when possible
- [ ] cub stage imports hierarchical IDs correctly

**Files**: src/cub/cli/plan.py, src/cub/cli/stage.py

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-048A-0 | 2 | P0 | Core ID system and models |
| cub-048A-1 | 1 | P1 | Wire into existing consumers |

**Total**: 2 epics, 3 tasks
"""

LEGACY_PLAN = """\
# Itemized Plan: Simple Feature

> Generated: 2026-02-11

## Context Summary

A simple feature using legacy IDs.

---

## Epic: cub-k7m - simple-feature #1: Implementation

Priority: 0
Labels: phase-1

Basic implementation.

### Task: cub-k7m.1 - Setup module

Priority: 0
Labels: phase-1, model:haiku

**Context**: Create the module structure.

**Implementation Steps**:
1. Create module file
2. Add exports

**Acceptance Criteria**:
- [ ] Module exists and is importable

---

### Task: cub-k7m.2 - Add tests

Priority: 1
Labels: phase-1, model:haiku

**Context**: Add test coverage.

**Implementation Steps**:
1. Write unit tests
2. Verify passing

**Acceptance Criteria**:
- [ ] Tests pass

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-k7m | 2 | P0 | Basic implementation |

**Total**: 1 epics, 2 tasks
"""

MIXED_PLAN = """\
# Itemized Plan: Mixed IDs

> Generated: 2026-02-11

## Context Summary

A plan using mixed case in IDs (uppercase plan letter).

---

## Epic: cub-054B-3 - mixed #1: Phase One

Priority: 0
Labels: phase-1

Phase one with uppercase plan letter B and numeric epic char 3.

### Task: cub-054B-3.1 - First task

Priority: 0
Labels: phase-1

**Context**: First task.

**Implementation Steps**:
1. Do the thing

**Acceptance Criteria**:
- [ ] Thing is done

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-054B-3 | 1 | P0 | Phase one |

**Total**: 1 epics, 1 tasks
"""


# ==============================================================================
# Tests: Parser accepts hierarchical IDs
# ==============================================================================


class TestParserHierarchicalIds:
    """Test that the parser correctly handles hierarchical IDs."""

    def test_parse_hierarchical_epic_ids(self) -> None:
        """Parser extracts hierarchical epic IDs like cub-054A-0."""
        result = parse_itemized_plan_content(HIERARCHICAL_PLAN)

        assert len(result.epics) == 2
        assert result.epics[0].id == "cub-048A-0"
        assert result.epics[1].id == "cub-048A-1"

    def test_parse_hierarchical_task_ids(self) -> None:
        """Parser extracts hierarchical task IDs like cub-054A-0.1."""
        result = parse_itemized_plan_content(HIERARCHICAL_PLAN)

        assert len(result.tasks) == 3
        assert result.tasks[0].id == "cub-048A-0.1"
        assert result.tasks[1].id == "cub-048A-0.2"
        assert result.tasks[2].id == "cub-048A-1.1"

    def test_parse_hierarchical_task_epic_association(self) -> None:
        """Tasks are correctly associated with their parent epics."""
        result = parse_itemized_plan_content(HIERARCHICAL_PLAN)

        assert result.tasks[0].epic_id == "cub-048A-0"
        assert result.tasks[1].epic_id == "cub-048A-0"
        assert result.tasks[2].epic_id == "cub-048A-1"

    def test_parse_legacy_ids_still_work(self) -> None:
        """Parser still handles legacy random IDs."""
        result = parse_itemized_plan_content(LEGACY_PLAN)

        assert len(result.epics) == 1
        assert result.epics[0].id == "cub-k7m"
        assert len(result.tasks) == 2
        assert result.tasks[0].id == "cub-k7m.1"
        assert result.tasks[1].id == "cub-k7m.2"

    def test_parse_mixed_case_ids(self) -> None:
        """Parser handles IDs with uppercase letters (plan letter B, epic char 3)."""
        result = parse_itemized_plan_content(MIXED_PLAN)

        assert len(result.epics) == 1
        assert result.epics[0].id == "cub-054B-3"
        assert len(result.tasks) == 1
        assert result.tasks[0].id == "cub-054B-3.1"

    def test_parse_hierarchical_metadata(self) -> None:
        """Parser extracts metadata correctly from hierarchical plan."""
        result = parse_itemized_plan_content(HIERARCHICAL_PLAN)

        assert result.metadata.title == "Ledger Consolidation"
        assert result.metadata.mindset == "production"
        assert result.metadata.scale == "team"

    def test_parse_hierarchical_task_details(self) -> None:
        """Parser extracts task details (blocks, context, criteria) from hierarchical plan."""
        result = parse_itemized_plan_content(HIERARCHICAL_PLAN)

        task = result.tasks[0]
        assert task.title == "Implement SpecId model"
        assert task.priority == 0
        assert "phase-1" in task.labels
        assert "cub-048A-0.2" in task.blocks
        assert "SpecId Pydantic model" in task.context
        assert len(task.implementation_steps) == 3
        assert len(task.acceptance_criteria) == 3

    def test_parse_file_with_hierarchical_ids(self, tmp_path: Path) -> None:
        """Parser reads and parses a file with hierarchical IDs."""
        plan_file = tmp_path / "itemized-plan.md"
        plan_file.write_text(HIERARCHICAL_PLAN, encoding="utf-8")

        result = parse_itemized_plan(plan_file)

        assert result.total_epics == 2
        assert result.total_tasks == 3
        assert result.epics[0].id == "cub-048A-0"


# ==============================================================================
# Tests: Stager handles hierarchical IDs
# ==============================================================================


class TestStagerHierarchicalIds:
    """Test that the stager correctly imports hierarchical IDs into the backend."""

    @pytest.fixture()
    def project_root(self, tmp_path: Path) -> Path:
        """Create a minimal project with a completed plan using hierarchical IDs."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "pyproject.toml").write_text('[project]\nname = "cub"')

        plan_dir = project / "plans" / "cub-048-ledger"
        plan_dir.mkdir(parents=True)

        # Write hierarchical itemized plan
        (plan_dir / "itemized-plan.md").write_text(HIERARCHICAL_PLAN, encoding="utf-8")

        # Create completed plan.json
        plan = Plan(
            slug="cub-048-ledger",
            project="cub",
            status=PlanStatus.COMPLETE,
        )
        plan.complete_stage(PlanStage.ORIENT)
        plan.complete_stage(PlanStage.ARCHITECT)
        plan.complete_stage(PlanStage.ITEMIZE)
        plan.save(project)

        return project

    def test_stager_imports_hierarchical_epic_ids(self, project_root: Path) -> None:
        """Stager creates epic tasks with hierarchical IDs."""
        plan_dir = project_root / "plans" / "cub-048-ledger"
        ctx = PlanContext.load(plan_dir, project_root)

        mock_backend = Mock()
        # Backend returns tasks matching what was imported
        mock_backend.import_tasks.side_effect = lambda tasks: tasks

        stager = Stager(ctx, backend=mock_backend)
        result = stager.stage()

        # Check that epics were created with hierarchical IDs
        epic_ids = [e.id for e in result.epics_created]
        assert "cub-048A-0" in epic_ids
        assert "cub-048A-1" in epic_ids

    def test_stager_imports_hierarchical_task_ids(self, project_root: Path) -> None:
        """Stager creates tasks with hierarchical IDs."""
        plan_dir = project_root / "plans" / "cub-048-ledger"
        ctx = PlanContext.load(plan_dir, project_root)

        mock_backend = Mock()
        mock_backend.import_tasks.side_effect = lambda tasks: tasks

        stager = Stager(ctx, backend=mock_backend)
        result = stager.stage()

        # Check that tasks were created with hierarchical IDs
        task_ids = [t.id for t in result.tasks_created]
        assert "cub-048A-0.1" in task_ids
        assert "cub-048A-0.2" in task_ids
        assert "cub-048A-1.1" in task_ids

    def test_stager_preserves_task_parent_association(self, project_root: Path) -> None:
        """Stager preserves parent epic association for tasks."""
        plan_dir = project_root / "plans" / "cub-048-ledger"
        ctx = PlanContext.load(plan_dir, project_root)

        mock_backend = Mock()
        mock_backend.import_tasks.side_effect = lambda tasks: tasks

        stager = Stager(ctx, backend=mock_backend)
        result = stager.stage()

        # Find tasks and check parent associations
        task_map = {t.id: t for t in result.tasks_created}

        assert task_map["cub-048A-0.1"].parent == "cub-048A-0"
        assert task_map["cub-048A-0.2"].parent == "cub-048A-0"
        assert task_map["cub-048A-1.1"].parent == "cub-048A-1"


# ==============================================================================
# Tests: Programmatic itemize uses hierarchical IDs
# ==============================================================================


class TestItemizeHierarchicalIds:
    """Test that the programmatic itemize path generates hierarchical IDs."""

    def test_extract_spec_info_from_filename(self) -> None:
        """_try_extract_spec_info extracts spec number from filename."""
        from cub.core.plan.itemize import _try_extract_spec_info

        result = _try_extract_spec_info("cub", "cub-048-ledger-consolidation.md")
        assert result is not None
        spec_number, project = result
        assert spec_number == 48
        assert project == "cub"

    def test_extract_spec_info_no_match(self) -> None:
        """_try_extract_spec_info returns None when filename doesn't match."""
        from cub.core.plan.itemize import _try_extract_spec_info

        assert _try_extract_spec_info("cub", "my-feature.md") is None
        assert _try_extract_spec_info("cub", None) is None

    def test_generate_hierarchical_epic_id(self) -> None:
        """_generate_hierarchical_epic_id produces correct format."""
        from cub.core.plan.itemize import _generate_hierarchical_epic_id

        result = _generate_hierarchical_epic_id("cub", 48, "A", "0")
        assert result == "cub-048A-0"

    def test_generate_hierarchical_epic_id_large_number(self) -> None:
        """_generate_hierarchical_epic_id handles large spec numbers."""
        from cub.core.plan.itemize import _generate_hierarchical_epic_id

        result = _generate_hierarchical_epic_id("cub", 1234, "B", "5")
        assert result == "cub-1234B-5"

    def test_generate_hierarchical_task_id(self) -> None:
        """_generate_hierarchical_task_id produces correct format."""
        from cub.core.plan.itemize import _generate_hierarchical_task_id

        result = _generate_hierarchical_task_id("cub-048A-0", 3)
        assert result == "cub-048A-0.3"
