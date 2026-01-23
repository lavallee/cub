"""Tests for itemized-plan.md parser."""

from datetime import datetime
from pathlib import Path

import pytest

from cub.core.plan.parser import (
    ParsedEpic,
    ParsedPlan,
    ParsedTask,
    PlanFileNotFoundError,
    PlanFormatError,
    PlanMetadata,
    _build_description,
    _parse_csv,
    _parse_metadata,
    convert_to_task_models,
    parse_itemized_plan,
    parse_itemized_plan_content,
)

# =============================================================================
# Sample content for testing
# =============================================================================

MINIMAL_PLAN = """# Itemized Plan: Minimal Test

## Epic: cub-abc - Test Epic

Priority: 0
Labels: test

Test epic description.

### Task: cub-abc.1 - Test Task

Priority: 0
Labels: test

**Context**: Test context.

---
"""

FULL_PLAN = """# Itemized Plan: Plan Phase Redesign

> Source: [plan-phase-redesign.md](../../specs/planned/plan-phase-redesign.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-20

## Context Summary

The current `cub prep` pipeline has unclear nomenclature and relies on bash scripts.

**Mindset:** mvp | **Scale:** team

---

## Epic: cub-mh3 - Foundation

Priority: 0
Labels: phase-1, foundation

Implementation phase 1: Foundation

### Task: cub-mh3.1 - Project setup and configuration

Priority: 0
Labels: phase-1, foundation

**Context**: Part of Foundation phase.

**Implementation Steps**:
1. Implement: Project setup and configuration
2. Add unit tests
3. Update documentation if needed

**Acceptance Criteria**:
- [ ] Project setup and configuration is implemented and working
- [ ] Tests pass
- [ ] mypy strict passes

---

### Task: cub-mh3.2 - Basic project structure

Priority: 0
Labels: phase-1, foundation
Blocks: cub-mh3.1

**Context**: Part of Foundation phase.

**Implementation Steps**:
1. Implement: Basic project structure
2. Add unit tests

**Acceptance Criteria**:
- [ ] Basic project structure is implemented and working
- [ ] Tests pass

**Files**: src/main.py, tests/test_main.py

---

## Epic: cub-2zd - Core Features

Priority: 1
Labels: phase-2, core-features

Implementation phase 2: Core Features

### Task: cub-2zd.1 - Main CLI command

Priority: 1
Labels: phase-2, core-features
Blocks: cub-mh3.2, cub-mh3.1

**Context**: Part of Core Features phase.

**Implementation Steps**:
1. Implement: Main CLI command
2. Add unit tests
3. Update documentation if needed

**Acceptance Criteria**:
- [ ] Main CLI command is implemented and working
- [ ] Tests pass

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-mh3 | 2 | P0 | Implementation phase 1: Foundation |
| cub-2zd | 1 | P1 | Implementation phase 2: Core Features |

**Total**: 2 epics, 3 tasks
"""


# =============================================================================
# Helper function tests
# =============================================================================


class TestParseCsv:
    """Tests for _parse_csv helper function."""

    def test_simple_list(self) -> None:
        """Test parsing simple comma-separated list."""
        result = _parse_csv("a, b, c")
        assert result == ["a", "b", "c"]

    def test_strips_whitespace(self) -> None:
        """Test that whitespace is stripped from items."""
        result = _parse_csv("  item1  ,  item2  ,  item3  ")
        assert result == ["item1", "item2", "item3"]

    def test_empty_items_filtered(self) -> None:
        """Test that empty items are filtered out."""
        result = _parse_csv("a,, b, ,c")
        assert result == ["a", "b", "c"]

    def test_empty_string(self) -> None:
        """Test empty string input."""
        result = _parse_csv("")
        assert result == []

    def test_single_item(self) -> None:
        """Test single item (no commas)."""
        result = _parse_csv("single-item")
        assert result == ["single-item"]


