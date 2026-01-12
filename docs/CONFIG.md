# Configuration Reference

This document provides a comprehensive reference for all Curb configuration options. Configuration can be set at multiple levels with the following priority (highest to lowest):

1. **CLI flags** (e.g., `--budget 500000`)
2. **Environment variables** (e.g., `CURB_BUDGET=500000`)
3. **Project config** (`.curb.json` in project root)
4. **Global config** (`~/.config/curb/config.json`)
5. **Hardcoded defaults**

## Quick Start

### Global Setup
```bash
curb-init --global
```

This creates `~/.config/curb/config.json` with defaults:
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
Create `.curb.json` in your project root to override global settings:
```bash
mkdir -p my-project && cd my-project
cat > .curb.json <<EOF
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
- **Description**: Default harness to use. With `auto`, curb attempts harnesses in priority order.

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
curb --harness claude
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
- **Environment Variable**: `CURB_BUDGET`
- **Description**: Token budget limit per session. Loop exits when exceeded.

#### `budget.warn_at`
- **Type**: Number (0.0-1.0)
- **Default**: `0.8` (80%)
- **Description**: Warning threshold as percentage of budget. Alerts when usage reaches this level.

**Examples:**

Small project (100k token budget):
```bash
export CURB_BUDGET=100000
curb
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
jq 'select(.event_type=="budget_warning")' ~/.local/share/curb/logs/myproject/*.jsonl

# Track total tokens
jq -s '[.[].data.tokens_used // 0] | add' ~/.local/share/curb/logs/myproject/*.jsonl
```

---

### Loop Configuration

Control the main execution loop behavior.

#### `loop.max_iterations`
- **Type**: Number
- **Default**: `100`
- **CLI Flag**: `--max-iterations <num>`
- **Environment Variable**: `CURB_MAX_ITERATIONS`
- **Description**: Maximum number of iterations before loop exits. Prevents infinite loops and controls costs.

**Examples:**

Quick test run with 5 iterations:
```bash
curb --max-iterations 5 --once
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
- **Environment Variable**: `CURB_REQUIRE_CLEAN`
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
curb --no-require-clean
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

See [Hooks Documentation](../README.md#hooks) for details on writing custom hooks.

#### Example Hooks

Curb ships with example hooks in `examples/hooks/` that you can copy and customize:

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
   mkdir -p .curb/hooks/pre-loop.d

   # Copy and enable the auto-branch hook
   cp examples/hooks/pre-loop.d/10-auto-branch.sh .curb/hooks/pre-loop.d/
   chmod +x .curb/hooks/pre-loop.d/10-auto-branch.sh
   ```

2. **For all projects (global):**
   ```bash
   # Create global hooks directory
   mkdir -p ~/.config/curb/hooks/pre-loop.d

   # Copy and enable the auto-branch hook globally
   cp examples/hooks/pre-loop.d/10-auto-branch.sh ~/.config/curb/hooks/pre-loop.d/
   chmod +x ~/.config/curb/hooks/pre-loop.d/10-auto-branch.sh
   ```

**Auto-Branch Hook:**

The `10-auto-branch.sh` hook automatically creates a new git branch when a curb session starts:

- Creates branches with naming convention: `curb/{session_name}/{timestamp}`
- Stores the base branch for later PR creation
- Idempotent (safe to run multiple times)
- Skips if not in a git repository or already on a curb branch

Example output:
```
[auto-branch] Creating branch: curb/porcupine/20260111-120000 (from main)
[auto-branch] Stored base branch: main
```

**PR Prompt Hook:**

The `90-pr-prompt.sh` hook offers to create a GitHub Pull Request when a curb session completes:

- Uses the GitHub CLI (`gh`) for PR creation
- Reads base branch from `.curb/.base-branch` (set by auto-branch hook)
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

Branch:  curb/porcupine/20260111-120000
Base:    main
Commits: 3 ahead

Title:   Curb: Porcupine session (3 commits)

[pr-prompt] Create PR? [y/N/e(dit)]
```

**Using Both Hooks Together:**

For a complete PR workflow, enable both hooks:
```bash
# In your project
mkdir -p .curb/hooks/pre-loop.d .curb/hooks/post-loop.d
cp examples/hooks/pre-loop.d/10-auto-branch.sh .curb/hooks/pre-loop.d/
cp examples/hooks/post-loop.d/90-pr-prompt.sh .curb/hooks/post-loop.d/
chmod +x .curb/hooks/*/[0-9]*.sh
```

This gives you:
1. Auto-branch at session start (pre-loop)
2. PR prompt at session end (post-loop)

**Customizing Hooks:**

Hooks receive context via environment variables:
- `CURB_SESSION_ID` - Session ID (e.g., "porcupine-20260111-114543")
- `CURB_PROJECT_DIR` - Project directory
- `CURB_TASK_ID` - Current task ID (for task hooks)
- `CURB_TASK_TITLE` - Current task title (for task hooks)
- `CURB_EXIT_CODE` - Task exit code (for post-task/on-error hooks)
- `CURB_HARNESS` - Harness being used

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
export CURB_MAX_TASK_ITERATIONS=10
export CURB_MAX_RUN_ITERATIONS=200
curb
```

