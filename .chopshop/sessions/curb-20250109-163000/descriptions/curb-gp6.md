## Context
Example hooks help users understand the pattern and get started quickly.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 30m
**Approach:** Create simple, well-commented example scripts.

## Implementation Steps
1. Create examples/hooks/ directory
2. Add post-task/slack-notify.sh - posts to webhook
3. Add post-loop/datadog-metric.sh - sends completion metric
4. Add on-error/pagerduty-alert.sh - alerts on failure
5. Document in each script how to install

## Acceptance Criteria
- [ ] 3+ example hooks created
- [ ] Each well-commented with usage instructions
- [ ] Demonstrates accessing context variables
- [ ] Documented in README

## Files Likely Involved
- examples/hooks/post-task/slack-notify.sh (new)
- examples/hooks/post-loop/datadog-metric.sh (new)
- examples/hooks/on-error/pagerduty-alert.sh (new)
