## Pause for Validation

Phase 1 is complete. Before proceeding to reliability features, validate:

## What's Ready
- Global config at ~/.config/curb/config.json
- Project config at .curb/config.json
- Structured JSONL logs after each run
- curb init --global onboarding

## Suggested Testing
- [ ] Run curb init --global and verify config created
- [ ] Create a project config that overrides a global setting
- [ ] Run curb on a test project and check logs created
- [ ] Query logs with jq: jq 'select(.event=="task_end")' logs/*.jsonl

## Questions for Feedback
- Is the config schema intuitive?
- Are the logs capturing the right metadata?
- Any settings that should be configurable but aren't?

## Next Steps
If approved, proceed to Phase 2: Reliability (clean state, budget tracking)
