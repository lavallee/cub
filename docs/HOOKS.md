# Hooks Reference

Cub provides a flexible hook system to integrate with external services, automate workflows, and extend functionality. Hooks are executable scripts that run at specific points in the cub lifecycle.

## Quick Start

```bash
# Create a post-task hook that logs completions
mkdir -p .cub/hooks/post-task.d
cat > .cub/hooks/post-task.d/01-log.sh << 'EOF'
#!/bin/bash
echo "[$(date)] Task $CUB_TASK_ID completed (exit: $CUB_EXIT_CODE)" >> .cub/hook.log
EOF
chmod +x .cub/hooks/post-task.d/01-log.sh

# Run cub - hook fires after each task
cub run --once
```

## Hook Lifecycle

Hooks fire at specific points in the cub execution flow:

```
┌─────────────────────────────────────────────────────────────┐
│                         cub run                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Initialize                                                  │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────┐                                            │
│  │  pre-loop   │ ← Runs once before main loop (sync)        │
│  └─────────────┘                                            │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Main Loop                         │    │
│  │                                                      │    │
│  │  ┌─────────────┐                                    │    │
│  │  │  pre-task   │ ← Before each task (sync)          │    │
│  │  └─────────────┘                                    │    │
│  │       │                                              │    │
│  │       ▼                                              │    │
│  │  ┌─────────────┐                                    │    │
│  │  │ Run Harness │                                    │    │
│  │  └─────────────┘                                    │    │
│  │       │                                              │    │
│  │       ├──────── Success ──────▶ ┌─────────────┐     │    │
│  │       │                         │  post-task  │     │    │
│  │       │                         │   (async)   │     │    │
│  │       │                         └─────────────┘     │    │
│  │       │                                              │    │
│  │       └──────── Failure ──────▶ ┌─────────────┐     │    │
│  │                                 │  on-error   │     │    │
│  │                                 │   (async)   │     │    │
│  │                                 └─────────────┘     │    │
│  │                                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────┐                                            │
│  │  post-loop  │ ← Runs once after loop ends (sync)         │
│  └─────────────┘                                            │
│       │                                                      │
│       ▼                                                      │
│  Wait for async hooks to complete                            │
│       │                                                      │
│       ▼                                                      │
│    Exit                                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Available Hooks

### Run Loop Hooks

| Hook | When It Fires | Execution | Common Use Cases |
|------|---------------|-----------|------------------|
| `pre-loop` | Once, before main loop starts | Sync | Branch creation, session setup, environment checks |
| `pre-task` | Before each task executes | Sync | Task-specific setup, resource allocation |
| `post-task` | After successful task completion | Async | Notifications, metrics, cleanup |
| `on-error` | When a task fails | Async | Alerts, incident creation, diagnostics |
| `on-budget-warning` | When budget crosses threshold (default 80%) | Async | Cost alerts, scaling decisions |
| `on-all-tasks-complete` | When all tasks are done | Async | Celebration, final notifications, trigger next phase |
| `post-loop` | Once, after loop ends | Sync | PR prompts, final reports, cleanup |

### Other Hooks

| Hook | When It Fires | Execution | Common Use Cases |
|------|---------------|-----------|------------------|
| `post-init` | After `cub init` completes | Sync | Custom project setup, install dependencies |

### Sync vs Async Execution

**Synchronous hooks** (`pre-loop`, `pre-task`, `post-loop`):
- Block execution until complete
- Must finish before next phase begins
- Can prevent execution if they fail (with `fail_fast: true`)

**Asynchronous hooks** (`post-task`, `on-error`):
- Fire in background without blocking
- Next task can start immediately
- All async hooks collected before session ends
- Ideal for notifications that shouldn't slow down the loop

Configure async behavior in `.cub.json`:
```json
{
  "hooks": {
    "async_notifications": false  // Force all hooks to run synchronously
  }
}
```

## Hook Locations

Hooks are discovered from two locations (in order):

1. **Global hooks**: `~/.config/cub/hooks/{hook-name}.d/`
2. **Project hooks**: `./.cub/hooks/{hook-name}.d/`

All executable files in these directories run in sorted order.

### Directory Structure

```
~/.config/cub/hooks/           # Global hooks (all projects)
├── pre-loop.d/
│   ├── 10-check-env.sh
│   └── 20-setup.sh
├── pre-task.d/
├── post-task.d/
│   └── 50-metrics.sh
├── on-error.d/
│   └── 10-pagerduty.sh
└── post-loop.d/
    └── 90-cleanup.sh

