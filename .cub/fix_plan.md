# Curb Fix Plan

**Generated**: 2026-01-10
**Analysis Method**: Parallel subagent analysis of specs, source code, tests, and TODOs

---

## Executive Summary

Curb 1.0 has a solid foundation with 438+ tests and comprehensive core functionality. However, several roadmap features remain incomplete, and there are gaps between documentation and implementation. This plan prioritizes items by impact and dependency order.

**Overall Status**:
- Core loop, task selection, artifacts: Complete
- Hook system: Complete (5/5 hooks)
- Harness abstraction: Partial (Claude/Codex working, Gemini/OpenCode need testing)
- Git workflow: Not started (branch-per-run, commit-per-task)
- Guardrails: Partial (budget exists, iteration limits exist, but typecheck/lint missing)

---

## Priority 0: Critical Path (Blocking 1.0 Release)

### 1. Git Workflow Implementation (Phase 3)

**What**: Implement branch-per-run and commit-per-task workflow modes as specified in 1.0-EXPECTATIONS.md.

**Why Critical**: Users expect "reviewable changes" - the primary 1.0 value proposition.

**Files Affected**:
- `lib/git.sh` (new file)
- `lib/state.sh` (extract git functions)
- `curb` (main loop integration)
- `lib/config.sh` (git mode configuration)

**Tasks in Beads**:
- curb-021: Create lib/git.sh and extract git functions from state.sh
- curb-022: Implement git_init_run_branch with naming convention
- curb-023: Implement git_commit_task with structured message format
- curb-024: Implement git_has_changes and git_get_run_branch helpers
- curb-026: Integrate git workflow into main loop
- curb-028: CHECKPOINT: Verify branch-per-run, commit-per-task workflow

**Dependencies**: None (can start immediately)

**Acceptance Criteria**:
- [ ] `cub run` creates branch `cub/{session-name}` at loop start
- [ ] Each task completion triggers commit with message `task({task-id}): {title}`
- [ ] Branch remains local unless `--push` flag is used
- [ ] Configuration: `git.mode = "branch-per-run" | "commit-per-task" | "patch-only"`

---

### 2. --push Flag Implementation

**What**: Implement the `--push` flag mentioned in help but currently stubbed.

**Why Critical**: Documented feature that doesn't work - breaks user trust.

**Files Affected**:
- `curb` (line 385-386, currently logs warning)
- `lib/git.sh` (new git_push_branch function)

**Tasks in Beads**:
- curb-025: Add --push flag and git_push_branch (explicit opt-in)

**Dependencies**: Requires git workflow (curb-021 to curb-024)

**Current Code** (curb:385):
```bash
log_warn "Push flag not yet implemented"
```

**Acceptance Criteria**:
- [ ] `cub --push` pushes branch to remote after each task
- [ ] Without `--push`, no remote operations occur (safe default)
- [ ] Push failures logged but don't stop the loop

---

### 3. Release Validation Checkpoint

**What**: Final verification that all 1.0 features work end-to-end.

**Tasks in Beads**:
- curb-052: CHECKPOINT: 1.0 release validation

**Dependencies**: All Phase 3-6 items

---

## Priority 1: Important Features (Should Have for 1.0)

### 4. Guardrails and Safety (Phase 4)

**What**: Implement iteration tracking, secret redaction, and configurable guardrails.

**Why Important**: Prevents runaway loops and cost overruns.

**Files Affected**:
- `lib/budget.sh` (iteration tracking)
- `lib/logger.sh` (secret redaction)
- `lib/config.sh` (guardrail schema)
- `curb` (integration)

**Tasks in Beads**:
- curb-029: Add iteration tracking to budget.sh
- curb-030: Implement budget_check_* and budget_increment_* functions
- curb-031: Add logger_redact function with secret patterns
- curb-032: Add logger_stream with timestamps
- curb-033: Add config schema for guardrails
- curb-034: Integrate iteration limits into main loop
- curb-035: Write BATS tests for iteration tracking and secret redaction
- curb-036: CHECKPOINT: Verify guardrails prevent runaway loops

**Dependencies**: None

**Acceptance Criteria**:
- [ ] Iteration counter tracks task attempts across session
- [ ] Secrets matching patterns (API keys, tokens) redacted in logs
- [ ] Config supports `guardrails.max_consecutive_failures`
- [ ] Loop stops if guardrail triggers

---

### 5. Failure Handling Modes (Phase 5)

**What**: Implement configurable failure modes: stop, move-on, retry.

**Why Important**: Currently failed tasks remain in_progress forever.

**Files Affected**:
- `lib/failure.sh` (new file)
- `curb` (main loop integration)

**Tasks in Beads**:
- curb-037: Create lib/failure.sh with mode enum and failure_get_mode
- curb-038: Implement stop and move-on failure modes
- curb-039: Implement retry mode with counter and context passing
- curb-040: Integrate failure handling into main loop
- curb-041: Implement cmd_explain to show task failure reasons
- curb-042: Write BATS tests for failure modes
- curb-043: CHECKPOINT: Verify failure handling works for all modes

**Dependencies**: None

