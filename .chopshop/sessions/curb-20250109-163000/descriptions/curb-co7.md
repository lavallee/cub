## Context
After each task, verify the harness left the repo in a clean state (committed its changes).

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Use git status/diff to check for uncommitted changes. Configurable behavior (warn vs fail).

## Implementation Steps
1. Create lib/state.sh
2. Add state_is_clean() - returns 0 if no uncommitted changes
3. Add state_ensure_clean() - checks and acts based on config
4. Read require_commit from config
5. Log warning or error appropriately

## Acceptance Criteria
- [ ] Detects uncommitted changes after harness run
- [ ] Respects clean_state.require_commit config
- [ ] Clear error message pointing to uncommitted files

## Files Likely Involved
- lib/state.sh (new)
- lib/config.sh (for reading settings)

## Notes
git diff --quiet HEAD returns 0 if clean, 1 if changes