.cub/hooks/                    # Project hooks (this project only)
├── pre-loop.d/
│   └── 10-auto-branch.sh
├── pre-task.d/
├── post-task.d/
│   └── 10-slack.sh
├── on-error.d/
└── post-loop.d/
    └── 90-pr-prompt.sh
```

### Execution Order

1. Global hooks first (alphabetically sorted)
2. Project hooks second (alphabetically sorted)

Use numeric prefixes to control order:
- `01-first.sh` runs before `02-second.sh`
- `10-setup.sh`, `50-main.sh`, `90-cleanup.sh`

## Environment Variables

Hooks receive context via environment variables:

| Variable | Available In | Description |
|----------|--------------|-------------|
| `CUB_HOOK_NAME` | All | Name of the current hook |
| `CUB_PROJECT_DIR` | All | Absolute path to project directory |
| `CUB_SESSION_ID` | Run hooks | Session identifier (e.g., "cub-20260118-143022") |
| `CUB_HARNESS` | Run hooks | Harness in use (claude, codex, gemini, opencode) |
| `CUB_TASK_ID` | Task hooks | ID of current task (e.g., "beads-abc123") |
| `CUB_TASK_TITLE` | Task hooks | Title of current task |
| `CUB_EXIT_CODE` | post-task, on-error | Exit code from task (0 = success) |
| `CUB_BUDGET_PERCENTAGE` | on-budget-warning | Percentage of budget used (e.g., "85.5") |
| `CUB_BUDGET_USED` | on-budget-warning | Tokens used so far |
| `CUB_BUDGET_LIMIT` | on-budget-warning | Token budget limit |
| `CUB_INIT_TYPE` | post-init | Init type: "global" or "project" |

### Using Environment Variables

```bash
#!/bin/bash
# Handle missing variables gracefully
TASK_ID="${CUB_TASK_ID:-unknown}"
EXIT_CODE="${CUB_EXIT_CODE:-0}"

