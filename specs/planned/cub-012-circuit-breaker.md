---
status: planned
priority: high
complexity: medium
dependencies: []
created: 2026-01-10
updated: 2026-01-19
readiness:
  score: 8
  blockers: []
  questions:
  - What thresholds should trigger circuit breaker?
  - How to detect "test-only" loops vs real progress?
  decisions_needed:
  - Choose stagnation metrics (file changes, test pass rate, etc)
  - Define recovery actions (prompt adjustment, context reset, abort)
  tools_needed:
  - Design Pattern Matcher (find proven circuit breaker patterns)
  - Technical Feasibility Checker (verify metrics tracking approach)
  - Test Coverage Planner (how to test stagnation detection logic)
notes: |
  Ready to implement. Clear pattern from Ralph.
  Main questions are tuning thresholds and defining recovery actions.
source: ralph, ralph-claude-code
spec_id: cub-012
---
# Circuit Breaker / Stagnation Detection

**Source:** [ralph-claude-code](https://github.com/frankbria/ralph-claude-code), [ralph](https://github.com/iannuttall/ralph)
**Dependencies:** None
**Complexity:** Medium

## Overview

Detect when the autonomous loop is stuck without making meaningful progress and take corrective action.

## Reference Implementation

From Ralph's README:
> "Circuit breaker pattern detecting stagnation after 3 loops without progress"

Ralph tracks:
- Completion indicators
- File changes per iteration
- Test-only loops (>30% threshold triggers concern)
- Consecutive "done" signals without actual completion

## Additional Reference: Stale Task Recovery

From Ralph's implementation:
- Tasks marked `in_progress` track a `startedAt` timestamp
- Configurable `STALE_SECONDS` parameter (default: disabled)
- If a task has been `in_progress` longer than the threshold, it's considered "stale"
- Stale tasks are automatically reopened for retry
- Prevents orphaned tasks when processes die unexpectedly

This pattern is valuable for:
- Long-running autonomous sessions
- Process crashes or interruptions
- Multi-machine setups where one worker dies
- CI/CD pipelines with timeouts

**Integration with beads:** The `bd ready` command could surface stale `in_progress` tasks alongside truly ready tasks, allowing automatic recovery.

---

## Problem Statement

Current cub failure modes:
1. AI claims completion but work isn't done
2. AI keeps iterating without making changes
3. AI is stuck in a loop fixing the same error repeatedly
4. AI makes changes but they don't compile/pass tests

Without stagnation detection, cub burns budget on unproductive iterations.

## Proposed Interface

```bash
# Configure stagnation threshold
cub run --stagnation-threshold 3

# Configure action on stagnation
cub run --on-stagnation pause|alert|abort|escalate
```

## Detection Signals

### 1. No File Changes
```bash
# After each iteration, check git diff
if git diff --quiet HEAD~1; then
  no_change_count=$((no_change_count + 1))
fi
```

### 2. Same Error Repeated
Track error signatures across iterations:
```json
{
  "error_history": [
    {"iteration": 5, "signature": "TypeError: undefined is not a function", "file": "src/auth.js:42"},
    {"iteration": 6, "signature": "TypeError: undefined is not a function", "file": "src/auth.js:42"},
    {"iteration": 7, "signature": "TypeError: undefined is not a function", "file": "src/auth.js:42"}
  ]
}
```

### 3. Task Not Progressing
Same task in_progress for N iterations without completion.

### 4. Completion Claims Without Evidence
AI outputs completion signals but:
- Tests still failing
- Required files missing
- Acceptance criteria unmet

## Circuit Breaker States

```
CLOSED (normal) ──[threshold exceeded]──> OPEN (tripped)
      ^                                        │
      │                                        │
      └────────[reset/intervention]────────────┘
```

### State Machine

```bash
# States
CB_CLOSED=0      # Normal operation
CB_OPEN=1        # Stagnation detected, action required
CB_HALF_OPEN=2   # Testing if issue resolved

# Transitions
cb_check_stagnation() {
  local no_progress_count=$1
  local threshold=${CUB_STAGNATION_THRESHOLD:-3}

  if [[ $no_progress_count -ge $threshold ]]; then
    cb_trip "No progress for $no_progress_count iterations"
  fi
}

cb_trip() {
  local reason=$1
  CB_STATE=$CB_OPEN
  log_event "circuit_breaker_open" "reason=$reason"

  case "${CUB_ON_STAGNATION:-pause}" in
    pause)    cb_pause ;;
    alert)    cb_alert ;;
    abort)    cb_abort ;;
    escalate) cb_escalate ;;
  esac
}
```

## Actions on Stagnation

### pause
Pause execution, wait for user input:
```
[STAGNATION DETECTED] No progress for 3 iterations
Task: beads-abc123 "Implement authentication"
Last error: TypeError in src/auth.js:42

Options:
  [c] Continue (reset counter)
  [s] Skip task (mark as blocked)
  [a] Abort run
  [r] Retry with different model
  [h] Get help (show context)

Choice:
```

### alert
Send notification but continue:
- Desktop notification
- Log warning
- Optional webhook (Slack, Discord, etc.)

### abort
Stop the run gracefully:
- Mark current task as blocked
- Save state for resume
- Exit with specific code

### escalate
Attempt automatic recovery:
1. Switch to more capable model (haiku -> sonnet -> opus)
2. Add failure context to next prompt
3. If still stuck after escalation, pause

## Configuration

```json
{
  "stagnation": {
    "threshold": 3,
    "action": "pause",
    "signals": {
      "no_file_changes": true,
      "repeated_errors": true,
      "task_timeout_iterations": 5,
      "completion_without_evidence": true
    },
    "escalation": {
      "enabled": true,
      "model_progression": ["haiku", "sonnet", "opus"]
    },
    "notifications": {
      "desktop": true,
      "webhook": null
    },
    "stale_task_recovery": {
      "enabled": true,
      "stale_seconds": 3600,
      "action": "reopen"
    }
  }
}
```

## Progress Tracking

New artifact per iteration:
```
.cub/runs/{session}/iterations/{n}/
├── changes.patch      # git diff from this iteration
├── errors.json        # errors detected
├── metrics.json       # tokens, time, etc.
└── completion_signals.json
```

## Implementation Notes

### Integration Points

1. **lib/loop.sh**: Add progress tracking after each iteration
2. **lib/harness.sh**: Extract error signatures from output
3. **New lib/circuit_breaker.sh**: State machine and actions
4. **lib/logging.sh**: New event types for circuit breaker

### Error Signature Extraction

```bash
extract_error_signature() {
  local output=$1
  # Look for common error patterns
  # Return normalized signature for comparison

  echo "$output" | grep -E "(Error|Exception|Failed|FAIL):" | head -1 | \
    sed 's/at line [0-9]*/at line N/' | \
    sed 's/:[0-9]*:/:N:/'
}
```

## Acceptance Criteria

### Stagnation Detection
- [ ] Track file changes per iteration
- [ ] Detect repeated identical errors
- [ ] Configurable stagnation threshold
- [ ] Support pause/alert/abort/escalate actions
- [ ] Log circuit breaker state changes
- [ ] Resume capability after pause
- [ ] Model escalation on stagnation (optional)
- [ ] Desktop/webhook notifications (optional)

### Stale Task Recovery
- [ ] Track `started_at` timestamp on `in_progress` tasks
- [ ] Configurable `stale_seconds` threshold
- [ ] `bd ready` surfaces stale tasks as available
- [ ] `cub doctor` warns about stale tasks
- [ ] Optional auto-reopen of stale tasks

## Future Enhancements

- ML-based stagnation prediction
- Automatic prompt adjustment on stagnation
- Historical stagnation pattern analysis
- Integration with task difficulty estimation
