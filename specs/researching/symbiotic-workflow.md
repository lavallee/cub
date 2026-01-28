---
status: researching
priority: high
complexity: high
dependencies:
  - JSON task backend at feature parity with beads
  - Ledger system decoupled from cub run loop
  - Claude Code hooks API
blocks: []
created: 2026-01-28
updated: 2026-01-28
readiness:
  score: 6
  blockers:
    - JSON backend parity with beads not yet verified
    - LedgerIntegration tightly coupled to cub run loop
  questions:
    - What lightweight script approach for hook paths avoids full cub startup?
    - How does skill/AGENTS.md configuration guide task association in direct sessions?
    - What is the JSON backend's current gap list relative to beads?
  decisions_needed:
    - Remove hook-based tracking from Claude harness backend (vs. flag-based detection) to prevent double-tracking
    - Exact session boundary semantics (compaction == new session is the current leaning)
  tools_needed: []
---

# Symbiotic Workflow: Hook-Based Task and Ledger Integration

## Overview

Enable fluid movement between CLI-driven (`cub run`) and interactive harness sessions (Claude Code, etc.) by using hooks to implicitly track task creation, execution, and completion regardless of mode. The repo remains the holistic source of truth -- code, docs, tests, specs, plans, runs, ledger, and prompts -- with eventual consistency across all work modes.

The core analogy is vim modes: you don't think about whether you're in insert mode or normal mode as a fundamental choice. You switch fluidly, and the mode serves you. Similarly, someone should be able to alternate between `cub run` for batch work and direct Claude Code sessions for interactive work, and at the end of the day `cub status` and the ledger show a coherent picture of everything that happened.

## Problem

Today, when someone works directly in a harness (Claude Code, Codex, etc.) instead of through `cub run`, cub has no visibility into what happened. This creates three costs:

1. **Learning degradation** -- the system can't learn effectively from incomplete data. Patterns, costs, and outcomes are only partially captured.
2. **Capability asymmetry** -- tools and features (like task management, plan capture, ledger tracking) are available in one mode but not the other. As cub adds toolsmithing, this gap widens.
3. **Cognitive overhead** -- having to choose between modes and remember different workflows is friction that should not exist.

The target alpha audience -- developers already familiar with AI coding tools -- won't accept being told to stop using their tools directly. They need cub to wrap around their existing workflow, not replace it.

## Goals

- Tasks tracked automatically regardless of mode (CLI or direct harness), as a side effect of normal work
- Ledger entries created implicitly, not via manual commands (`cub session done` etc.)
- Plans and specs captured to standard repo directories (`plans/`, `specs/`, `captures/`) when produced in direct sessions
- Task creation works from inside a harness session via multiple entry points:
  - Structured pipeline (orient/architect/plan producing specs and tasks)
  - Conversational (open-ended sessions producing artifacts as a byproduct)
  - Ad-hoc ("I just thought of something" captured cleanly as a task)
- JSON task backend operates as drop-in replacement for beads, running in "both" mode during migration
- Claude Code's plan artifacts captured and checked into the repo
- Harness-agnostic architecture (Claude Code first, others follow same patterns)
- Lightweight hook scripts that don't require full cub startup on the hot path
- Eventual consistency between modes (not real-time synchronization)

## Non-Goals

- **Web dashboard integration** -- the dashboard will eventually consume this data, but building dashboard views is not part of this work
- **Real-time token/cost tracking** -- eventual consistency is sufficient; post-hoc transcript parsing is acceptable
- **Replacing Claude Code's built-in task system** -- coexist and augment. Claude Code's task system is machine-local and ephemeral; cub's repo-local approach provides portability and history. We capture what it can't persist.
- **Multi-harness hook support in v1** -- build the architecture to be harness-agnostic, but only implement Claude Code hooks initially
- **Plan format translation in v1** -- accept Claude's plan format as-is, add a translation step later
- **Stitching across compaction boundaries** -- compaction starts a new session record. Comprehensive logging within sessions; boundaries between sessions are acceptable discontinuities.

## Design / Approach

