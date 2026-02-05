# Architecture Design: Ledger Consolidation & Unified ID System

**Date:** 2026-02-04
**Mindset:** Production
**Scale:** Personal
**Status:** Approved
**Spec:** specs/planned/cub-048-ledger-consolidation-and-id-system.md

---

## Technical Summary

This architecture extends cub's existing layered service architecture with three major changes: a unified hierarchical ID system, consolidated ledger storage, and extended lifecycle hooks.

The **ID system** replaces random 3-character suffixes with deterministic, counter-based hierarchical IDs (spec → plan → epic → task) tracked on the sync branch. This enables full traceability from any task back to its originating spec while preventing collisions across parallel worktrees via a pre-push git hook.

The **ledger consolidation** absorbs functionality from `runs/`, `run-sessions/`, and `logs/` directories into a single `.cub/ledger/` structure with `by-task/`, `by-epic/`, `by-plan/`, and `by-run/` subdirectories. Harness logs convert to JSONL format, and the `attempts/` subdirectory flattens to task-level artifact numbering.

The **lifecycle hooks** extend the existing hooks infrastructure with four new hook points (pre-session, end-of-task, end-of-epic, end-of-plan) that provide rich context for user-defined scripts. Five new commands (`release`, `retro`, `learn extract`, `verify`, `sync agent`) round out the feature set.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Established; match statements, type unions |
| CLI Framework | Typer | Established; type-safe subcommands |
| Data Models | Pydantic v2 | Established; validation, serialization |
| Storage | JSONL + JSON files | Established; no external dependencies |
| Testing | pytest | Established; good coverage tooling |
| Git Integration | Git plumbing commands | Established; sync branch pattern |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI LAYER                               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │  run    │ │ release │ │  retro  │ │ verify  │ │  learn  │  │
│  │ --plan  │ │         │ │         │ │         │ │ extract │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘  │
└───────┼──────────┼──────────┼──────────┼──────────┼───────────┘
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  RunService  │  │ReleaseService│  │ RetroService │         │
│  │  (extended)  │  │    (new)     │  │    (new)     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │VerifyService │  │ LearnService │  │ SyncService  │         │
│  │    (new)     │  │    (new)     │  │  (extended)  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└───────┬─────────────────────────────────────────────┬───────────┘
        │                                             │
        ▼                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       CORE DOMAIN                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   core/ids/  │  │ core/ledger/ │  │  core/sync/  │         │
│  │    (new)     │  │  (extended)  │  │  (extended)  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ core/hooks/  │  │  core/run/   │  │core/release/ │         │
│  │  (extended)  │  │  (extended)  │  │    (new)     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### ID System (`core/ids/`)

- **Purpose:** Generate and validate hierarchical IDs with counter-based allocation
- **Responsibilities:**
  - Generate spec, plan, epic, task, and standalone IDs
  - Parse and validate ID strings
  - Allocate counters from sync branch
  - Detect collisions via pre-push hook
- **Dependencies:** `core/sync/` for counter storage
- **Interface:** `generate_spec_id()`, `generate_plan_id()`, `generate_epic_id()`, `generate_task_id()`, `parse_id()`, `validate_id()`

**Package Structure:**
```
core/ids/
├── __init__.py       # Public API exports
├── models.py         # ID type models (SpecId, PlanId, EpicId, TaskId)
├── generator.py      # ID generation with counter allocation
├── parser.py         # ID parsing and validation
├── counters.py       # Counter management (sync branch integration)
└── hooks.py          # Pre-push hook for collision detection
```

### Ledger System (`core/ledger/`)

- **Purpose:** Unified storage for all task, epic, plan, and run completion records
- **Responsibilities:**
  - Write/read task entries with artifacts
  - Aggregate epic and plan summaries
  - Track run session metadata
  - Write JSONL harness logs
  - Manage artifact numbering (flattened)
