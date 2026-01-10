## Context
--help should show all new flags and features.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 15m
**Approach:** Update usage() function with new flags.

## Implementation Steps
1. Add --budget to help
2. Add --require-clean to help
3. Group flags by category (Core, Reliability, Debug)
4. Add examples section

## Acceptance Criteria
- [ ] All new flags in --help
- [ ] Grouped logically
- [ ] Examples helpful

## Files Likely Involved
- curb
