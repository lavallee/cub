#!/bin/bash
# Update all curb tasks with full descriptions
set -e

DESC_DIR="/Users/lavallee/tools/curb/.chopshop/sessions/curb-20250109-163000/descriptions"
mkdir -p "$DESC_DIR"

update_task() {
    local id="$1"
    local file="$DESC_DIR/$id.md"
    if [[ -f "$file" ]]; then
        bd update "$id" --body-file "$file" 2>/dev/null && echo "Updated: $id" || echo "Failed: $id"
    else
        echo "No description file for: $id"
    fi
}

# Phase 1: Foundation

cat > "$DESC_DIR/curb-1l6.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-0u2.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-et7.md" << 'EOF'
## Context
Structured logs enable post-run analysis and debugging. JSONL is grep-friendly and jq-queryable.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Simple functions that build JSON and append to log file. Use jq -n for safe JSON construction.

## Implementation Steps
1. Create lib/logger.sh
2. Add _LOG_FILE variable (set during init)
3. Add logger_init(project_name, session_id) - sets up log file path
4. Add logger_write(event_type, data_json) - appends JSONL line
5. Ensure log directory exists before writing

## Acceptance Criteria
- [ ] Log file created at ~/.local/share/curb/logs/{project}/{session}.jsonl
- [ ] Each line is valid JSON
- [ ] Timestamps in ISO 8601 format
- [ ] Log file is append-only

## Files Likely Involved
- lib/logger.sh (new)
- lib/xdg.sh (for directory helpers)
EOF

cat > "$DESC_DIR/curb-ohp.md" << 'EOF'
## Context
Each task run should log start/end with rich metadata for debugging and analysis.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** Wrapper functions that capture timing and call logger_write with structured data.

## Implementation Steps
1. Add log_task_start(task_id, task_title, harness)
2. Add log_task_end(task_id, exit_code, duration_sec, tokens_used)
3. Add log_error(message, context)
4. Capture git SHA at task end for traceability
5. Store start time in variable for duration calculation

## Acceptance Criteria
- [ ] task_start event logged with task_id, title, harness
- [ ] task_end event logged with duration, exit_code, tokens, git_sha
- [ ] Errors logged with context

## Files Likely Involved
- lib/logger.sh

## Notes
Use $SECONDS bash variable for simple duration tracking
EOF

cat > "$DESC_DIR/curb-13j.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-0b5.md" << 'EOF'
## Context
The main loop needs to call logging functions at the right points.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** Add logger_init at startup, wrap task execution with log_task_start/end.

## Implementation Steps
1. Source lib/logger.sh in curb
2. Call logger_init with project name and session ID
3. Before harness_invoke: call log_task_start
4. After harness_invoke: call log_task_end with results
5. On errors: call log_error

## Acceptance Criteria
- [ ] Running curb creates log file
- [ ] Each task iteration produces start/end log entries
- [ ] Log includes harness, task_id, duration

## Files Likely Involved
- curb (main script)
- lib/logger.sh
EOF

cat > "$DESC_DIR/curb-kiz.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-hp9.md" << 'EOF'
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
EOF

# Phase 2: Reliability

cat > "$DESC_DIR/curb-co7.md" << 'EOF'
## Context
After each task, verify the harness left the repo in a clean state (committed its changes).

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Use git status/diff to check for uncommitted changes. Configurable behavior (warn vs fail).

## Implementation Steps
1. Create lib/state.sh
2. Add state_is_clean() - returns 0 if no uncommitted changes
3. Add state_ensure_clean() - checks and acts based on config
4. Read require_commit from config
5. Log warning or error appropriately

## Acceptance Criteria
- [ ] Detects uncommitted changes after harness run
- [ ] Respects clean_state.require_commit config
- [ ] Clear error message pointing to uncommitted files

## Files Likely Involved
- lib/state.sh (new)
- lib/config.sh (for reading settings)

## Notes
git diff --quiet HEAD returns 0 if clean, 1 if changes
EOF

cat > "$DESC_DIR/curb-g21.md" << 'EOF'
## Context
Optionally require tests to pass before considering a task complete.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Detect test runner from project (package.json scripts, Makefile, etc). Run if configured.

