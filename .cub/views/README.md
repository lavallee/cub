# Dashboard Views Configuration

This directory contains custom view configurations for the Cub dashboard Kanban board.

## Overview

Views allow you to customize how the dashboard displays your project state. Each view can:
- Define which columns to show and what stages they represent
- Group entities by epic, label, or status
- Filter out unwanted entities (labels, types)
- Configure display settings (card size, metrics shown, etc.)

## Creating a Custom View

Create a new YAML file in this directory (e.g., `my-view.yaml`):

```yaml
id: my-view
name: My Custom View
description: A view focused on my workflow
is_default: false

columns:
  - id: ready
    title: Ready to Start
    stages: [READY]
  - id: in_progress
    title: In Progress
    stages: [IN_PROGRESS]
    group_by: epic_id  # Optional: group cards by epic
  - id: review
    title: Code Review
    stages: [NEEDS_REVIEW]
  - id: done
    title: Completed
    stages: [COMPLETE, RELEASED]

filters:
  exclude_labels:
    - archived
    - wontfix
    - spike
  include_types:  # Optional: only show these types
    - task
    - epic

display:
  show_cost: true          # Show task cost/budget
  show_tokens: false       # Hide token count
  show_duration: true      # Show time spent
  card_size: compact       # Card size: compact, normal, large
  group_collapsed: false   # Start with groups collapsed
```

## View Configuration Schema

### Top-level Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the view |
| `name` | string | Human-readable name |
| `description` | string | Optional description |
| `is_default` | boolean | Whether this is the default view |
| `columns` | array | Array of column configurations |
| `filters` | object | Optional filtering rules |
| `display` | object | Optional display settings |

### Column Configuration

Each column in the `columns` array:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the column |
| `title` | string | Column header text |
| `stages` | array | List of stages to show in this column |
| `group_by` | string | Optional: group by 'epic_id', 'type', or 'status' |

### Stages

Valid stage values (from the 8-column workflow):
- `CAPTURES` — Raw ideas and notes
- `SPECS` — Specifications being researched
- `PLANNED` — Specs in planning or existing plans
- `READY` — Tasks ready to work (no blockers)
- `IN_PROGRESS` — Active development
- `NEEDS_REVIEW` — Awaiting review or approval
- `COMPLETE` — Done but not released
- `RELEASED` — Shipped to production

### Filters (Optional)

```yaml
filters:
  exclude_labels:
    - archived      # Hide all archived items
    - wontfix
    - spike
  include_types:    # Only show these types (if specified)
    - task
    - epic
    - spec
```

Valid entity types:
- `capture`
- `spec`
- `plan`
- `epic`
- `task`
- `ledger`
- `release`

### Display Settings (Optional)

```yaml
display:
  show_cost: true      # Show task cost/budget (boolean)
  show_tokens: false   # Show token usage (boolean)
  show_duration: true  # Show time spent (boolean)
  card_size: compact   # Card size: compact, normal, large
  group_collapsed: false  # Start with groups collapsed
```

## Built-in Views

If no custom views are found, the dashboard uses built-in default views:

### Default View
Shows all 8 stages with all entity types, no grouping.

### By Epic View
Groups all entities by their epic, useful for sprint planning.

### Planning View
Shows SPECS → PLANNED → READY stages, focused on preparation.

### Execution View
Shows READY → IN_PROGRESS → NEEDS_REVIEW → COMPLETE stages, focused on execution.

## Examples

### Minimal View (3 columns)

```yaml
id: kanban-simple
name: Simple Kanban
description: Basic To-Do list view

columns:
  - id: todo
    title: To Do
    stages: [READY, PLANNED]
  - id: doing
    title: Doing
    stages: [IN_PROGRESS]
  - id: done
    title: Done
    stages: [COMPLETE, RELEASED]
```

### Team View (grouped by assignee/epic)

```yaml
id: kanban-team
name: Team View
description: Work grouped by epic for team planning

columns:
  - id: backlog
    title: Backlog
    stages: [PLANNED, READY]
  - id: active
    title: Active
    stages: [IN_PROGRESS]
    group_by: epic_id
  - id: review
    title: Review
    stages: [NEEDS_REVIEW]
  - id: shipped
    title: Shipped
    stages: [RELEASED]
```

### Spec Workflow View

```yaml
id: spec-workflow
name: Specification Workflow
description: Track specs from research through implementation

columns:
  - id: research
    title: Researching
    stages: [SPECS]
  - id: planning
    title: Planning
    stages: [PLANNED]
  - id: implementing
    title: Implementing
    stages: [IN_PROGRESS]
  - id: released
    title: Released
    stages: [RELEASED]

filters:
  include_types: [spec]
```

### Filtered View (exclude certain work)

```yaml
id: kanban-production
name: Production-Only View
description: Only show production tasks, exclude spikes and experiments

columns:
  - id: ready
    title: Ready
    stages: [READY]
  - id: active
    title: In Progress
    stages: [IN_PROGRESS]
  - id: done
    title: Done
    stages: [COMPLETE, RELEASED]

filters:
  exclude_labels:
    - spike
    - experiment
    - research
    - wontfix
  include_types:
    - task
    - epic
```

## How Views Are Loaded

The dashboard loads views in this order:

1. **Custom views** from `.cub/views/*.yaml` (if directory exists)
2. **Built-in default views** (if no custom views found or for missing views)
3. **Merging**: Custom and built-in views are merged, custom views override built-ins

This means you can:
- Override a built-in view by creating a YAML file with the same `id`
- Add new custom views alongside built-ins
- Mix custom and built-in views freely

## YAML Validation

View YAML files are validated against the `ViewConfig` Pydantic model. Common validation errors:

- **Missing required fields**: `id`, `name`, `columns`
- **Invalid stage names**: Use exact stage values from the schema
- **Invalid entity types**: Check the valid types list above
- **Invalid card sizes**: Must be `compact`, `normal`, or `large`

If a YAML file fails validation, it's logged as a warning and the built-in default is used instead.

## API Integration

Views are served via the dashboard API:

```bash
# List all available views
curl http://localhost:8000/api/views

# Get specific view configuration
curl http://localhost:8000/api/views/my-view

# Get board data for a specific view
curl http://localhost:8000/api/board?view=my-view
```

The `/api/board` endpoint applies the view's filters and column definitions when returning board data.

## Extending Views

For advanced customization beyond YAML configuration, you can:

1. **Add custom stage computation** — Modify `cub.core.dashboard.db.models.Stage` to add new stages
2. **Add filter types** — Extend the filter logic in `cub.core.dashboard.api.routes.board`
3. **Add display options** — Extend the display schema in `cub.core.dashboard.db.models.ViewConfig`

See `CLAUDE.md` under "Dashboard Feature" for architectural details.

## Troubleshooting

### View not showing up

1. Check the YAML file is in `.cub/views/` directory
2. Verify YAML syntax is valid (use `yaml lint` or an IDE validator)
3. Check dashboard logs: `tail -f .cub/logs/*.json | jq .`
4. Ensure `id` field is unique across all views

### Cards not showing in view

1. Check `filters.include_types` — may be excluding your entity type
2. Check `filters.exclude_labels` — may be filtering out cards
3. Verify stages in `columns` match entity stages
4. Check entity stage computation in `cub.core.dashboard.db.models.Stage`

### View resets on restart

Views are loaded fresh each time the server starts. Ensure YAML file is saved and in the correct location.

## See Also

- [README.md](../../README.md) — Dashboard overview
- [CLAUDE.md](../../CLAUDE.md) — Dashboard architecture details
- [cub.core.dashboard documentation](../../src/cub/core/dashboard) — API and implementation
