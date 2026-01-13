#!/usr/bin/env bash
#
# Datadog Metrics Collection Hook
#
# Submits a custom metric to Datadog when the cub loop completes.
# This hook runs after every loop completion via the post-loop hook point.
# Useful for tracking how often your AI agent successfully completes tasks.
#
# INSTALLATION:
#   1. Get your Datadog API key from https://app.datadoghq.com/organization/settings/api-keys
#      Example: abc123def456
#
#   2. Copy this script to your hooks directory:
#      mkdir -p ~/.config/cub/hooks/post-loop.d
#      cp datadog-metric.sh ~/.config/cub/hooks/post-loop.d/01-datadog.sh
#      chmod +x ~/.config/cub/hooks/post-loop.d/01-datadog.sh
#
#   3. Set your Datadog API key as an environment variable:
#      export DD_API_KEY="your-api-key"
#
#   4. Optional: Set your Datadog site (default: datadoghq.com)
#      export DD_SITE="datadoghq.com"    # for US
#      export DD_SITE="datadoghq.eu"     # for EU
#
#   5. Optional: Add custom tags
#      export DD_TAGS="env:production,service:cub"
#
# CONTEXT VARIABLES:
#   CUB_SESSION_ID    - Session ID (timestamp)
#   CUB_PROJECT_DIR   - Project directory
#   CUB_HARNESS       - Harness used (claude, codex, etc.)
#

set -euo pipefail

# Configuration from environment or defaults
DD_API_KEY="${DD_API_KEY:-}"
DD_SITE="${DD_SITE:-datadoghq.com}"
DD_TAGS="${DD_TAGS:-}"
PROJECT_DIR="${CUB_PROJECT_DIR:-.}"
SESSION_ID="${CUB_SESSION_ID:-unknown}"
HARNESS="${CUB_HARNESS:-unknown}"

# Require API key to be set
if [[ -z "$DD_API_KEY" ]]; then
    echo "Skipping Datadog metric: DD_API_KEY not set"
    exit 0
fi

# Get project name from directory
PROJECT_NAME=$(basename "$PROJECT_DIR")

# Get current git branch
GIT_BRANCH=$(cd "$PROJECT_DIR" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Build tag list
TAGS="harness:$HARNESS,project:$PROJECT_NAME,branch:$GIT_BRANCH"
if [[ -n "$DD_TAGS" ]]; then
    TAGS="${TAGS},${DD_TAGS}"
fi

# Convert tags to array format for API
# "tag1:val1,tag2:val2" -> ["tag1:val1", "tag2:val2"]
IFS=',' read -ra TAG_ARRAY <<< "$TAGS"
TAG_JSON=$(printf '%s\n' "${TAG_ARRAY[@]}" | jq -R . | jq -s .)

# Build Datadog metrics payload
# Sending two metrics:
# 1. cub.loop.completed - Counter of completed loops
# 2. cub.loop.timestamp - Timestamp gauge for tracking freshness
TIMESTAMP=$(date +%s)
PAYLOAD=$(cat <<EOF
{
    "series": [
        {
            "metric": "cub.loop.completed",
            "points": [[${TIMESTAMP}, 1]],
            "type": "gauge",
            "tags": $(echo "$TAG_JSON" | jq -c '.')
        },
        {
            "metric": "cub.loop.timestamp",
            "points": [[${TIMESTAMP}, ${TIMESTAMP}]],
            "type": "gauge",
            "tags": $(echo "$TAG_JSON" | jq -c '.')
        }
    ]
}
EOF
)

# Send to Datadog
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "https://api.${DD_SITE}/api/v1/series" \
    -H "DD-API-KEY: $DD_API_KEY" \
    -H "Content-Type: application/json" \
    --data "$PAYLOAD")

if [[ "$HTTP_CODE" == "202" ]]; then
    echo "Datadog metrics submitted successfully (HTTP $HTTP_CODE)"
    exit 0
else
    echo "Failed to submit metrics to Datadog (HTTP $HTTP_CODE)" >&2
    exit 1
fi
