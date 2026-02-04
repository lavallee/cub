---
status: researching
priority: medium
complexity: high
dependencies:
- knowledge-retention-system.md (parallel - ledger integration)
blocks: []
created: 2026-01-23
updated: 2026-01-23
readiness:
  score: 6
  blockers:
  - JS framework choice not finalized
  - View configuration schema not defined
  questions:
  - How to detect plan-epic relationships if not explicit?
  - SQLite schema design - normalize or denormalize?
  - How to handle multi-project views (future)?
  decisions_needed:
  - Choose JS framework (React, SolidJS, or Svelte)
  - Define SQLite schema for aggregated data
  - Define view configuration format
  tools_needed: []
notes: |-
  Web-based kanban dashboard for unified project visibility.
  Read-only for v1, with editing planned for future.
  Inspired by vibe-kanban but tailored for cub workflow.
spec_id: cub-035
---
# Project Kanban Dashboard

## Overview

A web-based kanban dashboard (`cub dashboard`) providing unified visibility across captures, specs, plans, epics, and tasks as they flow through the development lifecycle. The dashboard serves both as a project management view and as an implicit explanation of how cub works.

Read-only for v1, with all data access mediated through cub's API layer. The architecture anticipates future editing capabilities and additional metadata capture.

## Goals

- **Unified visibility**: See all work artifacts in one place, across the full lifecycle
- **Traceability**: Click any entity to see related artifacts (spec -> plan -> epic -> tasks -> ledger)
- **Workflow explanation**: Dashboard implicitly teaches cub workflow to stakeholders
- **Backend-agnostic**: Works with beads or JSON task backend via cub abstraction
- **View flexibility**: Support different views for different projects/contexts
- **Future-ready**: Architecture supports editing and richer metadata capture

## Non-Goals (v1)

- Editing/mutations (continue using CLI)
- Direct beads access from UI
- Real-time websocket updates
- Multi-project aggregation
- PR/merge/release automation wiring
- Mobile-optimized views

---

## Workflow Stages

The dashboard visualizes work flowing through these stages:

```
┌─────────┬─────────┬─────────┬─────────┬───────────┬────────────┬──────────┬──────────┐
│CAPTURES │  SPECS  │ PLANNED │  READY  │IN PROGRESS│NEEDS REVIEW│ COMPLETE │ RELEASED │
│         │(research)│         │         │           │   (PR)     │ (merged) │(shipped) │
├─────────┼─────────┼─────────┼─────────┼───────────┼────────────┼──────────┼──────────┤
│• idea-1 │• spec-a │ spec-c  │ epic-2  │ epic-1    │ epic-3     │ epic-4   │ epic-5   │
│• idea-2 │• spec-b │ ├plan-1 │ ├task-4 │ ├task-1   │ └task-7    │ ├task-8  │ └task-10 │
│         │         │ │└epic-1│ └task-5 │ └task-2   │            │ └task-9  │          │
│         │         │ └plan-2 │ task-x  │ task-y    │            │          │          │
│         │         │  └epic-2│         │           │            │          │          │
└─────────┴─────────┴─────────┴─────────┴───────────┴────────────┴──────────┴──────────┘
```

### Stage Definitions

| Stage | Description | Data Source |
|-------|-------------|-------------|
| **CAPTURES** | Raw ideas, inspirations, observations | `specs/captures/*.md` |
| **SPECS** | Researching status, not yet planned | `specs/researching/*.md` |
| **PLANNED** | Spec + plan(s) defined, not staged to tasks | `specs/planned/*.md` + `.cub/sessions/*/plan.jsonl` |
| **READY** | Epics/tasks exist in backend, unblocked | beads/JSON with status=open, no blockers |
| **IN PROGRESS** | Actively being worked | beads/JSON with status=in_progress |
| **NEEDS REVIEW** | PR open, awaiting review | beads/JSON with label=pr or status=review |
| **COMPLETE** | PR merged, work done | beads/JSON with status=closed + ledger entry |
| **RELEASED** | Shipped in a release | ledger with release tag (future) |

### Hierarchy

- **Specs** can have multiple plans (alternatives/variants)
- **Plans** contain epics
- **Epics** contain tasks (shown inline)
- **Independent tasks** (no epic) show standalone in their stage column

