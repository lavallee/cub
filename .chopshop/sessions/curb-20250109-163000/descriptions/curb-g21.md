## Context
Optionally require tests to pass before considering a task complete.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Detect test runner from project (package.json scripts, Makefile, etc). Run if configured.

## Implementation Steps
1. Add state_run_tests() to state.sh
2. Detect test command: npm test, make test, pytest, etc.
3. Read clean_state.require_tests from config
4. Run tests if enabled, capture exit code
5. Return failure if tests fail

## Acceptance Criteria
- [ ] Detects test command for npm/yarn/make/pytest projects
- [ ] Only runs if require_tests is true
- [ ] Test failures logged clearly
- [ ] Test output captured in logs

## Files Likely Involved
- lib/state.sh
