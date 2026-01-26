# Cub

**Work ahead of your AI coding agents, then let them run.**

Cub is for developers who are already running AI coding CLIs (Claude Code, Codex, OpenCode) in autonomous mode and want more structure. If you're juggling multiple agent sessions, manually routing work to different models, or finding that fully hands-off agents tend to run amok—Cub helps you work *ahead* of execution so you can be more hands-off *during* execution.

## Quick Install

```bash
curl -LsSf https://install.cub.tools | bash
```

Then restart your shell (or open a new terminal) and run:

```bash
cub init --global
```

(Already installed? Run `pipx upgrade cub` or re-run the installer.)

## The Problem

AI coding agents in 2026 are powerful. They can operate for hours, produce working code, run tests, and iterate toward production quality. But there's a gap:

- **Too hands-on**: Sitting in an IDE, approving every tool call, staying close to the work
- **Too hands-off**: Letting agents run wild with vague instructions, hoping for the best

Cub finds the balance. You invest time *before* code starts flying—breaking work into agent-sized tasks, routing complexity to the right models, reviewing the plan—then step back and let execution happen more seamlessly.

## Two Main Steps: Prep and Run

### Step 1. `cub prep`: Go From a Vision to Structured Tasks

Bring your ideas (a sentence, a spec, a whole design doc) and go through a structured interview to generate clear tasks for an LLM:

1. **Triage** — What are we trying to accomplish? What are the goals?
2. **Architect** — What makes sense technically? What's the implementation approach?
3. **Plan** — Break it into agent-sized chunks with clear acceptance criteria
4. **Bootstrap** — Write tasks to your chosen backend (beads or JSON)

The goal: observable, reviewable work *before* any code is written. No gaps in understanding slip through.

```bash
cub prep                    # Run full pipeline
cub triage                  # Or run stages individually
cub architect
cub plan
cub bootstrap
```

### Step 2: `cub run`: Turn Tasks Into Code

