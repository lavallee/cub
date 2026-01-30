---
status: draft
priority: high
complexity: low
dependencies: []
blocks:
  - agent-output-and-nl-routing
created: 2026-01-29
updated: 2026-01-29
readiness:
  score: 7
  blockers:
    - Need to audit full bd command surface for completeness
  questions:
    - Should cub task create support the full bd create flag set or start minimal?
    - Do we want cub task dep to mirror bd dep exactly or simplify the interface?
  decisions_needed:
    - Whether to deprecate direct bd usage in docs/skills or just prefer cub task
    - How to handle bd-specific features that don't map cleanly (labels, custom fields)
---

# cub task: Full Task Management Parity

## Overview

Make `cub task` the complete, authoritative interface for all task management operations. Currently, several common operations require dropping down to `bd` (beads CLI) directly — creating tasks, managing dependencies, listing blocked work. This creates a leaky abstraction: skills and docs reference `bd` commands, users need to know two CLIs, and the `--agent` output optimization can only apply to commands we control.

## Goals

- Add missing `cub task` subcommands to cover all common task operations
- Make `cub task` the only task interface referenced in skills, docs, and CLAUDE.md
- Ensure every subcommand supports `--json` and `--agent` output flags
- Keep `bd` as the underlying backend — `cub task` wraps it, doesn't replace it

## Non-Goals

- Replacing beads as a backend — cub task is a frontend to the task backend protocol
- Supporting every obscure bd flag — focus on the 90% use case
- Changing the task backend protocol (`cub.core.tasks.backend`)
- Migration tooling from bd to cub task — they coexist

## Design / Approach

### Gap Analysis

| Operation | bd command | cub task equivalent | Status |
|-----------|-----------|-------------------|--------|
| List ready tasks | `bd ready` | `cub task ready` | Exists |
| Show task details | `bd show <id>` | `cub task show <id>` | Exists |
| List tasks (filtered) | `bd list --status open` | `cub task list --status open` | Exists |
| Claim task | `bd update <id> --status in_progress` | `cub task claim <id>` | Exists |
| Close task | `bd close <id>` | `cub task close <id>` | Exists |
| Task counts/stats | `bd stats` | `cub task counts` | Exists |
| **Create task** | `bd create --title "..." --type task` | — | **Missing** |
| **Show blocked tasks** | `bd blocked` | — | **Missing** |
| **Add dependency** | `bd dep add <a> <b>` | — | **Missing** |
| **Remove dependency** | `bd dep remove <a> <b>` | — | **Missing** |
| **Update task fields** | `bd update <id> --title/--description/--notes` | — | **Missing** |
| **Add/remove labels** | `bd label add/remove <id> <label>` | — | **Missing** |
| **List by epic** | `bd list --parent <epic>` | — | **Missing** (could be `--epic` filter) |
| **Set priority** | `bd update <id> --priority 1` | — | **Missing** (could be part of update) |

### New Subcommands

**`cub task create`**
```bash
cub task create "Implement caching layer" \
  --type task \
  --priority 2 \
  --epic cub-abc \
  --description "Add Redis caching for API responses"
```
Wraps `bd create`. Returns the created task ID.

**`cub task blocked`**
```bash
cub task blocked              # All blocked tasks
cub task blocked --epic abc   # Blocked within an epic
```
Wraps `bd blocked`. With `--agent`, includes root blocker analysis and chain lengths.

**`cub task update`**
```bash
cub task update cub-042 --title "New title"
cub task update cub-042 --description "Updated description"
cub task update cub-042 --priority 1
cub task update cub-042 --notes "Added context from discussion"
```
Wraps `bd update`. Accepts individual field flags.

**`cub task dep`**
```bash
cub task dep add cub-042 cub-041    # 042 depends on 041
cub task dep remove cub-042 cub-041 # Remove dependency
cub task dep show cub-042           # Show what blocks/is blocked by
```
Wraps `bd dep`. With `--agent`, includes chain visualization.

