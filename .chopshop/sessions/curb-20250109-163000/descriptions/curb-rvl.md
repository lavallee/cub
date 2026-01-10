## Context
Main loop needs to stop when budget is exceeded.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** After each task, record usage and check budget. Exit gracefully if over.

## Implementation Steps
1. After harness completes, get token usage
2. Call budget_record with usage
3. Call budget_check - if returns 1, exit loop
4. Log budget status in task_end event
5. Final message showing total tokens used

## Acceptance Criteria
- [ ] Loop stops when budget exceeded
- [ ] Clear message: "Budget exceeded (used X of Y tokens)"
- [ ] Remaining budget logged after each task
- [ ] Graceful exit (not error code)

## Files Likely Involved
- curb (main script)
- lib/budget.sh
- lib/logger.sh

## Notes
Exit with 0 (success) when stopping for budget - it's expected behavior
