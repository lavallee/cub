# Implementation Plan: Cub 0.21-0.25

**Date:** 2026-01-14
**Granularity:** Standard (1-2 hour tasks)
**Total:** 5 epics, 34 tasks

---

## Summary

This plan breaks down the Cub 0.21-0.25 release sequence into executable tasks organized by epic (release). The work transforms cub from a Bash-based CLI to a full Python CLI using modern tooling (Typer, Pydantic, Rich).

**Key milestones:**
1. **0.21 Python Core** - Foundation migration (16 tasks)
2. **0.22 Codebase Health Audit** - Quality tooling (5 tasks)
3. **0.23 Live Dashboard** - Real-time visibility (4 tasks)
4. **0.24 Worktrees** - Parallel development (4 tasks)
5. **0.25 Sandbox Mode** - Safe autonomous execution (5 tasks)

**Deferred:** OpenCode and Gemini harness implementations (can add later via same pattern).

---

## Task Hierarchy

### Epic 1: v0.21 Python Core Migration [P0] `cub-E01`

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-001 | Initialize Python project with uv | haiku | P0 | - | 1h |
| cub-002 | Create Task and Config Pydantic models | sonnet | P0 | cub-001 | 1.5h |
| cub-003 | Implement TaskBackend protocol and registry | sonnet | P0 | cub-002 | 1h |
| cub-004 | Implement BeadsBackend for task management | sonnet | P0 | cub-003 | 2h |
| cub-005 | Implement JsonBackend for task management | sonnet | P0 | cub-003 | 1.5h |
| cub-006 | Implement config loader with multi-layer merging | sonnet | P0 | cub-002 | 1.5h |
| cub-007 | Implement HarnessBackend protocol and registry | sonnet | P0 | cub-001 | 1h |
| cub-008 | Implement Claude harness backend | sonnet | P0 | cub-007 | 2h |
| cub-009 | Implement Codex harness backend | sonnet | P0 | cub-007 | 1.5h |
| cub-010 | Create Typer CLI structure with core commands | sonnet | P0 | cub-001 | 1.5h |
| cub-011 | Implement cub run command with main loop | opus | P0 | cub-004, cub-005, cub-006, cub-008, cub-010 | 2h |
| cub-012 | Implement cub status command | haiku | P1 | cub-004, cub-005, cub-010 | 1h |
| cub-013 | Implement hook execution from Python | sonnet | P1 | cub-001 | 1h |
| cub-014 | Implement structured JSONL logging | haiku | P1 | cub-001 | 1h |
| cub-015 | Add pytest test suite for core modules | sonnet | P1 | cub-004, cub-005, cub-006, cub-008 | 2h |
| cub-016 | Update installation and migration docs | haiku | P2 | cub-011 | 1h |

**Phase 1 Total:** ~21 hours

---

### Epic 2: v0.22 Codebase Health Audit [P1] `cub-E02`

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-017 | Implement dead code detection for Python | sonnet | P1 | cub-E01 | 2h |
| cub-018 | Implement dead code detection for Bash | sonnet | P1 | cub-017 | 1.5h |
| cub-019 | Implement documentation validation | sonnet | P1 | cub-E01 | 1.5h |
| cub-020 | Implement test coverage reporting | haiku | P1 | cub-015 | 1h |
| cub-021 | Implement cub audit command | sonnet | P1 | cub-017, cub-018, cub-019, cub-020 | 1.5h |

**Phase 2 Total:** ~7.5 hours

---

### Epic 3: v0.23 Live Dashboard [P1] `cub-E03`

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-022 | Implement Rich-based dashboard renderer | sonnet | P1 | cub-E01 | 2h |
| cub-023 | Implement status file polling | haiku | P1 | cub-022 | 1h |
| cub-024 | Implement tmux integration for --monitor | sonnet | P1 | cub-022, cub-023 | 1.5h |
| cub-025 | Implement cub monitor command | haiku | P1 | cub-022, cub-023 | 1h |

**Phase 3 Total:** ~5.5 hours

---

### Epic 4: v0.24 Git Worktrees [P1] `cub-E04`

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-026 | Implement WorktreeManager class | sonnet | P1 | cub-E01 | 2h |
| cub-027 | Add --worktree flag to cub run | sonnet | P1 | cub-026 | 1.5h |
| cub-028 | Implement --parallel N for concurrent tasks | opus | P1 | cub-027 | 2h |
| cub-029 | Implement cub worktree subcommands | haiku | P2 | cub-026 | 1h |

**Phase 4 Total:** ~6.5 hours

---

### Epic 5: v0.25 Sandbox Mode [P1] `cub-E05`

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-030 | Implement SandboxProvider protocol and registry | sonnet | P1 | cub-E01 | 1.5h |
| cub-031 | Implement DockerProvider for sandbox | opus | P1 | cub-030 | 2h |
| cub-032 | Add --sandbox flag to cub run | sonnet | P1 | cub-031 | 1.5h |
| cub-033 | Implement cub sandbox subcommands | sonnet | P1 | cub-031 | 1.5h |
| cub-034 | Create Docker image for cub sandbox | haiku | P2 | cub-016 | 1h |

**Phase 5 Total:** ~7.5 hours

---

## Dependency Graph

