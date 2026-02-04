---
attempt: 1
harness: claude
model: ''
run_id: cub-20260203-221403
started_at: '2026-02-04T03:22:06.894515+00:00'
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

Task ID: cub-t44.2
Type: task
Title: Add explicit project_id to prevent task ID prefix collisions

Description:
The current `_get_prefix()` method in jsonl.py derives task ID prefixes from the first 3 characters of the project directory name, causing collisions when multiple projects share the same prefix (e.g., both "cub" and "cub-roundabout" get prefix "cub"). This results in task IDs like `cub-a1x` in the roundabout project instead of the intended `rou-a1x`, making task IDs non-unique across projects. The fix requires adding an explicit `project_id` setting to `.cub/config.json` that persists a unique prefix, with `cub init` prompting users to set or auto-generating one if not provided.

**Implementation Steps:**
1. Modify `.cub.json` template to include a `project_id` field with a unique prefix (auto-generated if not provided during init)
2. Update `src/cub/cli/init_cmd.py` to prompt for or auto-generate a project_id during initialization, ensuring uniqueness
3. Update `src/cub/core/tasks/jsonl.py::_get_prefix()` to read the project_id from config instead of deriving from directory name
4. Update config loading in `src/cub/core/config/loader.py` to handle the new `project_id` field
5. Add migration logic to detect old projects without `project_id` and auto-populate based on directory name on first use
6. Update tests to verify prefix comes from config, not directory name

Acceptance Criteria:
- `cub init` prompts for or auto-generates unique `project_id` and stores it in `.cub/config.json`
- Task IDs use the configured `project_id` prefix instead of directory name
- Existing projects without `project_id` migrate gracefully on first use
- Multiple projects with overlapping names (e.g., "cub" and "cub-roundabout") get distinct task ID prefixes
- All tests pass and cover prefix generation from config vs. directory name scenarios

## Epic Context

This task belongs to epic: **cub-t44** - 2026 02 03

Epic Purpose:
Punchlist tasks from: 2026-02-03.md

Completed Sibling Tasks:
- ✓ cub-t44.1: Fix statusline to support JSONL task backend

Remaining Sibling Tasks:
- ○ cub-t44.3: Consolidate AGENTS.md and CLAUDE.md into single source
- ○ cub-t44.4: Consolidate runloop.md and PROMPT.md initialization
- ○ cub-t44.5: Consolidate config files into single .cub/config.json
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
2. Update the line for task `cub-t44.2` with `"status": "in_progress"` when starting
3. Update the line for task `cub-t44.2` with `"status": "closed"` when complete

**File structure:**
Each line is a complete JSON object:
```jsonl
{"id": "cub-t44.2", "status": "open|in_progress|closed", ...}
{"id": "another-task", "status": "closed", ...}
```

**Important:** Always run feedback loops (tests, typecheck, lint) BEFORE marking the task closed.

## When Complete

1. Run feedback loops (typecheck, test, lint)
2. Mark the task complete (see Task Management above)
3. Commit: `task(cub-t44.2): Add explicit project_id to prevent task ID prefix collisions`