- **Dependencies:** Pydantic models, file I/O utilities
- **Interface:** `LedgerWriter`, `LedgerReader`, `HarnessLogWriter`

**Extended Structure:**
```
core/ledger/
├── models.py         # Extended with PlanEntry, RunEntry
├── writer.py         # Extended with by-plan, by-run writes
├── reader.py         # Extended with plan/run queries
├── harness_log.py    # NEW: JSONL harness log writer/reader
└── artifacts.py      # NEW: Artifact numbering (flatten attempts/)
```

### Sync System (`core/sync/`)

- **Purpose:** Persist state on git sync branch without affecting working tree
- **Responsibilities:**
  - Manage counter state on sync branch
  - Allocate counters with optimistic locking
  - Sync managed sections in agent.md
  - Provide pre-push hook verification
- **Dependencies:** Git plumbing commands
- **Interface:** `SyncService.allocate_counter()`, `SyncService.sync_agent_sections()`

**Extended Structure:**
```
core/sync/
├── service.py        # Extended with counter operations
├── models.py         # Extended with CounterState
├── counters.py       # NEW: Counter allocation protocol
└── git_hooks.py      # NEW: Pre-push hook implementation
```

### Hooks System (`core/hooks/`)

- **Purpose:** Execute user-defined scripts at lifecycle events
- **Responsibilities:**
  - Discover hook scripts in project and global directories
  - Execute hooks with rich context
  - Handle hook failures gracefully
  - Provide lifecycle hook points
- **Dependencies:** Subprocess execution, Pydantic models
- **Interface:** `HookExecutor.run()`, lifecycle context models

**New Package Structure:**
```
core/hooks/
├── __init__.py       # Public API
├── models.py         # Hook context models
├── executor.py       # Hook execution engine
├── lifecycle.py      # Lifecycle hook definitions
└── discovery.py      # Hook script discovery
```

### Run System (`core/run/`)

- **Purpose:** Orchestrate autonomous task execution loop
- **Responsibilities:**
  - Execute single tasks or full plans
  - Coordinate task selection, harness invocation, ledger recording
  - Invoke lifecycle hooks at appropriate points
  - Commit ledger artifacts with code changes
- **Dependencies:** `core/ids/`, `core/ledger/`, `core/hooks/`, `core/harness/`
- **Interface:** `RunService.execute_once()`, `RunService.execute_plan()`

### New Command Services

| Service | Purpose | Core Package |
|---------|---------|--------------|
| `ReleaseService` | Mark work as released, update CHANGELOG, git tag | `core/release/` |
| `RetroService` | Generate retrospective reports, extract lessons | `core/retro/` |
| `LearnService` | Extract knowledge from ledger into guardrails/CLAUDE.md | `core/learn/` |
| `VerifyService` | Verify task completion, ledger consistency, ID integrity | `core/verify/` |

## Data Model

### ID Models

```python
class SpecId(BaseModel):
    """Spec ID: {project}-{number:03d} → cub-054"""
    project: str
    number: int

    def __str__(self) -> str:
        return f"{self.project}-{self.number:03d}"

class PlanId(BaseModel):
    """Plan ID: {spec_id}{letter} → cub-054A"""
    spec: SpecId
    letter: str  # A-Z, a-z, 0-9

    def __str__(self) -> str:
        return f"{self.spec}{self.letter}"

class EpicId(BaseModel):
    """Epic ID: {plan_id}-{char} → cub-054A-0"""
    plan: PlanId
    char: str  # 0-9, a-z, A-Z

    def __str__(self) -> str:
        return f"{self.plan}-{self.char}"

class TaskId(BaseModel):
    """Task ID: {epic_id}.{number} → cub-054A-0.1"""
    epic: EpicId
    number: int

    def __str__(self) -> str:
        return f"{self.epic}.{self.number}"

class StandaloneTaskId(BaseModel):
    """Standalone task: {project}-s{number:03d} → cub-s017"""
    project: str
    number: int

    def __str__(self) -> str:
        return f"{self.project}-s{self.number:03d}"
```

