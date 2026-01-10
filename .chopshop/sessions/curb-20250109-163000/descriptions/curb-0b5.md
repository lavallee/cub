## Context
The main loop needs to call logging functions at the right points.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** Add logger_init at startup, wrap task execution with log_task_start/end.

## Implementation Steps
1. Source lib/logger.sh in curb
2. Call logger_init with project name and session ID
3. Before harness_invoke: call log_task_start
4. After harness_invoke: call log_task_end with results
5. On errors: call log_error

## Acceptance Criteria
- [ ] Running curb creates log file
- [ ] Each task iteration produces start/end log entries
- [ ] Log includes harness, task_id, duration

## Files Likely Involved
- curb (main script)
- lib/logger.sh