**Acceptance Criteria**:
- [ ] Config: `failure.mode = "stop" | "move-on" | "retry"`
- [ ] Retry mode passes previous failure context to next attempt
- [ ] `cub explain <task-id>` shows failure reason from artifacts
- [ ] Failed tasks marked with appropriate status

---

### 6. Harness Streaming Improvements

**What**: Complete streaming support for Codex and Gemini harnesses.

**Why Important**: Currently TODOs in code indicate incomplete implementation.

**Files Affected**:
- `lib/harness.sh` (lines 588, 652)

**Current TODOs**:
```bash
# Line 588: TODO: Investigate codex proto command for structured streaming
# Line 652: TODO: Test newer versions for streaming support
```

**Dependencies**: None

**Acceptance Criteria**:
- [ ] Codex streaming tested with current CLI version
- [ ] Gemini streaming tested with Gemini CLI > v0.1.9
- [ ] Documented workarounds for unsupported features

---

### 7. CLI Dispatcher Tests and Documentation (Phase 2)

**What**: Complete CLI restructuring with tests and updated help.

**Files Affected**:
- `curb` (help text)
- `tests/curb.bats` (dispatcher tests)
- `docs/` (documentation updates)

**Tasks in Beads**:
- curb-018: Update help text for subcommand CLI
- curb-019: Write BATS tests for CLI dispatcher and routing
- curb-027: Write BATS tests for lib/git.sh

**Dependencies**: Requires some subcommands to exist (artifacts, explain)

---

### 8. Beads Session Assignee Integration

**What**: When starting a task with beads backend, set assignee to session name.

**Why Important**: Explicitly requested in 1.0-TASKS.md.

**Files Affected**:
- `curb` (task acquisition)
- `lib/beads.sh` (assignee update)

**Tasks in Beads**:
- curb-050: Integrate beads assignee with session name

**Current Gap**: Session names exist but never assigned to tasks.

**Acceptance Criteria**:
- [ ] `bd update <task-id> -a <session-name>` called on task start
- [ ] Only when using beads backend
- [ ] Session name visible in beads task list

---

## Priority 2: Nice to Have (Can Ship Without)

### 9. Default Hooks for Epic Workflow

**What**: Add pre-loop hook for branch creation, post-loop hook for PR prompt.

**Files Affected**:
- `examples/hooks/pre-loop.d/` (new default hook)
- `examples/hooks/post-loop.d/` (new default hook)

**Tasks in Beads**:
- curb-044: Create default pre-loop hook for automatic branch creation
- curb-045: Create default post-loop hook for PR prompt

**Dependencies**: Requires git workflow (curb-021+)

---

### 10. Acceptance Criteria Parsing

**What**: Parse acceptance criteria from task descriptions and verify them.

**Files Affected**:
- `lib/tasks.sh` (parsing)
- `curb` (verification integration)

**Tasks in Beads**:
- curb-047: Implement acceptance criteria parsing from task descriptions

**Dependencies**: None

---

### 11. Documentation Updates

**What**: Update README, UPGRADING for new features.

**Files Affected**:
- `README.md`
- `UPGRADING.md`
- `docs/CONFIG.md`

**Tasks in Beads**:
- curb-046: Add full harness command line to debug output
- curb-048: Update UPGRADING.md with migration guide for subcommands
- curb-049: Update README.md with new commands and features

**Dependencies**: Features being documented must exist

---

## Missing Specifications (Gaps Found)

The following items are mentioned in roadmap/expectations but lack detailed specifications:

### 1. Typecheck/Lint Verification

**Gap**: 1.0-EXPECTATIONS.md (line 73-75) mentions:
> "formatting (if configured), unit tests (if configured), typecheck/lint (if configured)"

**Current State**: Only test detection exists (`state_detect_test_command`). No typecheck or lint.

**Recommendation**: Create specification for:
- `state_detect_typecheck_command()` - detect tsc, mypy, etc.
- `state_detect_lint_command()` - detect eslint, ruff, etc.
- Config: `clean_state.require_typecheck`, `clean_state.require_lint`

---

### 2. Command Allow/Denylist

**Gap**: 1.0-EXPECTATIONS.md (line 84) mentions:
> "explicit allowlist/denylist for commands (at least a denylist for dangerous operations)"

**Current State**: No command filtering exists. Harnesses run with full access.

**Recommendation**: Define specification for:
- Which commands are dangerous (rm -rf, git push --force, etc.)
- How to configure allow/denylist
- How to intercept/block commands (may require harness cooperation)

---

### 3. Plan-Only Full Mode

**Gap**: 1.0-EXPECTATIONS.md (line 85) mentions:
> '"plan-only" mode that never edits files'

**Current State**: `--plan` exists but is separate mode, not a modifier for `--once` or continuous runs.

**Recommendation**: Define whether plan-only should:
- Work with the main loop (read-only task execution)
- Or remain a separate analysis command

---

### 4. Session Context Continuation

**Gap**: 1.0-ROADMAP.md (line 22) mentions:
> "explore whether/when to use --continue with an existing session"

**Current State**: No session continuation exists. Each run starts fresh.

