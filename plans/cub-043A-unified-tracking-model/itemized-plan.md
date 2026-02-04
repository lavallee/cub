# Itemized Plan: Unified Tracking Model

> Source: [unified-tracking-model.md](../../specs/researching/unified-tracking-model.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-24

## Context Summary

Consolidate cub's tracking systems into a unified model centered on the ledger as the permanent record of work. The ledger extends the task lifecycle beyond beads—tracking work from first development attempt through review, validation, and release.

**Mindset:** Production | **Scale:** Personal

---

## Epic: cub-r4n - unified-tracking-model #1: Run Session Infrastructure

Priority: 0
Labels: phase-1, checkpoint

Track active `cub run` executions with symlink-based detection and orphan handling. This is the foundation for knowing what's currently running and enables `cub monitor` to display live progress.

### Task: cub-r4n.1 - Create session module and models

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, model

**Context**: The run session infrastructure needs Pydantic models to represent session state. This is the foundation for tracking active `cub run` executions.

**Implementation Steps**:
1. Create `src/cub/core/session/__init__.py` with module exports
2. Create `src/cub/core/session/models.py` with `SessionStatus` enum (running, completed, orphaned), `SessionBudget` model, and `RunSession` model with all fields from architecture spec
3. Add `generate_run_id()` helper (format: `cub-YYYYMMDD-HHMMSS`)
4. Ensure mypy strict compliance and JSON serialization works

**Acceptance Criteria**:
- [ ] `src/cub/core/session/models.py` exists with RunSession, SessionStatus, SessionBudget
- [ ] Models use Pydantic v2 patterns (Field, ConfigDict, validators)
- [ ] `generate_run_id()` produces correct format
- [ ] `mypy src/cub/core/session/` passes

**Files**: `src/cub/core/session/__init__.py`, `src/cub/core/session/models.py`

---

### Task: cub-r4n.2 - Implement RunSessionManager class

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, logic
Blocks: cub-r4n.3, cub-r4n.4

**Context**: The RunSessionManager handles the lifecycle of run sessions: creating files, managing the symlink, detecting orphans, and updating progress.

**Implementation Steps**:
1. Create `src/cub/core/session/manager.py`
2. Implement `RunSessionManager` class with `__init__(cub_dir)`, `start_session()`, `get_active_session()`, `update_session()`, `end_session()`, `detect_orphans()`
3. Handle atomic symlink replacement (unlink + symlink)
4. Add `_mark_orphaned(session, reason)` helper

**Acceptance Criteria**:
- [ ] `RunSessionManager` implements all 5 public methods
- [ ] Session files written to `.cub/run-sessions/`
- [ ] `active-run.json` symlink managed correctly
- [ ] Orphan detection finds stale sessions
- [ ] `mypy src/cub/core/session/` passes

**Files**: `src/cub/core/session/manager.py`, `src/cub/core/session/__init__.py`

---

### Task: cub-r4n.3 - Wire session manager into cub run

Priority: 0
Labels: phase-1, model:opus, complexity:high, logic
Blocks: cub-r4n.5

**Context**: The run loop needs to create a session on start, update it during execution, and end it on completion. This connects the session infrastructure to the actual execution flow.

**Implementation Steps**:
1. Import RunSessionManager in `cli/run.py`
2. At run start: instantiate manager, detect orphans, call `start_session()`
3. After each task completes: call `update_session()`
4. At run end: call `end_session()` with appropriate status
5. Use try/finally to ensure session is ended even on exceptions

**Acceptance Criteria**:
- [ ] `cub run` creates session file in `.cub/run-sessions/`
- [ ] `active-run.json` symlink exists during run
- [ ] Session updated after each task
- [ ] Symlink removed on run completion
- [ ] Orphans from previous crashed runs are marked

**Files**: `src/cub/cli/run.py`

---

### Task: cub-r4n.4 - Update cub monitor for session reading

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, ui

**Context**: `cub monitor` displays live progress. It should read the active session via the symlink rather than any previous mechanism.

**Implementation Steps**:
1. Import RunSessionManager in `cli/monitor.py`
2. Use `get_active_session()` to check if a run is active
3. Display session info: run_id, harness, tasks_completed, budget usage
4. Handle case where no active session (show "No active run")
5. Add refresh logic to poll session file for updates

**Acceptance Criteria**:
- [ ] `cub monitor` shows active session info when running
- [ ] Displays "No active run" when nothing is running
- [ ] Shows tasks_completed, budget usage
- [ ] Refreshes as session updates

**Files**: `src/cub/cli/monitor.py`

---

### Task: cub-r4n.5 - Add tests for session lifecycle

Priority: 0
Labels: phase-1, model:haiku, complexity:low, test

**Context**: Tests ensure the session infrastructure works correctly: file creation, symlink management, orphan detection.

**Implementation Steps**:
1. Create `tests/test_session_manager.py`
2. Add fixture for temp `.cub/` directory
3. Test cases: start_session, get_active_session, update_session, end_session, detect_orphans, multiple sessions

**Acceptance Criteria**:
- [ ] All test cases pass
- [ ] Tests use temp directories (no side effects)
- [ ] Orphan detection tested
- [ ] `pytest tests/test_session_manager.py -v` passes

**Files**: `tests/test_session_manager.py`

---

## Epic: cub-l7e - unified-tracking-model #2: Ledger Entry Lifecycle

Priority: 0
Labels: phase-2, checkpoint

Create and finalize ledger entries during task execution, tracking all attempts with prompts and logs. Every task execution is fully recorded: initial state capture, each attempt with prompt/log, and final outcome.

### Task: cub-l7e.1 - Extend LedgerEntry model with new fields

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, model
Blocks: cub-l7e.2

**Context**: The existing LedgerEntry model needs extension to support lineage tracking, multiple attempts, outcomes, and workflow stages per the spec.

**Implementation Steps**:
1. Add new models to `src/cub/core/ledger/models.py`: Lineage, TaskSnapshot, TaskChanged, Attempt, Outcome, DriftRecord, WorkflowState, StateTransition
2. Update `LedgerEntry` to include new fields with proper defaults
3. Add `version: int = 1` field
4. Ensure backward compatibility for reading old entries (optional fields)

**Acceptance Criteria**:
- [ ] All new models defined with Pydantic v2 patterns
- [ ] LedgerEntry includes lineage, task, task_changed, attempts, outcome, drift, verification, workflow, state_history
- [ ] Models serialize to JSON matching spec format
- [ ] `mypy src/cub/core/ledger/` passes

**Files**: `src/cub/core/ledger/models.py`

---

### Task: cub-l7e.2 - Implement prompt and log file writing

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, logic
Blocks: cub-l7e.3

**Context**: Each attempt needs a prompt file (with YAML frontmatter) and a harness log file. These are stored in the task's attempts/ directory.

**Implementation Steps**:
1. Add to `src/cub/core/ledger/writer.py`: `write_prompt_file()` and `write_harness_log()`
2. Create directory structure: `.cub/ledger/by-task/{task-id}/attempts/`
3. Implement YAML frontmatter format for prompt files
4. File naming: `001-prompt.md`, `001-harness.log` (zero-padded 3 digits)

**Acceptance Criteria**:
- [ ] `write_prompt_file()` creates properly formatted markdown with frontmatter
- [ ] `write_harness_log()` writes raw log content
- [ ] Files named with zero-padded attempt numbers
- [ ] Parent directories created automatically

**Files**: `src/cub/core/ledger/writer.py`

---

### Task: cub-l7e.3 - Create LedgerIntegration layer

Priority: 0
Labels: phase-2, model:opus, complexity:high, logic
Blocks: cub-l7e.4

**Context**: The LedgerIntegration layer coordinates all ledger writes during task execution, providing a clean interface for the run loop.

**Implementation Steps**:
1. Create `src/cub/core/ledger/integration.py`
2. Implement `LedgerIntegration` class with: `on_task_start()`, `on_attempt_start()`, `on_attempt_end()`, `on_task_close()`
3. Add helper `_detect_task_changed()` for drift detection
4. Coordinate with LedgerWriter for all file operations

**Acceptance Criteria**:
- [ ] LedgerIntegration implements all 4 lifecycle methods
- [ ] on_task_start creates entry with captured task state
- [ ] on_attempt_start writes prompt file
- [ ] on_attempt_end appends attempt and writes log
- [ ] on_task_close finalizes with outcome and task_changed detection

**Files**: `src/cub/core/ledger/integration.py`, `src/cub/core/ledger/__init__.py`

---

### Task: cub-l7e.4 - Wire LedgerIntegration into run loop

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, logic
Blocks: cub-l7e.5

**Context**: The run loop needs to call LedgerIntegration at each lifecycle point: task start, attempt start/end, task close.

**Implementation Steps**:
1. Import LedgerIntegration in `cli/run.py`
2. Instantiate at run start alongside RunSessionManager
3. Call lifecycle methods at appropriate points in task execution
4. Build Lineage from task metadata and collect commit refs from git

**Acceptance Criteria**:
- [ ] LedgerIntegration instantiated in run loop
- [ ] All 4 lifecycle methods called at correct points
- [ ] Ledger entry created on task start
- [ ] Prompt/log files written for each attempt
- [ ] Entry finalized on task close

**Files**: `src/cub/cli/run.py`

---

### Task: cub-l7e.5 - Add tests for ledger entry lifecycle

Priority: 0
Labels: phase-2, model:haiku, complexity:low, test

**Context**: Tests ensure the full task lifecycle is correctly recorded in the ledger.

**Implementation Steps**:
1. Create `tests/test_ledger_integration.py`
2. Add fixtures for temp ledger directory and LedgerIntegration instance
3. Test full lifecycle, task_changed detection, multiple attempts, file structure

**Acceptance Criteria**:
- [ ] All test cases pass
- [ ] Full lifecycle tested end-to-end
- [ ] task_changed detection tested
- [ ] File structure verified

**Files**: `tests/test_ledger_integration.py`

---

## Epic: cub-e2p - unified-tracking-model #3: Epic Aggregation

Priority: 1
Labels: phase-3, checkpoint

Track epic-level progress by aggregating data from child tasks. Provides project-level visibility into costs, progress, and escalation rates.

### Task: cub-e2p.1 - Add EpicEntry and aggregation models

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, model
Blocks: cub-e2p.2

**Context**: Epic entries aggregate data from child tasks, providing project-level visibility.

**Implementation Steps**:
1. Add to `src/cub/core/ledger/models.py`: EpicSnapshot, EpicAggregates, EpicEntry
2. Add `compute_aggregates(task_entries) -> EpicAggregates` helper
3. Compute: total_tasks, tasks_completed, total_cost, escalation_rate, avg_cost_per_task

**Acceptance Criteria**:
- [ ] EpicEntry model defined with all fields
- [ ] EpicAggregates computes all metrics
- [ ] `compute_aggregates()` helper works correctly
- [ ] `mypy src/cub/core/ledger/` passes

**Files**: `src/cub/core/ledger/models.py`

---

### Task: cub-e2p.2 - Implement epic CRUD and aggregation updates

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, logic
Blocks: cub-e2p.3

**Context**: LedgerWriter needs methods to create/update epic entries and recompute aggregates from child tasks.

**Implementation Steps**:
1. Add to `src/cub/core/ledger/writer.py`: `create_epic_entry()`, `get_epic_entry()`, `update_epic_aggregates()`, `add_task_to_epic()`
2. Create directory structure: `.cub/ledger/by-epic/{epic-id}/entry.json`
3. In `LedgerIntegration.on_task_close()`: update epic aggregates, auto-create if needed
4. Compute epic workflow.stage based on child task stages

**Acceptance Criteria**:
- [ ] Epic entries written to `.cub/ledger/by-epic/`
- [ ] `update_epic_aggregates()` correctly computes all metrics
- [ ] Epic auto-created when first task references it
- [ ] Epic stage computed from child tasks

**Files**: `src/cub/core/ledger/writer.py`, `src/cub/core/ledger/integration.py`

---

### Task: cub-e2p.3 - Add tests for epic aggregation

Priority: 1
Labels: phase-3, model:haiku, complexity:low, test

**Context**: Tests ensure epic aggregation works correctly across multiple tasks.

**Implementation Steps**:
1. Create `tests/test_epic_aggregation.py`
2. Test: epic auto-creation, aggregates computation, escalation rate, stage computation, multiple tasks same epic

**Acceptance Criteria**:
- [ ] All test cases pass
- [ ] Aggregation math verified
- [ ] Epic stage logic tested

**Files**: `tests/test_epic_aggregation.py`

---

## Epic: cub-c5i - unified-tracking-model #4: CLI Commands

Priority: 1
Labels: phase-4, checkpoint

Complete the ledger CLI interface with update, export, and gc commands. Provides user-facing tools for ledger inspection and management.

### Task: cub-c5i.1 - Extend ledger show for new fields

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, ui
Blocks: cub-c5i.2, cub-c5i.3, cub-c5i.4

**Context**: The existing `ledger show` command needs to display the new fields: attempts, outcome, lineage, workflow history.

**Implementation Steps**:
1. Update `src/cub/cli/ledger.py` show command with `--attempt N`, `--changes`, `--history` flags
2. Update default display to include lineage, attempts summary, outcome, workflow stage
3. Use Rich tables for attempts list
4. Format durations and costs nicely

**Acceptance Criteria**:
- [ ] `cub ledger show <id>` displays all new fields
- [ ] `--attempt N` shows specific attempt with prompt/log paths
- [ ] `--changes` shows task_changed if present
- [ ] `--history` shows state transitions

**Files**: `src/cub/cli/ledger.py`

---

### Task: cub-c5i.2 - Add ledger update command

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, logic

**Context**: Users need to manually transition workflow stages (e.g., mark as validated after review).

**Implementation Steps**:
1. Add `ledger update` command with `--stage` and `--reason` options
2. Validate stage is one of: dev_complete, needs_review, validated, released
3. Call `LedgerWriter.update_workflow_stage()`
4. Append to state_history and display confirmation

**Acceptance Criteria**:
- [ ] `cub ledger update <id> --stage validated` works
- [ ] Invalid stages rejected with error
- [ ] Reason recorded in state_history
- [ ] Confirmation message displayed

**Files**: `src/cub/cli/ledger.py`, `src/cub/core/ledger/writer.py`

---

### Task: cub-c5i.3 - Add ledger export command

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, logic

**Context**: Users need to export ledger data for external analysis or reporting.

**Implementation Steps**:
1. Add `ledger export` command with `--format` (json/csv), `--epic`, `--output` options
2. Use LedgerReader to get entries
3. For JSON: use `json.dumps()` with indent; For CSV: use `csv.DictWriter` with flattened fields
4. Output to file or stdout

**Acceptance Criteria**:
- [ ] `cub ledger export --format json` produces valid JSON
- [ ] `cub ledger export --format csv` produces valid CSV
- [ ] `--epic` filter works
- [ ] `--output` writes to file

**Files**: `src/cub/cli/ledger.py`

---

### Task: cub-c5i.4 - Add ledger gc stub command

Priority: 1
Labels: phase-4, model:haiku, complexity:low, logic

**Context**: Placeholder for future garbage collection/retention policy. For now, just shows what would be deleted.

**Implementation Steps**:
1. Add `ledger gc` command with `--dry-run` (always true for now) and `--keep-latest` options
2. Scan all task directories for attempt files
3. Identify files that would be deleted based on keep_latest
4. Print summary: "Would delete N files, freeing ~X MB"

**Acceptance Criteria**:
- [ ] `cub ledger gc --dry-run` lists files that would be deleted
- [ ] `--keep-latest N` controls retention
- [ ] Summary shows count and estimated size
- [ ] Actual deletion NOT implemented (stub only)

**Files**: `src/cub/cli/ledger.py`

---

### Task: cub-c5i.5 - Add tests for CLI commands

Priority: 1
Labels: phase-4, model:haiku, complexity:low, test

**Context**: Tests ensure all new CLI commands work correctly.

**Implementation Steps**:
1. Create or extend `tests/test_ledger_cli.py`
2. Use Typer's CliRunner for testing
3. Test: show new fields, update stage, export json/csv, gc dry run

**Acceptance Criteria**:
- [ ] All CLI commands tested
- [ ] Error cases tested
- [ ] Output format verified

**Files**: `tests/test_ledger_cli.py`

---

## Epic: cub-d8b - unified-tracking-model #5: Dashboard Integration

Priority: 1
Labels: phase-5, checkpoint

Sync ledger data to dashboard DB for visualization. Ledger entries become visible in dashboard Kanban board.

### Task: cub-d8b.1 - Create LedgerParser

Priority: 1
Labels: phase-5, model:sonnet, complexity:medium, logic
Blocks: cub-d8b.2

**Context**: The dashboard needs a parser to read ledger files and convert them to DashboardEntity objects.

**Implementation Steps**:
1. Create `src/cub/core/dashboard/sync/parsers/ledger.py`
2. Implement `LedgerParser` class with `parse()`, `_compute_stage()`, `_to_dashboard_entity()`, `_compute_checksum()`
3. Read from index.jsonl for fast enumeration
4. Map workflow stages: dev_complete → COMPLETE, needs_review → NEEDS_REVIEW, etc.

**Acceptance Criteria**:
- [ ] LedgerParser follows existing parser pattern
- [ ] Reads from index.jsonl
- [ ] Converts LedgerEntry to DashboardEntity
- [ ] Stage mapping correct
- [ ] Checksum computed for incremental sync

**Files**: `src/cub/core/dashboard/sync/parsers/ledger.py`, `src/cub/core/dashboard/sync/parsers/__init__.py`

---

### Task: cub-d8b.2 - Register parser and update resolver

Priority: 1
Labels: phase-5, model:sonnet, complexity:medium, logic
Blocks: cub-d8b.3

**Context**: The LedgerParser needs to be registered in SyncOrchestrator and relationships need to be resolved.

**Implementation Steps**:
1. Update `src/cub/core/dashboard/sync/orchestrator.py`: import LedgerParser, add to parser list
2. Update `src/cub/core/dashboard/db/models.py`: add TASK_TO_LEDGER to RelationshipType, add LEDGER to EntityType
3. Update `src/cub/core/dashboard/sync/resolver.py`: add ledger relationship resolution, enrich tasks with ledger data

**Acceptance Criteria**:
- [ ] LedgerParser called during sync
- [ ] TASK_TO_LEDGER relationships created
- [ ] Tasks enriched with ledger data
- [ ] `cub dashboard sync` includes ledger entities

**Files**: `src/cub/core/dashboard/sync/orchestrator.py`, `src/cub/core/dashboard/sync/resolver.py`, `src/cub/core/dashboard/db/models.py`

---

### Task: cub-d8b.3 - Add tests for dashboard sync

Priority: 1
Labels: phase-5, model:haiku, complexity:low, test

**Context**: Tests ensure ledger data syncs correctly to dashboard.

**Implementation Steps**:
1. Create `tests/test_ledger_parser.py`
2. Test: parser reads index, stage mapping, entity conversion, checksum computation, sync integration

**Acceptance Criteria**:
- [ ] Parser tests pass
- [ ] Stage mapping verified
- [ ] Integration with sync tested

**Files**: `tests/test_ledger_parser.py`

---

## Epic: cub-x3s - unified-tracking-model #6: Index & Bidirectional Sync

Priority: 2
Labels: phase-6, checkpoint

Fast queries via index and dashboard writeback to ledger. Enables efficient searches and allows dashboard UI to update ledger state.

### Task: cub-x3s.1 - Implement index maintenance

Priority: 2
Labels: phase-6, model:sonnet, complexity:medium, logic
Blocks: cub-x3s.2, cub-x3s.3

**Context**: The index.jsonl file needs to be updated whenever ledger entries are written.

**Implementation Steps**:
1. Update `src/cub/core/ledger/writer.py`: add `_update_index()` private method, call after every write
2. Index entry fields: type, id, title, epic, stage, cost, attempts, updated_at
3. Handle append vs update (read, filter, append, write)
4. Add `rebuild_index()` public method for recovery

**Acceptance Criteria**:
- [ ] Index updated on every write
- [ ] Index format matches spec
- [ ] `rebuild_index()` recovers from scratch
- [ ] Index consistent with entry files

**Files**: `src/cub/core/ledger/writer.py`

---

### Task: cub-x3s.2 - Enhance ledger search with index

Priority: 2
Labels: phase-6, model:sonnet, complexity:medium, logic

**Context**: The ledger search command should use the index for faster queries.

**Implementation Steps**:
1. Update `src/cub/core/ledger/reader.py`: add `_query_index()` method
2. Filter on index fields: stage, cost, epic
3. Update search CLI with `--stage`, `--cost-above`, `--escalated` options
4. Load full entries only for matches

**Acceptance Criteria**:
- [ ] Search queries index first
- [ ] Full entries loaded only for matches
- [ ] Filter options work correctly
- [ ] Search is fast even with many entries

**Files**: `src/cub/core/ledger/reader.py`, `src/cub/cli/ledger.py`

---

### Task: cub-x3s.3 - Implement PATCH API endpoint

Priority: 2
Labels: phase-6, model:sonnet, complexity:medium, api

**Context**: The dashboard needs to update workflow stage via API, which writes back to ledger files.

**Implementation Steps**:
1. Update dashboard API: add PATCH /api/entity/{id} endpoint
2. Accept body: `{"workflow": {"stage": "validated"}, "reason": "..."}`
3. Validate stage value, call `LedgerWriter.update_workflow_stage()`
4. Return updated entity, trigger incremental sync

**Acceptance Criteria**:
- [ ] PATCH /api/entity/{id} updates workflow stage
- [ ] Changes written to ledger file
- [ ] state_history updated with reason
- [ ] Dashboard reflects change after refresh

**Files**: `src/cub/core/dashboard/api/app.py`, `src/cub/core/ledger/writer.py`

---

### Task: cub-x3s.4 - Add tests for index and API

Priority: 2
Labels: phase-6, model:haiku, complexity:low, test

**Context**: Tests ensure index maintenance and API writeback work correctly.

**Implementation Steps**:
1. Add `tests/test_ledger_index.py`: test index update, rebuild, consistency, search uses index
2. Add `tests/test_dashboard_api.py`: test PATCH stage, invalid stage, not found, updates ledger

**Acceptance Criteria**:
- [ ] Index tests pass
- [ ] API tests pass
- [ ] Bidirectional sync verified

**Files**: `tests/test_ledger_index.py`, `tests/test_dashboard_api.py`

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-r4n | 5 | P0 | unified-tracking-model #1: Run Session Infrastructure |
| cub-l7e | 5 | P0 | unified-tracking-model #2: Ledger Entry Lifecycle |
| cub-e2p | 3 | P1 | unified-tracking-model #3: Epic Aggregation |
| cub-c5i | 5 | P1 | unified-tracking-model #4: CLI Commands |
| cub-d8b | 3 | P1 | unified-tracking-model #5: Dashboard Integration |
| cub-x3s | 4 | P2 | unified-tracking-model #6: Index & Bidirectional Sync |

**Total**: 6 epics, 25 tasks

**Dependency Chain**:
```
cub-r4n.1 → cub-r4n.2 → cub-r4n.3 → cub-r4n.5
                     ↘ cub-r4n.4

cub-l7e.1 → cub-l7e.2 → cub-l7e.3 → cub-l7e.4 → cub-l7e.5

cub-e2p.1 → cub-e2p.2 → cub-e2p.3

cub-c5i.1 → cub-c5i.2
         → cub-c5i.3
         → cub-c5i.4 → cub-c5i.5

cub-d8b.1 → cub-d8b.2 → cub-d8b.3

cub-x3s.1 → cub-x3s.2
         → cub-x3s.3 → cub-x3s.4
```

**Critical Path**: cub-r4n.1 → cub-r4n.2 → cub-r4n.3 → cub-l7e.1 → ... → cub-d8b.3

**Ready to Start**: cub-r4n.1 (no dependencies)
