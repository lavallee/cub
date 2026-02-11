---
title: cub task
description: Unified task management interface for creating, querying, and updating tasks.
---

# cub task

Manage tasks through a backend-agnostic interface that works with any configured task backend.

---

## Synopsis

```bash
cub task <subcommand> [OPTIONS]
```

---

## Description

The `cub task` command provides a unified interface for all task management operations. It abstracts over the underlying task backend (JSONL, Beads, etc.) so that commands work consistently regardless of storage format.

Use `cub task` to discover available work, claim tasks for a session, track progress, and close completed tasks. When working inside a direct harness session (Claude Code, Codex, etc.), these commands are the primary way to interact with the task system.

All subcommands support `--agent` for LLM-friendly markdown output and `--json` for machine-readable output.

---

## Subcommands

### cub task create

Create a new task in the task backend.

```bash
cub task create <title> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `TITLE` | Task title (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Task type: `task`, `feature`, `bug`, `epic`, `gate` (default: `task`) |
| `--priority` | `-p` | Priority level 0-4, where 0 is highest (default: `2`) |
| `--parent` | | Parent epic/task ID |
| `--label` | `-l` | Task label (can be repeated for multiple labels) |
| `--description` | `-d` | Task description |
| `--depends-on` | | Task IDs this task depends on (can be repeated) |
| `--json` | | Output as JSON |
| `--agent` | | Output markdown optimized for LLM consumption |

---

### cub task show

Show detailed information about a specific task.

```bash
cub task show <id> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ID` | Task ID to display (required) |

#### Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--agent` | Output in agent-friendly markdown format |

---

### cub task list

List tasks with optional filters.

```bash
cub task list [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--status` | `-s` | Filter by status: `open`, `in_progress`, `closed` |
| `--parent` | | Filter by parent epic/task ID |
| `--epic` | | Filter by parent epic/task ID (alias for `--parent`) |
| `--label` | `-l` | Filter by label |
| `--assignee` | `-a` | Filter by assignee |
| `--json` | | Output as JSON |
| `--agent` | | Output in agent-friendly markdown format |
| `--all` | | Show all tasks (disable truncation in `--agent` mode) |

---

### cub task ready

List tasks ready to work on. Ready tasks are open tasks with all dependencies satisfied.

```bash
cub task ready [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--parent` | | Filter by parent epic/task ID |
| `--epic` | | Filter by parent epic/task ID (alias for `--parent`) |
| `--label` | `-l` | Filter by label |
| `--by` | | Sort order: `priority` (default) or `impact` (transitive unblocks) |
| `--json` | | Output as JSON |
| `--agent` | | Output in agent-friendly markdown format |
| `--all` | | Show all tasks (disable truncation in `--agent` mode) |

---

### cub task claim

Claim a task for the current session by setting its status to `in_progress`.

```bash
cub task claim <id> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ID` | Task ID to claim (required) |

#### Options

| Option | Description |
|--------|-------------|
| `--agent` | Output markdown optimized for LLM consumption |

---

### cub task close

Close a completed task.

