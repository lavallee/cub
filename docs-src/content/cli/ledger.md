---
title: cub ledger
description: View, query, and manage the task completion ledger.
---

# cub ledger

View and query the append-only task completion ledger that records all completed work.

---

## Synopsis

```bash
cub ledger <subcommand> [OPTIONS]
```

---

## Description

The `cub ledger` command provides access to the task completion ledger -- an append-only record of all completed work stored in `.cub/ledger/`. Every task completed by `cub run` or via direct session commands (`cub done`) creates a ledger entry with detailed metadata including cost, token usage, duration, files changed, commits, verification status, and workflow stage.

The ledger serves as the institutional memory of the project, enabling retrospectives, cost analysis, pattern extraction, and audit trails.

### Ledger Storage Structure

```
.cub/ledger/
├── index.jsonl              # Index of all entries (fast lookups)
├── by-task/{task-id}/       # Full entries grouped by task ID
│   └── entry.json           # Complete ledger entry
├── by-epic/{epic-id}/       # Entries grouped by epic
├── by-run/{run-id}/         # Entries grouped by run session
└── forensics/               # Session event logs (JSONL per session)
    └── {session-id}.jsonl
```

---

## Subcommands

### cub ledger show

Show the detailed ledger entry for a completed task, including lineage, attempts, outcome, verification, and workflow stage.

```bash
cub ledger show <task-id> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to display (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--attempt` | `-a` | Show details for a specific attempt number |
| `--changes` | `-c` | Show detailed file changes and commits |
| `--history` | `-h` | Show workflow stage transition history |
| `--json` | | Output as JSON |
| `--agent` | | Output in agent-friendly markdown format |

---

### cub ledger stats

Show aggregate statistics for completed work, including task counts, cost metrics, token usage, time metrics, verification rates, and file changes.

```bash
cub ledger stats [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--since` | Only include tasks completed since date (YYYY-MM-DD) |
| `--epic` | Only include tasks in this epic |
| `--json` | Output as JSON |

---

### cub ledger search

Search ledger entries by title, files changed, or spec files. Supports filtering by workflow stage, cost threshold, verification status, and escalation status.

```bash
cub ledger search <query> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `QUERY` | Search query string (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--field` | `-f` | Fields to search: `title`, `files`, `spec` (can be repeated; default: all) |
| `--since` | | Only include tasks completed since date (YYYY-MM-DD) |
| `--epic` | | Only include tasks in this epic |
| `--verification` | | Filter by verification status: `pass`, `fail`, `warn`, `skip`, `pending`, `error` |
| `--stage` | | Filter by workflow stage: `dev_complete`, `needs_review`, `validated`, `released` |
| `--cost-above` | | Filter to tasks with cost above this threshold (USD) |
| `--escalated` | | Filter to escalated (`true`) or non-escalated (`false`) tasks |
| `--json` | | Output as JSON |

---

### cub ledger update

Update the workflow stage for a completed task. Transitions a task through post-completion stages (dev_complete, needs_review, validated, released) and records the change in the task's state history.

```bash
cub ledger update <task-id> [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to update (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--stage` | `-s` | New workflow stage: `dev_complete`, `needs_review`, `validated`, `released` (required) |
| `--reason` | `-r` | Reason for the stage transition |

---

### cub ledger export

Export ledger data for external analysis or reporting.

```bash
cub ledger export [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--format` | `-f` | Export format: `json` or `csv` (default: `json`) |
| `--epic` | `-e` | Only export tasks in this epic |
| `--output` | `-o` | Output file path (default: stdout) |
| `--since` | | Only include tasks completed since date (YYYY-MM-DD) |

---

### cub ledger gc

Garbage collect old attempt files. Scans all task directories and identifies attempt files that could be removed based on retention policy. Currently runs in dry-run mode only.

```bash
cub ledger gc [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--keep-latest` | `-k` | Number of latest attempts to keep per task (default: `5`) |
| `--dry-run` | | Show what would be deleted without deleting (default: `true`) |

