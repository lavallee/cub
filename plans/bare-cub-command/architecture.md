# Architecture Design: Bare Cub Command & In-Harness Mode Fluidity

**Date:** 2026-01-28
**Mindset:** Production
**Scale:** Personal → Team (open source alpha)
**Status:** Draft

---

## Technical Summary

This architecture refactors cub from a CLI-first tool to a core-first tool with thin interface layers. The primary deliverable is making `cub` (bare command) the unified entry point that launches a harness with opinionated project-aware guidance—but the enabling architecture is a clean separation between `cub.core` (business logic, interface-agnostic) and interface layers (CLI, harness skills, web, future daemon).

The refactor extracts ~2500 lines of business logic from `cli/run.py` into `core/run/`, moves Rich-dependent rendering from 5 core modules to CLI, and introduces a service layer (`core/services/`) that exposes clean operations for any interface to call. A new `SuggestionEngine` analyzes tasks, git state, ledger, and milestones to generate opinionated recommendations.

The bare `cub` command itself is a thin entry point: detect environment → generate welcome with suggestions → launch harness (or show inline status if already in one).

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing codebase, match/union types |
| CLI Framework | Typer | Existing, thin wrapper fits naturally |
| Data Models | Pydantic v2 | Existing, strong validation |
| Terminal UI | Rich | Existing, but confined to CLI layer only |
| Harness | Claude Code CLI/SDK | Alpha target harness |
| Task Storage | JSONL / Beads | Existing backends, interface-agnostic |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERFACE LAYER                               │
│                                                                       │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌─────────────────┐  │
│  │ CLI      │  │ Harness      │  │ Web      │  │ Future          │  │
│  │ (typer)  │  │ (skills/     │  │ (FastAPI │  │ (daemon,        │  │
│  │          │  │  hooks)      │  │  dash)   │  │  MCP, etc.)     │  │
│  │ Parses   │  │ Guided       │  │ REST     │  │                 │  │
│  │ args,    │  │ prompts,     │  │ routes,  │  │                 │  │
│  │ formats  │  │ slash        │  │ JSON     │  │                 │  │
│  │ output   │  │ commands     │  │ output   │  │                 │  │
│  │ w/ Rich  │  │              │  │          │  │                 │  │
│  └────┬─────┘  └──────┬───────┘  └────┬─────┘  └───────┬─────────┘  │
│       └───────────────┴──────────────┴─────────────────┘             │
│                              │                                        │
├──────────────────────────────┼────────────────────────────────────────┤
│                        SERVICE LAYER                                  │
│                     (cub.core.services)                               │
│                              │                                        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ RunService│  │PlanService│  │TaskService│  │SuggestionEngine │  │
│  │           │  │           │  │           │  │                  │  │
│  │ execute() │  │ orient()  │  │ list()    │  │ get_suggestions()│  │
│  │ run_once()│  │architect()│  │ claim()   │  │ get_welcome()    │  │
│  │ status()  │  │ itemize() │  │ close()   │  │ get_next_action()│  │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────────┬─────────┘  │
│        │               │              │                  │             │
│  ┌─────┴─────┐  ┌─────┴────┐  ┌──────┴──────┐  ┌──────┴──────────┐  │
│  │StatusSvc  │  │SessionSvc│  │ LedgerSvc   │  │ LaunchService   │  │
│  │           │  │          │  │             │  │                 │  │
│  │ summary() │  │ start()  │  │ query()     │  │ launch_harness()│  │
│  │ progress()│  │ end()    │  │ record()    │  │ detect_env()    │  │
│  │ health()  │  │ resume() │  │ stats()     │  │ is_nested()     │  │
│  └───────────┘  └──────────┘  └─────────────┘  └─────────────────┘  │
│                                                                       │
├───────────────────────────────────────────────────────────────────────┤
│                        DOMAIN LAYER                                   │
│                     (cub.core.* existing)                             │
│                                                                       │
│  ┌─ Harness ──────────┐  ┌─ Tasks ──────────┐  ┌─ Ledger ────────┐  │
│  │ async_backend.py   │  │ backend.py       │  │ models.py       │  │
│  │ claude_sdk.py      │  │ beads.py         │  │ writer.py       │  │
│  │ claude_cli.py      │  │ jsonl.py         │  │ reader.py       │  │
│  │ codex.py           │  │ service.py       │  │                 │  │
│  └────────────────────┘  └──────────────────┘  └─────────────────┘  │
│                                                                       │
│  ┌─ Run (NEW) ────────┐  ┌─ Config ─────────┐  ┌─ Git ───────────┐  │
│  │ loop.py            │  │ models.py        │  │ branches/       │  │
│  │ prompt_builder.py  │  │ loader.py        │  │ github/         │  │
│  │ budget.py          │  │ defaults.py      │  │ git_utils.py    │  │
│  │ interrupt.py       │  └──────────────────┘  └─────────────────┘  │
│  │ git_ops.py         │                                              │
│  └────────────────────┘                                              │
│                                                                       │
│  ┌─ Plan ─────────────┐  ┌─ Status ─────────┐  ┌─ Session ───────┐  │
│  │ pipeline.py        │  │ models.py        │  │ manager.py      │  │
│  │ orient.py          │  │ writer.py        │  │ models.py       │  │
│  │ architect.py       │  │ aggregator.py    │  └─────────────────┘  │
│  │ itemize.py         │  └──────────────────┘                        │
│  │ claude.py          │                                              │
│  └────────────────────┘  ┌─ Circuit Breaker ─┐  ┌─ Suggestions ──┐  │
│                          │ circuit_breaker.py │  │ engine.py (NEW)│  │
│                          └────────────────────┘  │ sources.py     │  │
│                                                  │ ranking.py     │  │
│                                                  └────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Service Layer (`cub.core.services`)

