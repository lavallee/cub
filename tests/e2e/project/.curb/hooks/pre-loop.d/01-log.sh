#!/usr/bin/env bash
# Hook to log pre-loop event

HOOK_LOG="${CURB_PROJECT_DIR}/hook_events.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [pre-loop] session=${CURB_SESSION_ID} harness=${CURB_HARNESS}" >> "$HOOK_LOG"
