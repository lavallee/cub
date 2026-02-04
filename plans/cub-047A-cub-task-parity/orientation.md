# Orient Report: cub task Full Task Management Parity

**Date:** 2026-01-29
**Orient Depth:** Standard
**Status:** Approved

---

## Executive Summary

Make `cub task` the complete, authoritative interface for task/issue lifecycle management. Currently, common operations like creating tasks, managing dependencies, and viewing blocked work require dropping to `bd` directly. This leaks the abstraction — skills reference `bd`, agents need to know two CLIs, and `--agent` output optimization can only apply to commands cub controls. This spec fills the gaps and adds a `DependencyGraph` class that unblocks the agent-output spec.

## Problem Statement

Leaky abstraction — users, skills, and agents must know both `cub task` and `bd` to do common task lifecycle operations. The router skill maps "what's blocked" to `bd blocked` because `cub task blocked` doesn't exist. This prevents `--agent` formatted output and breaks the principle that cub is the single interface for task management. Developers and AI agents using cub in Claude Code sessions have this problem.

## Refined Vision

Add missing `cub task` subcommands to cover all common task/issue lifecycle operations. Specifically:

**Scope includes (task/issue lifecycle):**
- Creating, updating, closing, reopening, deleting tasks
- Viewing blocked tasks with dependency analysis
- Managing dependencies (add, remove, show)
- Managing labels
- Searching tasks
- Filtering by epic, assignee, priority
- DependencyGraph for analysis (used by `--agent` output)

**Scope excludes (work coordination):**
- Swarm management (`bd swarm`)
- Gate management (`bd gate`)
- Merge slots (`bd merge-slot`)
- State dimensions (`bd set-state`)
- Molecules (`bd mol`)
- Activity feed (`bd activity`)
- Cross-rig operations (`bd refile`)

**Deprioritized (edge-case lifecycle):**
- Export (`bd export`) — niche
- History (`bd history`) — Dolt-specific
- Lint (`bd lint`) — nice-to-have
- Stale detection (`bd stale`) — achievable with list + sort
- Duplicate/supersede relationships — advanced, rare

## Requirements

### P0 - Must Have

- **`cub task blocked`** — List blocked tasks with optional epic filter. Supports `--json` and `--agent`. This is the most common gap; the router currently maps to `bd blocked`.
- **`cub task dep add/remove`** — Full dependency management through the protocol. Currently `dep add` delegates to `bd dep add` directly; `dep remove` doesn't exist.
- **`DependencyGraph` class** (`core/tasks/graph.py`) — Bidirectional dependency graph built from task list. Methods: `direct_unblocks()`, `transitive_unblocks()`, `root_blockers()`, `chains()`, `would_become_ready()`. Required by agent-output spec for analysis hints.
- **Protocol methods for dependencies** — Add `add_dependency(task_id, depends_on_id)` and `remove_dependency(task_id, depends_on_id)` to `TaskBackend` protocol.
- **Protocol method for blocked** — Add `list_blocked_tasks(parent?)` to `TaskBackend` protocol. Can be derived from `list_tasks()` but having a dedicated method is cleaner.
- **All new subcommands support `--json` and `--agent`** — Three output modes (Rich, JSON, agent markdown) for every command.

### P1 - Should Have

- **`cub task create`** — Already in protocol (`create_task`), needs CLI exposure with full flag set: `--type`, `--priority`, `--epic`, `--description`, `--depends-on`.
- **`cub task update`** — Already in protocol (`update_task`), needs CLI with individual field flags: `--title`, `--description`, `--priority`, `--notes`, `--assignee`.
- **`cub task label add/remove/list`** — Manage labels through protocol. Protocol needs `add_label(task_id, label)` and `remove_label(task_id, label)`.
- **`cub task reopen`** — Reopen closed tasks. Protocol needs `reopen_task(task_id)`.
- **`cub task delete`** — Delete tasks. Protocol needs `delete_task(task_id)`.
- **Enhanced filtering** — Add `--epic` and `--assignee` filters to `cub task list` and `cub task ready`.
- **Skill and doc updates** — Update router skill, passthrough skills, and CLAUDE.md to use `cub task` exclusively instead of `bd`.

### P2 - Nice to Have

- **`cub task search`** — Full-text search across task titles and descriptions. Protocol needs `search_tasks(query)`. May not be feasible for all backends.
- **`cub task ready --by impact`** — Order ready tasks by unblock count using DependencyGraph. Useful for `--agent` output recommendations.
- **Bulk operations** — `cub task close cub-041 cub-042 cub-043` for closing multiple tasks at once.

