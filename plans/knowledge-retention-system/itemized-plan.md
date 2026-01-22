# Itemized Plan: Knowledge Retention System

> Source: [specs/researching/knowledge-retention-system.md](../../specs/researching/knowledge-retention-system.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-22

## Context Summary

Cub needs a post-task memory system that bridges the gap between in-progress work (beads) and permanent record (git commits). This system will capture task intent, execution trace, and outcomes—serving both human auditing needs (cost visibility, drift detection) and agent context recovery.

**Mindset:** Production | **Scale:** Team

---

## Epic: cub-r7k - Token Persistence

Priority: 0
Labels: phase-1, token-persistence, foundation

Persist token/cost data that currently exists only in-memory during runs. Deliverables: Token data persisted in `.cub/runs/` artifacts, `cub status` shows accurate cost even after run completes, audit trail for prompt debugging (harness.log, prompt.md).

### Task: cub-r7k.1 - Extend task.json schema to include TokenUsage

Priority: 0
Labels: epic:cub-r7k, phase-1, model:sonnet, complexity:low

**Context**: Currently TokenUsage is extracted during runs but not persisted to task artifacts. This task adds the usage field to task.json so cost data survives after runs complete.

**Implementation Steps**:
1. Read `src/cub/core/status/models.py` to understand current TaskArtifact structure
2. Add `usage: TokenUsage | None = None` field to TaskArtifact model
3. Add `duration_seconds: float | None = None` field
4. Add `iterations: int = 0` field if not present
5. Update any Pydantic model_config for JSON serialization
6. Write unit tests for the extended model

**Acceptance Criteria**:
- [ ] TaskArtifact model includes usage: TokenUsage | None field
- [ ] TaskArtifact model includes duration_seconds field
- [ ] Model serializes correctly to JSON (test with model_dump_json)
- [ ] Unit tests pass for new fields

**Files**: src/cub/core/status/models.py, src/cub/core/harness/models.py, tests/test_status_models.py

---

### Task: cub-r7k.2 - Extend run.json schema to include budget totals

Priority: 0
Labels: epic:cub-r7k, phase-1, model:sonnet, complexity:low

**Context**: run.json currently has minimal metadata. We need to add budget totals so aggregate cost is visible after runs complete.

**Implementation Steps**:
1. Read `src/cub/core/status/models.py` to understand RunArtifact structure
2. Add `budget: BudgetStatus | None = None` field to RunArtifact
3. Add `completed_at: datetime | None = None` field
4. Add `tasks_completed: int = 0` field
5. Ensure BudgetStatus is imported from correct location
6. Write unit tests

**Acceptance Criteria**:
- [ ] RunArtifact model includes budget: BudgetStatus | None
- [ ] RunArtifact includes completed_at timestamp
- [ ] Model serializes correctly to JSON
- [ ] Unit tests pass

**Files**: src/cub/core/status/models.py, tests/test_status_models.py

---

### Task: cub-r7k.3 - Persist TokenUsage to task.json in run loop

Priority: 0
Labels: epic:cub-r7k, phase-1, model:sonnet, complexity:medium
Blocks: cub-r7k.5, cub-r7k.6, cub-r7k.7

**Context**: With models extended, we need to actually write the token data during task execution. The run loop in cli/run.py handles task execution and should persist usage after each task.

**Implementation Steps**:
1. Read `src/cub/cli/run.py` to find task completion handling (~line 1200+)
2. Read `src/cub/core/status/writer.py` to understand current persistence
3. After harness invocation returns TaskResult, extract TokenUsage
4. Update TaskArtifact with usage data
5. Call StatusWriter to persist updated task.json
6. Add integration test with mock harness

**Acceptance Criteria**:
- [ ] After task completion, task.json contains usage field with token counts
- [ ] Cost (cost_usd) is included if available
- [ ] Duration and iterations are recorded
- [ ] Works with all harness backends (claude, codex, etc.)
- [ ] Integration test verifies persistence

**Files**: src/cub/cli/run.py, src/cub/core/status/writer.py, tests/test_run_integration.py

---

### Task: cub-r7k.4 - Persist budget totals to run.json at run completion

Priority: 0
Labels: epic:cub-r7k, phase-1, model:sonnet, complexity:medium

**Context**: Aggregate token/cost totals should be written to run.json when a cub run session completes.

**Implementation Steps**:
1. Find run completion in cli/run.py (look for exit conditions, cleanup)
2. Aggregate BudgetStatus from tracked data
3. Update RunArtifact with budget and completed_at
4. Persist via StatusWriter
5. Handle both normal completion and early exit (budget exceeded, error)
6. Add test for run completion persistence

**Acceptance Criteria**:
- [ ] run.json contains budget field with totals after run completes
- [ ] completed_at timestamp is set
- [ ] Works for normal completion, budget exceeded, and error exits
- [ ] Test verifies persistence

**Files**: src/cub/cli/run.py, src/cub/core/status/writer.py, tests/test_run_integration.py

---

### Task: cub-r7k.5 - Capture harness.log for raw output audit trail

Priority: 1
Labels: epic:cub-r7k, phase-1, model:sonnet, complexity:medium

**Context**: Raw harness output is valuable for debugging and enables LLM extraction of approach/decisions in Phase 2. Currently not captured.

**Implementation Steps**:
1. Determine where harness output is currently handled in run.py
2. Create file path: `.cub/runs/{session}/tasks/{task-id}/harness.log`
3. Capture both stdout and stderr from harness subprocess
4. Write to harness.log during or after execution
5. Handle streaming mode (output goes to console AND file)
6. Test with both streaming and non-streaming modes

**Acceptance Criteria**:
- [ ] harness.log created in task directory after execution
- [ ] Contains complete stdout/stderr from harness
- [ ] Works in both streaming and non-streaming modes
- [ ] Large outputs handled correctly (don't run out of memory)
- [ ] Test verifies log creation and content

**Files**: src/cub/cli/run.py, src/cub/core/harness/

---

### Task: cub-r7k.6 - Capture prompt.md for rendered prompt audit trail

Priority: 1
Labels: epic:cub-r7k, phase-1, model:haiku, complexity:low

**Context**: The rendered prompt (system + task) is valuable for debugging prompt issues. Save it alongside harness.log.

**Implementation Steps**:
1. Find where prompts are assembled in run.py (system prompt + task prompt)
2. Create file path: `.cub/runs/{session}/tasks/{task-id}/prompt.md`
3. Write prompt with clear sections (## System Prompt, ## Task Prompt)
4. Do this before harness invocation (so prompt is saved even if harness fails)
5. Test prompt capture

**Acceptance Criteria**:
- [ ] prompt.md created in task directory before harness invocation
- [ ] Contains both system prompt and task prompt with clear headers
- [ ] Saved even if harness invocation fails
- [ ] Test verifies content structure

**Files**: src/cub/cli/run.py

---

### Task: cub-r7k.7 - Update cub status to display cost from persisted data

Priority: 1
Labels: epic:cub-r7k, phase-1, model:sonnet, complexity:medium, checkpoint

**Context**: cub status currently shows cost from in-memory data during active runs. It should also display cost from persisted run.json/task.json for completed runs.

**Implementation Steps**:
1. Read `src/cub/cli/status.py` to understand current display logic
2. Load run.json and task.json files from .cub/runs/
3. Display cost breakdown: total, per-task, per-model if available
4. Handle case where run is active (use in-memory) vs completed (use persisted)
5. Add --session flag to view specific historical run
6. Test display output

**Acceptance Criteria**:
- [ ] cub status shows cost for completed runs from persisted data
- [ ] Shows per-task cost breakdown
- [ ] Works for both active and completed runs
- [ ] --session flag allows viewing historical runs
- [ ] Test verifies output format

**Files**: src/cub/cli/status.py, src/cub/core/status/models.py

---

## Epic: cub-m4j - Ledger Core

Priority: 1
Labels: phase-2, ledger, core

Create the completed work ledger with entries and queries. Deliverables: `.cub/ledger/` directory structure populated on task completion, `cub ledger show/stats/search` commands working, LLM-extracted insights in entries, JSONL index for fast queries.

### Task: cub-m4j.1 - Create ledger package structure and Pydantic models

Priority: 0
Labels: epic:cub-m4j, phase-2, model:sonnet, complexity:medium

**Context**: The ledger service needs a clean package structure with well-defined Pydantic models. This is the foundation for all ledger functionality.

**Implementation Steps**:
1. Create `src/cub/core/ledger/` directory
2. Create `__init__.py` with public exports
3. Create `models.py` with LedgerEntry, LedgerIndex, CommitRef, EpicSummary, VerificationStatus, LedgerStats
4. Add Field() descriptions and validators
5. Write comprehensive tests for serialization

**Acceptance Criteria**:
- [ ] Package structure created: ledger/__init__.py, models.py
- [ ] LedgerEntry model has all fields from architecture doc
- [ ] LedgerIndex model defined for JSONL index
- [ ] Models serialize to JSON correctly
- [ ] Tests cover all models

**Files**: src/cub/core/ledger/__init__.py, src/cub/core/ledger/models.py, tests/test_ledger_models.py

---

### Task: cub-m4j.2 - Implement LedgerWriter for creating entries

Priority: 0
Labels: epic:cub-m4j, phase-2, model:sonnet, complexity:medium
Blocks: cub-m4j.3, cub-m4j.5, cub-m4j.6, cub-w9t.4, cub-w9t.7, cub-h3v.1

**Context**: LedgerWriter creates and updates ledger entries. It writes both the markdown file (human-readable) and updates the JSONL index.

**Implementation Steps**:
1. Read `src/cub/core/captures/store.py` for file storage pattern
2. Create `src/cub/core/ledger/writer.py`
3. Implement `create_entry(task, result, run_dir) -> LedgerEntry`
4. Implement `update_entry(entry) -> LedgerEntry` for updates
5. Implement `_append_to_index(entry)` helper
6. Handle directory creation if not exists
7. Write tests with tmp_path fixture

**Acceptance Criteria**:
- [ ] create_entry produces markdown file with frontmatter
- [ ] Entry written to .cub/ledger/by-task/{id}.md
- [ ] index.jsonl updated with compact entry
- [ ] update_entry works for modifications
- [ ] Tests verify file contents

**Files**: src/cub/core/ledger/writer.py, tests/test_ledger_writer.py

---

### Task: cub-m4j.3 - Implement LedgerReader for queries and search

Priority: 0
Labels: epic:cub-m4j, phase-2, model:sonnet, complexity:medium
Blocks: cub-m4j.4, cub-w9t.3, cub-w9t.4

**Context**: LedgerReader provides query capabilities: get single entry, list with filters, search by text, and compute stats.

**Implementation Steps**:
1. Create `src/cub/core/ledger/reader.py`
2. Implement `get_entry(task_id) -> LedgerEntry | None`
3. Implement `list_entries(since, epic_id) -> list[LedgerEntry]`
4. Implement `search(query) -> list[LedgerEntry]`
5. Implement `stats(since, epic_id) -> LedgerStats`
6. Write tests

**Acceptance Criteria**:
- [ ] get_entry returns full LedgerEntry from markdown
- [ ] list_entries filters by date and epic
- [ ] search finds entries by text
- [ ] stats returns correct aggregates
- [ ] Empty ledger returns empty results, not errors

**Files**: src/cub/core/ledger/reader.py, tests/test_ledger_reader.py

---

### Task: cub-m4j.4 - Implement cub ledger CLI commands (show, stats, search)

Priority: 0
Labels: epic:cub-m4j, phase-2, model:sonnet, complexity:medium, checkpoint

**Context**: CLI is prioritized early for manual testing. Implement the three core commands: show, stats, search.

**Implementation Steps**:
1. Create `src/cub/cli/ledger.py`
2. Create Typer app with commands: show, stats, search
3. Add `--json` flag to all commands
4. Add `--since` and `--epic` flags to stats
5. Register in `src/cub/cli/__init__.py`
6. Manual test all commands

**Acceptance Criteria**:
- [ ] cub ledger show <id> displays rich formatted entry
- [ ] cub ledger show <id> --json outputs JSON
- [ ] cub ledger stats shows totals and averages
- [ ] cub ledger search <q> finds matching entries
- [ ] Commands registered and appear in cub --help

**Files**: src/cub/cli/ledger.py, src/cub/cli/__init__.py

---

### Task: cub-m4j.5 - Implement LLM extraction for approach/decisions/lessons

Priority: 1
Labels: epic:cub-m4j, phase-2, model:opus, complexity:high, risk:medium
Blocks: cub-m4j.6

**Context**: Ledger entries should include LLM-extracted insights: approach taken, key decisions, and lessons learned. This uses the existing harness interface.

**Implementation Steps**:
1. Create `src/cub/core/ledger/extractor.py`
2. Implement `extract_insights(harness_log: str, task: Task) -> InsightExtraction`
3. Create prompt template for extraction
4. Use haiku model for cost efficiency
5. Handle extraction failure gracefully
6. Test with sample harness logs

**Acceptance Criteria**:
- [ ] InsightExtraction model defined
- [ ] Prompt template produces consistent results
- [ ] Uses haiku model for cost efficiency
- [ ] Extraction failures return empty insights, not errors
- [ ] Integrated into create_entry flow

**Files**: src/cub/core/ledger/extractor.py, tests/test_ledger_extractor.py

---

### Task: cub-m4j.6 - Wire ledger creation into run loop on task close

Priority: 1
Labels: epic:cub-m4j, phase-2, model:sonnet, complexity:medium, checkpoint

**Context**: Ledger entries should be created automatically when a task closes. This wires the ledger into the main execution flow.

**Implementation Steps**:
1. Find task close handling in `src/cub/cli/run.py`
2. After successful task completion, call LedgerWriter.create_entry()
3. Handle errors gracefully (log, don't fail run)
4. Add configuration option to disable ledger creation
5. Integration test

**Acceptance Criteria**:
- [ ] Ledger entry created automatically on task close
- [ ] Entry includes all available data (cost, files, commits)
- [ ] Ledger creation errors don't crash the run
- [ ] Configuration option to disable
- [ ] Integration test verifies full flow

**Files**: src/cub/cli/run.py, src/cub/core/ledger/writer.py, tests/test_run_integration.py

---

## Epic: cub-w9t - Context & Drift

Priority: 2
Labels: phase-3, context, drift-detection

Add context generation and drift detection. Deliverables: llms.txt generated from CLAUDE.md + activity, codebase-map.md using tree-sitter AST parsing, cub ledger drift command working, Git post-commit hook installed on cub init.

### Task: cub-w9t.1 - Add tree-sitter dependencies and basic setup

Priority: 0
Labels: epic:cub-w9t, phase-3, model:haiku, complexity:low
Blocks: cub-w9t.2

**Context**: Tree-sitter provides AST parsing for accurate codebase structure mapping. Need to add dependencies and verify installation.

**Implementation Steps**:
1. Add to pyproject.toml: tree-sitter, tree-sitter-python, tree-sitter-javascript
2. Run `uv sync` to install
3. Write quick test script to verify parsing works
4. Document any platform-specific installation notes

**Acceptance Criteria**:
- [ ] Dependencies added to pyproject.toml
- [ ] uv sync succeeds
- [ ] Basic parsing test passes
- [ ] Works on macOS and Linux

**Files**: pyproject.toml

---

### Task: cub-w9t.2 - Implement CodebaseMapper with tree-sitter

Priority: 1
Labels: epic:cub-w9t, phase-3, model:sonnet, complexity:high
Blocks: cub-w9t.6

**Context**: CodebaseMapper uses tree-sitter to extract structure, entry points, and key patterns from the codebase. Outputs codebase-map.md.

**Implementation Steps**:
1. Create `src/cub/core/context/codebase_map.py`
2. Implement tree-sitter parsing for Python
3. Extract class and function definitions
4. Generate structured markdown
5. Write to `.cub/codebase-map.md`
6. Test with cub's own codebase

**Acceptance Criteria**:
- [ ] Parses Python files with tree-sitter
- [ ] Generates codebase-map.md with structure
- [ ] Includes entry points and key definitions
- [ ] Graceful fallback for parse errors

**Files**: src/cub/core/context/codebase_map.py, tests/test_codebase_map.py

---

### Task: cub-w9t.3 - Implement LlmsTxtGenerator for llms.txt

Priority: 1
Labels: epic:cub-w9t, phase-3, model:sonnet, complexity:medium
Blocks: cub-w9t.6

**Context**: llms.txt follows the llmstxt.org convention - an LLM-friendly project overview. Generate from CLAUDE.md template plus recent activity.

**Implementation Steps**:
1. Create `src/cub/core/context/llms_txt.py`
2. Define llms.txt template structure
3. Implement `generate_llms_txt() -> Path`
4. Handle missing CLAUDE.md gracefully
5. Test generation

**Acceptance Criteria**:
- [ ] Generates llms.txt from CLAUDE.md template
- [ ] Includes recent activity from ledger
- [ ] Follows llmstxt.org convention
- [ ] Handles missing CLAUDE.md

**Files**: src/cub/core/context/llms_txt.py, tests/test_llms_txt.py

---

### Task: cub-w9t.4 - Implement drift detection via harness

Priority: 0
Labels: epic:cub-w9t, phase-3, model:opus, complexity:high, risk:medium, experiment
Blocks: cub-w9t.5

**Context**: Drift detection compares specs to ledger entries using LLM-assisted semantic comparison. This is the primary success criteria from orient.

**Implementation Steps**:
1. Create `src/cub/core/ledger/drift.py`
2. Implement `parse_spec_requirements(spec_path) -> list[str]`
3. Implement `compare_spec_to_ledger(spec_path, ledger_entries) -> DriftReport`
4. Define DriftReport model
5. Handle: implemented, diverged (documented), diverged (undocumented), not implemented
6. Test with real spec/ledger pairs

**Acceptance Criteria**:
- [ ] Extracts requirements from spec markdown
- [ ] LLM comparison classifies each requirement
- [ ] DriftReport contains all categories
- [ ] Works with real cub specs and ledger

**Files**: src/cub/core/ledger/drift.py, src/cub/core/ledger/models.py, tests/test_drift.py

---

### Task: cub-w9t.5 - Implement cub ledger drift command

Priority: 1
Labels: epic:cub-w9t, phase-3, model:sonnet, complexity:medium, checkpoint

**Context**: CLI command for running drift detection. Takes a spec path and outputs comparison report.

**Implementation Steps**:
1. Add `drift` command to `src/cub/cli/ledger.py`
2. Accept spec path as argument
3. Find related ledger entries
4. Call drift detector
5. Format DriftReport with Rich
6. Add --json flag

**Acceptance Criteria**:
- [ ] cub ledger drift <spec> works
- [ ] Output uses colors to indicate status
- [ ] Shows action items for undocumented divergences
- [ ] --json outputs structured data

**Files**: src/cub/cli/ledger.py

---

### Task: cub-w9t.6 - Implement cub context CLI commands

Priority: 1
Labels: epic:cub-w9t, phase-3, model:haiku, complexity:low
Blocks: cub-w9t.8, cub-h3v.3

**Context**: CLI for generating and viewing context files (llms.txt, codebase-map.md).

**Implementation Steps**:
1. Create `src/cub/cli/context.py`
2. Create Typer app with commands: generate, show
3. Add flags for specific file generation
4. Register in `src/cub/cli/__init__.py`
5. Test commands

**Acceptance Criteria**:
- [ ] cub context generate creates both files
- [ ] Flags allow generating specific files
- [ ] cub context show displays contents
- [ ] Commands registered in help

**Files**: src/cub/cli/context.py, src/cub/cli/__init__.py

---

### Task: cub-w9t.7 - Implement git post-commit hook installer

Priority: 2
Labels: epic:cub-w9t, phase-3, model:sonnet, complexity:medium

**Context**: Git hooks capture commits to ledger even when agents bypass cub run. Install post-commit hook on cub init.

**Implementation Steps**:
1. Create `src/cub/core/hooks/installer.py`
2. Create hook template (bash script)
3. Implement `install_hooks(project_dir) -> None`
4. Implement `uninstall_hooks(project_dir) -> None`
5. Integrate into cub init flow
6. Add --no-hooks flag to cub init

**Acceptance Criteria**:
- [ ] Hook script created in .git/hooks/post-commit
- [ ] Hook is executable
- [ ] Extracts Task-Id and updates ledger
- [ ] Never fails commits (safe)
- [ ] cub init --no-hooks skips installation

**Files**: src/cub/core/hooks/installer.py, src/cub/cli/init.py

---

### Task: cub-w9t.8 - Wire context regeneration to run completion

Priority: 2
Labels: epic:cub-w9t, phase-3, model:haiku, complexity:low

**Context**: Context files should be refreshed after cub run completes so agents in future sessions have up-to-date information.

**Implementation Steps**:
1. Find run completion handling in `src/cub/cli/run.py`
2. After successful run completion, call ContextGenerator.regenerate_all()
3. Make it optional via config
4. Handle errors gracefully
5. Test integration

**Acceptance Criteria**:
- [ ] Context files regenerated after run completion
- [ ] Can disable via config
- [ ] Errors don't crash run

**Files**: src/cub/cli/run.py, src/cub/core/context/

---

## Epic: cub-h3v - Epic Summaries & Polish

Priority: 3
Labels: phase-4, polish, documentation

Add epic-level aggregation and production polish. Deliverables: Epic summaries generated when epic completes, 60%+ test coverage for ledger and context modules, CLAUDE.md documentation updated, performance optimization if needed.

### Task: cub-h3v.1 - Implement epic summary generation

Priority: 2
Labels: epic:cub-h3v, phase-4, model:sonnet, complexity:medium
Blocks: cub-h3v.2

**Context**: When an epic completes (all tasks closed), generate an aggregated summary in .cub/ledger/by-epic/.

**Implementation Steps**:
1. Add `finalize_epic(epic_id) -> EpicSummary` to LedgerWriter
2. Query all ledger entries for epic
3. Aggregate totals
4. Generate summary markdown
5. Write to `.cub/ledger/by-epic/{epic-id}.md`

**Acceptance Criteria**:
- [ ] EpicSummary generated when epic closes
- [ ] Contains aggregated cost/time/files
- [ ] Task table shows individual stats
- [ ] Written to by-epic/ directory

**Files**: src/cub/core/ledger/writer.py, src/cub/core/ledger/models.py, tests/test_epic_summary.py

---

### Task: cub-h3v.2 - Implement cub ledger epic command

Priority: 2
Labels: epic:cub-h3v, phase-4, model:haiku, complexity:low

**Context**: CLI command to view and finalize epic summaries.

**Implementation Steps**:
1. Add `epic` command to `src/cub/cli/ledger.py`
2. `cub ledger epic <id>` - Show epic summary
3. `cub ledger epic <id> --finalize` - Generate summary now
4. `cub ledger epic --list` - List epics with summaries
5. Add --json flag

**Acceptance Criteria**:
- [ ] cub ledger epic <id> displays summary
- [ ] --finalize generates summary on demand
- [ ] --list shows available epics
- [ ] --json works

**Files**: src/cub/cli/ledger.py

---

### Task: cub-h3v.3 - Add comprehensive test coverage for ledger module

Priority: 2
Labels: epic:cub-h3v, phase-4, model:sonnet, complexity:medium

**Context**: Production code needs good test coverage. Target 60%+ for ledger module.

**Implementation Steps**:
1. Run coverage report: `pytest --cov=src/cub/core/ledger`
2. Identify uncovered code paths
3. Add tests for edge cases and error handling
4. Verify 60%+ coverage

**Acceptance Criteria**:
- [ ] 60%+ coverage for src/cub/core/ledger/
- [ ] All public methods have at least one test
- [ ] Edge cases covered

**Files**: tests/test_ledger_*.py, tests/test_cli_ledger.py

---

### Task: cub-h3v.4 - Add comprehensive test coverage for context module

Priority: 2
Labels: epic:cub-h3v, phase-4, model:sonnet, complexity:medium

**Context**: Production code needs good test coverage. Target 60%+ for context module.

**Implementation Steps**:
1. Run coverage report: `pytest --cov=src/cub/core/context`
2. Identify uncovered code paths
3. Add tests for tree-sitter edge cases and llms.txt variations
4. Verify 60%+ coverage

**Acceptance Criteria**:
- [ ] 60%+ coverage for src/cub/core/context/
- [ ] Tree-sitter edge cases covered
- [ ] CLI commands tested

**Files**: tests/test_context_*.py, tests/test_cli_context.py

---

### Task: cub-h3v.5 - Update CLAUDE.md with ledger and context documentation

Priority: 2
Labels: epic:cub-h3v, phase-4, model:haiku, complexity:low

**Context**: CLAUDE.md is the primary documentation for agents working on cub. Update with ledger and context system docs.

**Implementation Steps**:
1. Read current CLAUDE.md structure
2. Add sections: Knowledge Retention System, Ledger, Context Generation, Drift Detection
3. Update command reference section
4. Review for consistency

**Acceptance Criteria**:
- [ ] Ledger system documented in CLAUDE.md
- [ ] Context generation documented
- [ ] Drift detection documented
- [ ] Commands listed in reference

**Files**: CLAUDE.md

---

### Task: cub-h3v.6 - Performance optimization and final polish

Priority: 3
Labels: epic:cub-h3v, phase-4, model:sonnet, complexity:medium

**Context**: Final review for performance issues and polish. Address any slow operations or UX rough edges.

**Implementation Steps**:
1. Profile slow operations
2. Optimize if needed (caching, lazy loading)
3. Polish CLI (error messages, progress indicators)
4. Review and fix any mypy warnings
5. Final ruff lint and format

**Acceptance Criteria**:
- [ ] No operations take >5s for typical usage
- [ ] CLI has consistent UX
- [ ] mypy passes with no warnings
- [ ] ruff passes with no issues

**Files**: Various files across ledger and context

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-r7k | 7 | P0 | Token Persistence - persist cost data |
| cub-m4j | 6 | P1 | Ledger Core - completed work records |
| cub-w9t | 8 | P2 | Context & Drift - context gen and drift detection |
| cub-h3v | 6 | P3 | Polish - summaries, tests, docs |

**Total**: 4 epics, 27 tasks

### Model Distribution

| Model | Tasks | Rationale |
|-------|-------|-----------|
| opus | 2 | Complex LLM prompts (extraction, drift) |
| sonnet | 18 | Standard implementation work |
| haiku | 7 | Setup, simple CLI, docs |

### Checkpoints

1. **cub-r7k.7**: Cost data visible in `cub status`
2. **cub-m4j.4**: `cub ledger show/stats/search` working
3. **cub-m4j.6**: Ledger entries created automatically
4. **cub-w9t.5**: `cub ledger drift` producing reports

---

**Next Step:** Run `cub stage` to import these tasks into beads.
