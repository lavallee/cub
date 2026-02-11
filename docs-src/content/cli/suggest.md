---
title: cub suggest
description: Get smart recommendations for next actions based on project state.
---

# cub suggest

Analyze project state and provide prioritized recommendations for what to do next.

---

## Synopsis

```bash
cub suggest [OPTIONS]
```

---

## Description

The `suggest` command examines your project's current state and produces ranked recommendations for your next action. It considers multiple signals to surface the most impactful work:

- **Ready tasks** -- open tasks with all dependencies satisfied
- **Epic progress and momentum** -- epics that are close to completion get priority
- **Recent completions** -- what was just finished, and what naturally follows
- **Blockers** -- tasks that are blocked, and what would unblock them
- **Stale tasks** -- in-progress tasks that may have been abandoned
- **Checkpoints** -- review gates that need approval to unblock downstream work

This is useful at the start of a session when you need to decide what to work on, or when `cub run` is not being used and you want guided task selection.

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--json` | | Output recommendations as JSON for scripting |
| `--agent` | | Agent-friendly markdown output optimized for LLM consumption |
| `--verbose` | `-v` | Show detailed reasoning behind each recommendation |
| `--help` | `-h` | Show help message and exit |

---

## Examples

### Get Recommendations

```bash
cub suggest
```

Output:

```
Suggested Next Actions
━━━━━━━━━━━━━━━━━━━━━

1. Continue epic cub-049b (3/5 tasks done, momentum is high)
   → Next task: cub-049b-4 "Add retry logic to API client"

2. Unblock cub-050a by approving checkpoint gate-review-1
   → 4 tasks waiting on this review gate

3. Close stale task cub-048a-7 (in_progress for 3 days)
   → Last activity: 2026-02-08

4. Start fresh epic cub-051a (all 6 tasks ready, no blockers)
```

### Agent-Friendly Output

```bash
cub suggest --agent
```

Returns markdown formatted for LLM consumption, suitable for use inside harness sessions or with `cub run`.

### Verbose Reasoning

```bash
cub suggest --verbose
```

Shows why each recommendation was ranked where it is, including the scoring factors.

### JSON for Scripting

```bash
cub suggest --json
```

Output:

```json
{
  "suggestions": [
    {
      "rank": 1,
      "action": "continue_epic",
      "epic_id": "cub-049b",
      "task_id": "cub-049b-4",
      "reason": "Epic 3/5 complete, high momentum",
      "score": 0.92
    },
    {
      "rank": 2,
      "action": "approve_checkpoint",
      "checkpoint_id": "gate-review-1",
      "reason": "4 tasks blocked",
      "score": 0.85
    }
  ]
}
```

### Pipe to Other Commands

```bash
# Get the top suggested task ID and claim it
task_id=$(cub suggest --json | jq -r '.suggestions[0].task_id')
cub task claim "$task_id"
```

---

## Suggestion Engine

The recommendation engine is implemented in `cub.core.suggestions` and uses a multi-factor scoring system:

| Factor | Weight | Description |
|--------|--------|-------------|
| Epic momentum | High | Epics close to completion are prioritized |
| Dependency unblocking | High | Actions that unblock the most downstream tasks |
| Staleness | Medium | In-progress tasks with no recent activity |
| Task readiness | Medium | Ready tasks with no blockers |
| Recency | Low | Tasks related to recently completed work |

Scores are normalized to a 0-1 range. The top recommendations are presented in ranked order.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Suggestions generated successfully |
| `1` | Error (no task backend, configuration issue) |

---

## Related Commands

- [`cub status`](status.md) - View overall project progress
- [`cub task ready`](task.md) - List all ready tasks
- [`cub run`](run.md) - Execute tasks autonomously (uses suggestion engine internally)
- [`cub checkpoints`](checkpoints.md) - Manage review gates that may appear in suggestions

---

## See Also

- [Task Management Guide](../guide/tasks/index.md) - Understanding task states and readiness
- [Run Loop Guide](../guide/run-loop/index.md) - How the autonomous loop selects tasks
- [Dependencies](../guide/tasks/dependencies.md) - How dependency resolution works
