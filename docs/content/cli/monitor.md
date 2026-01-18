---
title: cub monitor
description: Display a live dashboard for an active cub run session.
---

# cub monitor

Display a live dashboard for monitoring an active cub run session with real-time updates.

---

## Synopsis

```bash
cub monitor [SESSION_ID] [OPTIONS]
```

---

## Description

The `monitor` command provides a live terminal dashboard that displays:

- Current task and iteration progress
- Budget usage (tokens, cost, tasks completed)
- Session phase and status
- Recent activity log

The dashboard auto-refreshes and updates in real-time as the run progresses.

---

## Arguments

| Argument | Description |
|----------|-------------|
| `SESSION_ID` | Session ID or run ID to monitor (optional, auto-detects latest) |

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--refresh SECONDS` | `-r` | Dashboard refresh interval (0.1-10.0, default: 1.0) |
| `--list` | | Show list of running sessions instead of monitoring |

---

## Dashboard Display

The dashboard shows a Rich-formatted terminal UI:

```
Monitoring session: cub-20260117-143022
Press Ctrl+C to exit

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                       Session Status                          ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Phase:        running                                         │
│ Iteration:    3 / 100                                         │
│ Current Task: cub-005: Add login validation                   │
├───────────────────────────────────────────────────────────────┤
│ Budget                                                        │
│   Tokens:     45,231 / 1,000,000                              │
│   Cost:       $0.4523 / $10.00                                │
│   Tasks:      2 completed                                     │
├───────────────────────────────────────────────────────────────┤
│ Recent Events                                                 │
│   [14:32:15] Starting task: Add login validation              │
│   [14:30:22] Task completed: Create login form                │
│   [14:28:45] Task completed: Add auth endpoints               │
└───────────────────────────────────────────────────────────────┘
```

---

## Examples

### Monitor Latest Session

```bash
# Auto-detect and monitor most recent session
cub monitor
```

### Monitor Specific Session

```bash
# Monitor by session ID
cub monitor cub-20260117-143022
```

### Faster Refresh Rate

```bash
# Update every half second
cub monitor --refresh 0.5
```

### List Running Sessions

```bash
# Show all sessions
cub monitor --list
```

Output:

```
Running Sessions
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Run ID                ┃ Session Name   ┃ Phase     ┃ Tasks Done ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ cub-20260117-143022   │ auth-feature   │ running   │ 2          │
│ cub-20260117-120000   │ cub-20260117   │ completed │ 5          │
└───────────────────────┴────────────────┴───────────┴────────────┘
```

---

## Session Phases

The dashboard shows the current session phase:

| Phase | Description |
|-------|-------------|
| `initializing` | Session starting up |
| `running` | Actively executing tasks |
| `completed` | All tasks finished successfully |
| `failed` | Run ended with error |
| `stopped` | User interrupted or max iterations reached |

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+C` | Exit monitor (doesn't stop the run) |

!!! note
    Exiting the monitor does not stop the running session. The session continues in the background.

---

## Status File Location

Monitor reads the status file at:

```
.cub/runs/{session-id}/status.json
```

If starting to monitor before the run creates this file, the monitor waits up to 10 seconds for it to appear.

---

## Running with Dashboard

Use `cub run --monitor` to launch both the run and dashboard together in a tmux split:

```bash
cub run --monitor
```

This creates a tmux session with:

- Left pane: Running `cub run`
- Right pane: Live dashboard (`cub monitor`)

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Monitor exited normally (user interrupt or session ended) |
| `1` | Error (no sessions found, read error) |

---

## Related Commands

- [`cub run`](run.md) - Start a task execution run
- [`cub run --monitor`](run.md) - Run with integrated dashboard
- [`cub status`](status.md) - Point-in-time status snapshot
- [`cub artifacts`](artifacts.md) - View completed task outputs

---

## See Also

- [Run Loop Guide](../guide/run-loop/index.md) - Understanding run execution
- [Budget Guide](../guide/budget/index.md) - Managing token and cost limits
