# Epic-Task Association: Canonical Approach

> **IMPORTANT**: This document explains the canonical approach for associating tasks with epics.
> Future maintainers should read this BEFORE making changes to epic/task filtering code.

## The Canonical Source: `parent` Field

**The `parent` field is THE canonical source for epic-task relationships.**

### Why `parent` is correct:

1. **First-class relationship**: The `parent` field represents a structural parent-child relationship in beads (and other backends). This is semantically correct - tasks *belong to* epics.

2. **Set at import time**: The stager (`stager.py`) correctly sets `task.parent = parsed_task.epic_id` during plan staging.

3. **Preserved by beads**: The `import_tasks` method creates `parent-child` dependencies in beads, which preserves this structural relationship.

4. **Queryable via `--parent`**: `bd list --parent epic-id` returns all tasks with that parent.

### The `epic:` Label: Compatibility Layer

The `epic:{epic_id}` label is a **compatibility layer**, not the primary source.

**Why it exists:**
- The `bd ready` command may not support `--parent` filtering
- Some older code looked for labels instead of parent
- Provides a fallback extraction path

**How it's used:**
- Added automatically during `import_tasks` for each task with a parent
- Dashboard extraction (`_extract_epic_id`) checks parent first, label as fallback
- `get_ready_tasks` uses it because `bd ready --parent` doesn't exist

## Code Locations and Their Responsibilities

### `beads.py:import_tasks`
- **Creates**: `parent-child` dependency to link task to epic
- **Creates**: `epic:{parent}` label on each task with a parent
- **Result**: Both structural relationship AND label are set

### `beads.py:list_tasks(parent=...)`
- **Uses**: `--parent` flag (structural query)
- **Correct**: This is the right approach

### `beads.py:get_ready_tasks(parent=...)`
- **Uses**: Python filtering after getting all ready tasks
- **Why**: `bd ready` doesn't support `--parent` flag
- **Fallback**: Also checks `epic:` label for backwards compatibility

### `beads.py:try_close_epic()`
- **Uses**: `list_tasks(parent=epic_id)` only
- **Why**: Structural relationship is sufficient and correct

### `dashboard/sync/parsers/tasks.py:_extract_epic_id`
- **Priority 1**: `task.parent` field
- **Priority 2**: `epic:` label (fallback for old data)
- **Correct**: Defensive approach that handles migration

### `stager.py:_convert_parsed_task_to_task`
- **Sets**: `task.parent = parsed_task.epic_id`
- **Correct**: Uses structural relationship

## Why NOT to Use Labels as Primary Source

**DO NOT flip this to use labels as the primary association mechanism.**

Reasons:
1. Labels are for categorization, not structural relationships
2. Labels can be accidentally removed or modified
3. Parent field has semantic meaning in git-like systems
4. Beads handles parent-child dependencies specially (cascade behaviors, etc.)

## Special Case: Punchlist Tasks

The **punchlist processor** (`src/cub/core/punchlist/processor.py`) intentionally uses
labels ONLY (no parent field) because:

1. `--parent` in beads creates a dependency from child to parent
2. This would block punchlist tasks until the epic closes (undesirable)
3. Punchlist tasks should be independently workable

For punchlist:
- Uses `epic:{id}` label for association
- Does NOT use parent field
- Does NOT use hierarchical IDs (epic.1, epic.2)

This is the ONE exception to the "parent field is canonical" rule. The dashboard
and filtering code handles this by checking both parent AND epic: label.

## Epic Title Format

Epic titles should be distinguishable across multiple plans. Format:

```
{plan_slug} #{epic_sequence}: {phase_name}
```

Examples:
- `auth-flow #1: Foundation`
- `auth-flow #2: Core Implementation`
- `dashboard #1: Database Layer`

This ensures:
- Plan context is always visible (which plan this epic belongs to)
- Sequence is clear (even if work isn't strictly sequential)
- Phase name describes what the epic accomplishes

## Task ID Format

Preserved from current implementation:
- Epic IDs: `{project}-{random 3 chars}` (e.g., `cub-k7m`)
- Task IDs: `{epic-id}.{n}` (e.g., `cub-k7m.1`, `cub-k7m.2`)

The task ID inherently encodes its epic relationship via the prefix.

## Migration Notes

If you find old tasks without proper parent relationships:
1. Check if they have `epic:` labels
2. If so, you can set their parent field to match
3. Going forward, both should be set via `import_tasks`

## Testing Checklist

When modifying epic/task association code, verify:
- [ ] `cub stage` creates tasks with `parent` field set
- [ ] `cub stage` creates tasks with `epic:{parent}` label
- [ ] `cub run --epic X` finds all tasks in epic X
- [ ] `bd list --parent X` returns same tasks as `bd list --label epic:X`
- [ ] Dashboard shows tasks grouped under correct epics
- [ ] `try_close_epic` correctly identifies all epic tasks