---

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     SOURCE DATA                                  │
├─────────────────────────────────────────────────────────────────┤
│ specs/captures/     specs/*.md        .cub/sessions/            │
│ specs/researching/  specs/planned/    .beads/issues.jsonl       │
│ specs/completed/    .cub/ledger/      (or prd.json)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CUB SYNC LAYER                                │
│  `cub dashboard sync` - imports/upserts to SQLite               │
├─────────────────────────────────────────────────────────────────┤
│  • Parse spec frontmatter                                        │
│  • Parse plan.jsonl for epics/tasks                             │
│  • Query task backend (beads or JSON)                           │
│  • Parse ledger entries                                          │
│  • Resolve relationships (spec -> plan -> epic -> task)         │
│  • Write to .cub/dashboard.db                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SQLITE DATABASE                               │
│  .cub/dashboard.db                                               │
├─────────────────────────────────────────────────────────────────┤
│  entities (id, type, title, status, stage, ...)                 │
│  relationships (source_id, target_id, rel_type)                 │
│  views (id, name, config_json)                                  │
│  sync_state (source, last_sync, checksum)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI SERVER                                │
│  `cub dashboard` starts server on localhost:PORT                │
├─────────────────────────────────────────────────────────────────┤
│  GET /api/board          - kanban board data                    │
│  GET /api/entity/{id}    - entity detail + relationships        │
│  GET /api/artifact/{path} - raw artifact content (md/json/yaml) │
│  GET /api/views          - available view configurations        │
│  GET /api/stats          - project statistics                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WEB UI                                        │
│  Static frontend served by FastAPI                               │
├─────────────────────────────────────────────────────────────────┤
│  • Kanban board view (main)                                      │
│  • Entity detail panel (sidebar or modal)                       │
│  • Artifact viewer (markdown/json/yaml rendered)                │
│  • View switcher (different board configurations)               │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Cub mediates all access**: UI never touches beads directly
2. **SQLite as aggregation layer**: Clean API, fast queries, no runtime parsing
3. **Sync on demand**: `cub dashboard sync` updates DB, auto-sync on dashboard start
4. **Backend-agnostic**: Same API whether using beads or JSON backend
5. **View configuration**: JSON-based view definitions for flexibility
6. **Smart backend, dumb frontend**: Business logic in Python, UI just renders

---

## Data Model

### SQLite Schema (Draft)

```sql
-- Core entity table (denormalized for query simplicity)
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- capture, spec, plan, epic, task
    title TEXT NOT NULL,
    description TEXT,
    status TEXT,         -- researching, planned, open, in_progress, closed, etc.
    stage TEXT,          -- computed: CAPTURES, SPECS, PLANNED, READY, etc.
    priority INTEGER,
    labels TEXT,         -- JSON array
    created_at TEXT,
    updated_at TEXT,
    completed_at TEXT,

    -- Source tracking
    source_type TEXT,    -- file, beads, json
    source_path TEXT,    -- file path or backend identifier
    source_checksum TEXT,

    -- Denormalized parent references for fast queries
    parent_id TEXT,      -- immediate parent (task -> epic, epic -> plan, etc.)
    spec_id TEXT,        -- originating spec (if traceable)
    plan_id TEXT,        -- originating plan
    epic_id TEXT,        -- parent epic (for tasks)

    -- Metrics (from ledger when available)
    cost_usd REAL,
    tokens INTEGER,
    duration_seconds INTEGER,
    verification_status TEXT,

    -- Raw content for detail view
    content TEXT,        -- markdown/json content
    frontmatter TEXT     -- JSON of parsed frontmatter
);

-- Relationships table for flexible linking
CREATE TABLE relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,  -- contains, blocks, references, parent-child
    metadata TEXT,           -- JSON for additional context
    FOREIGN KEY (source_id) REFERENCES entities(id),
    FOREIGN KEY (target_id) REFERENCES entities(id),
    UNIQUE(source_id, target_id, rel_type)
);

-- View configurations
CREATE TABLE views (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    config TEXT NOT NULL,    -- JSON view configuration
    is_default BOOLEAN DEFAULT FALSE,
    created_at TEXT,
    updated_at TEXT
);

-- Sync state tracking
CREATE TABLE sync_state (
    source TEXT PRIMARY KEY,  -- 'specs', 'plans', 'beads', 'ledger'
    last_sync TEXT,
    item_count INTEGER,
    checksum TEXT
);

-- Indexes for common queries
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_stage ON entities(stage);
CREATE INDEX idx_entities_status ON entities(status);
CREATE INDEX idx_entities_parent ON entities(parent_id);
CREATE INDEX idx_entities_epic ON entities(epic_id);
CREATE INDEX idx_relationships_source ON relationships(source_id);
CREATE INDEX idx_relationships_target ON relationships(target_id);
```

### Entity Types

| Type | Source | Stage Mapping |
|------|--------|---------------|
| `capture` | `specs/captures/*.md` | CAPTURES |
| `spec` | `specs/{researching,planned,completed}/*.md` | SPECS, PLANNED, COMPLETE |
| `plan` | `.cub/sessions/*/plan.jsonl` (session records) | PLANNED (with spec) |
| `epic` | beads/JSON with type=epic | READY → RELEASED |
| `task` | beads/JSON with type=task | READY → RELEASED |

### Stage Computation Logic

```python
def compute_stage(entity: Entity) -> str:
    if entity.type == 'capture':
        return 'CAPTURES'

    if entity.type == 'spec':
        if entity.status == 'researching':
            return 'SPECS'
        elif entity.status == 'planned':
            return 'PLANNED'
        elif entity.status == 'completed':
            return 'COMPLETE'

    if entity.type == 'plan':
        return 'PLANNED'  # Plans always shown in PLANNED column

    if entity.type in ('epic', 'task'):
        # Check for ledger entry (COMPLETE or RELEASED)
        if has_ledger_entry(entity.id):
            ledger = get_ledger_entry(entity.id)
            if ledger.release_tag:
                return 'RELEASED'
            return 'COMPLETE'

        # Check for PR/review status
        if 'pr' in entity.labels or entity.status == 'review':
            return 'NEEDS_REVIEW'

        # Active work
        if entity.status == 'in_progress':
            return 'IN_PROGRESS'

        # Ready vs still in plan (not yet staged)
        if entity.status == 'open':
            if is_blocked(entity):
                return 'PLANNED'  # Blocked tasks stay in planned
            return 'READY'

        if entity.status == 'closed':
            return 'COMPLETE'

    return 'UNKNOWN'
