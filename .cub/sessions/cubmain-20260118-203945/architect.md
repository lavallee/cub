# Architecture Design: Cub Test Coverage Improvement

**Date:** 2026-01-18
**Mindset:** Production
**Scale:** Team (5-20 contributors)
**Status:** Approved

---

## Technical Summary

This architecture establishes a layered testing strategy for Cub that provides high confidence in critical paths while remaining maintainable as the codebase evolves. The design introduces stability tiers that communicate module confidence levels to both human developers and AI agents, with coverage thresholds enforced per tier.

The core insight is that not all code needs the same testing rigor. Core abstractions (config, task backend, harness backend) are "solid" and require 80%+ coverage. The main execution loop and primary implementations are "moderate" at 60%+. Newer features are "experimental" at 40%+. UI-heavy and bash-delegated code has no threshold but is covered by BATS tests.

For external dependencies—especially AI harnesses—we use a three-layer approach: unit tests with mocks for fast feedback, contract tests to catch breaking changes in CLI interfaces, and optional integration tests for full end-to-end verification.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Core Testing | pytest (keep) | Already in use, mature ecosystem, team familiarity |
| Parallelization | pytest-xdist | `-n auto` for CI speedup, minimal config |
| Coverage | coverage.py + per-file config | Enforce different thresholds per stability tier |
| Test Selection | pytest-testmon | Track file dependencies for smart local runs |
| Property Testing | hypothesis (P2) | Defer until core coverage established |
| Mocking | pytest-mock (keep) | Already in use, works well |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         TEST PYRAMID                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              INTEGRATION TESTS                          │   │
│   │   Real subprocess calls in isolated environments        │   │
│   │   Run: CI only (slow), skip by default locally          │   │
│   │   Location: tests/integration/                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                            ▲                                    │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              CONTRACT TESTS                             │   │
│   │   Verify external tool behavior matches expectations    │   │
│   │   Run: Weekly CI job (catch upstream changes)           │   │
│   │   Location: tests/contracts/                            │   │
│   └─────────────────────────────────────────────────────────┘   │
│                            ▲                                    │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              UNIT TESTS (mocked)                        │   │
│   │   Fast, isolated, mock external calls                   │   │
│   │   Run: Every commit, locally and CI                     │   │
│   │   Location: tests/test_*.py (current structure)         │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    STABILITY TRACKING                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   .cub/STABILITY.md ◄──── Referenced by ────► CLAUDE.md        │
│         │                                         │             │
│         │                                         │             │
│         ▼                                         ▼             │
│   Coverage Config                          Agent Context        │
│   (pyproject.toml)                         (AGENTS.md)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Stability Tracking System

- **Purpose:** Track and communicate module confidence levels
- **Responsibilities:**
  - Define tier criteria (Solid/Moderate/Experimental/Untested)
  - List modules per tier with rationale
  - Provide guidance for agents making changes
- **Dependencies:** None (documentation-only)
- **Interface:** `.cub/STABILITY.md` file, referenced by CLAUDE.md

### Per-File Coverage Configuration

- **Purpose:** Enforce different coverage thresholds per module
- **Responsibilities:**
  - Map modules to coverage requirements
  - Fail CI if coverage drops below threshold
  - Allow exceptions for intentionally untested code
- **Dependencies:** coverage.py, pyproject.toml
- **Interface:** `[tool.coverage.report]` section with `fail_under` per file

### Unit Test Suite

- **Purpose:** Fast, isolated tests for all business logic
- **Responsibilities:**
  - Test pure functions directly
  - Mock subprocess/external calls
  - Cover error handling paths
- **Dependencies:** pytest, pytest-mock, existing fixtures
- **Interface:** `tests/test_*.py` files

### Contract Test Suite

- **Purpose:** Verify external CLI tools behave as expected
- **Responsibilities:**
  - Check `claude --version` output format
  - Verify `gh` CLI availability and auth
  - Test `bd` CLI output parsing
- **Dependencies:** Real CLI tools (marked for conditional skip)
- **Interface:** `tests/contracts/` directory, `@pytest.mark.contract`

### Integration Test Suite

- **Purpose:** End-to-end verification with real external calls
- **Responsibilities:**
  - Test full harness execution (with real API keys)
  - Verify git operations on real repos
  - Test Docker sandbox lifecycle
- **Dependencies:** Real services, API keys, Docker
- **Interface:** `tests/integration/` directory, `@pytest.mark.integration`

### Smart Test Selection

- **Purpose:** Run only relevant tests locally for fast feedback
- **Responsibilities:**
  - Track file-to-test dependencies
  - Skip unaffected tests on code changes
  - Reset on major changes
