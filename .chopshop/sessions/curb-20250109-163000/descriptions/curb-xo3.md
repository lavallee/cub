## Context
Hooks allow users to extend curb behavior without modifying core code.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Hook points are directories containing executable scripts. Run all scripts in order.

## Implementation Steps
1. Create lib/hooks.sh
2. Add hooks_run(hook_name) - runs all scripts in hook_name.d/
3. Export context variables before running
4. Capture output and exit codes
5. Log hook execution results

## Acceptance Criteria
- [ ] hooks_run "pre-task" executes scripts in pre-task.d/
- [ ] Scripts receive context via environment vars
- [ ] Hook failure logged but doesn't stop loop (configurable)
- [ ] Scripts run in sorted order (01-first.sh before 02-second.sh)

## Files Likely Involved
- lib/hooks.sh (new)

## Notes
Pattern: ~/.config/curb/hooks/pre-task.d/*.sh and .curb/hooks/pre-task.d/*.sh