class TestParseMetadata:
    """Tests for _parse_metadata function."""

    def test_full_metadata(self) -> None:
        """Test parsing full metadata."""
        metadata = _parse_metadata(FULL_PLAN)

        assert metadata.title == "Plan Phase Redesign"
        assert metadata.source_spec == "plan-phase-redesign.md"
        assert metadata.source_spec_path == "../../specs/planned/plan-phase-redesign.md"
        assert metadata.orientation_path == "./orientation.md"
        assert metadata.architecture_path == "./architecture.md"
        assert metadata.generated_date == datetime(2026, 1, 20)
        assert "unclear nomenclature" in metadata.context_summary
        assert metadata.mindset == "mvp"
        assert metadata.scale == "team"

    def test_minimal_metadata(self) -> None:
        """Test parsing minimal metadata."""
        content = "# Itemized Plan: Simple Test\n\n## Epic: test - Test"
        metadata = _parse_metadata(content)

        assert metadata.title == "Simple Test"
        assert metadata.source_spec is None
        assert metadata.generated_date is None
        assert metadata.mindset is None

    def test_missing_title(self) -> None:
        """Test parsing content with no title."""
        content = "## Epic: test - Test"
        metadata = _parse_metadata(content)

        assert metadata.title == ""


# =============================================================================
# Parse functions tests
# =============================================================================


class TestParseItemizedPlanContent:
    """Tests for parse_itemized_plan_content function."""

    def test_minimal_plan(self) -> None:
        """Test parsing minimal valid plan."""
        result = parse_itemized_plan_content(MINIMAL_PLAN)

        assert isinstance(result, ParsedPlan)
        assert result.total_epics == 1
        assert result.total_tasks == 1
        assert result.metadata.title == "Minimal Test"

    def test_full_plan(self) -> None:
        """Test parsing full plan with multiple epics and tasks."""
        result = parse_itemized_plan_content(FULL_PLAN)

        assert result.total_epics == 2
        assert result.total_tasks == 3
        assert result.metadata.title == "Plan Phase Redesign"

    def test_epic_parsing(self) -> None:
        """Test that epics are correctly parsed."""
        result = parse_itemized_plan_content(FULL_PLAN)

        epic1 = result.epics[0]
        assert epic1.id == "cub-mh3"
        assert epic1.title == "Foundation"
        assert epic1.priority == 0
        assert epic1.labels == ["phase-1", "foundation"]
        assert "Implementation phase 1" in epic1.description

        epic2 = result.epics[1]
        assert epic2.id == "cub-2zd"
        assert epic2.title == "Core Features"
        assert epic2.priority == 1
        assert epic2.labels == ["phase-2", "core-features"]

    def test_task_parsing(self) -> None:
        """Test that tasks are correctly parsed."""
        result = parse_itemized_plan_content(FULL_PLAN)

        task1 = result.tasks[0]
        assert task1.id == "cub-mh3.1"
        assert task1.title == "Project setup and configuration"
        assert task1.priority == 0
        assert task1.labels == ["phase-1", "foundation"]
        assert task1.epic_id == "cub-mh3"
        assert "Part of Foundation phase" in task1.context

    def test_task_implementation_steps(self) -> None:
        """Test that implementation steps are parsed."""
        result = parse_itemized_plan_content(FULL_PLAN)

        task = result.tasks[0]
        assert len(task.implementation_steps) == 3
        assert "Project setup and configuration" in task.implementation_steps[0]
        assert "unit tests" in task.implementation_steps[1]

    def test_task_acceptance_criteria(self) -> None:
        """Test that acceptance criteria are parsed."""
        result = parse_itemized_plan_content(FULL_PLAN)

        task = result.tasks[0]
        assert len(task.acceptance_criteria) == 3
        assert "is implemented and working" in task.acceptance_criteria[0]
        assert "Tests pass" in task.acceptance_criteria[1]
        assert "mypy strict passes" in task.acceptance_criteria[2]

    def test_task_blocks(self) -> None:
        """Test that task dependencies (blocks) are parsed."""
        result = parse_itemized_plan_content(FULL_PLAN)

        # Task 2 blocks task 1
        task2 = result.tasks[1]
        assert task2.id == "cub-mh3.2"
        assert task2.blocks == ["cub-mh3.1"]

        # Task 3 blocks multiple tasks
        task3 = result.tasks[2]
        assert task3.id == "cub-2zd.1"
        assert task3.blocks == ["cub-mh3.2", "cub-mh3.1"]

    def test_task_files(self) -> None:
        """Test that task files are parsed."""
        result = parse_itemized_plan_content(FULL_PLAN)

        # Task 2 has files
        task2 = result.tasks[1]
        assert task2.files == ["src/main.py", "tests/test_main.py"]

        # Task 1 has no files
        task1 = result.tasks[0]
        assert task1.files == []

    def test_get_tasks_for_epic(self) -> None:
        """Test getting tasks for a specific epic."""
        result = parse_itemized_plan_content(FULL_PLAN)

        tasks_mh3 = result.get_tasks_for_epic("cub-mh3")
        assert len(tasks_mh3) == 2
        assert all(t.epic_id == "cub-mh3" for t in tasks_mh3)

        tasks_2zd = result.get_tasks_for_epic("cub-2zd")
        assert len(tasks_2zd) == 1
        assert tasks_2zd[0].epic_id == "cub-2zd"

    def test_empty_content_raises_error(self) -> None:
        """Test that empty content raises PlanFormatError."""
        with pytest.raises(PlanFormatError, match="empty"):
            parse_itemized_plan_content("")

        with pytest.raises(PlanFormatError, match="empty"):
            parse_itemized_plan_content("   \n\n   ")

    def test_invalid_format_raises_error(self) -> None:
        """Test that invalid format raises PlanFormatError."""
        with pytest.raises(PlanFormatError, match="Invalid plan format"):
            parse_itemized_plan_content("Just some random text\nwith no structure")

    def test_raw_content_preserved(self) -> None:
        """Test that raw content is preserved in result."""
        result = parse_itemized_plan_content(MINIMAL_PLAN)
        assert result.raw_content == MINIMAL_PLAN


