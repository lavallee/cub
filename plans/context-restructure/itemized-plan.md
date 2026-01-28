# Itemized Plan: Context Restructure

> Source: [context-restructure.md](../../specs/researching/context-restructure.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-28

## Context Summary

Restructure cub's prompt context system to achieve parity between interactive
and autonomous sessions. Replace seven fragmented context files with a clean
layered stack. Eliminate progress.txt, guardrails.md, and fix_plan.md sprawl.
Add auto-generated project map with tree-sitter code intelligence. Ship default
constitution with journalistic principles.

**Mindset:** Production | **Scale:** Team

---

## Epic: cub-r1a - context-restructure #1: Cleanup

Priority: 0
Labels: phase-1, setup

Remove deprecated context files and references before building the new system.
This creates a clean foundation — no ambiguity about which files are canonical.
Done first so every subsequent task operates on the new model, not the old one.

### Task: cub-r1a.1 - Remove progress.txt references from templates and prompts

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, cleanup

**Context**: Templates and prompts instruct agents to "append learnings to
progress.txt", which created the 750KB+ sprawl. Removing these references is
step one — without it, new sessions will keep creating progress files.

**Implementation Steps**:
1. Search all templates (`templates/`) for references to progress.txt and remove them
2. Update `templates/PROMPT.md` to remove the `@progress.txt` reference from Context Files section and the "Append learnings to progress.txt" instruction from When You're Done section
3. Search `src/cub/` for any code that reads, writes, or references progress.txt and remove those code paths
4. Search for references in `instructions.py` (`generate_agents_md`, `generate_claude_md`) and remove progress.txt mentions
5. Verify no remaining references: `grep -r "progress" templates/ src/cub/`

**Acceptance Criteria**:
- [ ] No templates reference progress.txt or progress.md
- [ ] No source code reads or writes progress files
- [ ] `generate_agents_md()` and `generate_claude_md()` produce no progress.txt references
- [ ] Existing tests still pass (no broken imports or references)

**Files**: templates/PROMPT.md, src/cub/core/instructions.py, src/cub/cli/run.py

---

### Task: cub-r1a.2 - Remove deprecated template files

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, cleanup

**Context**: guardrails.md, fix_plan.md, and AGENT.md templates are being
replaced by constitution.md, ledger-based retry context, and cub map
respectively. Remove them from the template set so `cub init` and `cub update`
no longer deploy them.

**Implementation Steps**:
1. Delete `templates/guardrails.md`
2. Delete `templates/fix_plan.md`
3. Delete `templates/AGENT.md`
4. Delete `templates/progress.txt`
5. Search `src/cub/` for code that copies or references these template files (init, update commands) and remove those code paths
6. Update any tests that reference these template files
7. Do NOT delete `templates/PROMPT.md` yet (it gets replaced in Phase 2 by runloop.md)

**Acceptance Criteria**:
- [ ] Four template files deleted (guardrails.md, fix_plan.md, AGENT.md, progress.txt)
- [ ] No code references the deleted templates
- [ ] `cub init` and `cub update` do not attempt to deploy these files
- [ ] Tests pass

**Files**: templates/guardrails.md, templates/fix_plan.md, templates/AGENT.md, templates/progress.txt, src/cub/cli/init_cmd.py, src/cub/cli/update.py

---

### Task: cub-r1a.3 - Delete stale progress and guardrails files from cub repo

Priority: 1
Labels: phase-1, model:haiku, complexity:low, cleanup

**Context**: The cub repo itself has accumulated stale files: progress.txt
(451KB, root), .cub/progress.txt (294KB), .cub/progress.md, and
.cub/guardrails.md with test data. These need to be deleted. Also clean up
.cub/fix_plan.md if it has only placeholder content.

**Implementation Steps**:
1. Delete `progress.txt` from project root
2. Delete `.cub/progress.txt`
3. Delete `.cub/progress.md`
4. Delete `.cub/guardrails.md`
5. Delete `.cub/fix_plan.md` (if only placeholder/test content)
6. Verify .gitignore includes patterns to prevent future progress file accumulation
7. Commit the deletions

**Acceptance Criteria**:
- [ ] No progress.txt, progress.md, guardrails.md, or fix_plan.md in repo (except templates/constitution.md which replaces them)
- [ ] .gitignore updated if needed
- [ ] Git clean after commit

**Files**: progress.txt, .cub/progress.txt, .cub/progress.md, .cub/guardrails.md, .cub/fix_plan.md

---

## Epic: cub-r1b - context-restructure #2: Foundation

Priority: 0
Labels: phase-2, core

Build the demarcated section engine, constitution manager, and runloop prompt.
These are the core infrastructure that all subsequent work depends on — the map
needs somewhere to be referenced from, the run loop needs its new prompt, and
init/update need the upsert logic.

### Task: cub-r1b.1 - Implement managed section detection and upsert engine

Priority: 0
Labels: phase-2, model:opus, complexity:high, core, blocking

**Context**: This is the most architecturally significant task. The managed
section engine is the foundation for non-destructive CLAUDE.md/AGENTS.md
updates. It must handle: first init (no file), first init (existing file, no
markers), update (markers present), partial markers (error recovery), version
mismatch, and manual edit detection via content hashing.

**Implementation Steps**:
1. Add `UpsertResult` and `SectionInfo` Pydantic models to `instructions.py`
2. Implement `detect_managed_section(file_path)` — regex-based marker detection, returns `SectionInfo` with version, line range, and content hash
3. Implement `upsert_managed_section(file_path, content, version)` — handles all cases: create new file, append to existing file, replace existing section. Uses sha256 hash to detect manual edits inside markers (warn but proceed)
4. Implement marker format: `<!-- BEGIN CUB MANAGED SECTION v{N} -->`, `<!-- sha256:{hash} -->`, comment lines, content, `<!-- END CUB MANAGED SECTION -->`
5. Handle edge cases: file doesn't exist (create with section only), begin marker without end (warn, append end marker), end marker without begin (warn, prepend begin marker)
6. Write comprehensive tests covering all edge cases: empty file, file with user content, file with existing section, file with tampered section, partial markers, version upgrade

**Acceptance Criteria**:
- [ ] `detect_managed_section()` correctly finds markers and extracts version, line range, hash
- [ ] `upsert_managed_section()` creates file if missing
- [ ] `upsert_managed_section()` appends section to existing file without markers
- [ ] `upsert_managed_section()` replaces section content between existing markers
- [ ] Content outside markers is never modified
- [ ] Manual edits inside markers produce a warning in `UpsertResult.warnings`
- [ ] Partial marker recovery works (single begin or end marker)
- [ ] All tests pass, mypy clean

**Files**: src/cub/core/instructions.py, tests/test_instructions.py

---

### Task: cub-r1b.2 - Refactor instruction generators for managed section content

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, core
Blocks: cub-r1b.4

**Context**: `generate_agents_md()` and `generate_claude_md()` currently produce
full-file content (90+ lines each). They need to produce only the content that
goes inside the managed section markers — condensed to ~15-20 lines each with
references to `.cub/map.md` and `.cub/constitution.md`.

**Implementation Steps**:
1. Create `generate_managed_section(project_dir, config, harness="generic")` that produces the condensed managed section content
2. For "generic" (AGENTS.md): condensed task workflow (find → claim → complete in 5-6 lines), references to `@.cub/map.md` and `@.cub/constitution.md`, escape hatch summary (2 lines, link to full docs)
3. For "claude" (CLAUDE.md): same as generic plus Claude-specific additions (plan mode tip, skills reference)
4. Keep the existing `generate_agents_md()` and `generate_claude_md()` functions as wrappers that call `generate_managed_section()` and pass it through `upsert_managed_section()` — maintains backward compatibility for callers
5. Update tests to verify the new condensed content includes references to map and constitution
6. Total managed section should be ~20 lines for AGENTS.md, ~25 for CLAUDE.md

**Acceptance Criteria**:
- [ ] `generate_managed_section()` exists with harness parameter
- [ ] Generated AGENTS.md section is under 30 lines
- [ ] Generated CLAUDE.md section is under 35 lines
- [ ] Both reference `@.cub/map.md` and `@.cub/constitution.md`
- [ ] Both include condensed task workflow (bd ready, bd close)
- [ ] Existing callers (`init_cmd.py`) still work
- [ ] Tests pass, mypy clean

**Files**: src/cub/core/instructions.py, tests/test_instructions.py

---

### Task: cub-r1b.3 - Create runloop.md and constitution manager

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, core
Blocks: cub-r1b.4

**Context**: Two new files need to exist before init/update can reference them.
The runloop prompt is a stripped-down version of PROMPT.md with pure ralph-loop
behavior. The constitution manager copies the default template to `.cub/` and
provides a read API.

**Implementation Steps**:
1. Create `templates/runloop.md` by extracting from `templates/PROMPT.md`: keep ralph-loop workflow, escape hatch, COMPLETE signal, feedback loop instructions. Remove: `@AGENT.md` and `@specs/*` references, progress.txt references, generic coding advice (search before writing, no placeholders), the lengthy HTML comment header. Target ~40 lines.
2. Create `src/cub/core/constitution.py` with `ensure_constitution(project_dir, force)` and `read_constitution(project_dir)`
3. `ensure_constitution()`: check if `.cub/constitution.md` exists; if not, copy from `templates/constitution.md`; if force=True, overwrite; return Path
4. `read_constitution()`: read and return content, or None if not present
5. Write tests for constitution manager: creates when missing, skips when exists, overwrites with force
6. Write tests for runloop.md: verify it contains escape hatch, COMPLETE signal, does NOT contain progress.txt references

**Acceptance Criteria**:
- [ ] `templates/runloop.md` exists with pure ralph-loop behavior (~40 lines)
- [ ] `templates/runloop.md` does NOT reference progress.txt, AGENT.md, or specs/*
- [ ] `templates/runloop.md` contains escape hatch (`<stuck>`) and completion signal (`<promise>COMPLETE</promise>`)
- [ ] `ensure_constitution()` copies default on first call, skips on second
- [ ] `read_constitution()` returns content or None
- [ ] Tests pass, mypy clean

**Files**: templates/runloop.md, src/cub/core/constitution.py, templates/constitution.md, tests/test_constitution.py

---

### Task: cub-r1b.4 - Update cub init and cub update for new context stack

Priority: 0
Labels: phase-2, model:sonnet, complexity:medium, core

**Context**: The init and update commands need to use the new upsert engine
instead of writing full files. Init creates the initial context stack (managed
sections + constitution + runloop). Update refreshes the managed sections and
regenerates the map (map wiring comes in Phase 3, but the update command
structure needs to be ready).

**Implementation Steps**:
1. Modify `init_cmd.py`: replace direct file writes with `upsert_managed_section()` calls for AGENTS.md and CLAUDE.md
2. Add `ensure_constitution()` call to init flow
3. Add runloop copy to init flow: copy `templates/runloop.md` to `.cub/runloop.md` if not present
4. Modify `update.py`: add managed section refresh (find existing markers, replace content, bump version if template changed)
5. Add constitution check to update (ensure exists, don't overwrite)
6. Add runloop refresh to update (copy if missing, warn if modified from template)
7. Update `generate_system_prompt()` in run.py to look for `.cub/runloop.md` before `PROMPT.md` (new lookup order: `.cub/runloop.md` → `PROMPT.md` → `templates/PROMPT.md` → `templates/runloop.md` → fallback)
8. Update tests for init and update commands

**Acceptance Criteria**:
- [ ] `cub init` on a new project creates AGENTS.md and CLAUDE.md with managed sections
- [ ] `cub init` on a project with existing CLAUDE.md appends managed section without destroying user content
- [ ] `cub init` creates `.cub/constitution.md` from default template
- [ ] `cub init` creates `.cub/runloop.md` from template
- [ ] `cub update` refreshes managed sections in existing AGENTS.md/CLAUDE.md
- [ ] `generate_system_prompt()` reads `.cub/runloop.md` when present
- [ ] Tests pass, mypy clean

**Files**: src/cub/cli/init_cmd.py, src/cub/cli/update.py, src/cub/cli/run.py, tests/test_init.py

---

### Task: cub-r1b.5 - Add MapConfig to config system

Priority: 1
Labels: phase-2, model:sonnet, complexity:low, config

**Context**: The config system needs a `MapConfig` model so that `cub map`
behavior is configurable via `.cub.json`. This needs to exist before the map
module is built so it can reference the config.

**Implementation Steps**:
1. Add `MapConfig` Pydantic model to `src/cub/core/config/models.py`: `token_budget` (int, default 1500), `max_depth` (int, default 4), `include_code_intel` (bool, default True), `include_ledger_stats` (bool, default True), `exclude_patterns` (list[str], defaults for node_modules, .git, etc.)
2. Add `map: MapConfig` field to `CubConfig` with `default_factory=MapConfig`
3. Verify config loading works: default values, override via `.cub.json`
4. Add tests for MapConfig defaults and override

**Acceptance Criteria**:
- [ ] `MapConfig` model exists with all fields and defaults
- [ ] `CubConfig.map` field exists and loads correctly
- [ ] Config can be overridden via `.cub.json`
- [ ] Tests pass, mypy clean

**Files**: src/cub/core/config/models.py, tests/test_config_loader.py

---

## Epic: cub-r1c - context-restructure #3: Project Map

Priority: 1
Labels: phase-3, feature

Build the `cub map` command with structural analysis and tree-sitter code
intelligence. This is the largest epic — the map is the most complex new
capability and the highest-value deliverable for context parity.

### Task: cub-r1c.1 - Implement structure analyzer module

Priority: 0
Labels: phase-3, model:sonnet, complexity:medium, core

**Context**: The structure analyzer provides the foundational layer of the
project map — directory tree, tech stack detection, and build command extraction.
This works without tree-sitter and serves as the fallback when code intelligence
is unavailable.

**Implementation Steps**:
1. Create `src/cub/core/map/__init__.py` and `src/cub/core/map/structure.py`
2. Implement Pydantic models: `DirectoryTree`, `TechStack`, `BuildCommand`, `KeyFile`, `ModuleInfo`, `ProjectStructure`
3. Implement `analyze_structure(project_dir, max_depth)`:
   - Directory tree generation respecting .gitignore (use `pathspec` for pattern matching) and `MapConfig.exclude_patterns`
   - Depth-limited traversal (default 4 levels)
4. Implement config file parsers:
   - `pyproject.toml`: extract `[project.scripts]`, `[tool.pytest]`, `[tool.ruff]`, `[tool.mypy]` entries; detect dependencies for tech stack
   - `package.json`: extract `scripts`, `main`, `dependencies` for tech stack
   - `Cargo.toml`: extract `[[bin]]` targets, `[workspace]`
   - `go.mod`: extract module path
   - `Makefile`: extract target names (regex for lines matching `^target:`)
   - `Dockerfile`: extract `FROM` and `ENTRYPOINT`/`CMD`
5. Implement key file detection: README.*, LICENSE, main entry points (from config parsers), test directories
6. Implement module boundary detection: top-level directories under src/ or root with `__init__.py` (Python) or `index.{js,ts}` (JS/TS)
7. Write tests with fixture projects (minimal Python project, minimal Node project, empty project)

**Acceptance Criteria**:
- [ ] `analyze_structure()` returns a complete `ProjectStructure` for a Python project
- [ ] Directory tree respects .gitignore and exclude patterns
- [ ] Tech stack detected from pyproject.toml (at minimum)
- [ ] Build commands extracted from pyproject.toml scripts/tools
- [ ] Key files identified (README, entry points)
- [ ] Graceful handling of missing config files (returns partial structure)
- [ ] Tests pass, mypy clean

**Files**: src/cub/core/map/__init__.py, src/cub/core/map/structure.py, src/cub/core/map/models.py, tests/test_map_structure.py

---

### Task: cub-r1c.2 - Implement code intelligence module with tree-sitter

Priority: 0
Labels: phase-3, model:opus, complexity:high, core, risk:medium

**Context**: This is the tree-sitter + PageRank pipeline adapted from Aider's
repo map approach. Uses `grep-ast` for tag extraction and `networkx` for
ranking. This is the highest-risk task — it involves external library
integration and must degrade gracefully.

**Implementation Steps**:
1. Add dependencies to `pyproject.toml`: `grep-ast>=0.9.0`, `networkx>=3.2.0`, `tree-sitter-language-pack>=0.13.0`, `diskcache>=5.6.0`, `pathspec>=0.12.0`
2. Create `src/cub/core/map/code_intel.py`
3. Implement `SymbolTag` and `RankedSymbol` Pydantic models
4. Implement `extract_tags(project_dir, files)`:
   - Use `grep-ast` to parse each source file
   - Extract definition tags (functions, classes, methods) and reference tags (imports, calls)
   - Wrap in try/except per file — if parsing fails for a file, skip it with a warning
5. Implement `rank_symbols(tags, token_budget)`:
   - Build a networkx DiGraph: nodes are files, edges weighted by cross-file reference counts
   - Apply `networkx.pagerank()` to get file importance scores
   - Distribute file scores to their definition tags
   - Sort by rank, select top symbols within token budget
   - Use binary search to find optimal number of symbols (similar to Aider's approach)
6. Implement `diskcache`-based caching: cache parsed tags per file keyed by `(file_path, mtime, file_size)` — invalidate on any change
7. Implement graceful fallback: if `grep-ast` or `tree-sitter-language-pack` import fails, `extract_tags()` returns empty list with a logged warning
8. Write tests: mock `grep-ast` output for unit tests; integration test against the cub repo itself

**Acceptance Criteria**:
- [ ] `extract_tags()` returns definition and reference tags from Python source files
- [ ] `rank_symbols()` returns ranked symbols within token budget
- [ ] PageRank correctly identifies high-connectivity files (e.g., `config/models.py`, `tasks/backend.py`)
- [ ] Caching works: second call is faster than first
- [ ] Graceful fallback: returns empty list if grep-ast unavailable (no crash)
- [ ] Individual file parse failures don't crash the whole extraction
- [ ] Tests pass, mypy clean

**Files**: src/cub/core/map/code_intel.py, pyproject.toml, tests/test_map_code_intel.py

---

### Task: cub-r1c.3 - Implement map renderer with token budgeting

Priority: 0
Labels: phase-3, model:sonnet, complexity:medium, core
Blocks: cub-r1c.4

**Context**: The renderer combines structural analysis and ranked symbols into
a single markdown document within a token budget. It needs to prioritize
structural information (always useful) and fill remaining budget with ranked
symbols (valuable but cuttable).

**Implementation Steps**:
1. Create `src/cub/core/map/renderer.py`
2. Implement `render_map(structure, ranked_symbols, token_budget, include_ledger_stats, ledger_reader)`:
   - Start with Tech Stack section (from `structure.tech_stack`)
   - Add Build Commands section (from `structure.build_commands`)
   - Add Structure section (from `structure.tree`, condensed to module-level annotations)
   - Calculate tokens used so far (simple heuristic: word count * 1.3)
   - Fill remaining budget with Key Symbols section (from `ranked_symbols`, one line each: `name (file:line) - kind`)
   - If `include_ledger_stats` and `ledger_reader` available, add Project Health section (task counts, average attempts)
3. Implement token estimation: `estimate_tokens(text)` using word count heuristic (words / 0.75 ≈ tokens). This is model-agnostic and avoids a tiktoken dependency.
4. Implement budget allocation: structural sections get up to 40% of budget, symbols get remaining 60%, ledger stats capped at 10%
5. Write tests with fixture data: verify budget is respected, verify section ordering, verify graceful handling of empty symbols list

**Acceptance Criteria**:
- [ ] `render_map()` produces readable markdown with clear sections
- [ ] Output stays within token budget (verify with multiple budget sizes)
- [ ] Structural sections always present even with zero symbols
- [ ] Symbols section fills available budget, sorted by rank
- [ ] Ledger stats included when reader available, skipped gracefully when not
- [ ] Tests pass, mypy clean

**Files**: src/cub/core/map/renderer.py, tests/test_map_renderer.py

---

### Task: cub-r1c.4 - Implement cub map CLI command and wire into init/update

Priority: 0
Labels: phase-3, model:sonnet, complexity:medium, cli

**Context**: The CLI command ties together structure analysis, code intelligence,
and rendering. It also needs to be called by `cub init` and `cub update` so the
map is generated/refreshed automatically.

**Implementation Steps**:
1. Create `src/cub/cli/map.py` with Typer command:
   - Arguments: `project_dir` (default "."), `--tokens` (default from config), `--output` (default `.cub/map.md`), `--no-code-intel`, `--verbose`
   - Flow: load config → `analyze_structure()` → `extract_tags()` + `rank_symbols()` (unless `--no-code-intel`) → `render_map()` → write to output path
   - Rich console output: show progress, report token count, list detected tech stack
2. Register command in `src/cub/cli/__init__.py`: `app.command(name="map")` under appropriate panel
3. Wire map generation into `cub init`: call map generation after managed section upsert
4. Wire map generation into `cub update`: regenerate map as part of update flow
5. Update managed section content to reference `@.cub/map.md` (should already be there from Task cub-r1b.2, verify)
6. Write integration tests: `cub map` on a fixture project, verify output file exists and contains expected sections

**Acceptance Criteria**:
- [ ] `cub map` command generates `.cub/map.md` with structural + code intelligence sections
- [ ] `cub map --no-code-intel` generates structural-only map
- [ ] `cub map --tokens 500` produces a smaller map
- [ ] `cub init` generates `.cub/map.md` automatically
- [ ] `cub update` regenerates `.cub/map.md`
- [ ] Map is referenced from managed section in CLAUDE.md/AGENTS.md
- [ ] Tests pass, mypy clean

**Files**: src/cub/cli/map.py, src/cub/cli/__init__.py, src/cub/cli/init_cmd.py, src/cub/cli/update.py, tests/test_map_cli.py

---

## Epic: cub-r1d - context-restructure #4: Task Prompt Enrichment

Priority: 1
Labels: phase-4, feature

Add epic context, sibling awareness, and retry injection to task prompts.
Update the system prompt to use the new runloop.md. This is the final piece
that achieves full context parity between interactive and autonomous sessions.

### Task: cub-r1d.1 - Implement epic context generation for task prompts

Priority: 0
Labels: phase-4, model:sonnet, complexity:medium, core

**Context**: When a task belongs to an epic, the agent should know the epic's
purpose and what sibling tasks have been completed or remain. This prevents
repeated work and helps the agent avoid painting itself into a corner.

**Implementation Steps**:
1. Add `generate_epic_context(task, task_backend)` function to `run.py` (or a new `src/cub/core/prompt.py` module if run.py is getting too large)
2. Implementation:
   - If `task.parent` is None, return None
   - Fetch epic via `task_backend.get_task(task.parent)`
   - Fetch all sibling tasks via `task_backend.list_tasks(parent=task.parent)`
   - Partition siblings into completed (closed status) and remaining (open/in_progress, excluding current task)
   - Format as markdown section:
     ```
     ## EPIC CONTEXT
     Epic: {epic.id} - {epic.title}
     {epic.description, truncated to ~200 words}

     Completed tasks in this epic:
     - {id}: {title}

     Remaining tasks after this one:
     - {id}: {title}
     ```
3. Truncate epic description to ~200 words to avoid blowing up the prompt
4. Integrate into task prompt generation: call after `generate_task_prompt()`, append result if non-None
5. Write tests with mock task backend: task with epic, task without epic, epic with many siblings

**Acceptance Criteria**:
- [ ] `generate_epic_context()` returns None for tasks without a parent
- [ ] Returns formatted markdown with epic title, description, and sibling lists
- [ ] Completed siblings listed separately from remaining siblings
- [ ] Current task not listed in either sibling list
- [ ] Epic description truncated to reasonable length
- [ ] Integrated into task prompt pipeline in run.py
- [ ] Tests pass, mypy clean

**Files**: src/cub/cli/run.py (or src/cub/core/prompt.py), tests/test_run.py

---

### Task: cub-r1d.2 - Implement retry context injection from ledger

Priority: 0
Labels: phase-4, model:sonnet, complexity:medium, core

**Context**: When a task is retried after failure, the agent should know what
went wrong last time. The ledger already stores `error_category`,
`error_summary`, and the full harness log. We extract structured fields plus
the tail of the log.

**Implementation Steps**:
1. Add `generate_retry_context(task, ledger_reader, log_tail_lines=50)` function alongside `generate_epic_context()`
2. Implementation:
   - Read ledger entry via `ledger_reader.get_task(task.id)`
   - If no entry or no failed attempts, return None
   - Get the most recent failed attempt from `entry.attempts`
   - Extract `error_category` and `error_summary`
   - Read the harness log file: `.cub/ledger/by-task/{task.id}/attempts/{attempt_number:03d}-harness.log`
   - Extract last `log_tail_lines` lines from the log
   - Format as markdown section:
     ```
     ## PREVIOUS ATTEMPT

     This task was attempted before and did not succeed.
     Failure reason: {error_category}: {error_summary}

     Last 50 lines of previous attempt output:
     ```
     {log tail}
     ```
     ```
3. Handle missing log files gracefully (log may not exist if harness crashed)
4. Integrate into task prompt pipeline: call after epic context, append if non-None
5. Write tests: task with failed attempt, task with no attempts, task with successful-only attempts, missing log file

**Acceptance Criteria**:
- [ ] `generate_retry_context()` returns None for tasks with no failed attempts
- [ ] Returns formatted markdown with error category, summary, and log tail
- [ ] Handles missing harness log files gracefully (still returns error fields)
- [ ] Log tail is limited to configured number of lines
- [ ] Integrated into task prompt pipeline in run.py
- [ ] Tests pass, mypy clean

**Files**: src/cub/cli/run.py (or src/cub/core/prompt.py), tests/test_run.py

---

### Task: cub-r1d.3 - Update system prompt and document context composition

Priority: 1
Labels: phase-4, model:sonnet, complexity:medium, docs

**Context**: Final integration: update `generate_system_prompt()` to use the
new runloop.md lookup order, and document the entire context composition in
cub's own CLAUDE.md so future contributors understand the system.

**Implementation Steps**:
1. Update `generate_system_prompt()` in run.py: change lookup order to `.cub/runloop.md` → `PROMPT.md` → `templates/PROMPT.md` → `templates/runloop.md` → hardcoded fallback
2. Apply the new demarcated format to cub's own CLAUDE.md:
   - Preserve the existing hand-written content (project overview, tech stack, development setup, etc.)
   - Append the cub managed section using `upsert_managed_section()`
3. Add a "Context Composition" section to cub's CLAUDE.md documenting:
   - What files exist and their purpose
   - What agents see in interactive vs. cub run sessions
   - Where to customize behavior (outside managed section, in constitution, etc.)
   - The ASCII context stack diagram from the architecture doc
4. Update the "Gotchas & Learnings" section in CLAUDE.md to note the new system
5. Remove stale references to progress.txt, guardrails.md, fix_plan.md from CLAUDE.md

**Acceptance Criteria**:
- [ ] `generate_system_prompt()` reads `.cub/runloop.md` when present
- [ ] `generate_system_prompt()` falls back to PROMPT.md for backward compatibility
- [ ] Cub's own CLAUDE.md has managed section appended (not replacing existing content)
- [ ] Context composition documented: file purposes, interactive vs. run parity, where to customize
- [ ] No stale references to eliminated files in CLAUDE.md
- [ ] Tests pass

**Files**: src/cub/cli/run.py, CLAUDE.md, tests/test_run.py

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-r1a | 3 | P0 | Cleanup: remove deprecated files and references |
| cub-r1b | 5 | P0 | Foundation: demarcation engine, constitution, runloop |
| cub-r1c | 4 | P1 | Project Map: structure + tree-sitter + renderer + CLI |
| cub-r1d | 3 | P1 | Enrichment: epic context, retry injection, documentation |

**Total**: 4 epics, 15 tasks

### Dependency Graph

```
cub-r1a (Cleanup) ──────────────────────────────────────────────────────
  cub-r1a.1  Remove progress.txt references
  cub-r1a.2  Remove deprecated templates
  cub-r1a.3  Delete stale files from repo
         │
         ▼
cub-r1b (Foundation) ───────────────────────────────────────────────────
  cub-r1b.1  Managed section engine          ←── blocking
  cub-r1b.2  Refactor instruction generators  (needs r1b.1)
  cub-r1b.3  Runloop + constitution manager
  cub-r1b.4  Wire init + update              (needs r1b.2, r1b.3)
  cub-r1b.5  MapConfig in config system
         │
         ▼
cub-r1c (Project Map) ─────────────────────────────────────────────────
  cub-r1c.1  Structure analyzer
  cub-r1c.2  Code intelligence (tree-sitter)  ←── highest risk
  cub-r1c.3  Map renderer                    (needs r1c.1, r1c.2)
  cub-r1c.4  CLI + wire into init/update     (needs r1c.3, r1b.4)
         │
         ▼
cub-r1d (Enrichment) ──────────────────────────────────────────────────
  cub-r1d.1  Epic context generation
  cub-r1d.2  Retry context injection
  cub-r1d.3  System prompt + documentation   (needs r1d.1, r1d.2)
```

### Ready to Start Immediately

After cleanup (cub-r1a), these tasks have no dependencies:
- **cub-r1b.1** — Managed section engine (blocking)
- **cub-r1b.3** — Runloop + constitution manager
- **cub-r1b.5** — MapConfig in config system
- **cub-r1c.1** — Structure analyzer (can parallel with foundation)
