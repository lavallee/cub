# Itemized Plan: Plan Phase Redesign

> Source: [specs/researching/plan-phase-redesign.md](../../specs/researching/plan-phase-redesign.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-20

## Context Summary

This plan implements a redesign of cub's planning pipeline, renaming `prep` → `plan` and `bootstrap` → `stage`, with clearer nomenclature throughout. The implementation is in Python using the Claude Agent SDK for interview orchestration, replacing 1,700+ lines of bash.

Key architectural decisions:
- Plans live in visible `/plans/{slug}/` directories
- `itemized-plan.md` is the single editable source of truth; JSONL generated at stage time
- All 5 spec lifecycle stages are automated (researching → planned → staged → implementing → released)
- Tasks imported via `TaskBackend.import_tasks()` Protocol method (works with Beads and JSON)
- Beads IDs use random suffix format (`cub-k7m`), not sequential

The implementation is split into 4 phases: Foundation, Plan Command, Stage Command, and Polish.

---

## Epic: cub-p1f - Foundation

Priority: 0
Labels: phase-1, foundation

Establish the core infrastructure needed by subsequent phases: TaskBackend extension, spec workflow management, and plan data models.

### Task: cub-p1f.1 - Add import_tasks() to TaskBackend Protocol

Priority: 0
Labels: foundation, backend
Blocks: cub-p1f.2, cub-p1f.3

**Context**: The `TaskBackend` Protocol needs a bulk import method so `cub stage` can import all tasks from a plan efficiently. This is the foundation for both backend implementations.

**Implementation Steps**:
1. Open `src/cub/core/tasks/backend.py`
2. Add `import_tasks(self, tasks: list[Task]) -> list[Task]` to the Protocol
3. Add docstring explaining that backends should implement efficiently (not just loop create_task)
4. Update type hints and ensure mypy passes

**Acceptance Criteria**:
- [ ] `import_tasks()` method exists in `TaskBackend` Protocol
- [ ] Docstring explains bulk import semantics
- [ ] mypy strict passes

**Files**: `src/cub/core/tasks/backend.py`

---

### Task: cub-p1f.2 - Implement import_tasks() in BeadsBackend

Priority: 0
Labels: foundation, backend, beads
Blocks: cub-p3s.2

**Context**: BeadsBackend should use `bd import` for efficient bulk import rather than calling `bd create` N times.

**Implementation Steps**:
1. Open `src/cub/core/tasks/beads.py`
2. Add `import_tasks()` method
3. Write tasks to temporary JSONL file in beads format
4. Call `bd import <tempfile>` via `_run_bd()`
5. Clean up temp file
6. Return the imported tasks

**Acceptance Criteria**:
- [ ] `import_tasks()` implemented in BeadsBackend
- [ ] Uses temp JSONL file + `bd import`
- [ ] Temp file cleaned up even on error
- [ ] Tests pass with mock bd subprocess

**Files**: `src/cub/core/tasks/beads.py`, `tests/test_beads_backend.py`

---

### Task: cub-p1f.3 - Implement import_tasks() in JsonBackend

Priority: 0
Labels: foundation, backend, json
Blocks: cub-p3s.2

**Context**: JsonBackend should load prd.json once, append all tasks, and save once (not N separate load/save cycles).

**Implementation Steps**:
1. Open `src/cub/core/tasks/json.py`
2. Add `import_tasks()` method
3. Load prd.json once
4. Append all tasks to the tasks array
5. Save atomically once
6. Return the imported tasks

**Acceptance Criteria**:
- [ ] `import_tasks()` implemented in JsonBackend
- [ ] Single load/save cycle for efficiency
- [ ] Atomic write preserved
- [ ] Tests pass

**Files**: `src/cub/core/tasks/json.py`, `tests/test_json_backend.py`

---

### Task: cub-p1f.4 - Create SpecWorkflow class

Priority: 0
Labels: foundation, specs
Blocks: cub-p2p.5, cub-p3s.3

**Context**: Need a class to manage spec lifecycle: finding specs across stage directories and moving them via git mv.

**Implementation Steps**:
1. Create `src/cub/core/specs/__init__.py`
2. Create `src/cub/core/specs/workflow.py`
3. Implement `SpecWorkflow` class with:
   - `STAGES` constant listing all 5 stages
   - `find_spec(filename)` → searches all stage dirs
   - `move_spec(filename, to_stage)` → git mv to new location
4. Handle edge cases: spec not found, already in target stage, non-git directory
5. Add tests

**Acceptance Criteria**:
- [ ] `SpecWorkflow` class exists
- [ ] `find_spec()` searches all 5 stage directories
- [ ] `move_spec()` uses `git mv`
- [ ] Handles non-git directories gracefully (error or fallback)
- [ ] Tests cover happy path and edge cases

**Files**: `src/cub/core/specs/__init__.py`, `src/cub/core/specs/workflow.py`, `tests/test_spec_workflow.py`

---

### Task: cub-p1f.5 - Create plan data models

Priority: 0
Labels: foundation, models
Blocks: cub-p2p.1

**Context**: Need Pydantic models for Plan, PlanStage, PlanStatus, and SpecStage to manage plan state.

**Implementation Steps**:
1. Create `src/cub/core/plan/__init__.py`
2. Create `src/cub/core/plan/models.py`
3. Implement enums: `PlanStage`, `StageStatus`, `PlanStatus`, `SpecStage`
4. Implement `Plan` model with:
   - Fields: slug, created, updated, status, spec_file, stages, project
   - `load(plan_dir)` class method
   - `save(plan_dir)` method
   - `next_incomplete_stage()` helper
5. Add tests

**Acceptance Criteria**:
- [ ] All enums defined
- [ ] `Plan` model with load/save functionality
- [ ] plan.json round-trips correctly
- [ ] mypy strict passes
- [ ] Tests pass

**Files**: `src/cub/core/plan/__init__.py`, `src/cub/core/plan/models.py`, `tests/test_plan_models.py`

---

### Task: cub-p1f.6 - Create ID generation utilities

Priority: 1
Labels: foundation, utils
Blocks: cub-p2p.4

**Context**: Need utilities to generate beads-compatible IDs with random suffixes (not sequential).

**Implementation Steps**:
1. Create `src/cub/core/plan/ids.py`
2. Implement `generate_epic_id(project, existing_ids=None)` → `{project}-{random 3 chars}`
3. Implement `generate_task_id(epic_id, task_num)` → `{epic_id}.{num}`
4. Implement `generate_subtask_id(task_id, subtask_num)` → `{task_id}.{num}`
5. Use `secrets.choice()` for randomness
6. Add collision detection if `existing_ids` provided
7. Add tests

**Acceptance Criteria**:
- [ ] `generate_epic_id()` produces format `cub-k7m`
- [ ] Uses cryptographic randomness
- [ ] Collision detection works when existing_ids provided
- [ ] Tests verify format and uniqueness

**Files**: `src/cub/core/plan/ids.py`, `tests/test_plan_ids.py`

---

## Epic: cub-p2p - Plan Command

Priority: 1
Labels: phase-2, cli

Implement the `cub plan` command with orient, architect, and itemize subcommands using Claude SDK for interview orchestration.

### Task: cub-p2p.1 - Create cub plan CLI skeleton

Priority: 0
Labels: cli, plan
Blocks: cub-p2p.2, cub-p2p.3, cub-p2p.4

**Context**: Need the Typer CLI structure for `cub plan` with subcommands.

**Implementation Steps**:
1. Create `src/cub/cli/plan.py`
2. Create Typer app with subcommands: `orient`, `architect`, `itemize`
3. Add main `plan` command that runs full pipeline
4. Add common options: `--slug`, `--continue`
5. Register in `src/cub/cli/__init__.py`
6. Stub implementations that print "not implemented"

**Acceptance Criteria**:
- [ ] `cub plan --help` shows subcommands
- [ ] `cub plan orient --help` works
- [ ] `cub plan architect --help` works
- [ ] `cub plan itemize --help` works
- [ ] Commands registered in main CLI

**Files**: `src/cub/cli/plan.py`, `src/cub/cli/__init__.py`

---

### Task: cub-p2p.2 - Implement orient stage

Priority: 0
Labels: cli, plan, orient
Blocks: cub-p2p.3

**Context**: Orient is the first interview stage - gathering requirements and understanding the problem space.

**Implementation Steps**:
1. Create `src/cub/core/plan/orient.py`
2. Create `src/cub/core/plan/context.py` for context gathering
3. Implement `gather_context()` - reads spec, CLAUDE.md, SYSTEM-PLAN.md, existing plans
4. Implement `build_orient_prompt()` - constructs prompt with context
5. Implement `run_orient()` - calls SDK, streams output, handles user confirmation
6. Implement `write_orientation_md()` - writes output file
7. Wire into CLI subcommand
8. Add tests with mock SDK

**Acceptance Criteria**:
- [ ] `cub plan orient spec.md` runs interview
- [ ] Context gathered from codebase
- [ ] Assumptions presented for user review
- [ ] `orientation.md` written to plan directory
- [ ] plan.json updated with stage status

**Files**: `src/cub/core/plan/orient.py`, `src/cub/core/plan/context.py`, `src/cub/cli/plan.py`

---

### Task: cub-p2p.3 - Implement architect stage

Priority: 0
Labels: cli, plan, architect
Blocks: cub-p2p.4

**Context**: Architect stage designs the technical approach based on orientation.

**Implementation Steps**:
1. Create `src/cub/core/plan/architect.py`
2. Implement `build_architect_prompt()` - includes orientation.md content
3. Implement `run_architect()` - calls SDK, streams output, handles user confirmation
4. Implement `write_architecture_md()` - writes output file
5. Wire into CLI subcommand
6. Add tests with mock SDK

**Acceptance Criteria**:
- [ ] `cub plan architect plans/foo` runs interview
- [ ] Reads orientation.md as input
- [ ] Assumptions presented for user review
- [ ] `architecture.md` written to plan directory
- [ ] plan.json updated with stage status

**Files**: `src/cub/core/plan/architect.py`, `src/cub/cli/plan.py`

---

### Task: cub-p2p.4 - Implement itemize stage

Priority: 0
Labels: cli, plan, itemize
Blocks: cub-p3s.1

**Context**: Itemize stage breaks architecture into discrete tasks with proper beads IDs.

**Implementation Steps**:
1. Create `src/cub/core/plan/itemize.py`
2. Implement `build_itemize_prompt()` - includes orientation.md and architecture.md
3. Implement `run_itemize()` - calls SDK, generates IDs, streams output
4. Use `generate_epic_id()` and `generate_task_id()` for ID generation
5. Implement `write_itemized_plan_md()` - writes output file
6. Wire into CLI subcommand
7. Add tests with mock SDK

**Acceptance Criteria**:
- [ ] `cub plan itemize plans/foo` runs interview
- [ ] Reads orientation.md and architecture.md as input
- [ ] Generates proper beads IDs (random suffix, not sequential)
- [ ] `itemized-plan.md` written with correct format
- [ ] plan.json updated with stage status

**Files**: `src/cub/core/plan/itemize.py`, `src/cub/cli/plan.py`

---

### Task: cub-p2p.5 - Implement pipeline orchestration

Priority: 0
Labels: cli, plan, pipeline
Blocks: cub-p3s.1

**Context**: Full `cub plan` command should run all three stages in sequence with spec lifecycle management.

**Implementation Steps**:
1. Create `src/cub/core/plan/pipeline.py`
2. Implement `run_plan_pipeline()`:
   - Determine/create plan directory (handle slug collisions with `_alt_[a-z]`)
   - Load or create Plan model
   - Run orient → architect → itemize in sequence
   - Move spec from researching/ → planned/
3. Implement `resolve_plan_dir()` for slug collision handling
4. Wire main `cub plan` command to pipeline
5. Add integration tests

**Acceptance Criteria**:
- [ ] `cub plan spec.md` runs full pipeline
- [ ] Handles slug collisions with `_alt_a`, `_alt_b`, etc.
- [ ] Spec moved to `planned/` directory after completion
- [ ] Can resume from any stage with `--continue`
- [ ] plan.json reflects final state

**Files**: `src/cub/core/plan/pipeline.py`, `src/cub/cli/plan.py`

---

## Epic: cub-p3s - Stage Command

Priority: 2
Labels: phase-3, cli

Implement the `cub stage` command that parses itemized-plan.md and imports tasks via TaskBackend.

### Task: cub-p3s.1 - Create itemized-plan.md parser

Priority: 0
Labels: stage, parser
Blocks: cub-p3s.2

**Context**: Need to parse the markdown format of itemized-plan.md into Task objects.

**Implementation Steps**:
1. Create `src/cub/core/plan/parser.py`
2. Implement `parse_itemized_plan(path) -> list[Task]`:
   - Parse epic headers (`## Epic: cub-xxx - Title`)
   - Parse task headers (`### Task: cub-xxx.n - Title`)
   - Extract Priority, Labels, Blocks fields
   - Extract description from body
   - Handle acceptance criteria as checklist
3. Use regex or simple line-by-line parsing (not full markdown AST)
4. Add comprehensive tests with edge cases

**Acceptance Criteria**:
- [ ] Parses epics and tasks from markdown
- [ ] Extracts all metadata (priority, labels, blocks)
- [ ] Handles multi-line descriptions
- [ ] Returns list of Task objects
- [ ] Tests cover format variations

**Files**: `src/cub/core/plan/parser.py`, `tests/test_plan_parser.py`

---

### Task: cub-p3s.2 - Implement cub stage command

Priority: 0
Labels: cli, stage
Blocks: cub-p3s.3

**Context**: `cub stage` is the bridge between planning and execution - it imports tasks to the task backend.

**Implementation Steps**:
1. Create `src/cub/cli/stage.py`
2. Create `src/cub/core/stage/__init__.py`
3. Create `src/cub/core/stage/stager.py`
4. Implement `run_stage(plan_dir)`:
   - Validate plan completeness (all 3 stages done)
   - Parse itemized-plan.md → Task objects
   - Call `TaskBackend.import_tasks()`
   - Update plan.json status to "staged"
5. Add `--dry-run` option to preview without importing
6. Add `--prefix` option for ID prefix override
7. Register command in CLI
8. Add tests

**Acceptance Criteria**:
- [ ] `cub stage plans/foo` imports tasks
- [ ] Works with both BeadsBackend and JsonBackend
- [ ] `--dry-run` shows what would be imported
- [ ] plan.json updated to status "staged"
- [ ] Validates plan completeness before staging

**Files**: `src/cub/cli/stage.py`, `src/cub/core/stage/stager.py`

---

### Task: cub-p3s.3 - Wire spec lifecycle transitions

Priority: 0
Labels: stage, specs
Blocks: cub-p4x.1

**Context**: Spec should automatically move through lifecycle stages at appropriate triggers.

**Implementation Steps**:
1. Update `cub stage` to move spec: `planned/` → `staged/`
2. Update `cub run` (in existing code) to move spec: `staged/` → `implementing/` on first task start
3. Add hook point in `scripts/cut-release.sh` to move spec: `implementing/` → `released/`
4. Use `SpecWorkflow.move_spec()` for all transitions
5. Add tests for each transition

**Acceptance Criteria**:
- [ ] `cub stage` moves spec to `staged/`
- [ ] `cub run` moves spec to `implementing/` (on first task)
- [ ] `scripts/cut-release.sh` has hook for `released/` transition
- [ ] All transitions use git mv
- [ ] Tests verify transitions

**Files**: `src/cub/cli/stage.py`, `src/cub/cli/run.py`, `scripts/cut-release.sh`

---

## Epic: cub-p4x - Polish

Priority: 3
Labels: phase-4, polish

Final polish: deprecation warnings, documentation, error handling, test coverage.

### Task: cub-p4x.1 - Add deprecation warnings to old commands

Priority: 1
Labels: polish, cli
Blocks: cub-p4x.2

**Context**: Old commands (prep, triage, bootstrap) should warn and point to new commands.

**Implementation Steps**:
1. Update `src/cub/cli/delegated.py` for prep-related commands
2. Add deprecation warnings that print:
   - `cub prep` → "Deprecated. Use `cub plan` instead."
   - `cub triage` → "Deprecated. Use `cub plan orient` instead."
   - `cub bootstrap` → "Deprecated. Use `cub stage` instead."
3. Commands should still work (delegate to bash) but warn
4. Add tests for warning output

**Acceptance Criteria**:
- [ ] `cub prep` shows deprecation warning
- [ ] `cub triage` shows deprecation warning
- [ ] `cub bootstrap` shows deprecation warning
- [ ] Warnings point to correct new commands
- [ ] Old commands still function (for transition period)

**Files**: `src/cub/cli/delegated.py`

---

### Task: cub-p4x.2 - Update documentation

Priority: 1
Labels: polish, docs
Blocks: cub-p4x.3

**Context**: All documentation needs to reflect new command names and workflow.

**Implementation Steps**:
1. Update `README.md` with new workflow
2. Update `CLAUDE.md` with new commands
3. Update `UPGRADING.md` with migration guide
4. Update `CHANGELOG.md` with breaking changes
5. Rename `docs-src/content/guide/prep-pipeline/` → `plan-pipeline/`
6. Rename/update all files in that directory
7. Update `mkdocs.yml` navigation
8. Rebuild docs site

**Acceptance Criteria**:
- [ ] README reflects new commands
- [ ] CLAUDE.md updated
- [ ] UPGRADING.md has migration guide
- [ ] docs-src files renamed and updated
- [ ] mkdocs build succeeds
- [ ] No references to old command names in docs

**Files**: `README.md`, `CLAUDE.md`, `UPGRADING.md`, `CHANGELOG.md`, `docs-src/`

---

### Task: cub-p4x.3 - Rename skill files

Priority: 1
Labels: polish, skills

**Context**: Claude Code skill files need to be renamed to match new command names.

**Implementation Steps**:
1. `git mv .claude/commands/cub:triage.md .claude/commands/cub:orient.md`
2. `git mv .claude/commands/cub:plan.md .claude/commands/cub:itemize.md`
3. Update content in `cub:orient.md` (references, output filename)
4. Update content in `cub:itemize.md` (references, output filename)
5. Update content in `cub:architect.md` (output filename → architecture.md)
6. Update `cub:spec-to-issues.md` if it references old pipeline

**Acceptance Criteria**:
- [ ] Skill files renamed
- [ ] Content updated to match new nomenclature
- [ ] Output filenames correct (orientation.md, architecture.md, itemized-plan.md)
- [ ] Skills work when invoked

**Files**: `.claude/commands/cub:orient.md`, `.claude/commands/cub:itemize.md`, `.claude/commands/cub:architect.md`

---

### Task: cub-p4x.4 - Error handling and edge cases

Priority: 2
Labels: polish, robustness

**Context**: Ensure graceful handling of edge cases throughout the pipeline.

**Implementation Steps**:
1. Handle non-git directories (spec workflow falls back or errors clearly)
2. Handle missing plan stages (clear error: "Run orient first")
3. Handle SDK connection failures (retry or clear error)
4. Handle malformed itemized-plan.md (parser gives line numbers)
5. Handle TaskBackend import failures (rollback or partial import)
6. Add integration tests for error scenarios

**Acceptance Criteria**:
- [ ] All error cases produce clear, actionable messages
- [ ] No stack traces for expected errors
- [ ] Partial state is recoverable where possible
- [ ] Tests cover error scenarios

**Files**: Various - `src/cub/core/plan/`, `src/cub/core/stage/`

---

### Task: cub-p4x.5 - Test coverage

Priority: 2
Labels: polish, testing

**Context**: Ensure adequate test coverage for all new code.

**Implementation Steps**:
1. Check coverage report for new modules
2. Add missing unit tests
3. Add integration tests for full pipeline
4. Add tests for both backends
5. Target: 60%+ coverage for new code (Moderate tier per STABILITY.md)

**Acceptance Criteria**:
- [ ] All new modules have unit tests
- [ ] Integration test for full `cub plan` → `cub stage` flow
- [ ] Both BeadsBackend and JsonBackend tested
- [ ] Coverage meets Moderate tier threshold
- [ ] CI passes

**Files**: `tests/`

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-p1f | 6 | P0 | Foundation: backend, specs, models |
| cub-p2p | 5 | P1 | Plan command with interview stages |
| cub-p3s | 3 | P2 | Stage command and spec lifecycle |
| cub-p4x | 5 | P3 | Polish: deprecation, docs, testing |

**Total**: 4 epics, 19 tasks

**Dependency chain**:
```
cub-p1f.1 ─┬─▶ cub-p1f.2 ─┐
           └─▶ cub-p1f.3 ─┼─▶ cub-p3s.2
cub-p1f.4 ────────────────┼─▶ cub-p3s.3
cub-p1f.5 ─▶ cub-p2p.1 ───┼─▶ cub-p2p.2 ─▶ cub-p2p.3 ─▶ cub-p2p.4 ─┐
cub-p1f.6 ────────────────┼───────────────────────────▶ cub-p2p.4 ─┤
                          │                                         │
                          └─────────────────────────────────────────┴─▶ cub-p2p.5 ─▶ cub-p3s.1
                                                                                          │
cub-p3s.1 ─▶ cub-p3s.2 ─▶ cub-p3s.3 ─▶ cub-p4x.1 ─▶ cub-p4x.2 ─▶ cub-p4x.3              │
                                                                                          │
cub-p4x.4 (parallel)                                                                      │
cub-p4x.5 (parallel, after all implementation)                                            │
```
