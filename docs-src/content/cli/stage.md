---
title: cub stage
description: Import tasks from a completed plan into the task backend.
---

# cub stage

Import tasks from a completed plan into the task backend (beads), bridging planning and execution.

---

## Synopsis

```bash
cub stage [PLAN_SLUG] [OPTIONS]
```

---

## Description

The `stage` command imports tasks from a completed plan's `itemized-plan.md` into the task backend. After staging, tasks are ready for execution with `cub run`.

Staging also:

- Runs pre-flight checks (git repository, required tools)
- Generates `plans/<slug>/prompt-context.md` with plan-specific context for runtime injection
- Moves the spec from `planned/` to `staged/`

---

## Arguments

| Argument | Description |
|----------|-------------|
| `PLAN_SLUG` | Plan slug to stage (default: most recent complete plan) |

---

## Options

| Option | Description |
|--------|-------------|
| `-n`, `--dry-run` | Preview what would be imported without actually importing |
| `-l`, `--list` | List all stageable plans |
| `-v`, `--verbose` | Show detailed output |
| `--skip-checks` | Skip pre-flight checks (git, tools) |
| `--skip-prompt` | Don't generate prompt-context.md |
| `--project-root PATH` | Project root directory |
| `-h`, `--help` | Show help message |

---

## Examples

### Stage Most Recent Plan

```bash
cub stage
```

### Stage Specific Plan

```bash
cub stage my-feature
```

### Dry Run

Preview without importing:

```bash
cub stage --dry-run
```

### List Stageable Plans

```bash
cub stage --list
```

### Skip Pre-flight Checks

```bash
cub stage --skip-checks
```

---

## Pre-Flight Checks

Before staging, the following are verified:

| Check | Requirement | Warning |
|-------|-------------|---------|
| Git repository | `.git/` exists | Not a git repo |
| Working directory | Ideally clean | Uncommitted changes detected |
| Beads CLI | `bd` command available | Beads CLI not found |

Warnings are displayed but don't block staging. Use `--skip-checks` to suppress.

---

## Generated Files

### plans/<slug>/prompt-context.md

Plan-specific context for runtime injection, extracted from:

- Problem statement from orientation
- Requirements (P0/P1) from orientation
- Technical approach from architecture
- Components from architecture
- Constraints from orientation

This file is injected at runtime by `cub run` when executing tasks from this plan. It is NOT a global file — each plan gets its own context file.

---

## Spec Lifecycle

On successful staging, the spec moves through the lifecycle:

```
specs/planned/my-feature.md → specs/staged/my-feature.md
```

---

## Output

After staging completes:

```
Staging complete!
Duration: 2.3s

Created: 3 epics, 12 tasks
Spec moved to: specs/staged/my-feature.md
Generated: plans/<slug>/prompt-context.md

Next step: cub run
```

---

## Verifying the Import

```bash
# List all tasks
bd list

# Show ready tasks (no blockers)
bd ready

# Show task details
bd show auth-001
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or already staged) |
| `1` | Error occurred |

---

## Related Commands

- [`cub plan`](plan.md) - Create plans to stage
- [`cub run`](run.md) - Execute staged tasks
- [`cub status`](status.md) - View task progress

---

## See Also

- [Stage Guide](../guide/plan-flow/stage.md) - Detailed staging documentation
- [Plan Flow](../guide/plan-flow/index.md) - Complete pipeline overview