### Integration Surface: Claude Code Hooks

Claude Code provides hooks at key lifecycle points. We use these to observe and record work:

| Hook | Purpose in Symbiotic Workflow |
|------|-------------------------------|
| **SessionStart** | Create session record, inject project context (ready tasks, active epic) via `additionalContext` |
| **PostToolUse** (Write/Edit) | Detect writes to `plans/`, `specs/`, `captures/`, source files; associate with active task |
| **PostToolUse** (Bash) | Detect task commands (`cub` task operations, `git commit`); mirror state changes to ledger |
| **Stop** | Finalize session forensics; create/update ledger entry if task was claimed |
| **PreCompact** | Checkpoint session state before context is lost (compaction == new session) |
| **UserPromptSubmit** | Detect task ID mentions; inject task context as `additionalContext` |

### Architecture Layers

```
.claude/settings.json (hook configuration)
  |
  v
Lightweight shell scripts (.cub/scripts/hooks/)
  |-- fast-path checks (is this relevant? is cub-run active?)
  |-- invoke Python only when needed
  |
  v
cub.core.harness.hooks (enhanced Python handlers)
  |-- SessionStart: create forensics record, return project context
  |-- PostToolUse: log artifact writes, detect task commands
  |-- Stop: finalize session, create ledger entries
  |
  v
cub.core.ledger.integration (decoupled from run loop)
  |-- same LedgerIntegration API, callable from hooks or run loop
  |
  v
cub.core.tasks.json (JSON backend, drop-in for beads)
  |-- create, update, close, dependencies, epics, labels
  |-- runs in "both" mode alongside beads during migration
```

### Double-Tracking Prevention

When `cub run` invokes Claude Code as a harness, the hooks would fire inside the managed session, causing duplicate tracking. Solution: **remove hook-based tracking from the Claude harness backend** in `cub run`. The run loop already has its own tracking via `LedgerIntegration`. Hooks are exclusively for direct (non-cub-run) sessions. Other harnesses (Codex, Gemini) retain their existing tracking since they don't have hooks.

### Task Association in Direct Sessions

Three mechanisms, in priority order:

1. **Skill/AGENTS.md guidance** -- configure instructions that tell the harness to claim a task (`cub task claim <id>`) at session start or when work begins. The `SessionStart` hook injects available tasks as context.
2. **Prompt detection** -- `UserPromptSubmit` hook detects task ID patterns in user prompts and auto-injects task context.
3. **Branch inference** -- if the current branch is bound to an epic, associate work with that epic's tasks.
4. **Confirmation fallback** -- if no task is associated and the `Stop` hook detects substantive work was done, surface a reminder.

### Task Creation Entry Points

| Entry Point | Mode | Mechanism |
|-------------|------|-----------|
| `cub run` task selection | Automated | Run loop selects from backend |
| Structured pipeline (orient/architect/plan) | Both | Slash commands produce artifacts + create tasks |
| Conversational spec writing | Direct session | Slash commands (`/cub:spec`, `/cub:capture`) write to standard dirs; PostToolUse hook detects |
| Ad-hoc mid-session | Direct session | User says "create a task for X"; harness calls `cub task create`; PostToolUse (Bash) hook detects |
| Plan mode artifacts | Direct session | Claude's plan mode writes plans; PostToolUse (Write) hook captures to `plans/` |

### Ledger Decoupling

`LedgerIntegration` currently assumes it's called from the run loop with full task context. For hook-based usage:

- Extract a `SessionLedgerIntegration` that works with partial information (session ID, files changed, task ID if known)
- Support "lazy finalization" -- forensics log accumulates events during session, `Stop` hook synthesizes a ledger entry
- Transcript parsing as a post-hoc enrichment step (extract token usage, cost, conversation summary)

### Lightweight Hook Scripts

To avoid Python startup latency on every tool use:

- Shell wrapper scripts in `.cub/scripts/hooks/` do fast checks:
  - Is `CUB_RUN_ACTIVE` set? Skip (double-tracking prevention)
  - Is the tool relevant? (Write/Edit to tracked directories, Bash with task commands)
