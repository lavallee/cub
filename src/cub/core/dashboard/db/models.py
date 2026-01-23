"""
Pydantic models for the dashboard entities and API responses.

These models provide type-safe data structures for:
- DashboardEntity: Core entity model with all fields from various sources
- Relationship: Links between entities (spec -> plan -> task -> ledger)
- BoardColumn/BoardResponse: API response models for the Kanban board
- ViewConfig: View configuration models for customizing board display
- SyncState/SyncResult: Sync orchestration models

These models are used throughout the sync layer and API to ensure
consistent, validated data structures.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EntityType(str, Enum):
    """Entity types in the dashboard.

    These represent the different kinds of entities that can appear
    on the Kanban board, corresponding to different phases of work.
    """

    CAPTURE = "capture"
    SPEC = "spec"
    PLAN = "plan"
    EPIC = "epic"
    TASK = "task"
    LEDGER = "ledger"
    RELEASE = "release"


class Stage(str, Enum):
    """Lifecycle stages for the 8-column Kanban board.

    These stages represent the progression of work from initial capture
    through release. The architecture doc describes the stage computation
    logic that maps entities to these stages based on their type and status.

    Columns:
    - CAPTURES: Raw ideas and notes (capture entities)
    - SPECS: Specifications being researched (spec entities in researching/)
    - PLANNED: Plans exist but not staged (spec entities in planned/, plan entities)
    - READY: Tasks ready to work (tasks with status=open, no blockers)
    - IN_PROGRESS: Active work (tasks with status=in_progress, specs in implementing/)
    - NEEDS_REVIEW: Awaiting review (tasks with 'pr' label or status=review)
    - COMPLETE: Done but not released (tasks with ledger entry, specs in completed/)
    - RELEASED: Shipped (tasks in CHANGELOG, specs in released/)
    """

    CAPTURES = "CAPTURES"
    SPECS = "SPECS"
    PLANNED = "PLANNED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    COMPLETE = "COMPLETE"
    RELEASED = "RELEASED"


class RelationType(str, Enum):
    """Relationship types between entities.

    These define how entities are linked together, enabling
    navigation and traceability from captures through to releases.
    """

    CONTAINS = "contains"  # Parent contains child (epic -> task)
    BLOCKS = "blocks"  # Entity blocks another
    REFERENCES = "references"  # Generic reference link
    SPEC_TO_PLAN = "spec_to_plan"  # Spec generated a plan
    PLAN_TO_EPIC = "plan_to_epic"  # Plan created an epic
    EPIC_TO_TASK = "epic_to_task"  # Epic contains task
    TASK_TO_LEDGER = "task_to_ledger"  # Task has ledger entry
    TASK_TO_RELEASE = "task_to_release"  # Task included in release
    DEPENDS_ON = "depends_on"  # Task dependency


class DashboardEntity(BaseModel):
    """Core entity model for dashboard visualization.

    This model aggregates data from multiple sources (specs, plans, tasks,
    ledger) into a unified representation suitable for the Kanban board.

    Entity lifecycle:
    1. Capture: Raw idea/note captured
    2. Spec: Specification written and researched
    3. Plan: Implementation plan created
    4. Epic/Task: Broken down into executable tasks
    5. Ledger: Task completed, recorded in ledger
    6. Release: Work shipped to production

    Example:
        >>> entity = DashboardEntity(
        ...     id="cub-k8d.2",
        ...     type=EntityType.TASK,
        ...     title="Create Pydantic models",
        ...     stage=Stage.IN_PROGRESS,
        ...     status="in_progress",
        ...     priority=0,
        ...     labels=["complexity:medium", "foundation"],
        ...     source_type="beads",
        ...     source_path=".beads/issues.jsonl"
        ... )
    """

    # Core identification
    id: str = Field(..., description="Unique entity identifier")
    type: EntityType = Field(..., description="Entity type")
    title: str = Field(..., description="Display title")
    description: str | None = Field(default=None, description="Full description/content")

    # Lifecycle tracking
    stage: Stage = Field(..., description="Current stage for board column placement")
    status: str | None = Field(default=None, description="Raw status from source")
    priority: int | None = Field(
        default=None, ge=0, le=4, description="Priority level (0=P0/highest, 4=P4/lowest)"
    )
    labels: list[str] = Field(default_factory=list, description="Tags/labels for filtering")

    # Timestamps
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")

    # Hierarchy references (explicit relationship markers)
    parent_id: str | None = Field(default=None, description="Immediate parent entity")
    spec_id: str | None = Field(default=None, description="Originating spec")
    plan_id: str | None = Field(default=None, description="Originating plan")
    epic_id: str | None = Field(default=None, description="Parent epic (for tasks)")

    # Metrics (from ledger)
    cost_usd: float | None = Field(default=None, ge=0.0, description="Cost in USD")
    tokens: int | None = Field(default=None, ge=0, description="Token usage")
    duration_seconds: int | None = Field(default=None, ge=0, description="Duration in seconds")
    verification_status: str | None = Field(
        default=None, description="Verification status (pass/fail/warn/skip/pending/error)"
    )

    # Source tracking (for incremental sync)
    source_type: str = Field(..., description="Source type (file/beads/json)")
    source_path: str = Field(..., description="File path or identifier")
    source_checksum: str | None = Field(
        default=None, description="Checksum for incremental sync detection"
    )

    # Rich content for detail view
    content: str | None = Field(
        default=None, description="Raw content (markdown, description, etc.)"
    )
    frontmatter: dict[str, Any] | None = Field(
        default=None, description="Parsed frontmatter (for specs/captures)"
    )

    # Card metadata (extracted during sync for display)
    readiness_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Spec readiness assessment (0.0-1.0)"
    )
    task_count: int | None = Field(
        default=None, ge=0, description="Number of child tasks (for epics/plans)"
    )
    epic_count: int | None = Field(
        default=None, ge=0, description="Number of epics (for plans)"
    )
    notes_count: int | None = Field(
        default=None, ge=0, description="Number of notes/comments (for specs)"
    )
    description_excerpt: str | None = Field(
        default=None, description="Brief description excerpt for cards (max 100 chars)"
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @property
    def is_complete(self) -> bool:
        """Check if entity is in a completed stage."""
        return self.stage in (Stage.COMPLETE, Stage.RELEASED)

    @property
    def priority_display(self) -> str:
        """Get display string for priority (e.g., 'P0', 'P2')."""
        if self.priority is not None:
            return f"P{self.priority}"
        return ""


class Relationship(BaseModel):
    """Link between two entities.

    Relationships enable navigation and traceability across the board.
    For example, clicking a task can show its parent epic, originating spec,
    related plan, and ledger entry.

    Example:
        >>> rel = Relationship(
        ...     source_id="cub-k8d",
        ...     target_id="cub-k8d.2",
        ...     rel_type=RelationType.EPIC_TO_TASK
        ... )
    """

    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    rel_type: RelationType = Field(..., description="Relationship type")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional context")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class ColumnConfig(BaseModel):
    """Configuration for a single board column.

    Columns map to stages and can optionally group entities by
    a field like epic_id or spec_id for hierarchical display.

    Example:
        >>> col = ColumnConfig(
        ...     id="in_progress",
        ...     title="In Progress",
        ...     stages=[Stage.IN_PROGRESS],
        ...     group_by="epic_id"
        ... )
    """

    id: str = Field(..., description="Column identifier")
    title: str = Field(..., description="Display title")
    stages: list[Stage] = Field(..., description="Stages to include in this column")
    group_by: str | None = Field(
        default=None,
        description="Optional field to group by (e.g., 'epic_id', 'spec_id')",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )


class FilterConfig(BaseModel):
    """Filters to apply to board entities.

    Example:
        >>> filters = FilterConfig(
        ...     exclude_labels=["archived"],
        ...     include_types=[EntityType.TASK, EntityType.EPIC]
        ... )
    """

    exclude_labels: list[str] = Field(
        default_factory=list, description="Labels to exclude from view"
    )
    include_labels: list[str] = Field(
        default_factory=list, description="If set, only include entities with these labels"
    )
    exclude_types: list[EntityType] = Field(
        default_factory=list, description="Entity types to exclude"
    )
    include_types: list[EntityType] = Field(
        default_factory=list, description="If set, only include these entity types"
    )
    min_priority: int | None = Field(
        default=None, ge=0, le=4, description="Minimum priority (0=P0, 4=P4)"
    )
    max_priority: int | None = Field(
        default=None, ge=0, le=4, description="Maximum priority (0=P0, 4=P4)"
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )


class DisplayConfig(BaseModel):
    """Display settings for the board.

    Example:
        >>> display = DisplayConfig(
        ...     show_cost=True,
        ...     card_size="compact"
        ... )
    """

    show_cost: bool = Field(default=True, description="Show cost metrics on cards")
    show_tokens: bool = Field(default=False, description="Show token usage on cards")
    show_duration: bool = Field(default=False, description="Show duration on cards")
    card_size: str = Field(default="compact", description="Card size (compact/normal/detailed)")
    group_collapsed: bool = Field(default=False, description="Collapse groups by default")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class ViewConfig(BaseModel):
    """View configuration defining how the board is displayed.

    Views are stored as YAML files in .cub/views/ and define which
    columns to show, how to group entities, and what filters to apply.

    Default views:
    - default: Full 8-column workflow
    - sprint: Ready -> In Progress -> Review -> Complete
    - ideas: Captures -> Specs -> Planned

    Example:
        >>> view = ViewConfig(
        ...     id="default",
        ...     name="Full Workflow",
        ...     description="Complete workflow from captures to released",
        ...     columns=[
        ...         ColumnConfig(id="captures", title="Captures", stages=[Stage.CAPTURES]),
        ...         ColumnConfig(id="specs", title="Specs", stages=[Stage.SPECS]),
        ...         # ... more columns
        ...     ],
        ...     filters=FilterConfig(exclude_labels=["archived"]),
        ...     display=DisplayConfig(show_cost=True)
        ... )
    """

    id: str = Field(..., description="View identifier")
    name: str = Field(..., description="Display name")
    description: str | None = Field(default=None, description="View description")
    columns: list[ColumnConfig] = Field(..., description="Column configurations")
    filters: FilterConfig | None = Field(default=None, description="Entity filters")
    display: DisplayConfig | None = Field(default=None, description="Display settings")
    is_default: bool = Field(default=False, description="Is this the default view")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class BoardColumn(BaseModel):
    """A single column in the board response.

    Contains the column configuration and the entities that belong
    in this column based on their stage.

    Example:
        >>> column = BoardColumn(
        ...     id="in_progress",
        ...     title="In Progress",
        ...     stage=Stage.IN_PROGRESS,
        ...     entities=[entity1, entity2],
        ...     count=2
        ... )
    """

    id: str = Field(..., description="Column identifier")
    title: str = Field(..., description="Display title")
    stage: Stage = Field(..., description="Primary stage for this column")
    entities: list[DashboardEntity] = Field(..., description="Entities in this column")
    count: int = Field(..., ge=0, description="Number of entities")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class BoardStats(BaseModel):
    """Summary statistics for the board.

    Provides aggregate metrics across all entities for display
    in a stats bar or summary section.

    Example:
        >>> stats = BoardStats(
        ...     total=47,
        ...     by_stage={Stage.IN_PROGRESS: 5, Stage.READY: 8},
        ...     by_type={EntityType.TASK: 25, EntityType.SPEC: 12},
        ...     cost_total=12.47,
        ...     tokens_total=523000
        ... )
    """

    total: int = Field(default=0, ge=0, description="Total entity count")
    by_stage: dict[Stage, int] = Field(default_factory=dict, description="Entity counts by stage")
    by_type: dict[EntityType, int] = Field(
        default_factory=dict, description="Entity counts by type"
    )
    cost_total: float = Field(default=0.0, ge=0.0, description="Total cost in USD")
    tokens_total: int = Field(default=0, ge=0, description="Total token usage")
    duration_total_seconds: int = Field(default=0, ge=0, description="Total duration in seconds")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class BoardResponse(BaseModel):
    """Full board response for GET /api/board.

    This is the primary API response that the frontend consumes
    to render the Kanban board.

    Example:
        >>> response = BoardResponse(
        ...     view=view_config,
        ...     columns=[column1, column2],
        ...     stats=stats
        ... )
    """

    view: ViewConfig = Field(..., description="View configuration")
    columns: list[BoardColumn] = Field(..., description="Board columns with entities")
    stats: BoardStats = Field(..., description="Summary statistics")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class EntityDetail(BaseModel):
    """Detailed entity response for GET /api/entity/{id}.

    Provides full entity data plus related entities and relationships
    for the detail panel view.

    Example:
        >>> detail = EntityDetail(
        ...     entity=entity,
        ...     relationships=RelationshipDetail(
        ...         parent=parent_entity,
        ...         children=[child1, child2],
        ...         spec=spec_entity
        ...     ),
        ...     content="## Description\\n..."
        ... )
    """

    entity: DashboardEntity = Field(..., description="The entity")
    relationships: dict[str, list[DashboardEntity] | DashboardEntity | None] = Field(
        default_factory=dict, description="Related entities by relationship type"
    )
    content: str | None = Field(default=None, description="Full content (markdown/text)")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class ViewSummary(BaseModel):
    """Summary of a view for GET /api/views.

    Lightweight representation for listing available views.

    Example:
        >>> summary = ViewSummary(
        ...     id="default",
        ...     name="Full Workflow",
        ...     is_default=True
        ... )
    """

    id: str = Field(..., description="View identifier")
    name: str = Field(..., description="Display name")
    description: str | None = Field(default=None, description="View description")
    is_default: bool = Field(default=False, description="Is this the default view")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class SyncState(BaseModel):
    """Sync state tracking for incremental sync.

    Stored in SQLite to track which sources have been synced
    and their checksums for detecting changes.

    Example:
        >>> state = SyncState(
        ...     source="specs/planned/auth.md",
        ...     checksum="abc123def456",
        ...     last_synced=datetime.now(),
        ...     entity_count=1
        ... )
    """

    source: str = Field(..., description="Source identifier (file path, etc.)")
    checksum: str = Field(..., description="Content checksum (for change detection)")
    last_synced: datetime = Field(..., description="When this source was last synced")
    entity_count: int = Field(default=0, ge=0, description="Number of entities from source")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class SyncResult(BaseModel):
    """Result of a sync operation.

    Returned by sync orchestrator to report what was synced and
    any errors encountered.

    Example:
        >>> result = SyncResult(
        ...     success=True,
        ...     entities_added=12,
        ...     entities_updated=5,
        ...     entities_removed=2,
        ...     relationships_added=18,
        ...     duration_seconds=2.5
        ... )
    """

    success: bool = Field(..., description="Whether sync completed successfully")
    entities_added: int = Field(default=0, ge=0, description="Entities added")
    entities_updated: int = Field(default=0, ge=0, description="Entities updated")
    entities_removed: int = Field(default=0, ge=0, description="Entities removed")
    relationships_added: int = Field(default=0, ge=0, description="Relationships added")
    relationships_removed: int = Field(default=0, ge=0, description="Relationships removed")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Sync duration")
    sources_synced: list[str] = Field(default_factory=list, description="List of sources processed")

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @property
    def total_changes(self) -> int:
        """Total number of changes (additions + updates + removals)."""
        return self.entities_added + self.entities_updated + self.entities_removed