class TestParseItemizedPlan:
    """Tests for parse_itemized_plan function (file-based)."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Test that missing file raises PlanFileNotFoundError."""
        nonexistent = tmp_path / "does-not-exist.md"
        with pytest.raises(PlanFileNotFoundError, match="not found"):
            parse_itemized_plan(nonexistent)

    def test_parse_from_file(self, tmp_path: Path) -> None:
        """Test parsing from an actual file."""
        plan_file = tmp_path / "itemized-plan.md"
        plan_file.write_text(MINIMAL_PLAN, encoding="utf-8")

        result = parse_itemized_plan(plan_file)

        assert result.total_epics == 1
        assert result.total_tasks == 1
        assert result.metadata.title == "Minimal Test"

    def test_parse_full_plan_from_file(self, tmp_path: Path) -> None:
        """Test parsing full plan from file."""
        plan_file = tmp_path / "itemized-plan.md"
        plan_file.write_text(FULL_PLAN, encoding="utf-8")

        result = parse_itemized_plan(plan_file)

        assert result.total_epics == 2
        assert result.total_tasks == 3


# =============================================================================
# Data class tests
# =============================================================================


class TestParsedEpic:
    """Tests for ParsedEpic dataclass."""

    def test_default_values(self) -> None:
        """Test default values for ParsedEpic."""
        epic = ParsedEpic(id="test-abc", title="Test")
        assert epic.priority == 0
        assert epic.labels == []
        assert epic.description == ""

    def test_all_fields(self) -> None:
        """Test all fields for ParsedEpic."""
        epic = ParsedEpic(
            id="cub-xyz",
            title="Test Epic",
            priority=2,
            labels=["label1", "label2"],
            description="Epic description",
        )
        assert epic.id == "cub-xyz"
        assert epic.title == "Test Epic"
        assert epic.priority == 2
        assert epic.labels == ["label1", "label2"]
        assert epic.description == "Epic description"


class TestParsedTask:
    """Tests for ParsedTask dataclass."""

    def test_default_values(self) -> None:
        """Test default values for ParsedTask."""
        task = ParsedTask(id="test-abc.1", title="Test Task")
        assert task.priority == 0
        assert task.labels == []
        assert task.epic_id == ""
        assert task.blocks == []
        assert task.context == ""
        assert task.implementation_steps == []
        assert task.acceptance_criteria == []
        assert task.files == []

    def test_all_fields(self) -> None:
        """Test all fields for ParsedTask."""
        task = ParsedTask(
            id="cub-xyz.1",
            title="Test Task",
            priority=1,
            labels=["label1"],
            epic_id="cub-xyz",
            blocks=["cub-abc.1"],
            context="Test context",
            implementation_steps=["Step 1", "Step 2"],
            acceptance_criteria=["Criterion 1"],
            files=["file1.py"],
        )
        assert task.id == "cub-xyz.1"
        assert task.title == "Test Task"
        assert task.priority == 1
        assert task.labels == ["label1"]
        assert task.epic_id == "cub-xyz"
        assert task.blocks == ["cub-abc.1"]
        assert task.context == "Test context"
        assert task.implementation_steps == ["Step 1", "Step 2"]
        assert task.acceptance_criteria == ["Criterion 1"]
        assert task.files == ["file1.py"]


