---
status: researching
priority: high
complexity: medium
dependencies:
- symbiotic-workflow
- context-restructure
blocks: []
created: 2026-01-28
updated: 2026-01-28
readiness:
  score: 6
  blockers: []
  questions:
  - What does the welcome/guidance message contain beyond stats + suggestions?
  - How does --resume interact with cub context—does it re-inject updated project
    state?
  - What's the UX for background task completion notification within a harness session?
  - How does cub detect it's already inside a harness session to avoid nesting?
  - What's the right name for the core execution layer (cub-exec, cub.core, something
    else)?
  - How do suggestions get ranked (priority, low-hanging fruit, project momentum)?
  decisions_needed:
  - Whether to introduce a formal core/interface split in 0.30 or just bare cub +
    skills
  - Whether cub run inside a harness uses Claude Code's Task tool or subprocess
  tools_needed: []
spec_id: cub-028
---
# Bare Cub Command & In-Harness Mode Fluidity

## Overview

Make `cub` the unified front door for both interactive and autonomous AI-assisted development. Bare `cub` launches the default harness with project context and workflow guidance. From within a harness session, all cub modes (conversational, structured, supervised, autonomous) are accessible without exiting. This closes the gap between "using cub" and "using a harness directly" so they feel like the same workflow.

## The Problem

Today there's a split between cub-managed work (`cub run`, `cub plan`) and direct harness work (opening Claude Code). Moving between modes means exiting one context and entering another, losing momentum and context. Cub's value—task structure, planning artifacts, project awareness—should be available regardless of which mode you're in, and transitions between modes should be seamless.

## Goals

- **Bare `cub` drops into default harness** with a welcome message showing project stats and smart suggestions
- **Support `--resume` and `--continue`** flags that pass through to the underlying harness
- **Planning/spec commands work as in-session skills**, not subprocess wrappers—they're guided prompts, not CLI-to-CLI bridges
- **`cub run` from within harness**: single task = foreground with polling; multi-task = background with status checks
- **Avoid nesting**: detect if already inside a harness session and adapt behavior (possibly via a separate core binary)
- **Smart suggestions** inferred from ledger, recent commits, task state, and project momentum

## Non-Goals

- Full daemon/background service (post-alpha)
- Non-Claude-Code interactive harness support in alpha (others for autonomous `cub run` only)
- Building a complete intermediary layer on top of harnesses—leverage them
- Replacing harness capabilities or abstracting them away

## Design / Approach

### Mode Taxonomy

| Mode | Style | Entry Points |
|------|-------|-------------|
| **Conversational** | Language-based inquiry | Spec interviews, brainstorming, exploration |
| **Structured** | Artifact-producing | `cub plan`, `cub capture`, generating specs |
| **Supervised** | Hands-on execution | Working a task interactively with feedback |
| **Autonomous** | Hands-off execution | `cub run` burning through a task queue |

Mode transitions should happen **inside** the harness session. You shouldn't have to quit Claude Code to run `cub plan`, then quit planning to start `cub run`, then open Claude Code again to give feedback.

### Architecture: Core/Interface Split

Many cub commands are wrappers that set up context and launch harness sessions. The underlying logic can be separated from the interface that invokes it:

```
┌─────────────────────────────────────────────────┐
│  Interfaces (context-aware shells)              │
│  ┌──────┐  ┌──────┐  ┌─────────┐  ┌─────────┐  │
│  │ CLI  │  │ Web  │  │ Harness │  │ Future  │  │
│  │(cub) │  │(dash)│  │(skills) │  │(daemon) │  │
│  └──┬───┘  └──┬───┘  └────┬────┘  └────┬────┘  │
│     └─────────┴──────────┴──────────┘         │
│                    │                            │
│  ┌─────────────────▼──────────────────────────┐ │
│  │  Core API (cub.core)                       │ │
│  │  tasks, plans, runs, ledger, status        │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

- **Core API**: Context-agnostic execution logic. Doesn't care whether it's invoked from CLI, harness skill, web dashboard, or daemon.
- **Interfaces**: Adapt core operations for their environment. CLI formats output for terminals. Harness interface provides guided prompts and skills. Web provides REST endpoints.
- **Same code paths**: Whether you run `cub plan orient` from a terminal or invoke `/cub:orient` from inside Claude Code, the same core logic executes.

### Bare `cub` Behavior

When invoked with no subcommand:

1. **Detect environment**: Am I inside a harness session already?
   - If yes: Show status + suggestions inline (don't nest)
   - If no: Launch default harness with cub context
2. **Generate welcome message**: Project stats, smart suggestions
3. **Launch harness**: Pass through `--resume`/`--continue` if specified
4. **CLAUDE.md provides ongoing context**: Already loaded by the harness

### Smart Suggestions Engine

Infer actionable next steps from project state:

```
╭─ cub · v0.28.0 ─────────────────────────────────╮
│ 20 ready · 10 blocked · 316 completed            │
│ 9 epics ready to close · Last commit: 2h ago     │
╰──────────────────────────────────────────────────╯

  Suggestions:
  → Close 9 completed epics (cub-r1a, cub-r1b, ...)
  → Work on cub-ht4: Add cub upgrade command (P2, low)
  → Clean up: remove "curb" reference in CHANGELOG
  → Ready for 0.30? Run validation testing
