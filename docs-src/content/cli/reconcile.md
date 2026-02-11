---
title: cub reconcile
description: Reconstruct ledger entries from session forensics logs for post-hoc processing and repair.
---

# cub reconcile

Reconstruct ledger entries from session forensics logs. Ensures ledger completeness by replaying unprocessed session events.

---

## Synopsis

```bash
cub reconcile [OPTIONS]
```

---

## Description

The `cub reconcile` command processes hook-generated forensics logs from `.cub/ledger/forensics/` and produces complete ledger entries for sessions that have task associations but no corresponding ledger entry.

This is useful for:

- **Post-hoc processing** after direct Claude Code sessions where hooks partially failed
- **Repairing the ledger** when entries are missing or incomplete
- **Batch processing** multiple unprocessed sessions at once
- **Auditing** session activity with `--dry-run` before committing changes

The command is **idempotent** -- running it multiple times will not create duplicate entries. Sessions that already have ledger entries are skipped unless `--force` is used.

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--session ID` | `-s` | Reconcile a specific session ID only |
| `--dry-run` | `-n` | Show what would be reconciled without making changes |
| `--force` | `-f` | Force reconciliation even if ledger entry already exists |
| `--json` | | Output results as JSON |
| `--help` | `-h` | Show help message and exit |

---

## How It Works

The reconciliation process follows these steps:

1. **Scan** forensics directory (`.cub/ledger/forensics/`) for session JSONL files
2. **Parse** each forensics file to extract metadata (session ID, task claims, task closures)
3. **Filter** sessions that have task associations (skips sessions with no claimed task)
4. **Check** whether a ledger entry already exists for the task (skips if found, unless `--force`)
5. **Create** ledger entry from accumulated session events via `SessionLedgerIntegration`
6. **Write** entry to `.cub/ledger/by-task/{task_id}/` and update the ledger index

### Forensics Event Types

The reconciler processes these event types from forensics logs:

| Event Type | What It Captures |
|-----------|------------------|
| `session_start` | Session initialization timestamp |
| `file_write` | Files written during the session |
| `task_claim` | Task claimed for the session (provides task ID) |
| `task_close` | Task marked complete during the session |
| `git_commit` | Git commits made during the session |
| `session_end` | Session finalization timestamp |

---

## Examples

### Reconcile All Unprocessed Sessions

```bash
cub reconcile
```

Output:
```
      Reconciliation Summary
+------------------+-------+
| Total Sessions   |    14 |
| Processed        |     3 |
| Skipped          |    11 |
| Created          |     3 |
+------------------+-------+

Reconciliation complete. Created 3 ledger entries.
```

### Preview Without Making Changes

```bash
cub reconcile --dry-run
```

Output:
```
      Reconciliation Summary
+------------------+-------+
| Total Sessions   |    14 |
| Processed        |     3 |
| Skipped          |    11 |
| Would Create     |     3 |
+------------------+-------+

Dry run complete. 3 entries would be created.
```

### Reconcile a Specific Session

```bash
cub reconcile --session abc-123-def
```

### Force Re-Processing

Re-process sessions even if ledger entries already exist:

```bash
cub reconcile --force
```

### JSON Output for Scripting

```bash
cub reconcile --json
```

Output:
```json
{
  "processed": 3,
  "skipped": 11,
  "created": 3,
  "errors": 0,
  "sessions": [
    {
      "session_id": "abc-123-def",
      "task_id": "cub-048a-5.4",
      "status": "created",
      "entry_id": "ledger-001"
    }
  ]
}
```

### Combine Options

```bash
# Dry-run a specific session with JSON output
cub reconcile --session abc-123 --dry-run --json

# Force re-process all sessions
cub reconcile --force
```

---

## Session Skip Reasons

Sessions may be skipped during reconciliation for several reasons:

| Reason | Description |
|--------|-------------|
| `no_task_association` | No task was claimed during the session |
| `no_task_id` | Task claim event exists but has no task ID |
| `entry_exists` | Ledger entry already exists (use `--force` to override) |
| `no_entry_created` | Integration processed but produced no entry |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Reconciliation completed (including dry-run) |
| `1` | Error occurred during reconciliation |

---

## Related Commands

- [`cub session`](session.md) - Track work in direct harness sessions
- [`cub ledger`](ledger.md) - View and search the task completion ledger
- [`cub verify`](verify.md) - Verify cub data integrity

---

## See Also

- [Symbiotic Workflow Guide](../guide/symbiotic-workflow/index.md) - How hooks and forensics work
- [Ledger Guide](../guide/ledger/index.md) - Understanding the ledger system
- [Hooks Guide](../guide/hooks/index.md) - Hook configuration and troubleshooting
