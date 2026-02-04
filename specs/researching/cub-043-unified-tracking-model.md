---
status: researching
priority: high
complexity: high
dependencies:
- dashboard-sync-system
blocks: []
created: 2026-01-24
updated: 2026-01-24
readiness:
  score: 7
  blockers: []
  questions:
  - Retention policy for harness.log files (time-based vs count-based)?
  - Should old attempt logs be compressed/archived?
  - How to handle partial completion (some subtasks done)?
  decisions_needed:
  - Exact API endpoint structure for entity updates
  tools_needed: []
spec_id: cub-043
---
# Unified Tracking Model

## Overview

This spec consolidates cub's tracking systems into a unified model centered on the **ledger** as the permanent record of work. The ledger extends the task lifecycle beyond what the task backend (beads) handles—tracking work from first development attempt through review, validation, and release.

**Core Principle**: The ledger is the single source of truth for completed work. The dashboard database is a derived cache for query performance. All data can be reconstructed from files in the repo.

## Goals

- Establish ledger as the canonical record of task and epic lifecycle
- Track development attempts with full context (prompt, conditions, output)
- Enable post-development workflow stages (review, validation, release)
- Support bidirectional sync with dashboard (files ↔ DB)
- Provide CLI commands for ledger queries and updates
- Capture task/epic lineage (spec → plan → epic → task)

## Non-Goals

- Multi-agent/parallel execution handling
- External integrations (GitHub issues, Linear, Jira)
- Automated verification/CI integration (on-demand only for now)
- Backward compatibility with existing ledger format

## Design / Approach

### The Three Artifact Types

#### 1. Run Sessions (`.cub/run-sessions/`)

All runs live in `.cub/run-sessions/` with a symlink for the active run.

```
.cub/
├── active-run.json              # Symlink → run-sessions/{current-run-id}.json
└── run-sessions/
    ├── cub-20260124-123456.json  # Completed run
    ├── cub-20260124-140000.json  # Current run (symlink target)
    └── cub-20260123-090000.json  # Orphaned run (marked as such)
```

**Run file structure:**
```json
{
  "run_id": "cub-20260124-123456",
  "started_at": "2026-01-24T12:34:56",
  "project_dir": "/path/to/project",
  "harness": "claude",
  "budget": {
    "tokens_used": 50000,
    "tokens_limit": 1000000,
    "cost_usd": 1.23,
    "cost_limit": 10.00
  },
  "tasks_completed": 3,
  "tasks_failed": 0,
  "current_task": "cub-abc",
  "status": "running|completed|orphaned",
  "orphaned_at": null,
  "orphaned_reason": null
}
```

**Lifecycle:**
- Created in `run-sessions/` when `cub run` starts
- Symlink `active-run.json` points to current run
- On clean completion: status → `completed`, symlink removed
- On new run with existing active: old run marked `orphaned`, new symlink created
- `cub monitor` reads via symlink for simplicity

#### 2. Task Ledger (`.cub/ledger/by-task/{task-id}/`)

The permanent record of a task's lifecycle from first development attempt to release.

```
.cub/ledger/by-task/{task-id}/
├── entry.json           # The structured record
└── attempts/
    ├── 001-prompt.md    # Prompt with execution context (frontmatter)
    ├── 001-harness.log  # Harness output
    ├── 002-prompt.md    # Retry prompt
    └── 002-harness.log  # Retry output
```

**Prompt file format (with frontmatter):**
```markdown
---
attempt: 1
harness: claude
model: haiku
run_id: cub-20260124-123456
started_at: 2026-01-24T12:35:00
---

# Task: Fix the login bug

## Description
Users report 500 error when clicking login with empty password field...

## Context
...
```

