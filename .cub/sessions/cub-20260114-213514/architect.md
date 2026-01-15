# Architecture Design: Cub 0.21-0.25

**Date:** 2026-01-14
**Mindset:** Production
**Scale:** Product (1,000+ users)
**Status:** Approved

---

## Technical Summary

Cub 0.21-0.25 migrates from a Bash-based CLI to a full Python CLI while maintaining the existing pluggable architecture for task backends, AI harnesses, and adding new pluggable systems for sandbox providers.

The architecture uses modern Python tooling:
- **Typer** for type-safe CLI with auto-generated help and shell completion
- **Pydantic v2** for all data models with validation and serialization
- **Rich** for terminal output, progress bars, and live dashboard rendering
- **Protocol classes** for pluggable interfaces ensuring extensibility

The design prioritizes pluggability across all major subsystems (harnesses, task backends, sandbox providers, hooks) while keeping the implementation focused on the immediate needs (existing harnesses, Docker sandbox).

---

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | Python 3.10+ | Type hints, pattern matching, developer familiarity |
| **CLI Framework** | Typer | Type-safe, auto-generated help, shell completion |
| **Data Models** | Pydantic v2 | Validation, serialization, IDE support |
| **Terminal UI** | Rich | Dashboard rendering, progress bars, markdown |
| **Config Format** | TOML + JSON | `pyproject.toml` for project, JSON for runtime |
| **Testing** | pytest | Standard, good ecosystem, fixtures |
| **Packaging** | uv | Fast resolver, lockfiles, from Astral (ruff makers) |
| **Git Operations** | GitPython | Mature, feature-complete |
| **Subprocess** | subprocess (stdlib) | Reliable, well-understood |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         cub (Python CLI)                         │
│                    typer + rich + pydantic                       │
├─────────────────────────────────────────────────────────────────┤
│  cub run       │  cub status    │  cub audit   │  cub sandbox   │
│  cub monitor   │  cub worktree  │  cub init    │  cub doctor    │
└────────────────┴────────────────┴──────────────┴────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                       cub.core (library)                         │
├───────────────┬───────────────┬───────────────┬─────────────────┤
│   tasks/      │   config/     │   harness/    │   sandbox/      │
│  (backends)   │  (pydantic)   │  (backends)   │  (providers)    │
├───────────────┼───────────────┼───────────────┼─────────────────┤
│  • beads      │               │  • claude     │  • docker       │
│  • json       │               │  • codex      │  • (future)     │
│  • (future)   │               │  • gemini     │                 │
│               │               │  • opencode   │                 │
│               │               │  • (future)   │                 │
└───────────────┴───────────────┴───────────────┴─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     hooks/ (Bash scripts)                        │
│          User-extensible lifecycle hooks (remain as Bash)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
cub/
├── pyproject.toml              # uv/pip project config
├── uv.lock                     # Lockfile
├── src/
│   └── cub/
│       ├── __init__.py
│       ├── __main__.py         # Entry point: python -m cub
│       ├── cli/                # Typer CLI commands
│       │   ├── __init__.py     # Main app
│       │   ├── run.py          # cub run
│       │   ├── status.py       # cub status
│       │   ├── audit.py        # cub audit (0.22)
│       │   ├── monitor.py      # cub monitor (0.23)
│       │   ├── worktree.py     # cub worktree (0.24)
│       │   ├── sandbox.py      # cub sandbox (0.25)
│       │   └── init.py         # cub init
│       ├── core/               # Core business logic
│       │   ├── __init__.py
│       │   ├── tasks/          # Task management
│       │   │   ├── __init__.py
│       │   │   ├── models.py   # Pydantic models
│       │   │   ├── backend.py  # Protocol + registry
│       │   │   ├── beads.py    # Beads backend
│       │   │   └── json.py     # JSON backend
│       │   ├── config/         # Configuration
│       │   │   ├── __init__.py
│       │   │   ├── models.py   # Config models
│       │   │   └── loader.py   # Multi-layer loader
│       │   ├── harness/        # AI harness layer
│       │   │   ├── __init__.py
│       │   │   ├── backend.py  # Protocol + registry
│       │   │   ├── claude.py   # Claude Code
│       │   │   ├── codex.py    # OpenAI Codex
│       │   │   ├── gemini.py   # Google Gemini
│       │   │   └── opencode.py # OpenCode
│       │   ├── sandbox/        # Sandbox providers (0.25)
│       │   │   ├── __init__.py
│       │   │   ├── provider.py # Protocol + registry
│       │   │   └── docker.py   # Docker provider
│       │   └── worktree/       # Git worktree management (0.24)
│       │       ├── __init__.py
│       │       └── manager.py
│       ├── dashboard/          # Live dashboard (0.23)
│       │   ├── __init__.py
│       │   ├── renderer.py     # Rich-based rendering
│       │   └── status.py       # Status file management
│       ├── audit/              # Codebase health audit (0.22)
│       │   ├── __init__.py
│       │   ├── dead_code.py
│       │   ├── docs.py
│       │   └── coverage.py
│       └── utils/              # Shared utilities
│           ├── __init__.py
│           ├── git.py          # Git operations
│           ├── hooks.py        # Hook execution (calls Bash)
│           └── logging.py      # Structured JSONL logging
├── tests/
│   ├── conftest.py
│   ├── test_tasks/
│   ├── test_harness/
│   ├── test_config/
│   └── ...
├── hooks/                      # Bash hooks (user-extensible)
│   ├── pre-loop.d/
│   ├── post-loop.d/
│   ├── pre-task.d/
│   ├── post-task.d/
│   └── on-error.d/
└── legacy/                     # Preserved Bash (reference only)
    └── lib/
