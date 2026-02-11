---
title: cub sandbox
description: Manage Docker sandboxes for isolated task execution.
---

# cub sandbox

Manage Docker sandbox containers used for isolated task execution during `cub run --sandbox`.

---

## Synopsis

```bash
cub sandbox [COMMAND]
```

---

## Description

The `sandbox` command manages Docker containers created by `cub run --sandbox`. Sandboxes provide full filesystem and optional network isolation for task execution, preventing unintended side effects on your host system.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Subcommands

### logs

Show logs from a sandbox container.

```bash
cub sandbox logs
```

### status

Show sandbox status and resource usage.

```bash
cub sandbox status
```

### diff

Show changes made inside the sandbox compared to the host.

```bash
cub sandbox diff
```

### export

Export files from the sandbox to a local directory.

```bash
cub sandbox export [PATH]
```

### apply

Apply sandbox changes to the project (copy changed files from container to host).

```bash
cub sandbox apply
```

### clean

Remove sandbox containers and clean up resources.

```bash
cub sandbox clean
```

---

## Examples

```bash
# Check what's running
cub sandbox status

# See what changed in the sandbox
cub sandbox diff

# Apply sandbox changes to your project
cub sandbox apply

# Clean up old containers
cub sandbox clean
```

---

## Related Commands

- [`cub run`](../run.md) - Use `--sandbox` to run in a sandbox
- [`cub worktree`](../worktree.md) - Alternative isolation via git worktrees
