# Architecture Design: Project Kanban Dashboard

**Date:** 2026-01-23
**Mindset:** Production
**Scale:** Product
**Status:** Approved

---

## Technical Summary

The Project Kanban Dashboard is a web-based visualization tool for cub projects, providing unified visibility across captures, specs, plans, epics, and tasks. The architecture follows cub's existing patterns: Typer CLI, Pydantic models, and modular core logic.

The system consists of five layers: (1) a sync layer that parses all data sources and writes to SQLite, (2) a database layer with schema and query functions, (3) a FastAPI server exposing REST endpoints, (4) a Typer CLI for user interaction, and (5) a Preact frontend for the web UI.

Key architectural decisions include using SQLite as an aggregation layer (rather than querying sources at runtime), explicit relationship markers in artifacts (rather than heuristic detection), and a "dumb frontend" that simply renders what the API provides (enabling future UI changes without backend modifications).

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Codebase precedent, existing patterns |
| CLI | Typer | Codebase precedent |
| Data Models | Pydantic v2 | Codebase precedent, validation |
| API Server | FastAPI | Async, auto OpenAPI docs, Pydantic integration |
| Database | SQLite | Local, single-file, sufficient for project-scale data |
| Frontend | Preact + TypeScript | React-compatible (familiar), tiny bundle (3KB), fast |
| Build Tool | Vite | Fast dev server, optimized production builds |
| Styling | Tailwind CSS | Utility-first, consistent with modern practice |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES (read-only)                          │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│ specs/      │ .cub/       │ .beads/     │ .cub/       │ CHANGELOG.md        │
│ *.md        │ sessions/   │ issues.jsonl│ ledger/     │                     │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │             │                 │
       ▼             ▼             ▼             ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYNC LAYER (cub.core.dashboard.sync)                │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│ SpecParser  │ PlanParser  │ TaskParser  │LedgerParser │ ChangelogParser     │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │             │                 │
       └─────────────┴─────────────┴─────────────┴─────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    RelationshipResolver      │
                    │  (links via explicit markers)│
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       SQLite Writer          │
                    │   .cub/dashboard.db          │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE (cub.core.dashboard.db)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  entities          │  relationships     │  views            │  sync_state   │
│  (id, type, stage, │  (source, target,  │  (id, name,       │  (source,     │
│   title, ...)      │   rel_type)        │   config_json)    │   checksum)   │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API LAYER (cub.core.dashboard.api)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  FastAPI Application                                                        │
│  ├── GET /api/board?view={id}      → Board with columns and entities        │
│  ├── GET /api/entity/{id}          → Entity detail + relationships          │
│  ├── GET /api/artifact?path={path} → Raw file content                       │
│  ├── GET /api/views                → Available view configurations          │
│  ├── GET /api/stats                → Project statistics                     │
│  └── Static files at /             → Preact frontend                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLI LAYER (cub.cli.dashboard)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  cub dashboard           → sync + start server + open browser               │
│  cub dashboard sync      → sync data only                                   │
│  cub dashboard export    → dump board as JSON                               │
│  cub dashboard views     → list available views                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (src/cub/dashboard/web/)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Preact + TypeScript + Tailwind                                             │
│  ├── KanbanBoard        → 8-column board with horizontal scroll             │
│  ├── EntityCard         → Card displaying entity summary                    │
│  ├── DetailPanel        → Sidebar with full entity details                  │
│  ├── ViewSwitcher       → Dropdown to switch views                          │
│  ├── StatsBar           → Summary statistics                                │
│  └── ArtifactViewer     → Markdown/JSON/YAML renderer                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### Sync Layer (`src/cub/core/dashboard/sync/`)

- **Purpose:** Parse all data sources and write to SQLite
- **Responsibilities:**
  - Parse specs from `specs/**/*.md` using existing `Spec.from_frontmatter_dict`
  - Parse plans from `.cub/sessions/*/plan.jsonl` and `session.json`
  - Query task backend for epics/tasks (beads or JSON)
  - Read ledger entries using existing `LedgerReader`
  - Parse CHANGELOG.md for release → task mappings
  - Resolve relationships via explicit markers (`spec_id`, `plan_id`, `epic_id`)
  - Write entities and relationships to SQLite
- **Dependencies:** `cub.core.specs`, `cub.core.ledger`, `cub.core.tasks`
- **Interface:**
  ```python
  class SyncOrchestrator:
      def sync_all(self, project_root: Path, db_path: Path) -> SyncResult
      def sync_incremental(self, project_root: Path, db_path: Path) -> SyncResult
  ```

**Submodules:**
- `parsers/specs.py` - Spec file parsing
- `parsers/plans.py` - Plan session parsing
- `parsers/tasks.py` - Task backend integration
- `parsers/ledger.py` - Ledger entry parsing
- `parsers/changelog.py` - CHANGELOG.md parsing for releases
- `resolver.py` - Relationship resolution from markers
- `writer.py` - SQLite write operations
- `orchestrator.py` - Coordinate full/incremental sync

