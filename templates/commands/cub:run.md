# Run: Execute Tasks

You are launching cub's autonomous task execution loop. Determine the right flags from the user's input.

## Arguments

$ARGUMENTS

## Instructions

| Input | Command |
|-------|---------|
| (empty) / "once" / "one task" | `cub run --once` |
| "all" / "everything" / "loop" / "autonomous" | `cub run` |
| a task ID like `cub-xxx` | `cub run --task <id>` |
| an epic ID | `cub run --epic <id>` |
| "stream" / "watch" | `cub run --once --stream` |

**Before running**, confirm with the user what will be executed, since `cub run` launches a potentially long-running autonomous process.

For `--once` (single iteration), proceed immediately.
For full `cub run` (autonomous loop), confirm first: "This will run the autonomous loop until all ready tasks are complete. Proceed?"