**Purpose:** Clean API surface that any interface can call. Services are stateless orchestrators that compose domain operations.

**Design principle:** Every user-facing action maps to a service method. The method accepts typed inputs (dataclasses/Pydantic models), returns typed outputs, raises typed exceptions. No Rich, no sys.exit, no print statements.

#### RunService
- **Purpose:** Orchestrate task execution (extracted from `cli/run.py`)
- **Responsibilities:**
  - `execute(config, task_filter, mode)` → Run loop state machine
  - `run_once(config, task_id)` → Single task execution
  - `get_status()` → Current run state
- **Dependencies:** HarnessBackend, TaskBackend, LedgerWriter, CircuitBreaker, BudgetManager
- **Interface:** Returns `RunResult` (tasks completed, costs, errors)

#### PlanService
- **Purpose:** Orchestrate planning pipeline
- **Responsibilities:**
  - `orient(spec_path, mode)` → Requirements refinement
  - `architect(orient_path, mode)` → Technical design
  - `itemize(arch_path, mode)` → Task decomposition
  - `run_pipeline(spec_path, phases)` → Full pipeline
- **Dependencies:** PlanPipeline, HarnessBackend (for Claude invocation)
- **Interface:** Returns `PlanResult` (artifacts produced, status)

#### TaskService (existing, enhance)
- **Purpose:** Task CRUD and queries
- **Responsibilities:**
  - `list(filters)` → Filtered task list
  - `ready()` → Tasks ready to work
  - `claim(task_id, session_id)` → Claim task
  - `close(task_id, reason)` → Close task
  - `stale_epics()` → Epics ready to close
- **Dependencies:** TaskBackend
- **Interface:** Returns `Task` models

#### SuggestionEngine (NEW)
- **Purpose:** Analyze project state and recommend next actions
- **Responsibilities:**
  - `get_suggestions(limit)` → Ranked list of suggested actions
  - `get_welcome()` → Welcome message with stats + top suggestion
  - `get_next_action()` → Single best recommendation with rationale
- **Dependencies:** TaskService, LedgerService, GitState, MilestoneDetector
- **Interface:** Returns `Suggestion` models with action, rationale, priority

#### LaunchService (NEW)
- **Purpose:** Detect environment and launch harness sessions
- **Responsibilities:**
  - `detect_environment()` → Am I in a harness? Which one? Session ID?
  - `is_nested()` → Would launching create a nested session?
  - `launch_harness(harness, context, resume, continue_flag)` → Start harness
  - `get_session_id()` → Retrieve current/last session ID for resume
