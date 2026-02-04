# Architecture Design: 0.30 Foundation Phase

**Date:** 2026-01-26
**Mindset:** Production
**Scale:** Personal
**Status:** Approved

---

## Technical Summary

The 0.30 Foundation Phase consolidates cub's task management on a single JSONL format that's compatible with beads but self-contained. The architecture adds three new components: a `JsonlBackend` that implements the existing `TaskBackend` protocol, a `SyncService` that commits task state to a dedicated git branch using plumbing commands, and a `BothBackend` wrapper that validates the new backend against beads during transition.

The design prioritizes production quality (comprehensive testing, robust error handling) while keeping complexity appropriate for personal-scale usage. The JSONL format was chosen over SQLite for git-friendliness and debugging simplicity. All new code follows existing patterns: Pydantic models, Protocol-based interfaces, and the backend registry pattern.

The sync mechanism uses git plumbing (`write-tree`, `commit-tree`, `update-ref`) to commit to the `cub-sync` branch without checking it out, keeping the working tree clean. This is the same pattern beads uses, proven stable.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Existing codebase |
| Data Models | Pydantic v2 | Existing pattern, validation |
| Storage | JSONL file | Git-friendly, beads-compatible, easy debugging |
| Git Sync | Git plumbing commands | No checkout needed, proven in beads |
| CLI | Typer | Existing pattern |
| Testing | pytest | Existing pattern |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           cub CLI                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ cub run  │ │cub status│ │ cub sync │ │ cub init │ │cub doctor│  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
└───────┼────────────┼────────────┼────────────┼────────────┼────────┘
        │            │            │            │            │
        ▼            ▼            │            ▼            ▼
┌─────────────────────────────────┼───────────────────────────────────┐
│              Task Backend Layer │                                    │
│  ┌─────────────┐  ┌─────────────┼─┐  ┌─────────────┐                │
│  │ JsonlBackend│◄─┤ BothBackend │ ├─►│ BeadsBackend│                │
│  │ (new)       │  │ (new)       │ │  │ (existing)  │                │
│  └──────┬──────┘  └─────────────┼─┘  └──────┬──────┘                │
│         │                       │           │                        │
│         ▼                       │           ▼                        │
│  .cub/tasks.jsonl               │        bd CLI                      │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Sync Layer (new)                              │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      SyncService                                 ││
│  │  commit_tasks(message) ─► git plumbing to cub-sync branch       ││
│  │  pull_tasks() ─► fetch + merge from remote                      ││
│  │  push_tasks() ─► push cub-sync to remote                        ││
│  │  get_status() ─► compare local vs remote                        ││
│  │  detect_conflicts() ─► warn on divergent edits                  ││
│  └─────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                              ▼                                       │
│              .cub/.sync-state.json                                   │
│              cub-sync branch (local + remote)                        │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. JsonlBackend

**Purpose:** Native JSONL task storage using beads-compatible schema

**Responsibilities:**
- Read/write tasks from `.cub/tasks.jsonl`
- Implement full `TaskBackend` protocol (13 methods)
- Auto-migrate from old `prd.json` format on first access
- Atomic writes via temp file + rename (same pattern as existing `JsonBackend`)
- Generate task IDs using project prefix + incrementing number

**Dependencies:**
- `cub.core.tasks.models.Task` (existing Pydantic model)
- `cub.core.tasks.backend.TaskBackend` protocol

**Interface:**
```python
@register_backend("jsonl")
class JsonlBackend:
    def __init__(self, project_dir: Path | None = None) -> None: ...

    # TaskBackend protocol methods
    def list_tasks(self, status: TaskStatus | None = None, ...) -> list[Task]: ...
    def get_task(self, task_id: str) -> Task | None: ...
    def get_ready_tasks(self, parent: str | None = None, ...) -> list[Task]: ...
    def update_task(self, task_id: str, ...) -> Task: ...
    def close_task(self, task_id: str, reason: str | None = None) -> Task: ...
    def create_task(self, title: str, ...) -> Task: ...
    def get_task_counts(self) -> TaskCounts: ...
    def add_task_note(self, task_id: str, note: str) -> Task: ...
    def import_tasks(self, tasks: list[Task]) -> list[Task]: ...

    @property
    def backend_name(self) -> str: ...
    def get_agent_instructions(self, task_id: str) -> str: ...
    def bind_branch(self, epic_id: str, branch_name: str, ...) -> bool: ...
    def try_close_epic(self, epic_id: str) -> tuple[bool, str]: ...

    # Internal
    def _migrate_from_prd_json(self) -> None: ...
```

**File Location:** `src/cub/core/tasks/jsonl.py`

### 2. BothBackend

**Purpose:** Dual read/write wrapper for transition validation

**Responsibilities:**
- Wrap two backends (beads as primary, JSONL as secondary)
- Execute all reads against both backends
- Execute all writes to both backends
- Compare results and log divergence
- Return primary (beads) result to caller
- Enable confident cutover by validating JSONL matches beads