```

---

## View Configuration

Views are JSON configurations defining what columns to show and how to filter/group entities.

### Default View Schema

```json
{
  "id": "default",
  "name": "Full Workflow",
  "description": "Complete workflow from captures to released",
  "columns": [
    {
      "id": "captures",
      "title": "Captures",
      "stages": ["CAPTURES"],
      "collapsed": false
    },
    {
      "id": "specs",
      "title": "Specs",
      "stages": ["SPECS"],
      "group_by": null
    },
    {
      "id": "planned",
      "title": "Planned",
      "stages": ["PLANNED"],
      "group_by": "spec_id",
      "show_hierarchy": true
    },
    {
      "id": "ready",
      "title": "Ready",
      "stages": ["READY"],
      "group_by": "epic_id"
    },
    {
      "id": "in_progress",
      "title": "In Progress",
      "stages": ["IN_PROGRESS"],
      "group_by": "epic_id"
    },
    {
      "id": "review",
      "title": "Needs Review",
      "stages": ["NEEDS_REVIEW"],
      "group_by": "epic_id"
    },
    {
      "id": "complete",
      "title": "Complete",
      "stages": ["COMPLETE"],
      "collapsed": false
    },
    {
      "id": "released",
      "title": "Released",
      "stages": ["RELEASED"],
      "collapsed": true
    }
  ],
  "filters": {
    "exclude_labels": ["archived"],
    "date_range": null
  },
  "display": {
    "show_cost": true,
    "show_tokens": false,
    "show_dates": true,
    "card_size": "compact"
  }
}
```

### Alternative Views

```json
// Sprint view - just active work
{
  "id": "sprint",
  "name": "Current Sprint",
  "columns": [
    {"id": "ready", "title": "To Do", "stages": ["READY"]},
    {"id": "in_progress", "title": "Doing", "stages": ["IN_PROGRESS"]},
    {"id": "review", "title": "Review", "stages": ["NEEDS_REVIEW"]},
    {"id": "done", "title": "Done", "stages": ["COMPLETE"]}
  ],
  "filters": {
    "labels": ["sprint:current"]
  }
}

// Ideas pipeline - early stages only
{
  "id": "ideas",
  "name": "Ideas Pipeline",
  "columns": [
    {"id": "captures", "title": "Raw Ideas", "stages": ["CAPTURES"]},
    {"id": "specs", "title": "Researching", "stages": ["SPECS"]},
    {"id": "planned", "title": "Ready to Build", "stages": ["PLANNED"]}
  ]
}
```

---

## API Design

### FastAPI Endpoints

```python
# Board data - main kanban view
GET /api/board?view={view_id}
Response: {
    "view": { ... view config ... },
    "columns": [
        {
            "id": "captures",
            "title": "Captures",
            "entities": [
                {"id": "cap-001", "title": "...", "type": "capture", ...},
                ...
            ]
        },
        ...
    ],
    "stats": {
        "total": 47,
        "by_stage": {"CAPTURES": 5, "SPECS": 8, ...}
    }
}