- **Dependencies:** HarnessBackend, Config, environment variables
- **Interface:** Returns `LaunchResult` or `EnvironmentInfo`

#### StatusService
- **Purpose:** Project state summary
- **Responsibilities:**
  - `summary()` → High-level stats (counts, health)
  - `progress(epic_id)` → Epic progress
  - `health()` → Project health indicators
- **Dependencies:** TaskService, LedgerService, GitState

#### LedgerService
- **Purpose:** Query and record completed work
- **Responsibilities:**
  - `query(filters)` → Search ledger entries
  - `record(entry)` → Write ledger entry
  - `stats(period)` → Completion statistics
  - `recent(n)` → Last N completions
- **Dependencies:** LedgerReader, LedgerWriter

#### SessionService
- **Purpose:** Session lifecycle
- **Responsibilities:**
  - `start(task_id, harness)` → Begin session
  - `end(session_id, result)` → Finalize session
  - `resume(session_id)` → Resume previous session
  - `current()` → Get current session info
- **Dependencies:** SessionManager, LedgerService

### 2. Run Package (`cub.core.run`) — Extracted from `cli/run.py`

**Purpose:** All run loop business logic, independent of CLI.

| Module | Extracted From | Purpose |
|--------|---------------|---------|
| `loop.py` | `cli/run.py` main loop | State machine: pick task → execute → record → next |
| `prompt_builder.py` | `cli/run.py` prompt generation | Build system prompt + task context from AGENT.md, specs, plans |
| `budget.py` | `cli/run.py` budget tracking | Token/cost accounting, limit enforcement |
| `interrupt.py` | `cli/run.py` signal handling | SIGINT/SIGTERM handling, clean shutdown |
| `git_ops.py` | `cli/run.py` branch creation | Branch naming, creation, commit tracking |

### 3. Suggestion Engine (`cub.core.suggestions`)

**Purpose:** Analyze project state and produce ranked, opinionated recommendations.

| Module | Purpose |
|--------|---------|
| `engine.py` | Main entry point, composes sources, ranks results |
| `sources.py` | Data source adapters (tasks, git, ledger, milestones) |
| `ranking.py` | Priority scoring algorithm |
| `models.py` | `Suggestion`, `ProjectSnapshot`, `Milestone` models |

#### Suggestion Sources

| Source | What It Provides | Priority Signal |
|--------|-----------------|-----------------|
| **TaskSource** | Ready tasks, stale epics, blocked work | P0 stale epics, P1 ready tasks by priority |
| **GitSource** | Recent commits, uncommitted changes, branch state | Stale branches, unpushed work |
| **LedgerSource** | Recent completions, cost trends, velocity | Momentum direction, cost warnings |
| **MilestoneSource** | Version targets, CHANGELOG, sketches, specs | Goal awareness, "what's blocking release" |

#### Suggestion Model

```python
@dataclass
class Suggestion:
    action: str           # "Close 9 completed epics"
    rationale: str        # "All tasks in these epics are done"
    command: str | None   # "bd close cub-r1a cub-r1b ..." (optional)
    priority: float       # 0.0-1.0 ranking score
    category: str         # "housekeeping" | "execution" | "planning" | "release"
    source: str           # "tasks" | "git" | "ledger" | "milestone"
```

#### Ranking Algorithm

```
score = base_priority × urgency_multiplier × recency_decay

base_priority:
  stale_epic_close    = 0.9  (quick win, unblocks reporting)
  p0_ready_task       = 0.85 (highest priority work)
  milestone_blocker   = 0.8  (blocks release goal)
  low_complexity_task = 0.7  (low-hanging fruit)
  cost_warning        = 0.6  (budget awareness)
  unpushed_work       = 0.5  (hygiene)

urgency_multiplier:
  stale > 7 days      = 1.5x
  stale > 3 days      = 1.2x

recency_decay:
  recently_suggested  = 0.5x (don't repeat same suggestion)
```

### 4. Launch Service (`cub.core.launch`)

**Purpose:** Environment detection and harness launch orchestration.

