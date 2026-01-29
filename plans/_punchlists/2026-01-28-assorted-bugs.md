# Punchlist: 2026-01-28-assorted-bugs

## Fix label order comparison in backend divergence checks

The backend divergence detection is comparing task labels as ordered lists, causing false positives when the same labels appear in different orders. This occurs in `close_task()` and `get_task()` operations where the beads backend returns labels in a different order than the in-memory state.

**Context:**
Labels are semantically unordered and should be compared as sets, not lists. The current list comparison fails when:
- Beads sorts labels alphabetically: `['complexity:medium', 'core', 'epic:cub-b1a', ...]`
- In-memory state has different sort order: `['phase-1', 'core', 'refactor', ...]`

**Acceptance Criteria:**
1. Backend divergence checks compare labels as sets (order-independent)
2. False positives from label reordering are eliminated
3. Real divergences (actual label additions/removals) are still detected
4. No warnings logged when only label order differs
5. Tests verify set-based comparison with various label orderings

---

## Fix monitor command to work with beads backend

The `cub monitor` command currently fails with "No active session found" error. This appears to be due to changes in the codebase that have shifted from session-based monitoring to task-based execution using the beads backend.

**Context:**
- `cub monitor` is designed to provide a live dashboard during task execution
- The error suggests it's looking for an "active session" concept that may no longer exist or is stored differently
- The project now uses beads as the primary task backend

**Acceptance Criteria:**
- `cub monitor` command executes without error
- It displays task progress in real-time (or shows appropriate status if no tasks are running)
- It works with the current beads backend task management system
- Help text accurately describes what the command does

**Investigation needed:**
- Check how session state is tracked with beads backend
- Review what "active session" means in current architecture
- Determine if monitor should show beads task progress or if it needs refactoring for the new task model

---

## Add post-command guidance messages to cub workflow

Improve user experience by providing contextual next-step guidance after key cub commands execute.

**Context:**
Users new to cub need clear direction on what to do after running commands. Currently, commands complete silently or with minimal output, leaving users uncertain about the next workflow step.

**Acceptance Criteria:**

1. **`cub init` command**
   - After successful initialization, display a bulleted list of suggested next steps
   - Include: creating first capture, running interview, starting first task
   - Link to relevant documentation or show example commands

2. **`cub capture` command**
   - After successfully creating a capture, suggest next steps
   - Recommend: review capture, start interview, organize into spec

3. **`cub spec` command** (if creating new spec)
   - After spec creation, guide user to next phase
   - Suggest: detailed requirements, link to parent epic, schedule for planning

4. **General pattern**
   - Guidance should be concise (3-5 bullet points max)
   - Include actual command examples users can copy/paste
   - Use Rich formatting for readability
   - Respect `--quiet` flag if present (suppress guidance)