echo "Task: $TASK_ID, Exit: $EXIT_CODE"
```

## Configuration

Hook behavior is controlled in `.cub.json` or global config:

```json
{
  "hooks": {
    "enabled": true,
    "fail_fast": false,
    "async_notifications": true
  }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `true` | Enable/disable all hooks |
| `fail_fast` | `false` | Stop cub if any hook fails |
| `async_notifications` | `true` | Run post-task/on-error hooks asynchronously |

### Disable Hooks Temporarily

```bash
# Via environment variable
CUB_HOOKS_ENABLED=false cub run

# Via config
echo '{"hooks":{"enabled":false}}' > .cub.json
```

## Writing Hooks

### Basic Template

```bash
#!/usr/bin/env bash
set -euo pipefail

# Hook: post-task
# Description: Send Slack notification on task completion

# Use defaults for missing variables
TASK_ID="${CUB_TASK_ID:-unknown}"
EXIT_CODE="${CUB_EXIT_CODE:-0}"
PROJECT="${CUB_PROJECT_DIR:-$(pwd)}"

# Your logic here
echo "[my-hook] Processing task $TASK_ID"

# Exit 0 for success
exit 0
```

### Requirements

1. **Executable bit**: `chmod +x script.sh`
2. **Shebang line**: `#!/bin/bash` or `#!/usr/bin/env bash`
3. **Exit code**: Return 0 for success, non-zero for failure
4. **Handle missing vars**: Use `${VAR:-default}` pattern

### Timeout

All hooks have a **5-minute timeout** (300 seconds). For long operations:

```bash
#!/bin/bash
# Use timeout command for external calls
timeout 30 curl -s "$WEBHOOK_URL" -d "{...}" || true

# Or run in background for fire-and-forget
nohup long-running-script.sh &>/dev/null &
```

## Example Hooks

### Slack Notification (post-task)

```bash
#!/usr/bin/env bash
# .cub/hooks/post-task.d/10-slack.sh
set -euo pipefail

# Skip if no webhook configured
WEBHOOK="${SLACK_WEBHOOK_URL:-}"
if [[ -z "$WEBHOOK" ]]; then
    exit 0
fi

TASK_ID="${CUB_TASK_ID:-unknown}"
TASK_TITLE="${CUB_TASK_TITLE:-No title}"
EXIT_CODE="${CUB_EXIT_CODE:-0}"

if [[ "$EXIT_CODE" == "0" ]]; then
    EMOJI=":white_check_mark:"
    STATUS="completed"
else
    EMOJI=":x:"
    STATUS="failed"
fi

curl -s -X POST "$WEBHOOK" \
    -H 'Content-type: application/json' \
    -d "{
        \"text\": \"$EMOJI Task $STATUS: *$TASK_TITLE* ($TASK_ID)\"
    }" > /dev/null

echo "[slack] Notification sent for $TASK_ID"
```

### Auto Branch (pre-loop)

```bash
#!/usr/bin/env bash
# .cub/hooks/pre-loop.d/10-auto-branch.sh
set -euo pipefail

# Skip if not in a git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    exit 0
fi

# Skip if already on a cub branch
CURRENT=$(git branch --show-current)
if [[ "$CURRENT" == cub/* ]]; then
    exit 0
fi

# Create new branch
SESSION_ID="${CUB_SESSION_ID:-$(date +%Y%m%d-%H%M%S)}"
BRANCH="cub/$SESSION_ID"

git checkout -b "$BRANCH"
echo "$CURRENT" > .cub/.base-branch

echo "[auto-branch] Created $BRANCH (from $CURRENT)"
```

### PR Prompt (post-loop)

```bash
#!/usr/bin/env bash
# .cub/hooks/post-loop.d/90-pr-prompt.sh
set -euo pipefail

# Skip if no base branch recorded
BASE_FILE=".cub/.base-branch"
if [[ ! -f "$BASE_FILE" ]]; then
    exit 0
fi

BASE=$(cat "$BASE_FILE")
CURRENT=$(git branch --show-current)

# Check if we have commits to push
COMMITS=$(git rev-list --count "$BASE..$CURRENT" 2>/dev/null || echo 0)
if [[ "$COMMITS" == "0" ]]; then
    exit 0
fi

echo "========================================"
echo "[pr-prompt] Ready to create Pull Request"
echo "========================================"
echo "Branch:  $CURRENT"
echo "Base:    $BASE"
echo "Commits: $COMMITS ahead"
echo ""
read -p "Create PR? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    gh pr create --base "$BASE" --fill
fi
```

### PagerDuty Alert (on-error)

```bash
#!/usr/bin/env bash
# .cub/hooks/on-error.d/10-pagerduty.sh
set -euo pipefail

# Skip if no routing key
ROUTING_KEY="${PAGERDUTY_ROUTING_KEY:-}"
if [[ -z "$ROUTING_KEY" ]]; then
    exit 0
fi

TASK_ID="${CUB_TASK_ID:-unknown}"
TASK_TITLE="${CUB_TASK_TITLE:-No title}"
EXIT_CODE="${CUB_EXIT_CODE:-1}"

curl -s -X POST "https://events.pagerduty.com/v2/enqueue" \
    -H 'Content-Type: application/json' \
    -d "{
        \"routing_key\": \"$ROUTING_KEY\",
        \"event_action\": \"trigger\",
        \"payload\": {
            \"summary\": \"Cub task failed: $TASK_TITLE\",
            \"severity\": \"error\",
            \"source\": \"cub\",
            \"custom_details\": {
                \"task_id\": \"$TASK_ID\",
                \"exit_code\": \"$EXIT_CODE\"
            }
        }
    }" > /dev/null

echo "[pagerduty] Alert triggered for $TASK_ID"
```

### Budget Warning (on-budget-warning)

```bash
#!/usr/bin/env bash
# .cub/hooks/on-budget-warning.d/10-alert.sh
set -euo pipefail

PERCENTAGE="${CUB_BUDGET_PERCENTAGE:-0}"
USED="${CUB_BUDGET_USED:-0}"
LIMIT="${CUB_BUDGET_LIMIT:-0}"

echo "[budget-warning] Budget at ${PERCENTAGE}% ($USED / $LIMIT tokens)"

# Send alert via your preferred method
# Example: Slack, email, PagerDuty, etc.
if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
    curl -s -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-type: application/json' \
        -d "{\"text\": \":warning: Cub budget at ${PERCENTAGE}%\"}" > /dev/null
fi
```

### All Tasks Complete (on-all-tasks-complete)

```bash
#!/usr/bin/env bash
# .cub/hooks/on-all-tasks-complete.d/10-celebrate.sh
set -euo pipefail

SESSION_ID="${CUB_SESSION_ID:-unknown}"

echo "[complete] All tasks complete for session $SESSION_ID!"

# Send celebration notification
if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
    curl -s -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-type: application/json' \
        -d "{\"text\": \":tada: All tasks complete! Session: $SESSION_ID\"}" > /dev/null
fi

# Optionally trigger next phase
# Example: Start deployment, notify team, update status page
```

### Post Init (post-init)

```bash
#!/usr/bin/env bash
# .cub/hooks/post-init.d/10-setup.sh
set -euo pipefail

INIT_TYPE="${CUB_INIT_TYPE:-project}"
PROJECT_DIR="${CUB_PROJECT_DIR:-$(pwd)}"

echo "[post-init] Cub initialized ($INIT_TYPE)"

if [[ "$INIT_TYPE" == "project" ]]; then
    # Project-specific setup
    echo "[post-init] Setting up project hooks..."

    # Create common hook directories
    mkdir -p "$PROJECT_DIR/.cub/hooks/"{pre-loop,post-task,on-error,post-loop}.d

    # Copy team's standard hooks if available
    if [[ -d "$HOME/.cub-team-hooks" ]]; then
        cp -r "$HOME/.cub-team-hooks/"* "$PROJECT_DIR/.cub/hooks/"
        echo "[post-init] Installed team hooks"
    fi
fi
```

### Datadog Metrics (post-loop)

```bash
#!/usr/bin/env bash
# .cub/hooks/post-loop.d/50-datadog.sh
set -euo pipefail

# Skip if no API key
DD_API_KEY="${DD_API_KEY:-}"
if [[ -z "$DD_API_KEY" ]]; then
    exit 0
fi

SESSION_ID="${CUB_SESSION_ID:-unknown}"
PROJECT=$(basename "${CUB_PROJECT_DIR:-$(pwd)}")
TIMESTAMP=$(date +%s)

# Count tasks completed (from logs)
LOG_DIR="$HOME/.local/share/cub/logs/$PROJECT"
TASKS_COMPLETED=$(grep -l "task_completed" "$LOG_DIR"/*.jsonl 2>/dev/null | wc -l || echo 0)

curl -s -X POST "https://api.datadoghq.com/api/v1/series" \
    -H "Content-Type: application/json" \
    -H "DD-API-KEY: $DD_API_KEY" \
    -d "{
        \"series\": [{
            \"metric\": \"cub.session.tasks_completed\",
            \"points\": [[$TIMESTAMP, $TASKS_COMPLETED]],
            \"tags\": [\"project:$PROJECT\", \"session:$SESSION_ID\"]
        }]
    }" > /dev/null

echo "[datadog] Metrics sent: $TASKS_COMPLETED tasks"
```

## Best Practices

### 1. Make Hooks Idempotent

Hooks may run multiple times. Ensure they're safe to repeat:

```bash
# Good: Check before creating
if [[ ! -f ".cub/.setup-done" ]]; then
    do_setup
    touch .cub/.setup-done
fi

# Bad: Assumes first run
do_setup  # Might fail or duplicate on retry
```

### 2. Handle Missing Variables

Always provide defaults:

```bash
# Good
TASK_ID="${CUB_TASK_ID:-unknown}"
WEBHOOK="${SLACK_WEBHOOK_URL:-}"

# Bad
echo "Task: $CUB_TASK_ID"  # Fails if unset with set -u
```

### 3. Exit Cleanly

Always exit with explicit code:

```bash
# Good
if some_condition; then
    echo "Skipping hook"
    exit 0
fi

# Bad - implicit exit code
if some_condition; then
    echo "Skipping hook"
fi
# Exit code depends on last command
```

### 4. Use Prefixes for Logging

Make hook output identifiable:

```bash
echo "[my-hook] Starting..."
echo "[my-hook] Task: $TASK_ID"
echo "[my-hook] Done"
```

### 5. Keep Hooks Fast

Target under 30 seconds. For slow operations:

```bash
# Fire and forget (for async-safe hooks)
nohup slow-command &>/dev/null &

# Or timeout
timeout 10 slow-command || echo "[hook] Timed out"
```

### 6. Store State in `.cub/`

For inter-hook communication:

```bash
# In pre-loop hook
echo "main" > .cub/.base-branch

# In post-loop hook
BASE=$(cat .cub/.base-branch)
```

### 7. Test Locally First

Run hooks manually to verify:

```bash
# Set up environment
export CUB_HOOK_NAME="post-task"
export CUB_TASK_ID="test-123"
export CUB_TASK_TITLE="Test task"
export CUB_EXIT_CODE="0"
export CUB_PROJECT_DIR="$(pwd)"
export CUB_SESSION_ID="test-session"
export CUB_HARNESS="claude"

# Run hook
./.cub/hooks/post-task.d/10-slack.sh
```

## Troubleshooting

### Hooks Not Running

1. **Check hooks are enabled**:
   ```bash
   cat .cub.json | jq '.hooks.enabled'
   # Should be true or not set
   ```

2. **Verify executable bit**:
   ```bash
   ls -la .cub/hooks/post-task.d/
   # Look for 'x' in permissions
   chmod +x .cub/hooks/post-task.d/*.sh
   ```

3. **Check directory structure**:
   ```bash
   # Must be hook-name.d/ not just hook-name/
   ls -la .cub/hooks/
   # Should show: pre-loop.d/  post-task.d/  etc.
   ```

### Hook Fails Silently

1. **Check hook output**:
   ```bash
   # Run cub with debug flag
   cub run --debug --once 2>&1 | grep -i hook
   ```

2. **Test hook manually**:
   ```bash
   CUB_TASK_ID=test ./.cub/hooks/post-task.d/my-hook.sh
   echo "Exit code: $?"
   ```

### Hook Timeout

Hooks timeout after 300 seconds (5 minutes):

```
[hook:post-task] my-hook.sh timed out after 300 seconds
```

**Solutions**:
- Add internal timeout: `timeout 30 curl ...`
- Run in background: `nohup command &`
- Optimize the hook logic

### Hook Blocks Loop

If sync hooks are slow:

1. **Move to async hook point** (if appropriate)
2. **Add timeout**: `timeout 10 command`
3. **Run in background**: `nohup command &`

### Async Hooks Not Completing

Async hooks are collected before exit. If they hang:

```
[hook:async] Process timed out, killing...
```

**Solutions**:
- Check hook for infinite loops
- Add internal timeout
- Check external service availability

## Installing Example Hooks

Cub ships with example hooks in `examples/hooks/`:

```bash
# Install auto-branch hook (creates branch at session start)
cp examples/hooks/pre-loop.d/10-auto-branch.sh .cub/hooks/pre-loop.d/
chmod +x .cub/hooks/pre-loop.d/10-auto-branch.sh

# Install PR prompt hook (offers to create PR at session end)
cp examples/hooks/post-loop.d/90-pr-prompt.sh .cub/hooks/post-loop.d/
chmod +x .cub/hooks/post-loop.d/90-pr-prompt.sh

# Install Slack notification
cp examples/hooks/post-task.d/slack-notify.sh .cub/hooks/post-task.d/
chmod +x .cub/hooks/post-task.d/slack-notify.sh
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."
```

## See Also

- [Configuration Reference](CONFIG.md) - Full config options
- [Quick Start](QUICK_START.md) - Getting started with cub
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
