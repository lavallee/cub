# Module Stability Tiers

This document defines per-module stability tiers for the Cub codebase. Each tier has specific coverage requirements and testing expectations. AI coding agents and developers should use this information to understand which modules are well-tested and can be relied upon, versus which require more careful review.

## Tier Definitions

### Solid (80%+ Coverage Required)

Core abstractions that the entire system depends on. Changes here ripple everywhere, so high confidence is essential.

**Characteristics:**
- Pure logic with minimal external dependencies
- Well-defined interfaces (Protocol classes)
- Used by multiple downstream modules
- Breaking changes have severe impact

**Modules:**
| Module | Description | Current Coverage |
|--------|-------------|------------------|
| `core/config/` | Configuration loading/merging | ~99% |
| `core/tasks/backend.py` | Task backend interface | 100% |
| `core/tasks/models.py` | Task data models | 97% |
| `core/harness/backend.py` | Harness interface | 100% |
| `core/harness/models.py` | Harness data models | 93% |
| `core/captures/models.py` | Capture data models | 93% |
| `core/branches/models.py` | Branch binding models | 100% |
| `core/worktree/manager.py` | Git worktree management | 99% |
| `dashboard/renderer.py` | Dashboard rendering | 100% |
| `utils/logging.py` | JSONL structured logging | 99% |

### Moderate (60%+ Coverage Required)

Primary implementations and main execution paths. These modules coordinate between solid abstractions and handle the core use cases.

**Characteristics:**
- Implements business logic
- May have some external dependencies (subprocess, filesystem)
- Critical user-facing functionality
- Changes need careful testing

**Modules:**
| Module | Description | Current Coverage | Notes |
|--------|-------------|------------------|-------|
| `cli/run.py` | Core execution loop | 14% | **PRIORITY: Needs improvement** |
| `core/tasks/beads.py` | Beads backend implementation | 67% | Close to threshold |
| `core/tasks/json.py` | JSON backend implementation | 84% | Above threshold |
| `core/harness/claude.py` | Claude Code harness | 78% | Above threshold |
| `core/captures/store.py` | Capture persistence | 74% | Above threshold |
| `core/sandbox/docker.py` | Docker sandbox | 76% | Above threshold |
| `utils/hooks.py` | Hook execution system | 81% | Above threshold |
| `core/github/client.py` | GitHub API client | 51% | **Needs improvement** |
| `core/pr/service.py` | PR creation service | 39% | **Needs improvement** |
| `core/circuit_breaker.py` | Stagnation detection for run loop | — | New module |
| `core/instructions.py` | Instruction file generation | — | New module |
| `core/harness/hooks.py` | Hook handlers for artifact capture | — | New module |
| `core/ledger/models.py` | Ledger data models | — | New module |
| `core/ledger/reader.py` | Ledger query interface | — | New module |
| `core/ledger/writer.py` | Ledger persistence | — | New module |
| `core/dashboard/db/` | Dashboard database layer | 93% | Above threshold |
| `core/dashboard/api/` | Dashboard FastAPI routes | 84% | Above threshold |
| `core/dashboard/sync/` | Dashboard sync orchestrator | 60% | At threshold |
| `core/dashboard/views/` | Dashboard view configuration | 75% | Above threshold |

### Experimental (40%+ Coverage Required)

Newer features, less stable APIs, and modules still under active development. Breaking changes expected; testing coverage is lower but improving.

**Characteristics:**
- Recently added functionality
- API may change
- Lower usage frequency
- Okay for some gaps in coverage

**Modules:**
| Module | Description | Current Coverage | Notes |
|--------|-------------|------------------|-------|
| `audit/` | Codebase auditing tools | 77-95% | Above threshold |
| `core/sandbox/provider.py` | Sandbox provider abstraction | 66% | Above threshold |
| `core/sandbox/state.py` | Sandbox state management | 38% | **Needs improvement** |
| `core/captures/project_id.py` | Project ID generation | 73% | Above threshold |
| `core/github/issue_mode.py` | GitHub issue integration | 92% | Above threshold |
| `core/worktree/parallel.py` | Parallel worktree ops | 76% | Above threshold |
| `cli/captures.py` | Captures CLI | 79% | Above threshold |
| `cli/organize_captures.py` | Capture organization | 64% | Above threshold |
| `core/ledger/extractor.py` | LLM-based insight extraction | — | New module |
| `core/tools/` | Tool execution runtime | — | New module |
| `cli/session.py` | Direct session CLI commands | — | New module |
| `cli/new.py` | New project bootstrapping | — | New module |