Once you have structured tasks, Cub runs the [Ralph Wiggum loop](https://ghuntley.com/ralph/)—picking ready tasks, generating prompts, invoking your chosen AI harness, and iterating until done or budget exhausted.

```bash
cub run                     # Run until complete
cub run --once              # Single iteration
cub run --epic my-feature   # Target specific work
```

The execution loop handles dependency ordering, failure recovery, git commits, and structured logging. You can watch it stream or check in later.

## Key Features

### Right Model for the Task

Not everything needs Opus. Cub supports per-task model selection:

```bash
bd label add cub-abc model:haiku     # Simple rename, use fast model
bd label add cub-xyz model:sonnet    # Medium complexity
bd label add cub-123 model:opus      # Complex architecture work
```

Route simple refactoring to Haiku, medium tasks to Sonnet, reserve Opus for planning and complex work. Manage tokens as a resource.

### Multi-Harness Flexibility

Cub abstracts across multiple AI coding CLIs:

- **Claude Code** — General coding, complex refactoring (default)
- **OpenAI Codex** — Quick fixes, OpenAI ecosystem
- **Google Gemini** — Alternative perspective
- **OpenCode** — Open-source option

Each harness evolves rapidly. New capabilities emerge in one that may not exist in others. Cub lets you use the right tool without vendor lock-in.

```bash
cub run --harness claude    # Explicit selection
cub run --harness codex
```

### Deterministic Control Layer

Building outside any single harness means the core loop—task selection, success/failure detection, retry logic, state transitions—runs as traditional software, not LLM inference. This enables:

- **Reliable hooks**: Email when a task completes, not "hopefully the agent remembers"
- **Consistent logging**: Structured JSONL, not scattered console output
- **Predictable budgets**: Hard limits that actually stop execution

## Features

- **Autonomous Loop**: Runs until all tasks complete or budget exhausted
- **Dependency Tracking**: Respects task dependencies, picks ready tasks
- **Priority Scheduling**: P0-P4 priority-based task selection
- **Epic/Label Filtering**: Target specific epics or labeled tasks
- **Budget Management**: Token tracking with configurable limits and warnings
- **Guardrails**: Iteration limits, secret redaction, safety controls
- **Failure Handling**: Configurable modes (stop, move-on, retry, triage)
- **Session Management**: Named sessions, artifact bundles per task
- **Git Workflow**: Auto-branching, commit per task, clean state enforcement
- **Hooks System**: Custom scripts at 5 lifecycle points
- **Structured Logging**: JSONL logs with timestamps, durations, git SHAs
- **Dual Task Backend**: Use [beads](https://github.com/steveyegge/beads) CLI or simple JSON file
- **Streaming Output**: Watch agent activity in real-time
- **Dashboard**: Unified Kanban board visualization of project state across 8 columns

## Dashboard

Cub includes an integrated dashboard that provides a unified Kanban view of your entire project state—from initial ideas through release.

### 8-Column Kanban Workflow

The dashboard visualizes work across 8 stages:

1. **CAPTURES** — Raw ideas and notes
2. **SPECS** — Specifications being researched
3. **PLANNED** — Specs in planning or existing plans
4. **READY** — Tasks ready to work (no blockers)
5. **IN_PROGRESS** — Active development and implementing specs
6. **NEEDS_REVIEW** — Awaiting code review or approval
7. **COMPLETE** — Done but not released
8. **RELEASED** — Shipped to production/users

### Data Aggregation

The dashboard automatically aggregates data from multiple sources:

- **Specs** — From `specs/**/*.md` with frontmatter
- **Plans** — From `.cub/sessions/*/plan.jsonl`
- **Tasks** — From your beads or JSON backend
- **Ledger** — Completion records from `.cub/ledger/`
- **Changelog** — Released versions from `CHANGELOG.md`

### Running the Dashboard

```bash
# Start the dashboard API server
uvicorn cub.core.dashboard.api.app:app --reload --port 8000

# Open in your browser
open http://localhost:8000

# View API documentation
open http://localhost:8000/docs
```

### Customizing Views

Create custom Kanban views in `.cub/views/my-view.yaml`:

```yaml
id: my-view
name: My Workflow View
description: Customized view for my team

columns:
  - id: ready
    title: Ready to Start
    stages: [READY]
  - id: active
    title: In Progress
    stages: [IN_PROGRESS]
    group_by: epic_id  # Group by epic

filters:
  exclude_labels: [archived]
  include_types: [task, epic]

display:
  show_cost: true
  show_tokens: false
  card_size: compact
```

For details, see [.cub/views/README.md](.cub/views/README.md).

### Linking Entities

Use explicit relationship markers in frontmatter to link specs, plans, and tasks:

**Spec to Plan:**
```yaml
---
id: spec-auth
title: Authentication Flow
spec_id: cub-vd6  # Links to plan cub-vd6
---
```

**Plan to Epic:**
```yaml
---
id: plan-auth-flow
title: Auth Implementation Plan
plan_id: cub-vd6  # Links to epic cub-vd6
---
```

**Task to Epic:**
Created automatically by bootstrap, or add `epic_id` label:
```bash
bd label add cub-abc epic:cub-vd6
```

## Prerequisites

- **Python 3.10+** (required)
- **Harness** (Claude and others):
  - [Claude Code CLI](https://github.com/anthropics/claude-code) (`claude`) - Required for `cub prep`, recommended for `cub run`.
  - [OpenAI Codex CLI](https://github.com/openai/codex) (`codex`)
  - [Google Gemini CLI](https://github.com/google-gemini-cli) (`gemini`)
  - [OpenCode CLI](https://github.com/opencode) (`opencode`)
- **Task Backend** (optional):
  - [beads CLI](https://github.com/steveyegge/beads) (`bd`) - For advanced task management

## Installation

### One-Liner (Recommended)

```bash
curl -LsSf https://install.cub.tools | bash
```

This will:
- Install cub via pipx (installing pipx if needed)
- Add cub to your PATH
- Run `cub init --global` to set up config directories

Restart your shell after installation.

### Alternative Methods

<details>
<summary>Using pipx manually</summary>

```bash
pipx install git+https://github.com/lavallee/cub.git
cub init --global
```
</details>

<details>
<summary>Using uv</summary>

```bash
uv tool install git+https://github.com/lavallee/cub.git
cub init --global
```
</details>

<details>
<summary>From source (for development)</summary>

```bash
git clone https://github.com/lavallee/cub ~/tools/cub
cd ~/tools/cub
uv sync  # or: python3.10 -m venv .venv && source .venv/bin/activate && pip install -e .
export PATH="$HOME/tools/cub/.venv/bin:$PATH"
cub init --global
```

Add the PATH export to your `~/.bashrc` or `~/.zshrc`.
</details>

## Quick Start

```bash
cd my-project
cub init                    # Initialize project
```

### Path A: Start with Prep (Recommended)

When starting new work, use the prep pipeline to turn your ideas into structured tasks:

```bash
# Run the full prep interview
cub prep

# Or run stages individually for more control
cub triage      # Clarify goals and requirements
cub architect   # Design technical approach
cub plan        # Break into agent-sized tasks
cub bootstrap   # Write tasks to backend
```

### Path B: Create Tasks Directly

If you already know what needs doing:

```bash
# Using beads (recommended)
bd init
bd create "Implement user authentication" --type feature --priority 2
bd create "Add login form" --type task --priority 2

# Or edit prd.json directly (JSON backend)
```

### Run the Loop

```bash
cub status              # Check what's ready
cub run                 # Run until complete
cub run --once          # Single iteration
cub run --epic my-epic  # Target specific work
cub run --stream        # Watch in real-time
```

**Upgrading from v0.20 (Bash)?** See [UPGRADING.md](UPGRADING.md) for migration guide.

## Usage

### Prep Commands (Vision → Tasks)

```bash
# Full prep pipeline
cub prep                    # Run triage → architect → plan → bootstrap

# Individual stages (for more control)
cub triage                  # Clarify requirements and goals
cub architect               # Design technical implementation
cub plan                    # Break into agent-sized tasks
cub bootstrap               # Write tasks to backend

# Manage prep sessions
cub sessions                # List prep sessions
cub interview <task-id>     # Deep-dive on a specific task
cub interview --all --auto  # Batch interview all open tasks
```

### Run Commands (Tasks → Code)

```bash
# Execute the loop
cub run                     # Run until all tasks complete
cub run --once              # Single iteration
cub run --ready             # Show ready (unblocked) tasks
cub run --plan              # Run planning mode
cub run --name myname       # Custom session name

# Filtering
cub run --epic <id>         # Target tasks within a specific epic
cub run --label <name>      # Target tasks with a specific label
cub run --epic cub-1gq --label phase-1  # Combine filters

# Harness selection
cub run --harness claude    # Use Claude Code (default)
cub run --harness codex     # Use OpenAI Codex CLI
cub run --harness gemini    # Use Google Gemini
cub run --harness opencode  # Use OpenCode

# Output modes
cub run --stream            # Stream harness activity in real-time
cub run --debug             # Enable verbose debug logging
```

### Other Commands

```bash
# Setup
cub init                    # Initialize current project
cub init --global           # Set up global config

# Status and inspection
cub status                  # Show task progress
cub status --json           # JSON output for scripting
cub explain <task-id>       # Show full task details
cub artifacts               # List task outputs

# Git workflow
cub branch <epic-id>        # Create branch bound to epic
cub branches                # List branch-epic bindings
cub pr <epic-id>            # Create pull request for epic

# Utilities
cub validate                # Check beads state and config
cub doctor                  # Diagnose configuration issues
cub --migrate-to-beads      # Migrate prd.json to beads
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

## Task State Synchronization

Cub automatically syncs task state to a dedicated git branch (`cub-sync`) to ensure task progress persists across git clones and team collaboration. This sync happens independently of your working tree—no checkout required.

### How Auto-Sync Works

When you run `cub run`, the sync service:

1. **Initializes** the `cub-sync` branch (if not already created)
2. **Commits** task state to the branch after each task completion
3. **Tracks** changes using git plumbing commands (no working tree impact)
4. **Persists** `.cub/tasks.jsonl` in git history for recovery

### Auto-Sync Behavior

By default, auto-sync triggers after every task completion during `cub run`:

```bash
cub run                      # Auto-syncs after each task (default)
cub run --no-sync            # Disable auto-sync for this run
```

### Configuration

Control auto-sync behavior in your config file:

**Global config** (`~/.config/cub/config.json`):
```json
{
  "sync": {
    "enabled": true,
    "auto_sync": "run"
  }
}
```

**Project override** (`.cub.json`):
```json
{
  "sync": {
    "enabled": true,
    "auto_sync": "never"
  }
}
```

### Auto-Sync Modes

| Mode | Behavior |
|------|----------|
| `run` | Auto-sync during `cub run` only (default) |
| `always` | Auto-sync on every task mutation |
| `never` | Manual sync only (use `cub sync commit`) |

### Sync Commands

Manual sync operations are available via the CLI:

```bash
# Initialize sync branch
cub sync init

# Commit current task state
cub sync commit -m "Update tasks"

# Push to remote
cub sync push

# Pull remote changes
cub sync pull

# Check sync status
cub sync status
```

### Failure Handling

Auto-sync failures are logged but don't stop task execution:

- **Sync fails**: Warning logged, task still completes
- **Git unavailable**: Sync disabled for the run
- **No changes**: Commit skipped (same task state)

Example output:
```
✓ Task cub-abc completed
⚠ Warning: Failed to sync task state: git not found in PATH
```

### Multi-Task Runs

During multi-task runs, each task completion triggers a sync commit:

```bash
# Run with 3 tasks
cub run

# Creates 3 commits on cub-sync branch:
# - "Task cub-001 completed"
# - "Task cub-002 completed"
# - "Task cub-003 completed"
```

### Disabling Auto-Sync

To run without auto-sync (e.g., for testing):

```bash
# Temporary disable (this run only)
cub run --no-sync

# Permanent disable (config)
# Edit .cub.json:
{
  "sync": {
    "auto_sync": "never"
  }
}
```

### Collaboration

The `cub-sync` branch enables team collaboration on task state:

1. **Push** your local sync branch: `cub sync push`
2. **Team member pulls**: `cub sync pull`
3. **Conflicts** resolved using last-write-wins (based on `updated_at`)
4. **Recovery**: Clone repo, pull sync branch, continue work

### Technical Details

- **Branch**: `cub-sync` (configurable)
- **File**: `.cub/tasks.jsonl` committed to sync branch
- **Method**: Git plumbing (`git hash-object`, `git commit-tree`)
- **Working tree**: Never touched (uses `git update-ref`)
- **Conflict resolution**: Last-write-wins based on task `updated_at` timestamp

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

Cub supports eight hook points:

| Hook | When It Runs | Use Cases |
|------|--------------|-----------|
| `pre-loop` | Before starting the main loop | Setup, initialization, cleanup from previous run |
| `pre-task` | Before each task execution | Prepare environment, start timers |
| `post-task` | After each task (success or failure) | Notifications, metrics, logging |
| `on-error` | When a task fails | Alerts, incident creation, diagnostics |
| `on-budget-warning` | When budget crosses threshold (80%) | Cost alerts, scaling decisions |
| `on-all-tasks-complete` | When all tasks are done | Final notifications, trigger next phase |
| `post-loop` | After the main loop completes | Cleanup, final notifications, reports |
| `post-init` | After `cub init` completes | Custom project setup, install team hooks |

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
| `hooks.async_notifications` | `true` | Run post-task/on-error hooks asynchronously |

### Async Hooks

By default, `post-task` and `on-error` hooks run asynchronously (non-blocking). This means:

- These hooks fire in the background and don't slow down the main loop
- The next task can start while notifications are being sent
- All async hooks are collected before the session ends

To disable async execution and wait for each hook:

```json
{
  "hooks": {
    "async_notifications": false
  }
}
```

**Note:** `pre-loop`, `pre-task`, and `post-loop` hooks always run synchronously because they must complete before the next phase begins.

### Troubleshooting Hooks

**Hooks not running:**
- Verify `hooks.enabled: true` in config
- Check scripts are executable: `chmod +x <script>`
- Verify directory structure: `.cub/hooks/{hook-name}.d/`

**Hook timeout:**
- Hooks have a **5-minute timeout** (300 seconds)
- Long operations should use `timeout` command internally

**Hook failed:**
- Check output for error messages
- Exit code 0 = success, non-zero = failure
- With `fail_fast: false` (default), failures are logged but don't stop cub

**Naming convention:**
- Use numeric prefixes to control order: `01-first.sh`, `02-second.sh`
- Scripts run in alphabetical order (global before project)

### Hook Best Practices

1. **Make hooks idempotent** - Safe to run multiple times
2. **Handle missing variables** - Use `${VAR:-default}` syntax
3. **Exit cleanly** - Always `exit 0` for success
4. **Log with prefix** - `echo "[hook-name] message"` for clarity
5. **Use numeric prefixes** - `10-setup.sh`, `20-main.sh`, `90-cleanup.sh`
6. **Store state in `.cub/`** - For inter-hook communication
7. **Keep hooks fast** - Under 30 seconds ideally
8. **Test locally first** - `CUB_TASK_ID=test ./hook.sh`

Example with best practices:

```bash
#!/usr/bin/env bash
# 10-slack-notify.sh - Post task completion to Slack

set -euo pipefail

# Handle missing variables gracefully
TASK_ID="${CUB_TASK_ID:-unknown}"
EXIT_CODE="${CUB_EXIT_CODE:-0}"

# Skip if no webhook configured
if [[ -z "${SLACK_WEBHOOK_URL:-}" ]]; then
    echo "[slack-notify] No SLACK_WEBHOOK_URL set, skipping"
    exit 0
fi

# Send notification
curl -s -X POST "$SLACK_WEBHOOK_URL" \
    -H 'Content-type: application/json' \
    -d "{\"text\": \"Task $TASK_ID completed (exit code: $EXIT_CODE)\"}" \
    > /dev/null

echo "[slack-notify] Notification sent for $TASK_ID"
exit 0
```

## Toolsmith: Tool Discovery and Management

Cub includes **Toolsmith**, a built-in tool discovery system to help you find, evaluate, and catalog tools (MCP servers, skills, and integrations) from multiple sources.

### Quick Start

**Sync tools from all sources:**
```bash
cub toolsmith sync
```

**Search for tools:**
```bash
cub toolsmith search "database"
```

**View catalog statistics:**
```bash
cub toolsmith stats
```

### Commands

| Command | Purpose |
|---------|---------|
| `cub toolsmith sync [--source NAME]` | Populate catalog from external sources |
| `cub toolsmith search QUERY [--source NAME]` | Find tools by name, description, or capability |
| `cub toolsmith stats` | View catalog statistics and last sync time |

### Sources

Toolsmith syncs from multiple sources:

- **Smithery** - MCP server registry
- **Glama** - AI tool and skill marketplace
- **SkillsMP** - Multi-provider skills platform
- **ClawdHub** - Claude-focused tools

### Configuration

Toolsmith stores the tool catalog in:
- **SQLite database**: `~/.cub/toolsmith.db`
- **Override**: Set `CUB_TOOLSMITH_DB` environment variable

### Common Use Cases

```bash
# Populate your catalog (do this first)
cub toolsmith sync

# Find database tools
cub toolsmith search "database"

# Filter by source
cub toolsmith search "api" --source smithery

# Check what's been synced
cub toolsmith stats
```

### Documentation

For detailed documentation, examples, and troubleshooting, see [docs/toolsmith.md](docs/toolsmith.md).

---

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

## Source Code Reference

| Module | Purpose |
|--------|---------|
| `src/cub/cli/` | Typer CLI subcommands (run, status, init, prep commands) |
| `src/cub/core/config.py` | Configuration loading and merging |
| `src/cub/core/models.py` | Pydantic data models (Task, Config, etc.) |
| `src/cub/core/tasks/` | Task backends (beads, JSON) |
| `src/cub/core/harness/` | AI harness backends (Claude, Codex, Gemini, OpenCode) |
| `src/cub/core/logger.py` | Structured JSONL logging |
| `templates/PROMPT.md` | Default system prompt |
| `templates/AGENT.md` | Default agent instructions |

## License

MIT
