"""
Views API routes for the dashboard.

Provides endpoints for managing view configurations:
- GET /api/views - List available views with metadata
- GET /api/views/{view_id} - Get detailed view configuration (future)
- POST /api/views - Create new view (future)

Views define how the Kanban board is displayed, including:
- Which columns to show
- How to group entities
- What filters to apply
- Display settings (card size, metrics shown, etc.)

Default views are provided but users can create custom views
for different workflows and perspectives.
"""

from fastapi import APIRouter, HTTPException

from cub.core.dashboard.db.models import ViewSummary
from cub.core.dashboard.views import list_views

router = APIRouter()


@router.get("/views", response_model=list[ViewSummary])
async def get_views() -> list[ViewSummary]:
    """
    Get list of available view configurations.

    Returns all available views (both default and custom) that can be
    used to configure the Kanban board display. This endpoint powers
    the view switcher dropdown in the frontend.

    Each view includes:
    - id: Unique identifier for the view
    - name: Display name shown in UI
    - description: What this view is optimized for
    - is_default: Whether this is the default view

    Returns:
        List of ViewSummary objects sorted by name

    Raises:
        HTTPException: 500 if view loading fails

    Example response:
        [
            {
                "id": "default",
                "name": "Full Workflow",
                "description": "Complete workflow from captures to released",
                "is_default": true
            },
            {
                "id": "sprint",
                "name": "Sprint View",
                "description": "Active work focused view",
                "is_default": false
            },
            {
                "id": "ideas",
                "name": "Ideas View",
                "description": "Idea development focused view",
                "is_default": false
            }
        ]

    Usage:
        ```typescript
        // Frontend can use this to populate a view switcher dropdown
        const response = await fetch('/api/views');
        const views = await response.json();
        setAvailableViews(views);
        ```
    """
    try:
        # Load all views (built-in + custom from .cub/views/)
        views = list_views()
        return views
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch available views: {str(e)}",
        ) from e
