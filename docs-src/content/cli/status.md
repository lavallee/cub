---
title: cub status
description: Show current session status, task progress, and budget usage.
---

# cub status

Display current session status including task progress, ready tasks, and blocked tasks.

---

## Synopsis

```bash
cub status [OPTIONS]
```

---

## Description

The `status` command provides a summary of your project's task state:

- Total, open, in-progress, and closed task counts
- Completion percentage
- Number of ready (actionable) tasks
- Number of blocked tasks (waiting on dependencies)

Use this to understand the current state before running `cub run` or to check progress during a session.

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--verbose` | `-v` | Show detailed status including top ready tasks |
| `--json` | | Output status as JSON for scripting |
| `--session ID` | `-s` | Show status for specific session ID |

---

## Output

### Default Output

```
Task Progress Summary
┏━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Label          ┃ Count ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Total Tasks    │    12 │
│ Closed         │     4 │
│ In Progress    │     1 │
│ Open           │     7 │
│ Completion     │ 33.3% │
└────────────────┴───────┘

Task Availability
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Status                  ┃ Count ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Ready to work           │     3 │
│ Blocked by dependencies │     4 │
└─────────────────────────┴───────┘
```

### Verbose Output

With `--verbose`, shows top ready tasks:

```
Top Ready Tasks:
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ ID          ┃ Title                               ┃ Priority ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ cub-001     │ Add user authentication             │ high     │
│ cub-003     │ Create login form component         │ medium   │
│ cub-007     │ Add logout button                   │ medium   │
└─────────────┴─────────────────────────────────────┴──────────┘
```

### JSON Output

With `--json`, outputs machine-readable JSON:

```json
{
  "task_counts": {
    "total": 12,
    "open": 7,
    "in_progress": 1,
    "closed": 4,
    "completion_percentage": 33.3
  },
  "ready_tasks": 3,
  "blocked_tasks": 4
}
```

---

## Examples

### Basic Status

```bash
# Quick overview
cub status

# Detailed with ready tasks
cub status --verbose
```

### JSON for Scripts

```bash
# Get completion percentage
cub status --json | jq '.task_counts.completion_percentage'

# Count ready tasks
cub status --json | jq '.ready_tasks'

# Check if all done
cub status --json | jq '.task_counts.open == 0'
```

### Scripting Example

```bash
#!/bin/bash
# Run until all tasks complete

while true; do
    open_count=$(cub status --json | jq '.task_counts.open')

    if [ "$open_count" = "0" ]; then
        echo "All tasks complete!"
        exit 0
    fi

    echo "Running... $open_count tasks remaining"
    cub run --once
done
```

---

## Task States

Tasks progress through these states:

| State | Description |
|-------|-------------|
| `open` | Not started, waiting to be picked up |
| `in_progress` | Currently being worked on |
| `closed` | Completed |

### Ready vs Blocked

- **Ready tasks**: Open tasks with all dependencies satisfied
- **Blocked tasks**: Open tasks waiting on incomplete dependencies

---

## Understanding the Output

### Completion Percentage

```
Completion = (closed / total) * 100
```

This shows overall progress, not accounting for task complexity.

### Ready Tasks

Tasks are ready when:

1. Status is `open`
2. All `depends_on` tasks are `closed`
3. No blocking checkpoints are pending

### Blocked Tasks

Tasks are blocked when:

1. Status is `open`
2. At least one dependency is not `closed`

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Status displayed successfully |
| `1` | Error (no task backend, read error) |

---

## Related Commands

- [`cub run`](run.md) - Execute tasks
- [`cub run --ready`](run.md) - List ready tasks in detail
- [`cub monitor`](monitor.md) - Live dashboard
- [`cub artifacts`](artifacts.md) - View task outputs

---

## See Also

- [Task Management Guide](../guide/tasks/index.md) - Understanding task lifecycle
- [Dependencies](../guide/tasks/dependencies.md) - How dependencies work
