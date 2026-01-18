# cub close-task

Close a completed task from the command line.

## Synopsis

```bash
cub close-task <task-id> [OPTIONS]
```

## Description

The `cub close-task` command marks a task as completed. This command is primarily designed for **agent use** during autonomous execution, allowing the AI harness to signal task completion programmatically.

When a task is closed:

1. The task status changes to `closed`
2. A completion reason/summary is recorded
3. The task becomes available for verification
4. Dependent tasks may become unblocked

## Options

| Option | Description |
|--------|-------------|
| `<task-id>` | The task identifier to close (required) |
| `-r, --reason <text>` | Reason or summary for closing |
| `--commit <sha>` | Associate closing commit |

## Examples

### Basic Task Closure

```bash
# Close a task with a reason
cub close-task cub-123 -r "Implemented authentication with tests passing"
```

### With Commit Reference

```bash
# Close and link to the implementing commit
cub close-task cub-123 -r "Feature complete" --commit abc1234
```

### Agent Usage Pattern

The AI harness typically calls this after completing work:

```bash
# In agent prompt/workflow:
# 1. Complete the implementation
# 2. Run tests
# 3. Close the task
cub close-task cub-456 -r "Added user profile API endpoint with 95% test coverage"
```

## How It Works

### Task Backend Integration

The command delegates to the configured task backend:

- **Beads backend**: Calls `bd close <task-id> -r "reason"`
- **JSON backend**: Updates the task status in `prd.json`

### Verification Flow

After closing, tasks should be verified:

```bash
# Agent closes task
cub close-task cub-123 -r "Implementation complete"

# Later, verify the task is properly closed
cub verify-task cub-123
```

### Unblocking Dependents

When a task is closed, any tasks that depended on it may become ready for execution:

```
Before:
  cub-123 (open) ─blocks─> cub-124 (blocked)
                 ─blocks─> cub-125 (blocked)

After cub close-task cub-123:
  cub-123 (closed)
  cub-124 (open) ← now available
  cub-125 (open) ← now available
```

## Agent Instructions

When using `cub close-task` in autonomous mode, follow these guidelines:

1. **Only close when truly complete** - All acceptance criteria met
2. **Include meaningful reasons** - Summarize what was accomplished
3. **Verify before closing** - Run tests, check linting, confirm functionality
4. **Link commits when possible** - Helps track what code implements the task

### Example Agent Workflow

```markdown
# In agent.md or prompt.md:

When you complete a task:
1. Run all tests: `pytest tests/`
2. Check types: `mypy src/`
3. Verify functionality manually if needed
4. Close with summary: `cub close-task <id> -r "summary"`
5. Verify closure: `cub verify-task <id>`
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Task closed successfully |
| 1 | Task not found or already closed |
| 2 | Invalid arguments |

## Related Commands

- [`cub status`](status.md) - Check task status
- [`cub explain-task`](explain-task.md) - View task details
- [`cub run`](../guide/run-loop/index.md) - Execute tasks
- [`cub status`](../guide/run-loop/index.md) - View task status
