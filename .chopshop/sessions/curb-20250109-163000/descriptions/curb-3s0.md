## Context
Add Gemini as a supported harness based on spike findings.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Follow pattern from claude/codex implementations in harness.sh.

## Implementation Steps
1. Add gemini_invoke() function
2. Add gemini_invoke_streaming() if supported
3. Handle system prompt passing
4. Add to harness_detect() priority list
5. Update harness_available() check

## Acceptance Criteria
- [ ] curb --harness gemini works
- [ ] System and task prompts passed correctly
- [ ] Streaming mode if available
- [ ] Falls back gracefully if not installed

## Files Likely Involved
- lib/harness.sh
