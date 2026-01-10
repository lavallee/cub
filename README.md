# Curb

**C**oding **U**nder **R**alph + **B**eads


An autonomous AI coding agent harness that drives AI coding CLIs in a loop to build software from a structured task backlog.

Combines the [Ralph Wiggum technique](https://ghuntley.com/ralph/) (running an AI agent in a while loop) with [beads-style](https://github.com/steveyegge/beads) task management (hash IDs, P0-P4 priorities, dependency tracking).

## Features

- **Multi-Harness Support**: Works with Claude Code or OpenAI Codex CLI
- **Dual Task Backend**: Use beads CLI or simple prd.json for task management
- **Autonomous Loop**: Runs until all tasks are complete
- **Dependency Tracking**: Respects task dependencies, picks ready tasks
- **Priority Scheduling**: P0-P4 priority-based task selection
- **Epic/Label Filtering**: Target specific epics or labeled tasks
- **Per-Task Model Selection**: Tasks with `model:X` labels auto-select the model
- **Structured Logging**: JSONL logs with timestamps, durations, and git SHAs
- **Global + Project Config**: XDG-compliant configuration with overrides
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
# Clone curb to your tools directory
git clone https://github.com/lavallee/curb ~/tools/curb

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$PATH:$HOME/tools/curb"

# Or create symlinks
ln -s ~/tools/curb/curb /usr/local/bin/curb
ln -s ~/tools/curb/curb-init /usr/local/bin/curb-init
```

## Quick Start

```bash
# First-time setup (creates global config and directories)
curb-init --global

# Initialize a new project
cd my-project
curb-init

# Edit prd.json with your tasks (or use beads: bd init && bd create "Task")
# Add specifications to specs/
# Update AGENT.md with build instructions

# Check status
curb --status

# Run the autonomous loop
curb

# Or target a specific epic
curb --epic my-epic-id

# Or filter by label
curb --label phase-1
```

## Usage

```bash
# Core commands
curb              # Run loop until all tasks complete
curb --once       # Run single iteration
curb --status     # Show current task status
curb --ready      # Show ready (unblocked) tasks
curb --plan       # Run planning mode

# Filtering (works with beads or JSON backend)
curb --epic <id>      # Target tasks within a specific epic
curb --label <name>   # Target tasks with a specific label
curb --epic curb-1gq --label phase-1  # Combine filters

# Harness selection
curb --harness claude    # Use Claude Code (default)
curb --harness codex     # Use OpenAI Codex CLI

# Backend selection
curb --backend beads     # Force beads backend
curb --backend json      # Force JSON backend

# Output modes
curb --stream     # Stream harness activity in real-time
curb --debug      # Enable verbose debug logging

# Migration tools
curb --migrate-to-beads          # Migrate prd.json to beads
curb --migrate-to-beads-dry-run  # Preview migration

# Debugging
curb --test          # Test harness invocation
curb --dump-prompt   # Save prompts to files for inspection
curb --help          # Show help
```

## Project Structure

After running `curb-init`, your project will have:

```
my-project/
├── prd.json        # Task backlog (beads-style format)
├── PROMPT.md       # Loop prompt template (system instructions)
├── AGENT.md        # Build/run instructions for the agent
├── AGENTS.md       # Symlink to AGENT.md (for Codex compatibility)
├── progress.txt    # Session learnings (agent appends)
├── fix_plan.md     # Discovered issues and plans
└── specs/          # Detailed specifications
```

## Task Backends

Curb supports two task management backends:

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

# Curb auto-detects .beads/ directory
curb --status  # Uses beads backend automatically
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
bd label add curb-abc model:haiku     # Use fast model for simple tasks
bd label add curb-xyz model:sonnet    # Use balanced model for complex tasks
bd label add curb-123 model:opus-4.5  # Use most capable model for hard tasks
```

In JSON backend, add labels to the task:
```json
{
  "id": "prd-abc",
  "title": "Quick fix",
  "labels": ["model:haiku", "phase-1"]
}
```

When curb picks up a task with a `model:` label, it automatically sets `CURB_MODEL` to pass to the Claude harness.

### Task Selection Algorithm

1. Find tasks where `status == "open"`
2. Filter to tasks where all `dependsOn` items are `closed`
3. Sort by priority (P0 first)
4. Pick the first one

## AI Harnesses

Curb abstracts the AI coding CLI into a "harness" layer, supporting multiple backends:

### Claude Code (Default)

```bash
curb --harness claude
# or
export HARNESS=claude
```

Uses Claude Code's `--append-system-prompt` for clean prompt separation.

### OpenAI Codex

```bash
curb --harness codex
# or
export HARNESS=codex
```

Uses Codex's `--full-auto` mode with combined prompts.

### Google Gemini

```bash
curb --harness gemini
# or
export HARNESS=gemini
```

Uses Gemini CLI's `-y` (YOLO mode) for autonomous operation.

### OpenCode

```bash
curb --harness opencode
# or
export HARNESS=opencode
```

Uses OpenCode's `run` subcommand with JSON output for token tracking.

### Auto-Detection

By default, curb auto-detects available harnesses using this priority order:
1. **Explicit HARNESS setting** (CLI flag `--harness` or env var `HARNESS`)
2. **Config priority array** (`harness.priority` in config file)
3. **Default detection order**: claude > opencode > codex > gemini

#### Configuration Example

You can customize the harness priority in `.curb.json` or global config:

```json
{
  "harness": {
    "priority": ["gemini", "claude", "codex", "opencode"]
  }
}
```

Curb will try each harness in order and use the first one available. If none are found, it falls back to the default order.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CURB_PROJECT_DIR` | `$(pwd)` | Project directory |
| `CURB_MAX_ITERATIONS` | `100` | Max loop iterations |
| `CURB_DEBUG` | `false` | Enable debug mode |
| `CURB_STREAM` | `false` | Enable streaming output |
| `CURB_BACKEND` | `auto` | Task backend: `auto`, `beads`, `json` |
| `CURB_EPIC` | | Filter to tasks within this epic ID |
| `CURB_LABEL` | | Filter to tasks with this label |
| `CURB_MODEL` | | Override model for Claude harness |
| `CURB_BUDGET` | | Override token budget (overrides config) |
| `HARNESS` | `auto` | AI harness: `auto`, `claude`, `codex`, `opencode`, `gemini` |
| `CLAUDE_FLAGS` | | Extra flags for Claude Code |
| `CODEX_FLAGS` | | Extra flags for Codex CLI |
| `GEMINI_FLAGS` | | Extra flags for Gemini CLI |
| `OPENCODE_FLAGS` | | Extra flags for OpenCode CLI |

## Configuration

Curb uses XDG-compliant configuration with global and project-level overrides.

### Global Setup

```bash
curb-init --global
```

Creates:
- `~/.config/curb/config.json` - Global configuration
- `~/.config/curb/hooks/` - Hook directories
- `~/.local/share/curb/logs/` - Log storage
- `~/.cache/curb/` - Cache directory

### Configuration Precedence

1. **CLI flags** (highest priority)
2. **Environment variables**
3. **Project config** (`.curb.json` in project root)
4. **Global config** (`~/.config/curb/config.json`)
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

Create `.curb.json` in your project root to override global settings:

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

Curb logs all task executions in JSONL format for debugging and analytics.

### Log Location

```
~/.local/share/curb/logs/{project}/{session}.jsonl
```

Session ID format: `YYYYMMDD-HHMMSS` (e.g., `20260109-214858`)

### Log Events

Each task produces structured events:

```json
{"timestamp":"2026-01-09T21:48:58Z","event_type":"task_start","data":{"task_id":"curb-abc","task_title":"Fix bug","harness":"claude"}}
{"timestamp":"2026-01-09T21:52:30Z","event_type":"task_end","data":{"task_id":"curb-abc","exit_code":0,"duration":212,"tokens_used":0,"git_sha":"abc123..."}}
```

### Querying Logs

```bash
# Find all task starts
jq 'select(.event_type=="task_start")' ~/.local/share/curb/logs/myproject/*.jsonl

# Find failed tasks
jq 'select(.event_type=="task_end" and .data.exit_code != 0)' logs/*.jsonl

# Calculate total duration
jq -s '[.[].data.duration // 0] | add' logs/*.jsonl
```

## How It Works

### The Loop

```
┌──────────────────────────────────────────┐
│                 curb                      │
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

Curb generates two prompts for each iteration:

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

This signals curb to exit the loop.

## Advanced Usage

### Streaming Mode

Watch agent activity in real-time:

```bash
curb --stream
```

Shows tool calls, responses, and costs as they happen.

### Debug Mode

Get verbose output for troubleshooting:

```bash
curb --debug --once
```

Includes:
- Full prompts being sent
- Task selection details
- Timing information
- Saves prompts to temp files

### Planning Mode

Analyze codebase and update fix_plan.md:

```bash
curb --plan
```

Uses parallel subagents to study code, find TODOs, and document issues.

### Migrating to Beads

Convert existing prd.json to beads format:

```bash
# Preview what would happen
curb --migrate-to-beads-dry-run

# Perform migration
curb --migrate-to-beads
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
curb                      # Restart loop
```

### Choosing a Harness

| Harness | Best For |
|---------|----------|
| Claude Code | General coding, complex refactoring, multi-file changes |
| Codex | Quick fixes, OpenAI ecosystem projects |

## Files Reference

| File | Purpose |
|------|---------|
| `curb` | Main script - the autonomous loop |
| `curb-init` | Project and global initialization |
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
