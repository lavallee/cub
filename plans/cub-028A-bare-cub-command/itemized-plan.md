# Itemized Plan: Bare Cub Command & In-Harness Mode Fluidity

> Source: [bare-cub-command.md](../../specs/researching/bare-cub-command.md)
> Orient: [orientation.md](./orientation.md) | Architect: [architecture.md](./architecture.md)
> Generated: 2026-01-28

## Context Summary

Cub's value is invisible when developers work directly in a harness. This plan refactors cub from CLI-first to core-first, makes bare `cub` the unified entry point that launches a harness with opinionated guidance, and builds a suggestion engine that recommends next actions based on project state.

**Mindset:** Production | **Scale:** Personal → Team

---

## Epic: cub-orphan-00 - bare-cub #1: Core Run Extraction

Priority: 0
Labels: phase-1, core, refactor, risk:high

Extract ~2500 lines of business logic from `cli/run.py` into a new `core/run/` package. This is the highest-risk, highest-impact phase — it establishes the pattern that every subsequent phase follows. All existing tests must continue passing after each extraction step.

### Task: cub-orphan-00.1 - Create core/run package with prompt builder extraction

Priority: 0
Labels: phase-1, core, refactor, model:opus, complexity:high, blocking
Blocks: cub-orphan-00.2, cub-orphan-00.3, cub-orphan-00.4, cub-orphan-00.5

**Context**: The prompt builder (system prompt generation, task context injection, AGENT.md reading) is the most self-contained piece of `cli/run.py` and the safest to extract first. It establishes the `core/run/` package structure.

**Implementation Steps**:
1. Create `src/cub/core/run/__init__.py` package
2. Create `src/cub/core/run/prompt_builder.py` — extract `generate_system_prompt()`, `_build_task_context()`, `_read_agent_md()`, and related functions from `cli/run.py`
3. Define `PromptConfig` and `TaskPrompt` data models for inputs/outputs
4. Update `cli/run.py` to import from `core/run/prompt_builder` instead of using local functions
5. Ensure all existing run tests pass unchanged
6. Add unit tests for prompt builder in isolation

**Acceptance Criteria**:
- [ ] `core/run/prompt_builder.py` exists with all prompt generation logic
- [ ] `cli/run.py` calls prompt builder from core, no local prompt logic remains
- [ ] `pytest tests/` passes with no regressions
- [ ] `mypy src/cub` passes clean
- [ ] No Rich imports in `core/run/`

**Files**: src/cub/core/run/__init__.py, src/cub/core/run/prompt_builder.py, src/cub/cli/run.py, tests/test_run_prompt_builder.py

---

### Task: cub-orphan-00.2 - Extract budget tracking to core/run/budget.py

Priority: 0
Labels: phase-1, core, refactor, model:sonnet, complexity:medium

**Context**: Budget tracking (token counting, cost accounting, limit enforcement) is business logic embedded in the run loop. It needs to be accessible to any interface that runs tasks.

**Implementation Steps**:
1. Create `src/cub/core/run/budget.py` with `BudgetManager` class
2. Extract token tracking, cost accumulation, and limit checking from `cli/run.py`
3. Define `BudgetConfig` (limits) and `BudgetState` (current usage) models
4. Add `check_limit()` method that returns whether to continue or stop
5. Update `cli/run.py` to use `BudgetManager` instead of inline tracking
6. Write tests for budget limit enforcement

**Acceptance Criteria**:
- [ ] `BudgetManager` handles all token/cost tracking
- [ ] Budget limits trigger clean stops with clear reasons
- [ ] `cli/run.py` has no inline budget math
- [ ] Tests cover: under budget, at budget, over budget, no budget set

**Files**: src/cub/core/run/budget.py, src/cub/cli/run.py, tests/test_run_budget.py

---

### Task: cub-orphan-00.3 - Extract loop state machine to core/run/loop.py

Priority: 0
Labels: phase-1, core, refactor, model:opus, complexity:high, risk:high

**Context**: The run loop state machine (pick task → execute → record → next) is the core of cub. Extracting it cleanly is the hardest part of this phase — it touches task selection, harness invocation, result recording, and error handling.

