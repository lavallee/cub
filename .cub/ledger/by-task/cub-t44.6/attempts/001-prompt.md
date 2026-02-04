---
attempt: 1
harness: claude
model: ''
run_id: cub-20260203-221403
started_at: '2026-02-04T04:12:56.803376+00:00'
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

Task ID: cub-t44.6
Type: task
Title: Enhance agent.md template with richer cub workflow documentation

Description:
The current `templates/agent.md` provides functional setup instructions but lacks comprehensive guidance for developers using cub effectively during sessions. It misses quick-start workflows, common command patterns, troubleshooting resources, and pointers to diagnostic tools like hook logs. Enriching this template will improve developer experience by providing self-contained guidance within each project's agent context, reducing friction when switching between projects and enabling better autonomous coding sessions.

**Implementation Steps:**
1. Review current `templates/agent.md` and identify gaps in workflow guidance
2. Add a "Quick Start Workflow" section covering task discovery, claiming, and completion patterns
3. Add a "Common Command Patterns" section with practical examples of cub task, status, and suggest commands
4. Add a "Troubleshooting" section including hook verification, forensics log locations (.cub/ledger/forensics/), and common issues
5. Add a "Reading Task Output" section explaining task metadata, blockers, and dependencies
6. Add cross-references to full documentation with @.cub/agent.md links and cub docs pointers
7. Ensure template preserves the existing structure and remains under ~500 lines total
8. Test that generated CLAUDE.md files in new projects include the enhanced content

Acceptance Criteria:
- Template includes a "Quick Start Workflow" section with 3-5 key steps for claiming and completing tasks
- Template includes "Common Command Patterns" with at least 5 real-world command examples
- Template includes "Troubleshooting" section with hook verification and forensics log location (.cub/ledger/forensics/)
- Template includes "Reading Task Output" section explaining task metadata interpretation
- All sections reference external docs or .cub/ files appropriately using @-syntax
- Template remains well-organized and under ~500 lines (excluding existing architecture sections)
- Generated CLAUDE.md files in new projects (`cub new`) include the enhanced content
- mypy and ruff pass with no changes needed to template file itself

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

Remaining Sibling Tasks:
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
2. Update the line for task `cub-t44.6` with `"status": "in_progress"` when starting
3. Update the line for task `cub-t44.6` with `"status": "closed"` when complete

**File structure:**
Each line is a complete JSON object:
```jsonl
{"id": "cub-t44.6", "status": "open|in_progress|closed", ...}
{"id": "another-task", "status": "closed", ...}
```

**Important:** Always run feedback loops (tests, typecheck, lint) BEFORE marking the task closed.

## When Complete

1. Run feedback loops (typecheck, test, lint)
2. Mark the task complete (see Task Management above)
3. Commit: `task(cub-t44.6): Enhance agent.md template with richer cub workflow documentation`