---
title: cub sync
description: Sync task state to git branch for persistence and collaboration.
---

# cub sync

Sync task state and configuration to a dedicated git branch, enabling persistence across sessions and collaboration across machines.

---

## Synopsis

```bash
cub sync [OPTIONS] [COMMAND]
```

---

## Description

The `sync` command manages synchronization of cub task state with git. It stores task metadata on a dedicated sync branch so that state persists across sessions and can be shared with collaborators.

When run without a subcommand, `cub sync` performs a bidirectional sync: pulling remote changes, merging, and optionally pushing local changes.

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--pull` | | Pull and merge remote changes before syncing |
| `--push` | | Push local changes to remote after syncing |
| `--message TEXT` | `-m` | Custom commit message |
| `--help` | `-h` | Show help message and exit |

---

## Subcommands

### status

Show the current sync status, including whether local state is ahead of or behind the remote.

```bash
cub sync status
```

### init

Initialize the sync branch. Creates the dedicated branch for task state storage.

```bash
cub sync init
```

### agent

Sync managed sections in `agent.md` across worktrees and branches.

```bash
cub sync agent
```

---

## Examples

### Basic Sync

```bash
# Pull remote changes and sync
cub sync --pull

# Sync and push to remote
cub sync --push

# Full bidirectional sync
cub sync --pull --push
```

### Check Status

```bash
# See if local state is out of sync
cub sync status
```

### Initialize

```bash
# Set up sync branch for a new project
cub sync init
```

### Custom Commit Message

```bash
cub sync --push -m "checkpoint: auth epic complete"
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Sync completed successfully |
| `1` | Sync error (merge conflict, network issue, etc.) |

---

## Related Commands

- [`cub init`](init.md) - Initialize cub in a project
- [`cub status`](status.md) - View task progress
- [`cub branch`](branch.md) - Manage branch-epic bindings

---

## See Also

- [Git Integration Guide](../guide/git/index.md) - Git workflow overview
- [Configuration Reference](../guide/configuration/reference.md) - Sync settings
