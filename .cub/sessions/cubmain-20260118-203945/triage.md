# Triage Report: Cub Test Coverage Improvement

**Date:** 2026-01-18
**Triage Depth:** Standard
**Status:** Approved

---

## Executive Summary

Improve test coverage for the Cub CLI to ensure critical paths are tested, CI is trustworthy, and the codebase can evolve quickly with confidence. The approach should be realistic about what can be validated via tests vs. what remains "less proven," with this confidence level tracked and surfaced to AI coding agents working on the codebase.

## Problem Statement

Cub has 54% overall test coverage (779 pytest tests, ~496 BATS tests), but critical execution paths like `cli/run.py` (the core loop) have only 14% coverage. This creates risk when evolving the codebase - developers and AI agents can't trust that changes won't break existing functionality. The concern is not just hitting coverage numbers, but ensuring the tests reflect reality and provide genuine confidence.

## Refined Vision

Establish a layered testing strategy that:
1. Provides high-confidence coverage of critical paths
2. Tracks and communicates module stability levels to humans and AI agents
3. Enables fast local feedback loops with smart test selection
4. Maintains reliable CI that developers actually trust

## Requirements

### P0 - Must Have

- **Critical path coverage**: Test the core execution loop (`cli/run.py`) with meaningful tests that exercise real logic, not just mocked shells
- **Layered test strategy**: Unit tests for pure logic, integration tests for external dependency interactions (git, harnesses, Docker)
- **Stability tracking**: Create `.cub/STABILITY.md` that documents per-module confidence levels, referenced by CLAUDE.md/AGENTS.md
- **CI reliability**: Ensure test suite runs consistently without flaky failures that erode trust

### P1 - Should Have

- **Coverage.py per-file thresholds**: Configure coverage to enforce minimum thresholds per-module aligned with stability ratings
- **Smart local test selection**: Tooling to run only relevant tests for a given change (pytest-testmon, git-based selection, or custom)
- **GitHub Actions optimization**: Parallel test runs, caching improvements, faster feedback on PRs

### P2 - Nice to Have

- **Property-based testing**: Use Hypothesis for complex parsing logic (markdown, JSON, config)
- **Contract tests**: Lightweight verification that external APIs (GitHub, AI harnesses) behave as expected
- **Coverage visualization**: Dashboard or badge showing coverage trends over time

## Constraints

- Use existing pytest framework (no new test frameworks)
- Must work with current GitHub Actions infrastructure
- Tests must be maintainable as code evolves - avoid over-mocking that creates fragile tests

## Assumptions

- The existing 54% coverage represents genuinely tested code, not accidental coverage
- BATS tests provide meaningful integration coverage for bash components
- The layered approach will be more maintainable than either "mock everything" or "test nothing"

## Open Questions / Experiments

- **Smart test selection granularity**: How fine-grained should local test selection be? Experiment with pytest-testmon to see if file-level dependency tracking is sufficient
- **Integration test performance**: Can we run integration tests in parallel without flakiness? Experiment with pytest-xdist isolation
- **Stability rating accuracy**: Start with 3 levels (solid/moderate/experimental), adjust based on real-world experience

## Out of Scope

- 100% coverage target (explicitly rejected as unrealistic and potentially counterproductive)
- Rewriting existing tests that work
- Testing the bash script directly (BATS already covers this)
- Fuzzing or security testing (separate initiative)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tests become maintenance burden | High | Focus on critical paths, use layered approach to avoid over-mocking |
| Coverage numbers don't reflect confidence | Medium | Stability ratings separate from coverage %, review with skepticism |
| CI slowdown from more tests | Medium | Smart selection locally, parallel execution in CI |
| False confidence from passing tests | High | Require integration tests for external dependencies, not just mocks |

## MVP Definition

1. Get `cli/run.py` (the core loop) to 60%+ coverage with meaningful tests
2. Create `.cub/STABILITY.md` with initial module ratings (solid/moderate/experimental)
3. Update CLAUDE.md to reference STABILITY.md
4. Configure coverage.py with per-file thresholds for P0 modules
5. Verify CI passes reliably with new tests

This is the smallest useful increment that demonstrates the approach works and provides immediate value.

## Current State Analysis

### Coverage by Module (grouped by confidence tier)

**Needs Attention (Critical paths with <40% coverage):**
| Module | Coverage | Missing Lines | Notes |
|--------|----------|---------------|-------|
| `cli/run.py` | 14% | 660 | Core execution loop |
| `cli/audit.py` | 11% | 159 | Audit commands |
| `cli/investigate.py` | 12% | 242 | Investigation flow |
| `cli/sandbox.py` | 10% | 218 | Container management |
| `cli/merge.py` | 13% | 88 | PR merge logic |
| `cli/pr.py` | 14% | 91 | PR creation |
| `cli/upgrade.py` | 11% | 197 | Upgrade commands |
| `cli/monitor.py` | 15% | 85 | Monitoring dashboard |
| `cli/status.py` | 17% | 49 | Status display |
| `cli/worktree.py` | 18% | 85 | Worktree management |
| `cli/uninstall.py` | 13% | 109 | Uninstall logic |
| `core/harness/codex.py` | 14% | 115 | Codex harness |
| `core/prep/plan_markdown.py` | 0% | 122 | Plan parsing |
| `core/branches/store.py` | 22% | 104 | Branch storage |
| `dashboard/tmux.py` | 25% | 40 | Tmux integration |
| `core/sandbox/state.py` | 38% | 18 | Sandbox state |
| `core/tasks/service.py` | 38% | 74 | Task service |
| `core/pr/service.py` | 39% | 141 | PR service |

**Well-Tested (>80% coverage):**
- `core/config/loader.py` (99%)
- `core/harness/backend.py` (100%)
- `core/tasks/backend.py` (100%)
- `dashboard/renderer.py` (100%)
- `core/worktree/manager.py` (99%)
- `utils/logging.py` (99%)

### Existing CI Infrastructure

- GitHub Actions on push/PR to main
- Cross-platform: Ubuntu + macOS
- Python versions: 3.10, 3.11, 3.12, 3.13
- Coverage upload to Codecov
- Threshold: 53% (with acknowledgment that CLI is hard to test)
- BATS tests for bash components (~450-480 tests expected to pass)

---

**Next Step:** Run `cub architect` to design the technical implementation approach.
