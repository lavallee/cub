## Context
The main loop needs to call state checks after each harness invocation.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** After harness returns, call state_ensure_clean. If fails, handle based on config.

## Implementation Steps
1. Source lib/state.sh in curb
2. After harness_invoke completes, call state_ensure_clean
3. If returns non-zero, log error and decide: continue or abort
4. Add --require-clean flag override

## Acceptance Criteria
- [ ] Uncommitted changes detected after harness run
- [ ] Loop aborts if require_commit and changes exist
- [ ] Tests run if configured
- [ ] Behavior overridable with CLI flag

## Files Likely Involved
- curb (main script)
- lib/state.sh