| Module | Purpose |
|--------|---------|
| `detector.py` | Detect current environment (terminal, harness, nested) |
| `launcher.py` | Launch harness with context |
| `welcome.py` | Generate welcome message content |
| `models.py` | `EnvironmentInfo`, `LaunchConfig`, `WelcomeMessage` |

#### Environment Detection

```python
def detect_environment() -> EnvironmentInfo:
    """Detect whether we're in a terminal, harness, or nested session."""

    # Check for nesting
    if os.environ.get("CUB_SESSION_ACTIVE"):
        return EnvironmentInfo(context="nested", session_id=os.environ.get("CUB_SESSION_ID"))

    # Check for harness-specific env vars
    if os.environ.get("CLAUDE_CODE"):
        return EnvironmentInfo(context="harness", harness="claude")

    # Default: terminal
    return EnvironmentInfo(context="terminal")
```

#### Bare `cub` Flow

```
cub (no args)
  │
  ├─ detect_environment()
  │   ├─ "nested" → show inline status + suggestions (no nesting)
  │   ├─ "harness" → show inline status + suggestions (already in one)
  │   └─ "terminal" → continue to launch
  │
  ├─ get_welcome() from SuggestionEngine
  │   ├─ project stats (tasks, epics, health)
  │   ├─ top recommendation with rationale
  │   └─ available modes/skills
  │
  ├─ resolve harness
  │   ├─ config.harness.name or auto-detect
  │   └─ validate available
  │
  └─ launch_harness()
      ├─ set CUB_SESSION_ACTIVE=1
      ├─ set CUB_SESSION_ID=<uuid>
      ├─ pass --resume / --continue if specified
      ├─ inject welcome as initial context
      └─ exec claude [flags]
```

### 5. Thin CLI Layer (`cub.cli`)

**Design rule:** CLI modules handle ONLY:
1. Argument parsing (Typer decorators)
2. Calling service methods
3. Formatting output with Rich
4. Exit codes

**Example pattern:**

```python
# cli/run.py — AFTER refactor (thin)
from cub.core.services import RunService, RunConfig

def run(
    once: bool = typer.Option(False),
    epic: str | None = typer.Option(None),
    harness: str | None = typer.Option(None),
    # ... other CLI args
) -> None:
    """Execute autonomous task loop with AI harness."""
    config = RunConfig(once=once, epic=epic, harness=harness, ...)
    service = RunService.from_config(load_config())

    with Live(RunDisplay()) as display:  # Rich rendering
        for event in service.execute(config):
            display.update(event)  # CLI-specific rendering

    raise typer.Exit(0)
```

```python
# cli/default.py — bare `cub` handler (NEW)
from cub.core.services import LaunchService, SuggestionEngine

def default(
    resume: bool = typer.Option(False),
    continue_: bool = typer.Option(False, "--continue"),
) -> None:
    """Launch cub — the unified entry point."""
    launch = LaunchService.from_config(load_config())
    env = launch.detect_environment()

    if env.is_nested:
        # Already in a harness — show inline status
        suggestions = SuggestionEngine.from_config(load_config())
        welcome = suggestions.get_welcome()
        console.print(format_welcome(welcome))  # Rich formatting
        raise typer.Exit(0)

    # Launch harness
    welcome = SuggestionEngine.from_config(load_config()).get_welcome()
    launch.launch_harness(
        context=welcome,
        resume=resume,
        continue_=continue_,
    )
```

### 6. Rich Boundary Cleanup

Move terminal rendering out of core into CLI:

| Current Location | Issue | New Location |
|-----------------|-------|-------------|
| `core/review/reporter.py` | Full Rich dependency | `cli/review/display.py` |
| `core/pr/service.py` | Console import | Return data; `cli/pr.py` renders |
| `core/worktree/parallel.py` | Console progress | Emit events; `cli/worktree.py` renders |
| `core/bash_delegate.py` | Console + sys.exit | Move to `cli/delegated/` |
| `core/harness/hooks.py` | Rich logging | Use Python `logging` module |

**Pattern:** Core modules return structured data (Pydantic models, dataclasses). CLI modules render that data with Rich.

## Data Model

