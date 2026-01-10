## Context
Hooks live in multiple directories (global and project). Need to find and merge them.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 20m
**Approach:** Scan both global and project hook dirs, collect executable files.

## Implementation Steps
1. Add hooks_find(hook_name) - returns list of scripts to run
2. Check ~/.config/curb/hooks/{hook_name}.d/
3. Check .curb/hooks/{hook_name}.d/
4. Filter to executable files only
5. Sort by filename for ordering

## Acceptance Criteria
- [ ] Finds hooks in global directory
- [ ] Finds hooks in project directory
- [ ] Merges both (global runs first)
- [ ] Only returns executable files

## Files Likely Involved
- lib/hooks.sh
