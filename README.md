# Cub

**C**oding **U**nder **R**alph + **B**eads


An autonomous AI coding agent harness that drives AI coding CLIs in a loop to build software from a structured task backlog.

Combines the [Ralph Wiggum technique](https://ghuntley.com/ralph/) (running an AI agent in a while loop) with [beads-style](https://github.com/steveyegge/beads) task management (hash IDs, P0-P4 priorities, dependency tracking).

## Features

- **Multi-Harness Support**: Works with Claude Code, OpenAI Codex, Google Gemini, or OpenCode
- **Dual Task Backend**: Use beads CLI or simple prd.json for task management
- **Autonomous Loop**: Runs until all tasks are complete or budget exhausted
- **Dependency Tracking**: Respects task dependencies, picks ready tasks
- **Priority Scheduling**: P0-P4 priority-based task selection
- **Epic/Label Filtering**: Target specific epics or labeled tasks
- **Per-Task Model Selection**: Tasks with `model:X` labels auto-select the model
- **Budget Management**: Token budget tracking with configurable limits and warnings
- **Guardrails**: Iteration limits, secret redaction, and safety controls
- **Failure Handling**: Configurable modes (stop, move-on, retry, triage)
- **Session Management**: Named sessions with animal names, artifact bundles per task
- **Git Workflow**: Auto-branching, commit per task, clean state enforcement
- **Hooks System**: Custom scripts at 5 lifecycle points (pre/post loop, pre/post task, on-error)
- **Structured Logging**: JSONL logs with timestamps, durations, and git SHAs
- **Global + Project Config**: XDG-compliant configuration with overrides
- **Subcommand CLI**: Clear organization with init, run, status, explain, artifacts
- **Planning Mode**: Analyze codebase and generate fix plans
- **Streaming Output**: Watch agent activity in real-time
- **Migration Tools**: Convert between prd.json and beads formats

## Prerequisites

- **Required**: [jq](https://jqlang.github.io/jq/) for JSON processing
- **Required**: Bash 4+
- **Harness** (at least one):
  - [Claude Code CLI](https://github.com/anthropics/claude-code) (`claude`) - Recommended
  - [OpenAI Codex CLI](https://github.com/openai/codex) (`codex`)
- **Task Backend** (optional):
  - [beads CLI](https://github.com/steveyegge/beads) (`bd`) - For advanced task management

## Installation

```bash
# Clone cub to your tools directory
git clone https://github.com/lavallee/cub ~/tools/cub

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$PATH:$HOME/tools/cub"

# Or create symlinks
ln -s ~/tools/cub/cub /usr/local/bin/cub
ln -s ~/tools/cub/cub-init /usr/local/bin/cub-init
```

## Quick Start

```bash
# First-time setup (creates global config and directories)
cub init --global

# Initialize a new project
cd my-project
cub init

# Edit prd.json with your tasks (or use beads: bd init && bd create "Task")
# Add specifications to specs/
# Update AGENT.md with build instructions

# Check status
cub status

# Run the autonomous loop
cub run

# Or run a single iteration
cub run --once

# Or target a specific epic
cub run --epic my-epic-id

# Or filter by label
cub run --label phase-1
```

**Upgrading from an earlier version?** See [UPGRADING.md](UPGRADING.md) for migration guide and breaking changes.

## Usage

Cub uses a subcommand structure for clear organization:

```bash
# SUBCOMMANDS
cub init           # Initialize project or global config
cub run            # Run the main loop (default)
cub status         # Show task progress
cub explain <id>   # Show task details
cub artifacts      # List task outputs
cub version        # Show version

# CUB INIT - Initialize project or system
cub init                    # Initialize current directory
cub init --global           # Set up global config
cub init /path/to/project   # Initialize specific directory

# CUB RUN - Execute tasks (this is the default if no subcommand)
cub run                     # Run loop until all tasks complete
cub run --once              # Run single iteration
cub run --ready             # Show ready (unblocked) tasks
cub run --plan              # Run planning mode
cub run --name myname       # Use custom session name

# CUB STATUS - Show progress
cub status                  # Show task summary
cub status --json           # JSON output for scripting

# CUB EXPLAIN - Task details
cub explain cub-abc        # Show full task details

# CUB ARTIFACTS - View task outputs
cub artifacts               # List all artifacts
cub artifacts cub-abc      # Show artifacts for specific task

# FILTERING (works with beads or JSON backend)
cub run --epic <id>         # Target tasks within a specific epic
cub run --label <name>      # Target tasks with a specific label
cub run --epic cub-1gq --label phase-1  # Combine filters

# HARNESS SELECTION
cub run --harness claude    # Use Claude Code (default)
cub run --harness codex     # Use OpenAI Codex CLI
cub run --harness gemini    # Use Google Gemini
cub run --harness opencode  # Use OpenCode

# BACKEND SELECTION
cub run --backend beads     # Force beads backend
cub run --backend json      # Force JSON backend

# OUTPUT MODES
cub run --stream            # Stream harness activity in real-time
cub run --debug             # Enable verbose debug logging

# MIGRATION TOOLS
cub --migrate-to-beads          # Migrate prd.json to beads
cub --migrate-to-beads-dry-run  # Preview migration

# DEBUGGING
cub run --test              # Test harness invocation
cub run --dump-prompt       # Save prompts to files for inspection

# HELP
cub --help                  # Main help
cub init --help             # Init subcommand help
cub run --help              # Run subcommand help
cub status --help           # Status subcommand help
```

**Note:** Running `cub` without a subcommand defaults to `cub run`.

## Project Structure

After running `cub init`, your project will have:

```
my-project/
├── prd.json        # Task backlog (beads-style format)
├── PROMPT.md       # Loop prompt template (system instructions)
├── AGENT.md        # Build/run instructions for the agent
├── AGENTS.md       # Symlink to AGENT.md (for Codex compatibility)
├── progress.txt    # Session learnings (agent appends)
├── fix_plan.md     # Discovered issues and plans
├── specs/          # Detailed specifications
└── .cub/          # Cub runtime data (created during runs)
    ├── hooks/      # Project-specific hooks
    └── runs/       # Run artifacts and task outputs
```

### Artifacts Directory

Each cub run creates artifacts in `.cub/runs/{session-id}/`:

```
.cub/runs/porcupine-20260111-114543/
├── run.json                    # Run metadata and config
└── tasks/
    └── cub-abc/
        ├── task.json           # Task execution details
        ├── summary.md          # AI-generated summary
        └── changes.patch       # Git diff of changes
```

View artifacts with:
```bash
cub artifacts                  # List all artifacts
cub artifacts cub-abc         # Show specific task artifacts
```

## Task Backends

Cub supports two task management backends:

### JSON Backend (Default)

Simple file-based task management using `prd.json`:

```json
{
  "projectName": "my-project",
  "prefix": "myproj",
  "tasks": [
    {
      "id": "myproj-a1b2",
      "type": "feature",
      "title": "User authentication",
      "description": "Implement login functionality",
      "acceptanceCriteria": ["Login form renders", "Tests pass"],
      "priority": "P1",
      "status": "open",
      "dependsOn": [],
      "notes": ""
    }
  ]
}
```

### Beads Backend

For projects using the [beads](https://github.com/steveyegge/beads) CLI:

```bash
# Install beads
brew install steveyegge/beads/bd

# Initialize in project
bd init

# Cub auto-detects .beads/ directory
cub status  # Uses beads backend automatically
```

### Task Fields

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (prefix + hash, e.g., `prd-a1b2`) |
| `type` | `epic`, `feature`, `task`, `bug`, `chore` |
| `title` | Short description |
| `description` | Full details, can use user story format |
| `acceptanceCriteria` | Array of verifiable conditions |
| `priority` | P0 (critical) to P4 (backlog) |
| `status` | `open`, `in_progress`, `closed` |
| `dependsOn` | Array of task IDs that must be closed first |
| `parent` | (Optional) Parent epic ID |
| `labels` | (Optional) Array of labels for filtering and model selection |
| `notes` | Agent-maintained notes |

### Per-Task Model Selection

Tasks can specify which Claude model to use via a `model:` label:

```bash
# In beads:
bd label add cub-abc model:haiku     # Use fast model for simple tasks
bd label add cub-xyz model:sonnet    # Use balanced model for complex tasks
bd label add cub-123 model:opus-4.5  # Use most capable model for hard tasks
```

In JSON backend, add labels to the task:
```json
{
  "id": "prd-abc",
  "title": "Quick fix",
  "labels": ["model:haiku", "phase-1"]
}
```

When cub picks up a task with a `model:` label, it automatically sets `CUB_MODEL` to pass to the Claude harness.

### Task Selection Algorithm

1. Find tasks where `status == "open"`
2. Filter to tasks where all `dependsOn` items are `closed`
3. Sort by priority (P0 first)
4. Pick the first one

## AI Harnesses

Cub abstracts the AI coding CLI into a "harness" layer, supporting multiple backends.

For detailed capability matrix and technical reference, see [docs/HARNESSES.md](docs/HARNESSES.md).

### Claude Code (Default)

```bash
cub --harness claude
# or
export HARNESS=claude
```

Uses Claude Code's `--append-system-prompt` for clean prompt separation.

### OpenAI Codex

```bash
cub --harness codex
# or
export HARNESS=codex
```

Uses Codex's `--full-auto` mode with combined prompts.

### Google Gemini

```bash
cub --harness gemini
# or
export HARNESS=gemini
```

Uses Gemini CLI's `-y` (YOLO mode) for autonomous operation.

### OpenCode

```bash
cub --harness opencode
# or
export HARNESS=opencode
```

Uses OpenCode's `run` subcommand with JSON output for token tracking.

### Auto-Detection

By default, cub auto-detects available harnesses using this priority order:
1. **Explicit HARNESS setting** (CLI flag `--harness` or env var `HARNESS`)
2. **Config priority array** (`harness.priority` in config file)
3. **Default detection order**: claude > opencode > codex > gemini

#### Configuration Example

You can customize the harness priority in `.cub.json` or global config:

```json
{
  "harness": {
    "priority": ["gemini", "claude", "codex", "opencode"]
  }
}
```

Cub will try each harness in order and use the first one available. If none are found, it falls back to the default order.

## Budget Management

Cub provides token budget tracking to control AI API costs and prevent runaway spending.

### How It Works

Cub tracks token usage across all tasks and enforces budget limits:

1. **Per-task tracking**: Each harness reports tokens used (where available)
2. **Cumulative tracking**: Total tokens tracked per session in logs
3. **Warning threshold**: Alert when budget usage reaches a configurable percentage
4. **Hard limit**: Loop exits when budget is exceeded

### Budget Configuration

Set budget in your config file or via environment variable:

**Global config** (`~/.config/cub/config.json`):
```json
{
  "budget": {
    "default": 1000000,
    "warn_at": 0.8
  }
}
```

**Project override** (`.cub.json`):
```json
{
  "budget": {
    "default": 500000,
    "warn_at": 0.75
  }
}
```

**Environment variable**:
```bash
export CUB_BUDGET=2000000  # Overrides both config files
cub
```

### Budget Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `budget.default` | 1,000,000 | Token budget limit per session |
| `budget.warn_at` | 0.8 | Warn when usage reaches this % (0.0-1.0) |

### Common Budget Examples

**For development/testing** (small projects):
```bash
export CUB_BUDGET=100000  # 100k tokens
cub
```

**For medium projects** (most use cases):
```bash
export CUB_BUDGET=1000000  # 1M tokens (default)
cub
```

**For large projects** (extensive refactoring):
```bash
export CUB_BUDGET=5000000  # 5M tokens
cub
```

**For multi-day sessions**:
```bash
# Set higher budget if running multiple iterations
export CUB_BUDGET=10000000  # 10M tokens
cub --max-iterations 200
```

### Monitoring Budget Usage

Check token usage in structured logs:

```bash
# View all budget warnings
jq 'select(.event_type=="budget_warning")' ~/.local/share/cub/logs/myproject/*.jsonl

# Track total tokens per session
jq -s '[.[].data.tokens_used // 0] | add' ~/.local/share/cub/logs/myproject/*.jsonl

# Find high-cost tasks
jq 'select(.data.tokens_used > 10000)' ~/.local/share/cub/logs/myproject/*.jsonl
```

## Guardrails

Cub includes safety guardrails to prevent runaway loops and protect sensitive information.

### Iteration Limits

```json
{
  "guardrails": {
    "max_task_iterations": 3,    // Max retries per task
    "max_run_iterations": 50,    // Max total iterations per run
    "iteration_warning_threshold": 0.8  // Warn at 80% of limit
  }
}
```

When a task exceeds `max_task_iterations`, it's marked as failed and skipped.
When a run exceeds `max_run_iterations`, the entire run stops.

### Secret Redaction

Cub automatically redacts sensitive patterns in logs and debug output:

```json
{
  "guardrails": {
    "secret_patterns": [
      "api[_-]?key",
      "password",
      "token",
      "secret",
      "authorization",
      "credentials"
    ]
  }
}
```

Add custom patterns for project-specific secrets.

## Failure Handling

Cub provides configurable failure handling modes:

```json
{
  "failure": {
    "mode": "retry",
    "max_retries": 3
  }
}
```

### Failure Modes

| Mode | Behavior |
|------|----------|
| `stop` | Stop immediately on first failure |
| `move-on` | Mark task failed, continue to next task |
| `retry` | Retry task with failure context (up to max_retries) |
| `triage` | (Future) Human-in-the-loop intervention |

### Failure Context

When using `retry` mode, subsequent attempts include context about what failed:

```markdown
## Previous Attempt Failed
Exit code: 1
Error: Test failures in auth_test.py

Please fix the issues and try again.
```

## Session Management

Each cub run creates a unique session with an auto-generated animal name:

```bash
# Auto-generated session name
cub run    # Creates: porcupine-20260111-114543

# Custom session name
cub run --name release-1.0    # Creates: release-1.0-20260111-114543
```

Session names are used for:
- Git branch naming: `cub/{session}/{timestamp}`
- Artifact directories: `.cub/runs/{session}/`
- Log identification

### Session Assignment

Tasks can be assigned to specific sessions (useful for parallel work):

```bash
# With beads backend
bd assign cub-abc porcupine

# View task assignment
bd show cub-abc | grep Assignee
```

## Git Workflow

Cub follows a disciplined git workflow:

### Branch Per Run

Each run creates a feature branch (when using the auto-branch hook):

```
main
└── cub/porcupine/20260111-114543
```

### Commit Per Task

The AI commits after each completed task with a structured message:

```
task(cub-abc): Implement user authentication

- Added login form component
- Created auth API endpoints
- Added tests for auth flow

Task-Id: cub-abc
Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
```

### Clean State Enforcement

Cub verifies clean git state before and after tasks:

```json
{
  "clean_state": {
    "require_commit": true,   // Require all changes committed
    "require_tests": false    // Optionally require tests pass
  }
}
```

Override via CLI:
```bash
cub run --require-clean      # Force clean state check
cub run --no-require-clean   # Disable clean state check
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CUB_PROJECT_DIR` | `$(pwd)` | Project directory |
| `CUB_MAX_ITERATIONS` | `100` | Max loop iterations |
| `CUB_DEBUG` | `false` | Enable debug mode |
| `CUB_STREAM` | `false` | Enable streaming output |
| `CUB_BACKEND` | `auto` | Task backend: `auto`, `beads`, `json` |
| `CUB_EPIC` | | Filter to tasks within this epic ID |
| `CUB_LABEL` | | Filter to tasks with this label |
| `CUB_MODEL` | | Override model for Claude harness |
| `CUB_BUDGET` | | Override token budget (overrides config) |
| `HARNESS` | `auto` | AI harness: `auto`, `claude`, `codex`, `opencode`, `gemini` |
| `CLAUDE_FLAGS` | | Extra flags for Claude Code |
| `CODEX_FLAGS` | | Extra flags for Codex CLI |
| `GEMINI_FLAGS` | | Extra flags for Gemini CLI |
| `OPENCODE_FLAGS` | | Extra flags for OpenCode CLI |

## Configuration

Cub uses XDG-compliant configuration with global and project-level overrides.

For a complete reference of all configuration options, see [docs/CONFIG.md](docs/CONFIG.md).

### Global Setup

```bash
cub init --global
```

Creates:
- `~/.config/cub/config.json` - Global configuration
- `~/.config/cub/hooks/` - Hook directories
- `~/.local/share/cub/logs/` - Log storage
- `~/.cache/cub/` - Cache directory

### Configuration Precedence

1. **CLI flags** (highest priority)
2. **Environment variables**
3. **Project config** (`.cub.json` in project root)
4. **Global config** (`~/.config/cub/config.json`)
5. **Hardcoded defaults** (lowest priority)

### Config File Format

```json
{
  "harness": {
    "default": "auto",
    "priority": ["claude", "codex"]
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

```json
{
  "budget": {
    "default": 500000
  },
  "loop": {
    "max_iterations": 50
  }
}
```

## Structured Logging

Cub logs all task executions in JSONL format for debugging and analytics.

### Log Location

```
~/.local/share/cub/logs/{project}/{session}.jsonl
```

Session ID format: `YYYYMMDD-HHMMSS` (e.g., `20260109-214858`)

### Log Events

Each task produces structured events:

```json
{"timestamp":"2026-01-09T21:48:58Z","event_type":"task_start","data":{"task_id":"cub-abc","task_title":"Fix bug","harness":"claude"}}
{"timestamp":"2026-01-09T21:52:30Z","event_type":"task_end","data":{"task_id":"cub-abc","exit_code":0,"duration":212,"tokens_used":0,"git_sha":"abc123..."}}
```

### Querying Logs

```bash
# Find all task starts
jq 'select(.event_type=="task_start")' ~/.local/share/cub/logs/myproject/*.jsonl

# Find failed tasks
jq 'select(.event_type=="task_end" and .data.exit_code != 0)' logs/*.jsonl

# Calculate total duration
jq -s '[.[].data.duration // 0] | add' logs/*.jsonl
```

## Hooks

Cub provides a flexible hook system to integrate with external services and tools. Hooks are executable scripts that run at specific points in the cub lifecycle.

### Hook Lifecycle

The hook execution flow through a typical cub session:

```
┌─────────────────────────────────────────────────┐
│                   cub Start                     │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
            ┌──────────────┐
            │ pre-loop ✓   │  (setup, initialization)
            └──────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  Main Loop Starts    │
        └──────┬───────────────┘
               │
        ┌──────▼──────────┐
        │ pre-task ✓      │  (for each task)
        └────────┬────────┘
                 │
                 ▼
          ┌─────────────────┐
          │ Execute Task    │
          │  (harness)      │
          └────────┬────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
   ┌──────────┐         ┌──────────┐
   │ Success  │         │ Failure  │
   └────┬─────┘         └────┬─────┘
        │                    │
        │              ┌─────▼──────┐
        │              │ on-error ✓ │  (alert, logs)
        │              └─────┬──────┘
        │                    │
        └────────┬───────────┘
                 │
                 ▼
           ┌────────────────┐
           │ post-task ✓    │  (metrics, notify)
           └────────┬───────┘
                    │
        ┌───────────┴──────────┐
        │                      │
        ▼                      ▼
    ┌────────┐           ┌──────────┐
    │ More   │           │ All Done │
    │ Tasks? │           └──────┬───┘
    └───┬────┘                  │
        │ yes                   │
        ▼                       │
   (Loop Back)                  │
        │                       │
        └───────────────────────┘
                   │
                   ▼
            ┌──────────────┐
            │ post-loop ✓  │  (cleanup, reports)
            └──────────────┘
                   │
                   ▼
            ┌──────────────┐
            │  Exit Loop   │
            └──────────────┘
```

### Hook Points

Cub supports five hook points:

| Hook | When It Runs | Use Cases |
|------|--------------|-----------|
| `pre-loop` | Before starting the main loop | Setup, initialization, cleanup from previous run |
| `pre-task` | Before each task execution | Prepare environment, start timers |
| `post-task` | After each task (success or failure) | Notifications, metrics, logging |
| `on-error` | When a task fails | Alerts, incident creation, diagnostics |
| `post-loop` | After the main loop completes | Cleanup, final notifications, reports |

### Hook Locations

Hooks are discovered from two locations (in order):

1. **Global hooks**: `~/.config/cub/hooks/{hook-name}.d/` - Available to all projects
2. **Project hooks**: `./.cub/hooks/{hook-name}.d/` - Specific to a project

All executable files in these directories are run in sorted order (alphabetically).

### Context Variables

All hooks receive context via environment variables:

| Variable | Available In | Description |
|----------|--------------|-------------|
| `CUB_HOOK_NAME` | All | Name of the hook being executed |
| `CUB_PROJECT_DIR` | All | Project directory |
| `CUB_SESSION_ID` | pre-loop, post-loop | Unique session identifier |
| `CUB_HARNESS` | pre-loop, post-loop | Harness in use (claude, codex, etc.) |
| `CUB_TASK_ID` | pre-task, post-task, on-error | ID of the current task |
| `CUB_TASK_TITLE` | pre-task, post-task, on-error | Title of the current task |
| `CUB_EXIT_CODE` | post-task, on-error | Exit code from task execution (0 = success) |

### Example Hooks

Cub includes example hooks for common integrations:

- **`examples/hooks/post-task/slack-notify.sh`** - Posts task completion to Slack
- **`examples/hooks/post-loop/datadog-metric.sh`** - Sends metrics to Datadog
- **`examples/hooks/on-error/pagerduty-alert.sh`** - Creates PagerDuty incidents on failure

**To install an example hook:**

```bash
# Copy to global hooks directory
mkdir -p ~/.config/cub/hooks/{post-task,post-loop,on-error}.d
cp examples/hooks/post-task/slack-notify.sh ~/.config/cub/hooks/post-task.d/01-slack.sh
chmod +x ~/.config/cub/hooks/post-task.d/01-slack.sh

# Or to project-specific hooks
mkdir -p .cub/hooks/post-task.d
cp examples/hooks/post-task/slack-notify.sh .cub/hooks/post-task.d/01-slack.sh
chmod +x .cub/hooks/post-task.d/01-slack.sh
```

Each example script includes detailed installation and configuration instructions.

### Writing Custom Hooks

Creating a hook is simple - just write a bash script:

```bash
#!/usr/bin/env bash
# Example hook script

# Hooks receive context as environment variables
echo "Task $CUB_TASK_ID completed with exit code $CUB_EXIT_CODE"

# Exit with 0 for success, non-zero for failure
exit 0
```

**Requirements:**

- Script must be executable (`chmod +x`)
- Script must exit with status 0 (success) or non-zero (failure)
- Script should handle missing environment variables gracefully
- Hook failures are logged but don't stop the loop by default (unless `hooks.fail_fast` is enabled in config)

### Configuration

Hook behavior is controlled in your config file:

```json
{
  "hooks": {
    "enabled": true,
    "fail_fast": false
  }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `hooks.enabled` | `true` | Enable/disable all hooks |
| `hooks.fail_fast` | `false` | Stop loop if a hook fails (true) or continue (false) |

## How It Works

### The Loop

```
┌──────────────────────────────────────────┐
│                 cub                      │
│                                           │
│  Tasks ────▶ Find Ready Task             │
│                     │                     │
│                     ▼                     │
│              Generate Prompt              │
│                     │                     │
│                     ▼                     │
│           AI Harness (claude/codex)       │
│                     │                     │
│                     ▼                     │
│              Task Complete?               │
│                /        \                 │
│               ▼          ▼                │
│            Loop        Done               │
└──────────────────────────────────────────┘
```

### Prompt Structure

Cub generates two prompts for each iteration:

1. **System Prompt** (from `PROMPT.md`): Static instructions about workflow, rules, and completion signals
2. **Task Prompt**: Current task details including ID, description, and acceptance criteria

### Feedback Loops

The agent runs these before committing:
1. Type checking (tsc, mypy, etc.)
2. Tests (jest, pytest, etc.)
3. Linting (eslint, ruff, etc.)
4. Build (if applicable)

If any fail, the agent must fix before proceeding.

### Completion Signal

When all tasks have `status: "closed"`, the agent outputs:

```
<promise>COMPLETE</promise>
```

This signals cub to exit the loop.

## Advanced Usage

### Streaming Mode

Watch agent activity in real-time:

```bash
cub run --stream
```

Shows tool calls, responses, and costs as they happen.

### Debug Mode

Get verbose output for troubleshooting:

```bash
cub run --debug --once
```

Includes:
- Full prompts being sent
- Full harness command line (for copy-paste debugging)
- Task selection details
- Timing information
- Acceptance criteria logging
- Saves prompts to temp files

### Planning Mode

Analyze codebase and update fix_plan.md:

```bash
cub run --plan
```

Uses parallel subagents to study code, find TODOs, and document issues.

### Migrating to Beads

Convert existing prd.json to beads format:

```bash
# Preview what would happen
cub --migrate-to-beads-dry-run

# Perform migration
cub --migrate-to-beads
```

## Tips

### Task Sizing
Keep tasks small enough to complete in one iteration (~one context window). If a task feels big, break it into subtasks.

### Specifications
The more detailed your specs, the better the output. Put them in `specs/` and reference them in task descriptions.

### Progress Memory
The agent appends to `progress.txt` after each task. This creates memory across iterations - patterns discovered, gotchas encountered.

### Recovery
If the codebase gets into a broken state:
```bash
git reset --hard HEAD~1  # Undo last commit
cub                      # Restart loop
```

### Choosing a Harness

| Harness | Best For |
|---------|----------|
| Claude Code | General coding, complex refactoring, multi-file changes |
| Codex | Quick fixes, OpenAI ecosystem projects |

## Files Reference

| File | Purpose |
|------|---------|
| `cub` | Main script - the autonomous loop |
| `cub-init` | Project and global initialization |
| `lib/harness.sh` | AI harness abstraction (claude/codex) |
| `lib/tasks.sh` | Task backend abstraction (beads/json) |
| `lib/beads.sh` | Beads CLI wrapper functions |
| `lib/xdg.sh` | XDG Base Directory helpers |
| `lib/config.sh` | Configuration loading and merging |
| `lib/logger.sh` | Structured JSONL logging |
| `templates/PROMPT.md` | Default system prompt |
| `templates/AGENT.md` | Default agent instructions |

## License

MIT
