# Itemized Plan: Project Kanban Dashboard

> Source: [specs/researching/project-kanban-dashboard.md](../../specs/researching/project-kanban-dashboard.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-23

## Context Summary

This plan implements a web-based kanban dashboard (`cub dashboard`) providing unified visibility across captures, specs, plans, epics, and tasks. The dashboard aggregates data from multiple sources (specs/, .cub/sessions/, .beads/, .cub/ledger/, CHANGELOG.md) into SQLite for fast queries, serves via FastAPI, and renders with Preact.

Key architectural decisions:
- SQLite at `.cub/dashboard.db` as aggregation layer
- Explicit relationship markers in artifacts (`spec_id`, `plan_id`, `epic_id`)
- FastAPI backend with REST endpoints
- Preact + Vite + Tailwind frontend
- View configurations via YAML files

The implementation prioritizes **early visibility** - getting something running in the browser before completing all infrastructure. This is achieved through vertical slicing: Epic 1 delivers a minimal but functional board.

---

## Epic: cub-k8d - Kanban 1: Vertical Slice

Priority: 0
Labels: phase-1, vertical-slice, foundation

Get a minimal but functional dashboard visible in the browser. This epic delivers end-to-end: SQLite schema → spec parser → sync → API → frontend → CLI command.

### Task: cub-k8d.1 - Create SQLite schema and database module

Priority: 0
Labels: foundation, database, model:sonnet, complexity:medium
Blocks: cub-k8d.2, cub-k8d.3

**Context**: The SQLite database is the aggregation layer that powers all API queries. We need the schema and basic connection management before any data can be synced.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/__init__.py`
2. Create `src/cub/core/dashboard/db/__init__.py`
3. Create `src/cub/core/dashboard/db/schema.py`:
   - Define `SCHEMA_VERSION = 1`
   - Define `CREATE TABLE entities (...)` with all fields from architecture
   - Define `CREATE TABLE relationships (...)`
   - Define `CREATE TABLE sync_state (...)`
   - Implement `init_db(db_path: Path) -> sqlite3.Connection`
   - Implement `get_schema_version()` and `migrate_if_needed()`
4. Create `src/cub/core/dashboard/db/connection.py`:
   - Implement `DashboardDB` class with connection management
   - Add context manager support for transactions
5. Add tests for schema creation and migrations

**Acceptance Criteria**:
- [ ] `init_db()` creates database with all tables
- [ ] Schema matches architecture specification
- [ ] `DashboardDB` class manages connections
- [ ] WAL mode enabled for better concurrency
- [ ] Tests verify schema creation
- [ ] mypy strict passes

**Files**: `src/cub/core/dashboard/db/schema.py`, `src/cub/core/dashboard/db/connection.py`, `tests/test_dashboard_schema.py`

---

### Task: cub-k8d.2 - Create Pydantic models for dashboard entities

Priority: 0
Labels: foundation, models, model:sonnet, complexity:medium
Blocks: cub-k8d.4, cub-k8d.5

**Context**: Pydantic models provide type-safe data structures for entities, API responses, and view configurations. These are used throughout the sync layer and API.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/db/models.py`
2. Implement enums:
   - `EntityType` (capture, spec, plan, epic, task)
   - `Stage` (CAPTURES, SPECS, PLANNED, READY, IN_PROGRESS, NEEDS_REVIEW, COMPLETE, RELEASED)
3. Implement `DashboardEntity` model with all fields from architecture
4. Implement `Relationship` model
5. Implement `BoardColumn` and `BoardResponse` models for API
6. Implement `ViewConfig`, `ColumnConfig`, `FilterConfig`, `DisplayConfig` models
7. Implement `SyncState` and `SyncResult` models
8. Add model validation tests

**Acceptance Criteria**:
- [ ] All entity types and stages defined as enums
- [ ] `DashboardEntity` model matches architecture spec
- [ ] API response models defined (`BoardResponse`, etc.)
- [ ] View config models support YAML deserialization
- [ ] mypy strict passes
- [ ] Tests verify model validation

**Files**: `src/cub/core/dashboard/db/models.py`, `tests/test_dashboard_models.py`

---

### Task: cub-k8d.3 - Implement spec parser for sync layer

Priority: 0
Labels: sync, parser, model:sonnet, complexity:medium
Blocks: cub-k8d.4

**Context**: The spec parser reads markdown files from `specs/` directories and converts them to `DashboardEntity` objects. This is the first parser - start simple, add others later.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/sync/__init__.py`
2. Create `src/cub/core/dashboard/sync/parsers/__init__.py`
3. Create `src/cub/core/dashboard/sync/parsers/specs.py`
4. Implement `SpecParser` class:
   - `parse_all(specs_dir: Path) -> list[DashboardEntity]`
   - Reuse existing `cub.core.specs.models.Spec.from_frontmatter_dict()`
   - Map spec stage directories to dashboard stages
   - Extract `id` from frontmatter (or derive from filename)
   - Compute checksum for incremental sync
5. Handle edge cases: missing frontmatter, invalid YAML, empty files
6. Add tests with fixture spec files

**Acceptance Criteria**:
- [ ] Parses specs from all stage directories (researching, planned, staged, implementing, released)
- [ ] Converts to `DashboardEntity` with correct stage mapping
- [ ] Extracts `id` field from frontmatter
- [ ] Computes checksums for change detection
- [ ] Gracefully handles malformed files (logs warning, continues)
- [ ] Tests cover happy path and edge cases

**Files**: `src/cub/core/dashboard/sync/parsers/specs.py`, `tests/test_spec_parser.py`

---

### Task: cub-k8d.4 - Implement basic sync orchestrator and SQLite writer

Priority: 0
Labels: sync, database, model:sonnet, complexity:medium
Blocks: cub-k8d.5

**Context**: The sync orchestrator coordinates parsing and writing to SQLite. For the vertical slice, we only sync specs - other sources added later.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/sync/writer.py`:
   - `write_entities(conn, entities: list[DashboardEntity])`
   - `write_relationships(conn, relationships: list[Relationship])`
   - `update_sync_state(conn, source: str, checksum: str)`
   - Use `INSERT OR REPLACE` for upsert semantics
2. Create `src/cub/core/dashboard/sync/orchestrator.py`:
   - `SyncOrchestrator` class
   - `sync_all(project_root: Path, db_path: Path) -> SyncResult`
   - For now, only call `SpecParser`
   - Log sync progress and results
3. Add tests with in-memory SQLite

**Acceptance Criteria**:
- [ ] `SyncOrchestrator.sync_all()` parses specs and writes to SQLite
- [ ] Entities queryable after sync
- [ ] `sync_state` table updated with source checksums
- [ ] Returns `SyncResult` with counts
- [ ] Tests verify data round-trips correctly

**Files**: `src/cub/core/dashboard/sync/writer.py`, `src/cub/core/dashboard/sync/orchestrator.py`, `tests/test_sync_orchestrator.py`

---

### Task: cub-k8d.5 - Implement FastAPI app with /api/board endpoint

Priority: 0
Labels: api, model:sonnet, complexity:medium
Blocks: cub-k8d.6, cub-k8d.7

**Context**: The API server exposes dashboard data to the frontend. Start with just `/api/board` - enough to render the kanban board.

**Implementation Steps**:
1. Add `fastapi` and `uvicorn` to pyproject.toml dependencies
2. Create `src/cub/core/dashboard/api/__init__.py`
3. Create `src/cub/core/dashboard/api/app.py`:
   - `create_app(db_path: Path, static_dir: Path | None) -> FastAPI`
   - Configure CORS for local development
   - Mount static files if `static_dir` provided
4. Create `src/cub/core/dashboard/api/routes/__init__.py`
5. Create `src/cub/core/dashboard/api/routes/board.py`:
   - `GET /api/board` endpoint
   - Query entities grouped by stage
   - Return `BoardResponse` model
   - Support `?view=` parameter (default view for now)
6. Create `src/cub/core/dashboard/db/queries.py`:
   - `get_entities_by_stage(conn) -> dict[Stage, list[DashboardEntity]]`
   - `get_board_stats(conn) -> BoardStats`
7. Add API tests with TestClient

**Acceptance Criteria**:
- [ ] FastAPI app created with `/api/board` endpoint
- [ ] Returns entities grouped into columns by stage
- [ ] Includes basic stats (counts by stage)
- [ ] CORS configured for localhost
- [ ] OpenAPI docs available at `/docs`
- [ ] Tests verify response structure

**Files**: `src/cub/core/dashboard/api/app.py`, `src/cub/core/dashboard/api/routes/board.py`, `src/cub/core/dashboard/db/queries.py`, `tests/test_api_board.py`

---

### Task: cub-k8d.6 - Set up Vite + Preact + Tailwind frontend project

Priority: 0
Labels: frontend, setup, model:sonnet, complexity:medium
Blocks: cub-k8d.7

**Context**: The frontend is a Preact SPA that renders the kanban board. This task sets up the project structure and build tooling.

**Implementation Steps**:
1. Create `src/cub/dashboard/web/` directory
2. Initialize with Vite: `npm create vite@latest . -- --template preact-ts`
3. Install dependencies: `npm install tailwindcss postcss autoprefixer`
4. Configure Tailwind: `npx tailwindcss init -p`
5. Create project structure:
   ```
   web/
   ├── src/
   │   ├── main.tsx
   │   ├── App.tsx
   │   ├── index.css (Tailwind imports)
   │   ├── api/client.ts
   │   ├── components/
   │   └── types/api.ts
   ├── index.html
   ├── vite.config.ts
   ├── tailwind.config.js
   ├── tsconfig.json
   └── package.json
   ```
6. Configure Vite to output to `../static/` on build
7. Create `api/client.ts` with typed fetch wrapper
8. Create `types/api.ts` matching Python response models
9. Verify dev server runs: `npm run dev`
10. Verify production build: `npm run build`

**Acceptance Criteria**:
- [ ] `npm run dev` starts Vite dev server
- [ ] `npm run build` outputs to `src/cub/dashboard/static/`
- [ ] Tailwind CSS working
- [ ] TypeScript configured with strict mode
- [ ] API client typed to match backend models
- [ ] Basic App.tsx renders "Dashboard loading..."

**Files**: `src/cub/dashboard/web/*` (new directory)

---

### Task: cub-k8d.7 - Implement basic KanbanBoard and EntityCard components

Priority: 0
Labels: frontend, ui, model:sonnet, complexity:medium
Blocks: cub-k8d.8

**Context**: The core UI components that render the kanban board. Start minimal - just columns with cards showing entity titles.

**Implementation Steps**:
1. Create `src/cub/dashboard/web/src/components/KanbanBoard.tsx`:
   - Fetch board data from `/api/board` on mount
   - Render columns horizontally with overflow-x-auto
   - Pass entities to Column components
   - Show loading state
2. Create `src/cub/dashboard/web/src/components/Column.tsx`:
   - Render column header with title and count
   - Map entities to EntityCard components
   - Style with Tailwind (gray background, rounded)
3. Create `src/cub/dashboard/web/src/components/EntityCard.tsx`:
   - Display entity type icon, ID, and title
   - Show priority badge if set
   - Show labels as small tags
   - Clickable (onClick handler, no action yet)
4. Create `src/cub/dashboard/web/src/hooks/useBoard.ts`:
   - Custom hook for fetching and caching board data
   - Handle loading and error states
5. Update `App.tsx` to render `KanbanBoard`
6. Style for 8 columns with horizontal scroll

**Acceptance Criteria**:
- [ ] Board fetches data from API and renders columns
- [ ] Each column shows header with stage name and count
- [ ] Entity cards display type, ID, title, priority, labels
- [ ] Horizontal scroll works for 8 columns
- [ ] Loading state shown while fetching
- [ ] Error state shown if API fails

**Files**: `src/cub/dashboard/web/src/components/KanbanBoard.tsx`, `Column.tsx`, `EntityCard.tsx`, `hooks/useBoard.ts`

---

### Task: cub-k8d.8 - Implement cub dashboard CLI command

Priority: 0
Labels: cli, model:sonnet, complexity:medium
Blocks: cub-d2v.1

**Context**: The CLI command ties everything together - syncs data, starts the server, and opens the browser. This completes the vertical slice.

**Implementation Steps**:
1. Create `src/cub/cli/dashboard.py`
2. Create Typer app with main command and subcommands:
   ```python
   @app.command()
   def dashboard(
       port: int = 8420,
       no_open: bool = False,
       no_sync: bool = False,
   ): ...

   @app.command("sync")
   def sync(): ...
   ```
3. Implement main command:
   - Determine project root and db path (`.cub/dashboard.db`)
   - Run sync unless `--no-sync`
   - Build frontend if static dir missing or stale
   - Start uvicorn server
   - Open browser unless `--no-open`
4. Implement sync subcommand:
   - Just runs `SyncOrchestrator.sync_all()`
   - Prints summary
5. Register in `src/cub/cli/__init__.py`
6. Add integration test

**Acceptance Criteria**:
- [ ] `cub dashboard` syncs, starts server, opens browser
- [ ] `cub dashboard --no-open` skips browser
- [ ] `cub dashboard --no-sync` skips sync
- [ ] `cub dashboard sync` runs sync only
- [ ] Server serves API at `/api/*` and static files at `/`
- [ ] Ctrl+C gracefully shuts down

**Files**: `src/cub/cli/dashboard.py`, `src/cub/cli/__init__.py`

---

## Checkpoint 1: Minimal Dashboard Running

After completing Epic cub-k8d, you should be able to:
1. Run `cub dashboard`
2. See specs from your project rendered as cards in columns
3. Columns correspond to spec stages (researching → planned → etc.)

**What's testable**: End-to-end flow from files to browser
**Key validation**: Does the board render? Can you see your specs?

---

## Epic: cub-d2v - Kanban 2: Expand Data Sources

Priority: 1
Labels: phase-2, sync, parsers

Add remaining data source parsers: plans, tasks (via backend), ledger, and CHANGELOG. Implement relationship resolution and stage computation.

### Task: cub-d2v.1 - Implement plan parser

Priority: 0
Labels: sync, parser, model:sonnet, complexity:medium
Blocks: cub-d2v.5

**Context**: Plans are stored in `.cub/sessions/*/` directories with `session.json` metadata and `plan.jsonl` task definitions. Parse these to show planned work.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/sync/parsers/plans.py`
2. Implement `PlanParser` class:
   - `parse_all(sessions_dir: Path) -> list[DashboardEntity]`
   - Read `session.json` for plan metadata
   - Read `plan.jsonl` for epics/tasks within plan
   - Extract `spec_id` from session.json for relationship linking
   - Create `DashboardEntity` with type='plan'
3. Handle missing/incomplete sessions gracefully
4. Add tests with fixture session data

**Acceptance Criteria**:
- [ ] Parses plans from `.cub/sessions/*/`
- [ ] Extracts `spec_id` for relationship linking
- [ ] Creates plan entities with correct metadata
- [ ] Handles incomplete sessions (missing plan.jsonl)
- [ ] Tests cover various session states

**Files**: `src/cub/core/dashboard/sync/parsers/plans.py`, `tests/test_plan_parser.py`

---

### Task: cub-d2v.2 - Implement task parser via backend abstraction

Priority: 0
Labels: sync, parser, backend, model:sonnet, complexity:medium
Blocks: cub-d2v.5

**Context**: Tasks and epics come from the task backend (beads or JSON). Use existing backend abstraction rather than parsing files directly.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/sync/parsers/tasks.py`
2. Implement `TaskParser` class:
   - `parse_all(backend: TaskBackend) -> list[DashboardEntity]`
   - Call `backend.list_tasks()` to get all tasks
   - Convert Task models to DashboardEntity
   - Preserve `epic_id`, `spec_id`, `plan_id` if present in task metadata
   - Map task status to dashboard stage
3. Handle both beads and JSON backends
4. Add tests with mock backend

**Acceptance Criteria**:
- [ ] Parses tasks via TaskBackend abstraction
- [ ] Works with both BeadsBackend and JsonBackend
- [ ] Preserves relationship markers from task metadata
- [ ] Maps task status to dashboard stages correctly
- [ ] Tests use mock backend

**Files**: `src/cub/core/dashboard/sync/parsers/tasks.py`, `tests/test_task_parser.py`

---

### Task: cub-d2v.3 - Implement ledger parser

Priority: 0
Labels: sync, parser, model:haiku, complexity:low
Blocks: cub-d2v.5

**Context**: The ledger contains completion records with cost/token metrics. Parse to enrich entities and identify completed work.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/sync/parsers/ledger.py`
2. Implement `LedgerParser` class:
   - `parse_all(ledger_dir: Path) -> dict[str, LedgerData]`
   - Reuse existing `cub.core.ledger.reader.LedgerReader`
   - Return dict mapping task_id → ledger data
   - Extract: cost_usd, tokens, duration, verification_status, completed_at
3. This returns enrichment data, not entities (tasks come from TaskParser)
4. Add tests

**Acceptance Criteria**:
- [ ] Parses ledger entries using existing LedgerReader
- [ ] Returns dict for enriching task entities
- [ ] Handles missing ledger directory gracefully
- [ ] Tests verify ledger data extraction

**Files**: `src/cub/core/dashboard/sync/parsers/ledger.py`, `tests/test_ledger_parser.py`

---

### Task: cub-d2v.4 - Implement CHANGELOG parser for release detection

Priority: 0
Labels: sync, parser, model:sonnet, complexity:medium
Blocks: cub-d2v.5

**Context**: CHANGELOG.md contains release entries with task/epic IDs. Parse to determine which entities have been released.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/sync/parsers/changelog.py`
2. Implement `ChangelogParser` class:
   - `parse(changelog_path: Path) -> dict[str, str]`
   - Parse Keep-a-Changelog format: `## [version] - date`
   - Extract task/epic IDs from entries: `(cub-xxx, cub-yyy)`
   - Return dict mapping entity_id → release_version
3. Handle various ID formats: `cub-xxx`, `cub-xxx.n`, `#123`
4. Gracefully handle missing CHANGELOG or unparseable content
5. Add tests with sample CHANGELOG content

**Acceptance Criteria**:
- [ ] Parses Keep-a-Changelog format
- [ ] Extracts entity IDs from release entries
- [ ] Returns mapping of entity_id → version
- [ ] Handles missing CHANGELOG gracefully
- [ ] Tests cover various entry formats

**Files**: `src/cub/core/dashboard/sync/parsers/changelog.py`, `tests/test_changelog_parser.py`

---

### Task: cub-d2v.5 - Implement relationship resolver and stage computation

Priority: 0
Labels: sync, logic, model:opus, complexity:high
Blocks: cub-d2v.6

**Context**: The relationship resolver links entities via explicit markers and computes the correct stage for each entity based on multiple signals.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/sync/resolver.py`
2. Implement `RelationshipResolver` class:
   - `resolve(entities: list[DashboardEntity], ledger: dict, releases: dict) -> tuple[list[DashboardEntity], list[Relationship]]`
   - Build relationship graph from `spec_id`, `plan_id`, `epic_id` markers
   - Create Relationship objects for each link
3. Implement `compute_stage()` function following architecture logic:
   - Captures → CAPTURES
   - Specs → stage from directory
   - Plans → PLANNED
   - Tasks/Epics: check release → ledger → status → blocked
4. Enrich entities with ledger data (cost, tokens, etc.)
5. Add comprehensive tests for stage computation edge cases

**Acceptance Criteria**:
- [ ] Resolves relationships from explicit markers
- [ ] Creates Relationship objects for all links
- [ ] Stage computation matches architecture specification
- [ ] Entities enriched with ledger metrics
- [ ] Released entities detected via CHANGELOG
- [ ] Tests cover all stage computation paths

**Files**: `src/cub/core/dashboard/sync/resolver.py`, `tests/test_resolver.py`

---

### Task: cub-d2v.6 - Integrate all parsers into sync orchestrator

Priority: 0
Labels: sync, integration, model:sonnet, complexity:medium

**Context**: Update the sync orchestrator to use all parsers and the relationship resolver, producing a complete picture of project state.

**Implementation Steps**:
1. Update `src/cub/core/dashboard/sync/orchestrator.py`:
   - Add all parser imports
   - Update `sync_all()` to:
     1. Parse specs → entities
     2. Parse plans → entities
     3. Parse tasks (via backend) → entities
     4. Parse ledger → enrichment data
     5. Parse CHANGELOG → release data
     6. Resolve relationships and compute stages
     7. Write all entities and relationships to SQLite
2. Add progress logging for each step
3. Handle partial failures (one parser fails, others continue)
4. Update sync result with detailed counts
5. Add integration test with real project structure

**Acceptance Criteria**:
- [ ] All parsers integrated and called
- [ ] Relationships written to database
- [ ] Stages computed correctly
- [ ] Partial failures don't abort entire sync
- [ ] Sync result includes per-source counts
- [ ] Integration test verifies full sync

**Files**: `src/cub/core/dashboard/sync/orchestrator.py`, `tests/test_sync_integration.py`

---

## Epic: cub-a7f - Kanban 3: API Completeness

Priority: 2
Labels: phase-3, api

Implement remaining API endpoints: entity detail, artifact viewer, views list, and project stats.

### Task: cub-a7f.1 - Implement /api/entity/{id} endpoint

Priority: 0
Labels: api, model:sonnet, complexity:medium
Blocks: cub-m3x.1

**Context**: The entity detail endpoint returns full entity data with relationships, enabling the detail panel in the UI.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/api/routes/entity.py`
2. Implement `GET /api/entity/{id}`:
   - Query entity by ID from database
   - Query relationships (parent, children, spec, plan, ledger)
   - Include full content field
   - Return 404 if not found
3. Add to `src/cub/core/dashboard/db/queries.py`:
   - `get_entity_by_id(conn, id) -> DashboardEntity | None`
   - `get_entity_relationships(conn, id) -> EntityRelationships`
4. Register route in app
5. Add tests

**Acceptance Criteria**:
- [ ] Returns full entity with all fields
- [ ] Includes relationships (parent, children, spec, plan)
- [ ] Includes ledger data if available
- [ ] Returns 404 for unknown ID
- [ ] Tests verify response structure

**Files**: `src/cub/core/dashboard/api/routes/entity.py`, `src/cub/core/dashboard/db/queries.py`, `tests/test_api_entity.py`

---

### Task: cub-a7f.2 - Implement /api/artifact endpoint with path validation

Priority: 0
Labels: api, security, model:opus, complexity:high
Blocks: cub-m3x.5

**Context**: The artifact endpoint serves raw file content for viewing specs, plans, etc. Must validate paths to prevent directory traversal attacks.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/api/routes/artifact.py`
2. Implement `GET /api/artifact`:
   - Accept `path` query parameter
   - Validate path:
     - Must be relative (not start with /)
     - Must not contain `..`
     - Must resolve within project root
   - Read file content
   - Detect type from extension (markdown, json, yaml)
   - Parse frontmatter if markdown
   - Return `ArtifactResponse` model
3. Return 400 for invalid paths, 404 for missing files
4. Add security-focused tests

**Acceptance Criteria**:
- [ ] Serves file content for valid relative paths
- [ ] Rejects absolute paths with 400
- [ ] Rejects `..` traversal with 400
- [ ] Rejects paths outside project root with 400
- [ ] Returns 404 for missing files
- [ ] Detects file type correctly
- [ ] Parses markdown frontmatter
- [ ] Security tests verify path validation

**Files**: `src/cub/core/dashboard/api/routes/artifact.py`, `tests/test_api_artifact.py`

---

### Task: cub-a7f.3 - Implement /api/views endpoint

Priority: 0
Labels: api, model:haiku, complexity:low
Blocks: cub-m3x.3

**Context**: The views endpoint lists available view configurations for the view switcher UI.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/api/routes/views.py`
2. Implement `GET /api/views`:
   - For now, return hardcoded list of default views
   - Later will read from `.cub/views/` directory
   - Return list with id, name, is_default
3. Register route in app
4. Add tests

**Acceptance Criteria**:
- [ ] Returns list of available views
- [ ] Includes default, sprint, ideas views
- [ ] One view marked as is_default=True
- [ ] Tests verify response

**Files**: `src/cub/core/dashboard/api/routes/views.py`, `tests/test_api_views.py`

---

### Task: cub-a7f.4 - Implement /api/stats endpoint

Priority: 0
Labels: api, model:sonnet, complexity:medium
Blocks: cub-m3x.4

**Context**: The stats endpoint provides aggregate metrics for the stats bar: counts by type/stage, total cost, recent activity.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/api/routes/stats.py`
2. Implement `GET /api/stats`:
   - Query aggregate counts by type and stage
   - Sum cost_usd across entities with ledger data
   - Get recent activity (last 10 entity updates)
   - Return `StatsResponse` model
3. Add to `src/cub/core/dashboard/db/queries.py`:
   - `get_stats(conn) -> StatsResponse`
4. Register route in app
5. Add tests

**Acceptance Criteria**:
- [ ] Returns counts by entity type
- [ ] Returns counts by stage
- [ ] Returns total cost
- [ ] Returns recent activity list
- [ ] Tests verify aggregations

**Files**: `src/cub/core/dashboard/api/routes/stats.py`, `tests/test_api_stats.py`

---

### Task: cub-a7f.5 - Add error handling middleware and consistent error responses

Priority: 0
Labels: api, error-handling, model:sonnet, complexity:medium

**Context**: Ensure all API errors return consistent JSON responses with error codes, not stack traces.

**Implementation Steps**:
1. Update `src/cub/core/dashboard/api/app.py`:
   - Add exception handlers for common errors
   - Define `ErrorResponse` model: `{error: str, code: str, details: dict}`
2. Create error codes:
   - `ENTITY_NOT_FOUND`
   - `ARTIFACT_NOT_FOUND`
   - `INVALID_PATH`
   - `VIEW_NOT_FOUND`
   - `SYNC_ERROR`
   - `INTERNAL_ERROR`
3. Log errors with traceback for debugging
4. Return clean JSON to client
5. Add tests for error scenarios

**Acceptance Criteria**:
- [ ] All errors return consistent JSON format
- [ ] Error codes are meaningful and documented
- [ ] Stack traces logged but not exposed to client
- [ ] 4xx vs 5xx status codes used appropriately
- [ ] Tests verify error responses

**Files**: `src/cub/core/dashboard/api/app.py`, `tests/test_api_errors.py`

---

## Checkpoint 2: Full API Working

After completing Epic cub-a7f:
1. `/api/board` returns all entity types with correct stages
2. `/api/entity/{id}` shows full detail with relationships
3. `/api/stats` shows project metrics
4. All errors return clean JSON

**What's testable**: Full API via curl or Swagger UI at `/docs`

---

## Epic: cub-m3x - Kanban 4: Frontend Features

Priority: 2
Labels: phase-4, frontend, ui

Implement interactive frontend features: detail panel, view switching, stats bar, artifact viewer, and navigation.

### Task: cub-m3x.1 - Implement DetailPanel sidebar component

Priority: 0
Labels: frontend, ui, model:sonnet, complexity:medium
Blocks: cub-m3x.2

**Context**: When clicking an entity card, a sidebar slides in showing full details, relationships, and content.

**Implementation Steps**:
1. Create `src/cub/dashboard/web/src/components/DetailPanel.tsx`:
   - Slide-in from right animation
   - Header with entity type icon, ID, title, close button
   - Metadata section: stage, status, priority, dates
   - Relationships section: clickable links to parent, children, spec, plan
   - Content section: rendered markdown or raw text
   - Loading state while fetching
2. Create `src/cub/dashboard/web/src/hooks/useEntity.ts`:
   - Fetch entity detail from `/api/entity/{id}`
   - Cache results
3. Update `App.tsx`:
   - Track selected entity ID in state
   - Render DetailPanel when entity selected
4. Update `EntityCard.tsx`:
   - onClick sets selected entity ID
5. Style with Tailwind for professional appearance

**Acceptance Criteria**:
- [ ] Panel slides in when card clicked
- [ ] Shows all entity metadata
- [ ] Relationships displayed as clickable links
- [ ] Content rendered (basic text for now)
- [ ] Close button/escape key closes panel
- [ ] Loading state while fetching

**Files**: `src/cub/dashboard/web/src/components/DetailPanel.tsx`, `hooks/useEntity.ts`

---

### Task: cub-m3x.2 - Implement relationship navigation

Priority: 0
Labels: frontend, ui, model:sonnet, complexity:medium

**Context**: Clicking relationship links in the detail panel should navigate to that entity, enabling exploration of the entity graph.

**Implementation Steps**:
1. Update `DetailPanel.tsx`:
   - Make relationship links clickable
   - onClick navigates to that entity (updates selected ID)
2. Add breadcrumb or back button for navigation history
3. Create `src/cub/dashboard/web/src/hooks/useNavigation.ts`:
   - Track navigation history
   - Support back navigation
4. Style relationship links as visually distinct

**Acceptance Criteria**:
- [ ] Clicking parent/child/spec/plan link navigates to that entity
- [ ] Back button returns to previous entity
- [ ] Navigation history tracked (at least 1 level back)
- [ ] Links visually indicate they're clickable

**Files**: `src/cub/dashboard/web/src/components/DetailPanel.tsx`, `hooks/useNavigation.ts`

---

### Task: cub-m3x.3 - Implement ViewSwitcher dropdown

Priority: 0
Labels: frontend, ui, model:haiku, complexity:low

**Context**: The view switcher lets users change between different board configurations (Full Workflow, Sprint, Ideas).

**Implementation Steps**:
1. Create `src/cub/dashboard/web/src/components/ViewSwitcher.tsx`:
   - Dropdown showing available views
   - Fetch views from `/api/views`
   - Selected view highlighted
   - onChange triggers board reload with new view
2. Update `KanbanBoard.tsx`:
   - Accept `viewId` prop
   - Pass to `/api/board?view={viewId}`
3. Update `App.tsx`:
   - Track selected view in state
   - Pass to KanbanBoard
   - Render ViewSwitcher in header
4. Style as dropdown in top-right of header

**Acceptance Criteria**:
- [ ] Dropdown shows available views
- [ ] Selecting view reloads board with that configuration
- [ ] Current view indicated in dropdown
- [ ] Default view selected on load

**Files**: `src/cub/dashboard/web/src/components/ViewSwitcher.tsx`

---

### Task: cub-m3x.4 - Implement StatsBar component

Priority: 0
Labels: frontend, ui, model:haiku, complexity:low

**Context**: The stats bar shows quick metrics: entity counts by stage, total cost spent, etc.

**Implementation Steps**:
1. Create `src/cub/dashboard/web/src/components/StatsBar.tsx`:
   - Fetch from `/api/stats`
   - Display: total entities, by-stage counts, total cost
   - Compact horizontal layout
   - Auto-refresh when board refreshes
2. Update `App.tsx`:
   - Render StatsBar below header
3. Style for information density without clutter

**Acceptance Criteria**:
- [ ] Shows entity counts by stage
- [ ] Shows total cost (if available)
- [ ] Updates when board data changes
- [ ] Compact, non-intrusive display

**Files**: `src/cub/dashboard/web/src/components/StatsBar.tsx`

---

### Task: cub-m3x.5 - Implement ArtifactViewer with markdown rendering

Priority: 0
Labels: frontend, ui, model:sonnet, complexity:medium

**Context**: The artifact viewer renders spec/plan content nicely - markdown with syntax highlighting for code blocks.

**Implementation Steps**:
1. Install markdown library: `npm install marked highlight.js`
2. Create `src/cub/dashboard/web/src/components/ArtifactViewer.tsx`:
   - Fetch artifact from `/api/artifact?path={path}`
   - Detect type (markdown, json, yaml)
   - Render markdown with `marked`
   - Syntax highlight code blocks with `highlight.js`
   - Pretty-print JSON/YAML with highlighting
3. Update `DetailPanel.tsx`:
   - Use ArtifactViewer for content when source_path available
4. Add "View Source" button to open raw file

**Acceptance Criteria**:
- [ ] Markdown rendered with formatting
- [ ] Code blocks syntax highlighted
- [ ] JSON/YAML pretty-printed and highlighted
- [ ] Loading state while fetching
- [ ] Error state if artifact not found

**Files**: `src/cub/dashboard/web/src/components/ArtifactViewer.tsx`

---

### Task: cub-m3x.6 - Add loading states, error states, and keyboard navigation

Priority: 1
Labels: frontend, ui, polish, model:sonnet, complexity:medium

**Context**: Polish the UI with proper loading indicators, error handling, and keyboard shortcuts.

**Implementation Steps**:
1. Create loading skeleton components:
   - `ColumnSkeleton.tsx` - placeholder while loading
   - `CardSkeleton.tsx` - placeholder cards
2. Create error boundary and error display:
   - Catch fetch errors
   - Show retry button
   - Log errors to console
3. Add keyboard navigation:
   - `Escape` closes detail panel
   - `?` shows keyboard shortcuts help
   - Arrow keys navigate between cards (stretch goal)
4. Add empty state for columns with no entities

**Acceptance Criteria**:
- [ ] Loading skeletons shown while data fetches
- [ ] Errors displayed with retry option
- [ ] Escape key closes detail panel
- [ ] Empty columns show helpful message
- [ ] No flash of unstyled content

**Files**: Various frontend components

---

## Checkpoint 3: Interactive Dashboard

After completing Epic cub-m3x:
1. Click any entity to see full details in sidebar
2. Navigate relationships by clicking links
3. Switch between views
4. See project stats at a glance
5. View rendered markdown content

**What's testable**: Full interactive experience in browser

---

## Epic: cub-p9w - Kanban 5: Polish

Priority: 3
Labels: phase-5, polish

Production-ready polish: view configuration loading, default views, CLI commands, documentation.

### Task: cub-p9w.1 - Implement view configuration loading from .cub/views/

Priority: 0
Labels: config, views, model:sonnet, complexity:medium
Blocks: cub-p9w.2

**Context**: Load custom view configurations from YAML files in `.cub/views/` directory, with fallback to built-in defaults.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/views/__init__.py`
2. Create `src/cub/core/dashboard/views/loader.py`:
   - `load_views(views_dir: Path | None) -> list[ViewConfig]`
   - Parse YAML files from `.cub/views/`
   - Validate against ViewConfig model
   - Merge with built-in defaults
3. Create built-in default views as Python dicts
4. Update `/api/board` to use loaded view configs
5. Update `/api/views` to list loaded views
6. Add tests for YAML loading and validation

**Acceptance Criteria**:
- [ ] Loads views from `.cub/views/*.yaml`
- [ ] Falls back to built-in defaults if directory missing
- [ ] Validates view config structure
- [ ] Invalid configs logged and skipped (not fatal)
- [ ] Tests verify loading and merging

**Files**: `src/cub/core/dashboard/views/loader.py`, `tests/test_view_loader.py`

---

### Task: cub-p9w.2 - Ship default view configurations

Priority: 0
Labels: config, views, model:haiku, complexity:low

**Context**: Ship three default views as both built-in Python dicts and as example YAML files users can copy/modify.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/views/defaults.py`:
   - `DEFAULT_VIEW` - Full 8-column workflow
   - `SPRINT_VIEW` - Ready → In Progress → Review → Complete
   - `IDEAS_VIEW` - Captures → Specs → Planned
2. Create example files in `src/cub/dashboard/examples/`:
   - `default.yaml`
   - `sprint.yaml`
   - `ideas.yaml`
3. Add `cub dashboard init` command that copies examples to `.cub/views/`
4. Document view configuration format

**Acceptance Criteria**:
- [ ] Three built-in views available
- [ ] Example YAML files included in package
- [ ] `cub dashboard init` copies examples
- [ ] Views work correctly with board rendering

**Files**: `src/cub/core/dashboard/views/defaults.py`, `src/cub/dashboard/examples/*.yaml`

---

### Task: cub-p9w.3 - Implement cub dashboard export command

Priority: 1
Labels: cli, model:haiku, complexity:low

**Context**: Export the current board state as JSON for scripting, backup, or external tools.

**Implementation Steps**:
1. Update `src/cub/cli/dashboard.py`:
   - Add `export` subcommand
   - `cub dashboard export [--view VIEW] [--output FILE]`
2. Implementation:
   - Load board data (same as API)
   - Serialize to JSON
   - Write to file or stdout
3. Add tests

**Acceptance Criteria**:
- [ ] `cub dashboard export` outputs JSON to stdout
- [ ] `--output` writes to file
- [ ] `--view` selects which view to export
- [ ] Output matches API response format

**Files**: `src/cub/cli/dashboard.py`

---

### Task: cub-p9w.4 - Implement cub dashboard views command

Priority: 1
Labels: cli, model:haiku, complexity:low

**Context**: List available views from the CLI without starting the server.

**Implementation Steps**:
1. Update `src/cub/cli/dashboard.py`:
   - Add `views` subcommand
   - `cub dashboard views`
2. Implementation:
   - Load views using loader
   - Print table with id, name, description, is_default
   - Use Rich table for nice formatting
3. Add tests

**Acceptance Criteria**:
- [ ] `cub dashboard views` lists views in table format
- [ ] Shows which view is default
- [ ] Works without server running

**Files**: `src/cub/cli/dashboard.py`

---

### Task: cub-p9w.5 - Update documentation and CLAUDE.md

Priority: 1
Labels: docs, model:haiku, complexity:low

**Context**: Document the dashboard feature in CLAUDE.md and update any relevant documentation.

**Implementation Steps**:
1. Update `CLAUDE.md`:
   - Add `cub dashboard` to native commands list
   - Document all subcommands
   - Add dashboard to project structure
2. Update `README.md`:
   - Add dashboard feature description
   - Add usage example
3. Add docstrings to all new modules
4. Create `.cub/views/README.md` explaining view configuration

**Acceptance Criteria**:
- [ ] CLAUDE.md lists dashboard commands
- [ ] README mentions dashboard feature
- [ ] All new modules have docstrings
- [ ] View configuration documented

**Files**: `CLAUDE.md`, `README.md`, various module docstrings

---

### Task: cub-p9w.6 - Final test coverage and CI integration

Priority: 2
Labels: testing, ci, model:sonnet, complexity:medium

**Context**: Ensure adequate test coverage and CI integration for all new code.

**Implementation Steps**:
1. Run coverage report: `pytest --cov=src/cub/core/dashboard --cov=src/cub/cli/dashboard`
2. Add missing unit tests to reach 60%+ coverage (Moderate tier)
3. Add integration test: full flow from `cub dashboard sync` to API response
4. Add frontend build to CI if not already present
5. Update `.cub/STABILITY.md` with dashboard modules and tier

**Acceptance Criteria**:
- [ ] Test coverage >= 60% for new code
- [ ] Integration test for sync → API flow
- [ ] Frontend builds in CI
- [ ] STABILITY.md updated
- [ ] All tests pass in CI

**Files**: `tests/`, `.cub/STABILITY.md`, CI config

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-k8d | 8 | P0 | Vertical Slice: end-to-end minimal dashboard |
| cub-d2v | 6 | P1 | Expand Data: all parsers and relationships |
| cub-a7f | 5 | P2 | API Completeness: all endpoints |
| cub-m3x | 6 | P2 | Frontend Features: interactivity |
| cub-p9w | 6 | P3 | Polish: config, CLI, docs |

**Total**: 5 epics, 31 tasks

**Checkpoints**:
1. After cub-k8d: Minimal dashboard in browser (specs only)
2. After cub-a7f: Full API with all entity types
3. After cub-m3x: Interactive dashboard with detail views

---

## Dependency Graph

```
cub-k8d.1 (schema) ──┬──▶ cub-k8d.3 (spec parser) ──▶ cub-k8d.4 (sync) ──┐
                    │                                                     │
                    └──▶ cub-k8d.2 (models) ─────────▶ cub-k8d.4 ────────┤
                                             │                            │
                                             └──▶ cub-k8d.5 (API) ───────┤
                                                                         │
cub-k8d.6 (frontend setup) ──▶ cub-k8d.7 (board UI) ─────────────────────┤
                                                                         │
                                                                         ▼
                                                                  cub-k8d.8 (CLI)
                                                                         │
           ┌─────────────────────────────────────────────────────────────┘
           ▼
    cub-d2v.* (parsers) ──▶ cub-d2v.5 (resolver) ──▶ cub-d2v.6 (integrate)
           │
           ├──▶ cub-a7f.1 (entity endpoint) ──▶ cub-m3x.1 (detail panel)
           ├──▶ cub-a7f.2 (artifact endpoint) ──▶ cub-m3x.5 (artifact viewer)
           ├──▶ cub-a7f.3 (views endpoint) ──▶ cub-m3x.3 (view switcher)
           └──▶ cub-a7f.4 (stats endpoint) ──▶ cub-m3x.4 (stats bar)
                                  │
                                  ▼
                           cub-p9w.* (polish)
```

---

## Model Distribution

| Model | Tasks | Rationale |
|-------|-------|-----------|
| opus | 2 | Complex logic: resolver/stage computation, path security validation |
| sonnet | 23 | Standard implementation: parsers, API endpoints, UI components |
| haiku | 6 | Simple tasks: configs, CLI subcommands, documentation |

---

## Ready to Start

These tasks have no blockers:
- **cub-k8d.1**: Create SQLite schema and database module [P0] (sonnet)
- **cub-k8d.2**: Create Pydantic models for dashboard entities [P0] (sonnet)
- **cub-k8d.6**: Set up Vite + Preact + Tailwind frontend project [P0] (sonnet)

Can be done in parallel to accelerate Phase 1.

---

## Critical Path

```
cub-k8d.1 → cub-k8d.3 → cub-k8d.4 → cub-k8d.5 → cub-k8d.8 → [Checkpoint 1: Visible!]
                                         ↑
cub-k8d.6 → cub-k8d.7 ───────────────────┘
```

**Shortest path to browser**: 8 tasks in Epic cub-k8d

---

**Next Step:** Run `cub stage` to import tasks into beads and start development.
