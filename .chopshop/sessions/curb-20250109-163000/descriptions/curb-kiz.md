## Context
New users need an easy way to set up global curb config and verify dependencies.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Interactive prompts that create config file. Check for jq, harnesses.

## Implementation Steps
1. Add --global flag handling to curb-init
2. Check dependencies (jq, at least one harness)
3. Create ~/.config/curb/ directory structure
4. Generate config.json with sensible defaults
5. Create hooks directories
6. Print success message with next steps

## Acceptance Criteria
- [ ] curb init --global creates ~/.config/curb/config.json
- [ ] Missing dependencies are reported clearly
- [ ] Config has sensible defaults for budget, harness priority
- [ ] Hook directories created

## Files Likely Involved
- curb-init
