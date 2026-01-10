## Context
Verify all pieces work together before release.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Create a test project with multiple tasks, run with budget, verify all features.

## Implementation Steps
1. Create tests/e2e/ directory
2. Set up test project with 3-5 simple tasks
3. Add hooks that log to file
4. Run curb with --budget 100000
5. Verify: logs created, hooks ran, budget stopped loop

## Acceptance Criteria
- [ ] Full loop runs to completion or budget
- [ ] All hooks fire at right times
- [ ] Logs contain all expected events
- [ ] Clean state enforced
- [ ] Can be run in CI

## Files Likely Involved
- tests/e2e/run.sh (new)
- tests/e2e/project/ (test fixtures)