### Database Layer (`src/cub/core/dashboard/db/`)

- **Purpose:** SQLite schema and query functions
- **Responsibilities:**
  - Define and migrate schema
  - Provide typed query functions returning Pydantic models
  - Handle connection management
- **Dependencies:** sqlite3 (stdlib), Pydantic
- **Interface:**
  ```python
  class DashboardDB:
      def get_board(self, view_id: str) -> BoardResponse
      def get_entity(self, entity_id: str) -> EntityDetail
      def get_stats(self) -> BoardStats
      def list_views(self) -> list[ViewSummary]
  ```

**Submodules:**
- `schema.py` - Schema definition, migrations
- `queries.py` - Query functions
- `models.py` - Pydantic response models

### API Layer (`src/cub/core/dashboard/api/`)

- **Purpose:** FastAPI application serving REST API + static files
- **Responsibilities:**
  - Expose REST endpoints for board, entities, artifacts, views, stats
  - Serve static frontend files
  - Handle errors with consistent format
- **Dependencies:** FastAPI, uvicorn, database layer
- **Interface:** REST API (see API section below)

**Submodules:**
- `app.py` - FastAPI app factory
- `routes/board.py` - `/api/board` endpoint
- `routes/entity.py` - `/api/entity/{id}` endpoint
- `routes/artifact.py` - `/api/artifact` endpoint
- `routes/views.py` - `/api/views` endpoint
- `routes/stats.py` - `/api/stats` endpoint

### CLI Layer (`src/cub/cli/dashboard.py`)

- **Purpose:** Typer commands for dashboard operations
- **Responsibilities:**
  - `cub dashboard` - sync, start server, open browser
  - `cub dashboard sync` - sync data only
  - `cub dashboard export` - dump board as JSON
  - `cub dashboard views` - list available views
- **Dependencies:** Typer, sync layer, API layer
- **Interface:** CLI commands

### Frontend (`src/cub/dashboard/web/`)

- **Purpose:** Preact-based web UI
- **Responsibilities:**
  - Render kanban board with 8 columns
  - Display entity cards with summary info
  - Show detail panel on entity click
  - Support view switching
  - Display stats bar
  - Render artifact content (markdown, JSON, YAML)
- **Dependencies:** Preact, Vite, Tailwind CSS, TypeScript
- **Build Output:** `src/cub/dashboard/static/`

**Structure:**
```
web/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts
│   ├── components/
│   │   ├── KanbanBoard.tsx
│   │   ├── Column.tsx
│   │   ├── EntityCard.tsx
│   │   ├── DetailPanel.tsx
│   │   ├── ViewSwitcher.tsx
│   │   ├── StatsBar.tsx
│   │   └── ArtifactViewer.tsx
│   ├── hooks/
│   │   ├── useBoard.ts
│   │   └── useEntity.ts
│   └── types/
│       └── api.ts
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

## Data Model

### DashboardEntity
```
id: str                  - Unique identifier (e.g., "spec-auth", "cub-123")
type: EntityType         - capture | spec | plan | epic | task
title: str               - Display title
description: str | None  - Full description/content
stage: Stage             - CAPTURES | SPECS | PLANNED | READY | IN_PROGRESS | NEEDS_REVIEW | COMPLETE | RELEASED
status: str | None       - Raw status from source
priority: int | None     - 0-4 priority level
labels: list[str]        - Tags/labels
created_at: datetime | None
updated_at: datetime | None
completed_at: datetime | None

# Hierarchy references
parent_id: str | None    - Immediate parent
spec_id: str | None      - Originating spec
plan_id: str | None      - Originating plan
epic_id: str | None      - Parent epic (for tasks)

# Metrics (from ledger)
cost_usd: float | None
tokens: int | None
duration_seconds: int | None
verification_status: str | None

