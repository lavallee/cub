"""
Built-in default view configurations.

This module provides the default view configurations that are always available,
even if no custom views are defined in `.cub/views/`.

The system provides three built-in views:
- default: Full 8-column workflow (Captures → Released)
- sprint: Active work focused view (Ready → In Progress → Review → Complete)
- ideas: Idea development focused view (Captures → Specs → Planned)

These views serve as both:
1. Fallback configurations when custom views are not available
2. Examples for users creating their own custom views

Creating Custom Views
---------------------

To create a custom view:

1. Run `cub dashboard init` to copy example YAML files to `.cub/views/`
2. Edit the YAML files in `.cub/views/` to customize columns, filters, and display
3. Views are automatically loaded - just refresh the dashboard

View configuration format:

- **id**: Unique identifier for the view (used in URLs and API)
- **name**: Display name shown in the view switcher UI
- **description**: Brief description of the view's purpose
- **columns**: List of column configurations, each with:
  - id: Column identifier
  - title: Display title
  - stages: List of stages to include (CAPTURES, SPECS, PLANNED, READY,
            IN_PROGRESS, NEEDS_REVIEW, COMPLETE, RELEASED)
- **filters**: Entity filtering rules
  - exclude_labels: Labels to exclude from the view
  - include_labels: If set, only include entities with these labels
  - exclude_types: Entity types to exclude
  - include_types: If set, only include these entity types
  - min_priority / max_priority: Priority range (0=P0 highest, 4=P4 lowest)
- **display**: Display settings for entity cards
  - show_cost: Show cost in USD
  - show_tokens: Show token usage
  - show_duration: Show duration
- **is_default**: Whether this view is the default (only one should be true)

See example files in `src/cub/dashboard/examples/` for templates.
"""

from cub.core.dashboard.db.models import (
    ColumnConfig,
    DisplayConfig,
    FilterConfig,
    Stage,
    ViewConfig,
    ViewSummary,
)


def get_default_view() -> ViewConfig:
    """
    Get the default full 8-column workflow view.

    Returns:
        ViewConfig for the default view with all 8 stages

    Example:
        >>> view = get_default_view()
        >>> assert view.id == "default"
        >>> assert len(view.columns) == 8
        >>> assert view.is_default
    """
    return ViewConfig(
        id="default",
        name="Full Workflow",
        description="Complete workflow from captures to released (8 columns)",
        columns=[
            ColumnConfig(
                id="captures",
                title="Captures",
                stages=[Stage.CAPTURES],
            ),
            ColumnConfig(
                id="specs",
                title="Specs",
                stages=[Stage.SPECS],
            ),
            ColumnConfig(
                id="planned",
                title="Planned",
                stages=[Stage.PLANNED],
            ),
            ColumnConfig(
                id="ready",
                title="Ready",
                stages=[Stage.READY],
            ),
            ColumnConfig(
                id="in_progress",
                title="In Progress",
                stages=[Stage.IN_PROGRESS],
            ),
            ColumnConfig(
                id="needs_review",
                title="Needs Review",
                stages=[Stage.NEEDS_REVIEW],
            ),
            ColumnConfig(
                id="complete",
                title="Complete",
                stages=[Stage.COMPLETE],
            ),
            ColumnConfig(
                id="released",
                title="Released",
                stages=[Stage.RELEASED],
            ),
        ],
        filters=FilterConfig(
            exclude_labels=["archived"],
        ),
        display=DisplayConfig(
            show_cost=True,
            show_tokens=False,
            show_duration=False,
        ),
        is_default=True,
    )


def get_sprint_view() -> ViewConfig:
    """
    Get the sprint view focused on active work.

    Shows only the columns relevant to current sprint work:
    - Ready: Tasks ready to work on
    - In Progress: Tasks being actively worked
    - Needs Review: Tasks in review
    - Complete: Tasks done this sprint

    Returns:
        ViewConfig for the sprint view

    Example:
        >>> view = get_sprint_view()
        >>> assert view.id == "sprint"
        >>> assert len(view.columns) == 4
        >>> assert not view.is_default
    """
    return ViewConfig(
        id="sprint",
        name="Sprint View",
        description="Active work focused view (Ready → In Progress → Review → Complete)",
        columns=[
            ColumnConfig(
                id="ready",
                title="Ready",
                stages=[Stage.READY],
            ),
            ColumnConfig(
                id="in_progress",
                title="In Progress",
                stages=[Stage.IN_PROGRESS],
            ),
            ColumnConfig(
                id="needs_review",
                title="Needs Review",
                stages=[Stage.NEEDS_REVIEW],
            ),
            ColumnConfig(
                id="complete",
                title="Complete",
                stages=[Stage.COMPLETE],
            ),
        ],
        filters=FilterConfig(
            exclude_labels=["archived"],
        ),
        display=DisplayConfig(
            show_cost=True,
            show_tokens=False,
            show_duration=True,
        ),
        is_default=False,
    )


def get_ideas_view() -> ViewConfig:
    """
    Get the ideas view focused on idea development.

    Shows only the columns relevant to developing and planning ideas:
    - Captures: Raw ideas and notes
    - Specs: Specifications being researched
    - Planned: Plans exist but not yet staged

    Returns:
        ViewConfig for the ideas view

    Example:
        >>> view = get_ideas_view()
        >>> assert view.id == "ideas"
        >>> assert len(view.columns) == 3
        >>> assert not view.is_default
    """
    return ViewConfig(
        id="ideas",
        name="Ideas View",
        description="Idea development focused view (Captures → Specs → Planned)",
        columns=[
            ColumnConfig(
                id="captures",
                title="Captures",
                stages=[Stage.CAPTURES],
            ),
            ColumnConfig(
                id="specs",
                title="Specs",
                stages=[Stage.SPECS],
            ),
            ColumnConfig(
                id="planned",
                title="Planned",
                stages=[Stage.PLANNED],
            ),
        ],
        filters=FilterConfig(
            exclude_labels=["archived"],
        ),
        display=DisplayConfig(
            show_cost=False,
            show_tokens=False,
            show_duration=False,
        ),
        is_default=False,
    )


def get_built_in_views() -> dict[str, ViewConfig]:
    """
    Get all built-in view configurations.

    Returns:
        Dictionary mapping view IDs to ViewConfig objects

    Example:
        >>> views = get_built_in_views()
        >>> assert "default" in views
        >>> assert "sprint" in views
        >>> assert "ideas" in views
        >>> assert len(views) == 3
    """
    return {
        "default": get_default_view(),
        "sprint": get_sprint_view(),
        "ideas": get_ideas_view(),
    }


def get_built_in_view_summaries() -> list[ViewSummary]:
    """
    Get summaries of all built-in views.

    Returns lightweight ViewSummary objects for listing available views
    without loading full configurations.

    Returns:
        List of ViewSummary objects

    Example:
        >>> summaries = get_built_in_view_summaries()
        >>> assert len(summaries) == 3
        >>> assert any(s.is_default for s in summaries)
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
