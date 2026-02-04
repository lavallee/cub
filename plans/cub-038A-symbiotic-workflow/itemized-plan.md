# Itemized Plan: Symbiotic Workflow

> Source: [symbiotic-workflow.md](../../specs/researching/symbiotic-workflow.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-28

## Context Summary

When developers work directly in Claude Code instead of through `cub run`, cub has no visibility into what happened. This creates learning degradation, capability asymmetry, and cognitive overhead. The symbiotic workflow adds an observation layer via Claude Code hooks that feeds events into the same task and ledger systems that `cub run` uses, making the mode of work invisible to the tracking infrastructure.

**Mindset:** Production | **Scale:** Personal

---

## Epic: cub-w3f - symbiotic-workflow #1: Hook Pipeline and Session Forensics

Priority: 0
Labels: phase-1, infrastructure, hooks

Build the observation layer: shell fast-path filter, Python event handlers, session forensics logging, and hook configuration installer. After this phase, events from direct Claude Code sessions are observed and recorded to forensics JSONL.

### Task: cub-w3f.1 - Implement shell hook filter script

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, hooks, risk:medium
Blocks: cub-w3f.4

**Context**: The shell script is the fast-path gate for all hook events. It must parse stdin JSON quickly, check relevance, and only invoke Python when needed. This keeps latency under 50ms for the 90%+ of tool uses that aren't relevant.

**Implementation Steps**:
1. Create template at `src/cub/templates/scripts/cub-hook.sh`
2. Accept hook event name as `$1`
3. Read stdin into a variable; save for potential passthrough
4. Check `CUB_RUN_ACTIVE` env var -- if set, exit 0 immediately
5. For PostToolUse: extract `tool_name` from JSON; if not Write/Edit/Bash, exit 0
6. For Write/Edit PostToolUse: extract `file_path` from `tool_input`; check if path contains `plans/`, `specs/`, `captures/`, `src/`, or `.cub/`
7. For Bash PostToolUse: extract `command` from `tool_input`; check for `cub `, `git commit`, `git add` patterns
8. For SessionStart/Stop/PreCompact/UserPromptSubmit: always pass through
9. If relevant: pipe saved stdin to `python -m cub.core.harness.hooks "$1"`
10. Use `jq` if available, fall back to grep/sed for JSON extraction

**Acceptance Criteria**:
- [ ] Script exits 0 without invoking Python when `CUB_RUN_ACTIVE` is set
- [ ] Script exits 0 for irrelevant PostToolUse events (e.g., Read, Glob)
- [ ] Script invokes Python for Write/Edit to tracked directories
- [ ] Script invokes Python for Bash commands matching task/git patterns
- [ ] Script passes through SessionStart/Stop/PreCompact/UserPromptSubmit unconditionally
- [ ] Script handles malformed JSON gracefully (exit 0, no crash)
- [ ] Works without `jq` installed (fallback parsing)

**Files**: src/cub/templates/scripts/cub-hook.sh, tests/test_hook_filter.py

---

### Task: cub-w3f.2 - Enhance Python hook handlers for forensics logging

Priority: 0
Labels: phase-1, model:sonnet, complexity:medium, hooks, ledger
Blocks: cub-w3f.4

**Context**: The existing `cub.core.harness.hooks` module has stub handlers that log to forensics but don't classify events or track session state. Enhance these to produce structured forensics records that Phase 2 can consume.

**Implementation Steps**:
1. Define forensics event types as Pydantic models: `session_start`, `file_write`, `task_claim`, `task_close`, `git_commit`, `session_end`, `session_checkpoint`, `task_mention`
2. Enhance `handle_session_start`: write `session_start` event with cwd, timestamp
3. Enhance `handle_post_tool_use`:
   - For Write/Edit: classify file path (plan/spec/capture/source/other), write `file_write` event with category
   - For Bash: parse command for `cub task close`, `cub task claim`, `git commit` patterns; write appropriate event type
4. Enhance `handle_stop`: write `session_end` event with transcript path
5. Add `handle_pre_compact`: write `session_checkpoint` event, start new forensics file (compaction == new session)
6. Add `handle_user_prompt_submit`: detect task ID patterns (e.g., `cub-\w+`, configurable prefix), write `task_mention` event
7. Ensure all handlers return proper `HookEventResult` JSON on stdout

**Acceptance Criteria**:
- [ ] SessionStart writes structured `session_start` event to forensics JSONL
- [ ] PostToolUse (Write/Edit) classifies file paths and writes `file_write` events with category
- [ ] PostToolUse (Bash) detects `cub task close/claim` and `git commit` commands
- [ ] Stop writes `session_end` event with transcript path
- [ ] PreCompact checkpoints session state and starts new session
- [ ] UserPromptSubmit detects task ID patterns
- [ ] All events include timestamp, session_id
- [ ] Malformed payloads handled gracefully (no crash, exit 0)

**Files**: src/cub/core/harness/hooks.py, tests/test_harness_hooks.py

---

### Task: cub-w3f.3 - Add CUB_RUN_ACTIVE environment variable to harness backends

Priority: 1
Labels: phase-1, model:haiku, complexity:low, harness

**Context**: When `cub run` invokes Claude Code, the hooks must not fire (double-tracking prevention). The simplest signal is an env var set by the harness backends before launching the subprocess.

**Implementation Steps**:
1. In `claude_sdk.py`: set `CUB_RUN_ACTIVE=1` in the environment before invoking the SDK
2. In `claude_cli.py`: set `CUB_RUN_ACTIVE=1` in the subprocess environment dict
3. Ensure the env var is not set by non-Claude harnesses (Codex, Gemini don't have hooks)

**Acceptance Criteria**:
- [ ] Claude SDK backend sets `CUB_RUN_ACTIVE=1` in subprocess/SDK environment
- [ ] Claude CLI backend sets `CUB_RUN_ACTIVE=1` in subprocess environment
- [ ] Codex/Gemini backends do NOT set this env var
- [ ] Existing harness tests pass (no behavioral change to execution)

**Files**: src/cub/core/harness/claude_sdk.py, src/cub/core/harness/claude_cli.py, tests/test_claude_harness.py

---

### Task: cub-w3f.4 - Implement hook configuration installer

Priority: 1
Labels: phase-1, model:sonnet, complexity:medium, hooks, setup, risk:medium
Blocks: cub-w3f.5

**Context**: The hook shell script and Python handlers need to be wired into Claude Code via `.claude/settings.json`. This installer handles creating/merging the configuration without clobbering existing user content.

**Implementation Steps**:
1. Create `src/cub/core/hooks/__init__.py` and `src/cub/core/hooks/installer.py`
2. Define `HookInstallResult` and `HookIssue` Pydantic models
3. Implement `install_hooks(project_dir, force=False) -> HookInstallResult`:
   - Read existing `.claude/settings.json` if present
   - Parse existing hooks section; preserve non-cub hooks
   - Merge cub hook entries (SessionStart, PostToolUse Write|Edit, PostToolUse Bash, Stop, PreCompact, UserPromptSubmit)
   - Write `.claude/settings.json` atomically (temp + rename)
   - Copy shell script template to `.cub/scripts/hooks/cub-hook.sh`
   - Make shell script executable (`chmod +x`)
4. Implement `validate_hooks(project_dir) -> list[HookIssue]`:
   - Check `.claude/settings.json` exists and is valid JSON
   - Check all required cub hook events are configured
   - Check shell script exists and is executable
   - Check Python module is importable
5. Implement `uninstall_hooks(project_dir) -> None`:
   - Remove cub hook entries from `.claude/settings.json`, preserve non-cub hooks
   - Remove `.cub/scripts/hooks/cub-hook.sh`

**Acceptance Criteria**:
- [ ] Installs hooks into fresh project (no existing `.claude/settings.json`)
- [ ] Merges hooks into existing `.claude/settings.json` without clobbering non-cub entries
- [ ] Shell script installed to `.cub/scripts/hooks/` and made executable
- [ ] `validate_hooks` reports missing/broken hooks with actionable messages
- [ ] `uninstall_hooks` removes cub hooks but preserves non-cub hooks
- [ ] Handles malformed `.claude/settings.json` gracefully (warns, doesn't crash)

**Files**: src/cub/core/hooks/__init__.py, src/cub/core/hooks/installer.py, tests/test_hook_installer.py

---

### Task: cub-w3f.5 - Integrate hook installation into cub init and cub doctor

Priority: 2
Labels: phase-1, model:sonnet, complexity:medium, cli, setup

**Context**: `cub init` should offer to install Claude Code hooks as part of project setup. `cub doctor` should validate hook health. These are the natural entry and diagnostic points for users.

**Implementation Steps**:
1. Add `--hooks` flag to `cub init` (explicit opt-in)
2. During init, if Claude Code is detected (`.claude/` dir exists or `claude` in PATH): suggest hook installation
3. Call `install_hooks()` from the installer module
4. Report installation result to user via Rich output
5. In `cub doctor`: add hook validation section calling `validate_hooks()`
6. Report hook status and suggest fixes for any issues

**Acceptance Criteria**:
- [ ] `cub init --hooks` installs Claude Code hooks
- [ ] `cub init` suggests hooks when Claude Code is detected
- [ ] Installation result reported clearly with Rich formatting
- [ ] `cub doctor` reports hook installation status
- [ ] `cub doctor` suggests fixes for broken hooks
- [ ] Works in both fresh init and re-init scenarios

**Files**: src/cub/cli/init_cmd.py, src/cub/cli/doctor.py, tests/test_init.py, tests/test_doctor.py

---

> **Checkpoint**: After Phase 1, direct Claude Code sessions produce forensics JSONL in `.cub/ledger/forensics/`. Hooks are installed and filtering correctly. User can verify by running a Claude Code session and checking for forensics output.

---

## Epic: cub-v8n - symbiotic-workflow #2: Session Ledger Integration

Priority: 1
Labels: phase-2, ledger, integration

Connect hook events to the ledger system so direct session work produces real ledger entries. Decouple ledger integration from the run loop so it works from either path.

### Task: cub-v8n.1 - Implement SessionLedgerIntegration

Priority: 0
Labels: phase-2, model:sonnet, complexity:high, ledger, logic
Blocks: cub-v8n.2, cub-v8n.3, cub-v8n.4

**Context**: The current `LedgerIntegration` class is designed for the run loop: it expects `on_task_start` with a full Task object, then a sequence of attempts, then `on_task_close`. Direct sessions are different -- events arrive incrementally across separate process invocations, task association may happen mid-session, and we synthesize the ledger entry at session end from the forensics log.

**Implementation Steps**:
1. Create `src/cub/core/ledger/session_integration.py`
2. Implement `SessionLedgerIntegration` class with methods:
   - `on_session_start(session_id, cwd)` -- initialize tracking state
   - `on_file_write(session_id, file_path, tool_name)` -- categorize (plan/spec/capture/source) and record
   - `on_task_claim(session_id, task_id)` -- associate session with task, fetch task snapshot from backend
   - `on_task_close(session_id, task_id, reason)` -- record closure event
   - `on_git_commit(session_id, commit_hash, message)` -- record commit
   - `on_session_end(session_id, transcript_path)` -- synthesize LedgerEntry from accumulated events
   - `enrich_from_transcript(session_id, transcript_path)` -- parse transcript for token/cost
3. State reconstruction: each method reads the forensics JSONL to rebuild session state (stateless process model)
4. `on_session_end` should:
   - Read all forensics events for this session
   - Build LedgerEntry with: task snapshot, files_changed, commits, outcome
   - Create synthetic Attempt with harness="direct-session", model="interactive"
   - Set source="direct-session" in state history for traceability
   - Write via `LedgerWriter.create_entry()` or `update_entry()`
5. If no task was claimed: finalize forensics only, skip ledger entry

**Acceptance Criteria**:
- [ ] Session with task claim produces valid LedgerEntry on session end
- [ ] Session without task claim does not produce ledger entry (only forensics)
- [ ] File writes categorized correctly (plan/spec/capture/source)
- [ ] Git commits recorded as CommitRef in ledger entry
- [ ] LedgerEntry compatible with existing ledger reader/queries
- [ ] Multiple concurrent sessions (different session_ids) don't interfere
- [ ] State correctly reconstructed from forensics log across separate process invocations

**Files**: src/cub/core/ledger/session_integration.py, tests/test_session_ledger_integration.py

---

### Task: cub-v8n.2 - Connect hook handlers to SessionLedgerIntegration

Priority: 1
Labels: phase-2, model:sonnet, complexity:medium, hooks, ledger, logic

**Context**: Hook handlers currently write raw forensics. They need to also drive the `SessionLedgerIntegration` so events flow through to the ledger on session end.

**Implementation Steps**:
1. In `handle_session_start`: instantiate `SessionLedgerIntegration`, call `on_session_start()`
2. In `handle_post_tool_use`: after writing forensics, call `on_file_write()`, `on_task_close()`, or `on_git_commit()` as appropriate
3. In `handle_stop`: call `on_session_end()` which reconstructs state from forensics and synthesizes ledger entry
4. Each hook invocation is a separate process -- `SessionLedgerIntegration` reconstructs from forensics JSONL each time
5. Ensure `LedgerWriter` is properly initialized with project directory from hook payload `cwd`

**Acceptance Criteria**:
- [ ] PostToolUse events flow through to SessionLedgerIntegration
- [ ] Stop handler triggers session finalization and ledger entry creation
- [ ] Session state correctly reconstructed from forensics log across hook invocations
- [ ] Ledger entries appear in `cub ledger show` output
- [ ] No errors on sessions with partial data (e.g., missing cwd)

**Files**: src/cub/core/harness/hooks.py, tests/test_harness_hooks_integration.py

---

### Task: cub-v8n.3 - Implement transcript parsing for enrichment

Priority: 2
Labels: phase-2, model:sonnet, complexity:medium, ledger, logic

**Context**: Claude Code provides the transcript path in hook payloads. Parsing it post-session can extract token usage, cost, and model info that hooks themselves can't observe. This closes the gap between `cub run` (which gets token data from the harness) and direct sessions.

**Implementation Steps**:
1. Create `src/cub/core/ledger/transcript_parser.py`
2. Parse Claude Code transcript format (JSONL with message events)
3. Extract: total input/output tokens, cache tokens, model name, approximate cost, number of turns
4. Map extracted data to `TokenUsage` and `Attempt` model fields
5. Implement `enrich_from_transcript()` in SessionLedgerIntegration: update existing ledger entry with parsed data
6. Call from Stop handler after initial ledger entry creation (best-effort enrichment)
7. Handle missing, unreadable, or unexpected transcript formats gracefully

**Acceptance Criteria**:
- [ ] Parses Claude Code transcript JSONL format
- [ ] Extracts token usage (input, output, cache_read, cache_creation)
- [ ] Extracts model name used in session
- [ ] Updates existing ledger entry with extracted data via LedgerWriter
- [ ] Handles missing/malformed transcripts without error (best-effort)

**Files**: src/cub/core/ledger/transcript_parser.py, tests/test_transcript_parser.py

---

### Task: cub-v8n.4 - Refactor cub session done to use SessionLedgerIntegration

Priority: 2
Labels: phase-2, model:sonnet, complexity:low, cli, refactor

**Context**: `cub session done` currently creates ledger entries with ad-hoc code that duplicates the LedgerEntry construction logic. Refactor to use `SessionLedgerIntegration` for a single code path.

**Implementation Steps**:
1. Refactor `session.py` `done` command to instantiate `SessionLedgerIntegration`
2. Create a synthetic session: call `on_session_start`, `on_task_claim`, `on_task_close`, `on_session_end`
3. Remove the existing inline LedgerEntry construction code
4. Ensure backward compatibility: same CLI interface, same output messages, same ledger entry format

**Acceptance Criteria**:
- [ ] `cub session done <task-id>` produces equivalent ledger entry format
- [ ] Code path uses `SessionLedgerIntegration` instead of ad-hoc construction
- [ ] Existing session tests pass without modification
- [ ] Output messages unchanged

**Files**: src/cub/cli/session.py, tests/test_session.py

---

> **Checkpoint**: After Phase 2, direct Claude Code sessions produce real ledger entries. A user can work in Claude Code, close a task, and see the result in `cub ledger show`. Token/cost data is enriched from transcripts.

---

## Epic: cub-q2j - symbiotic-workflow #3: Task Backend and Instructions

Priority: 2
Labels: phase-3, tasks, instructions

JSON backend reaches full parity with beads. `cub task` CLI provides task management from any context. Instructions guide direct session workflow.

### Task: cub-q2j.1 - Add branch binding to JSON task backend

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, tasks, logic

**Context**: `bind_branch()` returns False in the JSON backend, blocking `cub branch` and `cub pr` for JSON-only users. Store bindings in `.cub/branches.json` with the same semantics as beads' `.beads/branches.yaml`.

**Implementation Steps**:
1. Create `src/cub/core/branches/json_store.py` following the pattern of the existing beads BranchStore
2. Define binding model: `epic_id`, `branch_name`, `base_branch`, `created_at`
3. Implement `get_binding(epic_id)`, `get_binding_by_branch(branch_name)`, `add_binding()`, `remove_binding()`
4. Storage: `.cub/branches.json` with atomic writes (temp + replace)
5. Wire into JSON backend's `bind_branch()` method
6. Update `cub branch` and `cub branches` commands to work with JSON backend's branch store

**Acceptance Criteria**:
- [ ] `bind_branch()` creates binding in `.cub/branches.json` and returns True
- [ ] Returns False if binding already exists for that epic
- [ ] `cub branch <epic>` works with JSON backend
- [ ] `cub branches` lists bindings from JSON backend
- [ ] Bindings persist across process restarts
- [ ] Atomic writes prevent corruption on concurrent access

**Files**: src/cub/core/branches/json_store.py, src/cub/core/tasks/json.py, tests/test_json_backend.py

---

### Task: cub-q2j.2 - Add cub task CLI subcommand

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, cli
Blocks: cub-q2j.3

**Context**: Direct sessions need lightweight task commands callable from Bash tool use. `cub task ready`, `cub task claim`, `cub task close`, `cub task create`. These wrap the task backend protocol and work identically with JSON or beads.

**Implementation Steps**:
1. Create `src/cub/cli/task.py` with Typer app and subcommands:
   - `cub task ready [--parent] [--label]` -- list ready tasks with Rich table output
   - `cub task claim <task-id>` -- set status to in_progress, print confirmation
   - `cub task close <task-id> [--reason]` -- close task in backend + create ledger entry via SessionLedgerIntegration
   - `cub task create <title> [--type] [--priority] [--parent] [--description]` -- create task, print new ID
   - `cub task show <task-id>` -- show task details with Rich formatting
   - `cub task list [--status] [--parent] [--label]` -- list tasks with filters
2. Register as `app.add_typer(task.app, name="task")` in `src/cub/cli/__init__.py`
3. Output concise for machine consumption; use `--json` flag for structured output

**Acceptance Criteria**:
- [ ] `cub task ready` lists tasks with no blockers
- [ ] `cub task claim <id>` sets status to in_progress and prints confirmation
- [ ] `cub task close <id>` closes task and creates ledger entry
- [ ] `cub task create <title>` creates new task and prints ID
- [ ] `cub task show <id>` displays task details
- [ ] All commands work with both JSON and beads backends
- [ ] `--json` flag produces machine-parseable output

**Files**: src/cub/cli/task.py, src/cub/cli/__init__.py, tests/test_task_cli.py

---

### Task: cub-q2j.3 - Update AGENTS.md and CLAUDE.md generation

Priority: 1
Labels: phase-3, model:sonnet, complexity:medium, instructions

**Context**: Current AGENTS.md tells agents to use `bd` commands. It needs to use `cub task` commands instead, and include guidance for task claiming at session start and plan capture.

**Implementation Steps**:
1. Update `generate_agents_md()` in `instructions.py`:
   - Replace `bd ready` with `cub task ready`
   - Replace `bd update <id> --status in_progress` with `cub task claim <id>`
   - Replace `bd close <id>` with `cub task close <id> --reason "..."`
   - Add session workflow section: "At session start, check `cub task ready` and claim a task"
   - Add plan capture: "Save plans to `plans/<name>/plan.md`"
2. Update `generate_claude_md()`:
   - Reference updated AGENTS.md workflow
   - Add note about hooks tracking work automatically
3. Remove or mark remaining `bd` references as legacy fallback

**Acceptance Criteria**:
- [ ] AGENTS.md uses `cub task` commands, not `bd` commands
- [ ] Includes task claiming guidance at session start
- [ ] Includes plan capture guidance
- [ ] CLAUDE.md references updated workflow and mentions hooks
- [ ] Existing instruction generation tests updated to match new content

**Files**: src/cub/core/instructions.py, tests/test_instructions.py

---

### Task: cub-q2j.4 - SessionStart hook injects project context

Priority: 2
Labels: phase-3, model:sonnet, complexity:medium, hooks

**Context**: When a direct Claude Code session starts, the SessionStart hook should inject available tasks and project context as `additionalContext`. This gives the harness ambient awareness of project state without the user having to ask.

**Implementation Steps**:
1. In `handle_session_start`: load task backend from project config
2. Query `backend.get_ready_tasks()` (top 5-10 by priority)
3. Query `backend.list_tasks(status="in_progress")` for resumed session awareness
4. Build concise context string: project name, ready tasks (ID + title + priority), in-progress tasks, active epic
5. Return as `additionalContext` in `HookEventResult.hook_specific`
6. Keep context under 500 tokens to avoid bloating conversation

**Acceptance Criteria**:
- [ ] SessionStart returns `additionalContext` with ready tasks summary
- [ ] Context includes task IDs, titles, and priorities
- [ ] Context is concise (under 500 tokens)
- [ ] Handles empty task list gracefully (still returns context with project name)
- [ ] Handles backend errors gracefully (returns empty context, not error)

**Files**: src/cub/core/harness/hooks.py, tests/test_harness_hooks.py

---

### Task: cub-q2j.5 - UserPromptSubmit hook for task ID detection

Priority: 3
Labels: phase-3, model:haiku, complexity:low, hooks

**Context**: When a user mentions a task ID in their prompt (e.g., "work on cub-042"), the hook should detect it and inject task details as context, reducing the need for manual lookup.

**Implementation Steps**:
1. In `handle_user_prompt_submit`: extract task ID patterns from `payload.prompt`
2. Pattern: configurable prefix from project config + number (e.g., `cub-\d+`, `proj-\w+`)
3. Query task backend for matching task
4. If found: return task details (title, description, acceptance criteria) as `additionalContext`
5. If not found or already in-progress: return empty context

**Acceptance Criteria**:
- [ ] Detects task IDs in user prompt text
- [ ] Injects task details (title, description, acceptance criteria) as `additionalContext`
- [ ] Handles non-existent task IDs gracefully (no error, no context injected)
- [ ] Pattern configurable via project prefix

**Files**: src/cub/core/harness/hooks.py, tests/test_harness_hooks.py

---

> **Checkpoint**: After Phase 3, the JSON backend is a full drop-in for beads. `cub task` commands work from any context. AGENTS.md guides harnesses to use cub's task workflow. SessionStart injects project context into direct sessions.

---

## Epic: cub-r9d - symbiotic-workflow #4: Reconciliation and Polish

Priority: 3
Labels: phase-4, polish, validation

Handle edge cases, provide manual recovery paths, and validate end-to-end parity between `cub run` and direct sessions.

### Task: cub-r9d.1 - Implement cub reconcile command

Priority: 2
Labels: phase-4, model:sonnet, complexity:medium, cli, logic

**Context**: For sessions where hooks didn't fire or partially failed, `cub reconcile` processes forensics logs and git history to reconstruct ledger entries after the fact.

**Implementation Steps**:
1. Create `src/cub/cli/reconcile.py` with Typer command
2. Scan `.cub/ledger/forensics/` for session JSONL files
3. For each file: check if a corresponding ledger entry exists (by session_id or task_id)
4. For unprocessed sessions: replay events through `SessionLedgerIntegration.on_session_end()`
5. Optionally scan `git log` for commits not associated with any ledger entry (orphaned work)
6. Report reconciliation results via Rich table
7. Ensure idempotency: running twice doesn't create duplicate entries

**Acceptance Criteria**:
- [ ] Processes orphaned forensics logs into ledger entries
- [ ] Detects commits not associated with ledger entries
- [ ] Reports reconciliation results clearly
- [ ] Idempotent (running twice produces same result)

**Files**: src/cub/cli/reconcile.py, src/cub/cli/__init__.py, tests/test_reconcile.py

---

### Task: cub-r9d.2 - Add hook validation to cub doctor

Priority: 2
Labels: phase-4, model:haiku, complexity:low, cli

**Context**: `cub doctor` should report on hook installation status so users can diagnose integration issues without manual inspection.

**Implementation Steps**:
1. Add "Hooks" section to `cub doctor` output
2. Call `validate_hooks()` from installer module
3. Report: hooks installed?, shell script present and executable?, Python module importable?, all hook events configured?
4. For each issue: suggest specific fix command

**Acceptance Criteria**:
- [ ] `cub doctor` reports hook installation status
- [ ] Reports specific issues with actionable fix suggestions
- [ ] Works gracefully when hooks are not installed (reports "not configured" not "error")

**Files**: src/cub/cli/doctor.py, tests/test_doctor.py

---

### Task: cub-r9d.3 - End-to-end integration tests

Priority: 2
Labels: phase-4, model:sonnet, complexity:high, test

**Context**: Simulate a complete direct Claude Code session via hook event payloads and verify the output is structurally equivalent to what `cub run` produces. This is the parity validation.

**Implementation Steps**:
1. Create `tests/integration/test_symbiotic_workflow.py`
2. Simulate hook event sequence: SessionStart -> PostToolUse (Write plan file) -> PostToolUse (Bash git commit) -> PostToolUse (Bash cub task close) -> Stop
3. Verify: forensics log created with correct events, ledger entry created with task snapshot + files + commits + outcome
4. Compare ledger entry structure with one produced by the `cub run` path (same required fields populated)
5. Test edge cases: session with no task claimed, session with multiple task claims, session interrupted before Stop (no ledger entry, forensics recoverable)

**Acceptance Criteria**:
- [ ] Full session simulation produces valid LedgerEntry
- [ ] Ledger entry has same required fields as `cub run` entries
- [ ] No-task session produces only forensics (no ledger entry)
- [ ] Multiple concurrent sessions (different session_ids) don't interfere
- [ ] Interrupted session leaves recoverable forensics for `cub reconcile`

**Files**: tests/integration/test_symbiotic_workflow.py

---

### Task: cub-r9d.4 - Documentation updates

Priority: 3
Labels: phase-4, model:haiku, complexity:low, docs

**Context**: Update project documentation to reflect the symbiotic workflow capability so users and future agents understand the integration.

**Implementation Steps**:
1. Update CLAUDE.md with symbiotic workflow section: what it does, how hooks work, session tracking
2. Add hook system and `.cub/scripts/hooks/` to project structure docs
3. Document `cub task` subcommands with examples
4. Document `cub reconcile` command with examples
5. Add troubleshooting section for common hook issues (not installed, wrong permissions, etc.)

**Acceptance Criteria**:
- [ ] CLAUDE.md documents hook system and session tracking
- [ ] `cub task` commands documented with usage examples
- [ ] `cub reconcile` documented with usage examples
- [ ] Troubleshooting guide covers common hook issues

**Files**: CLAUDE.md, README.md

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-w3f | 5 | P0 | Hook pipeline: shell filter, Python handlers, installer, init integration |
| cub-v8n | 4 | P1 | Ledger integration: SessionLedgerIntegration, hook wiring, transcript parsing |
| cub-q2j | 5 | P2 | Task backend parity, cub task CLI, updated instructions, context injection |
| cub-r9d | 4 | P3 | Reconciliation, doctor validation, integration tests, documentation |

**Total**: 4 epics, 18 tasks