# Source tracking
source_type: str         - file | beads | json
source_path: str         - File path or identifier
source_checksum: str     - For incremental sync
content: str | None      - Raw content for detail view
frontmatter: dict | None - Parsed frontmatter
```

### Relationship
```
source_id: str           - Source entity ID
target_id: str           - Target entity ID
rel_type: str            - contains | blocks | references | parent-child
metadata: dict | None    - Additional context
```

### ViewConfig
```
id: str                  - View identifier
name: str                - Display name
description: str | None
columns: list[ColumnConfig]
filters: FilterConfig | None
display: DisplayConfig | None
```

### Stage Computation

```python
def compute_stage(entity: Entity) -> Stage:
    if entity.type == 'capture':
        return Stage.CAPTURES

    if entity.type == 'spec':
        match entity.source_directory:
            case 'researching': return Stage.SPECS
            case 'planned': return Stage.PLANNED
            case 'staged' | 'implementing': return Stage.IN_PROGRESS
            case 'released' | 'completed': return Stage.COMPLETE

    if entity.type == 'plan':
        return Stage.PLANNED

    if entity.type in ('epic', 'task'):
        # Check for release in CHANGELOG
        if entity.release_version:
            return Stage.RELEASED

        # Check for ledger entry
        if has_ledger_entry(entity.id):
            return Stage.COMPLETE

        # Check for PR/review status
        if 'pr' in entity.labels or entity.status == 'review':
            return Stage.NEEDS_REVIEW

        if entity.status == 'in_progress':
            return Stage.IN_PROGRESS

        if entity.status == 'open':
            if is_blocked(entity):
                return Stage.PLANNED
            return Stage.READY

        if entity.status == 'closed':
            return Stage.COMPLETE

    return Stage.UNKNOWN
```

### Relationships

- **Spec → Plan**: `plan.spec_id` references spec
- **Plan → Epic**: `epic.plan_id` references plan
- **Epic → Task**: `task.epic_id` references epic (parent-child dependency)
- **Task → Ledger**: Matched by task ID
- **Task → Release**: Parsed from CHANGELOG.md entries

## APIs / Interfaces

### REST API

#### GET /api/board
- **Purpose:** Get kanban board data for a view
- **Query Params:** `view` (optional, default: "default")
- **Response:**
  ```json
  {
    "view": { "id": "default", "name": "Full Workflow", ... },
    "columns": [
      {
        "id": "captures",
        "title": "Captures",
        "stage": "CAPTURES",
        "entities": [
          { "id": "cap-001", "type": "capture", "title": "...", "stage": "CAPTURES", ... }
        ],
        "count": 5
      },
      ...
    ],
    "stats": {
      "total": 47,
      "by_stage": { "CAPTURES": 5, "SPECS": 8, ... },
      "cost_total": 12.47
    }
  }
  ```

#### GET /api/entity/{id}
- **Purpose:** Get entity detail with relationships
- **Response:**
  ```json
  {
    "entity": { "id": "cub-123", "type": "task", "title": "...", ... },
    "relationships": {
      "parent": { "id": "epic-1", "type": "epic", "title": "..." },
      "children": [],
      "spec": { "id": "spec-auth", "path": "specs/planned/auth.md" },
      "plan": { "id": "session-123", "path": ".cub/sessions/..." },
      "ledger": { "cost_usd": 0.12, "completed_at": "..." }
    },
    "content": "## Description\n..."
  }
  ```

#### GET /api/artifact
- **Purpose:** Get raw artifact content
- **Query Params:** `path` (required, relative to project root)
- **Response:**
  ```json
  {
    "path": "specs/planned/auth.md",
    "type": "markdown",
    "content": "---\nstatus: planned\n---\n# Auth Spec\n...",
    "frontmatter": { "status": "planned", ... }
  }
  ```

#### GET /api/views
- **Purpose:** List available view configurations
- **Response:**
  ```json
  [
    { "id": "default", "name": "Full Workflow", "is_default": true },
    { "id": "sprint", "name": "Current Sprint", "is_default": false },
    { "id": "ideas", "name": "Ideas Pipeline", "is_default": false }
  ]
  ```

#### GET /api/stats
- **Purpose:** Get project statistics
- **Response:**
  ```json
  {
    "total_entities": 47,
    "by_type": { "capture": 5, "spec": 12, "plan": 4, "epic": 8, "task": 18 },
    "by_stage": { "CAPTURES": 5, "SPECS": 8, ... },
    "cost_total": 12.47,
    "tokens_total": 523000,
    "recent_activity": [
      { "id": "cub-123", "action": "completed", "timestamp": "..." }
    ]
  }
  ```

### Error Response Format
```json
{
  "error": "Entity not found",
  "code": "ENTITY_NOT_FOUND",
  "details": { "id": "cub-999" }
}
```

## View Configuration

Views stored in `.cub/views/` as YAML files:

```yaml
# .cub/views/default.yaml
id: default
name: Full Workflow
description: Complete workflow from captures to released
columns:
  - id: captures
    title: Captures
    stages: [CAPTURES]
  - id: specs
    title: Specs
    stages: [SPECS]
  - id: planned
    title: Planned
    stages: [PLANNED]
    group_by: spec_id
  - id: ready
    title: Ready
    stages: [READY]
    group_by: epic_id
  - id: in_progress
    title: In Progress
    stages: [IN_PROGRESS]
    group_by: epic_id
  - id: review
    title: Needs Review
    stages: [NEEDS_REVIEW]
    group_by: epic_id
  - id: complete
    title: Complete
    stages: [COMPLETE]
  - id: released
    title: Released
    stages: [RELEASED]