---

### cub ledger extract

Extract insights (approach, decisions, lessons learned) from task execution logs using Claude Haiku. Can process a single task or batch process all tasks.

```bash
cub ledger extract [TASK_ID] [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to extract insights for (optional if `--all` is used) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | | Extract insights for all tasks with empty lessons_learned |
| `--force` | `-f` | Re-extract insights even if already present |
| `--verbose` | `-v` | Show detailed extraction output |

---

## Examples

### Viewing Completed Work

```bash
# Show ledger entry for a task
cub ledger show cub-048a-5

# Show a specific attempt in detail
cub ledger show cub-048a-5 --attempt 2

# Show all file changes and commits
cub ledger show cub-048a-5 --changes

# Show workflow stage history
cub ledger show cub-048a-5 --history

# Get full entry as JSON
cub ledger show cub-048a-5 --json
```

### Statistics and Analysis

```bash
# Show overall ledger statistics
cub ledger stats

# Stats for a specific time period
cub ledger stats --since 2026-01-01

# Stats for a specific epic
cub ledger stats --epic cub-048a

# Stats as JSON for scripting
cub ledger stats --json
```

### Searching the Ledger

```bash
# Search by keyword
cub ledger search "authentication"

# Search only in file names
cub ledger search "api" --field files

# Filter by workflow stage
cub ledger search "feature" --stage needs_review

# Find expensive tasks
cub ledger search "complex" --cost-above 0.50

# Find escalated tasks
cub ledger search "hard" --escalated true

# Combine filters
cub ledger search "login" --epic cub-048a --since 2026-01-01 --json
```

### Workflow Stage Management

```bash
# Mark a task as needing review
cub ledger update cub-048a-5 --stage needs_review

# Mark as validated with reason
cub ledger update cub-048a-5 --stage validated --reason "Tests passed, code reviewed"

# Mark as released
cub ledger update cub-048a-5 --stage released --reason "Deployed to production"
```

### Exporting Data

```bash
# Export all entries as JSON
cub ledger export --format json --output ledger.json

# Export a specific epic as CSV
cub ledger export --format csv --epic cub-048a --output epic-report.csv

# Export recent work to stdout
cub ledger export --format json --since 2026-02-01
```

### Insight Extraction

```bash
# Extract insights for a single task
cub ledger extract cub-048a-5

# Extract insights for all tasks
cub ledger extract --all

# Re-extract with verbose output
cub ledger extract --all --force --verbose
```

### Garbage Collection

```bash
# Preview what would be cleaned up
cub ledger gc

# Keep only 3 most recent attempts per task
cub ledger gc --keep-latest 3
```

---

## Workflow Stages

Completed tasks progress through post-completion workflow stages:

| Stage | Description |
|-------|-------------|
| `dev_complete` | Development finished (default after task closure) |
| `needs_review` | Awaiting code review or validation |
| `validated` | Reviewed and approved |
| `released` | Deployed or shipped |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Command completed successfully |
| `1` | Error (entry not found, invalid query, write failure) |

---

## Related Commands

- [`cub verify`](../guide/advanced/audit.md) - Check ledger consistency and data integrity
- [`cub reconcile`](../guide/hooks/index.md) - Reconstruct ledger entries from session forensics
- [`cub retro`](../guide/advanced/index.md) - Generate retrospective reports from ledger data
- [`cub review`](../guide/run-loop/completion.md) - Review completed task implementations
- [`cub session`](session.md) - Track work in direct harness sessions

---

## See Also

- [Run Loop Guide](../guide/run-loop/index.md) - How the run loop creates ledger entries
- [Task Management Guide](../guide/tasks/index.md) - Understanding the task lifecycle
- [Configuration Reference](../guide/configuration/reference.md) - Ledger configuration options
- [Hooks Guide](../guide/hooks/index.md) - How hooks feed session forensics into the ledger
