# Hook Points

Cub provides five hook points that execute at specific moments during the task lifecycle. Each hook point serves a distinct purpose and receives relevant context variables.

## Overview

| Hook Point | When It Runs | Typical Use Cases |
|------------|--------------|-------------------|
| `pre-loop` | Before the main loop starts | Setup, branch creation, cleanup |
| `pre-task` | Before each task executes | Prepare environment, start timers |
| `post-task` | After each task completes | Notifications, metrics, logging |
| `on-error` | When a task fails | Alerts, incident creation, diagnostics |
| `post-loop` | After the loop completes | Cleanup, reports, PR creation |

## pre-loop

Runs once at the beginning of a cub session, before any tasks are executed.

### When It Runs

- After configuration is loaded
- After session ID is generated
- Before the first task is selected

### Common Use Cases

- Create session branch
- Set up logging infrastructure
- Initialize external services
- Clean up from previous runs
- Validate prerequisites

### Example

```bash
#!/usr/bin/env bash
# .cub/hooks/pre-loop.d/01-setup.sh

set -euo pipefail

echo "[pre-loop] Session starting: $CUB_SESSION_ID"
echo "[pre-loop] Project: $CUB_PROJECT_DIR"
echo "[pre-loop] Harness: $CUB_HARNESS"

# Create session directory
mkdir -p "$CUB_PROJECT_DIR/.cub/sessions/$CUB_SESSION_ID"

exit 0
```

### Context Variables

| Variable | Description |
|----------|-------------|
| `CUB_HOOK_NAME` | `pre-loop` |
| `CUB_SESSION_ID` | Session identifier |
| `CUB_PROJECT_DIR` | Project root directory |
| `CUB_HARNESS` | AI harness being used |

## pre-task

Runs before each task is executed.

### When It Runs

- After a task is selected
- Before the harness is invoked
- For every task, including retries

### Common Use Cases

- Start timing/profiling
- Log task start to external systems
- Prepare task-specific resources
- Validate task requirements

### Example

```bash
#!/usr/bin/env bash
# .cub/hooks/pre-task.d/01-timer.sh

set -euo pipefail

echo "[pre-task] Starting: $CUB_TASK_ID - $CUB_TASK_TITLE"

# Record start time
echo "$(date +%s)" > "/tmp/cub-task-$CUB_TASK_ID-start"

exit 0
```

### Context Variables

| Variable | Description |
|----------|-------------|
| `CUB_HOOK_NAME` | `pre-task` |
| `CUB_PROJECT_DIR` | Project root directory |
| `CUB_TASK_ID` | Current task ID |
| `CUB_TASK_TITLE` | Current task title |

## post-task

Runs after each task completes, regardless of success or failure.

### When It Runs

- After the harness exits
- After task status is recorded
- For every task completion (success and failure)

### Common Use Cases

- Send completion notifications
- Record metrics
- Log task outcomes
- Update external trackers
- Calculate and log duration

### Example

```bash
#!/usr/bin/env bash
# .cub/hooks/post-task.d/01-metrics.sh

set -euo pipefail

# Calculate duration
START_TIME=$(cat "/tmp/cub-task-$CUB_TASK_ID-start" 2>/dev/null || echo "0")
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "[post-task] Completed: $CUB_TASK_ID"
echo "[post-task] Exit code: $CUB_EXIT_CODE"
echo "[post-task] Duration: ${DURATION}s"

# Clean up
rm -f "/tmp/cub-task-$CUB_TASK_ID-start"

exit 0
```

### Context Variables

| Variable | Description |
|----------|-------------|
| `CUB_HOOK_NAME` | `post-task` |
| `CUB_PROJECT_DIR` | Project root directory |
| `CUB_TASK_ID` | Completed task ID |
| `CUB_TASK_TITLE` | Completed task title |
| `CUB_EXIT_CODE` | Task exit code (0 = success) |

## on-error

Runs when a task fails (exits with non-zero code).

### When It Runs

- After a task exits with non-zero code
- Before post-task hooks
- Only for failed tasks

### Common Use Cases

- Create incidents in PagerDuty
- Send alert notifications
- Capture diagnostic information
- Log error context
- Notify on-call engineers

### Example

