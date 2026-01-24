"""
Entity API routes for the dashboard.

Provides endpoints for fetching and updating individual entity details:
- GET /api/entity/{id} - Full entity with relationships and content
- PUT /api/entity/{id}/workflow - Update workflow stage (drag-and-drop)
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cub.core.dashboard.db.connection import get_connection
from cub.core.dashboard.db.models import EntityDetail
from cub.core.dashboard.db.queries import get_entity_detail
from cub.core.ledger.models import WorkflowStage
from cub.core.ledger.writer import LedgerWriter

# Map workflow stages to database stage names
WORKFLOW_TO_DB_STAGE: dict[str, str] = {
    "COMPLETE": "completed",
    "NEEDS_REVIEW": "verifying",
    "VALIDATED": "validated",
    "RELEASED": "released",
}

router = APIRouter()


class WorkflowStageUpdate(BaseModel):
    """Request body for updating workflow stage."""

    stage: str  # Stage name (NEEDS_REVIEW, VALIDATED, RELEASED, COMPLETE)


class WorkflowUpdate(BaseModel):
    """Workflow section of entity update."""

    stage: str  # Stage name (NEEDS_REVIEW, VALIDATED, RELEASED, COMPLETE)


class EntityUpdate(BaseModel):
    """Request body for PATCH /api/entity/{id}."""

    workflow: WorkflowUpdate
    reason: str | None = None

# Default database path
DEFAULT_DB_PATH = Path.cwd() / ".cub" / "dashboard.db"


def get_db_path() -> Path:
    """
    Get the dashboard database path.

    Looks for database in the current working directory's .cub folder.
    In production, this could be configurable via environment variable.

    Returns:
        Path to dashboard database
    """
    # TODO: Make this configurable via environment variable
    return DEFAULT_DB_PATH


# Map from dashboard Stage to ledger WorkflowStage
STAGE_TO_WORKFLOW: dict[str, WorkflowStage] = {
    "NEEDS_REVIEW": WorkflowStage.NEEDS_REVIEW,
    "VALIDATED": WorkflowStage.VALIDATED,
    "RELEASED": WorkflowStage.RELEASED,
}


# NOTE: This route must be defined BEFORE /entity/{entity_id} to avoid
# FastAPI matching "workflow" as the entity_id parameter
@router.put("/entity/{entity_id}/workflow")
async def update_workflow_stage(
    entity_id: str, update: WorkflowStageUpdate
) -> dict[str, bool]:
    """
    Update the workflow stage for an entity.

    This endpoint is used by the drag-and-drop UI to update an entity's
    workflow stage when it's moved between the post-completion columns
    (Dev Complete, Needs Review, Validated, Released).

    The workflow stage is stored in the ledger and persists across
    dashboard syncs.

    Args:
        entity_id: Entity ID to update
        update: WorkflowStageUpdate with new stage

    Returns:
        {"success": True} if updated, {"success": False} if entity not found

    Raises:
        HTTPException: 400 if invalid stage, 500 if update fails

    Note:
        Moving to COMPLETE (Dev Complete) clears the workflow stage,
        returning the entity to its default completed state.
    """
    # Validate stage
    stage_name = update.stage.upper()

    # COMPLETE means clear the workflow stage (return to default completed state)
    if stage_name == "COMPLETE":
        workflow_stage = None
    elif stage_name in STAGE_TO_WORKFLOW:
        workflow_stage = STAGE_TO_WORKFLOW[stage_name]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workflow stage: {update.stage}. "
            f"Valid stages: COMPLETE, NEEDS_REVIEW, VALIDATED, RELEASED",
        )

    # Update database stage directly for immediate UI feedback
    # This works for all entities, even those without ledger entries (e.g., epics)
    db_path = get_db_path()
    if not db_path.exists():
        return {"success": False}

    try:
        db_stage = WORKFLOW_TO_DB_STAGE.get(stage_name, "completed")
        with get_connection(db_path) as conn:
            # Check if entity exists
            cursor = conn.execute(
                "SELECT id FROM entities WHERE id = ?",
                (entity_id,),
            )
            if cursor.fetchone() is None:
                return {"success": False}

            # Update the stage
            conn.execute(
                "UPDATE entities SET stage = ? WHERE id = ?",
                (db_stage, entity_id),
            )
            conn.commit()

        # Also try to update ledger if entry exists (for persistence across syncs)
        ledger_dir = Path.cwd() / ".cub" / "ledger"
        if ledger_dir.exists():
            try:
                writer = LedgerWriter(ledger_dir)
                if workflow_stage is None:
                    # Clear workflow stage
                    entry = writer.get_entry(entity_id)
                    if entry is not None:
                        entry.workflow_stage = None
                        entry.workflow_stage_updated_at = None
                        writer.update_entry(entry)
                else:
                    # Set workflow stage (will fail silently if no ledger entry)
                    writer.update_workflow_stage(entity_id, workflow_stage)
            except Exception:
                # Ledger update is optional - database update is what matters for UI
                pass

        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workflow stage: {str(e)}",
        ) from e


@router.patch("/entity/{entity_id}")
async def patch_entity(entity_id: str, update: EntityUpdate) -> EntityDetail:
    """
    Update entity via PATCH endpoint.

    Currently supports updating the workflow stage. This endpoint writes
    back to ledger files to ensure persistence across syncs.

    Args:
        entity_id: Entity ID to update
        update: EntityUpdate with workflow changes and optional reason

    Returns:
        Updated EntityDetail

    Raises:
        HTTPException: 400 if invalid stage, 404 if not found, 500 if update fails

    Example request:
        PATCH /api/entity/cub-x3s.3
        {"workflow": {"stage": "validated"}, "reason": "Tests passed"}
    """
    # Validate stage
    stage_name = update.workflow.stage.upper()

    # Map stage name to WorkflowStage or None for COMPLETE
    if stage_name == "COMPLETE":
        workflow_stage = None
    elif stage_name in STAGE_TO_WORKFLOW:
        workflow_stage = STAGE_TO_WORKFLOW[stage_name]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workflow stage: {update.workflow.stage}. "
            f"Valid stages: COMPLETE, NEEDS_REVIEW, VALIDATED, RELEASED",
        )

    # Get database path
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Entity not found: {entity_id}",
        )

    try:
        # Update database stage for immediate UI feedback
        db_stage = WORKFLOW_TO_DB_STAGE.get(stage_name, "completed")
        with get_connection(db_path) as conn:
            # Check if entity exists
            cursor = conn.execute(
                "SELECT id FROM entities WHERE id = ?",
                (entity_id,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Entity not found: {entity_id}",
                )

            # Update the stage
            conn.execute(
                "UPDATE entities SET stage = ? WHERE id = ?",
                (db_stage, entity_id),
            )
            conn.commit()

        # Update ledger file for persistence across syncs
        ledger_dir = Path.cwd() / ".cub" / "ledger"
        if ledger_dir.exists():
            writer = LedgerWriter(ledger_dir)

            if workflow_stage is None:
                # Clear workflow stage (return to COMPLETE)
                entry = writer.get_entry(entity_id)
                if entry is not None:
                    entry.workflow_stage = None
                    entry.workflow_stage_updated_at = None
                    writer.update_entry(entry)
            else:
                # Update workflow stage with reason
                # Note: update_workflow_stage expects string values like "validated"
                success = writer.update_workflow_stage(
                    entity_id,
                    workflow_stage.value,
                    reason=update.reason,
                    by="dashboard:api",
                )
                if not success:
                    # Entity exists in DB but not in ledger - this is OK for epics
                    # The DB update is sufficient for UI purposes
                    pass

        # Trigger incremental sync by fetching updated entity
        with get_connection(db_path) as conn:
            detail = get_entity_detail(conn, entity_id)
            if not detail:
                raise HTTPException(
                    status_code=404,
                    detail=f"Entity not found after update: {entity_id}",
                )
            return detail

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update entity: {str(e)}",
        ) from e


@router.get("/entity/{entity_id}", response_model=EntityDetail)
async def get_entity(entity_id: str) -> EntityDetail:
    """
    Get detailed entity data with relationships.

    Returns full entity information including:
    - Complete entity metadata
    - Related entities (parent, children, spec, plan, epic, ledger)
    - Full content (markdown, description, etc.)

    This endpoint powers the detail panel view in the UI, showing
    everything about an entity when clicked.

    Args:
        entity_id: Entity ID to fetch

    Returns:
        EntityDetail with entity, relationships, and content

    Raises:
        HTTPException: 404 if entity not found, 500 if database error

    Example response:
        {
          "entity": {
            "id": "cub-k8d.2",
            "type": "task",
            "title": "Create Pydantic models",
            "stage": "IN_PROGRESS",
            "status": "in_progress",
            "priority": 0,
            "labels": ["complexity:medium", "foundation"],
            "epic_id": "cub-k8d",
            "cost_usd": 1.5,
            "tokens": 5000,
            ...
          },
          "relationships": {
            "parent": { "id": "cub-k8d", "type": "epic", ... },
            "children": [],
            "blocks": [{ "id": "cub-k8d.3", ... }],
            "blocked_by": [],
            "spec": { "id": "project-kanban-dashboard", ... },
            "plan": { "id": "plan-123", ... },
            "ledger": { "id": "ledger-456", ... }
          },
          "content": "## Description\\n\\nCreate comprehensive Pydantic models..."
        }
    """
    db_path = get_db_path()

    if not db_path.exists():
        # Database doesn't exist yet - no entities available
        raise HTTPException(
            status_code=404,
            detail=f"Entity not found: {entity_id}",
        )

    try:
        with get_connection(db_path) as conn:
            detail = get_entity_detail(conn, entity_id)

            if not detail:
                raise HTTPException(
                    status_code=404,
                    detail=f"Entity not found: {entity_id}",
                )

            return detail
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch entity details: {str(e)}",
        ) from e
