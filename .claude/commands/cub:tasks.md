# Tasks: View and Manage Tasks

You are executing a cub task command. Run the appropriate subcommand based on the user's input and present the results.

## Arguments

$ARGUMENTS

## Instructions

Determine the right subcommand from the arguments:

| Input | Command |
|-------|---------|
| (empty) / "ready" / "available" / "priority" | `cub task ready` |
| a task ID like `cub-xxx` or `beads-xxx` | `cub task show <id> --full` |
| "list" / "all" / "open" | `cub task list --status open` |
| "claim \<id\>" / "start \<id\>" | `cub task claim <id>` |
| "close \<id\>" with a reason | `cub task close <id> -r "<reason>"` |
| "blocked" / "blockers" | `bd blocked` |

Run the command via Bash. Present the output clearly. If the user provides something ambiguous, default to `cub task ready`.
