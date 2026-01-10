# Implementation Plan: Curb 1.0

**Session:** curb-20250109-163000
**Generated:** 2025-01-09
**Granularity:** Micro (15-30 min tasks)
**Total:** 4 epics, 32 tasks, 4 checkpoints
**Estimated Duration:** ~12 hours

---

## Summary

This plan implements Curb 1.0 with focus on reliability for unattended operation. Work is organized into 4 phases with validation checkpoints after each:

1. **Foundation** - Config and logging infrastructure
2. **Reliability** - Clean state and budget enforcement
3. **Extensibility** - Hooks and new harnesses
4. **Polish** - Documentation and UX

---

## Task Hierarchy

### Epic 1: Foundation (Phase 1) [P0]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-001 | Create XDG directory structure | haiku | P0 | - | 15m |
| curb-002 | Implement config.sh interface | sonnet | P0 | curb-001 | 30m |
| curb-003 | Add config file loading/merge | sonnet | P0 | curb-002 | 30m |
| curb-004 | Implement logger.sh JSONL | sonnet | P0 | curb-001 | 30m |
| curb-005 | Add log_task functions | sonnet | P1 | curb-004 | 20m |
| curb-006 | Integrate config into curb | sonnet | P1 | curb-003 | 20m |
| curb-007 | Integrate logger into loop | sonnet | P1 | curb-005, curb-006 | 20m |
| curb-008 | Add curb init --global | sonnet | P1 | curb-003 | 30m |
| **CP1** | **Checkpoint: Config & Logging** | - | P1 | curb-007, curb-008 | - |

### Epic 2: Reliability (Phase 2) [P1]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-009 | Implement state.sh git check | sonnet | P0 | CP1 | 30m |
| curb-010 | Add test runner integration | sonnet | P1 | curb-009 | 30m |
| curb-011 | Integrate clean state check | sonnet | P1 | curb-010 | 20m |
| curb-012 | Implement budget.sh tracking | sonnet | P0 | CP1 | 30m |
| curb-013 | Add --budget CLI flag | haiku | P1 | curb-012 | 15m |
| curb-014 | Extract tokens from Claude | opus-4.5 | P0 | curb-012 | 45m |
| curb-015 | Add budget enforcement | sonnet | P1 | curb-013, curb-014 | 20m |
| curb-016 | Add budget warning | haiku | P2 | curb-015 | 15m |
| **CP2** | **Checkpoint: Reliability** | - | P1 | curb-011, curb-016 | - |

### Epic 3: Extensibility (Phase 3) [P1]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-017 | Implement hooks.sh framework | sonnet | P0 | CP2 | 30m |
| curb-018 | Add hook directory scanning | haiku | P1 | curb-017 | 20m |
| curb-019 | Implement 5 hook points | sonnet | P1 | curb-018 | 30m |
| curb-020 | Spike: Gemini CLI research | sonnet | P1 | CP2 | 30m |
| curb-021 | Implement Gemini harness | sonnet | P1 | curb-020 | 30m |
| curb-022 | Spike: OpenCode CLI research | sonnet | P1 | CP2 | 30m |
| curb-023 | Implement OpenCode harness | sonnet | P1 | curb-022 | 30m |
| curb-024 | Add harness capabilities | opus-4.5 | P2 | curb-021, curb-023 | 30m |
| curb-025 | Token extraction Gemini/OC | sonnet | P2 | curb-024 | 30m |
| curb-026 | Config harness priority | haiku | P2 | curb-024 | 15m |
| **CP3** | **Checkpoint: Extensibility** | - | P1 | curb-019, curb-025, curb-026 | - |

### Epic 4: Polish (Phase 4) [P2]

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-027 | Write example hooks | haiku | P2 | CP3 | 30m |
| curb-028 | Update README | haiku | P2 | CP3 | 30m |
| curb-029 | Improve --help | haiku | P3 | CP3 | 15m |
| curb-030 | Write migration guide | haiku | P2 | CP3 | 20m |
| curb-031 | Document config schema | haiku | P2 | CP3 | 20m |
| curb-032 | E2E test full loop | sonnet | P2 | curb-027, curb-028 | 30m |
| **CP4** | **Checkpoint: Ready for 1.0** | - | P2 | curb-029-032 | - |

---

## Dependency Graph