**Implementation Steps**:
1. Create `src/cub/core/run/loop.py` with `RunLoop` class
2. Define `RunConfig` model (all loop configuration: once, epic, harness, etc.)
3. Define `RunEvent` enum/model for loop events (task_start, task_end, budget_update, error, complete)
4. Implement `execute()` as a generator that yields `RunEvent` objects
5. Move task selection, harness invocation coordination, and result recording into `RunLoop`
6. Keep signal handling and Rich rendering in `cli/run.py`
7. `cli/run.py` becomes: parse args → create `RunConfig` → iterate `RunLoop.execute()` → render events

**Acceptance Criteria**:
- [ ] `RunLoop.execute()` yields `RunEvent` stream, no print/console output
- [ ] `cli/run.py` reduced to <500 lines (arg parsing + event rendering)
- [ ] `cub run --once` works end-to-end through the new architecture
- [ ] `cub run` (multi-task) works end-to-end
- [ ] All existing run tests pass
- [ ] `mypy` passes clean

**Files**: src/cub/core/run/loop.py, src/cub/core/run/models.py, src/cub/cli/run.py, tests/test_run_loop.py

---

### Task: cub-orphan-00.4 - Extract interrupt handling to core/run/interrupt.py

Priority: 1
Labels: phase-1, core, refactor, model:sonnet, complexity:medium

**Context**: Signal handling (SIGINT/SIGTERM) for clean shutdown needs to work regardless of which interface is driving the run loop. The interrupt handler should coordinate with the loop state machine.

**Implementation Steps**:
1. Create `src/cub/core/run/interrupt.py` with `InterruptHandler` class
2. Extract signal registration and `_interrupted` flag logic from `cli/run.py`
3. Implement cooperative interruption: handler sets flag, loop checks flag between tasks
4. Add `on_interrupt` callback for cleanup (artifact finalization, ledger entry)
5. Update `RunLoop` to check interrupt state between iterations

**Acceptance Criteria**:
- [ ] `InterruptHandler` manages SIGINT/SIGTERM registration
- [ ] Interrupts cause clean shutdown between tasks (not mid-task)
- [ ] Artifacts and ledger entries are finalized on interrupt
- [ ] Works when called from CLI or programmatically

**Files**: src/cub/core/run/interrupt.py, src/cub/core/run/loop.py, src/cub/cli/run.py, tests/test_run_interrupt.py

---

### Task: cub-orphan-00.5 - Extract git operations to core/run/git_ops.py

Priority: 1
Labels: phase-1, core, refactor, model:sonnet, complexity:medium

**Context**: Branch creation, commit tracking, and other git operations during `cub run` are business logic that should be accessible from any interface.

**Implementation Steps**:
1. Create `src/cub/core/run/git_ops.py` with run-specific git functions
2. Extract `_create_branch_from_base()`, `_get_gh_issue_title()`, `_get_epic_title()` from `cli/run.py`
3. Define clear interfaces: `create_run_branch(config) -> str`, `get_epic_context(epic_id) -> EpicContext`
4. Update `RunLoop` to call git_ops functions instead of inline logic
5. Write tests with mocked git operations

**Acceptance Criteria**:
- [ ] All git operations during run extracted to `core/run/git_ops.py`
- [ ] No git subprocess calls remain in `cli/run.py`
- [ ] Branch naming convention preserved
- [ ] Tests cover branch creation, epic title resolution

**Files**: src/cub/core/run/git_ops.py, src/cub/cli/run.py, tests/test_run_git_ops.py

---

### CHECKPOINT: Phase 1 Complete

After Phase 1:
- `cli/run.py` is a thin wrapper (<500 lines)
- `core/run/` package contains all business logic
- All existing tests pass
- `cub run` works identically from the user's perspective

---

## Epic: cub-orphan-01 - bare-cub #2: Rich Boundary Cleanup

Priority: 1
Labels: phase-2, core, refactor, cleanup

Remove all Rich imports from `cub.core` modules. Core returns structured data; CLI renders it. This establishes the architectural rule that enables non-CLI interfaces.

### Task: cub-orphan-01.1 - Move review reporter rendering to CLI layer

