# Architecture Design: Curb 1.0

**Session:** curb-20260110-143000
**Date:** 2026-01-10
**Mindset:** Production
**Scale:** Product (hundreds of users)
**Status:** Approved

---

## Technical Summary

Curb 1.0 preserves the existing well-tested Bash architecture (~4,300 lines, 341+ tests) while adding three new subsystems: session identity, artifact bundles, and git workflow automation. The refactoring focuses on CLI restructuring (flags → subcommands) and observability (structured per-task artifacts).

The design prioritizes backwards compatibility through deprecation warnings, maintains the modular `lib/*.sh` structure, and avoids external dependencies beyond what's already required (git, jq). New capabilities are implemented as additional library modules that integrate cleanly with the existing hook, config, and logging systems.

Production mindset drives decisions: comprehensive test coverage for new modules, explicit opt-in for destructive operations (push), and configurable guardrails for autonomous safety.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Core Language | Bash 4+ | Existing codebase, avoid rewrite, portable |
| Auxiliary | POSIX tools (git, jq, sed) | Already dependencies, no new requirements |
| Session Names | Embedded wordlist | ~100 animals in Bash array, no external dep |
| Diff Capture | `git diff` | Already have git as dependency |
| Testing | BATS | Existing framework, 341+ tests |
| Config | JSON (jq) | Existing pattern, well-tested |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         curb (dispatcher)                        │
│  ┌─────┐ ┌─────┐ ┌────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │init │ │ run │ │ status │ │ explain │ │artifacts│ │ version │ │
│  └──┬──┘ └──┬──┘ └───┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ │
└─────┼───────┼────────┼───────────┼───────────┼───────────┼──────┘
      │       │        │           │           │           │
      v       v        v           v           v           v
┌─────────────────────────────────────────────────────────────────┐
│                        lib/ modules                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ NEW:     │ │ NEW:     │ │ NEW:     │ │ EXTEND:  │            │
│  │session.sh│ │artifacts │ │ failure  │ │ git.sh   │            │
│  │          │ │    .sh   │ │   .sh    │ │(from     │            │
│  │- naming  │ │- bundles │ │- modes   │ │ state.sh)│            │
│  │- identity│ │- capture │ │- retry   │ │- branch  │            │
│  └──────────┘ └──────────┘ └──────────┘ │- commit  │            │
│                                         └──────────┘            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │EXISTING: │ │EXISTING: │ │EXISTING: │ │EXISTING: │            │
│  │tasks.sh  │ │harness.sh│ │logger.sh │ │budget.sh │            │
│  │          │ │          │ │+ redact  │ │+ iters   │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │config.sh │ │hooks.sh  │ │beads.sh  │ │ xdg.sh   │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### curb (Dispatcher Refactor)

- **Purpose:** Route subcommands to handlers, maintain backwards compatibility
- **Responsibilities:**
  - Parse subcommand and route to appropriate handler
  - Provide deprecation warnings for old flag syntax
  - Handle `--help` and `--version` at top level
- **Dependencies:** All lib modules
- **Interface:**
  ```
  curb <subcommand> [options]
  curb run [--once] [--epic X] [--name Y] [--push] ...
  curb init [--global] [path]
  curb status [--json]
  curb explain <task-id>
  curb artifacts <task-id>
  curb version
  ```

### lib/session.sh (NEW)

- **Purpose:** Manage session identity for concurrent instance disambiguation
- **Responsibilities:**
  - Generate random animal names from embedded wordlist (~100 animals)
  - Create session ID: `{name}-{YYYYMMDD-HHMMSS}`
  - Store session state (name, start time, run-id)
  - Provide session name for beads assignee integration
- **Dependencies:** None
- **Interface:**
  ```bash
  session_init [--name <name>]  # Initialize session
  session_get_name              # Returns "fox"
  session_get_id                # Returns "fox-20260110-143022"
  session_get_run_id            # Returns run ID for artifact paths
  ```

### lib/artifacts.sh (NEW)

- **Purpose:** Manage structured per-task artifact bundles
- **Responsibilities:**
  - Create artifact directory structure under `.curb/runs/`
  - Capture task metadata (task.json)
  - Capture plan output (plan.md)
  - Capture git diff (changes.patch)
  - Capture command log (commands.jsonl)
  - Generate summary (summary.md)
