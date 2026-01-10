## Context
Each task run should log start/end with rich metadata for debugging and analysis.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** Wrapper functions that capture timing and call logger_write with structured data.

## Implementation Steps
1. Add log_task_start(task_id, task_title, harness)
2. Add log_task_end(task_id, exit_code, duration_sec, tokens_used)
3. Add log_error(message, context)
4. Capture git SHA at task end for traceability
5. Store start time in variable for duration calculation

## Acceptance Criteria
- [ ] task_start event logged with task_id, title, harness
- [ ] task_end event logged with duration, exit_code, tokens, git_sha
- [ ] Errors logged with context

## Files Likely Involved
- lib/logger.sh

## Notes
Use $SECONDS bash variable for simple duration tracking