Priority: 1
Labels: phase-2, core, cleanup, model:sonnet, complexity:medium
Blocks: cub-orphan-01.5

**Context**: `core/review/reporter.py` is the heaviest Rich violator — it's ~90% Rich rendering. The data models already exist in `core/review/models.py`. We need to split data preparation from rendering.

**Implementation Steps**:
1. Audit `core/review/reporter.py` to identify data preparation vs rendering
2. Keep any data transformation logic in core; move to `core/review/formatter.py` if needed (returns structured data)
3. Create `cli/review/display.py` with all Rich rendering (Panel, Table, Text)
4. Update `cli/review.py` to call display functions instead of core reporter
5. Remove Rich imports from `core/review/reporter.py` (or delete if fully moved)
6. Update tests to verify data output, not rendered output

**Acceptance Criteria**:
- [ ] Zero Rich imports in `core/review/`
- [ ] `cli/review/display.py` handles all review rendering
- [ ] `cub review` command output unchanged from user's perspective
- [ ] Tests pass

**Files**: src/cub/core/review/reporter.py, src/cub/cli/review/display.py, src/cub/cli/review.py

---

### Task: cub-orphan-01.2 - Remove Rich from core/pr/service.py and core/worktree/parallel.py

Priority: 1
Labels: phase-2, core, cleanup, model:sonnet, complexity:medium
Blocks: cub-orphan-01.5

**Context**: Both modules use Rich Console for progress/status output. They should emit events or return data, letting the CLI layer handle display.

**Implementation Steps**:
1. In `core/pr/service.py`: replace `Console` usage with return values or Python logging
2. In `core/worktree/parallel.py`: replace progress output with callback/event pattern
3. Define callback protocols: `on_worker_start(task_id)`, `on_worker_complete(task_id, result)`
4. Update `cli/pr.py` and `cli/worktree.py` to provide Rich-based callbacks
5. Verify all PR and worktree commands work unchanged

**Acceptance Criteria**:
- [ ] Zero Rich imports in `core/pr/` and `core/worktree/`
- [ ] PR and worktree commands produce identical output
- [ ] Core modules use callbacks or return data for progress

**Files**: src/cub/core/pr/service.py, src/cub/core/worktree/parallel.py, src/cub/cli/pr.py, src/cub/cli/worktree.py

---

### Task: cub-orphan-01.3 - Move bash_delegate to CLI layer

Priority: 1
Labels: phase-2, core, cleanup, model:sonnet, complexity:low

**Context**: `core/bash_delegate.py` imports Rich Console and calls `sys.exit()`. It's purely a CLI concern — delegating commands to the bash version of cub.

**Implementation Steps**:
1. Move `core/bash_delegate.py` to `cli/delegated/runner.py`
2. Update imports in `cli/delegated.py` and `cli/__init__.py`
3. Remove `core/bash_delegate.py`
4. Verify delegated commands (prep, branch, etc.) still work

**Acceptance Criteria**:
- [ ] `core/bash_delegate.py` no longer exists
- [ ] Delegated commands work unchanged
- [ ] No Rich or sys.exit in any `core/` module

**Files**: src/cub/core/bash_delegate.py, src/cub/cli/delegated/runner.py, src/cub/cli/delegated.py

---

### Task: cub-orphan-01.4 - Replace Rich logging in core/harness/hooks.py

Priority: 1
Labels: phase-2, core, cleanup, model:haiku, complexity:low

**Context**: `core/harness/hooks.py` uses Rich for logging. It should use Python's standard `logging` module — hooks run in subprocess contexts where Rich may not be appropriate.

**Implementation Steps**:
1. Replace `from rich.console import Console` with `import logging`
2. Replace `console.print()` calls with `logger.info()`, `logger.debug()`, etc.
3. Configure logging format in hook entry point
4. Verify hook forensics still work correctly

**Acceptance Criteria**:
- [ ] Zero Rich imports in `core/harness/hooks.py`
- [ ] Hook logging works in subprocess contexts
- [ ] Forensics JSONL output unchanged

**Files**: src/cub/core/harness/hooks.py

---

