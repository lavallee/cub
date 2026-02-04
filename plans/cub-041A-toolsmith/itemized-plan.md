# Implementation Plan: Toolsmith

**Date:** 2026-01-20
**Granularity:** Standard (1-2 hour tasks)
**Total:** 4 epics, 20 tasks

---

## Summary

This plan implements Toolsmith, a tool discovery system for Cub. The work is organized into 4 phases:

1. **Foundation** - Core models, persistence, and CLI skeleton
2. **Sources** - Protocol and 5 source adapters (MCP Official, Smithery, Glama, SkillsMP, ClawdHub)
3. **Service** - Business logic orchestration and CLI wiring
4. **Polish** - Error handling, formatting, documentation, and test coverage

The plan prioritizes vertical integration: after Phase 1 and the first source adapter, you'll have a working end-to-end flow that can be validated before building out remaining sources.

---

## Task Hierarchy

## Epic cub-f7m: Foundation [P0]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-f7m.1 | Create Tool, ToolType, and Catalog models | haiku | P0 | - | 1h |
| cub-f7m.2 | Implement ToolsmithStore (load/save/search) | sonnet | P0 | cub-f7m.1 | 1.5h |
| cub-f7m.3 | Create CLI skeleton and register with main app | haiku | P0 | - | 1h |
| cub-f7m.4 | Write unit tests for models and store | haiku | P0 | cub-f7m.2 | 1h |

**Checkpoint 1:** Foundation complete - can create/save/load catalog, CLI commands exist (stubs)

---

## Epic cub-k3p: Sources [P1]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-k3p.1 | Define ToolSource protocol and registry | haiku | P1 | cub-f7m.1 | 1h |
| cub-k3p.2 | Implement MCP Official source adapter | sonnet | P1 | cub-k3p.1 | 2h |
| cub-k3p.3 | Implement Smithery.ai source adapter | sonnet | P1 | cub-k3p.1 | 2h |
| cub-k3p.4 | Implement Glama.ai source adapter | sonnet | P1 | cub-k3p.1 | 2h |
| cub-k3p.5 | Implement SkillsMP source adapter | sonnet | P1 | cub-k3p.1 | 2h |
| cub-k3p.6 | Implement ClawdHub source adapter | sonnet | P1 | cub-k3p.1 | 2h |

**Checkpoint 2:** First source works - can sync from MCP Official and see real tools

---

## Epic cub-v9s: Service Layer [P1]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-v9s.1 | Implement ToolsmithService sync logic | sonnet | P1 | cub-f7m.2, cub-k3p.1 | 2h |
| cub-v9s.2 | Implement search with live fallback | sonnet | P1 | cub-v9s.1 | 1.5h |
| cub-v9s.3 | Wire CLI commands to service | sonnet | P1 | cub-f7m.3, cub-v9s.2 | 1.5h |
| cub-v9s.4 | Write integration tests | sonnet | P1 | cub-v9s.3 | 1.5h |

**Checkpoint 3:** Full CLI working - sync all sources, search, stats all functional

---

## Epic cub-q2w: Polish [P2]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| cub-q2w.1 | Add Rich formatting for CLI output | haiku | P2 | cub-v9s.3 | 1h |
| cub-q2w.2 | Add error handling for network/parse failures | sonnet | P2 | cub-v9s.3 | 1.5h |
| cub-q2w.3 | Implement retry logic with backoff | sonnet | P2 | cub-q2w.2 | 1h |
| cub-q2w.4 | Add logging for debugging | haiku | P2 | cub-v9s.1 | 1h |
| cub-q2w.5 | Write user documentation | haiku | P2 | cub-v9s.4 | 1h |
| cub-q2w.6 | Achieve 80%+ test coverage | sonnet | P2 | cub-v9s.4 | 2h |

**Checkpoint 4:** Production ready - polished, documented, well-tested

---

## Dependency Graph