**entry.json structure:**
```json
{
  "id": "cub-abc",
  "version": 1,

  "lineage": {
    "spec_file": "specs/planned/auth-fixes.md",
    "plan_file": ".cub/sessions/auth-sprint/plan.jsonl",
    "epic_id": "cub-xyz"
  },

  "task": {
    "title": "Fix the login bug",
    "description": "Users report 500 error...",
    "type": "bug",
    "priority": 1,
    "labels": ["auth", "urgent"],
    "created_at": "2026-01-20T10:00:00",
    "captured_at": "2026-01-24T12:35:00"
  },

  "task_changed": {
    "detected_at": "2026-01-24T14:00:00",
    "fields_changed": ["description", "labels"],
    "original_description": "...",
    "final_description": "...",
    "notes": "Scope expanded during implementation"
  },

  "attempts": [
    {
      "attempt_number": 1,
      "run_id": "cub-20260124-123456",
      "started_at": "2026-01-24T12:35:00",
      "completed_at": "2026-01-24T12:40:00",
      "harness": "claude",
      "model": "haiku",
      "success": false,
      "error_category": "test_failure",
      "error_summary": "test_login_empty_password failed",
      "tokens": { "input": 1000, "output": 500, "cache_read": 5000, "cache_write": 200 },
      "cost_usd": 0.02,
      "duration_seconds": 300
    },
    {
      "attempt_number": 2,
      "run_id": "cub-20260124-123456",
      "started_at": "2026-01-24T12:41:00",
      "completed_at": "2026-01-24T12:50:00",
      "harness": "claude",
      "model": "sonnet",
      "success": true,
      "tokens": { "input": 1200, "output": 800, "cache_read": 5500, "cache_write": 100 },
      "cost_usd": 0.15,
      "duration_seconds": 540
    }
  ],

  "outcome": {
    "success": true,
    "completed_at": "2026-01-24T12:50:00",
    "total_cost_usd": 0.17,
    "total_attempts": 2,
    "total_duration_seconds": 840,
    "final_model": "sonnet",
    "escalated": true,
    "escalation_path": ["haiku", "sonnet"],
    "files_changed": ["src/auth/login.py", "tests/test_login.py"],
    "commits": [
      { "hash": "abc123f", "message": "fix: validate password before auth check", "timestamp": "2026-01-24T12:49:00" }
    ],
    "approach": "Added early validation in login handler...",
    "decisions": ["Used built-in validator instead of custom regex"],
    "lessons_learned": ["Auth endpoints should validate all inputs before business logic"]
  },

  "drift": {
    "additions": ["Rate limiting added (not in original spec)"],
    "omissions": [],
    "severity": "minor"
  },

  "verification": {
    "status": "pending|pass|fail",
    "checked_at": null,
    "tests_passed": null,
    "typecheck_passed": null,
    "lint_passed": null,
    "notes": []
  },

  "workflow": {
    "stage": "dev_complete|needs_review|validated|released",
    "stage_updated_at": "2026-01-24T15:00:00"
  },

  "state_history": [
    { "stage": "in_progress", "at": "2026-01-24T12:35:00", "by": "cub-run" },
    { "stage": "dev_complete", "at": "2026-01-24T12:50:00", "by": "cub-run" },
    { "stage": "needs_review", "at": "2026-01-24T14:00:00", "by": "dashboard:user@example.com" },
    { "stage": "validated", "at": "2026-01-24T16:00:00", "by": "dashboard:user@example.com" },
    { "stage": "needs_review", "at": "2026-01-24T17:00:00", "by": "dashboard:user@example.com", "reason": "Found regression" }
  ]
}
```

#### 3. Epic Ledger (`.cub/ledger/by-epic/{epic-id}/`)

Aggregated record of an epic's lifecycle.

```
.cub/ledger/by-epic/{epic-id}/
└── entry.json
```

**entry.json structure:**
```json
{
  "id": "cub-xyz",
  "version": 1,

  "lineage": {
    "spec_file": "specs/planned/auth-improvements.md",
    "plan_file": ".cub/sessions/auth-sprint/plan.jsonl"
  },

  "epic": {
    "title": "Auth Improvements Sprint",
    "description": "Improve authentication error handling and validation",
    "created_at": "2026-01-20T09:00:00",
    "captured_at": "2026-01-24T12:00:00"
  },

  "tasks": ["cub-abc", "cub-def", "cub-ghi"],

  "aggregates": {
    "total_tasks": 3,
    "tasks_completed": 2,
    "tasks_in_progress": 1,
    "total_cost_usd": 0.45,
    "total_tokens": { "input": 5000, "output": 2500, "cache_read": 15000, "cache_write": 500 },
    "total_attempts": 4,
    "escalation_rate": 0.33,
    "avg_cost_per_task": 0.15
  },

  "workflow": {
    "stage": "in_progress|dev_complete|needs_review|validated|released",
    "stage_updated_at": "2026-01-24T15:00:00"
  },

  "state_history": [
    { "stage": "in_progress", "at": "2026-01-24T12:00:00", "by": "cub-run" },
    { "stage": "dev_complete", "at": "2026-01-24T18:00:00", "by": "cub-run" }
  ]
}
```

#### 4. Ledger Index (`.cub/ledger/index.jsonl`)

Quick-lookup index for queries. One line per entity.

```jsonl
{"type":"task","id":"cub-abc","title":"Fix the login bug","epic":"cub-xyz","stage":"validated","cost":0.17,"attempts":2}
{"type":"task","id":"cub-def","title":"Add rate limiting","epic":"cub-xyz","stage":"dev_complete","cost":0.08,"attempts":1}
{"type":"epic","id":"cub-xyz","title":"Auth Improvements Sprint","stage":"in_progress","cost":0.45,"tasks":3}
```

### Lifecycle Flow

