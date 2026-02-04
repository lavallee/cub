# Orient Report: Ledger Consolidation & Unified ID System

**Date:** 2026-02-04
**Orient Depth:** Standard
**Status:** Approved
**Spec:** specs/planned/cub-048-ledger-consolidation-and-id-system.md

---

## Executive Summary

Cub has accumulated redundant storage directories (`runs/`, `run-sessions/`, `logs/`), collision-prone random IDs, and no traceability from specs to tasks. This spec consolidates storage into a single canonical ledger and introduces a hierarchical ID system tracked via the sync branch to enable full traceability and collision-free numbering across branches and worktrees.

## Problem Statement

**Who has this problem:** Developers using cub for autonomous coding sessions.

**The problem:**
- Redundant storage locations make it unclear where artifacts live
- Random-suffix IDs (e.g., `cub-a1f`) can collide across parallel worktrees
- No traceability chain from task → epic → plan → spec
- Ledger artifacts often left uncommitted, requiring safety-net cleanup
- Epic entries capture ID instead of title

## Refined Vision

Implement a unified storage and ID system that:
1. Uses hierarchical IDs: `cub-054` (spec) → `cub-054A` (plan) → `cub-054A-0` (epic) → `cub-054A-0.1` (task)
2. Tracks counters on sync branch with pre-push collision handling
3. Consolidates all artifacts into `.cub/ledger/`
4. Ensures ledger entries are committed alongside code changes
5. Extends hooks infrastructure with lifecycle events
6. Adds commands for release management, retrospectives, and knowledge extraction

## Requirements

### P0 - Must Have

| # | Requirement | Rationale |
|---|-------------|-----------|
| 1 | **Hierarchical ID System** | Enable traceability: spec(number) → plan(spec+letter) → epic(plan+char) → task(epic.number) |
| 2 | **Counter Tracking on Sync Branch** | `.cub/counters.json` with pre-push hook for collision detection/resolution |
| 3 | **Unified Ledger Structure** | Single `ledger/` with `by-task/`, `by-epic/`, `by-plan/`, `by-run/` subdirectories |
| 4 | **Eliminate Redundant Storage** | Remove `runs/`, `run-sessions/`, `logs/` directories |
| 5 | **JSONL Harness Logs** | Convert harness logs from plaintext to JSONL for structured queries |
| 6 | **`cub run --plan`** | Collapse `build-plan` into run command; remove `build-plan` entirely |
| 7 | **Ledger Committed with Code** | Artifacts committed as part of task/epic workflow, not cleanup afterward |
| 8 | **Epic Title Fix** | Capture actual title instead of ID in `by-epic/` entries |

### P1 - Should Have

| # | Requirement | Rationale |
|---|-------------|-----------|
| 9 | **Lifecycle Hooks** | Extend hooks infrastructure with end-of-task, end-of-epic, end-of-plan, pre-session events with appropriate context |
| 10 | **`cub release`** | Mark tasks/epics as released, update CHANGELOG, git tag, move specs to released/ |
| 11 | **`cub retro`** | Generate retrospective report for completed plan/epic, extract lessons learned |
| 12 | **`cub learn extract`** | Extract knowledge from ledger into guardrails.md and CLAUDE.md |
| 13 | **`cub verify`** | Verify task completion (tests pass), ledger consistency, ID integrity |
| 14 | **`cub sync agent`** | Manually sync managed sections in agent.md across worktrees/branches |
| 15 | **Managed Sections** | Injectable sections in agent.md with manual trigger via `cub sync agent` |
| 16 | **Consistency Checks** | Fast checks in `cub run` and `cub doctor` for ledger/ID integrity |
| 17 | **Flatten Attempts** | Artifacts numbered at task level (e.g., `001-prompt.md`), no `attempts/` subdirectory |

### P2 - Nice to Have

| # | Requirement | Rationale |
|---|-------------|-----------|
| 18 | **Archive/Compress Old Logs** | Future optimization if storage becomes an issue; start with "keep forever" |

## Constraints

