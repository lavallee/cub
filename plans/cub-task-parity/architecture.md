# Architecture Design: cub task Full Task Management Parity

**Date:** 2026-01-29
**Mindset:** Production
**Scale:** Personal
**Status:** Approved

---

## Technical Summary

This architecture extends the `TaskBackend` protocol with 7 new methods, implements them in both BeadsBackend and JsonlBackend, adds corresponding CLI subcommands to `cub task`, and introduces a `DependencyGraph` class for dependency analysis.

The design is conservative — it extends existing patterns rather than introducing new ones. The `TaskBackend` protocol gains methods that mirror operations the Task model already supports internally (`reopen()`, `add_label()`, `remove_label()`). The `DependencyGraph` is a pure, stateless query object built from the task list on demand. All new CLI commands follow the established pattern: get backend → call protocol method → format output (Rich / JSON / agent markdown).

The protocol extension strategy uses default implementations where possible. New methods that can be derived from existing methods (like `list_blocked_tasks` from `list_tasks`) get default implementations in a mixin, so backends that don't override them still work. Backend-specific optimizations (like beads' `bd blocked`) can override the defaults.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing codebase |
| Protocol | typing.Protocol | Existing pattern, runtime_checkable |
| Graph | In-memory dict-based adjacency lists | Task lists < 500 items; no persistence needed |
| Testing | pytest with parametrized tests | Test same operations across both backends |
| CLI | Typer per-command flags | Matches existing `--json` pattern |

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI Layer                              │
│                                                              │
│  cub task blocked    cub task dep add/remove                 │
│  cub task create*    cub task update*                        │
│  cub task label      cub task reopen                         │
│  cub task delete     cub task search                         │
│  (* = CLI exposure of existing protocol methods)             │
│                                                              │
│  Each command: --json | --agent | Rich (default)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   TaskBackend Protocol                        │
│                                                              │
│  Existing (12 methods):                                      │
│    list_tasks, get_task, get_ready_tasks, update_task,       │
│    close_task, create_task, get_task_counts, add_task_note,  │
│    import_tasks, get_agent_instructions, bind_branch,        │
│    try_close_epic                                            │
│                                                              │
│  New (7 methods):                                            │
│    add_dependency, remove_dependency, list_blocked_tasks,    │
│    reopen_task, delete_task, add_label, remove_label         │
│                                                              │
└──────────────┬────────────────────┬─────────────────────────┘
               │                    │
               ▼                    ▼
    ┌──────────────────┐  ┌──────────────────┐
    │  BeadsBackend    │  │  JsonlBackend    │
    │  (wraps bd CLI)  │  │  (file-based)    │
    └──────────────────┘  └──────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   DependencyGraph                            │
│                                                              │
│  Pure query object, built from list[Task]                    │
│  No persistence, no side effects                             │
│                                                              │
│  Methods:                                                    │
│    direct_unblocks(task_id) → list[str]                      │
│    transitive_unblocks(task_id) → set[str]                   │
│    root_blockers(limit) → list[tuple[str, int]]              │
│    chains(limit) → list[list[str]]                           │
│    would_become_ready(task_id) → list[str]                   │
│    has_cycle() → bool                                        │
│                                                              │
│  Used by: AgentFormatter (agent-output spec)                 │
│           cub task blocked --agent                            │
│           cub task ready --by impact                          │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Protocol Extensions (`core/tasks/backend.py`)

- **Purpose:** Add 7 methods to `TaskBackend` protocol for full lifecycle coverage
- **Responsibilities:**
  - Define method signatures with types and docstrings
  - Maintain backward compatibility (existing backends must not break)
- **Dependencies:** `Task`, `TaskStatus` models
- **Interface:** Protocol methods (must be implemented by all backends)

**New protocol methods:**

