---
title: cub import
description: Import tasks from external sources into your task backend.
---

# cub import

Load tasks from external sources (CSV, JSON, GitHub Issues, Jira) into your cub task backend.

---

## Synopsis

```bash
cub import [SOURCE] [OPTIONS]
```

---

## Description

The `import` command bridges external task trackers and cub's task system. It reads tasks from various formats and creates them in your configured backend, preserving metadata like priority, labels, and dependencies where possible.

This command is delegated to the bash implementation.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Examples

```bash
# Import from GitHub issues
cub import github my-repo

# Import from CSV file
cub import csv tasks.csv

# Import from Jira
cub import --format=jira <url>
```

---

## Related Commands

- [`cub task`](../task.md) - Manage imported tasks
- [`cub plan`](../plan.md) - Alternative: plan and generate tasks
