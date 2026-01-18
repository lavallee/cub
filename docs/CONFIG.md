# Configuration Reference

This document provides a comprehensive reference for all Cub configuration options. Configuration can be set at multiple levels with the following priority (highest to lowest):

1. **CLI flags** (e.g., `--budget 500000`)
2. **Environment variables** (e.g., `CUB_BUDGET=500000`)
3. **Project config** (`.cub.json` in project root)
4. **Global config** (`~/.config/cub/config.json`)
5. **Hardcoded defaults**

## Quick Start

### Global Setup
```bash
cub-init --global
```

This creates `~/.config/cub/config.json` with defaults:
```json
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "gemini", "codex", "opencode"]
  },
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  },
  "loop": {
    "max_iterations": 100
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": false
  },
  "hooks": {
    "enabled": true
  }
}
```

### Project Override
Create `.cub.json` in your project root to override global settings:
```bash
mkdir -p my-project && cd my-project
cat > .cub.json <<EOF
{
  "budget": {
    "default": 500000
  },
  "loop": {
    "max_iterations": 50
  }
}
EOF
```

## Configuration Sections

### Harness Configuration

Controls which AI harness (Claude Code, Codex, etc.) is used to execute tasks.

#### `harness.default`
- **Type**: String
- **Default**: `"auto"`
- **Allowed Values**: `auto`, `claude`, `codex`, `gemini`, `opencode`
- **CLI Flag**: `--harness <name>`
- **Environment Variable**: `HARNESS`
- **Description**: Default harness to use. With `auto`, cub attempts harnesses in priority order.

#### `harness.priority`
- **Type**: Array of strings
- **Default**: `["claude", "gemini", "codex", "opencode"]`
- **Description**: Order to try harnesses when using `auto` mode. First available harness is used.

**Examples:**

```json
{
  "harness": {
    "default": "claude",
    "priority": ["claude", "codex"]
  }
}
```

Force Claude and fall back to Codex:
```bash
cub --harness claude
```

Override priority to try Gemini first:
```json
{
  "harness": {
    "priority": ["gemini", "claude", "codex"]
  }
}
```

---

### Budget Configuration

Manage token budget to control AI API costs.

#### `budget.default`
- **Type**: Number
- **Default**: `1000000` (1 million tokens)
- **CLI Flag**: `--budget <tokens>`
- **Environment Variable**: `CUB_BUDGET`
- **Description**: Token budget limit per session. Loop exits when exceeded.

#### `budget.warn_at`
- **Type**: Number (0.0-1.0)
- **Default**: `0.8` (80%)
- **Description**: Warning threshold as percentage of budget. Alerts when usage reaches this level.

**Examples:**

Small project (100k token budget):
```bash
export CUB_BUDGET=100000
cub
```

High-cost project with warning at 70%:
```json
{
  "budget": {
    "default": 5000000,
    "warn_at": 0.7
  }
}
```

Monitor budget usage:
```bash
# View warnings
jq 'select(.event_type=="budget_warning")' ~/.local/share/cub/logs/myproject/*.jsonl

# Track total tokens
jq -s '[.[].data.tokens_used // 0] | add' ~/.local/share/cub/logs/myproject/*.jsonl
```

---

### Loop Configuration

Control the main execution loop behavior.

#### `loop.max_iterations`
- **Type**: Number
- **Default**: `100`
- **CLI Flag**: `--max-iterations <num>`
- **Environment Variable**: `CUB_MAX_ITERATIONS`
- **Description**: Maximum number of iterations before loop exits. Prevents infinite loops and controls costs.

**Examples:**

Quick test run with 5 iterations:
```bash
cub --max-iterations 5 --once
```

Extended session:
```json
{
  "loop": {
    "max_iterations": 200
  }
}
```

---

### Clean State Configuration

Enforce code quality and consistency checks between task executions.