- **Dependencies:** pytest-testmon
- **Interface:** `pytest --testmon` for local runs

## Data Model

### Stability Tier

```
tier: Solid | Moderate | Experimental | Untested
coverage_target: int (percentage, 0-100)
modules: list[str] (module paths)
rationale: str (why this tier)
```

### Coverage Report Integration

```
module_path: str
current_coverage: float
target_coverage: float
tier: StabilityTier
passing: bool
```

## APIs / Interfaces

### pytest Markers

- **Type:** Internal (test framework)
- **Purpose:** Categorize tests for selective execution
- **Key Markers:**
  - `@pytest.mark.unit` - Fast, mocked tests (default)
  - `@pytest.mark.integration` - Slow, real external calls
  - `@pytest.mark.contract` - External CLI verification
  - `@pytest.mark.slow` - Tests taking >5s

### Coverage Configuration

- **Type:** Configuration file
- **Purpose:** Define per-module thresholds
- **Location:** `pyproject.toml` or `.coveragerc`

### CI Workflow Triggers

- **Type:** GitHub Actions
- **Purpose:** Run appropriate tests at appropriate times
- **Key Workflows:**
  - `on: push` - Unit tests only (fast)
  - `on: pull_request` - Unit + contract tests
  - `on: schedule (weekly)` - Full integration suite

## Implementation Phases

### Phase 1: Foundation (MVP)

**Goal:** Establish the stability framework and hit 60% on cli/run.py

- Create `.cub/STABILITY.md` with initial tier assignments
- Update `CLAUDE.md` to reference stability tiers
- Add per-file coverage config to `pyproject.toml`
- Write unit tests for `cli/run.py` covering:
  - Task selection logic
  - Prompt generation
  - Harness invocation (mocked subprocess)
  - Exit conditions and signal handling
- Verify CI passes with new coverage threshold

### Phase 2: Coverage Expansion

**Goal:** Cover remaining critical modules and add CI improvements

- Add tests for `core/tasks/service.py` (task lifecycle)
- Add tests for `core/pr/service.py` (PR creation logic)
- Add tests for `core/harness/codex.py` (codex-specific logic)
- Create `tests/contracts/` directory with harness CLI tests
- Add pytest-xdist to dev dependencies
- Enable parallel test execution in CI (`pytest -n auto`)

### Phase 3: Smart Local Testing

**Goal:** Enable fast local feedback with smart test selection

- Add pytest-testmon to dev dependencies
- Document usage in CLAUDE.md: `pytest --testmon`
- Create pre-commit hook for running affected tests
- Add `make test-fast` target for quick iteration

### Phase 4: CI Hardening

**Goal:** Separate CI jobs for different test types

- Split test workflow into jobs:
  - `unit` - Fast, runs on every push
  - `integration` - Slow, runs on PR merge
  - `contracts` - Weekly schedule
- Add coverage trend gate (fail if coverage drops)
- Add badge to README showing test status

### Phase 5: Refinement (P2)

**Goal:** Advanced testing features

- Add hypothesis for property-based testing:
  - Config parsing
  - Markdown parsing
  - JSON parsing
- Docker-based integration tests for sandbox module
- Performance regression tests for critical paths

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Over-mocking creates false confidence | High | Medium | Contract tests verify real CLI behavior; review test quality |
| pytest-testmon misses dependencies | Medium | Low | Full test run in CI catches issues; reset testmon on major changes |
| Per-file coverage config is verbose | Low | High | Start with tier-level config, only add exceptions as needed |
| Integration tests are flaky | Medium | Medium | Run in isolated containers, mark flaky tests explicitly |
| AI agents ignore STABILITY.md | Medium | Low | Reference in CLAUDE.md preamble, test in practice |

## Dependencies

### External (New)

- pytest-xdist: Parallel test execution
- pytest-testmon: Smart test selection
- hypothesis (P2): Property-based testing

### Internal (Existing)

- pytest, pytest-cov, pytest-mock: Core testing
- coverage.py: Coverage reporting
- GitHub Actions: CI infrastructure
- Codecov: Coverage tracking

## Security Considerations

- Integration tests require API keys - use GitHub Secrets
- Contract tests should not leak credentials in output
- Test fixtures should not include real secrets
- Coverage reports should be public, but test logs may contain paths

## Future Considerations

- **Mutation testing:** Once coverage is solid, use mutmut to verify test quality
- **Visual regression:** If UI components grow, consider screenshot testing
- **Load testing:** If cub handles large task backlogs, add performance tests
- **Cross-platform parity:** Current tests run on Ubuntu + macOS; Windows support TBD

---

**Next Step:** Run `cub plan` to generate implementation tasks.
