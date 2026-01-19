# Implementation Plan: Cub Test Coverage Improvement

**Date:** 2026-01-18
**Granularity:** Macro (half-day to full-day tasks)
**Total:** 5 epics, 19 tasks

---

## Summary

This plan implements the layered testing strategy designed in the architecture phase. Work is organized into 5 phases:

1. **Foundation (MVP)** - Establish stability framework, achieve 60% coverage on cli/run.py
2. **Coverage Expansion** - Test remaining critical modules, add contract tests, enable parallel CI
3. **Smart Local Testing** - pytest-testmon for fast local feedback
4. **CI Hardening** - Separate workflows, coverage gates, badges
5. **Refinement** - Property-based testing, Docker integration tests, performance benchmarks

Each phase builds on the previous. Phase 1 delivers immediate value; later phases add polish and advanced features.

---

## Task Hierarchy

### Epic 1: Phase 1 - Foundation [P0]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-001 | Create STABILITY.md with tier definitions | sonnet | P0 | - | 2-4h |
| cub-002 | Update CLAUDE.md to reference STABILITY.md | haiku | P0 | cub-001 | 30m-1h |
| cub-003 | Configure per-file coverage thresholds | sonnet | P0 | cub-001 | 2-3h |
| cub-004 | Write comprehensive tests for cli/run.py | opus | P0 | - | 4-8h |
| cub-005 | Verify CI passes with new thresholds | sonnet | P0 | cub-003, cub-004 | 1-2h |

**Checkpoint: MVP Complete** - After cub-005, the stability framework is live and cli/run.py has 60%+ coverage.

---

### Epic 2: Phase 2 - Coverage Expansion [P1]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-006 | Add tests for core/tasks/service.py | sonnet | P1 | - | 3-4h |
| cub-007 | Add tests for core/pr/service.py | sonnet | P1 | - | 3-4h |
| cub-008 | Add tests for core/harness/codex.py | sonnet | P1 | - | 2-3h |
| cub-009 | Create contract tests for harness CLIs | sonnet | P1 | - | 3-4h |
| cub-010 | Enable parallel test execution (pytest-xdist) | haiku | P1 | cub-006, cub-007, cub-008 | 1-2h |

**Checkpoint: Coverage Expanded** - After cub-010, all critical modules have 60%+ coverage and CI runs in parallel.

---

### Epic 3: Phase 3 - Smart Local Testing [P2]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-011 | Add pytest-testmon for smart test selection | sonnet | P2 | - | 2-3h |
| cub-012 | Create pre-commit hook for affected tests | sonnet | P2 | cub-011 | 2-3h |
| cub-013 | Add make test-fast target | haiku | P2 | cub-011 | 30m-1h |

**Checkpoint: Fast Local Feedback** - After cub-013, developers can run `make test-fast` for quick iteration.

---

### Epic 4: Phase 4 - CI Hardening [P2]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-014 | Split CI workflow into separate jobs | sonnet | P2 | - | 3-4h |
| cub-015 | Add coverage trend gate to CI | sonnet | P2 | cub-014 | 2-3h |
| cub-016 | Add test status badge to README | haiku | P2 | cub-015 | 30m |

**Checkpoint: CI Optimized** - After cub-016, CI is fast for pushes, thorough for PRs, with coverage protection.

---

### Epic 5: Phase 5 - Refinement [P3]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-017 | Add Hypothesis property-based tests | sonnet | P3 | - | 4-6h |
| cub-018 | Add Docker integration tests for sandbox | opus | P3 | - | 4-6h |
| cub-019 | Add performance regression tests | sonnet | P3 | cub-017, cub-018 | 3-4h |

**Checkpoint: Advanced Testing Complete** - After cub-019, the full testing strategy is implemented.

---

## Dependency Graph