# Entity detail with relationships
GET /api/entity/{id}
Response: {
    "entity": { ... full entity data ... },
    "relationships": {
        "parent": {"id": "epic-1", "title": "...", "type": "epic"},
        "children": [...],
        "spec": {"id": "spec-auth", "title": "...", "path": "specs/planned/auth.md"},
        "plan": {...},
        "ledger": {...}
    },
    "content": "... markdown content ..."
}

# Raw artifact content
GET /api/artifact?path={relative_path}
Response: {
    "path": "specs/planned/auth.md",
    "type": "markdown",
    "content": "...",
    "frontmatter": { ... parsed YAML ... }
}

# Available views
GET /api/views
Response: [
    {"id": "default", "name": "Full Workflow", "is_default": true},
    {"id": "sprint", "name": "Current Sprint", "is_default": false},
    ...
]

# Project stats
GET /api/stats
Response: {
    "total_entities": 47,
    "by_type": {"capture": 5, "spec": 12, "plan": 4, "epic": 8, "task": 18},
    "by_stage": {...},
    "cost_total": 12.47,
    "recent_activity": [...]
}
```

---

## CLI Integration

### Commands

```bash
# Start dashboard server
cub dashboard
# Opens browser to http://localhost:8420

# Start without opening browser
cub dashboard --no-open

# Specify port
cub dashboard --port 8080

# Sync data without starting server
cub dashboard sync

# Export board state as JSON
cub dashboard export --view default > board.json

# List available views
cub dashboard views
```

### Implementation

```python
# src/cub/cli/dashboard.py

@app.command()
def dashboard(
    port: int = typer.Option(8420, help="Server port"),
    no_open: bool = typer.Option(False, help="Don't open browser"),
    sync_only: bool = typer.Option(False, "--sync", help="Only sync data, don't start server"),
) -> None:
    """Launch the project kanban dashboard."""

    # Always sync on start
    from cub.dashboard.sync import sync_all
    sync_all()

    if sync_only:
        return

    # Start FastAPI server
    from cub.dashboard.server import create_app
    import uvicorn

    app = create_app()

    if not no_open:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")

    uvicorn.run(app, host="127.0.0.1", port=port)