| Constraint | Impact |
|------------|--------|
| Extend existing hooks infrastructure | New lifecycle hooks must follow established patterns in `.cub/hooks/` |
| Sync branch mechanism required | Counter allocation depends on sync branch being available |
| JSONL as canonical format | All structured data uses JSONL for consistency with task backend |
| Pre-push hook for collision handling | Requires git hooks installed via `cub init` |

## Assumptions

| Assumption | Risk if Wrong |
|------------|---------------|
| Existing ledger entries can be discarded | N/A - confirmed acceptable |
| Migration script already handled | N/A - confirmed complete |
| Pre-push hook is sufficient for collision handling | Could miss collisions if users bypass hooks; low risk at current scale |
| Single project scope | Multi-project ID namespacing deferred to future |

## Open Questions / Experiments

| Unknown | Experiment |
|---------|------------|
| Optimal harness log retention policy | Start with "keep forever"; add archival if storage becomes issue |
| Best format for managed sections | Current format works; adjust based on usage feedback |

## Out of Scope

- Building the knowledge graph / self-improving agent (separate spec: cub-033)
- Migrating external task systems (Jira, Linear, etc.)
- Multi-project knowledge sharing
- Real-time collaboration features
- Cross-project ID namespacing

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| ID collision during parallel worktree work | M | Pre-push hook checks sync branch, re-allocates if needed |
| Breaking existing workflows | M | Remove `build-plan` cleanly; `cub run --plan` is direct replacement |
| Hook context insufficient for user needs | L | Design hooks with rich context; iterate based on feedback |
| Storage growth from JSONL logs | L | Keep forever initially; add archival if needed |

## MVP Definition

**Full scope is the target.** This is internal tooling improvement where partial implementation creates inconsistency. The phases in the spec (Migration → ID System → Ledger Consolidation → Commands/Hooks → Agent Instructions) represent the implementation order, not MVP cutoffs.

## ID Hierarchy Reference

```
Spec:       {project_id}-{number:03d}     → cub-054
Plan:       {spec_id}{LETTER}             → cub-054A
Epic:       {plan_id}-{char}              → cub-054A-0
Task:       {epic_id}.{number}            → cub-054A-0.1
Standalone: {project_id}-s{number:03d}    → cub-s017
```

**Visual Distinction:**
- Specs end with **numbers** (054)
- Plans add **uppercase letter** (054A, 054B)
- Epics add **hyphen + number/lowercase** (054A-0, 054A-a)
- Tasks add **dot + number** (054A-0.1)

## Ledger Structure Reference

```
.cub/ledger/
├── index.jsonl                    # Quick-lookup index
├── by-task/{task_id}.json         # Task completion record
├── by-task/{task_id}/
│   ├── 001-prompt.md              # Prompt sent to harness
│   └── 001-harness.jsonl          # Harness log (JSONL)
├── by-epic/{epic_id}/entry.json   # Epic summary
├── by-plan/{plan_id}/entry.json   # Plan summary
└── by-run/{run_id}.json           # Run session record
```

## New Commands Reference

| Command | Purpose |
|---------|---------|
| `cub release` | Mark tasks/epics as released, update CHANGELOG, git tag, move specs |
| `cub retro` | Generate retrospective for completed plan/epic, extract lessons |
| `cub learn extract` | Extract knowledge from ledger into guardrails/CLAUDE.md |
| `cub verify` | Verify task completion, ledger consistency, ID integrity |
| `cub sync agent` | Sync managed sections in agent.md |
| `cub run --plan` | Execute plan (replaces `build-plan`) |

## Lifecycle Hooks Reference

| Hook | Trigger | Context Provided |
|------|---------|------------------|
| `pre-session` | Before harness session starts | Task data, epic context, plan context |
| `end-of-task` | After task completion | Task result, files changed, cost/tokens |
| `end-of-epic` | After all epic tasks complete | Epic summary, task list, total cost |
| `end-of-plan` | After all plan epics complete | Plan summary, epic list, total cost |

---

**Next Step:** Run `/cub:architect` to proceed to technical design.