## Implementation Steps
1. Add state_run_tests() to state.sh
2. Detect test command: npm test, make test, pytest, etc.
3. Read clean_state.require_tests from config
4. Run tests if enabled, capture exit code
5. Return failure if tests fail

## Acceptance Criteria
- [ ] Detects test command for npm/yarn/make/pytest projects
- [ ] Only runs if require_tests is true
- [ ] Test failures logged clearly
- [ ] Test output captured in logs

## Files Likely Involved
- lib/state.sh
EOF

cat > "$DESC_DIR/curb-vdw.md" << 'EOF'
## Context
The main loop needs to call state checks after each harness invocation.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** After harness returns, call state_ensure_clean. If fails, handle based on config.

## Implementation Steps
1. Source lib/state.sh in curb
2. After harness_invoke completes, call state_ensure_clean
3. If returns non-zero, log error and decide: continue or abort
4. Add --require-clean flag override

## Acceptance Criteria
- [ ] Uncommitted changes detected after harness run
- [ ] Loop aborts if require_commit and changes exist
- [ ] Tests run if configured
- [ ] Behavior overridable with CLI flag

## Files Likely Involved
- curb (main script)
- lib/state.sh
EOF

cat > "$DESC_DIR/curb-4l8.md" << 'EOF'
## Context
Track cumulative token usage across loop iterations to enforce spending limits.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Simple counter stored in variable. Functions to init, record, check.

## Implementation Steps
1. Create lib/budget.sh
2. Add _BUDGET_LIMIT and _BUDGET_USED variables
3. Add budget_init(limit) - sets the budget for this run
4. Add budget_record(tokens) - adds to cumulative usage
5. Add budget_check() - returns 1 if over budget
6. Add budget_remaining() - echoes remaining tokens

## Acceptance Criteria
- [ ] budget_init sets limit correctly
- [ ] budget_record accumulates usage
- [ ] budget_check returns 1 when over
- [ ] budget_remaining shows correct value

## Files Likely Involved
- lib/budget.sh (new)
EOF

cat > "$DESC_DIR/curb-0ub.md" << 'EOF'
## Context
Users need to set a token budget for the current run via CLI.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 15m
**Approach:** Add flag parsing in getopts section, pass to budget_init.

## Implementation Steps
1. Add --budget to getopts parsing
2. Store value in BUDGET variable
3. Call budget_init with value (or config default)
4. Add to --help output

## Acceptance Criteria
- [ ] curb --budget 1000000 sets budget
- [ ] Default from config if no flag
- [ ] Shows in --help

## Files Likely Involved
- curb (main script)
EOF

cat > "$DESC_DIR/curb-0hz.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-rvl.md" << 'EOF'
## Context
Main loop needs to stop when budget is exceeded.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 20m
**Approach:** After each task, record usage and check budget. Exit gracefully if over.

## Implementation Steps
1. After harness completes, get token usage
2. Call budget_record with usage
3. Call budget_check - if returns 1, exit loop
4. Log budget status in task_end event
5. Final message showing total tokens used

## Acceptance Criteria
- [ ] Loop stops when budget exceeded
- [ ] Clear message: "Budget exceeded (used X of Y tokens)"
- [ ] Remaining budget logged after each task
- [ ] Graceful exit (not error code)

## Files Likely Involved
- curb (main script)
- lib/budget.sh
- lib/logger.sh

## Notes
Exit with 0 (success) when stopping for budget - it's expected behavior
EOF

cat > "$DESC_DIR/curb-iji.md" << 'EOF'
## Context
Warn users when approaching budget limit so they can decide to stop.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 15m
**Approach:** Check if usage > warn_at threshold, log warning once.

## Implementation Steps
1. Add budget_check_warning() function
2. Read warn_at from config (default 80% of budget)
3. Track if warning already shown (_BUDGET_WARNED)
4. Log warning when threshold crossed
5. Call after budget_record in main loop

## Acceptance Criteria
- [ ] Warning shown when crossing 80% threshold
- [ ] Warning only shown once per run
- [ ] Threshold configurable in config

## Files Likely Involved
- lib/budget.sh
- curb (main script)
EOF

