# Itemized Plan: 0.30 Foundation Phase

> Source: [0.30-foundation-phase.md](../../specs/researching/0.30-foundation-phase.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-26

## Context Summary

Cub needs a simpler, self-contained task backend for its 0.30 public alpha. The current dual-backend situation (beads vs JSON) confuses users and creates maintenance burden. This foundation phase adopts beads' JSONL schema as cub's native format, adds Python-native git sync, and polishes docs/CLI for alpha quality.

**Mindset:** Production | **Scale:** Personal

---

## Epic: cub-j1a - 0.30-foundation #1: JSONL Backend Core

Priority: 0
Labels: phase-1, critical-path, model:sonnet

Implement the core JSONL backend that stores tasks in `.cub/tasks.jsonl` using beads-compatible schema. This is the foundation all other work builds on. The backend must implement the full `TaskBackend` protocol (13 methods) and include migration from the old `prd.json` format.

### Task: cub-j1a.1 - Create JsonlBackend class with file I/O

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, setup

**Context**: The JSONL backend needs a class structure that follows existing patterns (like `JsonBackend`) but reads/writes JSONL format. This task creates the scaffolding and file I/O methods.

**Implementation Steps**:
1. Create `src/cub/core/tasks/jsonl.py` with module docstring
2. Implement `JsonlBackend` class with `__init__(project_dir: Path | None = None)`
3. Add private methods: `_load_tasks() -> list[dict]`, `_save_tasks(tasks: list[dict])`
4. Implement atomic writes via temp file + rename (copy pattern from `json.py`)
5. Add caching with mtime check (copy pattern from `json.py`)
6. Handle file creation if `.cub/tasks.jsonl` doesn't exist
7. Add `@register_backend("jsonl")` decorator

**Acceptance Criteria**:
- [ ] `JsonlBackend` class exists and can be instantiated
- [ ] `_load_tasks()` reads JSONL file (one JSON object per line)
- [ ] `_save_tasks()` writes JSONL atomically
- [ ] Caching works (second read doesn't re-parse if file unchanged)
- [ ] Empty file returns empty list, not error

**Files**: `src/cub/core/tasks/jsonl.py`

---

### Task: cub-j1a.2 - Implement core CRUD methods

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, logic
Blocks: cub-j1a.3, cub-j1a.4

**Context**: The CRUD methods (`list_tasks`, `get_task`, `create_task`, `update_task`, `close_task`) form the core of the backend. These must match the `TaskBackend` protocol signatures exactly.

**Implementation Steps**:
1. Implement `list_tasks(status, parent, label)` with filtering
2. Implement `get_task(task_id)` returning `Task | None`
3. Implement `create_task(title, description, task_type, priority, labels, depends_on, parent)` with ID generation
4. Implement `update_task(task_id, status, assignee, description, labels)`
5. Implement `close_task(task_id, reason)` setting `closed_at` and `close_reason`
6. Add `_generate_task_id()` helper using config prefix or default
7. Ensure all methods update `updated_at` timestamp

**Acceptance Criteria**:
- [ ] All 5 CRUD methods implemented with correct signatures
- [ ] Task IDs follow pattern `{prefix}-{number}` (e.g., `cub-001`)
- [ ] Filtering works for status, parent, and label
- [ ] Timestamps set correctly on create/update/close
- [ ] `close_reason` field populated when provided

**Files**: `src/cub/core/tasks/jsonl.py`

---

### Task: cub-j1a.3 - Implement dependency-aware and utility methods

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, logic

**Context**: The `get_ready_tasks` method is critical for `cub run` - it must correctly identify tasks with all dependencies satisfied. Other utility methods round out the protocol.

**Implementation Steps**:
1. Implement `get_ready_tasks(parent, label)` - open tasks with all deps closed
2. Parse `dependencies` array to build blocked-by relationships
3. Implement `get_task_counts()` returning `TaskCounts` model
4. Implement `add_task_note(task_id, note)` appending to notes field
5. Implement `import_tasks(tasks)` for bulk import with ID preservation
6. Sort ready tasks by priority (P0 first)

**Acceptance Criteria**:
- [ ] `get_ready_tasks` returns only tasks where all blockers are closed
- [ ] `get_ready_tasks` respects parent and label filters
- [ ] `get_task_counts` returns accurate counts
- [ ] `import_tasks` preserves explicit task IDs
- [ ] Tasks sorted by priority in `get_ready_tasks`

**Files**: `src/cub/core/tasks/jsonl.py`

---

### Task: cub-j1a.4 - Implement agent instructions and branch binding

Priority: 1
Labels: phase-1, model:haiku, complexity:low, logic

**Context**: The remaining protocol methods (`backend_name`, `get_agent_instructions`, `bind_branch`, `try_close_epic`) complete the interface. Some can be stubs initially.

**Implementation Steps**:
1. Implement `backend_name` property returning `"jsonl"`
2. Implement `get_agent_instructions(task_id)` with JSONL-specific instructions
3. Implement `bind_branch(epic_id, branch_name, base_branch)` storing in config or separate file
4. Implement `try_close_epic(epic_id)` checking all child tasks closed
5. Store branch bindings in `.cub/branches.yaml` (reuse existing `BranchStore` if compatible)

**Acceptance Criteria**:
- [ ] `backend_name` returns `"jsonl"`
- [ ] `get_agent_instructions` returns helpful string mentioning JSONL
- [ ] `bind_branch` creates branch binding (can share format with beads backend)
- [ ] `try_close_epic` returns `(True, message)` only when all child tasks closed

**Files**: `src/cub/core/tasks/jsonl.py`

---

### Task: cub-j1a.5 - Add migration from prd.json and write tests

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, test, checkpoint

**Context**: Existing users have `prd.json` files. The backend should auto-migrate on first access. Tests ensure the backend works correctly.

**Implementation Steps**:
1. Add `_migrate_from_prd_json()` method detecting old format
2. Convert JSON array format to JSONL (one task per line)
3. Map old field names: `type` -> `issue_type`, `dependsOn` -> `dependencies` array
4. Backup original as `prd.json.bak`
5. Call migration automatically in `_load_tasks()` if `.cub/tasks.jsonl` missing but `prd.json` exists
6. Write unit tests for all CRUD operations
7. Write test for migration path
8. Target 80%+ coverage

**Acceptance Criteria**:
- [ ] Migration runs automatically when `prd.json` exists and `tasks.jsonl` doesn't
- [ ] Original `prd.json` preserved as `prd.json.bak`
- [ ] Field names correctly mapped during migration
- [ ] Unit tests pass with 80%+ coverage
- [ ] Tests cover edge cases (empty file, unicode, large descriptions)

**Files**: `src/cub/core/tasks/jsonl.py`, `tests/test_jsonl_backend.py`

---

## Epic: cub-j1b - 0.30-foundation #2: Both Mode Validation

Priority: 0
Labels: phase-2, model:sonnet

Implement the `BothBackend` wrapper that delegates to both beads and JSONL backends, comparing results and logging divergence. This provides a safety net during transition.

### Task: cub-j1b.1 - Create BothBackend wrapper class

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, logic

**Context**: The `BothBackend` wraps two backends and delegates all operations to both. Beads is primary (its result is returned), JSONL is secondary (for validation).

**Implementation Steps**:
1. Create `src/cub/core/tasks/both.py` with module docstring
2. Implement `BothBackend` class taking `primary` and `secondary` backends
3. Add `divergence_log` path parameter (default `.cub/backend-divergence.log`)
4. Create `TaskDivergence` dataclass for recording differences
5. Implement delegation pattern: call both backends, compare, return primary result
6. Add `@register_backend("both")` decorator

**Acceptance Criteria**:
- [ ] `BothBackend` can wrap any two `TaskBackend` implementations
- [ ] Constructor accepts primary, secondary, and optional divergence_log
- [ ] Class registered as `"both"` backend

**Files**: `src/cub/core/tasks/both.py`

---

### Task: cub-j1b.2 - Implement delegation for all protocol methods

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, logic
Blocks: cub-j1b.3

**Context**: Every `TaskBackend` method must delegate to both backends. Write operations go to both; read operations query both and compare.

**Implementation Steps**:
1. Implement all 13 protocol methods with delegation
2. For write methods (create, update, close, add_note, import): execute on both
3. For read methods (list, get, get_ready, get_counts): query both and compare
4. Return primary backend's result in all cases
5. Catch exceptions from secondary (log but don't fail)
6. Handle case where secondary doesn't have a task that primary does

**Acceptance Criteria**:
- [ ] All 13 protocol methods implemented
- [ ] Write operations update both backends
- [ ] Read operations query both backends
- [ ] Secondary failures logged but don't crash
- [ ] Primary result always returned

**Files**: `src/cub/core/tasks/both.py`

---

### Task: cub-j1b.3 - Implement divergence detection and logging

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium, logic

**Context**: When backends return different results, we need to detect and log the divergence. This helps validate the JSONL backend matches beads behavior.

**Implementation Steps**:
1. Implement `_compare_tasks(primary_task, secondary_task) -> list[TaskDivergence]`
2. Compare all fields: id, title, status, priority, labels, dependencies, etc.
3. Implement `_log_divergence(divergences: list[TaskDivergence])`
4. Write to divergence log with timestamp and full context
5. Add `compare_all_tasks() -> list[TaskDivergence]` for full comparison
6. Add `get_divergence_count() -> int` for quick check

**Acceptance Criteria**:
- [ ] Field-by-field comparison detects all differences
- [ ] Divergence log includes timestamp, task ID, field, both values
- [ ] `compare_all_tasks()` returns comprehensive list
- [ ] `get_divergence_count()` returns accurate count
- [ ] Log file is append-only (doesn't lose history)

**Files**: `src/cub/core/tasks/both.py`

---

### Task: cub-j1b.4 - Update backend detection and add comparison script

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium, logic, checkpoint

**Context**: Backend auto-detection needs to recognize when to use `both` mode. A comparison script helps manual validation.

**Implementation Steps**:
1. Update `detect_backend()` in `backend.py` to check config for `mode = "both"`
2. If `.beads/` exists AND config says `both`, instantiate `BothBackend`
3. Create `scripts/compare-backends.py` standalone script
4. Script loads both backends and runs `compare_all_tasks()`
5. Pretty-print differences with color coding
6. Exit code 0 if identical, 1 if divergent
7. Write tests for both mode detection

**Acceptance Criteria**:
- [ ] `detect_backend()` returns `"both"` when configured
- [ ] `BothBackend` instantiated with beads as primary, JSONL as secondary
- [ ] `scripts/compare-backends.py` works standalone
- [ ] Script output is human-readable
- [ ] Tests verify detection logic

**Files**: `src/cub/core/tasks/backend.py`, `src/cub/core/tasks/both.py`, `scripts/compare-backends.py`, `tests/test_both_backend.py`

---

## Epic: cub-j1c - 0.30-foundation #3: Sync Branch

Priority: 1
Labels: phase-3, risk:high, model:opus

Implement git-based task persistence using the `cub-sync` branch. Uses git plumbing commands to commit without checkout.

### Task: cub-j1c.1 - Create SyncService with git plumbing foundation

Priority: 1
Labels: phase-3, model:opus, complexity:high, setup, risk:high

**Context**: The sync service uses git plumbing (`write-tree`, `commit-tree`, `update-ref`) to commit to a branch without checking it out. This is the highest-risk component.

**Implementation Steps**:
1. Create `src/cub/core/sync/` directory with `__init__.py`
2. Create `src/cub/core/sync/service.py` with `SyncService` class
3. Implement `__init__(project_dir, branch_name="cub-sync", tasks_file=".cub/tasks.jsonl")`
4. Add `_run_git(args) -> str` helper for subprocess calls
5. Implement `is_initialized() -> bool` checking if branch exists
6. Implement `initialize()` creating branch from empty tree or current HEAD
7. Create `SyncState` Pydantic model for `.cub/.sync-state.json`

**Acceptance Criteria**:
- [ ] `SyncService` can be instantiated
- [ ] `_run_git()` handles errors gracefully
- [ ] `is_initialized()` returns True if `cub-sync` branch exists
- [ ] `initialize()` creates branch without checkout
- [ ] Works in both new and existing repos

**Files**: `src/cub/core/sync/__init__.py`, `src/cub/core/sync/service.py`, `src/cub/core/sync/models.py`

---

### Task: cub-j1c.2 - Implement commit operation

Priority: 1
Labels: phase-3, model:opus, complexity:high, logic, risk:high
Blocks: cub-j1c.3, cub-j1c.4

**Context**: The `commit()` method uses git plumbing to add tasks.jsonl to the sync branch without affecting working tree.

**Implementation Steps**:
1. Implement `commit(message: str | None = None) -> str`
2. Use `git hash-object -w` to store tasks.jsonl content
3. Use `git mktree` to create tree with the blob
4. Use `git commit-tree` with parent from current branch tip
5. Use `git update-ref` to move branch to new commit
6. Update `.cub/.sync-state.json` with new SHA and timestamp
7. Return commit SHA

**Acceptance Criteria**:
- [ ] `commit()` creates commit on sync branch
- [ ] Working tree is unaffected
- [ ] Commit message defaults to "Sync tasks" if not provided
- [ ] Sync state updated after commit
- [ ] Returns commit SHA string

**Files**: `src/cub/core/sync/service.py`

---

### Task: cub-j1c.3 - Implement pull with conflict detection

Priority: 1
Labels: phase-3, model:opus, complexity:high, logic

**Context**: Pulling from remote requires fetching, detecting conflicts, and applying last-write-wins per task. Must warn on conflicts but not block.

**Implementation Steps**:
1. Implement `pull() -> SyncResult` dataclass with fields: success, conflicts, tasks_updated
2. Fetch remote sync branch: `git fetch origin cub-sync`
3. Compare local and remote task files
4. Detect conflicts: same task modified in both with different content
5. Apply last-write-wins based on `updated_at` timestamp
6. Merge remote changes into local tasks.jsonl
7. Log warnings for any conflicts
8. Commit merged result locally

**Acceptance Criteria**:
- [ ] `pull()` fetches from remote if available
- [ ] Conflicts detected by comparing task `updated_at`
- [ ] Warnings logged for conflicts
- [ ] Last-write-wins applied correctly
- [ ] `SyncResult` contains conflict details

**Files**: `src/cub/core/sync/service.py`, `src/cub/core/sync/models.py`

---

### Task: cub-j1c.4 - Implement push and status operations

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, logic

**Context**: Push sends local sync branch to remote. Status shows whether local is ahead, behind, or diverged from remote.

**Implementation Steps**:
1. Implement `push() -> bool` pushing sync branch to origin
2. Handle case where remote doesn't exist (create it)
3. Implement `get_status() -> SyncStatus` enum (UP_TO_DATE, AHEAD, BEHIND, DIVERGED)
4. Compare local and remote branch tips
5. Handle case where remote is unavailable gracefully
6. Create `SyncStatus` enum in models

**Acceptance Criteria**:
- [ ] `push()` sends sync branch to remote
- [ ] `push()` returns False gracefully if no remote
- [ ] `get_status()` correctly identifies all 4 states
- [ ] Works offline (returns appropriate status)

**Files**: `src/cub/core/sync/service.py`, `src/cub/core/sync/models.py`

---

### Task: cub-j1c.5 - Create cub sync CLI command and write tests

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, cli, test, checkpoint

**Context**: The CLI command exposes sync functionality to users. Tests ensure git operations work correctly.

**Implementation Steps**:
1. Create `src/cub/cli/sync.py` with Typer app
2. Implement `cub sync` - commit and push
3. Implement `cub sync --pull` - pull from remote
4. Implement `cub sync --status` - show sync status
5. Implement `cub sync --init` - initialize sync branch
6. Register command in main CLI app
7. Write integration tests using git repo fixture
8. Test offline scenarios

**Acceptance Criteria**:
- [ ] `cub sync` commits and pushes
- [ ] `cub sync --pull` pulls and reports conflicts
- [ ] `cub sync --status` shows human-readable status
- [ ] `cub sync --init` creates branch if missing
- [ ] Integration tests pass

**Files**: `src/cub/cli/sync.py`, `src/cub/cli/__init__.py`, `tests/test_sync.py`

---

## Epic: cub-j1d - 0.30-foundation #4: Run Loop Integration

Priority: 1
Labels: phase-4, model:sonnet

Integrate sync into the run loop so task mutations are automatically committed during `cub run`.

### Task: cub-j1d.1 - Add auto-sync after task mutations in run loop

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, logic

**Context**: When `cub run` closes a task, it should automatically sync to the cub-sync branch. This needs to be configurable.

**Implementation Steps**:
1. Add sync configuration to config models: `sync.enabled`, `sync.auto_sync` ("run", "always", "never")
2. Modify run loop in `src/cub/cli/run.py` to check sync config
3. After task close, call `SyncService.commit()` if auto_sync enabled
4. Handle sync failures gracefully (log warning, don't stop run)
5. Add `--no-sync` flag to disable for single run

**Acceptance Criteria**:
- [ ] Config option `sync.auto_sync = "run"` enables auto-sync
- [ ] Task close triggers sync commit during run
- [ ] Sync failures logged but don't stop run
- [ ] `--no-sync` flag disables auto-sync for that run

**Files**: `src/cub/cli/run.py`, `src/cub/core/config/models.py`

---

### Task: cub-j1d.2 - Test auto-sync and document behavior

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, test, docs, checkpoint

**Context**: Auto-sync needs integration testing and documentation so users understand the behavior.

**Implementation Steps**:
1. Write integration test for auto-sync during run
2. Test multi-task run with sync after each close
3. Test `--no-sync` flag
4. Test sync failure handling
5. Add section to README explaining sync behavior
6. Document config options

**Acceptance Criteria**:
- [ ] Integration tests pass for auto-sync
- [ ] Tests cover failure scenarios
- [ ] README has sync section
- [ ] Config options documented

**Files**: `tests/test_run_sync.py`, `README.md`

---

## Epic: cub-j1e - 0.30-foundation #5: Documentation Audit

Priority: 1
Labels: phase-5, model:haiku, docs

Ensure README and docs accurately reflect current commands and capabilities for alpha release.

### Task: cub-j1e.1 - Audit and update README command reference

Priority: 1
Labels: phase-5, model:haiku, complexity:low, docs

**Context**: README must match `cub --help` output. Deprecated commands must be removed, new commands added.

**Implementation Steps**:
1. Run `cub --help` and all subcommand `--help`
2. Compare against README command sections
3. Remove references to deprecated commands
4. Add new commands (`cub sync`, updated `cub init`)
5. Update examples to use JSONL backend
6. Verify all command flags documented

**Acceptance Criteria**:
- [ ] Every command in `cub --help` is in README
- [ ] No deprecated command references remain
- [ ] New `cub sync` command documented
- [ ] Examples use current syntax

**Files**: `README.md`

---

### Task: cub-j1e.2 - Walk through Quick Start and fix gaps

Priority: 1
Labels: phase-5, model:haiku, complexity:low, docs

**Context**: Quick Start must work end-to-end for a new user. Test it yourself and fix any issues.

**Implementation Steps**:
1. Follow Quick Start exactly as written in fresh directory
2. Note any errors or confusion points
3. Fix issues in README
4. Ensure JSONL backend is default path
5. Update any beads-specific instructions to be optional

**Acceptance Criteria**:
- [ ] Quick Start works end-to-end without errors
- [ ] No beads dependency required for basic flow
- [ ] All commands in Quick Start are valid

**Files**: `README.md`

---

### Task: cub-j1e.3 - Add alpha disclaimer and security warnings

Priority: 1
Labels: phase-5, model:haiku, complexity:low, docs, checkpoint

**Context**: Alpha release needs prominent disclaimers about stability and security considerations.

**Implementation Steps**:
1. Add alpha disclaimer banner at top of README
2. Add "Status: Alpha" badge
3. Add security warning section about permissions skipping
4. Mark experimental features with `[EXPERIMENTAL]` tag
5. Update CONTRIBUTING.md to match current architecture
6. Create `docs/ALPHA-NOTES.md` with known limitations

**Acceptance Criteria**:
- [ ] Alpha disclaimer visible at top of README
- [ ] Security section exists with appropriate warnings
- [ ] Experimental features clearly marked
- [ ] CONTRIBUTING.md current
- [ ] ALPHA-NOTES.md exists

**Files**: `README.md`, `CONTRIBUTING.md`, `docs/ALPHA-NOTES.md`

---

## Epic: cub-j1f - 0.30-foundation #6: CLI Polish

Priority: 2
Labels: phase-6, model:sonnet

Audit CLI for consistent UX, helpful errors, and intuitive behavior.

### Task: cub-j1f.1 - Audit and improve command help text

Priority: 2
Labels: phase-6, model:haiku, complexity:low, cli

**Context**: All commands should have helpful `--help` text that explains what they do and shows examples.

**Implementation Steps**:
1. Review all Typer command help strings
2. Add examples to complex commands
3. Ensure consistent formatting across commands
4. Add short descriptions to all subcommands
5. Fix any typos or unclear descriptions

**Acceptance Criteria**:
- [ ] All commands have descriptive help text
- [ ] Examples shown for complex commands
- [ ] Consistent formatting across all commands

**Files**: `src/cub/cli/*.py`

---

### Task: cub-j1f.2 - Add actionable error messages and standardize exit codes

Priority: 2
Labels: phase-6, model:sonnet, complexity:medium, cli

**Context**: Errors should tell users how to fix the problem. Exit codes should be consistent (0=success, 1=error, 2=user error).

**Implementation Steps**:
1. Audit common error paths (no harness, no git, no tasks)
2. Add actionable suggestions to each error
3. Standardize exit codes: 0=success, 1=error, 2=user error
4. Create error message templates with consistent format
5. Test error scenarios manually

**Acceptance Criteria**:
- [ ] Common errors include fix suggestions
- [ ] Exit codes consistent across all commands
- [ ] Error format is consistent

**Files**: `src/cub/cli/*.py`

---

### Task: cub-j1f.3 - Implement cub docs command and add alpha classifier

Priority: 2
Labels: phase-6, model:haiku, complexity:low, cli, checkpoint

**Context**: `cub docs` should open documentation in browser. Package metadata should indicate alpha status.

**Implementation Steps**:
1. Create `src/cub/cli/docs.py` with simple command
2. Use `webbrowser.open()` to open docs URL
3. Default to GitHub README or local docs
4. Register command in main CLI
5. Add `Development Status :: 3 - Alpha` classifier to pyproject.toml
6. Verify package metadata correct

**Acceptance Criteria**:
- [ ] `cub docs` opens browser to documentation
- [ ] Alpha classifier in pyproject.toml
- [ ] Package installable with correct metadata

**Files**: `src/cub/cli/docs.py`, `src/cub/cli/__init__.py`, `pyproject.toml`

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-j1a | 5 | P0 | JSONL Backend Core - native storage with beads schema |
| cub-j1b | 4 | P0 | Both Mode - dual-backend validation wrapper |
| cub-j1c | 5 | P1 | Sync Branch - git-based task persistence |
| cub-j1d | 2 | P1 | Run Loop Integration - auto-sync during cub run |
| cub-j1e | 3 | P1 | Documentation Audit - README and docs polish |
| cub-j1f | 3 | P2 | CLI Polish - help text and error messages |

**Total**: 6 epics, 22 tasks

**Checkpoints**:
- `cub-j1a.5` - JSONL backend complete, can be used standalone
- `cub-j1b.4` - Both mode complete, validation available
- `cub-j1c.5` - Sync branch complete, full persistence
- `cub-j1d.2` - Run integration complete, auto-sync works
- `cub-j1e.3` - Docs complete, alpha-ready
- `cub-j1f.3` - CLI polish complete, ready for release

**Ready to start immediately**:
- cub-j1a.1 (Create JsonlBackend class)
- cub-j1a.2 (Implement core CRUD methods) - after j1a.1
- cub-j1a.4 (Agent instructions and branch binding) - after j1a.1
- cub-j1a.5 (Migration and tests) - after j1a.2, j1a.3