```bash
cub task close <id> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ID` | Task ID to close (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--reason` | `-r` | Reason for closing the task |
| `--agent` | | Output markdown optimized for LLM consumption |

---

### cub task update

Update fields on an existing task.

```bash
cub task update <id> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ID` | Task ID to update (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--status` | `-s` | New status: `open`, `in_progress`, `closed` |
| `--title` | | Update title |
| `--description` | `-d` | Update description |
| `--priority` | `-p` | Update priority (0-4, where 0 is highest) |
| `--assignee` | `-a` | Set assignee |
| `--add-label` | | Add a label (can be repeated) |
| `--notes` | | Update notes/comments |
| `--agent` | | Output markdown optimized for LLM consumption |

---

### cub task counts

Show aggregate task statistics.

```bash
cub task counts [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--agent` | Output markdown optimized for LLM consumption |

---

### cub task blocked

Show tasks that are blocked by unresolved dependencies.

```bash
cub task blocked [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--epic` | Filter by epic/parent ID |
| `--json` | Output as JSON |
| `--agent` | Include agent analysis (root blockers, chain lengths) |
| `--all` | Show all tasks (disable truncation in `--agent` mode) |

---

### cub task search

Search for tasks by title or description.

```bash
cub task search <query> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `QUERY` | Search query string (required) |

#### Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |
| `--agent` | Output in agent-friendly markdown format |

---

### cub task reopen

Reopen a previously closed task.

```bash
cub task reopen <id> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ID` | Task ID to reopen (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--reason` | `-r` | Reason for reopening the task |
| `--json` | | Output as JSON |

---

### cub task delete

Permanently delete a task. Shows a confirmation prompt unless `--force` is passed.

```bash
cub task delete <id> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `ID` | Task ID to delete (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip confirmation prompt |
| `--json` | | Output as JSON (only with `--force`) |

---

### cub task dep

Manage task dependencies. This is a subcommand group with the following commands:

#### cub task dep add

Add a dependency between two tasks.

```bash
cub task dep add <task-id> <depends-on>
```

The first task will depend on (be blocked by) the second task.

#### cub task dep remove

Remove a dependency from a task.

```bash
cub task dep remove <task-id> <depends-on>
```

#### cub task dep list

List dependencies for a task, showing both what it depends on and what it blocks.

```bash
cub task dep list <task-id>
```

---

### cub task label

Manage task labels. This is a subcommand group with the following commands:

#### cub task label add

```bash
cub task label add <task-id> <label>
```

#### cub task label remove

```bash
cub task label remove <task-id> <label>
```

#### cub task label list

```bash
cub task label list <task-id>
```

---

## Examples

### Discovery

```bash
# List all ready tasks sorted by priority
cub task ready

# List ready tasks sorted by impact (most unblocks first)
cub task ready --by impact

# List all open tasks
cub task list --status open

# List tasks in a specific epic
cub task list --epic cub-048a

# Search for tasks by keyword
cub task search "authentication"

# Show task statistics
cub task counts
```

### Working with Tasks

```bash
# Create a new task
cub task create "Fix login validation" --type bug --priority 1

# Create a task under an epic with dependencies
cub task create "Add user profile" --type feature --parent cub-048a \
    --depends-on cub-048a-3 --label "frontend"

# Claim a task for the current session
cub task claim cub-048a-5

# Close a task with a reason
cub task close cub-048a-5 --reason "Implemented and tested"

# Update task fields
cub task update cub-048a-5 --priority 0 --add-label "urgent"
```

### Agent-Friendly Output

```bash
# Get ready tasks in markdown format for LLM consumption
cub task ready --agent

# Show all tasks without truncation
cub task list --agent --all

# View blocked tasks with dependency analysis
cub task blocked --agent
```

### JSON Output for Scripting

```bash
# Get ready tasks as JSON
cub task ready --json | jq '.[0].id'

# Count open tasks
cub task list --status open --json | jq 'length'

# Get task statistics as JSON
cub task counts --json
```

### Dependency Management

```bash
# Add a dependency: task-5 depends on task-3
cub task dep add cub-048a-5 cub-048a-3

# Remove a dependency
cub task dep remove cub-048a-5 cub-048a-3

# View all dependencies for a task
cub task dep list cub-048a-5
```

---

## Task States

Tasks progress through these states:

| State | Description |
|-------|-------------|
| `open` | Not started, waiting to be picked up |
| `in_progress` | Currently being worked on (claimed) |
| `closed` | Completed |

### Ready vs Blocked

- **Ready tasks**: Open tasks with all `depends_on` tasks closed and no blocking checkpoints
- **Blocked tasks**: Open tasks with at least one unresolved dependency

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Command completed successfully |
| `1` | Error (task not found, backend error, validation failure) |

---

## Related Commands

- [`cub status`](status.md) - View overall task progress and statistics
- [`cub run`](run.md) - Execute tasks autonomously with an AI harness
- [`cub explain-task`](explain-task.md) - Show detailed task information (delegated)
- [`cub close-task`](close-task.md) - Close a task (delegated, for agent use)
- [`cub session`](session.md) - Track work in direct harness sessions

---

## See Also

- [Task Management Guide](../guide/tasks/index.md) - Understanding the task lifecycle
- [Dependencies](../guide/tasks/dependencies.md) - How task dependencies work
- [Run Loop Guide](../guide/run-loop/index.md) - How tasks are selected and executed
- [Configuration Reference](../guide/configuration/reference.md) - Task backend configuration
