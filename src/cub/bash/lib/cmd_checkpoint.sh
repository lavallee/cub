#!/usr/bin/env bash
#
# cmd_checkpoint.sh - Checkpoint management commands for cub
#
# Provides commands for managing checkpoints (review/approval gates):
#   cub checkpoints               # List all checkpoints
#   cub checkpoints --epic <id>   # List checkpoints for an epic
#   cub checkpoint approve <id>   # Approve a checkpoint
#

# Include guard
if [[ -n "${_CUB_CMD_CHECKPOINT_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_CHECKPOINT_SH_LOADED=1

# Source checkpoints library if not already loaded
if [[ -z "${_CUB_CHECKPOINTS_SH_LOADED:-}" ]]; then
    source "${CUB_DIR}/lib/checkpoints.sh"
fi

# Colors
_checkpoint_red() { echo -e "\033[0;31m$1\033[0m"; }
_checkpoint_green() { echo -e "\033[0;32m$1\033[0m"; }
_checkpoint_yellow() { echo -e "\033[1;33m$1\033[0m"; }
_checkpoint_cyan() { echo -e "\033[0;36m$1\033[0m"; }
_checkpoint_dim() { echo -e "\033[2m$1\033[0m"; }

# Show help for checkpoints command
cmd_checkpoints_help() {
    cat <<EOF
cub checkpoints - List and manage checkpoints

Usage:
  cub checkpoints [options]

Options:
  --epic <id>        Filter by epic
  --json             Output as JSON
  --blocking         Show only blocking checkpoints
  --help             Show this help message

Subcommands:
  approve <id>       Approve (close) a checkpoint

Examples:
  cub checkpoints                       # List all checkpoints
  cub checkpoints --epic cub-vd6        # List checkpoints for epic
  cub checkpoints --blocking            # Show only blocking ones
  cub checkpoints approve cub-vd6.cp1   # Approve a checkpoint

Description:
  Checkpoints are review/approval points in workflows that block
  downstream tasks until they are approved. In beads, these are
  implemented as 'gate' type issues.

  Tasks that depend on a checkpoint cannot be started until the
  checkpoint is approved (closed). This ensures human review at
  critical points in automated workflows.
EOF
}

# List checkpoints
# Usage: cmd_checkpoints [options]
cmd_checkpoints() {
    local epic_id=""
    local json_output=false
    local blocking_only=false
    local subcommand=""
    local subcommand_args=()

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            approve)
                subcommand="approve"
                shift
                subcommand_args=("$@")
                break
                ;;
            --epic)
                shift
                epic_id="${1:-}"
                ;;
            --json)
                json_output=true
                ;;
            --blocking)
                blocking_only=true
                ;;
            --help|-h)
                cmd_checkpoints_help
                return 0
                ;;
            -*)
                echo "Unknown option: $1" >&2
                cmd_checkpoints_help >&2
                return 1
                ;;
            *)
                # Check if it's a subcommand
                if [[ "$1" == "approve" ]]; then
                    subcommand="approve"
                    shift
                    subcommand_args=("$@")
                    break
                else
                    echo "Unknown argument: $1" >&2
                    return 1
                fi
                ;;
        esac
        shift
    done

    # Handle subcommands
    case "$subcommand" in
        approve)
            _cmd_checkpoint_approve "${subcommand_args[@]}"
            return $?
            ;;
    esac

    # List checkpoints
    _cmd_checkpoints_list "$epic_id" "$json_output" "$blocking_only"
}