- **Dependencies:** git.sh, session.sh
- **Interface:**
  ```bash
  artifacts_init_run <run-id>
  artifacts_start_task <task-id>
  artifacts_capture_plan <task-id> <plan>
  artifacts_capture_command <task-id> <cmd> <exit_code> <output>
  artifacts_capture_diff <task-id>
  artifacts_finalize_task <task-id> <status> <summary>
  artifacts_get_path <task-id>
  ```

### lib/git.sh (NEW - extracted from state.sh)

- **Purpose:** Git workflow operations (branch per run, commit per task)
- **Responsibilities:**
  - Create run branch (`curb/<session-name>/<timestamp>`)
  - Commit task changes with structured message referencing task ID
  - Track uncommitted changes
  - Optional push with explicit `--push` flag only
- **Dependencies:** session.sh
- **Interface:**
  ```bash
  git_init_run_branch <session-name>
  git_commit_task <task-id> <summary>
  git_has_changes
  git_push_branch [--force]
  git_get_run_branch
  ```

### lib/failure.sh (NEW)

- **Purpose:** Configurable failure handling modes
- **Responsibilities:**
  - Implement failure policies: stop, move-on, retry, triage
  - Track retry counts per task
  - Provide failure context for retry attempts
  - Respect max iterations per task
- **Dependencies:** budget.sh, config.sh
- **Interface:**
  ```bash
  failure_get_mode
  failure_handle <task-id> <exit_code> <output>
  failure_should_retry <task-id>
  failure_increment_retry <task-id>
  ```

### lib/budget.sh (EXTEND)

- **Purpose:** Token and iteration budget tracking
- **New Responsibilities:**
  - Track iterations per task
  - Track iterations per run
  - Enforce configurable limits
- **Dependencies:** config.sh
- **New Interface:**
  ```bash
  budget_set_max_task_iterations <n>
  budget_set_max_run_iterations <n>
  budget_check_task_iterations <task-id>
  budget_check_run_iterations
  budget_increment_task_iteration <task-id>
  budget_increment_run_iteration
  ```

### lib/logger.sh (EXTEND)

- **Purpose:** Structured logging with JSONL output
- **New Responsibilities:**
  - Redact secrets from output (API_KEY, TOKEN, SECRET, PASSWORD, BEARER, private_key patterns)
  - Add timestamps to streamed output
- **Dependencies:** config.sh (for redaction patterns)
- **New Interface:**
  ```bash
  logger_redact <string>
  logger_stream <message>  # Timestamped stream output
  ```

## Data Model

### Session State
```json
{
  "name": "fox",
  "id": "fox-20260110-143022",
  "run_id": "fox-20260110-143022",
  "started_at": "2026-01-10T14:30:22Z",
  "branch": "curb/fox/20260110-143022"
}
```

### Run Metadata (.curb/runs/<run-id>/run.json)
```json
{
  "run_id": "fox-20260110-143022",
  "session_name": "fox",
  "started_at": "2026-01-10T14:30:22Z",
  "config": {
    "harness": "claude",
    "model": "sonnet",
    "max_task_iterations": 3,
    "max_run_iterations": 50,
    "failure_mode": "move-on"
  },
  "branch": "curb/fox/20260110-143022",
  "status": "in_progress",
  "tasks_completed": 3,
  "tasks_failed": 1
}
```

### Task Artifact (.curb/runs/<run-id>/tasks/<task-id>/task.json)
```json
{
  "task_id": "abc123",
  "title": "Add user authentication",
  "priority": "P0",
  "status": "completed",
  "iterations": 2,
  "started_at": "2026-01-10T14:31:00Z",
  "completed_at": "2026-01-10T14:35:22Z",
  "exit_code": 0
}
```

### Artifact Bundle Structure
```
.curb/runs/<run-id>/
├── run.json              # Run metadata
└── tasks/
    └── <task-id>/
        ├── task.json     # Task metadata snapshot
        ├── plan.md       # What the agent planned to do
        ├── changes.patch # git diff of changes
        ├── commands.jsonl# Commands executed
        └── summary.md    # Final status, what changed
```

## APIs / Interfaces

### CLI Interface
- **Type:** Command-line subcommands
- **Purpose:** User interaction with curb
- **Key Commands:**
  - `curb run`: Execute autonomous loop
  - `curb init`: Initialize project/global config
  - `curb status`: Show task/run status
  - `curb explain <task>`: Explain task state
  - `curb artifacts <task>`: Show artifact path
  - `curb version`: Show version