**Dependencies:**
- `JsonlBackend`
- `BeadsBackend`
- Both implement `TaskBackend` protocol

**Interface:**
```python
@register_backend("both")
class BothBackend:
    def __init__(
        self,
        primary: TaskBackend,
        secondary: TaskBackend,
        divergence_log: Path | None = None,
    ) -> None: ...

    # TaskBackend protocol methods (delegates to both)
    # ... all 13 methods ...

    # Comparison
    def compare_all_tasks(self) -> list[TaskDivergence]: ...
    def get_divergence_count(self) -> int: ...
```

**File Location:** `src/cub/core/tasks/both.py`

### 3. SyncService

**Purpose:** Git-based persistence of task state

**Responsibilities:**
- Commit `.cub/tasks.jsonl` to `cub-sync` branch using git plumbing
- Track sync state (last commit SHA, last sync time)
- Detect conflicts when pulling (warn but apply last-write-wins)
- Push/pull to remote when available
- Never require checkout of sync branch

**Dependencies:**
- Git CLI (via subprocess)
- `.cub/.sync-state.json` for state tracking

**Interface:**
```python
class SyncService:
    def __init__(
        self,
        project_dir: Path,
        branch_name: str = "cub-sync",
        tasks_file: str = ".cub/tasks.jsonl",
    ) -> None: ...

    def commit(self, message: str | None = None) -> str:
        """Commit current tasks.jsonl to sync branch. Returns commit SHA."""
        ...

    def pull(self) -> SyncResult:
        """Pull from remote, detect conflicts, apply last-write-wins."""
        ...

    def push(self) -> bool:
        """Push sync branch to remote. Returns True if successful."""
        ...

    def get_status(self) -> SyncStatus:
        """Get sync status (ahead/behind/diverged/up-to-date)."""
        ...

    def is_initialized(self) -> bool:
        """Check if sync branch exists."""
        ...

    def initialize(self) -> None:
        """Create sync branch if it doesn't exist."""
        ...
```

**File Location:** `src/cub/core/sync/service.py`

### 4. SyncHook Integration

**Purpose:** Auto-sync during `cub run`

**Responsibilities:**
- Hook into run loop after task mutations
- Call `SyncService.commit()` automatically
- Configurable (on by default during run)

**Dependencies:**
- `SyncService`
- Existing hook system

**File Location:** Integration in `src/cub/cli/run.py` or via existing hooks

### 5. Backend Detection Updates

**Purpose:** Update auto-detection to handle new backends

**Responsibilities:**
- Detect `.cub/tasks.jsonl` -> jsonl backend
- Detect `.beads/` + `.cub/tasks.jsonl` -> both backend (if mode=both in config)
- Maintain backwards compatibility with existing detection

**File Location:** Update `src/cub/core/tasks/backend.py`

## Data Model

### Task (JSONL Schema)

The JSONL file contains one JSON object per line, matching beads format:

```json
{
  "id": "cub-001",
  "title": "Task title",
  "description": "Full description with markdown",
  "status": "open|in_progress|closed",
  "priority": 0,
  "issue_type": "task|feature|bug|epic|gate",
  "labels": ["label1", "label2"],
  "assignee": "username or null",
  "parent": "epic-id or null",
  "dependencies": [
    {
      "issue_id": "cub-001",
      "depends_on_id": "cub-000",
      "type": "blocks|parent-child",
      "created_at": "2026-01-26T12:00:00Z"
    }
  ],
  "created_at": "2026-01-26T12:00:00Z",
  "updated_at": "2026-01-26T12:00:00Z",
  "closed_at": "2026-01-26T12:00:00Z or null",
  "close_reason": "string or null"
}
```

### Key Schema Differences from Current prd.json

| Field | prd.json | tasks.jsonl |
|-------|----------|-------------|
| File format | JSON object with `tasks` array | JSONL (one object per line) |
| Task type | `type` | `issue_type` |
| Dependencies | `dependsOn: ["id1", "id2"]` | `dependencies: [{issue_id, depends_on_id, type}]` |
| Close reason | Not present | `close_reason` field |
| ID generation | Requires `prefix` in file | Self-contained (stored in config) |

### SyncState

```json
{
  "last_commit_sha": "abc123...",
  "last_sync_time": "2026-01-26T12:00:00Z",
  "remote_tracking": true,
  "branch_name": "cub-sync"
}
```

### TaskDivergence (for Both mode)

```python
@dataclass
class TaskDivergence:
    task_id: str
    field: str
    primary_value: Any
    secondary_value: Any
    timestamp: datetime
```

## APIs / Interfaces

### Backend Protocol (Existing)

**Type:** Internal Python Protocol
**Purpose:** Pluggable task storage

The existing `TaskBackend` protocol defines 13 methods. Both `JsonlBackend` and `BothBackend` implement this protocol.

