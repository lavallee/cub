"""
Unit tests for Plan data models.

Tests validation, serialization, and computed properties for Plan and related enums.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from cub.core.plan.models import (
    Plan,
    PlanStage,
    PlanStatus,
    SpecStage,
    StageStatus,
)

# ==============================================================================
# PlanStatus Enum Tests
# ==============================================================================


class TestPlanStatus:
    """Test PlanStatus enum."""

    def test_plan_status_values(self):
        """Test all PlanStatus enum values exist."""
        assert PlanStatus.PENDING.value == "pending"
        assert PlanStatus.IN_PROGRESS.value == "in_progress"
        assert PlanStatus.COMPLETE.value == "complete"
        assert PlanStatus.STAGED.value == "staged"
        assert PlanStatus.ARCHIVED.value == "archived"

    def test_plan_status_from_string(self):
        """Test creating PlanStatus from string."""
        assert PlanStatus("pending") == PlanStatus.PENDING
        assert PlanStatus("complete") == PlanStatus.COMPLETE

    def test_plan_status_invalid_value(self):
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError):
            PlanStatus("invalid")


# ==============================================================================
# PlanStage Enum Tests
# ==============================================================================


class TestPlanStage:
    """Test PlanStage enum."""

    def test_plan_stage_values(self):
        """Test all PlanStage enum values exist."""
        assert PlanStage.ORIENT.value == "orient"
        assert PlanStage.ARCHITECT.value == "architect"
        assert PlanStage.ITEMIZE.value == "itemize"

    def test_plan_stage_output_files(self):
        """Test output_file property for each stage."""
        assert PlanStage.ORIENT.output_file == "orientation.md"
        assert PlanStage.ARCHITECT.output_file == "architecture.md"
        assert PlanStage.ITEMIZE.output_file == "itemized-plan.md"

    def test_plan_stage_next_stage(self):
        """Test next_stage property."""
        assert PlanStage.ORIENT.next_stage == PlanStage.ARCHITECT
        assert PlanStage.ARCHITECT.next_stage == PlanStage.ITEMIZE
        assert PlanStage.ITEMIZE.next_stage is None

    def test_plan_stage_previous_stage(self):
        """Test previous_stage property."""
        assert PlanStage.ORIENT.previous_stage is None
        assert PlanStage.ARCHITECT.previous_stage == PlanStage.ORIENT
        assert PlanStage.ITEMIZE.previous_stage == PlanStage.ARCHITECT


# ==============================================================================
# StageStatus Enum Tests
# ==============================================================================


class TestStageStatus:
    """Test StageStatus enum."""

    def test_stage_status_values(self):
        """Test all StageStatus enum values exist."""
        assert StageStatus.PENDING.value == "pending"
        assert StageStatus.IN_PROGRESS.value == "in_progress"
        assert StageStatus.COMPLETE.value == "complete"


# ==============================================================================
# SpecStage Enum Tests
# ==============================================================================


class TestSpecStage:
    """Test SpecStage enum."""

    def test_spec_stage_values(self):
        """Test all SpecStage enum values exist."""
        assert SpecStage.RESEARCHING.value == "researching"
        assert SpecStage.PLANNED.value == "planned"
        assert SpecStage.STAGED.value == "staged"
        assert SpecStage.IMPLEMENTING.value == "implementing"
        assert SpecStage.RELEASED.value == "released"

    def test_spec_stage_from_directory(self):
        """Test from_directory classmethod."""
        assert SpecStage.from_directory("researching") == SpecStage.RESEARCHING
        assert SpecStage.from_directory("planned") == SpecStage.PLANNED
        assert SpecStage.from_directory("staged") == SpecStage.STAGED
        assert SpecStage.from_directory("implementing") == SpecStage.IMPLEMENTING
        assert SpecStage.from_directory("released") == SpecStage.RELEASED

    def test_spec_stage_from_directory_invalid(self):
        """Test from_directory with invalid directory name."""
        with pytest.raises(ValueError, match="Unknown spec stage directory"):
            SpecStage.from_directory("invalid")

    def test_spec_stage_is_active(self):
        """Test is_active property (identifies -ing form stages)."""
        # Active stages (-ing form)
        assert SpecStage.RESEARCHING.is_active is True
        assert SpecStage.IMPLEMENTING.is_active is True

        # At-rest stages (past tense form)
        assert SpecStage.PLANNED.is_active is False
        assert SpecStage.STAGED.is_active is False
        assert SpecStage.RELEASED.is_active is False


# ==============================================================================
# Plan Model Tests
# ==============================================================================


class TestPlanModel:
    """Test Plan model validation and behavior."""

    def test_minimal_plan_creation(self):
        """Test creating a plan with minimal required fields."""
        plan = Plan(slug="user-auth", project="cub")
        assert plan.slug == "user-auth"
        assert plan.project == "cub"
        assert plan.status == PlanStatus.PENDING
        assert plan.spec_file is None
        assert all(s == StageStatus.PENDING for s in plan.stages.values())

    def test_full_plan_creation(self):
        """Test creating a plan with all fields."""
        now = datetime.now(timezone.utc)
        plan = Plan(
            slug="api-redesign",
            project="cub",
            status=PlanStatus.IN_PROGRESS,
            spec_file="api-redesign.md",
            stages={
                PlanStage.ORIENT: StageStatus.COMPLETE,
                PlanStage.ARCHITECT: StageStatus.IN_PROGRESS,
                PlanStage.ITEMIZE: StageStatus.PENDING,
            },
            created_at=now,
            updated_at=now,
        )
        assert plan.slug == "api-redesign"
        assert plan.spec_file == "api-redesign.md"
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.IN_PROGRESS

    def test_plan_validation_empty_slug(self):
        """Test that empty slug is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Plan(slug="", project="cub")
        assert "slug" in str(exc_info.value)

    def test_plan_validation_empty_project(self):
        """Test that empty project is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Plan(slug="test", project="")
        assert "project" in str(exc_info.value)


class TestPlanComputedFields:
    """Test Plan computed fields."""

    def test_is_complete(self):
        """Test is_complete computed field."""
        plan = Plan(slug="test", project="cub")
        assert plan.is_complete is False

        # Complete all stages
        plan.stages[PlanStage.ORIENT] = StageStatus.COMPLETE
        plan.stages[PlanStage.ARCHITECT] = StageStatus.COMPLETE
        plan.stages[PlanStage.ITEMIZE] = StageStatus.COMPLETE
        assert plan.is_complete is True

    def test_current_stage(self):
        """Test current_stage computed field."""
        plan = Plan(slug="test", project="cub")
        assert plan.current_stage is None

        plan.stages[PlanStage.ORIENT] = StageStatus.IN_PROGRESS
        assert plan.current_stage == PlanStage.ORIENT

        plan.stages[PlanStage.ORIENT] = StageStatus.COMPLETE
        plan.stages[PlanStage.ARCHITECT] = StageStatus.IN_PROGRESS
        assert plan.current_stage == PlanStage.ARCHITECT

    def test_next_pending_stage(self):
        """Test next_pending_stage computed field."""
        plan = Plan(slug="test", project="cub")
        assert plan.next_pending_stage == PlanStage.ORIENT

        plan.stages[PlanStage.ORIENT] = StageStatus.COMPLETE
        assert plan.next_pending_stage == PlanStage.ARCHITECT

        plan.stages[PlanStage.ARCHITECT] = StageStatus.COMPLETE
        assert plan.next_pending_stage == PlanStage.ITEMIZE

        plan.stages[PlanStage.ITEMIZE] = StageStatus.COMPLETE
        assert plan.next_pending_stage is None

    def test_completed_stages(self):
        """Test completed_stages computed field."""
        plan = Plan(slug="test", project="cub")
        assert plan.completed_stages == []

        plan.stages[PlanStage.ORIENT] = StageStatus.COMPLETE
        assert plan.completed_stages == [PlanStage.ORIENT]

        plan.stages[PlanStage.ARCHITECT] = StageStatus.COMPLETE
        assert plan.completed_stages == [PlanStage.ORIENT, PlanStage.ARCHITECT]


class TestPlanStageMethods:
    """Test Plan stage transition methods."""

    def test_start_stage_first(self):
        """Test starting the first stage."""
        plan = Plan(slug="test", project="cub")
        plan.start_stage(PlanStage.ORIENT)
        assert plan.stages[PlanStage.ORIENT] == StageStatus.IN_PROGRESS
        assert plan.status == PlanStatus.IN_PROGRESS

    def test_start_stage_requires_previous_complete(self):
        """Test that starting a stage requires previous stage complete."""
        plan = Plan(slug="test", project="cub")

        # Cannot start architect without orient complete
        with pytest.raises(ValueError, match="previous stage orient not complete"):
            plan.start_stage(PlanStage.ARCHITECT)

        # Complete orient, now can start architect
        plan.complete_stage(PlanStage.ORIENT)
        plan.start_stage(PlanStage.ARCHITECT)
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.IN_PROGRESS

    def test_complete_stage(self):
        """Test completing a stage."""
        plan = Plan(slug="test", project="cub")
        plan.complete_stage(PlanStage.ORIENT)
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.status == PlanStatus.IN_PROGRESS  # Some stages complete

    def test_complete_all_stages(self):
        """Test that completing all stages sets status to COMPLETE."""
        plan = Plan(slug="test", project="cub")
        plan.complete_stage(PlanStage.ORIENT)
        plan.complete_stage(PlanStage.ARCHITECT)
        plan.complete_stage(PlanStage.ITEMIZE)
        assert plan.status == PlanStatus.COMPLETE
        assert plan.is_complete is True

    def test_mark_staged(self):
        """Test marking a plan as staged."""
        plan = Plan(slug="test", project="cub")
        plan.complete_stage(PlanStage.ORIENT)
        plan.complete_stage(PlanStage.ARCHITECT)
        plan.complete_stage(PlanStage.ITEMIZE)

        plan.mark_staged()
        assert plan.status == PlanStatus.STAGED

    def test_mark_staged_requires_complete(self):
        """Test that staging requires all stages complete."""
        plan = Plan(slug="test", project="cub")
        with pytest.raises(ValueError, match="Cannot stage incomplete plan"):
            plan.mark_staged()

    def test_archive(self):
        """Test archiving a plan."""
        plan = Plan(slug="test", project="cub")
        plan.archive()
        assert plan.status == PlanStatus.ARCHIVED


class TestPlanPaths:
    """Test Plan path-related methods."""

    def test_get_plan_dir(self, tmp_path: Path):
        """Test get_plan_dir method."""
        plan = Plan(slug="user-auth", project="cub")
        plan_dir = plan.get_plan_dir(tmp_path)
        assert plan_dir == tmp_path / "plans" / "user-auth"

    def test_get_stage_output_path(self, tmp_path: Path):
        """Test get_stage_output_path method."""
        plan = Plan(slug="user-auth", project="cub")

        orient_path = plan.get_stage_output_path(PlanStage.ORIENT, tmp_path)
        assert orient_path == tmp_path / "plans" / "user-auth" / "orientation.md"

        architect_path = plan.get_stage_output_path(PlanStage.ARCHITECT, tmp_path)
        assert architect_path == tmp_path / "plans" / "user-auth" / "architecture.md"

        itemize_path = plan.get_stage_output_path(PlanStage.ITEMIZE, tmp_path)
        assert itemize_path == tmp_path / "plans" / "user-auth" / "itemized-plan.md"


class TestPlanSerialization:
    """Test Plan serialization and deserialization."""

    def test_to_json_dict(self):
        """Test converting plan to JSON dict."""
        plan = Plan(
            slug="user-auth",
            project="cub",
            status=PlanStatus.IN_PROGRESS,
            spec_file="user-auth.md",
        )
        plan.stages[PlanStage.ORIENT] = StageStatus.COMPLETE

        data = plan.to_json_dict()

        assert data["slug"] == "user-auth"
        assert data["project"] == "cub"
        assert data["status"] == "in_progress"
        assert data["spec_file"] == "user-auth.md"
        assert data["stages"]["orient"] == "complete"
        assert data["stages"]["architect"] == "pending"
        assert data["stages"]["itemize"] == "pending"
        assert "created" in data
        assert "updated" in data

    def test_from_json_dict(self):
        """Test creating plan from JSON dict."""
        data = {
            "slug": "api-redesign",
            "project": "cub",
            "status": "complete",
            "spec_file": "api-redesign.md",
            "stages": {
                "orient": "complete",
                "architect": "complete",
                "itemize": "complete",
            },
            "created": "2026-01-20T10:30:00+00:00",
            "updated": "2026-01-20T14:45:00+00:00",
        }

        plan = Plan.from_json_dict(data)

        assert plan.slug == "api-redesign"
        assert plan.project == "cub"
        assert plan.status == PlanStatus.COMPLETE
        assert plan.spec_file == "api-redesign.md"
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.COMPLETE

    def test_from_json_dict_partial_stages(self):
        """Test from_json_dict fills in missing stages."""
        data = {
            "slug": "test",
            "project": "cub",
            "stages": {"orient": "complete"},
        }

        plan = Plan.from_json_dict(data)

        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.PENDING
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.PENDING

    def test_from_json_dict_missing_slug(self):
        """Test from_json_dict raises error for missing slug."""
        data = {"project": "cub"}
        with pytest.raises(ValueError, match="Plan must have a slug"):
            Plan.from_json_dict(data)

    def test_from_json_dict_missing_project(self):
        """Test from_json_dict raises error for missing project."""
        data = {"slug": "test"}
        with pytest.raises(ValueError, match="Plan must have a project"):
            Plan.from_json_dict(data)

    def test_round_trip_json(self):
        """Test serialization round-trip through JSON."""
        original = Plan(
            slug="user-auth",
            project="cub",
            status=PlanStatus.IN_PROGRESS,
            spec_file="user-auth.md",
        )
        original.stages[PlanStage.ORIENT] = StageStatus.COMPLETE
        original.stages[PlanStage.ARCHITECT] = StageStatus.IN_PROGRESS

        # To JSON string and back
        json_str = json.dumps(original.to_json_dict())
        data = json.loads(json_str)
        restored = Plan.from_json_dict(data)

        assert restored.slug == original.slug
        assert restored.project == original.project
        assert restored.status == original.status
        assert restored.spec_file == original.spec_file
        assert restored.stages == original.stages


class TestPlanLoadSave:
    """Test Plan load/save functionality."""

    def test_save_creates_directory_and_file(self, tmp_path: Path):
        """Test that save creates the plan directory and plan.json."""
        plan = Plan(slug="user-auth", project="cub", spec_file="user-auth.md")

        plan_file = plan.save(tmp_path)

        assert plan_file.exists()
        assert plan_file == tmp_path / "plans" / "user-auth" / "plan.json"
        assert plan_file.parent.is_dir()

    def test_save_content(self, tmp_path: Path):
        """Test that save writes correct content."""
        plan = Plan(slug="user-auth", project="cub")
        plan.stages[PlanStage.ORIENT] = StageStatus.COMPLETE

        plan_file = plan.save(tmp_path)

        with plan_file.open() as f:
            data = json.load(f)

        assert data["slug"] == "user-auth"
        assert data["project"] == "cub"
        assert data["stages"]["orient"] == "complete"

    def test_load(self, tmp_path: Path):
        """Test loading a plan from directory."""
        # Create plan directory and file
        plan_dir = tmp_path / "plans" / "user-auth"
        plan_dir.mkdir(parents=True)

        plan_data = {
            "slug": "user-auth",
            "project": "cub",
            "status": "in_progress",
            "spec_file": "user-auth.md",
            "stages": {
                "orient": "complete",
                "architect": "in_progress",
                "itemize": "pending",
            },
            "created": "2026-01-20T10:30:00+00:00",
            "updated": "2026-01-20T14:45:00+00:00",
        }

        with (plan_dir / "plan.json").open("w") as f:
            json.dump(plan_data, f)

        plan = Plan.load(plan_dir)

        assert plan.slug == "user-auth"
        assert plan.project == "cub"
        assert plan.status == PlanStatus.IN_PROGRESS
        assert plan.spec_file == "user-auth.md"
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE

    def test_load_missing_file(self, tmp_path: Path):
        """Test loading from directory without plan.json."""
        plan_dir = tmp_path / "plans" / "nonexistent"
        plan_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="No plan.json found"):
            Plan.load(plan_dir)

    def test_save_load_round_trip(self, tmp_path: Path):
        """Test save and load round-trip."""
        original = Plan(
            slug="api-redesign",
            project="cub",
            spec_file="api-redesign.md",
        )
        original.complete_stage(PlanStage.ORIENT)
        original.start_stage(PlanStage.ARCHITECT)

        # Save
        original.save(tmp_path)

        # Load
        plan_dir = tmp_path / "plans" / "api-redesign"
        loaded = Plan.load(plan_dir)

        assert loaded.slug == original.slug
        assert loaded.project == original.project
        assert loaded.status == original.status
        assert loaded.spec_file == original.spec_file
        assert loaded.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert loaded.stages[PlanStage.ARCHITECT] == StageStatus.IN_PROGRESS


# ==============================================================================
# Stages Validator Tests
# ==============================================================================


class TestStagesValidator:
    """Test the stages field validator."""

    def test_stages_from_string_dict(self):
        """Test creating Plan with string dict stages (from JSON)."""
        plan = Plan(
            slug="test",
            project="cub",
            stages={
                "orient": "complete",
                "architect": "in_progress",
                "itemize": "pending",
            },
        )
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.IN_PROGRESS
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.PENDING

    def test_stages_from_enum_dict(self):
        """Test creating Plan with enum dict stages."""
        plan = Plan(
            slug="test",
            project="cub",
            stages={
                PlanStage.ORIENT: StageStatus.COMPLETE,
                PlanStage.ARCHITECT: StageStatus.PENDING,
            },
        )
        assert plan.stages[PlanStage.ORIENT] == StageStatus.COMPLETE
        assert plan.stages[PlanStage.ARCHITECT] == StageStatus.PENDING
        # Missing ITEMIZE should be filled in
        assert plan.stages[PlanStage.ITEMIZE] == StageStatus.PENDING

    def test_stages_empty_dict_fills_defaults(self):
        """Test that empty stages dict fills in defaults."""
        plan = Plan(slug="test", project="cub", stages={})
        assert len(plan.stages) == 3
        assert all(s == StageStatus.PENDING for s in plan.stages.values())
