## Context
Users need to set a token budget for the current run via CLI.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 15m
**Approach:** Add flag parsing in getopts section, pass to budget_init.

## Implementation Steps
1. Add --budget to getopts parsing
2. Store value in BUDGET variable
3. Call budget_init with value (or config default)
4. Add to --help output

## Acceptance Criteria
- [ ] curb --budget 1000000 sets budget
- [ ] Default from config if no flag
- [ ] Shows in --help

## Files Likely Involved
- curb (main script)
