"""
View configuration loader.

This module handles loading view configurations from YAML files in `.cub/views/`
directory, with fallback to built-in defaults.

View files are expected to be YAML with the following structure:

```yaml
id: my-view
name: My Custom View
description: A view focused on my workflow
is_default: false

columns:
  - id: ready
    title: Ready
    stages:
      - READY
  - id: in_progress
    title: In Progress
    stages:
      - IN_PROGRESS
    group_by: epic_id  # Optional grouping

filters:
  exclude_labels:
    - archived
    - wontfix
  include_types:  # Optional - only include these types
    - task
    - epic

display:
  show_cost: true
  show_tokens: false
  show_duration: true
  card_size: compact
  group_collapsed: false
```

The loader:
1. Looks for YAML files in `.cub/views/`
2. Validates them against the ViewConfig Pydantic model
3. Falls back to built-in defaults if directory doesn't exist
4. Merges custom views with built-in views
5. Caches results for performance
"""

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from cub.core.dashboard.db.models import ViewConfig, ViewSummary
from cub.core.dashboard.views.defaults import get_built_in_views

logger = logging.getLogger(__name__)

# Cache for loaded views to avoid repeated file I/O
_views_cache: dict[str, ViewConfig] | None = None
_views_dir_mtime: float | None = None


def get_views_directory() -> Path:
    """
    Get the views configuration directory.

    Returns:
        Path to .cub/views/ directory (may not exist)

    Example:
        >>> views_dir = get_views_directory()
        >>> assert str(views_dir).endswith(".cub/views")
    """
    return Path.cwd() / ".cub" / "views"


def load_view_from_yaml(yaml_path: Path) -> ViewConfig | None:
    """
    Load a single view configuration from a YAML file.

    Args:
        yaml_path: Path to YAML file

    Returns:
        ViewConfig instance or None if loading/validation fails

    Example:
        >>> from pathlib import Path
        >>> # If file exists
        >>> view = load_view_from_yaml(Path(".cub/views/my-view.yaml"))
        >>> if view:
        ...     assert isinstance(view, ViewConfig)
    """
    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            logger.warning(
                f"Invalid YAML structure in {yaml_path}: expected dict, got {type(data)}"
            )
            return None

        # Validate and create ViewConfig using Pydantic
        view = ViewConfig(**data)
        logger.debug(f"Loaded view '{view.id}' from {yaml_path}")
        return view

    except FileNotFoundError:
        logger.warning(f"View file not found: {yaml_path}")
        return None
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse YAML in {yaml_path}: {e}")
        return None
    except ValidationError as e:
        logger.warning(f"Invalid view configuration in {yaml_path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error loading view from {yaml_path}: {e}")
        return None


def load_custom_views() -> dict[str, ViewConfig]:
    """
    Load all custom view configurations from `.cub/views/` directory.

    Scans for `.yaml` and `.yml` files and attempts to load each one.
    Invalid files are logged and skipped.

    Returns:
        Dictionary mapping view IDs to ViewConfig objects

    Example:
        >>> views = load_custom_views()
        >>> assert isinstance(views, dict)
        >>> # May be empty if no custom views exist
        >>> for view_id, view in views.items():
        ...     assert view.id == view_id
    """
    views_dir = get_views_directory()

    if not views_dir.exists():
        logger.debug(f"Views directory does not exist: {views_dir}")
        return {}

    if not views_dir.is_dir():
        logger.warning(f"Views path exists but is not a directory: {views_dir}")
        return {}

    custom_views: dict[str, ViewConfig] = {}

    # Scan for YAML files
    for pattern in ["*.yaml", "*.yml"]:
        for yaml_path in views_dir.glob(pattern):
            view = load_view_from_yaml(yaml_path)
            if view:
                if view.id in custom_views:
                    logger.warning(
                        f"Duplicate view ID '{view.id}' in {yaml_path}, "
                        f"overriding previous definition"
                    )
                custom_views[view.id] = view

    logger.info(f"Loaded {len(custom_views)} custom view(s) from {views_dir}")
    return custom_views