### Counter State

```python
class CounterState(BaseModel):
    """Counter state stored on sync branch in .cub/counters.json"""
    version: int = 1
    updated_at: datetime
    spec_number: int = 0
    standalone_task_number: int = 0
```

### Ledger Extensions

```python
class PlanEntry(BaseModel):
    """Plan-level aggregation stored in by-plan/{plan_id}/entry.json"""
    plan_id: str
    spec_id: str
    title: str
    epics: list[str]  # Epic IDs
    status: Literal["in_progress", "completed", "released"]
    started_at: datetime
    completed_at: datetime | None
    total_cost: float
    total_tokens: int
    total_tasks: int
    completed_tasks: int

class RunEntry(BaseModel):
    """Run session record stored in by-run/{run_id}.json"""
    run_id: str
    started_at: datetime
    completed_at: datetime | None
    status: Literal["running", "completed", "failed", "interrupted"]
    config: dict  # Serialized RunConfig
    tasks_attempted: list[str]
    tasks_completed: list[str]
    total_cost: float
    total_tokens: int
    iterations: int
```

### Hook Context Models

```python
class PreSessionContext(BaseModel):
    """Context for pre-session hook"""
    task_id: str
    task_title: str
    epic_id: str | None
    epic_title: str | None
    plan_id: str | None
    run_config: dict

class EndOfTaskContext(BaseModel):
    """Context for end-of-task hook"""
    task_id: str
    task_title: str
    status: Literal["completed", "failed"]
    files_changed: list[str]
    tokens_used: int
    cost_usd: float
    commit_hash: str | None
    duration_seconds: int

class EndOfEpicContext(BaseModel):
    """Context for end-of-epic hook"""
    epic_id: str
    epic_title: str
    tasks_completed: list[str]
    tasks_failed: list[str]
    total_cost: float
    total_tokens: int
    duration_seconds: int

class EndOfPlanContext(BaseModel):
    """Context for end-of-plan hook"""
    plan_id: str
    spec_id: str
    epics_completed: list[str]
    total_cost: float
    total_tokens: int
    duration_seconds: int
```

### Relationships

- `SpecId` → `PlanId`: One spec can have multiple plans (A, B, C...)
- `PlanId` → `EpicId`: One plan can have multiple epics (0, 1, 2...)
- `EpicId` → `TaskId`: One epic can have multiple tasks (.1, .2, .3...)
- `LedgerEntry` → `TaskId`: Each ledger entry references one task
- `EpicEntry` → `LedgerEntry[]`: Epic aggregates multiple task entries
- `PlanEntry` → `EpicEntry[]`: Plan aggregates multiple epic entries
- `RunEntry` → `TaskId[]`: Run session tracks attempted/completed tasks

## APIs / Interfaces

### ID Generation API

- **Type:** Internal Python API
- **Purpose:** Generate hierarchical IDs with counter allocation
- **Key Methods:**
  - `allocate_spec_id(project: str) -> SpecId`: Allocate next spec number
  - `generate_plan_id(spec: SpecId, letter: str) -> PlanId`: Create plan ID
  - `generate_epic_id(plan: PlanId, char: str) -> EpicId`: Create epic ID
  - `generate_task_id(epic: EpicId, number: int) -> TaskId`: Create task ID
  - `parse_id(id_str: str) -> SpecId | PlanId | EpicId | TaskId`: Parse any ID
  - `validate_id(id_str: str) -> bool`: Validate ID format

### Ledger API

- **Type:** Internal Python API
- **Purpose:** Read/write completion records
- **Key Methods:**
  - `LedgerWriter.create_task_entry(entry: LedgerEntry) -> None`
  - `LedgerWriter.create_epic_entry(entry: EpicEntry) -> None`
  - `LedgerWriter.create_plan_entry(entry: PlanEntry) -> None`
  - `LedgerWriter.create_run_entry(entry: RunEntry) -> None`
  - `LedgerReader.get_task(task_id: str) -> LedgerEntry | None`
  - `LedgerReader.list_tasks(filters: TaskFilters) -> list[LedgerEntry]`
  - `HarnessLogWriter.write(event: HarnessEvent) -> None`

