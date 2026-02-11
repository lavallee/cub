---
title: "Recipe: Overnight Batch"
description: Set up and run autonomous AI agents overnight on a large task queue.
---

# Autonomous Overnight Run

Queue up a full backlog of tasks, set a budget ceiling, launch before bed, and wake up to completed work. This recipe walks through configuring and running an unattended overnight session with 20+ tasks across multiple epics.

## What You'll Do

1. Audit your task queue to confirm everything is ready
2. Set a dollar-amount budget as a safety net
3. Route tasks to the right model tier based on complexity
4. Launch in a persistent terminal session
5. Review results, ledger entries, and git history the next morning
6. Triage any failures

**Time to set up:** ~10 minutes. **Run time:** hours (overnight).

---

## Prerequisites

- Tasks already planned and staged (`cub plan` + `cub stage`, or manually created)
- At least one AI harness installed and authenticated (Claude Code, Codex, etc.)
- `cub init` completed in the project
- Sufficient API credits for the expected workload

---

## Step 1: Review Your Queue

Start by confirming your tasks are ready and dependencies are satisfied.

```bash
# See all tasks that are unblocked and ready to execute
cub task ready --agent

# Get a high-level project summary
cub status

# Check for blocked tasks to ensure dependencies are correct
cub task blocked --agent
```

Look for:

- **Ready count** -- You should see 20+ tasks in the ready state.
- **Blocked tasks** -- If tasks are unexpectedly blocked, check their `dependsOn` fields.
- **Epic distribution** -- Tasks should be spread across your target epics.

!!! warning "Fix dependency issues before launching"
    If `cub task blocked` shows tasks that should be ready, resolve the dependency chain first. An overnight run that stalls on the third task because of a bad dependency wastes the entire night.

---

## Step 2: Set Budget

Budget acts as a financial safety net. If the run exceeds the limit, it stops cleanly rather than burning through your API credits.

### Option A: CLI Flag (Recommended for One-Off Runs)

```bash
cub run --budget 50
```

This sets a $50 USD ceiling for the entire session.

### Option B: Configuration File (Persistent Default)

Edit `.cub/config.json`:

```json
{
  "budget": {
    "max_total_cost": 50.00,
    "max_tokens_per_task": 500000
  }
}
```

| Setting | Purpose |
|---------|---------|
| `max_total_cost` | Hard dollar ceiling across all tasks in the session |
| `max_tokens_per_task` | Per-task token ceiling to prevent runaway single tasks |

!!! tip "Budget estimation"
    A rough rule of thumb: simple tasks cost $0.50-1.00 with Haiku, $1-3 with Sonnet, and $3-10 with Opus. For 20 tasks of mixed complexity, $30-50 is a reasonable starting budget. Check `cub ledger stats` from previous runs to calibrate.

---

## Step 3: Configure Model Routing

Not every task needs the most powerful model. Label tasks with model hints so Cub routes them efficiently:

```bash
# Simple tasks: rename variables, update docs, fix typos
cub task label myproj-001 model:haiku
cub task label myproj-002 model:haiku

# Medium tasks: add a new endpoint, write tests, refactor a module
cub task label myproj-003 model:sonnet
cub task label myproj-004 model:sonnet

# Complex tasks: design a new subsystem, fix a subtle race condition
cub task label myproj-005 model:opus
```

**Guidelines for model selection:**

| Complexity | Model | Typical Tasks |
|-----------|-------|---------------|
| Low | `model:haiku` | Typo fixes, config changes, simple tests, doc updates |
| Medium | `model:sonnet` | New endpoints, refactors, feature additions with tests |
| High | `model:opus` | Architecture changes, subtle bugs, cross-cutting concerns |

!!! note "Default model"
    Tasks without a `model:` label use whatever model is configured in `.cub/config.json` or passed via `--model`. If you don't label anything, all tasks use the same model.

---

## Step 4: Launch

Use `tmux` or `screen` to keep the process running after you close your terminal.

### Using tmux (Recommended)

```bash
# Create a named tmux session
tmux new-session -d -s cub-overnight

# Launch cub inside it
tmux send-keys -t cub-overnight 'cub run --budget 50 --stream' Enter
```

To check on it later:

```bash
# Attach to the session
tmux attach -t cub-overnight

# Detach without stopping: press Ctrl+B, then D
```

### Using nohup (Simpler)

```bash
nohup cub run --budget 50 > cub-overnight.log 2>&1 &
echo $!  # Save the PID
```

### With Live Dashboard

If you want to peek at progress before going to bed:

```bash
# In tmux, launch with the monitor split
tmux new-session -d -s cub-overnight
tmux send-keys -t cub-overnight 'cub run --budget 50 --monitor' Enter
```

The `--monitor` flag opens a live dashboard in a tmux split pane showing task progress, token usage, and current activity.

!!! tip "Stream vs. quiet"
    Use `--stream` to see harness output in real-time (useful for debugging). Omit it for a quieter run that only logs task-level summaries.

---

## Step 5: Morning Review

When you wake up, check what happened.

### Quick Summary

```bash
# Overall project status
cub status

# Ledger statistics for the session
cub ledger stats

# Recent completions
cub ledger show --limit 20
```

### Detailed Review

```bash
# Check the git log for all commits made overnight
git log --oneline --since="yesterday"

# See what changed
git diff HEAD~20 --stat

# Review a specific task's work
cub review <task-id>
```

### Smart Suggestions

```bash
# Get recommendations for what to do next
cub suggest
```

Cub will analyze the state of your backlog and suggest the best next action based on what completed, what failed, and what is now unblocked.

---

## Step 6: Handle Failures

Not every task will succeed. Here is how to triage failures.

### Find Failed Tasks

```bash
# List tasks that are still open (should have been closed)
cub task list --status open --agent

# Review a specific failure
cub review <task-id>
```

### Common Failure Patterns

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Task ran but tests failed | Generated code has bugs | Fix manually or re-run with `--task <id>` |
| Task hit token limit | Task too large for one iteration | Split into smaller subtasks |
| Task stalled (no progress) | Unclear requirements or missing context | Add detail to task description, retry |
| Budget exhausted mid-run | Budget set too low | Increase budget, re-run remaining tasks |

### Retry Failed Tasks

```bash
# Re-run a specific failed task
cub run --task <task-id> --once --stream

# Re-run all remaining open tasks
cub run --budget 20 --stream
```

---

## Tips

!!! tip "Keep going past failures"
    By default, Cub stops when a task fails. For overnight runs, configure it to continue:

    ```json
    {
      "loop": {
        "on_task_failure": "move-on"
      }
    }
    ```

    This way one broken task does not block the other 19.

!!! tip "Set iteration limits as a backstop"
    Prevent infinite loops by setting a max iteration count:

    ```json
    {
      "loop": {
        "max_iterations": 100
      }
    }
    ```

!!! tip "Use circuit breaker for stagnation"
    Cub has built-in stagnation detection. If a task is not making progress (no new commits, no test improvements), the circuit breaker kicks in and moves to the next task.

!!! tip "Review with `cub learn extract` after a big run"
    After an overnight batch, extract patterns from the session:

    ```bash
    cub learn extract --since 1
    ```

    This analyzes what worked, what failed, and gives you insights to improve future runs.

---

## Next Steps

- [Budget & Guardrails](../guide/budget/index.md) -- Fine-tune token and cost limits
- [Parallel Epics](parallel-epics.md) -- Run multiple epics simultaneously for even faster throughput
- [Direct Session Tracking](direct-session-tracking.md) -- Fix failures interactively with full tracking
