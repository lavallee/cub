"""
Board API routes for the dashboard.

Provides endpoints for fetching Kanban board data:
- GET /api/board - Full board with all columns and entities
- GET /api/board/stats - Just statistics (faster for polling)
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from cub.core.dashboard.db.connection import get_connection
from cub.core.dashboard.db.models import BoardResponse, BoardStats
from cub.core.dashboard.db.queries import compute_board_stats, get_all_entities, get_board_data

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


@router.get("/board", response_model=BoardResponse)
async def get_board() -> BoardResponse:
    """
    Get full board data for Kanban visualization.

    Returns all entities grouped by stage/column with statistics.
    This is the primary endpoint the frontend polls to render the board.

    Returns:
        BoardResponse with view config, columns, and stats

    Raises:
        HTTPException: 500 if database error occurs

    Example response:
        {
          "view": {
            "id": "default",
            "name": "Full Workflow",
            "columns": [...]
          },
          "columns": [
            {
              "id": "in_progress",
              "title": "In Progress",
              "stage": "IN_PROGRESS",
              "entities": [...],
              "count": 5
            },
            ...
          ],
          "stats": {
            "total": 47,
            "by_stage": {"IN_PROGRESS": 5, "READY": 8},
            "cost_total": 12.47
          }
        }
    """
    db_path = get_db_path()

    if not db_path.exists():
        # Return empty board if database doesn't exist yet
        # This allows the frontend to render before first sync
        from cub.core.dashboard.views import get_view_config
        from cub.core.dashboard.db.models import BoardColumn

        # Load default view from view loader (supports custom views)
        view = get_view_config("default")
        if not view:
            # Fallback to built-in default if loading fails
            from cub.core.dashboard.db.queries import get_default_view_config
            view = get_default_view_config()

        empty_columns = [
            BoardColumn(
                id=col.id,
                title=col.title,
                stage=col.stages[0],
                entities=[],
                count=0,
            )
            for col in view.columns
        ]

        return BoardResponse(
            view=view,
            columns=empty_columns,
            stats=BoardStats(),
        )

    try:
        with get_connection(db_path) as conn:
            board = get_board_data(conn)
            return board
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch board data: {str(e)}",
        ) from e


@router.get("/board/stats", response_model=BoardStats)
async def get_board_stats() -> BoardStats:
    """
    Get board statistics without full entity data.

    Lighter-weight endpoint for polling statistics without
    loading all entity details. Useful for a stats bar or
    summary view.

    Returns:
        BoardStats with counts and totals

    Raises:
        HTTPException: 500 if database error occurs

    Example response:
        {
          "total": 47,
          "by_stage": {
            "IN_PROGRESS": 5,
            "READY": 8,
            "COMPLETE": 20
          },
          "by_type": {
            "task": 25,
            "spec": 12,
            "epic": 10
          },
          "cost_total": 12.47,
          "tokens_total": 523000
        }
    """
    db_path = get_db_path()

    if not db_path.exists():
        # Return empty stats if database doesn't exist yet
        return BoardStats()

    try:
        with get_connection(db_path) as conn:
            entities = get_all_entities(conn)
            stats = compute_board_stats(entities)
            return stats
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute board stats: {str(e)}",
        ) from e