### Task: cub-orphan-01.5 - Verify zero Rich imports in core and add CI gate

Priority: 1
Labels: phase-2, core, cleanup, model:haiku, complexity:low

**Context**: Final verification that the boundary is clean, plus a CI check to prevent regression.

**Implementation Steps**:
1. Run `grep -r "from rich" src/cub/core/` and verify zero results
2. Run `grep -r "import rich" src/cub/core/` and verify zero results
3. Add a test that programmatically checks no Rich imports in core
4. Verify `mypy src/cub` passes clean

**Acceptance Criteria**:
- [ ] `grep -r "from rich\|import rich" src/cub/core/` returns nothing
- [ ] Automated test enforces the boundary
- [ ] All commands work unchanged from user's perspective

**Files**: tests/test_architecture.py

---

### CHECKPOINT: Phase 2 Complete

After Phase 2:
- Zero Rich imports in `cub.core`
- The rule "core returns data, CLI renders it" is enforced
- All commands work identically

---

## Epic: cub-orphan-02 - bare-cub #3: Service Layer

Priority: 1
Labels: phase-3, core, architecture

Introduce `cub.core.services` as the public API surface. Services are thin orchestrators that compose domain operations. CLI modules are refactored to call services.

### Task: cub-orphan-02.1 - Create service layer foundation and RunService

Priority: 1
Labels: phase-3, core, architecture, model:opus, complexity:high, blocking
Blocks: cub-orphan-02.2, cub-orphan-02.3, cub-orphan-02.4

**Context**: RunService wraps the newly-extracted `core/run/` package, providing the clean API that CLI and future interfaces call. This establishes the service layer pattern.

**Implementation Steps**:
1. Create `src/cub/core/services/__init__.py` package
2. Create `src/cub/core/services/run.py` with `RunService` class
3. `RunService.from_config(config)` factory method
4. `RunService.execute(run_config) -> Iterator[RunEvent]` delegates to `core/run/loop.py`
5. `RunService.run_once(task_id) -> RunResult` convenience method
6. Refactor `cli/run.py` to use `RunService` instead of calling `core/run/` directly
7. Write service-level integration tests

**Acceptance Criteria**:
- [ ] `RunService` provides the complete API for task execution
- [ ] `cli/run.py` only calls `RunService`, not domain modules directly
- [ ] Service is stateless — configuration passed in, no globals
- [ ] Tests verify service orchestration

**Files**: src/cub/core/services/__init__.py, src/cub/core/services/run.py, src/cub/cli/run.py, tests/test_service_run.py

---

### Task: cub-orphan-02.2 - Create StatusService and LedgerService

Priority: 1
Labels: phase-3, core, architecture, model:sonnet, complexity:medium

**Context**: StatusService aggregates project state from multiple sources. LedgerService wraps ledger reader/writer. Both are needed by the suggestion engine.

**Implementation Steps**:
1. Create `src/cub/core/services/status.py` with `StatusService`
2. `summary() -> ProjectStats` — aggregate from tasks, ledger, git
3. `progress(epic_id) -> EpicProgress` — epic-level progress
4. Create `src/cub/core/services/ledger.py` with `LedgerService`
5. `query(filters) -> list[LedgerEntry]`, `recent(n) -> list[LedgerEntry]`, `stats(period) -> LedgerStats`
6. Define `ProjectStats`, `EpicProgress`, `LedgerStats` models
7. Refactor `cli/status.py` and `cli/ledger.py` to use services

**Acceptance Criteria**:
- [ ] `StatusService.summary()` returns structured project stats
- [ ] `LedgerService` wraps all ledger operations
- [ ] `cub status` and `cub ledger` commands work via services
- [ ] Models are Pydantic, serializable

**Files**: src/cub/core/services/status.py, src/cub/core/services/ledger.py, src/cub/core/services/models.py, src/cub/cli/status.py, src/cub/cli/ledger.py

---

### Task: cub-orphan-02.3 - Create LaunchService for environment detection and harness launch

Priority: 1
Labels: phase-3, core, architecture, model:sonnet, complexity:medium

**Context**: LaunchService handles the core logic for bare `cub`: detect environment, determine if nested, launch harness with context. This is the service that `cli/default.py` will call.

