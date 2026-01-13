#!/usr/bin/env bash
#
# PagerDuty Error Alert Hook
#
# Sends a PagerDuty incident when a curb task fails.
# This hook runs when task execution returns a non-zero exit code via the on-error hook point.
# Useful for alerting your team when the AI agent encounters problems.
#
# INSTALLATION:
#   1. Get your PagerDuty routing key from your PagerDuty account
#      Go to Services > select your service > Integrations > add Events API v2 integration
#      The routing key will be provided during setup.
#      Example: abc123def456ghi789
#
#   2. Copy this script to your hooks directory:
#      mkdir -p ~/.config/cub/hooks/on-error.d
#      cp pagerduty-alert.sh ~/.config/cub/hooks/on-error.d/01-pagerduty.sh
#      chmod +x ~/.config/cub/hooks/on-error.d/01-pagerduty.sh
#
#   3. Set your PagerDuty routing key as an environment variable:
#      export PD_ROUTING_KEY="your-routing-key"
#
#   4. Optional: Set severity level (default: error)
#      export PD_SEVERITY="critical"  # critical, error, warning, info
#
#   5. Optional: Set the dedupe key prefix for auto-resolution
#      export PD_DEDUPE_KEY_PREFIX="cub"
#
# CONTEXT VARIABLES:
#   CUB_TASK_ID       - Task ID that failed
#   CUB_TASK_TITLE    - Task title
#   CUB_EXIT_CODE     - Non-zero exit code
#   CUB_PROJECT_DIR   - Project directory
#   CUB_SESSION_ID    - Current session ID
#

set -euo pipefail

# Configuration from environment or defaults
PD_ROUTING_KEY="${PD_ROUTING_KEY:-}"
PD_SEVERITY="${PD_SEVERITY:-error}"
PD_DEDUPE_KEY_PREFIX="${PD_DEDUPE_KEY_PREFIX:-curb}"
PROJECT_DIR="${CUB_PROJECT_DIR:-.}"
TASK_ID="${CUB_TASK_ID:-unknown}"
TASK_TITLE="${CUB_TASK_TITLE:-No title}"
EXIT_CODE="${CUB_EXIT_CODE:-1}"
SESSION_ID="${CUB_SESSION_ID:-unknown}"

# Require routing key to be set
if [[ -z "$PD_ROUTING_KEY" ]]; then
    echo "Skipping PagerDuty alert: PD_ROUTING_KEY not set"
    exit 0
fi

# Get project name and git info
PROJECT_NAME=$(basename "$PROJECT_DIR")
GIT_BRANCH=$(cd "$PROJECT_DIR" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
GIT_COMMIT=$(cd "$PROJECT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_REMOTE=$(cd "$PROJECT_DIR" && git config --get remote.origin.url 2>/dev/null || echo "unknown")

# Build deduplication key for PagerDuty (prevents duplicate incidents)
# Format: curb-{project}-{task_id}-error
DEDUPE_KEY="${PD_DEDUPE_KEY_PREFIX}-${PROJECT_NAME}-${TASK_ID}-error"

# Get current timestamp in RFC3339 format
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Build the event summary
SUMMARY="Curb task failed: $TASK_TITLE (exit code: $EXIT_CODE)"

# Build PagerDuty Events API v2 payload
PAYLOAD=$(cat <<EOF
{
    "routing_key": "$PD_ROUTING_KEY",
    "event_action": "trigger",
    "dedup_key": "$DEDUPE_KEY",
    "payload": {
        "summary": "$SUMMARY",
        "severity": "$PD_SEVERITY",
        "source": "Curb AI Agent",
        "component": "$PROJECT_NAME",
        "group": "curb-tasks",
        "class": "task-failure",
        "custom_details": {
            "task_id": "$TASK_ID",
            "task_title": "$TASK_TITLE",
            "exit_code": $EXIT_CODE,
            "project": "$PROJECT_NAME",
            "branch": "$GIT_BRANCH",
            "commit": "$GIT_COMMIT",
            "git_remote": "$GIT_REMOTE",
            "session_id": "$SESSION_ID",
            "timestamp": "$TIMESTAMP"
        }
    },
    "links": [
        {
            "href": "$GIT_REMOTE",
            "text": "Repository"
        }
    ]
}
EOF
)

# Send to PagerDuty Events API v2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "https://events.pagerduty.com/v2/enqueue" \
    -H "Content-Type: application/json" \
    --data "$PAYLOAD")

if [[ "$HTTP_CODE" == "202" ]]; then
    echo "PagerDuty incident triggered successfully (HTTP $HTTP_CODE)"
    exit 0
else
    echo "Failed to trigger PagerDuty incident (HTTP $HTTP_CODE)" >&2
    exit 1
fi