```
Phase 1: Foundation
curb-001 (XDG dirs)
  ├─> curb-002 (config interface)
  │     └─> curb-003 (config loading)
  │           ├─> curb-006 (integrate config)
  │           └─> curb-008 (init --global)
  └─> curb-004 (logger)
        └─> curb-005 (log functions)
              └─> curb-007 (integrate logger)
                    └─> CP1 (Checkpoint)

Phase 2: Reliability
CP1 ─┬─> curb-009 (state check)
     │     └─> curb-010 (test runner)
     │           └─> curb-011 (integrate state)
     │                 └─> CP2
     └─> curb-012 (budget tracker)
           ├─> curb-013 (--budget flag)
           └─> curb-014 (token extraction) [opus]
                 └─> curb-015 (enforcement)
                       └─> curb-016 (warning)
                             └─> CP2 (Checkpoint)

Phase 3: Extensibility
CP2 ─┬─> curb-017 (hooks framework)
     │     └─> curb-018 (scanning)
     │           └─> curb-019 (5 hook points)
     │                 └─> CP3
     ├─> curb-020 (Gemini spike)
     │     └─> curb-021 (Gemini harness)
     │           └─> curb-024 (capabilities) [opus]
     └─> curb-022 (OpenCode spike)
           └─> curb-023 (OpenCode harness)
                 └─> curb-024
                       ├─> curb-025 (token extraction)
                       └─> curb-026 (priority config)
                             └─> CP3 (Checkpoint)

Phase 4: Polish
CP3 ─┬─> curb-027 (example hooks)
     ├─> curb-028 (README)
     │     └─> curb-032 (E2E test)
     ├─> curb-029 (--help)
     ├─> curb-030 (migration guide)
     └─> curb-031 (config docs)
           └─> CP4 (Ready for 1.0!)
```

---

## Model Distribution

| Model | Tasks | Rationale |
|-------|-------|-----------|
| opus-4.5 | 2 | Token extraction from harness output (tricky parsing), harness capability detection (cross-cutting design) |
| sonnet | 21 | Standard implementation work - config, logging, state, budget, hooks, harnesses |
| haiku | 9 | Boilerplate (XDG, flags), documentation, simple UI improvements |

---

## Validation Checkpoints

### Checkpoint 1: Config & Logging (after Phase 1)
**What's testable:** Global/project config, structured JSONL logs, onboarding command
**Key questions:**
- Is the config schema intuitive?
- Are logs capturing the right metadata?
**Validates assumption:** JSON config with jq is sufficient

### Checkpoint 2: Reliability (after Phase 2)
**What's testable:** Clean state enforcement, budget tracking and limits
**Key questions:**
- Is clean state check too strict?
- Is token counting accurate?
**Validates assumption:** Token counts extractable from harness output
**Milestone:** Curb is now trustworthy for overnight runs!

### Checkpoint 3: Extensibility (after Phase 3)
**What's testable:** 5 hook points, all 4 harnesses, capability detection
**Key questions:**
- Are hook points sufficient?
- All harnesses reliable?
**Validates assumption:** Gemini/OpenCode CLIs have compatible interfaces
**Milestone:** Curb is feature-complete!

### Checkpoint 4: Ready for 1.0 (after Phase 4)
**What's testable:** Docs, examples, E2E test, fresh install experience
**Key questions:**
- Can new user set up in < 5 minutes?
- Is migration path clear?
**Milestone:** Ship it!

> **Note:** Checkpoints are suggestions. Skip if confident, or add more for tighter feedback.

---

## Ready to Start

These tasks have no blockers and can begin immediately:
- **curb-001**: Create XDG directory structure [P0] (haiku) - 15m

---

## Critical Path

Longest dependency chain determining minimum time:
```
curb-001 → curb-002 → curb-003 → curb-006 → curb-007 → CP1
→ curb-012 → curb-014 → curb-015 → curb-016 → CP2
→ curb-017 → curb-018 → curb-019 → CP3
→ curb-028 → curb-032 → CP4
```

---

## Next Steps

1. Review this plan and adjust if needed
2. Load tasks into Beads:
   ```bash
   cd /Users/lavallee/tools/curb/.chopshop/sessions/curb-20250109-163000
   ./plan-commands.sh
   ```
3. Start work:
   ```bash
   bd ready  # See available tasks
   bd show curb-001  # View first task details
   ```
4. Complete tasks:
   ```bash
   bd close curb-001 --reason "Done"
   ```

---

## Files Summary

**New files to create:**
- `lib/xdg.sh` - XDG directory helpers
- `lib/config.sh` - Configuration management
- `lib/logger.sh` - Structured logging
- `lib/budget.sh` - Token budget tracking
- `lib/hooks.sh` - Hook system
- `lib/state.sh` - Clean state enforcement
- `docs/CONFIG.md` - Config reference
- `UPGRADING.md` - Migration guide
- `examples/hooks/` - Example hook scripts
- `tests/e2e/` - End-to-end tests

**Files to modify:**
- `curb` - Integrate all new subsystems
- `curb-init` - Add --global flag
- `lib/harness.sh` - Add Gemini, OpenCode, token reporting
- `README.md` - Document new features