def get_views_dir_mtime() -> float | None:
    """
    Get the modification time of the views directory.

    Used for cache invalidation - if the directory is modified,
    we need to reload views.

    Returns:
        Modification timestamp or None if directory doesn't exist

    Example:
        >>> mtime = get_views_dir_mtime()
        >>> assert mtime is None or isinstance(mtime, float)
    """
    views_dir = get_views_directory()
    if not views_dir.exists():
        return None
    try:
        return views_dir.stat().st_mtime
    except OSError:
        return None


def invalidate_cache() -> None:
    """
    Invalidate the views cache.

    Forces the next call to load_all_views() to reload from disk.
    Useful for testing or when views are modified at runtime.

    Example:
        >>> invalidate_cache()
        >>> # Next load_all_views() call will reload from disk
    """
    global _views_cache, _views_dir_mtime
    _views_cache = None
    _views_dir_mtime = None


def load_all_views(use_cache: bool = True) -> dict[str, ViewConfig]:
    """
    Load all view configurations (built-in + custom).

    Combines built-in default views with any custom views found in
    `.cub/views/`. Custom views can override built-in views by using
    the same ID.

    Args:
        use_cache: Whether to use cached views (default: True)

    Returns:
        Dictionary mapping view IDs to ViewConfig objects

    Example:
        >>> views = load_all_views()
        >>> assert "default" in views
        >>> assert "sprint" in views
        >>> assert "ideas" in views
        >>> assert len(views) >= 3
    """
    global _views_cache, _views_dir_mtime

    # Check if we can use cached views
    if use_cache and _views_cache is not None:
        current_mtime = get_views_dir_mtime()
        # Cache is valid if directory hasn't changed
        if current_mtime == _views_dir_mtime:
            logger.debug("Using cached views")
            return _views_cache.copy()

    # Load built-in views first
    all_views = get_built_in_views()
    logger.debug(f"Loaded {len(all_views)} built-in view(s)")

    # Load custom views (may override built-in views)
    try:
        custom_views = load_custom_views()
        if custom_views:
            logger.info(f"Merging {len(custom_views)} custom view(s)")
            all_views.update(custom_views)
    except Exception as e:
        logger.warning(f"Failed to load custom views, using only built-in views: {e}")

    # Update cache
    _views_cache = all_views.copy()
    _views_dir_mtime = get_views_dir_mtime()

    return all_views


def get_view_config(view_id: str, use_cache: bool = True) -> ViewConfig | None:
    """
    Get a specific view configuration by ID.

    Args:
        view_id: View identifier (e.g., "default", "sprint", "ideas")
        use_cache: Whether to use cached views (default: True)

    Returns:
        ViewConfig instance or None if view not found

    Example:
        >>> view = get_view_config("default")
        >>> assert view is not None
        >>> assert view.id == "default"
        >>> assert view.is_default
        >>>
        >>> missing = get_view_config("nonexistent")
        >>> assert missing is None
    """
    views = load_all_views(use_cache=use_cache)
    return views.get(view_id)


def list_views(use_cache: bool = True) -> list[ViewSummary]:
    """
    List all available views as lightweight summaries.

    Returns ViewSummary objects suitable for populating a dropdown
    or view switcher in the UI. Sorted by name for consistent ordering.

    Args:
        use_cache: Whether to use cached views (default: True)

    Returns:
        List of ViewSummary objects sorted by name

    Example:
        >>> summaries = list_views()
        >>> assert len(summaries) >= 3
        >>> assert any(s.is_default for s in summaries)
        >>> # Should be sorted by name
        >>> names = [s.name for s in summaries]
        >>> assert names == sorted(names)
    """
    views = load_all_views(use_cache=use_cache)

    summaries = [
        ViewSummary(
            id=view.id,
            name=view.name,
            description=view.description,
            is_default=view.is_default,
        )
        for view in views.values()
    ]

    # Sort by name for consistent ordering
    summaries.sort(key=lambda s: s.name)

    return summaries
