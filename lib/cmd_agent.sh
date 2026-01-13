#!/usr/bin/env bash
#
# cmd_agent.sh - agent helper subcommands
#

# Include guard
if [[ -n "${_CUB_CMD_AGENT_SH_LOADED:-}" ]]; then
    return 0
fi
_CUB_CMD_AGENT_SH_LOADED=1

cmd_agent_close_help() {
    cat <<'EOF'
cub agent-close <task-id>

Mark a task as closed (complete). This command is backend-aware and works
with both beads and prd.json backends.

USAGE:
  cub agent-close <task-id>    Mark the specified task as closed

DESCRIPTION:
  This command is designed to be called by the AI agent during task
  completion. It automatically detects the task backend (beads or json)
  and uses the appropriate method to close the task.

  For beads backend:  Runs 'bd close <task-id>'
  For json backend:   Updates prd.json to set status="closed"

EXAMPLES:
  cub agent-close cub-018
  cub agent-close link-030

SEE ALSO:
  cub agent-verify   Verify a task is properly closed
  cub status         Check overall progress
  cub explain        Show task details
EOF
}

cmd_agent_close() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_agent_close_help
        return 0
    fi

    local task_id="${1:-}"
    if [[ -z "$task_id" ]]; then
        _log_error_console "Usage: cub agent-close <task-id>"
        return 1
    fi

    local prd="${PROJECT_DIR}/prd.json"
    local backend
    backend=$(get_backend "${PROJECT_DIR}")

    if [[ "$backend" == "beads" ]]; then
        log_info "Closing task $task_id via beads..."
        if bd close "$task_id" 2>&1; then
            log_success "Task $task_id closed"
            return 0
        else
            _log_error_console "Failed to close task $task_id"
            return 1
        fi
    else
        log_info "Closing task $task_id in prd.json..."
        if json_update_task_status "$prd" "$task_id" "closed"; then
            log_success "Task $task_id closed"
            return 0
        else
            _log_error_console "Failed to close task $task_id"
            return 1
        fi
    fi
}

cmd_agent_verify_help() {
    cat <<'EOF'
cub agent-verify <task-id>

Verify that a task is properly marked as closed. This command is backend-aware
and works with both beads and prd.json backends.

USAGE:
  cub agent-verify <task-id>    Check if the task status is "closed"

DESCRIPTION:
  This command verifies that a task has been properly closed. It's designed
  to be called by the AI agent after closing a task to confirm the operation
  succeeded.

  Returns exit code 0 if task is closed, 1 otherwise.

EXAMPLES:
  cub agent-verify cub-018
  cub agent-verify link-030

  # In scripts:
  if cub agent-verify cub-018; then
    echo "Task is closed"
  else
    echo "Task is NOT closed"
  fi

SEE ALSO:
  cub agent-close    Close a task
  cub status         Check overall progress
  cub explain        Show task details
EOF
}

cmd_agent_verify() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_agent_verify_help
        return 0
    fi

    local task_id="${1:-}"
    if [[ -z "$task_id" ]]; then
        _log_error_console "Usage: cub agent-verify <task-id>"
        return 1
    fi

    local prd="${PROJECT_DIR}/prd.json"

    if verify_task_closed "$prd" "$task_id"; then
        log_success "Task $task_id is closed"
        return 0
    else
        _log_error_console "Task $task_id is NOT closed"
        return 1
    fi
}