**Implementation Steps**:
1. Create `src/cub/core/launch/__init__.py` package
2. Create `src/cub/core/launch/detector.py` with `detect_environment() -> EnvironmentInfo`
3. Check `CUB_SESSION_ACTIVE`, `CLAUDE_CODE`, `CLAUDE_PROJECT_DIR` env vars
4. Create `src/cub/core/launch/launcher.py` with `launch_harness(config, context)`
5. Implement harness binary resolution, flag assembly, `exec` call
6. Create `src/cub/core/launch/models.py` with `EnvironmentInfo`, `LaunchConfig`
7. Create `src/cub/core/services/launch.py` with `LaunchService` wrapper
8. Write tests with mocked environment variables

**Acceptance Criteria**:
- [ ] `detect_environment()` correctly identifies terminal, harness, and nested contexts
- [ ] `launch_harness()` assembles correct `claude` CLI invocation
- [ ] `--resume` and `--continue` flags pass through correctly
- [ ] `CUB_SESSION_ACTIVE` and `CUB_SESSION_ID` set in child environment
- [ ] Tests cover all three environment contexts

**Files**: src/cub/core/launch/detector.py, src/cub/core/launch/launcher.py, src/cub/core/launch/models.py, src/cub/core/services/launch.py, tests/test_launch.py

---

### Task: cub-orphan-02.4 - Enhance TaskService with ready(), stale_epics(), and claims

Priority: 1
Labels: phase-3, core, architecture, model:sonnet, complexity:medium

**Context**: TaskService already exists but needs additional methods for the suggestion engine and welcome message. `ready()` and `stale_epics()` are key data sources for suggestions.

**Implementation Steps**:
1. Add `ready() -> list[Task]` to TaskService — tasks with no blockers, ordered by priority
2. Add `stale_epics() -> list[Epic]` — epics where all child tasks are closed but epic is open
3. Add `claim(task_id, session_id) -> Task` — mark task as in-progress for a session
4. Add `close(task_id, reason) -> Task` — close task with reason
5. Ensure methods work with both beads and JSONL backends
6. Write tests for each method with both backends

**Acceptance Criteria**:
- [ ] `TaskService.ready()` returns correctly filtered and ordered tasks
- [ ] `TaskService.stale_epics()` detects epics ready to close
- [ ] Works with beads and JSONL backends
- [ ] Tests cover edge cases (no tasks, all blocked, mixed states)

**Files**: src/cub/core/tasks/service.py, tests/test_task_service.py

---

### CHECKPOINT: Phase 3 Complete

After Phase 3:
- `cub.core.services` package exists with RunService, StatusService, LedgerService, LaunchService, TaskService
- CLI modules call services, not domain modules directly
- The pattern is established for adding new interfaces

---

## Epic: cub-orphan-03 - bare-cub #4: Suggestion Engine

Priority: 1
Labels: phase-4, core, feature

Build the smart recommendation system that analyzes project state and produces ranked, opinionated suggestions for what to do next.

### Task: cub-orphan-03.1 - Create suggestion models and data sources

Priority: 1
Labels: phase-4, core, feature, model:sonnet, complexity:medium, blocking
Blocks: cub-orphan-03.2, cub-orphan-03.3

**Context**: Define the data models for suggestions and implement the four data source adapters (tasks, git, ledger, milestones) that feed the ranking engine.

**Implementation Steps**:
1. Create `src/cub/core/suggestions/__init__.py` package
2. Create `src/cub/core/suggestions/models.py` with `Suggestion`, `ProjectSnapshot`, `SuggestionCategory` enum
3. Create `src/cub/core/suggestions/sources.py` with source protocol and implementations:
   - `TaskSource`: queries TaskService for ready tasks, stale epics, blocked work
   - `GitSource`: reads git log, checks for uncommitted changes, branch state
   - `LedgerSource`: queries LedgerService for recent completions, cost trends
   - `MilestoneSource`: reads CHANGELOG.md, pyproject.toml version, sketches for goal context
4. Each source implements `get_suggestions() -> list[Suggestion]`
5. Write tests with fixture data mirroring current cub project state