### Hook Execution API

- **Type:** Internal Python API
- **Purpose:** Execute lifecycle hooks with context
- **Key Methods:**
  - `HookExecutor.run_pre_session(context: PreSessionContext) -> HookResult`
  - `HookExecutor.run_end_of_task(context: EndOfTaskContext) -> HookResult`
  - `HookExecutor.run_end_of_epic(context: EndOfEpicContext) -> HookResult`
  - `HookExecutor.run_end_of_plan(context: EndOfPlanContext) -> HookResult`

### CLI Commands

- **Type:** Typer CLI
- **Purpose:** User-facing commands
- **Key Commands:**
  - `cub run --plan <slug>`: Execute plan (replaces build-plan)
  - `cub release <plan-id>`: Mark plan as released
  - `cub retro <plan-id>`: Generate retrospective
  - `cub verify [--ledger] [--ids]`: Run consistency checks
  - `cub learn extract`: Extract knowledge from ledger
  - `cub sync agent`: Sync managed sections

## Implementation Phases

### Phase 1: ID System Foundation
**Goal:** Establish hierarchical ID generation with counter tracking

- Create `core/ids/` package structure
- Implement ID models (`SpecId`, `PlanId`, `EpicId`, `TaskId`, `StandaloneTaskId`)
- Implement ID parser with regex validation
- Implement ID generator with counter allocation
- Add `CounterState` model to `core/sync/models.py`
- Implement counter storage/retrieval on sync branch
- Create pre-push git hook script
- Update `cub init` to install pre-push hook
- Tests: ID generation, parsing, validation, counter allocation, collision detection

### Phase 2: Ledger Consolidation
**Goal:** Unify all storage into single ledger structure

- Add `PlanEntry` and `RunEntry` models to `core/ledger/models.py`
- Extend `LedgerWriter` with `create_plan_entry()` and `create_run_entry()`
- Create `HarnessLogWriter` for JSONL format in `core/ledger/harness_log.py`
- Create `ArtifactManager` for flattened numbering in `core/ledger/artifacts.py`
- Remove status writes to `.cub/runs/` directory
- Remove session writes to `.cub/run-sessions/` directory
- Update run loop to use new ledger locations
- Fix epic title capture (pass title not ID to `create_epic_entry`)
- Extend `LedgerReader` with `get_plan()`, `list_plans()`, `get_run()`, `list_runs()`
- Tests: Write/read all entry types, artifact numbering

### Phase 3: Run Loop Integration
**Goal:** Integrate ID system and consolidated ledger into run loop

- Add `--plan` flag to `RunConfig` model
- Add plan iteration logic to `RunLoop` (from build_plan.py)
- Update task selection to work with new hierarchical IDs
- Update ledger commit timing (commit ledger entry with code changes)
- Remove `cub build-plan` command from CLI
- Remove `cli/build_plan.py` module
- Update documentation references
- Tests: Run loop with `--plan` flag, single task, full plan execution

### Phase 4: Lifecycle Hooks
**Goal:** Extend hooks infrastructure with lifecycle events

- Create `core/hooks/` package structure
- Implement hook context models in `core/hooks/models.py`
- Implement `HookExecutor` in `core/hooks/executor.py`
- Implement hook discovery in `core/hooks/discovery.py`
- Define lifecycle hooks in `core/hooks/lifecycle.py`
- Integrate `pre-session` hook into run loop (before harness invocation)
- Integrate `end-of-task` hook into run loop (after task completion)
- Integrate `end-of-epic` hook into run loop (after epic completion)
- Integrate `end-of-plan` hook into run loop (after plan completion)
- Update `cub init` to create hook directories
- Tests: Hook discovery, execution, context passing, failure handling

