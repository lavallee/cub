---
title: cub new
description: Create a new project directory ready for cub-based development.
---

# cub new

Create a new project directory with git and cub initialized, ready for development.

---

## Synopsis

```bash
cub new <directory>
```

---

## Description

The `new` command bootstraps a complete project directory in one step. It combines directory creation, `git init`, and `cub init` into a single command.

**Behavior by directory state:**

| State | Action |
|-------|--------|
| Directory doesn't exist | Create it, `git init`, `cub init` |
| Directory exists but empty | `git init`, `cub init` |
| Directory exists with files | Prompt for confirmation, then `cub init` only (skips `git init` if `.git/` present) |

---

## Arguments

| Argument | Description |
|----------|-------------|
| `directory` | Path to the project directory to create |

---

## Examples

### Create a New Project

```bash
cub new my-app
```

Output:

```
Initialized git repository in /home/user/my-app
...cub init output...

Project ready at /home/user/my-app
```

### Nested Directory

```bash
cub new projects/2026/my-api
```

Creates all parent directories as needed.

### Existing Directory

```bash
cub new ~/existing-project
```

If the directory has files, you'll be prompted:

```
Directory '/home/user/existing-project' already has files. Run cub init there instead? [y/N]:
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Project created successfully (or user declined on existing directory) |
| `1` | Error (`git init` failed, `cub init` failed, or bash cub not found) |

---

## Related Commands

- [`cub init`](init.md) - Initialize cub in an existing project
- [`cub doctor`](doctor.md) - Diagnose configuration issues
- [`cub run`](run.md) - Execute the task loop

---

## See Also

- [Quick Start](../getting-started/quickstart.md) - Get started in 5 minutes
- [Installation Guide](../getting-started/install.md) - Complete installation instructions
