---
title: cub punchlist
description: Process punchlist files into itemized plans with structured tasks.
---

# cub punchlist

Process punchlist markdown files into itemized plans, converting informal notes and TODO lists into structured epics with tasks.

---

## Synopsis

```bash
cub punchlist [FILE] [OPTIONS]
```

---

## Description

The `punchlist` command bridges informal notes and the formal task system. It takes a markdown file containing a list of issues, remaining work, or polish items, and uses an AI harness to decompose them into structured epics with individual tasks.

Punchlist files are typically stored in `plans/_punchlists/` and can be created manually or captured during development sessions.

---

## Arguments

| Argument | Description |
|----------|-------------|
| `FILE` | Punchlist markdown file to process |

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--epic-title TEXT` | `-t` | Custom title for the epic (default: derived from filename) |
| `--label TEXT` | `-l` | Additional labels for the epic (can be repeated) |
| `--dry-run` | `-n` | Show what would be generated without writing files |
| `--output PATH` | `-o` | Custom output path for the plan file |
| `--stream` | `-s` | Stream Claude's output in real-time |
| `--debug` | | Show debug information (prompts, raw responses) |
| `--verbose` | `-v` | Show full raw text before each item |
| `--list` | | List punchlist files in `plans/_punchlists/` |
| `--help` | `-h` | Show help message and exit |

---

## Examples

### Process a Punchlist

```bash
# Process a specific punchlist file
cub punchlist plans/_punchlists/post-review.md
```

### Preview Without Writing

```bash
# Dry run to see what tasks would be created
cub punchlist plans/_punchlists/polish.md --dry-run
```

### Custom Epic Title

```bash
# Override the default epic title
cub punchlist todo.md --epic-title "Post-Launch Polish"
```

### Stream Output

```bash
# Watch the AI process items in real-time
cub punchlist items.md --stream
```

### List Available Punchlists

```bash
# See what punchlist files exist
cub punchlist --list
```

### Add Labels

```bash
# Tag the generated epic with labels
cub punchlist items.md --label cleanup --label v2
```

---

## Punchlist File Format

Punchlist files are simple markdown with items to process:

```markdown
# Post-Review Cleanup

- Fix the error handling in the auth module — currently swallows exceptions
- The dashboard API returns 500 when no data exists, should return empty array
- Add input validation to the user registration endpoint
- Refactor the duplicate code in `sync.py` and `async_sync.py`
- Missing tests for the edge case where token expires mid-request
```

Each item is analyzed and decomposed into one or more tasks with acceptance criteria.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Punchlist processed successfully |
| `1` | Processing error |

---

## Related Commands

- [`cub plan`](plan.md) - Full planning pipeline for larger features
- [`cub task`](task.md) - View and manage generated tasks
- [`cub stage`](stage.md) - Import plan tasks into the backend

---

## See Also

- [Plan Flow Guide](../guide/plan-flow/index.md) - Understanding the planning pipeline
- [Task Management](../guide/tasks/index.md) - Working with tasks
