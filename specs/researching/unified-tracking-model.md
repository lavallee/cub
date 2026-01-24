# Unified Tracking Model

**Status**: Researching
**Created**: 2026-01-24

## Overview

This spec consolidates cub's tracking systems into a unified model centered on the **ledger** as the permanent record of work. It eliminates the distinction between "runs" as a separate artifact tier and instead treats runs as execution contexts that produce ledger entries.

## Core Principle

> The ledger is the single source of truth for completed work. Everything else is either ephemeral (active execution) or derived (dashboards, reports).

## The Three Artifacts

### 1. Active Run (`.cub/active-run.json`)

The current execution context. Persists across sessions for continuity.

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
  "status": "running"
}
```

**Lifecycle:**
- Created when `cub run` starts
- Updated during execution
- Marked `status: "completed"` when done (not deleted)
- New run creates new file (or overwrites? TBD)

**Purpose:**
- Live monitoring during execution
- Session continuity if interrupted
- Historical record of run sessions

### 2. Ledger Entry (`.cub/ledger/by-task/{task-id}/`)

The permanent record of a task's lifecycle from claim to completion.

```
.cub/ledger/by-task/{task-id}/
├── entry.json           # The structured record
└── attempts/
    ├── 001-prompt.md    # What we asked (attempt 1)
    ├── 001-harness.log  # What it did (attempt 1)
    ├── 002-prompt.md    # Retry prompt (attempt 2)
    └── 002-harness.log  # Retry output (attempt 2)