### Suggestion
```
action: str              — What to do ("Close 9 completed epics")
rationale: str           — Why ("All tasks done, epics blocking stats")
command: str | None      — CLI command if applicable
skill: str | None        — Skill name if applicable ("/cub:orient")
priority: float          — 0.0-1.0 ranking score
category: SuggestionCategory — housekeeping | execution | planning | release
source: str              — Data source that generated this
```

### WelcomeMessage
```
version: str             — Current cub version
project_name: str        — Project name
stats: ProjectStats      — Task counts, epic counts, health
suggestions: list[Suggestion] — Ranked suggestions (top 3-5)
available_skills: list[SkillInfo] — Discoverable /cub:* skills
last_activity: str       — "Last commit: 2h ago"
```

### EnvironmentInfo
```
context: Literal["terminal", "harness", "nested"]
harness: str | None      — Which harness if in one
session_id: str | None   — Session ID if available
cub_version: str         — Current version
```

### RunEvent (for streaming run status to CLI)
```
type: Literal["task_start", "task_end", "budget_update", "stagnation", "error", "complete"]
task_id: str | None
message: str
data: dict[str, Any]     — Event-specific payload
timestamp: datetime
```

### Relationships
- `WelcomeMessage` contains `list[Suggestion]` and `ProjectStats`
- `RunService.execute()` yields `RunEvent` stream
- `SuggestionEngine` composes `TaskSource`, `GitSource`, `LedgerSource`, `MilestoneSource`
- `LaunchService` uses `EnvironmentInfo` to decide behavior

## APIs / Interfaces

### Service Layer API (Internal Python)
- **Type:** Python method calls
- **Purpose:** All business logic accessible to any interface
- **Key Methods:**
  - `RunService.execute(config) -> Iterator[RunEvent]`
  - `RunService.run_once(task_id) -> RunResult`
  - `SuggestionEngine.get_welcome() -> WelcomeMessage`
  - `SuggestionEngine.get_suggestions(limit) -> list[Suggestion]`
  - `LaunchService.detect_environment() -> EnvironmentInfo`
  - `LaunchService.launch_harness(context, resume, continue_) -> None`
  - `TaskService.ready() -> list[Task]`
  - `TaskService.stale_epics() -> list[Epic]`
  - `LedgerService.recent(n) -> list[LedgerEntry]`
  - `StatusService.summary() -> ProjectStats`

### CLI Interface (Typer)
- **Type:** Command-line
- **Purpose:** Terminal users
- **Pattern:** Parse args → call service → render with Rich

### Harness Interface (Skills + Hooks)
- **Type:** `.claude/commands/*.md` slash commands + hook scripts
- **Purpose:** In-session access to cub capabilities
- **Pattern:** Skill guides Claude → Claude calls `cub` CLI → service executes

### Web Interface (FastAPI — existing dashboard)
- **Type:** REST API
- **Purpose:** Browser-based project view
- **Pattern:** Route handler → call service → return JSON

## Implementation Phases

### Phase 1: Core Run Extraction
**Goal:** Move business logic from `cli/run.py` into `core/run/` package

- Extract loop state machine to `core/run/loop.py`
- Extract prompt builder to `core/run/prompt_builder.py`
- Extract budget tracking to `core/run/budget.py`
- Extract signal handling to `core/run/interrupt.py`
- Extract git operations to `core/run/git_ops.py`
- Make `cli/run.py` a thin wrapper that calls `core/run/`
- All existing tests must continue passing

### Phase 2: Rich Boundary Cleanup
**Goal:** Remove Rich imports from all `cub.core` modules

- Move `core/review/reporter.py` rendering to `cli/review/display.py`
- Move `core/pr/service.py` console output to `cli/pr.py`
- Move `core/worktree/parallel.py` progress to `cli/worktree.py`
- Move `core/bash_delegate.py` to `cli/delegated/`
- Replace Rich logging in `core/harness/hooks.py` with Python logging
- Verify: `grep -r "from rich" src/cub/core/` returns zero results

### Phase 3: Service Layer
**Goal:** Introduce `cub.core.services` as the public API surface

