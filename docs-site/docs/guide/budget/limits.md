# Iteration Limits

Iteration limits prevent runaway loops and ensure Cub stops gracefully even when tasks fail repeatedly or the AI gets stuck. These guardrails are essential for autonomous operation.

## Types of Iteration Limits

Cub tracks iterations at two levels:

| Limit Type | Scope | Default | Purpose |
|------------|-------|---------|---------|
| **max_task_iterations** | Per task | 3 | Prevents infinite retry loops on a single task |
| **max_run_iterations** | Per run | 50 | Caps total iterations across all tasks |
| **iteration_warning_threshold** | Both | 0.8 (80%) | Alerts before hitting limits |

## Max Task Iterations

This limit controls how many times Cub will attempt a single task before moving on or stopping.

### How It Works

```
Task: cub-054
  Attempt 1: Failed (tests not passing)
  Attempt 2: Failed (type errors)
  Attempt 3: Failed (still failing)
  -> Task marked as stuck, run stops or continues based on config
```

### Configuration

```json
{
  "guardrails": {
    "max_task_iterations": 3
  }
}
```

Common settings:

| Value | Use Case |
|-------|----------|
| 1 | Strict: fail fast on any error |
| 3 | Default: allow reasonable retries |
| 5 | Permissive: for complex tasks that may need multiple attempts |
| 10 | Very permissive: for experimental/exploratory work |

### Behavior When Limit Reached

When a task hits its iteration limit, behavior depends on `loop.on_task_failure`:

```json
{
  "loop": {
    "on_task_failure": "stop"
  }
}
```

| Setting | Behavior |
|---------|----------|
| `"stop"` | Run terminates after exhausting task iterations |
| `"continue"` | Move to next task, leave failed task for later |

## Max Run Iterations

This limit caps the total number of loop cycles across an entire run, regardless of which tasks are being worked on.

### How It Works

```
Run: cub-20260117-103000
  Iteration 1: Task cub-054 completed
  Iteration 2: Task cub-055 completed
  Iteration 3: Task cub-056 in progress...
  ...
  Iteration 50: Max iterations reached, stopping
```

### Configuration

```json
{
  "guardrails": {
    "max_run_iterations": 50
  }
}
```

Or in the loop section:

```json
{
  "loop": {
    "max_iterations": 100
  }
}
```

!!! note "Two Configuration Locations"
    `guardrails.max_run_iterations` and `loop.max_iterations` control the same behavior. The guardrails setting takes precedence if both are set.

### Common Settings

| Value | Use Case |
|-------|----------|
| 1 | `cub run --once` equivalent |
| 10 | Quick session, a few tasks |
| 50 | Default: reasonable work session |
| 100 | Extended autonomous session |
| 200+ | Long-running overnight work |

### CLI Override

```bash
# Single iteration
cub run --once

# Custom limit not directly exposed, use --once or config
```

## Warning Threshold

The warning threshold alerts you as iterations approach their limit.

### How It Works

```
Iteration 40 of 50 (80%)
[yellow]Warning: Approaching iteration limit[/yellow]
```

### Configuration

```json
{
  "guardrails": {
    "iteration_warning_threshold": 0.8
  }
}
```

| Value | When Warning Triggers |
|-------|----------------------|
| 0.5 | At 50% of limit |
| 0.8 | At 80% of limit (default) |
| 0.9 | At 90% of limit |
| 1.0 | No warning (hit limit directly) |

### What Happens at Warning

1. Warning logged to JSONL:
   ```json
   {"event_type": "budget_warning", "data": {"remaining": 10, "threshold": 40, "total": 50}}
   ```

2. Console output (if visible):
   ```
   [yellow]Warning: 80% of run iterations used (40/50)[/yellow]
   ```

3. Status file updated:
   ```json
   {"iteration": {"current": 40, "max": 50, "is_near_limit": true}}
   ```

## What Happens When Limits Are Hit

### Task Iteration Limit

```
Task cub-054 failed after 3 attempts
+-- on_task_failure: stop --+
|                           |
|  Run terminates           |
|  Exit code: 1             |
|  Phase: failed            |
+---------------------------+

+-- on_task_failure: continue --+
|                               |
|  Task left in progress        |
|  Move to next ready task      |
|  Run continues                |
+-------------------------------+
```

### Run Iteration Limit

```
Reached max iterations (50)

Run Summary
+------------------+------------+
| Duration         | 1234.5s    |
| Iterations       | 50         |
| Tasks Completed  | 12         |
| Final Phase      | stopped    |
+------------------+------------+
```

The run is marked as `stopped` (not `failed`) since hitting max iterations is expected behavior.

## Monitoring Iteration Status

### Live Dashboard

```bash
cub run --monitor
```

Shows iteration progress in real-time:

```
Iteration: 12/50 (24%)
Task Iteration: 1/3
```

### Status Command

```bash
cub status
```

### Status File

Check `.cub/runs/{session}/status.json`:

```json
{
  "iteration": {
    "current": 12,
    "max": 50,
    "task_iteration": 1,
    "max_task_iteration": 3,
    "percentage": 24.0,
    "task_percentage": 33.3,
    "is_near_limit": false
  }
}
```

## Best Practices

### For Development

Use conservative limits to catch issues early:

```json
{
  "guardrails": {
    "max_task_iterations": 2,
    "max_run_iterations": 10
  },
  "loop": {
    "on_task_failure": "stop"
  }
}
```

### For Production

Allow more attempts but maintain guardrails:

```json
{
  "guardrails": {
    "max_task_iterations": 5,
    "max_run_iterations": 100,
    "iteration_warning_threshold": 0.7
  },
  "loop": {
    "on_task_failure": "continue"
  }
}
```

### For Overnight Runs

Extended limits with monitoring:

```json
{
  "guardrails": {
    "max_task_iterations": 3,
    "max_run_iterations": 200,
    "iteration_warning_threshold": 0.8
  },
  "budget": {
    "max_total_cost": 50.0
  }
}
```

## Troubleshooting

### Task Keeps Failing

If a task repeatedly hits its iteration limit:

1. Check the task description for ambiguity
2. Review logs for consistent failure patterns
3. Consider breaking the task into smaller subtasks
4. Temporarily increase `max_task_iterations` for debugging

### Run Ends Too Quickly

If runs always hit `max_run_iterations`:

1. Tasks may be getting stuck without failing
2. Check for circular dependencies
3. Review the task queue for blocked tasks
4. Increase the limit if needed

### No Warnings Before Limit

If you're hitting limits without warning:

1. Check `iteration_warning_threshold` is set
2. Ensure console output is visible
3. Review JSONL logs for `budget_warning` events
