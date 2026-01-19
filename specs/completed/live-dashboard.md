---
status: complete
version: 0.23
priority: high
complexity: medium
dependencies: []
created: 2026-01-10
updated: 2026-01-19
completed: 2026-01-17
implementation:
  - src/cub/cli/monitor.py
  - src/cub/dashboard/renderer.py
  - src/cub/dashboard/status.py
  - src/cub/dashboard/tmux.py
  - cub monitor command
notes: |
  Core dashboard implementation complete with rich TUI.
  `cub monitor` command working with live updates.
  tmux integration and multi-session support implemented.
source: ralph-claude-code, ralph
---

# Live Dashboard (tmux)

**Dependencies:** None  
**Complexity:** Medium

## Overview

Real-time visual monitoring during autonomous `cub run` sessions via an integrated tmux dashboard.

## Reference Implementation

Ralph implements this via `ralph --monitor` which launches a tmux session with:
- Main pane: Claude Code execution
- Side/bottom pane: Live dashboard with status updates

Key file: Ralph's monitoring is handled through `ralph-monitor` standalone command.

## Proposed Interface

```bash
# Launch with integrated dashboard
cub run --monitor

# Standalone monitor (attach to existing run)
cub monitor [session-id]

# Dashboard only (no execution)
cub monitor --attach
```

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│ CUB DASHBOARD                          Session: fox-20260113 │
├─────────────────────────────────────────────────────────────┤
│ Status: RUNNING          Iteration: 7/50                    │
│ Task:   beads-abc123     "Implement user authentication"    │
│ Model:  claude-sonnet-4                                     │
├─────────────────────────────────────────────────────────────┤
│ BUDGET                                                      │
│ Tokens: ████████████░░░░░░░░ 450,000 / 1,000,000 (45%)     │
│ Tasks:  ████░░░░░░░░░░░░░░░░ 4 / 20 complete               │
├─────────────────────────────────────────────────────────────┤
│ RECENT ACTIVITY                                             │
│ 14:32:01  Task beads-xyz started                           │
│ 14:35:22  Task beads-xyz completed (42,300 tokens)         │
│ 14:35:24  Committed: feat(beads-xyz): Add login form       │
│ 14:35:26  Task beads-abc123 started                        │
├─────────────────────────────────────────────────────────────┤
│ RATE LIMITS                                                 │
│ API calls this hour: 23/100                                │
│ Next reset: 47:32                                          │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Notes

### tmux Session Structure

```bash
# Create session with named windows
tmux new-session -d -s "cub-${session_id}" -n main

# Split for dashboard
tmux split-window -h -p 35 -t "cub-${session_id}:main"

# Main pane (left): harness execution
# Dashboard pane (right): status updates
```

### Dashboard Update Mechanism

Options:
1. **File-based polling**: Dashboard reads from status file updated by main loop
2. **FIFO pipe**: Main loop writes to named pipe, dashboard reads
3. **Shared memory**: More complex but lower latency

Recommended: File-based polling with 1-second refresh interval.

Status file location: `.cub/runs/${session_id}/status.json`

```json
{
  "status": "running",
  "iteration": 7,
  "max_iterations": 50,
  "current_task": {
    "id": "beads-abc123",
    "title": "Implement user authentication",
    "started_at": "2026-01-13T14:35:26Z"
  },
  "budget": {
    "used": 450000,
    "limit": 1000000
  },
  "tasks": {
    "total": 20,
    "completed": 4,
    "in_progress": 1
  },
  "rate_limit": {
    "calls_this_hour": 23,
    "limit": 100,
    "reset_at": "2026-01-13T15:00:00Z"
  },
  "recent_events": [...]
}
```

### New Files

- `lib/dashboard.sh` - Dashboard rendering and update logic
- `lib/cmd_monitor.sh` - Monitor subcommand
- Dashboard status writer integrated into `lib/loop.sh`

### Configuration

```json
{
  "dashboard": {
    "enabled": true,
    "refresh_interval": 1000,
    "layout": "vertical",
    "pane_size": 35
  }
}
```

## Acceptance Criteria

- [ ] `cub run --monitor` launches tmux with dashboard
- [ ] Dashboard updates in real-time (1s refresh)
- [ ] Shows current task, iteration count, budget usage
- [ ] Shows recent activity log (last 10 events)
- [ ] `cub monitor` can attach to existing session
- [ ] Graceful fallback if tmux not available
- [ ] Dashboard survives task transitions
- [ ] Clean exit when run completes

## Future Enhancements

- Web-based dashboard alternative (for remote monitoring)
- Notification integration (desktop, Slack, etc.)
- Historical session replay
- Multi-session overview
