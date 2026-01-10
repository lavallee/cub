#!/usr/bin/env bash
#
# artifacts.sh - Artifact directory management
#
# Provides functions for managing artifact bundles that provide
# observability into each task's execution. Artifacts are stored
# in .curb/runs/{session-id}/tasks/{task-id}/ structure.
#
# Functions:
#   artifacts_get_run_dir() - Get the directory for the current run
#   artifacts_get_task_dir(task_id) - Get the directory for a specific task
#   artifacts_ensure_dirs(task_id) - Ensure directory structure exists
#   artifacts_init_run() - Initialize run-level artifacts and create run.json
#   artifacts_start_task(task_id, task_title, priority) - Start task and create task.json
#

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/session.sh"
source "${SCRIPT_DIR}/xdg.sh"

# Base directory for artifacts (relative to project root)
_ARTIFACTS_BASE_DIR=".curb/runs"

# Get the directory for the current run
# Returns: path to run directory (.curb/runs/{session-id})
#
# Returns:
#   Path to run directory on success, error on failure
#
# Example:
#   run_dir=$(artifacts_get_run_dir)
artifacts_get_run_dir() {
    # Check if session is initialized
    if ! session_is_initialized; then
        echo "ERROR: Session not initialized. Call session_init first." >&2
        return 1
    fi

    # Get session ID
    local session_id
    session_id=$(session_get_id)
    if [[ $? -ne 0 ]]; then
        return 1
    fi

    # Return the run directory path
    echo "${_ARTIFACTS_BASE_DIR}/${session_id}"
    return 0
}

# Get the directory for a specific task
# Returns: path to task directory (.curb/runs/{session-id}/tasks/{task-id})
#
# Args:
#   $1 - task_id: The task identifier (e.g., "curb-123")
#
# Returns:
#   Path to task directory on success, error on failure
#
# Example:
#   task_dir=$(artifacts_get_task_dir "curb-123")
artifacts_get_task_dir() {
    local task_id="$1"

    # Validate task_id
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    # Get run directory
    local run_dir
    run_dir=$(artifacts_get_run_dir)
    if [[ $? -ne 0 ]]; then
        return 1
    fi

    # Return the task directory path
    echo "${run_dir}/tasks/${task_id}"
    return 0
}

# Ensure artifact directory structure exists for a task
# Creates the full directory hierarchy with secure permissions (700)
#
# Args:
#   $1 - task_id: The task identifier (e.g., "curb-123")
#
# Returns:
#   0 on success, 1 on failure
#
# Example:
#   artifacts_ensure_dirs "curb-123"
artifacts_ensure_dirs() {
    local task_id="$1"

    # Validate task_id
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    # Get task directory path
    local task_dir
    task_dir=$(artifacts_get_task_dir "$task_id")
    if [[ $? -ne 0 ]]; then
        return 1
    fi

    # Create directory structure with secure permissions (700)
    # Using -p to create parent directories, -m to set permissions
    mkdir -p -m 700 "$task_dir"

    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to create directory: $task_dir" >&2
        return 1
    fi

    return 0
}

# Initialize run-level artifacts
# Creates the run directory and run.json with initial metadata
# Includes config snapshot from config_dump if available
#
# Returns:
#   0 on success, 1 on failure
#
# Example:
#   artifacts_init_run
artifacts_init_run() {
    # Check if session is initialized
    if ! session_is_initialized; then
        echo "ERROR: Session not initialized. Call session_init first." >&2
        return 1
    fi

    # Get run directory path
    local run_dir
    run_dir=$(artifacts_get_run_dir)
    if [[ $? -ne 0 ]]; then
        return 1
    fi

    # Create run directory with secure permissions (700)
    mkdir -p -m 700 "$run_dir"
    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to create run directory: $run_dir" >&2
        return 1
    fi

    # Get session metadata
    local run_id
    local session_name
    local started_at
    run_id=$(session_get_id)
    session_name=$(session_get_name)
    started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Get config snapshot if config.sh is available
    local config_snapshot="{}"
    if type config_dump &>/dev/null; then
        # Source config.sh if not already loaded
        if [[ -z "$(type -t config_dump)" ]]; then
            source "${SCRIPT_DIR}/config.sh" 2>/dev/null || true
        fi
        # Try to get config dump
        if type config_dump &>/dev/null; then
            config_snapshot=$(config_dump 2>/dev/null) || config_snapshot="{}"
        fi
    fi

    # Validate config_snapshot is valid JSON, fallback to empty object if not
    if ! echo "$config_snapshot" | jq empty 2>/dev/null; then
        config_snapshot="{}"
    fi

    # Create run.json using jq
    local run_json
    run_json=$(jq -n \
        --arg run_id "$run_id" \
        --arg session_name "$session_name" \
        --arg started_at "$started_at" \
        --arg status "in_progress" \
        --argjson config "$config_snapshot" \
        '{
            run_id: $run_id,
            session_name: $session_name,
            started_at: $started_at,
            status: $status,
            config: $config
        }')

    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to create run.json metadata" >&2
        return 1
    fi

    # Write run.json to file
    echo "$run_json" > "${run_dir}/run.json"
    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to write run.json to ${run_dir}/run.json" >&2
        return 1
    fi

    return 0
}

# Start a task and create task-level artifacts
# Creates the task directory and task.json with initial metadata
#
# Args:
#   $1 - task_id: The task identifier (e.g., "curb-123")
#   $2 - task_title: The task title/description
#   $3 - priority: Task priority (optional, defaults to "normal")
#
# Returns:
#   0 on success, 1 on failure
#
# Example:
#   artifacts_start_task "curb-123" "Implement feature X" "high"
artifacts_start_task() {
    local task_id="$1"
    local task_title="$2"
    local priority="${3:-normal}"

    # Validate required arguments
    if [[ -z "$task_id" ]]; then
        echo "ERROR: task_id is required" >&2
        return 1
    fi

    if [[ -z "$task_title" ]]; then
        echo "ERROR: task_title is required" >&2
        return 1
    fi

    # Ensure task directory exists
    artifacts_ensure_dirs "$task_id"
    if [[ $? -ne 0 ]]; then
        return 1
    fi

    # Get task directory path
    local task_dir
    task_dir=$(artifacts_get_task_dir "$task_id")
    if [[ $? -ne 0 ]]; then
        return 1
    fi

    # Get current timestamp in ISO 8601 format
    local started_at
    started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Create task.json using jq
    local task_json
    task_json=$(jq -n \
        --arg task_id "$task_id" \
        --arg title "$task_title" \
        --arg priority "$priority" \
        --arg status "in_progress" \
        --arg started_at "$started_at" \
        --argjson iterations 0 \
        '{
            task_id: $task_id,
            title: $title,
            priority: $priority,
            status: $status,
            started_at: $started_at,
            iterations: $iterations
        }')

    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to create task.json metadata" >&2
        return 1
    fi

    # Write task.json to file
    echo "$task_json" > "${task_dir}/task.json"
    if [[ $? -ne 0 ]]; then
        echo "ERROR: Failed to write task.json to ${task_dir}/task.json" >&2
        return 1
    fi

    return 0
}
