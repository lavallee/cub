# Itemized Plan: 2026-01-28-assorted Bug Fixes

> Source: [2026-01-28-assorted-bugs.md](plans/_punchlists/2026-01-28-assorted-bugs.md)
> Generated: 2026-01-29

## Context Summary
Tasks generated from punchlist: 2026-01-28-assorted-bugs.md

---

## Epic: cub-n6x - 2026-01-28-assorted Bug Fixes
Priority: 2
Labels: punchlist, punchlist:2026-01-28-assorted-bugs

Punchlist tasks from: 2026-01-28-assorted-bugs.md

### Task: cub-n6x.1 - Fix label order comparison in backend divergence checks
Priority: 2
Labels: punchlist

**Context**: The backend divergence detection compares task labels as ordered lists, causing false positives when labels appear in different orders between the beads backend (alphabetically sorted) and in-memory state. Since labels are semantically unordered, comparisons should use set equality instead, eliminating spurious warnings while maintaining detection of real label divergences.

**Implementation Steps**:
1. Locate backend divergence checks in `close_task()` and `get_task()` operations within the tasks backend implementation
2. Convert label list comparisons to set comparisons (e.g., `set(a.labels) == set(b.labels)`)
3. Update any helper functions or comparison logic that currently treat labels as ordered sequences
4. Add test cases verifying set-based comparison with various label orderings (different permutations of the same labels)
5. Run tests to confirm false positives are eliminated while real divergences are still detected

**Acceptance Criteria**:
- [ ] Backend divergence checks compare labels as sets, not lists
- [ ] False positives from label reordering are eliminated
- [ ] Real divergences (actual label additions/removals) are still detected
- [ ] No warnings logged when only label order differs
- [ ] Tests verify set-based comparison with various label orderings
- [ ] All existing tests pass with changes

---

### Task: cub-n6x.2 - Fix monitor command to work with beads backend
Priority: 2
Labels: punchlist

**Context**: The `cub monitor` command fails with "No active session found" error because it was designed for a session-based architecture that has been replaced by beads-based task management. The monitor command needs to be updated to work with the current task backend system, displaying real-time progress on beads tasks instead of looking for legacy session state. This is a critical UX feature for autonomous execution visibility.

**Implementation Steps**:
1. Investigate current session/task state storage in codebase (check how `cub run` tracks execution, beads backend integration)
2. Review `cub monitor` implementation to understand what "active session" lookup is attempting
3. Determine appropriate data source for live task progress (beads task status, run loop state, or execution ledger)
4. Refactor monitor to query beads backend and display real-time task progress
5. Update help text and error messages to reflect beads-based monitoring
6. Test monitor command during `cub run` execution to verify real-time updates
7. Add fallback behavior when no tasks are running (clear message instead of error)

**Acceptance Criteria**:
- [ ] `cub monitor` executes without "No active session found" error
- [ ] Command displays live task progress when `cub run` is executing
- [ ] Shows appropriate status message when no tasks are running
- [ ] Works with beads backend task management system
- [ ] Help text accurately describes monitoring beads tasks
- [ ] Works both standalone and during active `cub run` sessions

---

### Task: cub-n6x.3 - Add post-command guidance messages to key cub workflows
Priority: 2
Labels: punchlist

**Context**: Users new to cub lack clear direction after running commands, leaving them uncertain about next steps. Contextual guidance messages will improve onboarding and reduce friction by providing actionable next steps with concrete examples. This is a UX improvement focused on making cub more intuitive for new users.

**Implementation Steps**:
1. Create a guidance module (`cub/core/guidance.py`) with a `GuidanceProvider` class to generate contextual next-step messages based on command type and result
2. Add guidance output to `cub init` command - display suggested next steps (create capture, run interview, start task) after successful initialization
3. Add guidance output to `cub capture` command - suggest next steps (review capture, start interview, organize into spec) after capture creation
4. Add guidance output to `cub spec` command - guide to next phase (detailed requirements, link to epic, schedule planning) after spec creation
5. Implement `--quiet` flag support across these commands to suppress guidance messages when desired
6. Format guidance using Rich tables/panels for readability and consistency
7. Add tests for guidance module and verify all commands respect quiet flag

