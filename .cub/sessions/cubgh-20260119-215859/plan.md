# Implementation Plan: Harness Abstraction

**Date:** 2026-01-19
**Granularity:** Macro (half-day to full-day tasks)
**Total:** 1 epic, 5 tasks

---

## Summary

This plan implements the harness abstraction layer that enables Cub to support multiple LLM providers while leveraging provider-specific features. The work follows 5 phases from the architecture document:

1. **Core Async Infrastructure** - Establish async foundation with Protocol and models
2. **Claude SDK Harness** - Implement full-featured Claude harness using Claude Agent SDK
3. **Legacy Harness Migration** - Wrap existing shell-out harnesses in async interface
4. **Hook System** - Enable circuit breaker and guardrails via hooks
5. **CLI Integration & Testing** - Update CLI and ensure comprehensive test coverage

Each task is scoped to approximately half-day to full-day of focused work.

---

## Task Hierarchy

### Epic: cub-k41 - Harness Abstraction [P0]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-k41.1 | Create async harness protocol and models | sonnet | P0 | - | 4h |
| cub-k41.2 | Implement Claude SDK harness | opus | P0 | cub-k41.1 | 6h |
| cub-k41.3 | Migrate legacy harnesses to async interface | sonnet | P1 | cub-k41.1 | 4h |
| cub-k41.4 | Implement hook system for Claude SDK | opus | P1 | cub-k41.2 | 4h |
| cub-k41.5 | Integrate async harnesses into CLI and add tests | sonnet | P1 | cub-k41.3, cub-k41.4 | 6h |

**Total Estimated:** ~24 hours of work

---

## Dependency Graph

```
cub-k41 (epic)
  │
  └─> cub-k41.1 (async infrastructure) [P0]
        │
        ├─> cub-k41.2 (Claude SDK harness) [P0]
        │     │
        │     └─> cub-k41.4 (hook system) [P1]
        │           │
        │           └─> cub-k41.5 (CLI integration) [P1]
        │                 ▲
        └─> cub-k41.3 (legacy migration) [P1]
              │
              └─────────┘
```

---

## Model Distribution

| Model | Tasks | Rationale |
|-------|-------|-----------|
| opus | 2 | Claude SDK integration (cub-k41.2) and hook system (cub-k41.4) require novel problem-solving with unfamiliar SDK APIs |
| sonnet | 3 | Infrastructure (cub-k41.1), legacy migration (cub-k41.3), and CLI integration (cub-k41.5) follow established patterns |

---

## Validation Checkpoints

### Checkpoint 1: After cub-k41.2 (Claude SDK Harness)
**What's testable:** Claude SDK harness can execute a simple task
**Key questions:**
- Does `query()` work with basic prompts?
- Is token usage correctly extracted?
- Do errors propagate clearly?

### Checkpoint 2: After cub-k41.5 (Full Integration)
**What's testable:** Complete harness abstraction working end-to-end
**Key questions:**
- Does `cub run --harness claude` use SDK harness?
- Does `cub run --harness claude-legacy` work?
- Do hooks block dangerous commands?
- Are all tests passing?

---

## Ready to Start

These tasks have no blockers:

- **cub-k41.1**: Create async harness protocol and models [P0] (sonnet) - 4h

---

## Critical Path

```
cub-k41.1 → cub-k41.2 → cub-k41.4 → cub-k41.5
```

The critical path runs through the Claude SDK harness and hook system, as these are the core value of the feature. Legacy migration (cub-k41.3) can proceed in parallel with the SDK work after infrastructure is complete.

---

## Task Details

### cub-k41.1: Create async harness protocol and models

**Phase:** 1 - Core Async Infrastructure
**Model:** sonnet
**Priority:** P0
**Estimated:** 4 hours

Establish the async foundation for the new harness system:
- Add `anyio` and `pytest-asyncio` dependencies
- Extend `HarnessCapabilities` with hooks, custom_tools, sessions
- Create `HarnessFeature` enum
- Create `TaskInput`, `Message`, `ToolUse` models
- Define `AsyncHarnessBackend` Protocol
- Add async wrapper to `cub run`

---

### cub-k41.2: Implement Claude SDK harness

**Phase:** 2 - Claude SDK Harness
**Model:** opus
**Priority:** P0
**Estimated:** 6 hours
**Blocked by:** cub-k41.1

Core SDK integration:
- Add `claude-agent-sdk` dependency
- Implement `ClaudeSDKHarness` with `run_task()` and `stream_task()`
- Map `TaskInput` to `ClaudeAgentOptions`
- Parse SDK messages into our models
- Extract token usage
- Register as "claude" backend

---

### cub-k41.3: Migrate legacy harnesses to async interface

**Phase:** 3 - Legacy Harness Migration
**Model:** sonnet
**Priority:** P1
**Estimated:** 4 hours
**Blocked by:** cub-k41.1

Preserve backward compatibility:
- Rename `ClaudeBackend` to `ClaudeLegacyBackend`
- Wrap sync methods with `asyncio.to_thread()`
- Register as "claude-legacy"
- Migrate Codex, OpenCode harnesses
- Add deprecation warnings

---

### cub-k41.4: Implement hook system for Claude SDK

**Phase:** 4 - Hook System
**Model:** opus
**Priority:** P1
**Estimated:** 4 hours
**Blocked by:** cub-k41.2

Enable event interception:
- Define `HookEvent`, `HookContext`, `HookResult`
- Implement hook registry in `ClaudeSDKHarness`
- Map to SDK's `PreToolUse`/`PostToolUse`
- Execute PRE_TASK, POST_TASK, ON_ERROR hooks
- Add no-op hooks to legacy harnesses

---

### cub-k41.5: Integrate async harnesses into CLI and add tests

**Phase:** 5 - CLI Integration & Testing
**Model:** sonnet
**Priority:** P1
**Estimated:** 6 hours
**Blocked by:** cub-k41.3, cub-k41.4

Final integration:
- Update `cub run` to use async harness methods
- Update harness detection priority
- Add `--harness claude-legacy` documentation
- Create integration tests
- Update docs/HARNESSES.md feature matrix
- Add migration guide to UPGRADING.md

---

## Files Overview

| File | Created | Modified |
|------|:-------:|:--------:|
| pyproject.toml | | ✓ |
| src/cub/core/harness/models.py | | ✓ |
| src/cub/core/harness/async_backend.py | ✓ | |
| src/cub/core/harness/claude_sdk.py | ✓ | |
| src/cub/core/harness/claude.py | | ✓ |
| src/cub/core/harness/codex.py | | ✓ |
| src/cub/core/harness/opencode.py | | ✓ |
| src/cub/core/harness/__init__.py | | ✓ |
| src/cub/cli/run.py | | ✓ |
| tests/test_harness_claude_sdk.py | ✓ | |
| tests/test_harness_hooks.py | ✓ | |
| tests/test_harness_integration.py | ✓ | |
| docs/HARNESSES.md | | ✓ |
| README.md | | ✓ |
| UPGRADING.md | | ✓ |

---

**Next Step:** Run `cub bootstrap` to import tasks into beads and start development.