```
Phase 1 (Foundation)
├── cub-001 (STABILITY.md)
│   ├── cub-002 (Update CLAUDE.md)
│   └── cub-003 (Coverage thresholds)
│         └── cub-005 (Verify CI) ←── CHECKPOINT: MVP
└── cub-004 (cli/run.py tests) ──┘

Phase 2 (Coverage Expansion)
├── cub-006 (tasks/service tests)
├── cub-007 (pr/service tests)    ├── cub-010 (pytest-xdist) ←── CHECKPOINT
├── cub-008 (codex tests) ────────┘
└── cub-009 (contract tests)

Phase 3 (Smart Local Testing)
└── cub-011 (pytest-testmon)
    ├── cub-012 (pre-commit hook)
    └── cub-013 (make test-fast) ←── CHECKPOINT

Phase 4 (CI Hardening)
└── cub-014 (Split CI jobs)
    └── cub-015 (Coverage gate)
        └── cub-016 (README badge) ←── CHECKPOINT

Phase 5 (Refinement)
├── cub-017 (Hypothesis tests)
├── cub-018 (Docker tests) ───────┼── cub-019 (Perf tests) ←── CHECKPOINT
└─────────────────────────────────┘
```

---

## Model Distribution

| Model | Tasks | Rationale |
|-------|-------|-----------|
| opus | 2 | Complex work: cli/run.py tests (critical, 660 lines), Docker integration tests |
| sonnet | 13 | Standard implementation: most coverage tasks, CI configuration, property tests |
| haiku | 4 | Simple tasks: documentation updates, badge, Makefile |

---

## Validation Checkpoints

### Checkpoint 1: MVP Complete (after cub-005)
**What's testable:**
- STABILITY.md exists and is readable
- CLAUDE.md references stability tiers
- cli/run.py shows 60%+ coverage
- CI passes with new thresholds

**Key questions:**
- Does the stability framework make sense?
- Are the tier assignments reasonable?
- Do the cli/run.py tests exercise real logic?

---

### Checkpoint 2: Coverage Expanded (after cub-010)
**What's testable:**
- All moderate-tier modules at 60%+ coverage
- Contract tests verify CLI availability
- CI runs faster with parallel execution

**Key questions:**
- Are the mocks realistic enough?
- Do contract tests catch real issues?
- Is parallel execution stable?

---

### Checkpoint 3: Fast Local Feedback (after cub-013)
**What's testable:**
- `pytest --testmon` only runs affected tests
- `make test-fast` works
- Pre-commit hook catches failures

**Key questions:**
- Is testmon tracking dependencies correctly?
- Is the pre-commit hook too slow?

---

### Checkpoint 4: CI Optimized (after cub-016)
**What's testable:**
- Push triggers fast unit tests only
- PR merge triggers full suite
- Coverage gate prevents regressions
- Badge shows current status

**Key questions:**
- Is the CI fast enough for good DX?
- Are coverage gates too strict/lenient?

---

### Checkpoint 5: Advanced Testing Complete (after cub-019)
**What's testable:**
- Property tests find edge cases
- Docker tests verify sandbox lifecycle
- Performance benchmarks detect regressions

**Key questions:**
- Do property tests add real value?
- Are Docker tests stable in CI?

---

## Ready to Start

These tasks have no blockers:
- **cub-001**: Create STABILITY.md [P0] (sonnet) - 2-4h
- **cub-004**: Write tests for cli/run.py [P0] (opus) - 4-8h

Both can be started in parallel. cub-004 is the most valuable task - it directly improves coverage of the most critical module.

---

## Critical Path

```
cub-001 → cub-003 → cub-005 (MVP Checkpoint)
     ↘ cub-002

cub-004 → cub-005 (MVP Checkpoint)
```

The MVP requires completing:
1. STABILITY.md (cub-001)
2. Coverage thresholds (cub-003)
3. cli/run.py tests (cub-004)
4. CI verification (cub-005)

Estimated total for MVP: 1-2 days

---

## Estimated Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Foundation | 1-2 days | 1-2 days |
| Phase 2: Coverage Expansion | 2-3 days | 3-5 days |
| Phase 3: Smart Local Testing | 1 day | 4-6 days |
| Phase 4: CI Hardening | 1-2 days | 5-8 days |
| Phase 5: Refinement | 2-3 days | 7-11 days |

**Total estimated effort:** 7-11 days of focused work

---

**Next Step:** Run `cub bootstrap` to import tasks into beads.
