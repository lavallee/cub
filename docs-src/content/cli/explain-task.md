# cub explain-task

Display detailed information about a specific task.

## Synopsis

```bash
cub explain-task <task-id>
```

## Description

The `cub explain-task` command shows comprehensive details about a task, including its description, status, dependencies, related artifacts, and execution history. This is useful for understanding what a task entails before working on it or debugging issues with task execution.

## Options

| Option | Description |
|--------|-------------|
| `<task-id>` | The task identifier to explain (required) |

## Information Displayed

The command outputs detailed task information including:

| Section | Content |
|---------|---------|
| **Basic Info** | ID, title, type, status, priority |
| **Description** | Full task description and requirements |
| **Dependencies** | Tasks that must complete first |
| **Dependents** | Tasks waiting on this one |
| **Labels** | Tags and categories |
| **Epic** | Parent epic if assigned |
| **Artifacts** | Related files and outputs |
| **History** | Status changes and execution attempts |
| **Spec** | Interview-generated specifications (if any) |

## Examples

### View Task Details

```bash
cub explain-task cub-123
```

Output:
```
Task: cub-123
Title: Implement user authentication
Type: feature
Status: open
Priority: high
Epic: cub-auth-epic

Description:
  Add email/password authentication with session management.
  Support OAuth2 for social login providers.

Dependencies:
  - cub-120: Database schema setup (completed)
  - cub-121: API framework configuration (completed)

Dependents:
  - cub-125: User profile page
  - cub-126: Password reset flow

Labels:
  - auth
  - security
  - user-facing

Artifacts:
  - specs/cub-123-auth-spec.md
  - .cub/artifacts/cub-123/

History:
  2026-01-10 09:15: Created
  2026-01-11 14:30: Started (session: narwhal)
  2026-01-11 15:45: Blocked (waiting for cub-121)
  2026-01-12 10:00: Resumed
```

### Quick Reference During Development

```bash
# Check task requirements while implementing
cub explain-task cub-456
```

### Verify Dependencies

```bash
# See what's blocking a task
cub explain-task cub-789 | grep -A5 Dependencies
```

## Use Cases

### Before Starting Work

Review task details before beginning implementation:

```bash
cub explain-task cub-123
# Read description, check dependencies are met
cub run --task cub-123
```

### Debugging Failed Tasks

Understand why a task might have failed:

```bash
cub explain-task cub-456
# Check history for error patterns
# Review dependencies that might have regressed
```

### Understanding Task Context

When picking up work from another session:

```bash
# What was this task about?
cub explain-task cub-789

# What has been done?
cub artifacts cub-789
```

## Related Commands

- [`cub interview`](interview.md) - Deep-dive questioning for tasks
- [`cub close-task`](close-task.md) - Close a completed task
- [`cub artifacts`](../guide/run-loop/completion.md) - List task artifacts
- [`cub status`](../guide/run-loop/index.md) - Overview of all tasks
