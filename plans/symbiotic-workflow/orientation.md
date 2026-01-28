# Orientation: Symbiotic Workflow

**Date:** 2026-01-28
**Depth:** Light (requirements already explored via spec interview)
**Status:** Approved

---

## Problem Statement

When someone works directly in a harness (Claude Code, Codex, etc.) instead of through `cub run`, cub has no visibility into what happened. Tasks aren't tracked, plans aren't captured, ledger entries aren't created. This creates learning degradation (incomplete data), capability asymmetry (tools only available one way), and cognitive overhead (choosing between modes).

## Target User

Developers already familiar with AI coding tools (Claude Code, Cursor, Codex) who are drawn to reducing the pitfalls of agent-assisted development. They won't change their workflow to use cub -- cub must wrap around their existing workflow.

## Core Requirements

1. **Implicit tracking** -- work gets recorded as a side effect of normal activity, not via manual commands
2. **Mode fluidity** -- alternating between `cub run` and direct sessions should feel like switching vim modes
3. **Holistic repo** -- code, docs, tests, specs, plans, runs, ledger, and prompts all checked in
4. **Multiple task entry points** -- structured pipeline, conversational, and ad-hoc task creation
5. **JSON backend as primary** -- drop-in for beads, running in "both" mode during migration
6. **Claude Code first** -- harness-agnostic architecture, Claude Code hooks as v1 implementation

## Key Constraints

- Production mindset (quality-first, tested, maintainable)
- Personal scale (1-10 users for alpha)
- Hook latency must not degrade the interactive Claude Code experience
- Must not clobber existing `.claude/settings.json` content
- Eventual consistency is acceptable (no real-time cost tracking)
- Compaction == new session (no cross-compaction stitching)

## Success Criteria

Someone works on a project for a day, alternating between `cub run` and direct Claude Code sessions. At end of day, `cub status` and the ledger show a coherent picture: tasks created/claimed/completed, plans produced, files changed -- regardless of which mode produced the work.

## Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Double-tracking prevention | Remove hook tracking from Claude harness in `cub run` | Simpler than flag detection; hooks are for direct sessions only |
| Session boundaries | Compaction == new session | Comprehensive logging within sessions; boundaries are acceptable |
| Plan format | Accept Claude's format as-is in v1 | Translation step deferred; reduce scope |
| Task association | Skill/AGENTS.md guidance + prompt detection + confirmation | Multiple fallbacks for different workflows |
| Transcript access | Fair game for ledger enrichment | This is the point of the app |
| Hook performance | Shell fast-path filter before Python | Keeps 90%+ of tool uses under 50ms |

## Risks Identified

- Shell JSON parsing fragility (mitigate: jq with fallback)
- `.claude/settings.json` merge conflicts (mitigate: defensive merge, doctor validation)
- JSON backend semantic drift from beads (mitigate: "both" mode parallel execution)

## References

- Spec: `specs/researching/symbiotic-workflow.md`
- Architecture: `plans/symbiotic-workflow/architecture.md`
- Prior art: `sketches/harness-usage-map.md`, `sketches/0.30-epics.md` (E6: Symbiotic Workflow Spike)
- Existing code: `src/cub/core/harness/hooks.py`, `src/cub/core/ledger/integration.py`
