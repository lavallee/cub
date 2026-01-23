"""Tests for error handling and edge cases in plan module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cub.core.plan.context import PlanContext, SpecNotFoundError
from cub.core.plan.models import Plan, PlanStage, PlanStatus
from cub.core.plan.parser import PlanFormatError, parse_itemized_plan
from cub.core.stage.stager import Stager, StagerError, TaskImportError


class TestParserEncodingErrors:
    """Test encoding error handling in parser."""

    def test_unicode_decode_error(self, tmp_path: Path) -> None:
        """Test that non-UTF-8 files raise PlanFormatError."""
        plan_file = tmp_path / "bad-encoding.md"
        # Write invalid UTF-8 bytes
        plan_file.write_bytes(b"\xff\xfe# Invalid UTF-8")

        with pytest.raises(PlanFormatError, match="invalid UTF-8 encoding"):
            parse_itemized_plan(plan_file)

    def test_empty_file_after_read(self, tmp_path: Path) -> None:
        """Test that empty files raise PlanFormatError."""
        plan_file = tmp_path / "empty.md"
        plan_file.write_text("", encoding="utf-8")

        with pytest.raises(PlanFormatError, match="empty"):
            parse_itemized_plan(plan_file)

    def test_whitespace_only_file(self, tmp_path: Path) -> None:
        """Test that whitespace-only files raise PlanFormatError."""
        plan_file = tmp_path / "whitespace.md"
        plan_file.write_text("   \n\n  \t  \n", encoding="utf-8")

        with pytest.raises(PlanFormatError, match="empty"):
            parse_itemized_plan(plan_file)


class TestModelsFileOperations:
    """Test file operation error handling in Plan model."""

    def test_save_with_permission_error(self, tmp_path: Path) -> None:
        """Test that permission errors during save are handled."""
        plan = Plan(slug="test-plan", project="test")

        # Create a read-only directory
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)

        try:
            with pytest.raises(
                OSError, match="Cannot create plan directory|Cannot write plan file"
            ):
                plan.save(read_only_dir)
        finally:
            # Cleanup: restore permissions
            read_only_dir.chmod(0o755)

    def test_load_malformed_json(self, tmp_path: Path) -> None:
        """Test that malformed JSON raises ValueError."""
        plan_dir = tmp_path / "bad-plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan.json"
        plan_file.write_text("{ invalid json }", encoding="utf-8")

        with pytest.raises(ValueError, match="Malformed JSON"):
            Plan.load(plan_dir)

    def test_load_invalid_utf8(self, tmp_path: Path) -> None:
        """Test that invalid UTF-8 in plan.json raises ValueError."""
        plan_dir = tmp_path / "bad-encoding-plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan.json"
        plan_file.write_bytes(b"\xff\xfe{ invalid }")

        with pytest.raises(ValueError, match="Invalid UTF-8 encoding"):
            Plan.load(plan_dir)

    def test_load_wrong_type(self, tmp_path: Path) -> None:
        """Test that non-dict JSON raises ValueError."""
        plan_dir = tmp_path / "wrong-type"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan.json"
        plan_file.write_text('["array", "not", "dict"]', encoding="utf-8")

        with pytest.raises(ValueError, match="expected dict"):
            Plan.load(plan_dir)

    def test_load_missing_required_fields(self, tmp_path: Path) -> None:
        """Test that missing required fields raises ValueError."""
        plan_dir = tmp_path / "incomplete-plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan.json"
        # Missing 'slug' and 'project'
        plan_file.write_text('{"status": "pending"}', encoding="utf-8")

        with pytest.raises(ValueError, match="slug|project"):
            Plan.load(plan_dir)


class TestContextReadOperations:
    """Test error handling in PlanContext read operations."""

    def test_read_spec_empty_file(self, tmp_path: Path) -> None:
        """Test that empty spec files raise SpecNotFoundError."""
        spec_file = tmp_path / "empty-spec.md"
        spec_file.write_text("", encoding="utf-8")

        plan = Plan(slug="test", project="test", spec_file="empty-spec.md")
        ctx = PlanContext(
            project_root=tmp_path,
            project="test",
            plan=plan,
            spec_path=spec_file,
        )

        with pytest.raises(SpecNotFoundError, match="empty"):
            ctx.read_spec_content()

    def test_read_spec_invalid_encoding(self, tmp_path: Path) -> None:
        """Test that invalid UTF-8 spec raises SpecNotFoundError."""
        spec_file = tmp_path / "bad-spec.md"
        spec_file.write_bytes(b"\xff\xfe# Bad encoding")

        plan = Plan(slug="test", project="test", spec_file="bad-spec.md")
        ctx = PlanContext(
            project_root=tmp_path,
            project="test",
            plan=plan,
            spec_path=spec_file,
        )

        with pytest.raises(SpecNotFoundError, match="invalid UTF-8 encoding"):
            ctx.read_spec_content()

    def test_read_system_plan_handles_errors_gracefully(self, tmp_path: Path) -> None:
        """Test that system plan read errors return None."""
        plan = Plan(slug="test", project="test")
        ctx = PlanContext(project_root=tmp_path, project="test", plan=plan)

        # Create invalid system plan
        cub_dir = tmp_path / ".cub"
        cub_dir.mkdir()
        system_plan = cub_dir / "SYSTEM-PLAN.md"
        system_plan.write_bytes(b"\xff\xfe# Invalid")

        # Should return None instead of raising
        result = ctx.read_system_plan()
        assert result is None

    def test_ensure_plan_dir_permission_error(self, tmp_path: Path) -> None:
        """Test that directory creation permission errors are raised."""
        plan = Plan(slug="test", project="test")

        # Create a read-only parent directory
        read_only = tmp_path / "readonly"
        read_only.mkdir()
        read_only.chmod(0o444)

        try:
            ctx = PlanContext(
                project_root=read_only,
                project="test",
                plan=plan,
            )

            with pytest.raises(OSError, match="Cannot create plan directory"):
                ctx.ensure_plan_dir()
        finally:
            # Cleanup
            read_only.chmod(0o755)


class TestStagerErrorHandling:
    """Test error handling in Stager."""

    def test_backend_detection_failure(self, tmp_path: Path) -> None:
        """Test that backend detection failures raise StagerError."""
        plan_dir = tmp_path / "test-plan"
        plan_dir.mkdir()

        plan = Plan(slug="test-plan", project="test", status=PlanStatus.COMPLETE)
        plan.complete_stage(PlanStage.ORIENT)
        plan.complete_stage(PlanStage.ARCHITECT)
        plan.complete_stage(PlanStage.ITEMIZE)

        ctx = PlanContext(project_root=tmp_path, project="test", plan=plan)
        stager = Stager(ctx)

        # Mock get_backend to raise ValueError
        with patch("cub.core.stage.stager.get_backend", side_effect=ValueError("No backend found")):
            with pytest.raises(StagerError, match="Cannot detect task backend"):
                _ = stager.backend

    def test_empty_plan_raises_error(self, tmp_path: Path) -> None:
        """Test that staging an empty plan raises StagerError."""
        # Create plans directory structure
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_dir = plans_dir / "empty-plan"
        plan_dir.mkdir()

        plan = Plan(slug="empty-plan", project="test", status=PlanStatus.COMPLETE)
        plan.complete_stage(PlanStage.ORIENT)
        plan.complete_stage(PlanStage.ARCHITECT)
        plan.complete_stage(PlanStage.ITEMIZE)

        ctx = PlanContext(project_root=tmp_path, project="test", plan=plan)

        # Create empty itemized-plan.md
        itemized_path = plan_dir / "itemized-plan.md"
        itemized_path.write_text(
            "# Itemized Plan: Empty\n\n## Summary\n\nNo epics or tasks.",
            encoding="utf-8"
        )

        # Create a mock backend
        mock_backend = Mock()
        stager = Stager(ctx, backend=mock_backend)

        with pytest.raises(StagerError, match="no epics or tasks|Cannot stage an empty plan"):
            stager.stage()

    def test_invalid_task_parent_raises_error(self, tmp_path: Path) -> None:
        """Test that tasks with invalid parent IDs raise StagerError.

        This tests the validation logic by manually creating a ParsedTask
        with an invalid parent reference.
        """
        # Create plans directory structure
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_dir = plans_dir / "invalid-parent"
        plan_dir.mkdir()

        plan = Plan(slug="invalid-parent", project="test", status=PlanStatus.COMPLETE)
        plan.complete_stage(PlanStage.ORIENT)
        plan.complete_stage(PlanStage.ARCHITECT)
        plan.complete_stage(PlanStage.ITEMIZE)

        ctx = PlanContext(project_root=tmp_path, project="test", plan=plan)

        # Create itemized-plan.md
        itemized_path = plan_dir / "itemized-plan.md"
        itemized_path.write_text(
            """# Itemized Plan: Test

