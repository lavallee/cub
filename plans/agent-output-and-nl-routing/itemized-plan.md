# Itemized Plan: Agent Output and Natural Language Routing

> Source: [agent-output-and-nl-routing.md](../../specs/researching/agent-output-and-nl-routing.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-29

## Context Summary

Make cub's CLI output optimized for LLM consumption via an `--agent` flag, and upgrade the `/cub` natural language router to use this output and learn from usage over time. Three parts: AgentFormatter + `--agent` flag, passthrough skill updates, and hook-based route learning.

**Mindset:** Production | **Scale:** Personal

**Cross-spec dependency:** DependencyGraph (from cub-task-parity plan, epic cub-p1t) is optional for Phase 1 but enhances analysis sections. AgentFormatter methods accept `graph: DependencyGraph | None` — they work without it but produce richer output with it.

---

## Epic: cub-a1f - agent-output #1: AgentFormatter & --agent Flag

Priority: 0
Labels: phase-1, complexity:high, model:sonnet

Build the AgentFormatter module and wire `--agent` flags into Phase 1 CLI commands (task ready, task show, status, suggest). This is the core value — Claude gets structured, compact markdown with pre-computed analysis hints instead of raw Rich output.

### Task: cub-a1f.1 - Build AgentFormatter module with Phase 1 format methods

Priority: 0
Labels: phase-1, model:sonnet, complexity:high
Blocks: cub-a1f.2

**Context**: The AgentFormatter is a collection of static methods that transform service-layer data into structured markdown for LLM consumption. Each method follows the envelope template: heading, summary line, data tables, truncation notice, analysis section. The formatter returns plain strings — no Rich, no console. DependencyGraph is an optional parameter; when None, analysis hints that require graph queries are omitted.

**Implementation Steps**:
1. Create `src/cub/core/services/agent_format.py` with `AgentFormatter` class
2. Implement shared helpers:
   - `_truncation_notice(shown, total)` — returns "Showing N of M. Use --all for complete list." or empty string. Show all if ≤ 15, truncate to 10 if > 15.
   - `_analysis_section(hints: list[str])` — renders `## Analysis` with bullet points. Empty string if no hints.
   - `_markdown_table(headers, rows)` — renders a markdown table from lists
3. Implement `format_ready(tasks, graph=None)`:
   - Heading: `# cub task ready`
   - Summary: `{N} tasks ready to work on. {M} blocked across {C} dependency chains.` (chain info only if graph available)
   - Table: ID, Title, Pri, Blocks columns
   - Analysis: highest impact (if graph), highest priority, recommendation
4. Implement `format_task_detail(task, graph=None, epic_progress=None)`:
   - Heading: `# cub task show {id}`
   - Fields: priority, status, epic, type
   - Description: first 500 chars, truncated if longer
   - Dependencies section: blocks, blocked by, epic progress
   - Analysis: context within epic, recommendation
5. Implement `format_status(stats, epic_progress=None)`:
   - Heading: `# cub status`
   - Summary: `{total} tasks: {closed} closed ({pct}%), {in_progress} in progress, {open} open. {blocked} blocked, {ready} ready.`
   - Breakdown table: status counts
   - Epics table: progress per epic (if epic_progress provided)
   - Analysis: bottleneck identification, quick win suggestion
6. Implement `format_suggestions(suggestions)`:
   - Heading: `# cub suggest`
   - Summary: `{N} recommendations based on current project state.`
   - Table: Priority, Action, Target, Rationale columns
7. Write snapshot tests for each method with representative inputs (0, 1, 10, 20 items)
8. Write token budget test: assert output character count < 2000 for representative inputs

**Acceptance Criteria**:
- [ ] All 4 format methods return valid markdown strings
- [ ] Output follows the envelope template (heading, summary, tables, truncation, analysis)
- [ ] Truncation works: shows all if ≤ 15 items, truncates to 10 with notice if > 15
- [ ] Analysis section omits graph-dependent hints when graph is None
- [ ] Analysis section includes graph-dependent hints when graph is provided
- [ ] No Rich or console dependencies — pure string operations
- [ ] Token budget: all representative outputs < 2000 characters
- [ ] mypy passes with strict mode
- [ ] Snapshot tests pass for each method

**Files**: src/cub/core/services/agent_format.py, tests/test_agent_format.py

---

### Task: cub-a1f.2 - Wire --agent flag into Phase 1 CLI commands

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium

**Context**: Add `--agent` flag to `cub task ready`, `cub task show`, `cub status`, and `cub suggest`. Follow the existing `--json` pattern. When `--agent` is passed, call the corresponding AgentFormatter method and print the result. `--agent` wins silently over `--json` if both are passed. Include `_try_build_graph` helper that attempts to import DependencyGraph (returns None if not available yet).

**Implementation Steps**:
1. Create `_try_build_graph(backend)` helper function in `cli/task.py`:
   - Try to import `DependencyGraph` from `cub.core.tasks.graph`
   - If available, build graph from `backend.list_tasks()`
   - If ImportError or any exception, return None
2. In `cub task ready`:
   - Add `agent: bool = typer.Option(False, "--agent", help="Output for LLM consumption")`
   - If agent: build graph, call `AgentFormatter.format_ready(tasks, graph=graph)`, print, return
   - Place agent check before json check (agent wins over json)
3. In `cub task show`:
   - Add `--agent` flag
   - If agent: build graph, get epic progress if task has parent, call `AgentFormatter.format_task_detail(task, graph=graph, epic_progress=epic_progress)`, print, return
4. In `cub status` (status.py):
   - Add `--agent` flag
   - If agent: get ProjectStats from StatusService, optionally get epic progress list, call `AgentFormatter.format_status(stats, epic_progress=epics)`, print, return
5. In `cub suggest` (suggest.py):
   - Add `--agent` flag
   - If agent: get suggestions from SuggestionService, call `AgentFormatter.format_suggestions(suggestions)`, print, return
6. Write CLI integration tests for each command with `--agent` flag

**Acceptance Criteria**:
- [ ] `cub task ready --agent` outputs structured markdown
- [ ] `cub task show <id> --agent` outputs structured markdown
- [ ] `cub status --agent` outputs structured markdown
- [ ] `cub suggest --agent` outputs structured markdown
- [ ] `--agent` takes precedence over `--json` silently
- [ ] `_try_build_graph` returns None gracefully when DependencyGraph not available
- [ ] `_try_build_graph` returns working graph when DependencyGraph is available
- [ ] CLI tests pass for all four commands

**Files**: src/cub/cli/task.py, src/cub/cli/status.py, src/cub/cli/suggest.py

---

**CHECKPOINT: Core `--agent` Output Working**

At this point, `/cub` routing can use `--agent` for the four most common commands. Claude gets structured markdown with analysis hints. Validate with 5+ real `/cub` invocations: Does Claude parse it correctly? Does it add interpretation rather than parrot?

---

## Epic: cub-a2s - agent-output #2: Skill Updates & Router Integration

Priority: 1
Labels: phase-2, complexity:low, model:haiku

Update all passthrough skill files and the router skill to use `--agent` flag in their CLI invocations. This closes the loop: `/cub` → router → `cub task ready --agent` → structured markdown → Claude interprets.

### Task: cub-a2s.1 - Update passthrough skills and router to use --agent

Priority: 1
Labels: phase-2, model:haiku, complexity:low

**Context**: Seven passthrough skills exist and the router skill maps intent to CLI commands. Update all command invocations to include `--agent` so Claude always gets structured output when routing through skills. The router skill needs `--agent` on all CLI command mappings.

**Implementation Steps**:
1. Update `.claude/commands/cub:tasks.md`:
   - All `cub task` command invocations → add `--agent`
   - e.g., `cub task ready` → `cub task ready --agent`
2. Update `.claude/commands/cub:status.md`:
   - `cub status` → `cub status --agent`
3. Update `.claude/commands/cub:suggest.md`:
   - `cub suggest` → `cub suggest --agent`
4. Update `.claude/commands/cub:ledger.md`:
   - `cub ledger show` → `cub ledger show --agent` (will be available after Phase 3)
   - For now, only add `--agent` if the command supports it; otherwise leave as-is
5. Update `.claude/commands/cub:doctor.md`:
   - Same approach: add `--agent` when supported (Phase 4)
6. Update `.claude/commands/cub.md` (router):
   - All CLI command mappings in the intent routing table → add `--agent`
   - e.g., `cub task ready` → `cub task ready --agent`
   - e.g., `cub status` → `cub status --agent`
7. Add instruction in router skill about how Claude should treat `--agent` output:
   ```
   Present the data from the command output. The Analysis section contains
   pre-computed insights — use them as a starting point for your response,
   but apply your own judgment.
   ```

**Acceptance Criteria**:
- [ ] All Phase 1 commands in skill files use `--agent`
- [ ] Router skill intent table uses `--agent` for all supported commands
- [ ] Router skill includes instruction on treating analysis hints
- [ ] Skills for commands without `--agent` support are left unchanged
- [ ] No broken command invocations

**Files**: .claude/commands/cub.md, .claude/commands/cub:tasks.md, .claude/commands/cub:status.md, .claude/commands/cub:suggest.md, .claude/commands/cub:ledger.md, .claude/commands/cub:doctor.md

---

**CHECKPOINT: Full Loop Working**

`/cub what are my important tasks` → router → `cub task ready --agent` → structured markdown → Claude interprets with analysis hints. Validate the full loop with 10+ real invocations per the spec's validation plan.

---

## Epic: cub-a3r - agent-output #3: Route Learning

Priority: 1
Labels: phase-3, complexity:medium, model:sonnet

Build the hook-based route learning system: observe cub command usage via hooks, compile frequency data at session end, surface compiled routes to the router skill via file reference.

### Task: cub-a3r.1 - Add route observation to cub-hook.sh

Priority: 1
Labels: phase-3, model:haiku, complexity:low
Blocks: cub-a3r.2

**Context**: The existing `cub-hook.sh` fast-path filter fires on every Bash tool use. It already detects `cub` commands for the symbiotic workflow. Extend it to log command usage to `.cub/route-log.jsonl`. This is 4 lines of shell — minimal latency impact.

**Implementation Steps**:
1. In `.cub/scripts/hooks/cub-hook.sh`, in the PostToolUse/Bash handler where `cub ` commands are detected:
   - Add a case branch that appends a JSON line to `.cub/route-log.jsonl`
   - Format: `{"ts":"<ISO timestamp>","cmd":"<full command>"}`
   - Only log if the command starts with `cub ` (not `cub-hook` or other prefixes)
2. Add `.cub/route-log.jsonl` to `.gitignore` (raw log is local-only)
3. Ensure the logging doesn't interfere with existing hook behavior (the line is additive)
4. Test manually: run a `cub task ready` in Claude Code, verify log entry appears

**Acceptance Criteria**:
- [ ] Every `cub *` command executed via Bash tool use is logged to `.cub/route-log.jsonl`
- [ ] Log entries have ISO timestamp and full command string
- [ ] `.cub/route-log.jsonl` is in `.gitignore`
- [ ] Existing hook behavior is unchanged
- [ ] No measurable latency impact (shell echo + redirect)

**Files**: .cub/scripts/hooks/cub-hook.sh, .gitignore

---

### Task: cub-a3r.2 - Build route compiler and cub routes CLI

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium
Blocks: cub-a3r.3

**Context**: The route compiler reads the raw log, normalizes commands (strips task IDs, file paths), aggregates by frequency, filters noise (count < 3), and writes a markdown table to `.cub/learned-routes.md`. This compiled file is git-tracked and shared with the team. The compiler is triggered by the Stop hook at session end.

**Implementation Steps**:
1. Create `src/cub/core/routes/compiler.py`:
   - `RouteStats` dataclass: command (str), count (int), last_used (str)
   - `normalize_command(raw: str) -> str`: strip task IDs (cub-xxx, beads-xxx patterns), file paths, option values. Keep command structure.
     - `"cub task show cub-r6s.1 --full"` → `"cub task show"`
     - `"cub task ready --agent"` → `"cub task ready"`
     - `"cub run --task cub-042"` → `"cub run --task"`
     - `"cub status"` → `"cub status"`
   - `compile_routes(log_path, min_count=3, max_entries=1000) -> list[RouteStats]`: read JSONL, normalize, group, count, filter, sort by frequency desc
   - `render_learned_routes(routes: list[RouteStats]) -> str`: render markdown table
2. Create `src/cub/core/routes/__init__.py`
3. Create `src/cub/cli/routes.py`:
   - `compile` command: read log, compile, write `.cub/learned-routes.md`
   - `show` command: display current learned routes (read and print the md file)
   - `clear` command: delete both route-log.jsonl and learned-routes.md
4. Register routes app in `src/cub/cli/__init__.py`
5. Add Stop hook trigger in `cub-hook.sh`:
   - In the Stop handler, add: `python3 -m cub.cli.routes compile &` (background, non-blocking)
6. Write tests for `normalize_command` with edge cases (various command patterns)
7. Write tests for `compile_routes` with sample JSONL input
8. Write tests for `render_learned_routes` output format

**Acceptance Criteria**:
- [ ] `normalize_command` correctly strips IDs and values from 10+ command patterns
- [ ] `compile_routes` aggregates correctly, filters count < 3, sorts by frequency
- [ ] `compile_routes` handles max_entries truncation for large logs
- [ ] `render_learned_routes` produces valid markdown table
- [ ] `cub routes compile` writes `.cub/learned-routes.md`
- [ ] `cub routes show` displays the compiled routes
- [ ] `cub routes clear` deletes both files
- [ ] Stop hook triggers compilation in background
- [ ] mypy passes
- [ ] Tests pass for normalizer, compiler, and renderer

**Files**: src/cub/core/routes/__init__.py, src/cub/core/routes/compiler.py, src/cub/cli/routes.py, src/cub/cli/__init__.py, .cub/scripts/hooks/cub-hook.sh, tests/test_route_compiler.py

---

### Task: cub-a3r.3 - Add learned routes section to router skill

Priority: 1
Labels: phase-3, model:haiku, complexity:low

**Context**: The router skill needs to reference the compiled routes file so Claude can use frequency data as a tiebreaker for ambiguous intent. This is the only point where LLM judgment enters the route learning system.

**Implementation Steps**:
1. Add a "Learned Routes" section to `.claude/commands/cub.md`:
   ```markdown
   ## Learned Routes

   If @.cub/learned-routes.md exists, check it for frequently-used commands.
   When the user's intent could map to multiple commands, prefer ones that
   appear in the learned routes table (they've been useful before).
   ```
2. Place this section after the "Execution Rules" section and before "Examples"
3. The `@` prefix ensures Claude Code injects the file content into context

**Acceptance Criteria**:
- [ ] Router skill references `@.cub/learned-routes.md`
- [ ] Instructions tell Claude to use learned routes as tiebreaker, not override
- [ ] Section is positioned logically in the skill file
- [ ] Skill still works correctly when learned-routes.md doesn't exist yet

**Files**: .claude/commands/cub.md

---

**CHECKPOINT: Route Learning Active**

The full pipeline is operational: hooks observe → compiler aggregates → router consults. After a few sessions, `.cub/learned-routes.md` will contain frequency data. Validate: does the compiled output look reasonable? Does Claude actually reference it when routing?

---

## Epic: cub-a4e - agent-output #4: Extended Commands

Priority: 2
Labels: phase-4, complexity:medium, model:sonnet

Add `--agent` support to Phase 2 and Phase 3 commands. These depend on task parity (cub-task-parity) landing for `blocked` and `list`, and doctor refactor for `doctor`.

### Task: cub-a4e.1 - Add AgentFormatter methods for blocked, list, and ledger

Priority: 2
Labels: phase-4, model:sonnet, complexity:medium
Blocks: cub-a4e.2

**Context**: Three more commands get `--agent` support. `format_blocked` uses DependencyGraph heavily (root blockers, chain visualization). `format_list` is a general-purpose task table. `format_ledger` shows recent completions with cost summary. These depend on the task parity spec having landed `cub task blocked` and `cub task list` enhancements.

**Implementation Steps**:
1. Add `format_blocked(tasks, graph=None)` to AgentFormatter:
   - Summary: `{N} tasks blocked. {R} root blockers control all dependency chains.`
   - Root Blockers table (if graph): Blocker, Title, Pri, Unblocks
   - Dependency Chains list (if graph): longest chains
   - Analysis: critical path, recommendation
2. Add `format_list(tasks)` to AgentFormatter:
   - Summary: `{N} tasks.`
   - Table: ID, Title, Status, Pri, Epic
   - Standard truncation
3. Add `format_ledger(entries, stats=None)` to AgentFormatter:
   - Summary: `{N} ledger entries. Last completion: {date}.`
   - Recent Completions table: Date, Task, Title, Cost
   - Analysis: recent velocity, total cost, average per task
4. Write snapshot tests for each method
5. Write token budget tests

**Acceptance Criteria**:
- [ ] `format_blocked` produces correct output with and without graph
- [ ] `format_blocked` with graph shows root blockers and chains
- [ ] `format_list` produces correct output with truncation
- [ ] `format_ledger` produces correct output with cost summary
- [ ] All outputs < 2000 characters for representative inputs
- [ ] Snapshot tests pass

**Files**: src/cub/core/services/agent_format.py, tests/test_agent_format.py

---

### Task: cub-a4e.2 - Wire --agent flag into blocked, list, and ledger CLI commands

Priority: 2
Labels: phase-4, model:sonnet, complexity:medium

**Context**: Add `--agent` flag to `cub task blocked`, `cub task list`, and `cub ledger show`. These commands should already exist from the task parity spec. Wire in the AgentFormatter methods.

**Implementation Steps**:
1. In `cub task blocked` (cli/task.py):
   - Add `--agent` flag
   - If agent: build graph, call `AgentFormatter.format_blocked(tasks, graph=graph)`, print
2. In `cub task list` (cli/task.py):
   - Add `--agent` flag
   - If agent: call `AgentFormatter.format_list(tasks)`, print
3. In `cub ledger show` (cli/ledger.py):
   - Add `--agent` flag
   - If agent: get entries and stats from LedgerService, call `AgentFormatter.format_ledger(entries, stats=stats)`, print
4. Update corresponding skill files to use `--agent`
5. Write CLI tests

**Acceptance Criteria**:
- [ ] `cub task blocked --agent` outputs structured markdown
- [ ] `cub task list --agent` outputs structured markdown
- [ ] `cub ledger show --agent` outputs structured markdown
- [ ] Skill files updated to use `--agent` for these commands
- [ ] CLI tests pass

**Files**: src/cub/cli/task.py, src/cub/cli/ledger.py, .claude/commands/cub:tasks.md, .claude/commands/cub:ledger.md

---

### Task: cub-a4e.3 - Add --agent support for doctor command (requires refactor)

Priority: 2
Labels: phase-4, model:sonnet, complexity:medium

**Context**: The doctor command currently prints directly via Rich console. To support `--agent`, it needs to return structured diagnostic results instead. This is a refactor of the existing doctor command internals, not just adding a flag.

**Implementation Steps**:
1. Define `DiagnosticResult` model (or use existing if one exists):
   - `severity: str` (error, warning, info)
   - `check: str` (what was checked)
   - `status: str` (pass, fail, description)
   - `fix: str | None` (suggested fix command)
2. Refactor doctor command to collect `list[DiagnosticResult]` before rendering
3. Add `format_doctor(checks: list[DiagnosticResult])` to AgentFormatter:
   - Summary: `{N} issues found: {errors} errors, {warnings} warnings, {infos} info.`
   - Issues table: Severity, Check, Status, Fix
   - Analysis: prioritized action items
4. Add `--agent` flag to `cub doctor` command
5. If agent: call `AgentFormatter.format_doctor(checks)`, print
6. Ensure existing Rich output is unchanged when `--agent` is not passed
7. Update `cub:doctor.md` skill to use `--agent`
8. Write tests for both the refactored data collection and agent formatting

**Acceptance Criteria**:
- [ ] Doctor command collects structured `DiagnosticResult` list before rendering
- [ ] Existing Rich output is unchanged (no regression)
- [ ] `cub doctor --agent` outputs structured markdown
- [ ] `format_doctor` produces correct output
- [ ] Skill file updated
- [ ] Tests pass for both output modes

**Files**: src/cub/cli/doctor.py, src/cub/core/services/agent_format.py, .claude/commands/cub:doctor.md, tests/test_agent_format.py

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-a1f | 2 | P0 | AgentFormatter module + --agent flag on 4 core commands |
| cub-a2s | 1 | P1 | Passthrough skill and router updates to use --agent |
| cub-a3r | 3 | P1 | Route learning: observe, compile, surface |
| cub-a4e | 3 | P2 | Extended commands: blocked, list, ledger, doctor |

**Total**: 4 epics, 9 tasks

**Ready to start immediately**: cub-a1f.1 (AgentFormatter module) — no dependencies on other specs

**Cross-spec dependency**: DependencyGraph from cub-task-parity (cub-p1t.4) enhances analysis sections but is not required. AgentFormatter works without it.

**Dependency chain**:
```
cub-a1f.1 (AgentFormatter) ── cub-a1f.2 (CLI --agent flags)
                                    │
                              [CHECKPOINT: core working]
                                    │
                        ┌───────────┴───────────┐
                        │                       │
                  cub-a2s.1                cub-a3r.1 (hook obs)
                  (skill updates)               │
                        │                  cub-a3r.2 (compiler)
                        │                       │
                  [CHECKPOINT:             cub-a3r.3 (router ref)
                   full loop]                   │
                        │               [CHECKPOINT:
                        │                route learning]
                        │
                  cub-a4e.1 (format methods)
                        │
                  cub-a4e.2 (CLI wiring)
                        │
                  cub-a4e.3 (doctor refactor)
```