### UI/Delegated (No Coverage Threshold)

User interface components and bash-delegated commands. These are difficult to unit test meaningfully and are instead covered by BATS integration tests.

**Characteristics:**
- Heavy terminal I/O (Rich tables, prompts)
- Delegates to bash implementation
- Interactive user flows
- Covered by BATS tests in `tests/bats/`

**Modules:**
| Module | Description | Current Coverage | Notes |
|--------|-------------|------------------|-------|
| `cli/status.py` | Status display | 17% | BATS-covered |
| `cli/monitor.py` | Live dashboard | 15% | BATS-covered |
| `cli/sandbox.py` | Sandbox CLI | 10% | BATS-covered |
| `cli/upgrade.py` | Upgrade flow | 11% | BATS-covered |
| `cli/uninstall.py` | Uninstall flow | 13% | BATS-covered |
| `cli/worktree.py` | Worktree CLI | 18% | BATS-covered |
| `cli/delegated.py` | Bash delegation | 66% | Delegates to bash |
| `core/bash_delegate.py` | Delegation logic | 93% | Interface tested |
| `cli/audit.py` | Audit CLI | 11% | Interactive |
| `cli/investigate.py` | Investigation CLI | 12% | Interactive |
| `cli/merge.py` | Merge CLI | 13% | Interactive |
| `cli/pr.py` | PR CLI | 14% | Interactive |
| `dashboard/tmux.py` | Tmux integration | 25% | External process |
| `core/prep/plan_markdown.py` | Plan parsing | 0% | Low priority |

## Priority Actions

Based on current coverage gaps in the **Moderate** tier:

1. **`cli/run.py` (14% -> 60%)** - The core execution loop. This is the highest priority because it's the main code path for `cub run`. Needs unit tests for:
   - Task selection logic
   - Harness execution flow
   - Error handling paths
   - Budget tracking

2. **`core/pr/service.py` (39% -> 60%)** - PR creation is a critical workflow. Needs:
   - Mock-based tests for GitHub API interactions
   - Template rendering tests
   - Error case coverage

3. **`core/github/client.py` (51% -> 60%)** - GitHub integration. Needs:
   - Contract tests for API expectations
   - Error handling for rate limits, auth failures

4. **`core/sandbox/state.py` (38% -> 40%)** - Sandbox state management:
   - State transitions
   - Persistence edge cases

## Testing Strategy by Tier

### Solid Tier Testing
- Pure unit tests with no mocks
- 100% branch coverage goal
- Property-based testing where applicable
- Must pass before any release

### Moderate Tier Testing
- Unit tests with strategic mocking
- Integration tests for external dependencies
- Contract tests for external tools
- Focus on happy path + critical error cases

### Experimental Tier Testing
- Basic happy path coverage
- Error cases for user-facing failures
- Allowed to grow coverage over time
- Document known gaps

### UI/Delegated Tier Testing
- BATS tests for end-to-end flows
- Smoke tests for critical paths
- Manual testing acceptable for interactive flows
- Coverage tracking informational only

## How to Update This Document

1. Run coverage: `pytest --cov=src/cub --cov-report=term-missing`
2. Update the coverage percentages in the tables
3. Move modules between tiers if their role changes
4. Add new modules to appropriate tier based on characteristics

## For AI Coding Agents

When modifying code:

1. **Check the tier** of the module you're changing
2. **Solid tier**: Ensure changes have corresponding tests, run full test suite
3. **Moderate tier**: Add tests for new functionality, verify coverage doesn't drop
4. **Experimental tier**: Tests encouraged but not blocking
5. **UI/Delegated tier**: Verify manually or with BATS if available

When reviewing changes:
- Be more rigorous about test coverage for Solid/Moderate tiers
- Allow more flexibility for Experimental tier
- Don't block PRs solely on UI/Delegated tier coverage

---

*Last updated: 2026-01-23*
*Overall codebase coverage: 54% (287 dashboard tests, 779+ total pytest tests)*
