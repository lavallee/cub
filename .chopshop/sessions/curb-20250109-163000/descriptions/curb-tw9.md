## Context
Users should be able to configure which harness to prefer.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 15m
**Approach:** Read priority array from config, update harness_detect to respect it.

## Implementation Steps
1. Read harness.priority from config
2. Update harness_detect() to check in priority order
3. Document configuration in README
4. Add example to default config

## Acceptance Criteria
- [ ] Config priority respected: ["gemini", "claude", "codex", "opencode"]
- [ ] Falls through list until one is available
- [ ] Documented in config schema

## Files Likely Involved
- lib/harness.sh
- lib/config.sh

## Notes
Default priority: claude, gemini, codex, opencode
