## Context
Warn users when approaching budget limit so they can decide to stop.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 15m
**Approach:** Check if usage > warn_at threshold, log warning once.

## Implementation Steps
1. Add budget_check_warning() function
2. Read warn_at from config (default 80% of budget)
3. Track if warning already shown (_BUDGET_WARNED)
4. Log warning when threshold crossed
5. Call after budget_record in main loop

## Acceptance Criteria
- [ ] Warning shown when crossing 80% threshold
- [ ] Warning only shown once per run
- [ ] Threshold configurable in config

## Files Likely Involved
- lib/budget.sh
- curb (main script)
