---
title: cub version
description: Display the current cub version.
---

# cub version

Display the installed cub version and exit.

---

## Synopsis

```bash
cub version
```

---

## Description

Prints the current cub version number to stdout and exits. Useful for verifying your installation or including in bug reports.

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--help` | `-h` | Show help message and exit |

---

## Examples

```bash
# Check installed version
cub version

# Use in scripts
CUB_VERSION=$(cub version)
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Version printed successfully |

---

## Related Commands

- [`cub system-upgrade`](system-upgrade.md) - Upgrade to a newer version
- [`cub doctor`](doctor.md) - Full installation diagnostics
