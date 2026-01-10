# Architecture Design: Curb 1.0

**Session:** curb-20250109-163000
**Date:** 2025-01-09
**Mindset:** MVP
**Scale:** Team tool (developers using AI coding agents)
**Status:** Approved

---

## Technical Summary

Curb 1.0 extends the existing bash architecture with four new subsystems: **logging**, **hooks**, **budgets**, and **config**. Two new harnesses (Gemini, OpenCode) join Claude and Codex. The core loop remains bash, with potential helper utilities if complex parsing is needed.

The architecture preserves curb's "hackable script" character while adding the reliability features needed for unattended operation.

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Core | Bash | Proven, working, easy to modify. Keep unless hitting walls. |
| Config parsing | Bash + jq | TOML is nice but adds deps. Start with JSON/env, add TOML later if needed. |
| Logging | Bash → JSONL | Structured logs, easy to query with jq |
| New harnesses | Bash | Same pattern as existing claude/codex implementations |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           curb                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Config  │  │  Budget  │  │   Hooks  │  │  Logger  │        │
│  │  Manager │  │  Tracker │  │  System  │  │          │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│       └─────────────┴──────┬──────┴─────────────┘               │
│                            │                                    │
│                    ┌───────▼───────┐                           │
│                    │   Main Loop   │                           │
│                    └───────┬───────┘                           │
│                            │                                    │
│         ┌──────────────────┼──────────────────┐                │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐          │
│  │ Task Layer  │   │Harness Layer│   │ State Mgmt  │          │
│  │ (tasks.sh)  │   │(harness.sh) │   │(clean state)│          │
│  └──────┬──────┘   └──────┬──────┘   └─────────────┘          │
│         │                 │                                    │
│    ┌────┴────┐      ┌─────┴─────┬─────────┬─────────┐         │
│    ▼         ▼      ▼           ▼         ▼         ▼          │
│ [beads]   [json]  [claude]   [codex]  [gemini] [opencode]     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Config Manager (`lib/config.sh`)

**Purpose:** Load and merge global + project config

**Responsibilities:**
- Load global config from `~/.config/curb/config.json`
- Load project config from `.curb/config.json`
- Merge with precedence: CLI flags > env vars > project config > global config
- Provide `config_get key` interface

**Config Schema:**
```json
{
  "harness": {
    "priority": ["claude", "gemini", "codex", "opencode"],
    "claude": { "flags": "", "model": "" },
    "gemini": { "flags": "" }
  },
  "budget": {
    "default": 1000000,
    "warn_at": 800000
  },
  "hooks": {
    "enabled": true,
    "dirs": ["~/.config/curb/hooks", ".curb/hooks"]
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": false
  },
  "logging": {
    "level": "info",
    "dir": "~/.local/share/curb/logs"
  }
}
```

### 2. Logger (`lib/logger.sh`)

**Purpose:** Structured logging for observability

**Responsibilities:**
- Write JSONL logs to `~/.local/share/curb/logs/{project}/{session}.jsonl`
- Also write to `.curb/logs/` in project for easy access
- Capture: timestamp, task_id, harness, duration, token_usage, exit_code, git_sha
- Provide `log_task_start`, `log_task_end`, `log_error` functions

**Log Entry Schema:**
```json
{
  "ts": "2025-01-09T16:30:00Z",
  "event": "task_end",
  "task_id": "curb-a1b2",
  "harness": "claude",
  "duration_sec": 45,
  "tokens": { "input": 5000, "output": 2000 },
  "exit_code": 0,
  "git_sha": "abc123",
  "budget_remaining": 950000
}
```

### 3. Budget Tracker (`lib/budget.sh`)

**Purpose:** Track token usage and enforce limits

**Responsibilities:**
- Track cumulative tokens across loop iterations
- Query harness for usage after each invocation (where supported)
- Stop loop if budget exceeded
- Warn at configurable threshold
- Provide `budget_check`, `budget_record`, `budget_remaining` functions

**Interface:**
```bash
budget_init 1000000        # Set budget for this run
budget_record 7000         # Record tokens used
budget_check               # Returns 0 if OK, 1 if exceeded
budget_remaining           # Echo remaining tokens
```

### 4. Hook System (`lib/hooks.sh`)

**Purpose:** Extensibility via shell scripts

**Responsibilities:**
- Scan hook directories for executable scripts
- Execute hooks at defined lifecycle points
- Pass context via environment variables
- Capture hook output/errors in logs
- Continue on hook failure (configurable)

