---
title: cub run
description: Execute the autonomous task loop with AI harnesses.
---

# cub run

Execute the autonomous task loop. This is the primary command for running AI agents on your tasks.

---

## Synopsis

```bash
cub run [OPTIONS]
```

---

## Description

The `run` command executes the main cub loop:

1. **Find** the highest-priority ready task
2. **Generate** a prompt from the task details
3. **Invoke** the AI harness (Claude, Codex, Gemini, etc.)
4. **Monitor** execution and track token usage
5. **Loop** until tasks complete or budget exhausts

The loop continues until one of these conditions is met:

- All tasks are complete
- Budget is exhausted (tokens or cost)
- Maximum iterations reached
- User interrupt (Ctrl+C)
- `--once` flag used (single iteration)

---

## Options

### Core Options

| Option | Short | Description |
|--------|-------|-------------|
| `--harness NAME` | `-h` | AI harness to use (`claude`, `codex`, `gemini`, `opencode`) |
| `--once` | `-1` | Run a single iteration then exit |
| `--task ID` | `-t` | Run specific task by ID |
| `--model NAME` | `-m` | Model to use (e.g., `sonnet`, `opus`, `haiku`) |
| `--name NAME` | `-n` | Session name for tracking |

### Filtering Options

| Option | Short | Description |
|--------|-------|-------------|
| `--epic ID` | `-e` | Only work on tasks in this epic |
| `--label LABEL` | `-l` | Only work on tasks with this label |
| `--ready` | `-r` | List ready tasks without running |

### Budget Options

| Option | Short | Description |
|--------|-------|-------------|
| `--budget AMOUNT` | `-b` | Maximum budget in USD |
| `--budget-tokens COUNT` | | Maximum token budget |

### Output Options

| Option | Short | Description |
|--------|-------|-------------|
| `--stream` | `-s` | Stream harness output in real-time |
| `--monitor` | | Launch with live dashboard in tmux split pane |

### Isolation Options

| Option | Description |
|--------|-------------|
| `--worktree` | Run in isolated git worktree |
| `--worktree-keep` | Keep worktree after run completes |
| `--sandbox` | Run in Docker sandbox for isolation |
| `--sandbox-keep` | Keep sandbox container after run |
| `--no-network` | Disable network access (requires `--sandbox`) |
| `--parallel N` | `-p` | Run N tasks in parallel, each in its own worktree |

### Direct Mode Options

| Option | Short | Description |
|--------|-------|-------------|
| `--direct TASK` | `-d` | Run directly with provided task (string, @file, or `-` for stdin) |
| `--gh-issue NUM` | | Work on a specific GitHub issue by number |

---

## Examples

### Basic Usage

```bash
# Run with auto-detected harness
cub run

# Run with specific harness
cub run --harness claude

# Single iteration mode
cub run --once

# Run with streaming output
cub run --stream
```

### Task Filtering

```bash
# Run specific task
cub run --task cub-123

# Work only on epic's tasks
cub run --epic backend-v2

# Work on labeled tasks
cub run --label priority

# List ready tasks without running
cub run --ready
```

### Budget Control

```bash
# Set cost budget to $5
cub run --budget 5.0

# Set token budget
cub run --budget-tokens 100000

# Combine budget limits
cub run --budget 10.0 --budget-tokens 500000
```

### Monitoring

```bash
# Stream output in real-time
cub run --stream

# Launch with tmux dashboard
cub run --monitor

# Named session for tracking
cub run --name "auth-feature"
```

### Isolation

```bash
# Run in isolated git worktree
cub run --worktree

# Keep worktree after completion
cub run --worktree --worktree-keep

# Run in Docker sandbox
cub run --sandbox

# Sandbox without network access
cub run --sandbox --no-network
```

### Parallel Execution

```bash
# Run 3 independent tasks in parallel
cub run --parallel 3

# Parallel with specific harness
cub run --parallel 4 --harness claude
```

### Direct Mode

```bash
# Run with inline task description
cub run --direct "Add a logout button to the navbar"

# Read task from file
cub run --direct @task.txt

# Read task from stdin
echo "Fix the typo in README" | cub run --direct -

# Work on GitHub issue
cub run --gh-issue 123
```

---

## Harness Selection

Cub auto-detects available harnesses in this priority order:

1. `claude` - Claude Code
2. `gemini` - Google Gemini
3. `codex` - OpenAI Codex
4. `opencode` - OpenCode

Override with `--harness` or configure in `.cub.json`:

```json
{
  "harness": {
    "default": "claude",
    "priority": ["claude", "gemini", "codex"]
  }
}
```

---

## Model Selection

Specify models using the `--model` flag or task labels:

```bash
# Use opus model
cub run --model opus

# Use via environment
CUB_MODEL=sonnet cub run
```

Tasks can specify a model via labels:

```bash
bd create "Complex refactoring" --labels "model:opus"
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Run completed successfully |
| `1` | Run failed (task error, harness error, etc.) |
| `130` | Interrupted by user (Ctrl+C) |

---

## Signal Handling

Cub handles `SIGINT` (Ctrl+C) gracefully:

1. **First interrupt**: Finishes current task, then exits
2. **Second interrupt**: Force exits immediately

---

## Status File

Each run creates a status file at:

```
.cub/runs/{session-id}/status.json
```

The status file contains:

- Current phase and iteration
- Task progress
- Budget usage (tokens, cost)
- Event log

Monitor with `cub monitor` or read directly.

---

## Related Commands

- [`cub status`](status.md) - View task progress
- [`cub monitor`](monitor.md) - Live dashboard
- [`cub artifacts`](artifacts.md) - View run outputs
- [`cub plan`](plan.md) - Create tasks from vision

---

## See Also

- [Run Loop Guide](../guide/run-loop/index.md) - Understanding the execution loop
- [Task Selection](../guide/run-loop/selection.md) - How tasks are prioritized
- [Budget Guide](../guide/budget/index.md) - Managing token and cost limits