```

---

## Components

### Task Management (`cub.core.tasks`)

- **Purpose:** Unified interface for task CRUD operations across backends
- **Responsibilities:**
  - List, get, update, close tasks
  - Resolve dependencies (find ready tasks)
  - Filter by status, label, epic
  - Extract model labels for per-task model selection
- **Dependencies:** beads CLI (subprocess), prd.json file
- **Interface:** `TaskBackend` protocol with `BeadsBackend` and `JsonBackend` implementations

### Configuration (`cub.core.config`)

- **Purpose:** Multi-layer configuration with validation
- **Responsibilities:**
  - Load from project (.cub.json), user (~/.config/cub/config.json), defaults
  - Merge with correct precedence
  - Validate against schema
  - Provide typed access to config values
- **Dependencies:** None (stdlib json, tomllib)
- **Interface:** `CubConfig` Pydantic model with `load()` class method

### Harness Layer (`cub.core.harness`)

- **Purpose:** Abstract AI coding assistant interaction
- **Responsibilities:**
  - Detect available harnesses
  - Invoke harness with prompt
  - Stream output (where supported)
  - Report token usage
  - Handle capability differences
- **Dependencies:** AI CLI tools (subprocess)
- **Interface:** `HarnessBackend` protocol with implementations per harness

### Sandbox Providers (`cub.core.sandbox`)

- **Purpose:** Isolated execution environments
- **Responsibilities:**
  - Start/stop sandboxes
  - Stream logs
  - Generate diffs
  - Export/apply changes
  - Manage lifecycle
- **Dependencies:** Docker CLI (subprocess)
- **Interface:** `SandboxProvider` protocol with `DockerProvider` implementation

### Worktree Manager (`cub.core.worktree`)

- **Purpose:** Parallel development via git worktrees
- **Responsibilities:**
  - Create worktrees for tasks/epics
  - Manage worktree lifecycle
  - Coordinate parallel execution
  - Clean up merged worktrees
- **Dependencies:** git (subprocess or GitPython)
- **Interface:** `WorktreeManager` class

### Dashboard (`cub.dashboard`)

- **Purpose:** Real-time visibility into runs
- **Responsibilities:**
  - Render status to terminal (Rich)
  - Poll status.json for updates
  - Integrate with tmux
  - Show budget, tasks, recent events
- **Dependencies:** Rich, tmux
- **Interface:** `DashboardRenderer` class with `start()`, `stop()`, `update()`

### Audit (`cub.audit`)

- **Purpose:** Codebase health analysis
- **Responsibilities:**
  - Dead code detection (Python, Bash)
  - Documentation validation
  - Test coverage reporting
  - Generate actionable reports
- **Dependencies:** shellcheck, coverage.py, ast module
- **Interface:** `run_audit()` function returning `AuditReport`

---

## Data Models

### Task

```python
class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

