# Itemized Plan: Ledger Consolidation & Unified ID System

> Source: [cub-048-ledger-consolidation-and-id-system.md](../../specs/planned/cub-048-ledger-consolidation-and-id-system.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-02-04

## Context Summary

Cub has accumulated redundant storage directories (`runs/`, `run-sessions/`, `logs/`), collision-prone random IDs, and no traceability from specs to tasks. This plan consolidates storage into a single canonical ledger and introduces a hierarchical ID system tracked via the sync branch to enable full traceability and collision-free numbering across branches and worktrees.

**Mindset:** Production | **Scale:** Personal

---

## Epic: cub-048a-0 - ledger-consolidation #1: ID System Foundation

Priority: 0
Labels: phase-1, complexity:high, slice:id-system

Establish the hierarchical ID generation system with counter-based allocation tracked on the sync branch. This is the foundation that all other phases depend on.

**Checkpoint:** After this epic, hierarchical IDs can be generated and validated. Counter allocation works via sync branch.

---

### Task: cub-048a-0.1 - Create core/ids/ package with ID models

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, domain:model

**Context**: The ID models are the foundation of the hierarchical ID system. They provide type-safe representations of spec, plan, epic, task, and standalone IDs with validation and string conversion.

**Implementation Steps**:
1. Create `src/cub/core/ids/` directory with `__init__.py`
2. Create `models.py` with Pydantic models: `SpecId`, `PlanId`, `EpicId`, `TaskId`, `StandaloneTaskId`
3. Implement `__str__` methods for each model following the format spec
4. Add validation for letter/char fields (A-Z, a-z, 0-9 sequences)
5. Export public API from `__init__.py`

**Acceptance Criteria**:
- [ ] All five ID models implemented with proper validation
- [ ] `str(SpecId(project="cub", number=54))` returns `"cub-054"`
- [ ] `str(TaskId(...))` returns `"cub-054A-0.1"` format
- [ ] Invalid letter/char values raise ValidationError
- [ ] Models are immutable (frozen=True)

**Files**: `src/cub/core/ids/__init__.py`, `src/cub/core/ids/models.py`

---

### Task: cub-048a-0.2 - Implement ID parser and validator

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, domain:logic
Blocks: cub-048a-0.3, cub-048a-0.4

**Context**: The parser converts string IDs back to typed models and validates format. This enables working with IDs from task files, ledger entries, and user input.

**Implementation Steps**:
1. Create `src/cub/core/ids/parser.py`
2. Define regex patterns for each ID type (spec, plan, epic, task, standalone)
3. Implement `parse_id(id_str: str) -> SpecId | PlanId | EpicId | TaskId | StandaloneTaskId`
4. Implement `validate_id(id_str: str) -> bool` for quick format checking
5. Implement `get_id_type(id_str: str) -> Literal["spec", "plan", "epic", "task", "standalone"] | None`
6. Implement `get_parent_id(id_str: str) -> str | None` to extract parent from hierarchy
7. Handle backward compatibility with old random IDs (detect and pass through)

**Acceptance Criteria**:
- [ ] `parse_id("cub-054")` returns `SpecId(project="cub", number=54)`
- [ ] `parse_id("cub-054A-0.1")` returns fully nested `TaskId` with parent chain
- [ ] `get_parent_id("cub-054A-0.1")` returns `"cub-054A-0"`
- [ ] Old random IDs like `cub-k7m` are detected but not parsed (return None or raise)
- [ ] Invalid formats raise `ValueError` with descriptive message

**Files**: `src/cub/core/ids/parser.py`

---

### Task: cub-048a-0.3 - Implement counter management on sync branch

Priority: 0
Labels: phase-1, model:opus, complexity:high, domain:logic, risk:medium
Blocks: cub-048a-0.4

**Context**: Counters track the next available spec number and standalone task number. They live on the sync branch to enable collision-free allocation across worktrees. This integrates with the existing sync branch infrastructure.

**Implementation Steps**:
1. Add `CounterState` model to `src/cub/core/sync/models.py`
2. Create `src/cub/core/ids/counters.py` for counter operations
3. Implement `read_counters(sync_service: SyncService) -> CounterState`
4. Implement `allocate_spec_number(sync_service: SyncService) -> int` with optimistic locking
5. Implement `allocate_standalone_number(sync_service: SyncService) -> int`
6. Handle case where counters.json doesn't exist (initialize with defaults)
7. Implement retry logic for concurrent allocation conflicts

**Acceptance Criteria**:
- [ ] `CounterState` model has `spec_number`, `standalone_task_number`, `updated_at`
- [ ] `allocate_spec_number()` increments counter and commits to sync branch
- [ ] Concurrent allocations don't produce duplicate numbers
- [ ] Missing counters.json is auto-initialized
- [ ] Counter reads don't require network (use local sync branch state)

**Files**: `src/cub/core/sync/models.py`, `src/cub/core/ids/counters.py`

---

### Task: cub-048a-0.4 - Implement ID generator with counter integration

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, domain:logic

**Context**: The generator creates new IDs by combining counter allocation with the ID models. It provides the primary API for creating new specs, plans, epics, and tasks.

**Implementation Steps**:
1. Create `src/cub/core/ids/generator.py`
2. Implement `generate_spec_id(project: str, sync_service: SyncService) -> SpecId`
3. Implement `generate_plan_id(spec: SpecId, letter: str) -> PlanId` (letter is explicit)
4. Implement `generate_epic_id(plan: PlanId, char: str) -> EpicId` (char is explicit)
5. Implement `generate_task_id(epic: EpicId, number: int) -> TaskId` (number is explicit)
6. Implement `generate_standalone_id(project: str, sync_service: SyncService) -> StandaloneTaskId`
7. Add helper `next_plan_letter(existing: list[str]) -> str` for auto-selection
8. Add helper `next_epic_char(existing: list[str]) -> str` for auto-selection

**Acceptance Criteria**:
- [ ] `generate_spec_id("cub", sync)` allocates counter and returns `SpecId`
- [ ] Letter/char helpers follow sequence rules (A-Z, a-z, 0-9 for plans)
- [ ] Generator validates inputs (e.g., letter must be single char)
- [ ] All generators return properly typed ID models

**Files**: `src/cub/core/ids/generator.py`

---

### Task: cub-048a-0.5 - Create pre-push hook and update cub init

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, domain:setup
Blocks: cub-048a-1.1

**Context**: The pre-push hook verifies that locally-used spec/standalone numbers don't conflict with the remote sync branch. This catches collisions before they're pushed. The hook is installed by `cub init`.

**Implementation Steps**:
1. Create `src/cub/core/ids/hooks.py` with hook logic
2. Implement `verify_counters_before_push() -> tuple[bool, str]` that:
   - Fetches latest counters from remote sync branch
   - Compares local counter usage against remote
   - Returns (ok, message) tuple
3. Create shell script template `templates/hooks/pre-push` that calls Python
4. Update `cub init` to install pre-push hook to `.git/hooks/pre-push`
5. Make hook skip gracefully if sync branch not initialized
6. Add `--no-verify` documentation for bypassing

**Acceptance Criteria**:
- [ ] `cub init` installs pre-push hook (executable)
- [ ] Hook blocks push if local counters conflict with remote
- [ ] Hook passes silently if no conflicts
- [ ] Hook skips gracefully if sync branch not set up
- [ ] Tests verify hook installation and conflict detection

**Files**: `src/cub/core/ids/hooks.py`, `templates/hooks/pre-push`, `src/cub/cli/init_cmd.py`

---

## Epic: cub-048a-1 - ledger-consolidation #2: Ledger Consolidation

Priority: 0
Labels: phase-2, complexity:high, slice:ledger

Unify all storage into a single `.cub/ledger/` structure with `by-task/`, `by-epic/`, `by-plan/`, and `by-run/` subdirectories. Convert harness logs to JSONL and flatten the attempts/ directory structure.

**Checkpoint:** After this epic, all artifacts write to unified ledger structure. Old directories no longer used.

---

### Task: cub-048a-1.1 - Add PlanEntry and RunEntry models

Priority: 0
Labels: phase-2, model:sonnet, complexity:low, domain:model

**Context**: The ledger needs new models for plan-level and run-level aggregation. These complement the existing `LedgerEntry` and `EpicEntry` models.

**Implementation Steps**:
1. Add `PlanEntry` model to `src/cub/core/ledger/models.py`
2. Add `RunEntry` model to `src/cub/core/ledger/models.py`
3. Ensure models have all fields from architecture spec
4. Add `model_config` for JSON serialization compatibility
5. Export new models from package `__init__.py`

**Acceptance Criteria**:
- [ ] `PlanEntry` has: plan_id, spec_id, title, epics, status, timestamps, cost/token totals
- [ ] `RunEntry` has: run_id, timestamps, status, config, task lists, cost/token totals
- [ ] Both models serialize to JSON cleanly
- [ ] Status fields use Literal types for validation

**Files**: `src/cub/core/ledger/models.py`, `src/cub/core/ledger/__init__.py`

---

### Task: cub-048a-1.2 - Extend LedgerWriter with plan and run methods

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, domain:logic

**Context**: The LedgerWriter needs methods to create and update plan-level and run-level entries, following the same patterns as task and epic entries.

**Implementation Steps**:
1. Add `create_plan_entry(entry: PlanEntry) -> None` to `LedgerWriter`
2. Add `update_plan_entry(plan_id: str, updates: dict) -> None`
3. Add `create_run_entry(entry: RunEntry) -> None`
4. Add `update_run_entry(run_id: str, updates: dict) -> None`
5. Create `by-plan/{plan_id}/entry.json` directory structure
6. Create `by-run/{run_id}.json` file structure
7. Update index.jsonl with plan/run entries if needed

**Acceptance Criteria**:
- [ ] `create_plan_entry()` writes to `.cub/ledger/by-plan/{plan_id}/entry.json`
- [ ] `create_run_entry()` writes to `.cub/ledger/by-run/{run_id}.json`
- [ ] Updates use atomic write pattern (temp file + rename)
- [ ] Missing parent directories are created automatically

**Files**: `src/cub/core/ledger/writer.py`

---

### Task: cub-048a-1.3 - Create HarnessLogWriter for JSONL format

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, domain:logic

**Context**: Harness logs should be JSONL for structured queries instead of plaintext. This enables filtering, searching, and aggregating log data programmatically.

**Implementation Steps**:
1. Create `src/cub/core/ledger/harness_log.py`
2. Define `HarnessLogEvent` model with timestamp, event_type, data fields
3. Implement `HarnessLogWriter` class with:
   - `__init__(task_id: str, attempt: int)`
   - `write(event: HarnessLogEvent) -> None` (append to JSONL)
   - `close() -> None` (flush and close)
4. Implement `HarnessLogReader` class with:
   - `read_all(task_id: str, attempt: int) -> list[HarnessLogEvent]`
   - `stream(task_id: str, attempt: int) -> Iterator[HarnessLogEvent]`
5. Write to `by-task/{task_id}/{attempt:03d}-harness.jsonl`

**Acceptance Criteria**:
- [ ] Log events are valid JSONL (one JSON object per line)
- [ ] Reader can parse logs written by writer
- [ ] Large logs can be streamed without loading all into memory
- [ ] Timestamps are ISO 8601 format

**Files**: `src/cub/core/ledger/harness_log.py`

---

### Task: cub-048a-1.4 - Create ArtifactManager for flattened numbering

Priority: 0
Labels: phase-2, model:sonnet, complexity:low, domain:logic

**Context**: Artifacts should be numbered at task level (001-prompt.md, 002-prompt.md) without the attempts/ subdirectory. This simplifies the directory structure.

**Implementation Steps**:
1. Create `src/cub/core/ledger/artifacts.py`
2. Implement `ArtifactManager` class with:
   - `get_next_attempt_number(task_id: str) -> int`
   - `get_artifact_path(task_id: str, attempt: int, artifact_type: str) -> Path`
   - `list_attempts(task_id: str) -> list[int]`
3. Artifact types: "prompt", "harness", "patch"
4. Path format: `by-task/{task_id}/{attempt:03d}-{type}.{ext}`
5. Auto-detect next attempt number from existing files

**Acceptance Criteria**:
- [ ] `get_artifact_path("cub-048a-0.1", 1, "prompt")` returns correct Path
- [ ] Attempt numbers auto-increment based on existing files
- [ ] No `attempts/` subdirectory created
- [ ] Works with both new hierarchical IDs and old random IDs

**Files**: `src/cub/core/ledger/artifacts.py`

---

### Task: cub-048a-1.5 - Remove runs/ and run-sessions/ writes, fix epic title

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, domain:logic, risk:medium

**Context**: The run loop currently writes to `.cub/runs/` and `.cub/run-sessions/`. These writes need to be redirected to the new ledger structure. Also fix the bug where epic entries capture ID instead of title.

**Implementation Steps**:
1. Update `StatusWriter` to write to `ledger/by-run/` instead of `runs/`
2. Update `RunSessionManager` to write to `ledger/by-run/` instead of `run-sessions/`
3. Remove `runs/` directory creation code
4. Remove `run-sessions/` directory creation code
5. Find epic entry creation and pass title instead of ID
6. Update any code that reads from old locations to use new paths
7. Add deprecation warnings if old directories are detected

**Acceptance Criteria**:
- [ ] `cub run` no longer creates `.cub/runs/` directory
- [ ] `cub run` no longer creates `.cub/run-sessions/` directory
- [ ] Run data appears in `.cub/ledger/by-run/`
- [ ] Epic entries have `title` field with actual title, not ID
- [ ] Existing code that reads run data still works

**Files**: `src/cub/core/status/writer.py`, `src/cub/core/session/manager.py`, `src/cub/core/ledger/writer.py`

---

### Task: cub-048a-1.6 - Extend LedgerReader with plan and run queries

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, domain:logic

**Context**: The LedgerReader needs methods to query plan-level and run-level entries, enabling commands like `cub ledger show --plans` and run history queries.

**Implementation Steps**:
1. Add `get_plan(plan_id: str) -> PlanEntry | None` to `LedgerReader`
2. Add `list_plans(filters: PlanFilters | None) -> list[PlanEntry]`
3. Add `get_run(run_id: str) -> RunEntry | None`
4. Add `list_runs(filters: RunFilters | None) -> list[RunEntry]`
5. Create `PlanFilters` and `RunFilters` dataclasses
6. Support filtering by status, date range, spec_id

**Acceptance Criteria**:
- [ ] `get_plan()` returns PlanEntry or None
- [ ] `list_plans()` returns all plans, optionally filtered
- [ ] `list_runs()` supports date range filtering
- [ ] Empty results return empty list, not None

**Files**: `src/cub/core/ledger/reader.py`, `src/cub/core/ledger/models.py`

---

## Epic: cub-048a-2 - ledger-consolidation #3: Run Loop Integration

Priority: 0
Labels: phase-3, complexity:high, slice:run-loop

Integrate the new ID system and consolidated ledger into the run loop. Add `--plan` flag to `cub run` and remove the separate `build-plan` command.

**Checkpoint:** After this epic, `cub run --plan` works and `build-plan` is removed. Core functionality complete.

---

### Task: cub-048a-2.1 - Add --plan flag and plan iteration logic

Priority: 0
Labels: phase-3, model:opus, complexity:high, domain:logic, risk:medium

**Context**: The `--plan` flag enables `cub run` to execute an entire plan by iterating through its epics. This replaces the separate `build-plan` command with integrated functionality.

**Implementation Steps**:
1. Add `plan: str | None` field to `RunConfig` model
2. Add `--plan` flag to `cub run` CLI command
3. Extract plan iteration logic from `build_plan.py`
4. Add `execute_plan(plan_slug: str)` method to `RunLoop` or `RunService`
5. Implement epic ordering and iteration
6. Handle epic completion detection (all tasks in epic done)
7. Support `--start-epic` and `--only-epic` options for partial runs

**Acceptance Criteria**:
- [ ] `cub run --plan my-plan` executes all epics in order
- [ ] Plan execution creates/updates PlanEntry in ledger
- [ ] Epic completion triggers EpicEntry creation
- [ ] Partial run options work (--start-epic, --only-epic)
- [ ] Plan execution respects budget limits

**Files**: `src/cub/core/run/models.py`, `src/cub/core/run/loop.py`, `src/cub/cli/run.py`

---

### Task: cub-048a-2.2 - Update ledger commit timing

Priority: 0
Labels: phase-3, model:sonnet, complexity:medium, domain:logic

**Context**: Ledger entries should be committed alongside code changes, not as a separate cleanup step. This ensures artifacts are always in sync with the code they describe.

**Implementation Steps**:
1. Identify where task completion commits happen in run loop
2. Add ledger entry write before commit (so it's included)
3. Update commit message to mention ledger update
4. Ensure epic entry is written before epic completion commit
5. Remove any "cleanup" commits that only contain ledger files
6. Test that ledger files appear in same commit as code changes

**Acceptance Criteria**:
- [ ] Task completion commit includes `by-task/{id}.json`
- [ ] Epic completion commit includes `by-epic/{id}/entry.json`
- [ ] No separate "ledger cleanup" commits
- [ ] Git log shows ledger files with corresponding code changes

**Files**: `src/cub/core/run/loop.py`, `src/cub/core/ledger/writer.py`

---

### Task: cub-048a-2.3 - Remove build-plan command

Priority: 0
Labels: phase-3, model:haiku, complexity:low, domain:setup

**Context**: With plan execution integrated into `cub run --plan`, the separate `build-plan` command is redundant and should be removed.

**Implementation Steps**:
1. Remove `cli/build_plan.py` module
2. Remove build-plan registration from CLI app
3. Remove build-plan from bash delegated commands if present
4. Update CLAUDE.md to document `cub run --plan` instead
5. Remove any build-plan related templates or scripts
6. Add migration note to UPGRADING.md

**Acceptance Criteria**:
- [ ] `cub build-plan` returns "unknown command" error
- [ ] Documentation references `cub run --plan` not `build-plan`
- [ ] No dead code referencing build-plan remains
- [ ] UPGRADING.md documents the change

**Files**: `src/cub/cli/build_plan.py` (delete), `src/cub/cli/__init__.py`, `CLAUDE.md`, `UPGRADING.md`

---

### Task: cub-048a-2.4 - Tests for run loop changes

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, domain:test

**Context**: The run loop changes need comprehensive tests to ensure plan execution, ledger timing, and ID integration work correctly.

**Implementation Steps**:
1. Create `tests/test_run_plan.py` for plan execution tests
2. Test `cub run --plan` happy path (mock harness)
3. Test epic ordering and completion detection
4. Test ledger entries created at correct times
5. Test partial run options (--start-epic, --only-epic)
6. Test budget enforcement during plan execution
7. Test error handling (epic failure, harness timeout)

**Acceptance Criteria**:
- [ ] Plan execution test with multiple epics passes
- [ ] Ledger timing test verifies files in same commit
- [ ] Partial run tests verify correct epic selection
- [ ] Error handling tests verify graceful degradation
- [ ] All tests pass with `pytest tests/test_run_plan.py`

**Files**: `tests/test_run_plan.py`

---

## Epic: cub-048a-3 - ledger-consolidation #4: Lifecycle Hooks

Priority: 1
Labels: phase-4, complexity:medium, slice:hooks

Extend the hooks infrastructure with four new lifecycle events: pre-session, end-of-task, end-of-epic, end-of-plan. Each provides rich context for user-defined scripts.

---

### Task: cub-048a-3.1 - Create core/hooks/ package with context models

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, domain:model

**Context**: A new hooks package consolidates hook functionality and defines the context models that carry data to hook scripts.

**Implementation Steps**:
1. Create `src/cub/core/hooks/` directory with `__init__.py`
2. Create `models.py` with context models from architecture:
   - `PreSessionContext`
   - `EndOfTaskContext`
   - `EndOfEpicContext`
   - `EndOfPlanContext`
3. Create `HookResult` model for hook execution results
4. Create `HookConfig` model for hook configuration
5. Ensure all context models serialize to JSON for env var passing

**Acceptance Criteria**:
- [ ] All four context models implemented with fields from architecture
- [ ] Context models can serialize to JSON string
- [ ] HookResult captures success/failure, output, duration
- [ ] Models exported from package `__init__.py`

**Files**: `src/cub/core/hooks/__init__.py`, `src/cub/core/hooks/models.py`

---

### Task: cub-048a-3.2 - Implement hook executor and discovery

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, domain:logic

**Context**: The hook executor runs user scripts with context passed via environment variables. Discovery finds scripts in project and global hook directories.

**Implementation Steps**:
1. Create `src/cub/core/hooks/discovery.py`
2. Implement `discover_hooks(hook_name: str) -> list[Path]`
   - Check `.cub/hooks/{hook_name}/` for scripts
   - Check `~/.config/cub/hooks/{hook_name}/` for global scripts
   - Return executable scripts sorted by name
3. Create `src/cub/core/hooks/executor.py`
4. Implement `HookExecutor.run(hook_name: str, context: BaseModel) -> HookResult`
   - Serialize context to JSON env var `CUB_HOOK_CONTEXT`
   - Also set individual env vars for common fields
   - Run each discovered script
   - Capture stdout/stderr
   - Handle timeouts and failures

**Acceptance Criteria**:
- [ ] Discovery finds scripts in both project and global directories
- [ ] Only executable files are returned
- [ ] Executor passes context via `CUB_HOOK_CONTEXT` env var
- [ ] Hook timeout is configurable (default 30s)
- [ ] Failed hooks don't block execution (configurable)

**Files**: `src/cub/core/hooks/discovery.py`, `src/cub/core/hooks/executor.py`

---

### Task: cub-048a-3.3 - Integrate lifecycle hooks into run loop

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, domain:logic

**Context**: The run loop needs to invoke lifecycle hooks at the appropriate points: before session starts, after task completion, after epic completion, after plan completion.

**Implementation Steps**:
1. Create `src/cub/core/hooks/lifecycle.py` with hook point definitions
2. Add hook invocation before harness session (pre-session)
3. Add hook invocation after task completion (end-of-task)
4. Add hook invocation after epic completion (end-of-epic)
5. Add hook invocation after plan completion (end-of-plan)
6. Build context objects from run loop state
7. Log hook execution results
8. Make hooks optional (check config before running)

**Acceptance Criteria**:
- [ ] `pre-session` hook runs before harness invocation
- [ ] `end-of-task` hook runs after task marked complete
- [ ] `end-of-epic` hook runs after last task in epic
- [ ] `end-of-plan` hook runs after last epic in plan
- [ ] Hooks can be disabled via config

**Files**: `src/cub/core/hooks/lifecycle.py`, `src/cub/core/run/loop.py`

---

### Task: cub-048a-3.4 - Update cub init for hook directories and tests

Priority: 1
Labels: phase-4, model:haiku, complexity:low, domain:setup, domain:test

**Context**: `cub init` should create the hook directories so users know where to place their scripts. Tests verify hook functionality.

**Implementation Steps**:
1. Update `cub init` to create `.cub/hooks/` directory
2. Create subdirectories for each hook point
3. Add README.md in hooks directory explaining usage
4. Create `tests/test_hooks_lifecycle.py`
5. Test hook discovery with mock scripts
6. Test hook execution with context passing
7. Test hook failure handling

**Acceptance Criteria**:
- [ ] `cub init` creates `.cub/hooks/{pre-session,end-of-task,end-of-epic,end-of-plan}/`
- [ ] README.md explains hook usage and context fields
- [ ] Hook discovery tests pass
- [ ] Hook execution tests verify context in env vars

**Files**: `src/cub/cli/init_cmd.py`, `templates/hooks/README.md`, `tests/test_hooks_lifecycle.py`

---

## Epic: cub-048a-4 - ledger-consolidation #5: New Commands

Priority: 1
Labels: phase-5, complexity:medium, slice:commands

Implement five new commands: `release`, `retro`, `verify`, `learn extract`, and `sync agent`. Each has a service layer and CLI interface.

---

### Task: cub-048a-4.1 - Implement cub release command

Priority: 1
Labels: phase-5, model:sonnet, complexity:medium, domain:logic, domain:api

**Context**: The release command marks a plan as released, updates CHANGELOG, creates a git tag, and moves specs to the released/ directory.

**Implementation Steps**:
1. Create `src/cub/core/release/` package with `service.py`
2. Implement `ReleaseService` with methods:
   - `release_plan(plan_id: str, version: str) -> ReleaseResult`
   - `update_changelog(plan_id: str, version: str) -> None`
   - `create_git_tag(version: str, message: str) -> None`
   - `move_spec_to_released(spec_id: str) -> None`
3. Create `src/cub/cli/release.py` with Typer command
4. Add `--dry-run` flag to preview changes
5. Add `--no-tag` flag to skip git tag creation

**Acceptance Criteria**:
- [ ] `cub release cub-048a v0.30` updates ledger status to "released"
- [ ] CHANGELOG.md is updated with release notes from plan
- [ ] Git tag is created (unless --no-tag)
- [ ] Spec file is moved to specs/released/
- [ ] Dry-run shows what would happen without changes

**Files**: `src/cub/core/release/__init__.py`, `src/cub/core/release/service.py`, `src/cub/cli/release.py`

---

### Task: cub-048a-4.2 - Implement cub retro command

Priority: 1
Labels: phase-5, model:sonnet, complexity:medium, domain:logic, domain:api

**Context**: The retro command generates a retrospective report for a completed plan or epic, summarizing what went well, what didn't, and lessons learned.

**Implementation Steps**:
1. Create `src/cub/core/retro/` package with `service.py`
2. Implement `RetroService` with methods:
   - `generate_retro(plan_id: str) -> RetroReport`
   - `extract_metrics(plan_id: str) -> dict` (cost, duration, task counts)
   - `identify_issues(plan_id: str) -> list[str]` (failed tasks, retries)
3. Create `RetroReport` model with sections
4. Create `src/cub/cli/retro.py` with Typer command
5. Output as markdown to stdout or file
6. Support `--epic` flag for epic-level retro

**Acceptance Criteria**:
- [ ] `cub retro cub-048a` generates markdown report
- [ ] Report includes: summary, metrics, issues, timeline
- [ ] `--output` flag writes to file instead of stdout
- [ ] Epic-level retro works with `--epic` flag

**Files**: `src/cub/core/retro/__init__.py`, `src/cub/core/retro/service.py`, `src/cub/cli/retro.py`

---

### Task: cub-048a-4.3 - Implement cub verify command

Priority: 1
Labels: phase-5, model:sonnet, complexity:medium, domain:logic, domain:api

**Context**: The verify command checks ledger consistency, ID integrity, and counter sync status. It's useful for diagnosing issues and ensuring data health.

**Implementation Steps**:
1. Create `src/cub/core/verify/` package with `service.py`
2. Implement `VerifyService` with checks:
   - `check_ledger_consistency() -> list[Issue]` (orphaned entries, missing files)
   - `check_id_integrity() -> list[Issue]` (invalid formats, broken references)
   - `check_counter_sync() -> list[Issue]` (local vs remote counters)
3. Create `Issue` model with severity, message, fix suggestion
4. Create `src/cub/cli/verify.py` with Typer command
5. Support `--fix` flag to auto-fix simple issues
6. Support filtering: `--ledger`, `--ids`, `--counters`

**Acceptance Criteria**:
- [ ] `cub verify` runs all checks and reports issues
- [ ] Exit code is non-zero if issues found
- [ ] `--fix` attempts to repair simple issues
- [ ] Output is clear about what's checked and what failed

**Files**: `src/cub/core/verify/__init__.py`, `src/cub/core/verify/service.py`, `src/cub/cli/verify.py`

---

### Task: cub-048a-4.4 - Implement cub learn extract command

Priority: 1
Labels: phase-5, model:opus, complexity:high, domain:logic, domain:api

**Context**: The learn extract command analyzes ledger entries to extract patterns and lessons, updating guardrails.md and CLAUDE.md with discovered knowledge.

**Implementation Steps**:
1. Create `src/cub/core/learn/` package with `service.py`
2. Implement `LearnService` with methods:
   - `extract_patterns(since: date | None) -> list[Pattern]`
   - `suggest_guardrails(patterns: list[Pattern]) -> list[str]`
   - `update_guardrails(suggestions: list[str]) -> None`
   - `update_claude_md(insights: list[str]) -> None`
3. Create `Pattern` model for extracted patterns
4. Create `src/cub/cli/learn.py` with Typer command
5. Support `--dry-run` to preview changes
6. Support `--since` to limit analysis window

**Acceptance Criteria**:
- [ ] `cub learn extract` analyzes recent ledger entries
- [ ] Patterns are identified (repeated failures, cost outliers, etc.)
- [ ] Suggested guardrails are actionable
- [ ] `--dry-run` shows suggestions without modifying files

**Files**: `src/cub/core/learn/__init__.py`, `src/cub/core/learn/service.py`, `src/cub/cli/learn.py`

---

### Task: cub-048a-4.5 - Implement cub sync agent command

Priority: 1
Labels: phase-5, model:sonnet, complexity:medium, domain:logic, domain:api

**Context**: The sync agent command manually syncs managed sections in agent.md/CLAUDE.md across worktrees and branches, pulling from or pushing to the sync branch.

**Implementation Steps**:
1. Extend `SyncService` in `src/cub/core/sync/service.py`:
   - Add `sync_agent_sections(direction: Literal["push", "pull"]) -> SyncResult`
   - Add `get_managed_sections() -> dict[str, str]`
   - Add `set_managed_sections(sections: dict[str, str]) -> None`
2. Implement managed section parsing (find markers, extract content)
3. Implement managed section injection (replace between markers)
4. Add `sync agent` subcommand to `src/cub/cli/sync.py`
5. Support `--push` and `--pull` directions
6. Default to pull if no direction specified

**Acceptance Criteria**:
- [ ] `cub sync agent` pulls managed sections from sync branch
- [ ] `cub sync agent --push` pushes local sections to sync branch
- [ ] Managed section markers are preserved
- [ ] Non-managed content is not affected
- [ ] Conflict detection if both sides changed

**Files**: `src/cub/core/sync/service.py`, `src/cub/cli/sync.py`

---

## Epic: cub-048a-5 - ledger-consolidation #6: Consistency Checks & Cleanup

Priority: 1
Labels: phase-6, complexity:low, slice:cleanup

Add integrity checks to `cub doctor` and `cub run`, remove deprecated code paths, and finalize documentation.

---

### Task: cub-048a-5.1 - Add consistency checks to cub doctor

Priority: 1
Labels: phase-6, model:sonnet, complexity:medium, domain:logic

**Context**: `cub doctor` should include checks for ledger consistency, ID integrity, and counter sync status, reusing the verify service.

**Implementation Steps**:
1. Import `VerifyService` in `src/cub/cli/doctor.py`
2. Add "Ledger Health" section to doctor output
3. Run `check_ledger_consistency()` and report issues
4. Add "ID System" section
5. Run `check_id_integrity()` and report issues
6. Add "Counter Sync" section
7. Run `check_counter_sync()` and report issues
8. Use Rich formatting for clear output

**Acceptance Criteria**:
- [ ] `cub doctor` shows ledger health status
- [ ] Issues are displayed with severity and suggestions
- [ ] Passing checks show green checkmarks
- [ ] Failing checks show red X with details

**Files**: `src/cub/cli/doctor.py`

---

### Task: cub-048a-5.2 - Add pre-run consistency check

Priority: 1
Labels: phase-6, model:haiku, complexity:low, domain:logic

**Context**: `cub run` should optionally check consistency before starting, catching issues early. This should be fast and skippable.

**Implementation Steps**:
1. Add `--skip-checks` flag to `cub run`
2. Before run loop starts, call fast consistency checks
3. Check: ledger directory exists, counters readable, no obvious corruption
4. Skip expensive checks (full integrity scan)
5. Warn but don't block on minor issues
6. Block on critical issues (corrupted counter state)

**Acceptance Criteria**:
- [ ] `cub run` performs quick sanity check by default
- [ ] `cub run --skip-checks` bypasses pre-run checks
- [ ] Check completes in <1 second
- [ ] Critical issues block with clear error message

**Files**: `src/cub/cli/run.py`, `src/cub/core/run/loop.py`

---

### Task: cub-048a-5.3 - Remove deprecated code paths

Priority: 1
Labels: phase-6, model:haiku, complexity:low, domain:cleanup

**Context**: With the new ledger structure in place, code that reads from or writes to the old directories should be removed.

**Implementation Steps**:
1. Search for references to `.cub/runs/` and remove
2. Search for references to `.cub/run-sessions/` and remove
3. Search for references to `.cub/logs/` and remove
4. Remove `attempts/` directory handling in artifact code
5. Remove any backward-compatibility shims added during migration
6. Run tests to ensure nothing breaks

**Acceptance Criteria**:
- [ ] No code references `runs/` directory
- [ ] No code references `run-sessions/` directory
- [ ] No code references `logs/` directory
- [ ] All tests pass after removal

**Files**: Various (search and remove)

---

### Task: cub-048a-5.4 - Update documentation and gitignore

Priority: 1
Labels: phase-6, model:haiku, complexity:low, domain:docs

**Context**: Documentation needs to reflect the new storage structure, ID system, and commands. The gitignore template needs updating for new paths.

**Implementation Steps**:
1. Update CLAUDE.md with new ledger structure
2. Update CLAUDE.md with new ID format documentation
3. Update CLAUDE.md with new commands (release, retro, verify, learn, sync agent)
4. Remove references to build-plan, runs/, run-sessions/
5. Update `.gitignore` template in templates/
6. Add `.cub/ledger/by-run/` to gitignore (if run data shouldn't be committed)
7. Update README.md if needed
8. Update UPGRADING.md with migration notes

**Acceptance Criteria**:
- [ ] CLAUDE.md documents current state accurately
- [ ] New commands are documented
- [ ] Deprecated commands/paths are removed from docs
- [ ] UPGRADING.md has clear migration instructions

**Files**: `CLAUDE.md`, `README.md`, `UPGRADING.md`, `templates/.gitignore`

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-048a-0 | 5 | P0 | ID System Foundation |
| cub-048a-1 | 6 | P0 | Ledger Consolidation |
| cub-048a-2 | 4 | P0 | Run Loop Integration |
| cub-048a-3 | 4 | P1 | Lifecycle Hooks |
| cub-048a-4 | 5 | P1 | New Commands |
| cub-048a-5 | 4 | P1 | Consistency Checks & Cleanup |

**Total**: 6 epics, 28 tasks

**Checkpoints**:
- After cub-048a-0: ID system working, hierarchical IDs can be generated
- After cub-048a-2: Core functionality complete (`cub run --plan` replaces `build-plan`)
- After cub-048a-5: Full feature complete, documentation updated

**Ready to start**: 5 tasks in cub-048a-0 (Phase 1)