- Create `RunService` wrapping `core/run/` modules
- Create `StatusService` from status aggregation logic
- Enhance existing `TaskService` with `ready()`, `stale_epics()`
- Create `LedgerService` wrapping reader/writer
- Create `SessionService` wrapping session manager
- Create `LaunchService` for environment detection and harness launch
- Refactor CLI modules to call services instead of domain modules directly

### Phase 4: Suggestion Engine
**Goal:** Build the smart recommendation system

- Create `core/suggestions/models.py` (Suggestion, ProjectSnapshot)
- Create `core/suggestions/sources.py` (TaskSource, GitSource, LedgerSource, MilestoneSource)
- Create `core/suggestions/ranking.py` (priority scoring algorithm)
- Create `core/suggestions/engine.py` (compose sources, rank, filter)
- Create `SuggestionEngine` service
- Write tests with fixture data from current cub project state

### Phase 5: Bare `cub` Command
**Goal:** Implement the default command handler

- Create `cli/default.py` with bare `cub` handler
- Wire into `cli/__init__.py` (replace `no_args_is_help=True`)
- Support `--resume` and `--continue` passthrough
- Environment detection (terminal vs harness vs nested)
- Welcome message generation and display
- Harness launch with `CUB_SESSION_ACTIVE` env var
- Inline status display when nested

### Phase 6: Skill Discovery & Documentation
**Goal:** Make cub capabilities discoverable from within a harness session

- Create `/cub` meta-skill that lists available skills and commands
- Update welcome message to reference available skills
- Ensure all `/cub:*` skills are documented in CLAUDE.md
- Add `cub run --once` guidance for in-harness task execution
- Test full flow: bare `cub` → harness → use skills → exit

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Run extraction breaks subtle behavior | H | M | Comprehensive test coverage before refactor; run integration tests after each extraction step |
| Service layer adds unnecessary indirection | M | L | Keep services thin—orchestration only, no new logic. If a service just delegates to one module, skip the service. |
| Suggestion engine gives irrelevant advice | M | M | Start with simple heuristics (stale epics, ready tasks). Dogfood on cub project. Iterate. |
| Environment detection unreliable | M | M | Use multiple signals (env vars, process inspection). Degrade gracefully—if unsure, act as terminal. |
| Claude Code CLI changes break launch | L | L | Abstract CLI invocation behind LaunchService. Version-check if possible. |
| Refactor scope creep | H | H | Phase strictly. Each phase has a clear "done" state. Don't start Phase N+1 until N passes all tests. |

## Dependencies

### External
- **Claude Code CLI**: Harness launch, `--resume`/`--continue` flags
- **Beads CLI (`bd`)**: Task queries for suggestion engine
- **Git**: Branch state, recent commits for suggestions

### Internal
- **`cub.core.config`**: Configuration loading (clean, no changes needed)
- **`cub.core.harness`**: Harness backends (clean, no changes needed)
- **`cub.core.tasks`**: Task backends (clean, enhance TaskService)
- **`cub.core.ledger`**: Ledger storage (clean, wrap in LedgerService)
- **`cub.core.circuit_breaker`**: Stagnation detection (clean, move into run package)

## Security Considerations

- **Environment variables**: `CUB_SESSION_ACTIVE` and `CUB_SESSION_ID` are informational, not security boundaries. A malicious process could set them. This is acceptable for nesting detection (worst case: shows inline status instead of launching).
- **Harness launch**: `launch_harness()` execs the harness binary. Validate the binary path comes from config or auto-detection, not user input.
- **Suggestion engine**: Reads local files only (tasks, git, ledger). No network calls. No sensitive data in suggestions.

## Future Considerations

- **MCP tools for cub**: Expose services as MCP tools so Claude Code can call them natively (not via Bash)
- **Daemon mode**: `LaunchService` could be extended to manage a background daemon
- **Web dashboard integration**: `StatusService` and `SuggestionEngine` can power dashboard widgets
- **Multi-harness routing**: `RunService` could route tasks to different harnesses based on complexity labels
- **Plugin architecture**: Service layer is a natural extension point for third-party plugins

---

**Next Step:** Run `cub itemize` to break this into executable tasks.