#### `clean_state.require_commit`
- **Type**: Boolean
- **Default**: `true`
- **CLI Flags**: `--require-clean`, `--no-require-clean`
- **Environment Variable**: `CUB_REQUIRE_CLEAN`
- **Description**: Enforce git commits after harness completes a task. If false, allows uncommitted changes.

#### `clean_state.require_tests`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Enforce test passage before allowing commits. If enabled, tasks must pass all tests.

#### `clean_state.auto_commit`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Automatically commit remaining changes when the harness completes successfully (exit 0) but forgets to commit. This prevents task failures due to uncommitted changes when the work is actually complete. Session files (progress.txt, fix_plan.md) are always auto-committed regardless of this setting.

**Examples:**

Relax clean state for development:
```bash
cub --no-require-clean
```

Strict mode - require tests pass, disable auto-commit:
```json
{
  "clean_state": {
    "require_commit": true,
    "require_tests": true,
    "auto_commit": false
  }
}
```

---

### Task Configuration

Control task lifecycle behavior.

#### `task.auto_close`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Automatically close tasks when the harness completes successfully (exit 0) but the agent forgets to close the task. This is a safety net that prevents tasks from getting stuck in "in_progress" state when the work is actually complete. Works with both beads and prd.json backends.

**Examples:**

Default behavior (auto-close enabled):
```json
{
  "task": {
    "auto_close": true
  }
}
```

Disable auto-close (require explicit agent action):
```json
{
  "task": {
    "auto_close": false
  }
}
```

**Note:** When using the beads backend, auto-close runs `bd close <task-id>`. When using the prd.json backend, auto-close updates the task status to "closed" in prd.json.

---

### Hooks Configuration

Control the hook system for task lifecycle events.

#### `hooks.enabled`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Enable/disable all hooks.

#### `hooks.fail_fast`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Stop loop if a hook fails (true) or continue (false).

#### `hooks.async_notifications`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Run `post-task` and `on-error` hooks asynchronously (non-blocking). When enabled, these hooks fire in the background so they don't slow down the main loop. All async hooks are collected before the session ends. Set to `false` to run all hooks synchronously.

**Examples:**

Disable hooks for testing:
```json
{
  "hooks": {
    "enabled": false
  }
}
```

Strict mode - stop on hook failure:
```json
{
  "hooks": {
    "enabled": true,
    "fail_fast": true
  }
}
```

Run all hooks synchronously (wait for each to complete):
```json
{
  "hooks": {
    "enabled": true,
    "async_notifications": false
  }
}
```

