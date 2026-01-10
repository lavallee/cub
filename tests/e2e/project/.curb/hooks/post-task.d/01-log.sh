#!/usr/bin/env bash
# Hook to log post-task event

HOOK_LOG="${CURB_PROJECT_DIR}/hook_events.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [post-task] task=${CURB_TASK_ID} exit_code=${CURB_EXIT_CODE}" >> "$HOOK_LOG"
