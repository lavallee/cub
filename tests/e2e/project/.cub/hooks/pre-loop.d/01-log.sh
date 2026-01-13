#!/usr/bin/env bash
# Hook to log pre-loop event

HOOK_LOG="${CUB_PROJECT_DIR}/hook_events.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [pre-loop] session=${CUB_SESSION_ID} harness=${CUB_HARNESS}" >> "$HOOK_LOG"
