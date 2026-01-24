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
from cub.core.dashboard.db.models import EntityDetail, Stage
from cub.core.dashboard.db.queries import get_entity_detail
from cub.core.ledger.models import WorkflowStage
from cub.core.ledger.writer import LedgerWriter

router = APIRouter()


class WorkflowStageUpdate(BaseModel):
    """Request body for updating workflow stage."""

    stage: str  # Stage name (NEEDS_REVIEW, VALIDATED, RELEASED, COMPLETE)

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


# Map from dashboard Stage to ledger WorkflowStage
STAGE_TO_WORKFLOW: dict[str, WorkflowStage] = {
    "NEEDS_REVIEW": WorkflowStage.NEEDS_REVIEW,
    "VALIDATED": WorkflowStage.VALIDATED,
    "RELEASED": WorkflowStage.RELEASED,
}


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

    ledger_dir = Path.cwd() / ".cub" / "ledger"

    if not ledger_dir.exists():
        return {"success": False}

    try:
        writer = LedgerWriter(ledger_dir)

        if workflow_stage is None:
            # Clear workflow stage by reading entry and removing the field
            entry = writer.get_entry(entity_id)
            if entry is None:
                return {"success": False}
            entry.workflow_stage = None
            entry.workflow_stage_updated_at = None
            writer.update_entry(entry)
            return {"success": True}
        else:
            success = writer.update_workflow_stage(entity_id, workflow_stage)
            return {"success": success}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workflow stage: {str(e)}",
        ) from e