```
Task Backend (Beads)              Ledger
─────────────────────            ────────

[open] ─────────────────────────────────────────────────────────────
   │
   │  cub run claims task (OPEN → IN_PROGRESS)
   ▼
[in_progress] ──────────────────► Create ledger entry
   │                               - Copy task fields + lineage
   │                               - Set captured_at
   │                               - attempts = []
   │                               - state_history = [{stage: in_progress}]
   │
   │  Attempt 1
   │  - Write 001-prompt.md (with frontmatter)
   │  - Execute harness
   │  - Write 001-harness.log
   │  - Append to attempts[]
   │
   │  Attempt N (if retry/escalate)
   │  - Write NNN-prompt.md
   │  - Execute harness
   │  - Write NNN-harness.log
   │  - Append to attempts[]
   │
   │  Task succeeds
   ▼
[closed] ──────────────────────► Finalize ledger entry
   │                             - Re-fetch task from backend
   │                             - Detect task_changed
   │                             - Populate outcome
   │                             - Set stage: dev_complete
   │                             - Update epic aggregates
   │                             - Update index.jsonl
   │
   │  (Ledger takes over - beyond task backend scope)
   ▼
[dev_complete] ─────────────────► User reviews in dashboard
   │                               - Manual or automated checks
   ▼
[needs_review] ─────────────────► PR review, QA, etc.
   │                               - Can move backward if issues found
   ▼
[validated] ────────────────────► Approved, ready for release
   │
   ▼
[released] ─────────────────────► In CHANGELOG, shipped
```

### CLI Commands

#### `cub ledger show <id>`
Display detailed ledger entry for a task or epic.

```bash
cub ledger show cub-abc                    # Full entry
cub ledger show cub-abc --attempt 1        # Specific attempt details
cub ledger show cub-abc --changes          # Show task_changed details
cub ledger show cub-abc --history          # Show state_history
```

#### `cub ledger stats`
Aggregate statistics from the ledger.

```bash
cub ledger stats                           # Overall project stats
cub ledger stats --epic cub-xyz            # Stats for specific epic
cub ledger stats --model-analysis          # Model effectiveness breakdown
cub ledger stats --since 2026-01-01        # Time-bounded stats
```

#### `cub ledger search`
Query ledger entries.

```bash
cub ledger search --stage needs_review     # By workflow stage
cub ledger search --escalated              # Tasks that needed escalation
cub ledger search --drift significant      # Tasks with significant drift
cub ledger search --cost-above 0.50        # Expensive tasks
```

#### `cub ledger update <id>`
Update workflow stage or other fields.

```bash
cub ledger update cub-abc --stage validated
cub ledger update cub-abc --stage needs_review --reason "Found regression"
```

#### `cub ledger export`
Export ledger data for external analysis.

```bash
cub ledger export --format csv > ledger.csv
cub ledger export --format json --epic cub-xyz > epic-data.json
```

#### `cub ledger gc`
Garbage collect old attempt logs.

```bash
cub ledger gc --older-than 90d             # Remove logs older than 90 days
cub ledger gc --keep-latest 3              # Keep only last 3 attempts per task
cub ledger gc --dry-run                    # Show what would be removed
```

### API Endpoints

Using a unified `/api/entity/{id}` pattern for extensibility:

#### `GET /api/entity/{id}`
Retrieve entity (task, epic) with full ledger data.

#### `PATCH /api/entity/{id}`
Update entity fields (workflow stage, verification status).

```json
{
  "workflow": {
    "stage": "validated"
  },
  "reason": "Passed QA review"
}
```

#### `GET /api/entity/{id}/history`
Retrieve state history for an entity.

#### `POST /api/sync`
Trigger ledger → dashboard DB sync.

### Integration Points

#### `cub run`
- Creates ledger entry on first attempt (OPEN → IN_PROGRESS)
- Writes prompt files with frontmatter
- Updates attempts[] after each execution
- Finalizes entry on task close
- Updates epic aggregates

#### `cub monitor`
- Reads `active-run.json` symlink for current run state
- Displays live progress from run file

#### Dashboard
- Sync ingests ledger files → DB
- User stage changes → `PATCH /api/entity/{id}` → ledger file update
- DB is derived cache; ledger files are source of truth

## Implementation Notes

### Dashboard Sync Changes
- Add `LedgerParser` to sync layer (similar to existing parsers)
- Parse task entries from `.cub/ledger/by-task/*/entry.json`
- Parse epic entries from `.cub/ledger/by-epic/*/entry.json`
- Map ledger `workflow.stage` to dashboard Stage enum

### Bidirectional Sync
- Dashboard writes go through API
- API calls `cub ledger update` internally (or direct file write with locking)
- Append to `state_history` on every stage change
- Trigger incremental DB sync after file update

### File Locking
- Use file locks when writing ledger entries
- Prevent race conditions if multiple processes update

## Open Questions

1. **Retention policy**: How long to keep harness.log files? Options:
   - Time-based (e.g., 90 days)
   - Count-based (e.g., last 5 attempts per task)
   - Size-based (e.g., until ledger exceeds 1GB)

2. **Compression**: Should old attempt logs be gzipped in place?

3. **Partial completion**: If task partially succeeds, how to record?
   - Add `partial: true` flag to outcome?
   - Track subtask-level completion?

## Future Considerations

- Multi-agent support (parallel workers, concurrent attempts)
- External integrations (sync to GitHub issues, Linear)
- Automated verification (CI hooks to update verification status)
- Drift analysis tooling (compare spec to outcome automatically)

---

**Status**: researching
**Last Updated**: 2026-01-24