**Acceptance Criteria**:
- [ ] All four sources produce relevant suggestions from real project data
- [ ] `TaskSource` detects the 9 stale epics in current project
- [ ] `GitSource` detects unpushed work and stale branches
- [ ] `MilestoneSource` infers 0.30 alpha target from sketches/CHANGELOG
- [ ] Models are Pydantic, serializable

**Files**: src/cub/core/suggestions/models.py, src/cub/core/suggestions/sources.py, tests/test_suggestions_sources.py

---

### Task: cub-orphan-03.2 - Implement ranking algorithm and engine

Priority: 1
Labels: phase-4, core, feature, model:sonnet, complexity:medium

**Context**: The ranking algorithm scores and orders suggestions from all sources. The engine composes sources, applies ranking, and provides the public API.

**Implementation Steps**:
1. Create `src/cub/core/suggestions/ranking.py` with `rank_suggestions(suggestions) -> list[Suggestion]`
2. Implement scoring: `base_priority × urgency_multiplier × recency_decay`
3. Create `src/cub/core/suggestions/engine.py` with `SuggestionEngine` class
4. `get_suggestions(limit) -> list[Suggestion]` — ranked list
5. `get_welcome() -> WelcomeMessage` — stats + top suggestions + skills
6. `get_next_action() -> Suggestion` — single best recommendation
7. Write tests with deterministic fixture data to verify ranking order

**Acceptance Criteria**:
- [ ] Stale epic closure ranks above low-priority ready tasks
- [ ] P0 tasks rank above P2 tasks
- [ ] Milestone blockers rank high when release target detected
- [ ] `get_welcome()` produces a complete `WelcomeMessage` with stats
- [ ] Ranking is deterministic for same input

**Files**: src/cub/core/suggestions/ranking.py, src/cub/core/suggestions/engine.py, tests/test_suggestions_engine.py

---

### Task: cub-orphan-03.3 - Wire SuggestionEngine into services and dogfood

Priority: 1
Labels: phase-4, core, feature, model:sonnet, complexity:medium

**Context**: Connect the engine to real project data via services and validate it produces useful suggestions for the cub project itself.

**Implementation Steps**:
1. Create `src/cub/core/services/suggestions.py` as the service wrapper
2. Wire `SuggestionEngine` to use `TaskService`, `LedgerService`, `StatusService`
3. Add a CLI command for testing: `cub suggest` (or add to `cub status`)
4. Run against the current cub project and verify suggestions are sensible
5. Iterate on ranking weights based on dogfooding results
6. Document the suggestion categories and their use cases

**Acceptance Criteria**:
- [ ] `cub suggest` (or equivalent) produces useful output for cub project
- [ ] Suggestions include stale epics, ready tasks, and milestone awareness
- [ ] Output is human-readable and actionable
- [ ] Engine handles empty projects gracefully (new project with no tasks)

**Files**: src/cub/core/services/suggestions.py, src/cub/cli/suggest.py, tests/test_suggestions_integration.py

---

### CHECKPOINT: Phase 4 Complete

After Phase 4:
- SuggestionEngine produces ranked, opinionated recommendations
- Validated against real cub project data
- `cub suggest` command available for testing

---

## Epic: cub-orphan-04 - bare-cub #5: Bare Cub Command

Priority: 0
Labels: phase-5, cli, feature

Implement the default command handler — the user-facing deliverable. When someone types `cub` with no subcommand, it launches the default harness with an opinionated welcome.

### Task: cub-orphan-04.1 - Implement bare cub default command handler

Priority: 0
Labels: phase-5, cli, feature, model:opus, complexity:high, blocking
Blocks: cub-orphan-04.2, cub-orphan-04.3

**Context**: This is the primary user-facing deliverable. Bare `cub` detects the environment, generates a welcome message with suggestions, and either launches the harness (terminal) or shows inline status (nested/harness).

