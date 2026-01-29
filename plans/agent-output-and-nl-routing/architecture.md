# Architecture Design: Agent Output and Natural Language Routing

**Date:** 2026-01-29
**Mindset:** Production
**Scale:** Personal
**Status:** Approved

---

## Technical Summary

This architecture adds three capabilities to cub: (1) an `--agent` flag on CLI commands that produces structured markdown optimized for LLM consumption, (2) updates to passthrough skill files to use `--agent`, and (3) a hook-based route learning system.

The design follows cub's existing layered architecture. A new `AgentFormatter` module in the service layer transforms existing service data (ProjectStats, Suggestion, Task) into compact markdown with pre-computed analysis hints. No new data models are needed — the formatter consumes what services already return. Route learning adds a thin observation layer to the existing hook infrastructure (4 lines of shell) and a new `routes` CLI subcommand for compilation.

The key architectural decision is that `AgentFormatter` accepts an **optional** `DependencyGraph` parameter. When the graph is available (after task parity ships), analysis sections include impact scoring and root blocker identification. Without it, analysis sections are omitted or reduced to flat counts. This decouples the `--agent` flag from the graph timeline.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing codebase |
| CLI | Typer (per-command `--agent` flag) | Matches existing `--json` pattern |
| Formatting | Plain string formatting (f-strings, `textwrap`) | No template engine needed — markdown is simple enough |
| Route storage | JSONL (append-only log) + Markdown (compiled output) | Matches existing forensics pattern; markdown for `@` file reference |
| Testing | pytest with snapshot tests | Verify exact markdown output for each formatter method |

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     CLI Layer                             │
│                                                          │
│  task.py    status.py    suggest.py                      │
│  ┌──────┐   ┌──────┐    ┌──────┐                        │
│  │--agent│   │--agent│    │--agent│                       │
│  │--json │   │--json │    │--json │                       │
│  └──┬───┘   └──┬───┘    └──┬───┘                        │
│     │          │            │                             │
│     └────┬─────┴──────┬─────┘                            │
│          ▼            ▼                                   │
│   ┌──────────┐  ┌───────────┐                            │
│   │  Agent   │  │  Service  │                            │
│   │Formatter │  │  Layer    │                            │
│   │(new)     │  │(existing) │                            │
│   └──────────┘  └───────────┘                            │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                   Route Learning                          │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │cub-hook  │    │cub routes    │    │cub.md router  │  │
│  │.sh       │───▶│compile       │───▶│skill file     │  │
│  │(observe) │    │(compile)     │    │(@file ref)    │  │
│  └──────────┘    └──────────────┘    └───────────────┘  │
│                                                          │
│  .cub/route-log  .cub/learned-     .claude/commands/    │
│  .jsonl          routes.md          cub.md              │
└──────────────────────────────────────────────────────────┘
```

## Components

### 1. AgentFormatter (`src/cub/core/services/agent_format.py`)

- **Purpose:** Renders service-layer data as structured markdown for LLM consumption
- **Responsibilities:**
  - Format task lists (ready, blocked, list) as markdown tables with analysis
  - Format single task detail with dependency context
  - Format project stats with epic breakdown
  - Format suggestions as prioritized action table
  - Format ledger entries with cost summary
  - Apply consistent envelope template (heading, summary, tables, analysis)
  - Enforce truncation (default: show all if ≤ 15, truncate to 10 if > 15)
- **Dependencies:** `Task`, `ProjectStats`, `EpicProgress`, `Suggestion` models (all existing). Optional `DependencyGraph` (from task parity spec).
- **Interface:** Static methods, one per command output type. Each returns `str`.

```python
class AgentFormatter:
    DEFAULT_LIMIT: int = 10
    SHOW_ALL_THRESHOLD: int = 15

    @staticmethod
    def format_ready(
        tasks: list[Task],
        graph: DependencyGraph | None = None,
    ) -> str: ...

    @staticmethod
    def format_task_detail(
        task: Task,
        graph: DependencyGraph | None = None,
        epic_progress: EpicProgress | None = None,
    ) -> str: ...

    @staticmethod
    def format_status(
        stats: ProjectStats,
        epic_progress: list[EpicProgress] | None = None,
    ) -> str: ...

    @staticmethod
    def format_suggestions(
        suggestions: list[Suggestion],
    ) -> str: ...

    @staticmethod
    def format_blocked(
        tasks: list[Task],
        graph: DependencyGraph | None = None,
    ) -> str: ...

    @staticmethod
    def format_ledger(
        entries: list[LedgerEntry],
        stats: LedgerStats | None = None,
    ) -> str: ...

    @staticmethod
    def format_doctor(
        checks: list[DiagnosticResult],
    ) -> str: ...

    @staticmethod
    def _truncation_notice(shown: int, total: int) -> str:
        """Returns 'Showing N of M. Use --all for complete list.' or empty string."""
        ...

    @staticmethod
    def _analysis_section(hints: list[str]) -> str:
        """Renders ## Analysis with bullet points. Empty string if no hints."""
        ...
