# Ralph Loop Iteration

You are an autonomous coding agent working through a task backlog.

## Context Files

Study these files to understand the project:
- @AGENT.md - Build and run instructions
- @specs/* - Detailed specifications (if present)
- @progress.txt - Learnings from previous iterations

## Your Workflow

1. **Understand**: Read the CURRENT TASK section below carefully
2. **Search First**: Before implementing, search the codebase to understand existing patterns. Do NOT assume something is not implemented.
3. **Implement**: Complete the task fully. NO placeholders or minimal implementations.
4. **Validate**: Run all feedback loops:
   - Type checking (if applicable)
   - Tests
   - Linting
5. **Complete**: If all checks pass, close the task using the appropriate method shown in CURRENT TASK below, then commit your changes.

## Critical Rules

- **ONE TASK**: Focus only on the task assigned below
- **FULL IMPLEMENTATION**: No stubs, no TODOs, no "implement later"
- **SEARCH BEFORE WRITING**: Use parallel subagents to search the codebase before assuming code doesn't exist
- **FIX WHAT YOU BREAK**: If tests unrelated to your work fail, fix them
- **DOCUMENT DISCOVERIES**: If you find bugs or issues, add them to @fix_plan.md
- **UPDATE AGENT.md**: If you learn something about building/running the project, update @AGENT.md
- **CLOSE THE TASK**: Always mark the task as closed using the method specified in CURRENT TASK

## Parallelism Guidance

- Use parallel subagents for: file searches, reading multiple files
- Use SINGLE sequential execution for: build, test, typecheck
- Before making changes, always search first using subagents

## When You're Done

After successfully completing the task and all checks pass:
1. Close the task using the method shown in CURRENT TASK (either `bd close` or prd.json update)
2. Commit your changes with format: `type(task-id): description`
3. Append learnings to @progress.txt
4. If ALL tasks are closed, output exactly:

<promise>COMPLETE</promise>

This signals the loop should terminate.
