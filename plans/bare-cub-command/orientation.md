# Orient Report: Bare Cub Command & In-Harness Mode Fluidity

**Date:** 2026-01-28
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

Make `cub` the unified front door for AI-assisted development by launching the default harness with opinionated project-aware guidance, enabling seamless mode transitions within a session, and cleaning up the core/interface boundary so the same logic works from CLI, harness skills, web, and future interfaces.

## Problem Statement

Cub's value—task structure, planning artifacts, project awareness, smart suggestions—is invisible when developers work directly in a harness. There's no unified entry point that routes you intelligently based on project state. Developers default to opening their harness directly, bypassing cub's structure, and switching between cub-managed and direct work requires exiting one context and entering another.

## Refined Vision

Bare `cub` becomes the natural way to start working. It launches Claude Code with an opinionated welcome: project stats, a recommended next action with rationale, and awareness of available modes. From within the session, all cub capabilities are accessible as skills or commands without leaving. `cub run` can execute tasks in the foreground (single) or background (batch). The architectural foundation—a clean core/interface split—ensures this works consistently across CLI, harness, and future interfaces.

## Requirements

### P0 - Must Have

- **Bare `cub` launches default harness** (Claude Code) with project context and opinionated guidance
- **`--resume` and `--continue` flags** pass through to harness for session continuity
- **Nesting detection**: bare `cub` inside an existing harness session shows inline status, doesn't nest
- **Smart suggestions engine**: analyzes tasks, ledger, git state, and milestones to recommend specific next action with rationale
- **Core/interface refactor**: separate business logic from CLI/interface concerns so skills and future interfaces share code paths

### P1 - Should Have

- `/cub` meta-skill or equivalent that surfaces available cub skills within a harness session
- `cub run --once` from within harness: foreground execution with status polling
- `cub run --epic X` from within harness: background execution, user checks status later
- Planning skills (`/cub:orient`, `/cub:spec`, etc.) documented in welcome guidance

### P2 - Nice to Have

- Suggestion ranking tunable per project (weights for priority, momentum, complexity)
- Welcome message customizable via `.cub/welcome.md` or config
- Session ID tracking for `--resume` integration (store last session ID)

## Constraints

- **Claude Code only** for interactive mode in alpha. Other harnesses for `cub run` autonomous only.
- **No daemon.** Background task execution uses existing subprocess patterns.
- **Python 3.10+**, consistent with existing codebase requirements.

## Assumptions

- Claude Code's CLI supports passing context via system prompt or CLAUDE.md is sufficient
- Environment variables propagate to Bash tool calls within Claude Code (for nesting detection)
- Existing `/cub:*` skills work within harness sessions launched by bare `cub`
- The core/interface split can be done incrementally without breaking existing CLI behavior

## Open Questions / Experiments

- **Suggestion quality:** How good are heuristics at recommending the right next action? → Experiment: build the engine, dogfood it on cub itself, iterate on ranking
- **Resume mechanics:** Can we reliably retrieve/store Claude Code session IDs? → Experiment: test `--resume` flag passthrough
- **Core boundary inventory:** How much CLI-specific logic has leaked into `cub.core`? → Investigation: audit before planning refactor scope

## Out of Scope

- Daemon/background service (post-alpha)
- Non-Claude-Code interactive harness support
- Complete intermediary layer over harnesses
- MCP tool exposure for cub operations (future interface, not alpha)
- Web dashboard as an interface to core (already partially exists, but not part of this work)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Core refactor scope grows | H | Time-box the refactor; flag violations but only fix what's in the critical path |
| Suggestion engine gives bad advice | M | Start simple (stale epics, ready tasks), add sophistication iteratively |
| Nesting detection fragile across OS/shells | M | Use multiple signals (env var + process tree) not just one |
| `--resume` passthrough breaks across Claude Code versions | L | Degrade gracefully—if resume fails, start fresh session |

## MVP Definition

Full mode fluidity: bare `cub` entry point + opinionated welcome with smart suggestions + in-harness skill discovery + `cub run` foreground/background from within session + nesting prevention + core/interface separation. The full spec, not a subset.

## Success Criteria

1. **Muscle memory shifts**: Developer types `cub` instead of `claude` as their natural entry point
2. **Mode transitions feel invisible**: Moving from planning to coding to reviewing happens without thinking about which tool to use
3. **New users find their way**: Someone who installs cub and types `cub` immediately understands what to do next

---

**Next Step:** Run `cub architect` to design the technical architecture.