```
cub-f7m.1 (models)
  │
  ├─────────────────────────────┐
  │                             │
  ▼                             ▼
cub-f7m.2 (store)          cub-k3p.1 (protocol)
  │                             │
  ▼                             ├───┬───┬───┬───┐
cub-f7m.4 (tests)               │   │   │   │   │
  │                             ▼   ▼   ▼   ▼   ▼
  │                          k3p.2 k3p.3 k3p.4 k3p.5 k3p.6
  │                          (sources - can run in parallel)
  │
  └─────────┬───────────────────┘
            │
            ▼
      cub-v9s.1 (service sync)
            │
            ▼
      cub-v9s.2 (search + fallback)
            │
  ┌─────────┴─────────┐
  │                   │
  ▼                   ▼
cub-f7m.3 ────────► cub-v9s.3 (wire CLI)
(CLI skeleton)        │
                      ├───────────────┬───────────────┐
                      │               │               │
                      ▼               ▼               ▼
               cub-v9s.4        cub-q2w.1       cub-q2w.2
            (integration)    (rich output)   (error handling)
                      │               │               │
                      │               │               ▼
                      │               │          cub-q2w.3
                      │               │           (retry)
                      ▼               │
                cub-q2w.5        cub-q2w.4
                 (docs)         (logging)
                      │
                      ▼
                cub-q2w.6
               (coverage)
```

---

## Model Distribution

| Model | Tasks | Rationale |
|-------|-------|-----------|
| opus | 0 | No novel architectural decisions - patterns established |
| sonnet | 12 | Source adapters (web parsing), service logic, error handling |
| haiku | 8 | Models (clear schema), CLI (Typer patterns), tests, docs |

---

## Validation Checkpoints

### Checkpoint 1: Foundation Complete (after cub-f7m.4)
**What's testable:**
- Create Tool and Catalog objects with validation
- Save catalog to `.cub/toolsmith/catalog.json`
- Load catalog from disk
- Search catalog with keyword matching
- `cub toolsmith --help` shows commands

**Key questions:**
- Do the models feel right for the data we need to store?
- Is the store API ergonomic?

---

### Checkpoint 2: First Source Works (after cub-k3p.2)
**What's testable:**
- `cub toolsmith sync --source mcp-official` fetches real tools
- Tools appear in catalog with proper metadata
- Can search for tools by name/description

**Key questions:**
- Does the source abstraction work?
- Are tool descriptions from the source useful?
- Is the parsing robust?

---

### Checkpoint 3: Full CLI Working (after cub-v9s.3)
**What's testable:**
- `cub toolsmith sync` syncs all 5 sources
- `cub toolsmith search "browser"` finds relevant tools
- `cub toolsmith stats` shows catalog statistics
- Live fallback works when local search empty

**Key questions:**
- Is search effective at finding relevant tools?
- Does live fallback help?
- Is the output useful?

---

### Checkpoint 4: Production Ready (after cub-q2w.6)
**What's testable:**
- Error cases handled gracefully
- Retry logic prevents transient failures
- Output is polished and readable
- Documentation is complete
- Test coverage meets target

**Key questions:**
- Ready for public use?
- Are error messages helpful?
- Is it documented well enough?

---

## Ready to Start

These tasks have no blockers:

- **cub-f7m.1**: Create Tool, ToolType, and Catalog models [P0] (haiku) - 1h
- **cub-f7m.3**: Create CLI skeleton and register with main app [P0] (haiku) - 1h

---

## Critical Path

```
cub-f7m.1 → cub-f7m.2 → cub-v9s.1 → cub-v9s.2 → cub-v9s.3 → cub-v9s.4
   1h         1.5h         2h         1.5h        1.5h        1.5h
                                                              = 9h
```

The critical path is ~9 hours. Source adapters can be built in parallel once the protocol exists.

---

## Estimated Total Effort

| Phase | Tasks | Estimated Hours |
|-------|-------|-----------------|
| Foundation | 4 | 4.5h |
| Sources | 6 | 11h |
| Service | 4 | 6.5h |
| Polish | 6 | 7.5h |
| **Total** | **20** | **~29.5h** |

---

## Parallel Execution Opportunities

These task groups can run in parallel:

1. **Foundation parallel track:**
   - cub-f7m.1 (models) and cub-f7m.3 (CLI skeleton) can start together

2. **Source adapters:**
   - Once cub-k3p.1 (protocol) is done, all 5 source adapters can run in parallel
   - cub-k3p.2 through cub-k3p.6

3. **Polish parallel track:**
   - cub-q2w.1 (Rich formatting) and cub-q2w.2 (error handling) can start together after CLI wiring
   - cub-q2w.4 (logging) can start as soon as service exists

---

**Next Step:** Run `cub bootstrap` to import tasks into beads and start development.
