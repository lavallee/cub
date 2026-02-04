# Orient Report: Unified Tracking Model

**Date:** 2026-01-24
**Orient Depth:** Standard
**Status:** Approved
**Spec:** `specs/researching/unified-tracking-model.md`

---

## Executive Summary

Consolidate cub's tracking systems into a unified model centered on the **ledger** as the permanent record of work. The ledger extends the task lifecycle beyond the task backend (beads)—tracking work from first development attempt through review, validation, and release.

## Problem Statement

Cub currently has fragmented tracking: beads handles task state, the dashboard has its own DB, and there's no persistent record of development attempts, costs, or workflow progression. Users lack visibility into how tasks were completed (attempts, escalations, model usage) and cannot track work through post-development stages (review, validation, release).

## Refined Vision

Build a ledger-centric tracking system where:
- **Run sessions** track active cub executions
- **Task ledger entries** record the complete development history of each task
- **Epic ledger entries** aggregate task data for project-level visibility
- **Dashboard** syncs from ledger files as the derived cache
- **CLI commands** provide query and update capabilities

The ledger files are the source of truth; everything else can be reconstructed from them.

## Requirements

### P0 - Must Have

| ID | Requirement | Rationale |
|----|-------------|-----------|
| P0.1 | Run session tracking (`.cub/run-sessions/`, `active-run.json` symlink) | Know what's currently running, detect orphaned runs |
| P0.2 | Task ledger creation on task start | Begin tracking immediately when work begins |
| P0.3 | Prompt file writing with frontmatter (`NNN-prompt.md`) | Preserve exact context sent to harness |
| P0.4 | Attempt tracking (append to `attempts[]` after each execution) | Record all tries, costs, outcomes |
| P0.5 | Task ledger finalization on close (outcome, task_changed, stage) | Complete the development record |
| P0.6 | `cub ledger show <id>` command | Basic ledger inspection |

### P1 - Should Have

| ID | Requirement | Rationale |
|----|-------------|-----------|
| P1.1 | Epic ledger entries with aggregates | Project-level cost/progress visibility |
| P1.2 | Lineage tracking (spec_file, plan_file, epic_id) | Trace work back to its origin |
| P1.3 | `cub ledger stats` command | Aggregate analysis (cost, attempts, escalation rate) |
| P1.4 | `cub ledger search` command | Find tasks by stage, escalation, drift, cost |
| P1.5 | Dashboard LedgerParser integration | Sync ledger → dashboard DB |
| P1.6 | Index file (`index.jsonl`) maintenance | Fast lookups without full directory scan |

### P2 - Nice to Have

| ID | Requirement | Rationale |
|----|-------------|-----------|
| P2.1 | `cub ledger update <id>` for manual stage transitions | Human workflow progression |
| P2.2 | `cub ledger export` (CSV/JSON) | External analysis, reporting |
| P2.3 | `cub ledger gc` stub | Placeholder for future retention policy |
| P2.4 | Bidirectional dashboard sync (UI → API → ledger) | Enable dashboard-driven workflow |
| P2.5 | Verification tracking (tests, typecheck, lint status) | Quality gate recording |

## Constraints

| Constraint | Impact |
|------------|--------|
| Single-writer assumption | No parallel `cub run` support; simplifies file locking |
| Local dashboard only | No authentication required for API |
| Python 3.10+ | Can use modern language features |
| Existing dashboard architecture | Must integrate with current sync/parser pattern |

## Assumptions

1. **Clean break from old ledger**: Existing `.cub/ledger/` content will be ignored/deleted; no migration needed
2. **All stage transitions valid**: Workflow can move forward or backward (with reason recorded in state_history)
3. **Harness logs are raw**: `NNN-harness.log` captures unprocessed stdout/stderr
4. **Missing token data is acceptable**: If harness doesn't report tokens, record as null/0
5. **Epic auto-creation**: If task references non-existent epic ledger, create it automatically
6. **Index is rebuildable**: If `index.jsonl` corrupts, regenerate from `by-task/` and `by-epic/` directories

## Open Questions / Experiments

| Unknown | Resolution |
|---------|------------|
| Retention policy for harness logs | Punt for now; likely becomes part of release process |
| Compression of old logs | Punt for now; storage is cheap |
| Partial task completion | Use `partial: true` flag in outcome |
| `task_changed` detection | Compare task at capture time vs close time (did understanding shift during work) |

## Out of Scope

- Multi-agent/parallel execution handling
- External integrations (GitHub issues, Linear, Jira)
- Automated verification/CI integration
- Backward compatibility with existing ledger format
- Retention policy implementation (deferred)
- Log compression (deferred)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Schema evolution | High - breaking changes to entry.json | Version field in schema; add migration tooling when needed |
| Large harness logs | Medium - disk usage growth | Future `gc` command; retention policy at release time |
| Dashboard sync performance | Medium - many ledger files | Index file for fast lookups; incremental sync |
| File locking edge cases | Low - concurrent access | Single-writer assumption; standard Python locking |

## MVP Definition

The smallest useful implementation:

1. **Run session tracking** works (create, symlink, orphan detection)
2. **Task ledger entries** are created and finalized during `cub run`
3. **`cub ledger show`** displays a task's complete development history
4. **Dashboard syncs** ledger data for visualization

This provides immediate value: users can see exactly how each task was completed, including all attempts, costs, and escalations.

---

**Next Step:** Run `cub architect` to proceed to technical design.