class TaskPriority(str, Enum):
    P0 = "P0"  # Critical
    P1 = "P1"  # High
    P2 = "P2"  # Medium
    P3 = "P3"  # Low
    P4 = "P4"  # Backlog

class Task(BaseModel):
    id: str
    title: str
    description: str = ""
    type: str = "task"
    status: TaskStatus = TaskStatus.OPEN
    priority: TaskPriority = TaskPriority.P2
    depends_on: list[str] = []
    labels: list[str] = []
    parent: str | None = None
    notes: str = ""
```

### Configuration

```python
class GuardrailsConfig(BaseModel):
    max_task_iterations: int = 3
    max_run_iterations: int = 50
    iteration_warning_threshold: float = 0.8
    secret_patterns: list[str] = [...]

class BudgetConfig(BaseModel):
    default: int = 1_000_000
    warn_at: float = 0.8

class CubConfig(BaseModel):
    guardrails: GuardrailsConfig = GuardrailsConfig()
    budget: BudgetConfig = BudgetConfig()
    harness: HarnessConfig = HarnessConfig()
    hooks: HooksConfig = HooksConfig()
```

### Run Status

```python
class RunStatus(BaseModel):
    status: str  # running, complete, failed
    iteration: int
    max_iterations: int
    current_task: Task | None
    budget_used: int
    budget_limit: int
    tasks_completed: int
    tasks_total: int
    recent_events: list[dict]
    started_at: datetime
```

### Relationships

- `Task` → `Task`: dependency (depends_on)
- `Task` → `Epic`: parent relationship
- `RunStatus` → `Task`: current task reference
- `CubConfig` → all subsystem configs

---

## APIs / Interfaces

### Task Backend Protocol

```python
@runtime_checkable
class TaskBackend(Protocol):
    def list_tasks(
        self,
        status: TaskStatus | None = None,
        label: str | None = None,
        epic: str | None = None
    ) -> list[Task]: ...

    def get_task(self, task_id: str) -> Task | None: ...

    def get_ready_tasks(self, epic: str | None = None) -> list[Task]: ...

    def update_task(self, task_id: str, **updates) -> Task: ...

    def close_task(self, task_id: str, reason: str = "") -> Task: ...