```
cub-001 (setup)
  ├─> cub-002 (models)
  │     ├─> cub-003 (task protocol)
  │     │     ├─> cub-004 (beads backend)
  │     │     └─> cub-005 (json backend)
  │     └─> cub-006 (config)
  ├─> cub-007 (harness protocol)
  │     ├─> cub-008 (claude)
  │     └─> cub-009 (codex)
  ├─> cub-010 (cli)
  ├─> cub-013 (hooks)
  └─> cub-014 (logging)

cub-004 + cub-005 + cub-006 + cub-008 + cub-010
  └─> cub-011 (run command) ─────────────────────┐
        └─> cub-016 (docs)                        │
              └─> cub-034 (docker image)          │
                                                  │
cub-004 + cub-005 + cub-010 ──> cub-012 (status)  │
                                                  │
cub-004 + cub-005 + cub-006 + cub-008             │
  └─> cub-015 (tests)                             │
        └─> cub-020 (coverage)                    │
                                                  │
[0.21 Complete] ──────────────────────────────────┤
  ├─> cub-017 (python dead code)                  │
  │     └─> cub-018 (bash dead code)              │
  ├─> cub-019 (docs validation)                   │
  │                                               │
  │   cub-017 + cub-018 + cub-019 + cub-020       │
  │     └─> cub-021 (audit command)               │
  │                                               │
  ├─> cub-022 (dashboard renderer)                │
  │     └─> cub-023 (status polling)              │
  │           ├─> cub-024 (tmux)                  │
  │           └─> cub-025 (monitor cmd)           │
  │                                               │
  ├─> cub-026 (worktree manager)                  │
  │     ├─> cub-027 (--worktree flag)             │
  │     │     └─> cub-028 (--parallel N)          │
  │     └─> cub-029 (worktree cmds)               │
  │                                               │
  └─> cub-030 (sandbox protocol)                  │
        └─> cub-031 (docker provider)             │
              ├─> cub-032 (--sandbox flag)        │
              └─> cub-033 (sandbox cmds)          │
```

---

## Model Distribution

| Model | Tasks | Rationale |
|-------|-------|-----------|
| **opus** | 3 | Complex: main loop, parallel execution, Docker provider |
| **sonnet** | 23 | Standard implementation: protocols, backends, CLI commands |
| **haiku** | 8 | Boilerplate: project setup, simple commands, docs |

---

## Validation Checkpoints

### Checkpoint 1: Python Foundation (after cub-011)

**What's testable:** Core cub functionality works in Python
- `cub run --once` executes a task
- Task selection from beads/JSON works
- Claude harness invocation works
- Config loading with correct precedence

**Key questions:**
- Is Python startup latency acceptable?
- Does task selection match Bash behavior?
- Are harness invocations correct?

---

### Checkpoint 2: Quality Tooling (after cub-021)

**What's testable:** Audit reports useful information
- `cub audit` produces actionable findings
- Dead code detection works on cub itself
- Documentation validation catches real issues

**Key questions:**
- Are false positives acceptable?
- Is the report format actionable?

---

### Checkpoint 3: Real-time Visibility (after cub-025)

**What's testable:** Can monitor overnight runs
- `cub run --monitor` shows live progress
- Dashboard updates in real-time
- Can attach to running session

**Key questions:**
- Is 1s refresh sufficient?
- Does tmux integration work reliably?

---

### Checkpoint 4: Parallel Execution (after cub-028)

**What's testable:** Can process multiple tasks concurrently
- `cub run --parallel 3` works
- Tasks isolated in worktrees
- Results merge correctly

**Key questions:**
- What's the optimal parallel count?
- How do we handle failures in parallel?

---

### Checkpoint 5: Safe Autonomy (after cub-033)

**What's testable:** Can run overnight with confidence
- `cub run --sandbox` isolates execution
- Changes reviewable before applying
- Cleanup works correctly

**Key questions:**
- Is Docker isolation sufficient?
- Is the apply workflow intuitive?

---

## Ready to Start

These tasks have no blockers and can begin immediately:

- **cub-001**: Initialize Python project with uv [P0] (haiku) - 1h

After cub-001 completes, these become ready:
- cub-002: Create Task and Config Pydantic models
- cub-007: Implement HarnessBackend protocol
- cub-010: Create Typer CLI structure
- cub-013: Implement hook execution
- cub-014: Implement structured logging

---

## Critical Path

The minimum path to a working Python CLI:

```
cub-001 → cub-002 → cub-003 → cub-004 → cub-011
    ↘         ↘
     cub-007 → cub-008 ↗
          ↘
           cub-010 ↗
```

**Critical path duration:** ~10 hours

---

## Total Effort Summary

| Phase | Epic | Tasks | Hours |
|-------|------|-------|-------|
| 1 | v0.21 Python Core | 16 | ~21h |
| 2 | v0.22 Codebase Audit | 5 | ~7.5h |
| 3 | v0.23 Live Dashboard | 4 | ~5.5h |
| 4 | v0.24 Worktrees | 4 | ~6.5h |
| 5 | v0.25 Sandbox | 5 | ~7.5h |
| **Total** | | **34** | **~48h** |

---

**Next Step:** Run `cub bootstrap` to import these tasks into beads and start development.
