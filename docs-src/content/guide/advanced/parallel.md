# Parallel Execution

Parallel execution allows Cub to run multiple independent tasks simultaneously, each in its own git worktree. This can significantly speed up processing when you have tasks that don't depend on each other.

## How Parallel Execution Works

When you run `cub run --parallel N`, Cub:

1. **Finds independent tasks** - Identifies tasks with no mutual dependencies
2. **Creates worktrees** - Sets up N git worktrees (isolated working copies)
3. **Assigns tasks** - One task per worktree
4. **Executes in parallel** - Runs all tasks simultaneously
5. **Collects results** - Aggregates outcomes from all workers
6. **Cleans up** - Removes worktrees after completion

```
Main Repository
      |
      +-- .cub/worktrees/
             |
             +-- cub-054/  (Task 1)
             |      |
             |      +-- [full copy of repo]
             |      +-- cub run --task cub-054
             |
             +-- cub-055/  (Task 2)
             |      |
             |      +-- [full copy of repo]
             |      +-- cub run --task cub-055
             |
             +-- cub-056/  (Task 3)
                    |
                    +-- [full copy of repo]
                    +-- cub run --task cub-056
```

## Using Parallel Execution

### Basic Usage

```bash
# Run 3 tasks in parallel
cub run --parallel 3
```

### With Filters

```bash
# Parallel tasks from a specific epic
cub run --parallel 3 --epic backend-v2

# Parallel tasks with a label
cub run --parallel 3 --label priority
```

### With Harness Selection

```bash
# Use specific harness for all workers
cub run --parallel 3 --harness claude
```

## Task Selection

### Independent Tasks

Cub automatically selects tasks that can run in parallel. A task is independent if:

- It is ready (OPEN status, dependencies satisfied)
- It does not depend on any other selected task
- No other selected task depends on it

```
Task Graph:
  cub-054 (ready)     --> Selected
  cub-055 (ready)     --> Selected
  cub-056 -> cub-054  --> NOT selected (depends on cub-054)
  cub-057 (ready)     --> Selected (if 3 requested)
```

### Dependency Checking

If you have tasks A and B where:

- A depends on B
- B depends on A (circular)
- A blocks B

Only one will be selected for parallel execution.

### Not Enough Tasks

If fewer independent tasks exist than requested:

```bash
cub run --parallel 5
# Output: Found only 3 independent tasks (requested 5)
```

Cub proceeds with the available tasks.

## Session Assignment

Each parallel worker runs as an independent subprocess:

```bash
# Worker 1
cub run --task cub-054 --once

# Worker 2
cub run --task cub-055 --once

# Worker 3
cub run --task cub-056 --once
```

### Worker Isolation

Workers are fully isolated:

| Aspect | Isolation |
|--------|-----------|
| Filesystem | Separate worktree |
| Git state | Independent branches possible |
| Process | Separate subprocess |
| Output | Collected separately |

### No Cross-Worker Conflicts

Because each worker has its own worktree:

- No file conflicts
- No git lock contention
- No race conditions on shared state

## Worktree Management

### Automatic Cleanup

By default, worktrees are removed after the parallel run:

```bash
cub run --parallel 3
# Worktrees created in .cub/worktrees/
# Worktrees removed after completion
```

### Worktree Location

Worktrees are created at:

```
{project}/.cub/worktrees/{task-id}/
```

### Manual Worktree Use

You can also use worktrees without parallelism:

```bash
# Run single task in a worktree
cub run --worktree --task cub-054

# Keep worktree after completion
cub run --worktree --worktree-keep --task cub-054
```

## Results and Reporting

### Summary Output

After parallel execution:

```
Parallel Run Summary
+------------------+------------+
| Metric           | Value      |
+------------------+------------+
| Duration         | 234.5s     |
| Tasks Completed  | 3          |
| Tasks Failed     | 0          |
| Total Tokens     | 456,789    |
| Total Cost       | $2.34      |
+------------------+------------+

Task Results
+----------+--------+----------+---------+
| Task     | Status | Duration | Tokens  |
+----------+--------+----------+---------+
| cub-054  | ok     | 78.2s    | 152,345 |
| cub-055  | ok     | 92.1s    | 168,901 |
| cub-056  | ok     | 85.4s    | 135,543 |
+----------+--------+----------+---------+
```

### Exit Codes

| Condition | Exit Code |
|-----------|-----------|
| All tasks succeeded | 0 |
| Any task failed | 1 |

### Per-Worker Status

Each worker writes its own status file:

```
.cub/runs/{session}/status.json
.cub/worktrees/cub-054/.cub/status/status.json
.cub/worktrees/cub-055/.cub/status/status.json
```

## Avoiding Conflicts

### Database Migrations

If tasks might run migrations:

- Run migration tasks sequentially first
- Use parallel for non-migration tasks

### Shared Resources

For tasks that access shared resources:

- Files: Worktrees isolate
- Databases: Consider separate test DBs
- APIs: Rate limiting may apply

### Branch Conflicts

Each worktree works on the same base branch. If tasks both modify the same file:

- Changes stay in separate worktrees
- Manual merge needed after
- Consider sequential execution for overlapping tasks

## Performance Optimization

### Optimal Parallelism

| Tasks | Recommended `--parallel` |
|-------|-------------------------|
| 2-3 | 2 |
| 4-6 | 3-4 |
| 7+ | 4-5 |

Higher parallelism:

- Uses more disk space (worktrees)
- May hit API rate limits
- Diminishing returns above 5-6

### Disk Space

Each worktree is a full copy of your repository (excluding `.git`):

```
Space = Project Size x Number of Workers
```

For a 500MB project with 5 workers: ~2.5GB additional space.

### API Rate Limits

Parallel workers all call the AI API simultaneously. Consider:

- Your API tier's rate limits
- Using fewer workers if rate limited
- Different models for different tasks

## Combining with Other Features

### Parallel + Sandbox

```bash
# Run parallel tasks, each in sandbox
cub run --parallel 3 --sandbox
```

Each worker gets its own container.

### Parallel + Budget

```bash
# Budget applies across all workers
cub run --parallel 3 --budget 10.0
```

Total spending across all workers counts toward the budget.

## Troubleshooting

### Worktree Creation Failed

```
Failed to create worktree: ...
```

**Possible causes**:

- Disk space exhausted
- Git repository issues
- Path conflicts

**Solution**: Clean up old worktrees, check disk space.

### Tasks Not Running in Parallel

If tasks run sequentially:

- Check for dependencies between tasks
- Verify tasks are in OPEN status
- Review task graph for hidden dependencies

### One Worker Failed

If a worker fails:

- Other workers continue
- Failed task reported in summary
- Exit code is 1

### Cleanup Failed

If worktrees aren't cleaned up:

```bash
# Manual cleanup
rm -rf .cub/worktrees/

# Or use git
git worktree prune
```

## Best Practices

### Task Design

Design tasks for parallel execution:

- Avoid shared state dependencies
- Make tasks self-contained
- Use explicit dependencies

### Start Small

```bash
# Test with 2 workers first
cub run --parallel 2

# Scale up if successful
cub run --parallel 4
```

### Monitor Resources

Watch system resources during parallel runs:

- CPU usage
- Memory usage
- Disk I/O
- API rate limit responses

### Use Labels

Label tasks suitable for parallel execution:

```bash
bd label cub-054 parallel-ok
bd label cub-055 parallel-ok

cub run --parallel 3 --label parallel-ok
```
