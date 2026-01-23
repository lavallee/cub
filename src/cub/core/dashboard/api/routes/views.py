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

router = APIRouter()


def get_default_views() -> list[ViewSummary]:
    """
    Get the list of default views.

    The system provides three built-in views:
    - default: Full 8-column workflow
    - sprint: Active work (ready, in progress, review, complete)
    - ideas: Idea development (captures, specs, planned)

    Returns:
        List of ViewSummary objects for default views

    Example:
        >>> views = get_default_views()
        >>> assert len(views) >= 1
        >>> assert any(v.is_default for v in views)
    """
    return [
        ViewSummary(
            id="default",
            name="Full Workflow",
            description="Complete workflow from captures to released (8 columns)",
            is_default=True,
        ),
        ViewSummary(
            id="sprint",
            name="Sprint View",
            description="Active work focused view (Ready → In Progress → Review → Complete)",
            is_default=False,
        ),
        ViewSummary(
            id="ideas",
            name="Ideas View",
            description="Idea development focused view (Captures → Specs → Planned)",
            is_default=False,
        ),
    ]


def load_custom_views() -> list[ViewSummary]:
    """
    Load custom view configurations from .cub/views/.

    Users can create custom YAML/JSON view files in .cub/views/
    to define their own view configurations for different workflows.

    Returns:
        List of custom ViewSummary objects (empty if directory doesn't exist)

    Note:
        This is a placeholder for future implementation.
        Currently returns empty list.

    Example:
        >>> custom = load_custom_views()
        >>> assert isinstance(custom, list)
    """
    # TODO: Implement loading custom views from .cub/views/
    # For now, return empty list
    return []


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
        # Get default views
        views = get_default_views()

        # Try to load custom views
        try:
            custom_views = load_custom_views()
            views.extend(custom_views)
        except Exception:
            # If custom view loading fails, just use defaults
            pass

        # Sort by name for consistent ordering
        views.sort(key=lambda v: v.name)

        return views
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch available views: {str(e)}",
        ) from e
