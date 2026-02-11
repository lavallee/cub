---
title: cub learn extract
description: Extract patterns and lessons from completed work in the ledger.
---

# cub learn extract

Analyze ledger entries to discover patterns, duration trends, success and failure signals, and actionable recommendations.

---

## Synopsis

```bash
cub learn extract [OPTIONS]
```

---

## Description

The `learn extract` command reads your task completion ledger and surfaces insights about how work gets done in your project. It examines:

- **Common patterns** in task completion (recurring approaches, tool usage, file change patterns)
- **Duration and effort trends** (how long tasks take, cost distribution across epics)
- **Success and failure patterns** (what correlates with clean completions vs retries)
- **Technology and domain insights** (which areas of the codebase see the most churn)
- **Recommendations** for future work (process improvements, guardrail suggestions)

Use this after completing an epic or a batch of tasks to capture institutional knowledge before it fades from context.

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--since DAYS` | | Analyze work from the last N days |
| `--since-date DATE` | | Analyze work since a specific date (YYYY-MM-DD format) |
| `--verbose` | `-v` | Show detailed pattern information and reasoning |
| `--output PATH` | `-o` | Save analysis to a file instead of printing to stdout |
| `--apply` | | Apply pattern insights to guardrails and documentation |
| `--help` | `-h` | Show help message and exit |

---

## Examples

### Analyze All Entries

```bash
cub learn extract
```

Examines every ledger entry in the project.

### Recent Work Only

```bash
# Last 7 days
cub learn extract --since 7

# Since a specific date
cub learn extract --since-date 2026-02-01
```

### Detailed Output

```bash
cub learn extract --verbose
```

Shows the reasoning behind each pattern and how frequently it was observed.

### Save to File

```bash
cub learn extract --output analysis.md
```

Writes the full analysis to `analysis.md` for review or inclusion in retrospectives.

### Apply Insights

```bash
cub learn extract --apply
```

Automatically updates guardrails and project documentation with discovered patterns. This writes to `.cub/guardrails.md` and may update `agent.md` with new gotchas.

### Combine Options

```bash
cub learn extract --since 14 --verbose --output sprint-review.md
```

Analyze the last two weeks with detailed output, saved to a file.

---

## Output

The analysis report includes sections such as:

```
Pattern Analysis
================

Completion Patterns:
  - 78% of tasks completed in a single session
  - Average task duration: 12.4 minutes
  - Most common failure reason: test failures (3 occurrences)

Effort Distribution:
  - Epic cub-048a: 65% of total tokens
  - Epic cub-049b: 35% of total tokens

Technology Insights:
  - Most modified package: cub.core.services (14 tasks)
  - Test coverage correlated with first-attempt success

Recommendations:
  - Add pre-commit type checking (3 tasks failed on mypy)
  - Consider splitting large epics (048a had 12 tasks)
```

---

## Related Commands

- [`cub ledger show`](ledger.md) - View completed work ledger
- [`cub ledger stats`](ledger.md) - Show ledger statistics
- [`cub retro`](retro.md) - Generate retrospective reports for epics and plans
- [`cub verify`](verify.md) - Verify ledger and data integrity

---

## See Also

- [Ledger Guide](../guide/ledger/index.md) - Understanding the task completion ledger
- [Guardrails Guide](../guide/guardrails/index.md) - Managing institutional memory
- [Retrospectives](../guide/retrospectives/index.md) - Post-completion analysis workflows
