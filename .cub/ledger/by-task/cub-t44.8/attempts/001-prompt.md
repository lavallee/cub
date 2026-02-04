---
attempt: 1
harness: claude
model: ''
run_id: cub-20260204-081646
started_at: '2026-02-04T13:16:46.813508+00:00'
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

Task ID: cub-t44.8
Type: task
Title: Create cub:stage skill template

Description:
The `cub stage` command exists in the CLI but lacks a corresponding skill definition in `templates/commands/`. Without this file, the skill won't appear in the skill list and users can't invoke it via `/stage`. This is a documentation/discoverability gap that prevents users from easily accessing the stage command through the skill interface.

**Implementation Steps:**
1. Research the `cub stage` command implementation to understand its purpose, arguments, and behavior
2. Examine existing skill templates in `templates/commands/` to understand the expected format and structure
3. Create `src/cub/templates/commands/cub:stage.md` following the established skill template pattern
4. Document the command's purpose, usage examples, and any relevant flags or options
5. Verify the skill file is properly formatted and references the correct CLI command

Acceptance Criteria:
- `src/cub/templates/commands/cub:stage.md` file created with complete skill definition
- Skill template follows the same format and structure as other command skills
- Skill description accurately represents the `cub stage` command functionality
- Documentation includes purpose, syntax, examples, and relevant options
- Skill can be invoked via `/stage` and appears in skill list when available

## Epic Context

This task belongs to epic: **cub-t44** - 2026 02 03

Epic Purpose:
Punchlist tasks from: 2026-02-03.md

Completed Sibling Tasks:
- ✓ cub-t44.1: Fix statusline to support JSONL task backend
- ✓ cub-t44.2: Add explicit project_id to prevent task ID prefix collisions
- ✓ cub-t44.3: Consolidate AGENTS.md and CLAUDE.md into single source
- ✓ cub-t44.4: Consolidate runloop.md and PROMPT.md initialization
- ✓ cub-t44.5: Consolidate config files into single .cub/config.json
- ✓ cub-t44.6: Enhance agent.md template with richer cub workflow documentation
- ✓ cub-t44.7: Expand constitution.md template with principles and examples

Remaining Sibling Tasks:
- ○ cub-t44.9: Document hook forensics location and add log viewing
- ○ cub-t44.10: Fix plan.json generation through planning pipeline
- ○ cub-t44.11: Set explicit backend in cub init instead of auto-detection
- ○ cub-t44.12: Preserve user-modified prompt.md on init

## Task Management

This project uses the JSONL task backend (.cub/tasks.jsonl).

**Task lifecycle:**
1. Read `.cub/tasks.jsonl` to view task details (one JSON object per line)
2. Update the line for task `cub-t44.8` with `"status": "in_progress"` when starting
3. Update the line for task `cub-t44.8` with `"status": "closed"` when complete

**File structure:**
Each line is a complete JSON object:
```jsonl
{"id": "cub-t44.8", "status": "open|in_progress|closed", ...}
{"id": "another-task", "status": "closed", ...}
```

**Important:** Always run feedback loops (tests, typecheck, lint) BEFORE marking the task closed.

## When Complete

1. Run feedback loops (typecheck, test, lint)
2. Mark the task complete (see Task Management above)
3. Commit: `task(cub-t44.8): Create cub:stage skill template`