**`cub task label`**
```bash
cub task label add cub-042 model:sonnet
cub task label remove cub-042 model:sonnet
cub task label list cub-042
```
Wraps `bd label`.

### Enhanced Existing Subcommands

**`cub task list` — add filters**:
```bash
cub task list --epic cub-abc        # Filter by epic
cub task list --label model:haiku   # Filter by label
cub task list --priority 0          # Filter by priority
cub task list --assignee me         # Filter by assignee
```

**`cub task ready` — add ordering**:
```bash
cub task ready --by impact          # Order by unblock count (default with --agent)
cub task ready --by priority        # Order by priority number
cub task ready --epic cub-abc       # Ready tasks within an epic
```

## Implementation Notes

### Architecture

All new subcommands follow the existing pattern in `src/cub/cli/task.py`:

```python
@app.command()
def blocked(
    epic: str | None = typer.Option(None, "--epic", help="Filter by epic"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    agent: bool = typer.Option(False, "--agent", help="Agent-optimized output"),
) -> None:
    """Show blocked tasks and their dependency chains."""
    backend = get_task_backend(project_dir)
    tasks = backend.list_blocked_tasks()  # May need to add to protocol

    if agent:
        console.print(AgentFormatter.format_blocked(tasks))
        return
    if json_output:
        console.print(json.dumps([t.model_dump(mode="json") for t in tasks]))
        return
    # Rich table output...
```

### Task Backend Protocol

Some operations may need additions to the `TaskBackend` protocol in `cub.core.tasks.backend`:

- `list_blocked_tasks()` — currently only available via `bd blocked`
- `create_task(title, type, priority, parent)` — may already exist
- `add_dependency(task_id, depends_on)` — may need adding
- `update_task(task_id, **fields)` — may already exist

For operations not in the protocol, the beads backend implementation can shell out to `bd` directly as an interim step, then add protocol methods as needed.

### Output Flags

Every subcommand gets three output modes:
1. Default: Rich tables/panels (human terminal)
2. `--json`: Full Pydantic model dump (scripts/APIs)
3. `--agent`: Structured markdown with analysis (LLM consumption)

### Skill and Doc Updates

Once parity is achieved:
- Update `.claude/commands/cub:tasks.md` to cover new subcommands
- Update `.claude/commands/cub.md` router to use `cub task blocked` instead of `bd blocked`
- Update CLAUDE.md to prefer `cub task` over `bd` in all examples
- Update `.cub/PROMPT.md` runloop instructions

## Open Questions

1. **Protocol vs shell-out**: Should new operations go through the TaskBackend protocol or shell out to `bd` directly? Protocol is cleaner but more work. Shell-out is faster to implement but couples to beads.

   **Recommendation**: Shell out for v1, add protocol methods in a follow-up. The protocol should be the target, but getting the commands working quickly has more value.

2. **`cub task create` complexity**: `bd create` has many flags (type, priority, parent, labels, description, notes, design, assignee). Should `cub task create` expose all of them or start with a minimal set?

   **Recommendation**: Start with `--title` (positional), `--type`, `--priority`, `--epic`. Add others as needed.

3. **Deprecation of direct bd usage**: Should we warn when skills/docs reference `bd` directly?

   **Recommendation**: Not yet. Just make `cub task` the preferred interface in new content. `bd` remains available for power users and edge cases.

## Future Considerations

- **Interactive task creation**: `cub task create --interactive` could walk through fields with prompts, similar to `gh issue create`
- **Bulk operations**: `cub task close cub-041 cub-042 cub-043` for closing multiple tasks
- **Task templates**: `cub task create --template test-task` for common task shapes
- **Smart defaults**: `cub task create` in an epic branch auto-sets `--epic` from branch binding

---

**Status**: draft
**Last Updated**: 2026-01-29