### CLI Commands

**`cub sync`** (New)
- `cub sync` - Commit local changes to sync branch and push if remote available
- `cub sync --pull` - Pull and merge remote changes
- `cub sync --status` - Show sync status without syncing
- `cub sync --init` - Initialize sync branch

**`cub init`** (Updated)
- Create `.cub/tasks.jsonl` instead of `prd.json` for new projects
- Initialize sync branch by default
- `--backend beads` flag for opt-in beads

**`cub doctor`** (Updated)
- Report backend type and sync status
- Check for divergence if both mode enabled

### Configuration

```toml
# .cub/config.toml (or .cub.json)
[task_backend]
mode = "both"  # "jsonl", "beads", or "both"

[sync]
enabled = true
branch = "cub-sync"
auto_sync = "run"  # "run", "always", or "never"
```

## Implementation Phases

### Phase 1: JSONL Backend Core
**Goal:** Working JsonlBackend that passes all TaskBackend protocol tests

1. Create `src/cub/core/tasks/jsonl.py` with `JsonlBackend` class
2. Implement core CRUD methods (list, get, create, update, close)
3. Implement dependency-aware methods (get_ready_tasks)
4. Implement utility methods (get_task_counts, add_task_note, import_tasks)
5. Implement agent instructions and branch binding stubs
6. Add migration logic from prd.json
7. Write comprehensive unit tests (target: 80%+ coverage)
8. Register backend in registry

### Phase 2: Both Mode
**Goal:** Dual-backend wrapper for validation

1. Create `src/cub/core/tasks/both.py` with `BothBackend` class
2. Implement delegation logic for all TaskBackend methods
3. Implement comparison logic for task equality
4. Implement divergence logging
5. Add comparison script `./scripts/compare-backends.py`
6. Update backend detection for both mode
7. Write tests for divergence detection

### Phase 3: Sync Branch
**Goal:** Git-based task persistence

1. Create `src/cub/core/sync/` module
2. Implement `SyncService` with git plumbing operations
3. Implement `commit()` - write-tree, commit-tree, update-ref
4. Implement `pull()` with conflict detection
5. Implement `push()` to remote
6. Implement `get_status()` for ahead/behind detection
7. Create `cub sync` CLI command
8. Write integration tests (require git repo fixture)

### Phase 4: Run Loop Integration
**Goal:** Auto-sync during cub run

1. Add sync hook after task mutations in run loop
2. Add configuration for auto-sync behavior
3. Test sync during multi-task run
4. Document behavior in README

### Phase 5: Documentation Audit
**Goal:** README matches reality, Quick Start works

1. Run `cub --help` and compare against README
2. Remove deprecated command references
3. Walk through Quick Start end-to-end
4. Add alpha disclaimer banner
5. Add security warning section
6. Mark experimental features
7. Update CONTRIBUTING.md

### Phase 6: CLI Polish
**Goal:** Consistent, helpful CLI

1. Audit all command help text
2. Add actionable error messages
3. Standardize exit codes
4. Implement `cub docs` command
5. Add alpha classifier to pyproject.toml
6. Test error scenarios

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Git plumbing corrupts sync branch | High | Low | Never force operations, backup state, comprehensive tests |
| JSONL parsing edge cases (unicode, large descriptions) | Medium | Low | Use json module's encoding, add size limits if needed |
| Migration from prd.json loses data | High | Low | Backup before migrate, both mode validates |
| Both mode divergence masks real bugs | Medium | Medium | Log all divergence with full context, alerting in doctor |
| Sync conflicts cause data loss | High | Low | Detect and warn, never delete without backup |
| Performance with many tasks (>1000) | Low | Low | JSONL is O(n) read but sufficient for personal scale |

## Dependencies

### External
- **Git CLI**: Required for sync operations. Must be version 2.x+.
- **Python 3.10+**: Required for type unions and match statements.

### Internal
- **cub.core.tasks.backend**: Existing protocol and registry
- **cub.core.tasks.models**: Existing Task Pydantic model
- **cub.core.config**: Existing configuration loading

## Security Considerations

- **File Permissions**: Task files created with 600, directories with 700 (match existing artifacts pattern)
- **Sync Branch**: No secrets should be in task data; if they are, they'd be committed to git
- **Migration Backup**: Original prd.json preserved as .bak, not deleted

## Future Considerations

Explicitly deferred to post-0.30:

- **Multi-repo sync**: Beads supports hydrating from multiple repos
- **Daemon mode**: Background process for faster operations
- **Worktree isolation**: Full worktree support for parallel work
- **Conflict resolution UI**: Interactive merge for task conflicts
- **Auto-pull**: Automatically pull remote changes (manual for alpha)
- **SQLite caching**: Index JSONL for faster queries at scale

---

**Next Step:** Run `cub itemize` to generate implementation tasks.
