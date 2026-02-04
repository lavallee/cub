# Orient Report: Project Kanban Dashboard

**Date:** 2026-01-23
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

A web-based kanban dashboard (`cub dashboard`) providing unified visibility across captures, specs, plans, epics, and tasks as they flow through the development lifecycle. Solves the problem of fragmented project state scattered across multiple file types and backends, making it hard to maintain mental context on complex or multi-project work.

## Problem Statement

People working on projects of any complexity, or juggling multiple projects, have a hard time keeping the whole picture in their heads. Project state is fragmented across specs/, .cub/sessions/, .beads/, .cub/ledger/, and CHANGELOG.md - there are few tools that provide streamlined, real-time understanding of where everything stands.

## Refined Vision

A read-only web dashboard launched via `cub dashboard` that:
- Aggregates all work artifacts into a single SQLite database via sync layer
- Displays 8-column kanban board: CAPTURES → SPECS → PLANNED → READY → IN_PROGRESS → NEEDS_REVIEW → COMPLETE → RELEASED
- Shows entity hierarchy (specs contain plans, plans contain epics, epics contain tasks)
- Links related artifacts via explicit markers in frontmatter
- Parses CHANGELOG.md to determine which work has shipped
- Supports configurable views via JSON/YAML files (no UI editor needed)

Primary audience: Solo developer + occasional stakeholder demos.

## Requirements

### P0 - Must Have

| Requirement | Rationale |
|-------------|-----------|
| **Sync layer** - Import specs, plans, beads/JSON tasks, ledger, CHANGELOG into SQLite | Core data aggregation enabling all other features |
| **Stage computation** - Place entities correctly across 8 columns | The fundamental value proposition |
| **Explicit relationship markers** - Define convention for `spec_id`, `plan_id`, `epic_id` in artifacts | Reliable linking without fragile heuristics |
| **FastAPI server** - `/api/board`, `/api/entity/{id}`, `/api/artifact` endpoints | Backend for web UI |
| **Kanban board UI** - 8 columns, entity cards, horizontal scroll | Primary interface |
| **Detail panel** - Click entity → metadata, relationships, content | Context without leaving the board |
| **CHANGELOG.md parsing** - Extract release → task/epic mappings | Powers RELEASED stage detection |
| **`cub dashboard` command** - Start server, auto-sync, open browser | Entry point |

### P1 - Should Have

| Requirement | Rationale |
|-------------|-----------|
| **View configurations via JSON/YAML** - Ship 2-3 defaults, users can create custom | Different contexts need different views (full workflow vs sprint) |
| **Artifact viewer** - Render markdown, syntax-highlight JSON/YAML | See content without opening files |
| **Stats bar** - Counts by stage, total cost | Quick health check |
| **Relationship navigation** - Click links to navigate between related entities | Traceability is a core goal |

### P2 - Nice to Have

| Requirement | Rationale |
|-------------|-----------|
| **View persistence** - Remember last selected view | Minor convenience |
| **Column collapsing** - Hide RELEASED or CAPTURES to save space | UI polish |
| **Label filtering** - Filter board by labels | Useful for large projects |
| **Export** - `cub dashboard export` dumps board as JSON | Scripting/automation |

## Constraints

None hard - flexibility to build this right.

## Assumptions

- Modern browser only (no IE11 support)
- Projects comfortably fit in SQLite (< 10K entities)
- Ledger system will be available (parallel development, can stub if needed)
- FastAPI and SQLite are acceptable new dependencies for cub
- CHANGELOG.md follows a parseable convention with task/epic IDs

## Open Questions / Experiments

| Unknown | Experiment |
|---------|------------|
| Best frontend framework | Build Phase 2 UI with chosen stack (React, SolidJS, or Svelte), evaluate DX. If painful, migrate before Phase 3 polish work |
| Optimal sync frequency | Start with on-demand (`cub dashboard sync` + sync on startup). Add auto-refresh polling only if stale data becomes annoying in practice |

## Out of Scope

- **Editing/mutations from UI** - Continue using CLI for changes; v2 feature
- **Real-time websocket updates** - Polling/manual refresh sufficient for MVP
- **Multi-project aggregation** - One dashboard per project for now
- **Mobile-optimized views** - Desktop-first
- **PR/merge/release automation wiring** - CHANGELOG is source of truth, no GitHub integration needed yet

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Sync layer complexity becomes maintenance burden | Medium | Keep sync logic simple and explicit; accept some staleness rather than over-engineering incremental updates |
| Artifact marker adoption inconsistent | Medium | Update spec/plan generators (cub skills) to include markers as part of this project; document convention in CLAUDE.md |
| CHANGELOG parsing fragility | Low | Define strict format convention; fail gracefully with warning if unparseable |
| Frontend framework regret | Low | Start with familiar stack; architecture keeps frontend "dumb" so migration is feasible |

## MVP Definition

The full 8-column read-only dashboard:

1. **Sync layer** imports from all sources (specs, plans, tasks, ledger, CHANGELOG)
2. **SQLite database** at `.cub/dashboard.db` with entities and relationships
3. **FastAPI server** serving API + static frontend
4. **Kanban board** showing all 8 stages with entity cards
5. **Hierarchy display** - epics show child tasks inline, specs show child plans
6. **Detail panel** - click any entity to see metadata, relationships, rendered content
7. **View configs** - JSON/YAML files defining column layouts, shipped with 2-3 defaults
8. **`cub dashboard`** command to sync, start server, open browser

Success feels like: "I can answer 'what's the state of X?' in under 30 seconds by glancing at the dashboard."

---

## Artifact Marker Convention (New)

To enable reliable relationship linking, artifacts should include explicit markers:

**Specs** (`specs/**/*.md` frontmatter):
```yaml
id: project-kanban-dashboard  # unique spec identifier
```

**Plans** (`.cub/sessions/*/session.json`):
```json
{
  "spec_id": "project-kanban-dashboard"
}
```

**Epics/Tasks** (beads or plan.jsonl):
```json
{
  "spec_id": "project-kanban-dashboard",
  "plan_id": "cub-20260123-120000"
}
```

**CHANGELOG.md** entries:
```markdown
## [0.25.0] - 2026-02-15

### Added
- Project kanban dashboard (cub-E10, cub-101, cub-102, cub-103)
```

The sync layer parses these markers to build the relationship graph.

---

**Next Step:** Run `cub architect` to proceed to technical design.
