## Context
Need to get actual token counts from Claude Code to track budget accurately.

## Implementation Hints

**Recommended Model:** opus-4.5
**Estimated Duration:** 45m
**Approach:** Claude's stream-json output includes usage info. Parse from result event.

## Implementation Steps
1. Examine Claude Code's stream-json output for token fields
2. In claude_invoke_streaming, capture and return token usage
3. Add harness_get_usage() interface that returns tokens
4. Handle case where usage not available (estimate)
5. For non-streaming mode, check if --json output has usage

## Acceptance Criteria
- [ ] Token count extracted from Claude streaming output
- [ ] Returned in structured format (input_tokens, output_tokens)
- [ ] Fallback to estimate if not available
- [ ] Works with both streaming and non-streaming modes

## Files Likely Involved
- lib/harness.sh

## Notes
Claude Code result event has cost_usd - may need to calculate tokens from cost.
This is a complex task requiring careful parsing of streaming JSON output.
