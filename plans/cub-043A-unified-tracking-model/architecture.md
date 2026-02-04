# Architecture Design: Unified Tracking Model

**Date:** 2026-01-24
**Mindset:** Production
**Scale:** Personal
**Status:** Approved

---

## Technical Summary

The Unified Tracking Model extends cub's existing ledger infrastructure with three new capabilities:

1. **Run Session Manager** - New component tracking active `cub run` executions
2. **Ledger Integration Layer** - Hooks into the run loop to write entries at task start, each attempt, and task close
3. **Dashboard LedgerParser** - Syncs ledger files to dashboard DB following the existing parser pattern

The design leverages existing patterns: Protocol-based backends, Pydantic v2 models, and the Parser → Orchestrator → Writer sync architecture. Most work is wiring existing components together rather than new abstractions.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing codebase requirement |
| Models | Pydantic v2 | Existing pattern, type-safe serialization |
| CLI | Typer | Existing framework |
| Storage | JSON files + JSONL index | Simple, git-friendly, rebuildable |
| Dashboard DB | SQLite | Existing dashboard infrastructure |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           cub run loop                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ Task Backend │───▶│ Run Session  │───▶│ Ledger Integration   │  │
│  │   (beads)    │    │   Manager    │    │       Layer          │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│                             │                       │               │
│                             ▼                       ▼               │
│                    .cub/run-sessions/      .cub/ledger/            │
│                    ├── active-run.json     ├── index.jsonl         │
│                    └── {run-id}.json       ├── by-task/{id}/       │
│                                            │   ├── entry.json      │
│                                            │   └── attempts/       │
│                                            └── by-epic/{id}/       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Dashboard Sync                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │LedgerParser  │───▶│    Sync      │───▶│   Entity Writer      │  │
│  │  (new)       │    │ Orchestrator │    │   (existing)         │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│         ▲                                           │               │
│         │                                           ▼               │
│  .cub/ledger/                              dashboard.db             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          CLI Commands                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ ledger show  │    │ ledger stats │    │ ledger update/export │  │
│  │  (existing)  │    │  (existing)  │    │      (new)           │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Run Session Manager (New)

**Location:** `src/cub/core/session/manager.py`

- **Purpose:** Track active `cub run` executions with symlink-based detection
- **Responsibilities:**
  - Create run session file on `cub run` start
  - Manage `active-run.json` symlink
  - Detect and mark orphaned runs
  - Update run progress (tasks completed, budget used)
- **Dependencies:** None (standalone component)
- **Interface:**
  ```python
  class RunSessionManager:
      def start_session(harness: str, budget: Budget) -> RunSession
      def get_active_session() -> RunSession | None
      def update_session(tasks_completed: int, budget: Budget) -> None
      def end_session(status: SessionStatus) -> None
      def detect_orphans() -> list[RunSession]
  ```

### 2. Run Session Models (New)

**Location:** `src/cub/core/session/models.py`

- **Purpose:** Pydantic models for run session tracking
- **Key Models:**
  - `RunSession` - Full session state
  - `SessionStatus` - Enum (running, completed, orphaned)
  - `SessionBudget` - Token/cost tracking subset

### 3. Ledger Integration Layer (New)

**Location:** `src/cub/core/ledger/integration.py`

- **Purpose:** Coordinate ledger writes during task execution
- **Responsibilities:**
  - Create ledger entry when task starts (capture task state)
  - Write prompt files with frontmatter before each attempt
  - Capture harness output to log files
  - Append attempt results after each execution
  - Finalize entry on task close (outcome, task_changed, insights)
  - Update epic aggregates
- **Dependencies:** LedgerWriter, LedgerEntry models
- **Interface:**
  ```python
  class LedgerIntegration:
      def on_task_start(task: Task, run_id: str, lineage: Lineage) -> None
      def on_attempt_start(task_id: str, attempt: int, prompt: str, model: str) -> Path
      def on_attempt_end(task_id: str, attempt: int, result: HarnessResult) -> None
      def on_task_close(task_id: str, task: Task, commits: list[CommitRef]) -> None
  ```

### 4. Ledger Models (Extend Existing)

**Location:** `src/cub/core/ledger/models.py`

