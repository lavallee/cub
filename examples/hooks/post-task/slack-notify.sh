#!/usr/bin/env bash
#
# Slack Task Notification Hook
#
# Posts a message to Slack when a task completes (success or failure).
# This hook runs after every task execution via the post-task hook point.
#
# INSTALLATION:
#   1. Get your Slack webhook URL from https://api.slack.com/messaging/webhooks
#      Example: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
#
#   2. Copy this script to your hooks directory:
#      mkdir -p ~/.config/curb/hooks/post-task.d
#      cp slack-notify.sh ~/.config/curb/hooks/post-task.d/01-slack.sh
#      chmod +x ~/.config/curb/hooks/post-task.d/01-slack.sh
#
#   3. Set the webhook URL as an environment variable:
#      export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
#
#   4. Optional: Set the channel name (default: @curb-notifications)
#      export SLACK_CHANNEL="@your-channel"
#
# CONTEXT VARIABLES:
#   CURB_TASK_ID       - Task ID (e.g., "curb-abc123")
#   CURB_TASK_TITLE    - Task title
#   CURB_EXIT_CODE     - Exit code from task execution (0 = success)
#   CURB_PROJECT_DIR   - Project directory
#

set -euo pipefail

# Configuration from environment or defaults
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
SLACK_CHANNEL="${SLACK_CHANNEL:-@curb-notifications}"
PROJECT_DIR="${CURB_PROJECT_DIR:-.}"
TASK_ID="${CURB_TASK_ID:-unknown}"
TASK_TITLE="${CURB_TASK_TITLE:-No title}"
EXIT_CODE="${CURB_EXIT_CODE:-0}"

# Require webhook URL to be set
if [[ -z "$SLACK_WEBHOOK_URL" ]]; then
    echo "Skipping Slack notification: SLACK_WEBHOOK_URL not set"
    exit 0
fi

# Determine status and color based on exit code
if [[ "$EXIT_CODE" -eq 0 ]]; then
    STATUS="✅ Success"
    COLOR="good"
else
    STATUS="❌ Failed"
    COLOR="danger"
fi

# Get current git branch and commit
GIT_BRANCH=$(cd "$PROJECT_DIR" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
GIT_COMMIT=$(cd "$PROJECT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Build Slack message payload
PAYLOAD=$(cat <<EOF
{
    "channel": "$SLACK_CHANNEL",
    "attachments": [
        {
            "color": "$COLOR",
            "title": "Task Completed: $TASK_TITLE",
            "title_link": "https://example.com",
            "fields": [
                {
                    "title": "Task ID",
                    "value": "$TASK_ID",
                    "short": true
                },
                {
                    "title": "Status",
                    "value": "$STATUS",
                    "short": true
                },
                {
                    "title": "Exit Code",
                    "value": "$EXIT_CODE",
                    "short": true
                },
                {
                    "title": "Branch",
                    "value": "$GIT_BRANCH",
                    "short": true
                },
                {
                    "title": "Project",
                    "value": "$(basename "$PROJECT_DIR")",
                    "short": true
                },
                {
                    "title": "Commit",
                    "value": "$GIT_COMMIT",
                    "short": true
                }
            ],
            "footer": "Curb Task Notifications",
            "ts": $(date +%s)
        }
    ]
}
EOF
)

# Send to Slack
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H 'Content-type: application/json' \
    --data "$PAYLOAD" \
    "$SLACK_WEBHOOK_URL")

if [[ "$HTTP_CODE" == "200" ]]; then
    echo "Slack notification sent successfully (HTTP $HTTP_CODE)"
    exit 0
else
    echo "Failed to send Slack notification (HTTP $HTTP_CODE)" >&2
    exit 1
fi
