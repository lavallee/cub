#!/usr/bin/env bash
# Hook to log pre-task event

HOOK_LOG="${CUB_PROJECT_DIR}/hook_events.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [pre-task] task=${CUB_TASK_ID} title=\"${CUB_TASK_TITLE}\"" >> "$HOOK_LOG"
