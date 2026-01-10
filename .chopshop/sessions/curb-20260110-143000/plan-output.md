# Implementation Plan: Curb 1.0

**Session:** curb-20260110-143000
**Generated:** 2026-01-10
**Granularity:** Micro (15-30 min tasks)
**Total:** 6 epics, 52 tasks

---

## Summary

This plan delivers curb 1.0 across six phases, each ending with a validation checkpoint. The implementation proceeds bottom-up: foundation modules first (session identity, artifact bundles), then CLI restructuring to subcommands, followed by git workflow automation, safety guardrails, failure handling, and final polish.

Each task is sized for AI agent execution in one context window (~15-30 minutes). Tasks include detailed implementation steps, acceptance criteria, and model recommendations for optimal cost/quality balance.

---

## Task Hierarchy

### Epic 1: Foundation - Session + Artifacts [P0]
*Goal: Observable runs with structured output*

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-001 | Create lib/session.sh with animal wordlist | haiku | P0 | - | 25m |
| curb-002 | Implement session_init and session_get_* functions | haiku | P0 | curb-001 | 20m |
| curb-003 | Create lib/artifacts.sh with directory structure helpers | sonnet | P0 | curb-002 | 30m |
| curb-004 | Implement artifacts_init_run and artifacts_start_task | sonnet | P0 | curb-003 | 25m |
| curb-005 | Implement artifacts_capture_* functions | sonnet | P0 | curb-004 | 30m |
| curb-006 | Implement artifacts_finalize_task and summary generation | sonnet | P0 | curb-005 | 25m |
| curb-007 | Add curb version subcommand (establish dispatcher pattern) | haiku | P0 | - | 15m |
| curb-008 | Write BATS tests for lib/session.sh | haiku | P1 | curb-002 | 25m |
| curb-009 | Write BATS tests for lib/artifacts.sh | sonnet | P1 | curb-006 | 30m |
| curb-010 | Integrate session and artifacts into main loop | sonnet | P0 | curb-006, curb-007 | 30m |
| curb-011 | **CHECKPOINT**: Verify artifact bundle generation end-to-end | sonnet | P0 | curb-010 | 20m |

---

### Epic 2: CLI Restructuring [P0]
*Goal: Consistent subcommand interface*

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-012 | Create subcommand dispatcher in curb entry point | sonnet | P0 | curb-007 | 30m |
| curb-013 | Extract main loop logic into cmd_run function | sonnet | P0 | curb-012 | 30m |
| curb-014 | Move curb-init logic into cmd_init | sonnet | P0 | curb-012 | 30m |
| curb-015 | Implement cmd_status (migrate from --status flag) | sonnet | P1 | curb-012 | 25m |
| curb-016 | Implement cmd_artifacts to show task artifact paths | haiku | P1 | curb-012, curb-006 | 20m |
| curb-017 | Add deprecation warnings for legacy flag syntax | haiku | P1 | curb-013 | 20m |
| curb-018 | Update help text for subcommand CLI | haiku | P1 | curb-014 | 25m |
| curb-019 | Write BATS tests for CLI dispatcher and routing | sonnet | P1 | curb-014 | 30m |
| curb-020 | **CHECKPOINT**: Verify all subcommands work correctly | sonnet | P0 | curb-019 | 20m |

---

### Epic 3: Git Workflow [P0]
*Goal: Branch per run, commit per task*

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-021 | Create lib/git.sh and extract git functions from state.sh | sonnet | P0 | curb-011 | 30m |
| curb-022 | Implement git_init_run_branch with naming convention | sonnet | P0 | curb-021 | 25m |
| curb-023 | Implement git_commit_task with structured message format | sonnet | P0 | curb-022 | 25m |
| curb-024 | Implement git_has_changes and git_get_run_branch helpers | haiku | P0 | curb-021 | 20m |
| curb-025 | Add --push flag and git_push_branch (explicit opt-in) | sonnet | P1 | curb-023 | 25m |
| curb-026 | Integrate git workflow into main loop | sonnet | P0 | curb-023, curb-024 | 30m |
| curb-027 | Write BATS tests for lib/git.sh | sonnet | P1 | curb-026 | 30m |
| curb-028 | **CHECKPOINT**: Verify branch-per-run, commit-per-task workflow | sonnet | P0 | curb-027 | 20m |