```python
def add_dependency(self, task_id: str, depends_on: str) -> Task:
    """Add a dependency: task_id depends on depends_on."""
    ...

def remove_dependency(self, task_id: str, depends_on: str) -> Task:
    """Remove a dependency."""
    ...

def list_blocked_tasks(
    self,
    parent: str | None = None,
) -> list[Task]:
    """List tasks that have unresolved dependencies (status OPEN, depends_on not all closed)."""
    ...

def reopen_task(self, task_id: str) -> Task:
    """Reopen a closed task (set status back to OPEN)."""
    ...

def delete_task(self, task_id: str) -> bool:
    """Delete a task permanently. Returns True if deleted."""
    ...

def add_label(self, task_id: str, label: str) -> Task:
    """Add a label to a task."""
    ...

def remove_label(self, task_id: str, label: str) -> Task:
    """Remove a label from a task."""
    ...
```

**Protocol extension strategy:**

Since Python's `Protocol` doesn't support default implementations, and we don't want to break existing backends, we use a **mixin class** that backends can inherit alongside the protocol:

```python
class TaskBackendDefaults:
    """Default implementations for new protocol methods.

    Backends can inherit from this to get working (but potentially
    suboptimal) implementations of new methods. Backends that have
    more efficient alternatives (e.g., BeadsBackend using bd blocked)
    should override these.
    """

    def list_blocked_tasks(
        self: TaskBackend,
        parent: str | None = None,
    ) -> list[Task]:
        """Default: filter list_tasks() for tasks with unresolved deps."""
        all_tasks = self.list_tasks(status=TaskStatus.OPEN, parent=parent)
        closed_ids = {t.id for t in self.list_tasks(status=TaskStatus.CLOSED)}
        return [
            t for t in all_tasks
            if t.depends_on and not all(d in closed_ids for d in t.depends_on)
        ]
```

This lets us extend the protocol without requiring all backends to implement everything from scratch. The BothBackend wrapper inherits defaults too.

### 2. BeadsBackend Extensions (`core/tasks/beads.py`)

- **Purpose:** Implement 7 new protocol methods using `bd` CLI
- **Responsibilities:**
  - `add_dependency` → `bd dep add <task> <depends-on>`
  - `remove_dependency` → `bd dep remove <task> <depends-on>`
  - `list_blocked_tasks` → `bd blocked [--parent <epic>]` (parse output)
  - `reopen_task` → `bd update <id> --status open`
  - `delete_task` → `bd delete <id>`
  - `add_label` → `bd label add <id> <label>`
  - `remove_label` → `bd label remove <id> <label>`
- **Dependencies:** `bd` CLI (beads)
- **Interface:** Implements `TaskBackend` protocol methods

**bd compatibility notes:**
- `bd dep add` and `bd dep remove` don't return JSON — after mutation, fetch the task via `get_task()`
- `bd blocked` returns a JSON list when `--json` is passed — parse like `list_tasks`
- `bd delete` is destructive — confirm it exists before calling
- `bd label add/remove` don't return JSON — fetch after mutation

### 3. JsonlBackend Extensions (`core/tasks/jsonl.py`)

- **Purpose:** Implement 7 new protocol methods using in-memory operations
- **Responsibilities:**
  - `add_dependency` → append to task's `depends_on` list, save file
  - `remove_dependency` → remove from `depends_on` list, save file
  - `list_blocked_tasks` → filter tasks: OPEN status + has unresolved deps
  - `reopen_task` → set `status = OPEN`, clear `closed_at`, save file
  - `delete_task` → remove task from list, save file
  - `add_label` → call `task.add_label()`, save file
  - `remove_label` → call `task.remove_label()`, save file
- **Dependencies:** None (file-based)
- **Interface:** Implements `TaskBackend` protocol methods

All operations use the existing atomic write pattern (temp file → rename).

### 4. DependencyGraph (`core/tasks/graph.py`)