## Epic: cub-abc - Test Epic
Priority: 0
Labels: test

### Task: cub-abc.1 - Test Task
Priority: 0
Labels: test

**Context**: Test context.
""",
            encoding="utf-8"
        )

        mock_backend = Mock()
        stager = Stager(ctx, backend=mock_backend)

        # Manually create a scenario with invalid parent by patching parse_plan
        from cub.core.plan.parser import ParsedEpic, ParsedPlan, ParsedTask, PlanMetadata

        invalid_parsed_plan = ParsedPlan(
            metadata=PlanMetadata(title="Test"),
            epics=[ParsedEpic(id="cub-abc", title="Test Epic")],
            tasks=[ParsedTask(id="cub-xyz.1", title="Orphan Task", epic_id="cub-xyz")],
            raw_content="",
        )

        with patch.object(stager, 'parse_plan', return_value=invalid_parsed_plan):
            with pytest.raises(StagerError, match="references non-existent epic"):
                stager.stage()

    def test_backend_import_count_mismatch_raises_error(self, tmp_path: Path) -> None:
        """Test that backend import count mismatches raise TaskImportError."""
        # Create plans directory structure
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_dir = plans_dir / "mismatch"
        plan_dir.mkdir()

        plan = Plan(slug="mismatch", project="test", status=PlanStatus.COMPLETE)
        plan.complete_stage(PlanStage.ORIENT)
        plan.complete_stage(PlanStage.ARCHITECT)
        plan.complete_stage(PlanStage.ITEMIZE)

        ctx = PlanContext(project_root=tmp_path, project="test", plan=plan)

        # Create valid itemized-plan.md
        itemized_path = plan_dir / "itemized-plan.md"
        itemized_path.write_text(
            """# Itemized Plan: Test

