# Triage Report: Cub Releases 0.21-0.25

**Date:** 2026-01-14
**Triage Depth:** Deep
**Status:** Approved

---

## Executive Summary

Plan releases 0.21-0.25 for Cub, focusing on migrating performance-critical Bash code to Python (not Go initially), adding visibility via a live dashboard, enabling parallel development with git worktrees, and providing safe autonomous execution via Docker-based sandboxing. The goal is to establish the technical foundation that enables confident overnight autonomous operation.

## Problem Statement

Cub is currently ~9,400 lines of Bash with significant jq subprocess overhead (~10-50ms per JSON operation). This limits performance, maintainability, and the ability to add advanced features like parallel execution and real-time dashboards. Users need confidence to run cub autonomously overnight, which requires visibility (dashboard) and safety (sandbox).

## Refined Vision

Deliver five releases that transform cub from a Bash-only tool to a Python-powered platform capable of:
1. Fast task/config operations without jq subprocess overhead
2. Real-time visibility into autonomous runs
3. Parallel development via git worktrees
4. Safe "set and forget" execution via Docker sandboxing

---

## Requirements

### P0 - Must Have

- **Python Core (0.21):** Migrate tasks, config, and harness layers to Python
  - Eliminates jq subprocess overhead (10-50x performance improvement expected)
  - Python chosen over Go for flexibility, library ecosystem, and developer familiarity
  - Harness layer in Python enables easier prompt iteration

- **Status file generation:** Main loop must write `status.json` for dashboard consumption
  - Prerequisite for dashboard feature
  - Include: current task, iteration count, budget usage, recent events

- **Docker sandbox provider:** Isolated execution environment
  - Full filesystem isolation (copy of project)
  - Network isolation option
  - Resource limits (memory, CPU)
  - Real-time log streaming

### P1 - Should Have

- **Live Dashboard (0.23):** tmux-based real-time monitoring
  - Show current task, iteration count, budget usage
  - Recent activity log
  - Rate limit countdown

- **Worktrees (0.24):** Parallel development support
  - `--worktree` flag for isolated execution
  - `--parallel N` for auto-parallel independent tasks
  - One worktree per task/epic

- **Codebase Health Audit (0.22):** Formalized audit tooling
  - Dead code detection (multi-language aware)
  - Documentation freshness checks
  - Test coverage analysis
  - Post-migration verification

### P2 - Nice to Have

- **Pluggable sandbox provider interface:** Design for future providers (Sprites, Firecracker)
  - Provider abstraction layer
  - Capability detection
  - Don't implement Sprites yet, just design for it

- **Pre-warming:** Reduce sandbox startup latency
  - Prepare sandbox while user types command
  - Cache warmed containers

- **Snapshots:** Save/restore sandbox state (defer to future provider)

---

## Constraints

- **Solo developer:** Scope must be realistic for one person
- **No backward compatibility needed:** Only user is the developer
- **Modern Bash acceptable:** Can require Bash 5.x via Homebrew if needed, but likely moot after Python migration
- **Docker required for sandbox:** Sprites and other providers deferred

---

## Assumptions

- **Python performance is sufficient:** For tasks/config/harness, Python's ~50-100ms startup is acceptable vs Bash's jq overhead
- **tmux available:** Dashboard assumes tmux is installed (graceful fallback if not)
- **Git worktrees mature:** Feature has been stable since Git 2.5 (2015)
- **Docker available:** Sandbox feature requires Docker (common in dev environments)

---

## Open Questions / Experiments

- **CLI integration model:** TBD whether Python becomes the primary CLI or stays as libraries called by Bash
  - → Experiment: Assess bottom-up after migration - if majority of commands move to Python, Python should drive CLI

- **Go usage:** Reserved for cases where Python isn't fast enough
  - → Experiment: Profile post-migration to identify any hotspots requiring Go

- **Parallel task limit:** Optimal value for `--parallel N`
  - → Experiment: Test with 2, 3, 4 parallel tasks; measure context switching overhead

---

## Out of Scope

- **Sprites.dev provider:** Noted in spec, not implemented in 0.25. Design interface only.
- **Web dashboard:** tmux-based only. Web alternative is future enhancement.
- **Multi-model review:** Dependent on Implementation Review feature (post-0.25)
- **Go migration:** Reserved for future if Python proves insufficient

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Python startup latency | M | Measure early; cub is not latency-critical like a keyboard handler |
| Dashboard polling overhead | L | 1-second refresh interval; status.json is small |
| Worktree management complexity | M | Clear naming conventions; `cub worktree list` command |
| Docker not available on some systems | M | Clear error messaging; sandbox is opt-in |
| Harness streaming in Python | M | Use subprocess with line-buffered output; well-understood pattern |

---

## MVP Definition

**Minimum viable 0.21-0.25 sequence:**

