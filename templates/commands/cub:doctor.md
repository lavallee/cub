# Doctor: Diagnose Project Health

You are running cub's diagnostic tool to check configuration, hooks, and project health.

## Arguments

$ARGUMENTS

## Instructions

Run `cub doctor --agent` via Bash and present the results clearly.

The `--agent` flag provides structured markdown output optimized for LLM consumption.

If the doctor reports issues, explain what each problem means and suggest fixes. Common issues include:
- Missing or misconfigured hooks (fix: `cub hooks install`)
- Missing task backend configuration
- Stale epics with all subtasks complete (fix: `cub doctor --fix`)