### Hook Interface
- **Type:** Shell script callbacks
- **Purpose:** Extensibility points for custom integrations
- **Existing Hooks:** pre-loop, pre-task, post-task, on-error, post-loop
- **New Default Hooks:**
  - `pre-loop.d/10-branch.sh`: Create run branch
  - `post-loop.d/90-pr.sh`: Offer to create PR (if pushed)

### Beads Integration
- **Type:** CLI wrapper
- **Purpose:** Task management with beads backend
- **Enhancement:** Set assignee to session name on task claim

## Implementation Phases

### Phase 1: Foundation (Session + Artifacts)
**Goal:** Observable runs with structured output

- Create `lib/session.sh` with animal name generator (~100 animals)
- Create `lib/artifacts.sh` with directory structure and capture functions
- Integrate into main loop: init session → init run → per-task artifacts
- Add `curb version` subcommand (quick win, establishes pattern)
- Write BATS tests for new modules

### Phase 2: CLI Restructuring
**Goal:** Consistent subcommand interface

- Refactor `curb` with dispatcher to route subcommands
- Move `curb-init` logic into `curb init`
- Implement `curb status` (migrate from `--status` flag)
- Implement `curb artifacts <task-id>`
- Add deprecation warnings for old flags (`--status` → `curb status`)
- Update help text and documentation
- Write BATS tests for CLI routing

### Phase 3: Git Workflow
**Goal:** Branch per run, commit per task

- Extract git operations from `state.sh` into new `lib/git.sh`
- Implement `git_init_run_branch` with naming convention `curb/<session>/<timestamp>`
- Implement `git_commit_task` with structured commit messages
- Add `--push` flag (explicit opt-in only)
- Integrate into main loop between tasks
- Write BATS tests for git operations

### Phase 4: Guardrails + Safety
**Goal:** Iteration limits and safe defaults

- Extend `budget.sh` with iteration tracking (per-task and per-run)
- Add secret redaction to `logger.sh` with configurable patterns
- Add timestamps to streamed output
- Implement configurable defaults in config.json schema
- Write BATS tests for guardrails

### Phase 5: Failure Handling
**Goal:** Configurable failure modes

- Create `lib/failure.sh` with mode implementations
- Implement stop, move-on, retry modes
- Integrate failure handling into main loop
- Add `curb explain <task-id>` command to show failure reasons
- Write BATS tests for failure scenarios

### Phase 6: Polish (P1/P2 items)
**Goal:** Default hooks, debug enhancements, documentation

- Add default hooks for branch/PR workflow
- Debug mode enhancement: show full harness command line
- Acceptance criteria verification (parse from task description)
- Update UPGRADING.md with migration guide
- Update README.md with new commands
- Final test pass and documentation review

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Subcommand refactor breaks user scripts | Medium | Medium | Deprecation warnings for 2 releases, document in UPGRADING.md |
| Animal name collisions | Low | Low | Timestamp in run-id ensures uniqueness |
| Artifact I/O slows runs | Low | Low | Lazy writes on task complete, append for commands.jsonl |
| Git branch conflicts with concurrent runs | Medium | Low | Unique branch names with session + timestamp |
| Secret redaction misses patterns | Medium | Medium | Start conservative, make patterns configurable |

## Dependencies

### External
- **git**: Branch management, diff capture, commits
- **jq**: JSON processing (existing dependency)
- **beads CLI**: Optional task backend (existing integration)

### Internal
- **state.sh**: Will be partially refactored, git ops extracted to git.sh
- **config.sh**: Extended schema for new settings
- **hooks.sh**: New default hooks for git workflow

## Security Considerations

- **No auto-push**: Require explicit `--push` flag, never push by default
- **Secret redaction**: Patterns for API_KEY, TOKEN, SECRET, PASSWORD, BEARER, private_key
- **No credential storage**: Rely on existing harness auth mechanisms
- **Artifact permissions**: Create directories with 700, files with 600

## Future Considerations

- LLM-assisted failure triage (P2, opt-in experiment)
- Max wall-clock time guardrail
- Command allowlist/denylist for harness operations
- Patch-only and branch-per-task git modes
- Remote artifact storage (S3, GCS) for team sharing
- Web dashboard for artifact browsing

---

**Next Step:** Run `/chopshop:planner curb-20260110-143000` to generate implementation tasks.
