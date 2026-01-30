# Itemized Plan: cub task Full Task Management Parity

> Source: [cub-task-parity.md](../../specs/researching/cub-task-parity.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-29

## Context Summary

Make `cub task` the complete, authoritative interface for task lifecycle management. Fill gaps in the TaskBackend protocol, implement in both backends, add CLI subcommands, build DependencyGraph for analysis, and update skills/docs to reference only `cub task`.

**Mindset:** Production | **Scale:** Personal

---

## Epic: cub-p1t - cub-task-parity #1: Protocol Extensions & DependencyGraph

Priority: 0
Labels: phase-1, complexity:high, model:sonnet

Extend the TaskBackend protocol with 7 new methods, implement them in BeadsBackend and JsonlBackend, extend `update_task` signature, and build the DependencyGraph class. This is the foundation that everything else depends on.

### Task: cub-p1t.1 - Extend TaskBackend protocol with 7 new methods

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium
Blocks: cub-p1t.2, cub-p1t.3, cub-p1t.4

**Context**: The protocol needs 7 new methods for full lifecycle coverage. Also extend `update_task` to accept `title`, `priority`, and `notes` parameters. Create a `TaskBackendDefaults` mixin with default implementations for methods that can be derived from existing operations.

**Implementation Steps**:
1. Add 7 new method signatures to `TaskBackend` protocol in `backend.py`: `add_dependency`, `remove_dependency`, `list_blocked_tasks`, `reopen_task`, `delete_task`, `add_label`, `remove_label`
2. Extend `update_task` signature with optional `title: str | None`, `priority: int | None`, `notes: str | None` parameters
3. Create `TaskBackendDefaults` mixin class with default implementations:
   - `list_blocked_tasks`: filter `list_tasks(status=OPEN)` for tasks with unresolved deps
   - `add_label`/`remove_label`: get task, modify labels, call `update_task`
   - `reopen_task`: call `update_task(task_id, status=OPEN)`
4. Add `blocked: int = 0` field to `TaskCounts` model
5. Update type annotations and docstrings for all new methods

**Acceptance Criteria**:
- [ ] `TaskBackend` protocol has 19 methods (12 existing + 7 new)
- [ ] `update_task` accepts `title`, `priority`, `notes` optional params
- [ ] `TaskBackendDefaults` mixin has working default implementations
- [ ] `TaskCounts.blocked` field exists
- [ ] mypy passes with strict mode
- [ ] All new methods have complete docstrings

**Files**: src/cub/core/tasks/backend.py, src/cub/core/tasks/models.py

---

### Task: cub-p1t.2 - Implement new protocol methods in BeadsBackend

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium
Blocks: cub-p1t.5

**Context**: BeadsBackend wraps the `bd` CLI. Each new protocol method needs a corresponding `bd` command wrapper. Follow the existing `_run_bd` pattern — bd commands that don't return JSON need a follow-up `get_task()` call.

**Implementation Steps**:
1. `add_dependency(task_id, depends_on)` — run `bd dep add <task_id> <depends_on>`, then `get_task(task_id)`
2. `remove_dependency(task_id, depends_on)` — run `bd dep remove <task_id> <depends_on>`, then `get_task(task_id)`
3. `list_blocked_tasks(parent?)` — run `bd blocked --json` (or `bd list --status open --json` and filter), parse JSON output
4. `reopen_task(task_id)` — run `bd update <id> --status open`, then `get_task(task_id)`
5. `delete_task(task_id)` — run `bd delete <id>`, return True on success
6. `add_label(task_id, label)` — run `bd label add <id> <label>`, then `get_task(task_id)`
7. `remove_label(task_id, label)` — run `bd label remove <id> <label>`, then `get_task(task_id)`
8. Extend `update_task` to pass `--title`, `--priority`, `--notes` flags when provided
9. Update `get_task_counts` to include blocked count

**Acceptance Criteria**:
- [ ] All 7 new methods implemented and callable
- [ ] `update_task` supports title, priority, notes parameters
- [ ] `get_task_counts` includes blocked count
- [ ] Error handling follows existing pattern (ValueError on not found)
- [ ] Unit tests pass for all new methods (mocked bd subprocess)

**Files**: src/cub/core/tasks/beads.py, tests/test_beads_backend.py

---

### Task: cub-p1t.3 - Implement new protocol methods in JsonlBackend

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium
Blocks: cub-p1t.5

**Context**: JsonlBackend operates on an in-memory task list with atomic file writes. New methods manipulate task fields directly using existing Task model methods (`add_label()`, `remove_label()`, `reopen()`).

**Implementation Steps**:
1. `add_dependency(task_id, depends_on)` — find task, append to `depends_on` list, save
2. `remove_dependency(task_id, depends_on)` — find task, remove from `depends_on` list, save
3. `list_blocked_tasks(parent?)` — filter: status=OPEN, has depends_on, not all deps closed
4. `reopen_task(task_id)` — find task, call `task.reopen()`, save
5. `delete_task(task_id)` — remove task from list, save, return True
6. `add_label(task_id, label)` — find task, call `task.add_label(label)`, save
7. `remove_label(task_id, label)` — find task, call `task.remove_label(label)`, save
8. Extend `update_task` to handle title, priority, notes field updates
9. Update `get_task_counts` to include blocked count
10. All mutations use existing atomic write pattern (temp file → rename)

**Acceptance Criteria**:
- [ ] All 7 new methods implemented and callable
- [ ] `update_task` supports title, priority, notes parameters
- [ ] `get_task_counts` includes blocked count
- [ ] Atomic writes for all mutations (no partial state)
- [ ] Unit tests pass for all new methods

**Files**: src/cub/core/tasks/jsonl.py, tests/test_jsonl_backend.py

---

### Task: cub-p1t.4 - Build DependencyGraph class

Priority: 0
Labels: phase-1, model:opus, complexity:high
Blocks: cub-p1t.5

**Context**: Pure query object for dependency analysis. Built from a task list snapshot, immutable after construction. Used by AgentFormatter (agent-output spec) and `cub task blocked --agent` for impact analysis and recommendations. This is the critical piece that unblocks the agent-output spec.

**Implementation Steps**:
1. Create `src/cub/core/tasks/graph.py` with `DependencyGraph` class
2. Constructor takes `list[Task]`, builds:
   - `_tasks: dict[str, Task]` — task lookup
   - `_forward: dict[str, set[str]]` — depends_on edges (only open/in-progress)
   - `_reverse: dict[str, set[str]]` — blocks edges (inverse of forward)
   - `_closed: set[str]` — resolved task IDs
3. `direct_unblocks(task_id) -> list[str]` — reverse edge lookup
4. `transitive_unblocks(task_id) -> set[str]` — BFS from task through reverse edges
5. `root_blockers(limit=5) -> list[tuple[str, int]]` — compute transitive_unblocks for all open tasks, sort by count descending
6. `chains(limit=5) -> list[list[str]]` — DFS to find longest paths in forward graph
7. `would_become_ready(task_id) -> list[str]` — for each task in `direct_unblocks()`, check if ALL other deps are in `_closed`
8. `has_cycle() -> bool` — DFS with three-color marking (white/gray/black)
9. `stats` property — return dict with node count, edge count, max chain depth
10. Write comprehensive tests with topologies: empty, single task, linear chain, diamond, forest, cycle, mixed open/closed

**Acceptance Criteria**:
- [ ] All 6 query methods return correct results for test topologies
- [ ] Cycle detection works and doesn't cause infinite loops in other methods
- [ ] Closed tasks are correctly excluded from graph (treated as resolved)
- [ ] `would_become_ready` checks ALL deps, not just the given task
- [ ] `root_blockers` correctly ranks by transitive impact
- [ ] `chains` returns paths sorted by length descending
- [ ] mypy passes with strict mode
- [ ] Tests cover: empty graph, single node, linear chain (5 deep), diamond dependency, forest (disconnected), cycle, mixed open/closed states

**Files**: src/cub/core/tasks/graph.py, tests/test_dependency_graph.py

---

### Task: cub-p1t.5 - Update BothBackend and write cross-backend tests

Priority: 1
Labels: phase-1, model:sonnet, complexity:medium

**Context**: BothBackend delegates to primary and secondary backends. It needs to delegate all 7 new methods and log divergences. Also write parametrized tests that verify the same operations work identically across both backends.

**Implementation Steps**:
1. Update `BothBackend` to delegate all 7 new methods (follow existing delegation pattern)
2. Inherit from `TaskBackendDefaults` as fallback
3. Add divergence logging for new methods
4. Write parametrized pytest tests that run the same test cases against BeadsBackend (mocked) and JsonlBackend (temp files)
5. Test scenarios: add/remove dependency, list blocked, reopen, delete, add/remove label
6. Verify `DependencyGraph` produces consistent results from both backend outputs

**Acceptance Criteria**:
- [ ] BothBackend delegates all 7 new methods
- [ ] Divergence logging works for new methods
- [ ] Parametrized tests pass against both backends
- [ ] DependencyGraph produces same results regardless of backend
- [ ] mypy passes

**Files**: src/cub/core/tasks/both.py, tests/test_task_backends.py

---

**CHECKPOINT: Protocol & Graph Complete**

At this point, the foundation is solid:
- All task lifecycle operations are available through the protocol
- Both backends implement them
- DependencyGraph is available for analysis
- The agent-output spec can begin using DependencyGraph

---

## Epic: cub-p2c - cub-task-parity #2: CLI Subcommands

Priority: 1
Labels: phase-2, complexity:medium, model:sonnet

Add CLI commands for all new protocol operations. Each command supports three output modes: Rich (default), `--json`, `--agent`.

### Task: cub-p2c.1 - Add cub task blocked command

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium

**Context**: The most common gap — the router currently maps "what's blocked" to `bd blocked`. This command shows blocked tasks with optional epic filter. With `--agent`, it includes root blocker analysis and chain lengths from DependencyGraph.

**Implementation Steps**:
1. Add `blocked` command to task app in `cli/task.py`
2. Parameters: `--epic` (filter), `--json`, `--agent`
3. Rich output: table with ID, Priority, Title, Blocked By columns
4. JSON output: task model dumps
5. Agent output: call `AgentFormatter.format_blocked()` if available, otherwise fall back to a simple markdown table
6. Build DependencyGraph from all tasks for analysis hints
7. Show root blockers and chain summary in agent output

**Acceptance Criteria**:
- [ ] `cub task blocked` shows blocked tasks in Rich table
- [ ] `--epic` filter works
- [ ] `--json` outputs task list as JSON
- [ ] `--agent` outputs structured markdown with analysis
- [ ] Empty result shows helpful message ("No blocked tasks")
- [ ] CLI test covers all three output modes

**Files**: src/cub/cli/task.py

---

### Task: cub-p2c.2 - Add cub task dep add/remove and cub task label add/remove/list commands

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium

**Context**: Dependency and label management subcommands. These are simple CRUD wrappers around protocol methods with confirmation output.

**Implementation Steps**:
1. Create `dep` sub-app with `add` and `remove` commands
2. `cub task dep add <task> <depends-on>` — calls `add_dependency()`, prints confirmation
3. `cub task dep remove <task> <depends-on>` — calls `remove_dependency()`, prints confirmation
4. Enhance existing `dep list` to show both directions (what this task depends on AND what depends on it)
5. Create `label` sub-app with `add`, `remove`, `list` commands
6. `cub task label add <task> <label>` — calls `add_label()`, prints confirmation
7. `cub task label remove <task> <label>` — calls `remove_label()`, prints confirmation
8. `cub task label list <task>` — calls `get_task()`, displays labels
9. All commands support `--json` for machine output

**Acceptance Criteria**:
- [ ] `cub task dep add/remove` work and confirm the operation
- [ ] `cub task dep list <id>` shows both directions
- [ ] `cub task label add/remove/list` work and confirm operations
- [ ] `--json` output works for all commands
- [ ] Error handling for invalid task IDs
- [ ] CLI tests for each command

**Files**: src/cub/cli/task.py

---

### Task: cub-p2c.3 - Add cub task reopen and cub task delete commands

Priority: 1
Labels: phase-2, model:haiku, complexity:low

**Context**: Lifecycle management commands. Reopen is straightforward. Delete is destructive and needs a confirmation prompt (skippable with `--force`).

**Implementation Steps**:
1. Add `reopen` command — calls `reopen_task()`, prints confirmation with task title
2. Add `delete` command — prompts "Delete task {id} '{title}'? [y/N]" unless `--force` is passed
3. Both support `--json` for machine output
4. Error handling: task not found, task not in correct state (e.g., reopen a non-closed task)

**Acceptance Criteria**:
- [ ] `cub task reopen <id>` reopens a closed task
- [ ] `cub task delete <id>` prompts for confirmation
- [ ] `cub task delete <id> --force` skips confirmation
- [ ] Error messages for invalid states (reopen non-closed, delete non-existent)
- [ ] CLI tests

**Files**: src/cub/cli/task.py

---

### Task: cub-p2c.4 - Enhance existing cub task list, ready, create, update commands

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium

**Context**: Existing commands need additional filters and flags to reach parity. `list` and `ready` need `--epic` and `--assignee` filters. `create` needs full flag exposure. `update` needs `--title`, `--priority`, `--notes`.

**Implementation Steps**:
1. `cub task list`: add `--epic` (filter by parent), `--assignee` (filter by assignee) options
2. `cub task ready`: add `--epic` filter, add `--by impact|priority` ordering option (impact uses DependencyGraph)
3. `cub task create`: ensure CLI exposes `--type`, `--priority`, `--epic` (as `--parent`), `--description`, `--depends-on` (comma-separated list)
4. `cub task update`: add `--title`, `--priority`, `--notes` flags alongside existing `--description`, `--assignee`, `--status`
5. For `ready --by impact`: build DependencyGraph, sort tasks by `transitive_unblocks` count descending

**Acceptance Criteria**:
- [ ] `cub task list --epic <id>` filters correctly
- [ ] `cub task list --assignee <name>` filters correctly
- [ ] `cub task ready --epic <id>` filters correctly
- [ ] `cub task ready --by impact` sorts by unblock count
- [ ] `cub task create` exposes all flags
- [ ] `cub task update` supports title, priority, notes
- [ ] CLI tests for new filters and flags

**Files**: src/cub/cli/task.py

---

### Task: cub-p2c.5 - Add cub task search command

Priority: 2
Labels: phase-2, model:sonnet, complexity:medium

**Context**: Full-text search across task titles and descriptions. BeadsBackend wraps `bd search`. JsonlBackend does substring match on title + description in memory. This is P2 but included since we're not excluding anything.

**Implementation Steps**:
1. Add `search_tasks(query: str) -> list[Task]` to `TaskBackend` protocol
2. Implement in BeadsBackend: run `bd search <query> --json`, parse results
3. Implement in JsonlBackend: case-insensitive substring match on title and description
4. Add `search` command to task CLI: `cub task search <query>`
5. Support `--json` and `--agent` output modes
6. Show match count and results table

**Acceptance Criteria**:
- [ ] `cub task search "auth"` finds tasks with "auth" in title or description
- [ ] Works with both backends
- [ ] `--json` and Rich output modes work
- [ ] Empty results show helpful message
- [ ] Tests for both backends

**Files**: src/cub/core/tasks/backend.py, src/cub/core/tasks/beads.py, src/cub/core/tasks/jsonl.py, src/cub/cli/task.py

---

**CHECKPOINT: CLI Complete**

At this point, `cub task` has full parity with `bd` for lifecycle operations. Users and agents can do everything through `cub task`. The `--agent` output mode is available for commands where AgentFormatter methods exist.

---

## Epic: cub-p3s - cub-task-parity #3: Skill & Documentation Updates

Priority: 1
Labels: phase-3, complexity:low, model:haiku

Update all skills, router, and documentation to reference `cub task` exclusively. Remove `bd` from user-facing content.

### Task: cub-p3s.1 - Update router skill and passthrough skills

Priority: 1
Labels: phase-3, model:haiku, complexity:low

**Context**: The router skill (`.claude/commands/cub.md`) currently maps "what's blocked" to `bd blocked`. Passthrough skills reference `bd` commands. Update all to use `cub task` equivalents with `--agent` flag.

**Implementation Steps**:
1. In `.claude/commands/cub.md`:
   - Replace `bd blocked` → `cub task blocked --agent`
   - Replace `bd list --status open` → `cub task list --status open --agent` (if not already)
   - Add new intent patterns for: reopen, delete, label, dep, search
2. In `.claude/commands/cub:tasks.md`:
   - Add blocked, dep, label, reopen, delete, search to command routing table
   - Update all command invocations to use `--agent` flag
3. Review other skill files for any remaining `bd` references

**Acceptance Criteria**:
- [ ] Router skill has no `bd` references (except in "power user" context if desired)
- [ ] All task intent patterns route to `cub task` commands
- [ ] New subcommands (blocked, dep, label, reopen, delete, search) are in routing table
- [ ] `--agent` flag used in all command invocations within skills

**Files**: .claude/commands/cub.md, .claude/commands/cub:tasks.md

---

### Task: cub-p3s.2 - Update CLAUDE.md and PROMPT.md documentation

Priority: 2
Labels: phase-3, model:haiku, complexity:low

**Context**: CLAUDE.md (agent instructions) and `.cub/PROMPT.md` (runloop instructions) reference `bd` commands in examples. Update all examples to use `cub task` equivalents. Keep `bd` mentioned only in the "Pre-approved Commands" section (bd is still available for power users).

**Implementation Steps**:
1. In CLAUDE.md:
   - Update "Task Management" examples to use `cub task` commands
   - Update "Available Skills" section with new subcommands
   - Keep `bd` in "Pre-approved Commands" section
   - Update "Common Commands" quick reference section
2. In `.cub/PROMPT.md`:
   - Update task closure instructions to use `cub task close`
   - Update any `bd` references in runloop workflow steps
3. Audit all `.md` files in `.cub/` directory for stale `bd` references

**Acceptance Criteria**:
- [ ] CLAUDE.md examples use `cub task` not `bd` (except Pre-approved section)
- [ ] PROMPT.md task instructions use `cub task`
- [ ] No stale `bd` references in user-facing documentation
- [ ] `bd` still listed as pre-approved for power users

**Files**: CLAUDE.md, .cub/PROMPT.md

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-p1t | 5 | P0 | Protocol extensions, backend implementations, DependencyGraph |
| cub-p2c | 5 | P1 | CLI subcommands with three output modes |
| cub-p3s | 2 | P1-P2 | Skill and documentation updates |

**Total**: 3 epics, 12 tasks

**Ready to start immediately**: cub-p1t.1 (protocol extensions) — blocks everything else

**Dependency chain**:
```
cub-p1t.1 (protocol) ──┬── cub-p1t.2 (beads) ──┐
                        ├── cub-p1t.3 (jsonl)  ──┼── cub-p1t.5 (both + cross-tests)
                        └── cub-p1t.4 (graph)  ──┘
                                                  │
                                          [CHECKPOINT]
                                                  │
                                    cub-p2c.1..5 (CLI commands)
                                                  │
                                          [CHECKPOINT]
                                                  │
                                    cub-p3s.1..2 (skills/docs)
```
