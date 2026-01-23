# Punchlist: 2026-01-23-dashboard-bugs-01

## Fix card side panel blocking main board view

When clicking a card to open the side panel detail view, the main Kanban board becomes completely black instead of remaining visible. The side panel should slide in as an overlay without obscuring the background board.

**Context:**
The dashboard uses a side panel for detailed card views. Currently, when the panel opens, it's rendering with a background color or opacity that hides the main board content.

**Acceptance Criteria:**
- Side panel slides in as an overlay (not pushing/replacing main view)
- Main board remains visible and readable behind the panel
- Background board content is not obscured by black overlay or background color
- Smooth animation when panel opens/closes

---

## Fix Readiness validation errors in dashboard sync

When running `cub dashboard sync`, the parser fails to validate spec files with `readiness.tools_needed` field. The error indicates the parser is receiving dictionaries instead of strings for `tools_needed` items.

**Root Cause:** The `Readiness` model in `src/cub/core/specs/models.py:137` expects `tools_needed: list[str]`, but some spec files (like `specs/researching/tools-registry.md`) have YAML structure that gets parsed as dictionaries instead of strings.

**Affected Files:**
- `specs/researching/tools-registry.md` (lines 32-40): `tools_needed` entries formatted as complex objects
- `specs/researching/external-tools-analysis.md`: Similar issue mentioned in error

**Acceptance Criteria:**
1. Dashboard sync completes without validation errors
2. All spec files in `specs/researching/` parse successfully
3. The `tools_needed` field properly captures tool descriptions whether formatted as simple strings or complex structures
4. Error messages are clear if malformed YAML is encountered

**Options:**
- Update the YAML in affected spec files to use simple string format
- Enhance the Readiness model to accept flexible input (string or structured tool objects)
- Add YAML validation/migration tooling to help users fix their specs

---

## Enrich dashboard cards with metadata during sync

Enhance the dashboard to display contextual information on cards by extracting metadata during the sync phase rather than at render time. This allows graceful degradation when data is incomplete.

**Current State:**
Dashboard cards display minimal information (ID, title). Users lack visibility into work readiness and scope.

**Desired Changes:**

1. **SPEC Cards** - Add readiness score and note info
   - Extract readiness assessment from spec content
   - Display associated notes/comments

2. **EPIC Cards** - Add task count, priority, and description context
   - Count associated tasks during resolution phase
   - Extract priority level from epic metadata
   - Display brief description excerpt

3. **PLAN Cards** - Add description context and epic count
   - Extract description from plan content
   - Count number of EPICs this plan implements

**Implementation Approach:**
- Extend entity model to include optional metadata fields (readiness_score, task_count, priority, description, etc.)
- Update parsers (SpecParser, PlanParser, TaskParser) to extract this info during sync
- Store metadata in database alongside entity records
- Use graceful fallback (omit field or use default) when data is unavailable
- Return metadata in API responses for rendering

**Acceptance Criteria:**
- [ ] Entity models include optional metadata fields
- [ ] Sync phase extracts and validates metadata from source files
- [ ] Database schema updated to store metadata
- [ ] API returns metadata in entity responses
- [ ] UI displays metadata on cards (or gracefully omits if unavailable)
- [ ] Tests verify extraction with complete and incomplete data
- [ ] All tests passing, mypy clean

---

## Add BLOCKED stage for tasks not yet ready

Currently, tasks and epics that are not ready (e.g., blocked by dependencies) are incorrectly placed in the PLANNED stage. We need to create a new BLOCKED stage to properly represent their status.

**Context:**
The dashboard's stage computation logic currently lacks a distinct stage for blocked work items. Tasks and epics that cannot proceed (due to unmet dependencies, blocking issues, etc.) should be visually separated from PLANNED items, which represent work that is ready to start but hasn't been started yet.

**Acceptance Criteria:**
- [ ] New BLOCKED stage is added to the Stage enum in `cub.core.dashboard.db.models`
- [ ] Stage computation logic in `cub.core.dashboard.sync` correctly identifies and assigns tasks/epics to BLOCKED stage when they have blocking dependencies or are not ready
- [ ] BLOCKED stage is positioned appropriately in the Kanban workflow (between SPECS and READY)
- [ ] Dashboard API returns BLOCKED stage entities correctly
- [ ] Dashboard views display BLOCKED as a distinct column
- [ ] Tests verify that blocked tasks/epics appear in BLOCKED stage, not PLANNED
- [ ] EPICs and TASKs no longer appear in PLANNED stage unless they are actually ready to start

---

## Group PLANNED specs with their corresponding plans

