---
status: planned
priority: high
complexity: high
dependencies: []
blocks: []
created: 2026-02-04
updated: 2026-02-04
readiness:
  score: 7
  blockers: []
  questions:
  - What's the retention policy for JSONL harness logs given increased verbosity?
  - Should knowledge from old random-suffix IDs be migrated to new IDs in ledger?
  decisions_needed:
  - Confirm optimistic locking is sufficient for counter allocation
  tools_needed: []
spec_id: cub-048
---
# Ledger Consolidation & Unified ID System

## Overview

The cub project has accumulated redundant storage (runs/, ledger/, run-sessions/), collision-prone IDs, and missing traceability from specs to tasks. This spec consolidates storage into a single canonical ledger and introduces a hierarchical ID system tracked via the sync branch to enable full traceability and collision-free numbering across branches and worktrees.

## Goals

- Implement hierarchical IDs: spec(number) → plan(spec+letter) → epic(plan+letter) → task(epic.number)
- Track global counters (spec_number, standalone_task_number) on sync branch
- Eliminate `runs/` directory entirely
- Merge `run-sessions/` into `ledger/by-run/`
- Add `ledger/by-plan/` for plan-level aggregates
- Flatten `attempts/` subdirectories (artifacts numbered at task level)
- Convert harness logs to JSONL format
- Collapse `cub build-plan` into `cub run --plan`
- Add lifecycle hooks: end-of-task, end-of-epic, end-of-plan, pre-session
- Add commands: `release`, `retro`, `learn extract`, `verify`, `sync agent`
- Implement managed sections for agent.md in existing projects
- Add fast consistency checks to `cub run` and `cub doctor`
- Fix epic title capture in ledger entries (currently captures ID instead of title)
- Ensure ledger artifacts are committed alongside code (not scooped up afterward)
- Eliminate redundant `logs/` directory (build-plan wrapper logs)

## Non-Goals

- Building the knowledge graph / self-improving agent (separate spec)
- Migrating external task systems (Jira, Linear, etc.)
- Multi-project knowledge sharing
- Real-time collaboration features

## Design / Approach

### ID Hierarchy

```
Spec:       {project_id}-{number:03d}     → cub-054
Plan:       {spec_id}{LETTER}             → cub-054A
Epic:       {plan_id}-{char}              → cub-054A-0
Task:       {epic_id}.{number}            → cub-054A-0.1
Standalone: {project_id}-s{number:03d}    → cub-s017
```

**Visual Distinction by Level:**
- Specs end with **numbers** (054)
- Plans add **uppercase letter** (054A, 054B)
- Epics add **hyphen + number/lowercase** (054A-0, 054A-a)
- Tasks add **dot + number** (054A-0.1)

**Letter Sequences (62 options each):**
- Plans: `A-Z`, `a-z`, `0-9` (uppercase first)
- Epics: `0-9`, `a-z`, `A-Z` (numbers first)

### Counter Tracking

Store in `.cub/counters.json`, committed to sync branch:
```json
{
  "spec_number": 54,
  "standalone_task_number": 17
}
```

Allocation: optimistic locking with collision detection at staging time.

### Ledger Structure

```
.cub/ledger/
├── index.jsonl
├── by-task/{task_id}.json
├── by-task/{task_id}/
│   ├── 001-prompt.md
│   └── 001-harness.jsonl
├── by-epic/{epic_id}/entry.json
├── by-plan/{plan_id}/entry.json
└── by-run/{run_id}.json
```

### Artifacts in Git Philosophy

**Core Principle**: All cub artifacts belong in the git repo alongside code, not just the code itself.

**Commit with Code**:
- Ledger entries should be committed as part of the task commit (not scooped up by a catch-all process later)
- Task completion = code changes + ledger entry in same commit
- Epic completion = final task commit + epic summary entry

**Exclude from Git** (`.gitignore`):
- SQLite databases that are purely speed-up caches (e.g., `.cub/cache/*.db`)
- SQLite journal/WAL files (`*.db-journal`, `*.db-wal`, `*.db-shm`)
- Temporary files (`*.tmp`, `*.bak`)
- Active session state (`active-run.json` symlink)

**Include in Git**:
- All ledger entries (`.cub/ledger/**/*.json`, `*.jsonl`)
- All prompts and harness logs (`.cub/ledger/**/001-*.md`, `001-*.jsonl`)
- Counters (`.cub/counters.json`)
- Configuration (`.cub/config.json`)

## Implementation Notes

### Phase 1: Migration Script
- Retroactively number existing specs by creation date
- Update plan.json files with new plan IDs
- Update tasks.jsonl with new task IDs
- Update itemized-plan.md files
- Initialize counters.json on sync branch

### Phase 2: ID System
- Extend sync state schema to include counters
- Implement counter allocation protocol
- Update ID generation in `src/cub/core/plan/ids.py`

### Phase 3: Ledger Consolidation
- Remove runs/ writes from StatusWriter
- Merge run-sessions/ into ledger/by-run/
- Flatten attempts/ directories
- Implement JSONL harness log writer
- Remove logs/ directory (build-plan wrapper logs become part of by-plan/)
- Fix epic title capture (currently saves ID instead of title in by-epic entries)
- Update .gitignore template for cache exclusions

### Phase 4: Commands and Hooks
- Add `--plan` flag to run command (collapse build-plan into run)
- Move plan iteration logic from build_plan.py to run loop
- Implement lifecycle hooks
- Add new commands to CLI

### Phase 5: Agent Instructions
- Implement managed section injection
- Add consistency checks

## Open Questions

1. What's the retention policy for JSONL harness logs given increased verbosity?
2. Should knowledge from old random-suffix IDs be migrated to new IDs in ledger?

## Future Considerations

- Vector embeddings for semantic search across ledger (Knowledge System spec)
- Cross-project ID namespacing if cub manages multiple projects
- Archive/compress old ledger entries after N days

---

**Status**: planned
**Last Updated**: 2026-02-04