See [Hooks Documentation](../README.md#hooks) for details on writing custom hooks.

#### Example Hooks

Cub ships with example hooks in `examples/hooks/` that you can copy and customize:

| Hook | Location | Description |
|------|----------|-------------|
| `10-auto-branch.sh` | `pre-loop.d/` | Automatically creates a git branch when a session starts |
| `90-pr-prompt.sh` | `post-loop.d/` | Prompts to create a GitHub PR at end of run |
| `slack-notify.sh` | `post-task.d/` | Posts task completion notifications to Slack |
| `datadog-metric.sh` | `post-loop.d/` | Reports run metrics to Datadog |
| `pagerduty-alert.sh` | `on-error.d/` | Sends PagerDuty alerts on task failure |

**Installing Example Hooks:**

1. **For a specific project:**
   ```bash
   # Create hooks directory
   mkdir -p .cub/hooks/pre-loop.d

   # Copy and enable the auto-branch hook
   cp examples/hooks/pre-loop.d/10-auto-branch.sh .cub/hooks/pre-loop.d/
   chmod +x .cub/hooks/pre-loop.d/10-auto-branch.sh
   ```

2. **For all projects (global):**
   ```bash
   # Create global hooks directory
   mkdir -p ~/.config/cub/hooks/pre-loop.d

   # Copy and enable the auto-branch hook globally
   cp examples/hooks/pre-loop.d/10-auto-branch.sh ~/.config/cub/hooks/pre-loop.d/
   chmod +x ~/.config/cub/hooks/pre-loop.d/10-auto-branch.sh
   ```

**Auto-Branch Hook:**

The `10-auto-branch.sh` hook automatically creates a new git branch when a cub session starts:

- Creates branches with naming convention: `cub/{session_name}/{timestamp}`
- Stores the base branch for later PR creation
- Idempotent (safe to run multiple times)
- Skips if not in a git repository or already on a cub branch

Example output:
```
[auto-branch] Creating branch: cub/porcupine/20260111-120000 (from main)
[auto-branch] Stored base branch: main
```

**PR Prompt Hook:**

The `90-pr-prompt.sh` hook offers to create a GitHub Pull Request when a cub session completes:

- Uses the GitHub CLI (`gh`) for PR creation
- Reads base branch from `.cub/.base-branch` (set by auto-branch hook)
- Generates title and body from commit history
- Interactive prompt: yes/no/edit
- Skips automatically if:
  - No commits ahead of base branch
  - Already on main/master branch
  - PR already exists for the branch
  - Not running interactively (no TTY)

Prerequisites:
- GitHub CLI installed: `brew install gh`
- Authenticated: `gh auth login`
- Repository has GitHub remote

Example output:
```
==========================================
[pr-prompt] Ready to create Pull Request
==========================================

Branch:  cub/porcupine/20260111-120000
Base:    main
Commits: 3 ahead

Title:   Cub: Porcupine session (3 commits)

[pr-prompt] Create PR? [y/N/e(dit)]
```

**Using Both Hooks Together:**

For a complete PR workflow, enable both hooks:
```bash
# In your project
mkdir -p .cub/hooks/pre-loop.d .cub/hooks/post-loop.d
cp examples/hooks/pre-loop.d/10-auto-branch.sh .cub/hooks/pre-loop.d/
cp examples/hooks/post-loop.d/90-pr-prompt.sh .cub/hooks/post-loop.d/
chmod +x .cub/hooks/*/[0-9]*.sh
```

This gives you:
1. Auto-branch at session start (pre-loop)
2. PR prompt at session end (post-loop)

**Customizing Hooks:**

Hooks receive context via environment variables:
- `CUB_SESSION_ID` - Session ID (e.g., "porcupine-20260111-114543")
- `CUB_PROJECT_DIR` - Project directory
- `CUB_TASK_ID` - Current task ID (for task hooks)
- `CUB_TASK_TITLE` - Current task title (for task hooks)
- `CUB_EXIT_CODE` - Task exit code (for post-task/on-error hooks)
- `CUB_HARNESS` - Harness being used

---

### Guardrails Configuration

Prevent runaway loops and redact sensitive information from output.

#### `guardrails.max_task_iterations`
- **Type**: Number
- **Default**: `3`
- **Description**: Maximum number of times a single task can be attempted. When exceeded, task is marked failed and skipped. Prevents infinite retry loops.

#### `guardrails.max_run_iterations`
- **Type**: Number
- **Default**: `50`
- **Description**: Maximum number of total iterations in a run. When exceeded, run stops immediately. Prevents runaway loop behavior across all tasks.

#### `guardrails.iteration_warning_threshold`
- **Type**: Number (0.0-1.0)
- **Default**: `0.8` (80%)
- **Description**: Warning threshold as percentage of iteration limit. Logs warning when approaching max_task_iterations or max_run_iterations.

#### `guardrails.secret_patterns`
- **Type**: Array of strings (regex patterns)
- **Default**: `["api[_-]?key", "password", "token", "secret", "authorization", "credentials"]`
- **Description**: Regular expression patterns to detect and redact sensitive information from logs and output. Matched case-insensitively.

**Examples:**

Strict limits for testing:
```json
{
  "guardrails": {
    "max_task_iterations": 2,
    "max_run_iterations": 10,
    "iteration_warning_threshold": 0.5
  }
}
```

Add custom secret patterns:
```json
{
  "guardrails": {
    "secret_patterns": [
      "api[_-]?key",
      "password",
      "token",
      "secret",
      "authorization",
      "credentials",
      "webhook_url",
      "private_key",
      "aws_secret"
    ]
  }
}
```

Relaxed limits for complex tasks:
```bash
export CUB_MAX_TASK_ITERATIONS=10
export CUB_MAX_RUN_ITERATIONS=200
cub
```

---

## Environment Variables

Environment variables override all config files and provide quick, temporary overrides.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CUB_PROJECT_DIR` | String | `$(pwd)` | Project directory |
| `CUB_MODEL` | String | | Claude model: `haiku`, `sonnet`, `opus` |
| `CUB_BUDGET` | Number | 1,000,000 | Token budget limit |
| `CUB_MAX_ITERATIONS` | Number | 100 | Max loop iterations |
| `CUB_DEBUG` | Boolean | `false` | Enable debug logging |
| `CUB_STREAM` | Boolean | `false` | Stream harness output |
| `CUB_BACKEND` | String | `auto` | Task backend: `auto`, `beads`, `json` |
| `CUB_EPIC` | String | | Filter to epic ID |
| `CUB_LABEL` | String | | Filter to label name |
| `CUB_REQUIRE_CLEAN` | Boolean | `true` | Enforce clean state |
| `CUB_AUTO_CLOSE` | Boolean | `true` | Auto-close tasks on success |
| `CUB_MAX_TASK_ITERATIONS` | Number | 3 | Max attempts per task |
| `CUB_MAX_RUN_ITERATIONS` | Number | 50 | Max iterations per run |
| `HARNESS` | String | `auto` | Harness: `auto`, `claude`, `codex`, `gemini`, `opencode` |
| `CLAUDE_FLAGS` | String | | Extra flags for Claude Code CLI |
| `CODEX_FLAGS` | String | | Extra flags for OpenAI Codex CLI |
| `GEMINI_FLAGS` | String | | Extra flags for Gemini CLI |
| `OPENCODE_FLAGS` | String | | Extra flags for OpenCode CLI |

**Examples:**

Quick test with Haiku model:
```bash
export CUB_MODEL=haiku
export CUB_BUDGET=50000
cub --once
```

Debug a specific task:
```bash
CUB_DEBUG=true CUB_STREAM=true cub --once
```

Force beads backend and target epic:
```bash
CUB_BACKEND=beads CUB_EPIC=phase-1 cub
```

---

## CLI Flags

For one-time overrides, use CLI flags instead of config files:

```bash
cub [OPTIONS]
```

### Task Selection
| Flag | Description |
|------|-------------|
| `--epic <id>` | Target tasks within epic |
| `--label <name>` | Target tasks with label |
| `--once` | Run single iteration |

### Execution Control
| Flag | Description |
|------|-------------|
| `--budget <tokens>` | Set token budget |
| `--max-iterations <num>` | Set max iterations |
| `--require-clean` | Enforce clean state |
| `--no-require-clean` | Skip clean state checks |
| `--harness <name>` | Force harness |
| `--backend <name>` | Force task backend |

### Output & Debugging
| Flag | Description |
|------|-------------|
| `--debug, -d` | Enable verbose logging |
| `--stream` | Stream harness output |
| `--status` | Show task status |
| `--ready` | Show ready (unblocked) tasks |
| `--help` | Show help |

### Planning & Migration
| Flag | Description |
|------|-------------|
| `--plan` | Run planning mode |
| `--migrate-to-beads` | Migrate prd.json to beads |
| `--migrate-to-beads-dry-run` | Preview migration |

**Examples:**

```bash
# Run with specific model and budget
cub --budget 200000 --once

# Debug a specific epic
cub --debug --epic phase-1 --once

# Force harness and enable streaming
cub --harness claude --stream

# Run planning mode
cub --plan

# Show which tasks are ready to run
cub --ready
```

---

## Directory Structure

Cub uses XDG Base Directory specification for configuration and logs:

```
~/.config/cub/
├── config.json              # Global configuration
└── hooks/                   # Global hook directories
    ├── pre-loop.d/
    ├── pre-task.d/
    ├── post-task.d/
    ├── on-error.d/
    └── post-loop.d/

~/.local/share/cub/
└── logs/                    # Session logs
    └── {project}/
        └── {session}.jsonl  # YYYYMMDD-HHMMSS format

~/.cache/cub/              # Cache directory

.cub.json                  # Project-level config (in project root)
.cub/hooks/                # Project-specific hooks (in project root)
```

---

## Configuration Examples

### Example 1: Development Setup
Small budget for testing, relax requirements:
```json
{
  "budget": {
    "default": 100000,
    "warn_at": 0.9
  },
  "loop": {
    "max_iterations": 20
  },
  "clean_state": {
    "require_commit": false,
    "require_tests": false
  }
}
```

### Example 2: Production Setup
High budget, strict requirements, custom harness order:
```json
{
  "harness": {
    "priority": ["claude", "codex"]
  },
  "budget": {
    "default": 5000000,
    "warn_at": 0.75
  },
  "loop": {
    "max_iterations": 200
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": true
  },
  "hooks": {
    "enabled": true,
    "fail_fast": true
  }
}
```

### Example 3: CI/CD Integration
Minimal, deterministic config:
```json
{
  "harness": {
    "default": "claude"
  },
  "budget": {
    "default": 2000000
  },
  "loop": {
    "max_iterations": 50
  },
  "clean_state": {
    "require_commit": true,
    "require_tests": true
  }
}
```

### Example 4: Per-Model Overrides
```bash
# Fast tasks with Haiku
cub --label quick --model haiku --budget 50000

# Complex tasks with Opus
cub --label complex --model opus --budget 500000

# Standard tasks with Sonnet
cub --model sonnet
```

---

## Debugging Configuration

### View Merged Configuration
Check what configuration cub is actually using:

```bash
# Show in-memory config (requires examining logs)
cub --debug --once 2>&1 | grep -i config

# View global config
cat ~/.config/cub/config.json | jq .

# View project config
cat .cub.json | jq .
```

### Configuration Loading Order
Cub loads config in this order (later overrides earlier):
1. Hardcoded defaults
2. Global config (`~/.config/cub/config.json`)
3. Project config (`.cub.json`)
4. Environment variables
5. CLI flags

### Test Configuration
Validate JSON before using:
```bash
# Validate global config
jq empty ~/.config/cub/config.json && echo "Valid"

# Validate project config
jq empty .cub.json && echo "Valid"
```

---

## Troubleshooting

**Q: "Config file not found" error**
- Run `cub-init --global` to create global config
- Create `.cub.json` in your project if using project-level config

**Q: Budget exceeded but tasks remaining**
- Increase `budget.default` in config or via `CUB_BUDGET` env var
- Check token usage in logs: `jq '.data.tokens_used' ~/.local/share/cub/logs/myproject/*.jsonl`
- Reduce `budget.warn_at` to get earlier warnings

**Q: Wrong harness selected**
- Check `harness.priority` in config
- Use `--harness <name>` to force specific harness
- Verify harness is installed: `which claude`, `which codex`, etc.

**Q: Tasks not running**
- Check `loop.max_iterations` - may have hit limit
- Use `cub --ready` to see available tasks
- Check `--epic` and `--label` filters aren't too restrictive

**Q: Hook not executing**
- Ensure `hooks.enabled: true` in config
- Check script is executable: `chmod +x ~/.config/cub/hooks/post-task.d/myhook.sh`
- Verify hook location: `~/.config/cub/hooks/{hook-name}.d/` or `.cub/hooks/{hook-name}.d/`
