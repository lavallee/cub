---
title: cub audit
description: Run code health audits to identify dead code, missing docs, and coverage gaps.
---

# cub audit

Run automated code health audits that check for dead code, documentation gaps, test coverage, and other quality metrics.

---

## Synopsis

```bash
cub audit [COMMAND]
```

---

## Description

The `audit` command provides automated analysis of your codebase health. It uses AI-assisted inspection to identify issues that traditional linters miss, such as dead code paths, missing documentation for public APIs, and areas with insufficient test coverage.

!!! warning "Experimental"
    This command is experimental. Interface and behavior may change between releases.

---

## Subcommands

### run

Run the code health audit.

```bash
cub audit run
```

---

## Examples

```bash
# Run a full audit
cub audit run
```

---

## Related Commands

- [`cub doctor`](../doctor.md) - Diagnose cub configuration issues
- [`cub verify`](../verify.md) - Verify cub data integrity