### Phase 5: New Commands
**Goal:** Implement release, retro, verify, learn, sync agent commands

- **`cub release`:**
  - Create `core/release/` package with `ReleaseService`
  - Implement: update CHANGELOG, git tag, move specs to released/
  - Create `cli/release.py` with Typer command
  - Tests: Release workflow

- **`cub retro`:**
  - Create `core/retro/` package with `RetroService`
  - Implement: generate retrospective from ledger entries
  - Create `cli/retro.py` with Typer command
  - Tests: Retrospective generation

- **`cub verify`:**
  - Create `core/verify/` package with `VerifyService`
  - Implement: ledger consistency, ID integrity, counter sync checks
  - Create `cli/verify.py` with Typer command
  - Tests: Detection of various inconsistencies

- **`cub learn extract`:**
  - Create `core/learn/` package with `LearnService`
  - Implement: extract patterns from ledger, update guardrails/CLAUDE.md
  - Create `cli/learn.py` with Typer command
  - Tests: Knowledge extraction

- **`cub sync agent`:**
  - Extend `SyncService` with `sync_agent_sections()` method
  - Implement managed section injection logic
  - Add `sync agent` subcommand to existing `cli/sync.py`
  - Tests: Managed section sync

### Phase 6: Consistency Checks & Cleanup
**Goal:** Add integrity checks and remove deprecated code

- Add ledger consistency check to `cub doctor`
- Add ID integrity check to `cub doctor`
- Add counter sync check to `cub doctor`
- Add pre-run consistency check to `cub run` (fast, skippable)
- Remove deprecated `runs/` directory code paths
- Remove deprecated `run-sessions/` directory code paths
- Remove deprecated `logs/` directory code paths
- Update `.gitignore` template
- Final documentation pass
- Tests: Consistency check detection

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Pre-push hook bypass (user runs `git push --no-verify`) | ID collisions | Low | Document importance; collisions fixable manually at current scale |
| Complex migration of existing workflows | User confusion | Medium | Clear documentation; clean removal of build-plan |
| Hook context insufficient for user needs | User frustration | Low | Design rich context upfront; iterate based on feedback |
| Sync branch conflicts during counter allocation | Counter corruption | Low | Optimistic locking with clear error messages and retry |
| Large ledger files over time | Query performance | Low | Index-based queries; archive strategy deferred but designed-for |
| Backward compatibility with old random IDs | Mixed ID formats | Medium | Old IDs remain valid; parser handles both formats |

## Dependencies

### External
- **Git:** Plumbing commands for sync branch, pre-push hook
- **GitHub CLI (`gh`):** Release command for PR/tag creation (optional)

### Internal
- **`core/sync/`:** Counter storage on sync branch
- **`core/ledger/`:** Existing ledger infrastructure
- **`core/run/`:** Run loop for lifecycle hook integration
- **`core/harness/`:** Harness execution for log capture
- **`core/tasks/`:** Task backend for ID updates

## Security Considerations

For production mindset at personal scale:

- **File permissions:** Ledger files created with 0644 (user-writable, world-readable) - acceptable for personal use
- **No secrets in logs:** Harness log writer filters environment variables and API keys
- **Git hook security:** Pre-push hook runs locally only; no remote code execution
- **Counter integrity:** Optimistic locking prevents accidental overwrites; deliberate tampering not defended against

## Future Considerations

Explicitly deferred but designed-for:

- **Multi-project ID namespacing:** ID models support project prefix; counter storage could be extended
- **Knowledge graph (spec cub-033):** Ledger structure supports relationship queries
- **Log archival/compression:** JSONL format supports streaming; archive strategy can be added
- **Cross-worktree real-time sync:** Sync branch mechanism could support polling

---

**Next Step:** Run `/cub:itemize` to generate implementation tasks.