```

### Harness Backend Protocol

```python
@runtime_checkable
class HarnessBackend(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> HarnessCapabilities: ...

    def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> HarnessResult: ...

    def invoke_streaming(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> Iterator[str]: ...
```

### Sandbox Provider Protocol

```python
@runtime_checkable
class SandboxProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> SandboxCapabilities: ...

    def start(self, project_dir: str, **options) -> str: ...
    def stop(self, sandbox_id: str) -> None: ...
    def status(self, sandbox_id: str) -> SandboxStatus: ...
    def logs(self, sandbox_id: str, follow: bool = False) -> Iterator[str]: ...
    def diff(self, sandbox_id: str) -> str: ...
    def export(self, sandbox_id: str, dest: str) -> None: ...
    def cleanup(self, sandbox_id: str) -> None: ...
```

---

## Implementation Phases

### Phase 1: Python Core (0.21)

**Goal:** Replace Bash core with Python CLI

- Set up Python project with uv, pyproject.toml
- Implement Pydantic models for Task, Config, Status
- Port TaskBackend protocol with BeadsBackend, JsonBackend
- Port HarnessBackend protocol with all 4 harnesses
- Create Typer CLI structure with core commands
- Add status.json generation to main loop
- Port/update tests to pytest
- Update installation docs

**Exit criteria:**
- `cub run` works end-to-end in Python
- Task operations < 100ms
- All existing functionality preserved

### Phase 2: Codebase Health Audit (0.22)

**Goal:** Formalize audit tooling

- Dead code detection (Python ast, shellcheck for Bash)
- Unused variable/function detection
- Documentation validation (links, code examples)
- Test coverage reporting
- `cub audit` command with summary and JSON output
- CI integration (exit codes, thresholds)

**Exit criteria:**
- `cub audit` produces actionable report
- Can run in CI with pass/fail thresholds

### Phase 3: Live Dashboard (0.23)

**Goal:** Real-time visibility

- Rich-based dashboard renderer
- Status file polling with 1s refresh
- tmux integration for `--monitor` flag
- `cub monitor` command to attach to running session
- Show: task, iteration, budget, recent events

**Exit criteria:**
- `cub run --monitor` launches with live dashboard
- `cub monitor` can attach to existing run

### Phase 4: Worktrees (0.24)

**Goal:** Parallel development

- WorktreeManager class wrapping git worktree
- `--worktree` flag for isolated execution
- `--parallel N` for concurrent independent tasks
- `cub worktree list/clean` commands
- Integration with branch-epic bindings

**Exit criteria:**
- Can run multiple cub instances on same repo
- `--parallel 3` processes 3 independent tasks concurrently

### Phase 5: Sandbox Mode (0.25)

**Goal:** Safe autonomous execution

- SandboxProvider protocol with capabilities
- DockerProvider implementation
- `--sandbox` flag for `cub run`
- `cub sandbox logs/diff/apply/clean` commands
- Network isolation, resource limits

**Exit criteria:**
- `cub run --sandbox` executes in Docker isolation
- Changes can be reviewed and applied or discarded

---

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Python startup latency | M | L | Lazy imports, measure early, optimize imports |
| Subprocess streaming complexity | M | M | Use line-buffered PIPE, test thoroughly |
| beads CLI subprocess overhead | L | M | Consider direct JSONL parsing as optimization |
| Typer learning curve | L | L | Good documentation, familiar click-like API |
| Test migration effort | M | M | Port incrementally, keep reference to BATS |
| uv adoption | L | L | Fallback to pip if issues |
| Docker availability | M | M | Clear error messaging, sandbox is opt-in |

---

## Dependencies

### External

| Dependency | Purpose | Required |
|------------|---------|----------|
| beads (bd) | Task management backend | No (fallback to JSON) |
| claude | AI harness | At least one harness |
| codex | AI harness | At least one harness |
| gemini | AI harness | At least one harness |
| opencode | AI harness | At least one harness |
| git | Version control | Yes |
| gh | GitHub CLI for PRs | No |
| docker | Sandbox provider | No (for sandbox feature) |
| tmux | Dashboard integration | No (for monitor feature) |
| shellcheck | Bash audit | No (for audit feature) |

### Python Packages

| Package | Purpose | Version |
|---------|---------|---------|
| typer | CLI framework | ^0.9.0 |
| pydantic | Data models | ^2.0 |
| rich | Terminal UI | ^13.0 |
| GitPython | Git operations | ^3.1 |
| pytest | Testing | ^8.0 |

---

## Security Considerations

- **Sandbox isolation:** Docker provider enforces resource limits and optional network isolation
- **Secret redaction:** Existing secret pattern matching preserved in logging
- **Hook execution:** Hooks run as user, not elevated
- **No credential storage:** Harness auth handled by underlying CLI tools
- **Subprocess sanitization:** All subprocess calls use list form (no shell=True)

---

## Future Considerations

### Deferred to post-0.25

- **Go components:** Reserved for cases where Python proves insufficient
- **Sprites.dev provider:** Interface designed, implementation deferred
- **Web dashboard:** tmux-based for now, web UI future enhancement
- **Additional harnesses:** Protocol supports, implementations as needed
- **Async execution:** Consider asyncio for parallel operations in future

### Migration path

- Bash code preserved in `legacy/` for reference
- BATS tests kept during transition, replaced incrementally
- Existing workflows (hooks) continue working
- Configuration format unchanged

---

**Next Step:** Run `cub plan` to generate implementation tasks for this architecture.