class TestPlanMetadata:
    """Tests for PlanMetadata dataclass."""

    def test_default_values(self) -> None:
        """Test default values for PlanMetadata."""
        metadata = PlanMetadata()
        assert metadata.title == ""
        assert metadata.source_spec is None
        assert metadata.source_spec_path is None
        assert metadata.orientation_path is None
        assert metadata.architecture_path is None
        assert metadata.generated_date is None
        assert metadata.context_summary == ""
        assert metadata.mindset is None
        assert metadata.scale is None


class TestParsedPlan:
    """Tests for ParsedPlan dataclass."""

    def test_total_properties(self) -> None:
        """Test total_epics and total_tasks properties."""
        plan = ParsedPlan(
            metadata=PlanMetadata(),
            epics=[
                ParsedEpic(id="e1", title="Epic 1"),
                ParsedEpic(id="e2", title="Epic 2"),
            ],
            tasks=[
                ParsedTask(id="e1.1", title="Task 1"),
                ParsedTask(id="e1.2", title="Task 2"),
                ParsedTask(id="e2.1", title="Task 3"),
            ],
            raw_content="",
        )
        assert plan.total_epics == 2
        assert plan.total_tasks == 3

    def test_get_tasks_for_epic(self) -> None:
        """Test get_tasks_for_epic method."""
        plan = ParsedPlan(
            metadata=PlanMetadata(),
            epics=[
                ParsedEpic(id="e1", title="Epic 1"),
            ],
            tasks=[
                ParsedTask(id="e1.1", title="Task 1", epic_id="e1"),
                ParsedTask(id="e1.2", title="Task 2", epic_id="e1"),
                ParsedTask(id="e2.1", title="Task 3", epic_id="e2"),
            ],
            raw_content="",
        )
        e1_tasks = plan.get_tasks_for_epic("e1")
        assert len(e1_tasks) == 2
        assert all(t.epic_id == "e1" for t in e1_tasks)


# =============================================================================
# Conversion tests
# =============================================================================


class TestConvertToTaskModels:
    """Tests for convert_to_task_models function."""

    def test_basic_conversion(self) -> None:
        """Test basic conversion to task model dicts."""
        parsed = parse_itemized_plan_content(MINIMAL_PLAN)
        epics, task_dicts = convert_to_task_models(parsed)

        assert len(epics) == 1
        assert len(task_dicts) == 1

        task_dict = task_dicts[0]
        assert task_dict["id"] == "cub-abc.1"
        assert task_dict["title"] == "Test Task"
        assert task_dict["priority"] == 0
        assert task_dict["labels"] == ["test"]
        assert task_dict["parent"] == "cub-abc"

    def test_full_conversion(self) -> None:
        """Test conversion with full plan."""
        parsed = parse_itemized_plan_content(FULL_PLAN)
        epics, task_dicts = convert_to_task_models(parsed)

        assert len(epics) == 2
        assert len(task_dicts) == 3

        # Check first task
        task1 = task_dicts[0]
        assert task1["id"] == "cub-mh3.1"
        assert task1["parent"] == "cub-mh3"
        assert "Part of Foundation phase" in str(task1["description"])

        # Check task with blocks
        task2 = task_dicts[1]
        assert task2["blocks"] == ["cub-mh3.1"]

        # Check acceptance criteria preserved
        assert task1["acceptance_criteria"] == [
            "Project setup and configuration is implemented and working",
            "Tests pass",
            "mypy strict passes",
        ]


class TestBuildDescription:
    """Tests for _build_description helper function."""

    def test_with_context(self) -> None:
        """Test building description with context."""
        task = ParsedTask(id="t1", title="Test", context="Test context here")
        desc = _build_description(task)
        assert desc == "Test context here"

    def test_with_steps(self) -> None:
        """Test building description with implementation steps."""
        task = ParsedTask(
            id="t1",
            title="Test",
            implementation_steps=["Step 1", "Step 2"],
        )
        desc = _build_description(task)
        assert "**Implementation Steps:**" in desc
        assert "1. Step 1" in desc
        assert "2. Step 2" in desc

    def test_with_files(self) -> None:
        """Test building description with files."""
        task = ParsedTask(
            id="t1",
            title="Test",
            files=["file1.py", "file2.py"],
        )
        desc = _build_description(task)
        assert "**Files:** file1.py, file2.py" in desc

    def test_with_all_fields(self) -> None:
        """Test building description with all fields."""
        task = ParsedTask(
            id="t1",
            title="Test",
            context="Context here",
            implementation_steps=["Step 1"],
            files=["file.py"],
        )
        desc = _build_description(task)
        assert "Context here" in desc
        assert "**Implementation Steps:**" in desc
        assert "**Files:** file.py" in desc

    def test_empty_task(self) -> None:
        """Test building description for empty task."""
        task = ParsedTask(id="t1", title="Test")
        desc = _build_description(task)
        assert desc == ""


