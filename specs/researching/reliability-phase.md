---
status: researching
priority: high
complexity: medium
dependencies:
  - foundation-phase
blocks: []
created: 2026-01-26
updated: 2026-01-26
readiness:
  score: 8
  blockers: []
  questions:
    - How to detect session start in direct harness mode?
  decisions_needed: []
  tools_needed: []
---

# Reliability Phase (0.30 Alpha)

## Overview

Make cub trustworthy for unattended operation and compatible with direct harness use. Three pillars: rock-solid core loop that won't crash or corrupt state, hang detection to prevent overnight runs wasting hours on stuck tasks, and unified tracking so work is captured in the audit trail regardless of whether it came from `cub run` or a direct harness session.

## Goals

- **Core Loop Hardening (E4):** `cub run` is crash-proof with clean exits on all paths—Ctrl+C, budget exhaustion, iteration limits, task failures. Artifacts created even on interrupt.

- **Circuit Breaker (E5):** Time-based hang detection prevents runs from burning hours overnight on stuck harnesses. Simple MVP: if nothing happens for N minutes, trip the breaker. Also provide prompt-level instruction so agents know they can give up if stuck.

- **Symbiotic Workflow (E6):** Harness instrumentation enables unified audit trail. When users run Claude Code (or other harnesses) directly, cub hooks provide instructions for the harness to track work via cub commands. Ledger records and run-sessions get created regardless of entry point. Harness-agnostic design.

## Non-Goals

- **Sophisticated stagnation detection:** Semantic analysis of agent loops, repeated file modifications, error pattern recognition—that's future work. Start with simple time-based detection.

- **Forcing all work through `cub run`:** The symbiotic approach is about incremental adoption. Users can use cub for some work and harnesses directly for other work. Cub stays useful either way.

- **Perfect reconciliation of pre-existing work:** Focus is forward-looking. Users who've been using harnesses directly before adding cub don't need their history backfilled.

## Design / Approach

### E4: Core Loop Hardening

The sketch has solid acceptance criteria:
- `cub run --once` completes without crash on happy path
- `cub run` (multi-task) completes or exits cleanly at budget
- Ctrl+C during run/plan exits cleanly, no data corruption
- Budget exhaustion stops run with clear message
- Iteration limit stops run with clear message
- Task failure handled gracefully (logged, continues or stops per config)
- Artifacts created even on failure/interrupt

Primary work: integration tests for all exit paths, signal handling verification, manual testing.

### E5: Circuit Breaker

**MVP Approach:** Time-based hang detection.

1. Monitor harness subprocess for activity (output, completion)
2. If no activity for configurable timeout (default TBD—30-60 min), trip breaker
3. Clear message: "Harness appears hung (no activity for N minutes). Stopping run."
4. Configurable in cub.toml: `circuit_breaker.timeout_minutes`
5. CLI flag: `--no-circuit-breaker` to disable

**Prompt-level escape hatch:** Add instruction to task prompt template letting agents know they can signal "giving up" if stuck. This complements the time-based detection.

**Signal sources:** Harness logs provide visibility into subprocess state. Can distinguish "actually stuck" from "legitimately working on long operation."

### E6: Symbiotic Workflow

**Success Criteria:** A user can launch Claude Code directly and say "let's implement this new feature" OR use `cub spec/plan/run`—and get the same artifacts in the task list, ledger, and code.

**Core Principle:** CLI commands as the integration layer, not MCP. The harness follows instructions to run `bd` and `cub` commands directly. All logic stays in cub's codebase—deterministic, same code paths whether via `cub run` or direct session.

**Approach:** Instruction files (CLAUDE.md + AGENTS.md) plus hooks.

When a user runs Claude Code (or Codex, OpenCode) directly in a cub-enabled project:
1. Harness reads CLAUDE.md/AGENTS.md with cub workflow instructions
2. Instructions guide harness to use existing `bd` and `cub` commands for task tracking
3. Hooks capture artifacts (plan files, session logs) that would normally be created by `cub run`
4. Result: unified audit trail, same artifacts regardless of entry point

**Key properties:**
- **CLI-native:** No MCP mediation needed—same repo, same machine, just run commands
- **Harness-agnostic:** AGENTS.md works with Codex and OpenCode; CLAUDE.md for Claude Code
- **Same code paths:** Direct sessions call the same `bd close`, `cub ledger add` as `cub run`
- **Incremental adoption:** Users can mix `cub run` and direct harness use freely

**Artifact Parity:**

| Artifact | Via `cub run` | Via Direct Session |
|----------|---------------|-------------------|
| Task status updates | Automatic | Agent runs `bd update`, `bd close` |
| Ledger entries | Automatic | Agent runs `cub ledger add` |
| Run session logs | Created by cub | Hook or agent creates |
| Plan files | Stored in `plans/` | Hook captures from plan mode |
| Git commits | Made by agent | Made by agent (same) |

**Plan File Capture:**
When Claude Code uses plan mode, we want to capture those plans in `plans/`.

