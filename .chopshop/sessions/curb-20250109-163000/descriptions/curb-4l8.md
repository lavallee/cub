## Context
Track cumulative token usage across loop iterations to enforce spending limits.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Simple counter stored in variable. Functions to init, record, check.

## Implementation Steps
1. Create lib/budget.sh
2. Add _BUDGET_LIMIT and _BUDGET_USED variables
3. Add budget_init(limit) - sets the budget for this run
4. Add budget_record(tokens) - adds to cumulative usage
5. Add budget_check() - returns 1 if over budget
6. Add budget_remaining() - echoes remaining tokens

## Acceptance Criteria
- [ ] budget_init sets limit correctly
- [ ] budget_record accumulates usage
- [ ] budget_check returns 1 when over
- [ ] budget_remaining shows correct value

## Files Likely Involved
- lib/budget.sh (new)
