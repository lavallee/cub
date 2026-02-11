---
title: cub review
description: Assess completed task, epic, or plan implementations against requirements and specifications.
---

# cub review

Assess completed task, epic, or plan implementations by examining ledger entries, verification status, spec drift, and commit history.

---

## Synopsis

```bash
cub review task <TASK_ID> [OPTIONS]
cub review epic <EPIC_ID> [OPTIONS]
cub review plan <PLAN_SLUG> [OPTIONS]
```

---

## Description

The `cub review` command provides structured assessment of completed work at three levels of granularity:

- **Task review**: Examines a single task's ledger entry for verification status, spec drift, outcome success, and commit history
- **Epic review**: Assesses all tasks in an epic with aggregate completion rates and an overall grade
- **Plan review**: Reviews all epics and tasks associated with a plan session, providing a comprehensive assessment of plan completion

Each review level can optionally run **deep analysis** using an LLM to compare the actual implementation against the original specification.

---

## Subcommands

### `cub review task`

Review a single task implementation.

| Argument/Option | Short | Description |
|-----------------|-------|-------------|
| `TASK_ID` (required) | | Task ID to review |
| `--json` | | Output as JSON |
| `--verbose` | `-v` | Show detailed output including recommendations |
| `--deep` | | Run LLM-based deep analysis of implementation vs spec |

### `cub review epic`

Review all tasks in an epic.

| Argument/Option | Short | Description |
|-----------------|-------|-------------|
| `EPIC_ID` (required) | | Epic ID to review |
| `--json` | | Output as JSON |
| `--verbose` | `-v` | Show detailed output including recommendations |
| `--deep` | | Run LLM-based deep analysis of implementation vs spec |

### `cub review plan`

Review all work from a plan.

| Argument/Option | Short | Description |
|-----------------|-------|-------------|
| `PLAN_SLUG` (required) | | Plan slug to review |
| `--json` | | Output as JSON |
| `--verbose` | `-v` | Show detailed output including recommendations |
| `--deep` | | Run LLM-based deep analysis of implementation vs spec |

---

## What It Reviews

### Task-Level Assessment

For each task, the reviewer examines:

| Criterion | Description |
|-----------|-------------|
| Verification status | Whether the task passed verification checks |
| Outcome success | Whether the task was marked as successful in the ledger |
| Spec drift | Divergence between the original spec and the implementation |
| Commit history | Git commits associated with the task |
| Acceptance criteria | Whether stated acceptance criteria were met |

### Epic-Level Assessment

In addition to per-task assessments, epic reviews provide:

- **Completion rate** -- percentage of tasks completed
- **Aggregate grade** -- overall assessment across all tasks
- **Task breakdown** -- individual task assessments within the epic

### Plan-Level Assessment

Plan reviews aggregate across all epics in a plan:

- **Epic completion** -- which epics are fully implemented
- **Overall plan grade** -- aggregate assessment of plan execution
- **Gap analysis** -- work that was planned but not completed

### Deep Analysis

When `--deep` is specified, the reviewer uses an LLM to perform a detailed comparison of the implementation against the original specification. This catches subtle issues like:

- Partial implementations that pass basic checks
- Spec requirements that were interpreted differently
- Missing edge cases or error handling
- Architectural deviations from the planned approach

---

## Examples

### Review a Single Task

```bash
cub review task cub-048a-5.4
```

### Review a Task with Verbose Output

```bash
cub review task cub-048a-5.4 --verbose
```

### Review a Task with Deep Analysis

```bash
cub review task cub-048a-5.4 --deep
```

### Review an Epic

```bash
cub review epic cub-048a
```

### Review a Plan

```bash
cub review plan unified-tracking-model
```

### JSON Output for Scripting

```bash
# Task review as JSON
cub review task cub-048a-5.4 --json

# Epic review as JSON
cub review epic cub-048a --json

# Plan review as JSON
cub review plan unified-tracking-model --json
```

### Combine Options

```bash
# Verbose epic review with deep analysis
cub review epic cub-048a --verbose --deep

# JSON plan review with deep analysis
cub review plan unified-tracking-model --json --deep
```

---

## Output

### Default Output

The review displays a Rich-formatted assessment with:

- **Grade** (e.g., A, B, C, D, F) based on assessment criteria
- **Summary** of findings
- **Per-criterion results** with pass/fail indicators

### Verbose Output

With `--verbose`, additional details are shown:

- Detailed recommendations for improvement
- Individual criterion scores and reasoning
- Commit-level analysis

### JSON Output

With `--json`, the full assessment is serialized as structured JSON for use in scripts or CI pipelines.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Review completed successfully |
| `1` | Error occurred (no ledger found, invalid ID, etc.) |

---

## Related Commands

- [`cub retro`](retro.md) - Generate retrospective reports for completed work
- [`cub ledger`](ledger.md) - View and search the task completion ledger
- [`cub verify`](verify.md) - Verify cub data integrity
- [`cub status`](status.md) - Check current task progress

---

## See Also

- [Ledger Guide](../guide/ledger/index.md) - How the ledger tracks completed work
- [Review Workflow](../guide/review/index.md) - Best practices for reviewing implementations
- [Retrospectives](../guide/retrospectives/index.md) - Generating retros from completed work
