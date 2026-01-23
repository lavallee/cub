"""
View configuration loading for the dashboard.

This module provides functionality for loading view configurations from
YAML files in `.cub/views/` directory, with fallback to built-in defaults.

The view system allows users to customize how the Kanban board is displayed:
- Which columns to show
- How to group entities
- What filters to apply
- Display settings (card size, metrics shown, etc.)

Views are defined in YAML format and loaded on demand. If custom views are
not found, the system falls back to built-in default views.

Example usage:
    >>> from cub.core.dashboard.views import get_view_config, list_views
    >>> views = list_views()
    >>> config = get_view_config("default")
"""

from cub.core.dashboard.views.defaults import get_built_in_views
from cub.core.dashboard.views.loader import get_view_config, list_views

__all__ = [
    "get_view_config",
    "list_views",
    "get_built_in_views",
]
