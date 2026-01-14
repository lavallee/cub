#!/usr/bin/env bash
#
# checkpoints.sh - Checkpoint/Gate task management for cub
#
# Checkpoints are review/approval points in workflows that block downstream
# tasks until they are approved (closed). In beads, these are implemented
# as 'gate' type issues.
#
# Usage:
#   checkpoint_is_blocking <checkpoint_id>  # Check if checkpoint is blocking
#   checkpoint_get_blocked <checkpoint_id>  # Get tasks blocked by checkpoint
#   checkpoint_list [epic_id]               # List all checkpoints
#   checkpoint_approve <checkpoint_id>      # Approve (close) a checkpoint
#

# Include guard
if [[ -n "${_CUB_CHECKPOINTS_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CHECKPOINTS_SH_LOADED=1

# Checkpoint types (gate is the beads equivalent)
CHECKPOINT_TYPES=("checkpoint" "gate" "review")

# Check if a task is a checkpoint type
# Usage: is_checkpoint_type <type>
# Returns: 0 if checkpoint type, 1 otherwise
is_checkpoint_type() {
    local task_type="$1"
    local t
    for t in "${CHECKPOINT_TYPES[@]}"; do
        if [[ "$task_type" == "$t" ]]; then
            return 0
        fi
    done
    return 1
}

# Check if a checkpoint is blocking (not yet approved/closed)
# Usage: checkpoint_is_blocking <checkpoint_id> [prd_file]
# Returns: 0 if blocking, 1 if not blocking
checkpoint_is_blocking() {
    local checkpoint_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$checkpoint_id" ]]; then
        return 1
    fi

    # Get checkpoint task
    local task
    task=$(get_task "$prd" "$checkpoint_id")

    if [[ -z "$task" ]] || [[ "$task" == "null" ]]; then
        return 1  # Task doesn't exist, not blocking
    fi

    local task_type task_status
    task_type=$(echo "$task" | jq -r '.type // "task"')
    task_status=$(echo "$task" | jq -r '.status // "open"')

    # Check if it's a checkpoint type
    if ! is_checkpoint_type "$task_type"; then
        return 1  # Not a checkpoint type
    fi

    # Checkpoint is blocking if not closed
    if [[ "$task_status" != "closed" ]]; then
        return 0  # Blocking
    fi

    return 1  # Not blocking (already closed/approved)
}

# Get tasks blocked by a checkpoint
# Usage: checkpoint_get_blocked <checkpoint_id> [prd_file]
# Returns: JSON array of blocked task IDs
checkpoint_get_blocked() {
    local checkpoint_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$checkpoint_id" ]]; then
        echo "[]"
        return 1
    fi

    # Use beads to find tasks that depend on this checkpoint
    if command -v bd >/dev/null 2>&1; then
        local blocked_by
        blocked_by=$(bd show "$checkpoint_id" --json 2>/dev/null | jq -r '.blocked_by // []')
        if [[ -n "$blocked_by" ]] && [[ "$blocked_by" != "null" ]]; then
            echo "$blocked_by"
            return 0
        fi
    fi

    # Fall back to finding tasks with this as a dependency
    if [[ -f "$prd" ]]; then
        jq -r --arg id "$checkpoint_id" '[.tasks[] | select(.dependsOn[]? == $id) | .id]' "$prd" 2>/dev/null || echo "[]"
    else
        echo "[]"
    fi
}

# List all checkpoints
# Usage: checkpoint_list [epic_id] [prd_file]
# Returns: JSON array of checkpoint tasks
checkpoint_list() {
    local epic_id="${1:-}"
    local prd="${2:-prd.json}"

    local filter=""
    if [[ -n "$epic_id" ]]; then
        filter="--parent $epic_id"
    fi

    # Use beads if available
    if command -v bd >/dev/null 2>&1; then
        local result="[]"
        local types=("gate" "checkpoint" "review")

        for t in "${types[@]}"; do
            local tasks
            tasks=$(bd list --type "$t" --json $filter 2>/dev/null)
            if [[ -n "$tasks" ]] && [[ "$tasks" != "null" ]] && [[ "$tasks" != "[]" ]]; then
                result=$(echo "$result $tasks" | jq -s 'add')
            fi
        done

        echo "$result"
        return 0
    fi

    # Fall back to JSON backend
    if [[ -f "$prd" ]]; then
        local types_filter='["gate", "checkpoint", "review"]'
        if [[ -n "$epic_id" ]]; then
            jq --arg epic "$epic_id" --argjson types "$types_filter" '
                [.tasks[] | select(.type as $t | $types | index($t)) | select(.parent == $epic or .epic == $epic)]
            ' "$prd" 2>/dev/null || echo "[]"
        else
            jq --argjson types "$types_filter" '
                [.tasks[] | select(.type as $t | $types | index($t))]
            ' "$prd" 2>/dev/null || echo "[]"
        fi
    else
        echo "[]"
    fi
}

# Approve (close) a checkpoint
# Usage: checkpoint_approve <checkpoint_id> [prd_file]
# Returns: 0 on success, 1 on error
checkpoint_approve() {
    local checkpoint_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$checkpoint_id" ]]; then
        echo "ERROR: checkpoint_id is required" >&2
        return 1
    fi

    # Get checkpoint task
    local task
    task=$(get_task "$prd" "$checkpoint_id")

    if [[ -z "$task" ]] || [[ "$task" == "null" ]]; then
        echo "ERROR: Checkpoint $checkpoint_id not found" >&2
        return 1
    fi

    local task_type
    task_type=$(echo "$task" | jq -r '.type // "task"')

    if ! is_checkpoint_type "$task_type"; then
        echo "ERROR: Task $checkpoint_id is not a checkpoint (type: $task_type)" >&2
        return 1
    fi

    # Update status to closed
    update_task_status "$prd" "$checkpoint_id" "closed"
}

# Get checkpoint summary
# Usage: checkpoint_summary [epic_id] [prd_file]
# Returns: Human-readable summary
checkpoint_summary() {
    local epic_id="${1:-}"
    local prd="${2:-prd.json}"

    local checkpoints
    checkpoints=$(checkpoint_list "$epic_id" "$prd")

    local total blocking approved
    total=$(echo "$checkpoints" | jq 'length')

    if [[ -z "$total" ]] || [[ "$total" -eq 0 ]]; then
        echo "No checkpoints found."
        return 0
    fi

    # Count by status
    blocking=$(echo "$checkpoints" | jq '[.[] | select(.status != "closed")] | length')
    approved=$(echo "$checkpoints" | jq '[.[] | select(.status == "closed")] | length')

    echo "Checkpoints: $total total, $blocking blocking, $approved approved"

    # List blocking checkpoints
    if [[ "$blocking" -gt 0 ]]; then
        echo ""
        echo "Blocking checkpoints:"
        echo "$checkpoints" | jq -r '.[] | select(.status != "closed") | "  ⊙ \(.id): \(.title)"'
    fi
}

# Check if any task is blocked by an unapproved checkpoint
# Usage: is_task_blocked_by_checkpoint <task_id> [prd_file]
# Returns: 0 if blocked by checkpoint, 1 if not
is_task_blocked_by_checkpoint() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$task_id" ]]; then
        return 1
    fi

    # Get task dependencies
    local task
    task=$(get_task "$prd" "$task_id")

    if [[ -z "$task" ]] || [[ "$task" == "null" ]]; then
        return 1
    fi

    local deps
    deps=$(echo "$task" | jq -r '.dependsOn // []')

    if [[ "$deps" == "[]" ]] || [[ "$deps" == "null" ]]; then
        return 1
    fi

    # Check each dependency
    local dep_id
    for dep_id in $(echo "$deps" | jq -r '.[]'); do
        if checkpoint_is_blocking "$dep_id" "$prd"; then
            return 0  # Blocked by checkpoint
        fi
    done

    return 1  # Not blocked by checkpoint
}

# Get the checkpoint blocking a task (if any)
# Usage: get_blocking_checkpoint <task_id> [prd_file]
# Returns: Checkpoint ID or empty
get_blocking_checkpoint() {
    local task_id="$1"
    local prd="${2:-prd.json}"

    if [[ -z "$task_id" ]]; then
        echo ""
        return 1
    fi

    # Get task dependencies
    local task
    task=$(get_task "$prd" "$task_id")

    if [[ -z "$task" ]] || [[ "$task" == "null" ]]; then
        echo ""
        return 1
    fi

    local deps
    deps=$(echo "$task" | jq -r '.dependsOn // []')

    if [[ "$deps" == "[]" ]] || [[ "$deps" == "null" ]]; then
        echo ""
        return 1
    fi

    # Check each dependency
    local dep_id
    for dep_id in $(echo "$deps" | jq -r '.[]'); do
        if checkpoint_is_blocking "$dep_id" "$prd"; then
            echo "$dep_id"
            return 0
        fi
    done

    echo ""
    return 1
}
