# Orient Report: Reliability Phase (0.30 Alpha)

**Date:** 2026-01-26
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

Make cub trustworthy for unattended operation and compatible with direct harness use. Three pillars: rock-solid core loop that won't crash or corrupt state, hang detection to prevent overnight runs wasting hours on stuck tasks, and unified tracking so work is captured in the audit trail regardless of whether it came from `cub run` or a direct harness session.

## Problem Statement

Solo builders running overnight `cub run` sessions can't trust the loop—it might crash, hang for hours on a stuck task, or lose track of work they did directly in Claude Code. They need confidence that autonomous runs won't waste time/money and that all work gets captured regardless of entry point.

## Refined Vision

The reliability phase delivers three capabilities:
1. **Core Loop Hardening (E4):** `cub run` exits cleanly on all paths with artifacts preserved
2. **Circuit Breaker (E5):** Time-based hang detection stops wasted overnight runs
3. **Symbiotic Workflow (E6):** Direct harness sessions produce equivalent forensic records to `cub run`

## Requirements

### P0 - Must Have

1. **Clean exits on all paths (E4)** — `cub run` handles Ctrl+C, SIGTERM, budget exhaustion, iteration limits, and task failures without crash or data corruption. Artifacts created even on interrupt.

2. **Time-based circuit breaker (E5)** — If no harness activity for 30 minutes, trip breaker and stop run with clear message. Configurable via `circuit_breaker.timeout_minutes`. Disable with `--no-circuit-breaker`.

3. **Ledger capture for direct sessions (E6)** — When users run Claude Code/Codex/OpenCode directly, hooks + CLAUDE.md/AGENTS.md instructions ensure `.cub/ledger` and forensic files capture roughly equivalent records to `cub run`.

4. **Root-level AGENTS.md generation** — `cub init` creates AGENTS.md alongside CLAUDE.md for cross-harness compatibility.

### P1 - Should Have

5. **New `cub` commands for direct session tracking** — Commands that direct sessions can call (e.g., `cub session log`, `cub task done`) to record work. Design as needed.

6. **Hook-based artifact capture** — Research and implement Claude Code hooks (and equivalent for Codex/OpenCode) to capture plan files, session events without relying solely on agent following instructions.

7. **Prompt-level escape hatch** — Add instruction to task prompts letting agents signal "giving up" if stuck, complementing time-based detection.

### P2 - Nice to Have

8. **Session start/end detection via hooks** — If harness hooks support it, detect session boundaries automatically rather than requiring explicit commands.

9. **Plan file capture from ExitPlanMode** — If hooks work reliably, capture plans to `plans/` directory automatically.

## Constraints

- **CLI-native, cub-only** — Direct sessions call `cub` commands (not `bd`). Moving away from beads dependency.
- **Harness-agnostic (Claude Code, Codex, OpenCode)** — Gemini deferred.
- **Forward-looking only** — No backfilling history from pre-cub direct sessions.
- **Simple stagnation detection** — Time-based only for MVP. No semantic analysis.
- **Incremental adoption is key** — Users can mix `cub run` and direct harness freely. Critical for onboarding.
- **Hooks assumed reliable** — Proceed assuming Claude Code hooks work; verify during implementation.

## Assumptions

- 30-minute timeout is appropriate for protecting overnight/long-running sessions
- Users will follow CLAUDE.md/AGENTS.md instructions if the friction is low enough
- We can create the `cub` commands needed for direct session tracking
- Root-level AGENTS.md is sufficient (no monorepo hierarchy needed)

## Open Questions / Experiments

- **Session UX validation** → Experiment: Marc runs direct Claude Code/Codex sessions in cub-enabled project, verifies forensic capture feels natural. Iterate based on friction.
- **Hook reliability** → Experiment: Test Claude Code hooks for session/plan events during E6 implementation.

## Out of Scope

- Semantic stagnation detection (repeated errors, same-file loops, "I'm stuck" analysis)
- Gemini harness support
- Backfilling history from pre-cub sessions
- Hierarchical AGENTS.md for monorepos
- MCP-based integration
- Perfect session symmetry with harness concepts (focus on forensic equivalence)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hooks unreliable across harness versions | M | Primary reliance on CLAUDE.md instructions; hooks as enhancement |
| 30-min timeout too aggressive for legitimate long ops | L | Make configurable, document how to disable |
| Users don't follow direct-session instructions | M | Manual testing protocol with Marc; iterate on UX based on friction |
| `cub` commands for direct sessions not ready | H | Scope minimal command set; create what's needed for 0.30 |

## MVP Definition

The smallest useful reliability phase:
- E4: Ctrl+C + budget exhaustion exit cleanly, artifacts preserved
- E5: 30-minute timeout stops hung harness
- E6: CLAUDE.md/AGENTS.md instructions + hooks capture ledger entries from direct sessions

---

**Next Step:** Run `cub architect` to proceed to technical design.