**Implementation Steps**:
1. Create `src/cub/cli/default.py` with the default command function
2. Wire into `cli/__init__.py`: replace `no_args_is_help=True` with callback that invokes default
3. Accept `--resume` and `--continue` flags
4. Call `LaunchService.detect_environment()` to determine context
5. If nested/harness: call `SuggestionEngine.get_welcome()`, render with Rich, exit
6. If terminal: generate welcome, resolve harness, launch with `LaunchService.launch_harness()`
7. Set `CUB_SESSION_ACTIVE=1` and `CUB_SESSION_ID` in launched harness environment
8. Handle edge cases: no harness available, no project initialized, help flag

**Acceptance Criteria**:
- [ ] `cub` (no args) launches Claude Code with welcome context
- [ ] `cub --resume` passes `--resume` to Claude Code
- [ ] `cub --continue` passes `--continue` to Claude Code
- [ ] `cub` inside Claude Code shows inline status + suggestions (no nesting)
- [ ] `cub` with no harness available shows helpful error
- [ ] `cub --help` still works (shows help, not default action)
- [ ] Welcome message includes project stats and top suggestion

**Files**: src/cub/cli/default.py, src/cub/cli/__init__.py, tests/test_default_command.py

---

### Task: cub-orphan-04.2 - Design and implement welcome message format

Priority: 1
Labels: phase-5, cli, feature, model:sonnet, complexity:medium

**Context**: The welcome message is the first thing users see. It needs to be concise, opinionated, and immediately useful. It renders differently in terminal (Rich formatting) vs inline (plain text for harness context).

**Implementation Steps**:
1. Create `src/cub/core/launch/welcome.py` with `generate_welcome(snapshot) -> WelcomeMessage`
2. Design terminal format (Rich):
   ```
   ╭─ cub · v0.28.0 ─────────────────────────────────╮
   │ 20 ready · 10 blocked · 316 completed            │
   │ 9 epics ready to close · Last commit: 2h ago     │
   ╰──────────────────────────────────────────────────╯

   Recommended: Close 9 completed epics
   → All tasks done. Run: bd close cub-r1a cub-r1b ...

   Other suggestions:
   → Work on cub-s041: Add cub upgrade command (P2)
   → Fix: remove "curb" reference in CHANGELOG

   Skills: /cub:spec · /cub:orient · /cub:architect · /cub:plan · /cub:capture
   ```
3. Design harness context format (plain text for system prompt injection)
4. Create Rich renderer in `cli/default.py` for terminal output
5. Test with current cub project state

**Acceptance Criteria**:
- [ ] Welcome message shows version, task counts, and last activity
- [ ] Top suggestion is opinionated with rationale and command
- [ ] Available skills listed for discoverability
- [ ] Terminal and harness formats both look good
- [ ] Handles empty project gracefully (no tasks, no history)

**Files**: src/cub/core/launch/welcome.py, src/cub/cli/default.py, tests/test_welcome.py

---

### Task: cub-orphan-04.3 - Integration testing and edge cases

Priority: 1
Labels: phase-5, cli, test, model:sonnet, complexity:medium

**Context**: The bare cub command has many edge cases that need testing: no project, no harness, nested sessions, resume/continue, different backends.

**Implementation Steps**:
1. Write integration test: bare cub in fresh directory (no `.cub/`)
2. Write integration test: bare cub with JSONL backend
3. Write integration test: bare cub with beads backend
4. Write integration test: bare cub with `CUB_SESSION_ACTIVE=1` set
5. Write integration test: bare cub with `--resume`
6. Write integration test: bare cub when no harness available
7. Test that `cub --help` still shows help text
8. Test that `cub <subcommand>` still routes to subcommands normally

**Acceptance Criteria**:
- [ ] All integration tests pass
- [ ] No regressions in existing subcommand routing
- [ ] Edge cases produce helpful error messages, not crashes
- [ ] `--help` behavior preserved

**Files**: tests/test_default_command_integration.py

---

### CHECKPOINT: Phase 5 Complete

After Phase 5:
- `cub` (bare command) is the unified entry point
- Welcome message shows opinionated suggestions
- Nesting prevention works
- `--resume` and `--continue` passthrough works

---

## Epic: cub-orphan-05 - bare-cub #6: Skill Discovery & Documentation

Priority: 2
Labels: phase-6, docs, feature

Make cub capabilities discoverable from within a harness session and document the new architecture.

