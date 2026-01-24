"""
Tests for dashboard Pydantic models.

Tests validate:
- Model construction and validation
- Enum values
- Field constraints (ge, le, min_length)
- Computed properties
- Model serialization/deserialization
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cub.core.dashboard.db.models import (
    BoardColumn,
    BoardResponse,
    BoardStats,
    ColumnConfig,
    DashboardEntity,
    DisplayConfig,
    EntityDetail,
    EntityType,
    FilterConfig,
    Relationship,
    RelationType,
    Stage,
    SyncResult,
    SyncState,
    ViewConfig,
    ViewSummary,
)


class TestEnums:
    """Tests for enum values and properties."""

    def test_entity_type_values(self):
        """Test EntityType enum values."""
        assert EntityType.CAPTURE == "capture"
        assert EntityType.SPEC == "spec"
        assert EntityType.PLAN == "plan"
        assert EntityType.EPIC == "epic"
        assert EntityType.TASK == "task"
        assert EntityType.LEDGER == "ledger"
        assert EntityType.RELEASE == "release"

    def test_stage_values(self):
        """Test Stage enum values for 8-column board."""
        assert Stage.CAPTURES == "CAPTURES"
        assert Stage.RESEARCHING == "RESEARCHING"
        assert Stage.PLANNED == "PLANNED"
        assert Stage.READY == "READY"
        assert Stage.IN_PROGRESS == "IN_PROGRESS"
        assert Stage.NEEDS_REVIEW == "NEEDS_REVIEW"
        assert Stage.COMPLETE == "COMPLETE"
        assert Stage.RELEASED == "RELEASED"

    def test_relation_type_values(self):
        """Test RelationType enum values."""
        assert RelationType.CONTAINS == "contains"
        assert RelationType.BLOCKS == "blocks"
        assert RelationType.REFERENCES == "references"
        assert RelationType.SPEC_TO_PLAN == "spec_to_plan"
        assert RelationType.PLAN_TO_EPIC == "plan_to_epic"
        assert RelationType.EPIC_TO_TASK == "epic_to_task"
        assert RelationType.TASK_TO_LEDGER == "task_to_ledger"
        assert RelationType.TASK_TO_RELEASE == "task_to_release"
        assert RelationType.DEPENDS_ON == "depends_on"


class TestDashboardEntity:
    """Tests for DashboardEntity model."""

    def test_minimal_entity(self):
        """Test entity with only required fields."""
        entity = DashboardEntity(
            id="test-001",
            type=EntityType.TASK,
            title="Test task",
            stage=Stage.READY,
            source_type="beads",
            source_path=".beads/issues.jsonl",
        )

        assert entity.id == "test-001"
        assert entity.type == EntityType.TASK
        assert entity.title == "Test task"
        assert entity.stage == Stage.READY
        assert entity.source_type == "beads"
        assert entity.source_path == ".beads/issues.jsonl"
        assert entity.labels == []
        assert entity.description is None

    def test_full_entity(self):
        """Test entity with all fields populated."""
        now = datetime.now(timezone.utc)
        entity = DashboardEntity(
            id="cub-k8d.2",
            type=EntityType.TASK,
            title="Create Pydantic models",
            description="Implement models for dashboard entities",
            stage=Stage.IN_PROGRESS,
            status="in_progress",
            priority=0,
            labels=["complexity:medium", "foundation", "model:sonnet"],
            created_at=now,
            updated_at=now,
            completed_at=None,
            parent_id="cub-k8d",
            spec_id="project-kanban-dashboard",
            plan_id="session-123",
            epic_id="cub-k8d",
            cost_usd=0.12,
            tokens=15000,
            duration_seconds=1800,
            verification_status="pass",
            source_type="beads",
            source_path=".beads/issues.jsonl",
            source_checksum="abc123",
            content="Full task description here",
            frontmatter={"priority": "P0", "type": "task"},
        )

        assert entity.id == "cub-k8d.2"
        assert entity.priority == 0
        assert entity.cost_usd == 0.12
        assert entity.tokens == 15000
        assert entity.duration_seconds == 1800
        assert entity.verification_status == "pass"
        assert entity.parent_id == "cub-k8d"
        assert entity.spec_id == "project-kanban-dashboard"
        assert len(entity.labels) == 3

    def test_priority_validation(self):
        """Test priority field constraints (0-4)."""
        # Valid priorities
        for priority in range(5):
            entity = DashboardEntity(
                id="test",
                type=EntityType.TASK,
                title="Test",
                stage=Stage.READY,
                priority=priority,
                source_type="test",
                source_path="test",
            )
            assert entity.priority == priority

        # Invalid priorities
        with pytest.raises(ValidationError):
            DashboardEntity(
                id="test",
                type=EntityType.TASK,
                title="Test",
                stage=Stage.READY,
                priority=5,  # Too high
                source_type="test",
                source_path="test",
            )

        with pytest.raises(ValidationError):
            DashboardEntity(
                id="test",
                type=EntityType.TASK,
                title="Test",
                stage=Stage.READY,
                priority=-1,  # Negative
                source_type="test",
                source_path="test",
            )

    def test_is_complete_property(self):
        """Test is_complete computed property."""
        entity_complete = DashboardEntity(
            id="test-1",
            type=EntityType.TASK,
            title="Complete task",
            stage=Stage.COMPLETE,
            source_type="test",
            source_path="test",
        )
        assert entity_complete.is_complete is True

        entity_released = DashboardEntity(
            id="test-2",
            type=EntityType.TASK,
            title="Released task",
            stage=Stage.RELEASED,
            source_type="test",
            source_path="test",
        )
        assert entity_released.is_complete is True

        entity_in_progress = DashboardEntity(
            id="test-3",
            type=EntityType.TASK,
            title="In progress task",
            stage=Stage.IN_PROGRESS,
            source_type="test",
            source_path="test",
        )
        assert entity_in_progress.is_complete is False

    def test_priority_display_property(self):
        """Test priority_display computed property."""
        entity_p0 = DashboardEntity(
            id="test",
            type=EntityType.TASK,
            title="Test",
            stage=Stage.READY,
            priority=0,
            source_type="test",
            source_path="test",
        )
        assert entity_p0.priority_display == "P0"

        entity_p2 = DashboardEntity(
            id="test",
            type=EntityType.TASK,
            title="Test",
            stage=Stage.READY,
            priority=2,
            source_type="test",
            source_path="test",
        )
        assert entity_p2.priority_display == "P2"

        entity_no_priority = DashboardEntity(
            id="test",
            type=EntityType.TASK,
            title="Test",
            stage=Stage.READY,
            source_type="test",
            source_path="test",
        )
        assert entity_no_priority.priority_display == ""

    def test_entity_serialization(self):
        """Test entity can be serialized to dict."""
        entity = DashboardEntity(
            id="test",
            type=EntityType.TASK,
            title="Test task",
            stage=Stage.READY,
            priority=1,
            labels=["test"],
            source_type="test",
            source_path="test",
        )

        data = entity.model_dump()
        assert data["id"] == "test"
        assert data["type"] == "task"
        assert data["stage"] == "READY"
        assert data["priority"] == 1
        assert data["labels"] == ["test"]


class TestRelationship:
    """Tests for Relationship model."""

    def test_minimal_relationship(self):
        """Test relationship with required fields."""
        rel = Relationship(
            source_id="cub-k8d",
            target_id="cub-k8d.2",
            rel_type=RelationType.EPIC_TO_TASK,
        )

        assert rel.source_id == "cub-k8d"
        assert rel.target_id == "cub-k8d.2"
        assert rel.rel_type == RelationType.EPIC_TO_TASK
        assert rel.metadata is None

    def test_relationship_with_metadata(self):
        """Test relationship with metadata."""
        rel = Relationship(
            source_id="spec-auth",
            target_id="plan-123",
            rel_type=RelationType.SPEC_TO_PLAN,
            metadata={"created_at": "2026-01-23", "confidence": "high"},
        )

        assert rel.metadata is not None
        assert rel.metadata["created_at"] == "2026-01-23"
        assert rel.metadata["confidence"] == "high"


class TestViewConfiguration:
    """Tests for view configuration models."""

    def test_column_config(self):
        """Test ColumnConfig model."""
        column = ColumnConfig(
            id="in_progress",
            title="In Progress",
            stages=[Stage.IN_PROGRESS],
            group_by="epic_id",
        )

        assert column.id == "in_progress"
        assert column.title == "In Progress"
        assert column.stages == [Stage.IN_PROGRESS]
        assert column.group_by == "epic_id"

    def test_filter_config(self):
        """Test FilterConfig model."""
        filters = FilterConfig(
            exclude_labels=["archived"],
            include_types=[EntityType.TASK, EntityType.EPIC],
            min_priority=0,
            max_priority=2,
        )

        assert filters.exclude_labels == ["archived"]
        assert filters.include_types == [EntityType.TASK, EntityType.EPIC]
        assert filters.min_priority == 0
        assert filters.max_priority == 2

    def test_filter_config_defaults(self):
        """Test FilterConfig with defaults."""
        filters = FilterConfig()

        assert filters.exclude_labels == []
        assert filters.include_labels == []
        assert filters.exclude_types == []
        assert filters.include_types == []
        assert filters.min_priority is None
        assert filters.max_priority is None

    def test_display_config(self):
        """Test DisplayConfig model."""
        display = DisplayConfig(
            show_cost=True,
            show_tokens=False,
            card_size="compact",
        )

        assert display.show_cost is True
        assert display.show_tokens is False
        assert display.card_size == "compact"

    def test_display_config_defaults(self):
        """Test DisplayConfig defaults."""
        display = DisplayConfig()

        assert display.show_cost is True
        assert display.show_tokens is False
        assert display.show_duration is False
        assert display.card_size == "compact"
        assert display.group_collapsed is False

    def test_view_config(self):
        """Test ViewConfig model."""
        view = ViewConfig(
            id="default",
            name="Full Workflow",
            description="Complete workflow",
            columns=[
                ColumnConfig(
                    id="captures", title="Captures", stages=[Stage.CAPTURES]
                ),
                ColumnConfig(id="specs", title="Researching", stages=[Stage.RESEARCHING]),
            ],
            filters=FilterConfig(exclude_labels=["archived"]),
            display=DisplayConfig(show_cost=True),
            is_default=True,
        )

        assert view.id == "default"
        assert view.name == "Full Workflow"
        assert len(view.columns) == 2
        assert view.is_default is True
        assert view.filters is not None
        assert view.display is not None


class TestBoardResponse:
    """Tests for board API response models."""

    def test_board_column(self):
        """Test BoardColumn model."""
        entity = DashboardEntity(
            id="test",
            type=EntityType.TASK,
            title="Test",
            stage=Stage.READY,
            source_type="test",
            source_path="test",
        )

        column = BoardColumn(
            id="ready",
            title="Ready",
            stage=Stage.READY,
            entities=[entity],
            count=1,
        )

        assert column.id == "ready"
        assert column.title == "Ready"
        assert column.stage == Stage.READY
        assert len(column.entities) == 1
        assert column.count == 1

    def test_board_stats(self):
        """Test BoardStats model."""
        stats = BoardStats(
            total=47,
            by_stage={Stage.READY: 8, Stage.IN_PROGRESS: 5},
            by_type={EntityType.TASK: 25, EntityType.SPEC: 12},
            cost_total=12.47,
            tokens_total=523000,
            duration_total_seconds=15600,
        )

        assert stats.total == 47
        assert stats.by_stage[Stage.READY] == 8
        assert stats.by_type[EntityType.TASK] == 25
        assert stats.cost_total == 12.47
        assert stats.tokens_total == 523000

    def test_board_stats_defaults(self):
        """Test BoardStats with defaults."""
        stats = BoardStats()

        assert stats.total == 0
        assert stats.by_stage == {}
        assert stats.by_type == {}
        assert stats.cost_total == 0.0
        assert stats.tokens_total == 0

    def test_board_response(self):
        """Test BoardResponse model."""
        view = ViewConfig(
            id="default",
            name="Default",
            columns=[
                ColumnConfig(id="ready", title="Ready", stages=[Stage.READY])
            ],
        )

        entity = DashboardEntity(
            id="test",
            type=EntityType.TASK,
            title="Test",
            stage=Stage.READY,
            source_type="test",
            source_path="test",
        )

        column = BoardColumn(
            id="ready",
            title="Ready",
            stage=Stage.READY,
            entities=[entity],
            count=1,
        )

        stats = BoardStats(total=1)

        response = BoardResponse(view=view, columns=[column], stats=stats)

        assert response.view.id == "default"
        assert len(response.columns) == 1
        assert response.stats.total == 1

    def test_entity_detail(self):
        """Test EntityDetail model."""
        entity = DashboardEntity(
            id="cub-k8d.2",
            type=EntityType.TASK,
            title="Test task",
            stage=Stage.IN_PROGRESS,
            source_type="test",
            source_path="test",
        )

        parent = DashboardEntity(
            id="cub-k8d",
            type=EntityType.EPIC,
            title="Parent epic",
            stage=Stage.IN_PROGRESS,
            source_type="test",
            source_path="test",
        )

        detail = EntityDetail(
            entity=entity,
            relationships={"parent": parent, "children": []},
            content="Full task content",
        )

        assert detail.entity.id == "cub-k8d.2"
        assert detail.relationships["parent"].id == "cub-k8d"  # type: ignore
        assert detail.content == "Full task content"

    def test_view_summary(self):
        """Test ViewSummary model."""
        summary = ViewSummary(
            id="default", name="Full Workflow", is_default=True
        )

        assert summary.id == "default"
        assert summary.name == "Full Workflow"
        assert summary.is_default is True


class TestSyncModels:
    """Tests for sync orchestration models."""

    def test_sync_state(self):
        """Test SyncState model."""
        now = datetime.now(timezone.utc)
        state = SyncState(
            source="specs/planned/auth.md",
            checksum="abc123def456",
            last_synced=now,
            entity_count=1,
        )

        assert state.source == "specs/planned/auth.md"
        assert state.checksum == "abc123def456"
        assert state.last_synced == now
        assert state.entity_count == 1

    def test_sync_result(self):
        """Test SyncResult model."""
        result = SyncResult(
            success=True,
            entities_added=12,
            entities_updated=5,
            entities_removed=2,
            relationships_added=18,
            relationships_removed=3,
            duration_seconds=2.5,
            sources_synced=["specs/", ".beads/", ".cub/ledger/"],
        )

        assert result.success is True
        assert result.entities_added == 12
        assert result.entities_updated == 5
        assert result.entities_removed == 2
        assert result.relationships_added == 18
        assert result.duration_seconds == 2.5
        assert len(result.sources_synced) == 3

    def test_sync_result_defaults(self):
        """Test SyncResult with defaults."""
        result = SyncResult(success=True)

        assert result.success is True
        assert result.entities_added == 0
        assert result.entities_updated == 0
        assert result.entities_removed == 0
        assert result.relationships_added == 0
        assert result.relationships_removed == 0
        assert result.errors == []
        assert result.warnings == []
        assert result.duration_seconds == 0.0
        assert result.sources_synced == []

    def test_sync_result_total_changes(self):
        """Test SyncResult total_changes property."""
        result = SyncResult(
            success=True,
            entities_added=12,
            entities_updated=5,
            entities_removed=2,
        )

        assert result.total_changes == 19

    def test_sync_result_with_errors(self):
        """Test SyncResult with errors."""
        result = SyncResult(
            success=False,
            errors=["Failed to parse spec", "Missing required field"],
            warnings=["Deprecated field used"],
        )

        assert result.success is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.errors[0] == "Failed to parse spec"


class TestModelValidation:
    """Tests for model validation rules."""

    def test_entity_requires_all_fields(self):
        """Test that DashboardEntity requires all mandatory fields."""
        with pytest.raises(ValidationError):
            DashboardEntity()  # type: ignore

        with pytest.raises(ValidationError):
            DashboardEntity(id="test")  # type: ignore

    def test_relationship_requires_all_fields(self):
        """Test that Relationship requires all mandatory fields."""
        with pytest.raises(ValidationError):
            Relationship()  # type: ignore

        with pytest.raises(ValidationError):
            Relationship(source_id="test")  # type: ignore

    def test_negative_cost_rejected(self):
        """Test that negative cost is rejected."""
        with pytest.raises(ValidationError):
            DashboardEntity(
                id="test",
                type=EntityType.TASK,
                title="Test",
                stage=Stage.READY,
                cost_usd=-1.0,  # Negative cost
                source_type="test",
                source_path="test",
            )

    def test_negative_tokens_rejected(self):
        """Test that negative tokens is rejected."""
        with pytest.raises(ValidationError):
            DashboardEntity(
                id="test",
                type=EntityType.TASK,
                title="Test",
                stage=Stage.READY,
                tokens=-100,  # Negative tokens
                source_type="test",
                source_path="test",
            )

    def test_negative_duration_rejected(self):
        """Test that negative duration is rejected."""
        with pytest.raises(ValidationError):
            DashboardEntity(
                id="test",
                type=EntityType.TASK,
                title="Test",
                stage=Stage.READY,
                duration_seconds=-60,  # Negative duration
                source_type="test",
                source_path="test",
            )
