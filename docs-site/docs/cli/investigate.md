---
title: cub investigate
description: Investigate and process captures into actionable items based on their type.
---

# cub investigate

Investigate and process captures into actionable items based on their type.

## Synopsis

```bash
cub investigate [OPTIONS] [CAPTURE_ID]
```

## Description

The `cub investigate` command analyzes captures and determines what action each needs. It automatically categorizes captures and processes them appropriately:

| Category | Description | Action Taken |
|----------|-------------|--------------|
| `quick` | Small, immediate fixes | Creates a task |
| `audit` | Code exploration needed | Runs analysis, generates report |
| `research` | External investigation needed | Creates research template |
| `design` | Planning and feedback needed | Creates design document |
| `spike` | Exploratory work on a branch | Creates spike task |
| `unclear` | Needs clarification | Asks clarifying questions |

Output artifacts are saved to `specs/investigations/`.

## Arguments

| Argument | Description |
|----------|-------------|
| `CAPTURE_ID` | Capture ID to investigate (e.g., cap-042). Optional if using `--all`. |

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | `-a` | Investigate all active captures |
| `--mode MODE` | `-m` | Override auto-categorization (quick, audit, research, design, spike, unclear) |
| `--dry-run` | `-n` | Show what would be done without doing it |
| `--batch-quick-fixes` | | Batch quick fixes into a single task |
| `--help` | `-h` | Show help message and exit |

## Category Detection

The investigate command uses heuristics to categorize captures:

### quick

Detected when content contains indicators of small, well-defined changes:

- "fix typo", "fix bug", "fix error"
- "remove", "delete", "rename"
- "add option", "add flag", "add argument"
- "should take", "should accept", "should support"
- Short content (< 300 characters) with specific code references

**Action:** Creates a task in your task backend and archives the capture.

### audit

Detected when content suggests code exploration:

- "track all", "find all", "audit"
- "where do we", "how many", "list all"
- "search for"

**Action:** Runs code analysis, extracts search patterns, and generates a report at `specs/investigations/{id}-audit.md`.

### research

Detected when content suggests external investigation:

- "check out", "look at", "research"
- "investigate", "compare", "inspiration"
- "best practice", "how does", "what is"

**Action:** Creates a research template at `specs/investigations/{id}-research.md` with suggested search queries.

### design

Detected when content suggests planning needs:

- "think through", "design", "architect"
- "plan", "how should", "what if"
- "consider", "explore option"

**Action:** Creates a design document template at `specs/investigations/{id}-design.md`.

### spike

Detected when content suggests exploratory coding:

- "try", "test whether", "experiment"
- "prototype", "spike", "proof of concept"
- "explore approach", "see if"

**Action:** Creates a spike task for time-boxed exploration.

### unclear

Default when content is too short or ambiguous:

- Content less than 50 characters
- No clear category indicators

**Action:** Marks the capture for human review and appends clarifying questions.

## Output Formats

### Audit Report

```markdown
# Audit Report: {title}

**Capture ID:** cap-042
**Generated:** 2026-01-17 10:30:00 UTC
**Category:** audit

## Original Capture

{capture content}

## Search Patterns

- `pattern1`
- `pattern2`

## Findings

### Pattern: `pattern1`

Found in 5 file(s):
- `src/module.py`
- `src/other.py`

## Next Steps

- [ ] Review the findings above
- [ ] Identify patterns that need changes
- [ ] Create tasks for necessary modifications
```

### Research Template

```markdown
# Research: {title}

**Status:** needs_research

## Original Capture

{capture content}

## Suggested Search Queries

- [ ] "{query1}"
- [ ] "{query2}"

## Research Findings

### Key Sources

1. *Source 1*
2. *Source 2*

### Summary

*Summarize the key findings here.*

## Recommendations

- [ ] Recommendation 1
- [ ] Recommendation 2
```

### Design Document

```markdown
# Design: {title}

**Status:** draft

## Problem Statement

{capture content}

## Goals

- [ ] Goal 1
- [ ] Goal 2

## Proposed Solution

### Overview

*High-level description.*

### Detailed Design

*Detailed explanation.*

## Implementation Plan

### Phase 1

- [ ] Task 1
- [ ] Task 2
```

## Examples

### Investigate a single capture

```bash
cub investigate cap-042
```

Output:
```
Analyzing 1 capture(s)...

cap-042: Add dark mode toggle...
  Category: quick
  Action: Created task cub-123, archived capture

Summary:
+----------+-------+
| Category | Count |
+----------+-------+
| quick    | 1     |
+----------+-------+
```

### Investigate all captures

```bash
cub investigate --all
```

Processes all active captures that haven't been marked for review.

### Preview without changes

```bash
cub investigate --all --dry-run
```

Output:
```
Analyzing 5 capture(s)...

cap-042: Add dark mode toggle...
  Category: quick
  Action: Would create task for: Add dark mode toggle

cap-043: Audit error handling patterns...
  Category: audit
  Action: Would run code audit for: Audit error handling

Summary:
+----------+-------+
| Category | Count |
+----------+-------+
| quick    | 2     |
| audit    | 1     |
| research | 1     |
| unclear  | 1     |
+----------+-------+
```

### Override categorization

```bash
cub investigate cap-042 --mode=design
```

Forces the capture to be processed as a design item regardless of detected category.

### Batch quick fixes

```bash
cub investigate --all --batch-quick-fixes
```

Instead of creating individual tasks, groups all quick fixes into a single batched task:

```
Processing 4 batched quick fixes...
  Created batched task: cub-150
```

## Workflow Integration

### Daily capture processing

```bash
# Review what needs attention
cub investigate --all --dry-run

# Process everything
cub investigate --all
```

### Targeted investigation

```bash
# Focus on a specific capture
cub captures show cap-042
cub investigate cap-042

# Review the output
cat specs/investigations/cap-042-*.md
```

### Category override

Sometimes the automatic categorization is wrong:

```bash
# Force a capture to be treated as research
cub investigate cap-042 --mode=research
```

## Clarifying Questions

When a capture is categorized as `unclear`, the command appends questions:

```markdown
---

**Clarification needed** (2026-01-17 10:30:00 UTC)

This capture needs more detail. Please answer:

- Can you provide more context about what you're trying to accomplish?
- What specific question are you trying to answer?
- Which part of the codebase does this relate to?

Once clarified, run `cub investigate cap-042` again.
```

## Summary Table

After processing, a summary table shows category distribution:

```
Summary:
+----------+-------+
| Category | Count |
+----------+-------+
| quick    | 3     |
| audit    | 2     |
| research | 1     |
| design   | 1     |
| unclear  | 2     |
+----------+-------+
```

## Related Commands

- [`cub capture`](capture.md) - Create new captures
- [`cub captures`](captures.md) - List and manage captures
- [`cub organize-captures`](organize-captures.md) - Normalize capture files

## See Also

- [Roadmap](../contributing/roadmap.md) - Planned features and backlog
- [Task Management](../guide/tasks/index.md) - Working with tasks
- [Prep Pipeline](../guide/prep-pipeline/index.md) - Full planning workflow
