#!/usr/bin/env bash
#
# cmd_explain.sh - explain subcommand implementation
#

# Include guard
if [[ -n "${_CURB_CMD_EXPLAIN_SH_LOADED:-}" ]]; then
    return 0
fi
_CURB_CMD_EXPLAIN_SH_LOADED=1

cmd_explain_help() {
    cat <<'EOF'
curb explain <task-id>

Show detailed information about a specific task, including failure
reasons and blocking dependencies.

USAGE:
  curb explain <task-id>    Display full task details

OUTPUT INCLUDES:
  - Task ID and title
  - Task type (task, feature, bugfix, etc)
  - Current status (open, in_progress, closed, failed)
  - Priority level
  - Full description
  - Acceptance criteria
  - Dependencies (tasks that must be completed first)
  - Labels and other metadata

FOR FAILED TASKS:
  - Exit code from last execution
  - Failure mode (stop, move-on, retry)
  - Timestamp of failure
  - Error output (if captured)
  - Suggestions for resolution

FOR BLOCKED TASKS:
  - List of blocking dependencies with their status
  - Suggestions for unblocking

EXAMPLES:
  # View task details
  curb explain curb-018

  # Investigate why a task failed
  curb explain curb-041

  # Check what's blocking a task
  curb explain feature-42

  # Look up a task's requirements
  curb explain backend-001

SEE ALSO:
  curb status       Check overall progress
  curb run --ready  List ready tasks
  curb artifacts    Access task output files
  curb --help       Show all commands
EOF
}

cmd_explain() {
    # Check for --help first
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        cmd_explain_help
        return 0
    fi

    local target="${1:-}"
    if [[ -z "$target" ]]; then
        _log_error_console "Usage: curb explain <task-id>"
        return 1
    fi

    # Check if it's a task ID or session ID
    local backend
    backend=$(get_backend "${PROJECT_DIR}")

    # Try to get task first
    local prd="${PROJECT_DIR}/prd.json"
    local task
    task=$(get_task "$prd" "$target" 2>/dev/null) || true

    if [[ -n "$task" && "$task" != "null" ]]; then
        # Found a task - show task details
        local task_id
        task_id=$(echo "$task" | jq -r '.id')
        local task_status
        task_status=$(echo "$task" | jq -r '.status')

        echo "$task" | jq -r '
            "Task: \(.id)",
            "Title: \(.title)",
            "Type: \(.type // "task")",
            "Status: \(.status)",
            "Priority: \(.priority // "normal")",
            "",
            "Description:",
            "\(.description)",
            "",
            (if .acceptanceCriteria then "Acceptance Criteria:\n- " + (.acceptanceCriteria | join("\n- ")) else "" end),
            (if .dependsOn and (.dependsOn | length > 0) then "\nDepends on: " + (.dependsOn | join(", ")) else "" end),
            (if .labels and (.labels | length > 0) then "\nLabels: " + (.labels | join(", ")) else "" end)
        '

        # Show failure reason if task failed
        if [[ "$task_status" == "failed" ]]; then
            echo ""
            echo -e "${RED}=== Failure Information ===${NC}"

            # Look for failure.json in artifacts
            local artifacts_base="${PROJECT_DIR}/.curb/runs"
            local failure_file=""
            if [[ -d "$artifacts_base" ]]; then
                failure_file=$(find "$artifacts_base" -path "*/tasks/${task_id}/failure.json" 2>/dev/null | head -n 1)
            fi

            if [[ -n "$failure_file" && -f "$failure_file" ]]; then
                local exit_code
                exit_code=$(jq -r '.exit_code // "unknown"' "$failure_file" 2>/dev/null)
                local mode
                mode=$(jq -r '.mode // "unknown"' "$failure_file" 2>/dev/null)
                local timestamp
                timestamp=$(jq -r '.timestamp // "unknown"' "$failure_file" 2>/dev/null)
                local output
                output=$(jq -r '.output // ""' "$failure_file" 2>/dev/null)

                echo "Exit code: ${exit_code}"
                echo "Failure mode: ${mode}"
                echo "Timestamp: ${timestamp}"
                if [[ -n "$output" && "$output" != "null" && "$output" != "" ]]; then
                    echo ""
                    echo "Error output:"
                    echo "$output"
                fi
            else
                echo "No detailed failure information available."
                echo "The task may have failed before artifacts were created."
            fi

            # Provide suggestions
            echo ""
            echo -e "${YELLOW}Suggestions:${NC}"
            echo "  - Review task artifacts: curb artifacts ${task_id}"
            echo "  - Reset to open and retry: update status to 'open' in task source"
            echo "  - Check logs for more details"
        fi

        # Check for blocking dependencies
        local depends_on
        depends_on=$(echo "$task" | jq -r '.dependsOn // [] | .[]' 2>/dev/null)
        if [[ -n "$depends_on" ]]; then
            local blocking_deps=()
            while IFS= read -r dep_id; do
                if [[ -n "$dep_id" ]]; then
                    # Check if dependency is closed
                    local dep_task
                    dep_task=$(get_task "$prd" "$dep_id" 2>/dev/null)
                    if [[ -n "$dep_task" && "$dep_task" != "null" ]]; then
                        local dep_status
                        dep_status=$(echo "$dep_task" | jq -r '.status')
                        if [[ "$dep_status" != "closed" ]]; then
                            blocking_deps+=("${dep_id} (${dep_status})")
                        fi
                    else
                        blocking_deps+=("${dep_id} (not found)")
                    fi
                fi
            done <<< "$depends_on"

            if [[ ${#blocking_deps[@]} -gt 0 ]]; then
                echo ""
                echo -e "${YELLOW}=== Blocking Dependencies ===${NC}"
                echo "This task is blocked by the following dependencies:"
                for blocking in "${blocking_deps[@]}"; do
                    echo "  - ${blocking}"
                done
                echo ""
                echo -e "${YELLOW}Suggestions:${NC}"
                echo "  - Complete blocking tasks first"
                echo "  - Use 'curb explain <dep-id>' to investigate blockers"
            fi
        fi

        # Show artifacts path if available
        local artifacts_base="${PROJECT_DIR}/.curb/runs"
        if [[ -d "$artifacts_base" ]]; then
            local task_dir
            task_dir=$(find "$artifacts_base" -path "*/tasks/${task_id}" -type d 2>/dev/null | head -n 1)
            if [[ -n "$task_dir" && -d "$task_dir" ]]; then
                echo ""
                echo "Artifacts: ${task_dir}"
            fi
        fi
    else
        # Not a task, maybe a session? (future implementation)
        _log_error_console "Task not found: ${target}"
        _log_error_console "Tip: Run 'curb status' to see available tasks"
        return 1
    fi
}