**Acceptance Criteria**:
- [ ] `cub init` displays 3-5 actionable next steps with copyable command examples after initialization
- [ ] `cub capture` displays 3-5 actionable next steps after successful capture creation
- [ ] `cub spec` displays 3-5 actionable next steps after successful spec creation
- [ ] All guidance messages respect `--quiet` flag and suppress output when enabled
- [ ] Guidance uses Rich formatting (tables or panels) for consistent, readable output
- [ ] Command examples in guidance are accurate and directly copyable
- [ ] All existing command behavior remains unchanged (guidance is additive only)
- [ ] Unit tests cover guidance message generation for each command type

---

### Task: cub-n6x.4 - Configure git upstream on feature branch creation
Priority: 2
Labels: punchlist

**Context**: When build-plan creates a feature branch, it doesn't set upstream tracking, causing `git push` to fail with "fatal: The current branch has no upstream branch." Users must manually run `git push --set-upstream origin <branch>` before subsequent pushes work. This friction breaks the autonomous workflow where agents should be able to push changes without manual git intervention.

**Implementation Steps**:
1. Locate the feature branch creation logic in build-plan (likely in `cub.core.launch` or a related module that handles git operations)
2. After creating the local branch, immediately configure upstream tracking by either:

**Acceptance Criteria**:
- [ ] Feature branches created by build-plan have upstream tracking configured
- [ ] `git push` works on new branches without `--set-upstream` flag
- [ ] Works for both new local branches and existing branches being pushed for first time
- [ ] Tests confirm upstream tracking is set and push operations succeed
- [ ] Documentation updated in CLAUDE.md

---

### Task: cub-n6x.5 - Check completed steps before launching architect in plan run
Priority: 2
Labels: punchlist

**Context**: The `cub plan run` command currently assumes architect should launch automatically upon exit, but this breaks workflows where earlier steps are incomplete or partially completed. Users need visibility into which prep pipeline steps (triage, architect, plan, bootstrap) have already been done so they can decide whether to continue, re-run a step, or skip ahead. The system should detect artifacts from previous runs and guide users through the pipeline intelligently rather than blindly advancing.

**Implementation Steps**:
1. Create a step detection function that checks for completion artifacts (triage markdown files, architect outputs, plan.jsonl, beads state) in the project
2. Display a summary table showing which prep steps are completed, in-progress, or incomplete when exiting plan run
3. Prompt the user with options: continue to next incomplete step, re-run a specific step, or exit
4. Route the selected action back to the appropriate plan subcommand (orient, architect, plan, bootstrap)
5. Handle edge cases: partial architect completion, missing intermediate steps, corrupted artifacts

**Acceptance Criteria**:
- [ ] Detects completion status of all four prep steps via artifact inspection
- [ ] Displays step summary before prompting for next action
- [ ] Offers user choice to continue, re-run, or exit (not forced into architect)
- [ ] Does not launch architect if earlier steps are incomplete
- [ ] Gracefully handles partial completion and corrupted artifacts

---

### Task: cub-n6x.6 - Add build failure detection and retry logic to cub pr
Priority: 2
Labels: punchlist

**Context**: The `cub pr` command currently creates pull requests but has no visibility into CI check status or automated recovery from transient failures. This means flaky tests, rate limits, and temporary service issues require manual intervention, interrupting autonomous workflows. Adding automated failure detection and retry logic would enable self-healing PR workflows that handle common transient failures without manual handoff.