- **Purpose:** Extended Pydantic models per spec
- **New/Extended Models:**
  - `Lineage` - Spec/plan/epic references
  - `TaskSnapshot` - Task state at capture time
  - `TaskChanged` - Drift detection record
  - `Attempt` - Individual attempt record (extended)
  - `Outcome` - Final task completion record
  - `DriftRecord` - Additions/omissions tracking
  - `Verification` - Quality gate status
  - `WorkflowState` - Stage and timestamp
  - `StateTransition` - History entry
  - `EpicEntry` - Epic-level aggregation

### 5. Ledger Writer (Extend Existing)

**Location:** `src/cub/core/ledger/writer.py`

- **Purpose:** Extended write operations
- **New Methods:**
  - `create_task_entry()` - Initialize entry with lineage
  - `append_attempt()` - Add attempt to existing entry
  - `finalize_task_entry()` - Complete with outcome
  - `create_epic_entry()` - Initialize epic
  - `update_epic_aggregates()` - Recompute from tasks
  - `write_prompt_file()` - Write NNN-prompt.md
  - `write_harness_log()` - Write NNN-harness.log

### 6. Dashboard LedgerParser (New)

**Location:** `src/cub/core/dashboard/sync/parsers/ledger.py`

- **Purpose:** Parse ledger files for dashboard sync
- **Responsibilities:**
  - Read `index.jsonl` for fast enumeration
  - Parse individual task entries for full data
  - Compute dashboard Stage from workflow_stage
  - Generate checksum for incremental sync
- **Dependencies:** Follows existing parser pattern
- **Interface:**
  ```python
  class LedgerParser:
      def __init__(self, ledger_path: Path)
      def parse(self) -> list[DashboardEntity]
      def _compute_stage(entry: LedgerEntry) -> Stage
      def _to_dashboard_entity(entry: LedgerEntry) -> DashboardEntity
  ```

### 7. CLI Ledger Commands (Extend Existing)

**Location:** `src/cub/cli/ledger.py`

- **Purpose:** User-facing ledger operations
- **New Commands:**
  - `ledger update <id> --stage <stage> [--reason]` - Manual stage transitions
  - `ledger export [--format csv|json] [--epic]` - Data export
  - `ledger gc [--dry-run] [--keep-latest N]` - Garbage collection stub
- **Extended Commands:**
  - `ledger show` - Display new fields (attempts, outcome, lineage)

## Data Model

### RunSession

```
run_id: str              # cub-YYYYMMDD-HHMMSS format
started_at: datetime     # ISO 8601
project_dir: Path        # Absolute path
harness: str             # claude, codex, etc.
budget:
  tokens_used: int
  tokens_limit: int
  cost_usd: float
  cost_limit: float
tasks_completed: int
tasks_failed: int
current_task: str | None
status: str              # running | completed | orphaned
orphaned_at: datetime | None
orphaned_reason: str | None
```

### LedgerEntry (Extended)

```
id: str                  # Task ID
version: int = 1         # Schema version

lineage:
  spec_file: str | None  # Path to spec markdown
  plan_file: str | None  # Path to plan.jsonl
  epic_id: str | None    # Parent epic ID

task:                    # Snapshot at capture time
  title: str
  description: str
  type: str
  priority: int
  labels: list[str]
  created_at: datetime
  captured_at: datetime

task_changed:            # Drift detection (null if unchanged)
  detected_at: datetime
  fields_changed: list[str]
  original_description: str
  final_description: str
  notes: str | None

attempts: list[Attempt]  # All execution attempts

outcome:                 # Final completion (null if incomplete)
  success: bool
  partial: bool
  completed_at: datetime
  total_cost_usd: float
  total_attempts: int
  total_duration_seconds: int
  final_model: str
  escalated: bool
  escalation_path: list[str]
  files_changed: list[str]
  commits: list[CommitRef]
  approach: str | None
  decisions: list[str]
  lessons_learned: list[str]

drift:                   # Spec vs implementation
  additions: list[str]
  omissions: list[str]
  severity: str          # none | minor | significant

verification:
  status: str            # pending | pass | fail
  checked_at: datetime | None
  tests_passed: bool | None
  typecheck_passed: bool | None
  lint_passed: bool | None
  notes: list[str]

workflow:
  stage: str             # dev_complete | needs_review | validated | released
  stage_updated_at: datetime

state_history: list[StateTransition]
```

