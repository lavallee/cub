## Context
Need a simple interface to read config values with dot-notation keys.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Use jq for JSON parsing. Cache loaded config in a variable to avoid re-reading.

## Implementation Steps
1. Create lib/config.sh
2. Add _CONFIG_CACHE variable for loaded config
3. Add config_load() - reads and merges config files
4. Add config_get(key) - uses jq to extract value by dot-path
5. Add config_get_or(key, default) - with fallback

## Acceptance Criteria
- [ ] config_get "harness.priority" returns array
- [ ] config_get "budget.default" returns number
- [ ] config_get "nonexistent" returns empty
- [ ] config_get_or "nonexistent" "fallback" returns "fallback"

## Files Likely Involved
- lib/config.sh (new)
