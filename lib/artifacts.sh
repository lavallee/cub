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