---

### Epic 4: Guardrails + Safety [P1]
*Goal: Iteration limits and safe defaults*

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-029 | Add iteration tracking to budget.sh | sonnet | P1 | curb-020 | 30m |
| curb-030 | Implement budget_check_* and budget_increment_* functions | sonnet | P1 | curb-029 | 25m |
| curb-031 | Add logger_redact function with secret patterns | sonnet | P1 | - | 30m |
| curb-032 | Add logger_stream with timestamps | haiku | P1 | curb-031 | 20m |
| curb-033 | Add config schema for guardrails | haiku | P1 | curb-029 | 20m |
| curb-034 | Integrate iteration limits into main loop | sonnet | P1 | curb-030, curb-033 | 25m |
| curb-035 | Write BATS tests for iteration tracking and secret redaction | sonnet | P1 | curb-034, curb-032 | 30m |
| curb-036 | **CHECKPOINT**: Verify guardrails prevent runaway loops | sonnet | P1 | curb-035 | 20m |

---

### Epic 5: Failure Handling [P1]
*Goal: Configurable failure modes*

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-037 | Create lib/failure.sh with mode enum and failure_get_mode | haiku | P1 | curb-036 | 20m |
| curb-038 | Implement stop and move-on failure modes | sonnet | P1 | curb-037 | 25m |
| curb-039 | Implement retry mode with counter and context passing | sonnet | P1 | curb-038 | 30m |
| curb-040 | Integrate failure handling into main loop | sonnet | P1 | curb-039 | 30m |
| curb-041 | Implement cmd_explain to show task failure reasons | sonnet | P1 | curb-040, curb-012 | 25m |
| curb-042 | Write BATS tests for failure modes | sonnet | P1 | curb-041 | 30m |
| curb-043 | **CHECKPOINT**: Verify failure handling works for all modes | sonnet | P1 | curb-042 | 20m |

---

### Epic 6: Polish [P2]
*Goal: Default hooks, debug enhancements, documentation*

| ID | Task | Model | Priority | Blocked By | Est |
|----|------|-------|----------|------------|-----|
| curb-044 | Create default pre-loop hook for automatic branch creation | haiku | P2 | curb-028 | 20m |
| curb-045 | Create default post-loop hook for PR prompt | sonnet | P2 | curb-044 | 25m |
| curb-046 | Add full harness command line to debug output | haiku | P2 | curb-020 | 15m |
| curb-047 | Implement acceptance criteria parsing from task descriptions | sonnet | P2 | curb-043 | 30m |
| curb-048 | Update UPGRADING.md with migration guide | haiku | P2 | curb-020 | 25m |
| curb-049 | Update README.md with new commands and features | haiku | P2 | curb-048 | 30m |
| curb-050 | Integrate beads assignee with session name | haiku | P1 | curb-002 | 20m |
| curb-051 | Final integration test pass | sonnet | P1 | curb-049 | 30m |
| curb-052 | **CHECKPOINT**: 1.0 release validation | sonnet | P0 | curb-051 | 25m |

---

## Dependency Graph

```
Phase 1 (Foundation):
curb-001 ─┬─> curb-002 ─┬─> curb-003 ─> curb-004 ─> curb-005 ─> curb-006 ─┬─> curb-009
          │             │                                                  │
          │             ├─> curb-008                                       ├─> curb-010 ─> curb-011 [CP1]
          │             │                                                  │
          │             └─> curb-050                                       │
          │                                                                │
curb-007 ─┴────────────────────────────────────────────────────────────────┘

Phase 2 (CLI):
curb-007 ─> curb-012 ─┬─> curb-013 ─> curb-017
                      ├─> curb-014 ─┬─> curb-018
                      │             └─> curb-019 ─> curb-020 [CP2]
                      ├─> curb-015
                      └─> curb-016

Phase 3 (Git):
curb-011 ─> curb-021 ─┬─> curb-022 ─> curb-023 ─┬─> curb-025
                      │                         │
                      └─> curb-024 ─────────────┴─> curb-026 ─> curb-027 ─> curb-028 [CP3]

Phase 4 (Guardrails):
curb-020 ─> curb-029 ─┬─> curb-030 ─┬─> curb-034 ─> curb-035 ─> curb-036 [CP4]
                      │             │
                      └─> curb-033 ─┘
curb-031 ─> curb-032 ─────────────────────────────┘

Phase 5 (Failure):
curb-036 ─> curb-037 ─> curb-038 ─> curb-039 ─> curb-040 ─> curb-041 ─> curb-042 ─> curb-043 [CP5]

Phase 6 (Polish):
curb-028 ─> curb-044 ─> curb-045
curb-020 ─> curb-046
curb-020 ─> curb-048 ─> curb-049 ─> curb-051 ─> curb-052 [CP6]
curb-043 ─> curb-047
```