cat > "$DESC_DIR/curb-fxr.md" << 'EOF'
## Pause for Validation

Phase 2 is complete. Curb can now run unattended with confidence.

## What's Ready
- Clean state enforcement (uncommitted changes detected)
- Optional test requirement
- Token budget tracking
- Budget enforcement (stops at limit)
- Budget warnings (at 80%)

## Suggested Testing
- [ ] Run curb on a project, verify it commits changes
- [ ] Configure require_tests=true, verify tests run
- [ ] Set small --budget, verify it stops when exceeded
- [ ] Check logs show token usage per task

## Questions for Feedback
- Is the clean state check too strict or not strict enough?
- Is token counting accurate enough for your needs?
- Should budget be enforceable per-task as well as per-run?

## Key Milestone
After this checkpoint, curb is reliable enough for overnight runs!

## Next Steps
If approved, proceed to Phase 3: Extensibility (hooks, new harnesses)
EOF

# Phase 3: Extensibility

cat > "$DESC_DIR/curb-xo3.md" << 'EOF'
## Context
Hooks allow users to extend curb behavior without modifying core code.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Hook points are directories containing executable scripts. Run all scripts in order.

## Implementation Steps
1. Create lib/hooks.sh
2. Add hooks_run(hook_name) - runs all scripts in hook_name.d/
3. Export context variables before running
4. Capture output and exit codes
5. Log hook execution results

## Acceptance Criteria
- [ ] hooks_run "pre-task" executes scripts in pre-task.d/
- [ ] Scripts receive context via environment vars
- [ ] Hook failure logged but doesn't stop loop (configurable)
- [ ] Scripts run in sorted order (01-first.sh before 02-second.sh)

## Files Likely Involved
- lib/hooks.sh (new)

