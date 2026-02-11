---
title: cub session
description: Track work done in direct harness sessions outside of cub run.
---

# cub session

Record and track work performed in direct harness sessions (Claude Code, Codex, OpenCode) outside of `cub run`.

---

## Synopsis

```bash
cub session <subcommand> [OPTIONS]
```

---

## Description

The `cub session` commands bridge the gap between direct harness usage and the structured ledger system that `cub run` manages automatically. When you work directly in Claude Code or another harness, these commands let you record your work so it appears in the ledger alongside `cub run` entries.

This creates a unified audit trail regardless of whether work was done autonomously via `cub run` or interactively in a direct session.

### When to Use

Use `cub session` commands when you are:

- Working directly in Claude Code (not via `cub run`)
- Interacting with Codex, Gemini, or OpenCode manually
- Making changes outside the automated loop that should be tracked

### How It Works

1. Start working on a task in your harness
2. Use `cub session wip` to mark the task as in-progress
3. Work normally -- write code, run tests, commit changes
4. Use `cub session done` to mark the task complete and create a ledger entry

If hooks are configured (via `cub init`), much of this tracking happens automatically through the symbiotic workflow. These commands provide explicit control when needed.

---

## Subcommands

### cub session log

Add a timestamped entry to the session log at `.cub/session.log`. This creates a running audit trail similar to what `cub run` produces automatically.

```bash
cub session log <message>
```

Note: This command is also available as the shorthand `cub log`.

#### Arguments

| Argument | Description |
|----------|-------------|
| `MESSAGE` | Log message to record (required) |

---

### cub session done

Mark a task as complete and create a ledger entry. This command closes the task in the backend and writes a full ledger entry with synthetic forensics events, providing the same audit trail that `cub run` would create.

All ledger entries created by this command are tagged with `source="direct_session"` for traceability.

```bash
cub session done <task-id> [OPTIONS]
```

Note: This command is also available as the shorthand `cub done`.

#### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to mark as complete (required) |

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--reason` | `-r` | Reason or summary of completion |
| `--file` | `-f` | Files changed during task (can be repeated) |

---

### cub session wip

Mark a task as in-progress. Updates the task status in the backend and logs the start of work to the session log.

```bash
cub session wip <task-id>
```

Note: This command is also available as the shorthand `cub wip`.

#### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to mark as in-progress (required) |

---

## Examples

### Basic Session Workflow

```bash
# Start working on a task
cub session wip cub-048a-5

# Log progress as you work
cub session log "Implemented user validation logic"
cub session log "Added unit tests for edge cases"
cub session log "All tests passing"

# Mark the task as complete
cub session done cub-048a-5 --reason "Implemented and tested user validation"
```

### Recording File Changes

```bash
# Complete a task and record which files were changed
cub session done cub-048a-5 \
    --reason "Added authentication middleware" \
    --file src/middleware/auth.py \
    --file tests/test_auth.py \
    --file src/config/settings.py
```

### Quick Logging

```bash
# Record observations during a session
cub session log "Found edge case in date parsing -- needs fix"
cub session log "Refactored database connection pool for better error handling"
cub session log "Ready to commit -- all quality gates pass"
```

### Using Shorthand Commands

The session subcommands are also registered as top-level shortcuts:

```bash
# These are equivalent:
cub session log "message"     # Full form
cub log "message"             # Shorthand

cub session done cub-048a-5   # Full form
cub done cub-048a-5           # Shorthand

cub session wip cub-048a-5    # Full form
cub wip cub-048a-5            # Shorthand
```

---

## Session Log

The `cub session log` command appends timestamped entries to `.cub/session.log`:

```
[2026-02-11 14:30:00 UTC] Started working on authentication feature
[2026-02-11 14:45:00 UTC] Fixed bug in user validation logic
[2026-02-11 15:00:00 UTC] All tests passing, ready to commit
```

This file provides a human-readable audit trail for direct sessions.

---

## Comparison with cub run

| Capability | `cub run` | `cub session` commands |
|------------|-----------|------------------------|
| Task selection | Automatic | Manual (`cub session wip`) |
| Progress logging | Automatic | Manual (`cub session log`) |
| Ledger entry creation | Automatic on completion | Via `cub session done` |
| File tracking | Automatic from harness | Manual via `--file` flag |
| Cost/token tracking | Automatic from harness | Not captured (use `cub reconcile` for enrichment) |

For richer automatic tracking in direct sessions, configure hooks via `cub init`. The symbiotic workflow captures file writes, git commits, and task commands through Claude Code hooks without manual intervention.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Command completed successfully |
| `1` | Error (task not found, backend error, ledger write failure) |

---

## Related Commands

- [`cub task claim`](task.md) - Claim a task (alternative to `cub session wip`)
- [`cub task close`](task.md) - Close a task without creating a ledger entry
- [`cub reconcile`](../guide/hooks/index.md) - Reconstruct ledger entries from hook forensics
- [`cub ledger`](ledger.md) - View and query completed work records
- [`cub run`](run.md) - Execute tasks autonomously (handles tracking automatically)

---

## See Also

- [Hooks Guide](../guide/hooks/index.md) - Automatic tracking via the symbiotic workflow
- [Task Management Guide](../guide/tasks/index.md) - Understanding the task lifecycle
- [Run Loop Guide](../guide/run-loop/index.md) - How `cub run` manages sessions automatically