```

**Design decisions:**

1. **Static methods, not instance methods.** No state to carry. Each method is a pure function from data → string.

2. **Optional graph parameter.** When `None`, analysis hints that require graph queries are omitted. The output still has the summary, tables, and truncation — just no "Highest impact" or "Root blocker" lines. This lets Phase 1 ship without waiting for DependencyGraph.

3. **No Rich, no console.** The formatter returns plain strings. The CLI layer calls `console.print()` on the result. This keeps the formatter testable without terminal dependencies.

4. **Truncation is data-driven.** The formatter receives the full list and truncates internally, adding the notice. The caller doesn't need to pre-filter.

### 2. CLI Integration (modifications to existing files)

Each supporting command gets an `--agent` flag following the existing `--json` pattern:

**`src/cub/cli/task.py`** — `ready()`, `show()`, (future: `blocked()`, `list_tasks()`)
**`src/cub/cli/status.py`** — `status()`
**`src/cub/cli/suggest.py`** — `suggest()`
(Future: `src/cub/cli/ledger.py`, `src/cub/cli/doctor.py`)

Pattern for each command:

```python
def ready(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    agent: bool = typer.Option(False, "--agent", help="Output for LLM consumption"),
) -> None:
    backend = get_backend(project_dir)
    tasks = backend.get_ready_tasks()

    if agent:
        # Optional: build graph if available
        graph = _try_build_graph(backend)
        console.print(AgentFormatter.format_ready(tasks, graph=graph))
        return

    if json_output:
        console.print(json.dumps([t.model_dump(mode="json") for t in tasks]))
        return

    # ... existing Rich output ...
```

The `_try_build_graph` helper attempts to import and construct a `DependencyGraph`. If the class doesn't exist yet (task parity not landed), it returns `None`. This avoids hard coupling:

```python
def _try_build_graph(backend: TaskBackend) -> DependencyGraph | None:
    """Build dependency graph if available. Returns None if not yet implemented."""
    try:
        from cub.core.tasks.graph import DependencyGraph
        all_tasks = backend.list_tasks()
        return DependencyGraph(all_tasks)
    except (ImportError, Exception):
        return None
```

### 3. Route Observation (`cub-hook.sh` modification)

Add 4 lines to the existing PostToolUse/Bash handler in `cub-hook.sh`:

```bash
# In the PostToolUse/Bash handler, after existing cub command detection
case "$TOOL_INPUT" in
  cub\ *)
    echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"cmd\":\"$TOOL_INPUT\"}" \
      >> "$PROJECT_DIR/.cub/route-log.jsonl"
    ;;
esac
```

- Appends to `.cub/route-log.jsonl` (gitignored)
- No Python startup latency
- Runs inside the existing fast-path filter, so only fires for Bash tool uses containing `cub `
- Double-tracking prevention inherited from existing `CUB_RUN_ACTIVE` check

### 4. Route Compilation (`src/cub/cli/routes.py`)

New CLI subcommand: `cub routes compile`

```python
app = typer.Typer(name="routes", help="Manage learned command routes.")

@app.command()
def compile(
    project_dir: Path = typer.Option(Path("."), "--project-dir"),
    min_count: int = typer.Option(3, "--min-count", help="Minimum uses to include"),
    max_entries: int = typer.Option(1000, "--max-entries", help="Max log entries to process"),
) -> None:
    """Compile route-log.jsonl into learned-routes.md."""
    ...
