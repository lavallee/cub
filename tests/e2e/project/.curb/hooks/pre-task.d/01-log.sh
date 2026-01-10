#!/usr/bin/env bash
# Hook to log pre-task event

HOOK_LOG="${CURB_PROJECT_DIR}/hook_events.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [pre-task] task=${CURB_TASK_ID} title=\"${CURB_TASK_TITLE}\"" >> "$HOOK_LOG"
