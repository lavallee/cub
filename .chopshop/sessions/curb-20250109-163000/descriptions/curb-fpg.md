## Context
Token tracking needs to work across all harnesses for budget enforcement.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Implement harness-specific token extraction based on spike findings.

## Implementation Steps
1. Add gemini_get_usage() based on Gemini output format
2. Add opencode_get_usage() based on OpenCode output format
3. Update harness_get_usage() to delegate appropriately
4. Handle missing data gracefully (estimate or return 0)
5. Test with actual runs

## Acceptance Criteria
- [ ] Token counts available from Gemini runs
- [ ] Token counts available from OpenCode runs
- [ ] Estimation fallback works
- [ ] Budget tracking accurate across harnesses

## Files Likely Involved
- lib/harness.sh
- lib/budget.sh