```

---

## UI Design

### Layout (Inspired by vibe-kanban)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [logo] Project Kanban Dashboard          [View: Full Workflow ▼] [Sync] [?] │
├──────────────────────────────────────────────────────────────────────────────┤
│ Stats: 5 captures | 8 specs | 12 in progress | $12.47 spent                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│ │CAPTURES │ │  SPECS  │ │ PLANNED │ │  READY  │ │IN PROG  │ │COMPLETE │    │
│ │    (5)  │ │    (8)  │ │   (12)  │ │    (6)  │ │    (4)  │ │   (15)  │    │
│ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤    │
│ │┌───────┐│ │┌───────┐│ │┌───────┐│ │┌───────┐│ │┌───────┐│ │┌───────┐│    │
│ ││ idea  ││ ││ spec  ││ ││ spec  ││ ││▼epic-1││ ││▼epic-3││ ││ task  ││    │
│ │└───────┘│ │└───────┘│ ││├plan-1││ ││ task  ││ ││ task  ││ │└───────┘│    │
│ │┌───────┐│ │┌───────┐│ ││└epic-1││ ││ task  ││ │└───────┘│ │┌───────┐│    │
│ ││ idea  ││ ││ spec  ││ │└───────┘│ │└───────┘│ │┌───────┐│ ││ task  ││    │
│ │└───────┘│ │└───────┘│ │┌───────┐│ │┌───────┐│ ││ task  ││ │└───────┘│    │
│ │         │ │         │ ││ spec  ││ ││ task  ││ │└───────┘│ │         │    │
│ │         │ │         │ ││├plan-2││ │└───────┘│ │         │ │         │    │
│ │         │ │         │ ││└epic-2││ │         │ │         │ │         │    │
│ │         │ │         │ │└───────┘│ │         │ │         │ │         │    │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Entity Cards

```
┌─────────────────────────┐
│ [icon] task-123         │  <- Type icon + ID
│ Implement user auth     │  <- Title
│ ─────────────────────── │
│ P0 | $0.12 | 45min      │  <- Priority, cost, duration (if available)
│ [ready] [auth] [v0.25]  │  <- Labels/tags
└─────────────────────────┘
```

### Detail Panel (Sidebar)

When clicking an entity, a sidebar slides in showing:

```
┌────────────────────────────────────┐
│ [X] task-123: Implement user auth  │
├────────────────────────────────────┤
│ Stage: IN_PROGRESS                 │
│ Status: in_progress                │
│ Priority: P0                       │
│ Created: 2026-01-15                │
│                                    │
│ ─── Relationships ───              │
│ Epic: epic-auth (▶)               │
│ Spec: specs/planned/auth.md (▶)   │
│ Plan: session-20260115 (▶)        │
│ Ledger: (not yet complete)        │
│                                    │
│ ─── Content ───                    │
│ ## Description                     │
│ Implement JWT-based authentication │
│ with refresh tokens...             │
│                                    │
│ ## Acceptance Criteria             │
│ - [ ] Login endpoint works         │
│ - [ ] Refresh token rotation       │
│ ...                                │
└────────────────────────────────────┘
```

### Artifact Viewer

For viewing raw markdown/json/yaml:

- Markdown: Rendered with syntax highlighting for code blocks
- JSON: Pretty-printed with collapsible sections
- YAML: Syntax highlighted

---

## Implementation Plan

### Phase 1: Foundation (Core Infrastructure)

1. **SQLite schema and sync layer**
   - Create `src/cub/dashboard/db.py` with schema
   - Create `src/cub/dashboard/sync.py` with import logic
   - Parse specs, plans, beads, ledger
   - Compute stages and relationships

2. **FastAPI server skeleton**
   - Create `src/cub/dashboard/server.py`
   - Implement `/api/board`, `/api/entity/{id}`, `/api/views`
   - Static file serving for frontend

3. **CLI command**
   - Create `src/cub/cli/dashboard.py`
   - `cub dashboard`, `cub dashboard sync`

### Phase 2: Basic UI

4. **Kanban board view**
   - Column layout with drag-scroll
   - Entity cards with basic info
   - Click to expand detail panel

5. **Detail panel**
   - Entity metadata
   - Relationship links
   - Content viewer

### Phase 3: Polish

6. **View configurations**
   - Default views (Full, Sprint, Ideas)
   - View switcher in UI
   - Persist view preferences

7. **Artifact viewer**
   - Markdown rendering
   - JSON/YAML syntax highlighting

8. **Stats and filtering**
   - Stats bar
   - Label/date filtering

---

## Technology Choices

### Backend
- **FastAPI**: Async, fast, good OpenAPI support, already familiar
- **SQLite**: Simple, no server needed, good enough for single-project data
- **Uvicorn**: ASGI server for FastAPI

### Frontend (Decision Needed)

| Option | Pros | Cons |
|--------|------|------|
| **React** | Most familiar, huge ecosystem, easy to hire | Bundle size, complexity for simple UI |
| **SolidJS** | Fast, React-like, small bundle | Smaller ecosystem |
| **Svelte** | Simple, compiled, great DX | Different paradigm |
| **Vanilla + htmx** | Minimal, server-driven | More backend work, less interactive |

**Recommendation**: Start with **React** (or Preact for smaller bundle) given familiarity and ecosystem. Can migrate later if needed.

### Styling
- Tailwind CSS for utility-first styling
- Minimal custom components, leverage existing patterns

---

## Future Considerations

### v2: Editing

- Inline status changes (drag cards between columns)
- Create captures/specs from UI
- Edit entity metadata
- Requires API mutations and optimistic updates

### v3: Real-time

- WebSocket for live updates during `cub run`
- Show agent activity in real-time
- Collaborative viewing (multiple users)

### v4: Multi-project

- Aggregate view across multiple cub projects
- Cross-project dependency tracking
- Portfolio-level dashboards

---

## Open Questions

1. **Plan-epic relationship detection**: If not explicit in frontmatter, how do we link?
   - By session ID in both?
   - By title matching?
   - Require explicit linking?

2. **SQLite vs. in-memory**: Should we skip SQLite and just compute on-demand?
   - SQLite: Faster queries, persistence, incremental sync
   - In-memory: Simpler, always fresh, no sync issues

3. **View persistence**: Store in SQLite, in config file, or both?

4. **RELEASED detection**: How to know something shipped?
   - Git tags?
   - Explicit marking?
   - GitHub release integration?

---

## References

- [Vibe Kanban](https://github.com/bloopai/vibe-kanban) - Inspiration for layout and multi-agent orchestration
- [Knowledge Retention System](./knowledge-retention-system.md) - Ledger system design
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [Rich](https://rich.readthedocs.io/) - Terminal UI (for TUI slice, future)

---

**Status**: researching
**Last Updated**: 2026-01-23