```bash
#!/usr/bin/env bash
# .cub/hooks/on-error.d/01-alert.sh

set -euo pipefail

echo "[on-error] Task failed: $CUB_TASK_ID"
echo "[on-error] Title: $CUB_TASK_TITLE"
echo "[on-error] Exit code: $CUB_EXIT_CODE"

# Capture recent git log for context
GIT_LOG=$(cd "$CUB_PROJECT_DIR" && git log -3 --oneline 2>/dev/null || echo "N/A")
echo "[on-error] Recent commits:"
echo "$GIT_LOG"

# Send alert (example: email)
# echo "Task $CUB_TASK_ID failed" | mail -s "Cub Alert" team@example.com

exit 0
```

### Context Variables

| Variable | Description |
|----------|-------------|
| `CUB_HOOK_NAME` | `on-error` |
| `CUB_PROJECT_DIR` | Project root directory |
| `CUB_TASK_ID` | Failed task ID |
| `CUB_TASK_TITLE` | Failed task title |
| `CUB_EXIT_CODE` | Non-zero exit code |
| `CUB_SESSION_ID` | Session identifier |

## post-loop

Runs once after the main loop completes.

### When It Runs

- After all tasks are processed
- After budget exhaustion
- After max iterations reached
- Before cub exits

### Common Use Cases

- Generate session reports
- Create pull requests
- Send summary notifications
- Clean up temporary files
- Report aggregate metrics

### Example

```bash
#!/usr/bin/env bash
# .cub/hooks/post-loop.d/01-summary.sh

set -euo pipefail

echo "[post-loop] Session completed: $CUB_SESSION_ID"
echo "[post-loop] Harness used: $CUB_HARNESS"

# Count commits made during session
cd "$CUB_PROJECT_DIR"
COMMIT_COUNT=$(git rev-list --count HEAD ^$(git merge-base HEAD main) 2>/dev/null || echo "0")
echo "[post-loop] Commits made: $COMMIT_COUNT"

exit 0
```

### Context Variables

| Variable | Description |
|----------|-------------|
| `CUB_HOOK_NAME` | `post-loop` |
| `CUB_SESSION_ID` | Session identifier |
| `CUB_PROJECT_DIR` | Project root directory |
| `CUB_HARNESS` | AI harness used |

## Execution Order

Within each hook point, scripts execute in sorted alphabetical order:

```
01-first.sh
02-second.sh
10-middle.sh
50-later.sh
99-last.sh
```

### Best Practices for Naming

- Use numeric prefixes for ordering: `01-`, `10-`, `50-`, `99-`
- Lower numbers run first
- Use descriptive suffixes: `01-setup.sh`, `50-notify.sh`, `99-cleanup.sh`
- Global hooks run before project hooks at the same level

### Execution Example

Given this structure:

```
~/.config/cub/hooks/post-task.d/
  01-global-metrics.sh
  50-global-notify.sh

.cub/hooks/post-task.d/
  01-project-log.sh
  99-project-cleanup.sh
```

Execution order:
1. `~/.config/cub/hooks/post-task.d/01-global-metrics.sh`
2. `~/.config/cub/hooks/post-task.d/50-global-notify.sh`
3. `.cub/hooks/post-task.d/01-project-log.sh`
4. `.cub/hooks/post-task.d/99-project-cleanup.sh`

## Return Codes

Hook scripts should exit with appropriate codes:

| Exit Code | Meaning | Behavior |
|-----------|---------|----------|
| 0 | Success | Continue execution |
| Non-zero | Failure | Log error, continue (unless fail_fast) |

### Fail Fast Mode

When `hooks.fail_fast` is enabled:

```json
{
  "hooks": {
    "fail_fast": true
  }
}
```

Any non-zero exit code stops the cub loop immediately.

### Graceful Error Handling

Scripts should handle errors gracefully:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Check prerequisites
if [[ -z "${SLACK_WEBHOOK_URL:-}" ]]; then
    echo "[hook] SLACK_WEBHOOK_URL not set, skipping"
    exit 0  # Exit 0 to not block execution
fi

# Do the work
if ! curl -X POST "$SLACK_WEBHOOK_URL" ...; then
    echo "[hook] Failed to send Slack notification" >&2
    exit 0  # Exit 0 if notification is non-critical
fi

exit 0
```

## Timeout Handling

Hooks should complete within a reasonable time. Long-running hooks can:

- Delay task execution
- Block the loop
- Accumulate across iterations

### Best Practices

1. Keep hooks fast (under 5 seconds)
2. Use background processes for slow operations
3. Add timeouts to network calls

```bash
# Use timeout for network operations
timeout 5 curl -X POST "$WEBHOOK_URL" || true
```
