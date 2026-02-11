---
title: cub workflow
description: Manage post-completion workflow stages for tasks.
---

# cub workflow

Track tasks through post-completion workflow stages like review, QA, and deployment.

---

## Synopsis

```bash
cub workflow [COMMAND]
```

---

## Description

The `workflow` command extends task lifecycle beyond the `open → in_progress → closed` states. After a task is closed by the AI agent, it may still need human review, QA testing, or deployment. Workflow stages track this post-completion process.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Subcommands

### set

Set the workflow stage for a completed task.

```bash
cub workflow set <task-id> <stage>
```

### show

Show the current workflow status for a task.

```bash
cub workflow show <task-id>
```

### list

List tasks grouped by workflow stage.

```bash
cub workflow list
```

---

## Examples

```bash
# Mark a task as needing review
cub workflow set cub-042 review

# Check a task's workflow status
cub workflow show cub-042

# See all tasks by stage
cub workflow list
```

---

## Related Commands

- [`cub task`](../task.md) - Task management
- [`cub review`](../review.md) - Review task implementations
