---
title: cub triage
description: Refine requirements through interactive AI-assisted questioning.
---

# cub triage

Analyze capture files or raw text to understand the problem space and generate structured requirements.

---

## Synopsis

```bash
cub triage [FILE] [OPTIONS]
```

---

## Description

The `triage` command takes informal ideas (capture files, raw text) and refines them into structured requirements through AI-assisted analysis. It generates acceptance criteria, identifies constraints, and suggests task decomposition.

This command is delegated to the bash implementation.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Examples

```bash
# Triage a specific capture file
cub triage my-idea.md

# Triage all open captures
cub triage --all
```

---

## Related Commands

- [`cub capture`](../capture.md) - Create captures to triage
- [`cub spec`](../plan.md) - Full specification interview
- [`cub plan`](../plan.md) - Planning pipeline for larger work
