## Context
Config needs to merge from multiple sources with clear precedence.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Use jq to merge objects. Load global first, overlay project config.

## Implementation Steps
1. In config_load(), check for ~/.config/curb/config.json
2. Check for .curb/config.json in project
3. Merge with jq: global then project (project wins)
4. Also check env vars (CURB_*) and apply as overrides
5. Store merged result in _CONFIG_CACHE

## Acceptance Criteria
- [ ] Global config alone works
- [ ] Project config overrides global values
- [ ] Missing config files handled gracefully (empty default)
- [ ] CURB_BUDGET env var overrides config budget

## Files Likely Involved
- lib/config.sh

## Notes
Precedence: CLI flags > env vars > project config > global config