filters:
  exclude_labels: [archived]
display:
  show_cost: true
  card_size: compact
```

**Default Views Shipped:**
1. `default.yaml` - Full 8-column workflow
2. `sprint.yaml` - Ready → In Progress → Review → Complete
3. `ideas.yaml` - Captures → Specs → Planned

## Implementation Phases

### Phase 1: Data Foundation
**Goal:** Establish data layer and sync infrastructure

- Define SQLite schema in `db/schema.py`
- Implement database models in `db/models.py`
- Create spec parser using existing `Spec.from_frontmatter_dict`
- Create plan parser for `.cub/sessions/*/plan.jsonl`
- Create task parser using existing task backend
- Create ledger parser using existing `LedgerReader`
- Create changelog parser for CHANGELOG.md
- Implement relationship resolver
- Implement SQLite writer
- Implement sync orchestrator
- Create basic CLI: `cub dashboard sync`
- Add tests for parsers and sync logic

### Phase 2: API Server
**Goal:** Expose data via REST API

- Create FastAPI app factory
- Implement `/api/board` endpoint
- Implement `/api/entity/{id}` endpoint
- Implement `/api/artifact` endpoint
- Implement `/api/views` endpoint
- Implement `/api/stats` endpoint
- Add error handling middleware
- Add OpenAPI documentation
- Update CLI: `cub dashboard` starts server
- Add API integration tests

### Phase 3: Basic Frontend
**Goal:** Render functional kanban board

- Set up Vite + Preact + TypeScript project
- Configure Tailwind CSS
- Create API client
- Implement KanbanBoard component
- Implement Column component
- Implement EntityCard component
- Configure static file serving in FastAPI
- Build and bundle frontend
- Test end-to-end flow

### Phase 4: Interactive Features
**Goal:** Add detail views and navigation

- Implement DetailPanel sidebar
- Implement relationship navigation (click to view related)
- Implement ViewSwitcher dropdown
- Implement StatsBar
- Implement ArtifactViewer with markdown rendering
- Add loading and error states
- Add keyboard navigation (arrow keys, escape)

### Phase 5: Polish
**Goal:** Production-ready quality

- Load view configurations from `.cub/views/`
- Ship default views (default, sprint, ideas)
- Implement `cub dashboard export` command
- Implement `cub dashboard views` command
- Add comprehensive error handling
- Performance optimization (lazy loading, virtualization if needed)
- Documentation and CLAUDE.md updates
- Final test coverage review

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Sync performance with large projects | M | L | Incremental sync via checksums; SQLite indexes; profile early |
| Frontend build complexity | M | M | Vite is simple; keep dependencies minimal; document setup |
| Stage computation edge cases | M | M | Comprehensive unit tests; handle UNKNOWN gracefully |
| Relationship marker adoption | M | M | Update cub skills to include markers; document convention clearly |
| SQLite concurrency issues | L | L | WAL mode; sync is fast; add file locking if needed |
| Path traversal in /api/artifact | M | L | Validate paths are within project root; reject absolute paths |

## Dependencies

### External (New)

**Python (runtime):**
- `fastapi>=0.109.0` - API framework
- `uvicorn>=0.27.0` - ASGI server

**Node (build-time only):**
- `preact@^10.19.0` - UI framework
- `vite@^5.0.0` - Build tool
- `tailwindcss@^3.4.0` - Styling
- `typescript@^5.3.0` - Type safety
- `@preact/preset-vite@^2.8.0` - Vite integration
- `marked@^11.0.0` - Markdown rendering
- `highlight.js@^11.9.0` - Syntax highlighting

### Internal (Existing)

- `cub.core.specs` - Spec model and parsing
- `cub.core.ledger` - Ledger reading
- `cub.core.tasks` - Task backend abstraction
- `cub.core.captures` - Capture model (if captures are included)

## Security Considerations

- **Path traversal**: `/api/artifact` endpoint must validate that requested paths:
  - Are relative (not absolute)
  - Resolve to within project root
  - Don't contain `..` traversal
- **No authentication**: Local-only tool, single user assumed
- **No sensitive data**: Dashboard only reads existing project files
- **CORS**: Not needed for local-only; if added later, restrict origins

## Future Considerations

**Deferred to v2:**
- **Editing**: API mutations, optimistic updates, conflict resolution
- **Real-time**: WebSocket for live updates during `cub run`
- **Multi-project**: Aggregate view across projects
- **Mobile**: Responsive design, touch interactions
- **Collaboration**: Multiple users, presence indicators

**Keep in mind:**
- API design should anticipate POST/PATCH endpoints for editing
- Database schema should support tracking who made changes
- Frontend state management may need upgrade for editing (consider Zustand)

---

**Next Step:** Run `/cub:itemize` to break this into executable tasks.