**Implementation Steps**:
1. Create `cub.core.services.pr_monitor` module to implement check polling and failure detection via `gh pr checks`
2. Add retry configuration model to `cub.core.config` with timeout duration and max retry count parameters
3. Extend `LaunchService` to support background PR monitoring while harness is active
4. Implement check state machine: poll → detect failure → wait → retry → repeat or succeed
5. Add `--retry-timeout` and `--no-retry` flags to `cub pr` command in `cub.cli.pr`
6. Integrate check monitoring into session hooks to log retry history to session forensics
7. Add check status and retry attempts to `cub.core.ledger` models for session ledger recording
8. Write integration tests for check detection, retry triggering, and rate limit handling

**Acceptance Criteria**:
- [ ] `cub pr` detects PR check failures via `gh pr checks` polling
- [ ] Automatic retry timer (default 10 minutes, configurable) activates when failures detected
- [ ] `--retry-timeout` flag accepts duration strings (e.g., `5m`, `30s`)
- [ ] `--no-retry` flag disables automatic retry behavior for all check types
- [ ] Failed checks are re-triggered via `gh pr checks --rerun` or equivalent
- [ ] Session forensics (`.cub/ledger/forensics/{session_id}.jsonl`) logs all check statuses and retry attempts with timestamps
- [ ] Max retries (default 3) prevents infinite loop; stops retrying after limit reached
- [ ] Handles `gh` API rate limiting and network errors gracefully with exponential backoff
- [ ] Works with both draft PRs (`--draft`) and regular PRs

---

### Task: cub-n6x.7 - Ensure plan.json is created at pipeline start
Priority: 2
Labels: punchlist

**Context**: plan.json is currently written during the orient stage rather than when the plan context is first created. If orient fails before calling ctx.save_plan(), there's no plan.json file to recover from. This reduces fault tolerance and prevents resumption in cases where early stage failures occur. Creating plan.json immediately after context initialization ensures a persistent checkpoint exists from the start.

**Implementation Steps**:
1. Locate PipelineConfig.run() and identify where PlanContext is created or loaded
2. Add ctx.save_plan() call immediately after plan context initialization, before any stage runs
3. Verify orient stage's existing ctx.save_plan() call at line 484 doesn't duplicate writes
4. Run full test suite to ensure pipeline behavior remains unchanged
5. Verify plan.json exists at project root before any stage execution begins

**Acceptance Criteria**:
- [ ] plan.json is created immediately after plan context initialization
- [ ] plan.json exists before orient stage executes
- [ ] All existing tests pass with no behavioral changes
- [ ] Plan data is recoverable/resumable even if orient fails early

---

### Task: cub-n6x.8 - Remove deprecated cub:triage and cub:plan skill commands
Priority: 2
Labels: punchlist

**Context**: The cub:triage and cub:plan skill commands are no longer needed and create maintenance overhead. These commands were part of an earlier planning pipeline that has been superseded by other tooling. Removing them will reduce code complexity, eliminate dead skill registrations, and prevent confusion about available planning commands. This is a straightforward cleanup task with no backward compatibility concerns.

**Implementation Steps**:
1. Search the codebase for all references to `cub:triage` and `cub:plan` (skill definitions, command registrations, templates)
2. Remove skill command definitions for `cub:triage` and `cub:plan` from skill/command template files
3. Remove any `.claude/commands` configuration entries that register these skills
4. Remove skill routing and registration code that supports these commands
5. Search for any remaining references (comments, documentation, imports) and clean them up
6. Verify no broken references remain by grepping for "cub:triage" and "cub:plan" across the codebase

**Acceptance Criteria**:
- [ ] `cub:triage` no longer appears in any templates, configuration files, or code
- [ ] `cub:plan` no longer appears in any templates, configuration files, or code
- [ ] All skill registration/routing code that handled these commands is removed
- [ ] Remaining skills and commands continue to function correctly (verify with `cub --help`)
- [ ] No broken imports or dangling references to removed skill definitions
- [ ] Git status shows only the intended removals (no accidental changes)

---

### Task: cub-n6x.9 - Add harness and model info to task headline
Priority: 2
Labels: punchlist