---

## Model Distribution

| Model | Tasks | Rationale |
|-------|-------|-----------|
| opus-4.5 | 0 | No tasks require novel architectural decisions beyond designed spec |
| sonnet | 32 | Standard implementation: clear requirements, established patterns |
| haiku | 20 | Simple tasks: wordlists, helpers, config, documentation |

---

## Validation Checkpoints

### Checkpoint 1: curb-011 (after Phase 1)
**What's testable:** Artifact bundles generated for each task
**Key questions:**
- Are all artifact files present (task.json, plan.md, changes.patch, commands.jsonl, summary.md)?
- Is the session name appearing in run.json?
- Are permissions set correctly (700/600)?

### Checkpoint 2: curb-020 (after Phase 2)
**What's testable:** All subcommands work: `curb run`, `curb init`, `curb status`, `curb version`, `curb artifacts`
**Key questions:**
- Do deprecation warnings appear for old flag syntax?
- Does help text accurately describe new CLI?
- Does `curb-init` still work (backwards compatibility)?

### Checkpoint 3: curb-028 (after Phase 3)
**What's testable:** Branch created on run start, commit after each task
**Key questions:**
- Is branch naming correct (`curb/{session}/{timestamp}`)?
- Do commit messages include task IDs?
- Does `--push` work correctly?

### Checkpoint 4: curb-036 (after Phase 4)
**What's testable:** Iteration limits prevent runaway loops, secrets redacted
**Key questions:**
- Does exceeding max_task_iterations stop the task?
- Does exceeding max_run_iterations stop the run?
- Are API keys properly redacted in logs?

### Checkpoint 5: curb-043 (after Phase 5)
**What's testable:** Failure modes work (stop, move-on, retry)
**Key questions:**
- Does retry mode pass failure context back to agent?
- Does `curb explain <task>` show useful information?
- Does retry respect iteration limits?

### Checkpoint 6: curb-052 (1.0 Release)
**What's testable:** Full end-to-end workflow
**Key questions:**
- Does the happy path work smoothly?
- Is documentation complete and accurate?
- Are all P0 and P1 requirements met?

---

## Ready to Start

These tasks have no blockers:
- **curb-001**: Create lib/session.sh with animal wordlist [P0] (haiku) - 25m
- **curb-007**: Add curb version subcommand [P0] (haiku) - 15m
- **curb-031**: Add logger_redact function with secret patterns [P1] (sonnet) - 30m

---

## Critical Path

```
curb-001 → curb-002 → curb-003 → curb-004 → curb-005 → curb-006 → curb-010 → curb-011 [CP1]
                                                                        ↓
curb-007 → curb-012 → curb-013/014 → curb-019 → curb-020 [CP2] ←────────┘
                                                    ↓
curb-021 → curb-022 → curb-023 → curb-026 → curb-027 → curb-028 [CP3]
                                                    ↓
curb-029 → curb-030 → curb-034 → curb-035 → curb-036 [CP4]
                                                    ↓
curb-037 → curb-038 → curb-039 → curb-040 → curb-041 → curb-042 → curb-043 [CP5]
                                                                        ↓
curb-048 → curb-049 → curb-051 → curb-052 [CP6]
```

Estimated critical path duration: ~18-20 hours of agent work

---

## Next Steps

1. Review this plan
2. Load into beads: `bd import .chopshop/sessions/curb-20260110-143000/plan.jsonl`
3. Start work: `bd ready` or `curb run`

---

## Notes

- All tasks include detailed implementation steps and acceptance criteria in the JSONL file
- Model recommendations optimize for cost (haiku for simple) vs quality (sonnet for logic)
- Checkpoints are explicit tasks to ensure validation before proceeding
- Dependencies ensure correct build order while maximizing parallelism where possible
