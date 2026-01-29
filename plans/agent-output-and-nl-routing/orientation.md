# Orient Report: Agent Output and Natural Language Routing

**Date:** 2026-01-29
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

Make cub's CLI output optimized for LLM consumption via an `--agent` flag, and upgrade the `/cub` natural language router to use this output and learn from usage over time. This enables Claude to give noticeably better responses when developers use `/cub` in direct sessions -- with accurate dependency analysis, actionable recommendations, and no confabulation.

## Problem Statement

When Claude runs cub commands via `/cub`, it receives Rich-formatted terminal output designed for humans. This output wastes tokens, lacks analysis context, and forces Claude to guess at relationships between tasks. The result: Claude's responses about project status are less useful than they could be. Developers using cub in direct Claude Code sessions have this problem.

## Refined Vision

Three separable pieces shipping incrementally:

1. **`--agent` output flag** — Structured markdown output for key CLI commands, with pre-computed analysis hints (dependency impact, bottlenecks, recommendations). Per-command flag, not global.
2. **Passthrough skill updates** — Update existing skill files to use `--agent` flag in their Bash invocations.
3. **Route learning** — Hook-based observation of command usage + background compilation of frequency data, surfaced to the router via file reference.

Each piece delivers value independently. The design principle: deterministic infrastructure (hooks observe, code computes, files surface), LLM judgment only for interpretation.

## Requirements

### P0 - Must Have

- **`--agent` flag on Phase 1 commands** — `cub task ready`, `cub task show`, `cub status`, `cub suggest`. Each produces structured markdown under 500 tokens with summary line, data tables, truncation notices, and analysis section.
- **AgentFormatter** — Centralized formatting module (`core/services/agent_format.py`) that renders command data as LLM-optimized markdown following the envelope template.
- **DependencyGraph availability** — The `--agent` analysis hints for task commands depend on a DependencyGraph class. This is being built as part of the task parity spec (`cub-task-parity`). This spec depends on that work landing first for `task ready` and `task show` analysis sections.
- **Passthrough skill updates** — Update the 7 existing passthrough skills to include `--agent` in their Bash invocations.

### P1 - Should Have

- **Route observation** — PostToolUse hook logs every `cub *` command to `.cub/route-log.jsonl`. 4 lines of shell in `cub-hook.sh`.
- **Route compilation** — `cub routes compile` reads the log, groups by normalized command, filters noise (count < 3), writes `.cub/learned-routes.md`. Triggered by Stop hook.
- **Route surfacing** — Router skill (`.claude/commands/cub.md`) references learned routes as a tiebreaker for ambiguous intent.
- **Phase 2 commands** — `cub task blocked --agent`, `cub task list --agent`, `cub ledger show --agent` (after task parity lands).

### P2 - Nice to Have

- **Phase 3 commands** — `cub doctor --agent` (requires doctor refactor to return structured data instead of printing directly), `cub audit --agent`.
- **Token budget validation test** — Automated test asserting character count < 2000 for representative inputs.
- **Route log rotation** — Truncation or rotation strategy for `.cub/route-log.jsonl` in long-lived projects.

## Constraints

- **DependencyGraph dependency**: The most valuable analysis hints (impact scoring, root blockers, chain listing) require the `DependencyGraph` class. This is being built in the task parity spec. `--agent` output for task commands will have reduced analysis without it. Decision: build the formatter methods to accept an optional graph parameter — output works without it (no analysis section) and improves when graph becomes available.
- **Per-command flag**: `--agent` is added to each supporting command individually, not as a global app flag. This keeps the CLI clean — unsupported commands don't show the option.
- **`--agent` and `--json` are mutually exclusive**: `--agent` wins silently if both are passed.

## Assumptions

- Claude reliably reads `@`-referenced files (estimated ~95% based on project experience). Route learning depends on this for surfacing compiled routes.
- The 1 token ≈ 4 chars heuristic is accurate enough for markdown. The spec's examples range 150-300 tokens, well within the 500-token budget.
- Task lists remain small (<500 items). DependencyGraph is built fresh per invocation — no caching needed.
- The existing `cub-hook.sh` fast-path filter can be extended with minimal latency impact (adding 4 lines of shell).

## Open Questions / Experiments

- **Truncation threshold**: Show all items if ≤ 15, truncate to 10 with notice if > 15. → Experiment: try this default, adjust based on real output token counts during validation.
- **Claude's treatment of analysis hints**: Will Claude echo them helpfully or parrot blindly? → Experiment: the 10+ invocation validation plan in the spec. Adjust skill instructions based on results.
- **Route learning value**: Will command frequency data actually improve routing? → Experiment: ship it, observe whether learned routes correlate with better `/cub` responses over 2-4 weeks.
- **Daemon for background work**: Route compilation currently runs at session end (Stop hook). A daemon could compile continuously and handle other background tasks. → Separate spec to explore daemon architecture.

## Out of Scope

- MCP server for cub (separate future spec)
- Velocity/trajectory/ETA computation (no time-series data collected)
- Effort estimation for tasks (no complexity signal)
- Phrase-level route learning (deferred — start with command frequency)
- Route decay / time-weighted frequency (not needed initially)
- Daemon architecture (flagged for companion spec)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| DependencyGraph delays task parity | H | AgentFormatter works without graph (reduced analysis). Phase 1 can ship with flat task lists. |
| Claude ignores or parrots analysis hints | M | Validation plan (10+ invocations). Adjust skill instructions. Analysis is "informational, not authoritative." |
| Route log grows unbounded | L | Add rotation in P2. Projects typically generate <100 commands/day. |
| Doctor refactor for Phase 3 is larger than expected | L | Phase 3 is optional. Doctor works fine without --agent. |
| --agent output exceeds token budget for large projects | M | Truncation with explicit notices. Default 10-15 items. Test with real data. |

## MVP Definition

Full implementation of all three parts:

1. **`--agent` flag** on Phase 1 commands (task ready, task show, status, suggest) with AgentFormatter
2. **Passthrough skill updates** to use `--agent` in Bash invocations
3. **Route learning** pipeline (observe via hook → compile at session end → surface in router skill)

DependencyGraph integration follows when task parity spec delivers it. Until then, `--agent` output works but without the dependency analysis hints.

## Dependency Map

```
cub-task-parity (DependencyGraph)
       │
       ▼
agent-output Phase 1 ──→ Phase 2 ──→ Phase 3
(--agent flag,           (blocked,    (doctor refactor)
 AgentFormatter,          list,
 skill updates)           ledger)
       │
       ▼
route learning
(hook observation,
 compilation,
 router surfacing)
```

---

**Next Step:** Run `cub architect` to design the technical architecture.
