# Context Variables

Hooks receive context about the current execution state through environment variables. These variables provide information about the session, task, and execution environment.

## All Variables

| Variable | Type | Hook Points | Description |
|----------|------|-------------|-------------|
| `CUB_HOOK_NAME` | string | All | Name of the current hook point |
| `CUB_PROJECT_DIR` | path | All | Absolute path to project root |
| `CUB_SESSION_ID` | string | pre-loop, post-loop | Unique session identifier |
| `CUB_HARNESS` | string | pre-loop, post-loop | AI harness name |
| `CUB_TASK_ID` | string | pre-task, post-task, on-error | Current task ID |
| `CUB_TASK_TITLE` | string | pre-task, post-task, on-error | Current task title |
| `CUB_EXIT_CODE` | integer | post-task, on-error | Task exit code |

## Variables by Hook Point

### pre-loop

```bash
CUB_HOOK_NAME="pre-loop"
CUB_SESSION_ID="porcupine-20260111-114543"
CUB_PROJECT_DIR="/home/user/my-project"
CUB_HARNESS="claude"
```

### pre-task

```bash
CUB_HOOK_NAME="pre-task"
CUB_PROJECT_DIR="/home/user/my-project"
CUB_TASK_ID="cub-abc123"
CUB_TASK_TITLE="Implement user authentication"
```

### post-task

```bash
CUB_HOOK_NAME="post-task"
CUB_PROJECT_DIR="/home/user/my-project"
CUB_TASK_ID="cub-abc123"
CUB_TASK_TITLE="Implement user authentication"
CUB_EXIT_CODE="0"
```

### on-error

```bash
CUB_HOOK_NAME="on-error"
CUB_PROJECT_DIR="/home/user/my-project"
CUB_SESSION_ID="porcupine-20260111-114543"
CUB_TASK_ID="cub-abc123"
CUB_TASK_TITLE="Implement user authentication"
CUB_EXIT_CODE="1"
```

### post-loop

```bash
CUB_HOOK_NAME="post-loop"
CUB_SESSION_ID="porcupine-20260111-114543"
CUB_PROJECT_DIR="/home/user/my-project"
CUB_HARNESS="claude"
```

## Variable Details

### CUB_HOOK_NAME

The name of the hook point being executed.

**Values**: `pre-loop`, `pre-task`, `post-task`, `on-error`, `post-loop`

**Usage**:

```bash
#!/usr/bin/env bash
# Generic hook that handles multiple points

case "$CUB_HOOK_NAME" in
    pre-task)
        echo "Starting task: $CUB_TASK_ID"
        ;;
    post-task)
        echo "Completed task: $CUB_TASK_ID with exit code $CUB_EXIT_CODE"
        ;;
    *)
        echo "Unknown hook: $CUB_HOOK_NAME"
        ;;
esac
```

### CUB_PROJECT_DIR

Absolute path to the project root directory.

**Example**: `/home/user/my-project`

**Usage**:

```bash
#!/usr/bin/env bash

# Access project files
CONFIG_FILE="$CUB_PROJECT_DIR/.cub.json"
if [[ -f "$CONFIG_FILE" ]]; then
    echo "Found project config"
fi

# Get project name
PROJECT_NAME=$(basename "$CUB_PROJECT_DIR")
echo "Project: $PROJECT_NAME"
```

### CUB_SESSION_ID

Unique identifier for the current cub session.

**Format**: `{name}-{YYYYMMDD}-{HHMMSS}`

**Examples**:
- `porcupine-20260111-114543`
- `release-1.0-20260111-120000`

**Usage**:

```bash
#!/usr/bin/env bash

# Create session-specific log file
LOG_FILE="$CUB_PROJECT_DIR/.cub/logs/$CUB_SESSION_ID.log"
mkdir -p "$(dirname "$LOG_FILE")"
echo "Session started at $(date)" >> "$LOG_FILE"

# Extract session name (before first timestamp)
SESSION_NAME="${CUB_SESSION_ID%-*-*}"
echo "Session name: $SESSION_NAME"
```

### CUB_HARNESS

The AI harness being used for task execution.

**Values**: `claude`, `codex`, `gemini`, `opencode`

**Usage**:

```bash
#!/usr/bin/env bash

case "$CUB_HARNESS" in
    claude)
        echo "Using Claude Code"
        ;;
    codex)
        echo "Using OpenAI Codex"
        ;;
    gemini)
        echo "Using Google Gemini"
        ;;
    opencode)
        echo "Using OpenCode"
        ;;
esac

# Include in metrics
TAGS="harness:$CUB_HARNESS,project:$(basename "$CUB_PROJECT_DIR")"
```