*Research findings:* ExitPlanMode hook exists via `PermissionRequest` matcher, but has known bugs ([#15755](https://github.com/anthropics/claude-code/issues/15755), [#5036](https://github.com/anthropics/claude-code/issues/5036)) where "Allow" doesn't properly exit plan mode.

**Recommended approach (hybrid):**

1. **Primary — CLAUDE.md instruction** (reliable):
   ```markdown
   ## Plan Mode
   When creating implementation plans, save them to:
   `plans/<descriptive-name>/plan.md`
   ```

2. **Secondary — ExitPlanMode hook** (stretch, given bugs):
   ```json
   {
     "hooks": {
       "PermissionRequest": [
         {
           "matcher": "ExitPlanMode",
           "hooks": [{
             "type": "command",
             "command": "$CLAUDE_PROJECT_DIR/.cub/hooks/capture-plan.sh"
           }]
         }
       ]
     }
   }
   ```
   Hook receives `transcript_path` (JSONL with plan content) that could be parsed.

3. **Fallback — PostToolUse on Write** (if agent writes plan file):
   Watch for writes to `plans/` directory, log to ledger.

**AGENTS.md Generation:**
Generate AGENTS.md alongside CLAUDE.md for cross-harness compatibility. Most tools have consolidated on AGENTS.md as the standard (OpenAI repo has 88 of them). CLAUDE.md can point to AGENTS.md or include Claude-specific additions.

## Implementation Notes

### E4 Implementation

- Expand integration test coverage for run loop
- Test signal handling (SIGINT, SIGTERM) explicitly
- Verify artifact creation on all exit paths
- Consider `pytest-timeout` for test reliability

### E5 Implementation

- Add timeout monitoring to harness subprocess management
- Hook into existing logging to detect activity
- Add config schema for circuit breaker settings
- Add `--no-circuit-breaker` flag to `cub run`

### E6 Implementation

**Phase 1: Instruction Files**
- Enhance CLAUDE.md with direct session workflow instructions
- Generate AGENTS.md for Codex/OpenCode compatibility
- Document which `bd` and `cub` commands to use and when
- Add "When Running Directly" section with task tracking workflow

**Phase 2: Hook Integration**
- Research ExitPlanMode hook availability in Claude Code
- Implement plan file capture hook (copy to `plans/` directory)
- Consider session start/end detection via hooks
- Test artifact parity between `cub run` and direct session

**Phase 3: Session Context (stretch)**
- Detect cub-enabled project on harness start
- Auto-inject relevant context (recent tasks, ledger entries)
- Surface available work (`bd ready` output) in initial context

**Commands for Direct Sessions:**
```markdown
## When Running Directly (not via cub run)

This project uses cub for task management. To keep work tracked:

1. **Find available tasks:** `bd ready`
2. **Claim a task:** `bd update <id> --status=in_progress`
3. **When done:** `bd close <id> --reason="brief description"`
4. **Log session:** `cub ledger add --notes="what you accomplished"`

If creating a plan, save it to `plans/<descriptive-name>/plan.md`
```

## Open Questions

1. **Session boundaries:** In direct harness use, how does cub know when a "session" starts and ends for logging purposes? Options: explicit `cub session start/end`, git commit as proxy, or just log individual actions without session grouping.

2. **AGENTS.md placement:** Root only, or hierarchical (subdirs for monorepos)? Follow the pattern where "agents automatically read the nearest file in the directory tree."

## Resolved Decisions

- **Integration mechanism:** CLI commands, not MCP. Same code paths as `cub run`.
- **Instruction files:** Both CLAUDE.md and AGENTS.md for cross-harness compatibility.
- **Tracking commands:** Use existing `bd` and `cub` commands—no new commands needed.
- **Circuit breaker timeout:** 30 minutes of no activity as default. Configurable via `circuit_breaker.timeout_minutes`.
- **Plan file capture:** Primary via CLAUDE.md instruction (agent saves to `plans/`). ExitPlanMode hook exists but has bugs—use as stretch goal only.

## Future Considerations

- **Semantic stagnation detection:** Analyze agent output for repeated errors, same-file loops, "I'm stuck" statements. More sophisticated than time-based.

- **Cost tracking in direct mode:** If harness reports token usage, capture it in ledger even for direct sessions.

- **MCP integration (Tier 2):** Expose cub commands via MCP server for richer integration. Not needed for same-machine workflows, but could enable remote orchestration or IDE integration.

- **Multi-agent coordination (Tier 3):** Claude-squad style parallel execution, Agent-Fusion style intelligent handoffs between harnesses.

- **Session context injection:** Auto-surface recent tasks and ledger entries when harness starts in cub project.

## Research Context

This design is informed by landscape research on symbiotic workflow tools:

**Existing tools in this space:**
- [claude-squad](https://github.com/jqueryscript/awesome-claude-code) (5.6k ⭐) — manages multiple AI terminal agents
- [Agent-Fusion](https://github.com/jqueryscript/awesome-claude-code) — cross-harness collaboration
- [Task Orchestrator](https://github.com/jpicklyk/task-orchestrator) — MCP-based persistent memory
- [MemContext](https://memcontext.in/) — cross-tool memory layer

**Key patterns adopted:**
- AGENTS.md as tool-agnostic standard (CLAUDE.md for Claude-specific)
- CLI commands as integration layer (same code paths)
- Ledger as session handoff format
- Hooks for artifact capture

---

**Status**: researching
**Last Updated**: 2026-01-26
**Readiness**: 8/10 — E4 well-defined, E5/E6 approach clear with key decisions resolved
