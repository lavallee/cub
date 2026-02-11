---
title: cub verify
description: Verify cub data integrity including ledger consistency, ID formats, and counter synchronization.
---

# cub verify

Verify cub data integrity. Checks ledger consistency, ID formats, duplicate detection, and counter synchronization.

---

## Synopsis

```bash
cub verify [OPTIONS]
```

---

## Description

The `cub verify` command performs a comprehensive integrity check of your cub project data. It scans multiple data sources and validates their consistency, reporting issues by severity level.

Use this command to:

- **Detect data corruption** before it causes problems in task execution
- **Validate ledger entries** after manual edits or failed sessions
- **Check ID integrity** to catch format violations or duplicates
- **Verify counter synchronization** to ensure ID sequences match actual usage
- **Auto-fix simple issues** with the `--fix` flag

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--fix` | | Attempt to auto-fix simple issues |
| `--ledger/--no-ledger` | | Check ledger consistency (default: enabled) |
| `--ids/--no-ids` | | Check ID integrity (default: enabled) |
| `--counters/--no-counters` | | Check counter sync status (default: enabled) |
| `--verbose` | `-v` | Show detailed information including info-level issues |
| `--help` | `-h` | Show help message and exit |

---

## What It Checks

### Ledger Consistency

Validates the structural integrity of the ledger:

| Check | Description |
|-------|-------------|
| File structure | Verifies expected directory layout under `.cub/ledger/` |
| JSON validity | Ensures all JSONL entries parse correctly |
| Entry completeness | Checks required fields are present in each entry |
| Index integrity | Validates `index.jsonl` matches by-task entries |

### ID Integrity

Validates task and epic identifiers across the project:

| Check | Description |
|-------|-------------|
| Format validation | IDs must match `{project}-{epic}-{task}` pattern |
| Duplicate detection | No two entities share the same ID |
| Cross-reference validation | Referenced IDs (dependencies, parents) exist |

### Counter Synchronization

Ensures internal counters stay in sync with actual data:

| Check | Description |
|-------|-------------|
| ID sequences | Counter values match the highest used ID number |
| Gap detection | Reports unexpected gaps in ID sequences |

---

## Issue Severity Levels

The verify command categorizes issues by severity:

| Severity | Display | Meaning |
|----------|---------|---------|
| Error | Red | Data integrity problem that requires action |
| Warning | Yellow | Potential issue that may need attention |
| Info | Blue | Informational (only shown with `--verbose`) |

---

## Auto-Fix

When you run `cub verify --fix`, the command attempts to repair simple issues automatically. Each fixable issue is marked with `(auto-fixable)` in the output.

Common auto-fixes include:

- Rebuilding the ledger index from by-task entries
- Correcting counter values to match actual usage
- Normalizing malformed entries where data is recoverable

Issues that cannot be auto-fixed are reported with a suggested manual resolution.

---

## Examples

### Run All Checks

```bash
cub verify
```

Output:
```
Verifying cub data integrity...

Checking: ledger, IDs, counters

Verification Summary:
  Checks run: 3
  Files checked: 47

No issues found - data integrity verified
```

### Auto-Fix Simple Issues

```bash
cub verify --fix
```

Output:
```
Verifying cub data integrity...
Auto-fix mode enabled

Verification Summary:
  Checks run: 3
  Files checked: 47

Auto-fixed 2 issue(s)
```

### Check Only Ledger Consistency

```bash
cub verify --no-ids --no-counters
```

### Check Only ID Integrity

```bash
cub verify --no-ledger --no-counters
```

### Show All Issues Including Informational

```bash
cub verify --verbose
```

Output:
```
Verifying cub data integrity...

Checking: ledger, IDs, counters

Verification Summary:
  Checks run: 3
  Files checked: 47

                    Issues Found
+----------+----------+------------------------+----------+
| Severity | Category | Message                | Location |
+----------+----------+------------------------+----------+
| WARNING  | ledger   | Missing index entry    | by-task/ |
| INFO     | IDs      | Gap in ID sequence     | cub-042  |
+----------+----------+------------------------+----------+

Fix Suggestions:
  - Rebuild ledger index (auto-fixable)

Run with --fix to automatically fix simple issues

Found 1 warning(s)
Found 1 info message(s)
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed (or only warnings/info) |
| `1` | Errors found that require attention |

---

## Related Commands

- [`cub ledger`](ledger.md) - View and search the task completion ledger
- [`cub doctor`](doctor.md) - Diagnose configuration and setup issues
- [`cub reconcile`](reconcile.md) - Reconstruct ledger entries from forensics

---

## See Also

- [Data Integrity Guide](../guide/data-integrity/index.md) - Understanding cub data structures
- [Ledger Guide](../guide/ledger/index.md) - How the ledger works
- [Troubleshooting](../troubleshooting/index.md) - Common issues and solutions