---

## Environment Variables

Environment variables override all config files and provide quick, temporary overrides.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CURB_PROJECT_DIR` | String | `$(pwd)` | Project directory |
| `CURB_MODEL` | String | | Claude model: `haiku`, `sonnet`, `opus` |
| `CURB_BUDGET` | Number | 1,000,000 | Token budget limit |
| `CURB_MAX_ITERATIONS` | Number | 100 | Max loop iterations |
| `CURB_DEBUG` | Boolean | `false` | Enable debug logging |
| `CURB_STREAM` | Boolean | `false` | Stream harness output |
| `CURB_BACKEND` | String | `auto` | Task backend: `auto`, `beads`, `json` |
| `CURB_EPIC` | String | | Filter to epic ID |
| `CURB_LABEL` | String | | Filter to label name |
| `CURB_REQUIRE_CLEAN` | Boolean | `true` | Enforce clean state |
| `CURB_MAX_TASK_ITERATIONS` | Number | 3 | Max attempts per task |
| `CURB_MAX_RUN_ITERATIONS` | Number | 50 | Max iterations per run |
| `HARNESS` | String | `auto` | Harness: `auto`, `claude`, `codex`, `gemini`, `opencode` |
| `CLAUDE_FLAGS` | String | | Extra flags for Claude Code CLI |
| `CODEX_FLAGS` | String | | Extra flags for OpenAI Codex CLI |
| `GEMINI_FLAGS` | String | | Extra flags for Gemini CLI |
| `OPENCODE_FLAGS` | String | | Extra flags for OpenCode CLI |

**Examples:**

Quick test with Haiku model:
```bash
export CURB_MODEL=haiku
export CURB_BUDGET=50000
curb --once
```

Debug a specific task:
```bash
CURB_DEBUG=true CURB_STREAM=true curb --once
```

Force beads backend and target epic:
```bash
CURB_BACKEND=beads CURB_EPIC=phase-1 curb
```

---

## CLI Flags

For one-time overrides, use CLI flags instead of config files:

```bash
curb [OPTIONS]
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
curb --budget 200000 --once

# Debug a specific epic
curb --debug --epic phase-1 --once

# Force harness and enable streaming
curb --harness claude --stream

# Run planning mode
curb --plan

# Show which tasks are ready to run
curb --ready
```

---

## Directory Structure

Curb uses XDG Base Directory specification for configuration and logs:

```
~/.config/curb/
├── config.json              # Global configuration
└── hooks/                   # Global hook directories
    ├── pre-loop.d/
    ├── pre-task.d/
    ├── post-task.d/
    ├── on-error.d/
    └── post-loop.d/

~/.local/share/curb/
└── logs/                    # Session logs
    └── {project}/
        └── {session}.jsonl  # YYYYMMDD-HHMMSS format

~/.cache/curb/              # Cache directory

.curb.json                  # Project-level config (in project root)
.curb/hooks/                # Project-specific hooks (in project root)
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
curb --label quick --model haiku --budget 50000

# Complex tasks with Opus
curb --label complex --model opus --budget 500000

# Standard tasks with Sonnet
curb --model sonnet
```

---

## Debugging Configuration

### View Merged Configuration
Check what configuration curb is actually using:

```bash
# Show in-memory config (requires examining logs)
curb --debug --once 2>&1 | grep -i config

# View global config
cat ~/.config/curb/config.json | jq .

# View project config
cat .curb.json | jq .
```

### Configuration Loading Order
Curb loads config in this order (later overrides earlier):
1. Hardcoded defaults
2. Global config (`~/.config/curb/config.json`)
3. Project config (`.curb.json`)
4. Environment variables
5. CLI flags

### Test Configuration
Validate JSON before using:
```bash
# Validate global config
jq empty ~/.config/curb/config.json && echo "Valid"

# Validate project config
jq empty .curb.json && echo "Valid"
```

---

## Troubleshooting

**Q: "Config file not found" error**
- Run `curb-init --global` to create global config
- Create `.curb.json` in your project if using project-level config

**Q: Budget exceeded but tasks remaining**
- Increase `budget.default` in config or via `CURB_BUDGET` env var
- Check token usage in logs: `jq '.data.tokens_used' ~/.local/share/curb/logs/myproject/*.jsonl`
- Reduce `budget.warn_at` to get earlier warnings

**Q: Wrong harness selected**
- Check `harness.priority` in config
- Use `--harness <name>` to force specific harness
- Verify harness is installed: `which claude`, `which codex`, etc.

**Q: Tasks not running**
- Check `loop.max_iterations` - may have hit limit
- Use `curb --ready` to see available tasks
- Check `--epic` and `--label` filters aren't too restrictive

**Q: Hook not executing**
- Ensure `hooks.enabled: true` in config
- Check script is executable: `chmod +x ~/.config/curb/hooks/post-task.d/myhook.sh`
- Verify hook location: `~/.config/curb/hooks/{hook-name}.d/` or `.curb/hooks/{hook-name}.d/`