Currently, SPEC entities in the PLANNED stage are displayed as separate cards in the Kanban board. They should be grouped together with their corresponding PLAN entities (which implement them) to show the relationship between specification and implementation.

**Context:**
- PLAN entities have a `plan_id` marker that links them to their SPEC
- SPEC entities in PLANNED stage represent specifications that have implementation plans
- Grouping them together improves visualization of spec→plan relationships

**Acceptance Criteria:**
- [ ] PLANNED specs appear as a sub-group or nested within the same column as their corresponding PLAN entity
- [ ] The grouping respects the existing `plan_id` relationship marker in PLAN entities
- [ ] Legacy specs without plans (no corresponding PLAN entity) remain as floating cards in the PLANNED stage
- [ ] Grouping is configurable via view configuration (`.cub/views/*.yaml`)
- [ ] Dashboard board API (`/api/board`) returns grouped structure
- [ ] Web UI renders specs grouped with their plans

---

## Group ready tasks by epic in dashboard

In the dashboard ready column, tasks should be grouped by their associated epic. Tasks without an epic should appear in a separate ungrouped section.

**Context:**
The dashboard currently displays ready tasks without epic grouping. Tasks can be associated with epics through multiple mechanisms:
1. Parent relationship (beads parent field)
2. Label with epic ID format (e.g., `epic:cub-abc`)
3. Explicit epic_id field in task metadata

**Acceptance Criteria:**
- [ ] Sync layer detects epic associations during task parsing (check parent, labels, epic_id)
- [ ] Task model stores epic_id field after sync
- [ ] Ready column displays tasks grouped by epic
- [ ] Tasks without epic association appear in separate "No Epic" group
- [ ] Epic names/titles appear as group headers
- [ ] Dashboard API returns epic grouping metadata in `/api/board` response

---

## Rename dashboard column from "SPECS" to "RESEARCHING"

The Kanban dashboard currently displays a column titled "SPECS" for spec entities in the researching/ directory. This should be renamed to "RESEARCHING" to better reflect the workflow stage and align with the actual spec status value.

**Context:**
The dashboard's 8-column workflow includes a stage for specs that are actively being researched. The column header "SPECS" is ambiguous—it refers to the entity type rather than the workflow stage.

**Acceptance Criteria:**
- Column header displays "RESEARCHING" instead of "SPECS"
- Contains spec entities with status "researching"
- Maintains all filtering and grouping logic
- API response structure unchanged (still maps to SPECS stage internally if needed)

---

## the view switcher doesn’t work. it just says...

the view switcher doesn’t work. it just says “API request failed: Not Found”

---

## Fix artifact content HTML rendering

Artifact content is rendering raw HTML markup instead of interpolated/processed HTML. When artifacts are displayed in the dashboard or UI, HTML tags appear as text (e.g., `<div>content</div>`) instead of being rendered as actual DOM elements.

**Context:**
The dashboard sync layer parses artifact content from files and stores it in the database. When this content is served via the API and rendered in the frontend, HTML should be properly rendered as DOM elements, not displayed as raw markup.

**Acceptance Criteria:**
- Artifact HTML content renders as DOM elements in the UI (not as text)
- HTML tags are properly interpreted and displayed
- No XSS vulnerabilities introduced (content should be sanitized if user-generated)
- Artifacts display with proper formatting and styling
- Both inline HTML and structured HTML artifacts work correctly

---

## Format frontmatter gracefully in dashboard entities

Currently, the dashboard system parses frontmatter from markdown files but doesn't handle edge cases or malformed YAML gracefully. When frontmatter is missing, incomplete, or invalid, the parser may fail or produce unhelpful errors.

**Context:**
The dashboard sync layer parses entity metadata from frontmatter in spec and plan markdown files. This includes critical fields like `id`, `spec_id`, `plan_id`, `epic_id`, and `status`.

**Acceptance Criteria:**
- [ ] Invalid YAML frontmatter produces clear error messages (not stack traces)
- [ ] Missing frontmatter markers (e.g., no `---` delimiters) are handled gracefully
- [ ] Empty or null frontmatter fields don't crash parsers
- [ ] Sync operation continues with partial results when some files fail
- [ ] Warnings are logged for malformed files but don't block dashboard functionality
- [ ] Entity relationship linking (spec_id → plan_id) degrades gracefully if markers are missing

**Related modules:**
- `cub.core.dashboard.sync.parsers` - SpecParser, PlanParser
- `cub.core.dashboard.sync.orchestrator` - SyncOrchestrator
- Error handling throughout dashboard initialization

---
