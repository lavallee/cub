#!/usr/bin/env bash
# Hook to log error event

HOOK_LOG="${CURB_PROJECT_DIR}/hook_events.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [on-error] task=${CURB_TASK_ID} exit_code=${CURB_EXIT_CODE}" >> "$HOOK_LOG"