**Hook Points:**
| Hook | When | Context Vars |
|------|------|--------------|
| `pre-loop` | Before first iteration | PROJECT_DIR, HARNESS |
| `pre-task` | Before each task | TASK_ID, TASK_TITLE |
| `post-task` | After each task | TASK_ID, EXIT_CODE, DURATION |
| `on-error` | On harness failure | TASK_ID, ERROR, EXIT_CODE |
| `post-loop` | After loop ends | TOTAL_TASKS, TOTAL_DURATION |

**Directory Structure:**
```
~/.config/curb/hooks/       # Global hooks
  pre-task.d/
    01-notify-slack.sh
  post-task.d/
    01-log-to-datadog.sh

.curb/hooks/                # Project hooks
  pre-task.d/
    01-check-env.sh
```

### 5. Clean State Enforcer (`lib/state.sh`)

**Purpose:** Ensure repo is clean after each task

**Responsibilities:**
- After harness completes, check for uncommitted changes
- If changes exist and no commit was made, warn or fail
- Optionally run tests and fail if they don't pass
- Provide `state_check_clean`, `state_ensure_committed` functions

**Logic:**
```bash
state_ensure_clean() {
  # Check if git is clean
  if ! git diff --quiet HEAD; then
    # Uncommitted changes - harness didn't commit
    if [[ "$REQUIRE_COMMIT" == "true" ]]; then
      log_error "Harness left uncommitted changes"
      return 1
    fi
  fi

  # Optionally run tests
  if [[ "$REQUIRE_TESTS" == "true" ]]; then
    if ! run_project_tests; then
      log_error "Tests failing after task completion"
      return 1
    fi
  fi

  return 0
}
```

### 6. New Harnesses

**Gemini (`lib/harness.sh` extension):**
- Implement `gemini_invoke()` and `gemini_invoke_streaming()`
- Query Gemini CLI for token usage
- Handle Gemini-specific flags and models

**OpenCode (`lib/harness.sh` extension):**
- Implement `opencode_invoke()` and `opencode_invoke_streaming()`
- Query OpenCode CLI for token usage
- Handle OpenCode-specific configuration

---

## Implementation Phases

### Phase 1: Foundation
**Goal:** Config and logging infrastructure

- Global/project config loading and merging
- JSONL logger with task metadata
- XDG directory setup
- Onboarding command (`curb init --global`)

**Checkpoint:** Can configure curb globally, see structured logs after runs

### Phase 2: Reliability
**Goal:** Trust the loop to run unattended

- Clean state enforcement (commit check, optional tests)
- Budget tracking with token counting
- Budget enforcement (stop at limit, warn at threshold)
- Error handling improvements

**Checkpoint:** Can set a budget, run overnight, trust it won't overspend or leave repo broken

### Phase 3: Extensibility
**Goal:** Hooks and new harnesses

- Hook system with 5 lifecycle points
- Gemini harness implementation
- OpenCode harness implementation
- Harness capability discovery (which features each supports)

**Checkpoint:** Can add custom behavior via hooks, use any of 4 harnesses

### Phase 4: Polish
**Goal:** Ready for others to use

- Better error messages
- Documentation updates
- Example hooks library
- Migration guide for existing users

**Checkpoint:** New user can install and configure curb in < 5 minutes

---

## Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Token counting varies by harness | Medium | High | Abstract behind interface, estimate where unavailable |
| Gemini/OpenCode CLIs have different interfaces | Medium | Medium | Spike early, design harness interface to accommodate |
| Bash config parsing gets complex | Low | Medium | Start simple JSON, add TOML later if needed |
| Hook overhead slows loop | Low | Low | Measure, optimize only if >1s overhead |

---

## Dependencies

### External
- `jq` - JSON processing (already required)
- Gemini CLI - TBD, need to verify installation/interface
- OpenCode CLI - TBD, need to verify installation/interface

### Internal
- Existing `lib/harness.sh` - Foundation for new harnesses
- Existing `lib/tasks.sh` - No changes needed
- Existing `curb` main script - Will integrate new subsystems

---

## Security Considerations

- Config files may contain API keys - document proper permissions (600)
- Hooks execute arbitrary code - document trust model
- Logs may contain sensitive task content - configurable redaction

---

## Future Considerations (Post-1.0)

- TOML config format for better readability
- Plugin architecture (loadable modules vs. hook scripts)
- Web dashboard for monitoring long runs
- Multi-repo orchestration
- Session continuation (--continue flag) if spike proves feasible

---

**Next Step:** Run `/chopshop/planner curb-20250109-163000` to generate implementation tasks.
