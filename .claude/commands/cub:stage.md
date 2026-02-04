# Stage: Import Plan Tasks

You are executing the cub stage command, which bridges planning and execution by importing tasks from a completed plan into the task backend (beads or JSON).

## Arguments

$ARGUMENTS

## Instructions

Determine the right command flags from the user's input:

| Input | Command |
|-------|---------|
| (empty) / "stage" / "import" | `cub stage` (stages most recent complete plan) |
| a plan slug like `my-feature` | `cub stage <slug>` |
| a file path ending in `.md` | `cub stage <path>` (stages standalone itemized plan) |
| "list" / "show plans" / "available" | `cub stage --list` |
| "dry run" / "preview" / "what if" | `cub stage --dry-run` |
| "verbose" / "details" | `cub stage --verbose` |

## What Stage Does

1. **Validates** the plan is complete (orient, architect, itemize stages done)
2. **Parses** the `itemized-plan.md` file in the plan directory
3. **Imports** epics and tasks into the task backend
4. **Updates** the plan status to STAGED
5. **Generates** context files (`prompt-context.md`, `agent.md`)

## Prerequisites

- A plan must be **complete** (all planning stages finished)
- The `itemized-plan.md` file must exist
- A task backend must be configured (beads or JSON)

## Examples

```bash
# Stage the most recent complete plan
cub stage

# Stage a specific plan by slug
cub stage my-feature-plan

# Preview what would be staged without importing
cub stage --dry-run

# List all plans ready to be staged
cub stage --list

# Stage a standalone itemized plan file (e.g., from punchlist)
cub stage path/to/itemized-plan.md

# Stage with verbose output
cub stage --verbose
```

## After Staging

Once staging completes successfully:
- Tasks are created in the task backend
- Run `cub run` to start executing tasks
- Use `cub task ready` to see available tasks

Run the command via Bash. If staging fails due to an incomplete plan, suggest running `cub plan run <spec>` first.