```

#### entry.json Structure

```json
{
  "id": "cub-abc",
  "version": 1,

  "task": {
    "title": "Fix the login bug",
    "description": "Users report 500 error when clicking login with empty password field. Should show validation error instead.",
    "type": "bug",
    "priority": 1,
    "labels": ["auth", "urgent"],
    "epic_id": "cub-xyz",
    "spec_file": "specs/planned/auth-fixes.md",
    "created_at": "2026-01-20T10:00:00",
    "captured_at": "2026-01-24T12:35:00"
  },

  "task_changed": {
    "detected_at": "2026-01-24T14:00:00",
    "fields_changed": ["description", "labels"],
    "original_description": "Users report 500 error when clicking login with empty password field. Should show validation error instead.",
    "final_description": "Users report 500 error when clicking login with empty password field. Should show validation error instead. Also handle null email.",
    "notes": "Scope expanded during implementation"
  },

  "attempts": [
    {
      "attempt_number": 1,
      "run_id": "cub-20260124-123456",
      "started_at": "2026-01-24T12:35:00",
      "completed_at": "2026-01-24T12:40:00",
      "model": "haiku",
      "success": false,
      "error_category": "test_failure",
      "error_summary": "test_login_empty_password failed - expected 400, got 500",
      "tokens": {
        "input": 1000,
        "output": 500,
        "cache_read": 5000,
        "cache_write": 200
      },
      "cost_usd": 0.02,
      "duration_seconds": 300
    },
    {
      "attempt_number": 2,
      "run_id": "cub-20260124-123456",
      "started_at": "2026-01-24T12:41:00",
      "completed_at": "2026-01-24T12:50:00",
      "model": "sonnet",
      "success": true,
      "tokens": {
        "input": 1200,
        "output": 800,
        "cache_read": 5500,
        "cache_write": 100
      },
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

    "files_changed": [
      "src/auth/login.py",
      "tests/test_login.py"
    ],
    "commits": [
      {
        "hash": "abc123f",
        "message": "fix: validate password before auth check",
        "timestamp": "2026-01-24T12:49:00"
      }
    ],

    "approach": "Added early validation in login handler to check for empty password before attempting authentication. Returns 400 with clear error message.",
    "decisions": [
      "Used built-in validator instead of custom regex",
      "Added rate limiting as defensive measure"
    ],
    "lessons_learned": [
      "Auth endpoints should validate all inputs before any business logic"
    ],

    "drift": {
      "additions": ["Rate limiting added (not in original spec)"],
      "omissions": [],
      "severity": "minor"
    }
  },

  "verification": {
    "status": "pass",
    "checked_at": "2026-01-24T12:51:00",
    "tests_passed": true,
    "typecheck_passed": true,
    "lint_passed": true,
    "notes": []
  },

  "workflow_stage": "validated",
  "workflow_stage_updated_at": "2026-01-24T15:00:00"
}
```

### 3. Ledger Index (`.cub/ledger/index.jsonl`)

Quick-lookup index for queries. One line per task.

```jsonl
{"id":"cub-abc","title":"Fix the login bug","type":"bug","epic":"cub-xyz","completed":"2026-01-24","cost":0.17,"attempts":2,"model":"sonnet","escalated":true,"status":"pass","stage":"validated"}
{"id":"cub-def","title":"Add rate limiting","type":"feature","epic":"cub-xyz","completed":"2026-01-24","cost":0.08,"attempts":1,"model":"haiku","escalated":false,"status":"pass","stage":"complete"}
```

## Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TASK LIFECYCLE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Task Backend (Beads)              Ledger                                   │
│  ─────────────────────            ────────                                  │
│                                                                             │
│  [open] ──────────────────────────────────────────────────────────────────  │
│     │                                                                       │
│     │  cub claims task                                                      │
│     ▼                                                                       │
│  [in_progress] ───────────────────► Create ledger entry                     │
│     │                               - Copy task.* fields                    │
│     │                               - Set captured_at                       │
│     │                               - attempts = []                         │
│     │                               - outcome = null                        │
│     │                                                                       │
│     │  Attempt 1                                                            │
│     │  ─────────                                                            │
│     │  - Write prompt.md            - Append to attempts[]                  │
│     │  - Execute harness            - Write harness.log                     │
│     │  - Record result              - Update tokens, cost                   │
│     │                                                                       │
│     │  Attempt 2 (if retry)                                                 │
│     │  ────────────────────                                                 │
│     │  - Escalate model?            - Append to attempts[]                  │
│     │  - Write prompt.md            - Write harness.log                     │
│     │  - Execute harness            - Update tokens, cost                   │
│     │                                                                       │
│     │  Task succeeds                                                        │
│     ▼                                                                       │
│  [closed] ────────────────────────► Finalize ledger entry                   │
│                                     - Re-fetch task from backend            │
│                                     - Compare to captured task.*            │
│                                     - Populate task_changed if different    │
│                                     - Populate outcome.*                    │
│                                     - Run verification                      │
│                                     - Update index.jsonl                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Use Cases Enabled

### 1. Auditing & Debugging

**Question**: "Why did task X fail initially?"

**Answer**: Read `attempts[0]` in ledger entry, examine `001-harness.log`

```bash
cub ledger show cub-abc --attempt 1
# Shows: prompt, harness output, error category, tokens used
```

### 2. Cost-Benefit Analysis

**Question**: "How much did epic Y cost?"

**Answer**: Aggregate `outcome.total_cost_usd` for all tasks with `task.epic_id == Y`

```bash
cub ledger stats --epic cub-xyz
# Epic: cub-xyz (Auth Improvements)
# Tasks: 8 completed
# Total Cost: $4.23
# Total Tokens: 234,567
# Avg Cost/Task: $0.53
```

### 3. Model Effectiveness

**Question**: "How often does haiku succeed vs need escalation?"

**Answer**: Analyze `outcome.escalated` and `outcome.escalation_path` across ledger

```bash
cub ledger stats --model-analysis
# Model Performance:
#   haiku:  67% first-try success, avg $0.03/task
#   sonnet: 89% first-try success, avg $0.18/task
#   opus:   95% first-try success, avg $0.45/task
# Escalations: 23% of tasks (haiku→sonnet most common)
```

### 4. Drift Detection

**Question**: "Did we build what was specified?"

**Answer**: Compare `task.description` + `task.spec_file` to `outcome.drift`

```bash
cub ledger drift --epic cub-xyz
# Epic: cub-xyz
# Drift Analysis:
#   cub-abc: minor (added rate limiting)
#   cub-def: none
#   cub-ghi: significant (skipped caching requirement)
```

### 5. Task Definition Changes

**Question**: "Did requirements change during implementation?"

**Answer**: Check `task_changed` field

```bash
cub ledger show cub-abc --changes
# Task definition changed during implementation:
#   description: Added "Also handle null email"
#   labels: Added "scope-creep"
# Captured at: 2026-01-24T12:35:00
# Changed detected at: 2026-01-24T14:00:00
```

### 6. Evaluation / QA

**Question**: "Did the agent actually complete the task correctly?"

**Answer**: Human or automated review comparing:
- `task.description` (what was asked)
- `outcome.approach` (what was done)
- `outcome.drift` (what differed)
- `verification.*` (did it pass checks)

## Dashboard Integration

The dashboard synthesizes from ledger for visualization:

| Column | Data Source |
|--------|-------------|
| READY | Beads (open, unblocked tasks) |
| IN_PROGRESS | Beads (in_progress) + ledger (has entry, no outcome) |
| NEEDS_REVIEW | Ledger (outcome.success, verification.status == pending) |
| COMPLETE | Ledger (verification.status == pass, workflow_stage == null) |
| VALIDATED | Ledger (workflow_stage == validated) |
| RELEASED | Ledger (workflow_stage == released) + CHANGELOG |

**New dashboard capabilities:**
- Cost per column (sum of visible tasks)
- Model badges (which model completed each)
- Escalation indicators (tasks that needed retry)
- Drift warnings (tasks with significant drift)

## Migration Path

### Phase 1: Extend Current Ledger
- Add `task` section with backend info at claim time
- Add `task_changed` detection at close time
- Keep existing `tokens`, `cost_usd` fields (map to `outcome`)

### Phase 2: Add Attempts Tracking
- Change from single result to `attempts[]` array
- Store harness.log per attempt
- Track escalation path

### Phase 3: Deprecate Runs Directory
- Stop writing to `.cub/runs/{run-id}/tasks/`
- Keep `active-run.json` for session state
- Migrate any run-specific queries to ledger

### Phase 4: Archive Runs History
- Keep `.cub/runs/` for historical runs (read-only)
- New runs only write to ledger
- Eventually prune old runs directory

## Open Questions

1. **Retention policy**: How long to keep harness.log files? Per-task or time-based?

2. **Compression**: Should old attempt logs be compressed/archived?

3. **Active run history**: Keep all `active-run.json` versions or just current?

4. **Partial completion**: If task partially succeeds (some subtasks done), how to record?

5. **Multi-agent**: If parallel workers, how to handle concurrent attempts?

## Related Specs

- `specs/researching/knowledge-retention-system.md` - Original three-layer model
- `specs/researching/run-tracking-system.md` - Run artifacts (being superseded)
- `specs/completed/live-dashboard.md` - Dashboard design
- `specs/completed/guardrails-system.md` - Lessons learned capture

## Summary

This model:
- **Simplifies** by making ledger the single permanent record
- **Enriches** by capturing task intent at claim time
- **Enables** drift detection by comparing intent to outcome
- **Tracks** model effectiveness through attempts array
- **Preserves** debugging capability through per-attempt logs
- **Supports** all identified use cases with queryable structure