- Only invoke `python -m cub.core.harness.hooks` when the fast check passes
- `cub init` installs these scripts and configures `.claude/settings.json`

### Repo as Holistic Source of Truth

All artifacts land in version-controlled locations:

```
project/
  specs/           # Feature specifications
  plans/           # Implementation plans (from pipeline OR direct sessions)
  captures/        # Ad-hoc ideas and notes
  .cub/
    ledger/        # Task completion records
      by-task/     # Per-task ledger entries
      by-epic/     # Epic aggregations
      forensics/   # Raw session event logs
      index.jsonl  # Ledger index
    tasks.json     # JSON task backend (drop-in for .beads/issues.jsonl)
    session.log    # Session activity log
```

## Parity Matrix

What works the same in both modes:

| Capability | `cub run` | Direct Session + Hooks |
|------------|-----------|------------------------|
| Task selection | Automatic | Manual (guided by injected context) |
| Task claiming | Automatic | Via skill guidance or explicit command |
| Ledger entry creation | Automatic (LedgerIntegration) | Automatic (hook-based forensics -> ledger) |
| Plan capture | Automatic (harness output) | PostToolUse detects writes to plans/ |
| Spec/capture creation | Via pipeline commands | Via slash commands (same artifacts) |
| File change tracking | Run loop tracks | PostToolUse tracks Write/Edit targets |
| Git commit association | Run loop detects | PostToolUse detects git commit |
| Session context | Built into run loop | SessionStart injects via additionalContext |
| Budget tracking | Automatic (harness reports) | Post-hoc transcript parsing |
| Task creation | Pre-defined in backend | Pipeline, conversational, or ad-hoc |

## Implementation Notes

### Phase 1: Hook Wiring and Session Tracking

- Install hook configuration in `.claude/settings.json` via `cub init`
- Implement lightweight shell wrappers for fast-path filtering
- Enhance `SessionStart` handler to inject project context
- Enhance `PostToolUse` handler to track artifact writes and task commands
- Enhance `Stop` handler to finalize session records
- Add `CUB_RUN_ACTIVE` environment variable to Claude harness backend

### Phase 2: Ledger Decoupling and Integration

- Extract `SessionLedgerIntegration` from `LedgerIntegration`
- Connect hook handlers to ledger (not just forensics logs)
- Implement transcript parsing for token/cost extraction
- Create `cub reconcile` command for manual post-hoc processing

### Phase 3: Task Association and Creation

- Implement `UserPromptSubmit` hook for task ID detection
- Enhance AGENTS.md generation with task claiming guidance
- Ensure all slash commands (spec, capture, orient, architect, plan) create proper ledger records
- Implement `cub task create` as a lightweight CLI entry point callable from harness sessions

### Phase 4: JSON Backend Parity

- Verify JSON backend supports all operations beads provides
- Run in "both" mode (JSON + beads) during migration
- Validate that all hook handlers work with JSON backend
- Document migration path from beads to JSON-only

## Open Questions

1. What lightweight script approach for hook paths avoids full cub startup while remaining reliably installed and locatable?
2. How does skill/AGENTS.md configuration guide task association -- what does the ideal prompt look like?
3. What is the JSON backend's current gap list relative to beads?
4. Should `cub init` auto-install hooks into `.claude/settings.json`, or require opt-in?
5. How do we handle the case where someone has existing `.claude/settings.json` content we shouldn't clobber?

## Future Considerations

- **Web dashboard** consuming session and ledger data for visualization
- **Multi-harness hooks** -- Codex, Gemini, OpenCode equivalents when those platforms support hooks
- **Plan format translation** -- normalize Claude's plan format into cub's plan schema
- **Cross-machine sync** -- cub's repo-local approach already handles this via git, but could be more explicit
- **Real-time cost tracking** -- if harness APIs expose token data in hooks in the future
- **Auto-task creation from conversation** -- LLM-powered detection of "that sounds like a task" moments

---

**Status**: researching
**Last Updated**: 2026-01-28