# List checkpoints
_cmd_checkpoints_list() {
    local epic_id="$1"
    local json_output="$2"
    local blocking_only="$3"

    local checkpoints
    checkpoints=$(checkpoint_list "$epic_id")

    if [[ "$blocking_only" == "true" ]]; then
        checkpoints=$(echo "$checkpoints" | jq '[.[] | select(.status != "closed")]')
    fi

    if [[ "$json_output" == "true" ]]; then
        echo "$checkpoints"
        return 0
    fi

    local count
    count=$(echo "$checkpoints" | jq 'length' 2>/dev/null)

    if [[ -z "$count" ]] || [[ "$count" -eq 0 ]]; then
        echo "No checkpoints found."
        echo ""
        echo "Create a checkpoint with: bd create 'Review: feature complete' --type gate"
        return 0
    fi

    local blocking approved
    blocking=$(echo "$checkpoints" | jq '[.[] | select(.status != "closed")] | length')
    approved=$(echo "$checkpoints" | jq '[.[] | select(.status == "closed")] | length')

    echo "Checkpoints ($count total, $blocking blocking, $approved approved):"
    echo ""
    printf "%-15s %-45s %-10s\n" "ID" "TITLE" "STATUS"
    printf "%-15s %-45s %-10s\n" "--" "-----" "------"

    echo "$checkpoints" | jq -r '.[] | [.id, .title, .status] | @tsv' | while IFS=$'\t' read -r id title st; do
        # Truncate title if too long
        if [[ ${#title} -gt 43 ]]; then
            title="${title:0:40}..."
        fi

        # Color status
        case "$st" in
            open|in_progress)
                st=$(_checkpoint_yellow "⊙ blocking")
                ;;
            closed)
                st=$(_checkpoint_green "✓ approved")
                ;;
            *)
                st=$(_checkpoint_dim "$st")
                ;;
        esac
        printf "%-15s %-45s %s\n" "$id" "$title" "$st"
    done

    # Show blocking summary
    if [[ "$blocking" -gt 0 ]]; then
        echo ""
        echo "Blocking checkpoints require approval before dependent tasks can start."
        echo "Approve with: cub checkpoints approve <id>"
    fi
}

# Approve a checkpoint
_cmd_checkpoint_approve() {
    local checkpoint_id=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                echo "Usage: cub checkpoints approve <checkpoint-id>"
                return 0
                ;;
            -*)
                echo "Unknown option: $1" >&2
                return 1
                ;;
            *)
                if [[ -z "$checkpoint_id" ]]; then
                    checkpoint_id="$1"
                else
                    echo "Unexpected argument: $1" >&2
                    return 1
                fi
                ;;
        esac
        shift
    done

    if [[ -z "$checkpoint_id" ]]; then
        echo "ERROR: checkpoint-id is required" >&2
        echo "Usage: cub checkpoints approve <checkpoint-id>" >&2
        return 1
    fi

    # Get checkpoint info
    local task
    task=$(get_task "" "$checkpoint_id")

    if [[ -z "$task" ]] || [[ "$task" == "null" ]]; then
        echo "ERROR: Checkpoint $checkpoint_id not found" >&2
        return 1
    fi

    local task_type task_status task_title
    task_type=$(echo "$task" | jq -r '.type // "task"')
    task_status=$(echo "$task" | jq -r '.status // "open"')
    task_title=$(echo "$task" | jq -r '.title // ""')

    # Verify it's a checkpoint type
    if ! is_checkpoint_type "$task_type"; then
        echo "ERROR: Task $checkpoint_id is not a checkpoint (type: $task_type)" >&2
        echo "Checkpoint types are: gate, checkpoint, review" >&2
        return 1
    fi

    # Check if already approved
    if [[ "$task_status" == "closed" ]]; then
        echo "Checkpoint $checkpoint_id is already approved."
        return 0
    fi

    # Show confirmation
    echo "Approving checkpoint:"
    echo "  ID: $checkpoint_id"
    echo "  Title: $task_title"
    echo "  Type: $task_type"
    echo ""

    # Get blocked tasks
    local blocked
    blocked=$(checkpoint_get_blocked "$checkpoint_id")
    local blocked_count
    blocked_count=$(echo "$blocked" | jq 'length' 2>/dev/null)

    if [[ -n "$blocked_count" ]] && [[ "$blocked_count" -gt 0 ]]; then
        echo "This will unblock $blocked_count task(s):"
        echo "$blocked" | jq -r '.[]' | while read -r id; do
            echo "  - $id"
        done
        echo ""
    fi

    # Confirm
    read -p "Approve this checkpoint? [y/N] " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        return 0
    fi

    # Close the checkpoint
    if checkpoint_approve "$checkpoint_id"; then
        _checkpoint_green "✓ Checkpoint $checkpoint_id approved"

        if [[ -n "$blocked_count" ]] && [[ "$blocked_count" -gt 0 ]]; then
            echo ""
            echo "Unblocked tasks are now ready to work on."
            echo "Run 'cub run' to continue."
        fi
    else
        echo "ERROR: Failed to approve checkpoint" >&2
        return 1
    fi
}