### Attempt

```
attempt_number: int
run_id: str
started_at: datetime
completed_at: datetime
harness: str
model: str
success: bool
error_category: str | None
error_summary: str | None
tokens:
  input: int
  output: int
  cache_read: int
  cache_write: int
cost_usd: float
duration_seconds: int
```

### EpicEntry

```
id: str                  # Epic ID
version: int = 1

lineage:
  spec_file: str | None
  plan_file: str | None

epic:
  title: str
  description: str
  created_at: datetime
  captured_at: datetime

tasks: list[str]         # Task IDs in this epic

aggregates:
  total_tasks: int
  tasks_completed: int
  tasks_in_progress: int
  total_cost_usd: float
  total_tokens:
    input: int
    output: int
    cache_read: int
    cache_write: int
  total_attempts: int
  escalation_rate: float
  avg_cost_per_task: float

workflow:
  stage: str
  stage_updated_at: datetime

state_history: list[StateTransition]
```

### StateTransition

```
stage: str
at: datetime
by: str                  # cub-run | dashboard:{user} | cli
reason: str | None
```

### Relationships

- `Task` → `LedgerEntry`: 1:1 (entry.id = task.id)
- `Epic` → `EpicEntry`: 1:1 (entry.id = epic.id)
- `LedgerEntry` → `EpicEntry`: N:1 via lineage.epic_id
- `LedgerEntry` → `Spec`: N:1 via lineage.spec_file
- `LedgerEntry` → `Plan`: N:1 via lineage.plan_file

## File Structure

```
.cub/
├── active-run.json              # Symlink → run-sessions/{current}
├── run-sessions/
│   ├── cub-20260124-123456.json # Completed run
│   ├── cub-20260124-140000.json # Current run (symlink target)
│   └── cub-20260123-090000.json # Orphaned run
└── ledger/
    ├── index.jsonl              # One JSON per line, quick lookups
    ├── by-task/
    │   └── {task-id}/
    │       ├── entry.json       # Full ledger entry
    │       └── attempts/
    │           ├── 001-prompt.md    # Prompt with frontmatter
    │           ├── 001-harness.log  # Raw harness output
    │           ├── 002-prompt.md
    │           └── 002-harness.log
    └── by-epic/
        └── {epic-id}/
            └── entry.json       # Epic aggregation
```

## APIs / Interfaces

### Run Session Manager (Internal)

- **Type:** Internal Python API
- **Purpose:** Manage run session lifecycle
- **Key Methods:**
  - `start_session(harness, budget) -> RunSession`
  - `get_active_session() -> RunSession | None`
  - `update_session(tasks_completed, budget) -> None`
  - `end_session(status) -> None`
  - `detect_orphans() -> list[RunSession]`

### Ledger Integration (Internal)

- **Type:** Internal Python API
- **Purpose:** Coordinate ledger writes during execution
- **Key Methods:**
  - `on_task_start(task, run_id, lineage) -> None`
  - `on_attempt_start(task_id, attempt, prompt, model) -> Path`
  - `on_attempt_end(task_id, attempt, result) -> None`
  - `on_task_close(task_id, task, commits) -> None`

### CLI Commands (User-facing)

- **Type:** Typer CLI
- **Purpose:** User interaction with ledger
- **Commands:**
  - `cub ledger show <id> [--attempt N] [--changes] [--history]`
  - `cub ledger stats [--epic ID] [--since DATE] [--model-analysis]`
  - `cub ledger search [--stage] [--escalated] [--drift] [--cost-above]`
  - `cub ledger update <id> --stage <stage> [--reason]`
  - `cub ledger export [--format csv|json] [--epic ID]`
  - `cub ledger gc [--dry-run] [--keep-latest N]`

### Dashboard API (Extend Existing)

- **Type:** FastAPI REST
- **Purpose:** Dashboard data access
- **Key Endpoints:**
  - `GET /api/entity/{id}` - Returns ledger data if entity is task
  - `PATCH /api/entity/{id}` - Update workflow stage (writes to ledger)

## Implementation Phases

### Phase 1: Run Session Infrastructure
**Goal:** Track active runs with orphan detection