**Context**: The task headline box currently displays only basic task metadata (ID, title, priority, type, iteration), but doesn't show the runtime configuration (harness backend, model) that the iteration will use. This makes it difficult for developers to understand which AI backend and model will be executing their task, especially in contexts where multiple backends are available or when switching between different model configurations. Adding this information to the headline improves visibility into the execution environment and helps catch configuration mismatches early.

**Implementation Steps**:
1. Identify where the headline box is rendered during task iteration startup (in both `cub run` flow and direct session context)
2. Extract harness backend and model information from the current run context or task configuration
3. Modify the headline rendering logic to include harness backend and model as additional display fields
4. Implement graceful fallback to omit fields when not configured (no "None" or empty values displayed)
5. Test layout with various configuration combinations to ensure readability and prevent excessive line wrapping
6. Verify the changes work in both `cub run` autonomous mode and direct harness session contexts
7. Add or update tests to cover headline rendering with different harness/model configurations

**Acceptance Criteria**:
- [ ] Headline box displays harness backend name when available
- [ ] Headline box displays model name when available
- [ ] Other explicit configuration specs are included if applicable
- [ ] Layout remains readable without excessive line wrapping
- [ ] Unconfigured specs are omitted gracefully (no "None", "N/A", or blank values shown)
- [ ] Changes work in both `cub run` and direct session contexts
- [ ] Existing tests pass and new tests cover headline rendering scenarios

---

### Task: cub-n6x.10 - Add newlines between streamed harness messages
Priority: 2
Labels: punchlist

**Context**: When `cub run --stream` outputs AI harness messages, consecutive messages are concatenated without visual separation, making the output difficult to read and follow. Adding newlines between each streamed message improves readability and creates a cleaner user experience across all harness backends.

**Implementation Steps**:
1. Locate the stream message output handling in the run loop (likely in `cub.core.run` or `cub.cli.run`)
2. Identify where harness messages are printed/streamed to stdout
3. Add a newline character after each complete message is output
4. Ensure the newline only appears between messages, not duplicated at message start/end
5. Test with `cub run --stream` to verify output formatting with multiple consecutive messages
6. Verify non-stream output remains unchanged and unaffected by the change
7. Test with multiple harness backends (claude, codex, gemini) to ensure consistency

**Acceptance Criteria**:
- [ ] Each streamed message is followed by exactly one newline character
- [ ] Output is readable with clear visual separation between consecutive messages
- [ ] Non-stream output (`cub run` without `--stream`) is unaffected
- [ ] Works correctly with all harness backends (claude, codex, gemini, opencode)
- [ ] No duplicate blank lines or extra whitespace introduced
- [ ] Existing tests still pass and new behavior is tested

---

### Task: cub-n6x.11 - Add progress updates during punchlist item processing
Priority: 2
Labels: punchlist

**Context**: The punchlist processing command currently provides no feedback during the hydration phase, leaving users uncertain whether work is progressing or if the tool has hung. This is especially noticeable when processing larger punchlist files (10+ items) with API calls. Adding item-by-item progress updates will provide real-time visibility into processing status and improve the user experience without adding complexity.

**Implementation Steps**:
1. Locate the punchlist processing command and hydration loop (likely in `src/cub/cli/` or `src/cub/core/`)
2. Identify where items are iterated during hydration and replace silent iteration with Rich progress tracking
3. Extract item titles/summaries to display alongside progress indicator in format "[N/TOTAL]"
4. Use Rich's Progress or live output utilities to stream updates without blocking
5. Test with multiple punchlist sizes to ensure no significant latency is introduced
6. Verify output integrates cleanly with existing Rich console patterns in cub

**Acceptance Criteria**:
- [ ] Progress indicator displays "[current/total]" format for each item
- [ ] Item title or brief summary appears alongside progress update
- [ ] Updates appear incrementally as each item completes processing
- [ ] No measurable latency increase compared to current implementation
- [ ] Output uses Rich console consistent with other cub commands
- [ ] Works correctly with punchlist files of varying sizes (3-50+ items)

---