## Notes
Pattern: ~/.config/curb/hooks/pre-task.d/*.sh and .curb/hooks/pre-task.d/*.sh
EOF

cat > "$DESC_DIR/curb-zrg.md" << 'EOF'
## Context
Hooks live in multiple directories (global and project). Need to find and merge them.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 20m
**Approach:** Scan both global and project hook dirs, collect executable files.

## Implementation Steps
1. Add hooks_find(hook_name) - returns list of scripts to run
2. Check ~/.config/curb/hooks/{hook_name}.d/
3. Check .curb/hooks/{hook_name}.d/
4. Filter to executable files only
5. Sort by filename for ordering

## Acceptance Criteria
- [ ] Finds hooks in global directory
- [ ] Finds hooks in project directory
- [ ] Merges both (global runs first)
- [ ] Only returns executable files

## Files Likely Involved
- lib/hooks.sh
EOF

cat > "$DESC_DIR/curb-ffn.md" << 'EOF'
## Context
Integrate hooks at 5 lifecycle points in the main curb loop.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Call hooks_run at each point with appropriate context variables exported.

## Implementation Steps
1. Add pre-loop hook (before first iteration)
2. Add pre-task hook (before harness_invoke)
3. Add post-task hook (after harness completes)
4. Add on-error hook (when harness fails)
5. Add post-loop hook (after all tasks done)
6. Export TASK_ID, HARNESS, EXIT_CODE etc for each

## Acceptance Criteria
- [ ] All 5 hook points fire at correct times
- [ ] Context variables available to scripts
- [ ] on-error only fires on actual errors
- [ ] Hooks can be disabled via config

## Files Likely Involved
- curb (main script)
- lib/hooks.sh

## Notes
Context vars: PROJECT_DIR, TASK_ID, TASK_TITLE, HARNESS, EXIT_CODE, DURATION
EOF

cat > "$DESC_DIR/curb-4wz.md" << 'EOF'
## Context
Need to understand Gemini CLI before implementing harness.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Install Gemini CLI, test invocation patterns, document findings.

## Implementation Steps
1. Research Gemini CLI installation (likely gcloud or standalone)
2. Test basic invocation with prompt
3. Document flags for: auto mode, system prompt, streaming
4. Check for usage/token reporting
5. Note any significant differences from Claude/Codex

## Acceptance Criteria
- [ ] Installation method documented
- [ ] Basic invocation working
- [ ] Flags mapped to curb needs
- [ ] Token reporting capability assessed
- [ ] Findings written to .chopshop/spikes/gemini.md

## Files Likely Involved
- .chopshop/spikes/gemini.md (new)
EOF

cat > "$DESC_DIR/curb-3s0.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-d9l.md" << 'EOF'
## Context
Need to understand OpenCode CLI before implementing harness.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Install OpenCode CLI, test invocation patterns, document findings.

## Implementation Steps
1. Research OpenCode CLI installation
2. Test basic invocation with prompt
3. Document flags for: auto mode, system prompt, streaming
4. Check for usage/token reporting
5. Note differences from other harnesses

## Acceptance Criteria
- [ ] Installation method documented
- [ ] Basic invocation working
- [ ] Flags mapped to curb needs
- [ ] Token reporting capability assessed
- [ ] Findings written to .chopshop/spikes/opencode.md

## Files Likely Involved
- .chopshop/spikes/opencode.md (new)
EOF

cat > "$DESC_DIR/curb-lop.md" << 'EOF'
## Context
Add OpenCode as a supported harness based on spike findings.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Follow pattern from other harness implementations.

## Implementation Steps
1. Add opencode_invoke() function
2. Add opencode_invoke_streaming() if supported
3. Handle system prompt passing
4. Add to harness_detect() priority list
5. Update harness_available() check

## Acceptance Criteria
- [ ] curb --harness opencode works
- [ ] System and task prompts passed correctly
- [ ] Streaming mode if available
- [ ] Falls back gracefully if not installed

## Files Likely Involved
- lib/harness.sh
EOF

cat > "$DESC_DIR/curb-kod.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-fpg.md" << 'EOF'
## Context
Token tracking needs to work across all harnesses for budget enforcement.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Implement harness-specific token extraction based on spike findings.

## Implementation Steps
1. Add gemini_get_usage() based on Gemini output format
2. Add opencode_get_usage() based on OpenCode output format
3. Update harness_get_usage() to delegate appropriately
4. Handle missing data gracefully (estimate or return 0)
5. Test with actual runs

## Acceptance Criteria
- [ ] Token counts available from Gemini runs
- [ ] Token counts available from OpenCode runs
- [ ] Estimation fallback works
- [ ] Budget tracking accurate across harnesses

## Files Likely Involved
- lib/harness.sh
- lib/budget.sh
EOF

cat > "$DESC_DIR/curb-tw9.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-ch2.md" << 'EOF'
## Pause for Validation

Phase 3 is complete. Curb now supports customization and multiple harnesses.

## What's Ready
- 5 hook points (pre-loop, pre-task, post-task, on-error, post-loop)
- 4 harnesses (Claude, Codex, Gemini, OpenCode)
- Harness capability detection
- Token tracking across all harnesses

## Suggested Testing
- [ ] Create a pre-task hook that logs to a file, verify it runs
- [ ] Test each harness with curb --harness X --once
- [ ] Verify budget tracking works with different harnesses
- [ ] Try harness priority config

## Questions for Feedback
- Are the hook points sufficient? Any missing?
- Are all 4 harnesses working reliably?
- Is the capability detection useful in practice?

## Key Milestone
After this checkpoint, curb is feature-complete for 1.0!

## Next Steps
If approved, proceed to Phase 4: Polish (docs, examples, UX)
EOF

# Phase 4: Polish

cat > "$DESC_DIR/curb-gp6.md" << 'EOF'
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
EOF

cat > "$DESC_DIR/curb-zlk.md" << 'EOF'
## Context
README needs to cover all 1.0 features for new users.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 30m
**Approach:** Add sections for new features, update examples.

## Implementation Steps
1. Add Configuration section (global/project config)
2. Add Hooks section with lifecycle diagram
3. Add Budget section with usage examples
4. Update Harnesses section with all 4
5. Add Logging section

## Acceptance Criteria
- [ ] All new features documented
- [ ] Examples for common use cases
- [ ] Config schema documented
- [ ] Quick start still works

## Files Likely Involved
- README.md
EOF

cat > "$DESC_DIR/curb-2d6.md" << 'EOF'
## Context
--help should show all new flags and features.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 15m
**Approach:** Update usage() function with new flags.

## Implementation Steps
1. Add --budget to help
2. Add --require-clean to help
3. Group flags by category (Core, Reliability, Debug)
4. Add examples section

## Acceptance Criteria
- [ ] All new flags in --help
- [ ] Grouped logically
- [ ] Examples helpful

## Files Likely Involved
- curb
EOF

cat > "$DESC_DIR/curb-ehj.md" << 'EOF'
## Context
Existing curb users need to know what changed and how to adapt.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 20m
**Approach:** Document breaking changes, new defaults, migration steps.

## Implementation Steps
1. Create UPGRADING.md
2. List breaking changes (if any)
3. Document new environment variables
4. Explain new directory structure
5. Provide step-by-step upgrade process

## Acceptance Criteria
- [ ] All breaking changes listed
- [ ] Clear migration steps
- [ ] Before/after examples
- [ ] Linked from README

## Files Likely Involved
- UPGRADING.md (new)
- README.md (link to it)
EOF

cat > "$DESC_DIR/curb-a4p.md" << 'EOF'
## Context
Users need reference docs for all config options.

## Implementation Hints

**Recommended Model:** haiku
**Estimated Duration:** 20m
**Approach:** Create a config reference with all options and defaults.

## Implementation Steps
1. Create docs/CONFIG.md
2. Document each config section
3. List all options with types and defaults
4. Add examples for common scenarios
5. Link from README

## Acceptance Criteria
- [ ] All config options documented
- [ ] Types and defaults clear
- [ ] Examples for common cases
- [ ] Searchable/scannable format

## Files Likely Involved
- docs/CONFIG.md (new)
- README.md (link)
EOF

cat > "$DESC_DIR/curb-god.md" << 'EOF'
## Context
Verify all pieces work together before release.

## Implementation Hints

**Recommended Model:** sonnet
**Estimated Duration:** 30m
**Approach:** Create a test project with multiple tasks, run with budget, verify all features.

## Implementation Steps
1. Create tests/e2e/ directory
2. Set up test project with 3-5 simple tasks
3. Add hooks that log to file
4. Run curb with --budget 100000
5. Verify: logs created, hooks ran, budget stopped loop

## Acceptance Criteria
- [ ] Full loop runs to completion or budget
- [ ] All hooks fire at right times
- [ ] Logs contain all expected events
- [ ] Clean state enforced
- [ ] Can be run in CI

## Files Likely Involved
- tests/e2e/run.sh (new)
- tests/e2e/project/ (test fixtures)
EOF

cat > "$DESC_DIR/curb-61a.md" << 'EOF'
## Final Validation

All phases complete. Curb 1.0 is ready for release.

## What's Ready
- Config: global and project configuration
- Logging: structured JSONL logs
- Reliability: clean state, budget enforcement
- Hooks: 5 lifecycle extension points
- Harnesses: Claude, Codex, Gemini, OpenCode
- Documentation: README, examples, migration guide

## Release Checklist
- [ ] All tests passing
- [ ] README reviewed and accurate
- [ ] CHANGELOG updated
- [ ] Version bumped to 1.0.0
- [ ] Git tag created
- [ ] Announcement drafted

## Suggested Final Testing
- [ ] Fresh install on new machine
- [ ] Run through quick start guide
- [ ] Complete a multi-task project
- [ ] Verify budget tracking accurate
- [ ] Test one hook end-to-end

## Celebrate!
Curb 1.0 is reliable, extensible, and documented. Ship it!
EOF

# Now update all tasks
echo "Updating all tasks with descriptions..."

for id in curb-iwv curb-1l6 curb-0u2 curb-et7 curb-ohp curb-13j curb-0b5 curb-kiz curb-hp9 \
          curb-co7 curb-g21 curb-vdw curb-4l8 curb-0ub curb-0hz curb-rvl curb-iji curb-fxr \
          curb-xo3 curb-zrg curb-ffn curb-4wz curb-3s0 curb-d9l curb-lop curb-kod curb-fpg curb-tw9 curb-ch2 \
          curb-gp6 curb-zlk curb-2d6 curb-ehj curb-a4p curb-god curb-61a; do
    update_task "$id"
done

echo ""
echo "Done! All tasks updated with descriptions."