1. **0.21 Python Core:** Tasks + Config + Harness in Python. Single release for all jq-heavy code.
2. **0.22 Codebase Health Audit:** Basic dead code detection + test coverage reporting.
3. **0.23 Live Dashboard:** tmux dashboard with status/progress/recent events.
4. **0.24 Worktrees:** `--worktree` flag for isolation + `--parallel N` for concurrent tasks.
5. **0.25 Sandbox:** Docker provider with isolation, resource limits, diff/export/apply workflow.

**Pre-work:** Manual light audit before 0.21 to identify dead code (don't port what you don't need).

---

## Release Details

### 0.21 - Python Core

**Goal:** Eliminate jq subprocess overhead, establish Python foundation.

**Scope:**
- `lib/tasks.sh` → `cub_core/tasks.py` (~937 lines)
- `lib/beads.sh` → `cub_core/beads.py` (~376 lines)
- `lib/config.sh` → `cub_core/config.py`
- `lib/harness.sh` → `cub_core/harness.py` (~1,161 lines)

**Interface:**
- Python modules callable from Bash: `python -m cub_core.tasks list --status open`
- Or Python CLI if enough commands migrate: `cub tasks list --status open`

**Success criteria:**
- Task list operation < 100ms (vs current ~500ms)
- Config access < 20ms (vs current ~50ms)
- All existing tests pass (BATS tests may need updates)

### 0.22 - Codebase Health Audit

**Goal:** Formalize audit tooling for ongoing maintenance.

**Scope:**
- Dead function detection (Bash + Python)
- Unused variable detection
- README validation (code examples, links)
- Test coverage reporting
- JSON + summary output formats

**Command:**
- `cub audit` - Full audit with summary report
- `cub audit --ci` - Exit non-zero if below threshold

### 0.23 - Live Dashboard

**Goal:** Real-time visibility into autonomous runs.

**Scope:**
- Status file writer in main loop (`status.json`)
- tmux dashboard layout
- `cub run --monitor` launches with dashboard
- `cub monitor` attaches to existing run

**Dashboard shows:**
- Current task + iteration count
- Budget usage (tokens, tasks)
- Recent activity (last 10 events)
- Rate limit status

### 0.24 - Worktrees

**Goal:** Enable parallel development with isolated working directories.

**Scope:**
- `--worktree` flag for `cub run`
- `--parallel N` for concurrent independent tasks
- Worktree lifecycle management
- Integration with existing branch-epic binding

**Commands:**
- `cub run --worktree` - Run in dedicated worktree
- `cub run --parallel 3` - Process up to 3 independent tasks concurrently
- `cub worktree list` - Show active worktrees
- `cub worktree clean` - Remove merged worktrees

### 0.25 - Sandbox Mode

**Goal:** Safe autonomous execution for "overnight" confidence.

**Scope:**
- Provider abstraction interface (pluggable)
- Docker provider implementation
- Isolation: filesystem, network (optional), resources
- Workflow: diff → review → apply or discard

**Commands:**
- `cub run --sandbox` - Run in Docker sandbox
- `cub sandbox logs` - Stream logs
- `cub sandbox diff` - View changes
- `cub sandbox apply` - Apply changes to real project
- `cub sandbox clean` - Remove sandbox

---

## Dependency Graph

```
Pre-work (manual)
    │
    ▼
[0.21 Python Core] ──────────────────────────────┐
    │                                             │
    ▼                                             │
[0.22 Codebase Health Audit]                     │
    │                                             │
    ├─────────────────────────────────────────────┤
    │                                             │
    ▼                                             ▼
[0.23 Live Dashboard]                    [0.24 Worktrees]
    │                                             │
    └──────────────┬──────────────────────────────┘
                   │
                   ▼
            [0.25 Sandbox Mode]
```

**Notes:**
- 0.21 Python Core is prerequisite for all others (establishes foundation)
- 0.22 Audit runs post-migration to verify
- 0.23 Dashboard requires status.json (added in 0.21 or 0.23)
- 0.24 Worktrees is independent but benefits from Python core
- 0.25 Sandbox benefits from Dashboard (visibility) and Worktrees (parallel sandboxed runs)

---

## Sources

Research on git worktrees + AI agents:
- [Parallel Workflows: Git Worktrees and AI Agents](https://medium.com/@dennis.somerville/parallel-workflows-git-worktrees-and-the-art-of-managing-multiple-ai-agents-6fa3dc5eec1d)
- [Git Worktrees: Secret Weapon for Parallel AI Agents](https://medium.com/@mabd.dev/git-worktrees-the-secret-weapon-for-running-multiple-ai-coding-agents-in-parallel-e9046451eb96)
- [par - CLI for Parallel Worktree & Session Manager](https://github.com/coplane/par)
- [Addy Osmani - LLM Coding Workflow 2026](https://addyosmani.com/blog/ai-coding-workflow/)

---

**Next Step:** Run `cub architect` to design the technical architecture for this release sequence.
