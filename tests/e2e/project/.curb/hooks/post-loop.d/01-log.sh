#!/usr/bin/env bash
# Hook to log post-loop event

HOOK_LOG="${CURB_PROJECT_DIR}/hook_events.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [post-loop] session=${CURB_SESSION_ID}" >> "$HOOK_LOG"