# =============================================================================
# Edge case tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and unusual content."""

    def test_special_characters_in_title(self) -> None:
        """Test handling special characters in titles."""
        content = """# Itemized Plan: Test with `code` and *emphasis*

## Epic: cub-abc - Epic with `backticks` and *stars*

Priority: 0
Labels: test

### Task: cub-abc.1 - Task with special: chars & symbols

Priority: 0
Labels: test

**Context**: Context here.

---
"""
        result = parse_itemized_plan_content(content)

        assert "`code`" in result.metadata.title
        assert "`backticks`" in result.epics[0].title
        assert "&" in result.tasks[0].title

    def test_multiline_context(self) -> None:
        """Test task with multiline context (only first part captured)."""
        content = """# Itemized Plan: Test

## Epic: cub-abc - Test Epic

Priority: 0
Labels: test

### Task: cub-abc.1 - Test Task

Priority: 0
Labels: test

**Context**: This is a longer context that explains the task in detail.

**Implementation Steps**:
1. Do something

---
"""
        result = parse_itemized_plan_content(content)
        # Context should be captured
        assert "longer context" in result.tasks[0].context

    def test_no_summary_section(self) -> None:
        """Test plan without summary section."""
        content = """# Itemized Plan: No Summary

## Epic: cub-abc - Test Epic

Priority: 0
Labels: test

### Task: cub-abc.1 - Test Task

Priority: 0
Labels: test

**Context**: Context.
"""
        result = parse_itemized_plan_content(content)
        assert result.total_epics == 1
        assert result.total_tasks == 1

    def test_epic_with_no_tasks(self) -> None:
        """Test epic with no tasks."""
        content = """# Itemized Plan: Empty Epic

## Epic: cub-abc - Empty Epic

Priority: 0
Labels: test

Epic with no tasks.

## Epic: cub-def - Epic with Task

Priority: 0
Labels: test

### Task: cub-def.1 - Task

Priority: 0
Labels: test

**Context**: Context.

---
"""
        result = parse_itemized_plan_content(content)
        assert result.total_epics == 2
        assert result.total_tasks == 1

        abc_tasks = result.get_tasks_for_epic("cub-abc")
        assert len(abc_tasks) == 0

        def_tasks = result.get_tasks_for_epic("cub-def")
        assert len(def_tasks) == 1

    def test_task_with_checked_acceptance_criteria(self) -> None:
        """Test parsing acceptance criteria with mixed checked/unchecked."""
        content = """# Itemized Plan: Checked Criteria

## Epic: cub-abc - Test Epic

Priority: 0
Labels: test

### Task: cub-abc.1 - Test Task

Priority: 0
Labels: test

**Context**: Context.

**Acceptance Criteria**:
- [x] Already done criterion
- [ ] Still pending criterion

---
"""
        result = parse_itemized_plan_content(content)
        criteria = result.tasks[0].acceptance_criteria
        assert len(criteria) == 2
        assert "Already done criterion" in criteria[0]
        assert "Still pending criterion" in criteria[1]

    def test_priority_as_different_levels(self) -> None:
        """Test various priority levels are parsed correctly."""
        content = """# Itemized Plan: Priority Test

## Epic: cub-p0 - P0 Epic

Priority: 0
Labels: p0

### Task: cub-p0.1 - P0 Task

Priority: 0
Labels: p0

**Context**: Highest priority.

---

## Epic: cub-p3 - P3 Epic

Priority: 3
Labels: p3

### Task: cub-p3.1 - P3 Task

Priority: 3
Labels: p3

**Context**: Lower priority.

---
"""
        result = parse_itemized_plan_content(content)

        assert result.epics[0].priority == 0
        assert result.tasks[0].priority == 0
        assert result.epics[1].priority == 3
        assert result.tasks[1].priority == 3

    def test_only_epic_header_format_accepted(self) -> None:
        """Test that content with only epic headers is parsed."""
        # Even without proper itemized plan header, if it has epics, it parses
        content = """## Epic: cub-abc - Test Epic

Priority: 0
Labels: test

### Task: cub-abc.1 - Test Task

Priority: 0
Labels: test

**Context**: Context.
"""
        result = parse_itemized_plan_content(content)
        assert result.total_epics == 1
        assert result.total_tasks == 1