**Recommendation**: Define specification for:
- How to detect remaining context window
- Session state persistence format
- Safety considerations for continued sessions

---

### 5. Concurrency and Collision Behavior

**Gap**: 1.0-EXPECTATIONS.md (line 117-119) mentions:
> "Concurrency should be explicit: default single-worker, if multiple workers exist, define collision behavior"

**Current State**: No concurrency support. No collision detection.

**Recommendation**: Define specification for:
- Session locking mechanism
- Task claiming protocol (prevent double-assignment)
- Artifact directory collision handling

---

### 6. Task State Machine Alignment

**Gap**: 1.0-EXPECTATIONS.md (line 48) expects states:
> "todo, in_progress, blocked, done, failed, skipped"

**Current State**: prd.json uses: `open`, `in_progress`, `closed`

**Recommendation**: Align on state names:
- Map `todo` -> `open` (documented)
- Add `blocked` state (currently inferred from dependencies)
- Add `failed` state (currently stays in_progress)
- Add `skipped` state (for filtered/excluded tasks)

---

## Test Coverage Gaps

The following areas have insufficient test coverage:

| Area | Current Tests | Gap |
|------|---------------|-----|
| Beads backend | 0 | No dedicated beads.bats |
| OpenCode harness | 0 | Not tested despite being in capability matrix |
| Gemini harness | Minimal | Streaming not tested |
| Performance/stress | 0 | No tests with 1000+ tasks |
| Concurrency | 0 | No multi-session tests |
| Recovery/rollback | 0 | No crash recovery tests |

---

## Implementation Order (Dependency Graph)

```
Phase 3 (Git Workflow) - CURRENT PRIORITY
├── curb-021: Create lib/git.sh
├── curb-022: git_init_run_branch
├── curb-023: git_commit_task
├── curb-024: git helpers
├── curb-025: --push flag (depends on 021-024)
├── curb-026: Main loop integration (depends on 021-024)
├── curb-027: Tests (depends on 021-024)
└── curb-028: CHECKPOINT

Phase 4 (Guardrails) - AFTER PHASE 3
├── curb-029: Iteration tracking
├── curb-030: Budget functions
├── curb-031: Secret redaction
├── curb-032: Logger timestamps
├── curb-033: Config schema
├── curb-034: Loop integration
├── curb-035: Tests
└── curb-036: CHECKPOINT

Phase 5 (Failure Handling) - AFTER PHASE 4
├── curb-037: lib/failure.sh
├── curb-038: stop/move-on modes
├── curb-039: retry mode
├── curb-040: Loop integration
├── curb-041: cmd_explain
├── curb-042: Tests
└── curb-043: CHECKPOINT

Phase 6 (Polish) - AFTER PHASE 5
├── curb-044: pre-loop branch hook
├── curb-045: post-loop PR hook
├── curb-046: Debug output
├── curb-047: Acceptance parsing
├── curb-048: UPGRADING.md
├── curb-049: README.md
├── curb-050: Beads assignee
├── curb-051: Final tests
└── curb-052: 1.0 RELEASE CHECKPOINT
```

---

## Quick Wins (Low Effort, High Value)

1. **Fix --push stub** (curb:385-386) - Remove warning, implement basic git push
2. **Add pre-loop/pre-task example hooks** - Complete the examples set
3. **Test Gemini CLI streaming** - May work in newer versions
4. **Document task state mapping** - Clarify open/todo, closed/done naming

---

## Files Reference

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `curb` | ~1600 | Main script | Mostly complete |
| `lib/harness.sh` | 790 | Harness abstraction | 2 TODOs (streaming) |
| `lib/tasks.sh` | 667 | Task backend | Complete |
| `lib/artifacts.sh` | 761 | Artifact management | Complete |
| `lib/state.sh` | 280 | Git state verification | Needs git.sh extraction |
| `lib/hooks.sh` | 285 | Hook framework | Complete |
| `lib/budget.sh` | 240 | Budget tracking | Needs iteration tracking |
| `lib/logger.sh` | 280 | JSONL logging | Needs redaction |
| `lib/session.sh` | 160 | Session management | Complete |
| `lib/config.sh` | 200 | Configuration | Complete |
| `lib/beads.sh` | 200 | Beads wrapper | Complete |
| `lib/xdg.sh` | 100 | XDG directories | Complete |
| `lib/git.sh` | 0 | Git workflow | **NOT CREATED** |
| `lib/failure.sh` | 0 | Failure handling | **NOT CREATED** |

---

## Summary

**Total Open Tasks in Beads**: 44 tasks across 6 epics

**Critical Path to 1.0**:
1. Complete Phase 3 (Git Workflow) - 8 tasks
2. Complete Phase 4 (Guardrails) - 8 tasks
3. Complete Phase 5 (Failure Handling) - 7 tasks
4. Complete Phase 6 (Polish) - 9 tasks
5. Final checkpoint (curb-052)

**Estimated Scope**: 32 tasks remaining for full 1.0 feature set

**Risks**:
- Gemini/OpenCode streaming may require upstream CLI fixes
- Command allow/denylist may require harness-level changes
- Concurrency support is complex and may slip to post-1.0