```

**Compilation logic** (pure function, testable):

```python
# core/routes/compiler.py

@dataclass
class RouteStats:
    command: str         # Normalized command
    count: int           # Total invocations
    last_used: str       # ISO date of most recent use

def normalize_command(raw: str) -> str:
    """Strip task IDs, file paths, and values from commands.

    'cub task show cub-r6s.1 --full' → 'cub task show'
    'cub run --task cub-042'         → 'cub run --task'
    'cub status'                     → 'cub status'
    """
    ...

def compile_routes(
    log_path: Path,
    min_count: int = 3,
    max_entries: int = 1000,
) -> list[RouteStats]:
    """Read log, normalize, aggregate, filter, sort by frequency."""
    ...

def render_learned_routes(routes: list[RouteStats]) -> str:
    """Render as markdown table for @file reference."""
    ...
```

**Trigger**: Stop hook in `cub-hook.sh` calls `python3 -m cub.cli.routes compile &` (background, non-blocking).

### 5. Route Surfacing (`.claude/commands/cub.md` modification)

Add a section to the router skill file:

```markdown
## Learned Routes

If @.cub/learned-routes.md exists, check it for frequently-used commands.
When the user's intent could map to multiple commands, prefer ones that
appear in the learned routes table (they've been useful before).
```

This is the only point where LLM judgment enters the route learning system.

### 6. Passthrough Skill Updates

Update 7 existing skill files in `.claude/commands/` to use `--agent`:

| Skill file | Change |
|-----------|--------|
| `cub:tasks.md` | `cub task ready` → `cub task ready --agent` |
| `cub:status.md` | `cub status` → `cub status --agent` |
| `cub:suggest.md` | `cub suggest` → `cub suggest --agent` |
| `cub:ledger.md` | `cub ledger show` → `cub ledger show --agent` (Phase 2) |
| `cub:doctor.md` | `cub doctor` → `cub doctor --agent` (Phase 3) |
| `cub:run.md` | No change (run doesn't have `--agent`) |
| `cub:audit.md` | `cub audit` → `cub audit --agent` (Phase 3) |

Also update the router skill (`cub.md`) to use `--agent` in its command mappings:

```diff
- | "what tasks/work are ready" | `cub task ready` |
+ | "what tasks/work are ready" | `cub task ready --agent` |
```

## Data Model

### No new persistent models needed

All data consumed by `AgentFormatter` comes from existing models:
- `Task` (from `core/tasks/models.py`) — id, title, priority, status, depends_on, blocks, parent, description
- `ProjectStats` (from `core/services/models.py`) — task counts, epic counts, cost, git state
- `EpicProgress` (from `core/services/models.py`) — per-epic task breakdown
- `Suggestion` (from `core/suggestions/models.py`) — category, title, rationale, action, priority_score
- `DependencyGraph` (from `core/tasks/graph.py`, future) — query methods, no persistence

### Route learning data

**Route log** (`.cub/route-log.jsonl`, gitignored, append-only):
```json
{"ts": "2026-01-29T10:30:00Z", "cmd": "cub task ready"}
```

**Compiled routes** (`.cub/learned-routes.md`, git-tracked):
```markdown
# Learned Routes
...
| Command | Times used | Last used |
|---------|-----------|-----------|
| `cub task ready` | 24 | 2026-01-29 |
```

### RouteStats (in-memory only, for compilation)

```python
@dataclass
class RouteStats:
    command: str       # Normalized command string
    count: int         # Frequency
    last_used: str     # ISO date
```

## APIs / Interfaces

### AgentFormatter (internal Python API)

- **Type:** Internal module, no network API
- **Purpose:** Transform service data → markdown strings
- **Key Methods:**
  - `format_ready(tasks, graph?) -> str`
  - `format_task_detail(task, graph?, epic_progress?) -> str`
  - `format_status(stats, epic_progress?) -> str`
  - `format_suggestions(suggestions) -> str`
  - `format_blocked(tasks, graph?) -> str` (Phase 2)
  - `format_ledger(entries, stats?) -> str` (Phase 2)
  - `format_doctor(checks) -> str` (Phase 3)

### Route CLI (new subcommand)

- **Type:** CLI (Typer subcommand)
- **Purpose:** Compile and manage learned routes
- **Key Commands:**
  - `cub routes compile` — compile route log → learned routes file
  - `cub routes show` — display current learned routes (optional, for debugging)
  - `cub routes clear` — reset route log and compiled routes (optional)

## Implementation Phases

### Phase 1: Core `--agent` Output
**Goal:** Four commands produce LLM-optimized output. Skills updated to use it.

1. Create `AgentFormatter` module with `format_ready`, `format_task_detail`, `format_status`, `format_suggestions` methods
2. Add `--agent` flag to `cub task ready`, `cub task show`, `cub status`, `cub suggest`
3. Wire `_try_build_graph` helper (returns `None` until task parity lands)
4. Update passthrough skill files and router skill to use `--agent`
5. Write unit tests (snapshot tests for each format method)
6. Write token budget test (assert < 2000 chars for representative inputs)

### Phase 2: Route Learning
**Goal:** Command usage is observed, compiled, and surfaced to the router.

1. Add route logging to `cub-hook.sh` (4 lines of shell)
2. Create `core/routes/compiler.py` with normalize + compile + render functions
3. Create `cli/routes.py` with `compile` subcommand
4. Add Stop hook trigger for background compilation
5. Add learned routes section to router skill
6. Add `.cub/route-log.jsonl` to `.gitignore`
7. Write tests for normalization and compilation

### Phase 3: Extended Commands (after task parity)
**Goal:** More commands get `--agent` support using DependencyGraph.

1. Add `format_blocked` and `format_ledger` to AgentFormatter (blocked needs graph)
2. Add `--agent` flag to `cub task blocked`, `cub task list`, `cub ledger show`
3. Update DependencyGraph integration in `_try_build_graph` (now returns real graph)
4. Update remaining skill files

### Phase 4: Doctor Refactor (optional)
**Goal:** Doctor command returns structured data for `--agent` formatting.

1. Refactor `doctor` to return `list[DiagnosticResult]` instead of printing directly
2. Add `format_doctor` to AgentFormatter
3. Add `--agent` to `cub doctor` and `cub audit`

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| DependencyGraph not available for Phase 1 | M | H | `_try_build_graph` returns None; analysis hints omitted gracefully |
| `--agent` output exceeds 500-token budget | M | L | Truncation built into formatter; snapshot tests verify size |
| Claude ignores or parrots analysis hints | M | M | Skill instructions say "informational, not authoritative"; 10+ invocation validation |
| Route log grows unbounded | L | L | Personal scale; add rotation if log exceeds 10K entries |
| cub-hook.sh modification breaks existing hooks | H | L | Shell change is additive (new case branch); test with existing hook test suite |
| Stop hook background compilation fails silently | L | M | Best-effort; compiled file is optional for routing. Add error logging. |

## Dependencies

### External
- None new. Existing: beads CLI, Claude Code hooks, git

### Internal
- `DependencyGraph` (from task parity spec) — optional for Phase 1, required for Phase 3
- `StatusService`, `SuggestionService` — existing, consumed as-is
- `TaskBackend` protocol — existing, consumed as-is
- `LedgerService` — existing, consumed for Phase 2 ledger formatter
- `cub-hook.sh` — existing, extended with route logging

## Security Considerations

Minimal security surface. Route logs contain command strings (no credentials or user data). Compiled routes are git-tracked, so team members can review what's shared. The `--agent` flag doesn't expose any data not already available via `--json`.

## Future Considerations

- **Daemon**: Route compilation could move from Stop hook to a persistent daemon for continuous compilation and other background work. Separate companion spec.
- **MCP server**: `--agent` formatted output could be exposed as MCP tool results with `structuredContent` for richer client integration.
- **Phrase-level learning**: Log the NL input alongside commands by parsing hook context. Deferred until command frequency proves insufficient.
- **Route decay**: Time-weight frequency counts so stale patterns fade. Not needed at personal scale.

---

**Next Step:** Run `cub itemize` to generate implementation tasks.
