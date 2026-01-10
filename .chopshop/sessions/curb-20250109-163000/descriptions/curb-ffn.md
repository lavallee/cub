## Context
Integrate hooks at 5 lifecycle points in the main curb loop.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Call hooks_run at each point with appropriate context variables exported.

## Implementation Steps
1. Add pre-loop hook (before first iteration)
2. Add pre-task hook (before harness_invoke)
3. Add post-task hook (after harness completes)
4. Add on-error hook (when harness fails)
5. Add post-loop hook (after all tasks done)
6. Export TASK_ID, HARNESS, EXIT_CODE etc for each

## Acceptance Criteria
- [ ] All 5 hook points fire at correct times
- [ ] Context variables available to scripts
- [ ] on-error only fires on actual errors
- [ ] Hooks can be disabled via config

## Files Likely Involved
- curb (main script)
- lib/hooks.sh

## Notes
Context vars: PROJECT_DIR, TASK_ID, TASK_TITLE, HARNESS, EXIT_CODE, DURATION
