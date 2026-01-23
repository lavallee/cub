"""
Entity API routes for the dashboard.

Provides endpoints for fetching individual entity details:
- GET /api/entity/{id} - Full entity with relationships and content
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from cub.core.dashboard.db.connection import get_connection
from cub.core.dashboard.db.models import EntityDetail
from cub.core.dashboard.db.queries import get_entity_detail

router = APIRouter()

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