## Constraints

- **Protocol-first**: All new operations go through the `TaskBackend` protocol, not shell-out. This ensures both beads and JSONL backends work.
- **Backend capability variance**: JSONL backend can implement everything in-memory. Beads backend wraps `bd` commands. Some features (search) may have different fidelity across backends. Solution: implement best-effort for each backend, document differences.
- **bd remains available**: `cub task` doesn't replace `bd`. Power users can still use `bd` directly. But skills, docs, and CLAUDE.md should reference only `cub task`.
- **`--agent` flag requires AgentFormatter**: The `--agent` output for new commands depends on the AgentFormatter from the agent-output spec. These two specs can be implemented in parallel — this spec builds the data access, agent-output builds the formatting.

## Assumptions

- The `TaskBackend` protocol can be extended without breaking existing backends. Both BeadsBackend and JsonlBackend need to implement new methods.
- `bd` CLI output format is stable enough to parse reliably for beads backend implementation.
- DependencyGraph can be built in-memory from the task list without performance concerns (task lists < 500 items).
- The existing `depends_on` and `blocks` fields on Task model are sufficient for dependency management — no new relationship types needed for this spec.

## Open Questions / Experiments

- **Protocol method granularity**: Should `add_dependency` be a standalone protocol method or part of `update_task`? → Decision: standalone method. Dependencies are a distinct concept from field updates, and the DependencyGraph needs clean dependency operations.
- **Search fidelity across backends**: JSONL backend can do substring search in-memory. Beads backend has `bd search`. Should `search_tasks()` be a required or optional protocol method? → Experiment: make it required but allow backends to raise `NotImplementedError` with a helpful message. Revisit if this causes problems.
- **`list_blocked_tasks` vs computed**: Should "blocked" be a dedicated protocol method or computed by filtering `list_tasks()` results? → Decision: dedicated method is cleaner for backends that can optimize it (beads has `bd blocked`). Provide a default implementation that filters list_tasks for backends that don't override.

## Out of Scope

- Work coordination features (swarm, gates, merge slots, state dimensions, molecules)
- Cross-rig operations (refile/move)
- Dolt-specific features (history, diff)
- Export to external formats (Obsidian, JSONL export)
- Task lint/validation
- Stale task detection (achievable with existing list + sort)
- Duplicate/supersede relationship types
- Daemon architecture (separate spec)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Protocol changes break existing backends | H | Add methods with default implementations where possible. Run full test suite against both backends. |
| bd CLI output format changes break beads backend | M | Pin to known bd output patterns. Add integration tests that run real bd commands. |
| DependencyGraph has cycles in task data | M | Add cycle detection in graph construction. Log warning, don't crash. Break cycles by ignoring back-edges. |
| Scope creep from "just one more bd command" | M | Strict categorization: lifecycle only, no coordination. Defer edge-case commands. |
| JSONL backend falls behind beads in features | L | JSONL is the simpler backend — not all features need full fidelity. Document differences. |

## MVP Definition

Full implementation of all P0 and P1 requirements:

1. **New subcommands**: `blocked`, `dep add/remove`, `create` (CLI), `update` (CLI), `label add/remove/list`, `reopen`, `delete`
2. **Protocol additions**: `add_dependency`, `remove_dependency`, `list_blocked_tasks`, `add_label`, `remove_label`, `reopen_task`, `delete_task`
3. **DependencyGraph**: Full class with 5 query methods, usable by agent-output spec
4. **Enhanced filters**: `--epic` and `--assignee` on `list` and `ready`
5. **All commands support `--json` and `--agent`**
6. **Skill/doc updates**: Router, passthrough skills, CLAUDE.md reference only `cub task`

## Dependency Map

```
cub-task-parity
├── DependencyGraph (core/tasks/graph.py)
│   └── Used by: agent-output spec (AgentFormatter analysis hints)
├── Protocol additions (core/tasks/backend.py)
│   ├── Implemented by: BeadsBackend (core/tasks/beads.py)
│   └── Implemented by: JsonlBackend (core/tasks/jsonl.py)
├── CLI subcommands (cli/task.py)
│   └── Uses: --agent flag from agent-output spec (or --json fallback)
└── Skill/doc updates
    ├── .claude/commands/cub.md (router)
    ├── .claude/commands/cub:tasks.md
    └── CLAUDE.md
```

---

**Next Step:** Run `cub architect` to design the technical architecture.