- Create `src/cub/core/session/` module
- Add `RunSession`, `SessionStatus`, `SessionBudget` models
- Implement `RunSessionManager` class
- Wire into `cli/run.py` start/end lifecycle
- Update `cub monitor` to read active session via symlink
- Add tests for session lifecycle and orphan detection

### Phase 2: Ledger Entry Lifecycle
**Goal:** Create and finalize ledger entries during task execution

- Extend `LedgerEntry` model with lineage, attempts, outcome fields
- Add `Attempt`, `Outcome`, `TaskChanged`, `Lineage` models
- Implement `LedgerIntegration` layer
- Add `write_prompt_file()` and `write_harness_log()` to writer
- Wire into run loop: on_task_start, on_attempt_start/end, on_task_close
- Add tests for full task lifecycle

### Phase 3: Epic Aggregation
**Goal:** Track epic-level progress and costs

- Add `EpicEntry`, `EpicAggregates` models
- Implement epic CRUD in `LedgerWriter`
- Add `update_epic_aggregates()` method
- Wire epic updates into `LedgerIntegration.on_task_close`
- Auto-create epic entry when first task references it
- Add tests for epic aggregation

### Phase 4: CLI Commands
**Goal:** Complete ledger CLI interface

- Extend `ledger show` for new fields (Rich formatting for attempts, outcome)
- Add `ledger update` command with stage validation
- Add `ledger export` command (CSV via csv module, JSON via json.dumps)
- Add `ledger gc` stub (--dry-run shows what would be deleted)
- Add tests for new CLI commands

### Phase 5: Dashboard Integration
**Goal:** Sync ledger data to dashboard

- Create `LedgerParser` in `sync/parsers/ledger.py`
- Implement `parse()` method following existing pattern
- Map workflow_stage → dashboard Stage enum
- Register parser in `SyncOrchestrator`
- Add TASK_TO_LEDGER relationship type to models
- Update `RelationshipResolver` for ledger enrichment
- Add tests for parser and sync

### Phase 6: Index & Bidirectional Sync
**Goal:** Fast queries and dashboard writeback

- Implement index maintenance in `LedgerWriter` (update on every write)
- Add `rebuild_index()` method for recovery
- Enhance `ledger search` with index-based queries
- Implement `PATCH /api/entity/{id}` for stage updates
- Wire API to `LedgerWriter.update_workflow_stage()`
- Add tests for index operations and API writeback

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Schema changes break existing data | Medium | Low | Version field in schema; clean break already decided |
| Large harness logs fill disk | Medium | Medium | Defer retention; `gc` stub for future implementation |
| Orphan detection false positives | Low | Medium | Conservative detection (check PID, age); manual cleanup option |
| File locking race conditions | Low | Low | Single-writer assumption; standard fcntl locking if needed |
| Index corruption | Low | Low | Rebuild from source files; index is derived data |

## Dependencies

### External
- None (all internal to cub)

### Internal
- `cub.core.ledger.writer` - Existing ledger write operations
- `cub.core.ledger.reader` - Existing ledger read operations
- `cub.core.ledger.models` - Existing Pydantic models (to extend)
- `cub.core.tasks.backend` - Task state queries
- `cub.core.harness` - Execution results
- `cub.core.dashboard.sync` - Parser pattern to follow
- `cub.core.dashboard.db` - Entity models and writer

## Security Considerations

- **Sensitive data in logs:** Harness logs may contain API keys or secrets. Rely on existing guardrails secret redaction. Consider adding redaction to log capture if needed.
- **Local only:** Dashboard runs locally, no authentication required.
- **File permissions:** Ledger files inherit directory permissions; no special handling needed for personal use.

## Future Considerations

- **Multi-agent support:** Parallel `cub run` would require distributed locking (e.g., file locks with timeout, or move to SQLite for writes)
- **External sync:** GitHub Issues, Linear, Jira adapters would read ledger and sync externally
- **Automated verification:** CI hooks could call `cub ledger update` to set verification status
- **Retention policy:** Release process could archive/compress pre-release logs
- **Compression:** gzip old harness logs in place (change `.log` → `.log.gz`)

---

**Next Step:** Run `cub itemize` to break this into executable tasks.