### CUB_TASK_ID

Unique identifier of the current task.

**Format**: `{prefix}-{hash}`

**Examples**: `cub-abc123`, `myproj-xyz789`

**Usage**:

```bash
#!/usr/bin/env bash

# Task-specific operations
echo "Processing task: $CUB_TASK_ID"

# Create task artifact directory
TASK_DIR="$CUB_PROJECT_DIR/.cub/runs/$CUB_SESSION_ID/tasks/$CUB_TASK_ID"
mkdir -p "$TASK_DIR"

# Use task ID in API calls
curl -X POST "https://api.example.com/tasks/$CUB_TASK_ID/status" \
    -d "status=in_progress"
```

### CUB_TASK_TITLE

Human-readable title of the current task.

**Example**: `Implement user authentication`

**Usage**:

```bash
#!/usr/bin/env bash

# Include in notifications
SLACK_MESSAGE="Task completed: $CUB_TASK_TITLE"

# Sanitize for use in filenames
SAFE_TITLE=$(echo "$CUB_TASK_TITLE" | tr ' ' '_' | tr -cd '[:alnum:]_')
```

### CUB_EXIT_CODE

Exit code from task execution.

**Values**: `0` (success) or positive integer (failure)

**Usage**:

```bash
#!/usr/bin/env bash

if [[ "$CUB_EXIT_CODE" -eq 0 ]]; then
    STATUS="success"
    COLOR="good"
else
    STATUS="failed"
    COLOR="danger"
fi

echo "Task $CUB_TASK_ID: $STATUS (exit code: $CUB_EXIT_CODE)"
```

## Using Variables in Scripts

### Safe Variable Access

Always provide defaults for potentially unset variables:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Safe defaults
PROJECT_DIR="${CUB_PROJECT_DIR:-.}"
TASK_ID="${CUB_TASK_ID:-unknown}"
EXIT_CODE="${CUB_EXIT_CODE:-0}"

# Check for required variables
if [[ -z "${CUB_SESSION_ID:-}" ]]; then
    echo "Warning: CUB_SESSION_ID not set"
    exit 0
fi
```

### Combining Variables

Build compound values from multiple variables:

```bash
#!/usr/bin/env bash

# Build unique key
DEDUP_KEY="${CUB_PROJECT_DIR##*/}-$CUB_TASK_ID-$(date +%Y%m%d)"

# Build metric tags
TAGS="project:${CUB_PROJECT_DIR##*/},harness:$CUB_HARNESS,session:$CUB_SESSION_ID"

# Build log entry
LOG_ENTRY="$(date -Iseconds) [$CUB_HOOK_NAME] task=$CUB_TASK_ID exit=$CUB_EXIT_CODE"
```

### Exporting for Child Processes

Variables are automatically available to child processes:

```bash
#!/usr/bin/env bash

# Child script inherits CUB_* variables
./my-notification-script.sh

# Or explicitly pass them
CUB_TASK_ID="$CUB_TASK_ID" python3 send_metric.py
```

## Additional Environment

Beyond CUB_* variables, hooks also have access to:

### Standard Environment

- `PATH` - System path
- `HOME` - User home directory
- `USER` - Current username
- `PWD` - Current working directory

### Git Information

Derive git context in your scripts:

```bash
#!/usr/bin/env bash

cd "$CUB_PROJECT_DIR"

# Current branch
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Current commit
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Remote URL
GIT_REMOTE=$(git config --get remote.origin.url 2>/dev/null || echo "unknown")
```

### Custom Environment

Pass custom environment variables to cub:

```bash
# Set before running cub
export MY_API_KEY="secret"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."

cub run
```

Access in hooks:

```bash
#!/usr/bin/env bash

# Use custom variables
if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
    curl -X POST "$SLACK_WEBHOOK_URL" -d "{\"text\": \"Task completed\"}"
fi
```

## Debugging Variables

To see all available variables in a hook:

```bash
#!/usr/bin/env bash
# .cub/hooks/pre-task.d/00-debug.sh

echo "=== CUB Environment Variables ==="
env | grep ^CUB_ | sort

echo ""
echo "=== All Environment Variables ==="
env | sort
```

Run with debug mode:

```bash
CUB_DEBUG=true cub run --once
```