- **Purpose:** Bidirectional dependency graph for analysis queries
- **Responsibilities:**
  - Build forward (depends_on) and reverse (blocks) adjacency lists from task list
  - Answer impact queries (what does closing this task unblock?)
  - Identify bottlenecks (root blockers, longest chains)
  - Detect cycles (log warning, don't crash)
- **Dependencies:** `Task` model only
- **Interface:** Constructor takes `list[Task]`, methods return query results

```python
class DependencyGraph:
    """Bidirectional dependency graph built from a task list.

    Constructed from a snapshot of the task list. Immutable after construction.
    All methods are pure queries — no side effects, no persistence.

    Considers only OPEN and IN_PROGRESS tasks for dependency analysis.
    CLOSED tasks are treated as resolved (their edges are removed).
    """

    def __init__(self, tasks: list[Task]) -> None:
        """Build adjacency lists from task dependencies.

        Filters to open/in-progress tasks only. Closed tasks are
        considered resolved — their dependencies don't count.
        """
        self._tasks: dict[str, Task] = {}
        self._forward: dict[str, set[str]] = {}   # task → depends_on
        self._reverse: dict[str, set[str]] = {}    # task → blocks (what depends on it)
        self._closed: set[str] = set()
        # ... build from task list

    def direct_unblocks(self, task_id: str) -> list[str]:
        """Tasks directly depending on this one (reverse edges)."""
        ...

    def transitive_unblocks(self, task_id: str) -> set[str]:
        """All tasks transitively unblocked if this closes (BFS/DFS)."""
        ...

    def root_blockers(self, limit: int = 5) -> list[tuple[str, int]]:
        """Open tasks that transitively block the most work.
        Returns (task_id, unblock_count) sorted descending."""
        ...

    def chains(self, limit: int = 5) -> list[list[str]]:
        """Longest dependency chains, sorted by length descending.
        Uses DFS to find all maximal paths."""
        ...

    def would_become_ready(self, task_id: str) -> list[str]:
        """Tasks that would become ready if task_id closed.
        Checks ALL deps of each downstream task, not just this one."""
        ...

    def has_cycle(self) -> bool:
        """Check for cycles using DFS coloring."""
        ...

    @property
    def stats(self) -> dict[str, int]:
        """Summary stats: total nodes, edges, max depth, cycle count."""
        ...
```

**Design decisions:**

1. **Immutable after construction.** The graph is a snapshot. If tasks change, build a new graph. This eliminates consistency bugs.

2. **Closed tasks are resolved.** Only OPEN/IN_PROGRESS tasks appear as nodes. When checking "would_become_ready", closed deps are treated as already satisfied.

3. **Cycle handling.** Cycles shouldn't exist in well-formed task data, but defensive code handles them. `has_cycle()` returns True, and traversal methods use visited sets to avoid infinite loops. A warning is logged but operations continue.

4. **BFS for transitive_unblocks, DFS for chains.** BFS gives correct transitive closure. DFS with backtracking finds longest paths.

### 5. CLI Subcommands (`cli/task.py` extensions)

- **Purpose:** Expose all protocol operations as CLI commands
- **Responsibilities:**
  - Wire Typer commands to protocol methods
  - Support `--json`, `--agent`, and Rich output modes
  - Handle errors and display user-friendly messages
- **Dependencies:** `TaskBackend`, `AgentFormatter` (optional, from agent-output spec)

**New commands:**

| Command | Protocol method | Notes |
|---------|----------------|-------|
| `cub task blocked` | `list_blocked_tasks()` | With `--epic` filter |
| `cub task dep add <task> <dep>` | `add_dependency()` | Confirms success |
| `cub task dep remove <task> <dep>` | `remove_dependency()` | Confirms success |
| `cub task label add <task> <label>` | `add_label()` | Confirms success |
| `cub task label remove <task> <label>` | `remove_label()` | Confirms success |
| `cub task label list <task>` | `get_task()` → show labels | Display only |
| `cub task reopen <task>` | `reopen_task()` | Confirms success |
| `cub task delete <task>` | `delete_task()` | Prompts for confirmation |
| `cub task search <query>` | `search_tasks()` (P2) | Full-text search |

**Enhanced existing commands:**

| Command | Enhancement |
|---------|-------------|
| `cub task list` | Add `--epic`, `--assignee` filters |
| `cub task ready` | Add `--epic`, `--by impact\|priority` ordering |
| `cub task create` | Already in protocol; ensure CLI has `--type`, `--priority`, `--epic`, `--description`, `--depends-on` |
| `cub task update` | Already in protocol; ensure CLI has `--title`, `--description`, `--priority`, `--notes`, `--assignee` |

### 6. Skill and Doc Updates

- **Purpose:** Make `cub task` the authoritative interface everywhere
- **Files to update:**
  - `.claude/commands/cub.md` — replace `bd blocked` with `cub task blocked --agent`
  - `.claude/commands/cub:tasks.md` — add new subcommands to routing table
  - `CLAUDE.md` — replace `bd` examples with `cub task` equivalents
  - `.cub/PROMPT.md` — update runloop task instructions

## Data Model

### No new models needed

The `Task` model already has all fields needed:
- `depends_on: list[str]` — forward dependencies
- `blocks: list[str]` — reverse dependencies (populated by some backends)
- `labels: list[str]` — task labels
- `status: TaskStatus` — OPEN, IN_PROGRESS, CLOSED
- Methods: `add_label()`, `remove_label()`, `reopen()`, `close()`

### DependencyGraph (in-memory, no persistence)

Internal data structures:
```
_tasks: dict[str, Task]         — task lookup by ID
_forward: dict[str, set[str]]   — task_id → set of IDs it depends on
_reverse: dict[str, set[str]]   — task_id → set of IDs that depend on it
_closed: set[str]               — set of closed task IDs (resolved deps)
```

### TaskCounts extension

Add `blocked` count to existing `TaskCounts`:

```python
class TaskCounts(BaseModel):
    total: int
    open: int
    in_progress: int
    closed: int
    blocked: int = 0  # NEW: tasks with unresolved deps
```

## APIs / Interfaces

### TaskBackend Protocol (internal Python API)

- **Type:** Protocol (typing.Protocol, runtime_checkable)
- **Purpose:** Abstract task storage operations
- **Key new methods:**
  - `add_dependency(task_id, depends_on) -> Task`
  - `remove_dependency(task_id, depends_on) -> Task`
  - `list_blocked_tasks(parent?) -> list[Task]`
  - `reopen_task(task_id) -> Task`
  - `delete_task(task_id) -> bool`
  - `add_label(task_id, label) -> Task`
  - `remove_label(task_id, label) -> Task`

### DependencyGraph (internal Python API)

- **Type:** Pure query object
- **Purpose:** Dependency analysis for `--agent` output and task selection
- **Key methods:**
  - `direct_unblocks(task_id) -> list[str]`
  - `transitive_unblocks(task_id) -> set[str]`
  - `root_blockers(limit) -> list[tuple[str, int]]`
  - `chains(limit) -> list[list[str]]`
  - `would_become_ready(task_id) -> list[str]`
  - `has_cycle() -> bool`

### CLI (Typer subcommands)

- **Type:** CLI
- **Purpose:** User-facing task management
- **Output modes:** Rich (default), `--json`, `--agent`

## Implementation Phases

### Phase 1: Protocol & DependencyGraph
**Goal:** Backend protocol extended, both backends implement new methods, DependencyGraph available.

1. Add 7 new methods to `TaskBackend` protocol in `backend.py`
2. Create `TaskBackendDefaults` mixin with default implementations
3. Implement new methods in `BeadsBackend` (wrapping bd commands)
4. Implement new methods in `JsonlBackend` (in-memory operations)
5. Update `BothBackend` to delegate new methods
6. Create `DependencyGraph` class in `core/tasks/graph.py`
7. Write tests for all new protocol methods (parametrized across backends)
8. Write tests for `DependencyGraph` (linear chain, diamond, forest, cycle topologies)

### Phase 2: CLI Subcommands
**Goal:** All new task operations available as CLI commands with three output modes.

1. Add `cub task blocked` command with `--epic`, `--json`, `--agent`
2. Add `cub task dep add/remove` commands
3. Add `cub task label add/remove/list` commands
4. Add `cub task reopen` command
5. Add `cub task delete` command (with confirmation prompt)
6. Enhance `cub task list` with `--epic`, `--assignee` filters
7. Enhance `cub task ready` with `--epic` filter and `--by impact|priority`
8. Ensure `cub task create` CLI exposes full flag set
9. Ensure `cub task update` CLI exposes individual field flags (`--title`, `--priority`, `--notes`)
10. Write CLI tests

### Phase 3: Skill & Doc Updates
**Goal:** `cub task` is the only task interface in skills, router, and docs.

1. Update `.claude/commands/cub.md` router — replace `bd blocked` with `cub task blocked --agent`
2. Update `.claude/commands/cub:tasks.md` — add new subcommands
3. Update `CLAUDE.md` — replace `bd` examples with `cub task` equivalents
4. Update `.cub/PROMPT.md` runloop task instructions
5. Audit all skill files for remaining `bd` references

### Phase 4: Search (P2)
**Goal:** Full-text search across tasks.

1. Add `search_tasks(query)` to protocol
2. Implement in BeadsBackend (wraps `bd search`)
3. Implement in JsonlBackend (substring match on title + description)
4. Add `cub task search <query>` CLI command

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Protocol extension breaks BothBackend | H | M | BothBackend inherits `TaskBackendDefaults`; test delegation for all new methods |
| bd CLI output format changes | M | L | Beads backend already handles non-JSON responses; follow established `_run_bd` patterns |
| DependencyGraph cycles in real data | M | L | `has_cycle()` detection + visited sets in traversal. Log warning, don't crash. |
| `delete_task` is destructive | H | L | CLI prompts for confirmation. Protocol method has no confirmation — caller's responsibility. |
| `update_task` signature doesn't cover `--title`, `--priority`, `--notes` | M | H | Protocol's `update_task` only has status/assignee/description/labels. Need to extend signature or add separate methods. |

**Note on `update_task` risk:** The current protocol signature is:
```python
def update_task(self, task_id, status?, assignee?, description?, labels?) -> Task
```
This is missing `title`, `priority`, and `notes`. Options:
1. **Extend the signature** — add optional `title`, `priority`, `notes` parameters. Breaking change but both backends need updating anyway.
2. **Use kwargs** — `**kwargs` for extensibility. Loses type safety.
3. **Separate methods** — `set_title()`, `set_priority()`. Too granular.

**Recommendation:** Option 1 — extend the signature. We're already touching both backends for 7 new methods. Adding 3 parameters to an existing method is minor. The `cli/task.py` update command already calls `update_task` with the existing parameters; adding more is backward-compatible since they're all optional.

## Dependencies

### External
- `bd` CLI (beads) — for BeadsBackend method implementations
- No new external dependencies

### Internal
- `Task` model (`core/tasks/models.py`) — consumed by DependencyGraph and all new methods
- `TaskBackend` protocol (`core/tasks/backend.py`) — extended with 7 methods
- `BeadsBackend` (`core/tasks/beads.py`) — implements new methods
- `JsonlBackend` (`core/tasks/jsonl.py`) — implements new methods
- `BothBackend` (`core/tasks/both.py`) — delegates new methods
- `AgentFormatter` (from agent-output spec) — optional, for `--agent` output

## Security Considerations

`delete_task` is the only destructive operation. The CLI prompts for confirmation. The protocol method does not — it's the caller's responsibility. In `cub run` (autonomous mode), `delete_task` should never be called without explicit user instruction. This is consistent with how `close_task` works today.

## Future Considerations

- **Protocol versioning**: If the protocol grows much further, consider a capability-based approach where backends declare what they support. Not needed yet at 19 methods.
- **Bulk operations**: `close_tasks(ids)`, `delete_tasks(ids)` for batch processing. Add when the need arises.
- **Task search indexing**: JsonlBackend's substring search is O(n). If projects exceed 1000 tasks, consider SQLite-backed search. Not needed at personal scale.
- **`update_task` refactor**: The growing parameter list could be replaced by an `UpdateTaskRequest` Pydantic model. Consider when adding more updatable fields.

---

**Next Step:** Run `cub itemize` to generate implementation tasks.
