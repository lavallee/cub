#!/usr/bin/env bash
# Hook to log post-task event

HOOK_LOG="${CUB_PROJECT_DIR}/hook_events.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [post-task] task=${CUB_TASK_ID} exit_code=${CUB_EXIT_CODE}" >> "$HOOK_LOG"