**Out of scope:**
- Changes to existing command behavior
- New commands beyond what's listed
- Modifying beads (`bd`) output (it's separate tool)

---

## Ensure build-plan sets git upstream on push

When creating a feature branch during build-plan, the upstream tracking should be automatically configured so subsequent `git push` commands work without requiring `--set-upstream`.

**Context:**
After running build-plan and creating a feature branch, users encounter: "fatal: The current branch has no upstream branch" when attempting to push. This requires manual intervention with `git push --set-upstream origin <branch>`.

**Acceptance Criteria:**
- Build-plan creates feature branches with upstream tracking configured (equivalent to `git push -u origin <branch>` on first push)
- Subsequent `git push` commands work without additional flags
- Works with both initial branch creation and when pushing existing local branches
- Alternative: Configure `push.autoSetupRemote = true` in git config as part of `cub init`

---

## Check completed steps before launching architect in plan run exit

When exiting `cub plan run`, the system should inspect which steps have already been completed in the prep pipeline (triage, architect, plan, bootstrap) instead of automatically launching into architect mode.

**Context:**
Currently, when a user exits the plan command, the tool assumes the next step should be architect mode. This breaks the workflow when:
- Some steps have already been completed
- The user wants to re-run or skip a particular step
- Multiple iterations through the pipeline are needed

**Acceptance Criteria:**
- [ ] Detect which prep steps have been completed (check for artifacts: triage output, architect output, plan.jsonl, beads state)
- [ ] Display a summary of completed steps before prompting next action
- [ ] Offer user a choice: continue from next incomplete step, re-run a specific step, or exit
- [ ] Don't automatically jump to architect if earlier steps are incomplete
- [ ] Handle partial completion gracefully (e.g., architect started but not finished)

---

## Add build failure detection and retry logic to cub pr

The `cub pr` command should monitor PR checks (CI messages, build failures) and automatically retry or re-trigger them after a configurable timeout when failures are detected.

**Context:**
Currently, `cub pr` creates a pull request but doesn't actively monitor the status of CI checks and build results. This means failures that could be transient (flaky tests, rate limits, temporary service issues) require manual intervention to retry.

**Requirements:**
- Monitor PR checks via `gh pr checks` after creating a PR
- Detect build failures, CI errors, and other check failures
- When failures are detected, start a 10-minute timer (configurable via flag or config)
- After timer expires, automatically retry failed checks or re-trigger CI
- Continue monitoring until checks pass or max retries reached
- Log all check statuses and retry attempts to session ledger
- Gracefully handle network errors and API rate limiting

**Acceptance Criteria:**
- [ ] `cub pr` detects and logs PR check failures
- [ ] Automatic 10-minute retry timer kicks off when failures detected
- [ ] `--retry-timeout` flag allows customization (e.g., `--retry-timeout 5m`)
- [ ] `--no-retry` flag disables auto-retry behavior
- [ ] Checks are re-triggered via `gh pr checks --rerun` or similar
- [ ] Session ledger captures retry history with timestamps
- [ ] Max retries (default 3) prevents infinite loops
- [ ] Works with both draft and regular PRs

---

## Ensure plan.json is created at pipeline start, not after orient begins

plan.json is currently first written during the orient stage (after start_stage() is called), rather than when the plan context is initially created. This means if orient fails before that point, there's no plan.json to recover from.

**Current behavior:**
- PlanContext.create() initializes a Plan object in memory
- Pipeline runs orient stage, which calls ctx.save_plan() at line 484
- plan.json is written at that point

**Proposed improvement:**
- Call ctx.save_plan() immediately after creating or loading the plan context in PipelineConfig.run()
- Ensures plan.json exists before any stage runs
- Improves fault tolerance and allows resuming even if orient fails early

**Acceptance criteria:**
- plan.json is created when plan context is first created
- plan.json exists before orient stage runs
- Existing pipeline behavior unchanged (all tests pass)
- Plan data is accessible for recovery/resumption even if stages fail early

---

## Remove deprecated cub:triage and cub:plan commands

Remove the `cub:triage` and `cub:plan` skill commands from the codebase. These commands are no longer needed and don't require backward compatibility maintenance.

**Changes needed:**
1. Remove `cub:triage` and `cub:plan` from skill/command templates
2. Remove these commands from `.claude/commands` configuration
3. Remove any references or registrations in the codebase that support these skills

**Acceptance criteria:**
- `cub:triage` and `cub:plan` no longer appear in any templates or configuration files
- No skill registration or command routing code supports these commands
- Remaining skills and commands continue to function correctly
- No broken references to removed commands

---

## Add harness and model info to task headline

When starting a task iteration, the headline box should display the harness backend, model, and any other explicitly configured specs alongside the existing task metadata.

**Current behavior:**
The headline box shows: Task ID, Title, Priority, Type, Iteration

**Desired behavior:**
Include additional configuration details in the headline, such as:
- Harness backend (e.g., "claude", "gemini")
- Model (e.g., "claude-opus-4.5", "gemini-2.0")
- Any other explicit specs from the task config or run context

**Acceptance criteria:**
- [ ] Headline box displays harness backend when available
- [ ] Headline box displays model name when available
- [ ] Other explicit specs are included if applicable
- [ ] Layout remains readable (no excessive line wrapping)
- [ ] Specs are omitted gracefully if not configured (no "None" values displayed)
- [ ] Changes apply to both `cub run` and direct session contexts

---

## Add newlines between streamed messages in cub run

When `cub run --stream` is enabled, consecutive messages from the AI harness are concatenated without visual separation, making output difficult to read. Each message should be followed by a newline for clarity.

**Current behavior:**
```
Running claude...
I'll help you implement...Good! Now let me check...Perfect! Now let me explore...
```

**Expected behavior:**
```
Running claude...
I'll help you implement...

Good! Now let me check...

Perfect! Now let me explore...
```

**Acceptance Criteria:**
- Each streamed message is followed by a newline character
- Output remains readable and properly formatted
- Does not affect non-stream output
- Works with all harness backends (claude, codex, gemini, etc.)

---

## Add item-by-item progress updates during punchlist processing

When processing a punchlist file, users see only the initial "Parsed X items" message, then a long wait before the final result. The tool should provide real-time feedback on processing progress to show that work is happening.

**Current behavior:**
```
Processing: plans/_punchlists/2026-01-23-dashboard-bugs-01.md
Parsed 10 items
Hydrating items with Claude...
[long wait with no feedback]
```

**Desired behavior:**
Display progress as each item is processed:
```
Processing: plans/_punchlists/2026-01-23-dashboard-bugs-01.md
Parsed 10 items
Hydrating items with Claude...
  [1/10] Processing "Item title 1"...
  [2/10] Processing "Item title 2"...
  [3/10] Processing "Item title 3"...
  ...continues until complete
```

**Acceptance criteria:**
- Progress indicator shows current item number and total (e.g., "[3/10]")
- Item title or summary is displayed for context
- Updates appear incrementally as each item is processed
- Does not add significant latency or verbosity
- Works with Rich console output (consistent with existing cub UI patterns)

---
