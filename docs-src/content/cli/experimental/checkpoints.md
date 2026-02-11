---
title: cub checkpoints
description: Manage review and approval gates that block task execution.
---

# cub checkpoints

Manage checkpoints — review and approval gates that block downstream tasks until a human approves them.

---

## Synopsis

```bash
cub checkpoints [OPTIONS]
```

---

## Description

Checkpoints are tasks of type `gate` that act as human approval points in the task dependency graph. When `cub run` encounters a task blocked by an unapproved checkpoint, it skips that task and moves on.

This command is delegated to the bash implementation.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Examples

```bash
# List all checkpoints
cub checkpoints

# Show checkpoints for a specific epic
cub checkpoints --epic cub-123

# Show only blocking checkpoints
cub checkpoints --blocking

# Approve a checkpoint (unblocks dependent tasks)
cub checkpoints approve <checkpoint-id>
```

---

## Related Commands

- [`cub run`](../run.md) - Respects checkpoint gates during execution
- [`cub task`](../task.md) - Create gate tasks
- [`cub branch`](../branch.md) - Branch management for epics