### Task: cub-orphan-05.1 - Create /cub meta-skill for in-session discovery

Priority: 2
Labels: phase-6, docs, feature, model:sonnet, complexity:medium

**Context**: Users inside a harness session need to discover what cub skills are available. A `/cub` meta-skill lists available skills, common commands, and current project status.

**Implementation Steps**:
1. Create `.claude/commands/cub.md` as the meta-skill
2. Include: list of available `/cub:*` skills with one-line descriptions
3. Include: common `cub` CLI commands runnable via Bash (task ready, status, run)
4. Include: brief explanation of modes (conversational, structured, supervised, autonomous)
5. Include: dynamic project state (injected via template variables or by running `cub status`)

**Acceptance Criteria**:
- [ ] `/cub` skill exists and is invocable from Claude Code
- [ ] Lists all available `/cub:*` skills
- [ ] Lists common CLI commands
- [ ] Provides enough context for a user to navigate cub's capabilities

**Files**: .claude/commands/cub.md

---

### Task: cub-orphan-05.2 - Update CLAUDE.md with service architecture and skill reference

Priority: 2
Labels: phase-6, docs, model:sonnet, complexity:medium

**Context**: CLAUDE.md needs to reflect the new core/interface architecture so that harness sessions (and agents) understand cub's structure. Also document available skills.

**Implementation Steps**:
1. Update CLAUDE.md architecture section to reflect service layer
2. Add "Available Skills" section listing all `/cub:*` skills
3. Add "Cub Commands" section with commonly-used CLI commands
4. Update project structure diagram to show `core/services/`, `core/run/`, `core/suggestions/`, `core/launch/`
5. Add note about bare `cub` behavior and nesting detection
6. Remove any outdated references to old architecture

**Acceptance Criteria**:
- [ ] CLAUDE.md reflects current service layer architecture
- [ ] Skills section lists all available skills with descriptions
- [ ] Project structure diagram is accurate
- [ ] A harness session loading CLAUDE.md gets accurate information

**Files**: CLAUDE.md

---

### Task: cub-orphan-05.3 - End-to-end validation of full flow

Priority: 1
Labels: phase-6, test, model:sonnet, complexity:medium

**Context**: Final validation that the entire flow works: bare `cub` → harness → use skills → run tasks → exit. This is the acceptance test for the whole feature.

**Implementation Steps**:
1. Manual test: run `cub` from terminal, verify welcome + harness launch
2. Manual test: inside harness, run `/cub` to see available skills
3. Manual test: inside harness, run `/cub:spec` to start a spec
4. Manual test: inside harness, run `cub task ready` to see tasks
5. Manual test: inside harness, run `cub run --once` for foreground task
6. Manual test: run `cub` inside the harness (verify nesting prevention)
7. Document any issues found, create follow-up tasks if needed

**Acceptance Criteria**:
- [ ] Full flow works without crashes or confusing behavior
- [ ] Mode transitions feel natural
- [ ] Nesting prevention works correctly
- [ ] Any issues found are documented as follow-up tasks

**Files**: (manual testing, no code changes expected)

---

## Summary

| Epic | Tasks | Priority | Description |
|------|-------|----------|-------------|
| cub-orphan-00 | 5 | P0 | Core Run Extraction — extract business logic from cli/run.py |
| cub-orphan-01 | 5 | P1 | Rich Boundary Cleanup — zero Rich imports in core |
| cub-orphan-02 | 4 | P1 | Service Layer — clean API for all interfaces |
| cub-orphan-03 | 3 | P1 | Suggestion Engine — smart recommendations |
| cub-orphan-04 | 3 | P0 | Bare Cub Command — the user-facing entry point |
| cub-orphan-05 | 3 | P2 | Skill Discovery & Documentation |

**Total**: 6 epics, 23 tasks

**Critical path**: cub-orphan-00 (extraction) → cub-orphan-01 (cleanup) → cub-orphan-02 (services) → cub-orphan-03 (suggestions) → cub-orphan-04 (bare cub) → cub-orphan-05 (discovery)

**Ready to start immediately**: cub-orphan-00.1 (prompt builder extraction)