## Epic: cub-abc - Test Epic
Priority: 0
Labels: test

### Task: cub-abc.1 - Test Task
Priority: 0
Labels: test

**Context**: Test context.
""",
            encoding="utf-8"
        )

        # Mock backend to return wrong number of items
        mock_backend = Mock()
        # Backend returns empty list (wrong count)
        mock_backend.import_tasks.side_effect = [[], []]

        stager = Stager(ctx, backend=mock_backend)

        with pytest.raises(TaskImportError, match="Backend import mismatch"):
            stager.stage()


class TestParserPriorityValidation:
    """Test priority validation in parser."""

    def test_priority_overflow_handled(self, tmp_path: Path) -> None:
        """Test that priority overflow is handled gracefully."""
        plan_file = tmp_path / "overflow.md"
        plan_file.write_text(
            """# Itemized Plan: Overflow Test

## Epic: cub-abc - Test Epic
Priority: 999999999999999999999999999999
Labels: test

### Task: cub-abc.1 - Test Task
Priority: 999999999999999999999999999999
Labels: test

**Context**: Test.
""",
            encoding="utf-8"
        )

        # Should not raise, priority should default to 0
        result = parse_itemized_plan(plan_file)
        assert result.epics[0].priority == 0
        assert result.tasks[0].priority == 0

    def test_negative_priority_ignored(self, tmp_path: Path) -> None:
        """Test that negative priorities are ignored."""
        plan_file = tmp_path / "negative.md"
        plan_file.write_text(
            """# Itemized Plan: Negative Priority

## Epic: cub-abc - Test Epic
Priority: -5
Labels: test

### Task: cub-abc.1 - Test Task
Priority: -1
Labels: test

**Context**: Test.
""",
            encoding="utf-8"
        )

        result = parse_itemized_plan(plan_file)
        # Negative priorities should be ignored, defaulting to 0
        assert result.epics[0].priority == 0
        assert result.tasks[0].priority == 0

    def test_priority_out_of_range(self, tmp_path: Path) -> None:
        """Test that priorities > 9 are ignored."""
        plan_file = tmp_path / "outofrange.md"
        plan_file.write_text(
            """# Itemized Plan: Out of Range

## Epic: cub-abc - Test Epic
Priority: 50
Labels: test

### Task: cub-abc.1 - Test Task
Priority: 100
Labels: test

**Context**: Test.
""",
            encoding="utf-8"
        )

        result = parse_itemized_plan(plan_file)
        # Out of range priorities should be ignored, defaulting to 0
        assert result.epics[0].priority == 0
        assert result.tasks[0].priority == 0
