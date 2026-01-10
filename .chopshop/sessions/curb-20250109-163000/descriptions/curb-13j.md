## Context
The main curb script needs to load config at startup and use it for settings.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** Source config.sh early, call config_load, replace hardcoded defaults with config_get_or calls.

## Implementation Steps
1. Source lib/config.sh after lib/xdg.sh
2. Call config_load in initialization
3. Replace HARNESS default with config_get_or "harness.default" "auto"
4. Replace MAX_ITERATIONS with config value
5. Pass through to other libs as needed

## Acceptance Criteria
- [ ] curb respects config file harness priority
- [ ] curb respects config file max_iterations
- [ ] CLI flags still override config values

## Files Likely Involved
- curb (main script)
- lib/config.sh