```

Suggestion sources:
- **Stale epics**: Epics where all tasks are closed but epic isn't
- **Low-hanging fruit**: Low-complexity ready tasks
- **Momentum**: What was worked on recently, what's next in sequence
- **Milestone awareness**: Progress toward stated goals (e.g., 0.30 alpha)

### In-Harness Mode Transitions

Planning commands that currently wrap harness sessions should work as **skills within an existing session**:

| CLI Command | In-Harness Equivalent | Notes |
|-------------|----------------------|-------|
| `cub plan orient` | `/cub:orient` | Already exists as skill |
| `cub plan architect` | `/cub:architect` | Already exists as skill |
| `cub plan itemize` | `/cub:itemize` or `/cub:plan` | Already exists as skill |
| `cub spec` | `/cub:spec` | Already exists as skill |
| `cub capture` | `/cub:capture` | Already exists as skill |
| `cub run --once` | `cub run --once` (via Bash) | Foreground, poll for completion |
| `cub run --epic X` | `cub run --epic X` (via Bash) | Background, check status later |
| `cub task ready` | `cub task ready` (via Bash) | Works today |
| `cub status` | `cub status` (via Bash) | Works today |

The skills already exist. The gap is making them discoverable and ensuring the welcome message guides users toward them.

### `cub run` Inside a Harness

When invoked from within a harness session:

- **Single task** (`cub run --once`): Runs as foreground subprocess, harness polls/waits for result
- **Multi-task** (`cub run --epic X`): Runs in background, user checks `cub status` for progress
- **Default behavior**: Single task = foreground, multi-task = background

## Implementation Notes

### Phase 1: Bare `cub` (Alpha)
1. Add default command handler that detects no-subcommand invocation
2. Generate welcome message from `cub status` + `bd ready` + `bd stats`
3. Launch `claude` with system prompt containing welcome + guidance
4. Pass through `--resume` / `--continue` flags

### Phase 2: Nesting Prevention
1. Set environment variable (e.g., `CUB_SESSION_ACTIVE`) when harness is launched
2. When `cub` is invoked inside a session, show inline status instead of nesting
3. Consider whether a separate entry point (core binary) is cleaner

### Phase 3: Skill Enhancement
1. Ensure all planning skills are registered and documented
2. Add `/cub` meta-skill that shows available cub skills and commands
3. Add skill-based wrappers for `cub run` (single task mode)

### Phase 4: Background Run Integration
1. `cub run` inside harness detects it's in a session
2. Single task: foreground execution
3. Multi-task: background with notification on completion

## Open Questions

1. What does the welcome/guidance message contain beyond stats + suggestions?
2. How does `--resume` interact with cub context—does it re-inject updated project state on resume?
3. What's the UX for background task completion notification within a harness session?
4. How does cub detect it's already inside a harness session to avoid nesting?
5. What's the right name for the core execution layer?
6. How do suggestions get ranked (priority, low-hanging fruit, project momentum)?

## Future Considerations

- **Daemon mode**: Long-running background process that watches for work and notifies
- **Multi-harness coordination**: Route different task types to different harnesses
- **Web interface**: Dashboard becomes another interface to the same core
- **Session continuity**: Persistent session state across cub invocations
- **Non-Claude-Code harness support**: Extend interactive mode to Codex, Gemini, etc.

---

**Status**: researching
**Last Updated**: 2026-01-28
