"""
Stats API routes for the dashboard.

Provides aggregate metrics for the stats bar:
- GET /api/stats - Overall statistics (counts by type/stage, cost, recent activity)
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from cub.core.dashboard.db.connection import get_connection
from cub.core.dashboard.db.models import BoardStats
from cub.core.dashboard.db.queries import compute_board_stats, get_all_entities

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


@router.get("/stats", response_model=BoardStats)
async def get_stats() -> BoardStats:
    """
    Get aggregate statistics for the dashboard.

    Provides summary metrics for display in the stats bar, including:
    - Total entity count
    - Counts by stage (e.g., IN_PROGRESS: 5, READY: 8)
    - Counts by type (e.g., task: 25, spec: 12)
    - Total cost across all entities
    - Total token usage

    This is a lightweight endpoint optimized for polling without
    loading full entity details.

    Returns:
        BoardStats with aggregate metrics

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
          "tokens_total": 523000,
          "duration_total_seconds": 3600
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
            detail=f"Failed to compute stats: {str(e)}",
        ) from e
