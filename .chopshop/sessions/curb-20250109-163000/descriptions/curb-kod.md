## Context
Different harnesses have different capabilities. Need to detect and adapt.

## Implementation Hints

**Recommended Model:** opus-4.5
**Estimated Duration:** 30m
**Approach:** Create capability interface that each harness implements.

## Implementation Steps
1. Define capabilities: streaming, token_reporting, system_prompt, auto_mode
2. Add harness_supports(capability) function
3. Implement for each harness based on spike findings
4. Use in main loop to adapt behavior
5. Log capabilities at startup in debug mode

## Acceptance Criteria
- [ ] Can query if harness supports streaming
- [ ] Can query if harness reports tokens
- [ ] Main loop adapts to capabilities
- [ ] Degraded mode works when capability missing

## Files Likely Involved
- lib/harness.sh

## Notes
This is a design task requiring careful consideration of the abstraction.
Example: if harness doesn't report tokens, estimate from model pricing.
