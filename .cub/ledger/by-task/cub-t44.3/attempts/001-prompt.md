---
attempt: 1
harness: claude
model: ''
run_id: cub-20260203-221403
started_at: '2026-02-04T03:31:29.283438+00:00'
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

Task ID: cub-t44.3
Type: task
Title: Consolidate AGENTS.md and CLAUDE.md into single source

Description:
The `cub init` command currently generates both AGENTS.md and CLAUDE.md as separate files with identical content, creating maintenance burden and risk of drift. This violates DRY principle and causes confusion about which file is canonical. The solution is to generate CLAUDE.md as the single source of truth and create AGENTS.md as a symlink, ensuring consistency across the codebase and simplifying future updates.

**Implementation Steps:**
1. Examine current implementation in `src/cub/cli/init_cmd.py` and `src/cub/core/instructions.py` to understand how both files are currently generated
2. Modify `src/cub/core/instructions.py` to have a single template/function that generates CLAUDE.md content
3. Update `src/cub/cli/init_cmd.py` to write CLAUDE.md and create AGENTS.md as a symlink pointing to CLAUDE.md instead of generating duplicate content
4. Handle edge cases: Windows (symlinks require admin/developer mode), existing files (backup if needed), and git tracking (ensure .gitignore doesn't prevent symlink tracking)
5. Add tests to verify symlink creation and content consistency between the two logical references

Acceptance Criteria:
- CLAUDE.md is generated with full content from single source
- AGENTS.md exists as symlink to CLAUDE.md (not duplicate file)
- `cub init` creates both files without errors on Linux/macOS
- Symlink points to correct relative path (readable from `.cub/` directory)
- Existing tests pass and no duplicate content generation remains
- Documentation updated to reflect CLAUDE.md as canonical file

## Epic Context

This task belongs to epic: **cub-t44** - 2026 02 03

Epic Purpose:
Punchlist tasks from: 2026-02-03.md

Completed Sibling Tasks:
- ✓ cub-t44.1: Fix statusline to support JSONL task backend
- ✓ cub-t44.2: Add explicit project_id to prevent task ID prefix collisions

Remaining Sibling Tasks:
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
2. Update the line for task `cub-t44.3` with `"status": "in_progress"` when starting
3. Update the line for task `cub-t44.3` with `"status": "closed"` when complete

**File structure:**
Each line is a complete JSON object:
```jsonl
{"id": "cub-t44.3", "status": "open|in_progress|closed", ...}
{"id": "another-task", "status": "closed", ...}
```

**Important:** Always run feedback loops (tests, typecheck, lint) BEFORE marking the task closed.

## When Complete

1. Run feedback loops (typecheck, test, lint)
2. Mark the task complete (see Task Management above)
3. Commit: `task(cub-t44.3): Consolidate AGENTS.md and CLAUDE.md into single source`