---
attempt: 1
harness: claude
model: ''
run_id: cub-20260203-221403
started_at: '2026-02-04T03:59:36.802843+00:00'
---

# System Prompt

# Ralph Loop Iteration

You are an autonomous coding agent working through a task backlog.

## Your Workflow

1. **Understand**: Read the CURRENT TASK section below carefully
2. **Implement**: Complete the task fully. NO placeholders or minimal implementations.
3. **Validate**: Run all feedback loops:
   - Type checking (if applicable)
   - Tests
   - Linting
4. **Complete**: If all checks pass, close the task using the appropriate method shown in CURRENT TASK below, then commit your changes.

## Critical Rules

- **ONE TASK**: Focus only on the task assigned below
- **FULL IMPLEMENTATION**: No stubs, no TODOs, no "implement later"
- **FIX WHAT YOU BREAK**: If tests unrelated to your work fail, fix them
- **CLOSE THE TASK**: Always mark the task as closed using the method specified in CURRENT TASK

## Escape Hatch: Signal When Stuck

If you get stuck and cannot make progress despite a genuine attempt to solve the task, signal your state to the autonomous loop so it can stop gracefully instead of consuming time and budget on a blocked task.

**How to signal "stuck":**

Output this XML tag with your reason:

```
<stuck>REASON FOR BEING STUCK</stuck>
```

**What "stuck" means:**

- You have genuinely attempted to solve the task (multiple approaches, searched codebase, read docs)
- An external blocker prevents progress (missing file, dependency not found, environment issue, unclear requirements)
- Continuing to work on this task will waste time and money without producing value
- The blocker cannot be resolved within the scope of this task

**Effect of signaling "stuck":**

- The autonomous loop detects this signal and stops the run gracefully
- Your work so far is captured in artifacts and the ledger
- The task is marked with context for manual review

## When You're Done

After successfully completing the task and all checks pass:
1. Close the task using the method shown in CURRENT TASK
2. Commit your changes with format: `type(task-id): description`
3. If ALL tasks are closed, output exactly:

<promise>COMPLETE</promise>

This signals the loop should terminate.


# Task Prompt

## CURRENT TASK

Task ID: cub-t44.5
Type: task
Title: Consolidate config files into single .cub/config.json

Description:
The project has two config files with overlapping purposes: `.cub.json` (project root) for user settings like harness and budget, and `.cub/config.json` (internal state) for dev_mode flags. This split is confusing for users who don't know which file to edit. Consolidating all config into `.cub/config.json` simplifies the mental model, reduces maintenance burden, and makes configuration self-discoverable in the `.cub/` directory structure.

**Implementation Steps:**
1. Audit current config usage in `src/cub/core/config/loader.py` to identify all fields in `.cub.json` and `.cub/config.json`, document which are user-facing vs internal
2. Design unified config schema in `.cub/config.json` with clear separation between user settings (harness, budget, state checks) and internal state (dev_mode, etc.) via top-level sections
3. Update `src/cub/cli/init_cmd.py` to write all config to `.cub/config.json` and stop creating `.cub.json`
4. Update `src/cub/core/config/loader.py` to read from `.cub/config.json` with fallback to `.cub.json` for backwards compatibility, issue deprecation warning if `.cub.json` is found
5. Update template in `src/cub/templates/.cub.json` to add migration note or convert to `.cub/config.json` template
6. Add migration logic to detect existing `.cub.json` files and warn users to run `cub init` to consolidate
7. Write tests for backwards-compatible config loading and deprecation warnings
8. Update CLAUDE.md documentation to explain the consolidated config structure

Acceptance Criteria:
- All config read/write operations use `.cub/config.json` as primary location
- `.cub.json` is read for backwards compatibility with deprecation warning logged
- `cub init` creates only `.cub/config.json`, no `.cub.json`
- Unified config schema documented with clear user vs internal sections
- Migration path works: existing `.cub.json` projects are readable and warned to consolidate
- All tests pass including new backwards-compatibility tests
- mypy passes in strict mode
- CLAUDE.md updated with config structure and consolidation rationale

## Epic Context

This task belongs to epic: **cub-t44** - 2026 02 03

Epic Purpose:
Punchlist tasks from: 2026-02-03.md

Completed Sibling Tasks:
- ✓ cub-t44.1: Fix statusline to support JSONL task backend
- ✓ cub-t44.2: Add explicit project_id to prevent task ID prefix collisions
- ✓ cub-t44.3: Consolidate AGENTS.md and CLAUDE.md into single source
- ✓ cub-t44.4: Consolidate runloop.md and PROMPT.md initialization

Remaining Sibling Tasks:
- ○ cub-t44.6: Enhance agent.md template with richer cub workflow documentation
- ○ cub-t44.7: Expand constitution.md template with principles and examples
- ○ cub-t44.8: Create cub:stage skill template
- ○ cub-t44.9: Document hook forensics location and add log viewing
- ○ cub-t44.10: Fix plan.json generation through planning pipeline
- ○ cub-t44.11: Set explicit backend in cub init instead of auto-detection
- ○ cub-t44.12: Preserve user-modified prompt.md on init

## Task Management

This project uses the JSONL task backend (.cub/tasks.jsonl).

**Task lifecycle:**
1. Read `.cub/tasks.jsonl` to view task details (one JSON object per line)
2. Update the line for task `cub-t44.5` with `"status": "in_progress"` when starting
3. Update the line for task `cub-t44.5` with `"status": "closed"` when complete

**File structure:**
Each line is a complete JSON object:
```jsonl
{"id": "cub-t44.5", "status": "open|in_progress|closed", ...}
{"id": "another-task", "status": "closed", ...}
```

**Important:** Always run feedback loops (tests, typecheck, lint) BEFORE marking the task closed.

## When Complete

1. Run feedback loops (typecheck, test, lint)
2. Mark the task complete (see Task Management above)
3. Commit: `task(cub-t44.5): Consolidate config files into single .cub/config.json`