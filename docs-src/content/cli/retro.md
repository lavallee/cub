---
title: cub retro
description: Generate retrospective reports for completed plans and epics.
---

# cub retro

Generate a detailed retrospective report for a completed plan or epic, summarizing outcomes, metrics, decisions, and lessons learned.

---

## Synopsis

```bash
cub retro <ID> [OPTIONS]
```

---

## Description

The `retro` command aggregates data from the ledger, task backend, and git history to produce a comprehensive retrospective report. By default it treats the ID as a plan ID; use `--epic` to treat it as an epic ID instead.

The report is designed for team review, sprint retrospectives, or archival documentation. It captures both quantitative metrics and qualitative insights from the completed work.

---

## Arguments

| Argument | Description |
|----------|-------------|
| `ID` | Plan or epic ID to generate the retrospective for |

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--epic` | | Treat the ID as an epic ID (default treats as plan ID) |
| `--output PATH` | `-o` | Write the report to a file (default: print to stdout) |
| `--help` | `-h` | Show help message and exit |

---

## Report Contents

The retrospective report includes the following sections:

### Executive Summary

High-level outcome: what was built, how long it took, and whether it met its goals.

### Timeline

Start and end dates, total elapsed time, and active working time.

### Metrics

| Metric | Description |
|--------|-------------|
| Total cost | Aggregate USD cost across all sessions |
| Total tokens | Input and output token counts |
| Duration | Wall-clock and active session time |
| Tasks | Total, completed, failed, and skipped counts |
| Sessions | Number of harness invocations |

### Task List with Outcomes

Each task in the epic or plan, with its final status, duration, cost, and any notes.

### Key Decisions

Significant architectural or implementation decisions recorded during the work.

### Lessons Learned

Patterns that worked well and areas for improvement, extracted from ledger entries and session notes.

### Issues Encountered

Blockers, failures, and retries that occurred during execution.

---

## Examples

### Retrospective for a Plan

```bash
cub retro cub-048a
```

Prints the full retrospective to stdout.

### Retrospective for an Epic

```bash
cub retro cub-048a --epic
```

Treats `cub-048a` as an epic ID and generates the report from all tasks in that epic.

### Save to File

```bash
cub retro cub-048a -o retro.md
```

Writes the report to `retro.md` for review or archival.

### Combined Options

```bash
cub retro cub-048a --epic -o reports/sprint-retro.md
```

Generate an epic-level retrospective and save it to a specific path.

---

## Output Format

The report is formatted as Markdown. When printed to stdout, it renders well in terminals that support Markdown (or can be piped to a viewer). When saved to a file, it is ready for inclusion in documentation or pull request descriptions.

Example output structure:

```markdown
# Retrospective: cub-048a

## Executive Summary
Completed the authentication feature across 8 tasks in 3 sessions...

## Timeline
- Started: 2026-01-20
- Completed: 2026-01-25
- Active time: 4h 12m

## Metrics
| Metric        | Value     |
|---------------|-----------|
| Total cost    | $2.47     |
| Total tokens  | 384,000   |
| Tasks         | 8/8       |
| Sessions      | 3         |

## Tasks
1. cub-048a-1 — Set up auth models (completed, $0.31)
2. cub-048a-2 — Implement login endpoint (completed, $0.45)
...

## Lessons Learned
- Breaking auth into small tasks reduced retry rate
- Pre-commit hooks caught 2 type errors early
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Report generated successfully |
| `1` | Error (ID not found, no ledger entries, write failure) |

---

## Related Commands

- [`cub release`](release.md) - Mark work as released after retrospective
- [`cub ledger show`](ledger.md) - View raw ledger entries
- [`cub ledger stats`](ledger.md) - Aggregate ledger statistics
- [`cub review`](review.md) - Assess task implementations against requirements

---

## See Also

- [Retrospectives Guide](../guide/retrospectives/index.md) - Running effective retrospectives
- [Ledger Guide](../guide/ledger/index.md) - Understanding the task completion ledger
- [Release Workflow](../guide/releases/index.md) - End-to-end release process
