---
title: cub artifacts
description: Access and navigate to task artifact directories and output files.
---

# cub artifacts

Access and navigate to task artifact directories and output files from completed runs.

---

## Synopsis

```bash
cub artifacts [TASK_ID]
```

---

## Description

The `artifacts` command provides access to the output files generated during task execution:

- **Without arguments**: Lists all recent tasks with their artifact paths
- **With task ID**: Returns the path to a specific task's artifacts

Artifacts include execution logs, summaries, git diffs, and task metadata.

---

## Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID or prefix to find (optional) |

---

## Artifact Contents

Each task creates an artifact directory containing:

| File | Description |
|------|-------------|
| `task.json` | Task metadata and final status |
| `summary.md` | Execution summary |
| `changes.patch` | Git diff of changes made |
| `run.json` | Run-level information |
| `logs/` | Detailed execution logs |

---

## Examples

### List Recent Tasks

```bash
cub artifacts
```

Output:

```
Recent tasks:
  cub-018: .cub/runs/session-20260117-143022/tasks/cub-018
  cub-017: .cub/runs/session-20260117-143022/tasks/cub-017
  cub-016: .cub/runs/session-20260117-120000/tasks/cub-016
  cub-015: .cub/runs/session-20260117-120000/tasks/cub-015
```

### Get Specific Task Path

```bash
cub artifacts cub-018
```

Output:

```
.cub/runs/session-20260117-143022/tasks/cub-018
```

### Use in Shell Commands

```bash
# Navigate to task artifacts
cd $(cub artifacts cub-018)

# View task summary
cat $(cub artifacts cub-017)/summary.md

# Examine git changes
patch -p1 -R < $(cub artifacts cub-016)/changes.patch

# List logs directory
ls $(cub artifacts cub-015)/logs/
```

### Prefix Matching

Find tasks by ID prefix:

```bash
# Exact match if unique
cub artifacts cub-01

# If ambiguous, shows matches
cub artifacts cub-01
# Output:
# Ambiguous task ID 'cub-01' matches 3 tasks:
#   cub-010: .cub/runs/.../tasks/cub-010
#   cub-011: .cub/runs/.../tasks/cub-011
#   cub-012: .cub/runs/.../tasks/cub-012
# Please use a more specific prefix
```

---

## Directory Structure

Artifacts are organized under `.cub/runs/`:

```
.cub/runs/
├── session-20260117-143022/
│   ├── status.json           # Run status
│   └── tasks/
│       ├── cub-017/
│       │   ├── task.json
│       │   ├── summary.md
│       │   ├── changes.patch
│       │   └── logs/
│       └── cub-018/
│           ├── task.json
│           ├── summary.md
│           ├── changes.patch
│           └── logs/
└── session-20260117-120000/
    ├── status.json
    └── tasks/
        ├── cub-015/
        └── cub-016/
```

---

## Common Workflows

### Review What Changed

```bash
# See the diff from a task
git diff < $(cub artifacts cub-018)/changes.patch

# Or view it directly
cat $(cub artifacts cub-018)/changes.patch
```

### Investigate a Failure

```bash
# Read the summary
cat $(cub artifacts cub-018)/summary.md

# Check the logs
ls $(cub artifacts cub-018)/logs/
cat $(cub artifacts cub-018)/logs/harness.log
```

### Scripting

```bash
#!/bin/bash
# Process all task artifacts

for dir in .cub/runs/*/tasks/*/; do
    task_id=$(basename "$dir")
    echo "Processing $task_id"

    if [ -f "$dir/summary.md" ]; then
        head -5 "$dir/summary.md"
    fi
done
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (listed tasks or returned path) |
| `1` | Error (no artifacts found, ambiguous prefix) |

---

## Related Commands

- [`cub status`](status.md) - View task progress
- [`cub monitor`](monitor.md) - Live run dashboard
- [`cub run`](run.md) - Execute tasks

---

## See Also

- [Run Loop Guide](../guide/run-loop/index.md) - Understanding run execution
- [Audit Logging](../guide/advanced/audit.md) - Detailed logging configuration
